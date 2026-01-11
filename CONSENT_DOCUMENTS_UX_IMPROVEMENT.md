# Mejora UX: Documentos de Consentimiento

**Fecha:** 11 enero 2026
**Estado:** ✅ COMPLETADO
**Archivos modificados:** 3

---

## 📋 Contexto del Problema

En la ficha del paciente, la sección "Documentos de Consentimiento" presentaba una UX confusa cuando no había documentos:

❌ **Antes:**
- Mensaje genérico "Documento no adjuntado"
- No había CTA claro para resolver el problema
- Banner de advertencia sin acción directa
- Usuario no sabía qué hacer para completar los documentos

---

## ✅ Solución Implementada

### 1. **Estado Vacío Mejorado** (Sin documentos)

Cuando no hay documentos de consentimiento en el sistema:

```tsx
┌──────────────────────────────────────────┐
│   📄 Ícono amarillo en círculo           │
│                                          │
│   Sin Documentos de Consentimiento      │
│                                          │
│   No se han encontrado documentos de    │
│   consentimiento para este paciente.    │
│   Los documentos escaneados y firmados  │
│   deben ser subidos al sistema.         │
│                                          │
│   [🔼 Subir Documentos de Consentimiento]│
│         (Botón azul prominente)          │
└──────────────────────────────────────────┘
```

**Comportamiento:**
- Botón azul grande y visible
- Al hacer clic: abre selector de archivos
- Permite subir uno o varios PDFs de consentimiento

---

### 2. **Documentos Incompletos** (Algunos pendientes)

Cuando hay consentimientos en el sistema pero faltan archivos adjuntos:

```tsx
┌──────────────────────────────────────────┐
│ Documentos de Consentimiento  ✓ Completo │
│                                          │
│ ⚠️ Algunos consentimientos no tienen    │
│    archivo escaneado adjunto...          │
│                                          │
│ ┌────────────────────────────────────┐  │
│ │ Fotos Clínicas          [Vigente]   │  │
│ │ ⚠️ Documento no adjuntado           │  │
│ │              [🔼 Subir Documento]   │  │
│ └────────────────────────────────────┘  │
│                                          │
│ ┌────────────────────────────────────┐  │
│ │ Fotos de Marketing      [Vigente]   │  │
│ │ 📄 consent_marketing_2025.pdf       │  │
│ │    [Ver] [Descargar] [Eliminar]     │  │
│ └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

**Mejoras:**
- Fondo amarillo para documentos sin adjuntar (⚠️ visible)
- Botón azul prominente "Subir Documento" por consentimiento
- Indicador de estado "✓ Completo" cuando todos tienen archivo

---

### 3. **Documentos Completos**

Cuando todos los consentimientos tienen documentos adjuntos:

```tsx
┌──────────────────────────────────────────┐
│ Documentos de Consentimiento  ✓ Completo │
│                                          │
│ ┌────────────────────────────────────┐  │
│ │ Fotos Clínicas          [Vigente]   │  │
│ │ 📄 consent_photos_2025.pdf          │  │
│ │    [Ver] [Descargar] [Eliminar]     │  │
│ └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

**Comportamiento:**
- Badge verde "✓ Completo" en el encabezado
- Sin alertas ni advertencias
- Todos los documentos accesibles

---

## 🎨 Cambios de Interfaz

### Botón de Subida - Antes vs Después

**❌ Antes:**
```tsx
<button className="px-3 py-1 text-sm text-blue-600">
  Subir Documento
</button>
```
- Texto pequeño
- Sin ícono
- Poco visible

**✅ Después:**
```tsx
<button className="px-4 py-2 bg-blue-600 text-white">
  🔼 Subir Documento
</button>
```
- Fondo azul sólido
- Ícono de carga
- Botón prominente
- Spinner animado mientras sube

---

## 📝 Textos Agregados (Español)

```json
"consentDocuments": {
  "emptyState": {
    "title": "Sin Documentos de Consentimiento",
    "message": "No se han encontrado documentos de consentimiento para este paciente. Los documentos escaneados y firmados deben ser subidos al sistema.",
    "cta": "Subir Documentos de Consentimiento"
  },
  "complete": "Documentos Completos",
  "uploadSuccess": "Documento subido exitosamente"
}
```

---

## 🔄 Flujo de Usuario Mejorado

### Caso 1: Paciente sin documentos
1. Usuario entra a ficha del paciente
2. Ve banner amarillo "Faltan consentimientos"
3. Scroll a sección "Documentos de Consentimiento"
4. **Ve estado vacío con botón azul grande** ✨
5. Click en "Subir Documentos de Consentimiento"
6. Selecciona archivo PDF
7. Sistema sube → Muestra documento
8. Banner de advertencia desaparece

### Caso 2: Algunos documentos pendientes
1. Usuario ve lista de consentimientos
2. **Fondo amarillo** destaca los sin documento ⚠️
3. **Botón azul** para subir por cada pendiente
4. Click → Selecciona archivo → Sube
5. Fondo amarillo → Fondo gris (completado)
6. Cuando todos completos → Badge "✓ Completo"

---

## 🎯 Requisitos Cumplidos

✅ **Botón primario claro cuando no hay documentos**
- Implementado: "Subir Documentos de Consentimiento" (azul, grande, con ícono)

✅ **Permitir subir uno o varios archivos PDF**
- Input acepta: `.pdf,.jpg,.jpeg,.png,.heic,.heif`
- Validación: máx 25 MB por archivo

✅ **Refrescar lista tras subida exitosa**
- `loadConsents()` llamado tras upload success
- Estado actualizado automáticamente

✅ **Eliminar estado de error tras completar**
- Banner amarillo desaparece cuando `hasMissingDocuments === false`
- Badge "✓ Completo" aparece cuando todos tienen archivo

✅ **Sin navegación fuera de la ficha**
- Todo en la misma página
- Modal solo para confirmar eliminación
- Sin wizards ni pantallas nuevas

---

## 📂 Archivos Modificados

### 1. `/apps/web/src/components/patients/PatientConsentDocuments.tsx`

**Cambios:**
- ✨ Nuevo estado vacío con CTA prominente (líneas ~220-265)
- ✨ Badge "✓ Completo" en encabezado cuando todos OK
- ✨ Banner de advertencia para documentos pendientes
- 🎨 Botón de subida mejorado: azul sólido, más grande, con ícono y spinner
- 🎨 Fondo amarillo para consentimientos sin documento adjunto

### 2. `/apps/web/messages/es.json`

**Cambios:**
- ➕ `emptyState.title`: "Sin Documentos de Consentimiento"
- ➕ `emptyState.message`: Explicación clara
- ➕ `emptyState.cta`: "Subir Documentos de Consentimiento"
- ➕ `complete`: "Documentos Completos"
- ➕ `uploadSuccess`: "Documento subido exitosamente"

### 3. `/apps/web/messages/en.json`

**Cambios:**
- ➕ Traducciones en inglés de los mismos textos

---

## 🧪 Comportamiento Esperado

### ✅ Caso de Éxito

1. **Usuario ve estado vacío**
   - Ícono amarillo
   - Título claro
   - Mensaje explicativo
   - **Botón azul prominente**: "Subir Documentos de Consentimiento"

2. **Usuario hace click en botón**
   - Se abre selector de archivos nativo del SO
   - Muestra tipos permitidos: PDF, JPG, PNG, HEIC, HEIF

3. **Usuario selecciona archivo válido** (PDF ≤25MB)
   - Botón muestra spinner y texto "Subiendo..."
   - Backend recibe archivo vía presigned URL
   - Lista se recarga automáticamente
   - Documento aparece con opciones: [Ver] [Descargar] [Eliminar]
   - Si era el último pendiente → Badge "✓ Completo" aparece

### ❌ Caso de Error

1. **Archivo muy grande** (>25MB)
   - Alert: "El archivo es demasiado grande. El tamaño máximo es 25 MB."
   - Input se resetea

2. **Tipo de archivo inválido** (ej: .docx)
   - Alert: "Tipo de archivo no válido. Solo se permiten PDF, JPG, PNG, HEIC y HEIF."
   - Input se resetea

3. **Error de red/backend**
   - Alert: "Error al subir el documento. Por favor, inténtalo de nuevo."
   - Spinner desaparece
   - Usuario puede reintentar

---

## 🚀 Próximos Pasos Sugeridos (Opcional)

### Fase 2 - Mejoras Adicionales

1. **Drag & Drop**
   ```tsx
   <div 
     onDrop={handleDrop}
     onDragOver={handleDragOver}
     className="border-2 border-dashed"
   >
     Arrastra archivos aquí o haz click para seleccionar
   </div>
   ```

2. **Preview antes de subir**
   - Mostrar miniatura del PDF/imagen
   - Permitir cancelar antes de confirmar

3. **Subida múltiple simultánea**
   - `<input type="file" multiple />`
   - Barra de progreso por archivo
   - Queue de subidas

4. **Notificaciones toast**
   ```tsx
   toast.success('Documento subido exitosamente')
   toast.error('Error al subir documento')
   ```

---

## 📸 Resumen Visual

```
ANTES                           DESPUÉS
────────────────────────────────────────────────
📋 Documentos de Consentimiento  📋 Documentos de Consentimiento ✓

Sin mensajes claros              [Ícono amarillo grande]
                                Sin Documentos de Consentimiento
                                
                                Mensaje explicativo claro
                                
Documento no adjuntado          [🔼 SUBIR DOCUMENTOS] ← Botón azul
[link pequeño: subir]            (prominente, con ícono)

────────────────────────────────────────────────
Usuario confundido ❌           Usuario sabe qué hacer ✅
Sin CTA claro ❌                 CTA prominente ✅
Texto genérico ❌                Textos específicos ✅
```

---

## ✅ Checklist Final

- [x] Botón primario claro cuando no hay documentos
- [x] Permite subir archivos PDF (y JPG/PNG/HEIC)
- [x] Refresca lista tras subida exitosa
- [x] Elimina estado de error cuando completo
- [x] Muestra estado visual "Documentos Completos"
- [x] Sin wizards ni navegación externa
- [x] Textos en español claros y específicos
- [x] Comportamiento en error manejado
- [x] Validación de tamaño y tipo de archivo
- [x] Spinner durante subida
- [x] Traducción al inglés incluida

---

## 🎉 Resultado

La sección de Documentos de Consentimiento ahora tiene una UX clara, directa y sin confusión. El usuario sabe exactamente qué hacer cuando faltan documentos y recibe feedback visual inmediato.

**Impacto:**
- ⬇️ Reduce confusión del usuario
- ⬆️ Aumenta tasa de completitud de documentos
- ✨ Mejora experiencia de usuario
- 📱 Mantiene flujo dentro de la ficha del paciente
