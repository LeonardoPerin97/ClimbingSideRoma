from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any

from django.db.models import Count, Max, Q
from django.db.models.functions import Lower, TruncMonth

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


@dataclass(frozen=True)
class MonthlyAscentBucket:
    month: date
    count: int


def continuous_french_grade_distribution(
    counts: Mapping[str, int],
    *,
    project_count: int = 0,
) -> list[StatisticBucket]:
    """Return every French grade between the easiest and hardest recorded grade."""
    populated_indexes = [
        FRENCH_GRADE_INDEX[grade]
        for grade, count in counts.items()
        if count and grade in FRENCH_GRADE_INDEX
    ]
    buckets: list[StatisticBucket] = []
    if populated_indexes:
        buckets.extend(
            StatisticBucket(FRENCH_GRADE_BASES[index], counts.get(FRENCH_GRADE_BASES[index], 0))
            for index in range(min(populated_indexes), max(populated_indexes) + 1)
        )
    if project_count:
        buckets.append(StatisticBucket("Project", project_count))
    return buckets


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


def collective_statistics_context(*, today: date) -> dict[str, Any]:
    active_routes = ClimbingRoute.objects.filter(is_archived=False)
    discipline_rows = active_routes.values("discipline").annotate(count=Count("id"))
    discipline_counts = {row["discipline"]: row["count"] for row in discipline_rows}

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
            ),
            route_count=Count(
                "climbing_routes",
                filter=Q(
                    climbing_routes__is_archived=False,
                    climbing_routes__discipline=ClimbingRoute.Discipline.ROUTE,
                ),
            ),
            boulder_count=Count(
                "climbing_routes",
                filter=Q(
                    climbing_routes__is_archived=False,
                    climbing_routes__discipline=ClimbingRoute.Discipline.BOULDER,
                ),
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
        for month in (_month_start(first_month, offset) for offset in range(12))
    ]

    highest_grade_order = active_routes.filter(is_project=False).aggregate(
        highest=Max(grade_order_expression())
    )["highest"]
    return {
        "active_route_count": active_routes.count(),
        "route_count": discipline_counts.get(ClimbingRoute.Discipline.ROUTE, 0),
        "boulder_count": discipline_counts.get(ClimbingRoute.Discipline.BOULDER, 0),
        "active_wall_count": len(routes_by_wall),
        "active_user_count": User.objects.filter(is_active=True).count(),
        "ascent_count": Ascent.objects.count(),
        "project_count": active_routes.filter(is_project=True).count(),
        "highest_grade": format_grade_index(highest_grade_order),
        "grade_distribution": grade_distribution,
        "routes_by_wall": routes_by_wall,
        "monthly_ascents": monthly_ascents,
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
    }


def user_climbing_context(
    user: User,
    *,
    ascent_sort: str = "date_desc",
    ascent_discipline: str = "",
) -> dict[str, Any]:
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

    discipline_counts: dict[str, int] = {
        ClimbingRoute.Discipline.ROUTE: 0,
        ClimbingRoute.Discipline.BOULDER: 0,
    }
    wall_counter: Counter[str] = Counter()
    official_grade_counter: Counter[str] = Counter()
    project_count = 0
    highest_grade_order = -1

    for ascent in all_ascents:
        climbing_route = ascent.climbing_route
        discipline_counts[climbing_route.discipline] += 1
        wall_counter[climbing_route.wall.name] += 1
        if climbing_route.is_project:
            project_count += 1
            continue
        official_grade_counter[climbing_route.official_grade] += 1
        highest_grade_order = max(
            highest_grade_order,
            FRENCH_GRADE_INDEX[climbing_route.official_grade],
        )

    grade_distribution = continuous_french_grade_distribution(official_grade_counter)
    wall_distribution = [
        StatisticBucket(wall_name, count)
        for wall_name, count in sorted(
            wall_counter.items(),
            key=lambda item: (-item[1], item[0].casefold()),
        )
    ]

    return {
        "ascents": ascents,
        "ascent_sort": ascent_sort,
        "selected_discipline": selected_discipline,
        "disciplines": ClimbingRoute.Discipline.choices,
        "ascent_count": len(all_ascents),
        "highest_grade": format_grade_index(highest_grade_order),
        "discipline_counts": discipline_counts,
        "grade_distribution": grade_distribution,
        "maximum_grade_count": max(
            (bucket.count for bucket in grade_distribution),
            default=0,
        ),
        "project_count": project_count,
        "wall_distribution": wall_distribution,
    }
