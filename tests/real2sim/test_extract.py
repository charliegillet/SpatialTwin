"""Real2Sim extraction against the real pinned SDK (google-genai 2.33.0) with mocked HTTP; no credentials, no network.

These tests pin the request shape (field names the SDK actually sends) and the parsing of a streamed SSE response
with thought summaries, so a live probe only has to confirm the provider honours them.
"""
import asyncio
import base64
import copy
import io
import json
import socket

import httpx
import pytest
from PIL import Image

from backend.app.ai.grounding.adapter import GroundingAdapter
from backend.app.ai.real2sim.extract import (
    MAX_THOUGHT_CHARS,
    MAX_THOUGHTS,
    REAL2SIM_SYSTEM_INSTRUCTION,
    DraftExtractor,
    SourceDocument,
    provider_schema_copy,
)
from backend.app.ai.real2sim.schema import SourceImage, provider_response_schema
from backend.app.ai.receipts import receipts_dir

VALID_DRAFT = {
    "schema_version": "draft-1", "title": "Test flat", "image_kind": "sketch",
    "scale": {"basis": "unknown", "a": None, "b": None, "metres": None, "evidence": ""},
    "rooms": [
        {"key": "LIVING", "name": "Living", "kind": "room", "box": [100, 100, 500, 500], "extra_boxes": [],
         "label_point": [300, 300], "occupants_hint": None},
        {"key": "KITCHEN", "name": "Kitchen", "kind": "kitchen", "box": [100, 500, 500, 900], "extra_boxes": [],
         "label_point": [300, 700], "occupants_hint": None},
        {"key": "HALL", "name": "Hall", "kind": "corridor", "box": [500, 100, 600, 900], "extra_boxes": [],
         "label_point": [550, 500], "occupants_hint": None},
    ],
    "doors": [
        {"key": "KD1", "between": ["LIVING", "HALL"], "point": [500, 300], "width_m": None, "symbol": "swing",
         "confidence": 0.9, "evidence": "gap with swing arc"},
        {"key": "KD2", "between": ["KITCHEN", "HALL"], "point": [500, 700], "width_m": 0.9, "symbol": "opening",
         "confidence": 0.8, "evidence": "opening"},
    ],
    "exits": [{"key": "X1", "room": "HALL", "point": [600, 500], "width_m": None, "kind": "door", "label": "EXIT",
               "confidence": 0.95, "evidence": "EXIT sign"}],
    "sheet_corners": None, "you_are_here": None, "unreadable": ["smudged label top left"], "notes": "",
}
THOUGHTS = ["**Reading the walls**\n\nI see three rooms and a corridor.", "**Finding exits**\n\nOne EXIT sign."]


def _sse(events):
    body = "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events)
    return (body + "event: done\ndata: [DONE]\n\n").encode()


def stream_events(text, *, thoughts=THOUGHTS, model="gemini-4-argon", interaction_id="v1_offline", status="completed",
                  extra=(), complete=True):
    events = [("interaction.created", {"interaction": {"id": interaction_id, "status": "in_progress",
                                                       "object": "interaction", "model": model},
                                       "event_type": "interaction.created"}),
              ("step.start", {"index": 0, "step": {"type": "thought"}, "event_type": "step.start"})]
    events += [("step.delta", {"index": 0, "delta": {"type": "thought_summary", "content": {"type": "text", "text": t}},
                               "event_type": "step.delta"}) for t in thoughts]
    events += [("step.delta", {"index": 0, "delta": {"type": "thought_signature", "signature": "c2ln"},
                               "event_type": "step.delta"}),
               ("step.stop", {"index": 0, "event_type": "step.stop"}),
               ("step.start", {"index": 1, "step": {"type": "model_output"}, "event_type": "step.start"})]
    half = len(text) // 2
    events += [("step.delta", {"index": 1, "delta": {"type": "text", "text": part}, "event_type": "step.delta"})
               for part in (text[:half], text[half:]) if part]
    events += [("step.stop", {"index": 1, "event_type": "step.stop"}), *extra]
    if complete:
        events.append(("interaction.completed", {"interaction": {
            "id": interaction_id, "status": status, "model": model, "object": "interaction",
            "usage": {"total_input_tokens": 1200, "total_output_tokens": 300, "total_thought_tokens": 800,
                      "total_tokens": 2300}}, "event_type": "interaction.completed"}))
    return events


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Real network is disabled in extraction tests")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(httpx.Client, "send", blocked)


@pytest.fixture
def adapter():
    value = GroundingAdapter(api_key="offline-test-placeholder")
    assert value.sdk_version == "2.33.0" and value.is_live_configured()
    client = value.client
    yield value
    client.close()


@pytest.fixture
def mock_http(monkeypatch):
    calls = []
    state = {"events": stream_events(json.dumps(VALID_DRAFT)), "json": None, "status_code": 200, "delay": 0.0}

    async def send(client, request, *args, **kwargs):
        calls.append(json.loads(request.content))
        if state["delay"]:
            await asyncio.sleep(state["delay"])
        if state["status_code"] != 200:
            return httpx.Response(state["status_code"], json={"error": {"code": state["status_code"],
                                                                        "message": "provider says no"}},
                                  request=request)
        if state["json"] is not None:
            return httpx.Response(200, json=state["json"], request=request)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=_sse(state["events"]),
                              request=request)

    monkeypatch.setattr(httpx.AsyncClient, "send", send)
    return state, calls


def png_source(width=40, height=30):
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (240, 240, 240)).save(buffer, format="PNG")
    data = buffer.getvalue()
    return SourceDocument(data, "image/png", "photo", SourceImage(width, height, "0" * 64, "image/png"))


def receipt():
    path = receipts_dir() / "last_live.json"
    return json.loads(path.read_text()) if path.exists() else None


async def test_streamed_extraction_collects_thoughts_and_returns_a_salvaged_draft(adapter, mock_http):
    _, calls = mock_http
    seen = []
    result = await DraftExtractor(adapter, stream=True).extract(png_source(), on_thought=seen.append)
    assert result.status == "completed", result.errors
    assert result.provenance == "live" and result.streamed is True
    assert [room.key for room in result.draft.rooms] == ["LIVING", "KITCHEN", "HALL"]
    assert result.draft.unreadable == ["smudged label top left"]
    assert result.dropped == [] and result.repaired == []
    assert result.thoughts == THOUGHTS and seen == THOUGHTS
    assert result.first_thought_ms is not None and result.first_output_ms is not None
    assert result.provider_interaction_id == "v1_offline" and result.provider_model == "gemini-4-argon"
    assert result.token_usage["total_tokens"] == 2300
    assert receipt()["kind"] == "real2sim_extract" and receipt()["model"] == "gemini-4-argon"
    body = calls[0]
    assert body["model"] == "gemini-4-argon" and body["store"] is True and body["stream"] is True
    assert body["generation_config"] == {"thinking_level": "medium", "thinking_summaries": "auto",
                                         "max_output_tokens": 32768}
    assert body["response_format"] == {"type": "text", "mime_type": "application/json",
                                       "schema": provider_response_schema()}
    assert "previous_interaction_id" not in body and "tools" not in body
    assert "untrusted scene content" in body["system_instruction"]
    assert body["system_instruction"] == REAL2SIM_SYSTEM_INSTRUCTION
    prompt_part, image_part = body["input"][0]["content"]
    assert prompt_part["type"] == "text" and json.loads(prompt_part["text"])["task"] == "read_floor_plan"
    assert image_part["type"] == "image" and image_part["mime_type"] == "image/png"
    assert image_part["resolution"] == "high"
    assert base64.b64decode(image_part["data"]) == png_source().data


async def test_provider_schema_is_the_lead_schema_without_unproven_keywords():
    schema = provider_schema_copy()
    text = json.dumps(schema)
    assert schema == provider_response_schema()
    for keyword in ('"pattern"', '"default"', '"exclusiveMinimum"', '"const"'):
        assert keyword not in text
    schema["properties"].clear()          # a copy: the cached schema is never mutated by a caller
    assert provider_schema_copy()["properties"]


def _schema_keywords(node, field_names=False):
    """Every schema keyword used anywhere in the tree (keys under properties/$defs are names, not keywords)."""
    if isinstance(node, list):
        return set().union(*(_schema_keywords(item) for item in node)) if node else set()
    if not isinstance(node, dict):
        return set()
    found = set() if field_names else set(node)
    for key, value in node.items():
        found |= _schema_keywords(value, field_names=key in ("properties", "$defs") and not field_names)
    return found


async def test_the_sent_schema_has_no_bounds_anywhere():
    """Live, gemini-4-argon answered HTTP 400 ("too many states for serving") to the bounded schema (26 Oct 2026)."""
    keywords = _schema_keywords(provider_schema_copy())
    for bound in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "minItems", "maxItems",
                  "minLength", "maxLength", "pattern", "const", "default"):
        assert bound not in keywords, bound
    assert {"type", "properties", "required", "enum", "items"} <= keywords
    # The walk does see field names as names: the draft's own `title` and `exits` survive.
    assert {"title", "rooms", "exits"} <= set(provider_schema_copy()["properties"])


async def test_non_streaming_flag_reads_steps_and_summaries(adapter, mock_http):
    state, calls = mock_http
    state["json"] = {
        "id": "v1_plain", "model": "gemini-4-argon", "status": "completed",
        "steps": [{"type": "thought", "summary": [{"type": "text", "text": "Counting rooms."}]},
                  {"type": "model_output", "content": [{"type": "text", "text": json.dumps(VALID_DRAFT)}]}],
        "usage": {"total_tokens": 10},
    }
    result = await DraftExtractor(adapter, stream=False, thinking_level="high").extract(png_source())
    assert result.status == "completed", result.errors
    assert result.streamed is False and result.thoughts == ["Counting rooms."]
    assert calls[0]["stream"] is False and calls[0]["generation_config"]["thinking_level"] == "high"


async def test_a_pdf_is_sent_as_a_document_part(adapter, mock_http):
    _, calls = mock_http
    pdf = SourceDocument(b"%PDF-1.4\n%%EOF", "application/pdf", "pdf", SourceImage(1600, 1131, "0" * 64,
                                                                                 "application/pdf"))
    result = await DraftExtractor(adapter).extract(pdf)
    assert result.status == "completed", result.errors
    part = calls[0]["input"][0]["content"][1]
    assert part == {"type": "document", "mime_type": "application/pdf",
                    "data": base64.b64encode(pdf.data).decode("ascii")}


async def test_model_substitution_fails_closed_without_a_receipt(adapter, mock_http):
    state, _ = mock_http
    state["events"] = stream_events(json.dumps(VALID_DRAFT), model="gemini-3.8-flash")
    result = await DraftExtractor(adapter).extract(png_source())
    assert result.status == "failed" and result.errors == ["provider_model_mismatch"]
    assert result.draft is None and receipt() is None


@pytest.mark.parametrize("text, code", [
    ("not JSON", "invalid_provider_output"),
    ('{"schema_version": "draft-1"', "invalid_provider_output"),
    ('{"rooms": [], "rooms": []}', "invalid_provider_output"),
    ('{"title": NaN}', "invalid_provider_output"),
    ("[]", "draft_not_an_object"),
    (json.dumps({**VALID_DRAFT, "rooms": []}), "no_room_survived"),
])
async def test_malformed_output_is_a_typed_failure_never_a_fixture(adapter, mock_http, text, code):
    state, _ = mock_http
    state["events"] = stream_events(text)
    result = await DraftExtractor(adapter).extract(png_source())
    assert result.status == "failed" and result.provenance == "live"
    assert result.errors == [code] and result.draft is None
    assert receipt() is None


async def test_one_bad_door_is_dropped_and_listed_not_fatal(adapter, mock_http):
    state, _ = mock_http
    draft = copy.deepcopy(VALID_DRAFT)
    draft["doors"].append({"key": "KD9", "between": ["LIVING", "ATTIC"], "point": [100, 100], "width_m": None,
                           "symbol": "unknown", "confidence": 0.2, "evidence": ""})
    draft["rooms"][0]["box"] = [100.0, 100, 500, 500]
    state["events"] = stream_events(json.dumps(draft))
    result = await DraftExtractor(adapter).extract(png_source())
    assert result.status == "completed", result.errors
    assert [door.key for door in result.draft.doors] == ["KD1", "KD2"]
    assert any(line.startswith("door KD9") for line in result.dropped)


async def test_deadline_is_a_timeout(adapter, mock_http):
    state, _ = mock_http
    state["delay"] = 0.5
    result = await DraftExtractor(adapter, deadline_seconds=0.05).extract(png_source())
    assert result.status == "timed_out" and result.errors == ["provider_timeout"] and result.draft is None


@pytest.mark.parametrize("status_code, code", [(429, "provider_rate_limited"), (403, "provider_access_denied"),
                                               (503, "provider_unavailable"), (400, "provider_request_rejected")])
async def test_http_errors_are_short_codes_without_provider_text(adapter, mock_http, status_code, code):
    state, _ = mock_http
    state["status_code"] = status_code
    result = await DraftExtractor(adapter).extract(png_source())
    assert result.status == "failed" and result.errors == [code]
    assert "provider says no" not in result.model_dump_json()


@pytest.mark.parametrize("error_code, code, status", [("resource_exhausted", "provider_rate_limited", "failed"),
                                                      ("gateway_timeout", "provider_timeout", "timed_out"),
                                                      ("something_new", "provider_stream_error", "failed")])
async def test_in_stream_error_events_are_classified(adapter, mock_http, error_code, code, status):
    state, _ = mock_http
    error = ("error", {"error": {"code": error_code, "message": "secret provider detail"}, "event_type": "error"})
    state["events"] = stream_events(json.dumps(VALID_DRAFT), extra=[error], complete=False)
    result = await DraftExtractor(adapter).extract(png_source())
    assert result.status == status and result.errors == [code]
    assert "secret provider detail" not in result.model_dump_json()


async def test_stream_that_never_completes_is_not_a_result(adapter, mock_http):
    state, _ = mock_http
    state["events"] = stream_events(json.dumps(VALID_DRAFT), complete=False)
    result = await DraftExtractor(adapter).extract(png_source())
    assert result.errors == ["provider_stream_incomplete"] and result.draft is None


@pytest.mark.parametrize("status", ["failed", "incomplete", "in_progress"])
async def test_only_a_completed_interaction_publishes(adapter, mock_http, status):
    state, _ = mock_http
    state["events"] = stream_events(json.dumps(VALID_DRAFT), status=status)
    result = await DraftExtractor(adapter).extract(png_source())
    assert result.errors == ["provider_status_not_completed"] and result.draft is None


async def test_tool_steps_cannot_hide_behind_valid_json(adapter, mock_http):
    state, _ = mock_http
    call = ("step.start", {"index": 2, "step": {"type": "function_call", "id": "c1", "name": "open_door",
                                                "arguments": {}}, "event_type": "step.start"})
    state["events"] = stream_events(json.dumps(VALID_DRAFT), extra=[call])
    result = await DraftExtractor(adapter).extract(png_source())
    assert result.errors == ["unexpected_provider_step"] and result.draft is None


async def test_unknown_event_types_are_skipped(adapter, mock_http):
    state, _ = mock_http
    unknown = ("interaction.something_new", {"event_type": "interaction.something_new", "detail": 1})
    state["events"] = stream_events(json.dumps(VALID_DRAFT), extra=[unknown])
    result = await DraftExtractor(adapter).extract(png_source())
    assert result.status == "completed", result.errors


async def test_thought_summaries_are_bounded(adapter, mock_http):
    state, _ = mock_http
    state["events"] = stream_events(json.dumps(VALID_DRAFT), thoughts=["x" * 5000] * (MAX_THOUGHTS + 5))
    result = await DraftExtractor(adapter).extract(png_source())
    assert result.status == "completed"
    assert len(result.thoughts) == MAX_THOUGHTS and all(len(t) == MAX_THOUGHT_CHARS for t in result.thoughts)


async def test_unconfigured_and_invalid_settings_never_call_the_provider(mock_http):
    _, calls = mock_http
    unconfigured = await DraftExtractor(GroundingAdapter(api_key="")).extract(png_source())
    assert unconfigured.status == "unavailable" and unconfigured.errors == ["configuration_missing"]
    adapter = GroundingAdapter(api_key="offline-test-placeholder")
    try:
        bad_level = await DraftExtractor(adapter).extract(png_source(), thinking_level="max")
        bad_deadline = await DraftExtractor(adapter, deadline_seconds=float("nan")).extract(png_source())
    finally:
        adapter.client.close()
    assert bad_level.errors == ["invalid_thinking_level"] and bad_deadline.errors == ["invalid_deadline"]
    assert calls == []
