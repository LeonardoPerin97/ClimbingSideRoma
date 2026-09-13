import json

import pytest
from django.core.exceptions import ValidationError

from apps.climbs.annotations import (
    MAX_ANNOTATION_MARKERS,
    normalise_route_annotation,
    parse_route_annotation,
    validate_annotation_for_discipline,
)


def test_valid_annotation_is_normalised() -> None:
    payload = {
        "version": 1,
        "markers": [
            {"type": "start-left", "x": 0.1, "y": 0.8},
            {"type": "start-right", "x": 0.2, "y": 0.8},
            {"type": "move", "number": 1, "hand": "left", "x": 0.4, "y": 0.5},
            {"type": "top", "x": 0.5, "y": 0.1},
        ],
    }

    assert parse_route_annotation(json.dumps(payload)) == payload


@pytest.mark.parametrize(
    "payload",
    [
        {"version": 2, "markers": []},
        {"version": 1, "markers": [{"type": "unknown", "x": 0.2, "y": 0.3}]},
        {"version": 1, "markers": [{"type": "top", "x": 1.1, "y": 0.3}]},
        {
            "version": 1,
            "markers": [
                {"type": "top", "x": 0.2, "y": 0.3},
                {"type": "top", "x": 0.4, "y": 0.5},
            ],
        },
        {
            "version": 1,
            "markers": [{"type": "move", "number": 2, "x": 0.2, "y": 0.3}],
        },
    ],
)
def test_invalid_annotation_payload_is_rejected(payload: object) -> None:
    with pytest.raises(ValidationError):
        normalise_route_annotation(payload)


def test_annotation_marker_limit_is_enforced() -> None:
    payload = {
        "version": 1,
        "markers": [
            {"type": "move", "number": number, "x": 0.5, "y": 0.5}
            for number in range(1, MAX_ANNOTATION_MARKERS + 2)
        ],
    }

    with pytest.raises(ValidationError):
        normalise_route_annotation(payload)


def test_malformed_annotation_json_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_route_annotation("{not-json")


def test_boulder_annotation_accepts_multiple_unlabelled_starts_and_holds() -> None:
    payload = {
        "version": 1,
        "markers": [
            {"type": "start", "x": 0.1, "y": 0.8},
            {"type": "start", "x": 0.2, "y": 0.8},
            {"type": "hold", "x": 0.3, "y": 0.6},
            {"type": "hold", "x": 0.4, "y": 0.4},
            {"type": "top", "x": 0.5, "y": 0.1},
        ],
    }

    assert validate_annotation_for_discipline(payload, "boulder") == payload


def test_legacy_numbered_boulder_holds_are_normalised_without_numbers() -> None:
    legacy_payload = {
        "version": 1,
        "markers": [
            {"type": "hold", "number": 1, "x": 0.3, "y": 0.6},
            {"type": "hold", "number": 2, "x": 0.4, "y": 0.4},
        ],
    }
    expected = {
        "version": 1,
        "markers": [
            {"type": "hold", "x": 0.3, "y": 0.6},
            {"type": "hold", "x": 0.4, "y": 0.4},
        ],
    }

    assert validate_annotation_for_discipline(legacy_payload, "boulder") == expected


def test_annotation_markers_must_match_climb_type() -> None:
    boulder_marker = {
        "version": 1,
        "markers": [{"type": "start", "x": 0.1, "y": 0.8}],
    }
    route_marker = {
        "version": 1,
        "markers": [{"type": "start-left", "x": 0.1, "y": 0.8}],
    }

    with pytest.raises(ValidationError):
        validate_annotation_for_discipline(boulder_marker, "route")
    with pytest.raises(ValidationError):
        validate_annotation_for_discipline(route_marker, "boulder")


def test_first_route_hold_must_indicate_left_or_right() -> None:
    missing_hand = {
        "version": 1,
        "markers": [{"type": "move", "number": 1, "x": 0.4, "y": 0.5}],
    }
    invalid_later_hand = {
        "version": 1,
        "markers": [
            {"type": "move", "number": 1, "hand": "left", "x": 0.4, "y": 0.5},
            {"type": "move", "number": 2, "hand": "right", "x": 0.5, "y": 0.4},
        ],
    }

    assert normalise_route_annotation(missing_hand) == missing_hand
    with pytest.raises(ValidationError):
        validate_annotation_for_discipline(missing_hand, "route")
    with pytest.raises(ValidationError):
        normalise_route_annotation(invalid_later_hand)
