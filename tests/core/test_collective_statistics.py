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
    route_factory(
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

    response = client.get(reverse("core:statistics"), HTTP_ACCEPT_LANGUAGE="en")

    assert response.status_code == 200
    assert response.context["active_route_count"] == 3
    assert response.context["route_count"] == 2
    assert response.context["boulder_count"] == 1
    assert response.context["project_count"] == 1
    assert response.context["highest_grade"] == "7a"
    assert len(response.context["monthly_ascents"]) == 12
    assert sum(bucket.count for bucket in response.context["monthly_ascents"]) == 2
    assert [bucket.label for bucket in response.context["grade_distribution"]] == ["6a", "7a"]
    assert b"Collective statistics" in response.content


@pytest.mark.django_db
def test_collective_statistics_has_useful_empty_state(client: Client) -> None:
    response = client.get(reverse("core:statistics"), HTTP_ACCEPT_LANGUAGE="en")

    assert response.status_code == 200
    assert response.context["highest_grade"] == "—"
    assert response.context["maximum_grade_count"] == 0
    assert b"No graded active climbs are available yet" in response.content
