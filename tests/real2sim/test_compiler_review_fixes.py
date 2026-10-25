"""Regression tests for review findings on the compiler: unique renamed room ids and explicit zero occupancy."""
from backend.app.venues.graph_checks import errors_in, check_venue
from tests.real2sim.test_compiler import compile_raw, home_raw


def test_renamed_rooms_never_collide_with_other_rooms():
    raw = home_raw()
    # "D1" collides with the first generated door id; a room literally called "Z_D1" already exists.
    renames = {"LIVING": "D1", "KITCHEN": "Z_D1"}
    for item in raw["rooms"]:
        item["key"] = renames.get(item["key"], item["key"])
    for item in raw["doors"]:
        item["between"] = [renames.get(key, key) for key in item["between"]]
    for item in raw["exits"]:
        item["room"] = renames.get(item["room"], item["room"])
    result = compile_raw(raw, building_width_m=12)
    assert result.error is None and result.venue is not None
    ids = [zone.id for zone in result.venue.zones]
    assert len(ids) == len(set(ids)) and "Z_D1" in ids and "Z2_D1" in ids
    assert errors_in(check_venue(result.venue)) == []


def test_voids_frame_the_plan_but_are_not_floor():
    """An OPEN TO BELOW area is drawn but not walkable: it never becomes a zone and openings into it are dropped."""
    raw = home_raw()
    raw["rooms"].append({"key": "ATRIUM", "name": "OPEN TO BELOW", "kind": "void", "box": [100, 900, 500, 990],
                         "label_point": [300, 945]})
    raw["doors"].append({"key": "DKA", "between": ["KITCHEN", "ATRIUM"], "point": [300, 900], "width_m": None,
                         "symbol": "opening", "confidence": 0.5})
    result = compile_raw(raw, building_width_m=12)
    assert result.error is None
    assert "ATRIUM" not in {zone.id for zone in result.venue.zones}
    assert "door DKA: opens onto a void" in result.report.dropped
    assert any("ATRIUM: open to below" in edit for edit in result.report.edits)
    assert errors_in(check_venue(result.venue)) == []


def test_an_interior_exit_stair_core_is_kept():
    """Upper floors exit through stair cores inside the floor plate (live Ferry Building reading, 26 Oct 2026).

    The stair is the way down inside the core, not a gap in a wall: it is placed inside the room, and the whole venue
    is clean (no error of any kind, not only the stair and exit codes)."""
    raw = home_raw()
    # Carve a stair core out of the middle of the hall's north side: it touches no outside wall.
    raw["rooms"][2]["box"] = [500, 100, 600, 900]
    raw["rooms"].append({"key": "STAIR_CORE", "name": "Exit stair", "kind": "stair", "box": [420, 450, 500, 550],
                         "label_point": [460, 500]})
    raw["rooms"][0]["box"] = [100, 100, 500, 450]
    raw["rooms"][1]["box"] = [100, 550, 500, 900]
    raw["rooms"].append({"key": "MID", "name": "Middle", "kind": "room", "box": [100, 450, 420, 550],
                         "label_point": [260, 500]})
    raw["doors"] = [d for d in raw["doors"] if d["key"] != "DLK"] + [
        {"key": "DSH", "between": ["STAIR_CORE", "HALL"], "point": [500, 500], "width_m": None, "symbol": "swing",
         "confidence": 0.9},
        {"key": "DML", "between": ["MID", "LIVING"], "point": [260, 450], "width_m": None, "symbol": "swing",
         "confidence": 0.9}]
    # Drawn on the wall the core shares with MID: as a wall opening it would cut into MID.
    raw["exits"].append({"key": "STAIRX", "room": "STAIR_CORE", "point": [420, 500], "width_m": None, "kind": "stair",
                         "confidence": 0.9})
    result = compile_raw(raw, building_width_m=12)
    stair_exit = next(e for e in result.venue.exits if e.zone == "STAIR_CORE")
    assert stair_exit.kind == "stair"
    # The drawn point is on the wall (no clearance), so the core's label point (6.0, 6.6) m is used.
    assert stair_exit.position == (6.0, 6.6)
    assert "exit STAIRX: exit stair; placed inside STAIR_CORE at (6, 6.6) m (room label point), not in a wall" in \
        result.report.edits
    assert check_venue(result.venue) == []


def test_explicit_zero_hints_keep_the_building_empty():
    raw = home_raw()
    for item in raw["rooms"]:
        item["occupants_hint"] = 0
    venue = compile_raw(raw, building_width_m=12).venue
    assert sum(zone.initial_occupants for zone in venue.zones) == 0
