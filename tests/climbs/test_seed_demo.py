from io import StringIO

import pytest
from django.core.management import call_command

from apps.accounts.models import User
from apps.accounts.roles import Role, role_for
from apps.climbs.models import Ascent, ClimbingRoute, Wall


@pytest.mark.django_db
def test_seed_demo_is_idempotent_and_uses_unusable_passwords() -> None:
    first_output = StringIO()
    second_output = StringIO()

    call_command("seed_demo", stdout=first_output)
    first_counts = (
        User.objects.filter(username__startswith="demo-").count(),
        Wall.objects.filter(name__startswith="[DEMO]").count(),
        ClimbingRoute.objects.filter(name__startswith="[DEMO]").count(),
        Ascent.objects.filter(user__username__startswith="demo-").count(),
    )
    call_command("seed_demo", stdout=second_output)

    assert first_counts == (3, 3, 8, 8)
    assert (
        User.objects.filter(username__startswith="demo-").count(),
        Wall.objects.filter(name__startswith="[DEMO]").count(),
        ClimbingRoute.objects.filter(name__startswith="[DEMO]").count(),
        Ascent.objects.filter(user__username__startswith="demo-").count(),
    ) == first_counts
    assert all(not user.has_usable_password() for user in User.objects.all())
    assert role_for(User.objects.get(username="demo-setter")) is Role.ROUTE_SETTER
    assert "password" not in first_output.getvalue().casefold()
    assert "example.invalid" not in first_output.getvalue()
    assert "created=22" in first_output.getvalue()
    assert "reused=22" in second_output.getvalue()


@pytest.mark.django_db
def test_seed_demo_dry_run_leaves_database_unchanged() -> None:
    output = StringIO()

    call_command("seed_demo", "--dry-run", stdout=output)

    assert User.objects.count() == 0
    assert Wall.objects.count() == 0
    assert ClimbingRoute.objects.count() == 0
    assert Ascent.objects.count() == 0
    assert "dry-run" in output.getvalue()


@pytest.mark.django_db
def test_seed_demo_does_not_overwrite_a_colliding_real_user() -> None:
    real_user = User.objects.create_user(
        username="demo-alex",
        email="real-climber@example.com",
        password="Strong-Test-Password-42!",
        is_active=True,
    )
    output = StringIO()

    call_command("seed_demo", stdout=output)

    real_user.refresh_from_db()
    assert real_user.email == "real-climber@example.com"
    assert real_user.has_usable_password()
    assert not Ascent.objects.filter(user=real_user).exists()
    assert "skipped=5" in output.getvalue()
