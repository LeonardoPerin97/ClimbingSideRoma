from collections.abc import Callable

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError

from apps.accounts.models import User
from apps.accounts.roles import Role, assign_role
from apps.climbs.grades import encode_perceived_grade, format_perceived_grade
from apps.climbs.models import ClimbingRoute, Wall


@pytest.mark.django_db
def test_wall_names_are_case_insensitively_unique(
    wall_factory: Callable[..., Wall],
) -> None:
    wall_factory(name="North Wall")

    with pytest.raises(IntegrityError), transaction.atomic():
        Wall.objects.create(name="north wall")


@pytest.mark.django_db
def test_route_names_are_case_insensitively_unique(
    route_factory: Callable[..., ClimbingRoute],
    wall_factory: Callable[..., Wall],
) -> None:
    route_factory(name="Blue Moon")

    with pytest.raises(IntegrityError), transaction.atomic():
        ClimbingRoute.objects.create(
            name="blue moon",
            wall=wall_factory(name="South Wall"),
            discipline=ClimbingRoute.Discipline.BOULDER,
            official_grade="6b",
        )


@pytest.mark.django_db
def test_project_clears_official_grade(wall_factory: Callable[..., Wall]) -> None:
    climbing_route = ClimbingRoute(
        name="Open Project",
        wall=wall_factory(),
        discipline=ClimbingRoute.Discipline.ROUTE,
        official_grade="7a",
        is_project=True,
    )

    climbing_route.full_clean()

    assert climbing_route.official_grade == ""
    assert climbing_route.display_grade == "Project"


@pytest.mark.django_db
def test_non_project_requires_an_official_grade(
    wall_factory: Callable[..., Wall],
) -> None:
    climbing_route = ClimbingRoute(
        name="Missing Grade",
        wall=wall_factory(),
        discipline=ClimbingRoute.Discipline.ROUTE,
        official_grade="",
        is_project=False,
    )

    with pytest.raises(ValidationError) as error:
        climbing_route.full_clean()

    assert "official_grade" in error.value.message_dict


@pytest.mark.django_db
def test_database_rejects_inconsistent_project_grade(
    wall_factory: Callable[..., Wall],
) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        ClimbingRoute.objects.create(
            name="Invalid Project",
            wall=wall_factory(),
            discipline=ClimbingRoute.Discipline.BOULDER,
            official_grade="6c",
            is_project=True,
        )


@pytest.mark.django_db
def test_a_wall_can_contain_both_disciplines(
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    wall = wall_factory(name="Mixed Wall")
    route_factory(name="Long Line", wall=wall, discipline=ClimbingRoute.Discipline.ROUTE)
    route_factory(name="Short Line", wall=wall, discipline=ClimbingRoute.Discipline.BOULDER)

    assert set(wall.climbing_routes.values_list("discipline", flat=True)) == {
        ClimbingRoute.Discipline.ROUTE,
        ClimbingRoute.Discipline.BOULDER,
    }


@pytest.mark.django_db
def test_route_setters_are_optional_and_multiple(
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    first = user_factory(username="setter-one", email="setter-one@example.com")
    second = user_factory(username="setter-two", email="setter-two@example.com")
    assign_role(first, Role.ROUTE_SETTER)
    assign_role(second, Role.ROUTE_SETTER)
    climbing_route = route_factory(name="Collaborative Route")

    assert not climbing_route.route_setters.exists()

    climbing_route.route_setters.set([first, second])

    assert set(climbing_route.route_setters.all()) == {first, second}


@pytest.mark.django_db
def test_wall_with_routes_is_protected_from_deletion(
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    climbing_route = route_factory()

    with pytest.raises(ProtectedError):
        climbing_route.wall.delete()


def test_perceived_french_grade_round_trip() -> None:
    encoded = encode_perceived_grade("6a", 4)

    assert format_perceived_grade(encoded) == "6a.4"


@pytest.mark.parametrize(
    ("grade", "decimal"),
    [("3a", 0), ("6a", -1), ("6a", 10)],
)
def test_invalid_perceived_grade_is_rejected(grade: str, decimal: int) -> None:
    with pytest.raises(ValueError):
        encode_perceived_grade(grade, decimal)


@pytest.mark.parametrize("encoded", [-1, 999])
def test_invalid_encoded_grade_is_rejected(encoded: int) -> None:
    with pytest.raises(ValueError):
        format_perceived_grade(encoded)
