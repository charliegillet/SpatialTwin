"""Offline tests for the door investigation's Strategist lane and its routes. No network, no key.

The SDK-level tests drive the real pinned google-genai 2.33 client through a fake httpx transport, so request
bodies and parsed stream events are the SDK's own. Other tests use the recorded-shape fake in tests/agents/fakes.py.
"""
import asyncio
import json
import socket

import httpx
import pytest
from fastapi import FastAPI
from google import genai

from backend.app.ai.managed.adapter import ManagedAgentAdapter, MODEL
from backend.app.ai.managed.door_agent import (
    LOCAL_LABEL, DoorAgentRunner, DoorToolbox, parse_recommendation,
)
from backend.app.ai.managed.robustness import ScenarioEvaluator
from backend.app.hazard.door_planner import plan_doors
from backend.app.state.manager import StateManager
from backend.app.state.service import ScenarioService
from backend.app.state.store import SQLiteStore
from backend.app.venues import agent as agent_routes
from backend.app.venues.agent import build_door_agent_router
from backend.app.venues.model import VenueV2, load_building_v2
from backend.app.venues.schemas import DoorPlanRequest
from tests.agents.fakes import (
    BEST, ENV_ID, FIRE, GAS, HttpError, Provider, call, claims_for, final, interaction_id, response, submit,
)


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


@pytest.fixture(scope="module")
def evaluator(venue):
    return ScenarioEvaluator(venue, plan_request(FIRE))


def make_adapter(service, provider=None):
    return ManagedAgentAdapter(service, api_key="", client=provider, poll_interval=0.001)


def plan_request(*hazards):
    return DoorPlanRequest(hazards=list(hazards))


async def run(service, provider, venue, mode="live", hazards=(FIRE,), deadline=30.0, investigation_id="dinv-test",
              **runner_kwargs):
    runner = DoorAgentRunner(make_adapter(service, provider), retry_base=0.001, acknowledge=False, **runner_kwargs)
    return await runner.run(venue, plan_request(*hazards), investigation_id, mode, deadline), runner


# --- SDK level ------------------------------------------------------------------------------------------------

def sse(events):
    return "".join(f"event: {e['event_type']}\ndata: {json.dumps(e)}\n\n" for e in events) + "data: [DONE]\n\n"


async def test_strategist_streams_submits_once_and_publishes_at_requires_action(service, venue, evaluator, monkeypatch):
    requests = []
    first = interaction_id(1)
    claims = claims_for(evaluator, BEST, ["baseline"]) + [
        {**claims_for(evaluator, {"D4": "open", "D9": "closed"}, ["baseline"])[0], "applies_to": "fallback"}]
    submission = submit("call_886447", BEST, {"D4": "open", "D9": "closed"}, claims,
                        "D9 open carries all 125 modeled crossings; D4 adds none.")

    async def fake_send(self, request, *args, **kwargs):
        body = json.loads(request.content) if request.content else {}
        requests.append((request.method, request.url.path, body, dict(request.headers)))
        if request.method == "POST" and body.get("stream"):
            events = [
                {"event_type": "interaction.created", "event_id": "e1",
                 "interaction": {"id": first, "status": "in_progress", "model": MODEL}},
                {"event_type": "step.start", "event_id": "e2", "index": 0,
                 "step": {"type": "function_call", "id": "call_886447", "name": "submit_recommendation",
                          "arguments": {}}},
                {"event_type": "step.delta", "event_id": "e3", "index": 0,
                 "delta": {"type": "arguments_delta", "arguments": json.dumps(submission["arguments"])}},
                {"event_type": "step.stop", "event_id": "e4", "index": 0,
                 "usage": {"total_tokens": 5333, "total_input_tokens": 5304, "total_output_tokens": 16,
                           "total_cached_tokens": 0}},
                {"event_type": "interaction.status_update", "event_id": "e5", "interaction_id": first,
                 "status": "requires_action"}]
            return httpx.Response(200, text=sse(events), headers={"content-type": "text/event-stream"},
                                  request=request)
        if request.method == "GET":
            payload = {"id": first, "status": "requires_action", "steps": [submission]}
        else:  # the acknowledging continuation
            payload = {"id": interaction_id(2), "status": "in_progress", "steps": []}
        payload.update(environment_id=ENV_ID, model=MODEL,
                       usage={"total_tokens": 5333, "total_input_tokens": 5304, "total_output_tokens": 16,
                              "total_thought_tokens": 13, "total_cached_tokens": 0})
        return httpx.Response(200, json=payload, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)
    adapter = make_adapter(service, genai.Client(api_key="offline-placeholder"))
    runner = DoorAgentRunner(adapter)
    result = await runner.run(venue, plan_request(FIRE), "dinv-sdk", "live", 30.0)
    await runner.wait_background()
    assert result.status.value == "completed", result.errors
    assert result.provenance == "live" and result.provider_model == MODEL and result.lane == "strategist"
    assert result.recommended_door_states == BEST == result.checked_best_door_states
    assert result.agrees_with_checker and result.recommendation_source == "submit_recommendation"
    assert result.verification.verified == result.verification.total == 2 and not result.verification.mismatches
    assert result.fallback_if_jammed == {"D4": "open", "D9": "closed"}
    assert result.explanation.startswith("D9 open carries all 125")
    assert result.stream["used"] and result.stream["steps"] == 1 and not result.stream["drops"]
    assert result.cost_estimate["usd"] > 0 and result.token_budget == 40_000
    assert result.venue_id == "building-v2" and result.deadline_at.endswith("Z")
    assert [e.function_name for e in result.tool_ledger] == ["submit_recommendation"]
    # Request shapes: one streamed background create, one non-streaming get, one acknowledgement off the critical path.
    method, path, body, headers = requests[0]
    assert method == "POST" and body["background"] is True and body["stream"] is True and body["store"] is True
    assert headers["accept"] == "text/event-stream"
    # The SDK serialises the int64 budget as a JSON string.
    assert body["agent_config"] == {"type": "antigravity", "model": MODEL, "max_total_tokens": "40000"}
    assert [t["name"] for t in body["tools"]] == ["submit_recommendation"]
    params = body["tools"][0]["parameters"]
    assert params["required"] == ["door_states", "fallback_if_jammed", "claims", "rationale"]
    assert params["properties"]["claims"]["maxItems"] == 12
    assert params["properties"]["door_states"]["required"] == ["D4", "D9"]
    assert "Checked plan" in body["input"] and "candidate_hash" in body["input"]
    assert "synthetic population" in body["system_instruction"]
    assert requests[1][0] == "GET" and requests[1][1].endswith(first)
    ack = requests[2][2]
    assert ack["previous_interaction_id"] == first and ack["environment"] == ENV_ID and ack["background"] is True
    assert ack["input"][0]["type"] == "function_result" and ack["input"][0]["call_id"] == "call_886447"
    acked = json.loads(ack["input"][0]["result"])
    assert acked["verified"] == 2 and acked["accepted"] is True
    phases = [e["phase"] for e in await adapter.get_progress("dinv-sdk")]
    assert "plan_ready" in phases and "submission_verified" in phases and "ack_sent" in phases
    await adapter.aclose()


# --- runner -----------------------------------------------------------------------------------------------------

async def test_disagreement_reports_both_and_keeps_checker(service, venue):
    provider = Provider([response("requires_action", [submit("c1", {"D4": "open", "D9": "closed"})], tokens=5)])
    result, _ = await run(service, provider, venue)
    assert result.status.value == "completed"
    assert not result.agrees_with_checker and result.recommended_ties_checked_best is False
    assert result.recommended_door_states == {"D4": "open", "D9": "closed"}
    assert result.checked_best_door_states == BEST
    assert result.recommended_outcome["completed_crossings"] == 102
    assert result.agreement_note == "Agent suggested D4 open, D9 closed; the checker's best is D4 closed, D9 open."
    assert len(provider.create_calls) == 1  # terminal at requires_action: no continuation on the critical path


async def test_mismatching_claims_are_reported_not_hidden(service, venue, evaluator):
    claims = claims_for(evaluator, BEST, ["baseline", "stuck_closed:D9"], tamper=1)
    claims.append({"scenario": "stuck_closed:D99", "completed_crossings": 1})
    provider = Provider([response("requires_action", [submit("c1", BEST, claims=claims)], tokens=5)])
    result, _ = await run(service, provider, venue)
    assert result.status.value == "completed" and result.agrees_with_checker
    v = result.verification
    assert (v.verified, v.total) == (1, 3)
    reasons = {m["scenario"]: m["reason"] for m in v.mismatches}
    assert reasons == {"stuck_closed:D9": "crossings_mismatch", "stuck_closed:D99": "unknown_fault_door"}
    tampered = next(m for m in v.mismatches if m["scenario"] == "stuck_closed:D9")
    assert tampered["claimed_completed_crossings"] == tampered["local_completed_crossings"] + 1


async def test_text_fallback_when_the_agent_does_not_submit(service, venue):
    provider = Provider([response(text="D9 alone is enough.\nRECOMMENDATION: D4=closed D9=open")])
    result, _ = await run(service, provider, venue)
    assert result.status.value == "completed" and result.recommended_door_states == BEST
    assert result.recommendation_source == "text_fallback" and "recommendation_from_text" in result.errors
    assert result.explanation == "D9 alone is enough." and result.verification is None


async def test_unparsed_recommendation_is_not_agreement(service, venue):
    provider = Provider([response(text="Looks fine.")])
    result, _ = await run(service, provider, venue)
    assert result.status.value == "completed" and result.recommended_door_states is None
    assert not result.agrees_with_checker and "recommendation_unparsed" in result.errors


async def test_tool_call_cap(service, venue):
    calls = [submit(f"c{i}", {"D4": "ajar", "D9": "open"}) for i in range(4)]
    provider = Provider([response("requires_action", calls, tokens=5)])
    result, _ = await run(service, provider, venue)
    assert result.status.value == "failed" and "tool_call_limit" in result.errors
    assert len(result.tool_ledger) == 3
    assert result.recommended_door_states is None and result.checked_best_completed == 125
    assert provider.cancel_calls  # the remote run is cancelled, as in the tabletop


async def test_invalid_submission_is_rejected_then_corrected(service, venue):
    provider = Provider([
        response("requires_action", [submit("c1", {"D4": "ajar", "D9": "open"})], tokens=5),
        response("requires_action", [submit("c2")], identifier=interaction_id(2), tokens=9)])
    result, _ = await run(service, provider, venue)
    rejected = result.tool_ledger[0]
    assert rejected.status == "failed" and rejected.error == "invalid_door_state"
    assert json.loads(provider.create_calls[1]["input"][0]["result"]) == {"error": "invalid_door_state"}
    assert provider.create_calls[1]["previous_interaction_id"] == interaction_id(1)
    assert result.status.value == "completed" and result.recommended_door_states == BEST
    assert result.token_usage["total_tokens"] == 14


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


def test_submission_schema_is_strict(venue, evaluator):
    toolbox = DoorToolbox(plan_doors(venue, plan_request(FIRE)), evaluator)
    good = submit("c", BEST)["arguments"]
    assert toolbox.parse_submission(good).door_states == BEST
    cases = [({**good, "extra": 1}, "invalid_tool_arguments"),
             ({k: v for k, v in good.items() if k != "rationale"}, "invalid_tool_arguments"),
             ({**good, "fallback_if_jammed": {"D9": "open"}}, "invalid_tool_arguments"),
             ({**good, "claims": [{"scenario": "baseline", "completed_crossings": 1}] * 13}, "too_many_claims"),
             ({**good, "claims": [{"scenario": "baseline", "completed_crossings": "125"}]}, "invalid_claim"),
             ({**good, "claims": [{"scenario": "baseline", "completed_crossings": 1, "note": "x"}]}, "invalid_claim"),
             ({**good, "claims": [{"scenario": "baseline", "completed_crossings": 1, "applies_to": "x"}]},
              "invalid_claim")]
    for arguments, code in cases:
        with pytest.raises(Exception) as error:
            toolbox.parse_submission(arguments)
        assert str(error.value) == code
    long = toolbox.parse_submission({**good, "rationale": "x" * 900})
    assert len(long.rationale) == 400 and long.warnings == ["rationale_truncated"]
    schema = toolbox.submit_definition()["parameters"]
    assert schema["additionalProperties"] is False and schema["properties"]["rationale"]["maxLength"] == 400


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
    assert result.status.value == "completed" and result.provenance == "local" and result.label == LOCAL_LABEL
    assert result.provider_interaction_id is None and result.provider_model is None and result.token_usage == {}
    assert result.recommended_door_states == BEST and result.agrees_with_checker
    assert result.explanation.startswith(LOCAL_LABEL) and "125 of 125" in result.explanation
    assert [e.function_name for e in result.tool_ledger] == ["plan_doors", "compare_door_states"]
    assert result.agreement_note == "Local solver: the checker's best is D4 closed, D9 open."
    assert result.verification.source == "local" and result.verification.verified == result.verification.total == 1
    assert result.cost_estimate is None and not provider.create_calls


async def test_live_without_key_is_unavailable(service, venue):
    result, _ = await run(service, None, venue)
    assert result.status.value == "failed" and result.provenance == "unavailable"
    assert result.errors == ["configuration_missing"]
    assert result.recommended_door_states is None and result.token_usage == {} and result.tool_ledger == []
    assert result.checked_best_door_states == BEST and result.label == "Unavailable"


async def test_model_mismatch_fails_closed(service, venue):
    provider = Provider([response("requires_action", [submit("c1")], model="gemini-other")])
    result, _ = await run(service, provider, venue)
    assert result.status.value == "failed" and "provider_model_mismatch" in result.errors
    assert result.recommended_door_states is None and not result.agrees_with_checker


async def test_rate_limit_is_retried_inside_the_deadline_then_succeeds(service, venue):
    provider = Provider([HttpError(429), HttpError(503), response("requires_action", [submit("c1")])])
    result, _ = await run(service, provider, venue)
    assert result.status.value == "completed" and result.provider_retries == 2
    phases = [e["phase"] for e in result.provider_progress]
    assert phases.count("provider_retry") == 2
    assert [e.get("code") for e in result.provider_progress if e["phase"] == "provider_retry"] == [
        "provider_rate_limited", "provider_unavailable"]


async def test_rejection_is_classified_after_retries_run_out(service, venue):
    provider = Provider([HttpError(429)] * 4)
    result, _ = await run(service, provider, venue)
    assert result.status.value == "failed" and result.errors == ["provider_rate_limited"]
    assert len(provider.create_calls) == 4  # 1 + MAX_PROVIDER_RETRIES
    denied = Provider([HttpError(403)])
    result, _ = await run(service, denied, venue, investigation_id="dinv-test-2")
    assert result.errors == ["provider_access_denied"] and len(denied.create_calls) == 1  # never retried


async def test_deadline_times_out(service, venue):
    async def hang():
        await asyncio.sleep(30)
    result, _ = await run(service, Provider([hang]), venue, deadline=0.5)
    assert result.status.value == "timed_out" and "investigation_deadline" in result.errors
    assert result.deadline_seconds == 0.5


# --- routes -----------------------------------------------------------------------------------------------------

@pytest.fixture
def make_client(service):
    def build(provider=None, slots=None):
        adapter = make_adapter(service, provider)
        app = FastAPI()
        app.include_router(build_door_agent_router(adapter, slots or asyncio.Semaphore(2), lambda: True))
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    return build


async def poll(client, investigation_id, until=("running",), timeout=10.0, key="status", venue_id="building-v2"):
    end = asyncio.get_running_loop().time() + timeout
    while True:
        body = (await client.get(f"/api/venues/{venue_id}/investigations/{investigation_id}")).json()
        if body[key] not in until:
            return body
        assert asyncio.get_running_loop().time() < end
        await asyncio.sleep(0.01)


async def test_route_local_flow_and_progress(make_client):
    client = make_client()
    started = await client.post("/api/venues/building-v2/investigate", json={"hazards": [FIRE], "mode": "local"})
    assert started.status_code == 200
    payload = started.json()
    assert payload["lanes"]["strategist"]["deadline_seconds"] == 45.0 and payload["deadline_at"].endswith("Z")
    assert payload["trace_url"].endswith("/trace")
    body = await poll(client, payload["investigation_id"])
    assert body["status"] == "completed"
    assert body["investigation"]["provenance"] == "local" and body["investigation"]["venue_id"] == "building-v2"
    assert body["investigation"]["investigation_id"] == payload["investigation_id"]
    assert [e["phase"] for e in body["provider_progress"]][0] == "plan_ready"
    assert body["investigation"]["checked_best_door_states"] == BEST
    assert set(body["lanes"]) == {"strategist"} and body["lanes"]["strategist"]["effective"] == "local"
    missing = await client.get("/api/venues/building-v2/investigations/nope")
    assert missing.status_code == 404
    unknown = await client.post("/api/venues/other/investigate", json={"hazards": [], "mode": "local"})
    assert unknown.status_code == 404


async def test_route_scopes_investigations_to_their_venue(make_client, monkeypatch):
    home = VenueV2.model_validate(json.load(open("tests/venues/fixtures/home_flat.json")))
    real = agent_routes.get_venue
    monkeypatch.setattr(agent_routes, "get_venue", lambda vid: home if vid == "home-flat" else real(vid))
    client = make_client()
    started = await client.post("/api/venues/home-flat/investigate", json={"hazards": [
        {"id": "h0", "type": "FIRE", "position": {"x": 1, "y": 1}, "source": "simulated"}], "mode": "local"})
    investigation_id = started.json()["investigation_id"]
    body = await poll(client, investigation_id, venue_id="home-flat")
    assert body["investigation"]["venue_id"] == "home-flat"
    assert body["investigation"]["geometry_revision"] == home.geometry_revision
    other = await client.get(f"/api/venues/building-v2/investigations/{investigation_id}")
    assert other.status_code == 404 and other.json() == {"detail": {"code": "unknown_investigation"}}
    assert (await client.post(f"/api/venues/building-v2/investigations/{investigation_id}/cancel")).status_code == 404
    assert (await client.get(f"/api/venues/building-v2/investigations/{investigation_id}/trace")).status_code == 404


async def test_route_live_without_key_reports_configuration_missing(make_client):
    client = make_client()
    started = await client.post("/api/venues/building-v2/investigate", json={"hazards": [FIRE], "mode": "live"})
    body = await poll(client, started.json()["investigation_id"])
    assert body["status"] == "failed"
    assert body["investigation"]["provenance"] == "unavailable"
    assert body["investigation"]["errors"] == ["configuration_missing"]
    # The live failure stays visible; the lane falls back to the labelled local lane.
    body = await poll(client, started.json()["investigation_id"], key="team_status")
    lane = body["investigation"]["lanes"]["strategist"]
    assert lane["status"] == "failed" and lane["effective"] == "local_fallback"
    assert lane["fallback"]["provenance"] == "local" and lane["fallback"]["label"].startswith("Local fallback")
    assert lane["fallback"]["recommended_door_states"] == BEST


async def test_route_live_with_mocked_provider(make_client):
    provider = Provider([response("requires_action", [submit("c1")], tokens=5)])
    client = make_client(provider)
    started = await client.post("/api/venues/building-v2/investigate", json={"hazards": [FIRE], "mode": "live"})
    body = await poll(client, started.json()["investigation_id"])
    assert body["status"] == "completed" and body["investigation"]["agrees_with_checker"] is True
    assert body["investigation"]["provenance"] == "live"
    assert body["investigation"]["verification"]["total"] == 0


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
    for extra in ({"deadline_seconds": 91}, {"robustness_deadline_seconds": 241}, {"lanes": []},
                  {"lanes": ["strategist", "strategist", "robustness"]}, {"lanes": ["planner"]}):
        r = await client.post("/api/venues/building-v2/investigate", json={"hazards": [FIRE], "mode": "live", **extra})
        assert r.status_code == 422, extra


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
    await poll(client, started.json()["investigation_id"], key="team_status")
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
    body = await poll(client, investigation_id, key="team_status")
    assert body["investigation"]["lanes"]["strategist"]["fallback"] is None  # a cancellation never falls back
    again = await client.post(f"/api/venues/building-v2/investigations/{investigation_id}/cancel")
    assert again.json()["status"] == "already_finished"
    assert (await client.post("/api/venues/building-v2/investigations/nope/cancel")).status_code == 404
    for _ in range(100):
        if not slots.locked():
            break
        await asyncio.sleep(0.01)
    assert not slots.locked()
