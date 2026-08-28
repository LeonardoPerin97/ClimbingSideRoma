from typing import cast

from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.db import transaction
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from apps.core.audit import record_audit_event
from apps.core.models import AuditLogEntry

from .models import User
from .roles import ROLE_CHOICES, Role, assign_role, role_for


class AdminUserChangeForm(UserChangeForm):
    role = forms.ChoiceField(label=_("Role"), choices=ROLE_CHOICES)

    class Meta:
        model = User
        fields = "__all__"

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["role"].initial = role_for(self.instance)


class AdminUserCreationForm(UserCreationForm):
    role = forms.ChoiceField(label=_("Role"), choices=ROLE_CHOICES, initial=Role.USER)

    class Meta:
        model = User
        fields = ("username", "email", "preferred_language")


@admin.register(User)
class ClimbingSideUserAdmin(UserAdmin):
    form = AdminUserChangeForm
    add_form = AdminUserCreationForm
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            _("Personal information"),
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "email",
                    "email_verified_at",
                    "preferred_language",
                )
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "role",
                    "user_permissions",
                )
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "email",
                    "preferred_language",
                    "role",
                    "password1",
                    "password2",
                ),
            },
        ),
    )
    readonly_fields = ("last_login", "date_joined", "email_verified_at")
    list_display = (
        "username",
        "email",
        "role_display",
        "email_verified_at",
        "preferred_language",
        "is_active",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "groups", "preferred_language")
    search_fields = ("username", "email")

    @admin.display(description=_("Role"))
    def role_display(self, user: User) -> str:
        return role_for(user).value

    def save_model(
        self,
        request: HttpRequest,
        obj: User,
        form: forms.ModelForm,
        change: bool,
    ) -> None:
        old_role = role_for(obj) if change else None
        new_role = Role(form.cleaned_data["role"])
        with transaction.atomic():
            super().save_model(request, obj, form, change)
            assign_role(obj, new_role)
            if old_role is not None and old_role != new_role:
                action = AuditLogEntry.Action.ROLE_CHANGE
                metadata = {"old_role": old_role.value, "new_role": new_role.value}
            else:
                action = AuditLogEntry.Action.UPDATE if change else AuditLogEntry.Action.CREATE
                metadata = {"role": new_role.value}
            record_audit_event(
                actor=cast(User, request.user),
                action=action,
                entity_type="user",
                entity_id=obj.pk,
                metadata=metadata,
            )

    def delete_model(self, request: HttpRequest, obj: User) -> None:
        user_id = obj.pk
        actor = cast(User, request.user)
        super().delete_model(request, obj)
        record_audit_event(
            actor=None if actor.pk == user_id else actor,
            action=AuditLogEntry.Action.DELETE,
            entity_type="user",
            entity_id=user_id,
        )

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        user_ids = list(queryset.values_list("pk", flat=True))
        actor = cast(User, request.user)
        audit_actor = None if actor.pk in user_ids else actor
        super().delete_queryset(request, queryset)
        for user_id in user_ids:
            record_audit_event(
                actor=audit_actor,
                action=AuditLogEntry.Action.DELETE,
                entity_type="user",
                entity_id=user_id,
            )
