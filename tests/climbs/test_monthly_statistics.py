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
def test_profile_statistics_use_three_constant_queries_and_only_the_profile_owner(
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

    assert len(queries) == 3
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
def test_profile_activity_is_translated_on_both_profiles_and_keeps_account_info_last(
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
        url = reverse("accounts:public_profile", args=[owner.username])
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
    assert content.index("user-ascent-filters") < content.index('id="monthly-summary-heading"')
    assert content.index('id="monthly-summary-heading"') < content.index(f'id="{footer_heading}"')
    assert 'role="region"' in content
    assert 'tabindex="0"' in content
    assert 'datetime="2026-03"' in content
    assert content.index('datetime="2025-04"') < content.index('datetime="2026-03"')
    assert content.count("monthly-summary-empty") == 11
    assert 'id="highest-grade-trend-heading"' in content
    assert 'onchange="this.form.submit()"' in content
    assert 'id="profile-activity"' in content
    assert 'action="#profile-activity"' in content
    assert 'class="grade-trend-series grade-trend-series-route"' in content
    assert 'class="grade-trend-series grade-trend-series-boulder"' in content
    assert response.context["profile_grade_trend"][0].month == date(2025, 4, 1)
    assert response.context["profile_grade_trend"][-1].month == date(2026, 3, 1)
    assert response.context["profile_grade_trend"][-1].route_grade == "5c"
    assert response.context["profile_grade_trend"][-1].boulder_grade == "6a+"
    if language == "it":
        assert "Attività del profilo" in content
        assert "Ripetizioni mensili negli ultimi 12 mesi." in content
        assert "Grado più alto negli ultimi 12 mesi" in content
        assert "Grado più alto per mese" in content
        assert "Aggiornato al 15/03/2026" in content
        assert "Prima il mese più vecchio, poi quello corrente." not in content
        assert "Last 12 months" not in content
    else:
        assert "Profile activity" in content
        assert "Monthly ascents during the last 12 months." in content
        assert "Highest grade in the last 12 months" in content
        assert "Highest grade by month" in content
        assert "Oldest month first, then the current month." not in content
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
    assert response.content.decode().count("monthly-summary-empty") == 12


@pytest.mark.django_db
def test_profile_period_switch_changes_count_and_highest_grade(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
) -> None:
    today = date(2026, 3, 15)
    monkeypatch.setattr("apps.climbs.statistics.timezone.localdate", lambda: today)
    owner = user_factory()
    recent_route = route_factory(name="Recent", official_grade="6a")
    older_route = route_factory(name="Older", official_grade="8a")
    ascent_factory(user=owner, climbing_route=recent_route, date=date(2026, 3, 5))
    ascent_factory(user=owner, climbing_route=older_route, date=date(2024, 1, 5))

    url = reverse("accounts:public_profile", args=[owner.username])
    response = client.get(url, {"profile_period": "12m"})
    all_time_response = client.get(url, {"profile_period": "all"})

    assert response.context["profile_period"] == "12m"
    assert response.context["profile_period_ascent_count"] == 1
    assert response.context["profile_period_highest_grade"] == "6a"
    assert all_time_response.context["profile_period"] == "all"
    assert all_time_response.context["profile_period_ascent_count"] == 2
    assert all_time_response.context["profile_period_highest_grade"] == "8a"
    assert sum(bucket.count for bucket in response.context["profile_monthly_ascents"]) == 1
    assert sum(bucket.count for bucket in all_time_response.context["profile_monthly_ascents"]) == 2
    assert response.context["profile_monthly_summary"][-1].month == date(2025, 4, 1)
    assert all_time_response.context["profile_monthly_summary"][-1].month == date(2024, 1, 1)
    all_time_trend = all_time_response.context["profile_grade_trend"]
    assert all_time_trend[0].month == date(2024, 1, 1)
    assert all_time_trend[-1].month == date(2026, 3, 1)
    assert len(all_time_response.context["profile_route_grade_segments"]) == 1
    segment = all_time_response.context["profile_route_grade_segments"][0]
    assert segment.x1 < segment.x2
    assert len(all_time_response.context["profile_grade_trend_axis"]) <= 5
    assert all_time_response.context["profile_grade_trend_axis"][0].label == "6a"
    assert all_time_response.context["profile_grade_trend_axis"][-1].label == "8a"
    all_time_content = all_time_response.content.decode()
    assert (
        f'viewBox="0 0 {all_time_response.context["profile_grade_trend_width"]} 320"'
        in all_time_content
    )
    assert "Ripetizioni di sempre" in all_time_content
    assert '<option value="all" selected' in all_time_response.content.decode()
