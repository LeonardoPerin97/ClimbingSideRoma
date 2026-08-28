from collections.abc import Callable
from datetime import date

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.climbs.grades import encode_perceived_grade
from apps.climbs.models import Ascent, ClimbingRoute, Wall


@pytest.mark.django_db
def test_route_detail_calculates_public_ascent_statistics(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
) -> None:
    climbing_route = route_factory(name="Community Route")
    first = user_factory(username="first-user", email="first-private@example.com")
    second = user_factory(username="second-user", email="second-private@example.com")
    ascent_factory(
        user=first,
        climbing_route=climbing_route,
        rating=3,
        proposed_grade=encode_perceived_grade("6a", 2),
    )
    ascent_factory(
        user=second,
        climbing_route=climbing_route,
        rating=5,
        proposed_grade=encode_perceived_grade("6a", 6),
    )

    response = client.get(reverse("climbs:route_detail", args=[climbing_route.pk]))
    content = response.content.decode()

    assert response.context["climbing_route"].ascent_count == 2
    assert response.context["climbing_route"].average_rating == 4
    assert response.context["average_proposed_grade"] == "6a.4"
    assert [
        (bucket.label, bucket.count) for bucket in response.context["proposed_distribution"]
    ] == [
        ("6a.2", 1),
        ("6a.3", 0),
        ("6a.4", 0),
        ("6a.5", 0),
        ("6a.6", 1),
    ]
    assert response.context["maximum_proposed_grade_count"] == 1
    assert "first-user" in content and "second-user" in content
    assert "first-private@example.com" not in content


@pytest.mark.django_db
def test_route_list_sorts_by_ascent_count_and_rating(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
) -> None:
    popular = route_factory(name="Popular")
    best_rated = route_factory(name="Best Rated")
    empty = route_factory(name="No Ratings")
    ascent_factory(user=user_factory(), climbing_route=popular, rating=3)
    ascent_factory(user=user_factory(), climbing_route=popular, rating=4)
    ascent_factory(user=user_factory(), climbing_route=best_rated, rating=5)

    by_count = client.get(reverse("climbs:route_list"), {"sort": "ascents"})
    by_rating = client.get(reverse("climbs:route_list"), {"sort": "rating"})

    assert [item.name for item in by_count.context["page"].object_list][:3] == [
        "Popular",
        "Best Rated",
        "No Ratings",
    ]
    assert [item.name for item in by_rating.context["page"].object_list][:3] == [
        "Best Rated",
        "Popular",
        "No Ratings",
    ]
    assert empty.pk is not None


@pytest.mark.django_db
def test_wall_list_and_detail_include_ascent_totals(
    client: Client,
    user_factory: Callable[..., User],
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
) -> None:
    wall = wall_factory(name="Ascent Wall")
    active_route = route_factory(name="Active", wall=wall)
    archived_route = route_factory(name="Archived", wall=wall, is_archived=True)
    ascent_factory(user=user_factory(), climbing_route=active_route)
    ascent_factory(user=user_factory(), climbing_route=archived_route)

    list_response = client.get(reverse("climbs:wall_list"))
    listed_wall = list_response.context["page"].object_list[0]
    detail_response = client.get(reverse("climbs:wall_detail", args=[wall.pk]))

    assert listed_wall.ascent_count == 2
    assert detail_response.context["total_ascent_count"] == 2


@pytest.mark.django_db
def test_wall_detail_sorts_routes_by_ascents_and_rating_in_both_directions(
    client: Client,
    user_factory: Callable[..., User],
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
) -> None:
    wall = wall_factory(name="Ranked Wall")
    popular = route_factory(name="Popular", wall=wall)
    best_rated = route_factory(name="Best Rated", wall=wall)
    empty = route_factory(name="No Ascents", wall=wall)
    ascent_factory(user=user_factory(), climbing_route=popular, rating=3)
    ascent_factory(user=user_factory(), climbing_route=popular, rating=4)
    ascent_factory(user=user_factory(), climbing_route=best_rated, rating=5)

    by_ascents = client.get(
        reverse("climbs:wall_detail", args=[wall.pk]),
        {"sort": "ascents"},
    )
    by_rating = client.get(
        reverse("climbs:wall_detail", args=[wall.pk]),
        {"sort": "rating"},
    )
    by_ascents_ascending = client.get(
        reverse("climbs:wall_detail", args=[wall.pk]),
        {"sort": "ascents_asc"},
    )
    by_rating_ascending = client.get(
        reverse("climbs:wall_detail", args=[wall.pk]),
        {"sort": "rating_asc"},
    )

    assert [route.name for route in by_ascents.context["climbing_routes"]] == [
        "Popular",
        "Best Rated",
        "No Ascents",
    ]
    assert [route.name for route in by_rating.context["climbing_routes"]] == [
        "Best Rated",
        "Popular",
        "No Ascents",
    ]
    assert [route.name for route in by_ascents_ascending.context["climbing_routes"]] == [
        "No Ascents",
        "Best Rated",
        "Popular",
    ]
    assert [route.name for route in by_rating_ascending.context["climbing_routes"]] == [
        "Popular",
        "Best Rated",
        "No Ascents",
    ]
    assert empty.pk is not None


@pytest.mark.django_db
def test_wall_detail_shows_average_proposed_grade_and_completed_route(
    client: Client,
    user_factory: Callable[..., User],
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
) -> None:
    wall = wall_factory(name="Personal Wall")
    completed = route_factory(name="Completed Line", wall=wall)
    untouched = route_factory(name="Untouched Line", wall=wall)
    current_user = user_factory(username="current-climber")
    other_user = user_factory(username="other-climber")
    ascent_factory(
        user=current_user,
        climbing_route=completed,
        proposed_grade=encode_perceived_grade("6a", 2),
    )
    ascent_factory(
        user=other_user,
        climbing_route=completed,
        proposed_grade=encode_perceived_grade("6a", 6),
    )
    client.force_login(current_user)

    response = client.get(
        reverse("climbs:wall_detail", args=[wall.pk]),
        {"sort": "name"},
    )

    routes = response.context["climbing_routes"]
    assert routes[0].name == "Completed Line"
    assert routes[0].average_proposed_grade_display == "6a.4"
    assert routes[0].completed_by_user is True
    assert routes[1] == untouched
    assert routes[1].average_proposed_grade_display == "—"
    assert routes[1].completed_by_user is False
    content = response.content.decode()
    assert 'class="catalog-card is-completed"' in content
    assert "badge-completed" not in content
    assert "6a.4" in content


@pytest.mark.django_db
def test_route_detail_places_current_user_ascent_data_next_to_edit_action(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
) -> None:
    user = user_factory(username="detail-climber")
    climbing_route = route_factory(name="Personal Detail")
    ascent = ascent_factory(
        user=user,
        climbing_route=climbing_route,
        date=date(2026, 3, 14),
        rating=4,
        proposed_grade=encode_perceived_grade("6a", 3),
        attempt_type=Ascent.AttemptType.FLASH,
    )
    client.force_login(user)

    response = client.get(reverse("climbs:route_detail", args=[climbing_route.pk]))
    content = response.content.decode()

    assert response.context["user_ascent"] == ascent
    assert 'class="my-ascent-summary"' in content
    assert "6a.3" in content
    assert "★ 4/5" in content
    assert "Flash" in content


@pytest.mark.django_db
def test_user_list_can_sort_by_completed_routes_and_maximum_official_grade(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
) -> None:
    frequent = user_factory(username="frequent", email="frequent@example.com")
    strongest = user_factory(username="strongest", email="strongest@example.com")
    route_5a = route_factory(name="Five A", official_grade="5a")
    route_6a = route_factory(name="Six A", official_grade="6a")
    route_7a = route_factory(name="Seven A", official_grade="7a")
    ascent_factory(user=frequent, climbing_route=route_5a)
    ascent_factory(user=frequent, climbing_route=route_6a)
    ascent_factory(user=strongest, climbing_route=route_7a)

    by_count = client.get(reverse("climbs:user_list"), {"sort": "ascents"})
    by_grade = client.get(reverse("climbs:user_list"), {"sort": "grade"})

    assert by_count.context["page"].object_list[0].username == "frequent"
    assert by_grade.context["page"].object_list[0].username == "strongest"


@pytest.mark.django_db
def test_profile_context_contains_histogram_distributions_without_progression(
    client: Client,
    user_factory: Callable[..., User],
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
) -> None:
    user = user_factory(username="progressive", email="progressive-private@example.com")
    wall = wall_factory(name="Progress Wall")
    easy = route_factory(name="Easy Step", wall=wall, official_grade="5a")
    harder = route_factory(
        name="Harder Step",
        wall=wall,
        official_grade="6a",
        discipline=ClimbingRoute.Discipline.BOULDER,
    )
    ascent_factory(user=user, climbing_route=easy, date=date(2026, 1, 10))
    ascent_factory(user=user, climbing_route=harder, date=date(2026, 2, 10))

    response = client.get(reverse("accounts:public_profile", args=[user.username]))
    content = response.content.decode()

    assert response.context["ascent_count"] == 2
    assert response.context["highest_grade"] == "6a"
    assert response.context["discipline_counts"] == {"route": 1, "boulder": 1}
    assert response.context["maximum_grade_count"] == 1
    assert [bucket.label for bucket in response.context["grade_distribution"]] == [
        "5a",
        "5a+",
        "5b",
        "5b+",
        "5c",
        "5c+",
        "6a",
    ]
    assert "progression" not in response.context
    assert response.context["wall_distribution"][0].label == "Progress Wall"
    assert 'class="grade-histogram"' in content
    assert "progression-list" not in content
    assert "Easy Step" in content and "Harder Step" in content
    assert "progressive-private@example.com" not in content


@pytest.mark.django_db
def test_profile_ascents_can_be_sorted_by_date_and_official_grade(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
) -> None:
    user = user_factory(username="sorted-profile")
    easy = route_factory(name="Easy Recent", official_grade="5a")
    hard = route_factory(name="Hard Old", official_grade="7a")
    hard.discipline = ClimbingRoute.Discipline.BOULDER
    hard.save(update_fields=["discipline"])
    ascent_factory(user=user, climbing_route=easy, date=date(2026, 3, 10))
    ascent_factory(user=user, climbing_route=hard, date=date(2026, 1, 10))
    url = reverse("accounts:public_profile", args=[user.username])

    newest = client.get(url, {"sort": "date_desc"})
    oldest = client.get(url, {"sort": "date_asc"})
    easiest = client.get(url, {"sort": "grade"})
    hardest = client.get(url, {"sort": "grade_desc"})

    assert [ascent.climbing_route.name for ascent in newest.context["ascents"]] == [
        "Easy Recent",
        "Hard Old",
    ]
    assert [ascent.climbing_route.name for ascent in oldest.context["ascents"]] == [
        "Hard Old",
        "Easy Recent",
    ]
    assert [ascent.climbing_route.name for ascent in easiest.context["ascents"]] == [
        "Easy Recent",
        "Hard Old",
    ]
    assert [ascent.climbing_route.name for ascent in hardest.context["ascents"]] == [
        "Hard Old",
        "Easy Recent",
    ]

    boulders = client.get(
        url,
        {"discipline": ClimbingRoute.Discipline.BOULDER, "sort": "date_desc"},
    )
    assert boulders.context["selected_discipline"] == ClimbingRoute.Discipline.BOULDER
    assert [ascent.climbing_route.name for ascent in boulders.context["ascents"]] == [
        "Hard Old"
    ]
    assert boulders.context["ascent_count"] == 2
