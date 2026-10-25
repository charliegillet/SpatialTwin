"""Session state for the WalkTwin API: in-memory sessions persisted as JSON.

Each session lives at ``<root>/sessions/<id>/session.json`` and is rewritten
after every mutation. Results from modules that other lanes own (SfM,
alignment, loop iterations, investigations) are stored as plain JSON dicts so
this module never imports them; typed contracts are used where they exist.

Jobs are ``asyncio`` tasks tracked in ``session.jobs``. A job body never
crashes the server: exceptions are captured into ``JobState.error``.
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import re
import secrets
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal

from pydantic import BaseModel, Field

from .checker import CheckResult
from .contracts import Anchor, Scenario, VenueGraph
from .extract import ExtractionResult
from .flow import FlowRun
from .media import PreparedVideo

_ID_RE = re.compile(r"^[0-9a-f]{12}$")
ACTIVE = ("queued", "running")
MAX_INVESTIGATE_JOBS = 3


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class JobState(BaseModel):
    kind: str
    status: Literal["queued", "running", "done", "failed"]
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    meta: dict = Field(default_factory=dict)


class Approval(BaseModel):
    intervention_id: str
    investigation_id: str
    graph_revision: str
    scenario_hash: str
    run_id: str
    note_path: str
    approved_at: str


class Session(BaseModel):
    id: str
    video: PreparedVideo
    anchor: Anchor | None = None
    anchor_hint: str | None = None
    anchor_width_m: float | None = None
    sfm: dict | None = None  # walktwin.sfm.SfmResult as JSON
    alignment: dict | None = None  # walktwin.sfm.Alignment as JSON (frozen once fitted)
    alignment_error: str | None = None
    draft_graph: VenueGraph | None = None
    accepted_graph: VenueGraph | None = None
    scenario: Scenario = Field(default_factory=Scenario)
    current_run: FlowRun | None = None
    current_check: CheckResult | None = None
    iterations: list[dict] = Field(default_factory=list)  # walktwin.loop.Iteration
    extraction: ExtractionResult | None = None
    investigations: list[dict] = Field(default_factory=list)  # walktwin.agent.Investigation
    approvals: list[Approval] = Field(default_factory=list)
    jobs: dict[str, JobState] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now)

    @property
    def draft_revision(self) -> str | None:
        return self.draft_graph.revision if self.draft_graph else None

    @property
    def accepted_revision(self) -> str | None:
        return self.accepted_graph.revision if self.accepted_graph else None

    def ready_investigation(self) -> dict | None:
        """Latest completed investigation tagged with the current revision and scenario."""
        if self.accepted_graph is None:
            return None
        rev, s_hash = self.accepted_graph.revision, self.scenario.hash
        for inv in reversed(self.investigations):
            if (inv.get("status") == "completed" and inv.get("graph_revision") == rev
                    and inv.get("scenario_hash") == s_hash):
                return inv
        return None

    def active_jobs(self, kind: str) -> list[str]:
        return [k for k, j in self.jobs.items() if j.kind == kind and j.status in ACTIVE]


def to_jsonable(obj: Any) -> Any:
    """Pydantic models, dataclasses, namespaces and Paths -> plain JSON values."""
    def default(o: Any) -> Any:
        if isinstance(o, BaseModel):
            return o.model_dump(mode="json")
        if dataclasses.is_dataclass(o) and not isinstance(o, type):
            return dataclasses.asdict(o)
        if isinstance(o, Path):
            return str(o)
        if isinstance(o, (set, frozenset)):
            return sorted(o)
        if hasattr(o, "__dict__"):
            return vars(o)
        return str(o)

    if obj is None:
        return None
    return json.loads(json.dumps(obj, default=default))


class JobConflict(Exception):
    """Another job of this kind is running (or the investigate slots are full)."""


class SessionStore:
    """In-memory sessions keyed by id, persisted under ``root/sessions/<id>``."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self._sessions: dict[str, Session] = {}
        self._tasks: dict[tuple[str, str], asyncio.Task] = {}

    # -- paths / ids -------------------------------------------------------------
    @staticmethod
    def new_id() -> str:
        return secrets.token_hex(6)

    @staticmethod
    def valid_id(sid: str) -> bool:
        return bool(_ID_RE.match(sid))

    def dir(self, sid: str) -> Path:
        if not self.valid_id(sid):
            raise ValueError(f"invalid session id {sid!r}")
        return self.root / "sessions" / sid

    # -- crud ----------------------------------------------------------------------
    def create(self, video: PreparedVideo, anchor: Anchor | None = None, *,
               id: str | None = None, anchor_hint: str | None = None,
               anchor_width_m: float | None = None) -> Session:
        sid = id or self.new_id()
        s = Session(id=sid, video=video, anchor=anchor, anchor_hint=anchor_hint,
                    anchor_width_m=anchor_width_m)
        self._sessions[sid] = s
        self.save(s)
        return s

    def get(self, sid: str) -> Session | None:
        if not self.valid_id(sid):
            return None
        s = self._sessions.get(sid)
        if s is not None:
            return s
        path = self.dir(sid) / "session.json"
        if not path.exists():
            return None
        s = Session.model_validate_json(path.read_text())
        for j in s.jobs.values():  # tasks from a previous process are gone
            if j.status in ACTIVE:
                j.status, j.error, j.finished_at = "failed", "server restarted", _now()
        self._sessions[sid] = s
        return s

    def save(self, session: Session) -> None:
        d = self.dir(session.id)
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "session.json.tmp"
        tmp.write_text(session.model_dump_json())
        tmp.replace(d / "session.json")

    # -- jobs ----------------------------------------------------------------------
    def start_job(self, session: Session, key: str, kind: str,
                  body: Callable[[], Awaitable[str | None]], meta: dict | None = None) -> JobState:
        """Schedule ``body`` as an asyncio task tracked as ``session.jobs[key]``.

        ``body`` returns ``None`` on success or an error string for a soft failure
        (a provider result that is not ``completed``). Raises ``JobConflict`` when a
        job of that kind is running, or when the investigate slots are full.
        """
        active = session.active_jobs(kind)
        limit = MAX_INVESTIGATE_JOBS if kind == "investigate" else 1
        if len(active) >= limit or key in active:
            raise JobConflict(kind)
        job = JobState(kind=kind, status="queued", meta=meta or {})
        session.jobs[key] = job
        self.save(session)
        sid = session.id

        async def run() -> None:
            job.status, job.started_at = "running", _now()
            self._save_id(sid)
            try:
                err = await body()
                job.status, job.error = ("failed", err) if err else ("done", None)
            except asyncio.CancelledError:
                job.status, job.error = "failed", job.error or "cancelled"
                raise
            except Exception as e:  # noqa: BLE001 - jobs must never crash the server
                job.status, job.error = "failed", f"{type(e).__name__}: {e}"[:1000]
            finally:
                job.finished_at = _now()
                self._save_id(sid)
                self._tasks.pop((sid, key), None)

        self._tasks[(sid, key)] = asyncio.create_task(run(), name=f"{sid}:{key}")
        return job

    def cancel_jobs(self, session: Session, kind: str, reason: str) -> list[str]:
        """Cancel active jobs of ``kind``; their slots are freed immediately."""
        cancelled = []
        for key in session.active_jobs(kind):
            job = session.jobs[key]
            job.status, job.error, job.finished_at = "failed", reason, _now()
            task = self._tasks.pop((session.id, key), None)
            if task is not None:
                task.cancel()
            cancelled.append(key)
        if cancelled:
            self.save(session)
        return cancelled

    async def shutdown(self) -> None:
        tasks = list(self._tasks.values())
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _save_id(self, sid: str) -> None:
        s = self._sessions.get(sid)
        if s is not None:
            self.save(s)
