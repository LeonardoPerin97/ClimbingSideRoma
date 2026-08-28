from collections.abc import Callable
from typing import Any, cast

import pytest
from django.utils import timezone

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
