from collections.abc import Callable
from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.climbs.models import Ascent, ClimbingRoute, Wall


@pytest.mark.django_db
def test_collective_statistics_split_disciplines_and_exclude_archived_grades(
    client: Client,
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
    user_factory: Callable[..., User],
    wall_factory: Callable[..., Wall],
) -> None:
    wall = wall_factory(name="Mixed wall")
    route = route_factory(wall=wall, name="Active route", official_grade="6a")
    boulder = route_factory(
        wall=wall,
        name="Active boulder",
        discipline=ClimbingRoute.Discipline.BOULDER,
        official_grade="7a",
    )
    archived_route = route_factory(
        name="Archived hard route",
        official_grade="9c",
        is_archived=True,
    )
    route_factory(name="Open project", is_project=True, official_grade="")
    first_user = user_factory()
    second_user = user_factory()
    ascent_factory(
        user=first_user,
        climbing_route=route,
        date=timezone.localdate() - timedelta(days=10),
    )
    ascent_factory(
        user=second_user,
        climbing_route=boulder,
        date=timezone.localdate() - timedelta(days=40),
    )
    ascent_factory(
        user=first_user,
        climbing_route=archived_route,
        date=timezone.localdate() - timedelta(days=40),
    )

    response = client.get(reverse("core:statistics"), HTTP_ACCEPT_LANGUAGE="en")

    assert response.status_code == 200
    assert response.context["active_route_count"] == 3
    assert response.context["total_climb_count"] == 4
    assert response.context["ascent_count"] == 3
    assert response.context["route_ascent_count"] == 2
    assert response.context["boulder_ascent_count"] == 1
    assert response.context["route_count"] == 2
    assert response.context["boulder_count"] == 1
    assert response.context["project_count"] == 1
    assert response.context["highest_grade"] == "7a"
    assert response.context["highest_route_grade"] == "6a"
    assert response.context["highest_boulder_grade"] == "7a"
    assert response.context["highest_repeated_route"].label == "9c"
    assert response.context["highest_repeated_route_count"] == 1
    assert response.context["highest_repeated_boulder"].label == "7a"
    assert response.context["highest_repeated_boulder_count"] == 1
    assert response.context["routes_by_wall"][0].ascent_count == 2
    assert len(response.context["monthly_ascents"]) == 12
    assert sum(bucket.count for bucket in response.context["monthly_ascents"]) == 3
    assert [
        (bucket.label, bucket.count, bucket.routes, bucket.boulders)
        for bucket in response.context["repeated_grade_distribution"]
    ] == [("6a", 1, 1, 0), ("7a", 1, 0, 1), ("9c", 1, 1, 0)]
    monthly_months = [bucket.month for bucket in response.context["monthly_ascents"]]
    assert monthly_months == sorted(monthly_months, reverse=True)
    assert monthly_months[0] == timezone.localdate().replace(day=1)
    assert [bucket.label for bucket in response.context["grade_distribution"]] == ["6a", "7a"]
    content = response.content.decode()
    assert "Collective statistics" in content
    assert 'class="monthly-ascent-chart"' in content
    assert "--monthly-bar-height:" in content
    oldest_bucket = response.context["monthly_ascents"][-1]
    current_bucket = response.context["monthly_ascents"][0]
    assert content.index(f'title="{oldest_bucket.month.strftime("%B %Y")}') < content.index(
        f'title="{current_bucket.month.strftime("%B %Y")}'
    )
    header_start = content.index('<header class="catalog-header">')
    header_end = content.index("</header>", header_start)
    assert "<div>" in content[header_start:header_end]


@pytest.mark.django_db
def test_collective_statistics_recent_activity_and_community_ranking(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
    user_factory: Callable[..., User],
) -> None:
    today = timezone.localdate()
    monkeypatch.setattr("apps.core.views.timezone.localdate", lambda: today)
    popular_route = route_factory(name="Popular route", official_grade="7a")
    other_route = route_factory(name="Other route", official_grade="6a")
    old_route = route_factory(name="Old route", official_grade="8a")
    first_user = user_factory(username="first", email="first@example.com")
    second_user = user_factory(username="second", email="second@example.com")
    old_user = user_factory(username="old", email="old@example.com")
    ascent_factory(
        user=first_user,
        climbing_route=popular_route,
        date=today - timedelta(days=1),
    )
    ascent_factory(
        user=second_user,
        climbing_route=popular_route,
        date=today - timedelta(days=2),
    )
    ascent_factory(
        user=first_user,
        climbing_route=other_route,
        date=today - timedelta(days=3),
    )
    ascent_factory(
        user=old_user,
        climbing_route=old_route,
        date=today - timedelta(days=40),
    )

    response = client.get(
        reverse("core:statistics"),
        {"community_period": "30d"},
        HTTP_ACCEPT_LANGUAGE="en",
    )

    assert response.status_code == 200
    assert response.context["recent_ascent_count"] == 3
    assert response.context["recent_active_climber_count"] == 2
    assert response.context["recent_top_climber"].username == "first"
    assert response.context["recent_top_climber"].ascent_count == 2
    assert response.context["recent_top_route"].route == popular_route
    assert response.context["recent_top_route"].ascent_count == 2
    assert response.context["highest_repeated_grade"] == "8a"
    assert response.context["highest_repeated_grade_count"] == 1
    assert [
        (bucket.label, bucket.count, bucket.routes, bucket.boulders)
        for bucket in response.context["repeated_grade_distribution"]
    ] == [("6a", 1, 1, 0), ("7a", 2, 2, 0), ("8a", 1, 1, 0)]
    assert [climber.username for climber in response.context["community_climbers"]] == [
        "first",
        "second",
    ]
    assert all(bucket.bar_height >= 0 for bucket in response.context["monthly_ascents"])

    all_time_response = client.get(
        reverse("core:statistics"),
        {"community_period": "all"},
        HTTP_ACCEPT_LANGUAGE="en",
    )
    assert [climber.username for climber in all_time_response.context["community_climbers"]] == [
        "first",
        "old",
        "second",
    ]
    italian_response = client.get(
        reverse("core:statistics"),
        {"community_period": "30d"},
        HTTP_ACCEPT_LANGUAGE="it",
    )
    italian_content = italian_response.content.decode()
    assert "Attività recente" in italian_content
    assert "Climber più attivo" in italian_content
    assert "Vie totali (attive + archiviate)" in italian_content
    assert "Ripetizioni vie" in italian_content
    assert "Ripetizioni boulder" in italian_content
    assert "Ripetizioni per grado" in italian_content
    assert "Grafico delle ripetizioni mensili" in italian_content


@pytest.mark.django_db
def test_collective_statistics_has_useful_empty_state(client: Client) -> None:
    response = client.get(reverse("core:statistics"), HTTP_ACCEPT_LANGUAGE="en")

    assert response.status_code == 200
    assert response.context["highest_grade"] == "—"
    assert response.context["total_climb_count"] == 0
    assert response.context["ascent_count"] == 0
    assert response.context["route_ascent_count"] == 0
    assert response.context["boulder_ascent_count"] == 0
    assert response.context["highest_route_grade"] == "—"
    assert response.context["highest_boulder_grade"] == "—"
    assert response.context["highest_repeated_grade"] == "—"
    assert response.context["highest_repeated_grade_count"] == 0
    assert response.context["highest_repeated_route"] is None
    assert response.context["highest_repeated_boulder"] is None
    assert response.context["recent_ascent_count"] == 0
    assert response.context["recent_active_climber_count"] == 0
    assert response.context["recent_top_climber"] is None
    assert response.context["recent_top_route"] is None
    assert response.context["community_climbers"] == []
    assert response.context["repeated_grade_distribution"] == []
    assert response.context["maximum_grade_count"] == 0
    assert b"No graded active climbs are available yet" in response.content
    assert b"No ascents are available for this period yet" in response.content
    assert b"No repeated grades are available yet" in response.content
