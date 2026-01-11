# Sales-Stock Integration (Layer 3 A)

**Implementado:** Enero 2025  
**Alcance:** Consumo automático de stock FEFO cuando una venta se marca como pagada  
**Apps involucradas:** `apps.sales`, `apps.stock`, `apps.products`

---

## 📋 Resumen

Al marcar una venta como `paid`, el sistema:
1. **Consume stock automáticamente** usando FEFO (First Expired, First Out)
2. **Crea registros de StockMove** vinculados a la venta y líneas de venta
3. **Valida disponibilidad** antes de permitir el pago
4. **Rollback automático** si no hay stock suficiente (venta permanece `pending`)
5. **Idempotencia:** múltiples llamadas no duplican consumos

---

## 🔄 Flujo de Integración

### Diagrama de Secuencia

```
Usuario (Reception) → API → Sale.transition_to(PAID)
                                    ↓
                        consume_stock_for_sale()
                                    ↓
                        ┌───────────┴──────────┐
                        ↓                      ↓
              Idempotency Check        FEFO Allocation
              (existing moves?)      (create_stock_out_fefo)
                        ↓                      ↓
                      SKIP                StockMove(s)
                                              ↓
                                    Update StockOnHand
                                              ↓
                                    Link to Sale/SaleLine
                                              ↓
                                        SUCCESS ✅
                                              
                        Si falla ❌ → Rollback Sale status
```

### Paso a Paso

1. **Trigger:** Usuario llama `POST /api/sales/sales/{id}/transition/` con `new_status: "paid"`

2. **Validación:** Sale.transition_to() valida estado válido (`pending` → `paid`)

3. **Consumo Automático:**
   ```python
   from apps.sales.services import consume_stock_for_sale
   
   try:
       consume_stock_for_sale(sale=self, created_by=user)
   except InsufficientStockError:
       # Rollback: sale status NO cambia, paid_at = null
       raise
   ```

4. **FEFO Allocation:**
   - Para cada línea con `product != null` (productos, no servicios):
     - Busca batches en `MAIN-WAREHOUSE` ordenados por `expiry_date ASC`
     - Consume del batch más próximo a expirar
     - Si un batch no tiene suficiente, consume de múltiples batches

5. **Trazabilidad:**
   - StockMove.sale = Sale
   - StockMove.sale_line = SaleLine
   - StockMove.reference_type = 'Sale'
   - StockMove.reference_id = str(sale.id)
   - StockMove.created_by = usuario que cobró

6. **Respuesta API:**
   - **200 OK:** Sale marcada como paid, stock consumido
   - **400 Bad Request:** Stock insuficiente o batch expirado (error_type: 'insufficient_stock', 'expired_batch')

---

## 🔧 Arquitectura Técnica

### Modelos Modificados

#### SaleLine (apps/sales/models.py)
```python
class SaleLine(models.Model):
    # NUEVO CAMPO (nullable para servicios)
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sale_lines',
        help_text='Product if product sale, null for service/custom line'
    )
    
    # Campos existentes
    product_name = models.CharField(max_length=255)
    product_code = models.CharField(max_length=100, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    ...
```

**Lógica:**
- **Productos:** `product != null` → consume stock
- **Servicios:** `product == null` → NO consume stock (ej: consultas, tratamientos)

#### StockMove (apps/stock/models.py)
```python
class StockMove(models.Model):
    # NUEVOS CAMPOS (nullable para movimientos no-sale)
    sale = models.ForeignKey(
        'sales.Sale',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_moves'
    )
    sale_line = models.ForeignKey(
        'sales.SaleLine',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_moves'
    )
    
    # Campos existentes
    reference_type = models.CharField(max_length=50)  # 'Sale', 'Adjustment', etc.
    reference_id = models.CharField(max_length=255)
    move_type = models.CharField(...)  # SALE_OUT
    ...
```

**Trazabilidad Dual:**
1. **FK directas:** `sale`, `sale_line` → queryable (`sale.stock_moves.all()`)
2. **Generic fields:** `reference_type`, `reference_id` → flexibilidad (ajustes, transfers, etc.)

### Service Layer (apps/sales/services.py)

#### `consume_stock_for_sale(sale, location=None, created_by=None)`

**Propósito:** Consumir stock automáticamente al marcar venta como pagada

**Características:**
- ✅ **Idempotente:** Detecta si ya se consumió stock para evitar duplicados
- ✅ **Atómico:** `@transaction.atomic` - todo o nada
- ✅ **FEFO:** Usa `create_stock_out_fefo()` de Layer 2 A3
- ✅ **Trazabilidad:** Vincula StockMoves a Sale y SaleLine

**Código simplificado:**
```python
@transaction.atomic
def consume_stock_for_sale(sale, location=None, created_by=None):
    # 1. Idempotency check
    existing_moves = StockMove.objects.filter(sale=sale)
    if existing_moves.exists():
        return list(existing_moves)  # Ya consumido, retornar existentes
    
    # 2. Default location
    if location is None:
        location = get_default_stock_location()  # MAIN-WAREHOUSE
    
    # 3. Get product lines (skip services)
    product_lines = sale.lines.filter(product__isnull=False)
    if not product_lines.exists():
        return []  # Solo servicios, nada que consumir
    
    # 4. FEFO consumption per line
    moves = []
    for line in product_lines:
        line_moves = create_stock_out_fefo(
            product=line.product,
            location=location,
            quantity=int(line.quantity),
            move_type=StockMoveTypeChoices.SALE_OUT,
            reference_type='Sale',
            reference_id=str(sale.id),
            reason=f'Sale {sale.sale_number} - {line.product_name}',
            created_by=created_by,
            allow_expired=False  # ❌ No permitir batches expirados
        )
        
        # 5. Link moves to sale/sale_line
        for move in line_moves:
            move.sale = sale
            move.sale_line = line
            move.save(update_fields=['sale', 'sale_line'])
        
        moves.extend(line_moves)
    
    return moves
```

**Excepciones:**
- `InsufficientStockError`: No hay stock suficiente (mensaje incluye producto, cantidad requerida, disponible)
- `ExpiredBatchError`: Solo hay batches expirados disponibles
- `ValidationError`: Location inactiva, producto inválido, etc.

#### `check_stock_availability_for_sale(sale, location=None)`

**Propósito:** Verificar disponibilidad sin consumir (non-destructive check)

**Retorno:**
```python
{
    'available': True/False,
    'lines': [
        {
            'sale_line_id': uuid,
            'product_sku': 'BOTOX-50U',
            'required': 10,
            'available': 8,
            'status': 'insufficient' / 'ok'
        },
        ...
    ],
    'errors': ['Insufficient stock for BOTOX-50U: need 10, have 8']
}
```

**Uso:**
```python
from apps.sales.services import check_stock_availability_for_sale

availability = check_stock_availability_for_sale(sale)
if not availability['available']:
    # Mostrar errores al usuario antes de intentar cobrar
    print(availability['errors'])
```

---

## 🔐 Idempotencia y Concurrencia

### Idempotencia

**Problema:** ¿Qué pasa si se llama `transition_to(PAID)` múltiples veces?

**Solución:**
```python
# En consume_stock_for_sale()
existing_moves = StockMove.objects.filter(sale=sale)
if existing_moves.exists():
    return list(existing_moves)  # Ya consumido
```

**Casos de uso:**
- Retry de API (network failure)
- Usuario hace doble-click en botón "Cobrar"
- Background job reinicia

**Garantía:** Siempre se consumen las mismas unidades de stock, nunca duplicados.

### Concurrencia (Futuro - Layer 3 B)

**Actualmente:** No hay `select_for_update()` en StockOnHand

**Riesgo:** Race condition si dos ventas intentan consumir el último stock simultáneamente

**Solución futura:**
```python
# En create_stock_out_fefo() (Layer 2 A3)
batches = StockBatch.objects.filter(
    product=product,
    expiry_date__gte=today
).select_for_update()  # ← Lock pesimista

stock = StockOnHand.objects.filter(
    batch__in=batches,
    location=location
).select_for_update()  # ← Lock rows hasta commit
```

**Por ahora:** Riesgo bajo si volumen de ventas concurrentes es bajo.

---

## 🛡️ Manejo de Errores

### Rollback Automático en Sale.transition_to()

```python
# apps/sales/models.py
def transition_to(self, new_status, reason='', user=None):
    old_status = self.status
    
    # ... validations ...
    
    self.status = new_status
    
    if new_status == SaleStatusChoices.PAID:
        from django.utils import timezone
        self.paid_at = timezone.now()
        
        # Consumir stock (puede fallar)
        from apps.sales.services import consume_stock_for_sale
        try:
            consume_stock_for_sale(sale=self, created_by=user)
        except Exception as e:
            # ROLLBACK: revertir status y paid_at
            self.status = old_status
            self.paid_at = None
            raise  # Re-raise para que ViewSet maneje error
    
    self.save()  # Solo guarda si NO hubo excepciones
```

**Efecto:**
- Si `consume_stock_for_sale()` falla → Sale NO se marca como paid
- `transaction.atomic` de `consume_stock_for_sale` garantiza NO stock moves creados
- Usuario recibe error claro con detalles de qué producto falta

### Mensajes de Error en API

```python
# apps/sales/views.py
from apps.stock.services import InsufficientStockError, ExpiredBatchError

@action(methods=['post'], detail=True)
def transition(self, request, pk=None):
    try:
        sale.transition_to(new_status, user=request.user)
        return Response({'status': 'ok'}, status=200)
    
    except InsufficientStockError as e:
        return Response({
            'error': str(e),
            'error_type': 'insufficient_stock',
            'message': 'Cannot mark sale as paid: insufficient stock for one or more products'
        }, status=400)
    
    except ExpiredBatchError as e:
        return Response({
            'error': str(e),
            'error_type': 'expired_batch',
            'message': 'Cannot mark sale as paid: only expired stock available'
        }, status=400)
```

**Respuesta 400 Bad Request:**
```json
{
  "error": "Insufficient stock for BOTOX-50U: requested 10, available 3",
  "error_type": "insufficient_stock",
  "message": "Cannot mark sale as paid: insufficient stock for one or more products"
}
```

---

## 🔑 Permisos y Seguridad

### Matriz de Permisos

| Acción | Endpoint | Reception | ClinicalOps | Admin |
|--------|----------|-----------|-------------|-------|
| Marcar Sale como paid (auto-consume) | `POST /api/sales/sales/{id}/transition/` | ✅ Sí | ✅ Sí | ✅ Sí |
| Consumir stock manual FEFO | `POST /api/stock/moves/consume-fefo/` | ❌ No (403) | ✅ Sí | ✅ Sí |
| Ajustar stock manual | `POST /api/stock/moves/adjust/` | ❌ No (403) | ✅ Sí | ✅ Sí |
| Ver StockMoves de una venta | `GET /api/stock/moves/?sale={id}` | ✅ Sí | ✅ Sí | ✅ Sí |

### Separación de Responsabilidades

**Reception:**
- ✅ Puede cobrar ventas (trigger automático de consumo stock)
- ❌ NO puede manipular stock directamente (previene errores/fraude)

**ClinicalOps:**
- ✅ Puede cobrar ventas
- ✅ Puede consumir stock manualmente (ajustes, casos especiales)
- ✅ Gestión completa de inventario

**Justificación:**
- Reception: enfocado en atención al cliente, proceso guiado (menos errores)
- ClinicalOps: control total para manejo de excepciones y auditorías

---

## 📍 Política de Ubicación (Location)

### Default: MAIN-WAREHOUSE

```python
DEFAULT_STOCK_LOCATION_CODE = 'MAIN-WAREHOUSE'

def get_default_stock_location():
    try:
        return StockLocation.objects.get(
            code=DEFAULT_STOCK_LOCATION_CODE,
            is_active=True
        )
    except StockLocation.DoesNotExist:
        raise ValidationError(
            f"Default stock location '{DEFAULT_STOCK_LOCATION_CODE}' not found or inactive"
        )
```

**Criterio:**
- Todas las ventas consumen de `MAIN-WAREHOUSE` por defecto
- Simplifica operaciones (una sola ubicación para POS)
- Futuro: multi-location si abre sucursales

### Override Manual (API directa)

```python
# Ejemplo: consumir de ubicación específica
from apps.sales.services import consume_stock_for_sale

custom_location = StockLocation.objects.get(code='BRANCH-NORTE')
consume_stock_for_sale(sale, location=custom_location, created_by=user)
```

**Uso:** Solo para casos especiales (ajustes manuales, transfers)

---

## 🧪 Testing

### Test Suite: `tests/test_layer3_a_sales_stock.py`

**Cobertura (9 tests):**

1. ✅ **test_sale_paid_consumes_stock_fefo_allocation**  
   Verifica que se consume del batch más próximo a expirar

2. ✅ **test_sale_paid_consumes_from_multiple_batches_when_needed**  
   Si un batch no tiene suficiente, consume de múltiples (FEFO order)

3. ✅ **test_sale_with_service_lines_skips_stock_consumption**  
   Líneas sin `product` FK (servicios) no consumen stock

4. ✅ **test_sale_paid_fails_without_sufficient_stock**  
   InsufficientStockError, status NO cambia, 0 StockMoves creados

5. ✅ **test_sale_paid_fails_without_any_stock**  
   Mismo comportamiento cuando no hay stock en absoluto

6. ✅ **test_repeated_transition_to_paid_does_not_duplicate_stock_consumption**  
   Idempotencia: llamar `consume_stock_for_sale()` 2 veces retorna mismos moves

7. ✅ **test_reception_user_can_transition_sale_to_paid_via_api**  
   Reception llama `/transition/` con `new_status=paid` → 200 OK, stock consumido

8. ✅ **test_reception_user_cannot_consume_fefo_endpoint**  
   Reception llama `/stock/moves/consume-fefo/` → 403 Forbidden

9. ✅ **test_clinicalops_user_can_consume_fefo_endpoint**  
   ClinicalOps llama `/stock/moves/consume-fefo/` → 201 Created

### Ejecutar Tests

```bash
# Todos los tests de Layer 3 A
pytest apps/api/tests/test_layer3_a_sales_stock.py -v

# Test específico
pytest apps/api/tests/test_layer3_a_sales_stock.py::TestSalePaidConsumesStockFEFO::test_sale_paid_consumes_stock_fefo_allocation -v

# Con coverage
pytest apps/api/tests/test_layer3_a_sales_stock.py --cov=apps.sales.services --cov=apps.sales.models --cov-report=html
```

---

## 🗄️ Migraciones

### Orden de Aplicación

1. **products.0001_initial** - Crear modelo Product
   ```bash
   python manage.py migrate products
   ```

2. **sales.0002_add_product_fk_for_stock_integration** - Agregar FK `product` a SaleLine
   ```bash
   python manage.py migrate sales
   ```

3. **stock.0002_add_sale_fks_for_integration** - Agregar FKs `sale`, `sale_line` a StockMove
   ```bash
   python manage.py migrate stock
   ```

### Aplicar Todas

```bash
# Desde apps/api/
python manage.py migrate
```

**Nota:** Las migraciones son **nullables**, safe para ejecutar en producción (no rompe datos existentes)

---

## 📊 Trazabilidad: Consultas Útiles

### 1. Ver todos los StockMoves de una venta

```python
from apps.sales.models import Sale
from apps.stock.models import StockMove

sale = Sale.objects.get(id='...')
moves = sale.stock_moves.all()

for move in moves:
    print(f"Batch: {move.batch.batch_number}, Qty: {move.quantity}, Line: {move.sale_line.product_name}")
```

**SQL equivalente:**
```sql
SELECT sm.*, sb.batch_number, sl.product_name
FROM stock_moves sm
JOIN stock_batches sb ON sm.batch_id = sb.id
JOIN sale_lines sl ON sm.sale_line_id = sl.id
WHERE sm.sale_id = '<sale_uuid>';
```

### 2. Ver todas las ventas que consumieron un batch

```python
from apps.stock.models import StockBatch

batch = StockBatch.objects.get(batch_number='BATCH-001')
sales = Sale.objects.filter(stock_moves__batch=batch).distinct()
```

### 3. Auditoría: ¿Quién consumió stock de este producto?

```python
from apps.products.models import Product

product = Product.objects.get(sku='BOTOX-50U')
moves = StockMove.objects.filter(
    product=product,
    move_type=StockMoveTypeChoices.SALE_OUT
).select_related('sale', 'created_by')

for move in moves:
    print(f"Sale: {move.sale.sale_number}, User: {move.created_by.email}, Qty: {abs(move.quantity)}")
```

---

## 🚀 Próximos Pasos (Roadmap)

### Layer 3 B: Concurrencia y Locks
- [ ] Agregar `select_for_update()` en create_stock_out_fefo
- [ ] Tests de race conditions (múltiples ventas simultáneas)
- [ ] Deadlock detection y retry logic

### Layer 3 C: Multi-Location Sales
- [ ] Permitir vender desde `BRANCH-NORTE`, `BRANCH-SUR`, etc.
- [ ] API: agregar `location` opcional en Sale model
- [ ] Auto-detect location basado en usuario/terminal POS

### Layer 3 D: Reservas de Stock
- [ ] Sale en estado `pending` reserva stock (no lo consume)
- [ ] Timeout de reservas (liberar si no se paga en X horas)
- [ ] StockReservation model

### Layer 3 E: Refunds
- [ ] `Sale.transition_to(REFUNDED)` reversa stock consumption
- [ ] Crear StockMove IN vinculados a refund
- [ ] Políticas: ¿devolver a mismo batch o crear nuevo?

---

## 📚 Referencias

**Documentos relacionados:**
- `HARDENING_REPORT.md` - Identificó la falta de FK Product→SaleLine como technical debt
- `LAYER2_A3_FEFO_STOCK.md` - Implementación de `create_stock_out_fefo()`
- `LAYER2_A2_SALES_INTEGRITY.md` - State machine de Sale (draft→pending→paid)
- `PUBLIC_API_THROTTLING.md` - Rate limiting para endpoints públicos (Layer 2 B)

**Código clave:**
- `apps/sales/services.py` - consume_stock_for_sale, check_stock_availability_for_sale
- `apps/sales/models.py` - Sale.transition_to() integration
- `apps/stock/services.py` - create_stock_out_fefo, InsufficientStockError
- `apps/sales/views.py` - SaleViewSet.transition error handling

---

## ✅ Checklist de Implementación

- [x] Migration: product FK en SaleLine (nullable)
- [x] Migration: sale/sale_line FKs en StockMove (nullable)
- [x] Service: consume_stock_for_sale (idempotente, atómico, FEFO)
- [x] Service: check_stock_availability_for_sale (non-destructive)
- [x] Integration: Sale.transition_to(PAID) llama consume_stock_for_sale
- [x] Error handling: InsufficientStockError/ExpiredBatchError en ViewSet
- [x] Rollback: status reverts si stock consumption falla
- [x] Tests: 9 tests comprehensivos (FEFO, errors, idempotency, permissions)
- [x] Documentation: SALES_STOCK_INTEGRATION.md

**Status:** ✅ COMPLETO - Layer 3 A implementado y documentado

---

**Última actualización:** Enero 2025  
**Autor:** GitHub Copilot (Claude Sonnet 4.5)  
**Revisión:** Pendiente validación manual del flujo end-to-end
