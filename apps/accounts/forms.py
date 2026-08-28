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
        user.is_active = False
        user.email_verified_at = None
        if commit:
            user.save()
        return user


class ProfileUpdateForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "preferred_language")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.apply_control_classes()

    def clean_username(self) -> str:
        username = self.cleaned_data["username"].strip()
        duplicate = User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise ValidationError(_("An account with this username already exists."))
        return username


class VerificationResendForm(StyledFormMixin, forms.Form):
    email = forms.EmailField(label=_("Email"))

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.apply_control_classes()

    def clean_email(self) -> str:
        return User.objects.normalize_email(self.cleaned_data["email"]).casefold()
