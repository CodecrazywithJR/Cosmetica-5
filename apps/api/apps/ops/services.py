"""
Audit log service.

Single entry-point for recording domain events.  Must be called
explicitly from services, viewsets and state-machine transitions.
No Django signals are used.

Usage::

    from apps.ops.services import log_event
    from apps.ops.models import AuditEventType

    log_event(
        user=request.user,
        legal_entity=request.user.legal_entity,
        entity_type='Patient',
        entity_id=patient.pk,
        event_type=AuditEventType.PATIENT_CREATED,
        payload={'first_name': patient.first_name},
    )
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


def log_event(
    *,
    user,
    legal_entity,
    entity_type: str,
    entity_id: UUID,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """
    Create an immutable AuditLog entry.

    Args:
        user:         User instance or None (for system/Celery actions).
        legal_entity: LegalEntity instance — must not be None.
        entity_type:  String name of the domain entity (e.g. "Patient").
        entity_id:    UUID primary key of the entity.
        event_type:   One of AuditEventType choices (or arbitrary string).
        payload:      Optional dict of JSON-serialisable data.

    Raises:
        ValueError: if ``legal_entity`` is None.

    The function never raises for serialisation failures — it logs a
    warning and stores an empty payload instead, so the main request
    flow is never disrupted.
    """
    from apps.ops.models import AuditLog

    if legal_entity is None:
        raise ValueError(
            'log_event() requires legal_entity; got None. '
            'Provide the owning LegalEntity for tenant isolation.'
        )

    safe_payload = _coerce_payload(payload)

    try:
        AuditLog.objects.create(
            user=user,
            legal_entity=legal_entity,
            entity_type=entity_type,
            entity_id=entity_id,
            event_type=event_type,
            payload_json=safe_payload,
        )
    except Exception:  # pragma: no cover — DB failures must not abort requests
        logger.exception(
            'Failed to write AuditLog entry for %s#%s event=%s',
            entity_type,
            entity_id,
            event_type,
        )


def _coerce_payload(payload: Any) -> dict:
    """Return a JSON-safe dict or {} on failure."""
    import json

    if payload is None:
        return {}

    try:
        # Round-trip through JSON to surface non-serialisable values early.
        return json.loads(json.dumps(payload, default=str))
    except (TypeError, ValueError):
        logger.warning('AuditLog payload is not JSON-serialisable; storing {}.')
        return {}
