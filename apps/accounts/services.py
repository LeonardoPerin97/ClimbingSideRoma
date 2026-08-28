from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import translation
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .models import User
from .tokens import email_verification_token


def send_verification_email(*, user: User, request: HttpRequest) -> None:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    verification_url = request.build_absolute_uri(
        reverse(
            "accounts:verify_email",
            kwargs={"uidb64": uid, "token": token},
        )
    )

    with translation.override(user.preferred_language):
        context = {"user": user, "verification_url": verification_url}
        subject = " ".join(
            render_to_string("accounts/email/verify_email_subject.txt", context).splitlines()
        )
        message = render_to_string("accounts/email/verify_email.txt", context)
        html_message = render_to_string("accounts/email/verify_email.html", context)

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )
