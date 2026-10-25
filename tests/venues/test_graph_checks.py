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
