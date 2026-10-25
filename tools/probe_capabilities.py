"""Opt-in live capability probes P1..P7 with sanitized receipts.

Run from repository root: .venv/bin/python -m tools.probe_capabilities            (prints the plan, no network)
                          .venv/bin/python -m tools.probe_capabilities --live --confirm-spend
GEMINI_API_KEY is read from the environment and never printed or written.
"""
import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

CALL_CAP = 8
PRIMARY_MODEL = 'gemini-4-argon'
FALLBACK_MODEL = 'gemini-3.8-flash'
RECEIPT_DIR = Path('runtime/probes')
RECEIPT_FIELDS = ('probe_id', 'timestamp_utc', 'sdk_version', 'requested_model', 'echoed_model', 'http_status_class',
                  'error_code', 'token_usage', 'interaction_id_hash', 'passed', 'reason')


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
)
SPECS = {spec.probe_id: spec for spec in PLAN}


class CallCounter:
    """Pure hard cap on provider calls."""

    def __init__(self, cap=CALL_CAP):
        self.cap = cap
        self.used = 0

    @property
    def remaining(self):
        return self.cap - self.used

    def can_afford(self, calls):
        return self.used + calls <= self.cap

    def charge(self, calls):
        self.used += max(0, calls)


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


class GenaiProbeClient(ProbeClient):
    """Real client. Only P1/P1b are wired; other probes need integration code that lands in WP-F."""

    def __init__(self, api_key):
        from google import genai
        self.client = genai.Client(api_key=api_key)

    def run(self, probe_id, model):
        if probe_id not in ('P1', 'P1b'):
            raise ProbeNotWired(probe_id)
        try:
            interaction = self.client.interactions.create(model=model, input='Reply with the single word: ok', store=False)
        except Exception as exc:
            status = getattr(exc, 'code', None) or getattr(exc, 'status_code', None)
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


def run_probes(client, directory=RECEIPT_DIR, secrets=(), overwrite_failures=False, cap=CALL_CAP, now=None, version=None):
    """Run in plan order. Returns summary dict; writes receipts and model_resolution.json."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    counter = CallCounter(cap)
    outcomes = {}
    summary = {'results': {}, 'skipped': {}, 'calls_used': 0, 'cap_reached': False}
    version = version or sdk_version()
    for spec in PLAN:
        pid = spec.probe_id
        if pid == 'P1b' and outcomes.get('P1'):
            summary['skipped'][pid] = 'P1_passed'
            continue
        if pid in ('P5', 'P6') and not (outcomes.get('P1') or outcomes.get('P1b')):
            summary['skipped'][pid] = 'requires_P1_or_P1b'
            continue
        if _existing_failure(directory, pid) and not overwrite_failures:
            summary['skipped'][pid] = 'existing_failure_receipt_kept'
            continue
        if not counter.can_afford(spec.max_calls):
            summary['skipped'][pid] = 'call_cap_reached'
            summary['cap_reached'] = True
            continue
        try:
            raw = client.run(pid, spec.model)
        except ProbeNotWired:
            summary['skipped'][pid] = 'executor_not_wired'
            continue
        except Exception as exc:
            raw = {'error_code': type(exc).__name__, 'passed': False, 'reason': 'client_exception', 'calls': 1}
        counter.charge(int(raw.get('calls', 1)))
        stamp = (now or datetime.now(timezone.utc)).isoformat()
        receipt = sanitize_receipt({
            'probe_id': pid, 'timestamp_utc': stamp, 'sdk_version': version, 'requested_model': spec.model,
            'echoed_model': raw.get('model'), 'http_status_class': status_class(raw.get('http_status')),
            'error_code': raw.get('error_code'), 'token_usage': raw.get('usage'),
            'interaction_id_hash': hash_identifier(raw.get('interaction_id')),
            'passed': raw.get('passed'), 'reason': raw.get('reason') or ''}, secrets)
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
    args = parser.parse_args(argv)
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
    summary = run_probes(client, directory, secrets=(key,), overwrite_failures=args.overwrite_failures)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
