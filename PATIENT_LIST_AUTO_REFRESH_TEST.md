# Prueba Manual: Actualización Automática de Consentimientos

**Fecha:** 29 de diciembre de 2025  
**Objetivo:** Verificar que el estado de consentimientos se actualiza automáticamente en la lista después de editar/crear pacientes

---

## ✅ TEST 1: Editar Consentimientos de Paciente Existente

### Escenario: Marcar consentimientos en paciente que no los tiene

**Pasos:**

1. **Abrir lista de pacientes**
   ```
   URL: http://localhost:3000/es/patients
   ```
   - Identificar un paciente con badge amarillo "Faltan consentimientos"
   - Anotar el nombre del paciente: ________________

2. **Navegar al detalle del paciente**
   - Click en la fila del paciente
   - URL debería ser: `/es/patients/{id}`
   - Verificar que badge muestra: ⚠️ "Faltan consentimientos" (amarillo)

3. **Editar paciente**
   - Click en botón "Editar Paciente"
   - URL: `/es/patients/{id}/edit`
   - Scroll hasta sección "Consentimientos Legales"

4. **Marcar consentimientos**
   - ✅ Marcar checkbox "Política de privacidad aceptada"
   - ✅ Marcar checkbox "Términos y condiciones aceptados"
   - Verificar preview del badge: debería cambiar a verde "Consentimientos OK"

5. **Guardar cambios**
   - Click en botón "Guardar Cambios"
   - **Esperar navegación automática a detalle**

6. **✅ VERIFICACIÓN CRÍTICA 1: Detalle se actualiza**
   - Página detalle se recarga automáticamente
   - Badge debe mostrar: ✅ "Consentimientos OK" (verde)
   - **NO REFRESCAR MANUALMENTE (F5)**

7. **Volver a lista**
   - Click en botón "Volver a Lista"
   - URL: `/es/patients`

8. **✅ VERIFICACIÓN CRÍTICA 2: Lista se actualiza**
   - Buscar mismo paciente en la lista
   - Badge debe mostrar: ✅ "Consentimientos OK" (verde)
   - **SIN HACER REFRESH MANUAL**

**Resultado esperado:**
- ✅ Badge verde en detalle (sin refresh)
- ✅ Badge verde en lista (sin refresh)
- ✅ Cambio persistente (recargar con F5 sigue mostrando verde)

---

## ✅ TEST 2: Crear Nuevo Paciente CON Consentimientos

### Escenario: Crear paciente marcando consentimientos desde el inicio

**Pasos:**

1. **Ir a lista de pacientes**
   ```
   URL: http://localhost:3000/es/patients
   ```

2. **Abrir formulario de creación**
   - Click en botón verde "Nuevo Paciente"
   - URL: `/es/patients/new`

3. **Completar formulario mínimo**
   - Nombre: `Test AutoUpdate`
   - Apellido: `Consent Check`
   - Scroll hasta "Consentimientos Legales"

4. **Marcar consentimientos**
   - ✅ Marcar "Política de privacidad aceptada"
   - ✅ Marcar "Términos y condiciones aceptados"

5. **Guardar nuevo paciente**
   - Click en botón "Guardar"
   - **Esperar navegación automática a detalle**

6. **✅ VERIFICACIÓN CRÍTICA 3: Detalle del nuevo paciente**
   - URL: `/es/patients/{nuevo-id}`
   - Badge debe mostrar: ✅ "Consentimientos OK" (verde)

7. **Volver a lista**
   - Click en "Volver a Lista"
   - URL: `/es/patients`

8. **✅ VERIFICACIÓN CRÍTICA 4: Nuevo paciente en lista**
   - Buscar paciente "Test AutoUpdate Consent Check"
   - Badge debe mostrar: ✅ "Consentimientos OK" (verde)
   - **SIN REFRESH MANUAL**

**Resultado esperado:**
- ✅ Paciente creado con badge verde desde el inicio
- ✅ Lista refleja estado correcto inmediatamente

---

## ✅ TEST 3: Crear Nuevo Paciente SIN Consentimientos

### Escenario: Verificar que también funciona cuando NO se marcan

**Pasos:**

1. **Crear nuevo paciente**
   - URL: `/es/patients/new`
   - Nombre: `Test No Consent`
   - Apellido: `Validation`
   - ❌ NO marcar ningún checkbox de consentimientos

2. **Guardar**
   - Click en "Guardar"
   - Navegar automáticamente a detalle

3. **✅ VERIFICACIÓN CRÍTICA 5: Detalle sin consentimientos**
   - Badge debe mostrar: ⚠️ "Faltan consentimientos" (amarillo)

4. **Volver a lista**
   - Badge en lista debe ser: ⚠️ "Faltan consentimientos" (amarillo)
   - **SIN REFRESH MANUAL**

**Resultado esperado:**
- ⚠️ Badge amarillo en detalle
- ⚠️ Badge amarillo en lista
- Consistencia mantenida

---

## ✅ TEST 4: Editar Consentimientos → Desmarcar

### Escenario: Remover consentimientos de un paciente que los tiene

**Pasos:**

1. **Seleccionar paciente con consentimientos**
   - Buscar paciente con badge verde en lista
   - Navegar a edición: `/es/patients/{id}/edit`

2. **Desmarcar consentimientos**
   - ❌ Desmarcar "Política de privacidad aceptada"
   - ❌ Desmarcar "Términos y condiciones aceptados"
   - Preview del badge cambia a amarillo

3. **Guardar cambios**
   - Click en "Guardar Cambios"
   - Navegar a detalle

4. **✅ VERIFICACIÓN CRÍTICA 6: Detalle refleja cambio**
   - Badge: ⚠️ "Faltan consentimientos" (amarillo)

5. **Volver a lista**
   - Badge en lista: ⚠️ "Faltan consentimientos" (amarillo)
   - **SIN REFRESH**

**Resultado esperado:**
- ⚠️ Badge cambia de verde a amarillo
- ⚠️ Cambio visible inmediatamente en lista

---

## ✅ TEST 5: Cambio de Idioma (i18n)

### Escenario: Verificar que textos se traducen correctamente

**Pasos:**

1. **Lista en español**
   ```
   URL: http://localhost:3000/es/patients
   ```
   - Badge verde: "Consentimientos OK"
   - Badge amarillo: "Faltan consentimientos"

2. **Cambiar a francés**
   ```
   URL: http://localhost:3000/fr/patients
   ```
   - Badge verde: "Consentements OK"
   - Badge amarillo: "Consentements Manquants"

3. **Cambiar a inglés**
   ```
   URL: http://localhost:3000/en/patients
   ```
   - Badge verde: "Consents OK"
   - Badge amarillo: "Consents Missing"

4. **Editar paciente en francés**
   - Editar consentimientos en `/fr/patients/{id}/edit`
   - Guardar
   - Volver a lista francesa
   - ✅ Badge actualizado en francés

**Resultado esperado:**
- ✅ Traducciones correctas en cada idioma
- ✅ Actualización automática funciona en todos los idiomas

---

## ✅ TEST 6: Navegación Directa (sin lista intermedia)

### Escenario: Volver a lista desde otra ruta

**Pasos:**

1. **Editar paciente**
   - Editar consentimientos de paciente
   - Guardar → navega a detalle

2. **Navegar manualmente a lista**
   - En vez de "Volver a Lista", escribir en URL bar:
     ```
     http://localhost:3000/es/patients
     ```

3. **✅ VERIFICACIÓN CRÍTICA 7: Lista carga estado fresco**
   - Badge debe reflejar último estado guardado
   - Funciona porque lista siempre hace fetch al montar

**Resultado esperado:**
- ✅ Lista siempre muestra datos actualizados del backend

---

## ✅ TEST 7: Múltiples Pestañas (concurrencia)

### Escenario: Editar en una pestaña, ver en otra

**Pasos:**

1. **Abrir dos pestañas**
   - Pestaña A: Lista de pacientes
   - Pestaña B: Lista de pacientes (misma URL)

2. **En Pestaña B: Editar paciente**
   - Click en paciente → editar → marcar consentimientos → guardar
   - Volver a lista en Pestaña B
   - ✅ Badge verde (actualización local funciona)

3. **En Pestaña A: Verificar sincronización**
   - La Pestaña A **NO se actualiza automáticamente** (esto es normal)
   - Hacer refresh manual en Pestaña A (F5)
   - ✅ Badge verde (backend tiene estado correcto)

**Resultado esperado:**
- ✅ Cada pestaña se actualiza con sus propios eventos
- ✅ Backend es fuente de verdad (refresh siempre muestra correcto)
- ⚠️ Eventos no cruzan pestañas (comportamiento esperado sin WebSockets)

---

## 🐛 Debugging: Si algo falla

### Console Logs a Verificar

Abrir DevTools → Console:

1. **Al guardar edición:**
   ```
   Patients updated event received, reloading list...
   Patient updated event received, reloading detail...
   ```

2. **Al crear paciente:**
   ```
   Patients updated event received, reloading list...
   ```

3. **Si no aparecen los logs:**
   - El evento no se disparó
   - Verificar que `window.dispatchEvent(new Event('patients-updated'))` se ejecuta

### Network Tab

1. **Abrir DevTools → Network**
2. **Al guardar paciente:**
   - `PATCH /api/v1/clinical/patients/{id}/` → 200 OK
   - Verificar response incluye `privacy_policy_accepted: true`

3. **Al recargar lista:**
   - `GET /api/v1/clinical/patients/` → 200 OK
   - Verificar response incluye `privacy_policy_accepted: true` en el paciente editado

### Verificar Campos en Response

Backend debe devolver estos campos en la lista:

```json
{
  "results": [
    {
      "id": "...",
      "first_name": "...",
      "last_name": "...",
      "privacy_policy_accepted": true,    // ← REQUIRED
      "terms_accepted": true,             // ← REQUIRED
      "privacy_policy_accepted_at": "2025-12-29T...",
      "terms_accepted_at": "2025-12-29T...",
      ...
    }
  ]
}
```

**Si estos campos faltan en la lista:**
- `hasRequiredConsents()` siempre devuelve `false`
- Badge siempre será amarillo
- **Solución:** Backend debe incluir estos campos en el serializer de lista

---

## 📊 Checklist Final

Tras completar todos los tests, verificar:

- [ ] ✅ TEST 1: Editar consentimientos → badge verde en lista (sin refresh)
- [ ] ✅ TEST 2: Crear con consentimientos → badge verde en lista (sin refresh)
- [ ] ✅ TEST 3: Crear sin consentimientos → badge amarillo en lista
- [ ] ✅ TEST 4: Desmarcar consentimientos → badge amarillo en lista
- [ ] ✅ TEST 5: Traducciones correctas en ES/FR/EN
- [ ] ✅ TEST 6: Navegación directa carga estado correcto
- [ ] ✅ TEST 7: Backend es fuente de verdad (refresh siempre correcto)

## 📝 Notas Técnicas

### Implementación Usada

**Sistema de Eventos del Navegador:**
- No usa React Query (no instalado en proyecto)
- Usa `window.addEventListener('patients-updated', ...)`
- Evento disparado con `window.dispatchEvent(new Event('patients-updated'))`

**Ventajas:**
- ✅ Simple, no requiere dependencias externas
- ✅ Funciona con arquitectura useState/useEffect existente
- ✅ Compatible con Next.js App Router
- ✅ No rompe optimistic locking (row_version)

**Limitaciones:**
- ⚠️ Eventos no cruzan pestañas (requeriría WebSockets o localStorage events)
- ⚠️ Cada componente hace su propio fetch (no hay cache compartido)

**Alternativa Futura (con React Query):**
- Usar `queryClient.invalidateQueries(['patients'])`
- Cache compartido entre componentes
- Sincronización automática entre pestañas
- Menor carga en backend (cache inteligente)

---

## ✅ Confirmación de Éxito

**El fix está completo cuando:**

1. Editas consentimientos de un paciente
2. Guardas cambios
3. Vuelves a la lista
4. **El badge refleja el nuevo estado SIN presionar F5**

**Estado:**
- ✅ Código implementado
- ✅ Sin errores de TypeScript
- ⏳ Pendiente testing manual con backend real
- ⏳ Verificar que backend devuelve campos necesarios en lista

---

## 🔧 Comandos de Verificación

### Iniciar aplicación
```bash
cd /Users/josericardoparlonsebastian/Desktop/Ideas/Cosmetica\ 5
./start-dev.sh

# Esperar a que inicie completamente
# Navegar a http://localhost:3000/es/patients
```

### Ver logs en tiempo real
```bash
# En DevTools Console, ejecutar:
window.addEventListener('patients-updated', () => {
  console.log('✅ Event received:', new Date().toISOString());
});

# Luego editar/crear paciente
# Deberías ver el log aparecer
```

### Verificar payload del backend
```bash
# En DevTools Console, después de cargar lista:
console.table(
  window._patientsData?.results?.map(p => ({
    name: p.first_name + ' ' + p.last_name,
    privacy: p.privacy_policy_accepted,
    terms: p.terms_accepted
  }))
);
```

---

**Preparado para testing en entorno dev.** 🚀
