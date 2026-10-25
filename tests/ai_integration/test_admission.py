"""Public API and durable review checks: no provider/network/device access."""
from datetime import datetime, timezone
import json
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from backend.app.contracts import RunContext, GateObservedState, ApplyBlockageCommand, EntityType, TargetId
from backend.app.state.manager import StateManager
from backend.app.state.service import ScenarioService


@pytest.fixture
def api(monkeypatch):
    from backend.app import main
    from backend.app.ai.grounding.adapter import GroundingAdapter
    from backend.app.ai.managed.adapter import ManagedAgentAdapter
    manager = StateManager()
    monkeypatch.setattr(main, "state_manager", manager)
    service = ScenarioService(manager)
    monkeypatch.setattr(main, "scenario_service", service)
    monkeypatch.setattr(main, "grounding_adapter", GroundingAdapter(api_key=""))
    monkeypatch.setattr(main, "managed_agent_adapter", ManagedAgentAdapter(service, api_key=""))
    monkeypatch.setattr(main, "active_investigations", {})

    async def no_device():
        return None

    monkeypatch.setattr(main.hardware_bridge, "update_display", no_device)
    return TestClient(main.app), manager, main


def fixture_body(ctx):
    return {"capture_id": uuid4().hex, "timestamp_iso": datetime.now(timezone.utc).isoformat(),
            "source_context": ctx.model_dump(), "dimensions": [1920, 1080], "source_kind": "fixture",
            "mode": "fixture", "fixture_target": "P2"}


def command(ctx, proposal_id=None, **extra):
    return {"type": "APPLY_BLOCKAGE", "expected_context": ctx.model_dump(),
            "expected_scenario_revision": ctx.scenario_revision, "idempotency_key": uuid4().hex,
            "target_type": "portal", "target_id": "P2", "source": "grounding_proposal",
            "proposal_id": proposal_id, "reviewed": True, **extra}


def test_fixture_persisted_review_chain_and_no_double_apply(api):
    client, manager, _ = api
    ctx = manager.get_current_context()
    body = fixture_body(ctx)
    response = client.post('/api/scenarios/facility-demo/grounding', json=body)
    assert response.status_code == 200
    result = response.json()
    assert result['provenance'] == 'fixture'
    assert result['token_usage'] == {}
    saved = manager.store.get_grounding_result(result['proposal_id'])
    assert saved['result'] == result
    with manager.store._get_connection() as db:
        capture = json.loads(db.execute('SELECT metadata_json FROM observations WHERE capture_id=?', (body['capture_id'],)).fetchone()[0])
    assert capture['timestamp_iso'] == body['timestamp_iso']
    assert capture['source_context'] == ctx.model_dump()
    assert client.post('/api/scenarios/facility-demo/grounding', json=body).status_code == 409
    rejected = command(ctx, result['proposal_id'], reviewed=False)
    assert client.post('/api/scenarios/facility-demo/commands', json=rejected).status_code == 422
    forged = command(ctx, result['proposal_id'], target_id='P1')
    assert client.post('/api/scenarios/facility-demo/commands', json=forged).status_code == 400
    accepted = command(ctx, result['proposal_id'])
    assert client.post('/api/scenarios/facility-demo/commands', json=accepted).status_code == 200
    assert manager.blocked_portals == {'P2'}
    assert manager.store.get_grounding_result(result['proposal_id'])['reviewed_command_id'] == accepted['idempotency_key']
    assert client.post('/api/scenarios/facility-demo/commands', json=accepted).status_code == 409


def test_full_context_and_hash_rejected(api):
    client, manager, _ = api
    ctx = manager.get_current_context()
    changed = RunContext(**{**ctx.model_dump(exclude={'context_hash'}), 'parameters_revision': 'other'})
    assert client.post('/api/scenarios/facility-demo/grounding', json=fixture_body(changed)).status_code == 409
    assert client.post('/api/scenarios/facility-demo/commands', json=command(changed, source='manual_override')).status_code == 409
    forged = fixture_body(ctx)
    forged['source_context']['context_hash'] = 'forged'
    assert client.post('/api/scenarios/facility-demo/grounding', json=forged).status_code == 422


def test_production_disables_fixture_and_local(api, monkeypatch):
    client, manager, _ = api
    monkeypatch.setenv('SPATIALTWIN_MODE', 'production')
    ctx = manager.get_current_context()
    assert not client.get('/health').json()['ai']['fixtures_enabled']
    assert client.post('/api/scenarios/facility-demo/grounding', json=fixture_body(ctx)).status_code == 403
    assert client.post('/api/scenarios/facility-demo/investigate', json={
        'expected_context': ctx.model_dump(), 'investigation_id': uuid4().hex, 'mode': 'local'
    }).status_code == 403


def test_unconfigured_is_unavailable_not_fixture(api):
    client, manager, _ = api
    body = fixture_body(manager.get_current_context())
    body.update(mode='live', source_kind='tabletop_camera')
    body.pop('fixture_target')
    result = client.post('/api/scenarios/facility-demo/grounding', json=body).json()
    assert result['provenance'] == 'unavailable'
    assert result['proposal'] is None
    investigation = client.post('/api/scenarios/facility-demo/investigate', json={
        'expected_context': manager.context.model_dump(), 'investigation_id': uuid4().hex
    }).json()['investigation']
    assert investigation['provenance'] == 'unavailable'
    assert investigation['recommended_alternative'] is None
    assert investigation['token_usage'] == {}


def test_invalid_intake_never_echoes_image(api):
    client, manager, _ = api
    body = fixture_body(manager.context)
    body.update(image_base64='sensitive-image-marker', thinking_level='arbitrary')
    response = client.post('/api/scenarios/facility-demo/grounding', json=body)
    assert response.status_code == 422
    assert 'sensitive-image-marker' not in response.text
    assert client.post('/api/scenarios/facility-demo/commands', json={}).status_code == 422


def test_inflight_context_change_cannot_return_applicable_proposal(api, monkeypatch):
    client, manager, main = api
    original = main.grounding_adapter.interpret_capture

    async def change_during_provider(*args, **kwargs):
        result = await original(*args, **kwargs)
        manager.context = RunContext(**{**manager.context.model_dump(exclude={'context_hash'}), 'physical_revision': 2})
        return result

    monkeypatch.setattr(main.grounding_adapter, 'interpret_capture', change_during_provider)
    result = client.post('/api/scenarios/facility-demo/grounding', json=fixture_body(manager.context)).json()
    assert result['status'] == 'failed'
    assert result['proposal'] is None
    assert 'stale_context' in result['errors']


def test_numeric_request_id_reuses_run_and_rejects_other_inputs(monkeypatch):
    from backend.app.contracts import AlternativeId
    manager = StateManager()
    service = ScenarioService(manager)
    calls = []
    solve = service.planner.solve

    def counted(*args, **kwargs):
        calls.append(1)
        return solve(*args, **kwargs)

    monkeypatch.setattr(service.planner, 'solve', counted)
    a = service.evaluate_alternative(manager.context, AlternativeId.KEEP_CURRENT, 'unique-call')
    service2 = ScenarioService(manager)
    b = service2.evaluate_alternative(manager.context, AlternativeId.KEEP_CURRENT, 'unique-call')
    assert a.run_id == b.run_id
    assert len(calls) == 1
    with pytest.raises(ValueError, match='different inputs'):
        service.evaluate_alternative(manager.context, AlternativeId.OPEN_P3, 'unique-call')


def test_uncertain_gate_state_invalidates_old_ai_context():
    manager = StateManager()
    manager.apply_blockage(ApplyBlockageCommand(expected_scenario_revision=1, idempotency_key='block', target_type=EntityType.PORTAL, target_id=TargetId.P2))
    manager.update_physical_observation(GateObservedState.OPEN, 'boot', 1, 1)
    old = manager.context
    old_crossings = manager.current_plan.completed_crossings
    manager.update_physical_observation(GateObservedState.FAULT, 'boot', 2, 1)
    assert not old.is_current(manager.context)
    assert manager.current_plan.completed_crossings < old_crossings
    assert manager.current_plan.base_context == manager.context


def test_physical_approval_requires_saved_current_evidence_and_single_submission(api, monkeypatch):
    client, manager, main = api
    manager.apply_blockage(ApplyBlockageCommand(expected_scenario_revision=1, idempotency_key='block', target_type=EntityType.PORTAL, target_id=TargetId.P2))
    ctx = manager.context
    requests = []

    async def device_stub(target):
        requests.append(target)
        return True, 'mock-command'

    monkeypatch.setattr(main.hardware_bridge, 'request_gate_target', device_stub)
    # The device is stubbed here, so this test runs as the simulator; physical hardware has its own tests.
    monkeypatch.setattr(main.hardware_bridge, 'is_simulator', True)
    base = {'expected_context': ctx.model_dump(), 'candidate_alternative': 'OPEN_P3', 'idempotency_key': 'approval-one'}
    assert client.post('/api/hardware/operator-approve', json=base).status_code == 422
    result = client.post('/api/scenarios/facility-demo/investigate', json={
        'expected_context': ctx.model_dump(), 'investigation_id': uuid4().hex, 'mode': 'local'
    }).json()['investigation']
    assert result['status'] == 'completed'
    base['investigation_id'] = result['investigation_id']
    base['candidate_run_id'] = next(c['run_id'] for c in result['candidate_envelopes'] if c['alternative_id'] == 'OPEN_P3')
    assert client.post('/api/hardware/operator-approve', json=base).status_code == 200
    assert len(requests) == 1
    assert client.post('/api/hardware/operator-approve', json=base).status_code == 409
    assert len(requests) == 1


def test_restart_never_revalidates_old_evidence(tmp_path):
    from backend.app.state.store import SQLiteStore
    path = str(tmp_path / 'restart.sqlite3')
    first = StateManager(SQLiteStore(path))
    first.apply_blockage(ApplyBlockageCommand(expected_scenario_revision=1, idempotency_key='first', target_type=EntityType.PORTAL, target_id=TargetId.P2))
    old_context = first.context
    second = StateManager(SQLiteStore(path))
    second.apply_blockage(ApplyBlockageCommand(expected_scenario_revision=1, idempotency_key='second', target_type=EntityType.PORTAL, target_id=TargetId.P1))
    assert second.context.scenario_revision == old_context.scenario_revision
    assert second.context.state_epoch != old_context.state_epoch
    assert not second.context.is_current(old_context)
    assert second.physical_gate_state == GateObservedState.UNKNOWN


def test_conflicting_investigation_cannot_replace_original_record(api):
    client, manager, _ = api
    identity = uuid4().hex
    body = {'expected_context': manager.context.model_dump(), 'investigation_id': identity, 'mode': 'local'}
    original = client.post('/api/scenarios/facility-demo/investigate', json=body).json()['investigation']
    assert original['status'] == 'completed'
    body['mode'] = 'live'
    conflict = client.post('/api/scenarios/facility-demo/investigate', json=body).json()['investigation']
    assert conflict['status'] == 'failed'
    assert 'investigation_identity_conflict' in conflict['errors']
    assert manager.store.get_investigation(identity) == original


def test_pending_nonowner_does_not_poison_canonical_api_index(api):
    client, manager, main = api
    identity = uuid4().hex
    main.managed_agent_adapter.ledger.begin(identity, manager.context.model_dump(mode='json'), 'local')
    body = {'expected_context': manager.context.model_dump(), 'investigation_id': identity, 'mode': 'local'}
    transient = client.post('/api/scenarios/facility-demo/investigate', json=body).json()['investigation']
    assert transient['status'] == 'failed'
    assert manager.store.get_investigation(identity) is None


def test_live_capture_expires_before_apply(api):
    from datetime import timedelta
    client, manager, _ = api
    ctx = manager.context
    body = fixture_body(ctx)
    result = client.post('/api/scenarios/facility-demo/grounding', json=body).json()
    # Simulate a validated live result that waited beyond the review window.
    result['provenance'] = 'live'
    with manager.store._get_connection() as db:
        db.execute('UPDATE grounding_results SET result_json=? WHERE proposal_id=?', (json.dumps(result), result['proposal_id']))
        old_capture = manager.store.get_capture(body['capture_id'])
        old_capture['timestamp_iso'] = (datetime.now(timezone.utc)-timedelta(minutes=5)).isoformat()
        db.execute('UPDATE observations SET metadata_json=? WHERE capture_id=?', (json.dumps(old_capture), body['capture_id']))
    response = client.post('/api/scenarios/facility-demo/commands', json=command(ctx, result['proposal_id']))
    assert response.status_code == 400
    assert 'expired' in response.json()['detail']
    assert manager.blocked_portals == set()


@pytest.mark.asyncio
async def test_public_api_entire_workflow_uses_actual_sdk_and_durable_evidence(api, monkeypatch):
    import httpx
    from backend.app.ai.grounding.adapter import GroundingAdapter
    from backend.app.ai.managed.adapter import ManagedAgentAdapter
    from tools.verify_argon_http import exercise_api
    _, manager, main = api
    main.grounding_adapter = GroundingAdapter(api_key='offline-test-placeholder')
    main.managed_agent_adapter = ManagedAgentAdapter(ScenarioService(manager), api_key='offline-test-placeholder')
    monkeypatch.setenv('SPATIALTWIN_MODE', 'production')
    original_send = httpx.AsyncClient.send
    provider_requests = []

    async def sdk_http(client, request, *args, **kwargs):
        if request.url.host == 'isolated-api':
            return await original_send(client, request, *args, **kwargs)
        body = json.loads(request.content)
        provider_requests.append(body)
        if 'agent' not in body:
            output = {'status': 'matched', 'candidate_ids': ['portal:P2'], 'selected_entity_type': 'portal',
                'selected_entity_id': 'P2', 'operation': 'SET_UNAVAILABLE', 'evidence': 'Synthetic token on T_P2.', 'box_2d': [200, 600, 500, 900]}
            response = {'id': 'mock-direct', 'model': 'gemini-4-argon', 'status': 'completed',
                'steps': [{'type': 'model_output', 'content': [{'type': 'text', 'text': json.dumps(output)}]}], 'usage': {'total_tokens': 30}}
        else:
            initial = 'previous_interaction_id' not in body
            response = {'id': 'mock-agent-initial' if initial else 'mock-agent-final', 'model': 'gemini-4-argon',
                'environment_id': 'mock-env', 'status': 'requires_action' if initial else 'completed',
                'steps': [{'type': 'function_call', 'id': 'comparison', 'name': 'get_checked_comparison', 'arguments': {}}] if initial else [],
                'usage': {'total_tokens': 25 if initial else 30}}
        return httpx.Response(200, json=response, request=request)

    monkeypatch.setattr(httpx.AsyncClient, 'send', sdk_http)
    report = {}
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://isolated-api') as client:
            await exercise_api(client, report)
        assert report['status'] == 'passed'
        assert len(provider_requests) == 3  # Replay and rejected requests do not call Gemini.
        assert report['modeled_comparison']['open_p3'] > report['modeled_comparison']['keep_current']
        assert manager.store.get_investigation(report['investigation']['investigation_id'])['provenance'] == 'live'
    finally:
        await main.grounding_adapter.aclose()
        await main.managed_agent_adapter.aclose()


@pytest.mark.asyncio
async def test_progress_and_explicit_cancel_finish_the_owned_job(api, monkeypatch):
    import asyncio
    import httpx
    from types import SimpleNamespace
    from backend.app.ai.managed.adapter import ManagedAgentAdapter
    _, manager, main = api
    entered = asyncio.Event()
    creates = []

    async def slow_create(**kwargs):
        creates.append(kwargs)
        entered.set()
        await asyncio.Event().wait()

    async def close():
        pass

    provider = SimpleNamespace(aio=SimpleNamespace(interactions=SimpleNamespace(create=slow_create), aclose=close))
    adapter = ManagedAgentAdapter(ScenarioService(manager), api_key='', client=provider)
    monkeypatch.setattr(main, 'managed_agent_adapter', adapter)
    identity = uuid4().hex
    root = '/api/scenarios/facility-demo'
    ctx = manager.context
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://isolated-api') as client:
            pending = asyncio.create_task(client.post(root+'/investigate', json={'expected_context': ctx.model_dump(), 'investigation_id': identity}))
            await asyncio.wait_for(entered.wait(), timeout=2)
            progress = (await client.get(root+'/investigations/'+identity+'/progress')).json()
            assert progress['status'] == 'running'
            assert progress['provider_progress']
            wrong = RunContext(**{**ctx.model_dump(exclude={'context_hash'}), 'state_epoch': 'wrong-session'})
            assert (await client.post(root+'/investigations/'+identity+'/cancel', json={'expected_context': wrong.model_dump()})).status_code == 409
            response = await client.post(root+'/investigations/'+identity+'/cancel', json={'expected_context': ctx.model_dump()})
            assert response.json()['status'] == 'cancellation_requested'
            again = await client.post(root+'/investigations/'+identity+'/cancel', json={'expected_context': ctx.model_dump()})
            assert again.json()['status'] in ('cancellation_requested', 'already_finished')
            result = (await asyncio.wait_for(pending, timeout=3)).json()['investigation']
            assert result['status'] == 'cancelled'
            assert result['recommended_alternative'] is None
            assert len(creates) == 1
            assert manager.store.get_investigation(identity)['status'] == 'cancelled'
            final = (await client.get(root+'/investigations/'+identity+'/progress')).json()
            assert final['status'] == 'cancelled'
    finally:
        await adapter.aclose()


@pytest.mark.asyncio
async def test_shutdown_cancels_owned_jobs_and_closes_clients_on_error(api, monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    _, manager, main = api
    monkeypatch.setattr(main.hardware_bridge, 'start', AsyncMock())
    monkeypatch.setattr(main.hardware_bridge, 'stop', AsyncMock())
    monkeypatch.setattr(main.grounding_adapter, 'aclose', AsyncMock())
    monkeypatch.setattr(main.managed_agent_adapter, 'aclose', AsyncMock())
    pending = asyncio.create_task(asyncio.Event().wait())
    main.active_investigations['pending'] = (pending, manager.context)
    with pytest.raises(RuntimeError, match='application failure'):
        async with main.lifespan(main.app):
            raise RuntimeError('application failure')
    assert pending.cancelled()
    main.hardware_bridge.stop.assert_awaited_once()
    main.grounding_adapter.aclose.assert_awaited_once()
    main.managed_agent_adapter.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_api_rechecks_context_after_canonical_lookup_before_publication(api, monkeypatch):
    import httpx
    _, manager, main = api
    original = main.managed_agent_adapter.get_saved_result
    context = manager.context
    identity = uuid4().hex

    async def concurrent_change(investigation_id):
        result = await original(investigation_id)
        manager.context = RunContext(**{**manager.context.model_dump(exclude={'context_hash'}), 'parameters_revision': 'new-parameters'})
        return result

    monkeypatch.setattr(main.managed_agent_adapter, 'get_saved_result', concurrent_change)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://isolated-api') as client:
        response = await client.post('/api/scenarios/facility-demo/investigate', json={
            'expected_context': context.model_dump(), 'investigation_id': identity, 'mode': 'local'})
    result = response.json()['investigation']
    assert result['status'] == 'failed'
    assert result['recommended_alternative'] is None
    assert 'stale_context' in result['errors']
    assert manager.store.get_investigation(identity) is None
