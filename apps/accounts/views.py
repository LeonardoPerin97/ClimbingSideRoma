import logging
from typing import Any, cast

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from apps.climbs.statistics import user_climbing_context
from apps.core.pagination import paginate

from .forms import (
    ProfileImageUploadForm,
    ProfileUpdateForm,
    RegistrationForm,
    VerificationResendForm,
)
from .media_services import delete_profile_image, save_profile_changes
from .models import User
from .rate_limit import clear_login_failures, record_login_failure, seconds_until_unlock
from .roles import Role, assign_role, role_label_for
from .services import send_verification_email
from .tokens import email_verification_token

logger = logging.getLogger(__name__)


def _add_ascent_page(context: dict[str, Any], request: HttpRequest) -> None:
    ascent_page, show_all = paginate(request, context["ascents"])
    context.update(
        {
            "ascent_page": ascent_page,
            "ascent_pagination_show_all": show_all,
            "pagination_page_size": settings.PAGINATION_PAGE_SIZE,
        }
    )


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
        if settings.BYPASS_EMAIL_VERIFICATION:
            logger.warning("Email verification bypassed for user_id=%s", user.pk)
            messages.success(
                request,
                _(
                    "Account created. You can log in now; email verification is temporarily "
                    "disabled."
                ),
            )
            return redirect("accounts:login")
        try:
            send_verification_email(user=user, request=request)
        except Exception:
            logger.exception("Verification email delivery failed for user_id=%s", user.pk)
        return redirect("accounts:verification_sent")
    return render(
        request,
        "accounts/register.html",
        {
            "form": form,
            "email_verification_bypassed": settings.BYPASS_EMAIL_VERIFICATION,
        },
    )


def verification_sent(request: HttpRequest) -> HttpResponse:
    return render(request, "accounts/verification_sent.html")


@require_http_methods(["GET", "POST"])
def resend_verification(request: HttpRequest) -> HttpResponse:
    if settings.BYPASS_EMAIL_VERIFICATION:
        messages.warning(
            request,
            _("Email verification is temporarily disabled. You can log in directly."),
        )
        return redirect("accounts:login")
    form = VerificationResendForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = User.objects.filter(
            email__iexact=form.cleaned_data["email"],
            email_verified_at__isnull=True,
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

    user.email_verified_at = timezone.now()
    user.save(update_fields=["email_verified_at"])
    return render(request, "accounts/verification_complete.html")


class ClimbingSideLoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["email_verification_bypassed"] = settings.BYPASS_EMAIL_VERIFICATION
        return context

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
    return redirect(
        "accounts:public_profile",
        username=cast(User, request.user).username,
    )


def public_profile(request: HttpRequest, username: str) -> HttpResponse:
    profile_user = get_object_or_404(User, username__iexact=username, is_active=True)
    is_own_profile = request.user.is_authenticated and request.user.pk == profile_user.pk
    profile_image_management_url = ""
    if profile_user.profile_image:
        if is_own_profile:
            profile_image_management_url = reverse("accounts:profile_image_upload")
        elif request.user.is_authenticated and request.user.has_perm("accounts.change_user"):
            profile_image_management_url = reverse(
                "accounts:profile_image_manage",
                args=[profile_user.username],
            )
    context = user_climbing_context(
        profile_user,
        ascent_sort=request.GET.get("sort", "date_desc"),
        ascent_discipline=request.GET.get("discipline", ""),
    )
    _add_ascent_page(context, request)
    context.update(
        {
            "profile_user": profile_user,
            "role": role_label_for(profile_user),
            "is_own_profile": is_own_profile,
            "profile_image_management_url": profile_image_management_url,
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
    profile_user = cast(User, request.user)
    old_image_name = profile_user.profile_image.name
    form = ProfileUpdateForm(
        request.POST or None,
        request.FILES or None,
        instance=profile_user,
    )
    if request.method == "POST" and form.is_valid():
        profile_user, image_action = save_profile_changes(
            form,
            actor=profile_user,
            old_image_name=old_image_name,
        )
        if image_action is not None:
            logger.info(
                "profile_image_action actor_id=%s action=%s profile_user_id=%s",
                profile_user.pk,
                image_action,
                profile_user.pk,
            )
        messages.success(request, _("Profile updated successfully."))
        return redirect("accounts:public_profile", username=profile_user.username)
    return render(request, "accounts/profile_edit.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def upload_profile_image(request: HttpRequest) -> HttpResponse:
    profile_user = cast(User, request.user)
    old_image_name = profile_user.profile_image.name
    form = ProfileImageUploadForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        instance=profile_user,
    )
    if request.method == "POST" and form.is_valid():
        profile_user, image_action = save_profile_changes(
            form,
            actor=profile_user,
            old_image_name=old_image_name,
        )
        logger.info(
            "profile_image_action actor_id=%s action=%s profile_user_id=%s",
            profile_user.pk,
            image_action,
            profile_user.pk,
        )
        messages.success(request, _("Profile image updated successfully."))
        return redirect("accounts:public_profile", username=profile_user.username)
    return render(
        request,
        "accounts/profile_image_form.html",
        {
            "form": form,
            "profile_user": profile_user,
            "replacing": bool(old_image_name),
            "can_upload": True,
            "can_delete": bool(old_image_name),
        },
    )


@login_required
@require_http_methods(["GET"])
def manage_profile_image(request: HttpRequest, username: str) -> HttpResponse:
    profile_user = get_object_or_404(User, username__iexact=username, is_active=True)
    actor = cast(User, request.user)
    if actor.pk == profile_user.pk:
        return redirect("accounts:profile_image_upload")
    if not actor.has_perm("accounts.change_user"):
        raise PermissionDenied
    if not profile_user.profile_image:
        messages.info(request, _("This profile has no image to delete."))
        return redirect("accounts:public_profile", username=profile_user.username)
    return render(
        request,
        "accounts/profile_image_form.html",
        {
            "form": None,
            "profile_user": profile_user,
            "replacing": True,
            "can_upload": False,
            "can_delete": True,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def delete_profile_image_view(request: HttpRequest, username: str) -> HttpResponse:
    profile_user = get_object_or_404(User, username__iexact=username)
    actor = cast(User, request.user)
    if actor.pk != profile_user.pk and not actor.has_perm("accounts.change_user"):
        raise PermissionDenied

    if request.method == "POST":
        deleted = delete_profile_image(profile_user=profile_user, actor=actor)
        if deleted:
            logger.info(
                "profile_image_action actor_id=%s action=delete profile_user_id=%s",
                actor.pk,
                profile_user.pk,
            )
            messages.success(request, _("Profile image deleted."))
        else:
            messages.info(request, _("This profile has no image to delete."))
        return redirect("accounts:public_profile", username=profile_user.username)

    return render(
        request,
        "accounts/profile_image_delete_confirm.html",
        {"profile_user": profile_user},
    )


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

    def dispatch(
        self,
        request: HttpRequest,
        *args: object,
        **kwargs: object,
    ) -> HttpResponse:
        if settings.BYPASS_EMAIL_VERIFICATION:
            messages.warning(
                request,
                _(
                    "Password recovery by email is temporarily unavailable. Contact an "
                    "administrator if you cannot log in."
                ),
            )
            return redirect("accounts:login")
        return cast(HttpResponse, super().dispatch(request, *args, **kwargs))


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "accounts/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "accounts/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "accounts/password_reset_complete.html"
