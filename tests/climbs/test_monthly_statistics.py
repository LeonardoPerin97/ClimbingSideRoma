from collections.abc import Callable
from datetime import UTC, date, datetime
from itertools import pairwise

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.climbs.grades import encode_perceived_grade
from apps.climbs.models import Ascent, ClimbingRoute, Wall
from apps.climbs.statistics import (
    MonthlyClimbingSummary,
    user_climbing_context,
    user_monthly_ascent_summary,
)


def _ascent_on(
    day: date,
    grade: str = "6a",
    *,
    discipline: str = ClimbingRoute.Discipline.ROUTE,
    is_project: bool = False,
    is_archived: bool = False,
) -> Ascent:
    """Build unsaved models to exercise the aggregation without database queries."""
    return Ascent(
        date=day,
        climbing_route=ClimbingRoute(
            official_grade=grade,
            discipline=discipline,
            is_project=is_project,
            is_archived=is_archived,
        ),
        proposed_grade=encode_perceived_grade("9c", 9),
    )


def test_empty_monthly_summary_contains_twelve_months_newest_first() -> None:
    summary = user_monthly_ascent_summary([], today=date(2026, 1, 15))

    assert len(summary) == 12
    assert summary[0].month == date(2026, 1, 1)
    assert summary[-1].month == date(2025, 2, 1)
    assert all(earlier.month > later.month for earlier, later in pairwise(summary))
    assert all(
        month.total == 0
        and month.route_count == 0
        and month.boulder_count == 0
        and month.route_max_grade == "—"
        and month.boulder_max_grade == "—"
        for month in summary
    )


def test_monthly_maxima_are_official_separate_by_type_and_not_cumulative() -> None:
    ascents = [
        _ascent_on(date(2026, 1, 5), "7a"),
        _ascent_on(date(2026, 1, 6), "6c+"),
        _ascent_on(date(2026, 1, 7), "5c", discipline=ClimbingRoute.Discipline.BOULDER),
        _ascent_on(date(2026, 1, 8), "6a+", discipline=ClimbingRoute.Discipline.BOULDER),
        _ascent_on(date(2026, 2, 5), "5a"),
        _ascent_on(date(2026, 2, 6), "5a+"),
        _ascent_on(date(2026, 2, 7), "7b", discipline=ClimbingRoute.Discipline.BOULDER),
    ]

    summary = user_monthly_ascent_summary(iter(ascents), today=date(2026, 3, 15))
    march, february, january = summary[:3]

    assert january == MonthlyClimbingSummary(date(2026, 1, 1), 2, "7a", 2, "6a+")
    assert january.total == 4
    assert february == MonthlyClimbingSummary(date(2026, 2, 1), 2, "5a+", 1, "7b")
    assert february.total == 3
    assert march == MonthlyClimbingSummary(date(2026, 3, 1), 0, "—", 0, "—")


def test_monthly_window_includes_boundaries_and_leap_day_but_not_future_dates() -> None:
    ascents = [
        _ascent_on(date(2023, 3, 31), "9c"),
        _ascent_on(date(2023, 4, 1), "5a"),
        _ascent_on(date(2023, 12, 31), "5b"),
        _ascent_on(date(2024, 1, 1), "5c"),
        _ascent_on(date(2024, 2, 29), "6a"),
        _ascent_on(date(2024, 3, 15), "6b"),
        _ascent_on(date(2024, 3, 16), "9c"),
        _ascent_on(date(2024, 4, 1), "9c"),
    ]

    summary = user_monthly_ascent_summary(ascents, today=date(2024, 3, 15))

    assert len(summary) == 12
    assert sum(month.total for month in summary) == 5
    assert summary[-1] == MonthlyClimbingSummary(date(2023, 4, 1), 1, "5a", 0, "—")
    assert summary[3].route_max_grade == "5b"
    assert summary[2].route_max_grade == "5c"
    assert summary[1] == MonthlyClimbingSummary(date(2024, 2, 1), 1, "6a", 0, "—")
    assert summary[0] == MonthlyClimbingSummary(date(2024, 3, 1), 1, "6b", 0, "—")


def test_projects_count_without_grades_and_archived_ascents_are_included() -> None:
    ascents = [
        _ascent_on(date(2026, 2, 2), "", is_project=True),
        _ascent_on(
            date(2026, 2, 3), "", is_project=True, discipline=ClimbingRoute.Discipline.BOULDER
        ),
        _ascent_on(date(2026, 3, 1), "6c+", is_archived=True),
        _ascent_on(
            date(2026, 3, 2), "6b", is_archived=True, discipline=ClimbingRoute.Discipline.BOULDER
        ),
        _ascent_on(date(2026, 3, 3), "", is_project=True),
    ]

    summary = user_monthly_ascent_summary(ascents, today=date(2026, 3, 15))

    assert summary[1] == MonthlyClimbingSummary(date(2026, 2, 1), 1, "—", 1, "—")
    assert summary[1].total == 2
    assert summary[0] == MonthlyClimbingSummary(date(2026, 3, 1), 2, "6c+", 1, "6b")


@pytest.mark.django_db
def test_profile_monthly_summary_uses_one_query_and_only_the_profile_owner(
    user_factory: Callable[..., User],
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
) -> None:
    owner = user_factory()
    another_user = user_factory()
    wall = wall_factory(is_archived=True)
    for index in range(6):
        climbing_route = route_factory(
            wall=wall,
            name=f"Monthly climb {index}",
            official_grade="6a",
            discipline=(
                ClimbingRoute.Discipline.ROUTE if index < 4 else ClimbingRoute.Discipline.BOULDER
            ),
            is_archived=True,
        )
        ascent_factory(user=owner, climbing_route=climbing_route, date=date(2026, 3, 5))
        ascent_factory(user=another_user, climbing_route=climbing_route, date=date(2026, 3, 5))
    ascent_factory(user=owner, date=date(2024, 1, 1))

    with CaptureQueriesContext(connection) as queries:
        context = user_climbing_context(owner, today=date(2026, 3, 15))
        summary = context["monthly_summary"]

    assert len(queries) == 1
    assert context["ascent_count"] == 7
    assert sum(month.total for month in summary) == 6
    assert summary[0] == MonthlyClimbingSummary(date(2026, 3, 1), 4, "6a", 2, "6a")


@pytest.mark.django_db
def test_monthly_summary_changes_after_ascent_edit_delete_and_route_grade_change(
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
) -> None:
    owner = user_factory()
    climbing_route = route_factory(official_grade="6a")
    ascent = ascent_factory(user=owner, climbing_route=climbing_route, date=date(2026, 2, 5))
    today = date(2026, 3, 15)

    before = user_climbing_context(owner, today=today)["monthly_summary"]
    assert before[0].total == 0
    assert before[1].route_max_grade == "6a"

    ascent.date = date(2026, 3, 10)
    ascent.save(update_fields=["date"])
    climbing_route.official_grade = "6b+"
    climbing_route.save(update_fields=["official_grade"])

    after = user_climbing_context(owner, today=today)["monthly_summary"]
    assert after[0].total == 1
    assert after[0].route_max_grade == "6b+"
    assert after[1].total == 0
    assert after[1].route_max_grade == "—"

    ascent.delete()
    deleted = user_climbing_context(owner, today=today)["monthly_summary"]
    assert all(month.total == 0 for month in deleted)


@pytest.mark.django_db
@pytest.mark.parametrize("profile_kind", ["personal", "public"])
@pytest.mark.parametrize("language", ["it", "en"])
def test_monthly_summary_is_translated_on_both_profiles_and_keeps_account_info_last(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
    profile_kind: str,
    language: str,
) -> None:
    today = date(2026, 3, 15)
    owner = user_factory(preferred_language=language, email="monthly-private@example.com")
    route = route_factory(official_grade="5c")
    boulder = route_factory(discipline=ClimbingRoute.Discipline.BOULDER, official_grade="6a+")
    ascent_factory(user=owner, climbing_route=route, date=date(2026, 3, 1))
    ascent_factory(user=owner, climbing_route=boulder, date=date(2026, 3, 2))
    monkeypatch.setattr("apps.climbs.statistics.timezone.localdate", lambda: today)
    if profile_kind == "personal":
        client.force_login(owner)
        url = reverse("accounts:profile")
        footer_heading = "account-information-heading"
    else:
        url = reverse("accounts:public_profile", args=[owner.username])
        footer_heading = "profile-information-heading"

    response = client.get(url, HTTP_ACCEPT_LANGUAGE=language)
    filtered = client.get(
        url,
        {"discipline": ClimbingRoute.Discipline.BOULDER, "sort": "grade"},
        HTTP_ACCEPT_LANGUAGE=language,
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert filtered.status_code == 200
    assert response.context["monthly_summary"] == filtered.context["monthly_summary"]
    assert filtered.context["monthly_summary"][0].total == 2
    assert len(filtered.context["ascents"]) == 1
    assert response.context["monthly_summary_as_of"] == today
    assert content.index("profile-primary-histogram") < content.index(
        'id="monthly-summary-heading"'
    )
    assert content.index('id="monthly-summary-heading"') < content.index("user-ascent-filters")
    assert content.index("user-ascent-filters") < content.index(f'id="{footer_heading}"')
    assert 'role="region"' in content
    assert 'tabindex="0"' in content
    assert 'scope="colgroup"' in content
    assert 'datetime="2026-03"' in content
    assert 'class="monthly-summary-empty"' in content
    if language == "it":
        assert "Andamento mensile" in content
        assert "Marzo 2026" in content
        assert "Aggiornato al 15 Marzo 2026" in content
        assert "Sono incluse le vie archiviate." in content
        assert "Last 12 months" not in content
    else:
        assert "Monthly activity" in content
        assert "March 2026" in content
        assert "Archived climbs are included." in content
    if profile_kind == "public":
        assert owner.email not in content


@pytest.mark.django_db
def test_monthly_summary_default_date_uses_the_application_time_zone(
    monkeypatch: pytest.MonkeyPatch,
    user_factory: Callable[..., User],
) -> None:
    owner = user_factory()
    instant = datetime(2026, 2, 28, 23, 30, tzinfo=UTC)
    monkeypatch.setattr("django.utils.timezone.now", lambda: instant)

    with timezone.override("Europe/Rome"):
        context = user_climbing_context(owner)

    assert context["monthly_summary_as_of"] == date(2026, 3, 1)
    assert context["monthly_summary"][0].month == date(2026, 3, 1)


@pytest.mark.django_db
def test_public_profile_without_ascents_still_renders_twelve_empty_months(
    client: Client,
    user_factory: Callable[..., User],
) -> None:
    owner = user_factory()

    response = client.get(reverse("accounts:public_profile", args=[owner.username]))

    assert response.status_code == 200
    assert len(response.context["monthly_summary"]) == 12
    assert all(month.total == 0 for month in response.context["monthly_summary"])
    assert response.content.decode().count('class="monthly-summary-empty"') == 12
