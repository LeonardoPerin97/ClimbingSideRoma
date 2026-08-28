from typing import cast

from django.contrib import admin
from django.db.models import Count, QuerySet
from django.http import HttpRequest

from apps.accounts.models import User
from apps.core.audit import record_audit_event
from apps.core.models import AuditLogEntry

from .models import Ascent, ClimbingRoute, RouteImage, Wall


@admin.register(Wall)
class WallAdmin(admin.ModelAdmin):
    list_display = ("name", "route_count", "is_archived")
    list_filter = ("is_archived",)
    search_fields = ("name",)
    ordering = ("name",)

    def get_queryset(self, request: HttpRequest) -> QuerySet[Wall]:
        return super().get_queryset(request).annotate(_route_count=Count("climbing_routes"))

    @admin.display(description="Routes", ordering="_route_count")
    def route_count(self, wall: Wall) -> int:
        return int(getattr(wall, "_route_count", 0))

    def has_delete_permission(self, request: HttpRequest, obj: Wall | None = None) -> bool:
        del request, obj
        return False

    def save_model(
        self,
        request: HttpRequest,
        obj: Wall,
        form: object,
        change: bool,
    ) -> None:
        super().save_model(request, obj, form, change)
        record_audit_event(
            actor=cast(User, request.user),
            action=AuditLogEntry.Action.UPDATE if change else AuditLogEntry.Action.CREATE,
            entity_type="wall",
            entity_id=obj.pk,
        )


@admin.register(ClimbingRoute)
class ClimbingRouteAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "wall",
        "discipline",
        "grade_display",
        "is_archived",
    )
    list_filter = ("discipline", "is_project", "is_archived", "wall")
    search_fields = ("name", "wall__name", "route_setters__username")
    autocomplete_fields = ("wall", "route_setters")
    ordering = ("name",)

    @admin.display(description="Grade", ordering="official_grade")
    def grade_display(self, climbing_route: ClimbingRoute) -> str:
        return climbing_route.display_grade

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: ClimbingRoute | None = None,
    ) -> bool:
        del request, obj
        return False

    def save_model(
        self,
        request: HttpRequest,
        obj: ClimbingRoute,
        form: object,
        change: bool,
    ) -> None:
        super().save_model(request, obj, form, change)
        record_audit_event(
            actor=cast(User, request.user),
            action=AuditLogEntry.Action.UPDATE if change else AuditLogEntry.Action.CREATE,
            entity_type="route",
            entity_id=obj.pk,
        )


@admin.register(Ascent)
class AscentAdmin(admin.ModelAdmin):
    list_display = (
        "climbing_route",
        "user",
        "date",
        "rating",
        "proposed_grade_display",
        "attempts_display",
    )
    list_filter = ("rating", "attempt_type", "climbing_route__discipline", "date")
    search_fields = ("climbing_route__name", "user__username", "climbing_route__wall__name")
    autocomplete_fields = ("user", "climbing_route")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-date", "-created_at")

    @admin.display(description="Proposed grade", ordering="proposed_grade")
    def proposed_grade_display(self, ascent: Ascent) -> str:
        return ascent.display_proposed_grade

    @admin.display(description="Attempts", ordering="attempt_type")
    def attempts_display(self, ascent: Ascent) -> str:
        return ascent.display_attempts

    def save_model(
        self,
        request: HttpRequest,
        obj: Ascent,
        form: object,
        change: bool,
    ) -> None:
        super().save_model(request, obj, form, change)
        record_audit_event(
            actor=cast(User, request.user),
            action=AuditLogEntry.Action.UPDATE if change else AuditLogEntry.Action.CREATE,
            entity_type="ascent",
            entity_id=obj.pk,
        )

    def delete_model(self, request: HttpRequest, obj: Ascent) -> None:
        ascent_id = obj.pk
        super().delete_model(request, obj)
        record_audit_event(
            actor=cast(User, request.user),
            action=AuditLogEntry.Action.DELETE,
            entity_type="ascent",
            entity_id=ascent_id,
        )

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet[Ascent]) -> None:
        ascent_ids = list(queryset.values_list("pk", flat=True))
        super().delete_queryset(request, queryset)
        for ascent_id in ascent_ids:
            record_audit_event(
                actor=cast(User, request.user),
                action=AuditLogEntry.Action.DELETE,
                entity_type="ascent",
                entity_id=ascent_id,
            )


@admin.register(RouteImage)
class RouteImageAdmin(admin.ModelAdmin):
    list_display = ("climbing_route", "uploaded_by", "has_annotations", "updated_at")
    search_fields = ("climbing_route__name", "climbing_route__wall__name")
    list_select_related = ("climbing_route", "uploaded_by")
    readonly_fields = (
        "climbing_route",
        "image",
        "annotations",
        "uploaded_by",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        del request
        return False

    def has_change_permission(
        self,
        request: HttpRequest,
        obj: RouteImage | None = None,
    ) -> bool:
        del request, obj
        return False

    def has_delete_permission(
        self,
        request: HttpRequest,
        obj: RouteImage | None = None,
    ) -> bool:
        del request, obj
        return False
