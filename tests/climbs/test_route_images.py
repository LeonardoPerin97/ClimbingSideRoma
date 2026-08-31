import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.roles import Role, assign_role
from apps.climbs.images import MAX_ROUTE_IMAGE_BYTES, validate_route_image
from apps.climbs.models import ClimbingRoute, RouteImage
from apps.core.models import AuditLogEntry

ANNOTATION = {
    "version": 1,
    "markers": [
        {"type": "start-left", "x": 0.15, "y": 0.85},
        {"type": "move", "number": 1, "x": 0.5, "y": 0.5},
        {"type": "top", "x": 0.6, "y": 0.1},
    ],
}


@pytest.mark.django_db
def test_route_accepts_only_one_image(
    route_factory: Callable[..., ClimbingRoute],
    route_image_factory: Callable[..., RouteImage],
    route_image_upload_factory: Callable[..., SimpleUploadedFile],
) -> None:
    climbing_route = route_factory()
    route_image_factory(climbing_route=climbing_route)

    with pytest.raises(IntegrityError), transaction.atomic():
        RouteImage.objects.create(
            climbing_route=climbing_route,
            image=route_image_upload_factory(name="second.png"),
        )


@pytest.mark.django_db
def test_route_with_image_is_protected_from_deletion(
    route_image_factory: Callable[..., RouteImage],
) -> None:
    route_image = route_image_factory()

    with pytest.raises(ProtectedError):
        route_image.climbing_route.delete()


def test_invalid_or_mislabelled_images_are_rejected(
    route_image_upload_factory: Callable[..., SimpleUploadedFile],
) -> None:
    fake_image = SimpleUploadedFile("fake.png", b"not an image", content_type="image/png")
    wrong_content_type = route_image_upload_factory(content_type="text/plain")
    mismatched_extension = route_image_upload_factory(name="actually-jpeg.png", image_format="JPEG")
    mismatched_image_type = route_image_upload_factory(
        name="actually-jpeg.jpg",
        image_format="JPEG",
        content_type="image/png",
    )

    with pytest.raises(ValidationError):
        validate_route_image(fake_image)
    with pytest.raises(ValidationError):
        validate_route_image(wrong_content_type)
    with pytest.raises(ValidationError):
        validate_route_image(mismatched_extension)
    with pytest.raises(ValidationError):
        validate_route_image(mismatched_image_type)


def test_oversized_images_are_rejected() -> None:
    oversized = SimpleUploadedFile(
        "large.png",
        b"0" * (MAX_ROUTE_IMAGE_BYTES + 1),
        content_type="image/png",
    )

    with pytest.raises(ValidationError):
        validate_route_image(oversized)


@pytest.mark.django_db
def test_image_management_requires_authentication(
    client: Client,
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    climbing_route = route_factory()

    response = client.get(reverse("climbs:route_image_upload", args=[climbing_route.pk]))

    assert response.status_code == 302
    assert response.headers["Location"].startswith(reverse("accounts:login"))


@pytest.mark.django_db
def test_invalid_image_upload_is_reported_without_creating_a_record(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    route_setter = user_factory()
    assign_role(route_setter, Role.ROUTE_SETTER)
    climbing_route = route_factory()
    client.force_login(route_setter)
    fake_image = SimpleUploadedFile("fake.png", b"not an image", content_type="image/png")

    response = client.post(
        reverse("climbs:route_image_upload", args=[climbing_route.pk]),
        {"image": fake_image},
    )

    assert response.status_code == 200
    assert b"field-errors" in response.content
    assert not RouteImage.objects.filter(climbing_route=climbing_route).exists()


@pytest.mark.django_db
def test_standard_user_cannot_upload_or_annotate_images(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
    route_image_factory: Callable[..., RouteImage],
) -> None:
    user = user_factory()
    climbing_route = route_factory()
    route_image_factory(climbing_route=climbing_route)
    client.force_login(user)

    assert (
        client.get(reverse("climbs:route_image_upload", args=[climbing_route.pk])).status_code
        == 403
    )
    assert (
        client.get(reverse("climbs:route_annotation_edit", args=[climbing_route.pk])).status_code
        == 403
    )


@pytest.mark.django_db
def test_route_setter_can_upload_and_annotate_image(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
    route_image_upload_factory: Callable[..., SimpleUploadedFile],
    settings: Any,
    tmp_path: Path,
) -> None:
    settings.MEDIA_ROOT = tmp_path / "media"
    route_setter = user_factory()
    assign_role(route_setter, Role.ROUTE_SETTER)
    climbing_route = route_factory()
    client.force_login(route_setter)

    upload_response = client.post(
        reverse("climbs:route_image_upload", args=[climbing_route.pk]),
        {"image": route_image_upload_factory()},
    )
    route_image = RouteImage.objects.get(climbing_route=climbing_route)
    annotation_response = client.post(
        reverse("climbs:route_annotation_edit", args=[climbing_route.pk]),
        {"annotations": json.dumps(ANNOTATION)},
    )
    route_image.refresh_from_db()

    assert upload_response.status_code == 302
    assert upload_response.headers["Location"] == reverse(
        "climbs:route_annotation_edit", args=[climbing_route.pk]
    )
    assert annotation_response.status_code == 302
    assert route_image.annotations == ANNOTATION
    assert route_image.uploaded_by == route_setter
    assert set(
        AuditLogEntry.objects.filter(
            entity_type="route_image",
            entity_id=str(route_image.pk),
        ).values_list("action", flat=True)
    ) == {AuditLogEntry.Action.UPLOAD, AuditLogEntry.Action.ANNOTATE}


@pytest.mark.django_db
def test_invalid_annotation_is_not_saved(
    client: Client,
    user_factory: Callable[..., User],
    route_image_factory: Callable[..., RouteImage],
) -> None:
    route_setter = user_factory()
    assign_role(route_setter, Role.ROUTE_SETTER)
    route_image = route_image_factory(uploaded_by=route_setter)
    client.force_login(route_setter)

    response = client.post(
        reverse("climbs:route_annotation_edit", args=[route_image.climbing_route_id]),
        {"annotations": "not-json"},
    )
    route_image.refresh_from_db()

    assert response.status_code == 200
    assert route_image.annotations == {"version": 1, "markers": []}


@pytest.mark.django_db
def test_annotation_save_does_not_revalidate_stored_image(
    client: Client,
    user_factory: Callable[..., User],
    route_image_factory: Callable[..., RouteImage],
) -> None:
    route_setter = user_factory()
    assign_role(route_setter, Role.ROUTE_SETTER)
    route_image = route_image_factory(uploaded_by=route_setter)
    client.force_login(route_setter)

    with patch.object(
        route_image.image.storage,
        "size",
        side_effect=NotImplementedError("Remote storage does not expose file size."),
    ):
        response = client.post(
            reverse("climbs:route_annotation_edit", args=[route_image.climbing_route_id]),
            {"annotations": json.dumps(ANNOTATION)},
        )

    route_image.refresh_from_db()
    assert response.status_code == 302
    assert route_image.annotations == ANNOTATION


@pytest.mark.django_db(transaction=True)
def test_replacing_image_clears_markers_and_removes_previous_file(
    client: Client,
    user_factory: Callable[..., User],
    route_image_factory: Callable[..., RouteImage],
    route_image_upload_factory: Callable[..., SimpleUploadedFile],
) -> None:
    route_setter = user_factory()
    assign_role(route_setter, Role.ROUTE_SETTER)
    route_image = route_image_factory(annotations=ANNOTATION, uploaded_by=route_setter)
    old_path = Path(route_image.image.path)
    client.force_login(route_setter)

    response = client.post(
        reverse("climbs:route_image_upload", args=[route_image.climbing_route_id]),
        {"image": route_image_upload_factory(name="replacement.png")},
    )
    route_image.refresh_from_db()

    assert response.status_code == 302
    assert route_image.annotations == {"version": 1, "markers": []}
    assert not old_path.exists()
    assert Path(route_image.image.path).exists()


@pytest.mark.django_db
def test_route_setter_cannot_delete_image(
    client: Client,
    user_factory: Callable[..., User],
    route_image_factory: Callable[..., RouteImage],
) -> None:
    route_setter = user_factory()
    assign_role(route_setter, Role.ROUTE_SETTER)
    route_image = route_image_factory(uploaded_by=route_setter)
    client.force_login(route_setter)

    response = client.post(
        reverse("climbs:route_image_delete", args=[route_image.climbing_route_id])
    )

    assert response.status_code == 403
    assert RouteImage.objects.filter(pk=route_image.pk).exists()


@pytest.mark.django_db(transaction=True)
def test_admin_can_delete_image_and_stored_file(
    client: Client,
    user_factory: Callable[..., User],
    route_image_factory: Callable[..., RouteImage],
) -> None:
    admin_user = user_factory()
    assign_role(admin_user, Role.ADMIN)
    route_image = route_image_factory(uploaded_by=admin_user)
    image_path = Path(route_image.image.path)
    client.force_login(admin_user)

    response = client.post(
        reverse("climbs:route_image_delete", args=[route_image.climbing_route_id])
    )

    assert response.status_code == 302
    assert not RouteImage.objects.filter(pk=route_image.pk).exists()
    assert not image_path.exists()


@pytest.mark.django_db
def test_public_route_detail_displays_image_and_annotation_data(
    client: Client,
    route_image_factory: Callable[..., RouteImage],
) -> None:
    route_image = route_image_factory(annotations=ANNOTATION)

    response = client.get(reverse("climbs:route_detail", args=[route_image.climbing_route_id]))

    assert response.status_code == 200
    assert route_image.image.url.encode() in response.content
    assert b"route-annotation-data" in response.content
    assert b"start-left" in response.content


@pytest.mark.django_db
def test_image_mutations_are_csrf_protected(
    user_factory: Callable[..., User],
    route_image_factory: Callable[..., RouteImage],
    route_image_upload_factory: Callable[..., SimpleUploadedFile],
) -> None:
    admin_user = user_factory()
    assign_role(admin_user, Role.ADMIN)
    route_image = route_image_factory(uploaded_by=admin_user)
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(admin_user)

    assert (
        csrf_client.post(
            reverse("climbs:route_image_upload", args=[route_image.climbing_route_id]),
            {"image": route_image_upload_factory()},
        ).status_code
        == 403
    )
    assert (
        csrf_client.post(
            reverse("climbs:route_annotation_edit", args=[route_image.climbing_route_id]),
            {"annotations": json.dumps(ANNOTATION)},
        ).status_code
        == 403
    )
    assert (
        csrf_client.post(
            reverse("climbs:route_image_delete", args=[route_image.climbing_route_id])
        ).status_code
        == 403
    )
