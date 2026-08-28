from collections.abc import Callable

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.roles import Role, assign_role, role_for
from apps.core.models import AuditLogEntry


@pytest.mark.django_db
def test_role_groups_exist() -> None:
    assert set(
        Group.objects.filter(name__in={role.value for role in Role}).values_list("name", flat=True)
    ) == {
        "User",
        "RouteSetter",
        "Admin",
    }


@pytest.mark.django_db
def test_assigning_route_setter_does_not_grant_admin_access(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory()
    assign_role(user, Role.ROUTE_SETTER)
    user.refresh_from_db()

    assert role_for(user) is Role.ROUTE_SETTER
    assert not user.is_staff

    client.force_login(user)
    response = client.get(reverse("admin:index"))
    assert response.status_code == 302
    assert response.headers["Location"].startswith(reverse("admin:login"))


@pytest.mark.django_db
def test_assigning_admin_grants_staff_and_admin_permissions(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory()
    assign_role(user, Role.ADMIN)
    user.refresh_from_db()

    assert role_for(user) is Role.ADMIN
    assert user.is_staff
    assert user.has_perm("accounts.view_user")

    client.force_login(user)
    assert client.get(reverse("admin:index")).status_code == 200


@pytest.mark.django_db
def test_admin_can_open_user_role_management_form(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    admin_user = user_factory(username="admin-user", email="admin-user@example.com")
    target_user = user_factory(username="target-user", email="target-user@example.com")
    assign_role(admin_user, Role.ADMIN)
    client.force_login(admin_user)

    response = client.get(reverse("admin:accounts_user_change", args=[target_user.pk]))

    assert response.status_code == 200
    assert 'name="role"' in response.content.decode()


@pytest.mark.django_db
def test_admin_role_change_is_persisted_in_the_audit_log(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    admin_user = user_factory(username="audit-admin", email="audit-admin@example.com")
    target_user = user_factory(username="audited-user", email="audited-user@example.com")
    assign_role(admin_user, Role.ADMIN)
    client.force_login(admin_user)

    response = client.post(
        reverse("admin:accounts_user_change", args=[target_user.pk]),
        {
            "username": target_user.username,
            "email": target_user.email,
            "first_name": "",
            "last_name": "",
            "preferred_language": target_user.preferred_language,
            "is_active": "on",
            "role": Role.ROUTE_SETTER,
        },
    )

    target_user.refresh_from_db()
    entry = AuditLogEntry.objects.get(entity_type="user", entity_id=str(target_user.pk))
    assert response.status_code == 302
    assert role_for(target_user) is Role.ROUTE_SETTER
    assert entry.actor == admin_user
    assert entry.action == AuditLogEntry.Action.ROLE_CHANGE
    assert entry.metadata == {"old_role": "User", "new_role": "RouteSetter"}


@pytest.mark.django_db
def test_profile_requires_authentication(client: Client) -> None:
    response = client.get(reverse("accounts:profile"))

    assert response.status_code == 302
    assert response.headers["Location"].startswith(reverse("accounts:login"))


@pytest.mark.django_db
def test_account_information_is_at_the_end_of_personal_profile(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory()
    client.force_login(user)

    response = client.get(reverse("accounts:profile"))
    content = response.content.decode()

    assert response.status_code == 200
    assert content.index('id="climbing-statistics-heading"') < content.index(
        'id="account-information-heading"'
    )


@pytest.mark.django_db
def test_public_profile_is_visible_but_does_not_expose_email(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(username="visible-climber", email="private@example.com")

    response = client.get(reverse("accounts:public_profile", args=[user.username]))

    assert response.status_code == 200
    content = response.content.decode()
    assert "visible-climber" in content
    assert "private@example.com" not in content


@pytest.mark.django_db
def test_inactive_profile_is_not_public(client: Client) -> None:
    user = User.objects.create_user(
        username="inactive-profile",
        email="inactive-profile@example.com",
        password="Strong-Test-Password-42!",
        is_active=False,
    )

    response = client.get(reverse("accounts:public_profile", args=[user.username]))

    assert response.status_code == 404


@pytest.mark.django_db
def test_profile_update_persists_username_and_language(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(preferred_language="it")
    client.force_login(user)

    response = client.post(
        reverse("accounts:profile_edit"),
        {
            "username": "updated-climber",
            "first_name": "Leo",
            "last_name": "Perin",
            "preferred_language": "en",
        },
    )

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.username == "updated-climber"
    assert user.preferred_language == "en"

    home_response = client.get(reverse("core:home"))
    assert "Climbing Side Roma" in home_response.content.decode()


@pytest.mark.django_db
def test_language_selector_updates_authenticated_user(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(preferred_language="it")
    client.force_login(user)

    response = client.post(
        reverse("set_language"),
        {"language": "en", "next": reverse("core:home")},
    )

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.preferred_language == "en"
    assert response.cookies["django_language"].value == "en"
