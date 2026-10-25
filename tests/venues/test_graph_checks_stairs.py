"""Graph checks for interior exit stairs and for exits that share a gap with a door (review, 26 Oct 2026)."""
import copy
import json
from pathlib import Path

import pytest

from backend.app.venues.graph_checks import check_venue, errors_in
from backend.app.venues.model import VenueV2, load_building_v2

HOME = json.loads((Path(__file__).parent / "fixtures" / "home_flat.json").read_text())


def issues(raw: dict):
    return check_venue(VenueV2.model_validate(raw))


def home_with(**exit_fields) -> dict:
    """home_flat with E1 (Living's west-wall exit) changed."""
    raw = copy.deepcopy(HOME)
    raw["exits"][0].update(exit_fields)
    return raw


def test_an_interior_stair_inside_its_room_is_clean():
    # Living is 7 x 5 m; a stair exit at its middle is the way down, and every other check (reachability, overlap,
    # opening fit) still holds with no wall opening for it.
    assert issues(home_with(kind="stair", position=[3.5, 2.5])) == []


@pytest.mark.parametrize("position, why", [
    ([0, 2.5], "on Living's outside wall"),
    ([3, 5], "on the wall Living shares with the hall, at door D1"),
    ([7, 0], "on a corner"),
    ([9.5, 2.5], "inside the kitchen, not its own room"),
    ([20, 2.5], "outside the building"),
])
def test_a_stair_exit_not_strictly_inside_its_room_is_an_error(position, why):
    found = [i for i in errors_in(issues(home_with(kind="stair", position=position)))
             if i.code == "stair_exit_not_inside_its_room"]
    assert [i.element_ids for i in found] == [("E1",)], why
    assert found[0].message == "E1 is an exit stair but is not inside its room Living room."


def test_the_old_stair_wall_code_is_gone():
    codes = {i.code for i in issues(home_with(kind="stair", position=[3, 5]))}
    assert "exit_off_its_stair_wall" not in codes and "exit_overlaps_door" not in codes


def test_a_wall_exit_on_a_door_is_an_error():
    """Probe: a stair exit landed exactly on door D6; any wall exit sharing a door's gap is refused."""
    found = [i for i in issues(home_with(position=[3, 5])) if i.code == "exit_overlaps_door"]
    assert [(i.severity, i.element_ids) for i in found] == [("error", ("E1", "D1"))]
    assert found[0].message == "E1 overlaps door D1 on the same wall."


@pytest.mark.parametrize("x, overlaps", [(3.0, True), (3.85, True), (3.9, False), (2.1, False), (5.0, False)])
def test_exit_door_overlap_is_the_gap_interval(x, overlaps):
    # D1 is 0.9 m at (3, 5): its gap is 2.55-3.45. A 0.9 m exit at x spans x-0.45..x+0.45; touching is not overlap.
    codes = [i.code for i in issues(home_with(position=[x, 5]))]
    assert ("exit_overlaps_door" in codes) is overlaps


def test_shipped_venues_have_no_exit_door_overlap():
    assert issues(copy.deepcopy(HOME)) == []
    assert check_venue(load_building_v2()) == []
