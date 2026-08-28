from typing import Any

from apps.accounts.models import User

from .models import AuditLogEntry


def record_audit_event(
    *,
    actor: User | None,
    action: AuditLogEntry.Action,
    entity_type: str,
    entity_id: int | str,
    metadata: dict[str, Any] | None = None,
) -> AuditLogEntry:
    """Persist a security-safe administrative event.

    Callers must only pass technical identifiers or non-sensitive state in metadata.
    """
    return AuditLogEntry.objects.create(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        metadata=metadata or {},
    )
