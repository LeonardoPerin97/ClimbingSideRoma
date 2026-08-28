from typing import Any, ClassVar

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import UserManager as DjangoUserManager
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class UserManager(DjangoUserManager["User"]):
    use_in_migrations = True

    def _create_user(
        self,
        username: str,
        email: str | None,
        password: str | None,
        **extra_fields: Any,
    ) -> "User":
        username = username.strip()
        email = self.normalize_email(email or "").casefold()
        if not username:
            raise ValueError("The username must be set.")
        if not email:
            raise ValueError("The email must be set.")

        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(
        self,
        username: str,
        email: str | None = None,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(
        self,
        username: str,
        email: str | None = None,
        password: str | None = None,
        **extra_fields: Any,
    ) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("email_verified_at", timezone.now())
        if extra_fields.get("is_staff") is not True:
            raise ValueError("A superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_superuser=True.")
        return self._create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    class Language(models.TextChoices):
        ITALIAN = "it", _("Italiano")
        ENGLISH = "en", _("English")

    email = models.EmailField(_("email address"), unique=True)
    preferred_language = models.CharField(
        _("preferred language"),
        max_length=2,
        choices=Language.choices,
        default=Language.ITALIAN,
    )
    email_verified_at = models.DateTimeField(
        _("email verified at"),
        null=True,
        blank=True,
        editable=False,
    )

    objects: ClassVar[UserManager] = UserManager()

    REQUIRED_FIELDS = ["email"]

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        constraints = [
            models.UniqueConstraint(Lower("username"), name="accounts_user_username_ci_uniq"),
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_uniq"),
        ]

    def __str__(self) -> str:
        return self.username

    @property
    def email_is_verified(self) -> bool:
        return self.email_verified_at is not None


class LoginAttempt(models.Model):
    identifier_hash = models.CharField(max_length=64, unique=True)
    failures = models.PositiveSmallIntegerField(default=0)
    first_failed_at = models.DateTimeField()
    locked_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("login attempt")
        verbose_name_plural = _("login attempts")

    def __str__(self) -> str:
        return f"Login attempt {self.pk}"
