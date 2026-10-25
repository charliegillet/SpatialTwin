"""Preserved offline SpatialTwin AI audit probes, 24 October 2026.

Run from the repository root:
  PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /tmp/spatialtwin-ai-audit-20261024/offline_ai_probe.py

No real provider, credentials, StateManager/SQLite instance, device or serial use.
All socket connections fail closed. All HTTP sends are intercepted. Only an
explicit, non-secret placeholder is passed to the real SDK for serialization.
This combines the individual probes already executed during the audit.
"""

import asyncio
import importlib.metadata
import inspect
import json
import socket
from types import SimpleNamespace as NS


def blocked(*args, **kwargs):
    raise RuntimeError("Network disabled for offline audit")


socket.create_connection = blocked
socket.socket.connect = blocked

import httpx
from google import genai
from google.genai._gaos.types.interactions import AntigravityAgentConfig
from backend.app.ai.managed.adapter import ManagedAgentAdapter
from backend.app.ai.grounding.adapter import GroundingAdapter
from backend.app.contracts import Capture, RunContext


requests = []


def fake_send(self, request, *args, **kwargs):
    body = json.loads(request.content)
    requests.append(body)
    return httpx.Response(
        200,
        json={
            "id": "offline-interaction",
            "status": "completed",
            "model": body.get("model", "gemini-4-argon"),
            "steps": [{"type": "model_output", "content": [{"type": "text", "text": "{}"}]}],
            "usage": {"total_tokens": 6},
            "environment_id": "offline-env",
        },
        request=request,
    )


httpx.Client.send = fake_send
client = genai.Client(api_key="offline-audit-placeholder")
print("SDK_VERSION=", importlib.metadata.version("google-genai"))
print("SDK_CREATE_SIGNATURE=", inspect.signature(client.interactions.create))
result = client.interactions.create(
    model="gemini-4-argon",
    input=[
        {"type": "text", "text": "Offline serialization audit"},
        {"type": "image", "data": "AA==", "mime_type": "image/jpeg"},
    ],
    generation_config={"thinking_level": "low"},
    response_format={"type": "text", "mime_type": "application/json"},
)
print("DIRECT_BODY=", json.dumps(requests[-1], sort_keys=True))
print("OUTPUT_TEXT=", result.output_text)
print("USAGE_TYPE=", type(result.usage).__name__)
print("USAGE_GET_SUPPORTED=", hasattr(result.usage, "get"))
try:
    result.usage.get("total_tokens", 0)
except Exception as error:
    print("PROJECT_USAGE_EXPRESSION_ERROR=", type(error).__name__, str(error))
client.interactions.create(
    agent="antigravity-preview-09-2026",
    agent_config={"type": "antigravity", "model": "gemini-4-argon", "max_total_tokens": 20000},
    environment="remote",
    input=[{"type": "text", "text": "Offline serialization audit"}],
    tools=[],
)
print("MANAGED_BODY=", json.dumps(requests[-1], sort_keys=True))
print("AGENT_CONFIG_SERIALIZED=", AntigravityAgentConfig(max_total_tokens=20000, model="gemini-4-argon").model_dump_json(by_alias=True))
print("MOCKED_HTTP_REQUEST_COUNT=", len(requests))

context = RunContext(geometry_revision="offline-illustrative", scenario_revision=1, physical_revision=1)


class Service:
    def __init__(self):
        self.executions = 0

    def get_reviewed_context(self, current):
        self.executions += 1
        return {"context": current.model_dump()}


class FakeChain:
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0

    def create(self, **kwargs):
        response = self.responses[min(self.calls, len(self.responses) - 1)]
        self.calls += 1
        return response


def response(status, steps=None):
    return NS(id="offline-id", environment_id="offline-env", status=status, steps=steps or [], output_text="Offline fake response", usage={})


def adapter(responses):
    value = ManagedAgentAdapter.__new__(ManagedAgentAdapter)
    value.scenario_service = Service()
    value.client = NS(interactions=FakeChain(responses))
    return value


async def run_adapter_probes():
    duplicate = NS(type="function_call", id="same-provider-call", name="get_reviewed_scenario", arguments={})
    value = adapter([response("requires_action", [duplicate])])
    result = await value._run_live_antigravity_loop(context, "offline-duplicate", deadline_seconds=0)
    print("DUPLICATE_AND_ZERO_DEADLINE=", json.dumps({"tool_executions": value.scenario_service.executions, "ledger_ids": [entry.call_id for entry in result.tool_ledger], "result_status": result.status.value, "recommendation": result.recommended_alternative.value, "provider_calls": value.client.interactions.calls}))

    steps = [NS(type="function_call", id=f"call-{index}", name="get_reviewed_scenario", arguments={}) for index in range(6)]
    value = adapter([response("requires_action", steps), response("completed")])
    result = await value._run_live_antigravity_loop(context, "offline-batch", deadline_seconds=0)
    print("ONE_TURN_CALL_CAP=", json.dumps({"tool_executions": value.scenario_service.executions, "result_status": result.status.value}))

    for status in ["failed", "cancelled", "in_progress", "incomplete"]:
        value = adapter([response(status)])
        result = await value._run_live_antigravity_loop(context, "offline-status", deadline_seconds=0)
        print("LIFECYCLE=", json.dumps({"provider_status": status, "reported_status": result.status.value, "recommendation": result.recommended_alternative.value, "errors": result.errors}))

    grounding = GroundingAdapter.__new__(GroundingAdapter)
    grounding.client = NS(interactions=FakeChain([NS(output_text="not JSON", status="completed")]))
    capture = Capture(capture_id="offline-capture", timestamp_iso="2026-10-24T00:00:00Z", source_kind="tabletop_camera", source_geometry_revision="offline-illustrative", expected_scenario_revision=1, expected_physical_revision=1, image_base64="AA==")
    proposal, provenance = await grounding.interpret_capture(capture, context)
    print("MALFORMED_GROUNDING=", json.dumps({"status": proposal.status.value, "target": proposal.selected_entity_id, "provenance": provenance, "evidence": proposal.evidence}))
    print("CONTEXT_PARAMETER_MISMATCH_ACCEPTED=", context.is_current(context.model_copy(update={"parameters_revision": "different-params", "solver_version": "different-solver"})))

    stale_context = RunContext(geometry_revision="offline", scenario_revision=1, physical_revision=1)
    stale_capture = Capture(capture_id="offline-cap", timestamp_iso="2026-10-24T00:00:00Z", source_kind="tabletop_camera", source_geometry_revision="older-geometry", expected_scenario_revision=0, expected_physical_revision=0, image_base64="AA==")
    content = {"status": "matched", "candidate_ids": ["portal:P1", "invented:D99"], "selected_entity_type": "portal", "selected_entity_id": "P1", "operation": "OPEN_ALL_EXITS", "evidence": "offline fake", "box_2d": [-15, 2000]}
    grounding.client = NS(interactions=FakeChain([NS(status="incomplete", output_text=json.dumps(content))]))
    proposal, provenance = await grounding.interpret_capture(stale_capture, stale_context)
    print("INCOMPLETE_STALE_GROUNDING=", json.dumps({"input_provider_status": "incomplete", "input_operation": "OPEN_ALL_EXITS", "stale_capture_geometry": stale_capture.source_geometry_revision, "proposal_geometry": proposal.source_context.geometry_revision, "output_operation": proposal.operation, "status": proposal.status.value, "provenance": provenance, "box_2d": proposal.box_2d, "candidate_ids": proposal.candidate_ids, "semantic_validation": proposal.validate_semantic_soundness()}))


asyncio.run(run_adapter_probes())
