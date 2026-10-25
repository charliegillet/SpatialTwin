"""RoomLab room readings -> planable venues: alignment, splitting, voids, doors, exits, looks, hazards."""
import math

import pytest

from backend.app.ai.real2sim.room.provider_schema import ProviderRoomPayload, normalize_provider_payload
from backend.app.hazard.door_planner import plan_doors
from backend.app.venues.graph_checks import check_venue, errors_in
from backend.app.venues.room_compiler import compile_room
from backend.app.venues.schemas import DoorPlanRequest


def reading(payload):
    draft, _warnings = normalize_provider_payload(ProviderRoomPayload.model_validate(payload), {"frame-001"})
    return draft


def rect(w, d, cx=0.0, cz=0.0):
    return [{"x_m": cx - w / 2, "z_m": cz - d / 2}, {"x_m": cx + w / 2, "z_m": cz - d / 2},
            {"x_m": cx + w / 2, "z_m": cz + d / 2}, {"x_m": cx - w / 2, "z_m": cz + d / 2}]


def lobby(**extra):
    """12 x 8 m: a landing (north, z < -1) and a lobby behind a glass storefront with a door; front door on wall-3."""
    return {
        "name": "Reception lobby", "floor_vertices": rect(12, 8),
        "interior_walls": [{"id": "wall-partition-1", "role": "partition", "start_x_m": -6, "start_z_m": -1,
                            "end_x_m": 6, "end_z_m": -1, "height_m": 2.7}],
        "openings": [{"id": "door-glass", "wall_id": "wall-partition-1", "kind": "door", "offset_m": 5.0, "width_m": 1.8},
                     {"id": "door-front", "wall_id": "wall-3", "kind": "door", "offset_m": 5.0, "width_m": 1.2},
                     {"id": "win-1", "wall_id": "wall-2", "kind": "window", "offset_m": 2.0, "width_m": 2.0, "sill_m": 0.9}],
        "objects": [{"id": "counter", "label": "Reception counter", "category": "counter", "x_m": 0, "z_m": 2,
                     "width_m": 4, "depth_m": 0.9, "height_m": 1.1, "color": "#e3e6e8", "movable": False},
                    {"id": "plant", "label": "Potted plant", "category": "plant", "x_m": 4, "z_m": -3,
                     "width_m": 0.6, "depth_m": 0.6, "height_m": 1.6}],
        "wall_color": "#ece9e2", "floor_color": "#a7abae", "floor_material": "terrazzo",
        **extra,
    }


def checked(result):
    assert result.venue is not None, (result.error, result.report.dropped)
    errors = errors_in(check_venue(result.venue))
    assert errors == [], [e.message for e in errors]
    return result.venue


def test_partition_with_a_door_becomes_two_rooms_and_the_front_door_an_exit():
    venue = checked(compile_room(reading(lobby()), venue_id="lobby-abc123"))
    assert venue.extent == (12.0, 8.0)
    assert sorted(z.name for z in venue.zones) == ["North area", "Reception"]
    assert len(venue.doors) == 1 and venue.doors[0].width == 1.8
    assert len(venue.exits) == 1 and venue.exits[0].zone == "RECEPTION"
    assert venue.exits[0].position[1] in (0.0, 8.0)
    kinds = sorted(f.kind for f in venue.appearance.features)
    assert kinds == ["glass", "window"]
    assert {f.label for f in venue.appearance.furniture} == {"Reception counter", "Potted plant"}
    assert venue.appearance.zones["RECEPTION"].floor_material == "terrazzo"
    assert "appearance" not in venue.planning_json()


def test_fire_in_the_lobby_plans_through_the_partition_door():
    venue = checked(compile_room(reading(lobby()), venue_id="lobby-abc123"))
    north = next(z for z in venue.zones if z.name == "North area")
    xs = [p[0] for p in north.polygon]
    ys = [p[1] for p in north.polygon]
    plan = plan_doors(venue, DoorPlanRequest(hazards=[{"id": "h1", "type": "FIRE", "source": "simulated",
                                                       "position": {"x": sum(xs) / len(xs), "y": sum(ys) / len(ys)}}]))
    assert plan.venue_id == "lobby-abc123" and plan.no_hazard_completed > 0


def test_a_turned_room_is_squared_up_and_keeps_its_exit():
    angle = math.radians(17)
    pts = rect(10, 6)
    turned = [{"x_m": p["x_m"] * math.cos(angle) - p["z_m"] * math.sin(angle),
               "z_m": p["x_m"] * math.sin(angle) + p["z_m"] * math.cos(angle)} for p in pts]
    room = reading({"name": "Studio", "floor_vertices": turned,
                    "openings": [{"id": "door", "wall_id": "wall-1", "kind": "door", "offset_m": 4.0, "width_m": 1.0}],
                    "objects": [{"id": "sofa", "label": "Sofa", "category": "sofa", "x_m": 0, "z_m": 0,
                                 "width_m": 2, "depth_m": 0.9, "yaw_deg": -17}]})  # three.js rotation.y is clockwise from above
    venue = checked(compile_room(room, venue_id="studio-abc123"))
    assert [z.name for z in venue.zones] == ["Studio"]
    assert venue.extent == pytest.approx((10.0, 6.0), abs=0.11)
    assert len(venue.zones[0].polygon) == 4
    sofa = venue.appearance.furniture[0]
    assert sofa.yaw_deg == pytest.approx(0, abs=0.5)


def test_an_atrium_in_the_middle_is_cut_out_and_the_ring_still_reaches_the_exit():
    room = reading(lobby(interior_walls=[], openings=[
        {"id": "door-front", "wall_id": "wall-3", "kind": "door", "offset_m": 5.0, "width_m": 1.2}],
        floor_voids=[{"id": "atrium", "vertices": rect(4, 3)}]))
    result = compile_room(room, venue_id="ring-abc123")
    venue = result.venue
    assert venue is not None
    floor = sum(abs(sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(z.polygon, z.polygon[1:] + z.polygon[:1]))) / 2
                for z in venue.zones)
    assert floor == pytest.approx(12 * 8 - 4 * 3, abs=0.5)
    assert any("void" in edit for edit in result.report.edits)
    # The cut is open floor: the halves are joined by a wide open passage, so both reach the front door.
    assert errors_in(check_venue(venue)) == []
    assert any(d.kind == "opening" and d.width >= 2.5 for d in venue.doors)


def test_no_outside_door_means_no_venue():
    room = reading(lobby(openings=[{"id": "door-glass", "wall_id": "wall-partition-1", "kind": "door",
                                    "offset_m": 5.0, "width_m": 1.8}]))
    result = compile_room(room, venue_id="lobby-abc123")
    assert result.venue is None and result.error == "no_exit_survived"


def test_operator_width_rescales_and_controllable_doors_are_venue_ids():
    venue = checked(compile_room(reading(lobby()), venue_id="lobby-abc123", building_width_m=24,
                                 controllable_doors=["D1"], headcount=40))
    assert venue.extent == (24.0, 16.0)
    assert venue.doors[0].planner_can_open and venue.doors[0].default_state == "closed"
    assert sum(z.initial_occupants for z in venue.zones) == 40


def test_the_same_reading_always_compiles_to_the_same_venue():
    first = compile_room(reading(lobby()), venue_id="lobby-abc123").venue
    second = compile_room(reading(lobby()), venue_id="lobby-abc123").venue
    assert first.geometry_revision == second.geometry_revision
