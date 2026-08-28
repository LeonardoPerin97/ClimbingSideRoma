from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext

from .annotations import empty_route_annotation, validate_route_annotation
from .grades import FRENCH_GRADE_BASES, FRENCH_GRADE_CHOICES, format_perceived_grade
from .images import route_image_upload_path, validate_route_image


class Wall(models.Model):
    name = models.CharField(_("name"), max_length=100)
    is_archived = models.BooleanField(_("archived"), default=False)

    class Meta:
        ordering = ("name",)
        verbose_name = _("wall")
        verbose_name_plural = _("walls")
        constraints = [
            models.UniqueConstraint(Lower("name"), name="climbs_wall_name_ci_uniq"),
        ]

    def clean(self) -> None:
        self.name = self.name.strip()

    def __str__(self) -> str:
        return self.name


class ClimbingRoute(models.Model):
    class Discipline(models.TextChoices):
        ROUTE = "route", _("Routes")
        BOULDER = "boulder", _("Boulder")

    name = models.CharField(_("name"), max_length=120)
    wall = models.ForeignKey(
        Wall,
        on_delete=models.PROTECT,
        related_name="climbing_routes",
        verbose_name=_("wall"),
    )
    discipline = models.CharField(
        _("type"),
        max_length=10,
        choices=Discipline.choices,
    )
    official_grade = models.CharField(
        _("official grade"),
        max_length=3,
        choices=FRENCH_GRADE_CHOICES,
        blank=True,
    )
    is_project = models.BooleanField(_("project"), default=False)
    route_setters = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="set_climbing_routes",
        limit_choices_to={"groups__name": "RouteSetter", "is_active": True},
        verbose_name=_("route setters"),
    )
    is_archived = models.BooleanField(_("archived"), default=False)

    class Meta:
        ordering = ("name",)
        verbose_name = _("climbing route")
        verbose_name_plural = _("climbing routes")
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="climbs_climbingroute_name_ci_uniq",
            ),
            models.CheckConstraint(
                condition=(Q(is_project=True, official_grade=""))
                | (Q(is_project=False) & ~Q(official_grade="")),
                name="climbs_route_project_grade_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=("is_archived", "discipline")),
            models.Index(fields=("wall", "is_archived")),
            models.Index(fields=("official_grade",)),
        ]

    def clean(self) -> None:
        self.name = self.name.strip()
        if self.is_project:
            self.official_grade = ""
        elif not self.official_grade:
            raise ValidationError(
                {"official_grade": _("A non-project route must have an official grade.")}
            )

    @property
    def display_grade(self) -> str:
        return str(_("Project")) if self.is_project else self.official_grade

    def __str__(self) -> str:
        return self.name


class Ascent(models.Model):
    class AttemptType(models.TextChoices):
        ONSIGHT = "onsight", _("Onsight")
        FLASH = "flash", _("Flash")
        COUNT = "count", _("Number of attempts")
        UNKNOWN = "unknown", _("N.D.")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ascents",
        verbose_name=_("user"),
    )
    climbing_route = models.ForeignKey(
        ClimbingRoute,
        on_delete=models.PROTECT,
        related_name="ascents",
        verbose_name=_("climbing route"),
    )
    date = models.DateField(_("date"), default=timezone.localdate)
    rating = models.PositiveSmallIntegerField(
        _("rating"),
        validators=(MinValueValidator(1), MaxValueValidator(5)),
    )
    proposed_grade = models.PositiveSmallIntegerField(
        _("proposed grade"),
        validators=(
            MinValueValidator(0),
            MaxValueValidator((len(FRENCH_GRADE_BASES) - 1) * 10 + 9),
        ),
        help_text=_("Encoded French grade with a decimal from 0 to 9."),
    )
    attempt_type = models.CharField(
        _("attempt result"),
        max_length=10,
        choices=AttemptType.choices,
        default=AttemptType.UNKNOWN,
    )
    attempt_count = models.PositiveSmallIntegerField(
        _("attempt count"),
        null=True,
        blank=True,
        validators=(MinValueValidator(1),),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        ordering = ("-date", "-created_at")
        verbose_name = _("ascent")
        verbose_name_plural = _("ascents")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "climbing_route"),
                name="climbs_ascent_user_route_uniq",
            ),
            models.CheckConstraint(
                condition=Q(rating__gte=1, rating__lte=5),
                name="climbs_ascent_rating_range",
            ),
            models.CheckConstraint(
                condition=Q(
                    proposed_grade__gte=0,
                    proposed_grade__lte=(len(FRENCH_GRADE_BASES) - 1) * 10 + 9,
                ),
                name="climbs_ascent_proposed_grade_range",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        attempt_type="count",
                        attempt_count__isnull=False,
                        attempt_count__gte=1,
                    )
                    | (~Q(attempt_type="count") & Q(attempt_count__isnull=True))
                ),
                name="climbs_ascent_attempt_consistent",
            ),
        ]
        indexes = [
            models.Index(fields=("user", "date")),
            models.Index(fields=("climbing_route", "date")),
        ]

    def clean(self) -> None:
        if self.date and self.date > timezone.localdate():
            raise ValidationError({"date": _("The ascent date cannot be in the future.")})
        if self.attempt_type == self.AttemptType.COUNT:
            if self.attempt_count is None or self.attempt_count < 1:
                raise ValidationError({"attempt_count": _("Enter a positive number of attempts.")})
        else:
            self.attempt_count = None

    @property
    def display_proposed_grade(self) -> str:
        return format_perceived_grade(self.proposed_grade)

    @property
    def display_attempts(self) -> str:
        if self.attempt_type == self.AttemptType.COUNT:
            count = self.attempt_count or 0
            return ngettext(
                "%(count)s attempt",
                "%(count)s attempts",
                count,
            ) % {"count": count}
        return str(self.get_attempt_type_display())

    def __str__(self) -> str:
        return f"{self.user} — {self.climbing_route}"


class RouteImage(models.Model):
    climbing_route = models.OneToOneField(
        ClimbingRoute,
        on_delete=models.PROTECT,
        related_name="route_image",
        verbose_name=_("climbing route"),
    )
    image = models.ImageField(
        _("image"),
        upload_to=route_image_upload_path,
        validators=(validate_route_image,),
        max_length=255,
    )
    annotations = models.JSONField(
        _("annotations"),
        default=empty_route_annotation,
        validators=(validate_route_annotation,),
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_route_images",
        verbose_name=_("uploaded by"),
    )
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        ordering = ("climbing_route__name",)
        verbose_name = _("route image")
        verbose_name_plural = _("route images")

    @property
    def has_annotations(self) -> bool:
        markers = self.annotations.get("markers", [])
        return bool(markers)

    def __str__(self) -> str:
        return str(self.climbing_route)
