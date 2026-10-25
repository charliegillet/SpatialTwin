"""Interior exit stairs and voids (devil's-advocate review, 26 Oct 2026).

An exit stair with no outside wall is placed inside its room, never on a wall it shares with another room, and only
in circulation space. A wall facing an OPEN TO BELOW void (or a drawn box the compiler could not attach) is not an
outside wall, so no exit is placed on it.
"""
import pytest

from backend.app.hazard.door_planner import plan_doors
from backend.app.venues.graph_checks import check_venue, errors_in
from backend.app.venues.model import point_in_polygon
from backend.app.venues.schemas import DoorPlanRequest
from tests.real2sim.test_compiler import compile_raw, door, exit_, home_raw, room


def core_raw(core_kind="stair", exit_kind="stair", exit_point=(420, 500), label=(460, 500), mid_kind="room"):
    """home_raw with an enclosed 1.5 x 1.2 m core (x 5.25-6.75, y 6.0-7.2 m) between Living, Middle, Kitchen and the
    hall: it has no outside wall. At 12 m wide, one draft unit is 0.015 m."""
    raw = home_raw()
    raw["rooms"][0]["box"] = [100, 100, 500, 450]
    raw["rooms"][1]["box"] = [100, 550, 500, 900]
    raw["rooms"].append({"key": "CORE", "name": "Core", "kind": core_kind, "box": [420, 450, 500, 550],
                         "label_point": list(label)})
    raw["rooms"].append(room("MID", [100, 450, 420, 550], mid_kind, name="Middle"))
    raw["doors"] = [d for d in raw["doors"] if d["key"] != "DLK"] + [door("DCH", "CORE", "HALL", [500, 500])]
    if mid_kind != "void":
        raw["doors"].append(door("DML", "MID", "LIVING", [260, 450]))
    raw["exits"].append(exit_("CX", "CORE", list(exit_point), kind=exit_kind))
    return raw


def core_exit(result):
    return next((e for e in result.venue.exits if e.zone == "CORE"), None)


def on_any_door(venue, position):
    return any(abs(d.position[0] - position[0]) < 1e-6 and abs(d.position[1] - position[1]) < 1e-6
               for d in venue.doors)


@pytest.mark.parametrize("core_kind", ["office", "room", "bedroom", "hall", "kitchen"])
def test_a_stair_exit_in_a_non_circulation_room_is_dropped(core_kind):
    """Probe: an enclosed office with a "stair" exit compiled clean and the exit landed on a door."""
    result = compile_raw(core_raw(core_kind), building_width_m=12)
    assert result.error is None
    assert core_exit(result) is None
    assert (f"exit CX: an exit stair in CORE ({core_kind}); an interior exit stair must be in a stair, lobby or "
            "corridor; dropped") in result.report.dropped
    assert not any(on_any_door(result.venue, e.position) for e in result.venue.exits)
    assert check_venue(result.venue) == []


def test_a_stair_exit_is_dropped_from_an_office_even_with_an_outside_wall():
    """A stair is never turned into a facade door: in a room that cannot hold a stair, it is dropped."""
    raw = home_raw()
    raw["rooms"][0]["kind"] = "office"
    raw["exits"][0]["kind"] = "stair"                      # FRONT, drawn on Living's west outside wall
    result = compile_raw(raw, building_width_m=12)
    assert {e.zone for e in result.venue.exits} == {"KITCHEN", "BED_1"}
    assert ("exit FRONT: an exit stair in LIVING (office); an interior exit stair must be in a stair, lobby or "
            "corridor; dropped") in result.report.dropped


@pytest.mark.parametrize("core_kind, exit_kind, why", [
    ("stair", "door", "stair room with no outside wall"), ("stair", "stair", "exit stair"),
    ("lobby", "stair", "exit stair"), ("corridor", "stair", "exit stair")])
def test_a_stair_in_circulation_space_is_placed_inside(core_kind, exit_kind, why):
    """A stair exit in a stair room, lobby or corridor, or any exit of an enclosed stair room, is inside its room."""
    # Drawn well inside (6.0, 6.6) m; the label point (6.3, 6.9) m is too near the north wall.
    result = compile_raw(core_raw(core_kind, exit_kind, exit_point=(460, 500), label=(440, 520)), building_width_m=12)
    stair = core_exit(result)
    assert stair is not None and stair.kind == "stair" and stair.position == (6.0, 6.6)
    zone = next(z for z in result.venue.zones if z.id == "CORE")
    assert point_in_polygon(*stair.position, zone.polygon)
    assert f"exit CX: {why}; placed inside CORE at (6, 6.6) m (drawn point), not in a wall" in result.report.edits
    assert check_venue(result.venue) == []
    plan = plan_doors(result.venue, DoorPlanRequest(hazards=[]))
    assert plan.chosen.validator_report.is_valid


def test_interior_point_falls_back_to_the_room_centre():
    # Drawn on the core's north wall, label point on its north-west corner: neither is clear of the walls.
    result = compile_raw(core_raw(exit_point=(420, 500), label=(420, 450)), building_width_m=12)
    assert core_exit(result).position == (6.0, 6.6)
    assert any(edit.endswith("(room centre), not in a wall") for edit in result.report.edits)
    assert check_venue(result.venue) == []


def test_an_interior_stair_with_no_clear_point_is_dropped():
    raw = core_raw(exit_point=(480, 520), label=(440, 470))
    # An L of two 0.6 m strips: no point is 0.5 m from every wall and the box centre (6.0, 6.6) lies on a wall.
    core = next(r for r in raw["rooms"] if r["key"] == "CORE")
    core.update(box=[420, 450, 500, 490], extra_boxes=[[460, 490, 500, 550]])
    raw["rooms"].append(room("NOOK", [420, 490, 460, 550], "storage"))      # fills the L's corner: still enclosed
    raw["doors"].append(door("DMN", "MID", "NOOK", [420, 520]))
    result = compile_raw(raw, building_width_m=12)
    assert core_exit(result) is None
    assert "exit CX: no point inside CORE clear of its walls for the interior exit stair; dropped" in \
        result.report.dropped


def test_a_stair_exit_goes_inside_even_when_its_room_has_an_outside_wall():
    """On an upper floor a stair drawn as a facade door is an exit into the air: a stair exit skips the outside-wall
    search. Door and window exits still use it."""
    raw = home_raw()
    raw["rooms"][0]["kind"] = "stair"
    raw["rooms"][1]["kind"] = "lobby"
    raw["exits"][0]["kind"] = "stair"                      # FRONT, drawn on the west outside wall of Living
    result = compile_raw(raw, building_width_m=12)          # BACK stays a door exit of the (lobby) kitchen
    exits = {e.zone: e for e in result.venue.exits}
    living = next(z for z in result.venue.zones if z.id == "LIVING")
    # The drawn point is on the wall, so the room's label point (3, 9) m: inside, never in the facade.
    assert exits["LIVING"].kind == "stair" and exits["LIVING"].position == (3.0, 9.0)
    assert point_in_polygon(*exits["LIVING"].position, living.polygon)
    assert "exit FRONT: exit stair; placed inside LIVING at (3, 9) m (room label point), not in a wall" in \
        result.report.edits
    assert exits["KITCHEN"].kind == "door" and exits["KITCHEN"].position[0] == 12.0
    assert check_venue(result.venue) == []


def test_an_exit_facing_a_void_is_not_placed_there():
    """Probe: the kitchen exit landed on the atrium wall with no error, because voids were removed first."""
    raw = home_raw()
    raw["rooms"][1]["box"] = [100, 500, 500, 800]          # Kitchen ends at x = 10.5 m ...
    raw["rooms"].append({"key": "ATRIUM", "name": "OPEN TO BELOW", "kind": "void", "box": [100, 800, 500, 900],
                         "label_point": [300, 850]})       # ... and the atrium fills x 10.5-12 m beside it
    raw["exits"][1]["point"] = [300, 800]                  # drawn on the kitchen's atrium wall
    result = compile_raw(raw, building_width_m=12)
    back = next(e for e in result.venue.exits if e.zone == "KITCHEN")
    assert back.position == (10.05, 12.0)                  # on the kitchen's north wall instead
    assert "exit BACK: the wall of KITCHEN nearest its point faces void ATRIUM (drawn, not outside); not used as " \
           "an outside wall" in result.report.edits
    assert check_venue(result.venue) == []


def test_a_stair_core_whose_only_free_wall_faces_a_void_goes_inside():
    # A door exit of a stair room looks for an outside wall first; the atrium-facing wall does not count.
    result = compile_raw(core_raw(exit_kind="door", mid_kind="void"), building_width_m=12)
    stair = core_exit(result)
    assert stair is not None and stair.kind == "stair" and stair.position == (6.0, 6.6)
    assert any(edit.startswith("exit CX: the wall of CORE nearest its point faces void MID") for edit in
               result.report.edits)
    assert errors_in(check_venue(result.venue)) == []


def test_a_void_on_the_west_edge_keeps_the_rooms_offset_and_blocks_exits():
    """The void frames the drawing: the rooms start east of it (no hidden shift) and its wall is not outside."""
    raw = home_raw()
    raw["rooms"].append({"key": "LIGHTWELL", "name": "Light well", "kind": "void", "box": [100, 0, 900, 100],
                         "label_point": [500, 50]})
    result = compile_raw(raw, building_width_m=12)                # 900 units wide: 1 unit = 0.01333 m
    venue = result.venue
    assert min(p[0] for z in venue.zones for p in z.polygon) == 1.3 and venue.extent[0] == 12.0
    assert all(abs(e.position[0] - 1.3) > 1e-6 for e in venue.exits)
    assert {e.zone for e in venue.exits} == {"LIVING", "KITCHEN", "BED_1"}
    assert check_venue(venue) == []
