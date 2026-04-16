"""
MinIO Storage utilities for Clinical Photos and Documents.
Provides presigned URL generation with correct public hostnames.

ARCHITECTURE:
- Internal client (minio:9000) for direct operations (list, delete)
- Public client (localhost:9000) for presigned URLs only
"""
import uuid
import logging
from datetime import timedelta
from django.conf import settings
from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)


def get_minio_client_internal():
    """
    Get MinIO client for INTERNAL operations (list, delete, etc).
    Uses internal Docker hostname (minio:9000).
    """
    return Minio(
        settings.MINIO_ENDPOINT,  # minio:9000
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_USE_SSL
    )


def get_minio_client_public():
    """
    Get MinIO client for PRESIGNED URL generation.
    Uses public hostname (localhost:9000 in dev, real domain in prod).
    
    CRITICAL: This client should ONLY be used for generating presigned URLs.
    For actual operations (list, delete), use get_minio_client_internal().
    
    Region is set to 'us-east-1' to avoid auto-discovery which would
    require connection to MinIO (fails from container with localhost endpoint).
    """
    # Use public endpoint for presigned URLs
    public_endpoint = getattr(settings, 'MINIO_PUBLIC_ENDPOINT', settings.MINIO_ENDPOINT)
    
    return Minio(
        public_endpoint,  # localhost:9000 or real domain
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_USE_SSL,
        region='us-east-1'  # Explicit region to avoid auto-discovery connection
    )


def generate_presigned_get_url(bucket_name: str, object_key: str, expires: timedelta = timedelta(hours=1)) -> str:
    """
    Generate presigned GET URL for downloading/viewing a file from MinIO.
    
    Uses PUBLIC client to ensure URLs work from browser.
    
    Args:
        bucket_name: MinIO bucket name
        object_key: Object key/path in bucket
        expires: URL expiration time (default 1 hour)
    
    Returns:
        Presigned URL string with public hostname (localhost:9000 in dev)
    
    Raises:
        S3Error: If MinIO operation fails
    """
    # CRITICAL: Use public client for presigned URLs
    client = get_minio_client_public()
    
    try:
        url = client.presigned_get_object(
            bucket_name=bucket_name,
            object_name=object_key,
            expires=expires
        )
        logger.info(f"[Storage] Generated presigned GET URL: {url[:60]}...")
        return url
    except S3Error as e:
        logger.error(f"[Storage] Failed to generate presigned GET URL: {e}")
        raise RuntimeError(f"Failed to generate presigned GET URL: {e}") from e


def generate_presigned_put_url(
    bucket_name: str, 
    object_key: str, 
    content_type: str = '',  # noqa: S1172 - kept for API compatibility
    expires: timedelta = timedelta(minutes=15)
) -> str:
    """
    Generate presigned PUT URL for uploading a file to MinIO.
    
    Uses PUBLIC client to ensure URLs work from browser.
    
    Args:
        bucket_name: MinIO bucket name
        object_key: Object key/path in bucket
        content_type: MIME type of file to upload
        expires: URL expiration time (default 15 minutes)
    
    Returns:
        Presigned URL string with public hostname (localhost:9000 in dev)
    
    Raises:
        S3Error: If MinIO operation fails
    """
    # CRITICAL: Use public client for presigned URLs
    client = get_minio_client_public()
    
    try:
        url = client.presigned_put_object(
            bucket_name=bucket_name,
            object_name=object_key,
            expires=expires
        )
        logger.info(f"[Storage] Generated presigned PUT URL: {url[:60]}...")
        return url
    except S3Error as e:
        logger.error(f"[Storage] Failed to generate presigned PUT URL: {e}")
        raise RuntimeError(f"Failed to generate presigned PUT URL: {e}") from e


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
    
    Uses INTERNAL client for direct operations.
    
    Args:
        bucket_name: MinIO bucket name
        object_key: Object key/path in bucket
    
    Raises:
        S3Error: If MinIO operation fails
    """
    # Use internal client for direct operations
    client = get_minio_client_internal()
    
    try:
        client.remove_object(bucket_name=bucket_name, object_name=object_key)
        logger.info(f"[Storage] Deleted object: {bucket_name}/{object_key}")
    except S3Error as e:
        logger.error(f"[Storage] Failed to delete object: {e}")
        raise RuntimeError(f"Failed to delete object from MinIO: {e}") from e


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
