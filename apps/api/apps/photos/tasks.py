"""
Celery tasks for photo processing.
"""
from celery import shared_task
from PIL import Image
from io import BytesIO
from django.core.files.uploadedfile import InMemoryUploadedFile
import sys


@shared_task(name='apps.photos.tasks.generate_thumbnail')
def generate_thumbnail(photo_id):
    """
    Generate thumbnail for a skin photo.
    
    Args:
        photo_id: SkinPhoto model ID
    """
    from .models import SkinPhoto
    
    try:
        photo = SkinPhoto.objects.get(id=photo_id)
        
        # Open original image
        img = Image.open(photo.image)
        
        # Convert to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        # Create thumbnail
        thumbnail_size = (300, 300)
        img.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
        
        # Save to BytesIO
        output = BytesIO()
        img.save(output, format='JPEG', quality=85)
        output.seek(0)
        
        # Create Django file
        thumbnail_file = InMemoryUploadedFile(
            output,
            'ImageField',
            f"thumb_{photo.image.name.split('/')[-1]}",
            'image/jpeg',
            sys.getsizeof(output),
            None
        )
        
        # Save thumbnail
        photo.thumbnail.save(
            f"thumb_{photo.id}.jpg",
            thumbnail_file,
            save=False
        )
        photo.thumbnail_generated = True
        photo.save()
        
        return f"Thumbnail generated for photo {photo_id}"
        
    except Exception as e:
        return f"Error generating thumbnail for photo {photo_id}: {str(e)}"
