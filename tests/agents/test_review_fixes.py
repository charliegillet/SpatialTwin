"""Devil's-advocate review fixes: honest sandbox provenance (M3), cancellable sweeps (M4), follow-up sandbox safety
(M5), acknowledgement tokens, and invalid-state claims. Offline, fake provider."""
import asyncio
import json
import threading

import pytest

from backend.app.ai.managed import door_agent
from backend.app.ai.managed.door_agent import DoorAgentRunner, lane_id
from backend.app.ai.managed.robustness import (
    ScenarioEvaluator, SweepCancelled, robustness_sweep, verify_claims,
)
from backend.app.venues import agent as agent_routes
from backend.app.venues.schemas import DoorPlanRequest
from tests.agents.fakes import (
    ROBUST, FIRE, FakeStream, LaneProvider, claims_for, interaction_id, response, stream_events, submit,
)
from tests.agents.test_lanes import (  # noqa: F401  (fixtures are used by name)
    FALLBACK, RID, adapter_for, client_for, deadlines, evaluator, parent_with_ack, poll, robustness_script, run_team,
    service, strategist_script, venue,
)

SCENARIOS = ["baseline", "stuck_closed:D9", "stuck_closed:D2", "exit_blocked:E3", "jam:D4@0.50"]


def script_with_steps(evaluator, steps, claims=None):
    claims = claims if claims is not None else claims_for(evaluator, ROBUST, SCENARIOS)
    script = robustness_script(evaluator, claims=claims)
    script["creates"] = [FakeStream(stream_events(RID, "requires_action", steps))]
    return script, claims


def verification_of(result):
    return result.lanes["robustness"]["verification"]


# --- M3: sandbox provenance ------------------------------------------------------------------------------------------

async def test_robustness_lane_that_never_ran_code_is_labelled_agent(service, venue, evaluator):
    script, _ = script_with_steps(evaluator, [{"type": "thought"},
                                              {"type": "function_call", "id": "call_2002",
                                               "name": "submit_recommendation"}])
    provider = LaneProvider({"strategist": strategist_script(), "robustness": script})
    result, _, hub = await run_team(service, venue, provider)
    verification = verification_of(result)
    assert (verification["verified"], verification["total"]) == (5, 5)
    assert verification["source"] == "agent" and verification["sandbox_matched"] == 0
    assert {check["provenance"] for check in verification["checks"]} == {"agent"}
    verdicts = [e for e in hub.buffered("dinv-team", 0) if e["event"] == "verification" and e["lane"] == "robustness"]
    assert verdicts and verdicts[0]["source"] == "agent"


async def test_robustness_lane_that_ran_code_is_labelled_sandbox_per_claim(service, venue, evaluator):
    claims = claims_for(evaluator, ROBUST, SCENARIOS)
    shown = claims[:2]  # the sandbox printed only the first two scenarios
    output = json.dumps({c["scenario"]: c["completed_crossings"] for c in shown})
    steps = [{"type": "thought"}, {"type": "code_execution_call", "code": "python3 -m spatialtwin_kit.sweep"},
             {"type": "code_execution_result", "result": output},
             {"type": "function_call", "id": "call_2002", "name": "submit_recommendation"}]
    script, _ = script_with_steps(evaluator, steps, claims)
    provider = LaneProvider({"strategist": strategist_script(), "robustness": script})
    result, _, _ = await run_team(service, venue, provider)
    verification = verification_of(result)
    assert verification["source"] == "sandbox"
    printed = {c["completed_crossings"] for c in shown}
    expected = ["sandbox" if c["completed_crossings"] in printed else "agent" for c in claims]
    assert [check["provenance"] for check in verification["checks"]] == expected
    assert verification["sandbox_matched"] == expected.count("sandbox") >= 2
    # The strategist never has a sandbox.
    assert result.lanes["strategist"]["verification"]["source"] == "agent"


async def test_code_output_seen_only_in_the_polled_interaction_counts(service, venue, evaluator):
    """Non-streamed turns: the final get carries the code_execution_result step."""
    claims = claims_for(evaluator, ROBUST, ["baseline"])
    output = f"baseline {claims[0]['completed_crossings']}"
    polled = response("requires_action", [{"type": "code_execution_result", "result": output, "is_error": False},
                                          submit("call_2002", ROBUST, FALLBACK, claims, "r")],
                      identifier=RID, tokens=48_000)
    script = robustness_script(evaluator, claims=claims, creates=[response("in_progress", identifier=RID)],
                               gets=[polled])
    provider = LaneProvider({"strategist": strategist_script(), "robustness": script})
    runner = DoorAgentRunner(adapter_for(service, provider), stream=False, retry_base=0.001)
    result = await runner.run(venue, DoorPlanRequest(hazards=[FIRE]), "dinv-poll", "live", 20.0, lane="robustness")
    assert result.status.value == "completed", result.errors
    assert result.verification.source == "sandbox" and result.verification.checks[0]["provenance"] == "sandbox"


# --- M4: cancellable sweep -------------------------------------------------------------------------------------------

def test_cancelled_sweep_stops_between_scenarios(venue):
    request = DoorPlanRequest(hazards=[FIRE])
    full = robustness_sweep(venue, request)
    assert full["truncated"] is False and full["cancelled"] is False
    evaluator = ScenarioEvaluator(venue, request)
    cancel = threading.Event()
    real = evaluator.evaluate
    calls = []

    def evaluate(*args, **kwargs):
        calls.append(1)
        if len(calls) == 3:
            cancel.set()
        return real(*args, **kwargs)

    evaluator.evaluate = evaluate
    partial = robustness_sweep(venue, request, evaluator=evaluator, cancel=cancel)
    assert partial["cancelled"] and partial["truncated"]
    assert len(calls) <= 4 and partial["solves"] < full["solves"]
    assert len(partial["single_failures"]) < full["single_failures_total"]
    with pytest.raises(SweepCancelled):
        robustness_sweep(venue, request, cancel=cancel)  # already cancelled: nothing is computed


async def test_a_lane_that_ends_cancels_its_sweep_thread(service, venue, evaluator, monkeypatch):
    seen = {}
    real = door_agent.robustness_sweep

    def spy(*args, **kwargs):
        seen["cancel"] = kwargs["cancel"]
        return real(*args, **kwargs)

    monkeypatch.setattr(door_agent, "robustness_sweep", spy)

    async def hang():
        await asyncio.sleep(30)
    provider = LaneProvider({"robustness": robustness_script(evaluator, creates=[hang])})
    runner = DoorAgentRunner(adapter_for(service, provider), retry_base=0.001)
    result = await runner.run(venue, DoorPlanRequest(hazards=[FIRE]), "dinv-late-sweep", "live", 0.8,
                              lane="robustness")
    assert result.status.value == "timed_out"
    assert seen["cancel"].is_set()


async def test_a_cancelled_run_cancels_its_sweep_thread(service, venue, evaluator, monkeypatch):
    seen = {}
    real = door_agent.robustness_sweep

    def spy(*args, **kwargs):
        seen["cancel"] = kwargs["cancel"]
        return real(*args, **kwargs)

    monkeypatch.setattr(door_agent, "robustness_sweep", spy)

    async def hang():
        await asyncio.sleep(30)
    provider = LaneProvider({"robustness": robustness_script(evaluator, creates=[hang])})
    runner = DoorAgentRunner(adapter_for(service, provider), retry_base=0.001)
    task = asyncio.ensure_future(runner.run(venue, DoorPlanRequest(hazards=[FIRE]), "dinv-cancel-sweep", "live",
                                            20.0, lane="robustness"))
    for _ in range(300):
        if provider.calls:
            break
        await asyncio.sleep(0.01)
    task.cancel()
    result = await task
    assert result.status.value == "cancelled" and seen["cancel"].is_set()


# --- LOW: acknowledgement tokens and invalid-state claims ------------------------------------------------------------

async def test_acknowledgement_tokens_are_added_to_usage_and_cost(service, venue):
    provider = LaneProvider({"strategist": strategist_script(
        acks=[response("in_progress", identifier=interaction_id(2), tokens=777)])})
    runner = DoorAgentRunner(adapter_for(service, provider), retry_base=0.001)
    first = await runner.run(venue, DoorPlanRequest(hazards=[FIRE]), "dinv-ack-usage", "live", 10.0)
    await runner.wait_background()
    assert first.token_usage["total_tokens"] == 5333  # the published result is final
    saved = await runner.get_saved_result("dinv-ack-usage")
    assert saved.token_usage["total_tokens"] == 5333 + 777 and saved.ack_token_usage["total_tokens"] == 777
    assert saved.cost_estimate["usd"] > first.cost_estimate["usd"]


async def test_team_result_lane_views_include_acknowledgement_tokens(service, venue, evaluator):
    provider = LaneProvider({
        "strategist": strategist_script(acks=[response("in_progress", identifier=interaction_id(2), tokens=500)]),
        "robustness": robustness_script(evaluator, acks=[response("in_progress", identifier=interaction_id(102),
                                                                  tokens=900)])})
    _, runner, _ = await run_team(service, venue, provider)
    outcomes = {lane: (await runner.get_saved_result(lane_id("dinv-team", lane)), None)
                for lane in ("strategist", "robustness")}
    team = door_agent.compose_team("dinv-team", ["strategist", "robustness"], outcomes, "finished")
    assert team.lanes["strategist"]["ack_token_usage"]["total_tokens"] == 500
    assert team.lanes["robustness"]["token_usage"]["total_tokens"] == 48_000 + 900
    assert team.token_usage["total_tokens"] == 5333 + 500  # the legacy top level follows the first lane


def test_claim_about_an_invalid_state_is_not_reproduced():
    class Stub:
        def evaluate(self, states, scenario):
            return {"scenario": "baseline", "completed_crossings": 100, "candidate_hash": "abc", "is_valid": False}

    out = verify_claims(Stub(), {"D4": "open"}, None, [{"scenario": "baseline", "completed_crossings": 100,
                                                       "candidate_hash": "abc"}])
    assert out["verified"] == 0 and out["total"] == 1
    assert out["checks"][0]["reason"] == "local_plan_invalid" and out["checks"][0]["local_is_valid"] is False


# --- M5: follow-up safety --------------------------------------------------------------------------------------------

async def test_followup_is_409_when_the_venue_geometry_changed(service, monkeypatch):
    client, _ = client_for(service, LaneProvider({}))
    parent = (await client.post("/api/venues/building-v2/investigate", json={
        "hazards": [FIRE], "mode": "local", "lanes": ["strategist", "robustness"]})).json()
    await poll(client, parent["investigation_id"])
    real = agent_routes.get_venue
    monkeypatch.setattr(agent_routes, "get_venue", lambda venue_id: (lambda v: v.model_copy(
        update={"geometry_revision": "changed-revision"}) if v is not None else None)(real(venue_id)))
    follow = await client.post(f"/api/venues/building-v2/investigations/{parent['investigation_id']}/followup",
                               json={"scenario": "stuck_closed:D9", "mode": "local"})
    assert follow.status_code == 409 and follow.json() == {"detail": {"code": "parent_geometry_changed"}}
    monkeypatch.setattr(agent_routes, "get_venue", real)
    again = await client.post(f"/api/venues/building-v2/investigations/{parent['investigation_id']}/followup",
                              json={"scenario": "stuck_closed:D9", "mode": "local"})
    assert again.status_code == 200


async def test_a_second_live_followup_in_the_same_sandbox_is_refused(service, evaluator):
    release = asyncio.Event()

    async def slow_followup():
        await release.wait()
        return response("requires_action", [submit("call_3003", ROBUST, FALLBACK, claims_for(
            evaluator, ROBUST, ["stuck_closed:D3"]))], identifier=interaction_id(201))
    provider = parent_with_ack(evaluator, lambda: _ack())
    provider.scripts["robustness"]["creates"] = provider.scripts["robustness"]["creates"][:1] + [slow_followup]
    client, runner = client_for(service, provider)
    parent = (await client.post("/api/venues/building-v2/investigate", json={
        "hazards": [FIRE], "mode": "live", "lanes": ["strategist", "robustness"]})).json()
    await poll(client, parent["investigation_id"])
    await runner.wait_background()
    url = f"/api/venues/building-v2/investigations/{parent['investigation_id']}/followup"
    first = await client.post(url, json={"scenario": "stuck_closed:D3", "mode": "live"})
    assert first.status_code == 200, first.text
    second = await client.post(url, json={"scenario": "stuck_closed:D2", "mode": "live"})
    assert second.status_code == 409 and second.json()["detail"]["code"] == "followup_in_progress"
    release.set()
    body = await poll(client, first.json()["investigation_id"])
    assert body["investigation"]["lanes"]["followup"]["status"] == "completed"


async def _ack():
    return response("in_progress", identifier=interaction_id(102))
