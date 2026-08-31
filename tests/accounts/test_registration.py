import re
from collections.abc import Callable

import pytest
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.roles import Role, role_for

REGISTRATION_DATA = {
    "username": "Leonardo",
    "email": "Leonardo@example.com",
    "preferred_language": "it",
    "password1": "Strong-Test-Password-42!",
    "password2": "Strong-Test-Password-42!",
}


@pytest.mark.django_db
def test_registration_creates_inactive_user_and_sends_verification_email(
    client: Client,
) -> None:
    response = client.post(reverse("accounts:register"), REGISTRATION_DATA)

    assert response.status_code == 302
    assert response.headers["Location"] == reverse("accounts:verification_sent")

    user = User.objects.get(username="Leonardo")
    assert not user.is_active
    assert not user.email_is_verified
    assert user.email == "leonardo@example.com"
    assert user.check_password(REGISTRATION_DATA["password1"])
    assert role_for(user) is Role.USER

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["leonardo@example.com"]
    assert "Strong-Test-Password" not in mail.outbox[0].body
    assert reverse("accounts:login") not in mail.outbox[0].body


@pytest.mark.django_db
@override_settings(BYPASS_EMAIL_VERIFICATION=True)
def test_registration_bypass_activates_user_without_sending_email(
    client: Client,
) -> None:
    response = client.post(
        reverse("accounts:register"),
        REGISTRATION_DATA,
        follow=True,
        HTTP_ACCEPT_LANGUAGE="en",
    )

    user = User.objects.get(username="Leonardo")
    assert response.redirect_chain == [(reverse("accounts:login"), 302)]
    assert user.is_active
    assert not user.email_is_verified
    assert len(mail.outbox) == 0
    content = response.content.decode()
    assert "Account created. You can log in now" in content
    assert "password recovery are temporarily unavailable" in content


@pytest.mark.django_db
def test_email_verification_activates_account(client: Client) -> None:
    client.post(reverse("accounts:register"), REGISTRATION_DATA)
    match = re.search(r"https?://[^\s]+/verify-email/[^\s]+", str(mail.outbox[0].body))
    assert match is not None

    response = client.get(match.group(0))

    assert response.status_code == 200
    user = User.objects.get(username="Leonardo")
    assert user.is_active
    assert user.email_is_verified


@pytest.mark.django_db
def test_invalid_verification_token_does_not_activate_user(client: Client) -> None:
    client.post(reverse("accounts:register"), REGISTRATION_DATA)
    user = User.objects.get(username="Leonardo")

    response = client.get(
        reverse(
            "accounts:verify_email",
            kwargs={"uidb64": "invalid", "token": "invalid"},
        )
    )

    assert response.status_code == 400
    user.refresh_from_db()
    assert not user.is_active
    assert not user.email_is_verified


@pytest.mark.django_db
def test_duplicate_email_is_rejected_case_insensitively(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    user_factory(email="leonardo@example.com")

    response = client.post(reverse("accounts:register"), REGISTRATION_DATA)

    assert response.status_code == 200
    assert "email" in response.context["form"].errors
    assert User.objects.count() == 1


@pytest.mark.django_db
def test_resend_response_does_not_reveal_account_existence(client: Client) -> None:
    client.post(reverse("set_language"), {"language": "en", "next": "/"})
    response_unknown = client.post(
        reverse("accounts:resend_verification"),
        {"email": "unknown@example.com"},
        follow=True,
    )
    client.post(reverse("accounts:register"), REGISTRATION_DATA)
    mail.outbox.clear()
    response_existing = client.post(
        reverse("accounts:resend_verification"),
        {"email": "leonardo@example.com"},
        follow=True,
    )

    message = "If an unverified account exists, a new verification email has been sent."
    assert message in response_unknown.content.decode()
    assert message in response_existing.content.decode()
    assert len(mail.outbox) == 1


@pytest.mark.django_db
@override_settings(BYPASS_EMAIL_VERIFICATION=True)
def test_verification_resend_redirects_to_login_while_bypassed(client: Client) -> None:
    response = client.get(
        reverse("accounts:resend_verification"),
        follow=True,
        HTTP_ACCEPT_LANGUAGE="en",
    )

    assert response.redirect_chain == [(reverse("accounts:login"), 302)]
    assert "Email verification is temporarily disabled" in response.content.decode()


@pytest.mark.django_db
def test_registration_is_csrf_protected() -> None:
    csrf_client = Client(enforce_csrf_checks=True)

    response = csrf_client.post(reverse("accounts:register"), REGISTRATION_DATA)

    assert response.status_code == 403
