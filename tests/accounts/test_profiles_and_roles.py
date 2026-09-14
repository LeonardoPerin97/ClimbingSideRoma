from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
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
def test_route_setter_receives_catalogue_and_image_permissions(
    user_factory: Callable[..., User],
) -> None:
    user = user_factory()
    assign_role(user, Role.ROUTE_SETTER)

    expected_permissions = {
        "add_wall",
        "change_wall",
        "delete_wall",
        "view_wall",
        "add_climbingroute",
        "change_climbingroute",
        "delete_climbingroute",
        "view_climbingroute",
        "add_routeimage",
        "change_routeimage",
        "delete_routeimage",
        "view_routeimage",
    }

    assert all(user.has_perm(f"climbs.{codename}") for codename in expected_permissions)
    assert not user.has_perm("accounts.change_user")


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
def test_personal_area_redirects_to_own_climber_profile(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory()
    client.force_login(user)

    response = client.get(reverse("accounts:profile"))

    assert response.status_code == 302
    assert response.headers["Location"] == reverse(
        "accounts:public_profile",
        args=[user.username],
    )


@pytest.mark.django_db
def test_own_climber_profile_places_private_account_information_at_the_end(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(email="owner-private@example.com")
    client.force_login(user)

    response = client.get(reverse("accounts:public_profile", args=[user.username]))
    content = response.content.decode()

    assert response.status_code == 200
    assert content.index('class="summary-grid"') < content.index('id="account-information-heading"')
    assert "owner-private@example.com" in content
    assert "Iscritto dal" in content
    assert user.date_joined.strftime("%d/%m/%Y") in content
    assert reverse("accounts:profile_edit") in content
    assert reverse("accounts:password_change") in content
    assert 'id="profile-information-heading"' not in content
    assert 'id="climbing-statistics-heading"' not in content
    assert "Statistiche di arrampicata" not in content
    assert reverse("climbs:ascent_create") not in content


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
    assert 'id="account-information-heading"' not in content


@pytest.mark.django_db
def test_own_profile_without_image_shows_clickable_add_image_control(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(username="profile-without-image")
    client.force_login(user)

    response = client.get(reverse("accounts:public_profile", args=[user.username]))
    content = response.content.decode()

    assert response.status_code == 200
    assert 'class="profile-avatar profile-avatar-add"' in content
    assert f'href="{reverse("accounts:profile_image_upload")}"' in content
    assert ">+</span>" in content


@pytest.mark.django_db
def test_other_profile_without_image_keeps_non_interactive_initial(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    profile_user = user_factory(username="different-climber")

    response = client.get(
        reverse("accounts:public_profile", args=[profile_user.username]),
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert 'class="profile-avatar profile-avatar-placeholder"' in content
    assert 'class="profile-avatar profile-avatar-add"' not in content


@pytest.mark.django_db
def test_authenticated_user_cannot_see_another_climbers_account_information(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    viewer = user_factory(username="profile-viewer", email="viewer@example.com")
    other = user_factory(username="other-climber", email="other-private@example.com")
    client.force_login(viewer)

    response = client.get(reverse("accounts:public_profile", args=[other.username]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "other-private@example.com" not in content
    assert 'id="account-information-heading"' not in content
    assert reverse("accounts:profile_edit") not in content
    assert reverse("accounts:password_change") not in content
    assert 'id="profile-information-heading"' in content


@pytest.mark.django_db
def test_public_profile_places_summary_before_histogram_and_profile_information(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(username="ordered-public-profile")

    response = client.get(
        reverse("accounts:public_profile", args=[user.username]),
        HTTP_ACCEPT_LANGUAGE="en",
    )
    content = response.content.decode()

    assert content.index('class="summary-grid"') < content.index(
        'class="profile-card profile-histogram-card profile-primary-histogram"'
    )
    assert content.index(
        'class="profile-card profile-histogram-card profile-primary-histogram"'
    ) < content.index('id="profile-information-heading"')
    assert "Recorded ascents" in content
    assert "Highest grade" in content
    assert "Grade distribution" not in content
    assert "Number of ascents" not in content
    assert "Completed routes" not in content

    italian_response = client.get(
        reverse("accounts:public_profile", args=[user.username]),
        HTTP_ACCEPT_LANGUAGE="it",
    )
    italian_content = italian_response.content.decode()
    assert "Ripetizioni inserite" in italian_content
    assert "Grado più alto" in italian_content
    assert "Distribuzione dei gradi" not in italian_content


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
def test_profile_language_can_change_without_reopening_existing_profile_image(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(preferred_language="it")
    user.profile_image = f"profiles/{user.pk}/already-validated.png"
    user.save(update_fields=("profile_image",))
    original_image_name = user.profile_image.name
    client.force_login(user)

    response = client.post(
        reverse("accounts:profile_edit"),
        {
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "preferred_language": "en",
        },
    )
    user.refresh_from_db()

    assert response.status_code == 302
    assert user.preferred_language == "en"
    assert user.profile_image.name == original_image_name


@pytest.mark.django_db
def test_user_can_upload_profile_image_and_it_is_shown_on_public_profile(
    client: Client,
    user_factory: Callable[..., User],
    profile_image_upload_factory: Callable[..., SimpleUploadedFile],
    settings: Any,
    tmp_path: Path,
) -> None:
    settings.MEDIA_ROOT = tmp_path / "media"
    user = user_factory(username="pictured-climber")
    client.force_login(user)

    response = client.post(
        reverse("accounts:profile_edit"),
        {
            "username": user.username,
            "first_name": "",
            "last_name": "",
            "preferred_language": user.preferred_language,
            "profile_image": profile_image_upload_factory(),
        },
    )
    user.refresh_from_db()

    assert response.status_code == 302
    assert user.profile_image.name.startswith(f"profiles/{user.pk}/")
    assert Path(user.profile_image.path).exists()
    audit_entry = AuditLogEntry.objects.get(
        entity_type="profile_image",
        entity_id=str(user.pk),
    )
    assert audit_entry.actor == user
    assert audit_entry.action == AuditLogEntry.Action.UPLOAD

    profile_response = client.get(
        reverse("accounts:public_profile", args=[user.username]),
    )
    profile_content = profile_response.content.decode()
    assert 'class="profile-avatar"' in profile_content
    assert 'class="profile-avatar-link"' in profile_content
    assert reverse("accounts:profile_image_upload") in profile_content
    assert user.profile_image.url in profile_content
    delete_url = reverse("accounts:profile_image_delete", args=[user.username])
    assert delete_url not in profile_content

    image_form_response = client.get(reverse("accounts:profile_image_upload"))
    assert delete_url in image_form_response.content.decode()


@pytest.mark.django_db
def test_dedicated_profile_image_form_only_changes_the_image(
    client: Client,
    user_factory: Callable[..., User],
    profile_image_upload_factory: Callable[..., SimpleUploadedFile],
    settings: Any,
    tmp_path: Path,
) -> None:
    settings.MEDIA_ROOT = tmp_path / "media"
    user = user_factory(
        username="dedicated-image-form",
        first_name="Leonardo",
        preferred_language="it",
    )
    client.force_login(user)
    upload_url = reverse("accounts:profile_image_upload")

    form_response = client.get(upload_url)
    upload_response = client.post(
        upload_url,
        {"profile_image": profile_image_upload_factory()},
    )
    user.refresh_from_db()

    assert form_response.status_code == 200
    assert list(form_response.context["form"].fields) == ["profile_image"]
    assert 'enctype="multipart/form-data"' in form_response.content.decode()
    assert upload_response.status_code == 302
    assert upload_response.headers["Location"] == reverse(
        "accounts:public_profile",
        args=[user.username],
    )
    assert user.first_name == "Leonardo"
    assert user.preferred_language == "it"
    assert user.profile_image.name.startswith(f"profiles/{user.pk}/")


@pytest.mark.django_db
def test_dedicated_profile_image_form_requires_authentication(client: Client) -> None:
    response = client.get(reverse("accounts:profile_image_upload"))

    assert response.status_code == 302
    assert response.headers["Location"].startswith(reverse("accounts:login"))


@pytest.mark.django_db(transaction=True)
def test_replacing_profile_image_removes_previous_stored_file(
    client: Client,
    user_factory: Callable[..., User],
    profile_image_upload_factory: Callable[..., SimpleUploadedFile],
    settings: Any,
    tmp_path: Path,
) -> None:
    settings.MEDIA_ROOT = tmp_path / "media"
    user = user_factory()
    user.profile_image = profile_image_upload_factory(name="old.png")
    user.full_clean()
    user.save(update_fields=("profile_image",))
    old_path = Path(user.profile_image.path)
    client.force_login(user)

    response = client.post(
        reverse("accounts:profile_edit"),
        {
            "username": user.username,
            "first_name": "",
            "last_name": "",
            "preferred_language": user.preferred_language,
            "profile_image": profile_image_upload_factory(
                name="new.png",
                color=(85, 185, 232),
            ),
        },
    )
    user.refresh_from_db()

    assert response.status_code == 302
    assert not old_path.exists()
    assert Path(user.profile_image.path).exists()
    assert AuditLogEntry.objects.filter(
        actor=user,
        action=AuditLogEntry.Action.REPLACE,
        entity_type="profile_image",
        entity_id=str(user.pk),
    ).exists()


@pytest.mark.django_db(transaction=True)
def test_user_can_delete_own_profile_image_after_confirmation(
    client: Client,
    user_factory: Callable[..., User],
    profile_image_upload_factory: Callable[..., SimpleUploadedFile],
    settings: Any,
    tmp_path: Path,
) -> None:
    settings.MEDIA_ROOT = tmp_path / "media"
    user = user_factory(username="self-delete-image")
    user.profile_image = profile_image_upload_factory()
    user.full_clean()
    user.save(update_fields=("profile_image",))
    image_path = Path(user.profile_image.path)
    delete_url = reverse("accounts:profile_image_delete", args=[user.username])
    client.force_login(user)

    confirmation_response = client.get(delete_url)
    delete_response = client.post(delete_url)
    user.refresh_from_db()

    assert confirmation_response.status_code == 200
    assert delete_response.status_code == 302
    assert not user.profile_image
    assert not image_path.exists()
    assert AuditLogEntry.objects.filter(
        actor=user,
        action=AuditLogEntry.Action.DELETE,
        entity_type="profile_image",
        entity_id=str(user.pk),
    ).exists()


@pytest.mark.django_db(transaction=True)
def test_admin_can_delete_another_users_profile_image(
    client: Client,
    user_factory: Callable[..., User],
    profile_image_upload_factory: Callable[..., SimpleUploadedFile],
    settings: Any,
    tmp_path: Path,
) -> None:
    settings.MEDIA_ROOT = tmp_path / "media"
    admin_user = user_factory(username="profile-image-admin", email="image-admin@example.com")
    assign_role(admin_user, Role.ADMIN)
    target_user = user_factory(username="profile-image-target", email="image-target@example.com")
    target_user.profile_image = profile_image_upload_factory()
    target_user.full_clean()
    target_user.save(update_fields=("profile_image",))
    image_path = Path(target_user.profile_image.path)
    delete_url = reverse("accounts:profile_image_delete", args=[target_user.username])
    manage_url = reverse("accounts:profile_image_manage", args=[target_user.username])
    client.force_login(admin_user)

    profile_response = client.get(
        reverse("accounts:public_profile", args=[target_user.username]),
    )
    manage_response = client.get(manage_url)
    delete_response = client.post(delete_url)
    target_user.refresh_from_db()

    profile_content = profile_response.content.decode()
    manage_content = manage_response.content.decode()
    assert manage_url in profile_content
    assert delete_url not in profile_content
    assert manage_response.status_code == 200
    assert delete_url in manage_content
    assert 'name="profile_image"' not in manage_content
    assert 'enctype="multipart/form-data"' not in manage_content
    assert delete_response.status_code == 302
    assert not target_user.profile_image
    assert not image_path.exists()
    assert AuditLogEntry.objects.filter(
        actor=admin_user,
        action=AuditLogEntry.Action.DELETE,
        entity_type="profile_image",
        entity_id=str(target_user.pk),
    ).exists()


@pytest.mark.django_db
def test_route_setter_cannot_delete_another_users_profile_image(
    client: Client,
    user_factory: Callable[..., User],
    profile_image_upload_factory: Callable[..., SimpleUploadedFile],
    settings: Any,
    tmp_path: Path,
) -> None:
    settings.MEDIA_ROOT = tmp_path / "media"
    route_setter = user_factory(username="image-route-setter", email="setter-image@example.com")
    assign_role(route_setter, Role.ROUTE_SETTER)
    target_user = user_factory(username="protected-image-user", email="protected@example.com")
    target_user.profile_image = profile_image_upload_factory()
    target_user.full_clean()
    target_user.save(update_fields=("profile_image",))
    stored_name = target_user.profile_image.name
    client.force_login(route_setter)

    profile_response = client.get(
        reverse("accounts:public_profile", args=[target_user.username]),
    )
    manage_response = client.get(
        reverse("accounts:profile_image_manage", args=[target_user.username]),
    )
    delete_response = client.post(
        reverse("accounts:profile_image_delete", args=[target_user.username]),
    )
    target_user.refresh_from_db()

    assert reverse("accounts:profile_image_manage", args=[target_user.username]) not in (
        profile_response.content.decode()
    )
    assert manage_response.status_code == 403
    assert delete_response.status_code == 403
    assert target_user.profile_image.name == stored_name


@pytest.mark.django_db
def test_owner_profile_image_management_alias_redirects_to_upload_form(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory(username="own-image-management")
    client.force_login(user)

    response = client.get(
        reverse("accounts:profile_image_manage", args=[user.username]),
    )

    assert response.status_code == 302
    assert response.headers["Location"] == reverse("accounts:profile_image_upload")


@pytest.mark.django_db
def test_profile_image_deletion_is_csrf_protected(
    user_factory: Callable[..., User],
) -> None:
    user = user_factory()
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)

    response = csrf_client.post(
        reverse("accounts:profile_image_delete", args=[user.username]),
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_invalid_profile_image_is_rejected(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    user = user_factory()
    client.force_login(user)

    response = client.post(
        reverse("accounts:profile_edit"),
        {
            "username": user.username,
            "first_name": "",
            "last_name": "",
            "preferred_language": user.preferred_language,
            "profile_image": SimpleUploadedFile(
                "fake.png",
                b"not an image",
                content_type="image/png",
            ),
        },
    )
    user.refresh_from_db()

    assert response.status_code == 200
    assert "profile_image" in response.context["form"].errors
    assert not user.profile_image


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
