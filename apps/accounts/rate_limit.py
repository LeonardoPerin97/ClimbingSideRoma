from datetime import timedelta
from math import ceil

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import LoginAttempt


def _identifier_hash(request: HttpRequest, username: str) -> str:
    ip_address = request.META.get("REMOTE_ADDR", "unknown")
    value = f"{username.strip().casefold()}|{ip_address}"
    return salted_hmac("accounts.login-rate-limit", value).hexdigest()


def seconds_until_unlock(request: HttpRequest, username: str) -> int:
    attempt = LoginAttempt.objects.filter(
        identifier_hash=_identifier_hash(request, username)
    ).first()
    if attempt is None or attempt.locked_until is None:
        return 0

    remaining = ceil((attempt.locked_until - timezone.now()).total_seconds())
    if remaining <= 0:
        attempt.delete()
        return 0
    return remaining


@transaction.atomic
def record_login_failure(request: HttpRequest, username: str) -> int:
    now = timezone.now()
    window = timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
    identifier_hash = _identifier_hash(request, username)
    LoginAttempt.objects.filter(updated_at__lt=now - window).delete()
    attempt, created = LoginAttempt.objects.select_for_update().get_or_create(
        identifier_hash=identifier_hash,
        defaults={"failures": 1, "first_failed_at": now},
    )

    if not created and attempt.updated_at < now - window:
        attempt.failures = 1
        attempt.first_failed_at = now
        attempt.locked_until = None
    elif not created:
        attempt.failures += 1

    if attempt.failures >= settings.LOGIN_FAILURE_LIMIT:
        attempt.locked_until = now + window
    attempt.save()
    return seconds_until_unlock(request, username)


def clear_login_failures(request: HttpRequest, username: str) -> None:
    LoginAttempt.objects.filter(identifier_hash=_identifier_hash(request, username)).delete()
