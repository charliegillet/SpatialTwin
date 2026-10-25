"""Offline production-path tests against the real pinned SDK and mocked HTTP.

No credentials are read. Both HTTP clients and socket connections fail closed.
"""

import asyncio
import base64
import copy
import hashlib
import io
import json
import socket
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from PIL import Image

from backend.app.ai.grounding.adapter import GroundingAdapter, MAX_IMAGE_BYTES
from backend.app.contracts import Capture, GroundingStatus, RunContext


VALID_OUTPUT = {
    "status": "matched",
    "candidate_ids": ["portal:P2"],
    "selected_entity_type": "portal",
    "selected_entity_id": "P2",
    "operation": "SET_UNAVAILABLE",
    "evidence": "Circular token overlaps the printed T_P2 pad.",
    "box_2d": [200, 600, 320, 720],
}


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Real network is disabled in grounding tests")
    async def blocked_async(*args, **kwargs):
        raise AssertionError("HTTP response must be explicitly mocked")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(httpx.Client, "send", blocked)
    monkeypatch.setattr(httpx.AsyncClient, "send", blocked_async)


@pytest.fixture
def context():
    return RunContext(geometry_revision="illustrative-test", scenario_revision=4, physical_revision=3)


@pytest.fixture
def capture(context):
    output = io.BytesIO()
    Image.new("RGB", (12, 8), (120, 110, 100)).save(output, format="JPEG")
    data = output.getvalue()
    return Capture(
        capture_id="offline-capture",
        timestamp_iso=datetime.now(timezone.utc).isoformat(),
        source_kind="tabletop_camera",
        dimensions=(12, 8),
        source_context=context,
        source_geometry_revision=context.geometry_revision,
        expected_scenario_revision=context.scenario_revision,
        expected_physical_revision=context.physical_revision,
        image_base64=base64.b64encode(data).decode("ascii"),
        image_sha256=hashlib.sha256(data).hexdigest(),
    )


@pytest.fixture
def adapter():
    value = GroundingAdapter(api_key="offline-test-placeholder")
    assert value.sdk_version == "2.33.0"
    assert value.is_live_configured()
    client = value.client
    yield value
    client.close()


@pytest.fixture
def mock_http(monkeypatch):
    calls = []
    state = {
        "response": {
            "id": "offline-interaction-1", "model": "gemini-4-argon", "status": "completed",
            "steps": [{"type": "model_output", "content": [{"type": "text", "text": json.dumps(VALID_OUTPUT)}]}],
            "usage": {"total_input_tokens": 12, "total_output_tokens": 18, "total_tokens": 30,
                      "input_tokens_by_modality": [{"modality": "image", "tokens": 8}]},
        },
        "status_code": 200,
        "delay": 0,
    }
    async def send(client, request, *args, **kwargs):
        calls.append(json.loads(request.content))
        if state["delay"]:
            await asyncio.sleep(state["delay"])
        return httpx.Response(state["status_code"], json=state["response"], request=request)
    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    return state, calls


@pytest.mark.asyncio
async def test_real_sdk_async_schema_image_and_typed_usage(adapter, capture, context, mock_http):
    _, calls = mock_http
    result = await adapter.interpret_capture(capture, context)
    assert result.status == "completed", result.errors
    assert result.provenance == "live"
    assert result.proposal.status == GroundingStatus.MATCHED
    assert result.proposal.selected_entity_id == "P2"
    assert result.proposal.source_context == context
    assert result.provider_interaction_id == "offline-interaction-1"
    assert result.provider_model == "gemini-4-argon"
    assert result.token_usage == {"total_input_tokens": 12, "total_output_tokens": 18, "total_tokens": 30}
    assert result.sdk_version == "2.33.0"
    assert result.latency_ms > 0
    assert len(calls) == 1
    body = calls[0]
    assert body["model"] == "gemini-4-argon"
    assert body["store"] is True
    assert body["stream"] is False
    assert body["response_format"]["mime_type"] == "application/json"
    schema = body["response_format"]["schema"]
    assert schema["additionalProperties"] is False
    # `operation` is application-owned: the provider schema never asks for it.
    assert "operation" not in schema["properties"]
    assert set(schema["required"]) == set(VALID_OUTPUT) - {"operation"}
    assert body["generation_config"] == {"thinking_level": "low", "max_output_tokens": 8192}
    content = body["input"][0]["content"]
    assert content[1] == {"type": "image", "mime_type": "image/jpeg", "data": capture.image_base64}
    prompt = json.loads(content[0]["text"])
    assert prompt["source_context"] == context.model_dump(mode="json")
    assert {item["typed_id"] for item in prompt["catalog"]} == {"portal:P1", "portal:P2", "boundary:B2"}
    assert "tools" not in body


@pytest.mark.asyncio
@pytest.mark.parametrize("patch", [
    {"status": "invented"},
    {"operation": "OPEN_ALL_EXITS"},
    {"candidate_ids": ["portal:P2", "portal:P2"]},
    {"candidate_ids": ["portal:P2", "portal:P99"]},
    {"candidate_ids": ["portal:P1"]},
    {"selected_entity_type": "boundary"},
    {"selected_entity_id": "P3"},
    {"selected_entity_type": None},
    {"selected_entity_id": None},
    {"status": "ambiguous", "selected_entity_id": None},
    {"status": "no_match", "selected_entity_id": None, "selected_entity_type": None},
    {"evidence": "  "},
    {"evidence": "x" * 1001},
    {"box_2d": [20, 30]},
    {"box_2d": [-1, 30, 40, 50]},
    {"box_2d": [20, 30, 1001, 50]},
    {"box_2d": [40, 30, 20, 50]},
    {"box_2d": [20, 50, 40, 30]},
    {"box_2d": [20, 30, 20, 50]},
    {"box_2d": [20.0, 30, 40, 50]},
    {"box_2d": [False, 30, 40, 50]},
    {"box_2d": ["20", 30, 40, 50]},
    {"untrusted_field": "instruction"},
    {"source_context": {}},
])
async def test_invalid_provider_fields_are_rejected_without_rewrite(adapter, capture, context, mock_http, patch):
    state, calls = mock_http
    payload = copy.deepcopy(VALID_OUTPUT)
    payload.update(patch)
    state["response"]["steps"][0]["content"][0]["text"] = json.dumps(payload)
    result = await adapter.interpret_capture(capture, context)
    assert result.status == "failed"
    assert result.provenance == "live"
    assert result.proposal is None
    assert result.errors == ["invalid_provider_output"]
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["not JSON", '{"status":"matched"', '[]', 'null',
    json.dumps(VALID_OUTPUT)[:-1] + ',"operation":"SET_UNAVAILABLE"}',
    json.dumps(VALID_OUTPUT).replace('"Circular token overlaps the printed T_P2 pad."', 'NaN'),
])
async def test_malformed_partial_or_duplicate_key_json_is_not_a_proposal(adapter, capture, context, mock_http, text):
    state, _ = mock_http
    state["response"]["steps"][0]["content"][0]["text"] = text
    result = await adapter.interpret_capture(capture, context)
    assert result.proposal is None
    assert result.errors == ["invalid_provider_output"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["failed", "incomplete", "requires_action", "in_progress", "queued", "budget_exceeded", "unknown"])
async def test_only_completed_provider_status_can_publish(adapter, capture, context, mock_http, status):
    state, calls = mock_http
    state["response"]["status"] = status
    result = await adapter.interpret_capture(capture, context)
    assert result.status == "failed"
    assert result.proposal is None
    assert result.errors == ["provider_status_not_completed"]
    assert len(calls) == 1  # No automatic resumption or repeat billing.


@pytest.mark.asyncio
async def test_model_substitution_and_missing_receipt_are_rejected(adapter, capture, context, mock_http):
    state, _ = mock_http
    state["response"]["model"] = "gemini-3.8-flash"
    mismatch = await adapter.interpret_capture(capture, context)
    assert mismatch.errors == ["provider_model_mismatch"]
    assert mismatch.proposal is None
    state["response"]["model"] = "gemini-4-argon"
    del state["response"]["id"]
    missing = await adapter.interpret_capture(capture, context)
    assert missing.errors == ["provider_receipt_missing"]
    assert missing.proposal is None
    assert missing.provider_model == "gemini-4-argon"
    assert missing.token_usage["total_tokens"] == 30


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_id", [
    "opaque+base64/receipt==",
    "opaque+" + "AbCd/09+" * 200 + "==",
    "receipt=" + "x" * (16_384 - len("receipt=")),
])
async def test_long_and_padded_provider_ids_are_preserved_exactly(adapter, capture, context, mock_http, provider_id):
    state, calls = mock_http
    state["response"]["id"] = provider_id
    result = await adapter.interpret_capture(capture, context)
    assert result.status == "completed", result.errors
    assert result.provenance == "live"
    assert result.provider_interaction_id == provider_id
    assert result.proposal.selected_entity_id == "P2"
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_id", ["", "x" * 16_385, "opaque\nreceipt", "opaque\x7freceipt", "opaque\x85receipt"])
async def test_empty_oversized_and_control_character_receipts_fail_closed(adapter, capture, context, mock_http, provider_id):
    state, _ = mock_http
    state["response"]["id"] = provider_id
    result = await adapter.interpret_capture(capture, context)
    assert result.status == "failed"
    assert result.errors == ["provider_receipt_missing"]
    assert result.provider_interaction_id is None
    assert result.proposal is None


@pytest.mark.asyncio
async def test_unknown_or_tool_steps_cannot_hide_behind_valid_json(adapter, capture, context, mock_http):
    state, _ = mock_http
    state["response"]["steps"].append({"type": "function_call", "id": "call-x", "name": "set_servo", "arguments": {}})
    result = await adapter.interpret_capture(capture, context)
    assert result.proposal is None
    assert result.errors == ["unexpected_provider_step"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code,error", [(400, "provider_request_rejected"), (401, "provider_access_denied"),
    (403, "provider_access_denied"), (429, "provider_rate_limited"), (503, "provider_unavailable"),
    (408, "provider_timeout"), (504, "provider_timeout")])
async def test_provider_http_errors_are_safe_and_never_fixtures(adapter, capture, context, mock_http, caplog, status_code, error):
    state, calls = mock_http
    state["status_code"] = status_code
    state["response"] = {"error": {"code": status_code, "message": "SECRET-MUST-NOT-ESCAPE", "status": "PERMISSION_DENIED"}}
    result = await adapter.interpret_capture(capture, context)
    assert result.errors == [error]
    assert result.provenance == "live"
    assert result.proposal is None
    assert "SECRET-MUST-NOT-ESCAPE" not in result.model_dump_json() + caplog.text
    assert len(calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("patch", [
    {"selected_entity_type": "boundary", "selected_entity_id": "B2", "candidate_ids": ["boundary:B2"]},
    {"status": "ambiguous", "selected_entity_type": None, "selected_entity_id": None, "candidate_ids": ["portal:P1", "portal:P2"]},
    {"status": "no_match", "selected_entity_type": None, "selected_entity_id": None, "candidate_ids": [], "box_2d": None},
])
async def test_valid_boundary_and_abstention_results_remain_reviewable(adapter, capture, context, mock_http, patch):
    state, _ = mock_http
    payload = {**VALID_OUTPUT, **patch}
    state["response"]["steps"][0]["content"][0]["text"] = json.dumps(payload)
    result = await adapter.interpret_capture(capture, context)
    assert result.status == "completed"
    assert result.provenance == "live"
    assert result.proposal.selected_entity_id == payload["selected_entity_id"]
    assert result.proposal.status.value == payload["status"]


@pytest.mark.asyncio
async def test_abstention_without_operation_is_reviewable(adapter, capture, context, mock_http):
    # The live provider answered a camera still with no board this way on 25 October 2026.
    state, _ = mock_http
    payload = {"status": "no_match", "candidate_ids": [], "selected_entity_type": None, "selected_entity_id": None,
               "evidence": "The SpatialTwin tabletop model, token pads, and BLOCKED tokens are not visible.", "box_2d": None}
    state["response"]["steps"][0]["content"][0]["text"] = json.dumps(payload)
    result = await adapter.interpret_capture(capture, context)
    assert result.status == "completed", result.errors
    assert result.proposal.status == GroundingStatus.NO_MATCH
    assert result.proposal.operation == "SET_UNAVAILABLE"


@pytest.mark.asyncio
async def test_deadline_cancels_inflight_http_and_does_not_block_event_loop(adapter, capture, context, mock_http):
    state, calls = mock_http
    state["delay"] = 10
    heartbeat = asyncio.Event()
    async def tick():
        await asyncio.sleep(.01)
        heartbeat.set()
    result, _ = await asyncio.gather(adapter.interpret_capture(capture, context, deadline_seconds=.05), tick())
    assert heartbeat.is_set()
    assert result.status == "timed_out"
    assert result.errors == ["provider_timeout"]
    assert result.proposal is None
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_transport_timeout_does_not_retry_or_publish(adapter, capture, context, monkeypatch):
    calls = []
    async def timeout(client, request, *args, **kwargs):
        calls.append(request)
        raise httpx.ReadTimeout("SECRET-TIMEOUT-TEXT", request=request)
    monkeypatch.setattr(httpx.AsyncClient, "send", timeout)
    result = await adapter.interpret_capture(capture, context)
    assert result.status == "timed_out"
    assert result.errors == ["provider_timeout"]
    assert result.proposal is None
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_shutdown_closes_sdk_transports_and_disables_live_config(adapter, capture, context):
    client = adapter.client
    await adapter.aclose()
    assert client._api_client._httpx_client.is_closed
    assert client._api_client._async_httpx_client.is_closed
    assert not adapter.is_live_configured()
    await adapter.aclose()  # Application cleanup is idempotent.
    result = await adapter.interpret_capture(capture, context)
    assert result.status == "unavailable"
    assert result.proposal is None


@pytest.mark.asyncio
async def test_caller_cancellation_propagates_and_provider_cancellation_returns_no_proposal(adapter, capture, context, mock_http):
    state, calls = mock_http
    state["delay"] = 10
    task = asyncio.create_task(adapter.interpret_capture(capture, context))
    while not calls:
        await asyncio.sleep(.001)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):  # caller cancellation propagates, never becomes a result
        await task
    state["delay"] = 0
    state["response"]["status"] = "cancelled"
    provider = await adapter.interpret_capture(capture, context)
    assert provider.status == "cancelled"
    assert provider.proposal is None


@pytest.mark.asyncio
@pytest.mark.parametrize("patch,error", [
    ({"source_context": None}, "capture_context_required"),
    ({"source_geometry_revision": "older"}, "stale_capture"),
    ({"expected_scenario_revision": 2}, "stale_capture"),
    ({"expected_physical_revision": 2}, "stale_capture"),
    ({"timestamp_iso": "bad timestamp"}, "invalid_capture_timestamp"),
    ({"timestamp_iso": "2026-10-24T00:00:00"}, "invalid_capture_timestamp"),
    ({"image_base64": None}, "capture_image_required"),
    ({"image_base64": "not base64"}, "invalid_capture_image"),
    ({"image_base64": "AA=="}, "invalid_capture_image"),
    ({"dimensions": (1920, 1080)}, "capture_dimension_mismatch"),
    ({"image_sha256": "f" * 64}, "capture_image_hash_mismatch"),
])
async def test_capture_validation_fails_before_provider_contact(adapter, capture, context, mock_http, patch, error):
    _, calls = mock_http
    result = await adapter.interpret_capture(capture.model_copy(update=patch), context)
    assert result.status == "failed"
    assert result.proposal is None
    assert result.errors == [error]
    assert not calls


@pytest.mark.asyncio
async def test_full_source_context_and_live_timestamp_are_required(adapter, capture, context, mock_http):
    _, calls = mock_http
    other = RunContext(geometry_revision=context.geometry_revision, scenario_revision=context.scenario_revision,
        physical_revision=context.physical_revision, parameters_revision="other-parameters")
    stale = await adapter.interpret_capture(capture.model_copy(update={"source_context": other}), context)
    assert stale.errors == ["stale_capture"]
    for delta in (timedelta(seconds=-121), timedelta(seconds=6)):
        timestamp = (datetime.now(timezone.utc) + delta).isoformat()
        result = await adapter.interpret_capture(capture.model_copy(update={"timestamp_iso": timestamp}), context)
        assert result.errors == ["stale_capture"]
    assert not calls


@pytest.mark.asyncio
async def test_corrupt_and_mislabeled_images_are_rejected(adapter, capture, context, mock_http):
    _, calls = mock_http
    data = base64.b64decode(capture.image_base64)
    truncated = base64.b64encode(data[:-40] + b"\xff\xd9").decode()
    result = await adapter.interpret_capture(capture.model_copy(update={"image_base64": truncated}), context)
    assert result.errors == ["invalid_capture_image"]
    png = io.BytesIO()
    Image.new("RGB", (12, 8)).save(png, "PNG")
    result = await adapter.interpret_capture(capture.model_copy(update={"image_base64": base64.b64encode(png.getvalue()).decode()}), context)
    assert result.errors == ["invalid_capture_image"]
    assert not calls


@pytest.mark.asyncio
async def test_encoded_size_limit_runs_before_image_decode(adapter, capture, context, mock_http):
    _, calls = mock_http
    result = await adapter.interpret_capture(capture.model_copy(update={"image_base64": "A" * (MAX_IMAGE_BYTES * 2)}), context)
    assert result.errors == ["capture_image_too_large"]
    assert not calls


@pytest.mark.asyncio
async def test_missing_configuration_is_unavailable_not_a_matched_fixture(capture, context, mock_http):
    _, calls = mock_http
    result = await GroundingAdapter(api_key="").interpret_capture(capture, context)
    assert result.status == "unavailable"
    assert result.provenance == "unavailable"
    assert result.errors == ["configuration_missing"]
    assert result.proposal is None
    assert not calls


@pytest.mark.asyncio
async def test_force_target_cannot_relabel_real_camera_as_fixture(adapter, capture, context, mock_http):
    _, calls = mock_http
    result = await adapter.interpret_capture(capture, context, force_target="P2")
    assert result.errors == ["fixture_source_required"]
    assert result.proposal is None
    assert not calls


@pytest.mark.asyncio
async def test_local_fault_is_not_reported_as_provider_failure(adapter, capture, context, monkeypatch):
    def local_bug(*a, **k):
        raise RuntimeError("local bug")
    monkeypatch.setattr(GroundingAdapter, "_validate_image", staticmethod(local_bug))
    result = await adapter.interpret_capture(capture, context)
    assert result.status == "failed" and result.errors == ["local_processing_failure"]
