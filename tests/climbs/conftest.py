from collections.abc import Callable, Iterable
from io import BytesIO
from typing import Any, cast

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from apps.accounts.models import User
from apps.accounts.roles import Role, assign_role
from apps.climbs.grades import encode_perceived_grade
from apps.climbs.models import Ascent, ClimbingRoute, RouteImage, Wall


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
def wall_factory(db: None) -> Callable[..., Wall]:
    del db

    def create_wall(**overrides: object) -> Wall:
        sequence = Wall.objects.count() + 1
        values: dict[str, object] = {"name": f"Wall {sequence}"}
        values.update(overrides)
        wall = Wall(**cast(Any, values))
        wall.full_clean()
        wall.save()
        return wall

    return create_wall


@pytest.fixture
def route_factory(
    wall_factory: Callable[..., Wall],
) -> Callable[..., ClimbingRoute]:
    def create_route(**overrides: object) -> ClimbingRoute:
        route_setters = cast(Iterable[User], overrides.pop("route_setters", ()))
        wall = cast(Wall | None, overrides.pop("wall", None)) or wall_factory()
        sequence = ClimbingRoute.objects.count() + 1
        values: dict[str, object] = {
            "name": f"Climbing route {sequence}",
            "wall": wall,
            "discipline": ClimbingRoute.Discipline.ROUTE,
            "official_grade": "6a",
            "is_project": False,
        }
        values.update(overrides)
        climbing_route = ClimbingRoute(**cast(Any, values))
        climbing_route.full_clean()
        climbing_route.save()
        climbing_route.route_setters.set(route_setters)
        return climbing_route

    return create_route


@pytest.fixture
def ascent_factory(
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
) -> Callable[..., Ascent]:
    def create_ascent(**overrides: object) -> Ascent:
        user = cast(User | None, overrides.pop("user", None)) or user_factory()
        climbing_route = (
            cast(
                ClimbingRoute | None,
                overrides.pop("climbing_route", None),
            )
            or route_factory()
        )
        values: dict[str, object] = {
            "user": user,
            "climbing_route": climbing_route,
            "rating": 4,
            "proposed_grade": encode_perceived_grade("6a", 0),
            "attempt_type": Ascent.AttemptType.UNKNOWN,
            "attempt_count": None,
        }
        values.update(overrides)
        ascent = Ascent(**cast(Any, values))
        ascent.full_clean()
        ascent.save()
        return ascent

    return create_ascent


@pytest.fixture
def route_image_upload_factory() -> Callable[..., SimpleUploadedFile]:
    def create_upload(**overrides: object) -> SimpleUploadedFile:
        name = cast(str, overrides.pop("name", "route.png"))
        image_format = cast(str, overrides.pop("image_format", "PNG"))
        content_type = cast(str, overrides.pop("content_type", "image/png"))
        size = cast(tuple[int, int], overrides.pop("size", (80, 120)))
        buffer = BytesIO()
        Image.new("RGB", size, color=(34, 92, 61)).save(buffer, format=image_format)
        return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)

    return create_upload


@pytest.fixture
def route_image_factory(
    route_factory: Callable[..., ClimbingRoute],
    route_image_upload_factory: Callable[..., SimpleUploadedFile],
    settings: Any,
    tmp_path: Any,
) -> Callable[..., RouteImage]:
    settings.MEDIA_ROOT = tmp_path / "media"

    def create_route_image(**overrides: object) -> RouteImage:
        climbing_route = (
            cast(ClimbingRoute | None, overrides.pop("climbing_route", None)) or route_factory()
        )
        image = (
            cast(
                SimpleUploadedFile | None,
                overrides.pop("image", None),
            )
            or route_image_upload_factory()
        )
        values: dict[str, object] = {
            "climbing_route": climbing_route,
            "image": image,
        }
        values.update(overrides)
        route_image = RouteImage(**cast(Any, values))
        route_image.full_clean()
        route_image.save()
        return route_image

    return create_route_image
