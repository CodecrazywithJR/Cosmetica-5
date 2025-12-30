"""
Attachment counter utilities for Encounter (v1.1)
"""
from django.db import transaction
from apps.clinical.models import Encounter, EncounterPhoto, EncounterDocument

def recalc_attachment_counters(encounter_id):
    """
    Recalcula y persiste los contadores cacheados de adjuntos para un Encounter.
    Siempre cuenta desde la BD (ignora valores previos).
    Transaccional: debe llamarse dentro de la misma transacción que el upload/delete.
    """
    encounter = Encounter.objects.select_for_update().get(id=encounter_id)
    photo_count = EncounterPhoto.objects.filter(
        encounter=encounter,
        clinical_photo__is_deleted=False
    ).count()
    document_count = EncounterDocument.objects.filter(
        encounter=encounter,
        document__is_deleted=False
    ).count()
    has_photos = photo_count > 0
    has_documents = document_count > 0
    encounter.photo_count_cached = photo_count
    encounter.document_count_cached = document_count
    encounter.has_photos_cached = has_photos
    encounter.has_documents_cached = has_documents
    encounter.save(update_fields=[
        'photo_count_cached',
        'document_count_cached',
        'has_photos_cached',
        'has_documents_cached',
    ])
