"""Session API tests: FastAPI TestClient with fakes injected via dependency_overrides.

No network, Argon, pycolmap or Playwright is touched: every job runner and the
genai client factory come from ``Services`` built here.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from walktwin import api
from walktwin.api import Services, create_app, get_services
from walktwin.checker import check_run
from walktwin.contracts import FlowParams, Hazard, Scenario, VenueGraph
from walktwin.extract import ExtractionResult
from walktwin.flow import solve
from walktwin.graph_checks import check_graph
from walktwin.media import PreparedVideo, prepare_video
from walktwin.sessions import SessionStore

FIXTURES = Path(__file__).parent / "fixtures"
SHA = "b" * 64


def _office() -> VenueGraph:
    return VenueGraph.model_validate_json((FIXTURES / "office_graph.json").read_text())


def _fire(*door_ids: str, interventions: tuple[str, ...] = ()) -> Scenario:
    return Scenario(hazards=[Hazard(door_id=d, kind="fire") for d in door_ids],
                    interventions=list(interventions))


class Fakes:
    """Records calls; behaviour knobs are plain attributes."""

    def __init__(self) -> None:
        self.sfm_calls: list[Path] = []
        self.extract_calls: list[str] = []
        self.refine_calls: list[dict] = []
        self.fit_calls = 0
        self.investigate_calls: list[Scenario] = []
        self.active = 0
        self.max_active = 0
        self.check_ok = True
        self.block_extract = threading.Event()
        self.block_extract.set()  # set = do not block
        self.block_refine = threading.Event()
        self.block_refine.set()
        self.block_investigate = threading.Event()
        self.block_investigate.set()
        self.extract_status = "completed"
        self.investigations_completed = 0
        self.badge = "agrees"
        self.env_calls = 0
        self.env_kwargs: list[dict] = []
        self.notes: list[tuple] = []
        self.block_sfm = threading.Event()
        self.block_sfm.set()
        self.block_fit = threading.Event()
        self.block_fit.set()
        self.fit_started = threading.Event()
        self.score_calls: list[tuple[str, str]] = []  # (graph revision, alignment hash)

    # -- runners ------------------------------------------------------------
    def prepare_video(self, src: Path, out_dir: Path) -> PreparedVideo:
        out_dir.mkdir(parents=True, exist_ok=True)
        dst = out_dir / "prepared.mp4"
        shutil.copyfile(src, dst)
        return PreparedVideo(path=dst, sha256=SHA, duration_s=60.0, width=64, height=64)

    def run_sfm(self, video: PreparedVideo, work_dir: Path) -> dict:
        self.sfm_calls.append(work_dir)
        self.block_sfm.wait(10)
        frames = [{"t_s": t, "center": [t, 1.0, 0.0], "R": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                   "K": [[500, 0, 32], [0, 500, 32], [0, 0, 1]]} for t in (0.0, 0.5, 1.0)]
        return {"status": "completed", "frames": frames, "points": [[0.0, 0.0, 0.0]],
                "registered_fraction": 1.0, "elapsed_ms": 5, "error": None}

    def fit_alignment(self, sfm, graph) -> dict:
        self.fit_calls += 1
        self.fit_started.set()
        self.block_fit.wait(10)
        return {"scale": 2.0, "yaw_rad": 0.0, "tx": 1.0, "ty": 0.0,
                "floor_normal": [0.0, 0.0, 1.0], "floor_offset": 0.0,
                "residual_m": 0.1, "eye_height_m": 1.5, "hash": f"al-{self.fit_calls}"}

    @staticmethod
    def to_graph_xy(alignment: dict, p) -> tuple[float, float]:
        return (p[0] * alignment["scale"] + alignment["tx"], p[1] * alignment["scale"])

    async def extract(self, client, video, *, mode, deadline_s, anchor_hint=None):
        self.extract_calls.append(mode)
        while not self.block_extract.is_set():
            await asyncio.sleep(0.01)
        g = _office().model_copy(update={"video_sha256": video.sha256})
        if self.extract_status != "completed":
            return ExtractionResult(status=self.extract_status, graph=None, findings=[],
                                    receipt=None, mode=mode, agentic_observed=None,
                                    video_uri=None, error="provider status failed")
        return ExtractionResult(status="completed", graph=g,
                                findings=check_graph(g, video.duration_s), receipt=None,
                                mode=mode, agentic_observed=None,
                                video_uri="https://fake.test/files/x", error=None)

    async def refine(self, client, graph, video, extraction, *, sfm, alignment, base_url,
                     max_iterations=4, deadline_s, work_dir=None):
        self.refine_calls.append({"alignment": alignment, "sfm": sfm, "base_url": base_url,
                                  "work_dir": work_dir, "graph_revision": graph.revision})
        while not self.block_refine.is_set():
            await asyncio.sleep(0.01)
        new = graph.model_copy(update={"zones": [
            z.model_copy(update={"name": z.name + "*"}) if z.id == "Z1" else z
            for z in graph.zones]})
        rdir = work_dir / "renders"
        rdir.mkdir(parents=True, exist_ok=True)
        renders = []
        for i, (t, kind) in enumerate(((2.0, "perspective"), (None, "top"))):
            p = rdir / f"view{i}.png"
            p.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes([i]) * 16)
            renders.append({"t_s": t, "path": str(p), "kind": kind})
        it = {"index": 0, "graph_revision": new.revision, "discrepancy_count": 1,
              "applied": [0], "rejected": [], "findings": [], "geometry": None,
              "renders": renders, "receipt": None, "stop_reason": "no_discrepancies"}
        return new, [it]

    def score_geometry(self, graph, sfm, alignment, video):
        self.score_calls.append((graph.revision, alignment["hash"]))
        return {"alignment_hash": alignment["hash"], "illegal_crossings": [],
                "wall_support": 0.9, "unexplained_points": 0.1, "edge_chamfer_px": None,
                "edge_within_5px": None, "heldout_t_s": []}

    async def prepare_environment(self, client, *, runtime_root=None) -> str:
        self.env_kwargs.append({"runtime_root": runtime_root})
        self.env_calls += 1
        await asyncio.sleep(0.01)
        return "env-1"

    @staticmethod
    def allowed_interventions(graph: VenueGraph, scenario: Scenario) -> list[str]:
        hazard = {h.door_id for h in scenario.hazards}
        return sorted(f"OPEN:{d.id}" for d in graph.doors
                      if d.state in ("closed", "locked", "unknown") and d.id not in hazard)[:6]

    async def render_topdown(self, graph, out_dir: Path, base_url: str, hazards) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        p = out_dir / "top.png"
        p.write_bytes(b"\x89PNG fake")
        return p

    async def investigate(self, client, graph, scenario, params, *, environment_id,
                          topdown_png, deadline_s=180, max_rounds=4, sessions_dir=None) -> dict:
        assert sessions_dir is not None
        self.investigate_calls.append(scenario)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.05)
            while not self.block_investigate.is_set():
                await asyncio.sleep(0.01)
        finally:
            self.active -= 1
        self.investigations_completed += 1
        results = []
        for iid in self.allowed_interventions(graph, scenario):
            s2 = scenario.model_copy(update={"interventions": [*scenario.interventions, iid]})
            run = solve(graph, s2, params)
            results.append({"intervention_id": iid, "run_id": run.run_id,
                            "reached_exit": run.reached_exit, "total": run.total,
                            "delta_vs_current": 1, "limiting_doors": [],
                            "check_ok": self.check_ok and check_run(graph, s2, params, run).ok})
        n = len(self.investigate_calls)
        return {"investigation_id": f"inv-{n}", "graph_revision": graph.revision,
                "scenario_hash": scenario.hash, "status": "completed",
                "interaction_id": f"int-{n}", "environment_id": environment_id,
                "ledger": [], "sandbox_runs": 0, "results": results,
                "recommendation": None, "best": results[0] if results else None,
                "disagreement": None, "hook_denials": 0, "receipt": None,
                "topdown_png": str(topdown_png)}

    def draft_note(self, session, approval) -> str:
        self.notes.append((session.scenario.hash, approval.intervention_id))
        return f"# DRAFT — not sent\n\nTo security: {approval.intervention_id}\n"


@pytest.fixture
def fakes() -> Fakes:
    return Fakes()


@pytest.fixture
def services(tmp_path, fakes) -> Services:
    return Services(
        runtime_root=tmp_path / "runtime",
        base_url="http://127.0.0.1:9",
        make_client=lambda: object(),
        prepare_video=fakes.prepare_video,
        run_sfm=fakes.run_sfm,
        fit_alignment=fakes.fit_alignment,
        to_graph_xy=fakes.to_graph_xy,
        scale_badge=lambda alignment: fakes.badge,
        extract=fakes.extract,
        refine=fakes.refine,
        prepare_environment=fakes.prepare_environment,
        investigate=fakes.investigate,
        allowed_interventions=fakes.allowed_interventions,
        render_topdown=fakes.render_topdown,
        draft_note=fakes.draft_note,
        score_geometry=fakes.score_geometry,
    )


@pytest.fixture
def client(services):
    api.app.dependency_overrides[get_services] = lambda: services
    try:
        with TestClient(api.app) as c:
            yield c
    finally:
        api.app.dependency_overrides.clear()


# --- helpers --------------------------------------------------------------------


def wait_for(c: TestClient, sid: str, pred, timeout: float = 10.0) -> dict:
    end = time.monotonic() + timeout
    while True:
        snap = c.get(f"/api/sessions/{sid}").json()
        if pred(snap):
            return snap
        if time.monotonic() > end:
            raise AssertionError(f"timed out; jobs={snap.get('jobs')}")
        time.sleep(0.02)


def idle(snap: dict) -> bool:
    return all(j["status"] in ("done", "failed") for j in snap["jobs"].values())


def upload(c: TestClient, path: Path | None = None, **form) -> str:
    data = path.read_bytes() if path else b"not really a video"
    r = c.post("/api/sessions", files={"video": ("walk.mp4", data, "video/mp4")}, data=form)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def with_draft(c: TestClient) -> tuple[str, dict]:
    sid = upload(c)
    r = c.post(f"/api/sessions/{sid}/extract", json={"mode": "static_hifps"})
    assert r.status_code == 202, r.text
    snap = wait_for(c, sid, lambda s: s["draft_revision"] is not None and idle(s))
    return sid, snap


def accepted(c: TestClient) -> tuple[str, dict]:
    sid, snap = with_draft(c)
    r = c.post(f"/api/sessions/{sid}/accept", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 200, r.text
    snap = wait_for(c, sid, lambda s: idle(s) and len(s["investigations"]) == 2)
    return sid, snap


def set_fire(c: TestClient, sid: str, snap: dict, *doors: str):
    return c.post(f"/api/sessions/{sid}/scenario", json={
        "expected_revision": snap["accepted_revision"],
        "hazards": [{"door_id": d, "kind": "fire"} for d in doors]})


# --- brief tests ----------------------------------------------------------------


def test_upload_starts_sfm_job(client, services, fakes, tmp_path):
    clip = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                    "testsrc=size=64x48:rate=10:duration=1", "-pix_fmt", "yuv420p",
                    str(clip)], check=True)
    services.prepare_video = lambda src, out: prepare_video(src, out)  # real ffmpeg
    sid = upload(client, clip)
    snap = client.get(f"/api/sessions/{sid}").json()
    assert snap["jobs"]["sfm"]["kind"] == "sfm"
    assert snap["jobs"]["sfm"]["status"] in ("queued", "running", "done")
    snap = wait_for(client, sid, lambda s: s["jobs"]["sfm"]["status"] == "done")
    assert len(fakes.sfm_calls) == 1
    assert snap["sfm"]["status"] == "completed" and snap["sfm"]["frame_count"] == 3
    assert snap["ghost_path"] == []  # no alignment yet
    assert 0.9 < snap["video"]["duration_s"] < 1.2
    assert (services.runtime_root / "sessions" / sid / "session.json").exists()
    v = client.get(f"/api/sessions/{sid}/video")
    assert v.status_code == 200 and v.headers["content-type"] == "video/mp4"
    f = client.get(f"/api/sessions/{sid}/frame", params={"t": 0.5})
    assert f.status_code == 200 and f.headers["content-type"] == "image/jpeg"
    assert client.get(f"/api/sessions/{sid}/frame", params={"t": 99}).status_code == 422


def test_accept_rejects_errors_422(client):
    sid, snap = with_draft(client)
    g = VenueGraph.model_validate(snap["draft_graph"])
    broken = g.model_copy(update={"doors": [d for d in g.doors if d.b != "OUTSIDE"]})
    r = client.put(f"/api/sessions/{sid}/graph", json={
        "expected_revision": snap["draft_revision"], "graph": broken.model_dump(mode="json")})
    assert r.status_code == 200
    rev = r.json()["revision"]
    r = client.post(f"/api/sessions/{sid}/accept", json={"expected_revision": rev})
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "graph_errors"
    assert any(f["code"] == "NO_EXIT" for f in body["findings"])
    snap = client.get(f"/api/sessions/{sid}").json()
    assert snap["accepted_graph"] is None and snap["current_run"] is None


def test_put_graph_stale_409(client):
    sid, snap = with_draft(client)
    g = VenueGraph.model_validate(snap["draft_graph"])
    edited = g.model_copy(update={"doors": [
        d.model_copy(update={"state": "closed"}) if d.id == "D6" else d for d in g.doors]})
    r = client.put(f"/api/sessions/{sid}/graph", json={
        "expected_revision": "g-0000000000000000", "graph": edited.model_dump(mode="json")})
    assert r.status_code == 409
    assert r.json()["error"] == "stale"
    assert r.json()["current"] == snap["draft_revision"]
    r = client.put(f"/api/sessions/{sid}/graph", json={
        "expected_revision": snap["draft_revision"], "graph": edited.model_dump(mode="json")})
    assert r.status_code == 200
    assert r.json()["revision"] == edited.revision
    # the old revision is now stale
    r = client.put(f"/api/sessions/{sid}/graph", json={
        "expected_revision": snap["draft_revision"], "graph": g.model_dump(mode="json")})
    assert r.status_code == 409
    r = client.post(f"/api/sessions/{sid}/accept", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 409 and r.json()["error"] == "stale"


def test_scenario_resolve_returns_checked_run(client):
    sid, snap = accepted(client)
    assert snap["current_check"]["ok"] is True
    base_reached = snap["current_run"]["reached_exit"]
    r = set_fire(client, sid, snap, "D2")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["scenario_hash"] == _fire("D2").hash
    assert body["check"]["ok"] is True
    assert body["check"]["run_id"] == body["run"]["run_id"]
    snap = client.get(f"/api/sessions/{sid}").json()
    assert snap["current_check"]["ok"] is True
    assert snap["current_run"]["scenario_hash"] == snap["scenario_hash"] == _fire("D2").hash
    assert snap["current_run"]["reached_exit"] < base_reached
    # stale and unknown-door requests are refused without changing state
    r = client.post(f"/api/sessions/{sid}/scenario", json={
        "expected_revision": "g-stale", "hazards": []})
    assert r.status_code == 409 and r.json()["error"] == "stale"
    r = set_fire(client, sid, snap, "D99")
    assert r.status_code == 422 and r.json()["error"] == "unknown_door"
    assert client.get(f"/api/sessions/{sid}").json()["scenario_hash"] == _fire("D2").hash


def test_accept_starts_precomputed_investigations_on_open_exits(client, fakes, services):
    sid, snap = with_draft(client)
    r = client.post(f"/api/sessions/{sid}/accept", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 200
    body = r.json()
    assert body["check"]["ok"] is True
    assert len(body["investigation_jobs"]) == 2
    snap = client.get(f"/api/sessions/{sid}").json()
    inv_jobs = [j for j in snap["jobs"].values() if j["kind"] == "investigate"]
    assert len(inv_jobs) == 2
    snap = wait_for(client, sid, lambda s: idle(s) and len(s["investigations"]) == 2)
    rev = snap["accepted_revision"]
    # M2: only open exits (D2, D4); the locked D5 is not a fire candidate
    expected = {_fire(e).hash for e in ("D2", "D4")}
    assert {i["scenario_hash"] for i in snap["investigations"]} == expected
    assert all(i["graph_revision"] == rev for i in snap["investigations"])
    assert fakes.max_active <= 2
    assert fakes.env_calls == 1  # environment prepared once and shared
    assert fakes.env_kwargs == [{"runtime_root": services.runtime_root}]  # F6 cache root
    assert all(j["status"] == "done" for j in snap["jobs"].values() if j["kind"] == "investigate")
    # the current scenario (no hazards) has no precomputed investigation
    assert snap["ready_investigation_id"] is None


def test_precomputed_investigation_matches_hazard(client, fakes):
    sid, snap = accepted(client)
    n_calls = len(fakes.investigate_calls)
    r = set_fire(client, sid, snap, "D2")
    want = next(i for i in snap["investigations"] if i["scenario_hash"] == _fire("D2").hash)
    assert r.json()["ready_investigation_id"] == want["investigation_id"]
    snap = client.get(f"/api/sessions/{sid}").json()
    assert snap["ready_investigation_id"] == want["investigation_id"]
    assert snap["scenario_hash"] == want["scenario_hash"]
    assert len(fakes.investigate_calls) == n_calls  # only the local solve ran
    # D1 is an interior door with no precomputed investigation
    r = set_fire(client, sid, snap, "D1")
    assert r.status_code == 200
    assert r.json()["ready_investigation_id"] is None
    assert client.get(f"/api/sessions/{sid}").json()["ready_investigation_id"] is None


def test_stale_investigation_rejected(client):
    sid, snap = accepted(client)
    set_fire(client, sid, snap, "D2")
    snap = client.get(f"/api/sessions/{sid}").json()
    inv_id = snap["ready_investigation_id"]
    assert inv_id is not None
    r = set_fire(client, sid, snap, "D2", "D4")  # hazards change after the investigation
    assert r.status_code == 200
    snap = client.get(f"/api/sessions/{sid}").json()
    r = client.post(f"/api/sessions/{sid}/approve", json={
        "expected_revision": snap["accepted_revision"],
        "expected_scenario": snap["scenario_hash"],
        "investigation_id": inv_id, "intervention_id": "OPEN:D5"})
    assert r.status_code == 409
    assert r.json()["error"] == "stale_investigation"
    snap2 = client.get(f"/api/sessions/{sid}").json()
    assert snap2["approvals"] == [] and snap2["scenario"]["interventions"] == []


def test_approve_unchecked_intervention_rejected(client, fakes):
    fakes.check_ok = False
    sid, snap = accepted(client)
    set_fire(client, sid, snap, "D2")
    snap = client.get(f"/api/sessions/{sid}").json()
    inv_id = snap["ready_investigation_id"]
    body = {"expected_revision": snap["accepted_revision"],
            "expected_scenario": snap["scenario_hash"], "investigation_id": inv_id}
    r = client.post(f"/api/sessions/{sid}/approve", json={**body, "intervention_id": "OPEN:D5"})
    assert r.status_code == 422 and r.json()["error"] == "intervention_unchecked"
    r = client.post(f"/api/sessions/{sid}/approve", json={**body, "intervention_id": "OPEN:D9"})
    assert r.status_code == 422 and r.json()["error"] == "intervention_unchecked"
    snap = client.get(f"/api/sessions/{sid}").json()
    assert snap["approvals"] == [] and snap["scenario"]["interventions"] == []
    assert fakes.notes == []


def test_static_mount_does_not_shadow_api(tmp_path, services):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>WalkTwin</title>")
    app = create_app(static_dir=dist)
    app.dependency_overrides[get_services] = lambda: services
    with TestClient(app) as c:
        for path in ("/api/sessions/x", "/api/sessions/abcdef123456", "/api/nope"):
            r = c.get(path)
            assert r.status_code == 404, path
            assert r.headers["content-type"].startswith("application/json"), path
            assert r.json()["error"] == "not_found"
        r = c.get("/")
        assert r.status_code == 200 and "WalkTwin" in r.text  # the mount is active
    # the mount is last
    assert type(app.routes[-1]).__name__ == "Mount"


# --- further tests --------------------------------------------------------------


def test_approve_applies_checked_intervention_and_drafts_note(client, fakes, services):
    sid, snap = accepted(client)
    set_fire(client, sid, snap, "D2")
    snap = client.get(f"/api/sessions/{sid}").json()
    inv_id = snap["ready_investigation_id"]
    r = client.post(f"/api/sessions/{sid}/approve", json={
        "expected_revision": snap["accepted_revision"], "expected_scenario": "s-stale",
        "investigation_id": inv_id, "intervention_id": "OPEN:D5"})
    assert r.status_code == 409 and r.json()["error"] == "stale"
    r = client.post(f"/api/sessions/{sid}/approve", json={
        "expected_revision": snap["accepted_revision"],
        "expected_scenario": snap["scenario_hash"],
        "investigation_id": inv_id, "intervention_id": "OPEN:D5"})
    assert r.status_code == 200, r.text
    body = r.json()
    new_hash = _fire("D2", interventions=("OPEN:D5",)).hash
    assert body["scenario_hash"] == new_hash
    assert body["check"]["ok"] is True
    ap = body["approval"]
    assert ap["investigation_id"] == inv_id and ap["run_id"] == body["run"]["run_id"]
    assert ap["graph_revision"] == snap["accepted_revision"] and ap["scenario_hash"] == new_hash
    note = Path(ap["note_path"])
    assert note.read_text().startswith("# DRAFT — not sent")
    assert note.is_relative_to(services.runtime_root / "sessions" / sid)
    assert fakes.notes == [(new_hash, "OPEN:D5")]  # drafted from the post-approval state
    snap = client.get(f"/api/sessions/{sid}").json()
    assert snap["scenario"]["interventions"] == ["OPEN:D5"]
    assert snap["current_run"]["run_id"] == snap["current_check"]["run_id"] == ap["run_id"]
    assert len(snap["approvals"]) == 1


def test_job_running_409(client, fakes):
    sid = upload(client)
    fakes.block_extract.clear()
    assert client.post(f"/api/sessions/{sid}/extract", json={"mode": "static"}).status_code == 202
    r = client.post(f"/api/sessions/{sid}/extract", json={"mode": "static"})
    assert r.status_code == 409 and r.json()["error"] == "job_running"
    assert client.post(f"/api/sessions/{sid}/extract", json={"mode": "bogus"}).status_code == 422
    fakes.block_extract.set()
    snap = wait_for(client, sid, idle)
    assert snap["jobs"]["extract"]["status"] == "done"
    assert fakes.extract_calls == ["static"]


def test_refine_fits_alignment_once_and_ghost_path(client, fakes):
    sid, snap = with_draft(client)
    snap = wait_for(client, sid, lambda s: s["jobs"]["sfm"]["status"] == "done")
    assert snap["ghost_path"] == []
    r = client.post(f"/api/sessions/{sid}/refine", json={"expected_revision": "g-stale"})
    assert r.status_code == 409 and r.json()["error"] == "stale"
    r = client.post(f"/api/sessions/{sid}/refine", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 202
    snap = wait_for(client, sid, lambda s: idle(s) and s["jobs"]["refine"]["status"] == "done")
    assert fakes.fit_calls == 1
    assert snap["alignment"]["hash"] == "al-1"
    assert snap["draft_graph"]["zones"][0]["name"].endswith("*")
    assert len(snap["iterations"]) == 1
    assert snap["ghost_path"] == [{"t_s": 0.0, "x": 1.0, "y": 2.0},
                                  {"t_s": 0.5, "x": 2.0, "y": 2.0},
                                  {"t_s": 1.0, "x": 3.0, "y": 2.0}]
    r = client.post(f"/api/sessions/{sid}/refine", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 202
    snap = wait_for(client, sid, lambda s: idle(s) and len(s["iterations"]) == 2)
    assert fakes.fit_calls == 1  # frozen
    assert [c["alignment"]["hash"] for c in fakes.refine_calls] == ["al-1", "al-1"]


def test_job_exception_is_captured(client, services):
    def boom(video, work_dir):
        raise RuntimeError("pycolmap exploded")
    services.run_sfm = boom
    sid = upload(client)
    snap = wait_for(client, sid, lambda s: s["jobs"]["sfm"]["status"] == "failed")
    assert "pycolmap exploded" in snap["jobs"]["sfm"]["error"]
    assert client.get(f"/api/sessions/{sid}").status_code == 200  # server still fine


def test_default_report_module_serves_report_and_note(client, services):
    defaults = api.default_services(services.runtime_root)
    services.build_report, services.render_html = defaults.build_report, defaults.render_html
    services.draft_note = defaults.draft_note
    sid = upload(client)
    r = client.get(f"/api/sessions/{sid}/report")
    assert r.status_code == 200 and r.json()["verdict"] == "incomplete"
    sid, snap = accepted(client)
    rep = client.get(f"/api/sessions/{sid}/report").json()
    assert rep["verdict"] in ("verified_within_model", "failed")
    assert rep["run_id"] == snap["current_run"]["run_id"] and rep["security_note"] == ""
    page = client.get(f"/api/sessions/{sid}/report.html")
    assert page.status_code == 200 and "<script" not in page.text
    assert "Content-Security-Policy" in page.text
    set_fire(client, sid, snap, "D2")
    snap = client.get(f"/api/sessions/{sid}").json()
    r = client.post(f"/api/sessions/{sid}/approve", json={
        "expected_revision": snap["accepted_revision"],
        "expected_scenario": snap["scenario_hash"],
        "investigation_id": snap["ready_investigation_id"], "intervention_id": "OPEN:D5"})
    assert r.status_code == 200, r.text
    note = r.json()["note"]
    assert note.splitlines()[0] == "# DRAFT — not sent" and "D5 must stay unlocked" in note
    assert client.get(f"/api/sessions/{sid}/report").json()["security_note"] == note


def test_session_persisted_and_reloaded(client, services):
    sid, snap = accepted(client)
    store = SessionStore(services.runtime_root)
    s = store.get(sid)
    assert s is not None
    assert s.accepted_graph.revision == snap["accepted_revision"]
    assert s.current_check.ok and s.current_check.run_id == s.current_run.run_id
    assert len(s.investigations) == 2
    assert isinstance(s.video, PreparedVideo) and s.video.path.exists()


def test_snapshot_fields_r24(client):
    sid, snap = with_draft(client)
    assert snap["draft_revision"] == VenueGraph.model_validate(snap["draft_graph"]).revision
    assert snap["graph_revision"] is None and snap["allowed_interventions"] == []
    assert snap["scenario_hash"] == Scenario().hash
    g = VenueGraph.model_validate(snap["draft_graph"])
    assert snap["findings"] == [f.model_dump(mode="json") for f in check_graph(g, 60.0)]
    sid, snap = accepted(client)
    assert snap["graph_revision"] == snap["accepted_revision"] is not None
    assert snap["allowed_interventions"] == ["OPEN:D5"]  # D5 is the locked exit
    set_fire(client, sid, snap, "D5")
    snap = client.get(f"/api/sessions/{sid}").json()
    assert snap["allowed_interventions"] == []  # a door under a hazard is not allowed
    assert snap["scenario_hash"] == _fire("D5").hash


def test_allowed_interventions_unavailable_is_empty(client, services):
    def missing(graph, scenario):
        raise ModuleNotFoundError("No module named 'walktwin.agent'")
    services.allowed_interventions = missing
    sid, snap = with_draft(client)
    r = client.post(f"/api/sessions/{sid}/accept", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 200 and r.json()["investigation_jobs"] == []  # M2: nothing to try
    snap = client.get(f"/api/sessions/{sid}").json()
    assert snap["allowed_interventions"] == []


def test_render_url_route(client):
    sid, snap = with_draft(client)
    snap = wait_for(client, sid, lambda s: s["jobs"]["sfm"]["status"] == "done")
    client.post(f"/api/sessions/{sid}/refine", json={"expected_revision": snap["draft_revision"]})
    snap = wait_for(client, sid, lambda s: idle(s) and len(s["iterations"]) == 1)
    client.post(f"/api/sessions/{sid}/refine", json={"expected_revision": snap["draft_revision"]})
    snap = wait_for(client, sid, lambda s: idle(s) and len(s["iterations"]) == 2)
    for n, it in enumerate(snap["iterations"]):
        assert [r["url"] for r in it["renders"]] == [
            f"/api/sessions/{sid}/renders/{n}/0.png", f"/api/sessions/{sid}/renders/{n}/1.png"]
    r = client.get(snap["iterations"][1]["renders"][1]["url"])
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.content == Path(snap["iterations"][1]["renders"][1]["path"]).read_bytes()
    for bad in ("2/0.png", "0/2.png", "-1/0.png"):
        r = client.get(f"/api/sessions/{sid}/renders/{bad}")
        assert r.status_code == 404 and r.json()["error"] == "not_found", bad


def test_note_route_and_report_security_note(client, services):
    services.build_report = lambda session: {"session_id": session.id, "verdict": "incomplete"}
    sid, snap = accepted(client)
    assert client.get(f"/api/sessions/{sid}/report").json()["security_note"] == ""
    assert client.get(f"/api/sessions/{sid}/approvals/0/note").status_code == 404
    set_fire(client, sid, snap, "D2")
    snap = client.get(f"/api/sessions/{sid}").json()
    r = client.post(f"/api/sessions/{sid}/approve", json={
        "expected_revision": snap["accepted_revision"],
        "expected_scenario": snap["scenario_hash"],
        "investigation_id": snap["ready_investigation_id"], "intervention_id": "OPEN:D5"})
    assert r.status_code == 200
    r = client.get(f"/api/sessions/{sid}/approvals/0/note")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/markdown")
    assert r.text.startswith("# DRAFT — not sent")
    assert client.get(f"/api/sessions/{sid}/report").json()["security_note"] == r.text


# --- fix round 1 ----------------------------------------------------------------


def _jobs(snap: dict, kind: str) -> dict:
    return {k: j for k, j in snap["jobs"].items() if j["kind"] == kind}


def test_double_accept_keeps_task_tracking(client, fakes):
    """Re-accepting with the same revision and scenario reuses the job keys; every
    superseded task must stay cancellable and never report done."""
    fakes.block_investigate.clear()
    sid, snap = with_draft(client)
    rev = snap["draft_revision"]
    for _ in range(3):
        r = client.post(f"/api/sessions/{sid}/accept", json={"expected_revision": rev})
        assert r.status_code == 200, r.text
        rev = r.json()["revision"]
        time.sleep(0.15)  # let superseded tasks process their cancellation
    snap = client.get(f"/api/sessions/{sid}").json()
    assert len(_jobs(snap, "investigate")) == 2
    fakes.block_investigate.set()
    snap = wait_for(client, sid, lambda s: idle(s) and len(s["investigations"]) == 2)
    time.sleep(0.2)
    snap = client.get(f"/api/sessions/{sid}").json()
    assert fakes.investigations_completed == 2  # only the last accept's two ran to the end
    assert len(snap["investigations"]) == 2
    assert all(j["status"] == "done" for j in _jobs(snap, "investigate").values())


def test_investigate_cap_409_and_precompute_keeps_a_slot_free(client, fakes):
    """M3: precompute takes at most 2 of the 3 investigate slots; the judge gets the 3rd."""
    fakes.block_investigate.clear()
    sid, snap = with_draft(client)
    r = client.post(f"/api/sessions/{sid}/accept", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 200 and len(r.json()["investigation_jobs"]) == 2
    end = time.monotonic() + 5
    while fakes.active < 2 and time.monotonic() < end:
        time.sleep(0.01)
    assert fakes.active == 2
    snap = client.get(f"/api/sessions/{sid}").json()
    body = {"expected_revision": snap["accepted_revision"]}
    # the judge's request takes the reserved slot
    set_fire(client, sid, snap, "D1")
    r = client.post(f"/api/sessions/{sid}/investigate",
                    json={**body, "expected_scenario": _fire("D1").hash})
    assert r.status_code == 202 and r.json()["reused"] is False
    end = time.monotonic() + 5
    while fakes.active < 3 and time.monotonic() < end:
        time.sleep(0.01)
    assert fakes.active == 3
    # a 4th is refused while all three run
    set_fire(client, sid, snap, "D6")
    r = client.post(f"/api/sessions/{sid}/investigate",
                    json={**body, "expected_scenario": _fire("D6").hash})
    assert r.status_code == 409 and r.json()["error"] == "job_running"
    fakes.block_investigate.set()
    wait_for(client, sid, lambda s: idle(s) and len(s["investigations"]) == 3)
    r = client.post(f"/api/sessions/{sid}/investigate",
                    json={**body, "expected_scenario": _fire("D6").hash})
    assert r.status_code == 202 and r.json()["reused"] is False
    wait_for(client, sid, lambda s: idle(s) and len(s["investigations"]) == 4)
    assert fakes.max_active == 3  # never more than three at once


def test_hazard_order_normalised(client):
    sid, snap = accepted(client)
    set_fire(client, sid, snap, "D4")
    snap = client.get(f"/api/sessions/{sid}").json()
    r = client.post(f"/api/sessions/{sid}/accept", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 200
    # re-accept precomputes current {D4} + fire on the other open exit (D2)
    snap = wait_for(client, sid, lambda s: idle(s) and len(s["investigations"]) == 3)
    want = _fire("D2", "D4").hash  # precompute: current {D4} + fire on D2, sorted
    assert want in {i["scenario_hash"] for i in snap["investigations"]}
    a = set_fire(client, sid, snap, "D4", "D2").json()
    b = set_fire(client, sid, snap, "D2", "D4").json()
    assert a["scenario_hash"] == b["scenario_hash"] == want
    assert a["ready_investigation_id"] is not None
    assert a["ready_investigation_id"] == b["ready_investigation_id"]
    assert [h["door_id"] for h in a["scenario"]["hazards"]] == ["D2", "D4"]


def test_extract_requires_revision_and_resets_frame(client, fakes):
    sid, snap = with_draft(client)
    wait_for(client, sid, lambda s: s["jobs"]["sfm"]["status"] == "done")
    client.post(f"/api/sessions/{sid}/refine", json={"expected_revision": snap["draft_revision"]})
    snap = wait_for(client, sid, lambda s: idle(s) and len(s["iterations"]) == 1)
    r = client.post(f"/api/sessions/{sid}/accept", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 200
    snap = wait_for(client, sid, idle)
    assert snap["alignment"] is not None and snap["accepted_graph"] is not None
    r = client.post(f"/api/sessions/{sid}/extract", json={"mode": "static"})
    assert r.status_code == 409 and r.json()["error"] == "stale"
    r = client.post(f"/api/sessions/{sid}/extract",
                    json={"mode": "static", "expected_revision": snap["draft_revision"]})
    assert r.status_code == 202
    snap = wait_for(client, sid, lambda s: idle(s) and s["extraction"]["mode"] == "static")
    assert snap["alignment"] is None and snap["iterations"] == []
    assert snap["accepted_graph"] is None and snap["current_run"] is None
    assert snap["current_check"] is None and snap["scenario_hash"] == Scenario().hash
    assert snap["ghost_path"] == []


def test_refine_finishing_after_put_is_stale(client, fakes):
    sid, snap = with_draft(client)
    fakes.block_refine.clear()
    r = client.post(f"/api/sessions/{sid}/refine", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 202
    g = VenueGraph.model_validate(snap["draft_graph"])
    edited = g.model_copy(update={"doors": [
        d.model_copy(update={"state": "closed"}) if d.id == "D6" else d for d in g.doors]})
    r = client.put(f"/api/sessions/{sid}/graph", json={
        "expected_revision": snap["draft_revision"], "graph": edited.model_dump(mode="json")})
    assert r.status_code == 200
    fakes.block_refine.set()
    snap = wait_for(client, sid, lambda s: s["jobs"]["refine"]["status"] in ("done", "failed"))
    assert snap["jobs"]["refine"]["status"] == "failed"
    assert snap["jobs"]["refine"]["error"].startswith("stale_draft")
    assert snap["draft_revision"] == edited.revision
    assert VenueGraph.model_validate(snap["draft_graph"]) == edited  # the human's edit survives
    assert snap["iterations"] == []
    # the job refined the graph as it was at request time, not the edited one
    assert fakes.refine_calls[-1]["graph_revision"] == g.revision != edited.revision
    assert fakes.refine_calls[-1]["work_dir"] is not None


def test_extract_finishing_after_put_is_stale(client, fakes):
    sid, snap = with_draft(client)
    fakes.block_extract.clear()
    r = client.post(f"/api/sessions/{sid}/extract",
                    json={"mode": "static", "expected_revision": snap["draft_revision"]})
    assert r.status_code == 202
    g = VenueGraph.model_validate(snap["draft_graph"])
    edited = g.model_copy(update={"zones": [
        z.model_copy(update={"occupants": 7}) if z.id == "Z4" else z for z in g.zones]})
    r = client.put(f"/api/sessions/{sid}/graph", json={
        "expected_revision": snap["draft_revision"], "graph": edited.model_dump(mode="json")})
    assert r.status_code == 200
    fakes.block_extract.set()
    snap = wait_for(client, sid, lambda s: s["jobs"]["extract"]["status"] in ("done", "failed"))
    assert snap["jobs"]["extract"]["error"].startswith("stale_draft")
    assert snap["draft_revision"] == edited.revision
    assert snap["extraction"]["mode"] == "static_hifps"  # not overwritten


def test_failed_extraction_not_applied(client, fakes):
    fakes.extract_status = "failed"
    sid = upload(client)
    client.post(f"/api/sessions/{sid}/extract", json={"mode": "static"})
    snap = wait_for(client, sid, lambda s: s["jobs"]["extract"]["status"] in ("done", "failed"))
    assert snap["jobs"]["extract"]["status"] == "failed"
    assert "provider status failed" in snap["jobs"]["extract"]["error"]
    assert snap["draft_graph"] is None and snap["extraction"] is None


@pytest.mark.parametrize("width", ["nan", "inf", "-1", "0"])
def test_anchor_width_must_be_finite_positive(client, width):
    r = client.post("/api/sessions", files={"video": ("w.mp4", b"x", "video/mp4")},
                    data={"anchor_door_hint": "D1", "anchor_width_m": width})
    assert r.status_code == 422


def test_render_path_outside_session_not_served(client, services, tmp_path):
    sid, snap = with_draft(client)
    outside = tmp_path / "elsewhere.png"
    outside.write_bytes(b"\x89PNG")
    s = services.store.get(sid)
    s.iterations.append({"renders": [{"path": str(outside), "kind": "top", "t_s": None}]})
    s.approvals.append(api.Approval(intervention_id="OPEN:D5", investigation_id="inv-x",
                                    graph_revision="g", scenario_hash="s", run_id="r",
                                    note_path=str(outside), approved_at="now"))
    r = client.get(f"/api/sessions/{sid}/renders/0/0.png")
    assert r.status_code == 404 and r.json()["error"] == "render_missing"
    r = client.get(f"/api/sessions/{sid}/approvals/0/note")
    assert r.status_code == 404


def test_scale_disagrees_runs_model_reported_only(client, fakes):
    fakes.badge = "disagrees"
    sid, snap = with_draft(client)
    wait_for(client, sid, lambda s: s["jobs"]["sfm"]["status"] == "done")
    client.post(f"/api/sessions/{sid}/refine", json={"expected_revision": snap["draft_revision"]})
    snap = wait_for(client, sid, lambda s: idle(s) and len(s["iterations"]) == 1)
    assert snap["alignment"] is not None  # persisted, frozen
    assert snap["geometry_unavailable_reason"] == "scale disagrees"
    assert snap["ghost_path"] == []
    assert fakes.refine_calls[-1]["sfm"] is None and fakes.refine_calls[-1]["alignment"] is None
    # agreeing badge: geometry is used and the ghost path appears
    fakes.badge = "agrees"
    client.post(f"/api/sessions/{sid}/refine", json={"expected_revision": snap["draft_revision"]})
    snap = wait_for(client, sid, lambda s: idle(s) and len(s["iterations"]) == 2)
    assert snap["geometry_unavailable_reason"] is None and len(snap["ghost_path"]) == 3
    assert fakes.refine_calls[-1]["alignment"]["hash"] == "al-1"


def test_sfm_failure_sets_geometry_reason(client, services):
    services.run_sfm = lambda video, work_dir: {
        "status": "failed", "frames": [], "points": [], "registered_fraction": 0.0,
        "elapsed_ms": 1, "error": "no_floor_plane"}
    sid = upload(client)
    snap = wait_for(client, sid, lambda s: s["jobs"]["sfm"]["status"] == "failed")
    assert snap["geometry_unavailable_reason"] == "sfm failed: no_floor_plane"


def test_default_runners_rehydrate_real_sfm_types():
    from walktwin import sfm
    from walktwin.sessions import to_jsonable
    res = sfm.SfmResult(status="completed",
                        frames=[sfm.SfmFrame(t_s=0.5, center=(1.0, 2.0, 0.5),
                                             R=[[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                                             K=[[500, 0, 32], [0, 500, 32], [0, 0, 1]])],
                        points=[(0.0, 0.0, 0.0)], registered_fraction=1.0, elapsed_ms=3,
                        error=None)
    back = api._sfm_obj(to_jsonable(res))
    assert back == res
    al = sfm.Alignment(scale=2.0, yaw_rad=0.3, tx=1.0, ty=-1.0, floor_normal=(0.0, 0.0, 1.0),
                       floor_offset=0.0, residual_m=0.1, eye_height_m=1.5, hash="h")
    d = to_jsonable(al)
    assert api._alignment_obj(d) == al
    assert api._default_to_graph_xy(d, (1.0, 2.0, 0.5)) == sfm.to_graph_xy(al, (1.0, 2.0, 0.5))
    assert api._default_scale_badge(d) == sfm.scale_badge(al)


# --- final-review fixes (lane F2) ------------------------------------------------


def post_anchor(c: TestClient, sid: str, rev, door_id="D4", width=0.8):
    return c.post(f"/api/sessions/{sid}/anchor", json={
        "expected_revision": rev, "door_id": door_id, "measured_width_m": width})


def refined(c: TestClient) -> tuple[str, dict]:
    sid, snap = with_draft(c)
    r = c.post(f"/api/sessions/{sid}/refine", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 202, r.text
    snap = wait_for(c, sid, lambda s: idle(s) and s["jobs"]["refine"]["status"] == "done")
    return sid, snap


def test_anchor_endpoint_is_server_owned(client):
    """C2/D2: POST /anchor validates and stores the anchor; the draft is unchanged."""
    sid = upload(client)
    r = post_anchor(client, sid, "g-none")
    assert r.status_code == 409 and r.json()["error"] == "no_draft"
    sid, snap = with_draft(client)
    rev = snap["draft_revision"]
    r = post_anchor(client, sid, "g-stale")
    assert r.status_code == 409 and r.json()["error"] == "stale"
    r = post_anchor(client, sid, rev, door_id="D99")
    assert r.status_code == 422 and r.json()["error"] == "anchor_door_missing"
    for bad in ("NaN", "Infinity", "-Infinity", "0", "-1"):
        r = client.post(f"/api/sessions/{sid}/anchor", content=(
            '{"expected_revision": "%s", "door_id": "D4", "measured_width_m": %s}' % (rev, bad)),
            headers={"content-type": "application/json"})
        assert r.status_code == 422, bad
    assert client.get(f"/api/sessions/{sid}").json()["pending_anchor"] is None
    r = post_anchor(client, sid, rev)
    assert r.status_code == 200, r.text
    assert r.json()["pending_anchor"] == {"door_id": "D4", "measured_width_m": 0.8}
    snap = client.get(f"/api/sessions/{sid}").json()
    assert snap["pending_anchor"] == {"door_id": "D4", "measured_width_m": 0.8}
    assert snap["draft_revision"] == rev and snap["draft_graph"]["anchor"] is None


def test_put_graph_rejects_client_anchor(client):
    """C2/D2: the draft's anchor field can never be set by the client."""
    sid, snap = with_draft(client)
    g = snap["draft_graph"]
    r = client.put(f"/api/sessions/{sid}/graph", json={
        "expected_revision": snap["draft_revision"],
        "graph": {**g, "anchor": {"door_id": "D4", "measured_width_m": 0.8}}})
    assert r.status_code == 422 and r.json() == {"error": "anchor_server_owned"}
    snap2 = client.get(f"/api/sessions/{sid}").json()
    assert snap2["draft_revision"] == snap["draft_revision"] and snap2["pending_anchor"] is None
    # accepting now claims no anchor anywhere
    r = client.post(f"/api/sessions/{sid}/accept", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 200
    assert client.get(f"/api/sessions/{sid}").json()["accepted_graph"]["anchor"] is None


def test_accept_applies_pending_anchor_and_provenance(client, services):
    """C2: accept applies s.anchor with apply_anchor; provenance says tape-measured
    only when it ran."""
    defaults = api.default_services(services.runtime_root)
    services.build_report = defaults.build_report
    sid, snap = accepted(client)
    prov = client.get(f"/api/sessions/{sid}/report").json()["provenance"]
    assert not any("tape-measured" in p for p in prov)

    sid, snap = with_draft(client)
    assert post_anchor(client, sid, snap["draft_revision"], "D4", 0.76).status_code == 200
    r = client.post(f"/api/sessions/{sid}/accept", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 200, r.text
    snap = client.get(f"/api/sessions/{sid}").json()
    g = snap["accepted_graph"]
    d4 = next(d for d in g["doors"] if d["id"] == "D4")
    assert d4["clear_width"] == {"low_m": 0.76, "high_m": 0.76, "basis": "anchor_measured"}
    assert g["anchor"] == {"door_id": "D4", "measured_width_m": 0.76}
    f = 0.76 / 0.95
    z1 = next(z for z in g["zones"] if z["id"] == "Z1")
    assert z1["rect"] == pytest.approx([3 * f, 0, 12 * f, 8 * f])
    assert snap["draft_revision"] == snap["accepted_revision"] == r.json()["revision"]
    prov = client.get(f"/api/sessions/{sid}/report").json()["provenance"]
    assert any("D4 tape-measured at 0.760 m" in p for p in prov)
    # re-accepting the anchored draft does not scale it a second time
    r = client.post(f"/api/sessions/{sid}/accept", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 200 and r.json()["revision"] == snap["accepted_revision"]


def test_anchored_accept_scales_the_frozen_alignment(client, fakes):
    """C3/D3: the alignment moves into the accepted frame (scale, translation, eye
    height and residual times f, new hash); an "accepted" iteration is scored under it."""
    sid, snap = refined(client)
    al0 = snap["alignment"]
    ghost0 = snap["ghost_path"]
    n_its = len(snap["iterations"])
    rev = snap["draft_revision"]
    assert post_anchor(client, sid, rev, "D4", 0.76).status_code == 200
    r = client.post(f"/api/sessions/{sid}/accept", json={"expected_revision": rev})
    assert r.status_code == 200, r.text
    snap = client.get(f"/api/sessions/{sid}").json()
    f = 0.76 / 0.95
    al = snap["alignment"]
    assert snap["alignment_unanchored"] == al0
    assert al["scale"] == pytest.approx(al0["scale"] * f)
    assert (al["tx"], al["ty"]) == pytest.approx((al0["tx"] * f, al0["ty"] * f))
    assert al["eye_height_m"] == pytest.approx(al0["eye_height_m"] * f)
    assert al["residual_m"] == pytest.approx(al0["residual_m"] * f)
    assert (al["yaw_rad"], al["floor_normal"], al["floor_offset"]) == (
        al0["yaw_rad"], al0["floor_normal"], al0["floor_offset"])
    assert al["hash"] != al0["hash"]
    # the ghost path is drawn in the accepted frame
    assert [(p["x"], p["y"]) for p in snap["ghost_path"]] == pytest.approx(
        [(p["x"] * f, p["y"] * f) for p in ghost0])
    # the accepted iteration
    assert len(snap["iterations"]) == n_its + 1
    it = snap["iterations"][-1]
    assert it["kind"] == "accepted" and it["graph_revision"] == snap["accepted_revision"]
    assert it["applied"] == [] and it["rejected"] == [] and it["discrepancy_count"] == 0
    assert it["renders"] == [] and it["stop_reason"] is None
    assert it["geometry"]["alignment_hash"] == al["hash"]
    assert fakes.score_calls[-1] == (snap["accepted_revision"], al["hash"])
    # refine iterations keep their (default) kind
    assert all(i.get("kind", "round") == "round" for i in snap["iterations"][:-1])
    # a later refine of the anchored draft uses the same accepted-frame alignment
    r = client.post(f"/api/sessions/{sid}/refine", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 202
    wait_for(client, sid, lambda s: idle(s) and len(s["iterations"]) == n_its + 2)
    assert fakes.refine_calls[-1]["alignment"]["hash"] == al["hash"]
    assert fakes.fit_calls == 1


def test_unanchored_accept_keeps_alignment_and_adds_accepted_iteration(client, fakes):
    sid, snap = refined(client)
    al0 = snap["alignment"]
    r = client.post(f"/api/sessions/{sid}/accept", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 200
    snap = client.get(f"/api/sessions/{sid}").json()
    assert snap["alignment"] == al0 and snap["alignment_unanchored"] == al0
    it = snap["iterations"][-1]
    assert it["kind"] == "accepted" and it["geometry"]["alignment_hash"] == al0["hash"]


def test_scale_alignment_matches_sfm_math_and_hash():
    """D3 helper: same math and hash recipe as walktwin.sfm (until F4's helper merges)."""
    from walktwin import sfm
    from walktwin.sessions import to_jsonable
    from fixtures.sfm_synthetic import make_scene
    res, graph = make_scene(graph_scale=1.25)
    al = sfm.fit_alignment(res, graph)
    d = to_jsonable(al)
    assert api._scale_alignment(d, 1.0)["hash"] == al.hash  # identical recipe
    f = 0.8
    sd = api._scale_alignment(d, f)
    scaled = api._alignment_obj(sd)
    for fr in res.frames[::7]:
        x, y = sfm.to_graph_xy(al, fr.center)
        assert sfm.to_graph_xy(scaled, fr.center) == pytest.approx((x * f, y * f))
    assert scaled.eye_height_m == pytest.approx(al.eye_height_m * f)
    assert sd["hash"] == sfm._alignment_hash({
        "scale": al.scale * f, "yaw_rad": al.yaw_rad, "tx": al.tx * f, "ty": al.ty * f,
        "floor_normal": al.floor_normal, "floor_offset": al.floor_offset,
        "residual_m": al.residual_m * f, "eye_height_m": al.eye_height_m * f,
        "reflected": False})
    assert sd["hash"] != al.hash


def test_ghost_stays_inside_the_anchored_twin(client, services, fakes):
    """C3 end to end with the real alignment math: Argon over-scaled the room by 25 %,
    the tape-measured door brings it back, and the ghost path follows."""
    from walktwin import geometry_score, sfm
    from fixtures.sfm_synthetic import ROOM_D, ROOM_W, make_scene
    gs = 1.25
    res, kf_graph = make_scene(graph_scale=gs)
    ev = [{"start_s": 1.0, "end_s": 3.0, "note": "seen"}]
    graph = VenueGraph.model_validate({
        "schema_version": "1", "video_sha256": SHA, "anchor": None,
        "zones": [{"id": "Z1", "name": "Room", "rect": [0, 0, ROOM_W * gs, ROOM_D * gs],
                   "occupants": 20, "furniture_seen": False, "evidence": ev}],
        "doors": [{"id": "D1", "a": "Z1", "b": "OUTSIDE", "kind": "exit", "state": "open",
                   "clear_width": {"low_m": 1.2, "high_m": 1.3, "basis": "estimated"},
                   "position": [0, ROOM_D * gs / 2], "evidence": ev}],
        "keyframes": [k.model_dump() for k in kf_graph.keyframes]})

    async def extract(client_, video, *, mode, deadline_s, anchor_hint=None):
        return ExtractionResult(status="completed", graph=graph, findings=[], receipt=None,
                                mode=mode, agentic_observed=None,
                                video_uri="https://fake.test/files/x", error=None)

    async def refine(client_, g, video, extraction, *, sfm, alignment, base_url,
                     max_iterations=4, deadline_s, work_dir=None):
        return g, []

    services.run_sfm = lambda video, work_dir: res
    services.extract, services.refine = extract, refine
    services.fit_alignment = api._default_fit_alignment
    services.to_graph_xy = api._default_to_graph_xy
    services.scale_badge = api._default_scale_badge
    services.score_geometry = lambda g, s, a, v: geometry_score.score_geometry(
        g, api._sfm_obj(s), api._alignment_obj(a))
    sid, snap = refined(client)
    # the over-scaled draft puts the camera 1.875 m up: the badge disagrees, no ghost
    assert snap["geometry_unavailable_reason"] == "scale disagrees"
    assert snap["ghost_path"] == []
    al0 = api._alignment_obj(snap["alignment"])
    xs = [sfm.to_graph_xy(al0, f.center)[0] for f in res.frames]
    assert max(xs) > ROOM_W + 0.5  # the old ghost overshoots the anchored room
    assert post_anchor(client, sid, snap["draft_revision"], "D1", 1.0).status_code == 200
    r = client.post(f"/api/sessions/{sid}/accept", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 200, r.text
    snap = client.get(f"/api/sessions/{sid}").json()
    # the badge is re-checked under the accepted-frame alignment: it now agrees
    assert snap["geometry_unavailable_reason"] is None
    assert len(snap["ghost_path"]) == len(res.frames)
    x0, y0, w, h = snap["accepted_graph"]["zones"][0]["rect"]
    assert (w, h) == pytest.approx((ROOM_W, ROOM_D))
    for p in snap["ghost_path"]:
        assert x0 - 0.05 <= p["x"] <= x0 + w + 0.05 and y0 - 0.05 <= p["y"] <= y0 + h + 0.05, p
    al = snap["alignment"]
    assert al["eye_height_m"] == pytest.approx(1.5, abs=0.02)  # true eye height again
    assert sfm.scale_badge(api._alignment_obj(al)) == "agrees"
    it = snap["iterations"][-1]
    assert it["kind"] == "accepted" and it["geometry"]["alignment_hash"] == al["hash"]
    assert it["geometry"]["illegal_crossings"] == []


def test_refine_while_sfm_running_409(client, fakes):
    """I11: geometry would be silently skipped; refuse instead."""
    fakes.block_sfm.clear()
    sid = upload(client)
    client.post(f"/api/sessions/{sid}/extract", json={"mode": "static_hifps"})
    snap = wait_for(client, sid, lambda s: s["draft_revision"] is not None
                    and s["jobs"]["extract"]["status"] == "done")
    assert snap["jobs"]["sfm"]["status"] in ("queued", "running")
    r = client.post(f"/api/sessions/{sid}/refine", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 409 and r.json()["error"] == "sfm_running"
    fakes.block_sfm.set()
    snap = wait_for(client, sid, idle)
    r = client.post(f"/api/sessions/{sid}/refine", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 202


def test_refine_drops_alignment_fitted_for_a_replaced_extraction(client, fakes):
    """I11: a new extraction landing during fit_alignment must not get the old fit."""
    sid, snap = with_draft(client)
    fakes.block_fit.clear()
    r = client.post(f"/api/sessions/{sid}/refine", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 202
    assert fakes.fit_started.wait(5)
    s = client.app.dependency_overrides[get_services]().store.get(sid)
    new = s.extraction.model_copy(update={"mode": "static"})
    s.extraction = new  # what a completed re-extraction does
    s.geometry_unavailable_reason = "marker"
    fakes.block_fit.set()
    snap = wait_for(client, sid, lambda s: s["jobs"]["refine"]["status"] in ("done", "failed"))
    assert snap["jobs"]["refine"]["status"] == "failed"
    assert snap["jobs"]["refine"]["error"].startswith("stale_draft")
    assert snap["alignment"] is None and snap["alignment_error"] is None
    assert snap["geometry_unavailable_reason"] == "marker"  # not overwritten
    assert fakes.refine_calls == [] and snap["iterations"] == []


@pytest.mark.parametrize("kind", ["extract", "refine"])
def test_jobs_refuse_when_accepted_revision_changed(client, fakes, kind):
    """I13: an accept during the job (same draft revision) makes the result stale."""
    sid, snap = with_draft(client)
    rev = snap["draft_revision"]
    block = fakes.block_extract if kind == "extract" else fakes.block_refine
    block.clear()
    body = {"expected_revision": rev}
    if kind == "extract":
        body["mode"] = "static"
    assert client.post(f"/api/sessions/{sid}/{kind}", json=body).status_code == 202
    r = client.post(f"/api/sessions/{sid}/accept", json={"expected_revision": rev})
    assert r.status_code == 200
    block.set()
    snap = wait_for(client, sid, lambda s: s["jobs"][kind]["status"] in ("done", "failed"))
    assert snap["jobs"][kind]["status"] == "failed"
    assert snap["jobs"][kind]["error"].startswith("stale_draft")
    assert snap["accepted_revision"] == rev and snap["draft_revision"] == rev
    assert snap["extraction"]["mode"] == "static_hifps"


def test_new_extraction_clears_anchor_and_approvals(client):
    """I1/M10: anchors name the old draft's door ids; approvals belong to the old graph."""
    sid, snap = accepted(client)
    set_fire(client, sid, snap, "D2")
    snap = client.get(f"/api/sessions/{sid}").json()
    r = client.post(f"/api/sessions/{sid}/approve", json={
        "expected_revision": snap["accepted_revision"], "expected_scenario": snap["scenario_hash"],
        "investigation_id": snap["ready_investigation_id"], "intervention_id": "OPEN:D5"})
    assert r.status_code == 200
    snap = client.get(f"/api/sessions/{sid}").json()
    assert post_anchor(client, sid, snap["draft_revision"], "D4", 0.8).status_code == 200
    r = client.post(f"/api/sessions/{sid}/extract",
                    json={"mode": "static", "expected_revision": snap["draft_revision"]})
    assert r.status_code == 202
    snap = wait_for(client, sid, lambda s: idle(s) and s["extraction"]["mode"] == "static")
    assert snap["pending_anchor"] is None and snap["anchor"] is None
    assert snap["approvals"] == []
    assert snap["alignment"] is None and snap["alignment_unanchored"] is None


def test_upload_hint_is_text_until_argon_marks_a_door(client, fakes):
    """M8: an upload door hint is never resolved to a door id before extraction."""
    hints = []
    orig = fakes.extract

    async def extract(client_, video, *, mode, deadline_s, anchor_hint=None):
        hints.append(anchor_hint)
        return await orig(client_, video, mode=mode, deadline_s=deadline_s,
                          anchor_hint=anchor_hint)

    client.app.dependency_overrides[get_services]().extract = extract
    sid = upload(client, anchor_door_hint="D4", anchor_width_m="0.8")
    snap = client.get(f"/api/sessions/{sid}").json()
    assert snap["pending_anchor"] is None and snap["anchor_hint"] == "D4"
    client.post(f"/api/sessions/{sid}/extract", json={"mode": "static_hifps"})
    snap = wait_for(client, sid, lambda s: idle(s) and s["draft_revision"] is not None)
    assert hints == ["D4 Tape-measured clear width: 0.80 m."]
    assert snap["pending_anchor"] is None  # Argon marked no door "anchor:"


def test_precompute_skips_scenarios_without_allowed_interventions(client, services):
    """M2: no allowed intervention means nothing for the agent to investigate."""
    services.allowed_interventions = lambda graph, scenario: []
    sid, snap = with_draft(client)
    r = client.post(f"/api/sessions/{sid}/accept", json={"expected_revision": snap["draft_revision"]})
    assert r.status_code == 200 and r.json()["investigation_jobs"] == []


def test_snapshot_has_sfm_preview_once_sfm_completes(client, fakes):
    """I3/D4."""
    fakes.block_sfm.clear()
    sid = upload(client)
    assert client.get(f"/api/sessions/{sid}").json()["sfm_preview"] is None
    fakes.block_sfm.set()
    snap = wait_for(client, sid, lambda s: s["jobs"]["sfm"]["status"] == "done")
    pv = snap["sfm_preview"]
    assert pv["note"] == "unaligned, SfM units"
    assert [p["t_s"] for p in pv["points"]] == [0.0, 0.5, 1.0]
    assert pv["points"][0] == {"t_s": 0.0, "u": 0.0, "v": 0.0} or (
        abs(pv["points"][0]["u"]) < 1e-12 and abs(pv["points"][0]["v"]) < 1e-12)
    assert pv["points"][-1]["v"] == pytest.approx(1.0)
    assert snap["ghost_path"] == []  # still unaligned


def test_investigate_deadline_is_240(services):
    assert services.investigate_deadline_s == 240.0  # I10


def test_solves_run_off_the_event_loop(client, monkeypatch):
    """M1: solve/check_run in request handlers go through asyncio.to_thread."""
    on_loop = []
    real = api.solve

    def spy(*a, **kw):
        try:
            asyncio.get_running_loop()
            on_loop.append(True)
        except RuntimeError:  # a worker thread has no running loop
            on_loop.append(False)
        return real(*a, **kw)

    monkeypatch.setattr(api, "solve", spy)
    sid, snap = accepted(client)
    set_fire(client, sid, snap, "D2")
    snap = client.get(f"/api/sessions/{sid}").json()
    r = client.post(f"/api/sessions/{sid}/approve", json={
        "expected_revision": snap["accepted_revision"], "expected_scenario": snap["scenario_hash"],
        "investigation_id": snap["ready_investigation_id"], "intervention_id": "OPEN:D5"})
    assert r.status_code == 200, r.text
    assert on_loop == [False, False, False]  # accept, scenario, approve
