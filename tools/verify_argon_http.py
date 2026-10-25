"""Opt-in live API-to-provider trial with isolated storage and hardware disabled.

Run: .venv/bin/python -m tools.verify_argon_http --live
The synthetic image and automated test review do not establish camera accuracy.
"""
import argparse
import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import importlib
import json
import logging
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch
from uuid import uuid4

import httpx
from backend.app.state.store import SQLiteStore
from tools.verify_argon import image_bytes


class WorkflowError(Exception):
    pass


async def exercise_api(client, report):
    """Use public JSON contracts; usable with real or mocked SDK HTTP transport."""
    phases = report.setdefault('phases', [])

    async def request(method, path, *, expected=200, **kwargs):
        response = await client.request(method, path, **kwargs)
        if response.status_code != expected:
            phases.append({'path': path, 'http_status': response.status_code, 'passed': False})
            raise WorkflowError('unexpected_api_status')
        return response.json()

    scenario = '/api/scenarios/facility-demo'
    snapshot = await request('GET', scenario)
    original_context = snapshot['context']
    data, dimensions = image_bytes(None)
    capture_id = uuid4().hex
    timestamp = datetime.now(timezone.utc).isoformat()
    digest = hashlib.sha256(data).hexdigest()
    grounding = await request('POST', scenario+'/grounding', json={
        'capture_id': capture_id, 'timestamp_iso': timestamp, 'dimensions': list(dimensions),
        'source_context': original_context, 'source_kind': 'annotated_plan', 'mode': 'live',
        'image_base64': base64.b64encode(data).decode(), 'image_sha256': digest, 'deadline_seconds': 30,
    })
    report['grounding'] = grounding
    proposal = grounding.get('proposal') or {}
    if not (grounding['status'] == 'completed' and grounding['provenance'] == 'live'
            and grounding.get('provider_interaction_id') and grounding.get('provider_model') == 'gemini-4-argon'
            and proposal.get('status') == 'matched' and proposal.get('selected_entity_type') == 'portal'
            and proposal.get('selected_entity_id') == 'P2'):
        raise WorkflowError('live_grounding_not_verified')
    phases.append({'phase': 'live_grounding', 'passed': True})
    capture = (await request('GET', scenario+'/captures/'+capture_id))['capture']
    if not (capture['timestamp_iso'] == timestamp and capture['source_context'] == original_context
            and capture['image_sha256'] == digest and capture['image_base64'] == base64.b64encode(data).decode()):
        raise WorkflowError('capture_evidence_mismatch')
    phases.append({'phase': 'durable_capture', 'passed': True})
    command = {'type': 'APPLY_BLOCKAGE', 'expected_context': original_context,
        'expected_scenario_revision': original_context['scenario_revision'], 'idempotency_key': uuid4().hex,
        'target_type': 'portal', 'target_id': 'P2', 'source': 'grounding_proposal',
        'proposal_id': grounding['proposal_id'], 'reviewed': True}
    await request('POST', scenario+'/commands', expected=422, json={**command, 'reviewed': False})
    applied = await request('POST', scenario+'/commands', json=command)
    snapshot = applied['snapshot']
    if snapshot['blocked_portals'] != ['P2'] or snapshot['context']['scenario_revision'] != original_context['scenario_revision'] + 1:
        raise WorkflowError('reviewed_command_not_applied')
    phases.append({'phase': 'explicit_automated_test_review', 'passed': True})
    await request('POST', scenario+'/commands', expected=409, json=command)
    phases.append({'phase': 'duplicate_stale_apply_blocked', 'passed': True})
    identity = uuid4().hex
    payload = {'expected_context': snapshot['context'], 'investigation_id': identity, 'mode': 'live', 'deadline_seconds': 60}
    pending = asyncio.create_task(client.post(scenario+'/investigate', json=payload))
    observed = []
    while not pending.done():
        await asyncio.wait([pending], timeout=1)
        if not pending.done():
            progress = await client.get(scenario+'/investigations/'+identity+'/progress')
            if progress.status_code == 200:
                value = progress.json()
                if len(observed) < 64:
                    observed.append({'status': value['status'], 'receipt_count': len(value['provider_progress'])})
    response = await pending
    if response.status_code != 200:
        raise WorkflowError('investigation_api_failed')
    investigation = response.json()['investigation']
    report['investigation'] = investigation
    report['progress_observed'] = observed
    if not (investigation['status'] == 'completed' and investigation['provenance'] == 'live'
            and investigation.get('provider_model') == 'gemini-4-argon'
            and investigation.get('provider_interaction_id') and investigation['recommended_alternative'] == 'OPEN_P3'
            and not investigation['errors']):
        raise WorkflowError('live_investigation_not_verified')
    candidates = {c['alternative_id']: c for c in investigation['candidate_envelopes']}
    keep, opened = candidates['KEEP_CURRENT'], candidates['OPEN_P3']
    if not (all(c['validator_report']['is_valid'] and c['base_context'] == snapshot['context'] for c in candidates.values())
            and opened['completed_crossings'] > keep['completed_crossings']):
        raise WorkflowError('comparison_evidence_invalid')
    phases.append({'phase': 'live_checked_investigation', 'passed': True})
    for candidate in candidates.values():
        saved = await request('GET', '/api/runs/'+candidate['run_id'])
        if saved != candidate:
            raise WorkflowError('checked_run_not_durable')
    replay = (await request('POST', scenario+'/investigate', json=payload))['investigation']
    if not (replay.get('replayed') and replay['provider_interaction_id'] == investigation['provider_interaction_id']
            and replay['candidate_envelopes'] == investigation['candidate_envelopes']):
        raise WorkflowError('replay_evidence_mismatch')
    phases.append({'phase': 'durable_replay', 'passed': True})
    await request('POST', scenario+'/investigate', expected=409, json={**payload, 'expected_context': original_context})
    phases.append({'phase': 'stale_investigation_blocked', 'passed': True})
    await request('POST', scenario+'/grounding', expected=403, json={
        'capture_id': uuid4().hex, 'timestamp_iso': timestamp, 'dimensions': list(dimensions),
        'source_context': snapshot['context'], 'source_kind': 'fixture', 'mode': 'fixture', 'fixture_target': 'P2',
    })
    phases.append({'phase': 'production_fixture_blocked', 'passed': True})
    report.update(status='passed', review_kind='automated_synthetic_test_review',
        modeled_comparison={'keep_current': keep['completed_crossings'], 'open_p3': opened['completed_crossings']})


async def verify(report):
    if not os.environ.get('GEMINI_API_KEY', '').strip():
        raise WorkflowError('configuration_missing')
    if 'backend.app.main' in sys.modules:
        raise WorkflowError('api_already_loaded_cannot_isolate')
    with TemporaryDirectory(prefix='spatialtwin-http-live-') as directory:
        original_init = SQLiteStore.__init__

        def isolated_init(self, db_path=None):
            original_init(self, db_path or str(Path(directory)/'isolated.sqlite3'))

        with patch.dict(os.environ, {'SERIAL_PORT': '', 'SPATIALTWIN_MODE': 'production'}), patch.object(SQLiteStore, '__init__', isolated_init):
            api = importlib.import_module('backend.app.main')

            class NoHardware:
                is_simulator = True
                port = None
                command_count = 0

                async def update_display(self):
                    pass

                async def request_gate_target(self, *args, **kwargs):
                    self.command_count += 1
                    raise WorkflowError('physical_action_forbidden')

            api.hardware_bridge = NoHardware()
            try:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api.app), base_url='http://isolated-spatialtwin', timeout=65) as client:
                    await exercise_api(client, report)
            finally:
                report['hardware_command_count'] = api.hardware_bridge.command_count
                await api.grounding_adapter.aclose()
                await api.managed_agent_adapter.aclose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('runtime/argon-http-live-check.json'))
    args = parser.parse_args()
    if not args.live:
        parser.error('--live is required for potentially billed provider calls')
    logging.disable(logging.CRITICAL)
    report = {'status': 'failed', 'checked_at': datetime.now(timezone.utc).isoformat(),
        'evidence_type': 'real_provider_via_public_api', 'api_transport': 'isolated_ASGI_HTTP',
        'input_kind': 'synthetic_test_board', 'real_camera_accuracy_verified': False, 'physical_hardware_tested': False}
    started = time.monotonic()
    try:
        asyncio.run(verify(report))
    except Exception as error:
        report['errors'] = [str(error) if isinstance(error, WorkflowError) else 'http_smoke_failed']
    report['elapsed_ms'] = (time.monotonic()-started)*1000
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    args.output.chmod(0o600)
    print(json.dumps({'status': report['status'], 'receipt': str(args.output.resolve()), 'errors': report.get('errors', [])}))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
