from collections.abc import Callable

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.roles import Role, assign_role
from apps.climbs.models import Ascent, ClimbingRoute, RouteImage, Wall
from apps.core.audit import record_audit_event
from apps.core.models import AuditLogEntry


@pytest.mark.django_db
def test_audit_event_records_only_explicit_safe_metadata(
    user_factory: Callable[..., User],
) -> None:
    actor = user_factory()

    entry = record_audit_event(
        actor=actor,
        action=AuditLogEntry.Action.UPDATE,
        entity_type="route",
        entity_id=42,
        metadata={"wall_id": 7},
    )

    assert entry.actor == actor
    assert entry.entity_id == "42"
    assert entry.metadata == {"wall_id": 7}
    assert "route #42" in str(entry)


@pytest.mark.django_db
def test_management_dashboard_requires_an_administrator(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    url = reverse("core:management_dashboard")
    assert client.get(url).status_code == 302

    user = user_factory()
    client.force_login(user)
    assert client.get(url).status_code == 403

    assign_role(user, Role.ROUTE_SETTER)
    user.refresh_from_db()
    assert client.get(url).status_code == 403


@pytest.mark.django_db
def test_management_dashboard_summarises_data_and_recent_audit(
    client: Client,
    user_factory: Callable[..., User],
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
    route_image_factory: Callable[..., RouteImage],
) -> None:
    admin_user = user_factory()
    route_setter = user_factory()
    assign_role(admin_user, Role.ADMIN)
    assign_role(route_setter, Role.ROUTE_SETTER)
    wall = wall_factory()
    climbing_route = route_factory(wall=wall)
    ascent_factory(climbing_route=climbing_route)
    route_image_factory(climbing_route=climbing_route, uploaded_by=route_setter)
    record_audit_event(
        actor=admin_user,
        action=AuditLogEntry.Action.CREATE,
        entity_type="wall",
        entity_id=wall.pk,
    )
    client.force_login(admin_user)

    response = client.get(reverse("core:management_dashboard"))

    assert response.status_code == 200
    assert response.context["active_wall_count"] == 1
    assert response.context["active_route_count"] == 1
    assert response.context["ascent_count"] == 1
    assert response.context["image_count"] == 1
    assert response.context["admin_count"] == 1
    assert response.context["route_setter_count"] == 1
    assert "Attività amministrative recenti" in response.content.decode()


@pytest.mark.django_db
def test_route_creation_persists_audit_event(
    client: Client,
    user_factory: Callable[..., User],
    wall_factory: Callable[..., Wall],
) -> None:
    route_setter = user_factory()
    assign_role(route_setter, Role.ROUTE_SETTER)
    wall = wall_factory()
    client.force_login(route_setter)

    response = client.post(
        reverse("climbs:route_create"),
        {
            "name": "Audited route",
            "wall": wall.pk,
            "discipline": ClimbingRoute.Discipline.ROUTE,
            "official_grade": "6b",
        },
    )

    climbing_route = ClimbingRoute.objects.get(name="Audited route")
    entry = AuditLogEntry.objects.get(entity_type="route", entity_id=str(climbing_route.pk))
    assert response.status_code == 302
    assert entry.actor == route_setter
    assert entry.action == AuditLogEntry.Action.CREATE
    assert entry.metadata == {
        "wall_id": wall.pk,
        "discipline": ClimbingRoute.Discipline.ROUTE,
    }
