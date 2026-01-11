"""Utility functions for POS operations."""
import re
from typing import Optional


def normalize_phone_to_e164(phone: str) -> Optional[str]:
    """
    Normalize phone to E.164 format.
    
    Simple implementation: strip non-digits, ensure it starts with +.
    Real implementation should use phonenumbers library.
    
    Args:
        phone: Phone number in any format
        
    Returns:
        E.164 formatted phone or None if invalid
    """
    if not phone:
        return None
    
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    # If doesn't start with +, assume it's missing country code
    if not cleaned.startswith('+'):
        # Default to Mexico +52 if no country code (adjust as needed)
        cleaned = '+52' + cleaned
    
    # Basic validation: should have at least 10 digits after +
    if len(cleaned) < 11:  # + and at least 10 digits
        return None
    
    return cleaned


def mask_phone(phone_e164: Optional[str]) -> str:
    """
    Mask phone number for display.
    
    Shows country code + last 3 digits.
    Example: +521234567890 -> +52*******890
    """
    if not phone_e164:
        return ""
    
    if len(phone_e164) < 6:
        return phone_e164
    
    # Keep country code (first 3 chars) and last 3 digits
    country_code = phone_e164[:3]
    last_digits = phone_e164[-3:]
    masked_middle = '*' * (len(phone_e164) - 6)
    
    return f"{country_code}{masked_middle}{last_digits}"


def mask_email(email: Optional[str]) -> str:
    """
    Mask email for display.
    
    Shows first letter + *** + @domain
    Example: john.doe@example.com -> j***@example.com
    """
    if not email or '@' not in email:
        return ""
    
    local, domain = email.split('@', 1)
    
    if len(local) == 0:
        return email
    
    masked_local = local[0] + '***'
    return f"{masked_local}@{domain}"


def normalize_search_query(query: str) -> str:
    """
    Normalize search query for consistent matching.
    
    - Strip whitespace
    - Lowercase
    - Collapse multiple spaces
    """
    if not query:
        return ""
    
    normalized = query.strip().lower()
    # Collapse multiple spaces into one
    normalized = re.sub(r'\s+', ' ', normalized)
    
    return normalized


def is_email_like(query: str) -> bool:
    """Check if query looks like an email address."""
    return '@' in query and '.' in query.split('@')[-1] if query else False


def is_phone_like(query: str) -> bool:
    """Check if query looks like a phone number."""
    # Simple heuristic: contains mostly digits and possibly + or -
    if not query:
        return False
    
    digit_count = sum(c.isdigit() for c in query)
    total_chars = len(query.replace(' ', '').replace('-', '').replace('+', '').replace('(', '').replace(')', ''))
    
    # If >70% digits, consider it phone-like
    return digit_count / max(total_chars, 1) > 0.7
