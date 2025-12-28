"""
Encounter models - DEPRECATED APP

⚠️ DEPRECATION NOTICE ⚠️
Date: 2025-12-25
Status: DEPRECATED - DO NOT USE

The Encounter model in this module has been REMOVED.
USE: apps.clinical.models.Encounter (modern, production model)

Reasons for deprecation:
1. Incorrect FK to User (should be Practitioner)
2. Not linked with Appointment model
3. Lacks proper clinical workflow integration
4. Legacy endpoint /api/encounters/ not used by frontend

Migration Path:
- ✅ Use apps.clinical.models.Encounter for all code
- ✅ Use /api/v1/clinical/encounters/ endpoint
- ❌ DO NOT import from apps.encounters.models.Encounter (REMOVED)

Note: ClinicalMedia in this module is ACTIVE and should continue to be used.
Import from apps.encounters.models_media.ClinicalMedia or via this module's __all__.

This module now only exports ClinicalMedia for backward compatibility.
"""
from django.db import models

# Import ClinicalMedia for unified access
from .models_media import ClinicalMedia

__all__ = ['ClinicalMedia']  # Encounter REMOVED - use apps.clinical.models.Encounter
