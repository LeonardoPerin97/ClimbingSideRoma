import json
from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

ANNOTATION_VERSION = 1
MAX_ANNOTATION_MARKERS = 100
SINGLE_MARKER_TYPES = {"start-left", "start-right", "top"}
MARKER_TYPES = SINGLE_MARKER_TYPES | {"move"}


def empty_route_annotation() -> dict[str, Any]:
    return {"version": ANNOTATION_VERSION, "markers": []}


def parse_route_annotation(raw_value: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValidationError(_("The annotation data is not valid JSON.")) from error
    return normalise_route_annotation(payload)


def normalise_route_annotation(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or set(payload) != {"version", "markers"}:
        raise ValidationError(_("The annotation data has an invalid structure."))
    if payload["version"] != ANNOTATION_VERSION:
        raise ValidationError(_("This annotation version is not supported."))

    markers = payload["markers"]
    if not isinstance(markers, list):
        raise ValidationError(_("The annotation markers must be a list."))
    if len(markers) > MAX_ANNOTATION_MARKERS:
        raise ValidationError(
            _("An annotation can contain at most %(limit)s markers."),
            params={"limit": MAX_ANNOTATION_MARKERS},
        )

    normalised_markers: list[dict[str, Any]] = []
    seen_singletons: set[str] = set()
    expected_move_number = 1
    for marker in markers:
        if not isinstance(marker, dict):
            raise ValidationError(_("Every annotation marker must be an object."))
        marker_type = marker.get("type")
        if marker_type not in MARKER_TYPES:
            raise ValidationError(_("An annotation marker has an invalid type."))

        required_keys = (
            {"type", "x", "y", "number"}
            if marker_type == "move"
            else {
                "type",
                "x",
                "y",
            }
        )
        if set(marker) != required_keys:
            raise ValidationError(_("An annotation marker has invalid fields."))

        x = _normalised_coordinate(marker["x"])
        y = _normalised_coordinate(marker["y"])
        clean_marker: dict[str, Any] = {"type": marker_type, "x": x, "y": y}

        if marker_type == "move":
            number = marker["number"]
            if isinstance(number, bool) or not isinstance(number, int):
                raise ValidationError(_("Move marker numbers must be integers."))
            if number != expected_move_number:
                raise ValidationError(_("Move markers must be numbered consecutively."))
            clean_marker["number"] = number
            expected_move_number += 1
        else:
            if marker_type in seen_singletons:
                raise ValidationError(_("Start and top markers may only be used once."))
            seen_singletons.add(marker_type)

        normalised_markers.append(clean_marker)

    return {"version": ANNOTATION_VERSION, "markers": normalised_markers}


def validate_route_annotation(payload: Any) -> None:
    normalise_route_annotation(payload)


def _normalised_coordinate(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValidationError(_("Marker coordinates must be numbers."))
    coordinate = float(value)
    if not 0 <= coordinate <= 1:
        raise ValidationError(_("Marker coordinates must be between 0 and 1."))
    return round(coordinate, 6)
