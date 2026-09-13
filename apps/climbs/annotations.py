import json
from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

ANNOTATION_VERSION = 1
MAX_ANNOTATION_MARKERS = 100
SINGLE_MARKER_TYPES = {"start-left", "start-right", "top"}
ROUTE_MARKER_TYPES = SINGLE_MARKER_TYPES | {"move"}
BOULDER_MARKER_TYPES = {"start", "hold", "top"}
MARKER_TYPES = ROUTE_MARKER_TYPES | BOULDER_MARKER_TYPES
MARKER_HANDS = {"left", "right"}


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
    expected_legacy_hold_number = 1
    for marker in markers:
        if not isinstance(marker, dict):
            raise ValidationError(_("Every annotation marker must be an object."))
        marker_type = marker.get("type")
        if marker_type not in MARKER_TYPES:
            raise ValidationError(_("An annotation marker has an invalid type."))

        required_keys = {"type", "x", "y"}
        if marker_type == "move":
            required_keys.add("number")
        optional_keys = (
            {"hand"} if marker_type == "move" else {"number"} if marker_type == "hold" else set()
        )
        allowed_keys = required_keys | optional_keys
        if not required_keys <= set(marker) or not set(marker) <= allowed_keys:
            raise ValidationError(_("An annotation marker has invalid fields."))

        x = _normalised_coordinate(marker["x"])
        y = _normalised_coordinate(marker["y"])
        clean_marker: dict[str, Any] = {"type": marker_type, "x": x, "y": y}

        if marker_type == "move":
            number = marker["number"]
            if isinstance(number, bool) or not isinstance(number, int):
                raise ValidationError(_("Numbered marker values must be integers."))
            if number != expected_move_number:
                raise ValidationError(_("Numbered markers must be numbered consecutively."))
            clean_marker["number"] = number
            expected_move_number += 1
            hand = marker.get("hand")
            if hand is not None:
                if number != 1 or hand not in MARKER_HANDS:
                    raise ValidationError(_("Only the first route hold may specify left or right."))
                clean_marker["hand"] = hand
        elif marker_type == "hold" and "number" in marker:
            legacy_number = marker["number"]
            if isinstance(legacy_number, bool) or not isinstance(legacy_number, int):
                raise ValidationError(_("Numbered marker values must be integers."))
            if legacy_number != expected_legacy_hold_number:
                raise ValidationError(_("Numbered markers must be numbered consecutively."))
            expected_legacy_hold_number += 1
        else:
            if marker_type in SINGLE_MARKER_TYPES:
                if marker_type in seen_singletons:
                    raise ValidationError(_("This annotation marker may only be used once."))
                seen_singletons.add(marker_type)

        normalised_markers.append(clean_marker)

    return {"version": ANNOTATION_VERSION, "markers": normalised_markers}


def validate_route_annotation(payload: Any) -> None:
    normalise_route_annotation(payload)


def validate_annotation_for_discipline(
    payload: Any,
    discipline: str,
) -> dict[str, Any]:
    normalised = normalise_route_annotation(payload)
    allowed_types = BOULDER_MARKER_TYPES if discipline == "boulder" else ROUTE_MARKER_TYPES
    if any(marker["type"] not in allowed_types for marker in normalised["markers"]):
        raise ValidationError(
            _("The annotation contains markers that do not match the climb type.")
        )

    if discipline == "route":
        first_move = next(
            (marker for marker in normalised["markers"] if marker["type"] == "move"),
            None,
        )
        if first_move is not None and "hand" not in first_move:
            raise ValidationError(_("The first route hold must indicate left or right."))

    return normalised


def _normalised_coordinate(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValidationError(_("Marker coordinates must be numbers."))
    coordinate = float(value)
    if not 0 <= coordinate <= 1:
        raise ValidationError(_("Marker coordinates must be between 0 and 1."))
    return round(coordinate, 6)
