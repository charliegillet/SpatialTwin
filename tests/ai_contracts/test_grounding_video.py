"""Offline video-grounding tests: real SDK serialization, mocked HTTP, no network."""

import base64
import hashlib
import json
import socket
import struct
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from backend.app.ai.grounding import video as video_mod
from backend.app.ai.grounding.adapter import GroundingAdapter
from backend.app.ai.grounding.video import (
    IMAGE_FALLBACK_ERROR, MAX_VIDEO_BYTES, ground_video, video_enabled,
)
from backend.app.contracts import GroundingStatus, RunContext

VALID_OUTPUT = {
    "status": "matched", "candidate_ids": ["portal:P2"],
    "selected_entity_type": "portal", "selected_entity_id": "P2",
    "operation": "SET_UNAVAILABLE", "evidence": "Token placed on T_P2 pad.",
    "box_2d": [200, 600, 320, 720],
}


def mp4(seconds: float, pad: int = 0) -> bytes:
    scale = 1000
    mvhd_body = struct.pack(">B3xIIII", 0, 0, 0, scale, int(seconds * scale)) + b"\0" * 80
    mvhd = struct.pack(">I4s", 8 + len(mvhd_body), b"mvhd") + mvhd_body
    moov = struct.pack(">I4s", 8 + len(mvhd), b"moov") + mvhd
    ftyp = struct.pack(">I4s", 16, b"ftyp") + b"isom\0\0\0\0"
    return ftyp + moov + b"\0" * pad


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def blocked(*a, **k):
        raise AssertionError("network disabled")
    async def blocked_async(*a, **k):
        raise AssertionError("HTTP must be mocked")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(httpx.Client, "send", blocked)
    monkeypatch.setattr(httpx.AsyncClient, "send", blocked_async)


@pytest.fixture
def receipt(tmp_path):
    (tmp_path / "P3.json").write_text(json.dumps({"pass": True}))
    (tmp_path / "P4.json").write_text(json.dumps({"pass": True}))
    return tmp_path


@pytest.fixture
def context():
    return RunContext(geometry_revision="illustrative-test", scenario_revision=4, physical_revision=3)


@pytest.fixture
def adapter():
    value = GroundingAdapter(api_key="offline-test-placeholder")
    client = value.client
    yield value
    client.close()


@pytest.fixture
def mock_http(monkeypatch):
    calls = []
    state = {"response": {
        "id": "offline-video-1", "model": "gemini-4-argon", "status": "completed",
        "steps": [{"type": "model_output", "content": [{"type": "text", "text": json.dumps(VALID_OUTPUT)}]}],
        "usage": {"total_input_tokens": 10, "total_output_tokens": 5, "total_tokens": 15},
    }}
    async def send(client, request, *a, **k):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json=state["response"], request=request)
    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    return state, calls


def set_output(state, payload):
    state["response"]["steps"][0]["content"][0]["text"] = json.dumps(payload)


@pytest.mark.asyncio
async def test_agentic_serialization_and_proposal(adapter, context, mock_http, receipt):
    _, calls = mock_http
    clip = mp4(5)
    res = await ground_video(clip, "video/mp4", context, "agentic", adapter=adapter, receipt_path=receipt)
    assert res.status == "completed", res.errors
    assert res.proposal.status == GroundingStatus.MATCHED and res.proposal.selected_entity_id == "P2"
    assert res.proposal.capture_id == "video-" + hashlib.sha256(clip).hexdigest()[:16]
    part = calls[0]["input"][0]["content"][1]
    assert part["type"] == "video" and part["mime_type"] == "video/mp4"
    assert part["processing"] == "agentic"
    assert part["data"] == base64.b64encode(clip).decode()
    assert json.loads(calls[0]["input"][0]["content"][0]["text"])["video_sha256"] == hashlib.sha256(clip).hexdigest()
    assert "untrusted scene data" in calls[0]["system_instruction"]
    assert "tools" not in calls[0]


@pytest.mark.asyncio
async def test_static_serialization(adapter, context, mock_http, receipt):
    _, calls = mock_http
    res = await ground_video(mp4(5), "video/mp4", context, "static", adapter=adapter, receipt_path=receipt,
                             fps=2.0, start_offset="1s", end_offset="4.5s")
    assert res.status == "completed", res.errors
    assert calls[0]["input"][0]["content"][1]["processing"] == {
        "type": "static", "fps": 2.0, "start_offset": "1s", "end_offset": "4.5s"}


@pytest.mark.asyncio
async def test_rejections_make_no_call(adapter, context, mock_http, receipt):
    _, calls = mock_http
    async def go(clip, mime="video/mp4", **kw):
        return await ground_video(clip, mime, context, "agentic", adapter=adapter, receipt_path=receipt, **kw)
    assert (await go(mp4(5), "video/quicktime")).errors == ["unsupported_video_mime"]
    assert (await go(mp4(1, MAX_VIDEO_BYTES))).errors == ["video_too_large"]
    assert (await go(mp4(15.5))).errors == ["video_too_long"]
    assert (await go(mp4(5), duration_seconds=20)).errors == ["video_too_long"]
    assert (await go(b"\0" * 64)).errors == ["video_duration_unknown"]
    assert (await go(b"\0" * 64, "video/webm", duration_seconds=3)).status == "completed"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_prompt_injection_p3_is_rejected(adapter, context, mock_http, receipt):
    state, _ = mock_http
    payload = dict(VALID_OUTPUT, candidate_ids=["portal:P3"], selected_entity_id="P3")
    set_output(state, payload)
    res = await ground_video(mp4(5), "video/mp4", context, "agentic", adapter=adapter, receipt_path=receipt)
    assert res.proposal is None and len(res.errors) == 1 and res.errors[0].startswith(("invalid_provider_output:schema", "invalid_provider_output:semantic"))


@pytest.mark.asyncio
async def test_extra_fields_rejected(adapter, context, mock_http, receipt):
    state, _ = mock_http
    set_output(state, dict(VALID_OUTPUT, open_exit="P3"))
    res = await ground_video(mp4(5), "video/mp4", context, "agentic", adapter=adapter, receipt_path=receipt)
    assert res.proposal is None and len(res.errors) == 1 and res.errors[0].startswith(("invalid_provider_output:schema", "invalid_provider_output:semantic"))


@pytest.mark.asyncio
async def test_stale_clip_and_context(adapter, context, mock_http, receipt):
    _, calls = mock_http
    old = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
    res = await ground_video(mp4(5), "video/mp4", context, "agentic", adapter=adapter, receipt_path=receipt,
                             captured_at_iso=old)
    assert res.errors == ["stale_capture"]
    other = RunContext(geometry_revision="illustrative-test", scenario_revision=5, physical_revision=3)
    res = await ground_video(mp4(5), "video/mp4", context, "agentic", adapter=adapter, receipt_path=receipt,
                             source_context=other)
    assert res.errors == ["stale_capture"]
    assert calls == []


@pytest.mark.asyncio
async def test_disabled_gate_signals_image_fallback(adapter, context, mock_http, tmp_path, receipt):
    _, calls = mock_http
    missing = tmp_path / "none"
    assert not video_enabled("agentic", missing)
    res = await ground_video(mp4(5), "video/mp4", context, "agentic", adapter=adapter, receipt_path=missing)
    assert res.status == "unavailable" and res.errors == [IMAGE_FALLBACK_ERROR] and res.proposal is None
    (receipt / "P4.json").write_text(json.dumps({"pass": True}))
    (receipt / "P3.json").write_text(json.dumps({"pass": False}))
    assert video_enabled("agentic", receipt) and not video_enabled("static", receipt)
    (receipt / "P4.json").write_text("not json")
    assert not video_enabled("agentic", receipt)
    (receipt / "P4.json").write_text(json.dumps({"pass": "true"}))
    assert not video_enabled("agentic", receipt)
    assert calls == []


def test_default_receipt_absent_means_disabled():
    assert video_mod.VIDEO_PROBE_FILES == {"static": "P3.json", "agentic": "P4.json"}
    if not (video_mod.VIDEO_PROBE_DIR / "P4.json").exists():
        assert not video_enabled("agentic")


@pytest.mark.asyncio
async def test_provider_processing_steps_are_allowed(adapter, context, mock_http, receipt):
    # Regression (P4): agentic video runs provider-side processing steps before the final text.
    state, _ = mock_http
    text_step = state["response"]["steps"][0]
    state["response"]["steps"] = [{"type": "processing_call"}, {"type": "processing_result"}, text_step]
    res = await ground_video(mp4(5), "video/mp4", context, "agentic", adapter=adapter, receipt_path=receipt)
    assert res.status == "completed", res.errors


@pytest.mark.asyncio
async def test_client_function_call_step_still_rejected(adapter, context, mock_http, receipt):
    state, _ = mock_http
    state["response"]["steps"].insert(0, {"type": "function_call", "name": "get_checked_comparison"})
    res = await ground_video(mp4(5), "video/mp4", context, "agentic", adapter=adapter, receipt_path=receipt)
    assert res.status == "failed" and res.errors == ["unexpected_provider_step"]


@pytest.mark.asyncio
async def test_single_code_fence_is_tolerated(adapter, context, mock_http, receipt):
    # Regression (P3): a model may wrap the JSON in one markdown fence; the schema still decides the content.
    state, _ = mock_http
    fenced = "```json\n" + json.dumps(VALID_OUTPUT) + "\n```"
    state["response"]["steps"][0]["content"][0]["text"] = fenced
    res = await ground_video(mp4(5), "video/mp4", context, "static", adapter=adapter, receipt_path=receipt)
    assert res.status == "completed", res.errors


@pytest.mark.asyncio
async def test_parse_failure_reports_its_stage(adapter, context, mock_http, receipt):
    state, _ = mock_http
    state["response"]["steps"][0]["content"][0]["text"] = "I think the token is at P2."
    res = await ground_video(mp4(5), "video/mp4", context, "static", adapter=adapter, receipt_path=receipt)
    assert res.proposal is None and res.errors == ["invalid_provider_output:json"]


@pytest.mark.asyncio
async def test_schema_failure_names_fields_not_values(adapter, context, mock_http, receipt):
    # Diagnostics for P3: the reason carries the failing field names, never the offending value.
    state, _ = mock_http
    set_output(state, dict(VALID_OUTPUT, open_exit="SECRET-VALUE-XYZ"))
    res = await ground_video(mp4(5), "video/mp4", context, "static", adapter=adapter, receipt_path=receipt)
    assert res.proposal is None and len(res.errors) == 1
    assert res.errors[0].startswith("invalid_provider_output:schema:")
    assert "open_exit" in res.errors[0] and "SECRET-VALUE-XYZ" not in res.errors[0]
