from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from apps.clinical.models import Encounter
from apps.clinical.models import EncounterPhoto
from apps.clinical.models import EncounterDocument

class Command(BaseCommand):
    help = 'Recalcula los contadores cacheados de adjuntos (fotos/documentos) en Encounter.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Recalculando contadores de adjuntos en Encounter...'))
        encounters = Encounter.objects.filter(is_deleted=False)
        total = encounters.count()
        updated = 0
        for encounter in encounters.iterator():
            # Contar fotos reales (ClinicalPhoto no eliminadas)
            photo_count = EncounterPhoto.objects.filter(
                encounter=encounter,
                clinical_photo__is_deleted=False
            ).count()
            # Contar documentos reales (Document no eliminados)
            document_count = EncounterDocument.objects.filter(
                encounter=encounter,
                document__is_deleted=False
            ).count()
            has_photos = photo_count > 0
            has_documents = document_count > 0
            changed = (
                encounter.photo_count_cached != photo_count or
                encounter.document_count_cached != document_count or
                encounter.has_photos_cached != has_photos or
                encounter.has_documents_cached != has_documents
            )
            if changed:
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
                updated += 1
        self.stdout.write(self.style.SUCCESS(f'Procesados: {total}, actualizados: {updated}'))
