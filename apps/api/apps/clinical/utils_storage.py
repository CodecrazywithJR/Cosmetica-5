"""
MinIO Storage utilities for Clinical Photos and Documents.
Provides presigned URL generation for secure file access.
"""
import uuid
from datetime import timedelta
from django.conf import settings
from minio import Minio
from minio.error import S3Error


def get_minio_client():
    """Get configured MinIO client instance."""
    return Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_USE_SSL
    )


def generate_presigned_get_url(bucket_name: str, object_key: str, expires: timedelta = timedelta(hours=1)) -> str:
    """
    Generate presigned GET URL for downloading/viewing a file from MinIO.
    
    Args:
        bucket_name: MinIO bucket name
        object_key: Object key/path in bucket
        expires: URL expiration time (default 1 hour)
    
    Returns:
        Presigned URL string
    
    Raises:
        S3Error: If MinIO operation fails
    """
    client = get_minio_client()
    try:
        url = client.presigned_get_object(
            bucket_name=bucket_name,
            object_name=object_key,
            expires=expires
        )
        return url
    except S3Error as e:
        raise Exception(f"Failed to generate presigned GET URL: {e}")


def generate_presigned_put_url(
    bucket_name: str, 
    object_key: str, 
    content_type: str,
    expires: timedelta = timedelta(minutes=15)
) -> str:
    """
    Generate presigned PUT URL for uploading a file to MinIO.
    
    Args:
        bucket_name: MinIO bucket name
        object_key: Object key/path in bucket
        content_type: MIME type of file to upload
        expires: URL expiration time (default 15 minutes)
    
    Returns:
        Presigned URL string
    
    Raises:
        S3Error: If MinIO operation fails
    """
    client = get_minio_client()
    try:
        url = client.presigned_put_object(
            bucket_name=bucket_name,
            object_name=object_key,
            expires=expires
        )
        return url
    except S3Error as e:
        raise Exception(f"Failed to generate presigned PUT URL: {e}")


def generate_object_key(prefix: str, filename: str) -> str:
    """
    Generate unique object key for MinIO storage.
    
    Args:
        prefix: Folder prefix (e.g., 'photos', 'documents')
        filename: Original filename
    
    Returns:
        Unique object key string
    """
    unique_id = uuid.uuid4().hex[:12]
    # Sanitize filename
    safe_filename = "".join(c for c in filename if c.isalnum() or c in "._-")
    return f"{prefix}/{unique_id}_{safe_filename}"


def delete_object(bucket_name: str, object_key: str) -> None:
    """
    Delete an object from MinIO storage (hard delete).
    
    Args:
        bucket_name: MinIO bucket name
        object_key: Object key/path in bucket
    
    Raises:
        S3Error: If MinIO operation fails
    """
    client = get_minio_client()
    try:
        client.remove_object(bucket_name=bucket_name, object_name=object_key)
    except S3Error as e:
        raise Exception(f"Failed to delete object from MinIO: {e}")


def get_clinical_photo_url(photo) -> str:
    """
    Get presigned download URL for a ClinicalPhoto instance.
    
    Args:
        photo: ClinicalPhoto model instance
    
    Returns:
        Presigned URL valid for 1 hour
    """
    bucket = settings.MINIO_CLINICAL_BUCKET
    return generate_presigned_get_url(bucket, photo.object_key)


def get_document_url(document) -> str:
    """
    Get presigned download URL for a Document instance.
    
    Args:
        document: Document model instance
    
    Returns:
        Presigned URL valid for 1 hour
    """
    bucket = settings.MINIO_DOCUMENTS_BUCKET
    return generate_presigned_get_url(bucket, document.object_key)
