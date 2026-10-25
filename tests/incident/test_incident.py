"""Virtual door controller and incident mirror: ACK is not arrival, faults never read as open, stale plans cannot move doors."""
import asyncio
import json

import pytest

from backend.app.incident.events import EventHub
from backend.app.incident.gates import ControllerConfig, GateState, VirtualDoorController
from backend.app.venues.model import VenueV2
from backend.app.venues.registry import venue_registry
from tests.incident.conftest import FAST, HALL_FIRE, HOME, LOBBY_FIRE, approve_body, plan_with


def gate(state, gate_id):
    return next(g for g in state["controller"]["gates"] if g["gate_id"] == gate_id)


async def approve(client, manager, state, expect=200):
    response = await client.post("/api/incident/approve", json=approve_body(state))
    assert response.status_code == expect, response.text
    await manager.wait_idle()
    return response.json()


async def test_gates_exist_only_for_controllable_doors(client):
    state = (await client.get("/api/incident")).json()
    assert state["simulated"] and state["controller"]["simulated"]
    assert sorted(g["gate_id"] for g in state["controller"]["gates"]) == ["D4", "D9"]
    assert all(g["state"] == "CLOSED" and g["closed_switch"] and not g["open_switch"] for g in state["controller"]["gates"])


async def test_happy_approve_transit_then_endpoint_opens(client, manager):
    state = await plan_with(client, HALL_FIRE)
    assert state["plan"]["door_states"]["D4"] == "open" and state["plan"]["label"] == "primary" and state["plan"]["valid"]
    record = await client.post("/api/incident/approve", json=approve_body(state))
    assert record.status_code == 200 and record.json()["status"] == "actuating"
    await asyncio.sleep(0.003)  # mid-transit: an ACK has been given, nothing has arrived
    mid = (await client.get("/api/incident")).json()
    assert gate(mid, "D4")["state"] == "OPENING" and gate(mid, "D4")["last_ack"] == "ACCEPTED"
    assert gate(mid, "D4")["observed"] is None and not gate(mid, "D4")["open_switch"]
    assert next(d for d in mid["plan"]["doors"] if d["id"] == "D4")["applied"] == "moving"
    await manager.wait_idle()
    done = (await client.get("/api/incident")).json()
    d4 = gate(done, "D4")
    assert d4["state"] == "OPEN" and d4["open_switch"] and not d4["closed_switch"] and d4["epoch"] == 2
    assert done["approvals"][-1]["status"] == "applied" and done["approvals"][-1]["commands"] == {"D4": "OPEN"}
    assert next(d for d in done["plan"]["doors"] if d["id"] == "D4")["applied"] == "open"
    assert gate(done, "D9")["state"] == "CLOSED"  # not commanded


async def test_ack_without_endpoint_never_counts_as_open():
    seen = []
    controller = VirtualDoorController({"D4": "closed"}, ControllerConfig(transit_s=0.2), emit=lambda k, p: seen.append(p))
    task = asyncio.ensure_future(controller.command("D4", "OPEN"))
    await asyncio.sleep(0.05)
    g = controller.gates["D4"]
    assert g.last_ack == "ACCEPTED" and g.state == GateState.OPENING
    assert not g.open_switch and g.snapshot()["observed"] is None and g.snapshot()["applied"] == "moving"
    assert g.epoch == 1
    outcome = await task
    assert outcome.result == "arrived" and controller.gates["D4"].epoch == 2
    assert [p["phase"] for p in seen if p.get("gate_id") == "D4"] == ["command", "ack", "transit", "observed"]


async def test_stall_faults_marks_stuck_and_publishes_fallback(client, manager):
    state = await plan_with(client, LOBBY_FIRE)
    assert state["plan"]["door_states"] == {**state["plan"]["door_states"], "D9": "open", "D4": "closed"}
    primary_revision = state["plan"]["plan_revision"]
    assert (await client.post("/api/incident/faults", json={"gate_id": "D9", "fault": "stall"})).status_code == 200
    await approve(client, manager, state)
    after = (await client.get("/api/incident")).json()
    d9 = gate(after, "D9")
    assert d9["state"] == "FAULT" and not d9["open_switch"] and d9["observed"] is None and d9["applied"] == "unknown"
    assert after["stuck_doors"] == ["D9"]
    plan = after["plan"]
    assert plan["label"] == "fallback" and plan["note"] == "with D9 stuck closed"
    assert plan["plan_revision"] > primary_revision and plan["door_states"]["D9"] == "closed"
    assert plan["door_states"]["D4"] == "open"
    assert next(d for d in plan["doors"] if d["id"] == "D9")["stuck"] and plan["valid"]
    approval = after["approvals"][-1]
    assert approval["status"] == "failed" and "D9" in approval["reason"] and approval["fallback_plan_revision"] == plan["plan_revision"]
    # The old plan can no longer be approved, but the fallback needs a fresh human approval and then moves D4 only.
    stale = await client.post("/api/incident/approve", json=approve_body(state))
    assert stale.status_code == 409 and stale.json()["detail"]["code"] == "stale_plan"
    await approve(client, manager, after)
    final = (await client.get("/api/incident")).json()
    assert gate(final, "D4")["state"] == "OPEN" and gate(final, "D9")["state"] == "FAULT"
    assert final["approvals"][-1]["commands"] == {"D4": "OPEN"}


async def test_jam_injected_during_transit_still_bites(client, manager):
    state = await plan_with(client, HALL_FIRE)
    await client.post("/api/incident/approve", json=approve_body(state))
    await asyncio.sleep(0.003)
    await client.post("/api/incident/faults", json={"gate_id": "D4", "fault": "stall"})
    await manager.wait_idle()
    after = (await client.get("/api/incident")).json()
    assert gate(after, "D4")["state"] == "FAULT" and "D4" in after["stuck_doors"]
    assert after["plan"]["door_states"]["D4"] == "closed"


async def test_dropped_ack_leaves_unknown(client, manager):
    state = await plan_with(client, HALL_FIRE)
    await client.post("/api/incident/faults", json={"gate_id": "D4", "fault": "dropped_ack"})
    await approve(client, manager, state)
    after = (await client.get("/api/incident")).json()
    d4 = gate(after, "D4")
    assert d4["state"] == "UNKNOWN" and d4["last_ack"] is None and d4["applied"] == "unknown" and not d4["open_switch"]
    assert after["stuck_doors"] == ["D4"] and "ack_timeout" in after["approvals"][-1]["results"]["D4"]


async def test_switch_disagreement_is_a_fault_not_open(client, manager):
    state = await plan_with(client, HALL_FIRE)
    await client.post("/api/incident/faults", json={"gate_id": "D4", "fault": "switch_disagreement"})
    await approve(client, manager, state)
    after = (await client.get("/api/incident")).json()
    d4 = gate(after, "D4")
    assert d4["state"] == "FAULT" and d4["open_switch"] and d4["closed_switch"] and d4["observed"] is None
    assert after["stuck_doors"] == ["D4"] and after["plan"]["label"] == "fallback"


async def test_heartbeat_timeout_makes_every_gate_unknown_and_replans(client, manager):
    state = await plan_with(client, HALL_FIRE)
    await approve(client, manager, state)
    assert gate((await client.get("/api/incident")).json(), "D4")["state"] == "OPEN"
    await client.post("/api/incident/faults", json={"fault": "heartbeat_timeout"})
    await asyncio.sleep(0.08)
    await manager.wait_idle()
    after = (await client.get("/api/incident")).json()
    assert after["controller"]["heartbeat"] == "stale"
    assert {g["state"] for g in after["controller"]["gates"]} == {"UNKNOWN"}
    assert all(g["applied"] == "unknown" for g in after["controller"]["gates"])
    assert after["stuck_doors"] == ["D4", "D9"] and after["plan"]["label"] == "fallback"
    assert all(after["plan"]["door_states"][g] == "closed" for g in ("D4", "D9"))
    # A command to a stale controller is refused: nothing moves, nothing is observed.
    outcome = await manager.controller.command("D4", "OPEN")
    assert outcome.result == "unknown" and outcome.detail == "controller_stale"


async def test_stale_revision_and_hash_are_409(client, manager):
    state = await plan_with(client, HALL_FIRE)
    body = approve_body(state)
    for bad in ({**body, "plan_revision": body["plan_revision"] - 1}, {**body, "candidate_hash": "0" * 8},
                {**body, "door_states": {**body["door_states"], "D9": "open"}}):
        response = await client.post("/api/incident/approve", json=bad)
        assert response.status_code == 409 and response.json()["detail"]["code"] == "stale_plan"
    again = await client.post("/api/incident/hazards", json={"venue_id": "building-v2", "hazards": [],
                                                              "expected_plan_revision": body["plan_revision"] - 1})
    assert again.status_code == 409 and again.json()["detail"]["code"] == "stale_plan"
    # Nothing moved.
    assert {g["state"] for g in (await client.get("/api/incident")).json()["controller"]["gates"]} == {"CLOSED"}


async def test_approve_without_a_plan_is_409(client):
    state = (await client.get("/api/incident")).json()
    response = await client.post("/api/incident/approve", json={"plan_revision": state["plan_revision"], "candidate_hash": "x", "door_states": {}})
    assert response.status_code == 409 and response.json()["detail"]["code"] == "no_plan"


async def test_invalid_plan_is_422_and_planner_codes_pass_through(client, manager, monkeypatch):
    state = await plan_with(client, HALL_FIRE)
    manager.plan = manager.plan.model_copy(update={"valid": False})
    response = await client.post("/api/incident/approve", json=approve_body(state))
    assert response.status_code == 422 and response.json()["detail"]["code"] == "plan_not_valid"
    outside = {**HALL_FIRE, "position": {"x": 500, "y": 500}}
    bad = await client.post("/api/incident/hazards", json={"venue_id": "building-v2", "hazards": [outside],
                                                           "expected_plan_revision": manager.plan_revision})
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "outside_building"
    missing = await client.post("/api/incident/hazards", json={"venue_id": "nope-venue", "hazards": [], "expected_plan_revision": 0})
    assert missing.status_code == 404 and missing.json()["detail"]["code"] == "unknown_venue"
    camera = {**HALL_FIRE, "source": "camera"}
    unconfirmed = await client.post("/api/incident/hazards", json={"venue_id": "building-v2", "hazards": [camera],
                                                                   "expected_plan_revision": manager.plan_revision})
    assert unconfirmed.status_code == 422 and unconfirmed.json()["detail"]["code"] == "unconfirmed_camera_hazard"


async def test_fault_validation(client):
    assert (await client.post("/api/incident/faults", json={"gate_id": "D1", "fault": "stall"})).status_code == 404
    response = await client.post("/api/incident/faults", json={"fault": "stall"})
    assert response.status_code == 422 and response.json()["detail"]["code"] == "gate_required"
    assert (await client.post("/api/incident/faults", json={"gate_id": "D4", "fault": "melt"})).status_code == 422


async def test_reset_clears_faults_and_returns_gates_to_closed(client, manager):
    state = await plan_with(client, HALL_FIRE)
    await client.post("/api/incident/faults", json={"gate_id": "D9", "fault": "stall"})
    await approve(client, manager, state)
    assert gate((await client.get("/api/incident")).json(), "D4")["state"] == "OPEN"
    await client.post("/api/incident/faults", json={"fault": "heartbeat_timeout"})
    before = state["plan_revision"]
    response = await client.post("/api/incident/reset")
    after = response.json()
    assert response.status_code == 200 and after["plan"] is None and after["hazards"] == [] and after["stuck_doors"] == []
    assert after["plan_revision"] > before and after["approvals"] == []
    assert after["controller"]["heartbeat"] == "ok"
    for g in after["controller"]["gates"]:
        assert g["state"] == "CLOSED" and g["fault"] is None and g["closed_switch"] and g["epoch"] == 1
    # And it works again afterwards.
    fresh = await plan_with(client, HALL_FIRE)
    await approve(client, manager, fresh)
    assert gate((await client.get("/api/incident")).json(), "D4")["state"] == "OPEN"


async def test_reset_during_transit_cancels_the_command(client, manager):
    state = await plan_with(client, HALL_FIRE)
    manager.controller.config = ControllerConfig(transit_s=0.3)
    await client.post("/api/incident/approve", json=approve_body(state))
    await asyncio.sleep(0.01)
    await client.post("/api/incident/reset")
    await manager.wait_idle()
    after = (await client.get("/api/incident")).json()
    assert gate(after, "D4")["state"] == "CLOSED" and after["approvals"] == [] and after["plan"] is None


async def test_clear_fault_keeps_gate_unknown_until_observed(client, manager):
    state = await plan_with(client, HALL_FIRE)
    await client.post("/api/incident/faults", json={"gate_id": "D4", "fault": "dropped_ack"})
    await approve(client, manager, state)
    cleared = (await client.post("/api/incident/faults/clear", json={"gate_id": "D4"})).json()
    d4 = next(g for g in cleared["controller"]["gates"] if g["gate_id"] == "D4")
    assert d4["fault"] is None and d4["state"] == "UNKNOWN"
    outcome = await manager.controller.command("D4", "OPEN")
    assert outcome.result == "arrived"


async def test_door_plan_follows_the_fallback_after_a_jam(client, manager):
    """The twin draws what is executed: after a jam the full plan (routes, lamps, doors) is the fallback's."""
    assert (await client.get("/api/incident/door-plan")).json()["door_plan"] is None
    state = await plan_with(client, LOBBY_FIRE)
    primary = (await client.get("/api/incident/door-plan")).json()
    assert primary["plan_revision"] == state["plan_revision"]
    assert primary["door_plan"]["chosen"]["candidate_hash"] == state["plan"]["candidate_hash"]
    await client.post("/api/incident/faults", json={"gate_id": "D9", "fault": "stall"})
    await approve(client, manager, state)
    after = (await client.get("/api/incident")).json()
    view = (await client.get("/api/incident/door-plan")).json()
    full = view["door_plan"]
    assert view["plan_revision"] == after["plan_revision"] and after["plan"]["label"] == "fallback"
    assert full["geometry_revision"] == after["geometry_revision"], "drawn on the real venue, not the stuck copy"
    assert full["chosen"]["candidate_hash"] == after["plan"]["candidate_hash"]
    assert full["chosen"]["completed_crossings"] == after["plan"]["completed_crossings"]
    d9 = next(d for d in full["doors"] if d["id"] == "D9")
    assert d9["state"] == "closed" and "stuck closed" in d9["reason"]
    reset = await client.post("/api/incident/reset")
    assert reset.status_code == 200 and (await client.get("/api/incident/door-plan")).json()["door_plan"] is None


async def test_a_venue_rebind_is_published_as_a_reset(client, manager):
    """Other screens must drop the old venue's gates and approvals when another client moves the incident."""
    venue_registry().save_venue(VenueV2.model_validate(HOME), {"name": "Test flat"})
    first = (await client.get("/api/incident")).json()
    before = manager.hub.last_id
    await client.post("/api/incident/hazards", json={"venue_id": "home-flat", "expected_plan_revision": first["plan_revision"], "hazards": []})
    frames = [frame for _, frame in manager.hub.events_since(before)]
    first_event = parse(frames[0])
    assert first_event["event"] == "reset", frames[0]
    assert json.loads(first_event["data"])["state"]["venue_id"] == "home-flat"


async def test_second_venue_has_no_gates_and_signs_follow_the_plan(client, manager):
    venue_registry().save_venue(VenueV2.model_validate(HOME), {"name": "Test flat"})
    first = (await client.get("/api/incident")).json()
    response = await client.post("/api/incident/hazards", json={
        "venue_id": "home-flat", "expected_plan_revision": first["plan_revision"],
        "hazards": []})
    assert response.status_code == 200, response.text
    state = response.json()
    assert state["venue_id"] == "home-flat" and state["controller"]["gates"] == []
    assert all(d["applied"] == "sign" and not d["controllable"] for d in state["plan"]["doors"])
    approval = await client.post("/api/incident/approve", json=approve_body(state))
    assert approval.status_code == 200 and approval.json()["status"] == "applied" and approval.json()["commands"] == {}


# -- SSE -------------------------------------------------------------------------------------------------------------

def parse(frame: str):
    out = {}
    for line in frame.strip().split("\n"):
        key, _, value = line.partition(": ")
        out[key] = value
    return out


async def take(stream, count, timeout=1.0):
    return [await asyncio.wait_for(stream.__anext__(), timeout) for _ in range(count)]


async def test_sse_snapshot_ids_and_replay_from_last_event_id(client, manager):
    state = await plan_with(client, HALL_FIRE)
    await approve(client, manager, state)
    hub = manager.hub
    first = hub.stream(None, manager.snapshot)
    snap = parse((await take(first, 1))[0])
    assert snap["event"] == "snapshot" and "id" not in snap
    assert json.loads(snap["data"])["state"]["venue_id"] == "building-v2"
    await first.aclose()

    ids = [i for i, _ in hub.events_since(0)]
    assert ids == sorted(ids) and len(ids) >= 6  # plan, approval, command, ack, transit, observed, approval
    cut = ids[2]
    resumed = hub.stream(cut, manager.snapshot)
    frames = [parse(f) for f in await take(resumed, len(ids) - 3)]
    assert [int(f["id"]) for f in frames] == ids[3:]
    assert {f["event"] for f in frames} <= {"plan", "gate", "approval", "fault", "reset"}
    # A live event arrives after the backlog; an idle stream pings.
    hub.publish("fault", {"line": "x"})
    live = parse((await take(resumed, 1))[0])
    assert live["event"] == "fault" and int(live["id"]) == ids[-1] + 1
    hub.ping_seconds = 0.02
    assert (await take(resumed, 1))[0] == ": ping\n\n"
    await resumed.aclose()
    assert hub._subscribers == []


async def test_sse_gap_beyond_buffer_falls_back_to_snapshot():
    hub = EventHub(replay_limit=3)
    for i in range(10):
        hub.publish("gate", {"n": i})
    stream = hub.stream(2, lambda: {"state": {}})
    assert parse((await take(stream, 1))[0])["event"] == "snapshot"
    await stream.aclose()


async def test_events_route_streams_with_headers(client, manager):
    from backend.app.incident.routes import build_incident_router

    route = next(r for r in build_incident_router(manager).routes if r.path == "/api/incident/events")

    class Req:
        headers = {"last-event-id": "0"}

    response = await route.endpoint(Req(), None)
    assert response.media_type == "text/event-stream" and response.headers["cache-control"] == "no-cache"
    await response.body_iterator.aclose()
