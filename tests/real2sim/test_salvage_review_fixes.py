"""salvage_draft must not invent an exit or attach a door to the wrong room (devil's-advocate review, 26 Oct 2026)."""
from backend.app.ai.real2sim.schema import salvage_draft


def base() -> dict:
    return {
        "schema_version": "draft-1", "image_kind": "evacuation_map", "scale": {"basis": "unknown"},
        "rooms": [{"key": "CORRIDOR", "name": "Corridor", "kind": "corridor", "box": [400, 0, 600, 1000],
                   "label_point": [500, 500]},
                  {"key": "OFFICE", "name": "Office", "kind": "office", "box": [0, 0, 400, 500],
                   "label_point": [200, 250]}],
        "doors": [{"key": "D_OC", "between": ["OFFICE", "CORRIDOR"], "point": [400, 250], "confidence": 0.9}],
        "exits": [{"key": "X_W", "room": "CORRIDOR", "point": [500, 0], "kind": "door", "confidence": 0.9}],
    }


def test_a_door_to_a_dropped_room_keyed_exit_is_not_an_outside_exit():
    """Probe: the stair room EXIT was dropped for a bad box and its door became a 0.95 exit of the corridor."""
    raw = base()
    raw["rooms"].append({"key": "EXIT", "name": "Exit stair", "kind": "stair", "box": [0, 900, 0, 1000],
                         "label_point": [100, 950]})                     # empty box: dropped
    raw["doors"].append({"key": "D_STAIR", "between": ["CORRIDOR", "EXIT"], "point": [400, 950],
                         "confidence": 0.95})
    salvaged = salvage_draft(raw)
    assert [e.key for e in salvaged.draft.exits] == ["X_W"]
    assert [d.key for d in salvaged.draft.doors] == ["D_OC"]
    assert "door D_STAIR: joins room EXIT, which was dropped" in salvaged.dropped
    assert any(item.startswith("room EXIT:") for item in salvaged.dropped)
    assert not any("kept as an exit" in item for item in salvaged.repaired)


def test_exit_and_out_are_not_words_for_outside():
    raw = base()
    raw["doors"] += [{"key": "D_E", "between": ["CORRIDOR", "EXIT"], "point": [600, 900], "confidence": 0.9},
                     {"key": "D_O", "between": ["CORRIDOR", "OUT"], "point": [600, 800], "confidence": 0.9}]
    salvaged = salvage_draft(raw)
    assert [e.key for e in salvaged.draft.exits] == ["X_W"]
    assert "door D_E: joins unknown or identical room EXIT" in salvaged.dropped
    assert "door D_O: joins unknown or identical room OUT" in salvaged.dropped


def test_an_outside_word_that_was_also_a_room_key_is_that_room():
    raw = base()
    raw["rooms"].append({"key": "OUTSIDE", "name": "Terrace", "kind": "other", "box": [700, 0, 600, 100],
                         "label_point": [650, 50]})                      # unordered box: dropped
    raw["doors"].append({"key": "D_T", "between": ["CORRIDOR", "OUTSIDE"], "point": [600, 50], "confidence": 0.8})
    salvaged = salvage_draft(raw)
    assert [e.key for e in salvaged.draft.exits] == ["X_W"]
    assert "door D_T: joins room OUTSIDE, which was dropped" in salvaged.dropped
    # A real outside word with no such room still becomes an exit.
    raw = base()
    raw["doors"].append({"key": "D_S", "between": ["STREET", "CORRIDOR"], "point": [600, 50], "confidence": 0.8})
    salvaged = salvage_draft(raw)
    assert [(e.key, e.room, e.label) for e in salvaged.draft.exits] == [("X_W", "CORRIDOR", ""),
                                                                      ("D_S", "CORRIDOR", "door to outside")]


def test_keys_that_collide_after_normalising_never_borrow_a_room():
    """Probe: "Office-1" and "office 1" both normalise to OFFICE_1; the second room was dropped but its door and
    exit attached to the first."""
    raw = base()
    raw["rooms"] += [{"key": "Office-1", "name": "Office 1", "kind": "office", "box": [0, 500, 400, 750],
                      "label_point": [200, 600]},
                     {"key": "office 1", "name": "Other office", "kind": "office", "box": [0, 750, 400, 1000],
                      "label_point": [200, 900]}]
    raw["doors"] += [{"key": "D_1", "between": ["Office-1", "CORRIDOR"], "point": [400, 600], "confidence": 0.9},
                     {"key": "D_2", "between": ["office 1", "CORRIDOR"], "point": [400, 900], "confidence": 0.9},
                     {"key": "D_3", "between": ["OFFICE_1", "CORRIDOR"], "point": [400, 700], "confidence": 0.9},
                     {"key": "D_4", "between": ["Office-1", "OUTSIDE"], "point": [0, 600], "confidence": 0.6}]
    raw["exits"] += [{"key": "X_2", "room": "office 1", "point": [0, 900], "confidence": 0.7},
                     {"key": "X_1", "room": "Office-1", "point": [0, 700], "confidence": 0.7}]
    salvaged = salvage_draft(raw)
    assert [r.key for r in salvaged.draft.rooms] == ["CORRIDOR", "OFFICE", "OFFICE_1"]
    assert "room OFFICE_1: duplicate key" in salvaged.dropped
    # Only references spelled exactly like the kept room's key stay with it.
    assert [d.key for d in salvaged.draft.doors] == ["D_OC", "D_1"]
    assert "door D_2: room key 'office 1' is ambiguous (two rooms normalise to OFFICE_1)" in salvaged.dropped
    assert "door D_3: room key 'OFFICE_1' is ambiguous (two rooms normalise to OFFICE_1)" in salvaged.dropped
    assert "exit X_2: room key 'office 1' is ambiguous (two rooms normalise to OFFICE_1)" in salvaged.dropped
    assert [(e.key, e.room) for e in salvaged.draft.exits] == [("X_W", "CORRIDOR"), ("X_1", "OFFICE_1"),
                                                               ("D_4", "OFFICE_1")]


def test_a_repeated_identical_key_makes_every_reference_ambiguous():
    raw = base()
    raw["rooms"].append({"key": "OFFICE", "name": "Office again", "kind": "office", "box": [0, 500, 400, 1000],
                         "label_point": [200, 750]})
    salvaged = salvage_draft(raw)
    assert [r.key for r in salvaged.draft.rooms] == ["CORRIDOR", "OFFICE"]
    assert salvaged.draft.doors == []
    assert "door D_OC: room key 'OFFICE' is ambiguous (two rooms normalise to OFFICE)" in salvaged.dropped


def test_a_clean_reading_still_drops_nothing():
    salvaged = salvage_draft(base())
    assert salvaged.dropped == [] and salvaged.repaired == []
    assert [d.key for d in salvaged.draft.doors] == ["D_OC"] and [e.key for e in salvaged.draft.exits] == ["X_W"]
