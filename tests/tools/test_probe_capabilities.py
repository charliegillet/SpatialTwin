import json
from tools import probe_capabilities as pc

KEY = 'AIzaSyFAKEKEY1234567890'


class Fake(pc.ProbeClient):
    def __init__(self, outcomes=None, calls=None):
        self.log, self.outcomes, self.calls = [], outcomes or {}, calls

    def run(self, probe_id, model):
        self.log.append(probe_id)
        passed = self.outcomes.get(probe_id, True)
        return {'http_status': 200 if passed else 500, 'model': model, 'usage': {'total_tokens': 5, 'thought_tokens': 9},
                'interaction_id': 'abc', 'passed': passed, 'reason': f'ok {KEY}' if passed else 'bad', 'calls': self.calls or pc.SPECS[probe_id].max_calls,
                'error_code': None if passed else 'ServerError'}


def factory_that_fails(key):
    raise AssertionError('client must not be built')


def test_no_live_prints_plan_zero_calls(tmp_path, capsys):
    assert pc.main([], client_factory=factory_that_fails, directory=tmp_path) == 0
    out = capsys.readouterr().out
    for pid in ('P1 ', 'P1b', 'P2', 'P3', 'P4', 'P5', 'P6', 'P7'):
        assert pid in out
    assert not list(tmp_path.iterdir())


def test_live_without_confirm_makes_no_calls(tmp_path, monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY', KEY)
    assert pc.main(['--live'], client_factory=factory_that_fails, directory=tmp_path) == 0
    assert not list(tmp_path.iterdir())


def test_call_cap_enforced(tmp_path):
    fake = Fake()
    summary = pc.run_probes(fake, tmp_path)
    assert summary['calls_used'] == 8
    assert 'P7' not in fake.log
    assert summary['skipped']['P7'] == 'excluded_by_call_cap'


def test_counter_pure():
    counter = pc.CallCounter(8)
    counter.charge(7)
    assert counter.can_afford(1) and not counter.can_afford(2)


def test_sanitizer_strips_key_and_thoughts():
    raw = {'probe_id': 'P1', 'reason': f'leak {KEY}', 'thought': 'secret reasoning', 'thoughts': ['x'],
           'token_usage': {'total_tokens': 3, 'thought_tokens': 4}, 'passed': True, 'response_body': 'BODY'}
    text = json.dumps(pc.sanitize_receipt(raw, [KEY]))
    assert KEY not in text and 'secret reasoning' not in text and 'BODY' not in text and 'thought' not in text


def test_p5_p6_skipped_when_p1_p1b_fail(tmp_path):
    fake = Fake({'P1': False, 'P1b': False})
    summary = pc.run_probes(fake, tmp_path)
    assert 'P5' not in fake.log and 'P6' not in fake.log
    assert summary['skipped']['P5'] == 'requires_P1_or_P1b'
    assert json.loads((tmp_path / 'model_resolution.json').read_text())['managed_available'] is False


def test_receipts_have_no_secret_and_failure_written(tmp_path):
    pc.run_probes(Fake({'P2': False}), tmp_path, secrets=(KEY,))
    failed = json.loads((tmp_path / 'P2.json').read_text())
    assert failed['passed'] is False and failed['error_code'] == 'ServerError' and failed['http_status_class'] == '5xx'
    for path in tmp_path.glob('*.json'):
        assert KEY not in path.read_text()
    assert json.loads((tmp_path / 'P1.json').read_text())['interaction_id_hash'] != 'abc'


def test_existing_failure_not_overwritten(tmp_path):
    pc.run_probes(Fake({'P2': False}), tmp_path)
    before = (tmp_path / 'P2.json').read_text()
    fake = Fake()
    summary = pc.run_probes(fake, tmp_path)
    assert 'P2' not in fake.log and summary['skipped']['P2'] == 'existing_failure_receipt_kept'
    assert (tmp_path / 'P2.json').read_text() == before


# ---- live executors P2-P6 with fake adapters ----
import asyncio
from types import SimpleNamespace as NS
from backend.app.ai.grounding import video as video_mod

GOOD_PROPOSAL = NS(status='matched', selected_entity_type='portal', selected_entity_id='P2')


def g_result(status='completed', provenance='live', proposal=GOOD_PROPOSAL, iid='int-1'):
    return NS(status=status, provenance=provenance, proposal=proposal, provider_interaction_id=iid, provider_model='gemini-4-argon',
              token_usage={'total_tokens': 7, 'total_thought_tokens': 3}, errors=[] if status == 'completed' else ['x'])


class FakeGrounding:
    def __init__(self, result):
        self.result, self.closed = result, False

    async def interpret_capture(self, capture, context, **kw):
        return self.result

    async def aclose(self):
        self.closed = True


def m_result(status='completed', provenance='live', progress=()):
    return NS(status=status, provenance=provenance, provider_interaction_id='m-1', provider_model='gemini-4-argon',
              token_usage={'total_tokens': 9}, errors=[], provider_progress=list(progress))


class FakeAgents:
    def __init__(self, fail=False):
        self.deleted, self.fail = [], fail

    async def delete(self, id, timeout=None):
        self.deleted.append(id)
        if self.fail:
            raise RuntimeError('boom')


class FakeManaged:
    def __init__(self, result=None, raises=False, agents=None):
        self.result, self.raises, self.agents = result, raises, agents or FakeAgents()
        self.client = NS(aio=NS(agents=self.agents))
        self.agent = None

    async def investigate_scenario(self, context, deadline_seconds=60, mode='live'):
        if self.raises:
            raise RuntimeError('run failed')
        return self.result

    async def aclose(self):
        pass


def ensure_ok(client, enabled=None, cache_path=None):
    async def go():
        return NS(agent_id='spatialtwin-evac-v1', created=True)
    return go()


def ensure_none(client, enabled=None, cache_path=None):
    async def go():
        return None
    return go()


def tiny_image():
    return b'\xff\xd8\xff\xd9', (1, 1)


def execs(**kw):
    kw.setdefault('image_fn', None)
    return pc.LiveExecutors('k', **kw)


def run_with_manager(ex, probe):
    return ex.run(probe)


def test_p2_pass_and_fail(monkeypatch):
    import tools.verify_argon as va
    monkeypatch.setattr(va, 'image_bytes', lambda path: __import__('PIL.Image', fromlist=['x']) and _jpeg())
    raw = execs(grounding_factory=lambda: FakeGrounding(g_result())).run('P2')
    assert raw['passed'] is True and raw['calls'] == 1
    assert execs(grounding_factory=lambda: FakeGrounding(g_result(provenance='fixture'))).run('P2')['passed'] is False
    assert execs(grounding_factory=lambda: FakeGrounding(g_result(proposal=NS(status='matched', selected_entity_type='portal', selected_entity_id='P9')))).run('P2')['passed'] is False
    assert execs(grounding_factory=lambda: FakeGrounding(g_result(status='failed', proposal=None))).run('P2')['passed'] is False


def _jpeg():
    import io
    from PIL import Image
    out = io.BytesIO()
    Image.new('RGB', (8, 8), 'white').save(out, format='JPEG')
    return out.getvalue(), (8, 8)


def test_video_probes_pass_fail_and_receipts_enable_video(tmp_path):
    seen = []

    async def fake_ground(clip, mime, context, mode, *, adapter, deadline_seconds, receipt_path):
        seen.append((mode, mime, video_mod.video_enabled(mode, receipt_path)))
        return g_result()

    ex = execs(grounding_factory=lambda: FakeGrounding(None), ground_video_fn=fake_ground, clip_fn=lambda: b'clip')
    p3, p4 = ex.run('P3'), ex.run('P4')
    assert p3['passed'] and p3['mode'] == 'static' and p4['passed'] and p4['mode'] == 'agentic'
    assert seen == [('static', 'video/mp4', True), ('agentic', 'video/mp4', True)]

    class Client(pc.ProbeClient):
        def run(self, probe_id, model):
            return {'P3': p3, 'P4': p4}.get(probe_id, {'passed': True, 'calls': 1})
    pc.run_probes(Client(), tmp_path)
    assert (tmp_path / 'P3.json').exists() and (tmp_path / 'P4.json').exists()
    assert video_mod.video_enabled('static', tmp_path) and video_mod.video_enabled('agentic', tmp_path)
    assert json.loads((tmp_path / 'P3.json').read_text())['mode'] == 'static'

    async def failing(*a, **k):
        return g_result(status='failed', proposal=None)
    bad = execs(grounding_factory=lambda: FakeGrounding(None), ground_video_fn=failing, clip_fn=lambda: b'c').run('P3')
    assert bad['passed'] is False


def test_p5_pass_deletes_and_failure_still_deletes():
    agents = FakeAgents()
    ex = execs(managed_factory=lambda svc, **k: FakeManaged(m_result(), agents=agents), ensure_agent_fn=ensure_ok)
    raw = ex.run('P5')
    assert raw['passed'] and raw['deletion_result'] == 'deleted' and raw['calls'] == 3 and agents.deleted == ['spatialtwin-evac-v1']

    agents = FakeAgents()
    ex = execs(managed_factory=lambda svc, **k: FakeManaged(raises=True, agents=agents), ensure_agent_fn=ensure_ok)
    raw = ex.run('P5')
    assert raw['passed'] is False and agents.deleted == ['spatialtwin-evac-v1']

    agents = FakeAgents(fail=True)
    ex = execs(managed_factory=lambda svc, **k: FakeManaged(m_result(), agents=agents), ensure_agent_fn=ensure_ok)
    raw = ex.run('P5')
    assert raw['passed'] is False and raw['deletion_result'].startswith('delete_failed')

    agents = FakeAgents()
    raw = execs(managed_factory=lambda svc, **k: FakeManaged(m_result(), agents=agents), ensure_agent_fn=ensure_none).run('P5')
    assert raw['passed'] is False and agents.deleted == [] and raw['calls'] == 1


def test_p6_pass_fail_and_fallback():
    envs = []

    def factory(result):
        def make(svc, **k):
            envs.append(k.get('environment'))
            return FakeManaged(result)
        return make
    assert execs(managed_factory=factory(m_result())).run('P6')['passed'] is True
    assert envs[-1] == {'type': 'remote', 'network': 'disabled'}
    fb = execs(managed_factory=factory(m_result(progress=[{'phase': 'environment_fallback'}]))).run('P6')
    assert fb['passed'] is False and fb['fallback_note']
    assert execs(managed_factory=factory(m_result(status='failed'))).run('P6')['passed'] is False


def test_p7_not_wired_and_excluded(tmp_path):
    try:
        execs().run('P7')
        assert False
    except pc.ProbeNotWired:
        pass
    fake = Fake()
    summary = pc.run_probes(fake, tmp_path)
    assert summary['skipped']['P7'] == 'excluded_by_call_cap' and 'P7' not in fake.log
    assert not (tmp_path / 'P7.json').exists()


def test_receipt_has_pass_key_no_secret_or_thought(tmp_path):
    class C(pc.ProbeClient):
        def run(self, probe_id, model):
            return {'passed': True, 'calls': 1, 'reason': f'x {KEY}', 'usage': {'total_thought_tokens': 3, 'total_tokens': 4},
                    'deletion_result': f'deleted {KEY}', 'thought': 'private'}
    pc.run_probes(C(), tmp_path, secrets=(KEY,))
    for path in tmp_path.glob('P*.json'):
        text = path.read_text()
        assert KEY not in text and 'private' not in text and 'thought' not in text
        assert json.loads(text)['pass'] is True


def test_synthetic_clip_parses_5_seconds():
    clip = pc.make_synthetic_clip()
    assert abs(video_mod.clip_duration_seconds(clip, 'video/mp4') - 5.0) < 0.3
