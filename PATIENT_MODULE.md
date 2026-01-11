# PATIENT_MODULE.md
Módulo de Pacientes – ERP Consulta Médica

---

## 1. Propósito del módulo de pacientes

El módulo de pacientes permite registrar y gestionar a las personas que acuden a la consulta médica.

Su objetivo es:
- Permitir trabajar desde el primer contacto, aunque falte información
- Reducir errores humanos sin bloquear el flujo real de la consulta
- Cumplir requisitos legales mediante avisos claros y trazabilidad
- Separar tareas clínicas de tareas administrativas

Principio fundamental:
> Un paciente puede existir con información incompleta,  
> pero el sistema debe avisar claramente de lo que falta  
> sin bloquear el trabajo diario.

---

## 2. Relación con las decisiones globales del ERP

Este módulo hereda las decisiones generales definidas en `PROJECT_DECISIONS.md`, en especial:

- Priorizar seguridad clínica y legal
- Evitar bloqueos innecesarios
- Usar avisos visibles en lugar de errores tardíos
- Asumir que el personal puede cometer errores involuntarios
- Guiar al usuario sin infantilizarlo

El módulo de pacientes **no es especial**:  
es el primer módulo que aplica estas reglas de forma completa.

---

## 3. Qué es un paciente en el sistema

Un paciente es una entidad que puede existir en distintos estados de completitud.

El sistema **NO exige** que toda la información esté presente desde el primer momento.

Campos básicos:
- Nombre *
- Apellido *
- Email (opcional)
- Teléfono (opcional)
- Fecha de nacimiento
- Sexo

Los campos marcados con * son obligatorios para crear el paciente.

---

## 4. Validaciones de formulario (regla importante)

El sistema incluye validaciones de coherencia de datos en el formulario de alta y edición, por ejemplo:
- Tipo de documento y número de documento deben proporcionarse juntos
- Formatos incorrectos
- Campos obligatorios inconsistentes

Estas validaciones:
- Se consideran correctas y definitivas
- Mantienen su comportamiento bloqueante actual
- Se muestran como errores (rojo)
- NO deben modificarse

Estas validaciones **no están relacionadas** con consentimientos ni documentación.

---

## 5. Creación de paciente

Regla principal:

> La creación de un paciente **NO debe bloquearse**  
> por faltar consentimientos ni documentación escaneada.

Durante el alta:
- Los consentimientos pueden no estar aceptados
- No es obligatorio subir documentos
- El paciente se crea igualmente

El sistema informa mediante avisos visibles, pero no bloquea.

---

## 6. Edición del paciente y protección de datos

- El sistema protege frente a pérdida accidental de cambios
- Si hay cambios no guardados, se avisa antes de salir
- Las validaciones se aplican al guardar
- No se permiten estados inconsistentes silenciosos

---

## 7. Consentimientos legales

Existen dos niveles distintos y complementarios de consentimiento:

### 7.1 Consentimiento lógico (checkbox)

Representa que el paciente ha aceptado:
- Política de privacidad
- Términos y condiciones

Se registra como estado lógico (aceptado / no aceptado).

La falta de aceptación lógica:
- BLOQUEA la creación de consultas clínicas
- Se muestra como aviso amarillo
- Mantiene el comportamiento actual del sistema

---

### 7.2 Consentimiento documental (documentos escaneados)

Representa el documento físico firmado por el paciente.

Características:
- Se asocia directamente al paciente
- Puede contener uno o varios archivos por consentimiento
- Los archivos pueden ser PDF o imágenes escaneadas
- Los documentos pueden subirse en cualquier momento

Regla fundamental (cerrada):

> La falta de documentos escaneados  
> NO bloquea:
> - el alta del paciente
> - la creación de consultas / encounters

La falta de documentación:
- Genera avisos visibles (amarillo)
- No genera errores
- No bloquea ninguna acción clínica

---

## 8. Documentación de consentimientos – UX

La documentación de consentimientos:
- Se gestiona desde la pantalla de alta del paciente
- También es accesible desde la ficha del paciente ya creado

Para cada consentimiento:
- Se pueden subir uno o varios archivos
- Se muestra el estado:
  - Documentación pendiente
  - Documentación subida

Por cada archivo se permite:
- Ver (abrir en el navegador)
- Descargar (guardar en local para imprimir)
- Eliminar

No existe:
- Versionado
- Documento “principal”
- Validación del contenido del archivo

---

## 9. Avisos y código de colores

El sistema utiliza el código de colores existente, que NO debe modificarse:

- Rojo: error de validación bloqueante (formularios)
- Amarillo: aviso de información pendiente
- Azul: información general

Los consentimientos (lógicos o documentales):
- Siempre usan avisos amarillos
- Nunca se tratan como errores

---

## 10. Avisos visibles al usuario

Los avisos por falta de consentimientos o documentación:
- Se muestran en la pantalla de alta
- Se muestran en la ficha del paciente
- Se muestran en la lista de pacientes

Los avisos:
- Informan
- No bloquean
- Permiten priorizar tareas administrativas

---

## 11. Roles y responsabilidades

La doctora y el personal de recepción:
- Tienen los mismos permisos sobre pacientes y documentación
- Pueden crear, editar y completar información
- Pueden subir, ver, descargar y eliminar documentos

El sistema NO asume que la doctora realice tareas administrativas.

---

## 12. Internacionalización (i18n) – regla obligatoria

Regla no negociable:

> NO puede existir ningún texto hardcodeado en la UI  
> relacionado con este módulo.

Todo texto visible:
- Títulos
- Avisos
- Botones
- Mensajes de ayuda
- Estados

DEBE obtenerse exclusivamente del sistema i18n existente,  
en los 6 idiomas del ERP.

Esta regla es obligatoria y definitiva.

---

## 13. Decisiones explícitamente abiertas (futuro)

No forman parte del alcance actual:
- Firma digital
- Consentimientos específicos por tratamiento
- Integraciones externas
- Envío automático de documentos

Se documentan aquí para evitar confusión futura.

---

## 14. Resumen final

> El sistema permite trabajar sin fricción,  
> avisa claramente de lo que falta,  
> separa lo clínico de lo administrativo,  
> y no bloquea el trabajo real de la consulta.
