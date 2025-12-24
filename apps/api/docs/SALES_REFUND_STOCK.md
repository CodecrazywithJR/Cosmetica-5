# Sales Refund with Stock Restoration (Layer 3 B)

**Implementado:** Diciembre 2025  
**Alcance:** Devolución automática de stock cuando una venta pagada se marca como reembolsada  
**Apps involucradas:** `apps.sales`, `apps.stock`, `apps.products`

---

## 📋 Resumen

Al marcar una venta como `refunded`, el sistema:
1. **Restaura stock automáticamente** creando movimientos REFUND_IN
2. **Revierte exactamente** los batches consumidos en el pago original (NO recalcula FEFO)
3. **Valida estado PAID** antes de permitir refund (impide refunds de ventas no pagadas)
4. **Idempotencia:** múltiples llamadas no duplican devoluciones
5. **Atomicidad:** todo o nada mediante transaction.atomic
6. **Trazabilidad:** cada REFUND_IN vinculado al SALE_OUT original via reversed_move FK

---

## 🔄 Flujo de Refund

### Diagrama de Secuencia

```
Usuario (Reception/ClinicalOps) → API → Sale.transition_to(REFUNDED)
                                              ↓
                                   Validación: status == PAID?
                                              ↓
                                   refund_stock_for_sale()
                                              ↓
                          ┌───────────────────┴────────────────────┐
                          ↓                                        ↓
                  Idempotency Check                    Get Original SALE_OUT Moves
                  (existing reversals?)                (sale=sale, quantity<0)
                          ↓                                        ↓
                        SKIP                            Create REFUND_IN Moves
                                                      (1:1 reversal, same batch)
                                                                   ↓
                                                       Link via reversed_move FK
                                                                   ↓
                                                       Update StockOnHand (+quantity)
                                                                   ↓
                                                              SUCCESS ✅
                                                              
                                Si falla ❌ → Rollback Sale status
```

### Paso a Paso

1. **Precondición:** Sale debe estar en estado `paid`

2. **Trigger:** Usuario llama `POST /api/sales/sales/{id}/transition/` con `new_status: "refunded"`

3. **Validación:** Sale.transition_to() verifica transición válida (`paid` → `refunded`)

4. **Restauración Automática:**
   ```python
   from apps.sales.services import refund_stock_for_sale
   
   try:
       refund_stock_for_sale(sale=self, created_by=user)
   except ValidationError:
       # Rollback: sale status NO cambia, refund_reason = null
       raise
   ```

5. **Algoritmo de Reversión (NO FEFO):**
   - Busca todos los StockMove OUT generados en el pago (`sale=sale, quantity<0`)
   - Para cada OUT move:
     - Crea REFUND_IN con **mismo** product, location, batch
     - Cantidad positiva = abs(cantidad_original)
     - Vincula vía `reversed_move = original_out_move`
   - Actualiza StockOnHand (+cantidad) para cada batch

6. **Trazabilidad:**
   - StockMove.reversed_move → StockMove original OUT
   - StockMove.sale → Sale refunded
   - StockMove.sale_line → SaleLine original
   - StockMove.reference_type = 'SaleRefund'
   - StockMove.created_by = usuario que ejecutó refund

7. **Respuesta API:**
   - **200 OK:** Sale marcada como refunded, stock restaurado
   - **400 Bad Request:** Sale no está en estado PAID, transición inválida

---

## 🔧 Arquitectura Técnica

### Modelos Modificados

#### StockMoveTypeChoices (apps/stock/models.py)
```python
class StockMoveTypeChoices(models.TextChoices):
    # IN movements
    PURCHASE_IN = 'purchase_in', _('Purchase In')
    ADJUSTMENT_IN = 'adjustment_in', _('Adjustment In')
    TRANSFER_IN = 'transfer_in', _('Transfer In')
    REFUND_IN = 'refund_in', _('Refund In')  # ← NUEVO (Layer 3 B)
    
    # OUT movements
    SALE_OUT = 'sale_out', _('Sale Out')
    ADJUSTMENT_OUT = 'adjustment_out', _('Adjustment Out')
    WASTE_OUT = 'waste_out', _('Waste Out')
    TRANSFER_OUT = 'transfer_out', _('Transfer Out')
```

#### StockMove (apps/stock/models.py)
```python
class StockMove(models.Model):
    # Campos existentes...
    sale = models.ForeignKey('sales.Sale', ...)
    sale_line = models.ForeignKey('sales.SaleLine', ...)
    
    # NUEVO CAMPO (Layer 3 B)
    reversed_move = models.OneToOneField(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reversal',
        verbose_name=_('Reversed Move'),
        help_text=_('For REFUND_IN moves: the original SALE_OUT move being reversed')
    )
    
    # Índice para queries rápidas
    class Meta:
        indexes = [
            ...,
            models.Index(fields=['reversed_move'], name='idx_stock_move_reversed'),
        ]
```

**Uso:**
```python
# Get original OUT move from refund IN
out_move = refund_move.reversed_move

# Get refund IN move from original OUT
refund_move = out_move.reversal  # OneToOne reverse relation

# Query all refund moves for a sale
refund_moves = StockMove.objects.filter(
    sale=sale,
    move_type=StockMoveTypeChoices.REFUND_IN
)
```

### Service Layer (apps/sales/services.py)

#### `refund_stock_for_sale(sale, created_by=None)`

**Propósito:** Restaurar stock automáticamente al marcar venta como refunded

**Características:**
- ✅ **Validación:** Sale debe estar en PAID (valida antes de procesar)
- ✅ **Idempotente:** Detecta refunds previos vía reversed_move FK
- ✅ **Atómico:** `@transaction.atomic` - todo o nada
- ✅ **Exacto:** Revierte batches específicos (NO recalcula FEFO)
- ✅ **Trazabilidad:** OneToOne link OUT ↔ IN

**Código simplificado:**
```python
@transaction.atomic
def refund_stock_for_sale(sale, created_by=None):
    # 1. Validación: debe estar PAID
    if sale.status != SaleStatusChoices.PAID:
        raise ValidationError(
            f"Cannot refund sale: sale must be paid. Current status: {sale.get_status_display()}"
        )
    
    # 2. Get original OUT moves
    out_moves = StockMove.objects.filter(
        sale=sale,
        move_type=StockMoveTypeChoices.SALE_OUT,
        quantity__lt=0
    )
    
    if not out_moves.exists():
        return []  # All services, nothing to refund
    
    # 3. Idempotency check
    existing_reversals = StockMove.objects.filter(
        reversed_move__in=out_moves
    ).exists()
    
    if existing_reversals:
        return list(StockMove.objects.filter(reversed_move__in=out_moves))
    
    # 4. Create 1:1 reversal moves
    refund_moves = []
    
    for out_move in out_moves:
        refund_move = StockMove(
            product=out_move.product,
            location=out_move.location,
            batch=out_move.batch,  # ← Same batch as original
            move_type=StockMoveTypeChoices.REFUND_IN,
            quantity=abs(out_move.quantity),  # Positive
            sale=sale,
            sale_line=out_move.sale_line,
            reversed_move=out_move,  # ← Link to original
            reference_type='SaleRefund',
            reference_id=str(sale.id),
            reason=f'Refund of sale {sale.sale_number} - {out_move.product.name}',
            created_by=created_by
        )
        refund_move.full_clean()
        refund_move.save()
        refund_moves.append(refund_move)
    
    # 5. Update StockOnHand
    for refund_move in refund_moves:
        stock, created = StockOnHand.objects.get_or_create(
            product=refund_move.product,
            location=refund_move.location,
            batch=refund_move.batch,
            defaults={'quantity_on_hand': 0}
        )
        stock.quantity_on_hand += refund_move.quantity
        stock.save()
    
    return refund_moves
```

**Excepciones:**
- `ValidationError`: Sale no está en PAID o estado inválido

---

## 🔐 Idempotencia y Atomicidad

### Idempotencia

**Problema:** ¿Qué pasa si se llama `transition_to(REFUNDED)` múltiples veces?

**Solución:**
```python
# En refund_stock_for_sale()
existing_reversals = StockMove.objects.filter(
    reversed_move__in=out_moves
).exists()

if existing_reversals:
    return list(StockMove.objects.filter(reversed_move__in=out_moves))
```

**Casos de uso:**
- Retry de API (network failure)
- Usuario hace doble-click en botón "Refund"
- Background job reinicia

**Garantía:** Siempre se devuelven las mismas unidades de stock, nunca duplicados.

**Constraint a nivel DB (futuro):**
```python
# En StockMove.Meta.constraints
models.UniqueConstraint(
    fields=['reversed_move'],
    condition=Q(reversed_move__isnull=False),
    name='unique_refund_per_out_move'
)
```

### Atomicidad

**Transaction Boundary:**
```python
@transaction.atomic
def refund_stock_for_sale(sale, created_by=None):
    # All DB operations here are atomic
    # If ANY fails, ALL rollback
```

**Rollback en Sale.transition_to():**
```python
elif new_status == SaleStatusChoices.REFUNDED:
    if reason:
        self.refund_reason = reason
    
    from apps.sales.services import refund_stock_for_sale
    try:
        refund_stock_for_sale(sale=self, created_by=user)
    except Exception as e:
        # ROLLBACK: revert status and reason
        self.status = old_status
        self.refund_reason = None
        raise  # Re-raise for ViewSet to handle

self.save()  # Only saves if NO exceptions
```

**Efecto:**
- Si `refund_stock_for_sale()` falla → Sale NO se marca como refunded
- `transaction.atomic` garantiza NO stock moves parciales
- Usuario recibe error claro

---

## 🛡️ Validaciones y Reglas de Negocio

### Estados Permitidos

| Estado Origen | Estado Destino | Permitido | Nota |
|---------------|----------------|-----------|------|
| `draft` | `refunded` | ❌ No | Sale nunca fue pagada |
| `pending` | `refunded` | ❌ No | Sale no está pagada aún |
| `paid` | `refunded` | ✅ Sí | **Única transición válida** |
| `cancelled` | `refunded` | ❌ No | Terminal state, no fue pagada |
| `refunded` | `refunded` | ❌ No | Ya refunded (terminal) |

### Validación en transition_to()

```python
# Sale.can_transition_to()
VALID_TRANSITIONS = {
    'draft': ['pending', 'cancelled'],
    'pending': ['paid', 'cancelled'],
    'paid': ['refunded'],  # ← Única salida de PAID
    'cancelled': [],  # Terminal
    'refunded': [],   # Terminal
}
```

### Mensajes de Error

**Sale no PAID:**
```json
{
  "error": "Cannot refund sale: sale must be paid. Current status: Pending"
}
```

**Transición inválida (draft → refunded):**
```json
{
  "error": "Invalid transition from draft to refunded. Valid transitions: pending, cancelled"
}
```

---

## 🔑 Permisos y Seguridad

### Matriz de Permisos

| Acción | Endpoint | Reception | ClinicalOps | Admin |
|--------|----------|-----------|-------------|-------|
| Marcar Sale como refunded (auto-restore) | `POST /api/sales/sales/{id}/transition/` | ✅ Sí | ✅ Sí | ✅ Sí |
| Ver StockMoves de refund | `GET /api/stock/moves/?sale={id}&move_type=refund_in` | ✅ Sí | ✅ Sí | ✅ Sí |
| Restaurar stock manual (sin sale) | `POST /api/stock/moves/adjust/` | ❌ No (403) | ✅ Sí | ✅ Sí |

### Separación de Responsabilidades

**Reception:**
- ✅ Puede refund ventas (trigger automático de restauración stock)
- ❌ NO puede manipular stock directamente (previene errores/fraude)
- Flujo guiado: solo transiciona estados, sistema maneja stock

**ClinicalOps/Admin:**
- ✅ Puede refund ventas
- ✅ Puede ajustar stock manualmente (casos excepcionales)
- Control total para auditorías

**Configuración en ViewSet (no cambios necesarios):**
```python
# apps/sales/views.py - SaleViewSet ya permite Reception
permission_classes = [IsAuthenticated]  # Reception está autenticado
```

---

## 🔍 Algoritmo de Reversión: NO FEFO

### Diferencia Clave vs. Consumo

**Consumo (Layer 3 A - PAID):**
- Usa FEFO: busca batches ordenados por `expiry_date ASC`
- Puede consumir de múltiples batches si el primero no tiene suficiente
- Prioriza minimizar desperdicio por expiración

**Reversión (Layer 3 B - REFUNDED):**
- **NO usa FEFO:** devuelve a los **mismos batches** consumidos originalmente
- 1:1 mapping: cada SALE_OUT → un REFUND_IN
- Mantiene trazabilidad exacta (audit trail)

### Ejemplo Práctico

**Setup:**
- Batch A: expira en 5 días, stock inicial = 10
- Batch B: expira en 60 días, stock inicial = 50

**Consumo (PAID):**
```python
# Sale requiere 15 unidades → FEFO
OUT 1: Batch A, -10 (todo batch A)
OUT 2: Batch B, -5  (resto de batch B)

# StockOnHand después:
Batch A: 0
Batch B: 45
```

**Reversión (REFUNDED):**
```python
# NO recalcula FEFO, revierte exactos:
IN 1: Batch A, +10 (reversed_move → OUT 1)
IN 2: Batch B, +5  (reversed_move → OUT 2)

# StockOnHand después:
Batch A: 10  ← Restaurado
Batch B: 50  ← Restaurado
```

**Justificación:**
1. **Trazabilidad:** Audit trail claro (qué se devolvió de dónde)
2. **Simplicidad:** No hay ambigüedad (siempre mismo batch)
3. **Consistencia:** StockOnHand vuelve a estado pre-venta exacto
4. **Performance:** No requiere recalcular FEFO ni queries complejas

---

## 📊 Trazabilidad: Consultas Útiles

### 1. Ver todos los refund moves de una venta

```python
from apps.sales.models import Sale
from apps.stock.models import StockMove, StockMoveTypeChoices

sale = Sale.objects.get(id='...')
refund_moves = sale.stock_moves.filter(move_type=StockMoveTypeChoices.REFUND_IN)

for move in refund_moves:
    print(f"Refund: {move.product.name}, Batch: {move.batch.batch_number}, Qty: +{move.quantity}")
    print(f"  Original OUT: {move.reversed_move.id}, Qty: {move.reversed_move.quantity}")
```

**SQL equivalente:**
```sql
SELECT 
    sm_refund.*,
    sm_out.id AS original_out_id,
    sm_out.quantity AS original_out_qty,
    sb.batch_number
FROM stock_moves sm_refund
JOIN stock_moves sm_out ON sm_refund.reversed_move_id = sm_out.id
JOIN stock_batches sb ON sm_refund.batch_id = sb.id
WHERE sm_refund.sale_id = '<sale_uuid>'
  AND sm_refund.move_type = 'refund_in';
```

### 2. Verificar si una venta ha sido refunded (stock-wise)

```python
from apps.stock.models import StockMove, StockMoveTypeChoices

sale = Sale.objects.get(id='...')

# Check if refund moves exist
has_refund = StockMove.objects.filter(
    sale=sale,
    move_type=StockMoveTypeChoices.REFUND_IN
).exists()

if has_refund:
    print("Sale has been refunded (stock restored)")
else:
    print("Sale not refunded or has no stock moves")
```

### 3. Auditoría: ¿Qué ventas han sido refunded hoy?

```python
from django.utils import timezone
from datetime import timedelta

today_start = timezone.now().replace(hour=0, minute=0, second=0)

refunded_today = Sale.objects.filter(
    status=SaleStatusChoices.REFUNDED,
    stock_moves__move_type=StockMoveTypeChoices.REFUND_IN,
    stock_moves__created_at__gte=today_start
).distinct()

for sale in refunded_today:
    print(f"Sale: {sale.sale_number}, Patient: {sale.patient}, Reason: {sale.refund_reason}")
```

### 4. Ver stock timeline de un batch (incluyendo refunds)

```python
from apps.stock.models import StockBatch, StockMove

batch = StockBatch.objects.get(batch_number='BATCH-A-001')
moves = batch.stock_moves.all().order_by('created_at')

for move in moves:
    direction = "IN" if move.quantity > 0 else "OUT"
    print(f"{move.created_at}: {direction} {abs(move.quantity)} - {move.get_move_type_display()}")
    if move.move_type == StockMoveTypeChoices.REFUND_IN:
        print(f"  ↳ Refund of sale: {move.sale.sale_number}")
```

---

## 🧪 Testing

### Test Suite: `tests/test_layer3_b_refund_stock.py`

**Cobertura (10 tests):**

1. ✅ **test_refund_paid_sale_creates_refund_in_moves_matching_batches**  
   Venta con consumo de 2 batches → refund crea 2 IN en mismos batches

2. ✅ **test_refund_sale_with_single_batch_consumption**  
   Consumo de 1 batch → refund crea 1 IN

3. ✅ **test_refund_draft_sale_raises_validation_error**  
   Draft → Refunded = ValidationError

4. ✅ **test_refund_pending_sale_raises_validation_error**  
   Pending → Refunded = ValidationError

5. ✅ **test_refund_cancelled_sale_raises_validation_error**  
   Cancelled → Refunded = ValidationError (terminal)

6. ✅ **test_repeated_refund_does_not_duplicate_refund_in_moves**  
   Llamar refund 2 veces → mismo resultado, no duplicados

7. ✅ **test_refund_rolls_back_if_error_during_processing**  
   Error durante refund → status NO cambia, 0 moves creados

8. ✅ **test_reception_user_can_refund_paid_sale_via_api**  
   Reception llama `/transition/` → 200 OK, stock restaurado

9. ✅ **test_stock_on_hand_restored_to_exact_pre_sale_levels**  
   Refund restaura StockOnHand a cantidades exactas pre-venta

10. ✅ **test_refund_sale_with_no_stock_moves_returns_empty_list**  
    Venta solo servicios → refund exitoso, 0 moves

### Ejecutar Tests

```bash
# Todos los tests de Layer 3 B
pytest apps/api/tests/test_layer3_b_refund_stock.py -v

# Test específico
pytest apps/api/tests/test_layer3_b_refund_stock.py::TestRefundCreatesMatchingReversalMoves::test_refund_paid_sale_creates_refund_in_moves_matching_batches -v

# Con coverage
pytest apps/api/tests/test_layer3_b_refund_stock.py --cov=apps.sales.services --cov=apps.sales.models --cov-report=html
```

---

## 🗄️ Migraciones

### Aplicadas

**stock.0003_add_refund_support** - Agregar REFUND_IN y reversed_move FK
```bash
python manage.py migrate stock
```

**Operaciones:**
1. AlterField: `move_type` - agregar 'refund_in' a choices
2. AddField: `reversed_move` - OneToOneField a self
3. AddIndex: `idx_stock_move_reversed`

**Nota:** Migración es **nullable y backward-compatible**, safe para producción.

---

## 🚧 Casos Borde y Limitaciones

### Casos Soportados

✅ **Refund total:** 100% del stock consumido se devuelve  
✅ **Múltiples batches:** Refund devuelve a todos los batches originales  
✅ **Ventas solo servicios:** Refund exitoso sin stock moves  
✅ **Refund idempotente:** Safe llamar múltiples veces  
✅ **Rollback en error:** Transacción atómica protege consistencia

### Limitaciones Actuales (No Soportadas)

❌ **Refund parcial:** No se puede refund solo algunos productos de la venta  
   - Solución futura: agregar parámetro `lines_to_refund` a `refund_stock_for_sale()`
   - Por ahora: crear nueva venta negativa (credit note) si se requiere parcial

❌ **Refund después de batch expirado:** Si batch consumido ya expiró cuando se hace refund  
   - Sistema igualmente devuelve a batch expirado (mantiene trazabilidad)
   - Requiere proceso manual posterior para waste/disposal

❌ **Refund después de transfer de batch:** Si batch fue transferido a otra location  
   - Sistema devuelve a location original (puede quedar desbalanceado)
   - Requiere ajuste manual o transfer reverso

❌ **Re-sale de producto refunded:** No hay validación si producto refunded se vuelve a vender inmediatamente  
   - Es válido desde perspectiva de stock (cantidad disponible)
   - Puede requerir business logic adicional (ej: inspección de producto)

### Casos Futuros (Roadmap)

**Layer 3 C: Refund Parcial**
- Permitir refund de líneas específicas de venta
- Validar que suma de refunds parciales no exceda original
- Constraint: `sum(refund_moves.quantity) <= sum(out_moves.quantity)` por producto

**Layer 3 D: Credit Notes**
- Crear Sale negativa vinculada a original
- Tracking de balance: venta original - credit notes
- Soporte para refund parcial sin modificar venta original

**Layer 3 E: Batch Expiry Handling**
- Warning si refund devuelve a batch próximo a expirar
- Auto-suggest: mover stock refunded a nuevo batch
- Integration con waste tracking

---

## 📚 Referencias

**Documentos relacionados:**
- `SALES_STOCK_INTEGRATION.md` (Layer 3 A) - Consumo automático en pago
- `LAYER2_A3_FEFO_STOCK.md` - Implementación de FEFO allocation
- `LAYER2_A2_SALES_INTEGRITY.md` - State machine de Sale
- `HARDENING_REPORT.md` - Technical debt y mejoras futuras

**Código clave:**
- `apps/sales/services.py` - refund_stock_for_sale, consume_stock_for_sale
- `apps/sales/models.py` - Sale.transition_to() con refund integration
- `apps/stock/models.py` - StockMove con reversed_move FK
- `apps/stock/migrations/0003_add_refund_support.py` - DB schema changes

---

## ✅ Checklist de Implementación

- [x] Model: REFUND_IN agregado a StockMoveTypeChoices
- [x] Model: reversed_move OneToOneField en StockMove
- [x] Migration: stock.0003_add_refund_support
- [x] Service: refund_stock_for_sale (idempotente, atómico, exacto)
- [x] Integration: Sale.transition_to(REFUNDED) llama refund_stock_for_sale
- [x] Validación: Sale debe estar PAID para refund
- [x] Rollback: status reverts si refund falla
- [x] Idempotency: reversed_move FK previene duplicados
- [x] Tests: 10 tests comprehensivos (reversiones, validaciones, idempotencia, permisos)
- [x] Documentation: SALES_REFUND_STOCK.md completo

**Status:** ✅ COMPLETO - Layer 3 B implementado y documentado

---

## 🎯 Endpoint y Estados

### Endpoint Utilizado

**POST** `/api/sales/sales/{sale_id}/transition/`

**Body:**
```json
{
  "new_status": "refunded",
  "reason": "Customer requested refund"
}
```

**Response 200 OK:**
```json
{
  "id": "uuid",
  "status": "refunded",
  "refund_reason": "Customer requested refund",
  "paid_at": "2025-12-15T10:30:00Z",
  "total": "3000.00"
}
```

**Response 400 Bad Request (not paid):**
```json
{
  "error": "Invalid transition from pending to refunded. Valid transitions: paid, cancelled"
}
```

### Estados Exactos

**Nombres de estados (SaleStatusChoices):**
- `draft` - Borrador inicial
- `pending` - Pendiente de pago
- `paid` - ✅ **Estado requerido para refund**
- `cancelled` - Cancelada (terminal)
- `refunded` - ✅ **Estado destino** (terminal)

**Transición implementada:** `paid` → `refunded`

---

**Última actualización:** Diciembre 2025  
**Autor:** GitHub Copilot (Claude Sonnet 4.5)  
**Tests:** 10/10 passing ✅
