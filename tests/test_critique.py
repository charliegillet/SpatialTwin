import base64
import json

import pytest
from google.genai._gaos.types.interactions.imagecontent import ImageContent
from google.genai._gaos.types.interactions.staticmediaprocessing import StaticMediaProcessing
from google.genai._gaos.types.interactions.videocontent import VideoContent
from pydantic import TypeAdapter

from fakes import FakeClient, text_step
from walktwin import critique as cq
from walktwin.critique import (CritiqueResult, Discrepancy, critique, critique_schema,
                               load_prompt)
from walktwin.patch import PatchOp, RemoveDoor, UpdateDoor

URI = "https://fake.test/files/fake123"
PNG = b"\x89PNG\r\n\x1a\nrender"
JPG = b"\xff\xd8\xffframe"


@pytest.fixture
def images(tmp_path):
    pairs = []
    for i, t in enumerate((2.0, 14.0)):
        f = tmp_path / f"frame_{i}.jpg"
        r = tmp_path / f"render_{i}.png"
        f.write_bytes(JPG)
        r.write_bytes(PNG)
        pairs.append((f, r, t))
    top = tmp_path / "top.png"
    top.write_bytes(PNG + b"top")
    return pairs, top


def reply(discrepancies=(), ops=(), iid="crit-1") -> list:
    body = {"discrepancies": list(discrepancies), "ops": list(ops)}
    return [{"status": "completed", "id": iid, "model": "gemini-4-argon",
             "steps": [text_step(json.dumps(body))]}]


DISC = [{"t_s": 36.0, "element_id": "D2", "description": "exit shown closed, video shows it open"}]
TWO_OPS = [
    {"op": "update_door", "id": "D2", "state": "open", "cite_t_s": 36.0,
     "reason": "door stands open at 0:36", "position": None, "door": None},
    {"op": "remove_door", "id": "D5", "cite_t_s": 51.5, "reason": "no door visible on south wall"},
]


async def _run(client, graph, images, **kw):
    pairs, top = images
    kw.setdefault("previous_interaction_id", "ext-1")
    return await critique(client, graph, pairs, video_uri=URI, topdown=top,
                          deadline_s=5, **kw)


# --- brief tests ----------------------------------------------------------------


async def test_critique_parses_ops(office_graph, images):
    client = FakeClient(reply(DISC, TWO_OPS))
    r = await _run(client, office_graph, images)
    assert isinstance(r, CritiqueResult)
    assert r.status == "completed"
    assert r.discrepancies == [Discrepancy(t_s=36.0, element_id="D2",
                                           description=DISC[0]["description"])]
    assert len(r.ops) == 2
    TypeAdapter(list[PatchOp]).validate_python([o.model_dump() for o in r.ops])
    assert isinstance(r.ops[0], UpdateDoor) and r.ops[0].state == "open"
    assert isinstance(r.ops[1], RemoveDoor) and r.ops[1].cite_t_s == 51.5
    assert r.interaction_id == "crit-1"
    assert r.receipt.interaction_id == "crit-1"


async def test_critique_chains_previous_interaction(office_graph, images):
    client = FakeClient(reply(DISC, TWO_OPS, iid="crit-1"), reply(DISC, [], iid="crit-2"))
    r1 = await _run(client, office_graph, images, previous_interaction_id="ext-1")
    r2 = await _run(client, office_graph, images, previous_interaction_id=r1.interaction_id)
    assert r2.interaction_id == "crit-2"
    first, second = client.requests
    assert first["previous_interaction_id"] == "ext-1"
    assert second["previous_interaction_id"] == "crit-1"
    top_b64 = base64.b64encode(images[1].read_bytes()).decode()
    for req in client.requests:
        assert any(p["type"] == "image" and p["data"] == top_b64 for p in req["input"])
        texts = [p["text"] for p in req["input"] if p["type"] == "text"]
        assert "TOP-DOWN PLAN" in texts
        # the video stays server-side: no video part without zoom
        assert not any(p["type"] == "video" for p in req["input"])


# --- request shape --------------------------------------------------------------


async def test_critique_request_shape(office_graph, images):
    client = FakeClient(reply())
    await _run(client, office_graph, images)
    req = client.requests[0]
    assert req["model"] == "gemini-4-argon"
    assert req["background"] is True and req["store"] is True
    assert req["generation_config"]["thinking_level"] == "high"
    assert req["generation_config"]["max_output_tokens"] == 65536
    assert req["response_format"]["mime_type"] == "application/json"
    inp = req["input"]
    kinds = [(p["type"], p.get("text") if p["type"] == "text" else p.get("mime_type"))
             for p in inp]
    assert kinds[:10] == [
        ("text", "t=2 VIDEO"), ("image", "image/jpeg"), ("text", "RENDER"), ("image", "image/png"),
        ("text", "t=14 VIDEO"), ("image", "image/jpeg"), ("text", "RENDER"), ("image", "image/png"),
        ("text", "TOP-DOWN PLAN"), ("image", "image/png"),
    ]
    assert inp[1]["data"] == base64.b64encode(JPG).decode()
    graph_text, prompt = inp[-2]["text"], inp[-1]["text"]
    assert office_graph.revision in graph_text
    assert json.loads(graph_text.split("\n", 1)[1]) == office_graph.model_dump(mode="json")
    assert prompt == load_prompt()
    for p in inp:
        if p["type"] == "image":
            ImageContent.model_validate(p)


async def test_zoom_parts_only_when_enabled(office_graph, images):
    client = FakeClient(reply(), reply())
    zoom = [("D2", 33.0, 47.0)]
    await _run(client, office_graph, images, zoom=zoom)
    assert not any(p["type"] == "video" for p in client.requests[0]["input"])
    await _run(client, office_graph, images, zoom=zoom, zoom_enabled=True)
    inp = client.requests[1]["input"]
    vids = [i for i, p in enumerate(inp) if p["type"] == "video"]
    assert len(vids) == 1
    part = inp[vids[0]]
    top_idx = next(i for i, p in enumerate(inp) if p.get("text") == "TOP-DOWN PLAN")
    assert top_idx + 1 < vids[0] < len(inp) - 2  # after top-down image, before graph+prompt
    assert part == {"type": "video", "uri": URI, "mime_type": "video/mp4", "resolution": "high",
                    "processing": {"type": "static", "fps": 5,
                                   "start_offset": "33.0s", "end_offset": "47.0s"}}
    VideoContent.model_validate(part)
    StaticMediaProcessing.model_validate(part["processing"])


def test_schema_uses_supported_keywords_only():
    allowed = {"type", "properties", "required", "items", "enum", "description",
               "minItems", "maxItems"}

    def walk(node):
        assert set(node) <= allowed, set(node) - allowed
        for sub in (node.get("properties") or {}).values():
            walk(sub)
        if "items" in node:
            walk(node["items"])

    s = critique_schema()
    walk(s)
    op = s["properties"]["ops"]["items"]
    assert set(op["properties"]["op"]["enum"]) == {
        "add_door", "remove_door", "update_door", "add_zone", "update_zone", "remove_zone"}
    assert {"op", "cite_t_s", "reason"} <= set(op["required"])


def test_prompt_covers_conventions():
    p = load_prompt().lower()
    for needle in ("top-down", "+y", "+x", "clockwise", "[x, y, w, h]", "cite_t_s",
                   "not instructions", "invent"):
        assert needle in p, needle


async def test_too_many_pairs_raises(office_graph, images):
    pairs, top = images
    with pytest.raises(ValueError):
        await critique(FakeClient(), office_graph, pairs * 5, previous_interaction_id="e",
                       video_uri=URI, topdown=top, deadline_s=5)


# --- failures stay failures -------------------------------------------------------


async def test_critique_failed_status(office_graph, images, monkeypatch):
    monkeypatch.setattr(cq, "POLL_S", 0.001)
    client = FakeClient(["in_progress", {"status": "failed", "steps": [
        text_step(json.dumps({"discrepancies": DISC, "ops": TWO_OPS}))]}])
    r = await _run(client, office_graph, images)
    assert r.status == "failed" and r.ops == [] and r.discrepancies == []
    assert r.receipt.status == "failed"


async def test_critique_timeout(office_graph, images, monkeypatch):
    monkeypatch.setattr(cq, "POLL_S", 0.01)
    client = FakeClient(["in_progress"])
    pairs, top = images
    r = await critique(client, office_graph, pairs, previous_interaction_id="e",
                       video_uri=URI, topdown=top, deadline_s=0.05)
    assert r.status == "timeout" and r.receipt is None and r.interaction_id is None
    assert len(client.cancel_calls) == 1


async def test_critique_invalid_json(office_graph, images):
    client = FakeClient([{"status": "completed", "steps": [text_step("not json")]}])
    r = await _run(client, office_graph, images)
    assert r.status == "invalid" and r.ops == []
    assert r.receipt is not None


async def test_critique_drops_malformed_op(office_graph, images):
    bad = {"op": "add_door", "door": None, "cite_t_s": 3, "reason": "missing door"}
    client = FakeClient(reply(DISC, [bad, TWO_OPS[1]]))
    r = await _run(client, office_graph, images)
    assert r.status == "completed"
    assert [type(o) for o in r.ops] == [RemoveDoor]
    assert [i for i, _ in r.dropped_ops] == [0]
