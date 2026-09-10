from collections.abc import Callable
from datetime import date

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.climbs.models import Ascent, ClimbingRoute, Wall


@pytest.mark.django_db
@override_settings(PAGINATION_PAGE_SIZE=2)
def test_catalogue_lists_use_the_shared_page_size(
    client: Client,
    user_factory: Callable[..., User],
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    walls = [wall_factory(name=f"Page Wall {index}") for index in range(3)]
    for index in range(3):
        user_factory(
            username=f"page-user-{index}",
            email=f"page-user-{index}@example.com",
        )
        route_factory(name=f"Page Route {index}", wall=walls[0])

    walls_response = client.get(reverse("climbs:wall_list"))
    routes_response = client.get(reverse("climbs:route_list"))
    users_response = client.get(reverse("climbs:user_list"))
    all_walls_response = client.get(reverse("climbs:wall_list"), {"per_page": "all"})
    all_routes_response = client.get(reverse("climbs:route_list"), {"per_page": "all"})
    all_users_response = client.get(reverse("climbs:user_list"), {"per_page": "all"})

    assert len(walls_response.context["page"]) == 2
    assert len(routes_response.context["page"]) == 2
    assert len(users_response.context["page"]) == 2
    assert walls_response.context["page"].paginator.num_pages == 2
    assert routes_response.context["page"].paginator.num_pages == 2
    assert users_response.context["page"].paginator.num_pages == 2
    for response in (all_walls_response, all_routes_response, all_users_response):
        assert len(response.context["page"]) == 3
        assert response.context["pagination_show_all"] is True
        assert response.context["page"].paginator.num_pages == 1


@pytest.mark.django_db
@override_settings(PAGINATION_PAGE_SIZE=2)
def test_wall_detail_routes_are_paginated_without_changing_totals(
    client: Client,
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    wall = wall_factory(name="Paginated Wall")
    for index in range(3):
        route_factory(name=f"Wall Route {index}", wall=wall)

    first_page = client.get(reverse("climbs:wall_detail", args=[wall.pk]))
    second_page = client.get(reverse("climbs:wall_detail", args=[wall.pk]), {"page": 2})
    all_items = client.get(
        reverse("climbs:wall_detail", args=[wall.pk]),
        {"per_page": "all"},
    )

    assert len(first_page.context["page"]) == 2
    assert len(first_page.context["climbing_routes"]) == 2
    assert len(second_page.context["page"]) == 1
    assert first_page.context["total_route_count"] == 3
    assert len(all_items.context["climbing_routes"]) == 3
    assert all_items.context["pagination_show_all"] is True


@pytest.mark.django_db
@override_settings(PAGINATION_PAGE_SIZE=2)
def test_route_detail_ascents_are_paginated_from_newest_to_oldest(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
) -> None:
    climbing_route = route_factory(name="Popular Route")
    ascents = []
    for day in range(1, 4):
        user = user_factory(
            username=f"route-page-user-{day}",
            email=f"route-page-user-{day}@example.com",
        )
        ascents.append(
            ascent_factory(
                user=user,
                climbing_route=climbing_route,
                date=date(2026, 1, day),
            )
        )

    first_page = client.get(reverse("climbs:route_detail", args=[climbing_route.pk]))
    second_page = client.get(
        reverse("climbs:route_detail", args=[climbing_route.pk]),
        {"page": 2},
    )
    all_items = client.get(
        reverse("climbs:route_detail", args=[climbing_route.pk]),
        {"per_page": "all"},
    )

    assert list(first_page.context["ascent_page"]) == [ascents[2], ascents[1]]
    assert list(second_page.context["ascent_page"]) == [ascents[0]]
    assert list(all_items.context["ascent_page"]) == [ascents[2], ascents[1], ascents[0]]
    assert all_items.context["ascent_pagination_show_all"] is True


@pytest.mark.django_db
@override_settings(PAGINATION_PAGE_SIZE=2)
def test_profile_ascents_are_paginated_without_changing_statistics(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
) -> None:
    user = user_factory(username="profile-page-user", email="profile-page-user@example.com")
    for day in range(1, 4):
        climbing_route = route_factory(name=f"Profile Route {day}")
        ascent_factory(
            user=user,
            climbing_route=climbing_route,
            date=date(2026, 1, day),
        )

    first_page = client.get(reverse("accounts:public_profile", args=[user.username]))
    second_page = client.get(
        reverse("accounts:public_profile", args=[user.username]),
        {"page": 2},
    )
    all_items = client.get(
        reverse("accounts:public_profile", args=[user.username]),
        {"per_page": "all"},
    )

    assert len(first_page.context["ascent_page"]) == 2
    assert len(second_page.context["ascent_page"]) == 1
    assert len(all_items.context["ascent_page"]) == 3
    assert all_items.context["ascent_pagination_show_all"] is True
    assert first_page.context["ascent_count"] == 3
    assert sum(bucket.total for bucket in first_page.context["grade_distribution"]) == 3
