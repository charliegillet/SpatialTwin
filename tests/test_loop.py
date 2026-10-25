import json
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import pytest

from fakes import FakeClient, text_step
from walktwin import loop as lp
from walktwin.contracts import VenueGraph
from walktwin.extract import ExtractionResult
from walktwin.genai_client import Receipt
from walktwin.loop import Iteration, refine, refine_graph
from walktwin.media import PreparedVideo
from walktwin.render import RenderedView
from walktwin.sfm import Alignment, SfmFrame, SfmResult

D7 = {"id": "D7", "a": "Z4", "b": "OUTSIDE", "kind": "exit", "state": "open",
      "clear_width": {"low_m": 0.9, "high_m": 1.0, "basis": "estimated"},
      "position": [3.0, 9.5],
      "evidence": [{"start_s": 20, "end_s": 22, "note": "exit at back of green room"}]}
DISC = {"t_s": 21.0, "element_id": "D7", "description": "exit visible in video, absent in twin"}


def reply(discrepancies=(), ops=(), iid=None) -> list:
    state = {"status": "completed", "model": "gemini-4-argon",
             "steps": [text_step(json.dumps({"discrepancies": list(discrepancies),
                                             "ops": list(ops)}))]}
    if iid:
        state["id"] = iid
    return [state]


def add_d7(iid=None):
    return reply([DISC], [{"op": "add_door", "door": D7, "cite_t_s": 21, "reason": "exit sign"}], iid)


def remove_d7(iid=None):
    return reply([DISC], [{"op": "remove_door", "id": "D7", "cite_t_s": 21, "reason": "no door"}], iid)


# --- fakes --------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def fake_media(monkeypatch):
    calls = {"render": [], "frames": []}

    async def render_views(graph, out_dir, base_url, hazards=()):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        calls["render"].append(graph.revision)
        views = []
        for i, k in enumerate(graph.keyframes):
            p = out_dir / f"view_{i:02d}.png"
            p.write_bytes(b"png" + graph.revision.encode())
            views.append(RenderedView(t_s=k.t_s, path=p, kind="perspective"))
        top = out_dir / "view_top.png"
        top.write_bytes(b"top" + graph.revision.encode())
        views.append(RenderedView(t_s=None, path=top, kind="top"))
        return views

    def extract_frame(video, t_s, out):
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_bytes(b"jpg")
        calls["frames"].append(t_s)
        return Path(out)

    monkeypatch.setattr(lp, "render_views", render_views)
    monkeypatch.setattr(lp, "extract_frame", extract_frame)
    monkeypatch.setattr(lp.critique_mod, "POLL_S", 0.001)
    return calls


@dataclass(frozen=True)
class FakeScore:
    alignment_hash: str
    illegal_crossings: list = field(default_factory=list)
    wall_support: float = 1.0
    unexplained_points: int = 0
    edge_chamfer_px: float | None = None
    edge_within_5px: float | None = None
    heldout_t_s: list = field(default_factory=list)


PATH_DOORS = {"D1", "D3"}  # doors the walker's SfM path passes through


@pytest.fixture
def fake_geometry(monkeypatch):
    calls = []

    def score_geometry(graph, sfm, alignment, video=None, heldout_t_s=[]):
        calls.append({"revision": graph.revision, "heldout": list(heldout_t_s),
                      "alignment": alignment.hash})
        present = {d.id for d in graph.doors}
        return FakeScore(alignment_hash=alignment.hash,
                         illegal_crossings=sorted(PATH_DOORS - present),
                         heldout_t_s=list(heldout_t_s))

    def is_regression(before, after):
        return len(after.illegal_crossings) > len(before.illegal_crossings)

    mod = SimpleNamespace(score_geometry=score_geometry, is_regression=is_regression,
                          calls=calls)
    monkeypatch.setattr(lp, "geometry_score", mod)
    return mod


@pytest.fixture
def video(tmp_path) -> PreparedVideo:
    p = tmp_path / "prepared.mp4"
    p.write_bytes(b"\x00")
    return PreparedVideo(path=p, sha256="a" * 64, duration_s=60.0, width=1280, height=720)


@pytest.fixture
def extraction(office_graph) -> ExtractionResult:
    receipt = Receipt(interaction_id="ext-1", provider_model="gemini-4-argon",
                      status="completed", usage={}, elapsed_ms=1, processing_calls=0)
    return ExtractionResult(status="completed", graph=office_graph, findings=[],
                            receipt=receipt, mode="static_hifps", agentic_observed=None,
                            video_uri="https://fake.test/files/fake123", error=None)


@pytest.fixture
def sfm() -> SfmResult:
    # frames every 1 s; keyframes are at 2, 14, 26, 38, 50
    frames = [SfmFrame(t_s=float(t), center=(0.0, 0.0, 0.0),
                       R=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                       K=[[1, 0, 0], [0, 1, 0], [0, 0, 1]]) for t in range(0, 60)]
    return SfmResult(status="completed", frames=frames, points=[], registered_fraction=1.0,
                     elapsed_ms=1, error=None)


@pytest.fixture
def alignment() -> Alignment:
    return Alignment(scale=1.0, yaw_rad=0.0, tx=0.0, ty=0.0, floor_normal=(0.0, -1.0, 0.0),
                     floor_offset=1.5, residual_m=0.1, eye_height_m=1.5, hash="align-frozen")


async def _refine(client, office_graph, video, extraction, *, sfm=None, alignment=None,
                  tmp_path=None, **kw):
    return await refine(client, office_graph, video, extraction, sfm=sfm, alignment=alignment,
                        base_url="http://127.0.0.1:4173", deadline_s=30,
                        work_dir=tmp_path, **kw)


# --- brief tests ----------------------------------------------------------------


async def test_loop_stops_on_repeated_revision(office_graph, video, extraction, tmp_path):
    client = FakeClient(add_d7(), remove_d7(), add_d7(), remove_d7())
    its = await _refine(client, office_graph, video, extraction, tmp_path=tmp_path)
    assert len(its) <= 3
    assert its[-1].stop_reason == "repeated_revision"
    assert all(it.stop_reason is None for it in its[:-1])
    assert its[0].applied == [0]
    assert [it.index for it in its] == list(range(len(its)))


async def test_loop_rejects_measured_regression(office_graph, video, extraction, sfm,
                                                alignment, fake_geometry, tmp_path):
    remove_d1 = reply([{"t_s": 33, "element_id": "D1", "description": "no door at 0:33"}],
                      [{"op": "remove_door", "id": "D1", "cite_t_s": 33, "reason": "wall only"}])
    client = FakeClient(remove_d1)
    graph, its = await refine_graph(client, office_graph, video, extraction, sfm=sfm,
                                    alignment=alignment, base_url="http://127.0.0.1:4173",
                                    deadline_s=30, work_dir=tmp_path)
    assert len(its) == 1
    it = its[0]
    assert it.stop_reason == "measured_regression"
    assert it.applied == []
    assert it.rejected == [(0, "measured_regression")]
    assert it.graph_revision == office_graph.revision
    assert graph.revision == office_graph.revision
    assert it.geometry.illegal_crossings == []  # the kept graph's measured score
    assert it.rejected_geometry.illegal_crossings == ["D1"]
    # alignment stays frozen, held-out frames exclude anything within 1 s of a keyframe
    assert {c["alignment"] for c in fake_geometry.calls} == {"align-frozen"}
    held = fake_geometry.calls[0]["heldout"]
    kfs = [k.t_s for k in office_graph.keyframes]
    assert held and all(min(abs(t - k) for k in kfs) > 1.0 for t in held)
    assert 3.0 not in held and 4.0 in held


async def test_loop_stops_no_discrepancies(office_graph, video, extraction, tmp_path,
                                           fake_media):
    client = FakeClient(reply())
    its = await _refine(client, office_graph, video, extraction, tmp_path=tmp_path)
    assert len(its) == 1
    assert its[0].stop_reason == "no_discrepancies"
    assert its[0].discrepancy_count == 0
    assert its[0].graph_revision == office_graph.revision
    assert its[0].receipt is not None
    assert len(its[0].renders) == len(office_graph.keyframes) + 1
    assert fake_media["frames"] == [k.t_s for k in office_graph.keyframes]


async def test_loop_provider_failure_keeps_last_graph(office_graph, video, extraction, tmp_path):
    client = FakeClient(add_d7(iid="crit-1"), [{"status": "failed"}])
    graph, its = await refine_graph(client, office_graph, video, extraction, sfm=None,
                                    alignment=None, base_url="http://127.0.0.1:4173",
                                    deadline_s=30, work_dir=tmp_path)
    assert [it.stop_reason for it in its] == [None, "provider_failed"]
    assert any(d.id == "D7" for d in graph.doors)
    assert its[1].graph_revision == graph.revision == its[0].graph_revision
    assert its[1].receipt.status == "failed"
    # chaining: round 1 from the extraction, round 2 from round 1's critique
    assert client.requests[0]["previous_interaction_id"] == "ext-1"
    assert client.requests[1]["previous_interaction_id"] == "crit-1"


async def test_loop_without_sfm_labels_unavailable(office_graph, video, extraction, tmp_path):
    client = FakeClient(add_d7(), reply())
    its = await _refine(client, office_graph, video, extraction, tmp_path=tmp_path)
    assert len(its) == 2
    assert all(it.geometry is None for it in its)
    assert lp.LABELS == {"discrepancy_count": "model-reported", "geometry": "measured"}


# --- extra coverage ---------------------------------------------------------------


async def test_loop_no_ops_applied(office_graph, video, extraction, tmp_path):
    bad = reply([DISC], [{"op": "update_door", "id": "D9", "state": "open", "cite_t_s": 3,
                          "reason": "r"}])
    client = FakeClient(bad)
    its = await _refine(client, office_graph, video, extraction, tmp_path=tmp_path)
    assert its[0].stop_reason == "no_ops_applied"
    assert its[0].rejected and "unknown id" in its[0].rejected[0][1]
    assert its[0].discrepancy_count == 1


async def test_loop_max_iterations_with_geometry(office_graph, video, extraction, sfm,
                                                 alignment, fake_geometry, tmp_path):
    def open_door(ident, state):
        return reply([{"t_s": 50, "element_id": ident, "description": "state differs"}],
                     [{"op": "update_door", "id": ident, "state": state, "cite_t_s": 50,
                       "reason": "seen"}])
    client = FakeClient(open_door("D5", "open"), open_door("D5", "closed"))
    its = await _refine(client, office_graph, video, extraction, sfm=sfm,
                        alignment=alignment, tmp_path=tmp_path, max_iterations=2)
    assert [it.stop_reason for it in its] == [None, "max_iterations"]
    assert all(it.geometry is not None and it.geometry.alignment_hash == "align-frozen"
               for it in its)


async def test_loop_zoom_next_round_for_discrepant_doors(office_graph, video, extraction,
                                                         tmp_path):
    first = reply([{"t_s": 36, "element_id": "D2", "description": "exit differs"}],
                  [{"op": "update_door", "id": "D2", "state": "closed", "cite_t_s": 36,
                    "reason": "closed"}])
    client = FakeClient(first, reply())
    await _refine(client, office_graph, video, extraction, tmp_path=tmp_path,
                  zoom_enabled=True)
    assert not any(p["type"] == "video" for p in client.requests[0]["input"])
    vids = [p for p in client.requests[1]["input"] if p["type"] == "video"]
    assert [v["processing"]["start_offset"] for v in vids] == ["33.0s"]  # D2 evidence 35-45
    assert [v["processing"]["end_offset"] for v in vids] == ["47.0s"]


async def test_loop_zoom_off_by_default(office_graph, video, extraction, tmp_path):
    first = reply([{"t_s": 36, "element_id": "D2", "description": "exit differs"}],
                  [{"op": "update_door", "id": "D2", "state": "closed", "cite_t_s": 36,
                    "reason": "closed"}])
    client = FakeClient(first, reply())
    await _refine(client, office_graph, video, extraction, tmp_path=tmp_path)
    assert not any(p["type"] == "video" for r in client.requests for p in r["input"])


async def test_refine_needs_extraction_interaction(office_graph, video, extraction, tmp_path):
    bad = extraction.model_copy(update={"receipt": None})
    with pytest.raises(ValueError):
        await _refine(FakeClient(), office_graph, video, bad, tmp_path=tmp_path)
