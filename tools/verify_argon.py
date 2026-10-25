"""Opt-in live smoke check. Uses isolated state, no hardware, sanitized receipts.

Run from repository root: .venv/bin/python -m tools.verify_argon --live
Default image is a synthetic labeled board: this does NOT validate real-camera accuracy.
Supply --image PATH for a separately reviewed board capture. No credentials are saved.
"""
import argparse
import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
import logging
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from PIL import Image, ImageDraw, ImageFont
from backend.app.ai.grounding.adapter import GroundingAdapter
from backend.app.ai.managed.adapter import ManagedAgentAdapter
from backend.app.contracts import Capture
from backend.app.state.manager import StateManager
from backend.app.state.service import ScenarioService
from backend.app.state.store import SQLiteStore


def image_bytes(path):
    if path:
        with Image.open(path) as image:
            image = image.convert('RGB')
            output = io.BytesIO()
            image.save(output, format='JPEG')
            return output.getvalue(), image.size
    image = Image.new('RGB', (900, 600), 'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=30)
    for label, bounds in [('T_P1', (60, 100, 300, 300)), ('T_P2', (560, 100, 800, 300)), ('T_B2', (560, 380, 800, 570))]:
        draw.rectangle(bounds, outline='black', width=5)
        draw.text((bounds[0]+30, bounds[1]+15), label, fill='black', font=font)
    draw.ellipse((610, 175, 750, 295), fill='red')
    draw.text((615, 215), 'BLOCKED', fill='black', font=ImageFont.load_default(size=22))
    output = io.BytesIO()
    image.save(output, format='JPEG')
    return output.getvalue(), image.size


async def verify(args):
    logging.disable(logging.CRITICAL)
    report = {'checked_at': datetime.now(timezone.utc).isoformat(),
              'evidence_type': 'live_provider_smoke',
              'input_kind': 'provided_board_image' if args.image else 'synthetic_test_board',
              'real_camera_accuracy_verified': False, 'physical_hardware_tested': False}
    if not os.environ.get('GEMINI_API_KEY', '').strip():
        report.update(status='unavailable', errors=['configuration_missing'])
        return report
    with TemporaryDirectory(prefix='spatialtwin-live-check-') as directory:
        manager = StateManager(SQLiteStore(str(Path(directory)/'isolated.sqlite3')))
        direct = GroundingAdapter()
        managed = ManagedAgentAdapter(ScenarioService(manager))
        try:
            if args.cancel_receipt:
                previous = json.loads(args.cancel_receipt.read_text())
                identity = previous.get('investigation', {}).get('provider_interaction_id')
                if not identity:
                    return {**report, 'status': 'failed', 'errors': ['cleanup_identity_missing']}
                try:
                    interaction = await asyncio.wait_for(managed.client.aio.interactions.get(id=identity, timeout=5), timeout=5)
                    lifecycle = interaction.status
                    if lifecycle in ('queued', 'in_progress', 'requires_action'):
                        interaction = await asyncio.wait_for(managed.client.aio.interactions.cancel(id=identity, timeout=5), timeout=5)
                        lifecycle = interaction.status
                    return {**report, 'status': 'cleanup_checked', 'provider_interaction_id': identity, 'provider_status': lifecycle}
                except Exception:
                    return {**report, 'status': 'failed', 'errors': ['provider_cleanup_unconfirmed']}
            if args.only != 'managed':
                data, dimensions = image_bytes(args.image)
                capture = Capture(capture_id=uuid4().hex, timestamp_iso=datetime.now(timezone.utc).isoformat(),
                    source_kind='annotated_plan', dimensions=dimensions, source_geometry_revision=manager.context.geometry_revision,
                    expected_scenario_revision=manager.context.scenario_revision,
                    expected_physical_revision=manager.context.physical_revision, source_context=manager.context,
                    image_base64=base64.b64encode(data).decode(), image_sha256=hashlib.sha256(data).hexdigest())
                if direct.client:
                    resource = direct.client.aio.interactions
                    create = resource.create

                    async def observe_direct(*call_args, **call_kwargs):
                        response = await create(*call_args, **call_kwargs)
                        identity = getattr(response, 'id', None)
                        report['direct_response_structure'] = {
                            'type': type(response).__name__,
                            'keys': sorted(response.model_dump(exclude_none=True).keys()),
                            'id_type': type(identity).__name__,
                            'id_length': len(identity) if isinstance(identity, str) else None,
                            'status': getattr(response, 'status', None),
                            'model': getattr(response, 'model', None),
                            'step_types': [getattr(step, 'type', None) for step in (getattr(response, 'steps', None) or [])],
                        }
                        return response

                    resource.create = observe_direct
                grounding = await direct.interpret_capture(capture, manager.context, deadline_seconds=30)
                report['grounding'] = grounding.model_dump(mode='json')
            if args.only != 'direct':
                investigation = await managed.investigate_scenario(manager.context,
                    investigation_id=uuid4().hex, deadline_seconds=60, mode='live')
                report['investigation'] = investigation.model_dump(mode='json')
            outcomes = [value['status'] == 'completed' for key, value in report.items() if key in ('grounding', 'investigation')]
            report['status'] = 'passed' if outcomes and all(outcomes) else 'failed'
            if not args.image and 'grounding' in report:
                report['synthetic_target_correct'] = bool(grounding.proposal and grounding.proposal.selected_entity_id == 'P2')
                if not report['synthetic_target_correct']:
                    report['status'] = 'failed'
        finally:
            await direct.aclose()
            await managed.aclose()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Explicitly authorize real, potentially billed provider requests')
    parser.add_argument('--image', type=Path)
    parser.add_argument('--only', choices=['direct','managed','both'], default='both')
    parser.add_argument('--cancel-receipt', type=Path, help='Inspect/cancel only the previous smoke interaction recorded in this receipt')
    parser.add_argument('--output', type=Path, default=Path('runtime/argon-live-check.json'))
    args = parser.parse_args()
    if not args.live:
        parser.error('--live is required; offline tests are python -m pytest tests -q')
    try:
        report = asyncio.run(verify(args))
    except Exception:
        report = {'status': 'failed', 'errors': ['smoke_check_failed'], 'physical_hardware_tested': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    args.output.chmod(0o600)
    print(json.dumps({'status': report['status'], 'receipt': str(args.output.resolve()),
                      'direct_status': report.get('grounding', {}).get('status'),
                      'managed_status': report.get('investigation', {}).get('status'),
                      'errors': report.get('errors', [])}))
    return 0 if report['status'] in ('passed','cleanup_checked') else 1


if __name__ == '__main__':
    raise SystemExit(main())
