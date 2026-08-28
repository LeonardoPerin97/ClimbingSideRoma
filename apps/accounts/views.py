import logging
from typing import cast

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from apps.climbs.statistics import user_climbing_context

from .forms import ProfileUpdateForm, RegistrationForm, VerificationResendForm
from .models import User
from .rate_limit import clear_login_failures, record_login_failure, seconds_until_unlock
from .roles import Role, assign_role, role_label_for
from .services import send_verification_email
from .tokens import email_verification_token

logger = logging.getLogger(__name__)


@require_http_methods(["GET", "POST"])
def register(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("accounts:profile")

    form = RegistrationForm(
        request.POST or None, initial={"preferred_language": request.LANGUAGE_CODE}
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            assign_role(user, Role.USER)
        try:
            send_verification_email(user=user, request=request)
        except Exception:
            logger.exception("Verification email delivery failed for user_id=%s", user.pk)
        return redirect("accounts:verification_sent")
    return render(request, "accounts/register.html", {"form": form})


def verification_sent(request: HttpRequest) -> HttpResponse:
    return render(request, "accounts/verification_sent.html")


@require_http_methods(["GET", "POST"])
def resend_verification(request: HttpRequest) -> HttpResponse:
    form = VerificationResendForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = User.objects.filter(
            email__iexact=form.cleaned_data["email"],
            email_verified_at__isnull=True,
            is_active=False,
        ).first()
        if user:
            try:
                send_verification_email(user=user, request=request)
            except Exception:
                logger.exception("Verification email resend failed for user_id=%s", user.pk)
        messages.success(
            request,
            _("If an unverified account exists, a new verification email has been sent."),
        )
        return redirect("accounts:verification_sent")
    return render(request, "accounts/resend_verification.html", {"form": form})


def verify_email(request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is None or user.email_verified_at is not None:
        return render(request, "accounts/verification_invalid.html", status=400)

    if not email_verification_token.check_token(user, token):
        return render(request, "accounts/verification_invalid.html", status=400)

    user.is_active = True
    user.email_verified_at = timezone.now()
    user.save(update_fields=["is_active", "email_verified_at"])
    return render(request, "accounts/verification_complete.html")


class ClimbingSideLoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def post(self, request: HttpRequest, *args: object, **kwargs: object) -> HttpResponse:
        username = request.POST.get("username", "")[:150]
        retry_after = seconds_until_unlock(request, username)
        if retry_after:
            return self._lockout_response(request, retry_after)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form: AuthenticationForm) -> HttpResponse:
        username = self.request.POST.get("username", "")[:150]
        retry_after = record_login_failure(self.request, username)
        if retry_after:
            return self._lockout_response(self.request, retry_after)
        return super().form_invalid(form)

    def form_valid(self, form: AuthenticationForm) -> HttpResponse:
        username = self.request.POST.get("username", "")[:150]
        clear_login_failures(self.request, username)
        return super().form_valid(form)

    def _lockout_response(self, request: HttpRequest, retry_after: int) -> HttpResponse:
        response = render(
            request,
            "accounts/lockout.html",
            {"retry_after": retry_after},
            status=429,
        )
        response.headers["Retry-After"] = str(retry_after)
        return response


class ClimbingSideLogoutView(auth_views.LogoutView):
    next_page = "core:home"


@login_required
def profile(request: HttpRequest) -> HttpResponse:
    profile_user = cast(User, request.user)
    context = user_climbing_context(
        profile_user,
        ascent_sort=request.GET.get("sort", "date_desc"),
        ascent_discipline=request.GET.get("discipline", ""),
    )
    context.update(
        {
            "profile_user": profile_user,
            "role": role_label_for(profile_user),
            "can_manage_ascents": True,
        }
    )
    return render(
        request,
        "accounts/profile.html",
        context,
    )


def public_profile(request: HttpRequest, username: str) -> HttpResponse:
    profile_user = get_object_or_404(User, username__iexact=username, is_active=True)
    can_manage_ascents = (
        request.user.is_authenticated
        and request.user.pk == profile_user.pk
        and request.user.has_perm("climbs.change_ascent")
    )
    context = user_climbing_context(
        profile_user,
        ascent_sort=request.GET.get("sort", "date_desc"),
        ascent_discipline=request.GET.get("discipline", ""),
    )
    context.update(
        {
            "profile_user": profile_user,
            "role": role_label_for(profile_user),
            "can_manage_ascents": can_manage_ascents,
        }
    )
    return render(
        request,
        "accounts/public_profile.html",
        context,
    )


@login_required
@require_http_methods(["GET", "POST"])
def edit_profile(request: HttpRequest) -> HttpResponse:
    form = ProfileUpdateForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Profile updated successfully."))
        return redirect("accounts:profile")
    return render(request, "accounts/profile_edit.html", {"form": form})


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:password_change_done")


class PasswordChangeDoneView(auth_views.PasswordChangeDoneView):
    template_name = "accounts/password_change_done.html"


class PasswordResetView(auth_views.PasswordResetView):
    template_name = "accounts/password_reset_form.html"
    email_template_name = "accounts/email/password_reset_email.txt"
    html_email_template_name = "accounts/email/password_reset_email.html"
    subject_template_name = "accounts/email/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"
