"""Opt-in live capability probes P1..P11 with sanitized receipts.

P8-P11 (agent team: sandbox networkx ladder, trace stream shape, hooks deny, environment reuse) are opt-in only:
they run solely when named with --only, e.g. --only P8 (then P8b / P8c only if P8 reported "estimate").

Run from repository root: .venv/bin/python -m tools.probe_capabilities            (prints the plan, no network)
                          .venv/bin/python -m tools.probe_capabilities --live --confirm-spend
GEMINI_API_KEY is read from the environment and never printed or written.
"""
import argparse
import hashlib
import inspect
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Running this file puts tools/ first on sys.path; the backend package lives at the repo root.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CALL_CAP = 8
PRIMARY_MODEL = 'gemini-4-argon'
FALLBACK_MODEL = 'gemini-3.8-flash'
RECEIPT_DIR = REPO_ROOT / 'runtime' / 'probes'  # anchored to the repo, like video.py's receipt dir
RECEIPT_FIELDS = ('probe_id', 'timestamp_utc', 'sdk_version', 'requested_model', 'echoed_model', 'http_status_class',
                  'error_code', 'token_usage', 'interaction_id_hash', 'passed', 'reason')
OPTIONAL_FIELDS = ('mode', 'deletion_result', 'fallback_note', 'model_source', 'detail')
EXCLUDED_PROBES = {'P7': 'excluded_by_call_cap'}
OPT_IN_PROBES = frozenset({'P8', 'P8b', 'P8c', 'P9', 'P10', 'P11'})


@dataclass(frozen=True)
class ProbeSpec:
    probe_id: str
    purpose: str
    max_calls: int
    token_budget: int
    model: str = PRIMARY_MODEL


PLAN = (
    ProbeSpec('P1', 'Managed one-turn, model gemini-4-argon', 1, 5000),
    ProbeSpec('P1b', 'Managed one-turn fallback, model gemini-3.8-flash (only if P1 fails)', 1, 5000, FALLBACK_MODEL),
    ProbeSpec('P2', 'Direct grounding on existing image (regression)', 1, 15000),
    ProbeSpec('P3', 'Video static mode, 5 s synthetic clip', 1, 20000),
    ProbeSpec('P4', 'Video agentic mode', 1, 25000),
    ProbeSpec('P5', 'agents.create spatialtwin-evac-v1 + 1 run + agents.delete (needs P1 or P1b pass)', 3, 20000),
    ProbeSpec('P6', 'Run with network-deny environment (needs P1 or P1b pass)', 1, 15000),
    ProbeSpec('P7', 'Full investigation with hazard tools', 1, 30000),
    ProbeSpec('P8', 'Sandbox kit, network disabled: import networkx and run the kit sweep (exact or estimate)', 1, 30000),
    ProbeSpec('P8b', 'networkx as a zip uploaded via environments.files.upload, then zipimport (if P8 = estimate)', 3, 30000),
    ProbeSpec('P8c', 'pip install networkx with a PyPI allowlist, then reuse the environment network-disabled', 2, 40000),
    ProbeSpec('P9', 'Trace stream shape: background + stream create with code execution (event and step types)', 1, 20000),
    ProbeSpec('P10', 'Hooks deny observed: a write to /workspace/inputs is blocked by the kit guard hook', 1, 20000),
    ProbeSpec('P11', 'environments.create (SDK 2.33, undocumented) + two chained interactions reuse it + delete', 4, 30000),
)
SPECS = {spec.probe_id: spec for spec in PLAN}


class ProbeCapReached(Exception):
    """Raised before a provider call that would exceed the hard cap."""


class CallCounter:
    """Hard cap on provider calls. Metered clients charge it once per real call attempt."""

    COUNTED = frozenset({'create', 'get', 'cancel', 'delete', 'upload', 'create_environment', 'delete_environment'})
    CLEANUP = frozenset({'cancel', 'delete', 'delete_environment'})  # allowed (and counted) past the cap so nothing is orphaned

    def __init__(self, cap=CALL_CAP):
        self.cap = cap
        self.used = 0
        self.events = []  # one dict per real call: method, ok, status (int or None)

    def begin(self, method):
        if self.used >= self.cap and method not in self.CLEANUP:
            raise ProbeCapReached(method)
        self.charge(1)
        self.events.append({'method': method, 'ok': None, 'status': None})
        return len(self.events) - 1

    def finish(self, index, ok, status=None):
        self.events[index].update(ok=ok, status=status if isinstance(status, int) else None)

    def http_status_since(self, mark):
        """Real status observed on metered calls since `mark`: the last error status, else 200 when a call
        returned without raising (the SDK raises on non-2xx), else None."""
        window = self.events[mark:]
        errors = [e['status'] for e in window if e['ok'] is False and e['status'] is not None]
        if errors:
            return errors[-1]
        return 200 if any(e['ok'] for e in window) else None

    @property
    def remaining(self):
        return self.cap - self.used

    def can_afford(self, calls):
        return self.used + calls <= self.cap

    def charge(self, calls):
        self.used += max(0, calls)


def _error_status(exc):
    for value in (getattr(exc, 'code', None), getattr(exc, 'status_code', None),
                  getattr(getattr(exc, 'response', None), 'status_code', None)):
        if type(value) is int:
            return value
    return None


class MeteredClient:
    """Transparent proxy over a genai client: counts every interactions/agents create/get/cancel/delete."""

    _SCOPES = frozenset({'aio', 'interactions', 'agents', 'environments', 'files'})
    _METERED = ('interactions', 'agents', 'environments', 'files')

    def __init__(self, target, counter, scope='root'):
        self._target, self._counter, self._scope = target, counter, scope

    def __getattr__(self, name):
        value = getattr(self._target, name)
        if name in self._SCOPES:
            return MeteredClient(value, self._counter, name)
        if self._scope in self._METERED and name in CallCounter.COUNTED and callable(value):
            return self._wrap(name, value)
        return value

    def _wrap(self, name, function):
        counter = self._counter
        if inspect.iscoroutinefunction(function):
            async def call(*args, **kwargs):
                index = counter.begin(name)
                try:
                    result = await function(*args, **kwargs)
                except Exception as exc:
                    counter.finish(index, False, _error_status(exc))
                    raise
                counter.finish(index, True)
                return result
        else:
            def call(*args, **kwargs):
                index = counter.begin(name)
                try:
                    result = function(*args, **kwargs)
                except Exception as exc:
                    counter.finish(index, False, _error_status(exc))
                    raise
                counter.finish(index, True)
                return result
        return call


def meter_client(client, counter):
    return client if client is None or counter is None else MeteredClient(client, counter)


def status_class(status):
    if isinstance(status, int) and 100 <= status < 600:
        return f'{status // 100}xx'
    return 'none'


def hash_identifier(identifier):
    return hashlib.sha256(str(identifier).encode()).hexdigest()[:16] if identifier else None


def _scrub(value, secrets):
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, '[redacted]')
        return value
    return value


def _clean_usage(usage):
    if not isinstance(usage, dict):
        return None
    return {k: v for k, v in usage.items() if isinstance(v, int) and 'thought' not in k.lower() and 'thinking' not in k.lower()}


def sanitize_receipt(raw, secrets=()):
    """Whitelist receipt fields; drop thought/body content; scrub secret strings from every value."""
    receipt = {}
    for key in RECEIPT_FIELDS:
        value = raw.get(key)
        if key == 'token_usage':
            value = _clean_usage(value)
        elif key == 'passed':
            value = bool(value)
        else:
            value = _scrub(value, secrets)
        receipt[key] = value
    receipt['reason'] = (receipt['reason'] or '')[:200]
    for key in OPTIONAL_FIELDS:
        if raw.get(key) is not None:
            receipt[key] = (_scrub(str(raw[key]), secrets))[:200]
    # video.py video_enabled() reads exactly this top-level key from P3.json / P4.json.
    receipt['pass'] = receipt['passed']
    return receipt


def sdk_version():
    try:
        from importlib.metadata import version
        return version('google-genai')
    except Exception:
        return 'unknown'


class ProbeClient:
    """Injectable provider interface. run() returns a dict:
    http_status, error_code, model, usage, interaction_id, passed, reason, calls (provider calls made)."""

    def run(self, probe_id, model):
        raise NotImplementedError


class ProbeNotWired(Exception):
    pass


def make_synthetic_clip(seconds=5):
    """Deterministic 5 s H.264 mp4 built in-process (ffmpeg lavfi testsrc, no input files, nothing committed).
    Falls back to the smallest valid container (ftyp + moov/mvhd with the right duration, no media track)
    when ffmpeg is unavailable; the parser accepts it but a provider may reject it."""
    import shutil
    import struct
    import subprocess
    import tempfile
    ffmpeg = shutil.which('ffmpeg')
    if ffmpeg:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'clip.mp4'
            cmd = [ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', f'testsrc=duration={seconds}:size=320x240:rate=5',
                   '-pix_fmt', 'yuv420p', '-c:v', 'libx264', '-bitexact', '-movflags', '+faststart', '-y', str(out)]
            try:
                subprocess.run(cmd, check=True, timeout=60, capture_output=True)
                return out.read_bytes()
            except Exception:
                pass
    ftyp = struct.pack('>I4s4sI4s4s', 20, b'ftyp', b'isom', 0, b'isom', b'mp41')
    mvhd = struct.pack('>I4sBxxxIIII', 108, b'mvhd', 0, 0, 0, 1000, seconds * 1000) + bytes(108 - 28)
    return ftyp + struct.pack('>I4s', 8 + len(mvhd), b'moov') + mvhd


def _usage_ints(usage):
    return {k: v for k, v in (usage or {}).items() if isinstance(v, int)} or None


def _grounding_raw(result, pass_check):
    """Receipt fields from a GroundingResult; pass requires a live completed provider receipt."""
    live = getattr(result, 'provenance', None) == 'live' and bool(getattr(result, 'provider_interaction_id', None))
    ok = result.status == 'completed' and live and result.proposal is not None and pass_check(result.proposal)
    errors = list(getattr(result, 'errors', None) or [])
    return {'http_status': 200 if live else None, 'model': getattr(result, 'provider_model', None),
            'usage': _usage_ints(getattr(result, 'token_usage', None)),
            'interaction_id': getattr(result, 'provider_interaction_id', None), 'passed': ok, 'calls': 1,
            'error_code': errors[0] if errors else None,
            'reason': 'ok' if ok else f'status={result.status} provenance={result.provenance}'}


def _allowlisted(proposal):
    return (proposal.status.value if hasattr(proposal.status, 'value') else proposal.status) == 'matched' and \
        f'{getattr(proposal.selected_entity_type, "value", proposal.selected_entity_type)}:{proposal.selected_entity_id}' in (
            'portal:P1', 'portal:P2', 'boundary:B2')


def _new_context(directory):
    from backend.app.state.manager import StateManager
    from backend.app.state.store import SQLiteStore
    return StateManager(SQLiteStore(str(Path(directory) / 'probe.sqlite3')))


class LiveExecutors:
    """P2-P6 executors that call the existing backend adapters. Every dependency is injectable for offline tests."""

    def __init__(self, api_key, grounding_factory=None, managed_factory=None, ground_video_fn=None, ensure_agent_fn=None,
                 clip_fn=make_synthetic_clip, image_fn=None):
        self.api_key = api_key
        self.grounding_factory = grounding_factory or self._grounding
        self.managed_factory = managed_factory or self._managed
        self.ground_video_fn = ground_video_fn
        self.ensure_agent_fn = ensure_agent_fn
        self.clip_fn = clip_fn
        self.image_fn = image_fn
        self.meter = None

    def attach_meter(self, counter):
        self.meter = counter

    def _metered(self, adapter):
        """Route the adapter's provider client through the call counter (no-op when unmetered)."""
        if self.meter is not None and getattr(adapter, 'client', None) is not None:
            adapter.client = meter_client(adapter.client, self.meter)
        return adapter

    def _grounding(self):
        from backend.app.ai.grounding.adapter import GroundingAdapter
        return GroundingAdapter(self.api_key)

    def _managed(self, service, **kwargs):
        from backend.app.ai.managed.adapter import ManagedAgentAdapter
        return ManagedAgentAdapter(service, self.api_key, **kwargs)

    def run(self, probe_id):
        method = getattr(self, f'_{probe_id.lower()}', None)
        if method is None:
            raise ProbeNotWired(probe_id)
        import asyncio
        import tempfile
        with tempfile.TemporaryDirectory(prefix='spatialtwin-probe-') as tmp:
            manager = _new_context(tmp)
            try:
                return asyncio.run(method(manager, Path(tmp)))
            except Exception as exc:
                return {'error_code': type(exc).__name__, 'passed': False, 'reason': 'executor_exception', 'calls': 1}

    async def _p2(self, manager, tmp):
        import base64
        from backend.app.contracts import Capture
        if self.image_fn:
            data, dimensions = self.image_fn()
        else:
            from tools.verify_argon import image_bytes
            data, dimensions = image_bytes(None)
        capture = Capture(capture_id=hash_identifier(os.urandom(8).hex()), timestamp_iso=datetime.now(timezone.utc).isoformat(),
                          source_kind='annotated_plan', dimensions=dimensions,
                          source_geometry_revision=manager.context.geometry_revision,
                          expected_scenario_revision=manager.context.scenario_revision,
                          expected_physical_revision=manager.context.physical_revision, source_context=manager.context,
                          image_base64=base64.b64encode(data).decode(), image_sha256=hashlib.sha256(data).hexdigest())
        adapter = self._metered(self.grounding_factory())
        try:
            result = await adapter.interpret_capture(capture, manager.context, deadline_seconds=30)
        finally:
            await adapter.aclose()
        return _grounding_raw(result, _allowlisted)

    async def _video(self, manager, tmp, mode):
        ground_video = self.ground_video_fn
        if ground_video is None:
            from backend.app.ai.grounding.video import ground_video
        # video_enabled() gates on a pass receipt; give the probe a private bootstrap receipt so it does not
        # depend on (or fabricate) the real runtime/probes file. The real P3/P4 receipt is written by the runner.
        from backend.app.ai.grounding.video import VIDEO_PROBE_FILES
        gate = tmp / 'gate'
        gate.mkdir()
        (gate / VIDEO_PROBE_FILES[mode]).write_text(json.dumps({'pass': True}))
        adapter = self._metered(self.grounding_factory())
        try:
            result = await ground_video(self.clip_fn(), 'video/mp4', manager.context, mode, adapter=adapter,
                                        captured_at_iso=datetime.now(timezone.utc).isoformat(),
                                        deadline_seconds=45, receipt_path=gate)
        finally:
            await adapter.aclose()
        raw = _grounding_raw(result, lambda proposal: True)
        raw['mode'] = mode
        return raw

    async def _p3(self, manager, tmp):
        return await self._video(manager, tmp, 'static')

    async def _p4(self, manager, tmp):
        return await self._video(manager, tmp, 'agentic')

    @staticmethod
    def _managed_raw(result, calls, **extra):
        completed = str(getattr(result.status, 'value', result.status)).lower() == 'completed'
        live = result.provenance == 'live' and bool(result.provider_interaction_id)
        fell_back = 'environment_fallback' in json.dumps(result.provider_progress, default=str) or any(
            error == 'network_deny_rejected' for error in (result.errors or []))
        # 'agent_definition' means the interaction echoed no model and the verified saved-agent model was used.
        from_definition = any(e.get('phase') == 'model_from_agent_definition' for e in (result.provider_progress or []))
        return {'http_status': 200 if live else None, 'model': result.provider_model, 'usage': _usage_ints(result.token_usage),
                'model_source': 'agent_definition' if from_definition else 'echo', 'interaction_id': result.provider_interaction_id,
                'calls': calls, 'error_code': result.errors[0] if result.errors else None,
                'completed': completed and live, 'fell_back': fell_back}

    async def _p5(self, manager, tmp):
        from backend.app.ai.managed import agent_registry
        ensure = self.ensure_agent_fn or agent_registry.ensure_agent
        adapter = self._metered(self.managed_factory(manager_service(manager)))
        calls, result, ref, deletion = 0, None, None, 'not_attempted'
        try:
            calls += 1
            ref = await ensure(adapter.client, enabled=True, cache_path=str(tmp / 'agent_ref.json'))
            created = bool(ref and ref.created)
            if created:
                adapter.bind_agent(ref)
                calls += 1
                result = await adapter.investigate_scenario(manager.context, deadline_seconds=240, mode='live')
        finally:
            if ref is not None and ref.created:
                calls += 1
                try:
                    await adapter.client.aio.agents.delete(id=ref.agent_id, timeout=30)
                    deletion = 'deleted'
                except Exception as exc:
                    deletion = f'delete_failed:{type(exc).__name__}'
            await adapter.aclose()
        if result is None:
            return {'passed': False, 'calls': calls, 'reason': 'agent_not_created' if not (ref and ref.created) else 'run_missing',
                    'deletion_result': deletion}
        raw = self._managed_raw(result, calls)
        ok = raw['completed'] and deletion == 'deleted'
        raw.update(passed=ok, deletion_result=deletion,
                   reason='ok' if ok else f'created=True run_completed={raw["completed"]} deletion={deletion}')
        return raw

    async def _p6(self, manager, tmp):
        from backend.app.ai.managed.agent_registry import build_environment
        adapter = self._metered(self.managed_factory(manager_service(manager), environment=build_environment(True)))
        try:
            result = await adapter.investigate_scenario(manager.context, deadline_seconds=240, mode='live')
        finally:
            await adapter.aclose()
        raw = self._managed_raw(result, 1)
        ok = raw['completed'] and not raw['fell_back']
        raw.update(passed=ok, reason='ok' if ok else 'network_deny_rejected_or_incomplete')
        if raw['fell_back']:
            raw['fallback_note'] = 'provider rejected the network-deny environment; the run failed (no downgrade)'
        return raw

    # --- P8-P11: agent team capabilities (opt-in; code reviewed offline, run live only by the lead) -------------
    # Each uses blocking (non-background) interactions so a probe costs one metered call per turn, not a poll loop.

    def _team_client(self, manager):
        adapter = self._metered(self.managed_factory(manager_service(manager)))
        return adapter, adapter.client

    @staticmethod
    def _sandbox(environment_extra=None, network='disabled'):
        from backend.app.ai.managed.door_agent import DoorToolbox
        from backend.app.ai.managed.robustness import ScenarioEvaluator
        from backend.app.ai.managed.sandbox import input_documents, sandbox_environment
        from backend.app.hazard.door_planner import plan_doors
        from backend.app.venues.model import load_building_v2
        from backend.app.venues.schemas import DoorPlanRequest
        venue = load_building_v2()
        request = DoorPlanRequest(hazards=[{'id': 'h0', 'type': 'FIRE', 'position': {'x': 20, 'y': 4},
                                            'source': 'simulated'}])
        evaluator = ScenarioEvaluator(venue, request)
        documents = input_documents(venue, evaluator.base.horizon, evaluator.base.hazards,
                                    DoorToolbox(plan_doors(venue, request), evaluator).checked_plan())
        environment = sandbox_environment(documents, network_disabled=network == 'disabled')
        if network not in ('disabled', None):
            environment['network'] = network
        environment.update(environment_extra or {})
        return environment

    @staticmethod
    def _steps(interaction, kind):
        out = []
        for step in getattr(interaction, 'steps', None) or []:
            if getattr(step, 'type', None) == kind:
                out.append(step)
        return out

    @classmethod
    def _code_output(cls, interaction):
        return '\n'.join(str(getattr(step, 'result', '') or '') for step in cls._steps(interaction, 'code_execution_result'))

    @staticmethod
    def _interaction_raw(interaction, calls, **extra):
        from backend.app.ai.managed.adapter import ManagedAgentAdapter
        usage = ManagedAgentAdapter._usage(interaction) if interaction is not None else None
        return {'http_status': 200 if interaction is not None else None,
                'model': getattr(interaction, 'model', None) if interaction is not None else None,
                'usage': usage, 'interaction_id': getattr(interaction, 'id', None) if interaction is not None else None,
                'calls': calls, **extra}

    async def _agent_turn(self, client, input_text, environment, *, tools=None, previous=None, stream=False):
        from backend.app.ai.managed.adapter import AGENT, MODEL
        kwargs = dict(agent=AGENT, agent_config={'type': 'antigravity', 'model': MODEL, 'max_total_tokens': 20000},
                      environment=environment, input=input_text, tools=tools or [{'type': 'code_execution'}],
                      timeout=180)
        if previous:
            kwargs['previous_interaction_id'] = previous
        if stream:
            kwargs.update(stream=True, background=True, store=True)
        return await client.aio.interactions.create(**kwargs)

    async def _p8(self, manager, tmp):
        """Rung 1 + 4 of the ladder: does the sandbox import networkx, and does the kit sweep run either way?"""
        adapter, client = self._team_client(manager)
        try:
            interaction = await self._agent_turn(client, (
                "Use code execution to run exactly these two commands and nothing else, then stop:\n"
                "python3 -c \"import importlib.util as u; print('NX', bool(u.find_spec('networkx')))\"\n"
                "cd /workspace/kit && python3 -m spatialtwin_kit.sweep --only-single"), self._sandbox())
        finally:
            await adapter.aclose()
        output = self._code_output(interaction)
        has_nx = 'NX True' in output
        engine = 'exact' if 'exact copy of the local solver' in output else 'estimate' if 'sandbox estimate' in output else None
        ok = getattr(interaction, 'status', None) == 'completed' and engine is not None
        return self._interaction_raw(interaction, 1, passed=ok, mode=engine or 'failed',
                                     detail=f'networkx_importable={has_nx} engine={engine}',
                                     reason='ok' if ok else 'sweep_output_missing')

    async def _p8b(self, manager, tmp):
        """Rung 2: upload the venv's pure-Python networkx package as a zip and zipimport it in the same sandbox."""
        import io
        import zipfile
        import networkx
        package = Path(networkx.__file__).parent
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in package.rglob('*.py'):
                if 'tests' not in path.parts:
                    archive.write(path, Path('networkx') / path.relative_to(package))
        adapter, client = self._team_client(manager)
        calls = 0
        try:
            calls += 1
            first = await self._agent_turn(client, "Use code execution to run: ls /workspace/kit", self._sandbox())
            environment_id = getattr(first, 'environment_id', None)
            buffer.seek(0)
            calls += 1
            await client.aio.environments.files.upload(environment=environment_id, path='workspace/wheels/networkx.zip',
                                                       file=buffer, mime_type='application/zip', overwrite=True)
            calls += 1
            second = await self._agent_turn(client, (
                "Use code execution to run exactly: cd /workspace/kit && PYTHONPATH=/workspace/wheels/networkx.zip "
                "python3 -m spatialtwin_kit.sweep --only-single"), environment_id, previous=getattr(first, 'id', None))
        finally:
            await adapter.aclose()
        ok = 'exact copy of the local solver' in self._code_output(second)
        return self._interaction_raw(second, calls, passed=ok, mode='exact' if ok else 'failed',
                                     detail=f'zip_bytes={buffer.getbuffer().nbytes}',
                                     reason='ok' if ok else 'zipimport_failed')

    async def _p8c(self, manager, tmp):
        """Rung 3: pip install with a PyPI-only allowlist, then reuse the environment with the network disabled."""
        adapter, client = self._team_client(manager)
        allow = {'allowlist': [{'domain': 'pypi.org'}, {'domain': 'files.pythonhosted.org'}]}
        try:
            first = await self._agent_turn(client, "Use code execution to run exactly: pip install networkx==3.4.2",
                                           self._sandbox(network=allow))
            environment_id = getattr(first, 'environment_id', None)
            second = await self._agent_turn(client, (
                "Use code execution to run exactly: cd /workspace/kit && python3 -m spatialtwin_kit.sweep --only-single"),
                {'type': 'remote', 'environment_id': environment_id, 'network': 'disabled'},
                previous=getattr(first, 'id', None))
        finally:
            await adapter.aclose()
        ok = 'exact copy of the local solver' in self._code_output(second)
        return self._interaction_raw(second, 2, passed=ok, mode='exact' if ok else 'failed',
                                     reason='ok' if ok else 'reuse_network_disabled_failed')

    async def _p9(self, manager, tmp):
        """Shape only (event and step types, ids present, terminal status); never content."""
        adapter, client = self._team_client(manager)
        shapes, statuses, ids, last = [], [], 0, None
        try:
            stream = await self._agent_turn(client, "Use code execution to run: python3 -c 'print(6*7)'",
                                            {'type': 'remote', 'network': 'disabled'}, stream=True)
            async for event in stream:
                kind = getattr(event, 'event_type', None)
                ids += 1 if getattr(event, 'event_id', None) else 0
                detail = getattr(getattr(event, 'step', None), 'type', None) or getattr(getattr(event, 'delta', None), 'type', None)
                shape = f'{kind}:{detail}' if detail else str(kind)
                if shape not in shapes:
                    shapes.append(shape)
                status = getattr(event, 'status', None) or getattr(getattr(event, 'interaction', None), 'status', None)
                if status:
                    statuses.append(status)
                    last = getattr(event, 'interaction_id', None) or getattr(getattr(event, 'interaction', None), 'id', None) or last
        finally:
            await adapter.aclose()
        ok = 'step.stop' in shapes and bool(statuses) and statuses[-1] == 'completed'
        return {'http_status': 200, 'model': None, 'usage': None, 'interaction_id': last, 'calls': 1, 'passed': ok,
                'mode': f'event_ids={ids}', 'detail': ' '.join(shapes)[:200],
                'reason': 'ok' if ok else f'last_status={statuses[-1] if statuses else None}'}

    async def _p10(self, manager, tmp):
        adapter, client = self._team_client(manager)
        try:
            interaction = await self._agent_turn(client, (
                "Use code execution to run exactly: echo probe > /workspace/inputs/probe.txt\n"
                "Then run: ls /workspace/inputs and stop."), self._sandbox())
        finally:
            await adapter.aclose()
        output = self._code_output(interaction)
        denied = 'Read-only' in output or 'Read-only' in str(getattr(interaction, 'output_text', '') or '')
        written = 'probe.txt' in output
        ok = denied and not written
        return self._interaction_raw(interaction, 1, passed=ok, detail=f'deny_seen={denied} file_written={written}',
                                     reason='ok' if ok else 'hook_deny_not_observed')

    async def _p11(self, manager, tmp):
        adapter, client = self._team_client(manager)
        calls, environment_id, deletion, second = 0, None, 'not_attempted', None
        try:
            calls += 1
            environment = await client.aio.environments.create(network='disabled', sources=[
                {'type': 'inline', 'target': 'workspace/inputs/marker.txt', 'content': 'spatialtwin'}])
            environment_id = getattr(environment, 'id', None)
            calls += 1
            first = await self._agent_turn(client, "Use code execution to run: cat /workspace/inputs/marker.txt > "
                                                   "/workspace/out_marker.txt", environment_id)
            calls += 1
            second = await self._agent_turn(client, "Use code execution to run: cat /workspace/out_marker.txt",
                                            environment_id, previous=getattr(first, 'id', None))
        finally:
            if environment_id:
                calls += 1
                try:
                    await client.aio.environments.delete(id=environment_id)
                    deletion = 'deleted'
                except Exception as exc:
                    deletion = f'delete_failed:{type(exc).__name__}'
            await adapter.aclose()
        ok = second is not None and 'spatialtwin' in self._code_output(second) and \
            getattr(second, 'environment_id', None) == environment_id
        return self._interaction_raw(second, calls, passed=ok, deletion_result=deletion,
                                     detail=f'environments_create={"ok" if environment_id else "failed"}',
                                     reason='ok' if ok else 'environment_reuse_failed')


def manager_service(manager):
    from backend.app.state.service import ScenarioService
    return ScenarioService(manager)


class GenaiProbeClient(ProbeClient):
    """Real client. P1/P1b call the Interactions API directly; P2-P6 delegate to the existing backend adapters."""

    def __init__(self, api_key, executors=None):
        from google import genai
        self.client = genai.Client(api_key=api_key)
        self.executors = executors or LiveExecutors(api_key)

    def attach_meter(self, counter):
        """Count real provider calls on every client this probe run uses."""
        self.client = meter_client(self.client, counter)
        if hasattr(self.executors, 'attach_meter'):
            self.executors.attach_meter(counter)

    def run(self, probe_id, model):
        if probe_id not in ('P1', 'P1b'):
            return self.executors.run(probe_id)
        try:
            interaction = self.client.interactions.create(model=model, input='Reply with the single word: ok', store=False)
        except Exception as exc:
            status = _error_status(exc)
            return {'http_status': status, 'error_code': type(exc).__name__, 'calls': 1, 'passed': False,
                    'reason': 'provider_error'}
        usage = getattr(interaction, 'usage', None)
        usage_dict = {k: getattr(usage, k) for k in ('total_input_tokens', 'total_output_tokens', 'total_tokens')
                      if isinstance(getattr(usage, k, None), int)} if usage else None
        echoed = getattr(interaction, 'model', None)
        ok = getattr(interaction, 'status', None) == 'completed' and echoed == model
        return {'http_status': 200, 'model': echoed, 'usage': usage_dict, 'interaction_id': getattr(interaction, 'id', None),
                'passed': ok, 'reason': 'ok' if ok else 'echoed_model_mismatch_or_incomplete', 'calls': 1}


def print_plan(out=print):
    out(f'Probe plan (hard cap {CALL_CAP} provider calls). No network without --live --confirm-spend.')
    for spec in PLAN:
        out(f'{spec.probe_id:4} max_calls={spec.max_calls} ~tokens={spec.token_budget:<6} {spec.purpose}')
    out(f'Total rough token budget: {sum(s.token_budget for s in PLAN)}')


def _existing_failure(directory, probe_id):
    path = directory / f'{probe_id}.json'
    if not path.exists():
        return False
    try:
        return not json.loads(path.read_text()).get('passed', False)
    except Exception:
        return True


def _existing_mode(directory, pid, mode):
    try:
        return json.loads((Path(directory) / f'{pid}.json').read_text()).get('mode') == mode
    except (OSError, ValueError):
        return False


def _existing_pass(directory, pid):
    path = Path(directory) / f'{pid}.json'
    try:
        return json.loads(path.read_text()).get('passed') is True
    except (OSError, ValueError):
        return False


def run_probes(client, directory=RECEIPT_DIR, secrets=(), overwrite_failures=False, cap=CALL_CAP, now=None, version=None,
               only=None):
    """Run in plan order. Returns summary dict; writes receipts and model_resolution.json.

    `only` limits which probes make calls. A prior passing P1/P1b receipt still counts as the
    managed-model resolution, so P5/P6 can run in a later selective pass without repeating P1.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    counter = CallCounter(cap)
    metered = hasattr(client, 'attach_meter')
    if metered:
        client.attach_meter(counter)
    outcomes = {pid: True for pid in ('P1', 'P1b') if _existing_pass(directory, pid)}
    if _existing_failure(directory, 'P1'):
        outcomes['P1'] = False
    summary = {'results': {}, 'skipped': {}, 'calls_used': 0, 'cap_reached': False}
    version = version or sdk_version()
    for spec in PLAN:
        pid = spec.probe_id
        if only is not None and pid not in only:
            summary['skipped'][pid] = 'not_selected'
            continue
        if pid == 'P1b' and outcomes.get('P1') is not False:
            # The fallback model is tried only after a recorded P1 failure, never when P1 was not tested.
            summary['skipped'][pid] = 'P1_passed' if outcomes.get('P1') else 'requires_recorded_P1_failure'
            continue
        if pid in EXCLUDED_PROBES:
            summary['skipped'][pid] = EXCLUDED_PROBES[pid]
            continue
        if pid in OPT_IN_PROBES and (only is None or pid not in only):
            summary['skipped'][pid] = 'opt_in_only'
            continue
        if pid in ('P8b', 'P8c') and not _existing_mode(directory, 'P8', 'estimate'):
            summary['skipped'][pid] = 'requires_P8_estimate'
            continue
        if (pid in ('P5', 'P6') or pid in OPT_IN_PROBES) and not (outcomes.get('P1') or outcomes.get('P1b')):
            summary['skipped'][pid] = 'requires_P1_or_P1b'
            continue
        if _existing_failure(directory, pid) and not overwrite_failures:
            summary['skipped'][pid] = 'existing_failure_receipt_kept'
            continue
        if not (counter.remaining >= 1 if metered else counter.can_afford(spec.max_calls)):
            summary['skipped'][pid] = 'call_cap_reached'
            summary['cap_reached'] = True
            continue
        mark, used_before = len(counter.events), counter.used
        try:
            raw = client.run(pid, spec.model)
        except ProbeNotWired:
            summary['skipped'][pid] = 'executor_not_wired'
            continue
        except Exception as exc:
            raw = {'error_code': type(exc).__name__, 'passed': False, 'reason': 'client_exception', 'calls': 1}
        if metered:
            # Real calls were charged by the metered client; the executor's own estimate is ignored.
            observed = counter.http_status_since(mark)
            if counter.used > used_before:
                raw = {**raw, 'http_status': observed}
        else:
            counter.charge(int(raw.get('calls', 1)))
        stamp = (now or datetime.now(timezone.utc)).isoformat()
        receipt = sanitize_receipt({
            'probe_id': pid, 'timestamp_utc': stamp, 'sdk_version': version, 'requested_model': spec.model,
            'echoed_model': raw.get('model'), 'http_status_class': status_class(raw.get('http_status')),
            'error_code': raw.get('error_code'), 'token_usage': raw.get('usage'),
            'interaction_id_hash': hash_identifier(raw.get('interaction_id')),
            'passed': raw.get('passed'), 'reason': raw.get('reason') or '', 'mode': raw.get('mode'),
            'deletion_result': raw.get('deletion_result'), 'fallback_note': raw.get('fallback_note'),
            'detail': raw.get('detail')}, secrets)
        (directory / f'{pid}.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
        outcomes[pid] = receipt['passed']
        summary['results'][pid] = receipt['passed']
    resolved = PRIMARY_MODEL if outcomes.get('P1') else FALLBACK_MODEL if outcomes.get('P1b') else None
    (directory / 'model_resolution.json').write_text(json.dumps({
        'resolved_managed_model': resolved, 'managed_available': resolved is not None,
        'p1_passed': outcomes.get('P1'), 'p1b_passed': outcomes.get('P1b')}, indent=2, sort_keys=True) + '\n')
    summary['calls_used'] = counter.used
    summary['resolved_managed_model'] = resolved
    return summary


def main(argv=None, client_factory=None, directory=RECEIPT_DIR):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--confirm-spend', action='store_true')
    parser.add_argument('--overwrite-failures', action='store_true', help='allow replacing existing failure receipts')
    parser.add_argument('--only', default='', help='comma-separated probe ids to run, e.g. P2,P3,P4,P5,P6')
    args = parser.parse_args(argv)
    only = {p.strip() for p in args.only.split(',') if p.strip()} or None
    print_plan()
    if not args.live:
        print('Plan only (no --live). No calls made.')
        return 0
    if not args.confirm_spend:
        print('Refusing: --live requires --confirm-spend. No calls made.')
        return 0
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not key:
        print('GEMINI_API_KEY not configured. No calls made.')
        return 1
    client = client_factory(key) if client_factory else GenaiProbeClient(key)
    summary = run_probes(client, directory, secrets=(key,), overwrite_failures=args.overwrite_failures, only=only)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
