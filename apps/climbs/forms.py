from datetime import date
from json import dumps
from typing import Any, cast

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.core.forms import StyledFormMixin

from .annotations import empty_route_annotation, parse_route_annotation
from .grades import FRENCH_GRADE_CHOICES, encode_perceived_grade
from .images import validate_route_image
from .models import Ascent, ClimbingRoute, RouteImage, Wall


class WallForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Wall
        fields = ("name",)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.apply_control_classes()

    def clean_name(self) -> str:
        name = self.cleaned_data["name"].strip()
        duplicate = Wall.objects.filter(name__iexact=name).exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise ValidationError(_("A wall with this name already exists."))
        return name


class ClimbingRouteForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = ClimbingRoute
        fields = (
            "name",
            "wall",
            "discipline",
            "is_project",
            "official_grade",
            "route_setters",
        )
        widgets = {
            "is_project": forms.CheckboxInput(attrs={"data-project-toggle": ""}),
            "official_grade": forms.Select(attrs={"data-grade-field": ""}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.apply_control_classes()
        self.fields["official_grade"].required = False
        self.fields["route_setters"].required = False
        self.fields["route_setters"].help_text = _(
            "Optional. You may select one or more route setters."
        )

        available_walls = Wall.objects.filter(is_archived=False)
        if self.instance.pk and self.instance.wall_id:
            available_walls = Wall.objects.filter(
                Q(is_archived=False) | Q(pk=self.instance.wall_id)
            )
        wall_field = cast(forms.ModelChoiceField, self.fields["wall"])
        route_setters_field = cast(
            forms.ModelMultipleChoiceField,
            self.fields["route_setters"],
        )
        wall_field.queryset = available_walls.order_by(Lower("name"))
        route_setters_field.queryset = (
            User.objects.filter(groups__name="RouteSetter", is_active=True)
            .distinct()
            .order_by(Lower("username"))
        )

    def clean_name(self) -> str:
        name = self.cleaned_data["name"].strip()
        duplicate = ClimbingRoute.objects.filter(name__iexact=name).exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise ValidationError(_("A climbing route with this name already exists."))
        return name

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean() or {}
        if cleaned_data.get("is_project"):
            cleaned_data["official_grade"] = ""
            self.instance.official_grade = ""
        elif not cleaned_data.get("official_grade"):
            self.add_error(
                "official_grade",
                _("Choose an official grade or mark the route as Project."),
            )
        return cleaned_data


class ConfirmDeleteForm(StyledFormMixin, forms.Form):
    name = forms.CharField(label=_("Type the name to confirm"), max_length=120)

    def __init__(self, *args: Any, expected_name: str, **kwargs: Any) -> None:
        self.expected_name = expected_name
        super().__init__(*args, **kwargs)
        self.apply_control_classes()

    def clean_name(self) -> str:
        name = self.cleaned_data["name"].strip()
        if name != self.expected_name:
            raise ValidationError(_("The entered name does not match."))
        return name


class RouteImageUploadForm(StyledFormMixin, forms.Form):
    image = forms.ImageField(
        label=_("Route image"),
        validators=(validate_route_image,),
        widget=forms.ClearableFileInput(
            attrs={"accept": "image/jpeg,image/png,image/webp"},
        ),
        help_text=_("JPEG, PNG or WebP. Maximum 8 MB."),
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.apply_control_classes()


class RouteAnnotationForm(forms.Form):
    annotations = forms.CharField(widget=forms.HiddenInput())

    def __init__(
        self,
        *args: Any,
        route_image: RouteImage,
        **kwargs: Any,
    ) -> None:
        self.route_image = route_image
        if not args and "initial" not in kwargs:
            kwargs["initial"] = {"annotations": dumps(route_image.annotations)}
        super().__init__(*args, **kwargs)

    def clean_annotations(self) -> dict[str, Any]:
        return parse_route_annotation(self.cleaned_data["annotations"])

    def save(self) -> RouteImage:
        self.route_image.annotations = self.cleaned_data.get(
            "annotations",
            empty_route_annotation(),
        )
        # The image was validated before upload. Revalidating it while only the
        # JSON annotation changes would require reading the stored Cloudinary
        # asset again, which remote storage intentionally does not support.
        self.route_image.full_clean(exclude=("image",))
        self.route_image.save(update_fields=("annotations", "updated_at"))
        return self.route_image


class AscentForm(StyledFormMixin, forms.ModelForm):
    proposed_grade_base = forms.ChoiceField(
        label=_("Perceived grade"),
        choices=(("", _("Choose a grade")), *FRENCH_GRADE_CHOICES),
    )
    proposed_grade_decimal = forms.TypedChoiceField(
        label=_("Grade decimal"),
        choices=tuple((value, str(value)) for value in range(10)),
        coerce=int,
    )

    class Meta:
        model = Ascent
        fields = (
            "climbing_route",
            "date",
            "rating",
            "proposed_grade_base",
            "proposed_grade_decimal",
            "attempt_type",
            "attempt_count",
        )
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "rating": forms.Select(choices=tuple((value, value) for value in range(1, 6))),
            "attempt_type": forms.Select(attrs={"data-attempt-type": ""}),
            "attempt_count": forms.NumberInput(attrs={"min": 1, "data-attempt-count": ""}),
        }

    def __init__(
        self,
        *args: Any,
        user: User,
        **kwargs: Any,
    ) -> None:
        self.user = user
        super().__init__(*args, **kwargs)
        self.apply_control_classes()

        climbing_route_field = cast(
            forms.ModelChoiceField,
            self.fields["climbing_route"],
        )
        used_route_ids = (
            Ascent.objects.filter(user=user)
            .exclude(
                pk=self.instance.pk,
            )
            .values("climbing_route_id")
        )
        available_routes = ClimbingRoute.objects.exclude(pk__in=used_route_ids)
        climbing_route_field.queryset = available_routes.select_related("wall").order_by(
            Lower("name")
        )

        self.fields["rating"].help_text = _("From 1 to 5 stars.")
        self.fields["proposed_grade_decimal"].help_text = _(
            "Use 0 if you do not need a decimal refinement."
        )
        self.fields["attempt_count"].required = False
        self.fields["attempt_count"].help_text = _(
            "Required only when Number of attempts is selected."
        )

        if self.instance.pk:
            base_index, decimal = divmod(self.instance.proposed_grade, 10)
            self.initial["proposed_grade_base"] = FRENCH_GRADE_CHOICES[base_index][0]
            self.initial["proposed_grade_decimal"] = decimal

    def clean_date(self) -> date:
        ascent_date = self.cleaned_data["date"]
        if ascent_date > timezone.localdate():
            raise ValidationError(_("The ascent date cannot be in the future."))
        return ascent_date

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean() or {}
        climbing_route = cleaned_data.get("climbing_route")
        if climbing_route:
            duplicate = Ascent.objects.filter(
                user=self.user,
                climbing_route=climbing_route,
            ).exclude(pk=self.instance.pk)
            if duplicate.exists():
                self.add_error(
                    "climbing_route",
                    _("You have already recorded an ascent for this route."),
                )

        attempt_type = cleaned_data.get("attempt_type")
        attempt_count = cleaned_data.get("attempt_count")
        if attempt_type == Ascent.AttemptType.COUNT:
            if attempt_count is None or attempt_count < 1:
                self.add_error(
                    "attempt_count",
                    _("Enter a positive number of attempts."),
                )
        else:
            cleaned_data["attempt_count"] = None
            self.instance.attempt_count = None

        base_grade = cleaned_data.get("proposed_grade_base")
        decimal = cleaned_data.get("proposed_grade_decimal")
        if base_grade and decimal is not None:
            self.instance.proposed_grade = encode_perceived_grade(base_grade, decimal)
        self.instance.user = self.user
        return cleaned_data

    def save(self, commit: bool = True) -> Ascent:
        ascent = cast(Ascent, super().save(commit=False))
        ascent.user = self.user
        if commit:
            ascent.save()
            self.save_m2m()
        return ascent
