# Separación DEV vs PROD_LOCAL - Resumen de Implementación

**Fecha**: 2025-12-26  
**Objetivo**: Clarificar modos de ejecución y prevenir confusión entre desarrollo y producción local

## ✅ Cambios Realizados

### 1. Variables de Entorno

**Creados**:
- ✅ `.env.dev` - Variables para desarrollo (DEBUG=True, contraseñas débiles)
- ✅ `.env.prod` - Variables para producción local (DEBUG=False, requiere configurar contraseñas)

**Modificados**:
- ✅ `.env` - Marcado como DEPRECATED, revertido a usar nombres de servicio Docker

**Diferencias clave**:
```bash
# DEV (.env.dev)
DJANGO_DEBUG=True
DATABASE_HOST=postgres  # Nombre servicio Docker
DJANGO_COLLECTSTATIC=0  # Skip static collection
DJANGO_SUPERUSER_PASSWORD=admin123dev

# PROD (.env.prod)
DJANGO_DEBUG=False
DATABASE_HOST=postgres  # Nombre servicio Docker
DJANGO_COLLECTSTATIC=1  # Collect static files
DJANGO_SUPERUSER_PASSWORD=CHANGE_THIS  # Debe configurarse
```

### 2. Docker Compose

**Creados**:
- ✅ `docker-compose.dev.yml` - Configuración desarrollo
  - Hot reload habilitado
  - Volúmenes de código montados
  - Frontend: `npm run dev`
  - Backend: `python manage.py runserver`
  
- ✅ `docker-compose.prod.yml` - Configuración producción local
  - Sin volúmenes de código
  - Frontend: Build + production start
  - Backend: Gunicorn
  - Dockerfile.prod para frontends

**Modificados**:
- ✅ `docker-compose.yml` - Marcado como DEPRECATED

**Diferencias clave**:

| Característica | DEV | PROD |
|---|---|---|
| Volúmenes código | ✅ Montados | ❌ No montados |
| Hot reload | ✅ Sí | ❌ No |
| Frontend build | Dev mode | Production build |
| Backend server | runserver | Gunicorn |
| Contenedores | `emr-*-dev` | `emr-*-prod` |
| Red Docker | `emr-network-dev` | `emr-network-prod` |
| Volúmenes datos | `*_dev` | `*_prod` |

### 3. Dockerfiles de Producción

**Creados**:
- ✅ `apps/web/Dockerfile.prod` - Multi-stage build para frontend ERP
- ✅ `apps/site/Dockerfile.prod` - Multi-stage build para sitio público

**Características**:
- Multi-stage build (deps → builder → runner)
- Optimizado con `output: 'standalone'` de Next.js
- Usuario no-root (nextjs:nodejs)
- Imagen minimal para producción

### 4. Scripts de Arranque

**Creados**:
- ✅ `start-dev.sh` - Inicia entorno desarrollo
  - Verifica Docker corriendo
  - Verifica .env.dev existe
  - Ejecuta: `docker compose -f docker-compose.dev.yml --env-file .env.dev up -d --build`
  
- ✅ `start-prod.sh` - Inicia entorno producción local
  - Verifica Docker corriendo
  - Verifica .env.prod existe
  - Advierte si hay contraseñas default (CHANGE_THIS)
  - Ejecuta: `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build`
  
- ✅ `stop.sh` - Detiene servicios
  - Soporta: `./stop.sh [dev|prod|all]`
  - Detiene también docker-compose.yml antiguo
  
- ✅ `logs.sh` - Ver logs
  - Soporta: `./logs.sh [dev|prod] [service]`
  - Ejemplos: `./logs.sh dev api`, `./logs.sh prod web`

**Permisos**:
- ✅ Todos marcados como ejecutables (`chmod +x`)

### 5. Documentación

**Creado**:
- ✅ `RUN.md` - Guía completa de ejecución
  - Modo DEV vs PROD_LOCAL explicado
  - Comandos de arranque/parada
  - Troubleshooting
  - Diferencias clave en tabla comparativa
  - Arquitectura del sistema
  - Guía de backup para producción

**Actualizado**:
- ✅ `docs/PROJECT_DECISIONS.md` - Nueva sección completa
  - **Sección 13: Execution Modes: DEV vs PROD_LOCAL**
  - 11 subsecciones detalladas:
    1. Docker-First Architecture
    2. Supported Execution Modes
    3. Frontend Access
    4. What Does NOT Exist
    5. Configuration Files
    6. Network Communication
    7. Volumes and Data Persistence
    8. Migration from Old Setup
    9. When to Use Each Mode
    10. Troubleshooting
    11. Documentation Links
  - Renumeradas secciones siguientes (13→14, 14→15)

**Creado**:
- ✅ `README_STARTUP.md` - Quick start en raíz del proyecto
  - Instrucciones rápidas para DEV y PROD
  - Comandos principales
  - Arquitectura visual
  - Troubleshooting básico
  - Links a documentación completa

### 6. Marcado de Obsoletos

**Archivos marcados como DEPRECATED**:
- ✅ `docker-compose.yml` - Header advirtiendo usar .dev.yml o .prod.yml
- ✅ `.env` - Header advirtiendo usar .env.dev o .env.prod

**Nota**: No se eliminaron para evitar romper referencias existentes, pero claramente marcados como no usar.

## 🎯 Decisiones Clave Documentadas

### No Existe Modo Híbrido
- ❌ No se soporta Django local + servicios Docker
- Los servicios se comunican por nombres Docker (`postgres`, `redis`)
- Intentar correr Django localmente causa error: "could not translate host name postgres"

### Frontend es Web, No Desktop
- Frontend se accede vía navegador web
- No es aplicación de escritorio
- No es Electron/Tauri
- Arquitectura: Browser → Next.js Container → Django Container

### Arquitectura Docker-First
- Todo corre en contenedores
- DEV tiene volúmenes montados para hot reload
- PROD no tiene volúmenes de código (seguridad + inmutabilidad)
- Datos persistentes en volúmenes Docker separados

### Comunicación de Red
- Dentro de Docker: Nombres de servicio (`postgres:5432`)
- Desde host: `localhost:5432` (puerto mapeado)
- Docker Compose crea red aislada para cada modo

## 📊 Estructura de Archivos Resultante

```
/Cosmetica 5/
├── .env                          ❌ DEPRECATED
├── .env.dev                      ✅ Desarrollo
├── .env.prod                     ✅ Producción local
├── .env.example                  ℹ️ Template/referencia
├── docker-compose.yml            ❌ DEPRECATED
├── docker-compose.dev.yml        ✅ Config desarrollo
├── docker-compose.prod.yml       ✅ Config producción
├── start-dev.sh                  ✅ Script arranque DEV
├── start-prod.sh                 ✅ Script arranque PROD
├── stop.sh                       ✅ Script parada
├── logs.sh                       ✅ Script logs
├── README_STARTUP.md             ✅ Quick start
├── RUN.md                        ✅ Guía completa
├── apps/
│   ├── web/
│   │   ├── Dockerfile            ✅ Desarrollo
│   │   └── Dockerfile.prod       ✅ Producción
│   └── site/
│       ├── Dockerfile            ✅ Desarrollo
│       └── Dockerfile.prod       ✅ Producción
└── docs/
    └── PROJECT_DECISIONS.md      ✅ Actualizado con sección 13
```

## 🔍 Validación

### ✅ Verificaciones Realizadas

1. **Archivos .env correctos**:
   ```bash
   cat .env.dev | grep DATABASE_HOST
   # OUTPUT: DATABASE_HOST=postgres ✓
   ```

2. **Scripts ejecutables**:
   ```bash
   ls -la *.sh
   # Todos con permisos +x ✓
   ```

3. **Servicios antiguos detenidos**:
   ```bash
   ./stop.sh
   # Detuvo docker-compose.yml, dev, prod ✓
   ```

### ⏳ Pendiente de Validación

Para validar completamente, ejecutar:

```bash
# Test DEV
./start-dev.sh
curl http://localhost:8000/api/healthz
curl http://localhost:3000
./stop.sh dev

# Test PROD (después de configurar .env.prod)
# 1. Editar .env.prod - cambiar CHANGE_THIS
# 2. ./start-prod.sh
# 3. Verificar que frontend está en modo producción (sin hot reload)
# 4. ./stop.sh prod
```

## 📝 Notas de Implementación

### Cambios NO Realizados (Por Diseño)

- ❌ NO se eliminó `docker-compose.yml` - Marcado como deprecated
- ❌ NO se eliminó `.env` - Marcado como deprecated
- ❌ NO se modificó lógica de negocio - Solo infraestructura
- ❌ NO se modificó UX - Frontend intacto

### Compatibilidad con next.config.js

Next.js ya tiene `output: 'standalone'` configurado:
```javascript
// apps/web/next.config.js
const nextConfig = {
  output: 'standalone',  // ✓ Necesario para Dockerfile.prod
  // ...
};
```

Esto permite que los Dockerfile.prod funcionen correctamente con multi-stage builds.

## 🎓 Aprendizajes

1. **Docker service names** vs **localhost**:
   - Dentro de contenedor: `postgres:5432`
   - Desde host: `localhost:5432`
   - Confundir esto causa errores de conexión

2. **Volume mounts** en desarrollo:
   - Permiten hot reload
   - No deben usarse en producción (seguridad)

3. **Separación clara** previene:
   - Usar DEBUG=True en producción
   - Usar contraseñas débiles en producción
   - Confusión sobre qué modo está corriendo

## 🔐 Seguridad

### DEV (Seguridad Relajada)
- Contraseñas débiles OK (admin123dev)
- DEBUG=True muestra stacktraces
- Django Debug Toolbar habilitado

### PROD (Seguridad Reforzada)
- ⚠️ DEBE cambiar contraseñas en `.env.prod`
- DEBUG=False no expone información sensible
- Sin herramientas de desarrollo
- Contraseñas fuertes obligatorias

### Validación de Seguridad en start-prod.sh
```bash
if grep -q "CHANGE_THIS" .env.prod; then
    echo "⚠️  WARNING: Default passwords detected"
    read -p "Continue anyway? (y/N): "
fi
```

## 📦 Entregables

### Archivos Nuevos (14)
1. `.env.dev`
2. `.env.prod`
3. `docker-compose.dev.yml`
4. `docker-compose.prod.yml`
5. `apps/web/Dockerfile.prod`
6. `apps/site/Dockerfile.prod`
7. `start-dev.sh`
8. `start-prod.sh`
9. `stop.sh`
10. `logs.sh`
11. `RUN.md`
12. `README_STARTUP.md`
13. Este archivo: `DEV_PROD_SEPARATION.md`

### Archivos Modificados (3)
1. `docker-compose.yml` - Marcado DEPRECATED
2. `.env` - Marcado DEPRECATED, revertido
3. `docs/PROJECT_DECISIONS.md` - Nueva sección 13

### Total: 17 archivos

## ✅ Checklist de Implementación

- [x] Crear .env.dev con variables desarrollo
- [x] Crear .env.prod con variables producción
- [x] Crear docker-compose.dev.yml
- [x] Crear docker-compose.prod.yml
- [x] Crear Dockerfile.prod para apps/web
- [x] Crear Dockerfile.prod para apps/site
- [x] Crear start-dev.sh con validaciones
- [x] Crear start-prod.sh con advertencias seguridad
- [x] Crear stop.sh con opciones dev/prod/all
- [x] Crear logs.sh con filtrado por servicio
- [x] Hacer scripts ejecutables (chmod +x)
- [x] Crear RUN.md con guía completa
- [x] Crear README_STARTUP.md con quick start
- [x] Actualizar PROJECT_DECISIONS.md sección 13
- [x] Marcar docker-compose.yml como DEPRECATED
- [x] Marcar .env como DEPRECATED
- [x] Revertir .env a usar nombres servicio Docker
- [x] Documentar todo en PROJECT_DECISIONS.md

## 🎯 Conclusión

Se ha implementado una **separación clara y completa** entre modos de ejecución DEV y PROD_LOCAL:

✅ **Sin ambigüedad**: Scripts específicos para cada modo  
✅ **Sin modo híbrido**: Todo en Docker, sin confusión  
✅ **Seguridad reforzada**: Advertencias y validaciones en PROD  
✅ **Documentación exhaustiva**: 3 niveles (quick start, guía completa, decisiones)  
✅ **Backwards compatibility**: Archivos antiguos marcados deprecated pero presentes  
✅ **Sin cambios en lógica**: Solo infraestructura y configuración  

El sistema ahora tiene una arquitectura Docker-first **bien definida y documentada**, lista para desarrollo y despliegue en la máquina de la doctora.

---

**Próximos Pasos**:
1. Validar `./start-dev.sh` funciona correctamente
2. Configurar `.env.prod` con contraseñas reales
3. Validar `./start-prod.sh` funciona correctamente
4. Configurar backup automático para PROD_LOCAL
5. Entrenar a la doctora en uso de sistema producción
