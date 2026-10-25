"""Graph checks decide whether a venue Gemini proposed can be planned and drawn."""
import copy
import json
from pathlib import Path

import pytest

from backend.app.venues.graph_checks import check_venue, errors_in
from backend.app.venues.model import VenueV2, load_building_v2

HOME = json.loads((Path(__file__).parent / "fixtures" / "home_flat.json").read_text())


def codes(raw: dict) -> set:
    return {issue.code for issue in check_venue(VenueV2.model_validate(raw))}


def test_shipped_and_hand_written_venues_are_clean():
    assert check_venue(load_building_v2()) == []
    assert check_venue(VenueV2.model_validate(HOME)) == []


@pytest.mark.parametrize("mutate, code", [
    (lambda v: v["doors"][0].update(position=[3, 4]), "door_off_shared_wall"),
    (lambda v: v["exits"][0].update(position=[3, 5]), "exit_not_on_outside_wall"),
    (lambda v: v["zones"][1].update(polygon=[[6, 0], [12, 0], [12, 5], [6, 5]]), "rooms_overlap"),
    (lambda v: v["zones"][0].update(initial_occupants=11), "over_capacity"),
    (lambda v: v["doors"][0].update(width=7.0), "unusual_width"),
    (lambda v: [d.update(default_state="closed", planner_can_open=True) for d in v["doors"][:4]], "too_many_controllable_doors"),
    (lambda v: v["zones"][2].update(polygon=[[0, 5], [12, 5], [11, 6], [0, 6]]), "non_rectilinear_room"),
    (lambda v: [z.update(initial_occupants=0) for z in v["zones"]], "no_occupants"),
])
def test_each_defect_is_reported(mutate, code):
    raw = copy.deepcopy(HOME)
    mutate(raw)
    assert code in codes(raw)


@pytest.mark.parametrize("mutate, code", [
    # D1 is wider than the 7 m of wall Living and the Hall share.
    (lambda v: v["doors"][0].update(width=8.0), "door_wider_than_shared_wall"),
    # D1 centred on Living's corner (7, 5): half the opening would cut into the Kitchen's wall.
    (lambda v: v["doors"][0].update(position=[7, 5]), "door_wider_than_shared_wall"),
    # A 0.1 m-wide room lying entirely inside the Kitchen.
    (lambda v: v["zones"].append({"id": "SLIVER", "name": "Sliver", "max_capacity": 1, "initial_occupants": 0,
                                  "polygon": [[8, 1], [8.1, 1], [8.1, 4], [8, 4]]}), "rooms_overlap"),
    (lambda v: v["zones"][1].update(polygon=[[7, 0], [13, 0], [13, 5], [7, 5]]), "room_outside_extent"),
    (lambda v: v["exits"][0].update(width=6.0), "exit_wider_than_outside_wall"),
    (lambda v: v["led_map"].update(E1=[0, 120]), "light_strip_too_long"),
])
def test_review_false_negatives_are_caught(mutate, code):
    raw = copy.deepcopy(HOME)
    mutate(raw)
    assert code in codes(raw)


def test_a_door_nobody_can_open_does_not_count_as_a_path():
    raw = copy.deepcopy(HOME)
    # Bedroom 1's only usable ways out: D3 (to the hall) and the window E3. Close D3 for good and drop the window.
    raw["doors"][2].update(default_state="closed", planner_can_open=False)
    raw["exits"] = [e for e in raw["exits"] if e["id"] != "E3"]
    raw["led_map"].pop("E3")
    unreachable = [i for i in check_venue(VenueV2.model_validate(raw)) if i.code == "room_unreachable"]
    assert [i.element_ids for i in unreachable] == [("BED_1",)]


def test_unreachable_room():
    raw = copy.deepcopy(HOME)
    raw["doors"] = [d for d in raw["doors"] if d["id"] != "D3"]
    raw["exits"] = [e for e in raw["exits"] if e["id"] != "E3"]
    raw["led_map"].pop("E3")
    issues = check_venue(VenueV2.model_validate(raw))
    unreachable = [i for i in issues if i.code == "room_unreachable"]
    assert [i.element_ids for i in unreachable] == [("BED_1",)]
    assert unreachable[0].severity == "error" and errors_in(issues) == unreachable


def test_issue_json_shape():
    raw = copy.deepcopy(HOME)
    raw["doors"][0]["position"] = [3, 4]
    data = check_venue(VenueV2.model_validate(raw))[0].to_json()
    assert data == {"code": "door_off_shared_wall", "severity": "error",
                    "message": "D1 is not on a wall shared by Living room and Hall.", "element_ids": ["D1"]}
