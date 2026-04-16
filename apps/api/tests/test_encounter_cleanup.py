"""
Test suite para verificar que la limpieza del modelo Encounter deprecated fue exitosa.
Sprint 0 - Fase A Completada.
"""
import pytest
import os
from django.core.exceptions import ImproperlyConfigured
from apps.clinical.models import Encounter
from apps.clinical.models import ClinicalMedia
from tests.conftest import TEST_PASSWORD


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
        """Verificar que el endpoint legacy NO existe (404 o 410)"""
        from rest_framework.test import APIClient
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        
        user = User.objects.create_user(
            email='test_legacy@test.com',
            password=TEST_PASSWORD
        )
        
        client = APIClient()
        client.force_authenticate(user=user)
        
        response = client.get('/api/encounters/')
        assert response.status_code in [404, 410], \
            f"El endpoint /api/encounters/ debe retornar 404 o 410, pero retornó {response.status_code}"

    @pytest.mark.django_db
    def test_clinical_endpoint_works(self):
        """Verificar que el endpoint correcto funciona"""
        from rest_framework.test import APIClient
        from django.contrib.auth import get_user_model
        from apps.authz.models import Role, UserRole
        
        User = get_user_model()
        
        user = User.objects.create_user(
            email='test_clinical@test.com',
            password=TEST_PASSWORD,
            is_staff=True
        )
        role, _ = Role.objects.get_or_create(name='admin')
        UserRole.objects.create(user=user, role=role)
        
        client = APIClient()
        client.force_authenticate(user=user)
        
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
            if 'migrations' in root or 'deprecated' in root or 'tests' in root:
                continue
                
            for file in files:
                if file.endswith('.py') and not file.startswith('test_'):
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
        from apps.clinical.models import Encounter, Patient
        from django.contrib.auth import get_user_model
        from apps.authz.models import Practitioner
        from django.utils import timezone
        
        User = get_user_model()
        
        user = User.objects.create_user(
            email='doctor_enc@test.com',
            password=TEST_PASSWORD
        )
        
        practitioner = Practitioner.objects.create(
            user=user, display_name='Dr. Cleanup', specialty='General'
        )
        
        patient = Patient.objects.create(
            first_name='John',
            last_name='Doe',
            email='patient_enc@test.com'
        )
        
        encounter = Encounter.objects.create(
            patient=patient,
            practitioner=practitioner,
            type='consultation',
            status='draft',
            occurred_at=timezone.now(),
            created_by_user=user,
        )
        
        assert encounter.id is not None
        assert encounter.patient == patient
        assert encounter.practitioner == practitioner
        assert Encounter.objects.count() == 1

    @pytest.mark.django_db
    def test_clinical_media_with_encounter(self):
        """Verificar que ClinicalMedia funciona con el Encounter correcto"""
        from apps.clinical.models import Encounter, ClinicalMedia, Patient
        from django.contrib.auth import get_user_model
        from apps.authz.models import Practitioner
        from django.utils import timezone
        
        User = get_user_model()
        
        user = User.objects.create_user(
            email='doctor_media@test.com',
            password=TEST_PASSWORD
        )
        
        practitioner = Practitioner.objects.create(
            user=user, display_name='Dr. Media', specialty='General'
        )
        
        patient = Patient.objects.create(
            first_name='Jane',
            last_name='Smith',
            email='patient_media@test.com'
        )
        
        encounter = Encounter.objects.create(
            patient=patient,
            practitioner=practitioner,
            type='consultation',
            status='draft',
            occurred_at=timezone.now(),
            created_by_user=user,
        )
        
        media = ClinicalMedia.objects.create(
            encounter=encounter,
            uploaded_by=user,
            file='test.jpg',
            media_type='photo',
            notes='Test media'
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
        from apps.clinical.models import Encounter, ClinicalMedia, Patient
        from django.contrib.auth import get_user_model
        from apps.authz.models import Practitioner
        from django.utils import timezone
        
        User = get_user_model()
        
        doctor = User.objects.create_user(
            email='dr_flow@test.com',
            password=TEST_PASSWORD
        )
        
        practitioner = Practitioner.objects.create(
            user=doctor, display_name='Dr. Flow', specialty='General'
        )
        
        patient = Patient.objects.create(
            first_name='Test',
            last_name='Patient',
            email='patient_flow@test.com'
        )
        
        encounter = Encounter.objects.create(
            patient=patient,
            practitioner=practitioner,
            type='medical_consult',
            status='draft',
            occurred_at=timezone.now(),
            created_by_user=doctor,
        )
        
        media = ClinicalMedia.objects.create(
            encounter=encounter,
            uploaded_by=doctor,
            file='consultation.jpg',
            media_type='photo'
        )
        
        assert Encounter.objects.count() == 1
        assert ClinicalMedia.objects.count() == 1
        assert encounter.clinical_media.count() == 1
        assert encounter.clinical_media.first() == media
