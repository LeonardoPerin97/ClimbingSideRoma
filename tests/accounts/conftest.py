from collections.abc import Callable
from io import BytesIO
from typing import Any, cast

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from apps.accounts.models import User
from apps.accounts.roles import Role, assign_role


@pytest.fixture
def user_factory(db: None) -> Callable[..., User]:
    del db

    def create_user(**overrides: object) -> User:
        sequence = User.objects.count() + 1
        values: dict[str, object] = {
            "username": f"climber-{sequence}",
            "email": f"climber-{sequence}@example.com",
            "password": "Strong-Test-Password-42!",
            "email_verified_at": timezone.now(),
            "is_active": True,
        }
        values.update(overrides)
        user = User.objects.create_user(**cast(Any, values))
        assign_role(user, Role.USER)
        return user

    return create_user


@pytest.fixture
def profile_image_upload_factory() -> Callable[..., SimpleUploadedFile]:
    def create_upload(**overrides: object) -> SimpleUploadedFile:
        name = cast(str, overrides.pop("name", "profile.png"))
        image_format = cast(str, overrides.pop("image_format", "PNG"))
        content_type = cast(str, overrides.pop("content_type", "image/png"))
        size = cast(tuple[int, int], overrides.pop("size", (96, 96)))
        color = cast(tuple[int, int, int], overrides.pop("color", (244, 178, 35)))
        buffer = BytesIO()
        Image.new("RGB", size, color=color).save(buffer, format=image_format)
        return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)

    return create_upload
