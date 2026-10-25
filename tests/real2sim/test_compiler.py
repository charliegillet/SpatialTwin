"""The deterministic draft -> VenueV2 compiler: geometry, scale, doors, exits, occupants, determinism."""
import json

import pytest

from backend.app.ai.real2sim.schema import SourceImage, VenueDraftV1
from backend.app.hazard.door_planner import plan_doors
from backend.app.venues.compiler import compile_draft
from backend.app.venues.graph_checks import check_venue, errors_in
from backend.app.venues.schemas import DoorPlanRequest

IMG = SourceImage(1000, 1000, "0" * 64)
WIDE = SourceImage(2000, 1000, "1" * 64)


def room(key, box, kind="room", name=None, **extra):
    ymin, xmin, ymax, xmax = box
    return {"key": key, "name": name or key.title(), "kind": kind, "box": box,
            "label_point": [(ymin + ymax) // 2, (xmin + xmax) // 2], **extra}


def door(key, a, b, point, width=None, symbol="swing"):
    return {"key": key, "between": [a, b], "point": point, "width_m": width, "symbol": symbol, "confidence": 0.9}


def exit_(key, room_key, point, width=None, kind="door"):
    return {"key": key, "room": room_key, "point": point, "width_m": width, "kind": kind, "confidence": 0.9}


def make(rooms, doors, exits, kind="sketch", scale=None, **extra):
    return VenueDraftV1.model_validate({"schema_version": "draft-1", "image_kind": kind,
                                        "scale": scale or {"basis": "unknown"},
                                        "rooms": rooms, "doors": doors, "exits": exits, **extra})


def home_raw():
    """Living and kitchen over a hall over two bedrooms: the shape of tests/venues/fixtures/home_flat.json."""
    return {
        "rooms": [room("LIVING", [100, 100, 500, 500]), room("KITCHEN", [100, 500, 500, 900]),
                  room("HALL", [500, 100, 600, 900], "corridor"), room("BED_1", [600, 100, 900, 500], "bedroom"),
                  room("BED_2", [600, 500, 900, 900], "bedroom")],
        "doors": [door("DL", "LIVING", "HALL", [500, 300]), door("DK", "KITCHEN", "HALL", [500, 700]),
                  door("DB1", "BED_1", "HALL", [600, 300]), door("DB2", "BED_2", "HALL", [600, 700]),
                  door("DLK", "LIVING", "KITCHEN", [300, 500])],
        "exits": [exit_("FRONT", "LIVING", [300, 100]), exit_("BACK", "KITCHEN", [300, 900]),
                  exit_("WIN", "BED_1", [750, 100], kind="window")],
    }


def build(raw, **kw):
    return make(raw["rooms"], raw["doors"], raw["exits"], **kw)


def compile_raw(raw, image=IMG, **kw):
    kw.setdefault("venue_id", "home-test")
    return compile_draft(build(raw), image, **kw)


def compile_home(**kw):
    return compile_raw(home_raw(), **kw)


def test_home_compiles_clean_and_plans():
    result = compile_home(building_width_m=12)
    assert result.error is None and result.venue is not None
    assert check_venue(result.venue) == []
    plan = plan_doors(result.venue, DoorPlanRequest(hazards=[
        {"id": "h1", "type": "FIRE", "position": {"x": 3, "y": 6}, "source": "simulated"}]))
    assert plan.chosen.validator_report.is_valid
    assert result.venue.units == "m" and result.venue.schema_version == "2.0.0"
    assert result.venue.geometry_revision.startswith("geom-") and len(result.venue.geometry_revision) == 21


def test_axes_are_flipped_and_origin_is_south_west():
    venue = compile_home(building_width_m=8).venue
    zones = {z.id: z for z in venue.zones}
    assert min(p[0] for z in venue.zones for p in z.polygon) == 0
    assert min(p[1] for z in venue.zones for p in z.polygon) == 0
    assert max(p[1] for p in zones["LIVING"].polygon) > max(p[1] for p in zones["BED_1"].polygon)   # drawn higher -> north
    assert max(p[0] for p in zones["KITCHEN"].polygon) == venue.extent[0] == pytest.approx(8.0)


def test_scale_priority_operator_then_reference_then_default():
    ref = {"basis": "dimension_label", "a": [950, 100], "b": [950, 900], "metres": 16.0}
    draft = build(home_raw(), scale=ref)
    by_ref = compile_draft(draft, IMG, venue_id="home-test")
    assert by_ref.report.scale_basis == "dimension_label"
    assert by_ref.venue.extent[0] == pytest.approx(16.0)
    by_operator = compile_draft(draft, IMG, venue_id="home-test", building_width_m=10)
    assert by_operator.report.scale_basis == "operator_input" and by_operator.venue.extent[0] == pytest.approx(10.0)
    by_default = compile_home()
    assert by_default.report.scale_basis == "default_width" and by_default.venue.extent[0] == pytest.approx(12.0)
    assert any("assumed building width 12 m" in line for line in by_default.report.defaults)
    assert by_default.report.metres_per_px == pytest.approx(12.0 / 800)


def test_non_square_image_converts_through_pixels():
    # the drawing spans 1600 x 800 px on the wide image: 12 m across means 6 m tall, not 12
    wide = compile_home(image=WIDE, building_width_m=12).venue
    assert wide.extent[0] == pytest.approx(12.0) and wide.extent[1] == pytest.approx(6.0)
    assert compile_home(building_width_m=12).venue.extent[1] == pytest.approx(12.0)


def test_implausible_reference_is_ignored_with_a_reason():
    ref = {"basis": "scale_bar", "a": [950, 100], "b": [950, 101], "metres": 400.0}
    result = compile_draft(build(home_raw(), scale=ref), IMG, venue_id="home-test")
    assert result.report.scale_basis == "default_width"
    assert any(d.startswith("scale reference") for d in result.report.dropped)


def test_determinism():
    a, b = compile_home(building_width_m=12), compile_home(building_width_m=12)
    assert json.dumps(a.venue.to_json(), sort_keys=True) == json.dumps(b.venue.to_json(), sort_keys=True)
    assert a.venue.geometry_revision == b.venue.geometry_revision
    assert compile_home(building_width_m=13).venue.geometry_revision != a.venue.geometry_revision


def test_ids_and_report_maps():
    result = compile_home(building_width_m=12)
    ids = result.report.element_ids
    assert [d.id for d in result.venue.doors] == ["D1", "D2", "D3", "D4", "D5"]
    assert [e.id for e in result.venue.exits] == ["E1", "E2", "E3"]
    assert ids["DL"] == "D1" and ids["WIN"] == "E3" and ids["LIVING"] == "LIVING"
    assert result.report.evidence_points["D1"] == (500, 300) and result.report.evidence_points["E2"] == (300, 900)
    assert result.report.evidence_points["LIVING"] == (300, 300)


def test_zone_key_colliding_with_generated_id_is_prefixed():
    raw = home_raw()
    raw["rooms"][0]["key"] = "D1"
    raw["doors"][0]["between"] = ["D1", "HALL"]
    raw["doors"][4]["between"] = ["D1", "KITCHEN"]
    raw["exits"][0]["room"] = "D1"
    result = compile_raw(raw, building_width_m=12)
    assert result.venue.zones[0].id == "Z_D1" and result.report.element_ids["D1"] == "Z_D1"
    assert check_venue(result.venue) == []


def test_controllable_doors_and_kinds():
    raw = home_raw()
    raw["doors"][0]["symbol"] = "fire_door"
    raw["doors"][4]["symbol"] = "opening"
    result = compile_raw(raw, building_width_m=12, controllable_doors=["DK", "DB2", "NOPE"])
    doors = {d.id: d for d in result.venue.doors}
    assert (doors["D2"].default_state, doors["D2"].planner_can_open, doors["D2"].actuation) == ("closed", True, "motorized")
    assert doors["D4"].planner_can_open and doors["D4"].default_state == "closed"
    assert (doors["D1"].kind, doors["D1"].actuation, doors["D1"].default_state) == ("fire_door", "hold_open", "open")
    assert (doors["D5"].kind, doors["D5"].actuation) == ("opening", "fixed")
    assert (doors["D3"].kind, doors["D3"].actuation, doors["D3"].planner_can_open) == ("room_door", "indicator_only", False)
    assert any(d.startswith("controllable NOPE") for d in result.report.dropped)
    assert set(result.venue.led_map) == {"E1", "E2", "E3", "D2", "D4"}
    assert result.venue.led_map["E1"] == (0, 2) and result.venue.led_map["D4"] == (12, 14)
    assert check_venue(result.venue) == []


def test_too_many_controllable_doors_is_left_to_graph_checks():
    result = compile_home(building_width_m=12, controllable_doors=["DL", "DK", "DB1", "DB2"])
    assert result.venue is not None
    assert [i.code for i in errors_in(check_venue(result.venue))] == ["too_many_controllable_doors"]


def test_parallel_doors_are_merged():
    raw = home_raw()
    raw["doors"].append(door("DL2", "LIVING", "HALL", [500, 400], width=1.0))
    raw["doors"][0]["width_m"] = 0.8
    result = compile_raw(raw, building_width_m=12)
    assert len(result.venue.doors) == 5
    merged = result.venue.door_between("LIVING", "HALL")
    assert merged.width == pytest.approx(1.8) and result.report.element_ids["DL"] == result.report.element_ids["DL2"]
    assert any("merged parallel doors DL and DL2" in e for e in result.report.edits)
    assert check_venue(result.venue) == []


def test_door_between_non_adjacent_rooms_is_dropped():
    raw = home_raw()
    raw["doors"].append(door("DFAR", "LIVING", "BED_2", [400, 500]))
    result = compile_raw(raw, building_width_m=12)
    assert len(result.venue.doors) == 5
    assert any(line.startswith("door DFAR") and "share no wall" in line for line in result.report.dropped)
    assert "DFAR" not in result.report.element_ids


def test_door_point_is_projected_onto_the_shared_wall_and_clamped():
    raw = home_raw()
    raw["doors"][0]["point"] = [470, 110]          # near the hall's west end, off the wall by 30 units
    raw["doors"][0]["width_m"] = 1.2
    result = compile_raw(raw, building_width_m=8)
    d1 = result.venue.doors[0]
    assert d1.position[1] == pytest.approx(result.venue.zone("LIVING").polygon[0][1])      # on the shared wall y
    assert d1.position[0] >= 1.2 / 2 - 1e-9                                                # clamped inside the room
    assert check_venue(result.venue) == []


def test_default_door_and_exit_widths_are_declared():
    result = compile_home(building_width_m=12)
    assert all(d.width == 0.9 for d in result.venue.doors)
    assert [e.width for e in result.venue.exits] == [0.9, 0.9, 0.6]
    assert [e.service_rate_per_sec for e in result.venue.exits] == [0.54, 0.54, 0.18]
    assert all(d.throughput_per_sec == pytest.approx(d.width) for d in result.venue.doors)
    assert sum("(default; the drawing gave none)" in line for line in result.report.defaults) == 8


def test_exit_point_inside_room_projects_to_an_outside_wall():
    raw = home_raw()
    raw["exits"][0]["point"] = [300, 200]           # well inside the living room
    assert check_venue(compile_raw(raw, building_width_m=12).venue) == []


def test_exit_on_a_shared_wall_goes_to_the_exterior_part():
    raw = home_raw()
    raw["exits"][2]["point"] = [600, 300]           # on the wall BED_1 shares with the hall
    result = compile_raw(raw, building_width_m=12)
    assert check_venue(result.venue) == []


def test_no_exit_survives_returns_an_error_not_a_venue():
    rooms = [room(f"R{i}{j}", [100 + 300 * i, 100 + 300 * j, 400 + 300 * i, 400 + 300 * j])
             for i in range(3) for j in range(3)]
    result = compile_draft(make(rooms, [], [exit_("X", "R11", [550, 550])]), IMG, venue_id="grid-test")
    assert result.venue is None and result.error == "no_exit_survived"
    assert any(line.startswith("exit X") for line in result.report.dropped)


def test_l_shaped_room_stays_rectilinear_and_clean():
    rooms = [room("LOUNGE", [100, 100, 500, 600], "room", extra_boxes=[[500, 100, 900, 400]]),
             room("STUDY", [100, 600, 500, 900]), room("DEN", [500, 400, 900, 900], "bedroom")]
    doors = [door("D_LS", "LOUNGE", "STUDY", [300, 600]), door("D_LD", "LOUNGE", "DEN", [700, 400])]
    result = compile_draft(make(rooms, doors, [exit_("OUT", "LOUNGE", [700, 100])]), IMG, venue_id="l-shape",
                           building_width_m=16)
    lounge = result.venue.zone("LOUNGE")
    assert len(lounge.polygon) == 6
    assert all(abs(a[0] - b[0]) < 1e-9 or abs(a[1] - b[1]) < 1e-9
               for a, b in zip(lounge.polygon, lounge.polygon[1:] + lounge.polygon[:1]))
    assert check_venue(result.venue) == []
    assert any("merged 2 boxes into one rectilinear outline" in e for e in result.report.edits)
    assert result.venue.door_between("LOUNGE", "DEN") is not None


def test_disconnected_extra_box_is_dropped():
    rooms = [room("A", [100, 100, 400, 400], extra_boxes=[[600, 600, 800, 800]]), room("B", [100, 400, 400, 700])]
    result = compile_draft(make(rooms, [door("D", "A", "B", [250, 400])], [exit_("X", "A", [250, 100])]), IMG,
                           venue_id="gap-test", building_width_m=10)
    assert len(result.venue.zone("A").polygon) == 4
    assert any("extra box 1 does not touch" in d for d in result.report.dropped)


def test_snapping_aligns_jittered_walls_without_creating_overlaps():
    raw = home_raw()
    jitter = {"LIVING": [100, 100, 507, 496], "KITCHEN": [100, 503, 493, 900], "HALL": [496, 100, 604, 903],
              "BED_1": [598, 103, 900, 503], "BED_2": [603, 497, 897, 900]}
    for r in raw["rooms"]:
        r["box"] = jitter[r["key"]]
    result = compile_raw(raw, building_width_m=12)
    assert not [i for i in check_venue(result.venue) if i.code == "rooms_overlap"]
    assert check_venue(result.venue) == []
    living, kitchen = result.venue.zone("LIVING"), result.venue.zone("KITCHEN")
    assert max(p[0] for p in living.polygon) == min(p[0] for p in kitchen.polygon)       # one shared grid line
    assert any(e.startswith("snapped") for e in result.report.edits)
    assert all(abs(v * 10 - round(v * 10)) < 1e-6 for z in result.venue.zones for p in z.polygon for v in p)


def test_headcount_hints_and_density():
    base = compile_home(building_width_m=12)
    assert sum(z.initial_occupants for z in base.venue.zones) >= 1
    assert any("declared" in d and "per m²" in d for d in base.report.defaults)
    counted = compile_home(building_width_m=12, headcount=10)
    zones = {z.id: z for z in counted.venue.zones}
    assert sum(z.initial_occupants for z in counted.venue.zones) == 10 and zones["HALL"].initial_occupants == 0
    assert check_venue(counted.venue) == []
    huge = compile_home(building_width_m=12, headcount=500)
    assert all(z.initial_occupants <= z.max_capacity for z in huge.venue.zones)
    assert any("headcount capped" in e for e in huge.report.edits)
    raw = home_raw()
    raw["rooms"][0]["occupants_hint"] = 4
    raw["rooms"][1]["occupants_hint"] = 999
    zones = {z.id: z for z in compile_raw(raw, building_width_m=12).venue.zones}
    assert zones["LIVING"].initial_occupants == 4 and zones["KITCHEN"].initial_occupants == zones["KITCHEN"].max_capacity
    assert zones["BED_1"].initial_occupants == 0


def test_horizon_is_a_multiple_of_the_step_and_bounded():
    for width, count in [(6, 1), (12, 10), (60, 400)]:
        venue = compile_home(building_width_m=width, headcount=count).venue
        assert venue.default_horizon_seconds % venue.time_step_seconds == 0
        assert 30 <= venue.default_horizon_seconds <= 120


def test_provenance_default_and_caller_text():
    default = compile_home(building_width_m=12, name="My flat").venue.provenance
    assert default.startswith("My flat: Compiled by the local compiler") and "not a surveyed plan" in default
    assert "Gemini 4 Argon" in default and "operator-accepted" in default
    assert compile_home(provenance="Custom text").venue.provenance == "Custom text"
