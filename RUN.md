# Ejecución del Sistema: Guía Rápida

## Modos de Ejecución

El sistema EMR Dermatology + POS Cosmetics soporta dos modos de ejecución:

### 🔧 DEV (Desarrollo)

**Para desarrolladores**

```bash
./start-dev.sh
```

**Características:**
- Hot reload activo (cambios en código se reflejan automáticamente)
- DEBUG=True
- Logs detallados
- Frontend con `npm run dev`
- Backend con `python manage.py runserver`

**URLs:**
- Backend API: http://localhost:8000
- Frontend Web: http://localhost:3000
- Public Site: http://localhost:3001
- MinIO Console: http://localhost:9001
- API Docs: http://localhost:8000/api/schema/swagger-ui/

**Credenciales por defecto:**
- Usuario: `admin`
- Password: `admin123dev`

---

### 🏥 PROD_LOCAL (Producción Local)

**Para la doctora en su ordenador**

```bash
./start-prod.sh
```

**Características:**
- Sin hot reload
- DEBUG=False
- Frontend compilado en modo producción
- Backend con Gunicorn
- Mayor rendimiento y seguridad

**⚠️ ANTES DE USAR:**
1. Editar `.env.prod`
2. Cambiar TODAS las contraseñas marcadas con `CHANGE_THIS`
3. Generar claves secretas aleatorias

**URLs:**
- Backend API: http://localhost:8000
- Frontend Web: http://localhost:3000
- Public Site: http://localhost:3001
- MinIO Console: http://localhost:9001

---

## Comandos Útiles

### Iniciar servicios
```bash
# Desarrollo
./start-dev.sh

# Producción local
./start-prod.sh
```

### Detener servicios
```bash
# Detener todo
./stop.sh

# Detener solo desarrollo
./stop.sh dev

# Detener solo producción
./stop.sh prod
```

### Ver logs
```bash
# Ver todos los logs de desarrollo
./logs.sh dev

# Ver logs de un servicio específico
./logs.sh dev api
./logs.sh prod web

# Servicios disponibles: api, web, site, celery, postgres, redis, minio
```

### Ver estado de servicios
```bash
# Desarrollo
docker compose -f docker-compose.dev.yml ps

# Producción
docker compose -f docker-compose.prod.yml ps
```

---

## Arquitectura

```
┌─────────────────────────────────────────────────┐
│           DOCKER COMPOSE STACK                  │
├─────────────────────────────────────────────────┤
│                                                 │
│  Frontend (Next.js) ◄──► Backend (Django)      │
│  Puerto 3000                Puerto 8000         │
│                                  │              │
│  Public Site (Next.js)           │              │
│  Puerto 3001                     ▼              │
│                          PostgreSQL             │
│  MinIO (Storage)         Puerto 5432            │
│  Puerto 9000/9001                               │
│                          Redis                  │
│                          Puerto 6379            │
│                                                 │
│                          Celery Worker          │
│                          (Tareas asíncronas)    │
└─────────────────────────────────────────────────┘
```

**IMPORTANTE:**
- Todo corre en Docker
- El frontend se accede vía navegador
- No existe modo híbrido (servicios Docker + Django local)
- Los servicios se comunican por nombres de servicio en la red Docker

---

## Resolución de Problemas

### Docker no está corriendo
```bash
# macOS
open -a Docker

# Esperar a que Docker esté listo y reintentar
```

### Los puertos están ocupados
```bash
# Detener servicios existentes
./stop.sh

# Verificar puertos
lsof -i :3000
lsof -i :8000
```

### Ver errores detallados
```bash
# Ver logs del servicio con problema
./logs.sh dev api
./logs.sh prod web
```

### Reconstruir todo desde cero
```bash
# Detener servicios
./stop.sh

# Eliminar volúmenes (⚠️ ELIMINA DATOS)
docker volume rm postgres_data_dev redis_data_dev minio_data_dev

# Reiniciar
./start-dev.sh
```

---

## Diferencias Clave DEV vs PROD_LOCAL

| Característica | DEV | PROD_LOCAL |
|---------------|-----|------------|
| Hot Reload | ✅ Sí | ❌ No |
| DEBUG | True | False |
| Frontend Build | `npm run dev` | `npm run build` + `start` |
| Backend Server | Django runserver | Gunicorn |
| Volúmenes de código | Montados | No montados |
| Contraseñas | Por defecto | Deben cambiarse |
| Logs | Detallados | Producción |
| Performance | Normal | Optimizado |

---

## Backup (Solo PROD_LOCAL)

Los datos importantes están en volúmenes Docker:

```bash
# Ver volúmenes de producción
docker volume ls | grep prod

# Backup manual (ejemplo)
docker run --rm -v postgres_data_prod:/data -v $(pwd):/backup \
  alpine tar czf /backup/postgres-backup-$(date +%Y%m%d).tar.gz -C /data .
```

**Recomendación:** Configurar backups automáticos diarios para la máquina de la doctora.

---

## Archivos Importantes

- `.env.dev` - Variables de entorno para desarrollo
- `.env.prod` - Variables de entorno para producción (⚠️ NO COMMITEAR)
- `docker-compose.dev.yml` - Configuración Docker desarrollo
- `docker-compose.prod.yml` - Configuración Docker producción
- `start-dev.sh` - Script para iniciar desarrollo
- `start-prod.sh` - Script para iniciar producción
- `stop.sh` - Script para detener servicios
- `logs.sh` - Script para ver logs

---

## Soporte

Para problemas o dudas:
1. Revisar logs: `./logs.sh dev` o `./logs.sh prod`
2. Verificar estado: `docker compose -f docker-compose.dev.yml ps`
3. Consultar documentación en `docs/`
