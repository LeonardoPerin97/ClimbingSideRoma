from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import pairwise
from typing import Any

from django.db.models import Count, Max, Q
from django.db.models.functions import Lower, TruncMonth
from django.utils import timezone

from apps.accounts.models import User

from .grades import (
    FRENCH_GRADE_BASES,
    FRENCH_GRADE_INDEX,
    format_grade_index,
    format_perceived_grade,
    grade_order_expression,
)
from .models import Ascent, ClimbingRoute, Wall


@dataclass(frozen=True)
class StatisticBucket:
    label: str
    count: int


@dataclass(frozen=True)
class UserWallProgressBucket:
    wall: Wall
    completed: int
    total: int

    @property
    def label(self) -> str:
        return self.wall.name

    @property
    def count(self) -> int:
        return self.completed

    @property
    def percentage(self) -> float:
        return percentage(self.completed, self.total)


@dataclass(frozen=True)
class CollectiveGradeBucket:
    label: str
    total: int
    routes: int
    boulders: int

    @property
    def count(self) -> int:
        """Expose the total using the common histogram bucket interface."""
        return self.total


@dataclass(frozen=True)
class WallDisciplineBucket:
    wall: Wall
    total: int
    routes: int
    boulders: int
    ascent_count: int


@dataclass(frozen=True)
class MonthlyAscentBucket:
    month: date
    count: int
    bar_height: int = 0


@dataclass(frozen=True)
class CommunityClimberBucket:
    user_id: int
    username: str
    ascent_count: int
    highest_grade: str


@dataclass(frozen=True)
class RepeatedGradeBucket:
    label: str
    count: int
    routes: int
    boulders: int


@dataclass(frozen=True)
class RecentRouteBucket:
    route: ClimbingRoute
    ascent_count: int


@dataclass(frozen=True)
class MonthlyClimbingSummary:
    month: date
    route_count: int
    route_max_grade: str
    boulder_count: int
    boulder_max_grade: str

    @property
    def total(self) -> int:
        return self.route_count + self.boulder_count


@dataclass(frozen=True)
class MonthlyGradeTrendPoint:
    month: date
    x: int
    route_grade: str
    route_y: int | None
    boulder_grade: str
    boulder_y: int | None


@dataclass(frozen=True)
class GradeTrendSegment:
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True)
class GradeTrendAxisTick:
    label: str
    y: int


GRADE_TREND_TOP = 20
GRADE_TREND_BOTTOM = 270
GRADE_TREND_LEFT = 56
GRADE_TREND_DEFAULT_RIGHT = 704
GRADE_TREND_STEP = 59


def _grade_trend_y(
    grade: str,
    *,
    minimum_grade_index: int,
    maximum_grade_index: int,
) -> int | None:
    grade_index = FRENCH_GRADE_INDEX.get(grade)
    if grade_index is None:
        return None
    grade_range = maximum_grade_index - minimum_grade_index
    if not grade_range:
        return (GRADE_TREND_TOP + GRADE_TREND_BOTTOM) // 2
    return GRADE_TREND_BOTTOM - round(
        (grade_index - minimum_grade_index) / grade_range * (GRADE_TREND_BOTTOM - GRADE_TREND_TOP)
    )


def _monthly_grade_trend(
    summaries: Iterable[MonthlyClimbingSummary],
) -> tuple[
    list[MonthlyGradeTrendPoint],
    list[GradeTrendSegment],
    list[GradeTrendSegment],
    list[GradeTrendAxisTick],
    int,
    int,
]:
    chronological_summaries = list(reversed(list(summaries)))
    month_count = len(chronological_summaries)
    chart_right = max(
        GRADE_TREND_DEFAULT_RIGHT,
        GRADE_TREND_LEFT + max(month_count - 1, 1) * GRADE_TREND_STEP,
    )
    chart_width = chart_right + 16
    step = (chart_right - GRADE_TREND_LEFT) / max(month_count - 1, 1)
    grade_indexes = [
        FRENCH_GRADE_INDEX[grade]
        for summary in chronological_summaries
        for grade in (summary.route_max_grade, summary.boulder_max_grade)
        if grade in FRENCH_GRADE_INDEX
    ]
    if grade_indexes:
        minimum_grade_index = min(grade_indexes)
        maximum_grade_index = max(grade_indexes)
    else:
        minimum_grade_index = 0
        maximum_grade_index = len(FRENCH_GRADE_BASES) - 1
    if minimum_grade_index == maximum_grade_index:
        minimum_grade_index = max(0, minimum_grade_index - 1)
        maximum_grade_index = min(
            len(FRENCH_GRADE_BASES) - 1,
            maximum_grade_index + 1,
        )
    points = [
        MonthlyGradeTrendPoint(
            month=summary.month,
            x=round(GRADE_TREND_LEFT + index * step),
            route_grade=summary.route_max_grade,
            route_y=_grade_trend_y(
                summary.route_max_grade,
                minimum_grade_index=minimum_grade_index,
                maximum_grade_index=maximum_grade_index,
            ),
            boulder_grade=summary.boulder_max_grade,
            boulder_y=_grade_trend_y(
                summary.boulder_max_grade,
                minimum_grade_index=minimum_grade_index,
                maximum_grade_index=maximum_grade_index,
            ),
        )
        for index, summary in enumerate(chronological_summaries)
    ]

    def make_segments(
        values: list[int | None],
    ) -> list[GradeTrendSegment]:
        populated_points: list[tuple[MonthlyGradeTrendPoint, int]] = []
        for point, point_y in zip(points, values, strict=True):
            if point_y is not None:
                populated_points.append((point, point_y))
        return [
            GradeTrendSegment(
                x1=point.x,
                y1=point_y,
                x2=next_point.x,
                y2=next_point_y,
            )
            for (point, point_y), (next_point, next_point_y) in pairwise(populated_points)
        ]

    axis_range = maximum_grade_index - minimum_grade_index
    if axis_range <= 4:
        axis_indexes = list(range(minimum_grade_index, maximum_grade_index + 1))
    else:
        axis_indexes = sorted(
            {
                round(
                    minimum_grade_index + index * axis_range / 4,
                )
                for index in range(5)
            }
        )
    axis_ticks = [
        GradeTrendAxisTick(
            label=FRENCH_GRADE_BASES[grade_index],
            y=(
                GRADE_TREND_BOTTOM
                - round(
                    (grade_index - minimum_grade_index)
                    / max(axis_range, 1)
                    * (GRADE_TREND_BOTTOM - GRADE_TREND_TOP)
                )
            ),
        )
        for grade_index in axis_indexes
    ]
    return (
        points,
        make_segments([point.route_y for point in points]),
        make_segments([point.boulder_y for point in points]),
        axis_ticks,
        chart_width,
        chart_right,
    )


def _monthly_chart_buckets(
    summaries: Iterable[MonthlyClimbingSummary],
) -> list[MonthlyAscentBucket]:
    buckets = [
        MonthlyAscentBucket(month=summary.month, count=summary.total) for summary in summaries
    ]
    maximum_count = max((bucket.count for bucket in buckets), default=0)
    if not maximum_count:
        return buckets
    return [
        MonthlyAscentBucket(
            month=bucket.month,
            count=bucket.count,
            bar_height=round(bucket.count / maximum_count * 100),
        )
        for bucket in buckets
    ]


def _highest_grade_index(ascents: Iterable[Ascent]) -> int:
    return max(
        (
            FRENCH_GRADE_INDEX.get(ascent.climbing_route.official_grade, -1)
            for ascent in ascents
            if not ascent.climbing_route.is_project
        ),
        default=-1,
    )


def percentage(completed: int, total: int) -> float:
    """Return a bounded completion percentage, including the empty-catalogue case."""
    if total <= 0:
        return 0.0
    return min(round((completed / total) * 100, 1), 100.0)


def continuous_perceived_grade_distribution(
    counts: Mapping[int, int],
) -> list[StatisticBucket]:
    """Return every decimal grade between the lowest and highest proposal."""
    populated_values = [value for value, count in counts.items() if count]
    if not populated_values:
        return []
    return [
        StatisticBucket(format_perceived_grade(value), counts.get(value, 0))
        for value in range(min(populated_values), max(populated_values) + 1)
    ]


def continuous_discipline_grade_distribution(
    counts: Mapping[str, Mapping[str, int]],
    *,
    project_counts: Mapping[str, int] | None = None,
) -> list[CollectiveGradeBucket]:
    """Return a continuous French-grade series split into routes and boulders."""
    populated_indexes = [
        FRENCH_GRADE_INDEX[grade]
        for grade, discipline_counts in counts.items()
        if grade in FRENCH_GRADE_INDEX and any(discipline_counts.values())
    ]
    buckets: list[CollectiveGradeBucket] = []
    if populated_indexes:
        for index in range(min(populated_indexes), max(populated_indexes) + 1):
            grade = FRENCH_GRADE_BASES[index]
            discipline_counts = counts.get(grade, {})
            route_count = discipline_counts.get(ClimbingRoute.Discipline.ROUTE, 0)
            boulder_count = discipline_counts.get(ClimbingRoute.Discipline.BOULDER, 0)
            buckets.append(
                CollectiveGradeBucket(
                    label=grade,
                    total=route_count + boulder_count,
                    routes=route_count,
                    boulders=boulder_count,
                )
            )

    project_counts = project_counts or {}
    project_routes = project_counts.get(ClimbingRoute.Discipline.ROUTE, 0)
    project_boulders = project_counts.get(ClimbingRoute.Discipline.BOULDER, 0)
    if project_routes or project_boulders:
        buckets.append(
            CollectiveGradeBucket(
                label="Project",
                total=project_routes + project_boulders,
                routes=project_routes,
                boulders=project_boulders,
            )
        )
    return buckets


def _month_start(month: date, offset: int) -> date:
    month_index = month.year * 12 + month.month - 1 + offset
    year, zero_based_month = divmod(month_index, 12)
    return date(year, zero_based_month + 1, 1)


def _period_start(today: date, period: str) -> date | None:
    if period == "30d":
        return today - timedelta(days=29)
    if period == "12m":
        return _month_start(today.replace(day=1), -11)
    return None


def _community_climber_buckets(
    *,
    start_date: date | None,
    today: date,
) -> list[CommunityClimberBucket]:
    period_filter = Q(ascents__date__lte=today)
    if start_date is not None:
        period_filter &= Q(ascents__date__gte=start_date)
    users = (
        User.objects.filter(is_active=True)
        .annotate(
            period_ascent_count=Count(
                "ascents",
                filter=period_filter,
                distinct=True,
            ),
            period_highest_grade_order=Max(
                grade_order_expression(
                    "ascents__climbing_route__official_grade",
                    default_value=-1,
                ),
                filter=period_filter,
            ),
        )
        .filter(period_ascent_count__gt=0)
        .order_by(
            "-period_ascent_count",
            "-period_highest_grade_order",
            Lower("username"),
        )[:5]
    )
    return [
        CommunityClimberBucket(
            user_id=user.pk,
            username=user.username,
            ascent_count=user.period_ascent_count,
            highest_grade=format_grade_index(user.period_highest_grade_order),
        )
        for user in users
    ]


def _repeated_grade_buckets() -> list[RepeatedGradeBucket]:
    rows = (
        Ascent.objects.filter(climbing_route__is_project=False)
        .values("climbing_route__official_grade", "climbing_route__discipline")
        .annotate(count=Count("id"))
    )
    counts: dict[str, dict[str, int]] = {}
    for row in rows:
        grade_counts = counts.setdefault(
            row["climbing_route__official_grade"],
            {
                ClimbingRoute.Discipline.ROUTE: 0,
                ClimbingRoute.Discipline.BOULDER: 0,
            },
        )
        grade_counts[row["climbing_route__discipline"]] = row["count"]
    return [
        RepeatedGradeBucket(
            label=grade,
            count=(
                counts[grade][ClimbingRoute.Discipline.ROUTE]
                + counts[grade][ClimbingRoute.Discipline.BOULDER]
            ),
            routes=counts[grade][ClimbingRoute.Discipline.ROUTE],
            boulders=counts[grade][ClimbingRoute.Discipline.BOULDER],
        )
        for grade in FRENCH_GRADE_BASES
        if grade in counts
    ]


def user_monthly_ascent_summary(
    ascents: Iterable[Ascent],
    *,
    today: date,
    first_month: date | None = None,
) -> list[MonthlyClimbingSummary]:
    """Summarize calendar months, newest first, by ascent date.

    Maxima use current official grades, independently for each month and type.
    Archived climbs still count; Projects count without contributing a grade.
    Pass ascents with their climbing routes already loaded to avoid N+1 queries.

    By default, summarize the current month and the previous 11 months.
    """
    current_month = today.replace(day=1)
    first_month = (first_month or _month_start(current_month, -11)).replace(day=1)
    if first_month > current_month:
        first_month = current_month
    month_count = (
        (current_month.year - first_month.year) * 12 + current_month.month - first_month.month + 1
    )
    counts: Counter[tuple[date, str]] = Counter()
    maximum_grades: dict[tuple[date, str], int] = {}

    for ascent in ascents:
        if not first_month <= ascent.date <= today:
            continue
        climbing_route = ascent.climbing_route
        key = (ascent.date.replace(day=1), climbing_route.discipline)
        counts[key] += 1
        if not climbing_route.is_project:
            grade_index = FRENCH_GRADE_INDEX.get(climbing_route.official_grade, -1)
            maximum_grades[key] = max(maximum_grades.get(key, -1), grade_index)

    summaries: list[MonthlyClimbingSummary] = []
    for offset in range(0, -month_count, -1):
        month = _month_start(current_month, offset)
        route_key = (month, ClimbingRoute.Discipline.ROUTE)
        boulder_key = (month, ClimbingRoute.Discipline.BOULDER)
        summaries.append(
            MonthlyClimbingSummary(
                month=month,
                route_count=counts[route_key],
                route_max_grade=format_grade_index(maximum_grades.get(route_key)),
                boulder_count=counts[boulder_key],
                boulder_max_grade=format_grade_index(maximum_grades.get(boulder_key)),
            )
        )
    return summaries


def collective_statistics_context(
    *,
    today: date,
    community_period: str = "30d",
) -> dict[str, Any]:
    if community_period not in {"30d", "12m", "all"}:
        community_period = "30d"

    active_routes = ClimbingRoute.objects.filter(is_archived=False)
    discipline_rows = active_routes.values("discipline").annotate(count=Count("id"))
    discipline_counts = {row["discipline"]: row["count"] for row in discipline_rows}
    ascent_rows = Ascent.objects.values("climbing_route__discipline").annotate(count=Count("id"))
    ascent_counts = {row["climbing_route__discipline"]: row["count"] for row in ascent_rows}
    ascent_count = sum(ascent_counts.values())

    grade_rows = (
        active_routes.filter(is_project=False)
        .values("official_grade", "discipline")
        .annotate(count=Count("id"))
    )
    grade_counts: dict[str, dict[str, int]] = {
        grade: {
            ClimbingRoute.Discipline.ROUTE: 0,
            ClimbingRoute.Discipline.BOULDER: 0,
        }
        for grade in FRENCH_GRADE_BASES
    }
    for row in grade_rows:
        grade_counts[row["official_grade"]][row["discipline"]] = row["count"]
    grade_distribution = [
        CollectiveGradeBucket(
            label=grade,
            total=sum(grade_counts[grade].values()),
            routes=grade_counts[grade][ClimbingRoute.Discipline.ROUTE],
            boulders=grade_counts[grade][ClimbingRoute.Discipline.BOULDER],
        )
        for grade in FRENCH_GRADE_BASES
        if sum(grade_counts[grade].values())
    ]

    walls = (
        Wall.objects.filter(is_archived=False)
        .annotate(
            active_route_count=Count(
                "climbing_routes",
                filter=Q(climbing_routes__is_archived=False),
                distinct=True,
            ),
            route_count=Count(
                "climbing_routes",
                filter=Q(
                    climbing_routes__is_archived=False,
                    climbing_routes__discipline=ClimbingRoute.Discipline.ROUTE,
                ),
                distinct=True,
            ),
            boulder_count=Count(
                "climbing_routes",
                filter=Q(
                    climbing_routes__is_archived=False,
                    climbing_routes__discipline=ClimbingRoute.Discipline.BOULDER,
                ),
                distinct=True,
            ),
            ascent_count=Count(
                "climbing_routes__ascents",
                filter=Q(climbing_routes__is_archived=False),
                distinct=True,
            ),
        )
        .order_by("name")
    )
    routes_by_wall = [
        WallDisciplineBucket(
            wall=wall,
            total=wall.active_route_count,
            routes=wall.route_count,
            boulders=wall.boulder_count,
            ascent_count=wall.ascent_count,
        )
        for wall in walls
    ]

    current_month = today.replace(day=1)
    first_month = _month_start(current_month, -11)
    monthly_rows = (
        Ascent.objects.filter(date__gte=first_month, date__lte=today)
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    counts_by_month = {
        row["month"].date() if hasattr(row["month"], "date") else row["month"]: row["count"]
        for row in monthly_rows
    }
    monthly_ascents = [
        MonthlyAscentBucket(month=month, count=counts_by_month.get(month, 0))
        for month in (_month_start(current_month, offset) for offset in range(0, -12, -1))
    ]
    maximum_monthly_ascent_count = max(
        (bucket.count for bucket in monthly_ascents),
        default=0,
    )
    if maximum_monthly_ascent_count:
        monthly_ascents = [
            MonthlyAscentBucket(
                month=bucket.month,
                count=bucket.count,
                bar_height=round(bucket.count / maximum_monthly_ascent_count * 100),
            )
            for bucket in monthly_ascents
        ]

    recent_start = _period_start(today, "30d")
    recent_filter = Q(date__gte=recent_start, date__lte=today)
    recent_ascents = Ascent.objects.filter(recent_filter)
    recent_active_climber_count = (
        User.objects.filter(
            is_active=True,
            ascents__date__gte=recent_start,
            ascents__date__lte=today,
        )
        .distinct()
        .count()
    )
    recent_climbers = _community_climber_buckets(
        start_date=recent_start,
        today=today,
    )
    recent_route = (
        ClimbingRoute.objects.select_related("wall")
        .annotate(
            recent_ascent_count=Count(
                "ascents",
                filter=Q(ascents__date__gte=recent_start, ascents__date__lte=today),
                distinct=True,
            )
        )
        .filter(recent_ascent_count__gt=0)
        .order_by("-recent_ascent_count", Lower("name"))
        .first()
    )
    recent_top_route = (
        RecentRouteBucket(
            route=recent_route,
            ascent_count=recent_route.recent_ascent_count,
        )
        if recent_route is not None
        else None
    )
    repeated_grade_distribution = _repeated_grade_buckets()
    highest_repeated_grade = (
        repeated_grade_distribution[-1] if repeated_grade_distribution else None
    )
    community_start = _period_start(today, community_period)
    community_climbers = _community_climber_buckets(
        start_date=community_start,
        today=today,
    )

    active_route_count = active_routes.count()
    total_climb_count = ClimbingRoute.objects.count()
    highest_grade_order = active_routes.filter(is_project=False).aggregate(
        highest=Max(grade_order_expression())
    )["highest"]
    highest_route_grade = next(
        (bucket.label for bucket in reversed(grade_distribution) if bucket.routes),
        "—",
    )
    highest_boulder_grade = next(
        (bucket.label for bucket in reversed(grade_distribution) if bucket.boulders),
        "—",
    )
    highest_repeated_route = next(
        (bucket for bucket in reversed(repeated_grade_distribution) if bucket.routes),
        None,
    )
    highest_repeated_boulder = next(
        (bucket for bucket in reversed(repeated_grade_distribution) if bucket.boulders),
        None,
    )
    return {
        "active_route_count": active_route_count,
        "total_climb_count": total_climb_count,
        "route_count": discipline_counts.get(ClimbingRoute.Discipline.ROUTE, 0),
        "boulder_count": discipline_counts.get(ClimbingRoute.Discipline.BOULDER, 0),
        "active_wall_count": len(routes_by_wall),
        "active_user_count": User.objects.filter(is_active=True).count(),
        "ascent_count": ascent_count,
        "route_ascent_count": ascent_counts.get(ClimbingRoute.Discipline.ROUTE, 0),
        "boulder_ascent_count": ascent_counts.get(ClimbingRoute.Discipline.BOULDER, 0),
        "project_count": active_routes.filter(is_project=True).count(),
        "highest_grade": format_grade_index(highest_grade_order),
        "highest_route_grade": highest_route_grade,
        "highest_boulder_grade": highest_boulder_grade,
        "highest_repeated_grade": highest_repeated_grade.label if highest_repeated_grade else "—",
        "highest_repeated_grade_count": highest_repeated_grade.count
        if highest_repeated_grade
        else 0,
        "highest_repeated_route": highest_repeated_route,
        "highest_repeated_route_count": highest_repeated_route.routes
        if highest_repeated_route
        else 0,
        "highest_repeated_boulder": highest_repeated_boulder,
        "highest_repeated_boulder_count": highest_repeated_boulder.boulders
        if highest_repeated_boulder
        else 0,
        "grade_distribution": grade_distribution,
        "repeated_grade_distribution": repeated_grade_distribution,
        "routes_by_wall": routes_by_wall,
        "monthly_ascents": monthly_ascents,
        "recent_ascent_count": recent_ascents.count(),
        "recent_active_climber_count": recent_active_climber_count,
        "recent_top_climber": recent_climbers[0] if recent_climbers else None,
        "recent_top_route": recent_top_route,
        "community_period": community_period,
        "community_climbers": community_climbers,
        "statistics_as_of": today,
        "maximum_grade_count": max(
            (bucket.total for bucket in grade_distribution),
            default=0,
        ),
        "maximum_wall_count": max(
            (bucket.total for bucket in routes_by_wall),
            default=0,
        ),
        "maximum_monthly_ascent_count": max(
            (bucket.count for bucket in monthly_ascents),
            default=0,
        ),
        "maximum_repeated_grade_count": max(
            (bucket.count for bucket in repeated_grade_distribution),
            default=0,
        ),
    }


def user_climbing_context(
    user: User,
    *,
    ascent_sort: str = "date_desc",
    ascent_discipline: str = "",
    profile_period: str = "12m",
    catalogue_scope: str = "all",
    today: date | None = None,
) -> dict[str, Any]:
    if catalogue_scope not in {"active", "all"}:
        catalogue_scope = "all"

    ascents_queryset = (
        Ascent.objects.filter(user=user)
        .select_related("climbing_route", "climbing_route__wall")
        .annotate(
            official_grade_order=grade_order_expression(
                "climbing_route__official_grade",
            )
        )
    )
    if ascent_sort == "date_asc":
        ascents_queryset = ascents_queryset.order_by("date", "created_at")
    elif ascent_sort == "grade":
        ascents_queryset = ascents_queryset.order_by(
            "climbing_route__is_project",
            "official_grade_order",
            Lower("climbing_route__name"),
        )
    elif ascent_sort == "grade_desc":
        ascents_queryset = ascents_queryset.order_by(
            "climbing_route__is_project",
            "-official_grade_order",
            Lower("climbing_route__name"),
        )
    else:
        ascent_sort = "date_desc"
        ascents_queryset = ascents_queryset.order_by("-date", "-created_at")
    all_ascents = list(ascents_queryset)
    statistics_today = today if today is not None else timezone.localdate()
    if profile_period not in {"12m", "all"}:
        profile_period = "12m"
    monthly_summary = user_monthly_ascent_summary(all_ascents, today=statistics_today)
    if profile_period == "12m":
        first_month = _month_start(statistics_today.replace(day=1), -11)
        period_ascents = [
            ascent for ascent in all_ascents if first_month <= ascent.date <= statistics_today
        ]
        profile_monthly_summary = monthly_summary
    else:
        period_ascents = [ascent for ascent in all_ascents if ascent.date <= statistics_today]
        earliest_ascent = min(
            (ascent.date for ascent in period_ascents),
            default=None,
        )
        first_month = (
            earliest_ascent.replace(day=1)
            if earliest_ascent is not None
            else _month_start(statistics_today.replace(day=1), -11)
        )
        profile_monthly_summary = user_monthly_ascent_summary(
            period_ascents,
            today=statistics_today,
            first_month=first_month,
        )
    profile_monthly_ascents = _monthly_chart_buckets(profile_monthly_summary)
    (
        profile_grade_trend,
        profile_route_grade_segments,
        profile_boulder_grade_segments,
        profile_grade_trend_axis,
        profile_grade_trend_width,
        profile_grade_trend_right,
    ) = _monthly_grade_trend(profile_monthly_summary)
    if ascent_discipline in ClimbingRoute.Discipline.values:
        selected_discipline = ascent_discipline
        ascents = [
            ascent
            for ascent in all_ascents
            if ascent.climbing_route.discipline == selected_discipline
        ]
    else:
        selected_discipline = ""
        ascents = all_ascents

    completion_ascents = (
        [ascent for ascent in all_ascents if not ascent.climbing_route.is_archived]
        if catalogue_scope == "active"
        else all_ascents
    )

    discipline_counts: dict[str, int] = {
        ClimbingRoute.Discipline.ROUTE: 0,
        ClimbingRoute.Discipline.BOULDER: 0,
    }
    official_grade_counts: dict[str, dict[str, int]] = {}
    project_counts: dict[str, int] = {
        ClimbingRoute.Discipline.ROUTE: 0,
        ClimbingRoute.Discipline.BOULDER: 0,
    }
    highest_grade_order = -1

    for ascent in all_ascents:
        climbing_route = ascent.climbing_route
        discipline_counts[climbing_route.discipline] += 1
        if climbing_route.is_project:
            project_counts[climbing_route.discipline] += 1
            continue
        grade_counts = official_grade_counts.setdefault(
            climbing_route.official_grade,
            {
                ClimbingRoute.Discipline.ROUTE: 0,
                ClimbingRoute.Discipline.BOULDER: 0,
            },
        )
        grade_counts[climbing_route.discipline] += 1
        highest_grade_order = max(
            highest_grade_order,
            FRENCH_GRADE_INDEX[climbing_route.official_grade],
        )

    completion_discipline_counts: dict[str, int] = {
        ClimbingRoute.Discipline.ROUTE: 0,
        ClimbingRoute.Discipline.BOULDER: 0,
    }
    completion_wall_counter: Counter[int] = Counter()
    for ascent in completion_ascents:
        climbing_route = ascent.climbing_route
        completion_discipline_counts[climbing_route.discipline] += 1
        completion_wall_counter[climbing_route.wall_id] += 1

    grade_distribution = continuous_discipline_grade_distribution(
        official_grade_counts,
        project_counts=project_counts,
    )
    graded_distribution = [
        bucket for bucket in grade_distribution if bucket.label in FRENCH_GRADE_INDEX
    ]
    highest_route_grade = next(
        (bucket.label for bucket in reversed(graded_distribution) if bucket.routes),
        "—",
    )
    highest_boulder_grade = next(
        (bucket.label for bucket in reversed(graded_distribution) if bucket.boulders),
        "—",
    )
    catalogue_routes = ClimbingRoute.objects.all()
    if catalogue_scope == "active":
        catalogue_routes = catalogue_routes.filter(is_archived=False)
    catalogue_counts = {
        row["discipline"]: row["count"]
        for row in catalogue_routes.order_by().values("discipline").annotate(count=Count("id"))
    }
    total_route_count = catalogue_counts.get(ClimbingRoute.Discipline.ROUTE, 0)
    total_boulder_count = catalogue_counts.get(ClimbingRoute.Discipline.BOULDER, 0)
    total_climb_count = total_route_count + total_boulder_count

    if catalogue_scope == "active":
        catalogue_walls = Wall.objects.annotate(
            total_climbs=Count(
                "climbing_routes",
                filter=Q(climbing_routes__is_archived=False),
            )
        )
    else:
        catalogue_walls = Wall.objects.annotate(total_climbs=Count("climbing_routes"))
    catalogue_walls = catalogue_walls.filter(total_climbs__gt=0).order_by(Lower("name"))
    wall_distribution = sorted(
        (
            UserWallProgressBucket(
                wall=wall,
                completed=completion_wall_counter[wall.pk],
                total=int(getattr(wall, "total_climbs", 0)),
            )
            for wall in catalogue_walls
        ),
        key=lambda bucket: (-bucket.completed, bucket.label.casefold()),
    )

    return {
        "ascents": ascents,
        "ascent_sort": ascent_sort,
        "selected_discipline": selected_discipline,
        "disciplines": ClimbingRoute.Discipline.choices,
        "catalogue_scope": catalogue_scope,
        "ascent_count": len(all_ascents),
        "catalogue_ascent_count": len(completion_ascents),
        "total_climb_count": total_climb_count,
        "climb_completion_percentage": percentage(
            len(completion_ascents),
            total_climb_count,
        ),
        "highest_grade": format_grade_index(highest_grade_order),
        "highest_route_grade": highest_route_grade,
        "highest_boulder_grade": highest_boulder_grade,
        "profile_period": profile_period,
        "profile_period_ascent_count": len(period_ascents),
        "profile_period_highest_grade": format_grade_index(_highest_grade_index(period_ascents)),
        "discipline_counts": discipline_counts,
        "catalogue_discipline_counts": completion_discipline_counts,
        "total_route_count": total_route_count,
        "route_completion_percentage": percentage(
            completion_discipline_counts[ClimbingRoute.Discipline.ROUTE],
            total_route_count,
        ),
        "total_boulder_count": total_boulder_count,
        "boulder_completion_percentage": percentage(
            completion_discipline_counts[ClimbingRoute.Discipline.BOULDER],
            total_boulder_count,
        ),
        "grade_distribution": grade_distribution,
        "maximum_grade_count": max(
            (bucket.total for bucket in grade_distribution),
            default=0,
        ),
        "project_count": sum(project_counts.values()),
        "wall_distribution": wall_distribution,
        "monthly_summary": monthly_summary,
        "profile_monthly_summary": profile_monthly_summary,
        "profile_monthly_ascents": profile_monthly_ascents,
        "profile_grade_trend": profile_grade_trend,
        "profile_route_grade_segments": profile_route_grade_segments,
        "profile_boulder_grade_segments": profile_boulder_grade_segments,
        "profile_grade_trend_axis": profile_grade_trend_axis,
        "profile_grade_trend_width": profile_grade_trend_width,
        "profile_grade_trend_right": profile_grade_trend_right,
        "profile_grade_trend_has_data": any(
            point.route_y is not None or point.boulder_y is not None
            for point in profile_grade_trend
        ),
        "maximum_profile_monthly_ascent_count": max(
            (bucket.count for bucket in profile_monthly_ascents),
            default=0,
        ),
        "monthly_summary_as_of": statistics_today,
    }
