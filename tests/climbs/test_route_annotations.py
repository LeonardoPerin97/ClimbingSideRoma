import json

import pytest
from django.core.exceptions import ValidationError

from apps.climbs.annotations import (
    MAX_ANNOTATION_MARKERS,
    normalise_route_annotation,
    parse_route_annotation,
)


def test_valid_annotation_is_normalised() -> None:
    payload = {
        "version": 1,
        "markers": [
            {"type": "start-left", "x": 0.1, "y": 0.8},
            {"type": "start-right", "x": 0.2, "y": 0.8},
            {"type": "move", "number": 1, "x": 0.4, "y": 0.5},
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
