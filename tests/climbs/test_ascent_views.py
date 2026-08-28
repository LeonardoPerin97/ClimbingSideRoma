from collections.abc import Callable
from datetime import date, timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.climbs.grades import encode_perceived_grade
from apps.climbs.models import Ascent, ClimbingRoute


def ascent_form_data(climbing_route: ClimbingRoute, **overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "climbing_route": climbing_route.pk,
        "date": timezone.localdate().isoformat(),
        "rating": 4,
        "proposed_grade_base": "6a",
        "proposed_grade_decimal": 4,
        "attempt_type": Ascent.AttemptType.UNKNOWN,
        "attempt_count": "",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_standard_user_can_record_ascent(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    user = user_factory()
    climbing_route = route_factory()
    client.force_login(user)

    response = client.post(
        reverse("climbs:ascent_create"),
        ascent_form_data(
            climbing_route,
            rating=5,
            attempt_type=Ascent.AttemptType.FLASH,
        ),
    )
    ascent = Ascent.objects.get(user=user, climbing_route=climbing_route)

    assert response.status_code == 302
    assert response.headers["Location"] == reverse("climbs:route_detail", args=[climbing_route.pk])
    assert ascent.rating == 5
    assert ascent.display_proposed_grade == "6a.4"
    assert ascent.attempt_type == Ascent.AttemptType.FLASH


@pytest.mark.django_db
def test_existing_ascent_redirects_to_edit_form(
    client: Client,
    ascent_factory: Callable[..., Ascent],
) -> None:
    ascent = ascent_factory()
    client.force_login(ascent.user)

    response = client.get(
        reverse("climbs:ascent_create"),
        {"route": ascent.climbing_route_id},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == reverse("climbs:ascent_edit", args=[ascent.pk])


@pytest.mark.django_db
def test_create_form_defaults_to_today_three_stars_and_official_grade_decimal_five(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    user = user_factory()
    climbing_route = route_factory(official_grade="6b+")
    client.force_login(user)

    response = client.get(
        reverse("climbs:ascent_create"),
        {"route": climbing_route.pk},
    )
    form = response.context["form"]

    assert response.status_code == 200
    assert form.initial["climbing_route"] == climbing_route
    assert form.initial["date"] == timezone.localdate()
    assert form.initial["rating"] == 3
    assert form.initial["proposed_grade_base"] == "6b+"
    assert form.initial["proposed_grade_decimal"] == 5


@pytest.mark.django_db
def test_project_create_form_requires_user_to_choose_a_perceived_grade(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    user = user_factory()
    project = route_factory(is_project=True, official_grade="")
    client.force_login(user)

    response = client.get(reverse("climbs:ascent_create"), {"route": project.pk})
    form = response.context["form"]

    assert "proposed_grade_base" not in form.initial
    assert form.fields["proposed_grade_base"].choices[0][0] == ""


@pytest.mark.django_db
def test_edit_form_uses_all_values_from_existing_ascent(
    client: Client,
    ascent_factory: Callable[..., Ascent],
) -> None:
    ascent = ascent_factory(
        date=date(2026, 2, 9),
        rating=2,
        proposed_grade=encode_perceived_grade("6b+", 7),
        attempt_type=Ascent.AttemptType.COUNT,
        attempt_count=4,
    )
    client.force_login(ascent.user)

    response = client.get(reverse("climbs:ascent_edit", args=[ascent.pk]))
    form = response.context["form"]

    assert response.status_code == 200
    assert form.initial["climbing_route"] == ascent.climbing_route_id
    assert form.initial["date"] == date(2026, 2, 9)
    assert form.initial["rating"] == 2
    assert form.initial["proposed_grade_base"] == "6b+"
    assert form.initial["proposed_grade_decimal"] == 7
    assert form.initial["attempt_type"] == Ascent.AttemptType.COUNT
    assert form.initial["attempt_count"] == 4


@pytest.mark.django_db
def test_number_of_attempts_requires_positive_count(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    user = user_factory()
    climbing_route = route_factory()
    client.force_login(user)

    response = client.post(
        reverse("climbs:ascent_create"),
        ascent_form_data(
            climbing_route,
            attempt_type=Ascent.AttemptType.COUNT,
            attempt_count="",
        ),
    )

    assert response.status_code == 200
    assert "attempt_count" in response.context["form"].errors
    assert not Ascent.objects.filter(user=user, climbing_route=climbing_route).exists()


@pytest.mark.django_db
def test_future_date_is_rejected_by_form(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    user = user_factory()
    climbing_route = route_factory()
    client.force_login(user)

    response = client.post(
        reverse("climbs:ascent_create"),
        ascent_form_data(
            climbing_route,
            date=(timezone.localdate() + timedelta(days=1)).isoformat(),
        ),
    )

    assert response.status_code == 200
    assert "date" in response.context["form"].errors


@pytest.mark.django_db
def test_owner_can_edit_and_delete_ascent(
    client: Client,
    ascent_factory: Callable[..., Ascent],
) -> None:
    ascent = ascent_factory()
    client.force_login(ascent.user)

    edit_response = client.post(
        reverse("climbs:ascent_edit", args=[ascent.pk]),
        ascent_form_data(
            ascent.climbing_route,
            rating=2,
            proposed_grade_base="6b",
            proposed_grade_decimal=1,
            attempt_type=Ascent.AttemptType.COUNT,
            attempt_count=5,
        ),
    )
    ascent.refresh_from_db()

    assert edit_response.status_code == 302
    assert ascent.rating == 2
    assert ascent.display_proposed_grade == "6b.1"
    assert ascent.attempt_count == 5

    delete_response = client.post(reverse("climbs:ascent_delete", args=[ascent.pk]))

    assert delete_response.status_code == 302
    assert not Ascent.objects.filter(pk=ascent.pk).exists()


@pytest.mark.django_db
def test_other_user_cannot_edit_or_delete_ascent(
    client: Client,
    user_factory: Callable[..., User],
    ascent_factory: Callable[..., Ascent],
) -> None:
    ascent = ascent_factory()
    client.force_login(user_factory(username="intruder", email="intruder@example.com"))

    assert client.get(reverse("climbs:ascent_edit", args=[ascent.pk])).status_code == 404
    assert client.post(reverse("climbs:ascent_delete", args=[ascent.pk])).status_code == 404
    assert Ascent.objects.filter(pk=ascent.pk).exists()


@pytest.mark.django_db
def test_ascent_can_be_recorded_for_archived_route(
    client: Client,
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    user = user_factory()
    climbing_route = route_factory(is_archived=True)
    client.force_login(user)

    response = client.post(
        reverse("climbs:ascent_create"),
        ascent_form_data(climbing_route),
    )

    assert response.status_code == 302
    assert Ascent.objects.filter(user=user, climbing_route=climbing_route).exists()


@pytest.mark.django_db
def test_ascent_delete_is_csrf_protected(
    ascent_factory: Callable[..., Ascent],
) -> None:
    ascent = ascent_factory()
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(ascent.user)

    response = csrf_client.post(reverse("climbs:ascent_delete", args=[ascent.pk]))

    assert response.status_code == 403
    assert Ascent.objects.filter(pk=ascent.pk).exists()
