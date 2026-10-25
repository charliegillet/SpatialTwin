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
    assert summary['cap_reached'] and summary['skipped']['P7'] == 'call_cap_reached'
    assert 'P7' not in fake.log


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
