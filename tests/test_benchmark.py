from walktwin.benchmark import AnswerKey, BenchmarkScore, KeyDoor, score
from walktwin.contracts import Door, Evidence, Measure


def _door(did, kind, ev, width=(1.0, 1.0)):
    return Door(
        id=did, a="Z1", b="OUTSIDE" if kind == "exit" else "Z2", kind=kind, state="open",
        clear_width=Measure(low_m=width[0], high_m=width[1], basis="estimated"),
        position=(0.0, 0.0),
        evidence=[Evidence(start_s=s, end_s=e, note="x") for s, e in ev],
    )


def _graph(base, doors):
    return base.model_copy(update={"doors": doors})


def _key(doors):
    return AnswerKey(venue="v", video_sha256="0" * 64, source="tape", doors=doors)


def test_perfect_match(office_graph):
    g = _graph(office_graph, [_door("D1", "door", [(9, 11)]), _door("D2", "door", [(19, 21)]),
                              _door("D3", "exit", [(29, 31)])])
    key = _key([KeyDoor(t_s=10, kind="door", measured_width_m=None),
                KeyDoor(t_s=20, kind="door", measured_width_m=None),
                KeyDoor(t_s=30, kind="exit", measured_width_m=None)])
    s = score(g, key)
    assert isinstance(s, BenchmarkScore)
    assert (s.door_precision, s.door_recall, s.door_f1, s.exit_recall) == (1.0, 1.0, 1.0, 1.0)
    assert sorted(s.matched) == [("D1", 0), ("D2", 1), ("D3", 2)]
    assert s.width_mae_m is None


def test_kind_mismatch_not_matched(office_graph):
    g = _graph(office_graph, [_door("D1", "door", [(9, 11)])])
    s = score(g, _key([KeyDoor(t_s=10, kind="exit", measured_width_m=None)]))
    assert s.matched == [] and s.door_f1 == 0.0 and s.exit_recall == 0.0
    # opening is compatible with door
    s2 = score(g, _key([KeyDoor(t_s=10, kind="opening", measured_width_m=None)]))
    assert s2.matched == [("D1", 0)]


def test_tolerance(office_graph):
    g = _graph(office_graph, [_door("D1", "door", [(12.5, 13)])])
    key = _key([KeyDoor(t_s=15, kind="door", measured_width_m=None)])
    assert score(g, key, tolerance_s=2.0).matched == [("D1", 0)]
    assert score(g, key, tolerance_s=1.0).matched == []


def test_width_mae(office_graph):
    g = _graph(office_graph, [_door("D1", "door", [(9, 11)], (0.9, 0.9)),
                              _door("D2", "door", [(19, 21)], (1.0, 1.2))])
    key = _key([KeyDoor(t_s=10, kind="door", measured_width_m=0.85),
                KeyDoor(t_s=20, kind="door", measured_width_m=0.95)])
    assert abs(score(g, key).width_mae_m - 0.10) < 1e-9


def test_empty_never_divides_by_zero(office_graph):
    g = _graph(office_graph, [])
    s = score(g, _key([]))
    assert (s.door_precision, s.door_recall, s.door_f1, s.exit_recall) == (0.0, 0.0, 0.0, 0.0)


def test_greedy_one_to_one_tie_break(office_graph):
    # D1 and D2 both cover key 0 at the same distance; D1 wins by id; D2 stays unmatched.
    g = _graph(office_graph, [_door("D2", "door", [(9, 11)]), _door("D1", "door", [(9, 11)])])
    s = score(g, _key([KeyDoor(t_s=10, kind="door", measured_width_m=None)]))
    assert s.matched == [("D1", 0)]
    assert s.door_precision == 0.5 and s.door_recall == 1.0


# ---- CLI ------------------------------------------------------------------------------
import argparse
import json
import types

import pytest

from walktwin import benchmark
from walktwin.benchmark import mode_label


def test_mode_is_required():
    with pytest.raises(Exception):
        BenchmarkScore(door_precision=0, door_recall=0, door_f1=0, exit_recall=0)


def test_mode_label():
    assert mode_label("agentic", False) == "agentic (not observed)"
    assert mode_label("agentic", True) == "agentic"
    assert mode_label("agentic", None) == "agentic"
    assert mode_label("agentic_loop", False) == "agentic_loop"
    assert mode_label("static", None) == "static"


class _Receipt:
    def model_dump(self, mode="json"):
        return {"interaction_id": "i1"}


def _setup(tmp_path, monkeypatch, office_graph, *, sfm_status="completed", graph_none=False,
           geometry=True):
    bench = tmp_path / "bench" / "v"
    bench.mkdir(parents=True, exist_ok=True)
    key = _key([KeyDoor(t_s=10, kind="door", measured_width_m=None)])
    (bench / "answer_key.json").write_text(key.model_dump_json())
    g = _graph(office_graph, [_door("D1", "door", [(9, 11)])])
    calls = {"extract": [], "refine": 0}

    async def fake_extract(client, video, *, mode, deadline_s):
        calls["extract"].append(mode)
        return types.SimpleNamespace(
            status="failed" if graph_none else "completed", graph=None if graph_none else g,
            receipt=_Receipt(), agentic_observed=True if mode == "agentic" else None,
            error="boom" if graph_none else None)

    async def fake_refine(client, graph, video, extraction, **kw):
        calls["refine"] += 1
        geo = types.SimpleNamespace(illegal_crossings=[1, 2]) if geometry else None
        return graph, [types.SimpleNamespace(geometry=geo)]

    from walktwin import extract, genai_client, loop, media, sfm
    monkeypatch.setattr(extract, "extract_venue", fake_extract)
    monkeypatch.setattr(loop, "refine_graph", fake_refine)
    monkeypatch.setattr(sfm, "run_sfm", lambda v, w: types.SimpleNamespace(
        status=sfm_status, error=None if sfm_status == "completed" else "no_floor_plane"))
    monkeypatch.setattr(sfm, "fit_alignment", lambda s, g: object())
    monkeypatch.setattr(genai_client, "make_client", lambda: object())
    monkeypatch.setattr(media, "prepare_video", lambda raw, work: types.SimpleNamespace(
        sha256=key.video_sha256, duration_s=30.0))
    args = argparse.Namespace(venue=str(bench), modes="static,agentic,agentic_loop", video=None,
                              out=str(tmp_path / "out"), tolerance_s=2.0, deadline_s=5.0,
                              base_url="http://x")
    return args, calls


def test_run_cli_awaits_and_writes(tmp_path, monkeypatch, office_graph):
    args, calls = _setup(tmp_path, monkeypatch, office_graph)
    assert benchmark.run_cli(args) == 0
    data = json.loads((tmp_path / "out" / "v.json").read_text())
    rows = {r["mode"]: r for r in data["rows"]}
    assert set(rows) == {"static", "agentic", "agentic_loop"}
    assert rows["agentic_loop"]["score"]["door_f1"] == 1.0
    assert rows["agentic_loop"]["score"]["final_illegal_crossings"] == 2
    assert rows["agentic_loop"]["geometry"]["available"] is True
    assert calls["extract"] == ["static", "agentic"]  # agentic extraction reused by the loop
    assert calls["refine"] == 1
    assert "agentic_loop_base_extraction" in rows["agentic_loop"]["receipt"]


def test_run_cli_failed_sfm_and_no_geometry(tmp_path, monkeypatch, office_graph):
    args, _ = _setup(tmp_path, monkeypatch, office_graph, sfm_status="failed")
    args.modes = "agentic_loop"
    assert benchmark.run_cli(args) == 0
    row = json.loads((tmp_path / "out" / "v.json").read_text())["rows"][0]
    assert row["geometry"]["available"] is False and "no_floor_plane" in row["geometry"]["reason"]
    assert row["score"]["final_illegal_crossings"] is None

    args, _ = _setup(tmp_path, monkeypatch, office_graph, geometry=False)
    args.modes = "agentic_loop"
    benchmark.run_cli(args)
    row = json.loads((tmp_path / "out" / "v.json").read_text())["rows"][0]
    assert row["score"]["final_illegal_crossings"] is None


def test_run_cli_graph_none_and_bad_modes(tmp_path, monkeypatch, office_graph):
    args, calls = _setup(tmp_path, monkeypatch, office_graph, graph_none=True)
    args.modes = "static,agentic_loop"
    assert benchmark.run_cli(args) == 0
    rows = json.loads((tmp_path / "out" / "v.json").read_text())["rows"]
    assert all(r["score"] is None and "boom" in r["error"] for r in rows)
    assert calls["refine"] == 0

    args, calls = _setup(tmp_path, monkeypatch, office_graph)
    args.modes = "static,bogus"
    with pytest.raises(SystemExit):
        benchmark.run_cli(args)
    assert calls["extract"] == []
