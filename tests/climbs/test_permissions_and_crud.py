from collections.abc import Callable

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.roles import Role, assign_role
from apps.climbs.models import Ascent, ClimbingRoute, Wall


def route_form_data(wall: Wall, **overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "name": "Created Route",
        "wall": wall.pk,
        "discipline": ClimbingRoute.Discipline.ROUTE,
        "official_grade": "6a",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_catalogue_mutations_require_authentication(client: Client) -> None:
    response = client.get(reverse("climbs:route_create"))

    assert response.status_code == 302
    assert response.headers["Location"].startswith(reverse("accounts:login"))


@pytest.mark.django_db
def test_standard_user_cannot_create_walls_or_routes(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    client.force_login(user_factory())

    assert client.get(reverse("climbs:wall_create")).status_code == 403
    assert client.get(reverse("climbs:route_create")).status_code == 403


@pytest.mark.django_db
def test_route_setter_can_create_edit_and_archive_route_without_setter(
    client: Client,
    user_factory: Callable[..., User],
    wall_factory: Callable[..., Wall],
) -> None:
    route_setter = user_factory(username="route-setter", email="setter@example.com")
    assign_role(route_setter, Role.ROUTE_SETTER)
    client.force_login(route_setter)
    wall = wall_factory(name="Creation Wall")

    form_response = client.get(reverse("climbs:route_create"))
    create_response = client.post(
        reverse("climbs:route_create"),
        route_form_data(wall),
    )
    climbing_route = ClimbingRoute.objects.get(name="Created Route")

    assert form_response.status_code == 200
    assert ">Tipo</label>" in form_response.content.decode()
    assert create_response.status_code == 302
    assert not climbing_route.route_setters.exists()

    edit_response = client.post(
        reverse("climbs:route_edit", args=[climbing_route.pk]),
        route_form_data(wall, name="Edited Route", official_grade="6b+"),
    )
    climbing_route.refresh_from_db()

    assert edit_response.status_code == 302
    assert climbing_route.name == "Edited Route"
    assert climbing_route.official_grade == "6b+"

    archive_response = client.post(reverse("climbs:route_archive", args=[climbing_route.pk]))
    climbing_route.refresh_from_db()

    assert archive_response.status_code == 302
    assert climbing_route.is_archived


@pytest.mark.django_db
def test_route_setter_cannot_manage_walls_or_permanently_delete_routes(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    route_setter = user_factory()
    assign_role(route_setter, Role.ROUTE_SETTER)
    client.force_login(route_setter)
    climbing_route = route_factory(is_archived=True)

    assert client.get(reverse("climbs:wall_create")).status_code == 403
    assert client.get(reverse("climbs:route_delete", args=[climbing_route.pk])).status_code == 403


@pytest.mark.django_db
def test_admin_can_create_edit_and_archive_wall(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    admin_user = user_factory(username="catalog-admin", email="admin@example.com")
    assign_role(admin_user, Role.ADMIN)
    client.force_login(admin_user)

    create_response = client.post(reverse("climbs:wall_create"), {"name": "New Wall"})
    wall = Wall.objects.get(name="New Wall")
    edit_response = client.post(
        reverse("climbs:wall_edit", args=[wall.pk]),
        {"name": "Renamed Wall"},
    )
    archive_response = client.post(reverse("climbs:wall_archive", args=[wall.pk]))
    wall.refresh_from_db()

    assert create_response.status_code == 302
    assert edit_response.status_code == 302
    assert archive_response.status_code == 302
    assert wall.name == "Renamed Wall"
    assert wall.is_archived


@pytest.mark.django_db
def test_wall_cannot_be_archived_while_it_has_active_routes(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    admin_user = user_factory()
    assign_role(admin_user, Role.ADMIN)
    client.force_login(admin_user)
    climbing_route = route_factory()

    response = client.post(reverse("climbs:wall_archive", args=[climbing_route.wall_id]))
    climbing_route.wall.refresh_from_db()

    assert response.status_code == 302
    assert not climbing_route.wall.is_archived


@pytest.mark.django_db
def test_active_route_cannot_be_permanently_deleted(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    admin_user = user_factory()
    assign_role(admin_user, Role.ADMIN)
    client.force_login(admin_user)
    climbing_route = route_factory()

    response = client.post(
        reverse("climbs:route_delete", args=[climbing_route.pk]),
        {"name": climbing_route.name},
    )

    assert response.status_code == 302
    assert ClimbingRoute.objects.filter(pk=climbing_route.pk).exists()


@pytest.mark.django_db
def test_archived_route_requires_exact_name_before_permanent_deletion(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    admin_user = user_factory()
    assign_role(admin_user, Role.ADMIN)
    client.force_login(admin_user)
    climbing_route = route_factory(name="Delete Me", is_archived=True)
    url = reverse("climbs:route_delete", args=[climbing_route.pk])

    invalid_response = client.post(url, {"name": "delete me"})
    assert invalid_response.status_code == 200
    assert ClimbingRoute.objects.filter(pk=climbing_route.pk).exists()

    valid_response = client.post(url, {"name": "Delete Me"})
    assert valid_response.status_code == 302
    assert not ClimbingRoute.objects.filter(pk=climbing_route.pk).exists()


@pytest.mark.django_db
def test_archived_wall_with_routes_is_still_protected_from_deletion(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    admin_user = user_factory()
    assign_role(admin_user, Role.ADMIN)
    client.force_login(admin_user)
    climbing_route = route_factory(is_archived=True)
    wall = climbing_route.wall
    wall.is_archived = True
    wall.save(update_fields=["is_archived"])

    response = client.post(
        reverse("climbs:wall_delete", args=[wall.pk]),
        {"name": wall.name},
    )

    assert response.status_code == 302
    assert Wall.objects.filter(pk=wall.pk).exists()


@pytest.mark.django_db
def test_project_form_does_not_persist_a_grade(
    client: Client,
    user_factory: Callable[..., User],
    wall_factory: Callable[..., Wall],
) -> None:
    route_setter = user_factory()
    assign_role(route_setter, Role.ROUTE_SETTER)
    client.force_login(route_setter)
    wall = wall_factory()

    response = client.post(
        reverse("climbs:route_create"),
        route_form_data(wall, is_project="on", official_grade="7a"),
    )
    climbing_route = ClimbingRoute.objects.get(name="Created Route")

    assert response.status_code == 302
    assert climbing_route.is_project
    assert climbing_route.official_grade == ""


@pytest.mark.django_db
def test_archive_endpoint_is_csrf_protected(
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    route_setter = user_factory()
    assign_role(route_setter, Role.ROUTE_SETTER)
    climbing_route = route_factory()
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(route_setter)

    response = csrf_client.post(reverse("climbs:route_archive", args=[climbing_route.pk]))

    assert response.status_code == 403
    climbing_route.refresh_from_db()
    assert not climbing_route.is_archived


@pytest.mark.django_db
def test_route_with_ascent_is_protected_from_permanent_deletion(
    client: Client,
    user_factory: Callable[..., User],
    ascent_factory: Callable[..., Ascent],
) -> None:
    admin_user = user_factory(username="delete-admin", email="delete-admin@example.com")
    assign_role(admin_user, Role.ADMIN)
    client.force_login(admin_user)
    ascent = ascent_factory()
    climbing_route = ascent.climbing_route
    climbing_route.is_archived = True
    climbing_route.save(update_fields=["is_archived"])

    response = client.post(
        reverse("climbs:route_delete", args=[climbing_route.pk]),
        {"name": climbing_route.name},
    )

    assert response.status_code == 302
    assert ClimbingRoute.objects.filter(pk=climbing_route.pk).exists()
    assert Ascent.objects.filter(pk=ascent.pk).exists()
