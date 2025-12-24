# Generated migration - Create default legal entity for France

from django.db import migrations
import uuid


def create_default_legal_entity(apps, schema_editor):
    """
    Create a default legal entity for the clinic in France.
    
    This allows the system to work immediately after migration,
    with the understanding that administrators will update the
    entity with actual registration data (SIREN, SIRET, etc.) later.
    
    Design Decision (ADR-002):
    - Single entity assumed initially
    - Placeholder data to be replaced by actual registration info
    - No fiscal logic - just legal entity identification
    """
    LegalEntity = apps.get_model('legal', 'LegalEntity')
    
    # Create default entity only if none exists
    if not LegalEntity.objects.exists():
        LegalEntity.objects.create(
            id=uuid.uuid4(),
            legal_name='Clinique de Dermatologie',  # Placeholder
            trade_name='',  # To be filled by administrator
            address_line_1='[À COMPLÉTER]',  # To be filled
            address_line_2='',
            postal_code='75001',  # Placeholder Paris postal code
            city='Paris',  # Placeholder
            country_code='FR',
            siren=None,  # To be filled after business registration
            siret=None,  # To be filled after business registration
            vat_number=None,  # To be filled if applicable
            currency='EUR',
            timezone='Europe/Paris',
            invoice_footer_text='',
            is_active=True,
        )


def reverse_default_legal_entity(apps, schema_editor):
    """
    Reverse migration - delete default entity.
    
    Note: This will fail if the entity is referenced by sales.
    That's intentional - we don't want to orphan data.
    """
    LegalEntity = apps.get_model('legal', 'LegalEntity')
    LegalEntity.objects.filter(
        legal_name='Clinique de Dermatologie',
        address_line_1='[À COMPLÉTER]'
    ).delete()


class Migration(migrations.Migration):
    """
    Data migration to create default legal entity.
    
    Purpose: Allow system to function immediately after migration.
    
    IMPORTANT:
    - This is placeholder data
    - Must be updated by administrators with actual registration info
    - See: LEGAL_READINESS.md for setup instructions
    """

    dependencies = [
        ('legal', '0001_create_legal_entity'),
    ]

    operations = [
        migrations.RunPython(
            create_default_legal_entity,
            reverse_default_legal_entity
        ),
    ]
