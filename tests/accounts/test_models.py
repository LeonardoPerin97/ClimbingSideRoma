import pytest
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
