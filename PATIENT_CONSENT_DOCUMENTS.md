# PATIENT_CONSENT_DOCUMENTS.md  
Consentimientos Documentales del Paciente

---

## 1. Propósito del documento

Este documento define el funcionamiento de los **consentimientos documentales** del paciente  
(es decir, los documentos físicos firmados y escaneados), y su relación con:

- el modelo de pacientes
- los consentimientos lógicos (checkbox)
- la infraestructura de almacenamiento de documentos
- la UX del ERP

Este documento **complementa**, pero NO sustituye, a:
- `PROJECT_DECISIONS.md`
- `PATIENT_MODULE.md`
- `Patient Clinical Actions - Consent-Based Blocking`

---

## 2. Definición clave (muy importante)

Existen **DOS niveles distintos de consentimiento**, que NO deben confundirse:

### 2.1 Consentimiento lógico (checkbox)
- Se registra mediante campos booleanos en el paciente
- Ejemplos:
  - `privacy_policy_accepted`
  - `terms_accepted`
- Controla el **bloqueo de acciones clínicas**
- Ya está implementado y documentado en otros módulos

### 2.2 Consentimiento documental (este documento)
- Representa el **documento físico firmado** por el paciente
- Se almacena como archivo (PDF o imagen)
- NO bloquea la creación del paciente
- NO bloquea la creación de consultas
- Su ausencia **solo genera avisos informativos**

👉 Ambos niveles son complementarios, no excluyentes.

---

## 3. Principio fundamental de negocio

> El papel firmado debe existir,  
> pero su ausencia temporal **NO debe bloquear el trabajo clínico ni administrativo**.

El sistema:
- permite trabajar
- avisa de lo que falta
- no castiga al usuario

---

## 4. Relación con el backend (hechos, no opiniones)

El backend ya dispone de:

- Infraestructura de almacenamiento (MinIO)
- Modelo `Document`
- Modelo `Consent` con campo `document` nullable
- Utilidades de subida y descarga mediante URLs firmadas (presigned URLs)

Este documento **NO introduce nueva infraestructura**,  
solo define cómo se utiliza correctamente lo existente.

---

## 5. Tipos de archivo permitidos

### 5.1 Formatos aceptados (CERRADO)

Se permiten los siguientes formatos para documentos de consentimiento:

- **PDF**
- **Imágenes escaneadas**:
  - JPG
  - PNG
  - HEIC / HEIF (formato habitual de iPhone)

Motivo:
- La doctora utiliza iPhone
- El escaneo suele hacerse con el móvil
- El sistema debe adaptarse a la realidad, no al revés

No se permiten:
- DOC / DOCX
- XLS / XLSX
- otros formatos ofimáticos

---

## 6. Tamaño máximo de archivo

### 6.1 Límite definido (CERRADO)

- **25 MB por archivo**

Motivo:
- PDFs multipágina reales
- Imágenes sin comprimir de móvil
- Evitar bloqueos innecesarios en recepción

---

## 7. Flujo de creación y subida

### 7.1 Creación del consentimiento

- Un registro de consentimiento puede existir **sin documento adjunto**
- El documento puede subirse:
  - en el momento del alta
  - más tarde
  - por la doctora o por recepción

Mientras el documento no exista:
- el sistema muestra avisos
- pero NO bloquea ningún flujo

---

### 7.2 Subida del documento

- El documento se asocia a un registro de `Consent`
- Se almacena como `Document` en el bucket `documents`
- El archivo se sube mediante URL firmada (upload directo a storage)
- El backend no procesa el archivo binario

No existe:
- versionado
- documento “principal”
- validación de contenido del archivo

---

## 8. Permisos (RBAC) — decisión cerrada

### 8.1 Recepción

El personal de recepción:

- ✅ Puede:
  - subir documentos de consentimiento
  - ver documentos
  - descargarlos
  - eliminarlos (si procede)
- ❌ No puede:
  - gestionar documentación clínica de encounters

---

### 8.2 Doctora

La doctora:

- ✅ Tiene acceso completo a:
  - documentación administrativa del paciente
  - documentación clínica asociada a encounters

---

### 8.3 Principio rector

> Recepción gestiona documentación administrativa del paciente  
> Doctora gestiona clínica

---

## 9. UX y avisos

### 9.1 Avisos por documentación pendiente

Si falta documentación de consentimiento:

- Se muestra **aviso amarillo**
- El texto distingue claramente:
  - consentimientos lógicos
  - consentimientos documentales
- El aviso aparece:
  - en la pantalla de alta
  - en la ficha del paciente
  - en la lista de pacientes

El aviso:
- informa
- no bloquea
- no se muestra como error

---

## 10. Internacionalización (i18n)

Regla obligatoria:

> No puede existir ningún texto hardcodeado  
> relacionado con consentimientos documentales.

Todo texto visible:
- avisos
- botones
- títulos
- ayudas

Debe pasar por el sistema i18n existente  
en los 6 idiomas del ERP.

---

## 11. Qué NO forma parte del alcance

De forma explícita, NO se implementa:

- Firma digital
- OCR
- Extracción de texto
- Indexación de documentos
- Versionado
- Auditoría legal avanzada

Estos puntos quedan fuera de alcance por decisión de producto.

---

## 12. Resumen final

> El consentimiento documental es una obligación legal,  
> no una fricción operativa.
>
> El sistema permite trabajar,  
> avisa de lo que falta,  
> y respeta la realidad de la consulta médica.
