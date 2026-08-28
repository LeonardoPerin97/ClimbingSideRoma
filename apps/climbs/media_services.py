import logging
from collections.abc import Callable

from django.core.files.storage import Storage
from django.db import transaction
from django.db.models.fields.files import FieldFile

from apps.accounts.models import User

from .annotations import empty_route_annotation
from .models import ClimbingRoute, RouteImage

logger = logging.getLogger(__name__)


def save_route_image(
    *,
    climbing_route: ClimbingRoute,
    actor: User,
    upload: FieldFile,
    existing: RouteImage | None,
) -> tuple[RouteImage, bool]:
    route_image = existing or RouteImage(climbing_route=climbing_route)
    created = existing is None
    old_name = route_image.image.name if existing else ""
    storage = route_image.image.storage
    route_image.image = upload
    route_image.uploaded_by = actor
    route_image.annotations = empty_route_annotation()

    new_name = ""
    try:
        with transaction.atomic():
            route_image.full_clean()
            route_image.save()
            new_name = route_image.image.name
            if old_name and old_name != new_name:
                transaction.on_commit(_safe_delete_callback(storage, old_name))
    except Exception:
        new_name = route_image.image.name
        if new_name and new_name != old_name:
            _safe_delete(storage, new_name)
        raise
    return route_image, created


def delete_route_image(route_image: RouteImage) -> None:
    storage = route_image.image.storage
    stored_name = route_image.image.name
    with transaction.atomic():
        route_image.delete()
        transaction.on_commit(_safe_delete_callback(storage, stored_name))


def _safe_delete_callback(storage: Storage, name: str) -> Callable[[], None]:
    return lambda: _safe_delete(storage, name)


def _safe_delete(storage: Storage, name: str) -> None:
    try:
        storage.delete(name)
    except Exception:
        logger.exception("route_image_storage_cleanup_failed")
