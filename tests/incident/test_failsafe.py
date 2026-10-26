"""The unattended fail-safe: off by default; armed, it approves a checked plan nobody approved in time, never opening a
gate into a room with a hazard, and a person can take over at any moment."""
import asyncio

from backend.app.incident.gates import GateState
from backend.app.incident.models import IncidentState
from backend.app.venues.model import load_building_v2
from tests.incident.conftest import FAST, HALL_FIRE, LOBBY_FIRE, approve_body, plan_with

WINDOW = 0.05  # the route asks for 5-120 s; the manager takes any window, so the tests do not sleep for seconds


def gate(state, gate_id):
    return next(g for g in state["controller"]["gates"] if g["gate_id"] == gate_id)


async def read(client):
    return (await client.get("/api/incident")).json()


async def test_off_by_default_and_nothing_moves_without_a_person(client, manager):
    state = await plan_with(client, LOBBY_FIRE)
    assert state["failsafe"]["armed"] is False and state["failsafe"]["status"] == "off"
    await asyncio.sleep(WINDOW * 3)
    await manager.wait_failsafe()
    after = await read(client)
    assert after["approvals"] == [] and gate(after, "D9")["state"] == "CLOSED"


async def test_nobody_approves_so_the_fail_safe_applies_the_checked_plan(client, manager):
    state = await plan_with(client, LOBBY_FIRE)
    revision = state["plan_revision"]
    assert state["plan"]["door_states"]["D9"] == "open"  # D9 is not a door into the lobby
    view = await manager.set_failsafe(True, WINDOW)
    assert view.status == "counting_down" and view.plan_revision == revision and view.would_hold == []
    assert view.deadline_at is not None and 0 <= view.seconds_left <= WINDOW
    await manager.wait_failsafe()
    done = await read(client)
    approval = done["approvals"][-1]
    assert approval["actor"] == "fail_safe" and approval["plan_revision"] == revision and approval["commands"] == {"D9": "OPEN"}
    assert approval["status"] == "applied" and gate(done, "D9")["observed"] == "open"
    assert done["plan_revision"] == revision and done["plan"]["held_doors"] == []  # applied as is: nothing to hold
    failsafe = done["failsafe"]
    assert failsafe["status"] == "acted" and failsafe["last_action"]["approval_id"] == approval["approval_id"]
    assert "opening D9" in failsafe["last_action"]["summary"] and "125 of 125 modeled crossings" in failsafe["last_action"]["summary"]


async def test_it_never_opens_a_gate_into_a_hazard_room(client, manager):
    # A fire in the hall: the best plan opens D4 (hall -> north stair). Unattended, D4 is held closed and re-checked.
    state = await plan_with(client, HALL_FIRE)
    primary = state["plan"]
    assert primary["door_states"]["D4"] == "open" and primary["completed_crossings"] == 105
    view = await manager.set_failsafe(True, WINDOW)
    assert view.would_hold == ["D4"]
    await manager.wait_failsafe()
    done = await read(client)
    plan = done["plan"]
    assert plan["plan_revision"] > primary["plan_revision"] and plan["valid"]
    assert plan["door_states"]["D4"] == "closed" and plan["held_doors"] == ["D4"] and plan["completed_crossings"] == 93
    assert "held closed by the fail-safe" in next(d for d in plan["doors"] if d["id"] == "D4")["reason"]
    assert "held closed by the fail-safe" in plan["note"]
    approval = done["approvals"][-1]
    assert approval["actor"] == "fail_safe" and approval["plan_revision"] == plan["plan_revision"]
    assert approval["commands"] == {} and gate(done, "D4")["state"] == "CLOSED"  # D4 was already closed
    failsafe = done["failsafe"]
    assert failsafe["held_doors"] == {"D4": ["HALL"]}
    summary = failsafe["last_action"]["summary"]
    assert "held D4 closed (it opens into Hall, a room with a hazard)" in summary
    assert "93 of 125 modeled crossings" in summary and "a person could approve 105 by opening D4" in summary
    # The full door plan the twin draws is the held one, with the real venue's geometry revision.
    door_plan = (await client.get("/api/incident/door-plan")).json()
    assert door_plan["plan_revision"] == plan["plan_revision"]
    assert door_plan["door_plan"]["geometry_revision"] == done["geometry_revision"]
    assert next(d for d in door_plan["door_plan"]["doors"] if d["id"] == "D4")["state"] == "closed"


async def test_a_person_who_approves_in_time_wins(client, manager):
    state = await plan_with(client, LOBBY_FIRE)
    await manager.set_failsafe(True, 0.3)
    response = await client.post("/api/incident/approve", json=approve_body(state))
    assert response.status_code == 200
    await manager.wait_idle()
    await asyncio.sleep(0.4)
    await manager.wait_failsafe()
    done = await read(client)
    assert [a["actor"] for a in done["approvals"]] == ["operator"]
    assert done["failsafe"]["status"] == "approved" and done["failsafe"]["last_action"] is None


async def test_new_hazards_restart_the_window_on_the_new_plan(client, manager):
    first = await plan_with(client, HALL_FIRE)
    await manager.set_failsafe(True, 0.2)
    second = await plan_with(client, LOBBY_FIRE)
    assert second["plan_revision"] > first["plan_revision"]
    assert second["failsafe"]["status"] == "counting_down" and second["failsafe"]["plan_revision"] == second["plan_revision"]
    await manager.wait_failsafe()
    done = await read(client)
    assert [(a["actor"], a["plan_revision"]) for a in done["approvals"]] == [("fail_safe", second["plan_revision"])]
    assert done["plan"]["held_doors"] == []


async def test_im_here_hands_the_held_gates_back_to_the_planner(client, manager):
    await plan_with(client, HALL_FIRE)
    await manager.set_failsafe(True, WINDOW)
    await manager.wait_failsafe()
    held = await read(client)
    assert held["plan"]["held_doors"] == ["D4"]
    response = await client.post("/api/incident/failsafe", json={"armed": False})
    assert response.status_code == 200 and response.json()["status"] == "off"
    await manager.wait_idle()
    back = await read(client)
    assert back["plan_revision"] > held["plan_revision"] and back["plan"]["held_doors"] == []
    assert back["plan"]["door_states"]["D4"] == "open" and back["plan"]["completed_crossings"] == 105
    assert back["failsafe"]["armed"] is False
    # The full plan is a person's to approve now.
    assert (await client.post("/api/incident/approve", json=approve_body(back))).status_code == 200


async def test_a_jam_under_the_fail_safe_re_plans_and_gets_its_own_window(client, manager):
    await plan_with(client, LOBBY_FIRE)
    assert (await client.post("/api/incident/faults", json={"gate_id": "D9", "fault": "stall"})).status_code == 200
    await manager.set_failsafe(True, WINDOW)
    await manager.wait_failsafe()  # the fail-safe approves; D9 stalls; a fallback is published with a new window
    mid = await read(client)
    assert mid["approvals"][-1]["status"] == "failed" and mid["approvals"][-1]["actor"] == "fail_safe"
    assert mid["plan"]["label"] == "fallback" and mid["plan"]["stuck_doors"] == ["D9"]
    assert mid["failsafe"]["status"] == "counting_down" and mid["failsafe"]["plan_revision"] == mid["plan_revision"]
    await manager.wait_failsafe()
    done = await read(client)
    last = done["approvals"][-1]
    assert last["actor"] == "fail_safe" and last["plan_revision"] == mid["plan_revision"] and last["status"] == "applied"
    assert done["failsafe"]["status"] == "acted"


async def test_a_gate_in_doubt_is_treated_as_stuck_closed(client, manager):
    await plan_with(client, LOBBY_FIRE)
    manager.controller.gates["D9"].state = GateState.FAULT  # position unknown, not yet marked stuck
    await manager.set_failsafe(True, WINDOW)
    await manager.wait_failsafe()
    done = await read(client)
    assert "D9" in done["stuck_doors"] and done["plan"]["door_states"]["D9"] == "closed"
    assert done["approvals"][-1]["actor"] == "fail_safe" and "D9" not in done["approvals"][-1]["commands"]
    assert "treated D9 as stuck closed (position unknown)" in done["failsafe"]["last_action"]["summary"]


async def test_no_checked_plan_means_nothing_moves(client, manager):
    await plan_with(client, LOBBY_FIRE)
    manager.plan = manager.plan.model_copy(update={"valid": False})
    view = await manager.set_failsafe(True, WINDOW)
    assert view.status == "standing_by"
    await asyncio.sleep(WINDOW * 3)
    await manager.wait_failsafe()
    assert (await read(client))["approvals"] == []


async def test_reset_and_a_rebind_disarm_it(client, manager):
    await plan_with(client, LOBBY_FIRE)
    await manager.set_failsafe(True, 30)
    reset = (await client.post("/api/incident/reset")).json()
    assert reset["failsafe"]["armed"] is False and manager._failsafe_timer is None
    await manager.set_failsafe(True, 30)
    assert IncidentState.model_validate(manager.state().model_dump()).failsafe.armed is True
    manager._bind(manager.venue)  # a venue change starts a fresh incident, with a person in the loop
    assert manager.state().failsafe.armed is False and manager._failsafe_timer is None


async def test_route_validates_the_window_and_events_carry_the_view(client, manager):
    await plan_with(client, LOBBY_FIRE)
    assert (await client.post("/api/incident/failsafe", json={"armed": True, "window_seconds": 2})).status_code == 422
    assert (await client.post("/api/incident/failsafe", json={"armed": True, "window_seconds": 500})).status_code == 422
    armed = await client.post("/api/incident/failsafe", json={"armed": True})
    assert armed.status_code == 200 and armed.json()["window_seconds"] == 15 and armed.json()["status"] == "counting_down"
    frames = [frame for _, frame in manager.hub.events_since(0)]
    assert any(frame.startswith("id: ") and "event: failsafe\n" in frame and "FAILSAFE armed" in frame for frame in frames)
    off = await client.post("/api/incident/failsafe", json={"armed": False})
    assert off.json()["status"] == "off" and manager._failsafe_timer is None


# -- review round: the devil's-advocate findings -------------------------------------------------------------------

def zone_centre(zone_id):
    zone = next(z for z in load_building_v2().zones if z.id == zone_id)
    xs = [p[0] if isinstance(p, (list, tuple)) else p.x for p in zone.polygon]
    ys = [p[1] if isinstance(p, (list, tuple)) else p.y for p in zone.polygon]
    return {"x": sum(xs) / len(xs), "y": sum(ys) / len(ys)}


WEST_FIRE = {"id": "h0", "type": "FIRE", "position": zone_centre("WEST_CORR"), "source": "simulated"}


async def open_d4_then_fire_in_the_hall(client, manager):
    """A person opened D4 for a west-corridor fire; then the fire is in the hall, and D4 opens into it."""
    state = await plan_with(client, WEST_FIRE)
    assert state["plan"]["door_states"]["D4"] == "open"
    assert (await client.post("/api/incident/approve", json=approve_body(state))).status_code == 200
    await manager.wait_idle()
    assert gate(await read(client), "D4")["observed"] == "open"
    return await plan_with(client, HALL_FIRE)


async def test_im_here_while_the_fail_safe_moves_doors_still_hands_them_back(client, manager):
    manager.config = FAST.model_copy(update={"transit_s": 0.3})  # before the first request binds the controller
    await open_d4_then_fire_in_the_hall(client, manager)
    await manager.set_failsafe(True, WINDOW)
    await asyncio.sleep(WINDOW + 0.1)  # the fail-safe has commanded D4 CLOSED; it is in transit
    moving = await read(client)
    assert moving["approvals"][-1]["actor"] == "fail_safe" and moving["approvals"][-1]["commands"] == {"D4": "CLOSED"}
    assert moving["approval_in_progress"] is True
    off = await client.post("/api/incident/failsafe", json={"armed": False})
    assert off.json()["status"] == "off"
    await manager.wait_idle()
    back = await read(client)
    assert back["plan"]["held_doors"] == [] and back["plan"]["door_states"]["D4"] == "open"
    assert back["failsafe"]["held_doors"] == {}


async def test_a_held_gate_whose_close_is_never_seen_is_not_called_closed(client, manager):
    await open_d4_then_fire_in_the_hall(client, manager)
    assert (await client.post("/api/incident/faults", json={"gate_id": "D4", "fault": "stall"})).status_code == 200
    await manager.set_failsafe(True, WINDOW)
    await manager.wait_failsafe()  # the fail-safe commands D4 CLOSED, it stalls, a fallback is published
    mid = await read(client)
    failed = mid["approvals"][-1]
    assert failed["actor"] == "fail_safe" and failed["status"] == "failed"
    assert "D4: position unknown, may still be open" in failed["reason"]
    d4 = next(d for d in mid["plan"]["doors"] if d["id"] == "D4")
    assert "position is unknown and it may still be open" in d4["reason"]
    await manager.wait_failsafe()  # the fallback's own window
    done = await read(client)
    assert "D4 may still be open into a room with a hazard" in done["failsafe"]["last_action"]["summary"]


async def test_an_unchecked_held_plan_never_replaces_the_persons_plan(client, manager, monkeypatch):
    state = await plan_with(client, HALL_FIRE)
    real = manager._plan

    async def unchecked(hazards, stuck, reason):
        plan, door_plan = await real(hazards, stuck, reason)
        return (plan.model_copy(update={"valid": False}) if manager.held else plan), door_plan

    monkeypatch.setattr(manager, "_plan", unchecked)
    await manager.set_failsafe(True, WINDOW)
    await manager.wait_failsafe()
    after = await read(client)
    assert after["plan_revision"] == state["plan_revision"] and after["plan"]["valid"] and after["approvals"] == []
    assert after["plan"]["held_doors"] == [] and manager.held == {}
    assert after["failsafe"]["status"] == "standing_by"
    frames = [frame for _, frame in manager.hub.events_since(0)]
    assert any("no checked plan with D4 closed; nothing moved; a person must approve" in frame for frame in frames)
    assert (await client.post("/api/incident/approve", json=approve_body(after))).status_code == 200  # still approvable


async def test_an_error_while_acting_is_reported_and_never_leaves_it_counting(client, manager, monkeypatch):
    await plan_with(client, LOBBY_FIRE)

    async def broken():
        raise ValueError("boom")

    monkeypatch.setattr(manager, "_failsafe_act_locked", broken)
    await manager.set_failsafe(True, WINDOW)
    await manager.wait_failsafe()
    view = (await read(client))["failsafe"]
    assert view["status"] == "standing_by" and view["deadline_at"] is None
    frames = [frame for _, frame in manager.hub.events_since(0)]
    assert any("could not act (ValueError); nothing moved" in frame for frame in frames)


async def test_the_countdown_names_gates_in_doubt(client, manager):
    await plan_with(client, LOBBY_FIRE)
    manager.controller.gates["D9"].state = GateState.UNKNOWN
    view = await manager.set_failsafe(True, 30)
    assert view.status == "counting_down" and view.in_doubt == ["D9"]
    await manager.set_failsafe(False)
