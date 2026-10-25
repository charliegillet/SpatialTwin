import json

import pytest

from backend.app.hazard.door_planner import EXPOSURE_LABEL, DoorPlanError, plan_doors
from tests.venues.conftest import make_request

LOBBY, HALL, EAST, WEST, KITCHEN = (20, 4), (20, 14), (30, 12), (10, 12), (36, 4)


def plan(venue, hazards, **extra):
    return plan_doors(venue, make_request(hazards, **extra))


def doors(r):
    return {d.id: d for d in r.doors}


def exits(r):
    return {e.id: e for e in r.exits}


def test_no_hazard_changes_nothing(venue):
    r = plan(venue, [])
    assert r.chosen.completed_crossings == r.baseline.completed_crossings == r.no_hazard_completed == 125
    assert all(not d.changed and d.decided_by == "default" for d in r.doors)
    assert r.provenance == "local_door_planner_v1" and r.hypothetical is True and r.plan_id.startswith("dp-")
    assert r.chosen.exposure_label == EXPOSURE_LABEL and r.chosen.modeled_exposure_people_seconds == 0
    assert r.lights.px == "FFFFFFFFFFFFggggggFFFBBB"


def test_fire_in_lobby(venue):
    r = plan(venue, [("FIRE", *LOBBY)])
    d, e = doors(r), exits(r)
    assert r.chosen.completed_crossings == 125 and r.baseline.completed_crossings == 96
    for door in ("D1", "D5", "D6"):
        assert d[door].state == "closed" and d[door].lamp == "red" and d[door].entry_denied_into == ["LOBBY"]
        assert d[door].decided_by == "hazard_rule" and d[door].changed
    assert not e["E1"].safe and e["E1"].lamp == "red_x"
    assert d["D9"].state == "open" and d["D9"].decided_by == "door_planner" and "+" in d["D9"].reason
    assert r.chosen.validator_report.is_valid
    assert r.lights.px[:6] == "XXXXXX"
    zone = next(z for z in r.zones if z.id == "LOBBY")
    assert zone.status == "no_entry" and zone.hazard_type == "FIRE" and zone.untenable_at_s == 6


def test_fire_in_hall_opens_servo_door_egress_only(venue):
    r = plan(venue, [("FIRE", *HALL)])
    d4 = doors(r)["D4"]
    assert d4.state == "open" and d4.decided_by == "door_planner" and d4.entry_denied_into == ["HALL"]
    assert "egress only; entry into HALL denied" in d4.reason and d4.lamp == "red"
    assert r.chosen.completed_crossings > r.baseline.completed_crossings
    assert r.lights.px[21:] == "OOO"


def test_smoke_in_hall_slows_and_d4_is_decisive(venue):
    r = plan(venue, [("SMOKE", *HALL)])
    assert doors(r)["D4"].state == "open"
    assert r.chosen.completed_crossings - r.baseline.completed_crossings >= 10
    assert any(route.slowed for route in r.routes)
    assert next(z for z in r.zones if z.id == "HALL").throughput_multiplier == 0.5
    assert r.hazards[0].untenable_s == 12


def test_gas_in_hall_locks_servo_and_switches_nothing(venue):
    r = plan(venue, [("GAS", *HALL)])
    d = doors(r)
    assert d["D4"].locked and d["D4"].state == "closed" and d["D4"].decided_by == "gas_lock" and d["D4"].lamp == "red_static"
    assert not any(x.decided_by == "door_planner" for x in r.doors)
    assert not any(x.changed for x in r.doors)
    assert set(r.lights.held) == {"D1", "D2", "D3", "D4"} and r.lights.px[21:] == "LLL"
    assert any("ventilate to the outside manually; operate no switches nearby" in a for a in r.advisories)
    assert [a.door_states for a in r.alternatives][0].keys() == {"D9"}  # D4 is not in the free set


def test_gas_in_kitchen_holds_exit_free_zone_lamp(venue):
    r = plan(venue, [("GAS", *KITCHEN)])
    assert r.lights.held == ["D8"] and doors(r)["D8"].lamp == "red_static" and not doors(r)["D8"].locked


def test_chemical_confines_and_closes_exits(venue):
    r = plan(venue, [("CHEMICAL", *EAST)])
    d = doors(r)
    for door in ("D3", "D6"):  # hold-open fire/smoke doors are released
        assert d[door].state == "closed" and d[door].entry_denied_into == ["EAST_CORR"] and d[door].lamp == "red"
    # an indicator-only door cannot be switched: it keeps its state, shows red, and entry is still denied
    assert d["D8"].state == "open" and d["D8"].lamp == "red" and d["D8"].entry_denied_into == ["EAST_CORR"]
    assert next(z for z in r.zones if z.id == "EAST_CORR").hazard_type == "CHEMICAL"
    assert any("deny entry" in a for a in r.advisories)
    assert d["D9"].state == "closed"  # opening the dock door would only feed the contaminated corridor


def test_water_slows_without_changing_doors(venue):
    r = plan(venue, [("WATER", *WEST)])
    assert not any(d.changed and d.decided_by == "hazard_rule" for d in r.doors)
    assert all(d.entry_denied_into == [] for d in r.doors)
    assert next(z for z in r.zones if z.id == "WEST_CORR").status == "slowed"
    assert any(route.slowed for route in r.routes)
    assert r.hazards[0].untenable_s is None


def test_precedence_gas_lock_survives_fire(venue):
    r = plan(venue, [("FIRE", *HALL), ("GAS", 22, 12)])
    assert [h.effective for h in r.hazards] == [True, False]
    assert next(z for z in r.zones if z.id == "HALL").hazard_type == "FIRE"
    assert doors(r)["D4"].locked and doors(r)["D4"].decided_by == "gas_lock"
    assert doors(r)["D1"].lamp == "red_static" and doors(r)["D1"].state == "open"  # gas holds, fire does not release
    assert exits(r)["E1"].safe


def test_precedence_fire_over_smoke_and_water(venue):
    r = plan(venue, [("WATER", *LOBBY), ("SMOKE", 22, 6), ("FIRE", 18, 2)])
    assert [h.effective for h in r.hazards] == [False, False, True]
    assert next(z for z in r.zones if z.id == "LOBBY").hazard_type == "FIRE"
    assert next(z for z in r.zones if z.id == "LOBBY").untenable_at_s == 6


def test_hazards_in_two_zones_combine(venue):
    r = plan(venue, [("SMOKE", *HALL, {"untenable_s": 8}), ("FIRE", *LOBBY, {"untenable_s": 4})])
    assert r.chosen.validator_report.is_valid
    assert {z.id: z.untenable_at_s for z in r.zones if z.untenable_at_s} == {"HALL": 8, "LOBBY": 4}


def test_stranded_people_are_reported_with_cause(venue):
    r = plan(venue, [("FIRE", *HALL, {"untenable_s": 0})])
    assert r.chosen.remaining_population >= 80
    assert any("remain in Hall" in a and "not an intended one" in a for a in r.advisories)
    assert r.chosen.status == "PARTIAL_WITHIN_HORIZON"


def test_ranking_and_alternatives(venue):
    r = plan(venue, [("FIRE", *HALL)])
    ranks = [a.rank for a in r.alternatives]
    assert ranks == list(range(1, len(ranks) + 1)) and len(r.alternatives) == 4
    scores = [(not a.is_valid, -a.completed_crossings, a.modeled_exposure_people_seconds) for a in r.alternatives]
    assert scores == sorted(scores)
    assert r.alternatives[0].run_id == r.chosen.run_id
    assert next(a for a in r.alternatives if not any(v == "open" for v in a.door_states.values())).completed_crossings \
        == r.baseline.completed_crossings


def test_deterministic_apart_from_ids_and_timings(venue):
    def stable(r):
        data = json.loads(r.model_dump_json())
        for key in ("plan_id", "timings_ms"):
            data.pop(key)
        data["chosen"].pop("run_id"); data["baseline"].pop("run_id")
        for a in data["alternatives"]:
            a.pop("run_id")
        return data
    first = stable(plan(venue, [("FIRE", *HALL), ("WATER", *WEST)]))
    assert first == stable(plan(venue, [("FIRE", *HALL), ("WATER", *WEST)]))


def test_routes_account_for_every_completed_person(venue):
    r = plan(venue, [("FIRE", *LOBBY)])
    assert sum(route.people for route in r.routes) == r.chosen.completed_crossings
    for route in r.routes:
        assert len(route.via_doors) == len(route.path) - 1 and len(set(route.path)) == len(route.path)
    assert [x.people for x in r.routes] == sorted((x.people for x in r.routes), reverse=True)


def test_every_frame_conserves(venue):
    r = plan(venue, [("SMOKE", *HALL), ("WATER", *WEST)])
    for f in r.chosen.timeline:
        assert sum(f.occupancy.values()) + f.in_transit + f.total_completed == 125


@pytest.mark.parametrize("hazards, extra, code", [
    ([("FIRE", *LOBBY)] * 7, {}, "too_many_hazards"),
    ([("FIRE", *LOBBY)], {"horizon_seconds": 9}, "invalid_horizon"),
    ([("FIRE", *LOBBY)], {"horizon_seconds": 130}, "invalid_horizon"),
    ([("FIRE", *LOBBY)], {"horizon_seconds": 41}, "invalid_horizon"),
    ([("FIRE", 100, 100)], {}, "outside_building"),
    ([("FIRE", *LOBBY, {"zone_id": "HALL"})], {}, "zone_mismatch"),
    ([("FIRE", *LOBBY, {"untenable_s": 5})], {}, "invalid_untenable_time"),
    ([("FIRE", *LOBBY, {"untenable_s": 40})], {}, "invalid_untenable_time"),
    ([("FIRE", *LOBBY, {"untenable_s": -2})], {}, "invalid_untenable_time"),
])
def test_validation_codes(venue, hazards, extra, code):
    with pytest.raises(DoorPlanError) as error:
        plan(venue, hazards, **extra)
    assert error.value.code == code


def test_duplicate_hazard_id(venue):
    from backend.app.venues.schemas import DoorPlanRequest
    req = DoorPlanRequest(hazards=[{"id": "a", "type": "FIRE", "position": {"x": 20, "y": 4}, "source": "simulated"},
                                   {"id": "a", "type": "SMOKE", "position": {"x": 20, "y": 14}, "source": "simulated"}])
    with pytest.raises(DoorPlanError) as error:
        plan_doors(venue, req)
    assert error.value.code == "duplicate_hazard_id"


def test_shared_wall_point_resolves_to_first_zone(venue):
    r = plan(venue, [("FIRE", 20, 8)])
    assert r.hazards[0].zone_id == "HALL"


def test_short_horizon_caps_default_untenable(venue):
    r = plan(venue, [("SMOKE", *HALL)], horizon_seconds=10)
    assert r.hazards[0].untenable_s == 8 and r.chosen.validator_report.is_valid


def test_door_plan_is_fast_once_warm(venue):
    import time
    plan(venue, [("FIRE", *LOBBY)])
    start = time.perf_counter()
    plan(venue, [("FIRE", *HALL), ("WATER", *WEST), ("SMOKE", *EAST)])
    assert (time.perf_counter() - start) * 1000 < 1000
