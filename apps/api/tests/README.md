# Tests Infrastructure

Este directorio contiene la infraestructura de testing del proyecto usando **pytest** + **pytest-django**.

## Stack de Testing

- `pytest==7.4.3` - Framework de testing
- `pytest-django==4.7.0` - Integración con Django
- `pytest-cov==4.1.0` - Reportes de cobertura
- `factory-boy==3.3.0` - Generación de fixtures

## Configuración

La configuración está en `pytest.ini` en la raíz de `apps/api/`:

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = tests.py test_*.py *_tests.py
addopts = -q --reuse-db
testpaths = tests
```

## Ejecutar Tests

### Todos los tests
```bash
cd apps/api
pytest
```

### Tests específicos por keyword
```bash
pytest -k appointment
pytest -k patient
pytest -k "test_create"
```

### Con reporte de cobertura
```bash
pytest --cov
pytest --cov=apps --cov-report=html
```

### Tests de un módulo específico
```bash
pytest tests/test_models.py
pytest tests/clinical/test_views_appointment.py
```

### Modo verbose
```bash
pytest -v
pytest -vv
```

### Sin reuso de DB (útil para debugging)
```bash
pytest --create-db
```

### Ejecutar tests en paralelo (requiere pytest-xdist)
```bash
pytest -n auto
```

## Estructura Sugerida

```
tests/
├── __init__.py
├── README.md (este archivo)
├── conftest.py (fixtures globales)
├── clinical/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_serializers.py
│   ├── test_views_patient.py
│   ├── test_views_appointment.py
│   └── test_permissions.py
├── authz/
│   ├── __init__.py
│   └── test_views_auth.py
└── core/
    ├── __init__.py
    └── test_models.py
```

## Fixtures Comunes

Crear fixtures en `conftest.py` para reutilizar en múltiples tests:

- `api_client` - DRF APIClient autenticado
- `user_admin`, `user_practitioner`, `user_reception` - Usuarios con roles
- `patient_factory` - Factory para crear pacientes
- `appointment_factory` - Factory para crear citas
- `encounter_factory` - Factory para crear encuentros

## Buenas Prácticas

1. **Nombrar tests descriptivamente**: `test_create_appointment_requires_auth`
2. **Usar factories**: Preferir factory-boy sobre crear instancias manualmente
3. **Aislar tests**: Cada test debe ser independiente
4. **Fixtures scope**: Usar `scope='function'` por defecto para aislamiento
5. **Marcar tests**: Usar `@pytest.mark.slow` para tests lentos
6. **Parametrizar**: Usar `@pytest.mark.parametrize` para casos múltiples

## Ejemplos de Uso

```python
# test_views_appointment.py
import pytest
from rest_framework import status

@pytest.mark.django_db
def test_list_appointments_as_admin(api_client, user_admin):
    api_client.force_authenticate(user=user_admin)
    response = api_client.get('/api/v1/appointments/')
    assert response.status_code == status.HTTP_200_OK

@pytest.mark.django_db
def test_create_appointment_requires_auth(api_client):
    response = api_client.post('/api/v1/appointments/', {})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
```

## Debugging

Para debuggear un test con breakpoint:

```bash
pytest -s tests/test_views.py::test_specific_case
```

El flag `-s` deshabilita capture de output, permitiendo ver prints y usar pdb.
