import logging
from typing import Any, cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Avg, BooleanField, Count, Exists, F, Max, OuterRef, Q, QuerySet, Value
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Lower
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.models import User
from apps.core.audit import record_audit_event
from apps.core.models import AuditLogEntry

from .forms import (
    AscentForm,
    ClimbingRouteForm,
    ConfirmDeleteForm,
    RouteAnnotationForm,
    RouteImageUploadForm,
    WallForm,
)
from .grades import (
    FRENCH_GRADE_BASES,
    format_perceived_grade,
    grade_order_expression,
)
from .media_services import delete_route_image, save_route_image
from .models import Ascent, ClimbingRoute, RouteImage, Wall
from .statistics import (
    continuous_french_grade_distribution,
    continuous_perceived_grade_distribution,
)

logger = logging.getLogger(__name__)


def _authorised_user(request: HttpRequest, permission: str) -> User:
    user = cast(User, request.user)
    if not user.has_perm(permission):
        raise PermissionDenied
    return user


def _status_filter(queryset: QuerySet[Any], status: str) -> QuerySet[Any]:
    if status == "archived":
        return queryset.filter(is_archived=True)
    if status == "all":
        return queryset
    return queryset.filter(is_archived=False)


def wall_list(request: HttpRequest) -> HttpResponse:
    search = request.GET.get("q", "").strip()[:100]
    status = request.GET.get("status", "active")
    sort = request.GET.get("sort", "name")
    walls = Wall.objects.annotate(
        route_count=Count(
            "climbing_routes",
            filter=Q(climbing_routes__is_archived=False),
            distinct=True,
        ),
        route_discipline_count=Count(
            "climbing_routes",
            filter=Q(
                climbing_routes__is_archived=False,
                climbing_routes__discipline=ClimbingRoute.Discipline.ROUTE,
            ),
            distinct=True,
        ),
        boulder_count=Count(
            "climbing_routes",
            filter=Q(
                climbing_routes__is_archived=False,
                climbing_routes__discipline=ClimbingRoute.Discipline.BOULDER,
            ),
            distinct=True,
        ),
        ascent_count=Count("climbing_routes__ascents", distinct=True),
    )
    walls = _status_filter(walls, status)
    if search:
        walls = walls.filter(name__icontains=search)
    if sort == "routes":
        walls = walls.order_by("-route_count", Lower("name"))
    elif sort == "ascents":
        walls = walls.order_by("-ascent_count", Lower("name"))
    else:
        sort = "name"
        walls = walls.order_by(Lower("name"))

    page = Paginator(walls, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "climbs/wall_list.html",
        {"page": page, "search": search, "status": status, "sort": sort},
    )


def wall_detail(request: HttpRequest, pk: int) -> HttpResponse:
    wall = get_object_or_404(Wall, pk=pk)
    show_archived = request.GET.get("status") == "all"
    selected_discipline = request.GET.get("discipline", "")
    sort = request.GET.get("sort", "grade")
    catalogue_routes = wall.climbing_routes.all()
    if not show_archived:
        catalogue_routes = catalogue_routes.filter(is_archived=False)

    discipline_counts = {
        row["discipline"]: row["count"]
        for row in catalogue_routes.order_by().values("discipline").annotate(count=Count("id"))
    }
    grade_counts_raw = {
        row["official_grade"]: row["count"]
        for row in catalogue_routes.filter(is_project=False)
        .order_by()
        .values("official_grade")
        .annotate(count=Count("id"))
    }
    project_count = catalogue_routes.filter(is_project=True).count()
    grade_distribution = continuous_french_grade_distribution(
        grade_counts_raw,
        project_count=project_count,
    )

    climbing_routes = catalogue_routes.select_related("wall").annotate(
        grade_order=grade_order_expression(),
        ascent_count=Count("ascents"),
        average_rating=Avg("ascents__rating"),
        average_proposed_grade=Avg("ascents__proposed_grade"),
    )
    if request.user.is_authenticated:
        climbing_routes = climbing_routes.annotate(
            completed_by_user=Exists(
                Ascent.objects.filter(
                    user=request.user,
                    climbing_route_id=OuterRef("pk"),
                )
            )
        )
    else:
        climbing_routes = climbing_routes.annotate(
            completed_by_user=Value(False, output_field=BooleanField())
        )

    if selected_discipline in ClimbingRoute.Discipline.values:
        climbing_routes = climbing_routes.filter(discipline=selected_discipline)
    else:
        selected_discipline = ""

    if sort == "name":
        climbing_routes = climbing_routes.order_by(Lower("name"))
    elif sort == "name_desc":
        climbing_routes = climbing_routes.order_by(Lower("name").desc())
    elif sort == "grade_desc":
        climbing_routes = climbing_routes.order_by(
            "is_project",
            "-grade_order",
            Lower("name"),
        )
    elif sort == "ascents_asc":
        climbing_routes = climbing_routes.order_by("ascent_count", Lower("name"))
    elif sort == "ascents":
        climbing_routes = climbing_routes.order_by("-ascent_count", Lower("name"))
    elif sort == "rating_asc":
        climbing_routes = climbing_routes.order_by(
            F("average_rating").asc(nulls_last=True),
            Lower("name"),
        )
    elif sort == "rating":
        climbing_routes = climbing_routes.order_by(
            F("average_rating").desc(nulls_last=True),
            Lower("name"),
        )
    else:
        sort = "grade"
        climbing_routes = climbing_routes.order_by(
            "is_project",
            "grade_order",
            Lower("name"),
        )

    route_list = list(climbing_routes)
    for climbing_route in route_list:
        average_value = getattr(climbing_route, "average_proposed_grade", None)
        average_display = (
            format_perceived_grade(round(average_value)) if average_value is not None else "—"
        )
        cast(Any, climbing_route).average_proposed_grade_display = average_display

    return render(
        request,
        "climbs/wall_detail.html",
        {
            "wall": wall,
            "climbing_routes": route_list,
            "discipline_counts": discipline_counts,
            "grade_distribution": grade_distribution,
            "maximum_grade_count": max(
                (bucket.count for bucket in grade_distribution),
                default=0,
            ),
            "project_count": project_count,
            "total_route_count": catalogue_routes.count(),
            "total_ascent_count": wall.climbing_routes.aggregate(total=Count("ascents"))["total"],
            "disciplines": ClimbingRoute.Discipline.choices,
            "selected_discipline": selected_discipline,
            "sort": sort,
            "show_archived": show_archived,
        },
    )


def route_list(request: HttpRequest) -> HttpResponse:
    search = request.GET.get("q", "").strip()[:120]
    grade = request.GET.get("grade", "")
    wall_id = request.GET.get("wall", "")
    discipline = request.GET.get("discipline", "")
    status = request.GET.get("status", "active")
    sort = request.GET.get("sort", "grade")

    climbing_routes = ClimbingRoute.objects.select_related("wall").annotate(
        grade_order=grade_order_expression(),
        ascent_count=Count("ascents"),
        average_rating=Avg("ascents__rating"),
    )
    climbing_routes = _status_filter(climbing_routes, status)
    if search:
        climbing_routes = climbing_routes.filter(name__icontains=search)
    if grade == "project":
        climbing_routes = climbing_routes.filter(is_project=True)
    elif grade in FRENCH_GRADE_BASES:
        climbing_routes = climbing_routes.filter(is_project=False, official_grade=grade)
    else:
        grade = ""
    if wall_id.isdigit():
        climbing_routes = climbing_routes.filter(wall_id=int(wall_id))
    else:
        wall_id = ""
    if discipline in ClimbingRoute.Discipline.values:
        climbing_routes = climbing_routes.filter(discipline=discipline)
    else:
        discipline = ""

    if sort == "name":
        climbing_routes = climbing_routes.order_by(Lower("name"))
    elif sort == "name_desc":
        climbing_routes = climbing_routes.order_by(Lower("name").desc())
    elif sort == "grade_desc":
        climbing_routes = climbing_routes.order_by("is_project", "-grade_order", Lower("name"))
    elif sort == "ascents":
        climbing_routes = climbing_routes.order_by("-ascent_count", Lower("name"))
    elif sort == "rating":
        climbing_routes = climbing_routes.order_by(
            F("average_rating").desc(nulls_last=True),
            Lower("name"),
        )
    else:
        sort = "grade"
        climbing_routes = climbing_routes.order_by("is_project", "grade_order", Lower("name"))

    page = Paginator(climbing_routes, 20).get_page(request.GET.get("page"))
    walls = Wall.objects.order_by(Lower("name"))
    return render(
        request,
        "climbs/route_list.html",
        {
            "page": page,
            "walls": walls,
            "grades": FRENCH_GRADE_BASES,
            "disciplines": ClimbingRoute.Discipline.choices,
            "search": search,
            "selected_grade": grade,
            "selected_wall": wall_id,
            "selected_discipline": discipline,
            "status": status,
            "sort": sort,
        },
    )


def route_detail(request: HttpRequest, pk: int) -> HttpResponse:
    climbing_route = get_object_or_404(
        ClimbingRoute.objects.select_related("wall", "route_image")
        .prefetch_related("route_setters")
        .annotate(
            ascent_count=Count("ascents"),
            average_rating=Avg("ascents__rating"),
            average_proposed_grade=Avg("ascents__proposed_grade"),
        ),
        pk=pk,
    )
    ascents = climbing_route.ascents.select_related("user").order_by(
        "-date", Lower("user__username")
    )
    proposed_grade_counts = {
        row["proposed_grade"]: row["count"]
        for row in climbing_route.ascents.order_by()
        .values("proposed_grade")
        .annotate(count=Count("id"))
        .order_by("proposed_grade")
    }
    proposed_distribution = continuous_perceived_grade_distribution(proposed_grade_counts)
    average_proposed_value = getattr(climbing_route, "average_proposed_grade", None)
    average_proposed_grade = (
        format_perceived_grade(round(average_proposed_value))
        if average_proposed_value is not None
        else "—"
    )
    user_ascent = None
    if request.user.is_authenticated:
        user_ascent = Ascent.objects.filter(
            user=request.user,
            climbing_route=climbing_route,
        ).first()
    route_image = getattr(climbing_route, "route_image", None)
    return render(
        request,
        "climbs/route_detail.html",
        {
            "climbing_route": climbing_route,
            "ascents": ascents,
            "proposed_distribution": proposed_distribution,
            "maximum_proposed_grade_count": max(
                (bucket.count for bucket in proposed_distribution),
                default=0,
            ),
            "average_proposed_grade": average_proposed_grade,
            "user_ascent": user_ascent,
            "route_image": route_image,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def wall_create(request: HttpRequest) -> HttpResponse:
    actor = _authorised_user(request, "climbs.add_wall")
    form = WallForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            wall = form.save()
            record_audit_event(
                actor=actor,
                action=AuditLogEntry.Action.CREATE,
                entity_type="wall",
                entity_id=wall.pk,
            )
        logger.info(
            "catalog_action actor_id=%s action=create entity=wall entity_id=%s", actor.pk, wall.pk
        )
        messages.success(request, _("Wall created successfully."))
        return redirect("climbs:wall_detail", pk=wall.pk)
    return render(request, "climbs/wall_form.html", {"form": form, "editing": False})


@login_required
@require_http_methods(["GET", "POST"])
def wall_edit(request: HttpRequest, pk: int) -> HttpResponse:
    actor = _authorised_user(request, "climbs.change_wall")
    wall = get_object_or_404(Wall, pk=pk)
    form = WallForm(request.POST or None, instance=wall)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            wall = form.save()
            record_audit_event(
                actor=actor,
                action=AuditLogEntry.Action.UPDATE,
                entity_type="wall",
                entity_id=wall.pk,
            )
        logger.info(
            "catalog_action actor_id=%s action=update entity=wall entity_id=%s", actor.pk, wall.pk
        )
        messages.success(request, _("Wall updated successfully."))
        return redirect("climbs:wall_detail", pk=wall.pk)
    return render(
        request,
        "climbs/wall_form.html",
        {"form": form, "wall": wall, "editing": True},
    )


@login_required
@require_POST
def wall_archive(request: HttpRequest, pk: int) -> HttpResponse:
    actor = _authorised_user(request, "climbs.change_wall")
    with transaction.atomic():
        wall = get_object_or_404(Wall.objects.select_for_update(), pk=pk)
        if not wall.is_archived and wall.climbing_routes.filter(is_archived=False).exists():
            messages.error(request, _("Archive all routes on this wall first."))
            return redirect("climbs:wall_detail", pk=wall.pk)
        wall.is_archived = not wall.is_archived
        wall.save(update_fields=["is_archived"])
        action = AuditLogEntry.Action.ARCHIVE if wall.is_archived else AuditLogEntry.Action.RESTORE
        record_audit_event(
            actor=actor,
            action=action,
            entity_type="wall",
            entity_id=wall.pk,
        )
    logger.info(
        "catalog_action actor_id=%s action=%s entity=wall entity_id=%s", actor.pk, action, wall.pk
    )
    messages.success(request, _("Wall status updated."))
    return redirect("climbs:wall_detail", pk=wall.pk)


@login_required
@require_http_methods(["GET", "POST"])
def wall_delete(request: HttpRequest, pk: int) -> HttpResponse:
    actor = _authorised_user(request, "climbs.delete_wall")
    wall = get_object_or_404(Wall, pk=pk)
    if not wall.is_archived:
        messages.error(request, _("Archive the wall before deleting it permanently."))
        return redirect("climbs:wall_detail", pk=wall.pk)
    form = ConfirmDeleteForm(request.POST or None, expected_name=wall.name)
    if request.method == "POST" and form.is_valid():
        wall_id = wall.pk
        try:
            with transaction.atomic():
                wall.delete()
                record_audit_event(
                    actor=actor,
                    action=AuditLogEntry.Action.DELETE,
                    entity_type="wall",
                    entity_id=wall_id,
                )
        except ProtectedError:
            messages.error(request, _("This wall still contains routes and cannot be deleted."))
            return redirect("climbs:wall_detail", pk=wall_id)
        logger.info(
            "catalog_action actor_id=%s action=delete entity=wall entity_id=%s", actor.pk, wall_id
        )
        messages.success(request, _("Wall permanently deleted."))
        return redirect("climbs:wall_list")
    return render(
        request,
        "climbs/delete_confirm.html",
        {
            "form": form,
            "object": wall,
            "object_type": _("wall"),
            "cancel_url": reverse("climbs:wall_detail", kwargs={"pk": wall.pk}),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def route_create(request: HttpRequest) -> HttpResponse:
    actor = _authorised_user(request, "climbs.add_climbingroute")
    form = ClimbingRouteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            climbing_route = form.save()
            record_audit_event(
                actor=actor,
                action=AuditLogEntry.Action.CREATE,
                entity_type="route",
                entity_id=climbing_route.pk,
                metadata={
                    "wall_id": climbing_route.wall_id,
                    "discipline": climbing_route.discipline,
                },
            )
        logger.info(
            "catalog_action actor_id=%s action=create entity=route entity_id=%s",
            actor.pk,
            climbing_route.pk,
        )
        messages.success(request, _("Climbing route created successfully."))
        return redirect("climbs:route_detail", pk=climbing_route.pk)
    return render(request, "climbs/route_form.html", {"form": form, "editing": False})


@login_required
@require_http_methods(["GET", "POST"])
def route_edit(request: HttpRequest, pk: int) -> HttpResponse:
    actor = _authorised_user(request, "climbs.change_climbingroute")
    climbing_route = get_object_or_404(ClimbingRoute, pk=pk)
    form = ClimbingRouteForm(request.POST or None, instance=climbing_route)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            climbing_route = form.save()
            record_audit_event(
                actor=actor,
                action=AuditLogEntry.Action.UPDATE,
                entity_type="route",
                entity_id=climbing_route.pk,
            )
        logger.info(
            "catalog_action actor_id=%s action=update entity=route entity_id=%s",
            actor.pk,
            climbing_route.pk,
        )
        messages.success(request, _("Climbing route updated successfully."))
        return redirect("climbs:route_detail", pk=climbing_route.pk)
    return render(
        request,
        "climbs/route_form.html",
        {"form": form, "climbing_route": climbing_route, "editing": True},
    )


@login_required
@require_POST
def route_archive(request: HttpRequest, pk: int) -> HttpResponse:
    actor = _authorised_user(request, "climbs.change_climbingroute")
    with transaction.atomic():
        climbing_route = get_object_or_404(
            ClimbingRoute.objects.select_for_update(),
            pk=pk,
        )
        climbing_route.is_archived = not climbing_route.is_archived
        climbing_route.save(update_fields=["is_archived"])
        action = (
            AuditLogEntry.Action.ARCHIVE
            if climbing_route.is_archived
            else AuditLogEntry.Action.RESTORE
        )
        record_audit_event(
            actor=actor,
            action=action,
            entity_type="route",
            entity_id=climbing_route.pk,
        )
    logger.info(
        "catalog_action actor_id=%s action=%s entity=route entity_id=%s",
        actor.pk,
        action,
        climbing_route.pk,
    )
    messages.success(request, _("Climbing route status updated."))
    return redirect("climbs:route_detail", pk=climbing_route.pk)


@login_required
@require_http_methods(["GET", "POST"])
def route_delete(request: HttpRequest, pk: int) -> HttpResponse:
    actor = _authorised_user(request, "climbs.delete_climbingroute")
    climbing_route = get_object_or_404(ClimbingRoute, pk=pk)
    if not climbing_route.is_archived:
        messages.error(request, _("Archive the route before deleting it permanently."))
        return redirect("climbs:route_detail", pk=climbing_route.pk)
    form = ConfirmDeleteForm(request.POST or None, expected_name=climbing_route.name)
    if request.method == "POST" and form.is_valid():
        route_id = climbing_route.pk
        try:
            with transaction.atomic():
                climbing_route.delete()
                record_audit_event(
                    actor=actor,
                    action=AuditLogEntry.Action.DELETE,
                    entity_type="route",
                    entity_id=route_id,
                )
        except ProtectedError:
            messages.error(request, _("This route has related records and cannot be deleted."))
            return redirect("climbs:route_detail", pk=route_id)
        logger.info(
            "catalog_action actor_id=%s action=delete entity=route entity_id=%s", actor.pk, route_id
        )
        messages.success(request, _("Climbing route permanently deleted."))
        return redirect("climbs:route_list")
    return render(
        request,
        "climbs/delete_confirm.html",
        {
            "form": form,
            "object": climbing_route,
            "object_type": _("climbing route"),
            "cancel_url": reverse(
                "climbs:route_detail",
                kwargs={"pk": climbing_route.pk},
            ),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def route_image_upload(request: HttpRequest, pk: int) -> HttpResponse:
    climbing_route = get_object_or_404(ClimbingRoute, pk=pk)
    existing = RouteImage.objects.filter(climbing_route=climbing_route).first()
    permission = "climbs.change_routeimage" if existing else "climbs.add_routeimage"
    actor = _authorised_user(request, permission)
    form = (
        RouteImageUploadForm(request.POST, request.FILES)
        if request.method == "POST"
        else RouteImageUploadForm()
    )
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                route_image, created = save_route_image(
                    climbing_route=climbing_route,
                    actor=actor,
                    upload=form.cleaned_data["image"],
                    existing=existing,
                )
                record_audit_event(
                    actor=actor,
                    action=(
                        AuditLogEntry.Action.UPLOAD if created else AuditLogEntry.Action.REPLACE
                    ),
                    entity_type="route_image",
                    entity_id=route_image.pk,
                    metadata={"route_id": climbing_route.pk},
                )
        except IntegrityError:
            form.add_error(
                None,
                _("The route image changed while you were editing. Reload and try again."),
            )
        else:
            action = "create" if created else "replace"
            logger.info(
                "image_action actor_id=%s action=%s image_id=%s route_id=%s",
                actor.pk,
                action,
                route_image.pk,
                climbing_route.pk,
            )
            if created:
                messages.success(request, _("Image uploaded. You can now add route markers."))
            else:
                messages.success(
                    request,
                    _("Image replaced. Previous markers were cleared because the image changed."),
                )
            return redirect("climbs:route_annotation_edit", pk=climbing_route.pk)
    return render(
        request,
        "climbs/route_image_form.html",
        {
            "form": form,
            "climbing_route": climbing_route,
            "replacing": existing is not None,
            "route_image": existing,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def route_annotation_edit(request: HttpRequest, pk: int) -> HttpResponse:
    actor = _authorised_user(request, "climbs.change_routeimage")
    route_image = get_object_or_404(
        RouteImage.objects.select_related("climbing_route"),
        climbing_route_id=pk,
    )
    form = (
        RouteAnnotationForm(request.POST, route_image=route_image)
        if request.method == "POST"
        else RouteAnnotationForm(route_image=route_image)
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            route_image = form.save()
            record_audit_event(
                actor=actor,
                action=AuditLogEntry.Action.ANNOTATE,
                entity_type="route_image",
                entity_id=route_image.pk,
                metadata={"route_id": route_image.climbing_route_id},
            )
        logger.info(
            "image_action actor_id=%s action=annotate image_id=%s route_id=%s",
            actor.pk,
            route_image.pk,
            route_image.climbing_route_id,
        )
        messages.success(request, _("Route annotation saved."))
        return redirect("climbs:route_detail", pk=route_image.climbing_route_id)
    return render(
        request,
        "climbs/route_annotation_form.html",
        {
            "form": form,
            "climbing_route": route_image.climbing_route,
            "route_image": route_image,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def route_image_delete(request: HttpRequest, pk: int) -> HttpResponse:
    actor = _authorised_user(request, "climbs.delete_routeimage")
    route_image = get_object_or_404(
        RouteImage.objects.select_related("climbing_route"),
        climbing_route_id=pk,
    )
    climbing_route = route_image.climbing_route
    if request.method == "POST":
        image_id = route_image.pk
        with transaction.atomic():
            delete_route_image(route_image)
            record_audit_event(
                actor=actor,
                action=AuditLogEntry.Action.DELETE,
                entity_type="route_image",
                entity_id=image_id,
                metadata={"route_id": climbing_route.pk},
            )
        logger.info(
            "image_action actor_id=%s action=delete image_id=%s route_id=%s",
            actor.pk,
            image_id,
            climbing_route.pk,
        )
        messages.success(request, _("Route image and its annotation were deleted."))
        return redirect("climbs:route_detail", pk=climbing_route.pk)
    return render(
        request,
        "climbs/route_image_delete_confirm.html",
        {"climbing_route": climbing_route, "route_image": route_image},
    )


def user_list(request: HttpRequest) -> HttpResponse:
    search = request.GET.get("q", "").strip()[:150]
    sort = request.GET.get("sort", "name")
    users = User.objects.filter(is_active=True).annotate(
        ascent_count=Count("ascents", distinct=True),
        highest_grade_order=Max(
            grade_order_expression(
                "ascents__climbing_route__official_grade",
                default_value=-1,
            )
        ),
    )
    if search:
        users = users.filter(username__icontains=search)
    if sort == "ascents":
        users = users.order_by("-ascent_count", Lower("username"))
    elif sort == "grade":
        users = users.order_by("-highest_grade_order", Lower("username"))
    else:
        sort = "name"
        users = users.order_by(Lower("username"))

    page = Paginator(users, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "climbs/user_list.html",
        {"page": page, "search": search, "sort": sort},
    )


@login_required
@require_http_methods(["GET", "POST"])
def ascent_create(request: HttpRequest) -> HttpResponse:
    actor = _authorised_user(request, "climbs.add_ascent")
    selected_route = None
    route_id = request.GET.get("route", "")
    if route_id.isdigit():
        selected_route = get_object_or_404(ClimbingRoute, pk=int(route_id))
        if request.method == "GET":
            existing_ascent = Ascent.objects.filter(
                user=actor,
                climbing_route=selected_route,
            ).first()
            if existing_ascent:
                messages.info(
                    request,
                    _("You already recorded this route. You can update it here."),
                )
                return redirect("climbs:ascent_edit", pk=existing_ascent.pk)

    initial: dict[str, Any] | None = None
    if request.method == "GET":
        initial = {
            "date": timezone.localdate(),
            "rating": 3,
        }
        if selected_route:
            initial["climbing_route"] = selected_route
            if not selected_route.is_project:
                initial["proposed_grade_base"] = selected_route.official_grade
                initial["proposed_grade_decimal"] = 5

    form = AscentForm(request.POST or None, user=actor, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                ascent = form.save()
        except IntegrityError:
            form.add_error(
                "climbing_route",
                _("You have already recorded an ascent for this route."),
            )
        else:
            logger.info(
                "ascent_action actor_id=%s action=create ascent_id=%s route_id=%s",
                actor.pk,
                ascent.pk,
                ascent.climbing_route_id,
            )
            messages.success(request, _("Ascent recorded successfully."))
            return redirect("climbs:route_detail", pk=ascent.climbing_route_id)
    return render(
        request,
        "climbs/ascent_form.html",
        {"form": form, "editing": False},
    )


@login_required
@require_http_methods(["GET", "POST"])
def ascent_edit(request: HttpRequest, pk: int) -> HttpResponse:
    actor = _authorised_user(request, "climbs.change_ascent")
    ascent = get_object_or_404(
        Ascent.objects.select_related("climbing_route"),
        pk=pk,
        user=actor,
    )
    form = AscentForm(request.POST or None, instance=ascent, user=actor)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                ascent = form.save()
        except IntegrityError:
            form.add_error(
                "climbing_route",
                _("You have already recorded an ascent for this route."),
            )
        else:
            logger.info(
                "ascent_action actor_id=%s action=update ascent_id=%s route_id=%s",
                actor.pk,
                ascent.pk,
                ascent.climbing_route_id,
            )
            messages.success(request, _("Ascent updated successfully."))
            return redirect("climbs:route_detail", pk=ascent.climbing_route_id)
    return render(
        request,
        "climbs/ascent_form.html",
        {"form": form, "editing": True, "ascent": ascent},
    )


@login_required
@require_http_methods(["GET", "POST"])
def ascent_delete(request: HttpRequest, pk: int) -> HttpResponse:
    actor = _authorised_user(request, "climbs.delete_ascent")
    ascent = get_object_or_404(
        Ascent.objects.select_related("climbing_route"),
        pk=pk,
        user=actor,
    )
    if request.method == "POST":
        route_id = ascent.climbing_route_id
        ascent_id = ascent.pk
        with transaction.atomic():
            ascent.delete()
        logger.info(
            "ascent_action actor_id=%s action=delete ascent_id=%s route_id=%s",
            actor.pk,
            ascent_id,
            route_id,
        )
        messages.success(request, _("Ascent deleted successfully."))
        return redirect("climbs:route_detail", pk=route_id)
    return render(
        request,
        "climbs/ascent_delete_confirm.html",
        {"ascent": ascent},
    )
