"""A model's reading is validated element by element: one bad element is dropped and reported, never fatal."""
import json
from pathlib import Path

from backend.app.ai.real2sim.schema import VenueDraftV1, provider_response_schema, salvage_draft

FIXTURE = Path(__file__).resolve().parents[2] / "venue" / "real2sim" / "sketch-home" / "draft.json"


def base() -> dict:
    return {
        "schema_version": "draft-1", "image_kind": "sketch", "scale": {"basis": "unknown"},
        "rooms": [{"key": "LIVING", "name": "Living", "kind": "room", "box": [0, 0, 500, 600], "label_point": [250, 300]},
                  {"key": "HALL", "name": "Hall", "kind": "hall", "box": [500, 0, 600, 1000], "label_point": [550, 500]}],
        "doors": [{"key": "D_LH", "between": ["LIVING", "HALL"], "point": [500, 300], "confidence": 0.9}],
        "exits": [{"key": "X_FRONT", "room": "LIVING", "point": [250, 0], "confidence": 0.8}],
    }


def test_a_clean_reading_round_trips():
    raw = json.loads(FIXTURE.read_text())
    salvaged = salvage_draft(raw)
    assert salvaged.draft == VenueDraftV1.model_validate(raw)
    assert salvaged.dropped == [] and salvaged.error is None


def test_one_bad_element_is_dropped_not_fatal():
    raw = base()
    raw["rooms"].append({"key": "CLOSET", "name": "Closet", "kind": "storage", "box": [10, 10, 10, 50], "label_point": [10, 30]})
    raw["doors"].append({"key": "D_X", "between": ["LIVING", "ATTIC"], "point": [10, 10], "confidence": 0.4})
    raw["exits"].append({"key": "X_BAD", "room": "GARAGE", "point": [0, 0], "confidence": 0.5})
    salvaged = salvage_draft(raw)
    assert [r.key for r in salvaged.draft.rooms] == ["LIVING", "HALL"]
    assert [d.key for d in salvaged.draft.doors] == ["D_LH"] and [e.key for e in salvaged.draft.exits] == ["X_FRONT"]
    assert any(item.startswith("room CLOSET:") for item in salvaged.dropped)
    assert "door D_X: joins unknown or identical room ATTIC" in salvaged.dropped
    assert "exit X_BAD: unknown room GARAGE" in salvaged.dropped


def test_harmless_repairs_are_applied_and_listed():
    raw = base()
    raw["rooms"][0].update(name="L" * 50, box=[0.0, 0.0, 500.0, 600.4], key="living room")
    raw["doors"][0]["between"] = ["living room", "HALL"]
    raw["exits"][0]["room"] = "living room"
    raw["scale"] = {"basis": "dimension_label", "metres": 12.0}   # incomplete reference
    raw["image_kind"] = "napkin"
    salvaged = salvage_draft(raw)
    living = salvaged.draft.rooms[0]
    assert living.key == "LIVING_ROOM" and len(living.name) == 40 and living.box == [0, 0, 500, 600]
    assert salvaged.draft.scale.basis == "unknown" and salvaged.draft.image_kind == "other"
    assert salvaged.dropped == [] and len(salvaged.repaired) >= 4


def test_a_door_to_the_outside_becomes_an_exit_and_exits_may_be_empty():
    raw = base()
    raw["exits"] = []
    raw["doors"].append({"key": "D_OUT", "between": ["HALL", "OUTSIDE"], "point": [600, 500], "confidence": 0.7})
    salvaged = salvage_draft(raw)
    assert [(e.key, e.room, e.label) for e in salvaged.draft.exits] == [("D_OUT", "HALL", "door to outside")]
    no_exit = base()
    no_exit["exits"] = []
    assert salvage_draft(no_exit).draft.exits == []


def test_only_a_reading_without_rooms_fails_whole():
    assert salvage_draft("nope").error == "draft_not_an_object"
    assert salvage_draft({**base(), "rooms": [{"key": "X"}]}).error == "no_room_survived"


def test_provider_schema_avoids_unproven_keywords():
    text = json.dumps(provider_response_schema())
    for keyword in ('"pattern"', '"const"', '"exclusiveMinimum"', '"default"'):
        assert keyword not in text
    assert '"enum": ["draft-1"]' in text
