"""
Image utilities for HEIC/HEIF conversion and thumbnail generation.
"""
import io
from PIL import Image
import pillow_heif

THUMBNAIL_SIZE = 512  # Max long side in px


def open_image_convert_heic(file):
    """
    Open an uploaded image file, converting HEIC/HEIF to RGB.
    Returns a Pillow Image object in RGB mode.
    """
    try:
        # Try to open as standard image
        img = Image.open(file)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        return img
    except Exception:
        # Try HEIC/HEIF
        file.seek(0)
        heif_file = pillow_heif.read_heif(file.read())
        img = Image.frombytes(
            heif_file.mode,
            heif_file.size,
            heif_file.data,
            "raw"
        )
        if img.mode != 'RGB':
            img = img.convert('RGB')
        return img


def save_jpg_to_bytes(img, quality=90):
    """
    Save Pillow Image to bytes as JPG.
    """
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=quality)
    buf.seek(0)
    return buf


def generate_thumbnail(img):
    """
    Generate thumbnail (long side = 512px) from Pillow Image.
    Returns Pillow Image.
    """
    img_copy = img.copy()
    img_copy.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.LANCZOS)
    return img_copy
