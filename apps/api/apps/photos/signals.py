"""
Photo signals - trigger Celery tasks on photo upload.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import SkinPhoto
from .tasks import generate_thumbnail


@receiver(post_save, sender=SkinPhoto)
def on_photo_created(sender, instance, created, **kwargs):
    """
    Trigger thumbnail generation when a new photo is uploaded.
    """
    if created and instance.image:
        # Enqueue async task
        generate_thumbnail.delay(instance.id)
