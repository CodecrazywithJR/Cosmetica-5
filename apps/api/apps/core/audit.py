"""
Audit helper — ``log_clinical_access()``

Provides a single function to record meaningful clinical-data accesses
into ``ClinicalAccessLog``.  Call it from view-layer code only; it is
**not** wired into signals or middleware.

Usage::

    from apps.core.audit import log_clinical_access
    from apps.clinical.audit_access_log import ClinicalAccessAction

    log_clinical_access(
        request,
        action=ClinicalAccessAction.VIEW_PATIENT,
        patient=patient_instance,
        resource=patient_instance,
    )
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _get_client_ip(request) -> Optional[str]:
    """Best-effort client IP extraction (X-Forwarded-For aware)."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def log_clinical_access(request, *, action: str, patient=None, resource=None):
    """
    Write one ``ClinicalAccessLog`` row.

    Parameters
    ----------
    request : DRF / Django request
        Used to extract *user*, *tenant*, *IP*, and *User-Agent*.
    action : str
        One of the ``ClinicalAccessAction`` constants.
    patient : Patient | None
        The patient whose data is being accessed.
    resource : Model | None
        The specific resource instance (Patient, Encounter, …).
        ``resource_type`` and ``resource_id`` are derived from it.
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return  # anonymous — nothing to log

    tenant = getattr(request, "tenant", None)
    if tenant is None:
        # Fallback: resolve from user
        tenant = getattr(user, "legal_entity", None)
    if tenant is None:
        # Cannot record without a tenant (superuser w/o header, system calls)
        logger.debug("log_clinical_access: skipped — no tenant (action=%s)", action)
        return

    resource_type = ""
    resource_id = None
    if resource is not None:
        resource_type = type(resource).__name__
        resource_id = getattr(resource, "pk", None)

    from apps.clinical.audit_access_log import ClinicalAccessLog  # late import

    try:
        ClinicalAccessLog.objects.create(
            legal_entity=tenant,
            user=user,
            patient=patient,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=_get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:1000] or None,
        )
    except Exception:
        logger.exception("Failed to write ClinicalAccessLog (action=%s)", action)
