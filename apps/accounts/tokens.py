from django.contrib.auth.tokens import PasswordResetTokenGenerator

from .models import User


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user: User, timestamp: int) -> str:
        verified_at = user.email_verified_at.isoformat() if user.email_verified_at else ""
        return f"{user.pk}{timestamp}{user.is_active}{verified_at}{user.email}"


email_verification_token = EmailVerificationTokenGenerator()
