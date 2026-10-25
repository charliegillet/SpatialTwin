"""Offline tests for the Camera twin card reader against the real pinned SDK and mocked HTTP.

No credentials are read and no network is reached.
"""

import asyncio
import base64
import hashlib
import io
import json
import socket
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from PIL import Image

from backend.app.ai.grounding.adapter import GroundingAdapter
from backend.app.ai.grounding.hazard_read import CARD_SYSTEM_INSTRUCTION, HazardCardReader

CARD = {"type": "FIRE", "point": [300, 500], "box_2d": [250, 450, 350, 550], "label_text": "FIRE",
        "evidence": "Red card with a flame icon and the word FIRE in the lobby."}


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Real network is disabled in card-reader tests")
    async def blocked_async(*args, **kwargs):
        raise AssertionError("HTTP response must be explicitly mocked")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(httpx.Client, "send", blocked)
    monkeypatch.setattr(httpx.AsyncClient, "send", blocked_async)


@pytest.fixture
def image():
    output = io.BytesIO()
    Image.new("RGB", (16, 10), (200, 30, 30)).save(output, format="JPEG")
    data = output.getvalue()
    return {"image_base64": base64.b64encode(data).decode("ascii"), "dimensions": (16, 10),
            "image_sha256": hashlib.sha256(data).hexdigest()}


@pytest.fixture
def reader():
    adapter = GroundingAdapter(api_key="offline-test-placeholder")
    yield HazardCardReader(adapter)
    adapter.client.close()


@pytest.fixture
def mock_http(monkeypatch):
    calls = []
    state = {"output": {"cards": [CARD], "corners": []}, "status_code": 200, "model": "gemini-4-argon", "delay": 0}

    async def send(client, request, *args, **kwargs):
        calls.append(json.loads(request.content))
        if state["delay"]:
            await asyncio.sleep(state["delay"])
        body = {
            "id": "offline-card-read-1", "model": state["model"], "status": "completed",
            "steps": [{"type": "model_output", "content": [{"type": "text", "text": json.dumps(state["output"])}]}],
            "usage": {"total_input_tokens": 20, "total_output_tokens": 30, "total_tokens": 50},
        }
        return httpx.Response(state["status_code"], json=body, request=request)

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    return state, calls


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.mark.asyncio
async def test_live_read_returns_typed_cards_with_receipt(reader, image, mock_http):
    _, calls = mock_http
    result = await reader.read(capture_id="cap-1", timestamp_iso=_now(), **image)
    assert result.status == "completed", result.errors
    assert result.provenance == "live"
    assert result.provider_interaction_id == "offline-card-read-1"
    assert [card.type for card in result.cards] == ["FIRE"]
    assert result.cards[0].confidence == "high"
    request = calls[0]
    assert request["model"] == "gemini-4-argon"
    assert request["system_instruction"] == CARD_SYSTEM_INSTRUCTION
    assert request["response_format"]["schema"]["properties"]["cards"]["maxItems"] == 8


@pytest.mark.asyncio
async def test_mismatched_word_is_low_confidence_not_dropped(reader, image, mock_http):
    state, _ = mock_http
    state["output"] = {"cards": [{**CARD, "type": "GAS", "label_text": "FIRE"}], "corners": []}
    result = await reader.read(capture_id="cap-2", timestamp_iso=_now(), **image)
    assert result.status == "completed"
    assert result.cards[0].confidence == "low"
    assert result.cards[0].low_confidence_reason == "printed word does not match the type"


@pytest.mark.asyncio
async def test_unknown_type_or_unordered_box_fails_closed(reader, image, mock_http):
    state, _ = mock_http
    for bad in ({**CARD, "type": "FLOOD"}, {**CARD, "box_2d": [350, 450, 250, 550]}, {**CARD, "point": [300, 1200]}):
        state["output"] = {"cards": [bad], "corners": []}
        result = await reader.read(capture_id="cap-3", timestamp_iso=_now(), **image)
        assert result.status == "failed"
        assert result.errors == ["invalid_provider_output"]
        assert result.cards == []


@pytest.mark.asyncio
async def test_more_than_eight_cards_fails_closed(reader, image, mock_http):
    state, _ = mock_http
    state["output"] = {"cards": [CARD] * 9, "corners": []}
    result = await reader.read(capture_id="cap-4", timestamp_iso=_now(), **image)
    assert result.errors == ["invalid_provider_output"]


@pytest.mark.asyncio
async def test_corners_only_when_requested(reader, image, mock_http):
    state, _ = mock_http
    corners = [{"id": "TL", "point": [40, 30]}, {"id": "TR", "point": [40, 970]}]
    state["output"] = {"cards": [], "corners": corners}
    unrequested = await reader.read(capture_id="cap-5", timestamp_iso=_now(), **image)
    assert unrequested.errors == ["invalid_provider_output"]
    requested = await reader.read(capture_id="cap-6", timestamp_iso=_now(), include_corners=True, **image)
    assert requested.status == "completed"
    assert [c.id for c in requested.corners] == ["TL", "TR"]
    state["output"] = {"cards": [], "corners": corners + [{"id": "TL", "point": [41, 31]}]}
    duplicate = await reader.read(capture_id="cap-7", timestamp_iso=_now(), include_corners=True, **image)
    assert duplicate.errors == ["invalid_provider_output"]


@pytest.mark.asyncio
async def test_model_mismatch_and_stale_capture_fail(reader, image, mock_http):
    state, calls = mock_http
    state["model"] = "some-other-model"
    mismatch = await reader.read(capture_id="cap-8", timestamp_iso=_now(), **image)
    assert mismatch.errors == ["provider_model_mismatch"]
    stale = await reader.read(capture_id="cap-9", timestamp_iso=(datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(), **image)
    assert stale.errors == ["stale_capture"]
    assert stale.provenance == "unavailable"


@pytest.mark.asyncio
async def test_tampered_image_is_rejected_before_any_call(reader, image, mock_http):
    _, calls = mock_http
    tampered = await reader.read(capture_id="cap-10", timestamp_iso=_now(), **{**image, "image_sha256": "0" * 64})
    assert tampered.errors == ["capture_image_hash_mismatch"]
    assert calls == []


@pytest.mark.asyncio
async def test_rate_limit_and_timeout_are_classified(reader, image, mock_http):
    state, _ = mock_http
    state["status_code"] = 429
    limited = await reader.read(capture_id="cap-11", timestamp_iso=_now(), **image)
    assert limited.errors == ["provider_rate_limited"]
    state["status_code"] = 200
    state["delay"] = 0.5
    slow = await reader.read(capture_id="cap-12", timestamp_iso=_now(), deadline_seconds=0.05, **image)
    assert slow.status == "timed_out"


@pytest.mark.asyncio
async def test_fixture_mode_is_labelled_and_needs_cards(reader, mock_http):
    _, calls = mock_http
    empty = await reader.read(capture_id="cap-13", timestamp_iso=_now(), image_base64=None, dimensions=(1, 1), mode="fixture")
    assert empty.errors == ["fixture_cards_required"]
    fixture = await reader.read(capture_id="cap-14", timestamp_iso=_now(), image_base64=None, dimensions=(1, 1),
                                mode="fixture", fixture_cards=[{"type": "WATER", "point": [500, 300], "box_2d": [450, 250, 550, 350]}])
    assert fixture.status == "completed"
    assert fixture.provenance == "fixture"
    assert fixture.cards[0].evidence.startswith("[FIXTURE]")
    assert calls == []


@pytest.mark.asyncio
async def test_unconfigured_reader_is_unavailable(image):
    reader = HazardCardReader(GroundingAdapter(api_key=""))
    result = await reader.read(capture_id="cap-15", timestamp_iso=_now(), **image)
    assert result.status == "unavailable"
    assert result.errors == ["configuration_missing"]
