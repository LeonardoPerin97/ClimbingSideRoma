import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from django.core.files.storage import Storage
from django.db import transaction

from apps.core.audit import record_audit_event
from apps.core.models import AuditLogEntry

from .models import User

if TYPE_CHECKING:
    from .forms import ProfileUpdateForm

logger = logging.getLogger(__name__)


def save_profile_changes(
    form: "ProfileUpdateForm",
    *,
    actor: User,
    old_image_name: str,
) -> tuple[User, AuditLogEntry.Action | None]:
    profile_user = form.instance
    storage = profile_user.profile_image.storage
    action: AuditLogEntry.Action | None = None

    try:
        with transaction.atomic():
            profile_user = form.save()
            new_image_name = profile_user.profile_image.name
            if new_image_name != old_image_name:
                action = (
                    AuditLogEntry.Action.REPLACE if old_image_name else AuditLogEntry.Action.UPLOAD
                )
                record_audit_event(
                    actor=actor,
                    action=action,
                    entity_type="profile_image",
                    entity_id=profile_user.pk,
                )
                if old_image_name:
                    schedule_profile_image_file_deletion(storage, old_image_name)
    except Exception:
        new_image_name = profile_user.profile_image.name
        if (
            new_image_name
            and new_image_name != old_image_name
            and profile_user.profile_image._committed
        ):
            _safe_delete(storage, new_image_name)
        raise

    return profile_user, action


def delete_profile_image(*, profile_user: User, actor: User) -> bool:
    with transaction.atomic():
        locked_user = User.objects.select_for_update().get(pk=profile_user.pk)
        stored_name = locked_user.profile_image.name
        if not stored_name:
            return False
        storage = locked_user.profile_image.storage
        locked_user.profile_image = ""
        locked_user.save(update_fields=("profile_image",))
        record_audit_event(
            actor=actor,
            action=AuditLogEntry.Action.DELETE,
            entity_type="profile_image",
            entity_id=locked_user.pk,
        )
        schedule_profile_image_file_deletion(storage, stored_name)
    profile_user.profile_image = ""
    return True


def schedule_profile_image_file_deletion(storage: Storage, name: str) -> None:
    transaction.on_commit(_safe_delete_callback(storage, name))


def _safe_delete_callback(storage: Storage, name: str) -> Callable[[], None]:
    return lambda: _safe_delete(storage, name)


def _safe_delete(storage: Storage, name: str) -> None:
    try:
        storage.delete(name)
    except Exception:
        logger.exception("profile_image_storage_cleanup_failed")
