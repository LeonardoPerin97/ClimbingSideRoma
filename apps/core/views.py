from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.i18n import set_language as django_set_language

from apps.accounts.models import User
from apps.accounts.roles import Role, role_for
from apps.climbs.models import Ascent, ClimbingRoute, RouteImage, Wall
from apps.climbs.statistics import collective_statistics_context

from .models import AuditLogEntry


def home(request: HttpRequest) -> HttpResponse:
    active_routes = ClimbingRoute.objects.filter(is_archived=False)

    recent_ascents = Ascent.objects.select_related(
        "user",
        "climbing_route",
        "climbing_route__wall",
    ).order_by("-created_at")[:10]

    popular_routes = (
        active_routes.select_related("wall")
        .annotate(
            ascent_count=Count("ascents"),
        )
        .order_by("-ascent_count", Lower("name"))[:5]
    )

    hero_route_image = (
        RouteImage.objects.filter(climbing_route__is_archived=False)
        .select_related("climbing_route")
        .order_by("-updated_at")
        .first()
    )

    return render(
        request,
        "core/home.html",
        {
            "recent_ascents": recent_ascents,
            "popular_routes": popular_routes,
            "hero_route_image": hero_route_image,
            "active_route_count": active_routes.count(),
            "active_wall_count": Wall.objects.filter(is_archived=False).count(),
            "active_user_count": User.objects.filter(is_active=True).count(),
            "ascent_count": Ascent.objects.count(),
        },
    )


def statistics_dashboard(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "core/statistics_dashboard.html",
        collective_statistics_context(today=timezone.localdate()),
    )


@login_required
def management_dashboard(request: HttpRequest) -> HttpResponse:
    user = request.user

    if not isinstance(user, User) or role_for(user) is not Role.ADMIN:
        raise PermissionDenied

    users = User.objects.filter(is_active=True)

    role_counts = {
        Role.ADMIN: users.filter(
            Q(is_superuser=True) | Q(groups__name=Role.ADMIN)
        )
        .distinct()
        .count(),
        Role.ROUTE_SETTER: users.filter(
            groups__name=Role.ROUTE_SETTER
        )
        .distinct()
        .count(),
        Role.USER: users.filter(
            groups__name=Role.USER
        )
        .distinct()
        .count(),
    }

    route_status_counts = {
        row["is_archived"]: row["count"]
        for row in ClimbingRoute.objects.values("is_archived").annotate(
            count=Count("id")
        )
    }

    wall_status_counts = {
        row["is_archived"]: row["count"]
        for row in Wall.objects.values("is_archived").annotate(
            count=Count("id")
        )
    }

    context = {
        "active_user_count": users.count(),
        "admin_count": role_counts[Role.ADMIN],
        "route_setter_count": role_counts[Role.ROUTE_SETTER],
        "standard_user_count": role_counts[Role.USER],
        "active_wall_count": wall_status_counts.get(False, 0),
        "archived_wall_count": wall_status_counts.get(True, 0),
        "active_route_count": route_status_counts.get(False, 0),
        "archived_route_count": route_status_counts.get(True, 0),
        "ascent_count": Ascent.objects.count(),
        "image_count": RouteImage.objects.count(),
        "recent_audit_entries": AuditLogEntry.objects.select_related(
            "actor"
        )[:20],
    }

    return render(
        request,
        "core/management_dashboard.html",
        context,
    )


def set_language_preference(request: HttpRequest) -> HttpResponse:
    response = django_set_language(request)
    language = request.POST.get("language")
    supported_languages = {
        code for code, _name in settings.LANGUAGES
    }

    if request.user.is_authenticated and language in supported_languages:
        User.objects.filter(pk=request.user.pk).update(
            preferred_language=language
        )
        request.user.preferred_language = language

    return response
    