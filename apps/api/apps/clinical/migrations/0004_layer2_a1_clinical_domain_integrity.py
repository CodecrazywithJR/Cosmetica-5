# Generated migration for Layer 2 A1: Clinical Domain Integrity

from django.db import migrations, models


def clean_inconsistent_encounter_appointments(apps, schema_editor):
    """
    Data migration to clean up encounters with inconsistent appointments.
    
    BUSINESS RULE: If encounter.appointment exists, then
    encounter.patient MUST == appointment.patient.
    
    Strategy: Set appointment to NULL for encounters where patients don't match.
    Log all changes to ClinicalAuditLog for traceability.
    """
    Encounter = apps.get_model('encounters', 'Encounter')
    Appointment = apps.get_model('clinical', 'Appointment')
    ClinicalAuditLog = apps.get_model('clinical', 'ClinicalAuditLog')
    
    # Find encounters with appointments where patients don't match
    inconsistent_encounters = []
    
    for encounter in Encounter.objects.select_related('appointment', 'patient').filter(
        appointment__isnull=False
    ):
        if encounter.appointment and encounter.appointment.patient_id != encounter.patient_id:
            inconsistent_encounters.append({
                'encounter_id': encounter.id,
                'encounter_patient_id': encounter.patient_id,
                'appointment_id': encounter.appointment.id,
                'appointment_patient_id': encounter.appointment.patient_id,
            })
    
    if inconsistent_encounters:
        print(f"\n⚠️  Found {len(inconsistent_encounters)} encounters with patient-appointment mismatch:")
        
        for item in inconsistent_encounters:
            print(f"  - Encounter {item['encounter_id']}: "
                  f"encounter.patient={item['encounter_patient_id']} vs "
                  f"appointment.patient={item['appointment_patient_id']}")
            
            # Get the encounter object
            encounter = Encounter.objects.get(pk=item['encounter_id'])
            
            # Log to audit trail BEFORE fixing
            ClinicalAuditLog.objects.create(
                actor_user=None,  # System action
                action='update',
                entity_type='Encounter',
                entity_id=encounter.id,
                patient_id=encounter.patient_id,
                appointment_id=encounter.appointment_id,
                metadata={
                    'reason': 'Data migration: Layer 2 A1 - Clean inconsistent appointment',
                    'before': {
                        'appointment_id': str(encounter.appointment_id),
                        'patient_id': str(encounter.patient_id),
                    },
                    'after': {
                        'appointment_id': None,
                        'patient_id': str(encounter.patient_id),
                    },
                    'inconsistency': {
                        'encounter_patient_id': str(item['encounter_patient_id']),
                        'appointment_patient_id': str(item['appointment_patient_id']),
                    },
                    'migration': '0004_layer2_a1_clinical_domain_integrity'
                }
            )
            
            # Fix: Remove appointment reference
            encounter.appointment = None
            encounter.save(update_fields=['appointment'])
        
        print(f"✅ Fixed {len(inconsistent_encounters)} encounters (appointment set to NULL)")
        print(f"   All changes logged to ClinicalAuditLog for traceability")
    else:
        print("✅ No inconsistent encounter-appointment relationships found")


def clean_inconsistent_photo_encounters(apps, schema_editor):
    """
    Data migration to clean up SkinPhotos with inconsistent encounters.
    
    BUSINESS RULE: If photo.encounter exists, then
    photo.patient MUST == encounter.patient.
    
    Strategy: Set encounter to NULL for photos where patients don't match.
    """
    SkinPhoto = apps.get_model('photos', 'SkinPhoto')
    ClinicalAuditLog = apps.get_model('clinical', 'ClinicalAuditLog')
    
    # Find photos with encounters where patients don't match
    inconsistent_photos = []
    
    for photo in SkinPhoto.objects.select_related('encounter', 'patient').filter(
        encounter__isnull=False
    ):
        if photo.encounter and photo.encounter.patient_id != photo.patient_id:
            inconsistent_photos.append({
                'photo_id': photo.id,
                'photo_patient_id': photo.patient_id,
                'encounter_id': photo.encounter.id,
                'encounter_patient_id': photo.encounter.patient_id,
            })
    
    if inconsistent_photos:
        print(f"\n⚠️  Found {len(inconsistent_photos)} photos with patient-encounter mismatch:")
        
        for item in inconsistent_photos:
            print(f"  - Photo {item['photo_id']}: "
                  f"photo.patient={item['photo_patient_id']} vs "
                  f"encounter.patient={item['encounter_patient_id']}")
            
            # Get the photo object
            photo = SkinPhoto.objects.get(pk=item['photo_id'])
            
            # Log to audit trail (reuse ClinicalAuditLog for consistency)
            ClinicalAuditLog.objects.create(
                actor_user=None,  # System action
                action='update',
                entity_type='ClinicalPhoto',  # Using same terminology
                entity_id=photo.id,
                patient_id=photo.patient_id,
                metadata={
                    'reason': 'Data migration: Layer 2 A1 - Clean inconsistent encounter',
                    'before': {
                        'encounter_id': str(photo.encounter_id),
                        'patient_id': str(photo.patient_id),
                    },
                    'after': {
                        'encounter_id': None,
                        'patient_id': str(photo.patient_id),
                    },
                    'inconsistency': {
                        'photo_patient_id': str(item['photo_patient_id']),
                        'encounter_patient_id': str(item['encounter_patient_id']),
                    },
                    'migration': '0004_layer2_a1_clinical_domain_integrity'
                }
            )
            
            # Fix: Remove encounter reference
            photo.encounter = None
            photo.save(update_fields=['encounter'])
        
        print(f"✅ Fixed {len(inconsistent_photos)} photos (encounter set to NULL)")
        print(f"   All changes logged to ClinicalAuditLog for traceability")
    else:
        print("✅ No inconsistent photo-encounter relationships found")


class Migration(migrations.Migration):

    dependencies = [
        ('encounters', '0001_initial'),  # Adjust to your latest migration
        ('photos', '0001_initial'),      # Adjust to your latest migration
        ('clinical', '0003_clinical_audit_log'),
    ]

    operations = [
        # Step 1: Clean inconsistent data BEFORE adding constraints
        migrations.RunPython(
            clean_inconsistent_encounter_appointments,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            clean_inconsistent_photo_encounters,
            reverse_code=migrations.RunPython.noop,
        ),
        
        # Step 2: Add timeline index to Encounter
        migrations.AddIndex(
            model_name='encounter',
            index=models.Index(
                fields=['patient', '-created_at'],
                name='idx_encounter_patient_timeline'
            ),
        ),
        
        # Step 3: Add timeline index to ClinicalPhoto (if exists in clinical app)
        # Note: This assumes ClinicalPhoto is in clinical app
        # If the model structure is different, adjust accordingly
    ]
