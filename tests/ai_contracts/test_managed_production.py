"""Offline SDK and orchestration tests. Never use an actual provider or device."""
import asyncio
import json
import socket
import threading
import time
from types import SimpleNamespace as NS
from unittest.mock import Mock

import httpx
import pytest
from google import genai
from backend.app.ai.managed.adapter import ManagedAgentAdapter, MODEL, TOKEN_BUDGET
from backend.app.contracts import AlternativeId, InvestigationStatus, RunContext
from backend.app.state.manager import StateManager
from backend.app.state.service import ScenarioService
from backend.app.state.store import SQLiteStore


@pytest.fixture(autouse=True)
def network_disabled(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Unexpected network in offline managed tests")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)


@pytest.fixture
def service(tmp_path):
    return ScenarioService(StateManager(SQLiteStore(str(tmp_path / "state.sqlite3"))))


def function(call_id="comparison", name="get_checked_comparison", arguments=None):
    return {"type": "function_call", "id": call_id, "name": name, "arguments": arguments or {}}


def response(status="completed", steps=None, identifier="i-1", tokens=10, model=MODEL):
    return NS(id=identifier, environment_id="env-1", model=model, status=status,
              steps=steps or [], usage=NS(total_tokens=tokens), output_text="Untrusted prose: open every exit.")


class Provider:
    def __init__(self, creates, gets=()):
        self.creates = list(creates)
        self.gets = list(gets)
        self.create_calls = []
        self.get_calls = []
        self.cancel_calls = []
        self.aio = NS(interactions=self)

    async def create(self, **kwargs):
        self.create_calls.append(kwargs)
        value = self.creates.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    async def get(self, **kwargs):
        self.get_calls.append(kwargs)
        value = self.gets.pop(0)
        if callable(value):
            return await value()
        return value

    async def cancel(self, **kwargs):
        self.cancel_calls.append(kwargs)
        return response("cancelled")


def make_adapter(service, provider=None):
    return ManagedAgentAdapter(service, api_key="", client=provider, poll_interval=0.001)


@pytest.mark.asyncio
async def test_missing_credentials_fail_without_implicit_fallback(service):
    result = await make_adapter(service).investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.FAILED
    assert result.provenance == "unavailable"
    assert result.recommended_alternative is None
    assert result.token_usage == {}
    assert result.tool_ledger == []
    assert result.errors == ["provider_unavailable"]


@pytest.mark.asyncio
async def test_explicit_local_mode_has_no_provider_claim_or_usage(service):
    provider = Provider([])
    result = await make_adapter(service, provider).investigate_scenario(service.state_manager.context, mode="local")
    assert result.status == InvestigationStatus.COMPLETED
    assert result.provenance == "local"
    assert result.provider_interaction_id is None
    assert result.provider_model is None
    assert result.token_usage == {}
    assert result.recommended_alternative == AlternativeId.KEEP_CURRENT
    assert len(result.tool_ledger) == 3
    assert not provider.create_calls
    assert "Antigravity" not in result.agent_explanation


@pytest.mark.asyncio
async def test_real_async_sdk_serializes_and_reads_typed_usage(service, monkeypatch):
    requests = []
    async def fake_send(self, request, *args, **kwargs):
        body = json.loads(request.content)
        requests.append(body)
        initial = "previous_interaction_id" not in body
        payload = {"id": "sdk-initial" if initial else "sdk-final", "environment_id": "env-1",
                   "model": MODEL, "status": "requires_action" if initial else "completed",
                   "usage": {"total_tokens": 20 if initial else 7},
                   "steps": [function()] if initial else []}
        return httpx.Response(200, json=payload, request=request)
    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)
    client = genai.Client(api_key="offline-placeholder")
    adapter = make_adapter(service, client)
    result = await adapter.investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.COMPLETED, result.errors
    assert result.token_usage == {"total_tokens": 27}
    assert result.provenance == "live"
    assert result.provider_model == MODEL
    assert result.provider_interaction_id == "sdk-final"
    assert result.provider_environment_id == "env-1"
    assert requests[0]["agent_config"]["max_total_tokens"] == "20000"
    assert requests[1]["agent_config"]["max_total_tokens"] == "19980"
    assert requests[1]["previous_interaction_id"] == "sdk-initial"
    assert json.loads(requests[1]["input"][0]["result"])["keep_current"]["validator_report"]["is_valid"]
    assert "timeline" not in json.loads(requests[1]["input"][0]["result"])["keep_current"]
    assert result.candidate_envelopes[0].timeline
    progress = await adapter.get_progress(result.investigation_id)
    assert [entry["phase"] for entry in progress].count("provider_request") == 2
    assert any(entry["phase"] == "local_tool_complete" for entry in progress)
    assert all("output_text" not in entry and "arguments" not in entry for entry in progress)
    assert result.provider_progress == progress
    assert result.last_provider_status == "completed"
    await adapter.aclose()


@pytest.mark.asyncio
async def test_poll_usage_counted_once_and_lifecycle_ids_preserved(service):
    provider = Provider([response("in_progress", tokens=2), response(identifier="i-2", tokens=4)],
                        [response("in_progress", tokens=3), response("requires_action", [function()], tokens=5)])
    result = await make_adapter(service, provider).investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.COMPLETED
    assert result.token_usage["total_tokens"] == 9
    assert len(provider.get_calls) == 2
    assert provider.create_calls[1]["agent_config"]["max_total_tokens"] == TOKEN_BUDGET - 5


@pytest.mark.asyncio
async def test_duplicate_calls_reuse_durable_result_and_completed_run_replays(service):
    count = Mock(wraps=service.get_checked_comparison)
    service.get_checked_comparison = count
    provider = Provider([response("requires_action", [function()]),
                         response("requires_action", [function()], "i-2"), response(identifier="i-3")])
    adapter = make_adapter(service, provider)
    context = service.state_manager.context
    result = await adapter.investigate_scenario(context, "durable-replay")
    assert result.status == InvestigationStatus.COMPLETED
    assert count.call_count == 1
    assert len(result.tool_ledger) == 1
    adapter.ledger.close()
    second_provider = Provider([])
    replay = await make_adapter(service, second_provider).investigate_scenario(context, "durable-replay")
    assert replay.replayed is True
    assert result.replayed is False
    assert replay.model_copy(update={"replayed": False}).model_dump() == result.model_dump()
    assert second_provider.create_calls == []


@pytest.mark.asyncio
async def test_pending_claim_after_restart_fails_closed(service):
    adapter = make_adapter(service)
    context = service.state_manager.context
    adapter.ledger.begin("interrupted", context.model_dump(mode="json"), "live")
    adapter.ledger.claim("interrupted", "call-1", "get_checked_comparison", {}, 4)
    adapter.ledger.close()
    provider = Provider([])
    result = await make_adapter(service, provider).investigate_scenario(context, "interrupted")
    assert result.status == InvestigationStatus.FAILED
    assert result.errors == ["tool_execution_uncertain"]
    assert not provider.create_calls


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_status,expected", [("failed", "failed"), ("cancelled", "cancelled"),
                                                    ("incomplete", "incomplete"), ("budget_exceeded", "incomplete")])
async def test_terminal_lifecycle_never_recommends(service, provider_status, expected):
    provider = Provider([response(provider_status)])
    result = await make_adapter(service, provider).investigate_scenario(service.state_manager.context)
    assert result.status.value == expected
    assert result.recommended_alternative is None
    assert result.errors == [f"provider_{provider_status}"]
    assert not provider.cancel_calls


@pytest.mark.asyncio
@pytest.mark.parametrize("name,args", [("evaluate_allowed_alternative", {}),
    ("evaluate_allowed_alternative", {"alternative_id": "OPEN_P3", "serial": "unsafe"}),
    ("evaluate_allowed_alternative", {"alternative_id": "OPEN_P99"}),
    ("get_reviewed_scenario", {"extra": 1}), ("set_gate_target", {})])
async def test_missing_extra_unknown_arguments_rejected_before_tool_execution(service, name, args):
    provider = Provider([response("requires_action", [function(name=name, arguments=args)])])
    result = await make_adapter(service, provider).investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.FAILED
    assert result.recommended_alternative is None
    assert result.tool_ledger == []
    assert len(provider.create_calls) == 1


@pytest.mark.asyncio
async def test_four_accepted_calls_maximum_not_four_turns(service):
    provider = Provider([response("requires_action", [function(str(i), "get_reviewed_scenario") for i in range(6)])])
    result = await make_adapter(service, provider).investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.FAILED
    assert "tool_call_limit" in result.errors
    assert len(result.tool_ledger) == 4
    assert len(provider.create_calls) == 1


@pytest.mark.asyncio
async def test_cumulative_budget_never_gets_a_fresh_full_allowance(service):
    provider = Provider([response("requires_action", [function()], tokens=19_999),
                         response("requires_action", [function()], "i-2", tokens=1)])
    result = await make_adapter(service, provider).investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.FAILED
    assert "token_budget_exhausted" in result.errors
    assert result.token_usage["total_tokens"] == 20_000
    assert len(provider.create_calls) == 2
    assert provider.create_calls[1]["agent_config"]["max_total_tokens"] == 1


@pytest.mark.asyncio
async def test_deadline_cancels_remote_without_blocking_event_loop(service):
    async def slow():
        await asyncio.sleep(10)
    provider = Provider([response("in_progress")], [slow])
    adapter = make_adapter(service, provider)
    ticks = 0
    async def ticker():
        nonlocal ticks
        for _ in range(10):
            await asyncio.sleep(.003)
            ticks += 1
    start = time.monotonic()
    result, _ = await asyncio.gather(adapter.investigate_scenario(service.state_manager.context, deadline_seconds=.08), ticker())
    assert time.monotonic() - start < .2
    assert result.status == InvestigationStatus.TIMED_OUT, result.errors
    assert result.recommended_alternative is None
    assert provider.cancel_calls
    assert ticks == 10


@pytest.mark.asyncio
async def test_caller_cancellation_is_persisted_and_cancels_provider(service):
    started = asyncio.Event()
    async def slow():
        started.set()
        await asyncio.sleep(10)
    provider = Provider([response("in_progress")], [slow])
    adapter = make_adapter(service, provider)
    task = asyncio.create_task(adapter.investigate_scenario(service.state_manager.context, "cancelled-run"))
    await started.wait()
    task.cancel()
    result = await task
    assert result.status == InvestigationStatus.CANCELLED
    assert result.recommended_alternative is None
    assert provider.cancel_calls
    assert json.loads(adapter.ledger.begin("cancelled-run", service.state_manager.context.model_dump(mode="json"), "live")[1]["result_json"])["status"] == "cancelled"


@pytest.mark.asyncio
async def test_stale_context_and_wrong_model_have_no_recommendation(service):
    context = service.state_manager.context
    stale = RunContext(geometry_revision=context.geometry_revision, scenario_revision=context.scenario_revision,
                       physical_revision=context.physical_revision, parameters_revision="wrong-parameters")
    provider = Provider([])
    result = await make_adapter(service, provider).investigate_scenario(stale)
    assert result.errors == ["stale_context"]
    assert not provider.create_calls
    result = await make_adapter(service, Provider([response(model="unexpected-model")])).investigate_scenario(context)
    assert result.status == InvestigationStatus.FAILED
    assert result.recommended_alternative is None
    assert "provider_model_mismatch" in result.errors


@pytest.mark.asyncio
async def test_provider_exception_is_sanitized_and_never_local_fallback(service, caplog):
    secret = "credential-do-not-echo"
    provider = Provider([RuntimeError(secret)])
    result = await make_adapter(service, provider).investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.FAILED
    assert result.provenance == "unavailable"
    assert result.token_usage == {}
    assert result.tool_ledger == []
    assert secret not in result.model_dump_json() + caplog.text


@pytest.mark.asyncio
async def test_late_read_only_worker_cannot_publish_after_deadline(service):
    original = service.get_checked_comparison
    def slow(*args):
        time.sleep(.08)
        return original(*args)
    service.get_checked_comparison = slow
    provider = Provider([response("requires_action", [function()])])
    adapter = make_adapter(service, provider)
    result = await adapter.investigate_scenario(service.state_manager.context, "late-worker", deadline_seconds=.04)
    assert result.status == InvestigationStatus.TIMED_OUT, result.errors
    assert result.recommended_alternative is None
    assert result.tool_ledger[0].status == "requested"
    await asyncio.sleep(.1)
    assert adapter.ledger.calls("late-worker")[0]["status"] == "executed"
    stored = adapter.ledger.begin("late-worker", service.state_manager.context.model_dump(mode="json"), "live")[1]
    assert json.loads(stored["result_json"])["status"] == "timed_out"
    assert json.loads(stored["result_json"])["recommended_alternative"] is None


@pytest.mark.asyncio
async def test_fulfilled_provider_history_is_not_reexecuted(service):
    steps = [function("already-done", "set_gate_target"),
             {"type": "function_result", "call_id": "already-done", "result": "ignored remote result"},
             function()]
    provider = Provider([response("requires_action", steps), response(identifier="i-2")])
    result = await make_adapter(service, provider).investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.COMPLETED
    assert [entry.call_id for entry in result.tool_ledger] == ["comparison"]


@pytest.mark.asyncio
async def test_complete_without_both_checked_candidates_is_incomplete(service):
    result = await make_adapter(service, Provider([response()])).investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.INCOMPLETE
    assert result.recommended_alternative is None
    assert result.errors == ["comparison_evidence_incomplete"]


@pytest.mark.asyncio
async def test_inconsistent_conditions_cannot_recommend(service):
    original = service.get_checked_comparison
    def changed(*args):
        value = original(*args)
        value["open_p3"]["horizon_seconds"] += 1
        return value
    service.get_checked_comparison = changed
    provider = Provider([response("requires_action", [function()]), response(identifier="i-2")])
    result = await make_adapter(service, provider).investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.FAILED
    assert result.recommended_alternative is None
    assert "comparison_conditions_mismatch" in result.errors


@pytest.mark.asyncio
async def test_stale_context_after_tool_is_rejected(service):
    original = service.get_checked_comparison
    def changed(*args):
        value = original(*args)
        current = service.state_manager.context
        service.state_manager.context = RunContext(geometry_revision=current.geometry_revision,
            scenario_revision=current.scenario_revision + 1, physical_revision=current.physical_revision)
        return value
    service.get_checked_comparison = changed
    provider = Provider([response("requires_action", [function()])])
    result = await make_adapter(service, provider).investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.FAILED
    assert result.recommended_alternative is None
    assert "stale_context" in result.errors
    assert len(provider.create_calls) == 1


@pytest.mark.asyncio
async def test_usage_absent_cannot_start_unmetered_continuation(service):
    initial = response("requires_action", [function()])
    initial.usage = None
    provider = Provider([initial])
    result = await make_adapter(service, provider).investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.FAILED
    assert result.errors == ["usage_unavailable_for_continuation"]
    assert len(provider.create_calls) == 1


@pytest.mark.asyncio
async def test_same_call_id_cannot_change_arguments(service):
    provider = Provider([response("requires_action", [function("bound", "get_reviewed_scenario")]),
                         response("requires_action", [function("bound")], "i-2")])
    result = await make_adapter(service, provider).investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.FAILED
    assert "tool_call_identity_conflict" in result.errors
    assert len(result.tool_ledger) == 1


@pytest.mark.asyncio
async def test_repeated_completed_call_cannot_drive_unlimited_continuations(service):
    provider = Provider([response("requires_action", [function()], f"i-{i}", tokens=0) for i in range(6)])
    result = await make_adapter(service, provider).investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.FAILED
    assert "continuation_limit" in result.errors
    assert len(provider.create_calls) == 5
    assert len(result.tool_ledger) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("http_status,error_code", [(400, "provider_request_rejected"),
    (401, "provider_access_denied"), (403, "provider_access_denied"),
    (429, "provider_rate_limited"), (503, "provider_unavailable")])
async def test_actual_sdk_does_not_retry_provider_errors(service, monkeypatch, http_status, error_code):
    requests = []
    async def fake_send(self, request, *args, **kwargs):
        requests.append(request)
        return httpx.Response(http_status, json={"error": {"code": http_status, "message": "sanitized fake"}}, request=request)
    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)
    adapter = ManagedAgentAdapter(service, api_key="offline-placeholder")
    result = await adapter.investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.FAILED
    assert result.recommended_alternative is None
    assert result.errors == [error_code]
    assert len(requests) == 1
    await adapter.aclose()


@pytest.mark.asyncio
async def test_actual_sdk_timeout_wrapper_is_classified_and_sanitized(service, monkeypatch, caplog):
    requests = []
    async def fake_send(self, request, *args, **kwargs):
        requests.append(request)
        raise httpx.ReadTimeout("private-token-do-not-echo", request=request)
    monkeypatch.setattr(httpx.AsyncClient, "send", fake_send)
    adapter = ManagedAgentAdapter(service, api_key="offline-placeholder")
    result = await adapter.investigate_scenario(service.state_manager.context)
    assert result.status == InvestigationStatus.FAILED
    assert result.errors == ["provider_timeout"]
    assert len(requests) == 1
    assert "private-token-do-not-echo" not in result.model_dump_json() + caplog.text
    await adapter.aclose()


@pytest.mark.asyncio
async def test_progress_has_only_bounded_sanitized_receipts(service):
    adapter = make_adapter(service)
    # The bound rose from 64 to 256 for two-lane runs with retries and streaming; trace rows are kept apart.
    for index in range(300):
        adapter.ledger.event("bounded", float(index), "provider_response",
                             {"method": "get", "interaction_id": "opaque", "status": "in_progress"})
    adapter.ledger.event("bounded", 999.0, "trace", {"seq": 1, "event": "step"})
    events = await adapter.get_progress("bounded")
    assert len(events) == 256
    assert events[0]["elapsed_ms"] == 44.0
    assert events[-1]["elapsed_ms"] == 299.0
    assert [row["seq"] for row in adapter.ledger.trace_events("bounded")] == [1]


@pytest.mark.asyncio
async def test_checked_numbers_survive_provider_final_timeout_without_recommendation(service):
    async def slow():
        await asyncio.sleep(10)
    provider = Provider([response("requires_action", [function()]), response("in_progress", identifier="i-2")], [slow])
    result = await make_adapter(service, provider).investigate_scenario(service.state_manager.context, deadline_seconds=.08)
    assert result.status == InvestigationStatus.TIMED_OUT
    assert len(result.candidate_envelopes) == 2
    assert all(candidate.is_publishable for candidate in result.candidate_envelopes)
    assert result.recommended_alternative is None


@pytest.mark.asyncio
async def test_only_finished_owner_result_is_available_for_public_index(service):
    adapter = make_adapter(service)
    context = service.state_manager.context
    adapter.ledger.begin("unfinished", context.model_dump(mode="json"), "local")
    assert await adapter.get_saved_result("missing") is None
    assert await adapter.get_saved_result("unfinished") is None
    result = await adapter.investigate_scenario(context, "finished", mode="local")
    assert (await adapter.get_saved_result("finished")).model_dump() == result.model_dump()


@pytest.mark.asyncio
async def test_concurrent_nonowner_failure_never_becomes_saved_owner_result(service):
    started = asyncio.Event()
    release = asyncio.Event()
    provider = Provider([response("requires_action", [function()]), response(identifier="i-2")])
    original_create = provider.create
    async def delayed(**kwargs):
        if not provider.create_calls:
            started.set()
            await release.wait()
        return await original_create(**kwargs)
    provider.create = delayed
    adapter = make_adapter(service, provider)
    context = service.state_manager.context
    owner = asyncio.create_task(adapter.investigate_scenario(context, "concurrent-owner"))
    await started.wait()
    nonowner = await adapter.investigate_scenario(context, "concurrent-owner")
    assert nonowner.status == InvestigationStatus.FAILED
    assert await adapter.get_saved_result("concurrent-owner") is None
    release.set()
    owner_result = await owner
    saved = await adapter.get_saved_result("concurrent-owner")
    assert saved.status == InvestigationStatus.COMPLETED
    assert saved.model_dump() == owner_result.model_dump()
    assert saved.errors == []


@pytest.mark.asyncio
async def test_delayed_final_write_cannot_publish_success_after_deadline(service, monkeypatch):
    adapter = make_adapter(service)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = adapter.ledger.finish
    def delayed(*args):
        entered.set()
        release.wait(.8)
        try:
            return original(*args)
        finally:
            finished.set()
    monkeypatch.setattr(adapter.ledger, "finish", delayed)
    task = asyncio.create_task(adapter.investigate_scenario(
        service.state_manager.context, "delayed-final-write", deadline_seconds=.15, mode="local"))
    try:
        assert await asyncio.to_thread(entered.wait, .5)
        result = await task
        assert result.status == InvestigationStatus.TIMED_OUT
        assert result.recommended_alternative is None
        assert "investigation_deadline" in result.errors
        assert (await adapter.get_saved_result(result.investigation_id)).model_dump() == result.model_dump()
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, .5)
    assert (await adapter.get_saved_result(result.investigation_id)).model_dump() == result.model_dump()


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["calls", "finish"])
async def test_cancellation_during_finalization_is_durable_and_late_workers_cannot_replace_it(service, monkeypatch, phase):
    adapter = make_adapter(service)
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    original = getattr(adapter.ledger, phase)
    def delayed(*args):
        entered.set()
        release.wait(.8)
        try:
            return original(*args)
        finally:
            finished.set()
    monkeypatch.setattr(adapter.ledger, phase, delayed)
    task = asyncio.create_task(adapter.investigate_scenario(
        service.state_manager.context, f"cancel-final-{phase}", mode="local"))
    try:
        assert await asyncio.to_thread(entered.wait, .5)
        task.cancel()
        result = await task
        assert result.status == InvestigationStatus.CANCELLED
        assert result.recommended_alternative is None
        assert "investigation_cancelled" in result.errors
        assert (await adapter.get_saved_result(result.investigation_id)).model_dump() == result.model_dump()
    finally:
        release.set()
        assert await asyncio.to_thread(finished.wait, .5)
    assert (await adapter.get_saved_result(result.investigation_id)).model_dump() == result.model_dump()


@pytest.mark.asyncio
async def test_context_drift_during_final_ledger_read_blocks_canonical_recommendation(service, monkeypatch):
    adapter = make_adapter(service)
    context = service.state_manager.context
    original = adapter.ledger.calls
    def drift(*args):
        entries = original(*args)
        with service.state_manager._state_lock:
            values = context.model_dump(exclude={"context_hash"})
            values["scenario_revision"] += 1
            service.state_manager.context = RunContext(**values)
        return entries
    monkeypatch.setattr(adapter.ledger, "calls", drift)
    result = await adapter.investigate_scenario(context, "final-read-drift", mode="local")
    assert result.status == InvestigationStatus.FAILED
    assert "stale_context" in result.errors
    assert result.recommended_alternative is None
    assert not result.base_context.is_current(service.state_manager.context)
    assert (await adapter.get_saved_result(result.investigation_id)).model_dump() == result.model_dump()


@pytest.mark.asyncio
async def test_staged_result_is_not_public_or_replayed_after_restart(service):
    adapter = make_adapter(service)
    context = service.state_manager.context
    completed = await adapter.investigate_scenario(context, "source-result", mode="local")
    adapter.ledger.begin("staged-result", context.model_dump(mode="json"), "local")
    staged = completed.model_copy(update={"investigation_id": "staged-result"})
    adapter.ledger.finish("staged-result", staged.model_dump_json())
    assert await adapter.get_saved_result("staged-result") is None
    restarted = make_adapter(service)
    result = await restarted.investigate_scenario(context, "staged-result", mode="local")
    assert result.status == InvestigationStatus.FAILED
    assert result.errors == ["investigation_recovery_required"]
    assert result.replayed is False
    assert result.recommended_alternative is None
    assert await restarted.get_saved_result("staged-result") is None


@pytest.mark.asyncio
async def test_terminal_cas_is_immutable_even_if_late_staging_or_publication_attempts_success(service):
    adapter = make_adapter(service)
    result = await adapter.investigate_scenario(service.state_manager.context, "terminal-cas", mode="local")
    attempted = result.model_copy(update={"status": InvestigationStatus.FAILED, "recommended_alternative": None})
    adapter.ledger.finish(result.investigation_id, attempted.model_dump_json())
    assert adapter.ledger.publish(result.investigation_id, attempted.model_dump_json()) == result.model_dump_json()
    assert (await adapter.get_saved_result(result.investigation_id)).model_dump() == result.model_dump()


@pytest.mark.asyncio
async def test_immediate_cancellation_has_resolved_ownership_before_first_await(service, monkeypatch):
    adapter = make_adapter(service)
    def old_threaded_begin(*args):
        # An old delayed begin must never run after the cancelled await.
        raise AssertionError("Ownership was delegated to an uninterruptible worker")
    monkeypatch.setattr(adapter.ledger, "begin", old_threaded_begin)
    task = asyncio.create_task(adapter.investigate_scenario(
        service.state_manager.context, "cancel-first-turn", mode="local"))
    await asyncio.sleep(0)  # Same registration boundary used by the API task registry.
    task.cancel()
    result = await task
    assert result.status == InvestigationStatus.CANCELLED
    assert result.recommended_alternative is None
    assert (await adapter.get_saved_result(result.investigation_id)).model_dump() == result.model_dump()


@pytest.mark.asyncio
async def test_busy_ownership_claim_fails_without_waiting_or_late_running_row(service):
    adapter = make_adapter(service)
    entered, release = threading.Event(), threading.Event()
    def hold_lock():
        with adapter.ledger._lock:
            entered.set()
            release.wait(.8)
    holder = asyncio.create_task(asyncio.to_thread(hold_lock))
    try:
        assert await asyncio.to_thread(entered.wait, .5)
        started = time.monotonic()
        result = await adapter.investigate_scenario(service.state_manager.context, "busy-claim", mode="local")
        assert time.monotonic() - started < .1
        assert result.status == InvestigationStatus.FAILED
        assert result.errors == ["investigation_storage_busy"]
        assert result.recommended_alternative is None
    finally:
        release.set()
        await holder
    assert await adapter.get_saved_result("busy-claim") is None
    with adapter.ledger._lock:
        assert adapter.ledger._connection.execute(
            "SELECT 1 FROM managed_runs_v1 WHERE investigation_id=?", ("busy-claim",)).fetchone() is None
