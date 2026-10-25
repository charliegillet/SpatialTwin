import json

import pytest

from fakes import FakeClient, processing_call_step, text_step
from walktwin import extract as ex
from walktwin.contracts import VenueGraph
from walktwin.extract import (ExtractionResult, extract_venue, gemini_schema,
                              load_prompt, venue_graph_schema)
from walktwin.graph_checks import check_graph
from walktwin.media import PreparedVideo

SHA = "a" * 64


@pytest.fixture
def video(tmp_path) -> PreparedVideo:
    p = tmp_path / "prepared.mp4"
    p.write_bytes(b"\x00")
    return PreparedVideo(path=p, sha256=SHA, duration_s=60.0, width=1280, height=720)


@pytest.fixture
def canned(office_graph) -> str:
    data = office_graph.model_dump(mode="json")
    assert "revision" not in data
    data["video_sha256"] = "made-up-by-model"
    return json.dumps(data)


def completed(text: str, *extra_steps) -> list:
    return [{"status": "completed", "id": "int-x", "model": "gemini-4-argon",
             "steps": [*extra_steps, text_step(text)]}]


def _video_part(client) -> dict:
    return client.requests[0]["input"][0]


# --- brief tests ----------------------------------------------------------------


async def test_valid_extraction(video, canned):
    client = FakeClient(completed(canned))
    r = await extract_venue(client, video, deadline_s=5)
    assert isinstance(r, ExtractionResult)
    assert r.status == "completed"
    assert r.error is None
    assert isinstance(r.graph, VenueGraph)
    assert r.graph.revision.startswith("g-")
    assert r.graph.video_sha256 == SHA  # model's value overridden
    assert r.findings == check_graph(r.graph, video.duration_s)
    assert r.receipt.interaction_id == "int-x"
    assert r.interaction_id == "int-x"
    assert r.video_uri == "https://fake.test/files/fake123"
    assert r.mode == "static_hifps"
    assert r.agentic_observed is None


async def test_schema_violation_invalid(video, office_graph):
    data = office_graph.model_dump(mode="json")
    del data["zones"]
    client = FakeClient(completed(json.dumps(data)))
    r = await extract_venue(client, video, deadline_s=5)
    assert r.status == "invalid"
    assert r.graph is None
    assert r.findings == []
    assert "zones" in r.error
    assert r.receipt is not None and r.receipt.status == "completed"


async def test_mode_static_sends_fps(video, canned):
    client = FakeClient(completed(canned))
    await extract_venue(client, video, mode="static", deadline_s=5)
    part = _video_part(client)
    assert part["processing"] == {"type": "static", "fps": 1}
    assert "resolution" not in part


async def test_mode_static_hifps_sends_fps3_high(video, canned):
    client = FakeClient(completed(canned))
    await extract_venue(client, video, mode="static_hifps", deadline_s=5)
    part = _video_part(client)
    assert part["processing"] == {"type": "static", "fps": 3}
    assert part["resolution"] == "high"


async def test_agentic_not_observed(video, canned):
    client = FakeClient(completed(canned))
    r = await extract_venue(client, video, mode="agentic", deadline_s=5)
    assert _video_part(client)["processing"] == "agentic"
    assert r.status == "completed"
    assert r.agentic_observed is False


async def test_output_cap_65536(video, canned):
    client = FakeClient(completed(canned))
    await extract_venue(client, video, deadline_s=5)
    assert client.requests[0]["generation_config"]["max_output_tokens"] == 65536


async def test_failed_status_propagates(video, canned, monkeypatch):
    # Even with parseable text on the step list, a failed run is never a graph.
    monkeypatch.setattr(ex, "POLL_S", 0.001)
    client = FakeClient(["in_progress", {"status": "failed", "steps": [text_step(canned)]}])
    r = await extract_venue(client, video, deadline_s=5)
    assert r.status == "failed"
    assert r.graph is None
    assert r.findings == []
    assert r.receipt.status == "failed"


async def test_timeout(video, monkeypatch):
    monkeypatch.setattr(ex, "POLL_S", 0.01)
    client = FakeClient(["in_progress"])
    r = await extract_venue(client, video, deadline_s=0.05)
    assert r.status == "timeout"
    assert r.graph is None
    assert r.receipt is None
    assert len(client.cancel_calls) == 1
    assert r.video_uri == "https://fake.test/files/fake123"
    assert r.interaction_id == client.cancel_calls[0] == "int-1"


# --- extra coverage -------------------------------------------------------------


async def test_agentic_observed_true(video, canned):
    client = FakeClient(completed(canned, processing_call_step("p1"), processing_call_step("p2")))
    r = await extract_venue(client, video, mode="agentic", deadline_s=5)
    assert r.agentic_observed is True
    assert r.receipt.processing_calls == 2


async def test_incomplete_is_failed(video, canned):
    client = FakeClient([{"status": "incomplete", "steps": [text_step(canned[:50])]}])
    r = await extract_venue(client, video, deadline_s=5)
    assert r.status == "failed"
    assert r.error == "incomplete"
    assert r.graph is None


@pytest.mark.parametrize("status", ["cancelled", "requires_action", "budget_exceeded"])
async def test_other_statuses_are_failed(video, status):
    client = FakeClient([status])
    r = await extract_venue(client, video, deadline_s=5)
    assert r.status == "failed"
    assert status in r.error


async def test_invalid_json(video):
    client = FakeClient(completed('{"schema_version": "1", "zones": ['))
    r = await extract_venue(client, video, deadline_s=5)
    assert r.status == "invalid"
    assert r.graph is None
    assert r.error.startswith("invalid JSON")


async def test_empty_text_invalid(video):
    client = FakeClient([{"status": "completed", "steps": []}])
    r = await extract_venue(client, video, deadline_s=5)
    assert r.status == "invalid"


class ProviderError(Exception):
    pass


async def test_create_error_is_failed(video, monkeypatch):
    client = FakeClient([])

    async def boom(**kwargs):
        client.requests.append(kwargs)
        raise ProviderError("400 INVALID_ARGUMENT: schema too complex")

    monkeypatch.setattr(client.aio.interactions, "create", boom)
    r = await extract_venue(client, video, deadline_s=5)
    assert r.status == "failed"
    assert r.receipt is None and r.interaction_id is None
    assert r.error == "ProviderError: 400 INVALID_ARGUMENT: schema too complex"
    assert r.video_uri == "https://fake.test/files/fake123"
    assert len(client.requests) == 1


async def test_upload_mime_type_used(video, canned, monkeypatch):
    from google.genai import types

    client = FakeClient(completed(canned))

    async def upload(**kwargs):
        return types.File(name="files/q", uri="https://fake.test/files/q",
                          mime_type="video/quicktime", state="ACTIVE")

    monkeypatch.setattr(client.aio.files, "upload", upload)
    await extract_venue(client, video, deadline_s=5)
    assert _video_part(client)["mime_type"] == "video/quicktime"
    assert _video_part(client)["uri"] == "https://fake.test/files/q"


async def test_request_shape(video, canned):
    client = FakeClient(completed(canned))
    await extract_venue(client, video, deadline_s=5, anchor_hint="the door at 0:12 is 0.86 m wide")
    req = client.requests[0]
    assert req["model"] == "gemini-4-argon"
    assert req["store"] is True and req["background"] is True
    assert req["generation_config"] == {"thinking_level": "high", "max_output_tokens": 65536,
                                        "thinking_summaries": "auto"}
    rf = req["response_format"]
    assert rf["type"] == "text" and rf["mime_type"] == "application/json"
    assert rf["schema"] == venue_graph_schema()
    video_part, text_part = req["input"]
    assert video_part["type"] == "video"
    assert video_part["uri"] == "https://fake.test/files/fake123"
    assert video_part["mime_type"] == "video/mp4"
    assert text_part["type"] == "text"
    assert "the door at 0:12 is 0.86 m wide" in text_part["text"]
    assert "60.0" in text_part["text"]  # duration given to the model
    assert "{{" not in text_part["text"]
    assert client.uploads[0]["file"] == str(video.path)


async def test_no_anchor_hint_block_when_absent(video, canned):
    client = FakeClient(completed(canned))
    await extract_venue(client, video, deadline_s=5)
    text = client.requests[0]["input"][1]["text"]
    assert "No anchor hint was given" in text
    assert "{{" not in text


async def test_model_anchor_is_dropped(video, office_graph):
    data = office_graph.model_dump(mode="json")
    data["anchor"] = {"door_id": "D1", "measured_width_m": 0.86}
    client = FakeClient(completed(json.dumps(data)))
    r = await extract_venue(client, video, deadline_s=5)
    assert r.status == "completed"
    assert r.graph.anchor is None  # only a tape measurement sets the anchor


async def test_code_fence_and_heading_normalised(video, office_graph):
    data = office_graph.model_dump(mode="json")
    data["keyframes"][0]["heading_deg"] = 360.0
    data["keyframes"][1]["heading_deg"] = -90.0
    data["zones"][0]["evidence"][0]["note"] = "x" * 250
    client = FakeClient(completed("```json\n" + json.dumps(data) + "\n```"))
    r = await extract_venue(client, video, deadline_s=5)
    assert r.status == "completed", r.error
    assert r.graph.keyframes[0].heading_deg == 0.0
    assert r.graph.keyframes[1].heading_deg == 270.0
    assert len(r.graph.zones[0].evidence[0].note) == 200


# --- schema ---------------------------------------------------------------------

ALLOWED_KEYS = {"type", "properties", "required", "items", "enum", "description",
                "minItems", "maxItems"}


def _walk(node, path="$"):
    if isinstance(node, dict):
        yield path, node
        for k, v in node.items():
            if k == "properties":
                for name, sub in v.items():
                    yield from _walk(sub, f"{path}.{name}")
            elif isinstance(v, (dict, list)):
                yield from _walk(v, f"{path}/{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _walk(v, f"{path}[{i}]")


def test_pydantic_schema_has_no_revision():
    assert "revision" not in json.dumps(VenueGraph.model_json_schema())


def test_schema_is_flat_and_supported():
    s = venue_graph_schema()
    text = json.dumps(s)
    for bad in ("$ref", "$defs", "prefixItems", "anyOf", "const", "exclusiveMinimum",
                "exclusiveMaximum", "minimum", "maximum", "pattern", "maxLength", "title",
                "default", "revision"):
        assert f'"{bad}":' not in text, bad  # as a key, not inside descriptions
    for path, node in _walk(s):
        if "properties" in node or "type" in node:
            assert set(node) <= ALLOWED_KEYS, (path, set(node) - ALLOWED_KEYS)


def test_schema_shape():
    s = venue_graph_schema()
    assert s["type"] == "object"
    assert set(s["required"]) == {"schema_version", "video_sha256", "anchor", "zones",
                                  "doors", "keyframes"}
    assert s["properties"]["schema_version"]["enum"] == ["1"]
    assert s["properties"]["anchor"]["type"] == ["object", "null"]
    zone = s["properties"]["zones"]["items"]
    # every property required (furniture_seen must be stated per zone)
    assert set(zone["required"]) == set(zone["properties"])
    assert "furniture_seen" in zone["required"]
    rect = zone["properties"]["rect"]
    assert rect == {**rect, "type": "array", "items": {"type": "number"},
                    "minItems": 4, "maxItems": 4}
    door = s["properties"]["doors"]["items"]
    assert door["properties"]["state"]["enum"] == ["open", "closed", "locked", "unknown"]
    assert door["properties"]["position"]["minItems"] == 2
    assert door["properties"]["clear_width"]["properties"]["basis"]["enum"] == [
        "anchor_measured", "estimated", "assumed"]
    kf = s["properties"]["keyframes"]
    assert kf["minItems"] == 5 and kf["maxItems"] == 8
    assert zone["properties"]["evidence"]["minItems"] == 1


def test_gemini_schema_flattens_generic_constructs():
    from pydantic import BaseModel

    class Inner(BaseModel):
        v: int

    class Outer(BaseModel):
        pair: tuple[float, str]
        maybe: Inner | None
        many: list[Inner]

    s = gemini_schema(Outer)
    assert s["properties"]["maybe"] == {"type": ["object", "null"],
                                        "properties": {"v": {"type": "integer"}},
                                        "required": ["v"]}
    assert s["properties"]["many"]["items"]["properties"]["v"] == {"type": "integer"}
    # heterogeneous tuples keep prefixItems (documented as supported)
    assert s["properties"]["pair"]["prefixItems"] == [{"type": "number"}, {"type": "string"}]


def test_gemini_schema_anyof_keeps_description_and_untyped_alt():
    from typing import Literal

    from pydantic import BaseModel, Field

    class M(BaseModel):
        n: int | None = Field(description="count or null")
        tag: Literal["a", 1] | None = Field(description="mixed enum")  # no single "type"

    s = gemini_schema(M)
    assert s["properties"]["n"] == {"type": ["integer", "null"], "description": "count or null"}
    tag = s["properties"]["tag"]
    assert tag["description"] == "mixed enum"
    assert tag["anyOf"][1] == {"type": "null"}
    assert tag["anyOf"][0]["enum"] == ["a", 1]


def _probe(dir_, name, elapsed_ms):
    # Same layout tools/probe.py writes: top-level "receipt" = Receipt.model_dump().
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / f"{name}.json").write_text(json.dumps({
        "probe": name, "sdk_version": "2.33.0", "finished_at": "2026-10-25T12:00:00",
        "ok": True, "receipt": {"interaction_id": "i", "provider_model": "gemini-4-argon",
                                "status": "completed", "usage": {},
                                "elapsed_ms": elapsed_ms, "processing_calls": 0},
        "text": "{}", "step_types": ["model_output"]}))


def test_default_deadline_from_probe_files(tmp_path):
    probes = tmp_path / "runtime" / "probes"
    assert ex._default_deadline("static_hifps", probes) == 900.0  # no files: floor
    _probe(probes, "video_static", 400_000)    # 400 s
    _probe(probes, "video_agentic", 200_000)   # 200 s
    assert ex._default_deadline("static", probes) == 1200.0
    assert ex._default_deadline("agentic", probes) == 900.0     # 600 s -> floor
    assert ex._default_deadline("static_hifps", probes) == 1200.0  # 3 x max(400, 200)
    _probe(probes, "video_agentic", 500_000)
    assert ex._default_deadline("static_hifps", probes) == 1500.0
    (probes / "video_static.json").write_text('{"ok": false, "error": "x"}')  # failed probe
    assert ex._default_deadline("static", probes) == 900.0
    assert ex._default_deadline("static_hifps", probes) == 1500.0


# --- prompt ---------------------------------------------------------------------


def test_prompt_file_covers_brief():
    p = load_prompt().lower()
    for needle in ("+y", "+x", "heading_deg", "meters", "axis-aligned", "[x, y, w, h]",
                   "start_s", "end_s", "low_m", "high_m", "unknown", "furniture_seen",
                   "5", "8", "keyframe", "not instructions", "outside", "z1", "d1",
                   "stair", "exit", "opening", "{{duration_s}}", "{{anchor_hint}}"):
        assert needle in p, needle
