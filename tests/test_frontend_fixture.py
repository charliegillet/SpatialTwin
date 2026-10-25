"""Generates the frontend's vitest snapshot fixture from the real session API.

The session runs through ``walktwin.api`` with offline fakes only for Argon, SfM,
alignment and the managed agent; solve, check, check_graph, allowed_interventions,
the snapshot builder and every serializer are the real ones. Loop and agent
results are the real ``Iteration``/``GeometryScore``/``Investigation`` types.

    WALKTWIN_WRITE_FIXTURE=1 .venv/bin/python -m pytest tests/test_frontend_fixture.py

rewrites ``frontend/src/__fixtures__/snapshot.json``. Without the variable the
test checks that the committed fixture still has the same shape as a fresh one.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import time
from pathlib import Path

from fastapi.testclient import TestClient

from walktwin import api
from walktwin.agent import (Investigation, InterventionResult, LedgerEntry, Recommendation,
                            allowed_interventions, limiting_doors)
from walktwin.api import Services, get_services
from walktwin.checker import check_run
from walktwin.contracts import FlowParams, Scenario, VenueGraph
from walktwin.extract import ExtractionResult
from walktwin.flow import solve
from walktwin.geometry_score import Crossing, GeometryScore
from walktwin.graph_checks import check_graph
from walktwin.loop import Iteration
from walktwin.media import PreparedVideo
from walktwin.render import RenderedView

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "frontend" / "src" / "twin" / "__fixtures__" / "office_graph.json"
OUT = ROOT / "frontend" / "src" / "__fixtures__" / "snapshot.json"
FIXED_ID = "0000000000fa"
DURATION_S = 60.0

# the walker's path in graph metres: (t_s, x, y)
WAYPOINTS = [(0, 9, 1), (2, 9, 2), (11, 3, 5.4), (14, 1.5, 4), (18, 3, 4), (26, 12, 4),
             (31, 15, 2.6), (38, 16.5, 4), (42, 15, 4), (46.5, 6, 8), (50, 5, 9.5), (54, 5, 10)]


def _path(step: float = 0.5) -> list[tuple[float, float, float]]:
    out, t = [], 0.0
    while t <= WAYPOINTS[-1][0] + 1e-9:
        i = max(j for j in range(len(WAYPOINTS) - 1) if WAYPOINTS[j][0] <= t)
        i = min(i, len(WAYPOINTS) - 2)
        (t0, x0, y0), (t1, x1, y1) = WAYPOINTS[i], WAYPOINTS[i + 1]
        u = min(1.0, max(0.0, (t - t0) / (t1 - t0)))
        out.append((round(t, 2), round(x0 + u * (x1 - x0), 3), round(y0 + u * (y1 - y0), 3)))
        t += step
    return out


def _office() -> VenueGraph:
    return VenueGraph.model_validate_json(GRAPH.read_text())


class Offline:
    """Stands in for Argon, SfM and the managed agent; nothing touches the network."""

    def prepare_video(self, src: Path, out_dir: Path) -> PreparedVideo:
        out_dir.mkdir(parents=True, exist_ok=True)
        dst = out_dir / "prepared.mp4"
        shutil.copyfile(src, dst)
        return PreparedVideo(path=dst, sha256="fixture", duration_s=DURATION_S, width=1280, height=720)

    def run_sfm(self, video: PreparedVideo, work_dir: Path) -> dict:
        frames = [{"t_s": t, "center": [x, 1.5, y], "R": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                   "K": [[900, 0, 640], [0, 900, 360], [0, 0, 1]]} for t, x, y in _path()]
        return {"status": "completed", "frames": frames,
                "points": [[3.1, 1.0, 2.0], [14.9, 1.2, 6.0], [9.0, 0.8, 0.1]],
                "registered_fraction": 0.94, "elapsed_ms": 83000, "error": None}

    def fit_alignment(self, sfm, graph) -> dict:
        return {"scale": 1.0, "yaw_rad": 0.0, "tx": 0.0, "ty": 0.0,
                "floor_normal": [0.0, 1.0, 0.0], "floor_offset": 0.0,
                "residual_m": 0.21, "eye_height_m": 1.53, "hash": "a-fixture"}

    @staticmethod
    def to_graph_xy(alignment: dict, p) -> tuple[float, float]:
        return (float(p[0]), float(p[2]))

    async def extract(self, client, video, *, mode, deadline_s, anchor_hint=None):
        g = _office()
        return ExtractionResult(status="completed", graph=g, findings=check_graph(g, DURATION_S),
                                receipt=None, mode=mode, agentic_observed=None,
                                video_uri="files/fixture-video", error=None)

    async def refine(self, client, graph, video, extraction, *, sfm, alignment, base_url,
                     max_iterations=4, deadline_s):
        g1 = graph.model_copy(update={"zones": [
            z.model_copy(update={"furniture_seen": True}) if z.id == "Z4" else z for z in graph.zones]})
        g2 = g1.model_copy(update={"doors": [
            d.model_copy(update={"clear_width": d.clear_width.model_copy(update={"low_m": 0.95})})
            if d.id == "D4" else d for d in g1.doors]})
        rdir = video.path.parent / "renders"
        rdir.mkdir(parents=True, exist_ok=True)

        def renders(tag: str) -> list[RenderedView]:
            out = []
            for k in graph.keyframes:
                p = rdir / f"{tag}-t{k.t_s:g}.png"
                p.write_bytes(b"\x89PNG\r\n\x1a\n")
                out.append(RenderedView(t_s=k.t_s, path=p, kind="perspective"))
            top = rdir / f"{tag}-top.png"
            top.write_bytes(b"\x89PNG\r\n\x1a\n")
            return [*out, RenderedView(t_s=None, path=top, kind="top")]

        held = [5.5, 20.5, 33.0, 44.5]
        c = [Crossing(11.0, 3.0, 5.4, "Z1.west"), Crossing(31.0, 15.0, 2.6, "Z1.east"),
             Crossing(46.5, 6.0, 8.0, "Z1.north")]
        its = [
            Iteration(index=1, graph_revision=g1.revision, discrepancy_count=5, applied=[0, 1],
                      rejected=[(2, "unknown id D9")], findings=check_graph(g1, DURATION_S),
                      geometry=GeometryScore("a-fixture", c, 0.61, 0.29, 7.4, 0.48, held),
                      renders=renders("r1"), receipt=None, stop_reason=None),
            Iteration(index=2, graph_revision=g2.revision, discrepancy_count=1, applied=[0],
                      rejected=[(1, "measured_regression")], findings=check_graph(g2, DURATION_S),
                      geometry=GeometryScore("a-fixture", c[2:], 0.74, 0.16, 4.1, 0.63, held),
                      renders=renders("r2"), receipt=None, stop_reason="max_iterations"),
        ]
        return g2, its

    async def prepare_environment(self, client) -> str:
        return "env-fixture"

    async def render_topdown(self, graph, out_dir: Path, base_url: str, hazards) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        p = out_dir / "top.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n")
        return p

    async def investigate(self, client, graph, scenario, params: FlowParams, *, environment_id,
                          topdown_png, deadline_s=180, max_rounds=4) -> Investigation:
        await asyncio.sleep(0.01)
        base = solve(graph, scenario, params)
        results = []
        for iid in allowed_interventions(graph, scenario):
            s2 = scenario.model_copy(update={"interventions": [*scenario.interventions, iid]})
            run = solve(graph, s2, params)
            results.append(InterventionResult(
                intervention_id=iid, run_id=run.run_id, reached_exit=run.reached_exit,
                total=run.total, delta_vs_current=run.reached_exit - base.reached_exit,
                check_ok=check_run(graph, s2, params, run).ok,
                limiting_doors=limiting_doors(graph, run, params)))
        good = [r for r in results if r.check_ok and r.delta_vs_current > 0]
        best = max(good, key=lambda r: r.reached_exit) if good else None
        claimed = best.reached_exit - 2 if best else None
        rec = Recommendation(
            intervention_id=best.intervention_id if best else None, claimed_reached_exit=claimed,
            rationale="With that exit under fire the hall drains through fewer doors. Opening the "
                      "locked exit adds a direct way out of the hall.",
            caveats=["Door widths are estimated, not tape-measured"])
        ids = [r.intervention_id for r in results]
        ledger = [
            LedgerEntry(call_id="c1", kind="sandbox_step", name="code_execution",
                        args={"code": "from flow import solve\nfor iid in allowed: ..."},
                        result={"output": f"{ids} -> {claimed}"}, executed_at="2026-10-25T18:41:02Z"),
            LedgerEntry(call_id="c2", kind="client_function", name="evaluate_interventions",
                        args={"ids": ids}, result={"results": [r.model_dump() for r in results]},
                        executed_at="2026-10-25T18:41:09Z"),
            LedgerEntry(call_id="c3", kind="client_function", name="submit_recommendation",
                        args=rec.model_dump(), result={"ok": True}, executed_at="2026-10-25T18:41:12Z"),
        ]
        disagreement = (f"Agent claimed {claimed} for {best.intervention_id}; checker computed "
                        f"{best.reached_exit}") if best else None
        return Investigation(
            investigation_id=f"inv-{scenario.hash}", graph_revision=graph.revision,
            scenario_hash=scenario.hash, status="completed", interaction_id="int-agent",
            environment_id=environment_id, ledger=ledger, sandbox_runs=1, results=results,
            recommendation=rec, best=best, disagreement=disagreement, hook_denials=0, receipt=None)


def _generate(tmp_path: Path) -> dict:
    off = Offline()
    services = Services(
        runtime_root=tmp_path / "runtime", base_url="http://127.0.0.1:9",
        make_client=lambda: object(), prepare_video=off.prepare_video, run_sfm=off.run_sfm,
        fit_alignment=off.fit_alignment, to_graph_xy=off.to_graph_xy, extract=off.extract,
        refine=off.refine, prepare_environment=off.prepare_environment,
        investigate=off.investigate, render_topdown=off.render_topdown)
    services.store.new_id = staticmethod(lambda: FIXED_ID)  # stable ids in the fixture
    api.app.dependency_overrides[get_services] = lambda: services
    try:
        with TestClient(api.app) as c:
            def wait(pred, timeout=20.0) -> dict:
                end = time.monotonic() + timeout
                while True:
                    s = c.get(f"/api/sessions/{FIXED_ID}").json()
                    if pred(s):
                        return s
                    assert time.monotonic() < end, s["jobs"]
                    time.sleep(0.02)

            def idle(s):
                return all(j["status"] in ("done", "failed") for j in s["jobs"].values())

            r = c.post("/api/sessions", files={"video": ("walk.mp4", b"fixture", "video/mp4")})
            assert r.status_code == 201, r.text
            wait(lambda s: s["jobs"]["sfm"]["status"] == "done")
            assert c.post(f"/api/sessions/{FIXED_ID}/extract", json={"mode": "static_hifps"}).status_code == 202
            s = wait(lambda s: s["draft_revision"] and idle(s))
            r = c.post(f"/api/sessions/{FIXED_ID}/refine", json={"expected_revision": s["draft_revision"]})
            assert r.status_code == 202, r.text
            s = wait(lambda s: len(s["iterations"]) == 2 and idle(s))
            r = c.post(f"/api/sessions/{FIXED_ID}/accept", json={"expected_revision": s["draft_revision"]})
            assert r.status_code == 200, r.text
            s = wait(lambda s: idle(s) and len(s["investigations"]) == 3)
            r = c.post(f"/api/sessions/{FIXED_ID}/scenario", json={
                "expected_revision": s["accepted_revision"],
                "hazards": [{"door_id": "D2", "kind": "fire", "from_s": 0}]})
            assert r.status_code == 200, r.text
            snap = c.get(f"/api/sessions/{FIXED_ID}").json()
    finally:
        api.app.dependency_overrides.clear()
    for j in snap["jobs"].values():  # wall-clock noise
        j["started_at"] = j["finished_at"] = "2026-10-25T18:40:00+0000"
    snap["created_at"] = "2026-10-25T18:39:00+0000"
    # server-side render paths: keep them relative so no local tmp path lands in the fixture
    text = json.dumps(snap).replace(str((tmp_path / "runtime").resolve()) + "/", "runtime/")
    return json.loads(text.replace(str(tmp_path / "runtime") + "/", "runtime/"))


def _shape(v):
    if isinstance(v, dict):
        return {k: _shape(x) for k, x in sorted(v.items())}
    if isinstance(v, list):
        return [_shape(v[0])] if v else []
    return type(v).__name__ if not isinstance(v, (int, float)) or isinstance(v, bool) else "number"


def test_frontend_snapshot_fixture(tmp_path):
    snap = _generate(tmp_path)
    assert snap["ready_investigation_id"] is not None
    assert snap["current_check"]["run_id"] == snap["current_run"]["run_id"]
    assert len(snap["ghost_path"]) > 10
    assert all(r.get("url") for it in snap["iterations"] for r in it["renders"])
    if os.environ.get("WALKTWIN_WRITE_FIXTURE") == "1":
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(snap, indent=1) + "\n")
    committed = json.loads(OUT.read_text())
    assert _shape(committed) == _shape(snap), "re-run with WALKTWIN_WRITE_FIXTURE=1"
