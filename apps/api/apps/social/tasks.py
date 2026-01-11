"""
Celery tasks for social media operations.
"""
import os
import zipfile
from io import BytesIO
from celery import shared_task
from django.conf import settings
from django.utils import timezone


@shared_task
def generate_instagram_pack(post_id):
    """
    Generate Instagram publish pack (ZIP file).
    
    Contents:
    - caption.txt: Full caption with hashtags
    - image_1.jpg, image_2.jpg, etc.: Media files from marketing bucket
    
    Args:
        post_id: InstagramPost ID
    
    Returns:
        str: Path to generated ZIP file
    """
    from apps.social.models import InstagramPost
    from minio import Minio
    
    try:
        post = InstagramPost.objects.get(id=post_id)
    except InstagramPost.DoesNotExist:
        return f"Error: Post {post_id} not found"
    
    if not post.can_generate_pack():
        return f"Error: Post {post_id} cannot generate pack (status={post.status}, media_count={len(post.media_keys)})"
    
    # Initialize MinIO client
    minio_client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_USE_SSL
    )
    
    # Create ZIP in memory
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add caption.txt
        caption = post.get_full_caption()
        zip_file.writestr('caption.txt', caption.encode('utf-8'))
        
        # Add media files from marketing bucket
        for idx, media_key in enumerate(post.media_keys, start=1):
            try:
                # Get file extension
                _, ext = os.path.splitext(media_key)
                if not ext:
                    ext = '.jpg'  # Default to jpg
                
                # Download from MinIO marketing bucket
                response = minio_client.get_object(settings.MINIO_MARKETING_BUCKET, media_key)
                media_data = response.read()
                response.close()
                response.release_conn()
                
                # Add to ZIP
                filename = f"image_{idx}{ext}"
                zip_file.writestr(filename, media_data)
                
            except Exception as e:
                # Log error but continue with other files
                print(f"Error downloading {media_key}: {str(e)}")
                continue
        
        # Add metadata.txt
        metadata = f"""Instagram Post Pack
Generated: {timezone.now().isoformat()}
Post ID: {post.id}
Language: {post.language}
Status: {post.status}
Media Count: {len(post.media_keys)}

--- Instructions ---
1. Review caption.txt
2. Open Instagram app on your phone
3. Create new post
4. Select all images in order (image_1, image_2, etc.)
5. Paste caption from caption.txt
6. Publish
7. Copy the post URL
8. Update this post in admin with the URL and mark as Published
"""
        zip_file.writestr('README.txt', metadata.encode('utf-8'))
    
    # Save ZIP to local storage (could also save to MinIO)
    zip_filename = f"instagram_pack_{post.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.zip"
    zip_path = os.path.join('/tmp', zip_filename)  # In production, use proper storage
    
    with open(zip_path, 'wb') as f:
        f.write(zip_buffer.getvalue())
    
    # Update post
    post.pack_generated_at = timezone.now()
    post.pack_file_path = zip_path
    post.save()
    
    return zip_path
