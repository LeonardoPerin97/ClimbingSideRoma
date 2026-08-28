import re
from collections.abc import Callable

import pytest
from django.core import mail
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User


@pytest.mark.django_db
def test_verified_user_can_login_and_logout(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(username="leo", email="leo@example.com")

    login_response = client.post(
        reverse("accounts:login"),
        {"username": user.username, "password": "Strong-Test-Password-42!"},
    )
    assert login_response.status_code == 302
    assert login_response.headers["Location"] == reverse("accounts:profile")

    profile_response = client.get(reverse("accounts:profile"))
    assert profile_response.status_code == 200

    logout_response = client.post(reverse("accounts:logout"))
    assert logout_response.status_code == 302
    assert logout_response.headers["Location"] == reverse("core:home")
    assert client.get(reverse("accounts:profile")).status_code == 302


@pytest.mark.django_db
def test_username_login_is_case_insensitive(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    user_factory(username="Leonardo")

    response = client.post(
        reverse("accounts:login"),
        {"username": "leonardo", "password": "Strong-Test-Password-42!"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == reverse("accounts:profile")


@pytest.mark.django_db
def test_unverified_user_cannot_login(client: Client) -> None:
    user = User.objects.create_user(
        username="inactive",
        email="inactive@example.com",
        password="Strong-Test-Password-42!",
        is_active=False,
    )

    response = client.post(
        reverse("accounts:login"),
        {"username": user.username, "password": "Strong-Test-Password-42!"},
    )

    assert response.status_code == 200
    assert response.context["form"].errors
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_logout_rejects_get_requests(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory()
    client.force_login(user)

    response = client.get(reverse("accounts:logout"))

    assert response.status_code == 405


@pytest.mark.django_db
def test_password_change_updates_hash_and_keeps_session(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory()
    client.force_login(user)

    response = client.post(
        reverse("accounts:password_change"),
        {
            "old_password": "Strong-Test-Password-42!",
            "new_password1": "A-New-Secure-Password-43!",
            "new_password2": "A-New-Secure-Password-43!",
        },
    )

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.check_password("A-New-Secure-Password-43!")
    assert client.get(reverse("accounts:profile")).status_code == 200


@pytest.mark.django_db
def test_password_reset_flow_changes_password(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(email="reset@example.com")

    response = client.post(
        reverse("accounts:password_reset"),
        {"email": "reset@example.com"},
    )
    assert response.status_code == 302
    assert len(mail.outbox) == 1
    assert "Strong-Test-Password" not in mail.outbox[0].body

    match = re.search(
        r"https?://[^\s]+/password-reset/[^\s]+",
        str(mail.outbox[0].body),
    )
    assert match is not None
    confirm_response = client.get(match.group(0))
    assert confirm_response.status_code == 302

    set_password_response = client.post(
        confirm_response.headers["Location"],
        {
            "new_password1": "Reset-Secure-Password-44!",
            "new_password2": "Reset-Secure-Password-44!",
        },
    )
    assert set_password_response.status_code == 302
    user.refresh_from_db()
    assert user.check_password("Reset-Secure-Password-44!")


@pytest.mark.django_db
def test_password_reset_does_not_reveal_unknown_email(client: Client) -> None:
    response = client.post(
        reverse("accounts:password_reset"),
        {"email": "unknown@example.com"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == reverse("accounts:password_reset_done")
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_repeated_failed_logins_are_rate_limited(client: Client) -> None:
    statuses = []
    for _attempt in range(5):
        response = client.post(
            reverse("accounts:login"),
            {"username": "attacked-user", "password": "wrong-password"},
            REMOTE_ADDR="198.51.100.23",
        )
        statuses.append(response.status_code)

    assert statuses[:4] == [200, 200, 200, 200]
    assert statuses[4] == 429
    assert 895 <= int(response.headers["Retry-After"]) <= 900
