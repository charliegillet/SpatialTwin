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


def test_explicit_zero_hints_keep_the_building_empty():
    raw = home_raw()
    for item in raw["rooms"]:
        item["occupants_hint"] = 0
    venue = compile_raw(raw, building_width_m=12).venue
    assert sum(zone.initial_occupants for zone in venue.zones) == 0
