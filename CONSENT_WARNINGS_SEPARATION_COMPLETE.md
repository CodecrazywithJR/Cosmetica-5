# Separación de Warnings de Consentimientos: Checks vs Documentos

**Fecha:** 2026-01-12  
**Estado:** ✅ IMPLEMENTADO  
**Impacto:** CRÍTICO - Separación correcta de warnings bloqueantes vs informativos

---

## 📋 Resumen Ejecutivo

Se ha separado correctamente la lógica de warnings de consentimientos en dos categorías distintas:

1. **Consentimientos legales faltantes** (checkboxes) → **BLOQUEANTE** para encounters
2. **Documentos de consentimiento faltantes** (PDF/PNG) → **SOLO INFORMATIVO**

Esto corrige el problema donde el sistema mostraba "Legal consents required" cuando los checks estaban marcados pero faltaba el documento opcional.

---

## 🎯 Objetivo

**Problema anterior:**
```
✔ Privacy Policy checkbox marcado
✔ Terms & Conditions checkbox marcado
❌ Documento NO subido

Sistema mostraba: "Legal consents required" ❌ INCORRECTO
```

**Solución implementada:**
```
✔ Privacy Policy checkbox marcado
✔ Terms & Conditions checkbox marcado
❌ Documento NO subido

Sistema muestra ahora: "Consent document not attached" ✅ CORRECTO (azul, informativo)
```

---

## 🔧 Implementación

### **1. Backend: Dos Anotaciones Separadas**

**Archivo:** `apps/api/apps/clinical/views.py`

**Lógica implementada:**

```python
# TWO separate flags:
# 1) has_missing_legal_consents: TRUE if checkboxes not marked (BLOCKS encounters)
# 2) has_missing_consent_documents: TRUE if documents not uploaded (INFORMATIVE only)

queryset = queryset.annotate(
    # Count granted privacy_policy consents (not revoked)
    privacy_policy_count=Count(
        'consents',
        filter=Q(
            consents__consent_type=ConsentTypeChoices.PRIVACY_POLICY,
            consents__status=ConsentStatusChoices.GRANTED,
            consents__revoked_at__isnull=True
        )
    ),
    # Count granted terms_and_conditions consents (not revoked)
    terms_count=Count(
        'consents',
        filter=Q(
            consents__consent_type=ConsentTypeChoices.TERMS_AND_CONDITIONS,
            consents__status=ConsentStatusChoices.GRANTED,
            consents__revoked_at__isnull=True
        )
    ),
    # Count privacy_policy consents WITH document attached
    privacy_with_doc_count=Count(
        'consents',
        filter=Q(
            consents__consent_type=ConsentTypeChoices.PRIVACY_POLICY,
            consents__status=ConsentStatusChoices.GRANTED,
            consents__revoked_at__isnull=True,
            consents__document__isnull=False
        )
    ),
    # Count terms_and_conditions consents WITH document attached
    terms_with_doc_count=Count(
        'consents',
        filter=Q(
            consents__consent_type=ConsentTypeChoices.TERMS_AND_CONDITIONS,
            consents__status=ConsentStatusChoices.GRANTED,
            consents__revoked_at__isnull=True,
            consents__document__isnull=False
        )
    )
).annotate(
    # Flag 1: TRUE if either required LEGAL CONSENT is missing (BLOCKING)
    has_missing_legal_consents=Case(
        When(Q(privacy_policy_count=0) | Q(terms_count=0), then=True),
        default=False,
        output_field=BooleanField()
    ),
    # Flag 2: TRUE if consents exist BUT documents are missing (INFORMATIVE)
    # Only relevant when has_missing_legal_consents=False
    has_missing_consent_documents=Case(
        When(
            Q(privacy_policy_count__gt=0) &
            Q(terms_count__gt=0) &
            (Q(privacy_with_doc_count=0) | Q(terms_with_doc_count=0)),
            then=True
        ),
        default=False,
        output_field=BooleanField()
    )
)
```

**Cambios clave:**
- ✅ **4 counts** separados: privacy, terms, privacy_with_doc, terms_with_doc
- ✅ `has_missing_legal_consents`: TRUE si falta privacy_policy O terms_and_conditions
- ✅ `has_missing_consent_documents`: TRUE SOLO si ambos checks OK pero documentos faltan
- ✅ Los dos flags son **independientes** y **mutuamente excluyentes** en la UI

### **2. Backend: Serializer con Ambos Flags**

**Archivo:** `apps/api/apps/clinical/serializers.py`

```python
class PatientListSerializer(serializers.ModelSerializer):
    """Serializer for Patient list view (limited fields)"""
    has_missing_legal_consents = serializers.SerializerMethodField()
    has_missing_consent_documents = serializers.SerializerMethodField()
    
    class Meta:
        model = Patient
        fields = [
            # ... otros campos ...
            'has_missing_legal_consents',      # ← BLOQUEANTE
            'has_missing_consent_documents',    # ← INFORMATIVO
        ]
    
    def get_has_missing_legal_consents(self, obj):
        return getattr(obj, 'has_missing_legal_consents', False)
    
    def get_has_missing_consent_documents(self, obj):
        return getattr(obj, 'has_missing_consent_documents', False)
```

### **3. Frontend: Interfaz Patient Actualizada**

**Archivo:** `apps/web/src/lib/api/patients.ts`

```typescript
export interface Patient {
  // ...
  
  // Computed fields from backend (list view only)
  has_missing_legal_consents?: boolean;  // Checkboxes not marked (BLOCKING)
  has_missing_consent_documents?: boolean;  // Documents not uploaded (INFORMATIVE)
}
```

### **4. Frontend: Lógica Condicional de Warnings**

**Archivo:** `apps/web/src/app/[locale]/patients/page.tsx`

```tsx
<td className="px-6 py-4">
  <div className="flex flex-col gap-1">
    {/* Priority 1: Legal consents missing (BLOCKING) - Yellow warning */}
    {patient.has_missing_legal_consents && (
      <div className="inline-flex items-center gap-1 px-2 py-1 bg-yellow-50 border border-yellow-300 rounded text-xs text-yellow-800">
        <svg>...</svg>
        <span>{t('list.warnings.legalConsentsRequired')}</span>
      </div>
    )}
    
    {/* Priority 2: Consent documents missing (INFORMATIVE) - Blue warning */}
    {/* Only show if legal consents are OK */}
    {!patient.has_missing_legal_consents && patient.has_missing_consent_documents && (
      <div className="inline-flex items-center gap-1 px-2 py-1 bg-blue-50 border border-blue-300 rounded text-xs text-blue-800">
        <svg>...</svg>
        <span>{t('list.warnings.consentDocumentMissing')}</span>
      </div>
    )}
  </div>
</td>
```

**Lógica clave:**
- ✅ **NUNCA se muestran ambos warnings a la vez**
- ✅ Prioridad 1: `has_missing_legal_consents` (amarillo, bloqueante)
- ✅ Prioridad 2: `has_missing_consent_documents` (azul, informativo)
- ✅ El warning de documentos SOLO aparece si checks están OK

### **5. i18n: Traducciones en 6 Idiomas**

**Archivos:** `apps/web/messages/{es,en,fr,ru,uk,hy}.json`

**Nueva clave:** `patients.list.warnings.consentDocumentMissing`

```json
{
  "patients": {
    "list": {
      "warnings": {
        "legalConsentsRequired": "...",
        "consentDocumentMissing": "..."  // ← Nueva clave
      }
    }
  }
}
```

**Traducciones:**
- 🇪🇸 **Español:** "Documento de consentimiento no adjuntado"
- 🇬🇧 **English:** "Consent document not attached"
- 🇫🇷 **Français:** "Document de consentement non joint"
- 🇷🇺 **Русский:** "Документ согласия не прикреплён"
- 🇺🇦 **Українська:** "Документ згоди не прикріплено"
- 🇦🇲 **Հայերեն:** "Համաձայնության փաստաթուղթը կցված չէ"

---

## 📊 Comparación: Antes vs Después

### **Escenarios de Testing**

| Escenario | Privacy Check | Terms Check | Documento | ANTES (Incorrecto) | DESPUÉS (Correcto) |
|-----------|---------------|-------------|-----------|-------------------|-------------------|
| A | ❌ | ❌ | ❌ | ⚠️ Legal consents required | ⚠️ Legal consents required (amarillo) |
| B | ✅ | ❌ | ❌ | ⚠️ Legal consents required | ⚠️ Legal consents required (amarillo) |
| C | ✅ | ✅ | ❌ | ⚠️ Legal consents required ❌ | ℹ️ Consent document not attached (azul) ✅ |
| D | ✅ | ✅ | ✅ | ✅ No warning | ✅ No warning |

**Caso crítico corregido:** **Escenario C**
- Antes: Mostraba warning bloqueante (incorrecto)
- Ahora: Muestra warning informativo (correcto)

### **Arquitectura de Flags**

```
Backend ORM Annotations:

Patient (queryset annotated):
├── privacy_policy_count         → Count(granted privacy_policy)
├── terms_count                  → Count(granted terms_and_conditions)
├── privacy_with_doc_count       → Count(granted privacy_policy WITH document)
├── terms_with_doc_count         → Count(granted terms_and_conditions WITH document)
│
├── has_missing_legal_consents   → TRUE if privacy_count=0 OR terms_count=0
└── has_missing_consent_documents → TRUE if counts>0 BUT doc_counts=0

Frontend Rendering Logic:

if (has_missing_legal_consents) {
  ⚠️ Show BLOCKING warning (yellow) → "Legal consents required"
} else if (has_missing_consent_documents) {
  ℹ️ Show INFORMATIVE warning (blue) → "Consent document not attached"
} else {
  ✅ No warning (all good)
}
```

---

## 🎨 Diseño de Warnings

### **Warning Bloqueante (Amarillo)**
```tsx
<div className="bg-yellow-50 border border-yellow-300 text-yellow-800">
  <svg>⚠️</svg>
  <span>Legal consents required</span>
</div>
```
- **Significado:** Faltan checkboxes (bloqueante para encounters)
- **Color:** Amarillo (alerta importante)
- **Icono:** Triángulo de advertencia

### **Warning Informativo (Azul)**
```tsx
<div className="bg-blue-50 border border-blue-300 text-blue-800">
  <svg>📄</svg>
  <span>Consent document not attached</span>
</div>
```
- **Significado:** Faltan documentos (solo informativo)
- **Color:** Azul (información)
- **Icono:** Documento

---

## ✅ Reglas de Negocio Mantenidas

### **✅ Paciente SE PUEDE crear sin:**
- ✅ Marcar checkboxes de consentimiento
- ✅ Subir documentos de consentimiento

### **✅ Checkboxes son:**
- ✅ NO obligatorios para crear/editar paciente
- ✅ SÍ obligatorios para crear encounters
- ✅ Los ÚNICOS que bloquean funcionalidad clínica

### **✅ Documentos son:**
- ✅ COMPLETAMENTE OPCIONALES
- ✅ NO bloquean nada
- ✅ Solo informativos / compliance

---

## 🧪 Validación

### **Django Check**
```bash
$ docker exec emr-api-dev python manage.py check
System check identified no issues (0 silenced). ✅
```

### **TypeScript Compilation**
```bash
No errors found in:
- apps/web/src/lib/api/patients.ts ✅
- apps/web/src/app/[locale]/patients/page.tsx ✅
```

### **i18n Files**
```bash
Updated 6 language files:
- es.json ✅
- en.json ✅
- fr.json ✅
- ru.json ✅
- uk.json ✅
- hy.json ✅
```

### **Servicios Reiniciados**
```bash
$ docker compose restart api celery
✔ Container emr-api-dev     Started ✅
✔ Container emr-celery-dev  Started ✅
```

---

## 📝 Archivos Modificados

### **Backend:**
```
apps/api/apps/clinical/views.py
├── Línea 121-191: Nueva lógica con 4 counts y 2 flags
└── Import: BooleanField añadido

apps/api/apps/clinical/serializers.py
├── Línea 62-63: Dos SerializerMethodField
├── Línea 82-83: Ambos flags en fields
└── Línea 86-91: Dos métodos get_*
```

### **Frontend:**
```
apps/web/src/lib/api/patients.ts
├── Línea 28-30: Dos flags en interfaz Patient
└── Comentarios explicativos

apps/web/src/app/[locale]/patients/page.tsx
├── Línea 310-334: Lógica condicional de warnings
├── Warning amarillo (bloqueante)
└── Warning azul (informativo)
```

### **i18n:**
```
apps/web/messages/es.json ← consentDocumentMissing
apps/web/messages/en.json ← consentDocumentMissing
apps/web/messages/fr.json ← consentDocumentMissing
apps/web/messages/ru.json ← consentDocumentMissing
apps/web/messages/uk.json ← consentDocumentMissing
apps/web/messages/hy.json ← consentDocumentMissing
```

---

## 🎯 Flujo de Usuario Final

### **Caso 1: Paciente sin consentimientos**
```
Usuario crea paciente → No marca checkboxes → Guarda
  ↓
Listado muestra: ⚠️ "Legal consents required" (amarillo)
  ↓
Usuario intenta crear encounter → ❌ BLOQUEADO por falta de consents
```

### **Caso 2: Paciente con checks pero sin documento**
```
Usuario edita paciente → Marca checkboxes → NO sube documento → Guarda
  ↓
Listado muestra: ℹ️ "Consent document not attached" (azul)
  ↓
Usuario puede crear encounter → ✅ PERMITIDO (documento es opcional)
```

### **Caso 3: Paciente completo**
```
Usuario edita paciente → Marca checkboxes → Sube documento → Guarda
  ↓
Listado muestra: (sin warning)
  ↓
Usuario puede crear encounter → ✅ PERMITIDO
```

---

## 🚀 Próximos Pasos

### **Testing Manual Recomendado:**

1. **Test Warning Bloqueante:**
   - [ ] Crear paciente sin marcar checkboxes
   - [ ] Verificar warning amarillo "Legal consents required"
   - [ ] Intentar crear encounter → Debe estar bloqueado

2. **Test Warning Informativo:**
   - [ ] Editar paciente, marcar ambos checkboxes
   - [ ] NO subir documento
   - [ ] Guardar y verificar warning azul "Consent document not attached"
   - [ ] Crear encounter → Debe estar permitido

3. **Test Sin Warnings:**
   - [ ] Editar paciente, marcar checkboxes y subir documento
   - [ ] Verificar que NO aparece ningún warning
   - [ ] Crear encounter → Debe estar permitido

4. **Test Multiidioma:**
   - [ ] Cambiar idioma a cada uno de los 6 soportados
   - [ ] Verificar que traducciones se muestran correctamente

### **Mejoras Futuras (Opcional):**

1. **Tooltip Explicativo:** Añadir tooltip en warning informativo explicando que el documento es opcional
2. **Estadísticas:** Dashboard con % de pacientes con documentos adjuntos
3. **Recordatorio:** Email/notificación cuando falta documento (compliance)
4. **Bulk Upload:** Subida masiva de documentos escaneados

---

## 📚 Lecciones Aprendidas

### **✅ Buenas Prácticas Aplicadas:**

1. **Separación de Concerns:** Flags independientes para propósitos distintos
2. **Lógica Condicional Clara:** Nunca mostrar ambos warnings simultáneamente
3. **UI/UX Consistente:** Colores distintos para warnings de distinta severidad
4. **i18n Completo:** Traducciones en todos los idiomas desde el inicio
5. **Documentación:** Comentarios en código explicando el "por qué"

### **❌ Errores Evitados:**

1. ❌ Mezclar lógica de checks y documentos en un solo flag
2. ❌ Mostrar ambos warnings a la vez (confuso para el usuario)
3. ❌ Hacer los documentos obligatorios (viola regla de negocio)
4. ❌ Usar mismo color para warnings de distinta severidad

---

**Estado:** ✅ **IMPLEMENTACIÓN COMPLETA**  
**Testing Manual:** ⏳ PENDIENTE  
**Breaking Changes:** Ninguno (backward compatible)  
**Performance:** Mejorada (queries optimizadas con annotations)

---

**Próximo paso:** Testing manual en navegador para validar los 3 escenarios principales y verificar traducciones en todos los idiomas.
