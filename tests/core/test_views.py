from collections.abc import Callable
from unittest.mock import patch

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.climbs.models import Ascent, ClimbingRoute, Wall


@pytest.mark.django_db
def test_home_page_is_available(client: Client) -> None:
    response = client.get(reverse("core:home"))

    assert response.status_code == 200

    content = response.content.decode()

    assert "Climbing Side Roma" in content
    assert "/static/images/climbingside-logo.jpg" in content
    assert "brand-mark" not in content
    assert "🇮🇹" in content
    assert "🇬🇧" in content
    assert "Pensata per la palestra di arrampicata" not in content


@pytest.mark.django_db
def test_home_page_summarises_public_gym_activity(
    client: Client,
    user_factory: Callable[..., User],
    wall_factory: Callable[..., Wall],
    route_factory: Callable[..., ClimbingRoute],
    ascent_factory: Callable[..., Ascent],
) -> None:
    wall = wall_factory(name="North Wall")

    most_climbed = route_factory(
        name="Popular line",
        wall=wall,
    )
    other_route = route_factory(
        name="Quiet line",
        wall=wall,
    )

    first_user = user_factory(
        username="alice",
        email="alice-private@example.com",
    )
    second_user = user_factory(
        username="bob",
        email="bob-private@example.com",
    )

    ascent_factory(
        user=first_user,
        climbing_route=most_climbed,
    )
    ascent_factory(
        user=second_user,
        climbing_route=most_climbed,
    )
    ascent_factory(
        user=first_user,
        climbing_route=other_route,
    )

    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    assert response.context["active_route_count"] == 2
    assert response.context["active_wall_count"] == 1
    assert response.context["active_user_count"] == 2
    assert response.context["ascent_count"] == 3
    assert next(iter(response.context["popular_routes"])) == most_climbed
    assert (
        next(iter(response.context["recent_ascents"])).climbing_route
        == other_route
    )

    content = response.content.decode()

    assert "Popular line" in content
    assert "alice-private@example.com" not in content
    assert content.count('<th scope="col">') == 3
    assert 'class="activity-climber"' in content
    assert 'class="activity-climb"' in content
    assert "rating-stars" not in content


@pytest.mark.django_db
def test_health_check_reports_database_availability(
    client: Client,
) -> None:
    response = client.get(reverse("core:health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_health_check_hides_database_error_details(
    client: Client,
) -> None:
    with patch(
        "apps.core.health.connection.cursor",
        side_effect=RuntimeError("private detail"),
    ):
        response = client.get(reverse("core:health"))

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert "private detail" not in response.content.decode()


def test_supported_languages_are_italian_and_english() -> None:
    assert settings.LANGUAGES == [
        ("it", "Italiano"),
        ("en", "English"),
    ]


@pytest.mark.django_db
def test_language_can_be_changed_with_django_endpoint(
    client: Client,
) -> None:
    response = client.post(
        reverse("set_language"),
        {
            "language": "en",
            "next": "/",
        },
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/"
    assert (
        response.cookies[settings.LANGUAGE_COOKIE_NAME].value
        == "en"
    )

    home_response = client.get(reverse("core:home"))

    assert "Climbing Side Roma" in home_response.content.decode()
    