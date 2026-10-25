"""Regression tests for review findings on the incident mirror: no movement after Reset, no venue swap mid-plan,
and a fresh snapshot for a browser that reconnects with an id from before a server restart."""
import asyncio
import time

from backend.app.incident import manager as manager_module
from backend.app.incident.events import EventHub
from backend.app.venues.model import VenueV2
from backend.app.venues.registry import venue_registry
from tests.incident.conftest import HALL_FIRE, HOME, approve_body, plan_with


def gate(state, gate_id):
    return next(g for g in state["controller"]["gates"] if g["gate_id"] == gate_id)


async def test_reset_before_the_approval_task_runs_moves_nothing(client, manager):
    state = await plan_with(client, HALL_FIRE)
    # Approve and reset in the same event-loop turn: the actuation task is queued but has not started.
    await manager.approve(manager_module.ApproveRequest.model_validate(approve_body(state)))
    await manager.reset()
    await manager.wait_idle()
    after = (await client.get("/api/incident")).json()
    assert gate(after, "D4")["state"] == "CLOSED" and gate(after, "D4")["observed"] == "closed"
    assert after["plan"] is None and after["approvals"] == []


async def test_a_poll_during_planning_never_swaps_the_venue(client, manager, monkeypatch):
    venue_registry().save_venue(VenueV2.model_validate(HOME), {})   # accepted, but building-v2 stays active
    real = manager_module.plan_doors

    def slow(venue, request):
        time.sleep(0.15)
        return real(venue, request)

    monkeypatch.setattr(manager_module, "plan_doors", slow)
    hazard = {"id": "h0", "type": "SMOKE", "position": {"x": 9, "y": 8}, "source": "simulated"}
    current = (await client.get("/api/incident")).json()
    posting = asyncio.create_task(client.post("/api/incident/hazards", json={
        "venue_id": "home-flat", "expected_plan_revision": current["plan_revision"], "hazards": [hazard]}))
    await asyncio.sleep(0.05)   # the planner thread is running for home-flat
    polled = (await client.get("/api/incident")).json()
    assert polled["venue_id"] == "home-flat"
    done = await posting
    assert done.status_code == 200, done.text
    assert done.json()["venue_id"] == "home-flat" and done.json()["plan"]["valid"]


async def test_an_id_from_before_a_restart_gets_a_snapshot():
    hub = EventHub(ping_seconds=0.05)
    hub.publish("plan", {"n": 1})
    stream = hub.stream(17, lambda: {"state": "fresh"})
    first = await stream.__anext__()
    await stream.aclose()
    assert first.startswith("event: snapshot") and '"state":"fresh"' in first
