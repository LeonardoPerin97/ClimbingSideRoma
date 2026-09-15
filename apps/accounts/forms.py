from typing import Any

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.core.forms import StyledFormMixin

from .models import User


class RegistrationForm(StyledFormMixin, UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "email", "preferred_language")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.apply_control_classes()
        self.fields["email"].required = True
        self.fields["email"].help_text = _("We will send a verification link to this address.")

    def clean_username(self) -> str:
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError(_("An account with this username already exists."))
        return username

    def clean_email(self) -> str:
        email = User.objects.normalize_email(self.cleaned_data["email"]).casefold()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError(_("An account with this email already exists."))
        return email

    def save(self, commit: bool = True) -> User:
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_active = True
        user.email_verified_at = None
        if commit:
            user.save()
        return user


class ProfileUpdateForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "profile_image",
            "preferred_language",
        )
        widgets = {
            "profile_image": forms.FileInput(
                attrs={"accept": "image/jpeg,image/png,image/webp"},
            ),
        }
        help_texts = {
            "profile_image": _("JPEG, PNG or WebP. Maximum 4 MB."),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.apply_control_classes()

    def _get_validation_exclusions(self) -> set[str]:
        exclude = super()._get_validation_exclusions()  # type: ignore[misc]
        if self.is_bound and "profile_image" not in self.files:
            exclude.add("profile_image")
        return exclude

    def clean_username(self) -> str:
        username = self.cleaned_data["username"].strip()
        duplicate = User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise ValidationError(_("An account with this username already exists."))
        return username


class ProfileImageUploadForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("profile_image",)
        widgets = {
            "profile_image": forms.FileInput(
                attrs={"accept": "image/jpeg,image/png,image/webp"},
            ),
        }
        help_texts = {
            "profile_image": _("JPEG, PNG or WebP. Maximum 4 MB."),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.apply_control_classes()
        self.fields["profile_image"].required = True
        self.fields["profile_image"].error_messages["required"] = _(
            "Select an image before continuing."
        )

    def clean_profile_image(self) -> Any:
        if "profile_image" not in self.files:
            raise ValidationError(_("Select an image before continuing."))
        return self.cleaned_data["profile_image"]


class VerificationResendForm(StyledFormMixin, forms.Form):
    email = forms.EmailField(label=_("Email"))

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.apply_control_classes()

    def clean_email(self) -> str:
        return User.objects.normalize_email(self.cleaned_data["email"]).casefold()
