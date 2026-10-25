"""WalkTwin session API (FastAPI).

upload -> ``sfm`` job -> Argon extraction -> refine loop -> human accept ->
hazards and checked solves -> background managed-agent investigations ->
human approve -> drafted security note.

Authority: no model output changes the accepted graph or the scenario. Only
``accept``, ``scenario`` and ``approve`` do, and each carries
``expected_revision`` (plus ``expected_scenario`` where relevant); a mismatch
returns 409. Modules owned by other lanes (sfm, loop, agent, report, render)
are imported lazily inside the default job runners, which tests replace via
``app.dependency_overrides[get_services]``.

Run from the repo root::

    PYTHONPATH=backend .venv/bin/uvicorn walktwin.api:app --port 8000
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import logging
import math
import os
import re
import secrets
import shutil
import subprocess
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal, Sequence

from fastapi import APIRouter, Depends, FastAPI, File, Form, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .checker import CheckResult, check_run
from .contracts import Anchor, FlowParams, Hazard, Scenario, VenueGraph, apply_anchor
from .extract import ExtractionResult
from .flow import FlowRun, solve
from .graph_checks import Finding, check_graph, has_errors
from .media import PreparedVideo, extract_frame
from .preview import sfm_preview
from .sessions import (MAX_INVESTIGATE_JOBS, Approval, JobConflict, JobState, Session,
                       SessionStore, to_jsonable)

log = logging.getLogger("walktwin.api")

REPO_ROOT = Path(__file__).resolve().parents[2]
DIST = REPO_ROOT / "frontend" / "dist"
OUTSIDE = "OUTSIDE"
PARAMS = FlowParams()  # declared parameters
MAX_UPLOAD_BYTES = 2 * 1024**3  # Files API limit
DRAFT_HEADER = "# DRAFT — not sent"


# --- errors -------------------------------------------------------------------------


class ApiError(Exception):
    def __init__(self, status: int, error: str, **extra: Any) -> None:
        super().__init__(error)
        self.status, self.error, self.extra = status, error, extra


def _stale(expected: str | None, current: str | None, what: str = "graph") -> None:
    if expected != current:
        raise ApiError(409, "stale", what=what, expected=expected, current=current)


# --- services (dependency-injected) -------------------------------------------------


def _report_module():
    from . import report
    return report


def _lazy_build_report(session: Session) -> Any:
    return _report_module().build_report(session)


def _lazy_render_html(report: Any) -> str:
    return _report_module().render_html(report)


def _lazy_draft_note(session: Session, approval: Approval) -> str:
    return _report_module().draft_security_note(session, approval)


def _sfm_obj(d: dict) -> Any:
    from . import sfm as m
    if hasattr(m.SfmResult, "model_validate"):
        return m.SfmResult.model_validate(d)
    frames = [m.SfmFrame(**{**f, "center": tuple(f["center"])}) for f in d.get("frames", [])]
    return m.SfmResult(**{**d, "frames": frames,
                          "points": [tuple(p) for p in d.get("points", [])]})


def _alignment_obj(d: dict) -> Any:
    from . import sfm as m
    if hasattr(m.Alignment, "model_validate"):
        return m.Alignment.model_validate(d)
    return m.Alignment(**{**d, "floor_normal": tuple(d["floor_normal"])})


def _default_run_sfm(video: PreparedVideo, work_dir: Path) -> Any:
    from .sfm import run_sfm
    return run_sfm(video, work_dir)


def _default_fit_alignment(sfm: dict, graph: VenueGraph) -> Any:
    from .sfm import fit_alignment
    return fit_alignment(_sfm_obj(sfm), graph)


def _default_to_graph_xy(alignment: dict, p: Sequence[float]) -> tuple[float, float]:
    from .sfm import to_graph_xy
    return to_graph_xy(_alignment_obj(alignment), tuple(p))


def _default_scale_badge(alignment: dict) -> str:
    from .sfm import scale_badge
    return scale_badge(_alignment_obj(alignment))


def _default_score_geometry(graph: VenueGraph, sfm: dict, alignment: dict,
                            video: PreparedVideo) -> Any:
    """Score ``graph`` exactly as the loop does (same held-out frames rule)."""
    from .geometry_score import score_geometry
    from .loop import heldout_times
    s = _sfm_obj(sfm)
    heldout = heldout_times(s, [k.t_s for k in graph.keyframes])
    return score_geometry(graph, s, _alignment_obj(alignment), video=video, heldout_t_s=heldout)


def _alignment_hash(params: dict) -> str:
    # Same recipe as walktwin.sfm._alignment_hash (asserted by test_api).
    def r(x):
        if isinstance(x, bool):
            return x
        if isinstance(x, (list, tuple)):
            return [r(v) for v in x]
        return round(float(x), 4) + 0.0
    data = {k: r(v) for k, v in params.items()}
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _scale_alignment(alignment: dict, f: float) -> dict:
    """D3: the alignment for a graph scaled by ``f`` about the origin (apply_anchor).

    TODO(F4 merge): replace with ``to_jsonable(sfm.scale_alignment(_alignment_obj(a), f))``;
    this private copy has the same math and the same hash recipe.
    """
    reflected = bool(alignment.get("_reflected", False))
    params = {
        "scale": alignment["scale"] * f, "yaw_rad": alignment["yaw_rad"],
        "tx": alignment["tx"] * f, "ty": alignment["ty"] * f,
        "floor_normal": [float(v) for v in alignment["floor_normal"]],
        "floor_offset": alignment["floor_offset"],
        "residual_m": alignment["residual_m"] * f,
        "eye_height_m": alignment["eye_height_m"] * f,
    }
    return {**params, "hash": _alignment_hash({**params, "reflected": reflected}),
            "_reflected": reflected}


async def _default_extract(client, video, *, mode, deadline_s, anchor_hint=None):
    from .extract import extract_venue
    return await extract_venue(client, video, mode=mode, deadline_s=deadline_s,
                               anchor_hint=anchor_hint)


async def _default_refine(client, graph, video, extraction, *, sfm, alignment, base_url,
                          max_iterations=4, deadline_s, work_dir=None):
    from .loop import refine_graph
    return await refine_graph(
        client, graph, video, extraction,
        sfm=_sfm_obj(sfm) if sfm else None,
        alignment=_alignment_obj(alignment) if alignment else None,
        base_url=base_url, max_iterations=max_iterations, deadline_s=deadline_s,
        work_dir=work_dir)


async def _default_prepare_environment(client, *, runtime_root: Path | None = None) -> str:
    from .agent import prepare_environment
    # Lane F6 keys the environment cache under ``runtime_root``; tolerate the
    # pre-F6 signature until both lanes are merged.
    kw = _runtime_root_kw(prepare_environment, runtime_root) if runtime_root else {}
    return await prepare_environment(client, **kw)


async def _default_investigate(client, graph, scenario, params, **kwargs) -> Any:
    from .agent import investigate
    return await investigate(client, graph, scenario, params, **kwargs)


def _default_allowed_interventions(graph: VenueGraph, scenario: Scenario) -> list[str]:
    from .agent import allowed_interventions
    return allowed_interventions(graph, scenario)


async def _default_render_topdown(graph: VenueGraph, out_dir: Path, base_url: str,
                                  hazards: Sequence[str]) -> Path:
    from .render import render_views
    views = await render_views(graph, out_dir, base_url, hazards=list(hazards))
    top = [v for v in views if v.kind == "top"]
    if not top:
        raise RuntimeError("render_views returned no top-down view")
    return top[0].path


def _default_make_client():
    from .genai_client import make_client
    return make_client()


def _default_prepare_video(src: Path, out_dir: Path) -> PreparedVideo:
    from .media import prepare_video
    return prepare_video(src, out_dir)


@dataclass
class Services:
    """Everything with side effects. SfM and alignment cross this boundary as JSON dicts."""

    runtime_root: Path
    base_url: str  # origin serving frontend/dist, for headless renders
    make_client: Callable[[], Any] = _default_make_client
    prepare_video: Callable[[Path, Path], PreparedVideo] = _default_prepare_video
    run_sfm: Callable[[PreparedVideo, Path], Any] = _default_run_sfm  # sync, run in a thread
    fit_alignment: Callable[[dict, VenueGraph], Any] = _default_fit_alignment  # sync
    to_graph_xy: Callable[[dict, Sequence[float]], tuple[float, float]] = _default_to_graph_xy
    scale_badge: Callable[[dict], str] = _default_scale_badge
    score_geometry: Callable[[VenueGraph, dict, dict, PreparedVideo], Any] = (
        _default_score_geometry)  # sync, run in a thread
    extract: Callable[..., Awaitable[ExtractionResult]] = _default_extract
    refine: Callable[..., Awaitable[tuple[VenueGraph, list]]] = _default_refine
    prepare_environment: Callable[..., Awaitable[str]] = _default_prepare_environment
    investigate: Callable[..., Awaitable[Any]] = _default_investigate
    allowed_interventions: Callable[[VenueGraph, Scenario], list[str]] = (
        _default_allowed_interventions)
    render_topdown: Callable[..., Awaitable[Path]] = _default_render_topdown
    draft_note: Callable[[Session, Approval], str] = _lazy_draft_note
    build_report: Callable[[Session], Any] = _lazy_build_report
    render_html: Callable[[Any], str] = _lazy_render_html
    extract_deadline_s: float = 900.0
    refine_deadline_s: float = 1800.0
    investigate_deadline_s: float = 240.0
    store: SessionStore = field(init=False)
    _env_id: str | None = field(default=None, init=False)
    _env_lock: asyncio.Lock | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.runtime_root = Path(self.runtime_root)
        self.store = SessionStore(self.runtime_root)

    async def environment_id(self, client) -> str:
        """Prepare the agent environment once and share it across investigations."""
        if self._env_id is None:
            if self._env_lock is None:
                self._env_lock = asyncio.Lock()
            async with self._env_lock:
                if self._env_id is None:
                    self._env_id = await self.prepare_environment(
                        client, **_runtime_root_kw(self.prepare_environment, self.runtime_root))
        return self._env_id


def _runtime_root_kw(fn: Callable, runtime_root: Path) -> dict:
    """``{"runtime_root": ...}`` when ``fn`` accepts it (lane F6's cache root)."""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return {}
    ok = "runtime_root" in params or any(p.kind is p.VAR_KEYWORD for p in params.values())
    return {"runtime_root": runtime_root} if ok else {}


def default_services(runtime_root: Path | None = None) -> Services:
    return Services(
        runtime_root=runtime_root or REPO_ROOT / "runtime",
        base_url=os.environ.get("WALKTWIN_BASE_URL", "http://127.0.0.1:8000"),
    )


@lru_cache(maxsize=1)
def _singleton() -> Services:
    return default_services()


def get_services() -> Services:
    return _singleton()


# --- snapshot -----------------------------------------------------------------------


class GhostPoint(BaseModel):
    t_s: float
    x: float
    y: float


class VideoInfo(BaseModel):
    sha256: str
    duration_s: float
    width: int
    height: int
    url: str


class SessionSnapshot(BaseModel):
    id: str
    created_at: str
    video: VideoInfo
    anchor: Anchor | None  # same as pending_anchor (kept for older clients)
    pending_anchor: Anchor | None  # server-owned (D2); applied at the next accept
    anchor_hint: str | None
    anchor_width_m: float | None
    jobs: dict[str, JobState]
    sfm: dict | None  # summary: status, registered_fraction, frame_count, point_count, ...
    sfm_preview: dict | None  # D4: unaligned walk in SfM units, once SfM completes
    alignment: dict | None  # in the draft's frame (the accepted frame after an anchored accept)
    alignment_unanchored: dict | None
    alignment_error: str | None
    geometry_unavailable_reason: str | None
    ghost_path: list[GhostPoint]  # [] when geometry is unavailable
    extraction: ExtractionResult | None
    draft_graph: VenueGraph | None
    draft_revision: str | None
    findings: list[Finding]  # check_graph on the draft
    accepted_graph: VenueGraph | None
    accepted_revision: str | None
    graph_revision: str | None  # accepted graph revision (same as accepted_revision)
    scenario: Scenario
    scenario_hash: str
    current_run: FlowRun | None
    current_check: CheckResult | None
    iterations: list[dict]
    investigations: list[dict]
    ready_investigation_id: str | None
    allowed_interventions: list[str]
    approvals: list[Approval]


def _allowed(services: Services, s: Session) -> list[str]:
    if s.accepted_graph is None:
        return []
    return _allowed_for(services, s.accepted_graph, s.scenario)


def _allowed_for(services: Services, graph: VenueGraph, scenario: Scenario) -> list[str]:
    try:
        return list(services.allowed_interventions(graph, scenario))
    except ImportError:  # walktwin.agent not importable
        return []
    except Exception:  # noqa: BLE001 - a snapshot must always render
        log.exception("allowed_interventions failed for graph %s", graph.revision)
        return []


def render_url(sid: str, iteration: int, index: int) -> str:
    return f"/api/sessions/{sid}/renders/{iteration}/{index}.png"


def _with_render_urls(sid: str, start: int, iterations: list[dict]) -> list[dict]:
    for n, it in enumerate(iterations, start):
        for i, r in enumerate(it.get("renders") or []):
            if isinstance(r, dict):
                r["url"] = render_url(sid, n, i)
    return iterations


def _ghost_path(services: Services, s: Session) -> list[GhostPoint]:
    if (not s.alignment or not s.sfm or s.sfm.get("status") != "completed"
            or s.geometry_unavailable_reason):
        return []  # never draw a path from a reconstruction we do not trust
    try:
        frames = sorted(s.sfm.get("frames") or [], key=lambda f: f["t_s"])
        out = []
        for f in frames:
            x, y = services.to_graph_xy(s.alignment, f["center"])
            out.append(GhostPoint(t_s=float(f["t_s"]), x=float(x), y=float(y)))
        return out
    except Exception:  # noqa: BLE001 - a snapshot must always render
        log.exception("ghost path unavailable for session %s", s.id)
        return []


def _sfm_summary(sfm: dict | None) -> dict | None:
    if sfm is None:
        return None
    keep = ("status", "registered_fraction", "elapsed_ms", "error")
    return {**{k: sfm.get(k) for k in keep},
            "frame_count": len(sfm.get("frames") or []),
            "point_count": len(sfm.get("points") or [])}


def _preview(s: Session) -> dict | None:
    try:
        return sfm_preview(s.sfm)
    except Exception:  # noqa: BLE001 - a snapshot must always render
        log.exception("sfm preview unavailable for session %s", s.id)
        return None


def snapshot(services: Services, s: Session) -> SessionSnapshot:
    ready = s.ready_investigation()
    return SessionSnapshot(
        id=s.id, created_at=s.created_at,
        video=VideoInfo(sha256=s.video.sha256, duration_s=s.video.duration_s,
                        width=s.video.width, height=s.video.height,
                        url=f"/api/sessions/{s.id}/video"),
        anchor=s.anchor, pending_anchor=s.anchor,
        anchor_hint=s.anchor_hint, anchor_width_m=s.anchor_width_m,
        jobs=s.jobs, sfm=_sfm_summary(s.sfm), sfm_preview=_preview(s),
        alignment=s.alignment, alignment_unanchored=s.alignment_unanchored,
        alignment_error=s.alignment_error,
        geometry_unavailable_reason=s.geometry_unavailable_reason,
        ghost_path=_ghost_path(services, s),
        extraction=s.extraction, draft_graph=s.draft_graph, draft_revision=s.draft_revision,
        findings=check_graph(s.draft_graph, s.video.duration_s) if s.draft_graph else [],
        accepted_graph=s.accepted_graph, accepted_revision=s.accepted_revision,
        graph_revision=s.accepted_revision,
        scenario=s.scenario, scenario_hash=s.scenario.hash,
        current_run=s.current_run, current_check=s.current_check,
        iterations=s.iterations, investigations=s.investigations,
        ready_investigation_id=ready.get("investigation_id") if ready else None,
        allowed_interventions=_allowed(services, s),
        approvals=s.approvals,
    )


# --- helpers ------------------------------------------------------------------------


def _session(services: Services, sid: str) -> Session:
    s = services.store.get(sid)
    if s is None:
        raise ApiError(404, "not_found")
    return s


def _require_accepted(s: Session) -> VenueGraph:
    if s.accepted_graph is None:
        raise ApiError(409, "not_accepted")
    return s.accepted_graph


def _solve_checked(graph: VenueGraph, scenario: Scenario) -> tuple[FlowRun, CheckResult]:
    run = solve(graph, scenario, PARAMS)
    return run, check_run(graph, scenario, PARAMS, run)


def normalise_scenario(hazards: Sequence[Hazard], interventions: Sequence[str]) -> Scenario:
    """The one place a scenario is built: hazards sorted by (door_id, from_s) so the
    same hazard set always hashes the same, whatever order the judge dropped them in."""
    return Scenario(hazards=sorted(hazards, key=lambda h: (h.door_id, h.from_s)),
                    interventions=list(interventions))


def _scenario_for(graph: VenueGraph, scenario: Scenario) -> Scenario:
    """Drop hazards and interventions that name doors missing from ``graph``."""
    ids = {d.id for d in graph.doors}
    return normalise_scenario(
        [h for h in scenario.hazards if h.door_id in ids],
        [i for i in scenario.interventions if i.split(":", 1)[-1] in ids])


def _within(path: Path, root: Path) -> bool:
    try:
        return Path(path).resolve().is_relative_to(Path(root).resolve())
    except (OSError, ValueError):
        return False


def _clear_for_new_extraction(services: Services, s: Session) -> None:
    """R27: a new extraction is a new coordinate frame; drop what was built on the old one.

    That includes the anchor (it names the old draft's door ids, I1) and the
    approvals (they belong to the old accepted graph, M10)."""
    s.alignment = s.alignment_unanchored = None
    s.frame_scale = 1.0
    s.alignment_error = s.geometry_unavailable_reason = None
    if s.sfm and s.sfm.get("status") != "completed":
        s.geometry_unavailable_reason = f"sfm failed: {s.sfm.get('error') or 'unknown'}"[:300]
    s.iterations = []
    s.accepted_graph = s.current_run = s.current_check = None
    s.scenario = Scenario()
    s.anchor = None
    s.approvals = []
    services.store.cancel_jobs(s, "investigate", "superseded by a new extraction")


def _resolve_anchor(s: Session) -> None:
    """With a typed width, take the one door Argon marked ``anchor:`` in the new draft.
    The upload's door hint is only text for Argon (M8): Argon assigns its own ids."""
    if s.anchor is not None or s.anchor_width_m is None or s.draft_graph is None:
        return
    marked = [d.id for d in s.draft_graph.doors
              if any(ev.note.strip().lower().startswith("anchor:") for ev in d.evidence)]
    if len(marked) == 1:
        s.anchor = Anchor(door_id=marked[0], measured_width_m=s.anchor_width_m)


def _anchor_hint_text(s: Session) -> str | None:
    parts = [s.anchor_hint or ""]
    if s.anchor_width_m is not None:
        parts.append(f"Tape-measured clear width: {s.anchor_width_m:.2f} m.")
    text = " ".join(p for p in parts if p).strip()
    return text or None


def _start(services: Services, s: Session, key: str, kind: str, body, meta=None) -> str:
    try:
        services.store.start_job(s, key, kind, body, meta)
    except JobConflict:
        raise ApiError(409, "job_running", kind=kind) from None
    return key


def _start_sfm(services: Services, s: Session) -> None:
    store = services.store

    async def body() -> str | None:
        res = await asyncio.to_thread(services.run_sfm, s.video, store.dir(s.id) / "sfm")
        s.sfm = to_jsonable(res)
        if s.sfm.get("status") != "completed":
            err = s.sfm.get("error") or f"status {s.sfm.get('status')}"
            s.geometry_unavailable_reason = f"sfm failed: {err}"[:300]
            store.save(s)
            return err
        store.save(s)
        return None

    _start(services, s, "sfm", "sfm", body)


def _start_investigation(services: Services, s: Session, graph: VenueGraph,
                         scenario: Scenario, **meta: Any) -> str:
    store = services.store
    key = f"investigate:{graph.revision}:{scenario.hash}"

    async def body() -> str | None:
        client = services.make_client()
        env = await services.environment_id(client)
        out = store.dir(s.id) / "renders" / f"inv-{scenario.hash}-{secrets.token_hex(3)}"
        top = await services.render_topdown(graph, out, services.base_url,
                                            [h.door_id for h in scenario.hazards])
        inv = await services.investigate(
            client, graph, scenario, PARAMS, environment_id=env, topdown_png=top,
            deadline_s=services.investigate_deadline_s,
            sessions_dir=store.dir(s.id) / "investigations")
        d = to_jsonable(inv)
        if d.get("graph_revision") != graph.revision or d.get("scenario_hash") != scenario.hash:
            return "investigation tags do not match the requested graph revision and scenario"
        s.investigations.append(d)
        store.save(s)
        if d.get("status") != "completed":
            return f"investigation {d.get('status')}"
        return None

    return _start(services, s, key, "investigate", body,
                  {"graph_revision": graph.revision, "scenario_hash": scenario.hash, **meta})


PRECOMPUTE_MAX = MAX_INVESTIGATE_JOBS - 1  # M3: one slot stays free for the judge


def _precompute(services: Services, s: Session, graph: VenueGraph, run: FlowRun) -> list[str]:
    """Investigations for the busiest open exits by baseline flow: current scenario +
    fire there. Skips exits that are not open and scenarios with nothing to try (M2),
    and leaves one investigate slot free (M3)."""
    hazarded = {h.door_id for h in s.scenario.hazards}

    def flow(door_id: str) -> int:
        return sum(abs(x) for x in run.door_flows.get(door_id, []))

    exits = [d.id for d in graph.doors
             if OUTSIDE in (d.a, d.b) and d.state == "open" and d.id not in hazarded]
    budget = PRECOMPUTE_MAX - len(s.active_jobs("investigate"))
    keys: list[str] = []
    for door_id in sorted(exits, key=lambda i: (-flow(i), i)):
        if len(keys) >= budget:
            break
        sc = normalise_scenario([*s.scenario.hazards, Hazard(door_id=door_id, kind="fire")],
                                s.scenario.interventions)
        if not _allowed_for(services, graph, sc):
            continue
        try:
            keys.append(_start_investigation(services, s, graph, sc, precomputed_for=door_id))
        except ApiError:
            log.warning("investigate slots full; skipped precompute for %s", door_id)
    return keys


# --- request bodies -----------------------------------------------------------------


class ExtractBody(BaseModel):
    mode: Literal["static", "static_hifps", "agentic"] = "static_hifps"
    expected_revision: str | None = None


class RevisionBody(BaseModel):
    expected_revision: str


class GraphBody(BaseModel):
    expected_revision: str
    graph: VenueGraph


class AcceptBody(BaseModel):
    expected_revision: str
    anchor: Anchor | None = None  # same as POST /anchor then accept, in one request


class AnchorBody(BaseModel):
    expected_revision: str
    door_id: str
    measured_width_m: float


class ScenarioBody(BaseModel):
    expected_revision: str
    hazards: list[Hazard]


class InvestigateBody(BaseModel):
    expected_revision: str
    expected_scenario: str


class ApproveBody(BaseModel):
    expected_revision: str
    expected_scenario: str
    investigation_id: str
    intervention_id: str


# --- routes -------------------------------------------------------------------------

router = APIRouter(prefix="/api")
Svc = Depends(get_services)


@router.post("/sessions", status_code=201)
async def create_session(video: UploadFile = File(...),
                         anchor_door_hint: str | None = Form(None),
                         anchor_width_m: float | None = Form(None),
                         services: Services = Svc) -> dict:
    if anchor_width_m is not None and not (math.isfinite(anchor_width_m) and anchor_width_m > 0):
        raise ApiError(422, "invalid_anchor_width")
    store = services.store
    sid = store.new_id()
    sdir = store.dir(sid)
    suffix = Path(video.filename or "").suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,5}", suffix):
        suffix = ".bin"
    src = sdir / "upload" / f"original{suffix}"
    src.parent.mkdir(parents=True, exist_ok=True)
    try:
        size = 0
        with open(src, "wb") as f:
            while chunk := await video.read(1 << 20):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise ApiError(413, "too_large")
                f.write(chunk)
        try:
            prepared = await asyncio.to_thread(services.prepare_video, src, sdir / "video")
        except ValueError as e:
            raise ApiError(422, "too_long" if str(e) == "too_long" else "invalid_video",
                           detail=str(e)[:300]) from None
        except (subprocess.CalledProcessError, OSError, KeyError, IndexError) as e:
            raise ApiError(422, "invalid_video", detail=f"{type(e).__name__}"[:300]) from None
    except BaseException:
        shutil.rmtree(sdir, ignore_errors=True)
        raise

    # M8: the door hint is only text for Argon; door ids exist only after extraction.
    hint = (anchor_door_hint or "").strip() or None
    s = store.create(prepared, None, id=sid, anchor_hint=hint, anchor_width_m=anchor_width_m)
    _start_sfm(services, s)  # the judge's SfM path appears before Argon finishes
    return {"id": sid}


@router.get("/sessions/{sid}")
async def get_session(sid: str, services: Services = Svc) -> dict:
    return snapshot(services, _session(services, sid)).model_dump(mode="json")


@router.post("/sessions/{sid}/extract", status_code=202)
async def start_extract(sid: str, body: ExtractBody, services: Services = Svc) -> dict:
    s = _session(services, sid)
    if s.draft_graph is not None or body.expected_revision is not None:
        _stale(body.expected_revision, s.draft_revision)  # R27: required once a draft exists
    store = services.store
    mode = body.mode
    base, accepted_base = s.draft_revision, s.accepted_revision  # captured at request time
    hint = _anchor_hint_text(s)

    async def job() -> str | None:
        client = services.make_client()
        r = await services.extract(client, s.video, mode=mode,
                                   deadline_s=services.extract_deadline_s, anchor_hint=hint)
        if r.status != "completed" or r.graph is None:
            return f"extraction {r.status}: {r.error or 'no graph'}"[:1000]
        if s.draft_revision != base or s.accepted_revision != accepted_base:
            return "stale_draft: the draft changed during extraction; result not applied"
        s.extraction = r
        s.draft_graph = r.graph
        _clear_for_new_extraction(services, s)
        _resolve_anchor(s)
        store.save(s)
        return None

    return {"job": _start(services, s, "extract", "extract", job)}


@router.post("/sessions/{sid}/refine", status_code=202)
async def start_refine(sid: str, body: RevisionBody, services: Services = Svc) -> dict:
    s = _session(services, sid)
    if s.draft_graph is None:
        raise ApiError(409, "no_draft")
    _stale(body.expected_revision, s.draft_revision)
    if s.extraction is None or s.extraction.graph is None:
        raise ApiError(409, "no_extraction")
    if s.jobs.get("sfm") is not None and s.jobs["sfm"].status in ("queued", "running"):
        raise ApiError(409, "sfm_running")  # I11: geometry would be silently skipped
    store = services.store
    # Captured at request time: the job refines exactly what the human asked for.
    base, graph, extraction = s.draft_revision, s.draft_graph, s.extraction
    accepted_base = s.accepted_revision
    work_dir = store.dir(s.id) / "refine" / secrets.token_hex(4)
    stale = "stale_draft: the draft changed during refine; result not applied"

    def current() -> bool:
        return (s.draft_revision == base and s.accepted_revision == accepted_base
                and s.extraction is extraction)

    async def job() -> str | None:
        sfm = s.sfm if (s.sfm and s.sfm.get("status") == "completed") else None
        reason = None
        if s.sfm and s.sfm.get("status") != "completed":
            reason = f"sfm failed: {s.sfm.get('error') or 'unknown'}"
        if sfm is not None and s.alignment is None and s.extraction is extraction:
            # Fit once, on the iteration-0 (extraction) graph, then freeze.
            try:
                al, err = await asyncio.to_thread(services.fit_alignment, sfm,
                                                  extraction.graph), None
            except Exception as e:  # noqa: BLE001 - refine still runs without geometry
                al, err = None, f"{type(e).__name__}: {e}"[:500]
            if not current():  # I11: a new extraction (or edit) landed during the fit
                return stale
            if err is None:
                s.alignment_unanchored = to_jsonable(al)
                # the draft may already be in an anchored frame (accepted before the fit)
                s.alignment = (s.alignment_unanchored if s.frame_scale == 1.0 else
                               _scale_alignment(s.alignment_unanchored, s.frame_scale))
                s.alignment_error = None
            else:
                s.alignment_error = err
                reason = f"alignment failed: {err}"
        if not current():
            return stale
        alignment = s.alignment if sfm is not None else None
        if alignment is not None:
            # R30: a confidently wrong GLOMAP path only shows as a disagreeing scale badge.
            try:
                if services.scale_badge(alignment) == "disagrees":
                    reason = "scale disagrees"
            except Exception as e:  # noqa: BLE001
                reason = f"scale badge unavailable: {type(e).__name__}: {e}"
        if reason is not None:
            sfm = alignment = None  # the loop runs on model-reported counts only
        s.geometry_unavailable_reason = reason[:300] if reason else None
        store.save(s)
        client = services.make_client()
        final, iterations = await services.refine(
            client, graph, s.video, extraction, sfm=sfm if alignment else None,
            alignment=alignment, base_url=services.base_url, max_iterations=4,
            deadline_s=services.refine_deadline_s, work_dir=work_dir)
        if not current():
            return stale
        its = [to_jsonable(i) for i in iterations]
        for it in its:
            it.setdefault("kind", "round")  # D1 (lane F3's loop writes it itself)
        its = _with_render_urls(s.id, len(s.iterations), its)
        s.iterations.extend(its)
        s.draft_graph = final
        store.save(s)
        if its and its[-1].get("stop_reason") == "provider_failed":
            return "provider_failed"
        return None

    return {"job": _start(services, s, "refine", "refine", job)}


@router.put("/sessions/{sid}/graph")
async def put_graph(sid: str, body: GraphBody, services: Services = Svc) -> dict:
    s = _session(services, sid)
    if s.draft_graph is None:
        raise ApiError(409, "no_draft")
    _stale(body.expected_revision, s.draft_revision)
    if body.graph.anchor != s.draft_graph.anchor:  # D2: only accept applies an anchor
        raise ApiError(422, "anchor_server_owned")
    s.draft_graph = body.graph
    services.store.save(s)
    findings = check_graph(body.graph, s.video.duration_s)
    return {"revision": body.graph.revision,
            "findings": [f.model_dump(mode="json") for f in findings]}


def _valid_anchor(graph: VenueGraph, anchor: Anchor) -> None:
    if not (math.isfinite(anchor.measured_width_m) and anchor.measured_width_m > 0):
        raise ApiError(422, "invalid_anchor_width")
    if not any(d.id == anchor.door_id for d in graph.doors):
        raise ApiError(422, "anchor_door_missing", door_id=anchor.door_id)


@router.post("/sessions/{sid}/anchor")
async def set_anchor(sid: str, body: AnchorBody, services: Services = Svc) -> dict:
    """D2: store the tape-measured door. The draft is unchanged until accept applies it."""
    s = _session(services, sid)
    if s.draft_graph is None:
        raise ApiError(409, "no_draft")
    _stale(body.expected_revision, s.draft_revision)
    if not (math.isfinite(body.measured_width_m) and body.measured_width_m > 0):
        raise ApiError(422, "invalid_anchor_width")
    anchor = Anchor(door_id=body.door_id, measured_width_m=body.measured_width_m)
    _valid_anchor(s.draft_graph, anchor)
    s.anchor = anchor
    services.store.save(s)
    return {"pending_anchor": anchor.model_dump(mode="json"), "draft_revision": s.draft_revision}


def _anchor_factor(graph: VenueGraph, anchor: Anchor) -> float | None:
    """The apply_anchor factor, or None when ``graph`` already carries this anchor."""
    door = next(d for d in graph.doors if d.id == anchor.door_id)
    if door.clear_width.basis == "anchor_measured" and graph.anchor == anchor:
        return None  # applied at an earlier accept; never scale twice
    w = door.clear_width
    return anchor.measured_width_m / ((w.low_m + w.high_m) / 2)


def _geometry_hash(geometry: Any) -> str | None:
    d = to_jsonable(geometry)
    return d.get("alignment_hash") if isinstance(d, dict) else None


def _accepted_iteration(index: int, graph: VenueGraph, findings: list[Finding],
                        geometry: Any, geometry_error: str | None) -> dict:
    """D1 "accepted": the accepted graph rescored under the accepted-frame alignment."""
    return {"index": index, "kind": "accepted", "graph_revision": graph.revision,
            "discrepancy_count": 0, "applied": [], "rejected": [],
            "findings": [f.model_dump(mode="json") for f in findings],
            "geometry": to_jsonable(geometry), "geometry_error": geometry_error,
            "renders": [], "receipt": None, "stop_reason": None,
            "rejected_geometry": None, "critique": None}


@router.post("/sessions/{sid}/accept")
async def accept(sid: str, body: AcceptBody, services: Services = Svc) -> dict:
    s = _session(services, sid)
    if s.draft_graph is None:
        raise ApiError(409, "no_draft")
    _stale(body.expected_revision, s.draft_revision)
    anchor = body.anchor or s.anchor  # server-owned: never the draft's own anchor field
    graph = s.draft_graph
    factor = None
    if anchor is not None:
        _valid_anchor(graph, anchor)
        factor = _anchor_factor(graph, anchor)
        if factor is not None:
            graph = apply_anchor(graph, anchor)
    findings = check_graph(graph, s.video.duration_s)
    if has_errors(findings):
        raise ApiError(422, "graph_errors",
                       findings=[f.model_dump(mode="json") for f in findings])
    scenario = _scenario_for(graph, s.scenario)

    # D3: move the frozen alignment into the accepted frame with the same factor.
    def state() -> tuple:
        return (s.draft_revision, s.accepted_revision, s.scenario.hash, id(s.alignment),
                s.frame_scale, id(s.sfm))

    before = state()
    alignment = s.alignment
    sfm_ok = s.sfm is not None and s.sfm.get("status") == "completed"
    reason = s.geometry_unavailable_reason
    if factor is not None and alignment is not None:
        alignment = _scale_alignment(alignment, factor)
        if sfm_ok and reason in (None, "scale disagrees"):
            # The badge cross-checks the anchor's scale: re-check it in the accepted frame.
            try:
                reason = "scale disagrees" if services.scale_badge(alignment) == "disagrees" else None
            except Exception as e:  # noqa: BLE001
                reason = f"scale badge unavailable: {type(e).__name__}: {e}"[:300]
    use_geometry = alignment is not None and sfm_ok and not reason
    run, check = await asyncio.to_thread(_solve_checked, graph, scenario)  # M1
    geometry, geometry_error = None, None
    if use_geometry:
        try:
            geometry = await asyncio.to_thread(services.score_geometry, graph, s.sfm,
                                               alignment, s.video)
        except Exception as e:  # noqa: BLE001 - accept never fails on a measurement
            log.exception("accept: geometry score failed for session %s", s.id)
            geometry_error = f"{type(e).__name__}: {e}"[:300]
    # Another request may have run while we solved and scored.
    if state() != before:
        raise ApiError(409, "stale", what="graph", expected=body.expected_revision,
                       current=s.draft_revision)

    if body.anchor is not None:
        s.anchor = body.anchor
    if factor is not None:
        s.frame_scale *= factor
        if s.alignment is not None:
            s.alignment_unanchored = s.alignment_unanchored or s.alignment
            s.alignment = alignment
            s.geometry_unavailable_reason = reason
    s.draft_graph = s.accepted_graph = graph
    s.scenario, s.current_run, s.current_check = scenario, run, check
    # One "accepted" row per (graph, alignment): a repeated accept does not add another.
    last = s.iterations[-1] if s.iterations else {}
    if (last.get("kind") != "accepted" or last.get("graph_revision") != graph.revision
            or _geometry_hash(last.get("geometry")) != _geometry_hash(geometry)):
        s.iterations.append(_accepted_iteration(len(s.iterations), graph, findings,
                                                geometry, geometry_error))
    services.store.cancel_jobs(s, "investigate", "superseded by a new accept")
    jobs = _precompute(services, s, graph, run) if check.ok else []
    services.store.save(s)
    return {"revision": graph.revision, "scenario_hash": scenario.hash,
            "run": run.model_dump(mode="json"), "check": to_jsonable(check),
            "findings": [f.model_dump(mode="json") for f in findings],
            "alignment_hash": s.alignment.get("hash") if s.alignment else None,
            "investigation_jobs": jobs}


@router.post("/sessions/{sid}/scenario")
async def set_scenario(sid: str, body: ScenarioBody, services: Services = Svc) -> dict:
    s = _session(services, sid)
    graph = _require_accepted(s)
    _stale(body.expected_revision, s.accepted_revision)
    ids = {d.id for d in graph.doors}
    unknown = sorted({h.door_id for h in body.hazards} - ids)
    if unknown:
        raise ApiError(422, "unknown_door", doors=unknown)
    scenario = normalise_scenario(body.hazards, s.scenario.interventions)
    hash_before = s.scenario.hash
    run, check = await asyncio.to_thread(_solve_checked, graph, scenario)  # M1
    _stale(body.expected_revision, s.accepted_revision)  # another request ran meanwhile
    _stale(hash_before, s.scenario.hash, "scenario")
    s.scenario, s.current_run, s.current_check = scenario, run, check
    services.store.save(s)
    ready = s.ready_investigation()
    return {"scenario_hash": scenario.hash, "scenario": scenario.model_dump(mode="json"),
            "run": run.model_dump(mode="json"), "check": to_jsonable(check),
            "ready_investigation_id": ready.get("investigation_id") if ready else None}


@router.post("/sessions/{sid}/investigate", status_code=202)
async def start_investigate(sid: str, body: InvestigateBody, services: Services = Svc) -> dict:
    s = _session(services, sid)
    graph = _require_accepted(s)
    _stale(body.expected_revision, s.accepted_revision)
    _stale(body.expected_scenario, s.scenario.hash, "scenario")
    ready = s.ready_investigation()
    if ready is not None:
        return {"job": None, "investigation_id": ready.get("investigation_id"), "reused": True}
    key = _start_investigation(services, s, graph, s.scenario)
    return {"job": key, "investigation_id": None, "reused": False}


@router.post("/sessions/{sid}/approve")
async def approve(sid: str, body: ApproveBody, services: Services = Svc) -> dict:
    s = _session(services, sid)
    graph = _require_accepted(s)
    inv = next((i for i in s.investigations
                if i.get("investigation_id") == body.investigation_id), None)
    if inv is None:
        raise ApiError(404, "investigation_not_found")
    if (inv.get("graph_revision") != s.accepted_revision
            or inv.get("scenario_hash") != s.scenario.hash):
        raise ApiError(409, "stale_investigation",
                       investigation={"graph_revision": inv.get("graph_revision"),
                                      "scenario_hash": inv.get("scenario_hash")},
                       current={"graph_revision": s.accepted_revision,
                                "scenario_hash": s.scenario.hash})
    _stale(body.expected_revision, s.accepted_revision)
    _stale(body.expected_scenario, s.scenario.hash, "scenario")
    result = next((r for r in inv.get("results") or []
                   if r.get("intervention_id") == body.intervention_id), None)
    if result is None or result.get("check_ok") is not True:
        raise ApiError(422, "intervention_unchecked", intervention_id=body.intervention_id)
    if body.intervention_id not in services.allowed_interventions(graph, s.scenario):
        raise ApiError(422, "intervention_not_allowed", intervention_id=body.intervention_id)

    scenario = normalise_scenario(s.scenario.hazards,
                                  [*s.scenario.interventions, body.intervention_id])
    rev_before, hash_before = s.accepted_revision, s.scenario.hash
    run, check = await asyncio.to_thread(_solve_checked, graph, scenario)  # M1
    if not check.ok:
        raise ApiError(422, "check_failed", violations=check.violations[:20])
    notes_dir = services.store.dir(s.id) / "notes"
    note_path = notes_dir / f"approval-{len(s.approvals) + 1}.md"
    approval = Approval(intervention_id=body.intervention_id,
                        investigation_id=body.investigation_id,
                        graph_revision=graph.revision, scenario_hash=scenario.hash,
                        run_id=run.run_id, note_path=str(note_path),
                        approved_at=_iso_now())
    # Draft from the post-approval state without committing it yet: if drafting
    # raises, nothing changes.
    preview = s.model_copy(deep=True, update={"scenario": scenario, "current_run": run,
                                              "current_check": check,
                                              "approvals": [*s.approvals, approval]})
    note = await asyncio.to_thread(services.draft_note, preview, approval)
    # Another request may have run while the note was drafted.
    _stale(rev_before, s.accepted_revision)
    _stale(hash_before, s.scenario.hash, "scenario")
    if any(a.note_path == approval.note_path for a in s.approvals):
        raise ApiError(409, "stale", what="approvals")
    if not note.startswith(DRAFT_HEADER):
        note = f"{DRAFT_HEADER}\n\n{note}"
    notes_dir.mkdir(parents=True, exist_ok=True)
    note_path.write_text(note, encoding="utf-8")

    s.scenario, s.current_run, s.current_check = scenario, run, check
    s.approvals.append(approval)
    services.store.save(s)
    return {"approval": approval.model_dump(mode="json"), "scenario_hash": scenario.hash,
            "run": run.model_dump(mode="json"), "check": to_jsonable(check), "note": note}


@router.get("/sessions/{sid}/report")
async def get_report(sid: str, services: Services = Svc) -> dict:
    s = _session(services, sid)
    report = to_jsonable(services.build_report(s))
    if isinstance(report, dict):
        latest = (_note_text(s.approvals[-1], services.store.dir(s.id))
                  if s.approvals else None)
        report["security_note"] = latest or ""
    return report


@router.get("/sessions/{sid}/report.html")
async def get_report_html(sid: str, services: Services = Svc) -> HTMLResponse:
    s = _session(services, sid)
    return HTMLResponse(services.render_html(services.build_report(s)))


def _note_text(approval: Approval, session_dir: Path) -> str | None:
    path = Path(approval.note_path)
    if not _within(path, session_dir):
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


@router.get("/sessions/{sid}/approvals/{index}/note")
async def get_note(sid: str, index: int, services: Services = Svc) -> Response:
    s = _session(services, sid)
    if not 0 <= index < len(s.approvals):
        raise ApiError(404, "not_found")
    text = _note_text(s.approvals[index], services.store.dir(s.id))
    if text is None:
        raise ApiError(404, "note_missing")
    return Response(text, media_type="text/markdown; charset=utf-8")


@router.get("/sessions/{sid}/renders/{iteration}/{index}.png")
async def get_render(sid: str, iteration: int, index: int,
                     services: Services = Svc) -> FileResponse:
    s = _session(services, sid)
    if not 0 <= iteration < len(s.iterations):
        raise ApiError(404, "not_found")
    renders = s.iterations[iteration].get("renders") or []
    if not 0 <= index < len(renders) or not isinstance(renders[index], dict):
        raise ApiError(404, "not_found")
    path = Path(str(renders[index].get("path") or ""))
    # Only paths recorded by the loop are served, and only PNG files.
    if (path.suffix.lower() != ".png" or not _within(path, services.store.dir(s.id))
            or not path.is_file()):
        raise ApiError(404, "render_missing")
    return FileResponse(path, media_type="image/png")


@router.get("/sessions/{sid}/video")
async def get_video(sid: str, services: Services = Svc) -> FileResponse:
    s = _session(services, sid)
    if not _within(s.video.path, services.store.dir(s.id)) or not s.video.path.is_file():
        raise ApiError(404, "video_missing")
    return FileResponse(s.video.path, media_type="video/mp4")


@router.get("/sessions/{sid}/frame")
async def get_frame(sid: str, t: float = Query(...), services: Services = Svc) -> FileResponse:
    s = _session(services, sid)
    if not 0 <= t <= s.video.duration_s:
        raise ApiError(422, "bad_time", duration_s=s.video.duration_s)
    out = services.store.dir(s.id) / "frames" / f"t{round(t * 1000):08d}.jpg"
    if not out.exists():
        try:
            await asyncio.to_thread(extract_frame, s.video.path, t, out)
        except subprocess.CalledProcessError:
            raise ApiError(422, "no_frame") from None
        if not out.exists():
            raise ApiError(422, "no_frame")
    return FileResponse(out, media_type="image/jpeg")


def _iso_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --- app ----------------------------------------------------------------------------


def create_app(static_dir: Path | None = DIST) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        services = app.dependency_overrides.get(get_services, get_services)()
        await services.store.shutdown()

    app = FastAPI(title="WalkTwin", lifespan=lifespan)

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse({"error": exc.error, **jsonable_encoder(exc.extra)},
                            status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse({"error": "invalid_request", "detail": jsonable_encoder(exc.errors())},
                            status_code=422)

    app.include_router(router)

    @app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                   include_in_schema=False)
    async def _api_not_found(path: str) -> JSONResponse:
        return JSONResponse({"error": "not_found"}, status_code=404)

    if static_dir is not None and Path(static_dir).is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")  # last
    return app


app = create_app()
