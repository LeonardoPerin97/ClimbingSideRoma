import re
from collections.abc import Callable

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
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

    response = client.get(
        reverse("climbs:wall_list"),
        HTTP_ACCEPT_LANGUAGE="it",
    )

    listed_wall = response.context["page"].object_list[0]
    assert response.status_code == 200
    assert listed_wall.route_count == 1
    assert listed_wall.route_discipline_count == 1
    assert listed_wall.boulder_count == 0
    content = response.content.decode()
    assert 'class="wall-list"' in content
    assert 'class="wall-card-stats"' in content
    assert 'class="wall-stat' not in content
    assert 'class="list-name-link"' in content
    assert "<dt>Vie</dt>" in content
    assert "<dt>Ripetizioni</dt>" in content
    assert "<dt>Vie attive</dt>" not in content
    assert "<dt>Ripetizioni registrate</dt>" not in content


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
    assert "Bellezza più alta" in content
    assert "Valutazione più alta" not in content
    assert ">Tipo</label>" in content
    assert ">Tutti i tipi</option>" in content
    assert "Disciplina" not in content
    assert content.count('class="list-name-link"') == 2
    assert 'class="data-list route-data-list route-data-list-with-wall"' in content
    desktop_header = content.split(
        'class="data-list-header route-data-row data-list-header-desktop"',
        maxsplit=1,
    )[1].split(
        'class="data-list-header route-data-row data-list-header-compact"',
        maxsplit=1,
    )[0]
    assert all(
        f">{label}</span>" in desktop_header
        for label in ("Nome", "Parete", "Tipo", "Grado", "Proposto", "Bellezza", "Ripetizioni")
    )
    assert desktop_header.index(">Bellezza</span>") < desktop_header.index(">Ripetizioni</span>")
    compact_header = content.split(
        'class="data-list-header route-data-row data-list-header-compact"',
        maxsplit=1,
    )[1].split('class="data-list-rows"', maxsplit=1)[0]
    assert ">Grado</span>" in compact_header
    assert ">Gradi</span>" not in compact_header
    assert ">Attività</span>" not in compact_header
    assert ">Ripetizioni</span>" in compact_header
    assert re.search(
        r'class="route-type-cell">.*?>\s*Via\s*</span>',
        content,
        re.DOTALL,
    )
    assert content.index('class="route-beauty"') < content.index('class="route-ascent-count"')
    assert 'class="data-cell-compact-label">Proposto</span>' not in content


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
def test_route_list_filters_by_grade_range_or_exact_grade(
    client: Client,
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    easy = route_factory(name="Easy range", official_grade="5a")
    middle = route_factory(name="Middle range", official_grade="6a")
    hard = route_factory(name="Hard range", official_grade="7a")
    project = route_factory(name="Range project", is_project=True, official_grade="")

    all_grades = client.get(reverse("climbs:route_list"), {"grade_mode": "all"})
    from_middle = client.get(
        reverse("climbs:route_list"),
        {"grade_mode": "from", "grade": "6a"},
    )
    up_to_middle = client.get(
        reverse("climbs:route_list"),
        {"grade_mode": "up_to", "grade": "6a"},
    )
    equal_middle = client.get(
        reverse("climbs:route_list"),
        {"grade_mode": "equal", "grade": "6a"},
        HTTP_ACCEPT_LANGUAGE="en",
    )

    assert list(all_grades.context["page"].object_list) == [easy, middle, hard, project]
    assert list(from_middle.context["page"].object_list) == [middle, hard]
    assert list(up_to_middle.context["page"].object_list) == [easy, middle]
    assert list(equal_middle.context["page"].object_list) == [middle]
    assert equal_middle.context["selected_grade_mode"] == "equal"
    assert equal_middle.context["selected_grade"] == "6a"
    content = equal_middle.content.decode()
    assert "data-grade-filter-mode" in content
    assert ">From</option>" in content
    assert ">Up to</option>" in content
    assert ">Equal to</option>" in content


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
    assert 'class="histogram-tooltip"' in content
    assert "data-histogram-column" in content
    assert 'class="histogram-value"' not in content
    assert "5a · Climbs:" in content
    assert "Total climbs by grade" in content
    assert "Routes" in content and "Boulders" in content
    assert content.index('class="profile-card catalogue-histogram-card"') < content.index(
        'class="filter-bar route-filters"'
    )


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
    assert routes[0].average_proposed_grade_display == "6a.0"
    assert routes[1] == untouched
    assert routes[1].completed_by_user is False
    assert routes[1].average_proposed_grade_display == "—"
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
    assert "Bellezza più alta" in content
    assert "Bellezza più bassa" in content
    assert "Valutazione più alta" not in content
    assert "Valutazione più bassa" not in content
    assert "data-discipline-histogram" in content
    assert 'data-histogram-filter="all"' in content
    assert 'data-histogram-filter="route"' in content
    assert 'data-histogram-filter="boulder"' in content
    assert 'class="histogram-stacked-bar is-zero"' in content
    assert "Vie per grado" in content
    assert 'class="data-list route-data-list route-data-list-without-wall"' in content
    route_table_start = content.index(
        'class="data-list route-data-list route-data-list-without-wall"'
    )
    route_desktop_header = content[route_table_start:].split(
        'class="data-list-header route-data-row data-list-header-compact"',
        maxsplit=1,
    )[0]
    assert ">Nome</span>" in route_desktop_header
    assert ">Parete</span>" not in route_desktop_header
    assert all(
        f">{label}</span>" in route_desktop_header
        for label in ("Tipo", "Grado", "Proposto", "Bellezza", "Ripetizioni")
    )
    assert route_desktop_header.index(">Bellezza</span>") < route_desktop_header.index(
        ">Ripetizioni</span>"
    )
    route_compact_header = (
        content[route_table_start:]
        .split(
            'class="data-list-header route-data-row data-list-header-compact"',
            maxsplit=1,
        )[1]
        .split('class="data-list-rows"', maxsplit=1)[0]
    )
    assert ">Ripetizioni</span>" in route_compact_header
    assert re.search(
        r'class="route-type-cell">.*?>\s*Via\s*</span>',
        content,
        re.DOTALL,
    )
    assert re.search(
        r'class="route-type-cell">.*?>\s*Boulder\s*</span>',
        content,
        re.DOTALL,
    )
    assert 'class="data-cell-compact-label">Proposto</span>' not in content


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
def test_route_detail_shows_free_form_setters(
    client: Client,
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    climbing_route = route_factory(route_setters="Anna Rossi, Marco Bianchi")

    response = client.get(reverse("climbs:route_detail", args=[climbing_route.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Anna Rossi, Marco Bianchi" in content
    assert f'<a class="list-name-link" href="{reverse("climbs:wall_list")}">' in content
    assert "Palestra" in content


@pytest.mark.django_db
def test_route_detail_shows_notes_only_when_present(
    client: Client,
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    with_notes = route_factory(
        name="Route with public notes",
        notes="Start on the left.\nAvoid the grey hold.",
    )
    without_notes = route_factory(name="Route without public notes")

    notes_response = client.get(reverse("climbs:route_detail", args=[with_notes.pk]))
    empty_response = client.get(reverse("climbs:route_detail", args=[without_notes.pk]))

    notes_content = notes_response.content.decode()
    empty_content = empty_response.content.decode()
    assert "Start on the left.<br>" in notes_content
    assert "Avoid the grey hold." in notes_content
    assert ">Note</dt>" in notes_content
    assert ">Note</dt>" not in empty_content


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("discipline", "expected_badge"),
    [
        (ClimbingRoute.Discipline.ROUTE, "Via"),
        (ClimbingRoute.Discipline.BOULDER, "Boulder"),
    ],
)
def test_route_detail_places_singular_type_badge_below_title(
    client: Client,
    route_factory: Callable[..., ClimbingRoute],
    discipline: str,
    expected_badge: str,
) -> None:
    climbing_route = route_factory(
        name="Badge Position",
        discipline=discipline,
    )

    response = client.get(
        reverse("climbs:route_detail", args=[climbing_route.pk]),
        HTTP_ACCEPT_LANGUAGE="it",
    )
    header = (
        response.content.decode()
        .split(
            '<header class="detail-header route-detail-header">',
            maxsplit=1,
        )[1]
        .split("</header>", maxsplit=1)[0]
    )

    assert response.status_code == 200
    assert header.index('class="route-title-row"') < header.index(
        'class="badge-row route-title-badges"'
    )
    assert re.search(
        rf'class="badge badge-discipline[^\"]*">\s*{expected_badge}\s*</span>',
        header,
    )
    if discipline == ClimbingRoute.Discipline.ROUTE:
        assert ">Vie<" not in header


@pytest.mark.django_db
def test_wall_and_route_breadcrumbs_start_from_gym(
    client: Client,
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    climbing_route = route_factory(name="Breadcrumb Route")

    wall_response = client.get(
        reverse("climbs:wall_detail", args=[climbing_route.wall_id]),
        HTTP_ACCEPT_LANGUAGE="en",
    )
    route_response = client.get(
        reverse("climbs:route_detail", args=[climbing_route.pk]),
        HTTP_ACCEPT_LANGUAGE="en",
    )
    wall_breadcrumb = (
        wall_response.content.decode()
        .split(
            '<nav class="breadcrumb"',
            maxsplit=1,
        )[1]
        .split("</nav>", maxsplit=1)[0]
    )
    route_breadcrumb = (
        route_response.content.decode()
        .split(
            '<nav class="breadcrumb"',
            maxsplit=1,
        )[1]
        .split("</nav>", maxsplit=1)[0]
    )

    assert f'href="{reverse("climbs:wall_list")}">Gym</a>' in wall_breadcrumb
    assert climbing_route.wall.name in wall_breadcrumb
    assert "All walls" not in wall_breadcrumb
    assert f'href="{reverse("climbs:wall_list")}">Gym</a>' in route_breadcrumb
    assert climbing_route.wall.name in route_breadcrumb
    assert climbing_route.name in route_breadcrumb

    route_header = (
        route_response.content.decode()
        .split('<header class="detail-header route-detail-header">', maxsplit=1)[1]
        .split("</header>", maxsplit=1)[0]
    )
    assert climbing_route.wall.name not in route_header


@pytest.mark.django_db
def test_route_list_is_paginated_at_fifty_items(
    client: Client,
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    wall = wall_factory(name="Busy Wall")
    for index in range(51):
        route_factory(name=f"Route {index:02}", wall=wall)

    response = client.get(reverse("climbs:route_list"))

    assert len(response.context["page"].object_list) == 50
    assert response.context["page"].paginator.num_pages == 2
