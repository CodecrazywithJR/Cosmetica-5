# Generated manually for business rules implementation

from django.db import migrations, models
import django.db.models.deletion


def migrate_appointment_statuses(apps, schema_editor):
    """
    Migrate existing appointment statuses to new business rule statuses.
    
    Old -> New mapping:
    - scheduled -> draft
    - confirmed -> confirmed (no change)
    - attended -> completed
    - no_show -> no_show (no change)
    - cancelled -> cancelled (no change)
    """
    Appointment = apps.get_model('clinical', 'Appointment')
    
    # Map old statuses to new ones
    status_mapping = {
        'scheduled': 'draft',
        'confirmed': 'confirmed',
        'attended': 'completed',
        'no_show': 'no_show',
        'cancelled': 'cancelled',
    }
    
    for old_status, new_status in status_mapping.items():
        Appointment.objects.filter(status=old_status).update(status=new_status)


def reverse_migrate_appointment_statuses(apps, schema_editor):
    """Reverse migration - map new statuses back to old ones."""
    Appointment = apps.get_model('clinical', 'Appointment')
    
    # Map new statuses back to old ones
    status_mapping = {
        'draft': 'scheduled',
        'confirmed': 'confirmed',
        'checked_in': 'confirmed',  # Best approximation
        'completed': 'attended',
        'no_show': 'no_show',
        'cancelled': 'cancelled',
    }
    
    for new_status, old_status in status_mapping.items():
        Appointment.objects.filter(status=new_status).update(status=old_status)


class Migration(migrations.Migration):

    dependencies = [
        ('clinical', '0001_initial'),
    ]

    operations = [
        # Step 1: Migrate existing data to new status values
        migrations.RunPython(
            migrate_appointment_statuses,
            reverse_migrate_appointment_statuses
        ),
        
        # Step 2: Update status field choices
        migrations.AlterField(
            model_name='appointment',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('confirmed', 'Confirmed'),
                    ('checked_in', 'Checked In'),
                    ('completed', 'Completed'),
                    ('cancelled', 'Cancelled'),
                    ('no_show', 'No Show')
                ],
                max_length=20
            ),
        ),
        
        # Step 3: Make patient field required (NOT NULL)
        # Note: This assumes all existing appointments have a patient
        # If not, you need to handle orphaned appointments first
        migrations.AlterField(
            model_name='appointment',
            name='patient',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='appointments',
                to='clinical.patient'
            ),
        ),
    ]
