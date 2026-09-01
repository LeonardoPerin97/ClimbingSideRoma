from collections.abc import Callable

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.roles import Role, assign_role
from apps.climbs.models import Ascent, ClimbingRoute, Wall


@pytest.mark.django_db
def test_wall_list_counts_only_active_routes(
    client: Client,
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    wall = wall_factory(name="Main Wall")
    route_factory(name="Active Route", wall=wall)
    route_factory(
        name="Archived Boulder",
        wall=wall,
        discipline=ClimbingRoute.Discipline.BOULDER,
        is_archived=True,
    )

    response = client.get(reverse("climbs:wall_list"))

    listed_wall = response.context["page"].object_list[0]
    assert response.status_code == 200
    assert listed_wall.route_count == 1
    assert listed_wall.route_discipline_count == 1
    assert listed_wall.boulder_count == 0
    content = response.content.decode()
    assert 'class="wall-stat wall-stat-climbs"' in content
    assert 'class="wall-stat wall-stat-ascents"' in content


@pytest.mark.django_db
def test_route_list_hides_archived_routes_by_default(
    client: Client,
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    route_factory(name="Visible Route")
    route_factory(name="Hidden Route", is_archived=True)

    response = client.get(reverse("climbs:route_list"))
    names = {item.name for item in response.context["page"].object_list}
    content = response.content.decode()

    assert names == {"Visible Route"}
    assert ">Tipo</label>" in content
    assert ">Tutti i tipi</option>" in content
    assert "Disciplina" not in content


@pytest.mark.django_db
def test_route_list_combines_search_and_catalogue_filters(
    client: Client,
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    selected_wall = wall_factory(name="Selected Wall")
    other_wall = wall_factory(name="Other Wall")
    expected = route_factory(
        name="Blue Comet",
        wall=selected_wall,
        discipline=ClimbingRoute.Discipline.BOULDER,
        official_grade="6b",
    )
    route_factory(
        name="Blue Route",
        wall=selected_wall,
        discipline=ClimbingRoute.Discipline.ROUTE,
        official_grade="6b",
    )
    route_factory(
        name="Blue Boulder Elsewhere",
        wall=other_wall,
        discipline=ClimbingRoute.Discipline.BOULDER,
        official_grade="6b",
    )

    response = client.get(
        reverse("climbs:route_list"),
        {
            "q": "blue",
            "wall": selected_wall.pk,
            "discipline": ClimbingRoute.Discipline.BOULDER,
            "grade": "6b",
        },
    )

    assert list(response.context["page"].object_list) == [expected]


@pytest.mark.django_db
def test_route_list_shows_continuous_type_split_histogram(
    client: Client,
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    route_factory(name="Route 5a", official_grade="5a")
    route_factory(
        name="Boulder 5a",
        official_grade="5a",
        discipline=ClimbingRoute.Discipline.BOULDER,
    )
    route_factory(name="Route 6a", official_grade="6a")
    route_factory(
        name="Boulder project",
        official_grade="",
        is_project=True,
        discipline=ClimbingRoute.Discipline.BOULDER,
    )

    response = client.get(reverse("climbs:route_list"), HTTP_ACCEPT_LANGUAGE="en")
    distribution = response.context["grade_distribution"]

    assert [bucket.label for bucket in distribution] == [
        "5a",
        "5a+",
        "5b",
        "5b+",
        "5c",
        "5c+",
        "6a",
        "Project",
    ]
    assert (distribution[0].total, distribution[0].routes, distribution[0].boulders) == (
        2,
        1,
        1,
    )
    assert (distribution[-1].total, distribution[-1].routes, distribution[-1].boulders) == (
        1,
        0,
        1,
    )
    assert response.context["maximum_grade_count"] == 2
    content = response.content.decode()
    assert 'class="histogram-stacked-bar' in content
    assert 'data-histogram-filter="all"' in content
    assert 'data-histogram-filter="route"' in content
    assert 'data-histogram-filter="boulder"' in content
    assert 'data-route-count="1"' in content
    assert 'data-boulder-count="1"' in content
    assert "Total climbs by grade" in content
    assert "Routes" in content and "Boulders" in content


@pytest.mark.django_db
def test_route_list_highlights_only_current_user_completed_routes(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
) -> None:
    user = user_factory(username="catalogue-climber")
    completed = route_factory(name="Completed catalogue route")
    untouched = route_factory(name="Untouched catalogue route")
    ascent_factory(user=user, climbing_route=completed)
    client.force_login(user)

    response = client.get(reverse("climbs:route_list"), {"sort": "name"})
    routes = list(response.context["page"].object_list)

    assert routes[0] == completed
    assert routes[0].completed_by_user is True
    assert routes[1] == untouched
    assert routes[1].completed_by_user is False
    assert response.content.decode().count("is-completed") == 1


@pytest.mark.django_db
def test_project_and_archived_status_filters(
    client: Client,
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    expected = route_factory(
        name="Old Project",
        is_project=True,
        official_grade="",
        is_archived=True,
    )
    route_factory(name="Current Project", is_project=True, official_grade="")
    route_factory(name="Old Graded Route", is_archived=True)

    response = client.get(
        reverse("climbs:route_list"),
        {"grade": "project", "status": "archived"},
    )

    assert list(response.context["page"].object_list) == [expected]


@pytest.mark.django_db
def test_routes_are_sorted_by_french_grade_with_projects_last(
    client: Client,
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    route_factory(name="Hard", official_grade="7a")
    route_factory(name="Easy", official_grade="4a")
    route_factory(name="Middle", official_grade="6a+")
    route_factory(name="Project", is_project=True, official_grade="")

    ascending = client.get(reverse("climbs:route_list"), {"sort": "grade"})
    descending = client.get(reverse("climbs:route_list"), {"sort": "grade_desc"})

    assert [item.name for item in ascending.context["page"].object_list] == [
        "Easy",
        "Middle",
        "Hard",
        "Project",
    ]
    assert [item.name for item in descending.context["page"].object_list] == [
        "Hard",
        "Middle",
        "Easy",
        "Project",
    ]


@pytest.mark.django_db
def test_wall_detail_exposes_disciplines_and_grade_distribution(
    client: Client,
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    wall = wall_factory(name="Statistics Wall")
    route_factory(name="First 5a", wall=wall, official_grade="5a")
    route_factory(
        name="Second 6a",
        wall=wall,
        official_grade="6a",
        discipline=ClimbingRoute.Discipline.BOULDER,
    )
    route_factory(name="Open Line", wall=wall, is_project=True, official_grade="")

    response = client.get(reverse("climbs:wall_detail", args=[wall.pk]))

    assert response.context["discipline_counts"] == {"route": 2, "boulder": 1}
    assert [(bucket.label, bucket.count) for bucket in response.context["grade_distribution"]] == [
        ("5a", 1),
        ("5a+", 0),
        ("5b", 0),
        ("5b+", 0),
        ("5c", 0),
        ("5c+", 0),
        ("6a", 1),
        ("Project", 1),
    ]
    assert response.context["maximum_grade_count"] == 1
    assert response.context["project_count"] == 1
    content = response.content.decode()
    assert "data-discipline-histogram" in content
    assert 'data-histogram-filter="all"' in content
    assert 'data-histogram-filter="route"' in content
    assert 'data-histogram-filter="boulder"' in content
    assert 'class="histogram-stacked-bar is-zero"' in content
    assert "Vie per grado" in content


@pytest.mark.django_db
def test_wall_histogram_counts_both_types_projects_and_only_its_own_climbs(
    client: Client,
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
) -> None:
    wall = wall_factory()
    repeated_route = route_factory(wall=wall, official_grade="5a")
    route_factory(wall=wall, official_grade="5a")
    route_factory(wall=wall, official_grade="5a", discipline=ClimbingRoute.Discipline.BOULDER)
    route_factory(wall=wall, official_grade="6a", discipline=ClimbingRoute.Discipline.BOULDER)
    route_factory(wall=wall, is_project=True, official_grade="")
    route_factory(
        wall=wall, is_project=True, official_grade="", discipline=ClimbingRoute.Discipline.BOULDER
    )
    route_factory(official_grade="9c")
    route_factory(is_project=True, official_grade="")
    for _ in range(3):
        ascent_factory(climbing_route=repeated_route)

    response = client.get(reverse("climbs:wall_detail", args=[wall.pk]))
    distribution = response.context["grade_distribution"]

    assert response.status_code == 200
    assert [
        (bucket.label, bucket.total, bucket.routes, bucket.boulders) for bucket in distribution
    ] == [
        ("5a", 3, 2, 1),
        ("5a+", 0, 0, 0),
        ("5b", 0, 0, 0),
        ("5b+", 0, 0, 0),
        ("5c", 0, 0, 0),
        ("5c+", 0, 0, 0),
        ("6a", 1, 0, 1),
        ("Project", 2, 1, 1),
    ]
    assert response.context["maximum_grade_count"] == 3
    assert response.context["project_count"] == 2
    assert (
        sum(bucket.total for bucket in distribution) == response.context["total_route_count"] == 6
    )
    assert response.context["total_ascent_count"] == 3
    content = response.content.decode()
    assert 'data-route-count="2"' in content
    assert 'data-boulder-count="1"' in content


@pytest.mark.django_db
@pytest.mark.parametrize("status", ["", "all", "invalid"])
def test_wall_histogram_respects_the_archived_routes_option(
    client: Client,
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
    status: str,
) -> None:
    wall = wall_factory()
    route_factory(wall=wall, official_grade="5a")
    route_factory(
        wall=wall,
        official_grade="5c",
        discipline=ClimbingRoute.Discipline.BOULDER,
        is_archived=True,
    )
    route_factory(wall=wall, is_project=True, official_grade="", is_archived=True)
    route_factory(
        wall=wall,
        is_project=True,
        official_grade="",
        discipline=ClimbingRoute.Discipline.BOULDER,
        is_archived=True,
    )
    route_factory(official_grade="9c", is_archived=True)

    response = client.get(reverse("climbs:wall_detail", args=[wall.pk]), {"status": status})
    distribution = response.context["grade_distribution"]

    assert response.status_code == 200
    if status == "all":
        assert [bucket.label for bucket in distribution] == [
            "5a",
            "5a+",
            "5b",
            "5b+",
            "5c",
            "Project",
        ]
        assert (distribution[-2].routes, distribution[-2].boulders) == (0, 1)
        assert (distribution[-1].routes, distribution[-1].boulders) == (1, 1)
        assert response.context["project_count"] == 2
        assert response.context["maximum_grade_count"] == 2
        assert response.context["total_route_count"] == 4
    else:
        assert [(bucket.label, bucket.total) for bucket in distribution] == [("5a", 1)]
        assert response.context["project_count"] == 0
        assert response.context["maximum_grade_count"] == 1
        assert response.context["total_route_count"] == 1


@pytest.mark.django_db
@pytest.mark.parametrize("only_projects", [False, True])
def test_wall_histogram_handles_empty_walls_and_project_only_walls(
    client: Client,
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
    only_projects: bool,
) -> None:
    wall = wall_factory()
    if only_projects:
        route_factory(
            wall=wall,
            is_project=True,
            official_grade="",
            discipline=ClimbingRoute.Discipline.BOULDER,
        )

    response = client.get(reverse("climbs:wall_detail", args=[wall.pk]), HTTP_ACCEPT_LANGUAGE="en")
    distribution = response.context["grade_distribution"]
    content = response.content.decode()

    assert response.status_code == 200
    if only_projects:
        assert [(bucket.label, bucket.routes, bucket.boulders) for bucket in distribution] == [
            ("Project", 0, 1)
        ]
        assert response.context["maximum_grade_count"] == 1
        assert 'data-histogram-filter="route"' in content
        assert 'data-histogram-filter="boulder"' in content
    else:
        assert distribution == []
        assert response.context["maximum_grade_count"] == 0
        assert "No routes are available on this wall." in content
        assert "data-discipline-histogram" not in content


@pytest.mark.django_db
def test_wall_detail_filters_discipline_without_changing_wall_summary(
    client: Client,
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    wall = wall_factory(name="Mixed Wall")
    route_factory(name="Beta Route", wall=wall, official_grade="5a")
    boulder = route_factory(
        name="Alpha Boulder",
        wall=wall,
        official_grade="7a",
        discipline=ClimbingRoute.Discipline.BOULDER,
    )

    response = client.get(
        reverse("climbs:wall_detail", args=[wall.pk]),
        {"discipline": ClimbingRoute.Discipline.BOULDER},
    )

    assert response.context["climbing_routes"] == [boulder]
    assert response.context["total_route_count"] == 2
    assert response.context["discipline_counts"] == {"route": 1, "boulder": 1}
    assert response.context["selected_discipline"] == ClimbingRoute.Discipline.BOULDER
    unfiltered = client.get(reverse("climbs:wall_detail", args=[wall.pk]))
    assert response.context["grade_distribution"] == unfiltered.context["grade_distribution"]
    assert response.context["grade_distribution"][0].routes == 1
    assert response.context["grade_distribution"][-1].boulders == 1


@pytest.mark.django_db
def test_wall_detail_sorts_by_name_and_grade_in_both_directions(
    client: Client,
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    wall = wall_factory(name="Sorting Wall")
    route_factory(name="Beta Easy", wall=wall, official_grade="5a")
    route_factory(name="Alpha Hard", wall=wall, official_grade="7a")

    by_name = client.get(reverse("climbs:wall_detail", args=[wall.pk]), {"sort": "name"})
    by_name_desc = client.get(
        reverse("climbs:wall_detail", args=[wall.pk]),
        {"sort": "name_desc"},
    )
    by_grade = client.get(reverse("climbs:wall_detail", args=[wall.pk]), {"sort": "grade"})
    by_grade_desc = client.get(
        reverse("climbs:wall_detail", args=[wall.pk]),
        {"sort": "grade_desc"},
    )

    assert [route.name for route in by_name.context["climbing_routes"]] == [
        "Alpha Hard",
        "Beta Easy",
    ]
    assert [route.name for route in by_grade.context["climbing_routes"]] == [
        "Beta Easy",
        "Alpha Hard",
    ]
    assert [route.name for route in by_name_desc.context["climbing_routes"]] == [
        "Beta Easy",
        "Alpha Hard",
    ]
    assert [route.name for route in by_grade_desc.context["climbing_routes"]] == [
        "Alpha Hard",
        "Beta Easy",
    ]


@pytest.mark.django_db
def test_route_detail_lists_setters_without_exposing_email(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    first = user_factory(username="anna-setter", email="anna-private@example.com")
    second = user_factory(username="marco-setter", email="marco-private@example.com")
    assign_role(first, Role.ROUTE_SETTER)
    assign_role(second, Role.ROUTE_SETTER)
    climbing_route = route_factory(route_setters=[first, second])

    response = client.get(reverse("climbs:route_detail", args=[climbing_route.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "anna-setter" in content
    assert "marco-setter" in content
    assert "anna-private@example.com" not in content
    assert "marco-private@example.com" not in content


@pytest.mark.django_db
def test_route_list_is_paginated_at_twenty_items(
    client: Client,
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    wall = wall_factory(name="Busy Wall")
    for index in range(21):
        route_factory(name=f"Route {index:02}", wall=wall)

    response = client.get(reverse("climbs:route_list"))

    assert len(response.context["page"].object_list) == 20
    assert response.context["page"].paginator.num_pages == 2
