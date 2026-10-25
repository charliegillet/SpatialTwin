"""Agent team: two lanes in parallel, per-lane deadlines, retries, labelled local fallback, terminal submission,
stream drop -> resume -> polling, sandbox environment and environment reuse. Offline, recorded-shape fakes."""
import asyncio
import json

import httpx
import pytest
from fastapi import FastAPI

from backend.app.ai.managed.adapter import ManagedAgentAdapter
from backend.app.ai.managed.door_agent import (
    DoorAgentRunner, deadline_stamp, lane_id,
)
from backend.app.ai.managed.robustness import ScenarioEvaluator
from backend.app.ai.managed.trace import TraceHub
from backend.app.state.manager import StateManager
from backend.app.state.service import ScenarioService
from backend.app.state.store import SQLiteStore
from backend.app.venues.agent import build_door_agent_router
from backend.app.venues.model import load_building_v2
from backend.app.venues.schemas import DoorPlanRequest
from tests.agents.fakes import (
    BEST, ENV_ID, FIRE, ROBUST, FakeStream, HttpError, LaneProvider, claims_for, interaction_id, response,
    stream_events, submit,
)

SID, RID = interaction_id(1), interaction_id(101)
FALLBACK = {"D4": "open", "D9": "closed"}


@pytest.fixture
def service(tmp_path):
    return ScenarioService(StateManager(SQLiteStore(str(tmp_path / "state.sqlite3"))))


@pytest.fixture(scope="module")
def venue():
    return load_building_v2()


@pytest.fixture(scope="module")
def evaluator(venue):
    return ScenarioEvaluator(venue, DoorPlanRequest(hazards=[FIRE]))


def adapter_for(service, provider):
    return ManagedAgentAdapter(service, api_key="", client=provider, poll_interval=0.001)


def strategist_script(**overrides):
    return {"creates": [response("requires_action", [submit("call_1001")], identifier=SID)],
            "acks": [response("in_progress", identifier=interaction_id(2))], "gets": [], "streams": [], **overrides}


def robustness_script(evaluator, claims=None, **overrides):
    claims = claims if claims is not None else claims_for(
        evaluator, ROBUST, ["baseline", "stuck_closed:D9", "stuck_closed:D2", "exit_blocked:E3", "jam:D4@0.50"])
    steps = [{"type": "thought"},
             {"type": "code_execution_call", "code": "cd /workspace/kit && python3 -m spatialtwin_kit.sweep"},
             {"type": "code_execution_result", "result": '{"single_failures_held": 18, "single_failures_total": 18}'},
             {"type": "function_call", "id": "call_2002", "name": "submit_recommendation"}]
    return {"creates": [FakeStream(stream_events(RID, "requires_action", steps))],
            "gets": [response("requires_action", [submit("call_2002", ROBUST, FALLBACK, claims,
                                                         "D4 + D9 open ties 125 and holds every single failure.")],
                              identifier=RID, tokens=48_000)],
            "acks": [response("in_progress", identifier=interaction_id(102))], "streams": [], **overrides}


def deadlines(strategist=30.0, robustness=30.0):
    return {"strategist": (strategist, deadline_stamp(strategist)[1]),
            "robustness": (robustness, deadline_stamp(robustness)[1])}


async def run_team(service, venue, provider, lanes=("strategist", "robustness"), mode="live", team_id="dinv-team",
                   **deadline_kwargs):
    hub = TraceHub()
    hub.open(team_id)
    runner = DoorAgentRunner(adapter_for(service, provider), trace=hub, retry_base=0.001)
    result = await runner.run_team(venue, DoorPlanRequest(hazards=[FIRE]), team_id, mode, list(lanes),
                                   deadlines(**deadline_kwargs))
    await runner.wait_background()
    return result, runner, hub


async def test_two_live_lanes_run_in_parallel_and_compose(service, venue, evaluator):
    robustness_started = asyncio.Event()

    async def strategist_create():
        await asyncio.wait_for(robustness_started.wait(), 5)  # deadlocks unless the lanes run in parallel
        return response("requires_action", [submit("call_1001")], identifier=SID)

    async def robustness_create():
        robustness_started.set()
        return robustness_script(evaluator)["creates"][0]

    provider = LaneProvider({"strategist": strategist_script(creates=[strategist_create]),
                             "robustness": robustness_script(evaluator, creates=[robustness_create])})
    result, runner, hub = await run_team(service, venue, provider)
    assert result.investigation_id == "dinv-team" and result.team_status == "finished"
    assert result.status.value == "completed" and result.lane == "strategist"   # legacy fields = strategist
    assert result.recommended_door_states == BEST and result.agrees_with_checker
    strategist, robustness = result.lanes["strategist"], result.lanes["robustness"]
    assert strategist["effective"] == robustness["effective"] == "live"
    assert robustness["recommended_door_states"] == ROBUST and robustness["fallback_if_jammed"] == FALLBACK
    assert robustness["verification"] == {"verified": 5, "total": 5, "source": "sandbox", "mismatches": []}
    assert robustness["recommended_ties_checked_best"] is True and robustness["agrees_with_checker"] is False
    assert "Both give 125 modeled crossings" in robustness["agreement_note"]
    assert robustness["stream"]["used"] and robustness["stream"]["steps"] == 4
    assert robustness["sandbox"]["network"] == "disabled" and robustness["sandbox"]["available"]
    assert robustness["token_budget"] == 150_000 and robustness["cost_estimate"]["usd"] > 0
    # The local sweep ran alongside and is the reference the sandbox claims were compared with.
    assert result.robustness["single_failures_held"] == 8 and result.robustness["most_robust_tied_state"] == ROBUST
    assert "D4 open + D9 open ties at baseline and holds 18 of 18" in result.robustness_headline
    # Robustness request: network-disabled sandbox with the kit and inputs; code execution + both functions.
    first = provider.lane_calls("robustness")[0]
    env = first["environment"]
    targets = {s["target"] for s in env["sources"]}
    assert env["type"] == "remote" and env["network"] == "disabled"
    assert {".agents/AGENTS.md", ".agents/hooks.json", ".agents/skills/robustness-sweep/SKILL.md",
            "workspace/kit/spatialtwin_kit/sweep.py", "workspace/inputs/venue.json",
            "workspace/inputs/checked_plan.json", "workspace/inputs/hazards.json"} <= targets
    assert [t.get("name") or t["type"] for t in first["tools"]] == ["code_execution", "verify_candidates",
                                                                    "submit_recommendation"]
    assert first["agent_config"]["max_total_tokens"] == 150_000 and first["stream"] is True
    # Both submissions were acknowledged after publication.
    acks = [k for lane in ("strategist", "robustness") for k in provider.lane_calls(lane)
            if k.get("previous_interaction_id")]
    assert {k["previous_interaction_id"] for k in acks} == {SID, RID}


async def test_each_lane_has_its_own_deadline_and_a_labelled_local_fallback(service, venue, evaluator):
    async def hang():
        await asyncio.sleep(30)
    provider = LaneProvider({"strategist": strategist_script(),
                             "robustness": robustness_script(evaluator, creates=[hang])})
    result, runner, _ = await run_team(service, venue, provider, strategist=10.0, robustness=0.6)
    strategist, robustness = result.lanes["strategist"], result.lanes["robustness"]
    assert strategist["status"] == "completed" and strategist["effective"] == "live"
    assert robustness["status"] == "timed_out" and "investigation_deadline" in robustness["errors"]
    assert robustness["effective"] == "local_fallback"
    fallback = robustness["fallback"]
    assert fallback["provenance"] == "local" and fallback["status"] == "completed"
    assert fallback["label"] == "Local fallback · live robustness lane failed (investigation_deadline)"
    assert fallback["fallback_for"]["status"] == "timed_out"
    assert fallback["recommended_door_states"] == ROBUST and fallback["verification"]["source"] == "local"
    saved = await runner.get_saved_result(lane_id("dinv-team", "robustness"))
    assert saved.deadline_seconds == 0.6
    assert (await runner.get_saved_result(lane_id("dinv-team", "strategist"))).deadline_seconds == 10.0


async def test_rate_limited_lane_retries_then_succeeds(service, venue, evaluator):
    script = robustness_script(evaluator)
    provider = LaneProvider({"strategist": strategist_script(creates=[HttpError(429), HttpError(503),
                                                                      response("requires_action", [submit("call_1001")],
                                                                               identifier=SID)]),
                             "robustness": script})
    result, _, hub = await run_team(service, venue, provider)
    assert result.lanes["strategist"]["status"] == "completed" and result.lanes["strategist"]["provider_retries"] == 2
    retries = [e for e in hub.buffered("dinv-team", 0) if e["event"] == "retry"]
    assert [e["code"] for e in retries] == ["provider_rate_limited", "provider_unavailable"]


async def test_live_failure_stays_visible_and_falls_back(service, venue, evaluator):
    provider = LaneProvider({"strategist": strategist_script(creates=[HttpError(500)] * 4),
                             "robustness": robustness_script(evaluator)})
    result, _, hub = await run_team(service, venue, provider)
    assert result.status.value == "failed" and result.errors == ["provider_unavailable"]  # top level = live strategist
    lane = result.lanes["strategist"]
    assert lane["effective"] == "local_fallback" and lane["fallback"]["recommended_door_states"] == BEST
    assert any(e["event"] == "fallback" and e["lane"] == "strategist" for e in hub.buffered("dinv-team", 0))


async def test_mismatching_sandbox_claims_are_counted(service, venue, evaluator):
    claims = claims_for(evaluator, ROBUST, ["baseline", "stuck_closed:D9", "exit_blocked:E3"], tamper=2)
    claims.append({"scenario": "jam:D9@0.5", "completed_crossings": 125, "candidate_hash": "0000000000000000"})
    provider = LaneProvider({"strategist": strategist_script(),
                             "robustness": robustness_script(evaluator, claims=claims)})
    result, _, _ = await run_team(service, venue, provider)
    verification = result.lanes["robustness"]["verification"]
    assert (verification["verified"], verification["total"]) == (2, 4)
    assert {m["reason"] for m in verification["mismatches"]} == {"crossings_mismatch", "candidate_hash_mismatch"}


async def test_submission_is_published_before_the_acknowledgement(service, venue):
    released = asyncio.Event()
    provider_ref = {}

    async def slow_ack():
        # The lane result is already durable while its acknowledgement is still in flight.
        saved = await provider_ref["runner"].get_saved_result("dinv-ack")
        provider_ref["seen"] = saved.status.value if saved else None
        await released.wait()
        return response("in_progress", identifier=interaction_id(2))

    provider = LaneProvider({"strategist": strategist_script(acks=[slow_ack])})
    runner = DoorAgentRunner(adapter_for(service, provider), retry_base=0.001)
    provider_ref["runner"] = runner
    result = await runner.run(load_building_v2(), DoorPlanRequest(hazards=[FIRE]), "dinv-ack", "live", 10.0)
    assert result.status.value == "completed" and len(provider.lane_calls("strategist")) <= 2
    for _ in range(100):
        if "seen" in provider_ref:
            break
        await asyncio.sleep(0.01)
    assert provider_ref["seen"] == "completed"
    released.set()
    await runner.wait_background()
    phases = [e["phase"] for e in await runner.get_progress("dinv-ack")]
    assert phases[-1] == "ack_sent"


async def test_stream_drop_resumes_from_the_last_event_id(service, venue, evaluator):
    script = robustness_script(evaluator)
    events = script["creates"][0].events
    script["creates"] = [FakeStream(events, drop_after=5)]
    script["streams"] = [FakeStream(events[5:])]
    provider = LaneProvider({"robustness": script})
    result, _, _ = await run_team(service, venue, provider, lanes=("robustness",))
    lane = result.lanes["robustness"]
    assert lane["status"] == "completed" and lane["stream"]["drops"] == 1 and lane["stream"]["resumed"] == 1
    assert not lane["stream"]["fell_back_to_polling"]
    resume = provider.lane_calls("robustness", "get")[0]
    assert resume["stream"] is True and resume["last_event_id"] == events[4]["event_id"] and resume["id"] == RID


async def test_stream_drop_without_resume_falls_back_to_polling(service, venue, evaluator):
    script = robustness_script(evaluator)
    events = script["creates"][0].events
    script["creates"] = [FakeStream(events, drop_after=3)]
    script["streams"] = [HttpError(503), HttpError(503), HttpError(503), HttpError(503)]
    script["gets"] = [response("in_progress", identifier=RID)] + script["gets"]
    provider = LaneProvider({"robustness": script})
    result, _, _ = await run_team(service, venue, provider, lanes=("robustness",))
    lane = result.lanes["robustness"]
    assert lane["status"] == "completed", lane["errors"]
    assert lane["stream"]["drops"] == 1 and lane["stream"]["resumed"] == 0 and lane["stream"]["fell_back_to_polling"]
    assert lane["verification"]["verified"] == lane["verification"]["total"] == 5


async def test_rejected_stream_request_retries_without_a_stream(service, venue):
    provider = LaneProvider({"strategist": strategist_script(creates=[
        HttpError(400), response("requires_action", [submit("call_1001")], identifier=SID)])})
    result, _, _ = await run_team(service, venue, provider, lanes=("strategist",))
    assert result.status.value == "completed"
    first, second = provider.lane_calls("strategist")[:2]
    assert first.get("stream") is True and "stream" not in second
    assert result.lanes["strategist"]["stream"]["rejected"] is True


async def test_local_team_runs_both_lanes_locally(service, venue):
    result, _, _ = await run_team(service, venue, LaneProvider({}), mode="local")
    assert result.provenance == "local" and result.team_status == "finished"
    robustness = result.lanes["robustness"]
    assert robustness["effective"] == "local" and robustness["recommended_door_states"] == ROBUST
    assert robustness["explanation"].startswith("Local solver · no Gemini call. D9 open holds 8 of 16")
    assert robustness["verification"]["source"] == "local"
    assert result.robustness["provenance"] == "local_checker"


# --- routes: team, supersede, follow-up -----------------------------------------------------------------------------

def client_for(service, provider, slots=None):
    adapter = adapter_for(service, provider)
    runner = DoorAgentRunner(adapter, retry_base=0.001)
    app = FastAPI()
    app.include_router(build_door_agent_router(adapter, slots or asyncio.Semaphore(2), lambda: True, runner=runner,
                                               ping_seconds=0.05))
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test"), runner


async def poll(client, investigation_id, key="team_status", until=("running",)):
    for _ in range(1000):
        body = (await client.get(f"/api/venues/building-v2/investigations/{investigation_id}")).json()
        if body[key] not in until:
            return body
        await asyncio.sleep(0.01)
    raise AssertionError("did not finish")


async def test_route_team_progress_then_followup_reuses_the_environment(service, evaluator):
    rob = robustness_script(evaluator)
    follow_id = interaction_id(201)
    rob["gets"].append(response("completed", identifier=interaction_id(102)))          # the ack settled
    rob["creates"].append(response("requires_action", [submit("call_3003", ROBUST, FALLBACK, claims_for(
        evaluator, ROBUST, ["stuck_closed:D3"]))], identifier=follow_id))
    rob["acks"].append(response("in_progress", identifier=interaction_id(202)))
    provider = LaneProvider({"strategist": strategist_script(), "robustness": rob})
    client, runner = client_for(service, provider)
    started = (await client.post("/api/venues/building-v2/investigate", json={
        "hazards": [FIRE], "mode": "live", "lanes": ["robustness", "strategist"]})).json()
    assert set(started["lanes"]) == {"strategist", "robustness"}
    assert started["lanes"]["robustness"]["deadline_seconds"] == 150.0
    assert started["deadline_at_ms"] == started["lanes"]["robustness"]["deadline_at_ms"]
    body = await poll(client, started["investigation_id"])
    assert body["team_status"] == "finished" and body["status"] == "completed"
    assert body["investigation"]["lanes"]["robustness"]["verification"]["verified"] == 5
    await runner.wait_background()
    follow = await client.post(f"/api/venues/building-v2/investigations/{started['investigation_id']}/followup",
                               json={"scenario": "stuck_closed:D3", "mode": "live"})
    assert follow.status_code == 200, follow.text
    follow = follow.json()
    assert follow["parent_investigation_id"] == started["investigation_id"] and follow["scenario"] == "stuck_closed:D3"
    body = await poll(client, follow["investigation_id"])
    lane = body["investigation"]["lanes"]["followup"]
    assert lane["status"] == "completed", lane["errors"]
    assert lane["effective"] == "live" and lane["scenario"] == "stuck_closed:D3"
    assert body["parent_investigation_id"] == started["investigation_id"]
    create = provider.lane_calls("robustness")[-1] if not provider.lane_calls("robustness")[-1].get(
        "input", [{}])[0].get("type") == "function_result" else provider.lane_calls("robustness")[-2]
    assert create["environment"] == ENV_ID and create["previous_interaction_id"] == interaction_id(102)
    assert "system_instruction" not in create and "stuck_closed:D3" in create["input"]
    assert [t.get("name") or t["type"] for t in create["tools"]][0] == "code_execution"
    bad = await client.post(f"/api/venues/building-v2/investigations/{started['investigation_id']}/followup",
                            json={"scenario": "jam:D9@2"})
    assert bad.status_code == 422 and bad.json() == {"detail": {"code": "scenario_unrecognized"}}


async def test_route_live_followup_without_a_live_parent_falls_back_locally(service):
    client, _ = client_for(service, LaneProvider({}))
    parent = (await client.post("/api/venues/building-v2/investigate", json={
        "hazards": [FIRE], "mode": "local", "lanes": ["strategist", "robustness"]})).json()
    await poll(client, parent["investigation_id"])
    follow = (await client.post(f"/api/venues/building-v2/investigations/{parent['investigation_id']}/followup",
                                json={"scenario": "stuck_closed:D9", "mode": "live"})).json()
    body = await poll(client, follow["investigation_id"])
    lane = body["investigation"]["lanes"]["followup"]
    assert lane["status"] == "failed" and lane["errors"] == ["followup_parent_unavailable"]
    assert lane["effective"] == "local_fallback"
    assert lane["fallback"]["recommended_door_states"] == {"D4": "open", "D9": "closed"}  # best with D9 stuck shut
    assert "Under stuck_closed:D9" in lane["fallback"]["explanation"]


async def test_route_new_team_supersedes_the_running_one(service, evaluator):
    async def hang():
        await asyncio.sleep(30)
    provider = LaneProvider({"strategist": strategist_script(creates=[hang, response(
        "requires_action", [submit("call_1001")], identifier=SID)], acks=[]),
        "robustness": robustness_script(evaluator, creates=[hang, robustness_script(evaluator)["creates"][0]])})
    client, _ = client_for(service, provider)
    body = {"hazards": [FIRE], "mode": "live", "lanes": ["strategist", "robustness"]}
    first = (await client.post("/api/venues/building-v2/investigate", json=body)).json()
    for _ in range(200):
        if len(provider.calls) >= 2:
            break
        await asyncio.sleep(0.01)
    refused = await client.post("/api/venues/building-v2/investigate", json={**body, "supersede": False})
    assert refused.status_code == 429
    second = await client.post("/api/venues/building-v2/investigate", json=body)
    assert second.status_code == 200
    old = await poll(client, first["investigation_id"])
    assert old["team_status"] == "cancelled" and old["status"] == "cancelled"
    new = await poll(client, second.json()["investigation_id"])
    assert new["status"] == "completed"
