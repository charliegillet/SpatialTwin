"""Offline tests for the building-v2 door investigation. No network, no key; the SDK is the real pinned one."""
import asyncio
import json
import socket
from types import SimpleNamespace as NS

import httpx
import pytest
from fastapi import FastAPI
from google import genai

from backend.app.ai.managed.adapter import ManagedAgentAdapter, MODEL
from backend.app.ai.managed.door_agent import (
    DoorAgentRunner, DoorToolbox, LOCAL_LABEL, parse_recommendation,
)
from backend.app.hazard.door_planner import plan_doors
from backend.app.state.manager import StateManager
from backend.app.state.service import ScenarioService
from backend.app.state.store import SQLiteStore
from backend.app.venues import agent as agent_routes
from backend.app.venues.agent import build_door_agent_router
from backend.app.venues.model import load_building_v2
from backend.app.venues.schemas import DoorPlanRequest

FIRE = {"id": "h0", "type": "FIRE", "position": {"x": 20, "y": 4}, "source": "simulated"}
GAS = {"id": "g0", "type": "GAS", "position": {"x": 20, "y": 14}, "source": "simulated"}
BEST = {"D4": "closed", "D9": "open"}  # checker's best for FIRE at (20, 4): 125 of 125


@pytest.fixture(autouse=True)
def network_disabled(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Unexpected network in offline managed tests")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


@pytest.fixture
def service(tmp_path):
    return ScenarioService(StateManager(SQLiteStore(str(tmp_path / "state.sqlite3"))))


@pytest.fixture(scope="module")
def venue():
    return load_building_v2()


def call(call_id, name, arguments=None):
    return {"type": "function_call", "id": call_id, "name": name, "arguments": arguments or {}}


def response(status="completed", steps=None, identifier="i-1", tokens=10, model=MODEL, text=""):
    return NS(id=identifier, environment_id="env-1", model=model, status=status, steps=steps or [],
              usage=NS(total_tokens=tokens), output_text=text)


class Provider:
    def __init__(self, creates, gets=()):
        self.creates, self.gets = list(creates), list(gets)
        self.create_calls, self.cancel_calls = [], []
        self.aio = NS(interactions=self)

    async def create(self, **kwargs):
        self.create_calls.append(kwargs)
        value = self.creates.pop(0)
        if callable(value):
            return await value()
        return value

    async def get(self, **kwargs):
        value = self.gets.pop(0)
        return await value() if callable(value) else value

    async def cancel(self, **kwargs):
        self.cancel_calls.append(kwargs)
        return response("cancelled")


def make_adapter(service, provider=None):
    return ManagedAgentAdapter(service, api_key="", client=provider, poll_interval=0.001)


def plan_request(*hazards):
    return DoorPlanRequest(hazards=list(hazards))


def compare(call_id, states):
    return call(call_id, "compare_door_states", states)


def final(text, identifier="i-2"):
    return response(identifier=identifier, text=text)


async def run(service, provider, venue, mode="live", hazards=(FIRE,), deadline=30.0):
    runner = DoorAgentRunner(make_adapter(service, provider))
    return await runner.run(venue, plan_request(*hazards), "dinv-test", mode, deadline), runner


# --- runner ---------------------------------------------------------------------------------------------------

async def test_live_run_calls_plan_then_compare_and_agrees(service, venue, monkeypatch):
    requests = []

    async def fake_send(self, request, *args, **kwargs):
        body = json.loads(request.content)
        requests.append(body)
        step = len(requests)
        if step == 1:
            payload = {"status": "requires_action", "steps": [call("c1", "plan_doors")]}
        elif step == 2:
            payload = {"status": "requires_action", "steps": [compare("c2", BEST)]}
        else:
            text = "The closed D4 with an open D9 keeps every modeled crossing.\nRECOMMENDATION: D4=closed D9=open"
            payload = {"status": "completed", "steps": [{"type": "model_output", "content": [{"type": "text", "text": text}]}]}
        payload.update(id=f"sdk-{step}", environment_id="env-1", model=MODEL, usage={"total_tokens": 10 * step})
        return httpx.Response(200, json=payload, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)
    adapter = make_adapter(service, genai.Client(api_key="offline-placeholder"))
    result = await DoorAgentRunner(adapter).run(venue, plan_request(FIRE), "dinv-sdk", "live", 30.0)
    assert result.status.value == "completed", result.errors
    assert result.provenance == "live" and result.provider_model == MODEL
    assert result.provider_interaction_id == "sdk-3" and result.provider_environment_id == "env-1"
    assert result.recommended_door_states == BEST == result.checked_best_door_states
    assert result.agrees_with_checker and "agree" in result.agreement_note
    assert (result.checked_best_completed, result.initial_population, result.total_states) == (125, 125, 4)
    assert [e.function_name for e in result.tool_ledger] == ["plan_doors", "compare_door_states"]
    assert all(e.status == "executed" for e in result.tool_ledger)
    assert result.token_usage == {"total_tokens": 60}
    assert "RECOMMENDATION" not in result.explanation and result.explanation.startswith("The closed D4")
    # Request shape: background, network posture of the adapter, client-executed function tools, continuation.
    first = requests[0]
    assert first["background"] is True and first["agent"] == adapter.agent
    assert [t["name"] for t in first["tools"]] == ["plan_doors", "compare_door_states"]
    assert first["tools"][1]["parameters"]["required"] == ["D4", "D9"]
    assert "synthetic population" in first["system_instruction"] and "simulated" in first["system_instruction"].lower()
    assert requests[1]["previous_interaction_id"] == "sdk-1" and requests[2]["previous_interaction_id"] == "sdk-2"
    sent = json.loads(requests[1]["input"][0]["result"])
    assert sent["chosen_door_states"] == BEST and sent["completed_crossings"] == 125 and "timeline" not in sent
    events = [e["phase"] for e in await adapter.get_progress("dinv-sdk")]
    assert "plan_ready" in events and events.count("provider_request") >= 3 and "local_tool_complete" in events
    await adapter.aclose()


async def test_disagreement_reports_both_and_keeps_checker(service, venue):
    provider = Provider(
        [response("requires_action", [call("c1", "plan_doors"), compare("c2", {"D4": "open", "D9": "closed"})], tokens=5),
         final("Opening D4 looks natural.\nRECOMMENDATION: D4=open D9=closed")])
    result, _ = await run(service, provider, venue)
    assert result.status.value == "completed"
    assert not result.agrees_with_checker
    assert result.recommended_door_states == {"D4": "open", "D9": "closed"}
    assert result.checked_best_door_states == BEST
    assert result.recommended_outcome["completed_crossings"] == 102
    assert result.agreement_note == "Agent suggested D4 open, D9 closed; the checker's best is D4 closed, D9 open."


async def test_unparsed_recommendation_is_not_agreement(service, venue):
    provider = Provider([response("requires_action", [call("c1", "plan_doors")], tokens=5), final("Looks fine.")])
    result, _ = await run(service, provider, venue)
    assert result.status.value == "completed" and result.recommended_door_states is None
    assert not result.agrees_with_checker and "recommendation_unparsed" in result.errors


async def test_no_tool_evidence_is_incomplete(service, venue):
    provider = Provider([response(text="RECOMMENDATION: D4=closed D9=open")])
    result, _ = await run(service, provider, venue)
    assert result.status.value == "incomplete" and "tool_evidence_missing" in result.errors
    assert result.recommended_door_states is None and not result.agrees_with_checker
    assert result.checked_best_door_states == BEST


async def test_tool_call_cap(service, venue):
    calls = [call(f"c{i}", "plan_doors") for i in range(7)]
    provider = Provider([response("requires_action", calls, tokens=5)])
    result, _ = await run(service, provider, venue)
    assert result.status.value == "failed" and "tool_call_limit" in result.errors
    assert len(result.tool_ledger) == 6
    assert result.recommended_door_states is None and result.checked_best_completed == 125
    assert provider.cancel_calls  # the remote run is cancelled, as in the tabletop


async def test_invalid_door_state_is_rejected_and_reported_to_the_agent(service, venue):
    provider = Provider(
        [response("requires_action", [compare("c1", {"D4": "ajar", "D9": "open"})], tokens=5),
         final("RECOMMENDATION: D4=closed D9=open")])
    result, _ = await run(service, provider, venue)
    rejected = result.tool_ledger[0]
    assert rejected.status == "failed" and rejected.error == "invalid_door_state"
    sent = json.loads(provider.create_calls[1]["input"][0]["result"])
    assert sent == {"error": "invalid_door_state"}
    # No executed tool call: the run cannot claim evidence.
    assert result.status.value == "incomplete" and "tool_evidence_missing" in result.errors


def test_toolbox_rejects_gas_locked_unknown_and_incomplete_states(venue):
    toolbox = DoorToolbox(plan_doors(venue, plan_request(GAS)))
    assert toolbox.free == ["D9"] and toolbox.locked == ["D4"]
    ok = toolbox.run("compare_door_states", {"D9": "open"})
    assert ok["completed_crossings"] == 125 and ok["is_valid"]
    for arguments, code in [({"D4": "open", "D9": "open"}, "door_gas_locked"),
                            ({"D1": "open", "D9": "open"}, "door_not_controllable"),
                            ({}, "invalid_tool_arguments"), ({"D9": 1}, "invalid_door_state"),
                            ({"D9": "OPEN"}, "invalid_door_state")]:
        with pytest.raises(Exception) as error:
            toolbox.run("compare_door_states", arguments)
        assert str(error.value) == code
    with pytest.raises(Exception):
        toolbox.run("plan_doors", {"x": 1})
    summary = toolbox.run("plan_doors", {})
    assert summary["gas_locked_doors"] == ["D4"] and summary["free_doors"] == ["D9"]
    assert summary["is_valid"] is True and summary["states_checked"] == 2


def test_parse_recommendation():
    free = ["D4", "D9"]
    assert parse_recommendation("x\nRECOMMENDATION: D4=closed D9=open", free) == {"D4": "closed", "D9": "open"}
    assert parse_recommendation("recommendation: d9: Open, d4: CLOSED", free) == {"D4": "closed", "D9": "open"}
    assert parse_recommendation("RECOMMENDATION: D4=open", free) is None
    assert parse_recommendation("RECOMMENDATION: D4=open D9=open D1=open", free) is None
    assert parse_recommendation("RECOMMENDATION: D4=open D4=closed D9=open", free) is None
    assert parse_recommendation("no marker D4=open D9=open", free) is None


async def test_local_mode_has_no_provider_call(service, venue):
    provider = Provider([])
    result, _ = await run(service, provider, venue, mode="local")
    assert result.status.value == "completed" and result.provenance == "local"
    assert result.provider_interaction_id is None and result.provider_model is None and result.token_usage == {}
    assert result.recommended_door_states == BEST and result.agrees_with_checker
    assert result.explanation.startswith(LOCAL_LABEL) and "125 of 125" in result.explanation
    assert [e.function_name for e in result.tool_ledger] == ["plan_doors", "compare_door_states"]
    assert result.agreement_note == "Local solver: the checker's best is D4 closed, D9 open."
    assert not provider.create_calls


async def test_live_without_key_is_unavailable(service, venue):
    result, _ = await run(service, None, venue)
    assert result.status.value == "failed" and result.provenance == "unavailable"
    assert result.errors == ["configuration_missing"]
    assert result.recommended_door_states is None and result.token_usage == {} and result.tool_ledger == []
    assert result.checked_best_door_states == BEST


async def test_model_mismatch_fails_closed(service, venue):
    provider = Provider([response("requires_action", [call("c1", "plan_doors")], model="gemini-other")])
    result, _ = await run(service, provider, venue)
    assert result.status.value == "failed" and "provider_model_mismatch" in result.errors
    assert result.recommended_door_states is None and not result.agrees_with_checker


async def test_provider_rejection_is_classified_like_the_tabletop(service, venue):
    class Rejected(Exception):
        status_code = 429
    async def boom():
        raise Rejected()
    result, _ = await run(service, Provider([boom]), venue)
    assert result.status.value == "failed" and result.errors == ["provider_rate_limited"]


async def test_deadline_times_out(service, venue):
    async def hang():
        await asyncio.sleep(30)
    result, _ = await run(service, Provider([hang]), venue, deadline=0.5)
    assert result.status.value == "timed_out" and "investigation_deadline" in result.errors


# --- routes ---------------------------------------------------------------------------------------------------

@pytest.fixture
def make_client(service):
    clients = []

    def build(provider=None, slots=None):
        adapter = make_adapter(service, provider)
        app = FastAPI()
        app.include_router(build_door_agent_router(adapter, slots or asyncio.Semaphore(2), lambda: True))
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        clients.append(client)
        return client
    yield build
    for client in clients:
        asyncio.get_event_loop_policy()  # clients are closed by the loop teardown; nothing else to release


async def poll(client, investigation_id, until=("running",), timeout=10.0):
    end = asyncio.get_running_loop().time() + timeout
    while True:
        body = (await client.get(f"/api/venues/building-v2/investigations/{investigation_id}")).json()
        if body["status"] not in until:
            return body
        assert asyncio.get_running_loop().time() < end
        await asyncio.sleep(0.01)


async def test_route_local_flow_and_progress(make_client):
    client = make_client()
    started = await client.post("/api/venues/building-v2/investigate", json={"hazards": [FIRE], "mode": "local"})
    assert started.status_code == 200
    investigation_id = started.json()["investigation_id"]
    body = await poll(client, investigation_id)
    assert body["status"] == "completed"
    assert body["investigation"]["provenance"] == "local"
    assert [e["phase"] for e in body["provider_progress"]][0] == "plan_ready"
    assert body["investigation"]["checked_best_door_states"] == BEST
    missing = await client.get("/api/venues/building-v2/investigations/nope")
    assert missing.status_code == 404
    unknown = await client.post("/api/venues/other/investigate", json={"hazards": [], "mode": "local"})
    assert unknown.status_code == 404


async def test_route_live_without_key_reports_configuration_missing(make_client):
    client = make_client()
    started = await client.post("/api/venues/building-v2/investigate", json={"hazards": [FIRE], "mode": "live"})
    body = await poll(client, started.json()["investigation_id"])
    assert body["status"] == "failed"
    assert body["investigation"]["provenance"] == "unavailable"
    assert body["investigation"]["errors"] == ["configuration_missing"]


async def test_route_live_with_mocked_provider(make_client):
    provider = Provider([response("requires_action", [call("c1", "plan_doors"), compare("c2", BEST)], tokens=5),
                         final("Fine.\nRECOMMENDATION: D4=closed D9=open")])
    client = make_client(provider)
    started = await client.post("/api/venues/building-v2/investigate", json={"hazards": [FIRE], "mode": "live"})
    body = await poll(client, started.json()["investigation_id"])
    assert body["status"] == "completed" and body["investigation"]["agrees_with_checker"] is True
    assert body["investigation"]["provenance"] == "live"


@pytest.mark.parametrize("hazard, code", [
    ({**FIRE, "source": "camera"}, "unconfirmed_camera_hazard"),
    ({**FIRE, "source": "camera", "proposal_id": "nope"}, "unconfirmed_camera_hazard"),
])
async def test_route_unconfirmed_camera_hazard_is_422(make_client, hazard, code):
    client = make_client(Provider([]))
    response_ = await client.post("/api/venues/building-v2/investigate", json={"hazards": [hazard], "mode": "live"})
    assert response_.status_code == 422 and response_.json() == {"detail": {"code": code}}


async def test_route_validates_like_door_plan(make_client):
    client = make_client(Provider([]))
    for payload, code in [({"hazards": [{**FIRE, "position": {"x": 99, "y": 99}}]}, "outside_building"),
                          ({"hazards": [FIRE], "horizon_seconds": 7}, "invalid_horizon")]:
        r = await client.post("/api/venues/building-v2/investigate", json={**payload, "mode": "live"})
        assert r.status_code == 422 and r.json() == {"detail": {"code": code}}
    r = await client.post("/api/venues/building-v2/investigate", json={"hazards": [FIRE], "mode": "live", "deadline_seconds": 61})
    assert r.status_code == 422


async def test_route_429_when_slots_full(make_client):
    slots = asyncio.Semaphore(2)
    await slots.acquire()
    await slots.acquire()
    client = make_client(Provider([]), slots)
    r = await client.post("/api/venues/building-v2/investigate", json={"hazards": [FIRE], "mode": "live"})
    assert r.status_code == 429


async def test_route_slot_released_after_run(make_client):
    slots = asyncio.Semaphore(1)
    client = make_client(None, slots)
    started = await client.post("/api/venues/building-v2/investigate", json={"hazards": [FIRE], "mode": "local"})
    assert slots.locked()
    await poll(client, started.json()["investigation_id"])
    for _ in range(100):
        if not slots.locked():
            break
        await asyncio.sleep(0.01)
    assert not slots.locked()


async def test_route_cancel_mid_run(make_client):
    gate = asyncio.Event()

    async def hang():
        await gate.wait()
    provider = Provider([hang])
    slots = asyncio.Semaphore(1)
    client = make_client(provider, slots)
    started = await client.post("/api/venues/building-v2/investigate", json={"hazards": [FIRE], "mode": "live"})
    investigation_id = started.json()["investigation_id"]
    for _ in range(200):  # wait until the provider call is in flight
        if provider.create_calls:
            break
        await asyncio.sleep(0.01)
    cancelled = await client.post(f"/api/venues/building-v2/investigations/{investigation_id}/cancel")
    assert cancelled.json() == {"status": "cancellation_requested"}
    body = await poll(client, investigation_id)
    assert body["status"] == "cancelled"
    assert body["investigation"]["errors"][0] == "investigation_cancelled"
    assert body["investigation"]["recommended_door_states"] is None
    assert body["investigation"]["agrees_with_checker"] is False
    again = await client.post(f"/api/venues/building-v2/investigations/{investigation_id}/cancel")
    assert again.json()["status"] == "already_finished"
    assert (await client.post("/api/venues/building-v2/investigations/nope/cancel")).status_code == 404
    for _ in range(100):
        if not slots.locked():
            break
        await asyncio.sleep(0.01)
    assert not slots.locked()
