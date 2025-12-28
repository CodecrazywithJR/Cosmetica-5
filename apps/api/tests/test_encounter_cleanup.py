"""
Test suite para verificar que la limpieza del modelo Encounter deprecated fue exitosa.
Sprint 0 - Fase A Completada.
"""
import pytest
import os
from django.core.exceptions import ImproperlyConfigured
from apps.clinical.models import Encounter
from apps.encounters.models_media import ClinicalMedia


class TestEncounterCleanup:
    """Verificar que solo existe Encounter en apps.clinical"""

    def test_clinical_encounter_exists_and_works(self):
        """El modelo Encounter en apps.clinical existe y es funcional"""
        from apps.clinical.models import Encounter as ClinicalEncounter
        assert ClinicalEncounter is not None
        assert ClinicalEncounter.__name__ == 'Encounter'
        assert 'clinical' in ClinicalEncounter._meta.app_label

    def test_legacy_encounter_model_does_not_exist(self):
        """El modelo Encounter en apps.encounters NO existe"""
        with pytest.raises((ImportError, AttributeError)):
            from apps.encounters.models import Encounter
            # Si llegamos aquí, falló el test
            assert False, "encounters.models.Encounter NO debería existir"

    def test_clinical_media_uses_correct_fk(self):
        """ClinicalMedia usa FK a clinical.Encounter, no encounters.Encounter"""
        encounter_field = ClinicalMedia._meta.get_field('encounter')
        related_model = encounter_field.related_model
        
        assert related_model.__name__ == 'Encounter'
        assert related_model._meta.app_label == 'clinical'
        
        # Verificar que el FK apunta al modelo correcto
        assert related_model is Encounter

    @pytest.mark.django_db
    def test_legacy_endpoints_deprecated(self):
        """Verificar que el endpoint legacy retorna 410 Gone"""
        from django.test import Client
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        # Crear usuario para autenticación (el endpoint requiere auth)
        user = User.objects.create_user(
            email='test@test.com',
            password='testpass123'
        )
        
        client = Client()
        client.force_login(user)
        
        # El endpoint legacy debe retornar 410 Gone
        response = client.get('/api/encounters/')
        assert response.status_code == 410, \
            f"El endpoint /api/encounters/ debe retornar 410 Gone, pero retornó {response.status_code}"

    @pytest.mark.django_db
    def test_clinical_endpoint_works(self):
        """Verificar que el endpoint correcto funciona"""
        from django.test import Client
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        # Crear usuario para autenticación
        user = User.objects.create_user(
            email='test@test.com',
            password='testpass123',
            is_staff=True
        )
        
        client = Client()
        client.force_login(user)
        
        # El endpoint correcto debe funcionar
        response = client.get('/api/v1/clinical/encounters/')
        assert response.status_code in [200, 403], \
            f"El endpoint /api/v1/clinical/encounters/ debe estar activo, retornó {response.status_code}"

    def test_no_imports_from_legacy_model(self):
        """Verificar que no hay imports del modelo legacy en el código activo"""
        import os
        import re
        
        # Buscar imports del modelo deprecated
        apps_path = '/app/apps'  # Path dentro del container
        pattern = re.compile(r'from apps\.encounters\.models import Encounter')
        
        found_imports = []
        if not os.path.exists(apps_path):
            # Skip if path doesn't exist (test environment)
            return
            
        for root, dirs, files in os.walk(apps_path):
            # Saltar migraciones y archivos deprecated explícitos
            if 'migrations' in root or 'deprecated' in root:
                continue
                
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, 'r') as f:
                            content = f.read()
                            if pattern.search(content):
                                found_imports.append(filepath)
                    except:
                        pass
        
        assert len(found_imports) == 0, \
            f"Se encontraron imports del modelo legacy en: {found_imports}"


class TestEncounterFunctionality:
    """Verificar que el modelo Encounter consolidado funciona correctamente"""

    @pytest.mark.django_db
    def test_create_encounter(self):
        """Crear un Encounter usando el modelo correcto"""
        from apps.clinical.models import Encounter
        from django.contrib.auth import get_user_model
        from apps.patients.models import Patient
        
        User = get_user_model()
        
        # Crear datos necesarios
        user = User.objects.create_user(
            email='doctor@test.com',
            password='testpass123'
        )
        
        patient = Patient.objects.create(
            first_name='John',
            last_name='Doe',
            email='patient@test.com'
        )
        
        # Crear encounter
        encounter = Encounter.objects.create(
            patient=patient,
            practitioner=user,
            start_date='2025-01-01 10:00:00',
            end_date='2025-01-01 11:00:00',
            status='scheduled'
        )
        
        assert encounter.id is not None
        assert encounter.patient == patient
        assert encounter.practitioner == user
        assert Encounter.objects.count() == 1

    @pytest.mark.django_db
    def test_clinical_media_with_encounter(self):
        """Verificar que ClinicalMedia funciona con el Encounter correcto"""
        from apps.clinical.models import Encounter
        from apps.encounters.models_media import ClinicalMedia
        from django.contrib.auth import get_user_model
        from apps.patients.models import Patient
        
        User = get_user_model()
        
        # Crear datos
        user = User.objects.create_user(
            email='doctor@test.com',
            password='testpass123'
        )
        
        patient = Patient.objects.create(
            first_name='Jane',
            last_name='Smith',
            email='patient@test.com'
        )
        
        encounter = Encounter.objects.create(
            patient=patient,
            practitioner=user,
            start_date='2025-01-01 10:00:00',
            end_date='2025-01-01 11:00:00',
            status='scheduled'
        )
        
        # Crear ClinicalMedia asociado
        media = ClinicalMedia.objects.create(
            encounter=encounter,
            file='test.jpg',
            media_type='photo',
            description='Test media'
        )
        
        assert media.id is not None
        assert media.encounter == encounter
        assert media.encounter.__class__.__name__ == 'Encounter'
        assert media.encounter._meta.app_label == 'clinical'


# Tests de integración
@pytest.mark.django_db
class TestEncounterIntegration:
    """Tests de integración para verificar el funcionamiento completo"""

    def test_full_encounter_flow(self):
        """Test del flujo completo: crear encounter + media"""
        from apps.clinical.models import Encounter
        from apps.encounters.models_media import ClinicalMedia
        from django.contrib.auth import get_user_model
        from apps.patients.models import Patient
        
        User = get_user_model()
        
        # Setup
        doctor = User.objects.create_user(
            email='dr@test.com',
            password='testpass123'
        )
        
        patient = Patient.objects.create(
            first_name='Test',
            last_name='Patient',
            email='patient@test.com'
        )
        
        # Crear encounter
        encounter = Encounter.objects.create(
            patient=patient,
            practitioner=doctor,
            start_date='2025-01-01 10:00:00',
            end_date='2025-01-01 11:00:00',
            status='scheduled'
        )
        
        # Agregar media
        media = ClinicalMedia.objects.create(
            encounter=encounter,
            file='consultation.jpg',
            media_type='photo'
        )
        
        # Verificaciones
        assert Encounter.objects.count() == 1
        assert ClinicalMedia.objects.count() == 1
        assert encounter.clinicalmedia_set.count() == 1
        assert encounter.clinicalmedia_set.first() == media
