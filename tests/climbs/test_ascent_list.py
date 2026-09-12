from collections.abc import Callable
from datetime import date

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.climbs.grades import encode_perceived_grade
from apps.climbs.models import Ascent, ClimbingRoute, Wall


@pytest.mark.django_db
def test_global_ascent_list_is_public_and_orders_newest_date_first(
    client: Client,
    user_factory: Callable[..., User],
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
) -> None:
    wall = wall_factory(name="Global Wall")
    older_user = user_factory(username="older-climber", email="older-private@example.com")
    newer_user = user_factory(username="newer-climber", email="newer-private@example.com")
    older_route = route_factory(name="Older Route", wall=wall, official_grade="5c")
    newer_route = route_factory(name="Newer Boulder", wall=wall, official_grade="6a+")
    older = ascent_factory(
        user=older_user,
        climbing_route=older_route,
        date=date(2026, 8, 10),
        proposed_grade=encode_perceived_grade("5c", 2),
    )
    newer = ascent_factory(
        user=newer_user,
        climbing_route=newer_route,
        date=date(2026, 9, 11),
        proposed_grade=encode_perceived_grade("6a+", 8),
        attempt_type=Ascent.AttemptType.COUNT,
        attempt_count=3,
    )

    response = client.get(
        reverse("climbs:ascent_list"),
        HTTP_ACCEPT_LANGUAGE="en",
    )

    assert response.status_code == 200
    assert list(response.context["page"].object_list) == [newer, older]
    content = response.content.decode()
    assert 'class="data-list ascent-data-list ascent-data-list-global"' in content
    desktop_header = content.split(
        'class="data-list-header ascent-data-row data-list-header-desktop"',
        maxsplit=1,
    )[1].split(
        'class="data-list-header ascent-data-row data-list-header-compact"',
        maxsplit=1,
    )[0]
    assert all(
        f">{label}</span>" in desktop_header
        for label in (
            "Date",
            "User",
            "Climb",
            "Wall",
            "Grade",
            "Proposed",
            "Attempts",
            "Beauty",
        )
    )
    assert content.index("11/09/2026") < content.index("10/08/2026")
    assert "newer-climber" in content
    assert "Newer Boulder" in content
    assert "Global Wall" in content
    assert "6a+" in content
    assert "6a+.8" in content
    assert "3 attempts" in content
    assert "newer-private@example.com" not in content


@pytest.mark.django_db
def test_global_ascent_list_has_requested_compact_groups_and_italian_text(
    client: Client,
    ascent_factory: Callable[..., Ascent],
) -> None:
    ascent = ascent_factory()
    client.force_login(ascent.user)

    response = client.get(
        reverse("climbs:ascent_list"),
        HTTP_ACCEPT_LANGUAGE="it",
    )
    content = response.content.decode()
    compact_header = content.split(
        'class="data-list-header ascent-data-row data-list-header-compact"',
        maxsplit=1,
    )[1].split('class="data-list-rows"', maxsplit=1)[0]

    assert response.status_code == 200
    assert ">Ripetizioni</h1>" in content
    assert "Tutte le ripetizioni della community, dalla più recente." in content
    assert ">Aggiungi ripetizione</a>" in content
    assert all(
        css_class in content
        for css_class in (
            "ascent-global-user-group",
            "ascent-global-date-cell",
            "ascent-global-route-group",
            "ascent-global-wall-cell",
            "ascent-global-grade-group",
            "ascent-global-activity-group",
        )
    )
    assert all(
        f">{label}</span>" in compact_header for label in ("Utente", "Via", "Grado", "Tentativi")
    )


@pytest.mark.django_db
def test_global_ascent_list_empty_state(client: Client) -> None:
    response = client.get(
        reverse("climbs:ascent_list"),
        HTTP_ACCEPT_LANGUAGE="it",
    )

    assert response.status_code == 200
    assert "Nessuna ripetizione registrata" in response.content.decode()
