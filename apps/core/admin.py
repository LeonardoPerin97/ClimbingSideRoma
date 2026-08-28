from django.contrib import admin
from django.http import HttpRequest

from .models import AuditLogEntry


@admin.register(AuditLogEntry)
class AuditLogEntryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "entity_type", "entity_id", "actor_id")
    list_filter = ("action", "entity_type", "created_at")
    search_fields = ("entity_id",)
    list_select_related = ("actor",)
    ordering = ("-created_at", "-pk")
    readonly_fields = (
        "actor",
        "action",
        "entity_type",
        "entity_id",
        "metadata",
        "created_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        del request
        return False

    def has_change_permission(
        self,
        request: HttpRequest,
        obj: AuditLogEntry | None = None,
    ) -> bool:
        del request, obj
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: AuditLogEntry | None = None,
    ) -> bool:
        del request, obj
        return False
