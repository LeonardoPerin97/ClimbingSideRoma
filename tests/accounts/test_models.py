from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User


@pytest.mark.django_db
def test_user_manager_normalises_identity_and_hashes_password() -> None:
    user = User.objects.create_user(
        username="  Leonardo  ",
        email="Leonardo@Example.COM",
        password="a-secure-test-password",
    )

    assert user.username == "Leonardo"
    assert user.email == "leonardo@example.com"
    assert user.password != "a-secure-test-password"
    assert user.check_password("a-secure-test-password")
    assert not user.profile_image


@pytest.mark.django_db
def test_user_email_is_required() -> None:
    with pytest.raises(ValueError, match="email must be set"):
        User.objects.create_user(username="leo", email="", password="test-password")


@pytest.mark.django_db
def test_username_is_unique_case_insensitively() -> None:
    User.objects.create_user(
        username="Leonardo",
        email="first@example.com",
        password="test-password",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user(
            username="leonardo",
            email="second@example.com",
            password="test-password",
        )


@pytest.mark.django_db
def test_email_is_unique_case_insensitively() -> None:
    User.objects.create_user(
        username="first-user",
        email="Leonardo@example.com",
        password="test-password",
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        User.objects.create_user(
            username="second-user",
            email="leonardo@EXAMPLE.COM",
            password="test-password",
        )


@pytest.mark.django_db
def test_superuser_is_created_with_verified_email() -> None:
    user = User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="test-password",
    )

    assert user.is_superuser
    assert user.is_staff
    assert user.is_active
    assert user.email_verified_at is not None
    assert user.email_verified_at <= timezone.now()


@pytest.mark.django_db(transaction=True)
def test_deleting_user_removes_stored_profile_image(
    user_factory: Callable[..., User],
    profile_image_upload_factory: Callable[..., SimpleUploadedFile],
    settings: Any,
    tmp_path: Path,
) -> None:
    settings.MEDIA_ROOT = tmp_path / "media"
    user = user_factory()
    user.profile_image = profile_image_upload_factory()
    user.full_clean()
    user.save(update_fields=("profile_image",))
    image_path = Path(user.profile_image.path)

    user.delete()

    assert not image_path.exists()
