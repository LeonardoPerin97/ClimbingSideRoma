from collections.abc import Callable
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone
from django.utils.translation import override

from apps.accounts.models import User
from apps.climbs.grades import encode_perceived_grade
from apps.climbs.models import Ascent, ClimbingRoute


@pytest.mark.django_db
def test_only_one_ascent_is_allowed_per_user_and_route(
    ascent_factory: Callable[..., Ascent],
) -> None:
    ascent = ascent_factory()

    with pytest.raises(IntegrityError), transaction.atomic():
        Ascent.objects.create(
            user=ascent.user,
            climbing_route=ascent.climbing_route,
            rating=5,
            proposed_grade=encode_perceived_grade("6a", 4),
        )


@pytest.mark.django_db
def test_different_users_can_record_the_same_route(
    user_factory: Callable[..., User],
    ascent_factory: Callable[..., Ascent],
) -> None:
    first_ascent = ascent_factory()
    second_ascent = ascent_factory(
        user=user_factory(username="second-climber", email="second@example.com"),
        climbing_route=first_ascent.climbing_route,
    )

    assert first_ascent.climbing_route.ascents.count() == 2
    assert second_ascent.user != first_ascent.user


@pytest.mark.django_db
def test_future_ascent_date_is_rejected(
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    ascent = Ascent(
        user=user_factory(),
        climbing_route=route_factory(),
        date=timezone.localdate() + timedelta(days=1),
        rating=4,
        proposed_grade=encode_perceived_grade("6a", 0),
    )

    with pytest.raises(ValidationError) as error:
        ascent.full_clean()

    assert "date" in error.value.message_dict


@pytest.mark.django_db
def test_rating_range_is_enforced_by_database(
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Ascent.objects.create(
            user=user_factory(),
            climbing_route=route_factory(),
            rating=6,
            proposed_grade=encode_perceived_grade("6a", 0),
        )


@pytest.mark.django_db
def test_attempt_count_is_required_only_for_number_option(
    ascent_factory: Callable[..., Ascent],
) -> None:
    counted = ascent_factory(
        attempt_type=Ascent.AttemptType.COUNT,
        attempt_count=3,
    )
    flash = Ascent(
        user=counted.user,
        climbing_route=counted.climbing_route,
        rating=4,
        proposed_grade=counted.proposed_grade,
        attempt_type=Ascent.AttemptType.FLASH,
        attempt_count=8,
    )

    flash.clean()

    with override("en"):
        assert counted.display_attempts == "3 attempts"
    assert flash.attempt_count is None


@pytest.mark.django_db
def test_inconsistent_attempt_data_is_rejected_by_database(
    user_factory: Callable[..., User],
    route_factory: Callable[..., ClimbingRoute],
) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        Ascent.objects.create(
            user=user_factory(),
            climbing_route=route_factory(),
            rating=4,
            proposed_grade=encode_perceived_grade("6a", 0),
            attempt_type=Ascent.AttemptType.COUNT,
            attempt_count=None,
        )


@pytest.mark.django_db
def test_ascent_displays_decimal_perceived_grade(
    ascent_factory: Callable[..., Ascent],
) -> None:
    ascent = ascent_factory(proposed_grade=encode_perceived_grade("6b+", 7))

    assert ascent.display_proposed_grade == "6b+.7"


@pytest.mark.django_db
def test_ascent_protects_user_and_route_from_accidental_deletion(
    ascent_factory: Callable[..., Ascent],
) -> None:
    ascent = ascent_factory()

    with pytest.raises(ProtectedError):
        ascent.user.delete()
    with pytest.raises(ProtectedError):
        ascent.climbing_route.delete()
