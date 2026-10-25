"""Agent-team probes P8-P11: opt-in gating, the call meter on environments/files, and offline executor parsing.
Nothing here reaches a provider: fake clients stand in for google-genai."""
import json
from types import SimpleNamespace as NS

from tools import probe_capabilities as pc


class Fake(pc.ProbeClient):
    def __init__(self, modes=None):
        self.log, self.modes = [], modes or {}

    def run(self, probe_id, model):
        self.log.append(probe_id)
        return {'http_status': 200, 'passed': True, 'calls': 1, 'reason': 'ok', 'mode': self.modes.get(probe_id)}


def test_team_probes_are_opt_in_and_gated(tmp_path):
    fake = Fake()
    summary = pc.run_probes(fake, tmp_path)
    assert not set(fake.log) & pc.OPT_IN_PROBES
    assert all(summary['skipped'][p] == 'opt_in_only' for p in pc.OPT_IN_PROBES)
    # P8 needs a managed-model receipt first; P8b/P8c run only after P8 reported the estimator.
    fake = Fake({'P8': 'exact'})
    pc.run_probes(fake, tmp_path / 'a', only={'P1', 'P8', 'P8b'})
    assert fake.log == ['P1', 'P8']
    fake = Fake({'P8': 'estimate'})
    pc.run_probes(fake, tmp_path / 'b', only={'P1', 'P8'})
    later = Fake()
    summary = pc.run_probes(later, tmp_path / 'b', only={'P8b', 'P8c'})
    assert later.log == ['P8b', 'P8c']
    assert json.loads((tmp_path / 'b' / 'P8.json').read_text())['mode'] == 'estimate'
    nothing = Fake()
    assert pc.run_probes(nothing, tmp_path / 'c', only={'P9'})['skipped']['P9'] == 'requires_P1_or_P1b'


def test_meter_counts_environment_and_file_calls():
    counter = pc.CallCounter(3)

    class Resource:
        async def create(self, **kwargs):
            return NS(id='env')

        async def delete(self, **kwargs):
            return None

        async def upload(self, **kwargs):
            return NS(files=[])

    environments = Resource()
    environments.files = Resource()
    client = pc.meter_client(NS(aio=NS(environments=environments)), counter)
    import asyncio

    async def go():
        await client.aio.environments.create(network='disabled')
        await client.aio.environments.files.upload(path='x', file=b'')
        await client.aio.environments.create()
        try:
            await client.aio.environments.create()
        except pc.ProbeCapReached:
            pass
        await client.aio.environments.delete(id='env')  # cleanup is allowed past the cap
    asyncio.run(go())
    assert counter.used == 4 and [e['method'] for e in counter.events] == ['create', 'upload', 'create', 'delete']


class FakeInteractions:
    def __init__(self, results):
        self.results, self.calls = list(results), []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.results.pop(0)


def executors(interactions, environments=None):
    class Adapter:
        def __init__(self, service, **kwargs):
            self.client = NS(aio=NS(interactions=interactions, environments=environments))

        async def aclose(self):
            pass
    return pc.LiveExecutors('key', managed_factory=lambda service, **kw: Adapter(service, **kw))


def interaction(output, status='completed', environment_id='env-1'):
    return NS(id='v1_x', status=status, model='gemini-4-argon', environment_id=environment_id, output_text='',
              usage=NS(total_tokens=10, total_input_tokens=8, total_output_tokens=2),
              steps=[NS(type='code_execution_result', result=output)])


def test_p8_reports_engine_and_mounts_the_kit_network_disabled():
    fake = FakeInteractions([interaction('NX False\n{"engine_label": "sandbox estimate", ...}')])
    raw = executors(fake).run('P8')
    assert raw['passed'] and raw['mode'] == 'estimate' and raw['detail'] == 'networkx_importable=False engine=estimate'
    environment = fake.calls[0]['environment']
    assert environment['network'] == 'disabled'
    assert '.agents/hooks.json' in {s['target'] for s in environment['sources']}
    assert fake.calls[0]['tools'] == [{'type': 'code_execution'}] and 'background' not in fake.calls[0]


def test_p10_requires_the_deny_to_be_seen_and_no_file_written():
    denied = executors(FakeInteractions([interaction('Read-only: this command appears to write ...')])).run('P10')
    assert denied['passed'] and denied['detail'] == 'deny_seen=True file_written=False'
    written = executors(FakeInteractions([interaction('probe.txt\nvenue.json')])).run('P10')
    assert not written['passed'] and written['reason'] == 'hook_deny_not_observed'


def test_p11_reuses_the_created_environment_and_deletes_it():
    deleted = []

    class Environments:
        async def create(self, **kwargs):
            assert kwargs['network'] == 'disabled'
            return NS(id='env-9')

        async def delete(self, **kwargs):
            deleted.append(kwargs['id'])
    fake = FakeInteractions([interaction('', environment_id='env-9'), interaction('spatialtwin', environment_id='env-9')])
    raw = executors(fake, Environments()).run('P11')
    assert raw['passed'] and raw['deletion_result'] == 'deleted' and deleted == ['env-9']
    assert fake.calls[0]['environment'] == 'env-9' and fake.calls[1]['previous_interaction_id'] == 'v1_x'
