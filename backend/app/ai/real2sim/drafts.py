"""Real2Sim draft orchestration: one background pipeline per draft, persisted in the venue registry.

A draft goes ``extracting`` -> ``checking`` -> (``critiquing``) -> ``ready`` (or ``failed``):

1. read: a live Argon extraction (``extract.py``; thought summaries stream into the event log as they arrive) or a
   saved run from disk (``fixtures.py``; labelled ``synthetic`` or ``saved_run``, never presented as live);
2. compile + check: the local compiler builds a preview VenueV2 and ``graph_checks`` types its defects;
3. critique: only when there are errors, at most ``critique_rounds`` chained rounds (``critique.py``), each kept only
   if the local rule says it improved;
4. render: the evidence overlay and the top-down picture for the operator.

Nothing here makes a venue usable. Accept (``accept``) recompiles with the operator's controllable doors, headcount
and scale, re-runs the graph checks, and stores the venue through ``VenueRegistry.accept_draft`` under the draft's
compare-and-set revision, so a stale screen gets a 409 instead of overwriting a newer reading.

Persistence: the registry payload holds the source metadata, the draft, the compile report, checks, rounds, bounded
thought summaries, provenance, receipts (provider interaction ids hashed exactly as the probes hash them), errors and
timings. The raw interaction id lives only in memory, to chain the critique. The source bytes, overlay and top-down
PNGs live under the runtime directory (gitignored). The per-draft event log is in memory and bounded; after a restart
the event stream is re-synthesized from the persisted status.
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import dataclasses
import hashlib
import io
import json
import os
import re
import secrets
import sqlite3
import time
import warnings
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, Iterable, List, Optional

from PIL import Image, ImageOps, UnidentifiedImageError

from backend.app.ai.grounding.adapter import MAX_IMAGE_DIMENSION, MAX_IMAGE_PIXELS, GroundingAdapter
from backend.app.ai.real2sim.critique import (
    DEFAULT_CRITIQUE_DEADLINE_SECONDS,
    Assessment,
    clamp_rounds,
    hash_identifier,
    run_critique_round,
)
from backend.app.ai.real2sim.extract import (
    SOURCE_MIME_TYPES,
    THINKING_LEVELS,
    DraftExtractor,
    ExtractionResult,
    SourceDocument,
)
from backend.app.ai.real2sim.fixtures import SavedRun, provenance_label
from backend.app.ai.real2sim.schema import CompileReport, CompileResult, SourceImage, VenueDraftV1
from backend.app.venues.graph_checks import GraphIssue, check_venue, errors_in, summary
from backend.app.venues.model import BUILTIN_VENUE_ID, VENUE_ID_PATTERN
from backend.app.venues.registry import RegistryConflict, venue_registry

REPO_ROOT = Path(__file__).resolve().parents[4]
RUNTIME_DIR_ENV = "SPATIALTWIN_REAL2SIM_DIR"
CRITIQUE_ROUNDS_ENV = "SPATIALTWIN_REAL2SIM_CRITIQUE_ROUNDS"
DRAFT_ID_PATTERN = r"^r2s-[0-9a-f]{24}$"
_DRAFT_ID = re.compile(DRAFT_ID_PATTERN)
_VENUE_ID = re.compile(VENUE_ID_PATTERN)
MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_BASE64_CHARS = ((MAX_SOURCE_BYTES + 2) // 3) * 4
MAX_CONTROLLABLE_DOORS = 3
MAX_EVENTS = 400
MAX_PAYLOAD_THOUGHTS = 120
MAX_LOGS = 32
DEFAULT_PING_SECONDS = 15.0
PDF_CANVAS_WIDTH_PX = 1600
A4_LANDSCAPE_PT = (842.0, 595.0)
IN_PROGRESS = ("extracting", "checking", "critiquing")
SOURCE_SUFFIX = {"image/jpeg": "jpg", "image/png": "png", "application/pdf": "pdf"}
PAPER = (255, 255, 255)

CompileFn = Callable[..., CompileResult]
CheckFn = Callable[[Any], List[GraphIssue]]
OverlayFn = Callable[[bytes, VenueDraftV1, CompileResult], bytes]
TopdownFn = Callable[[Any], bytes]


class Real2SimError(Exception):
    """An application-owned code with the HTTP status the route returns and optional structured detail."""

    def __init__(self, code: str, http_status: int, **extra: Any):
        super().__init__(code)
        self.code = code
        self.http_status = http_status
        self.extra = extra


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def runtime_root(explicit: Optional[Path] = None) -> Path:
    return Path(explicit) if explicit is not None else Path(
        os.environ.get(RUNTIME_DIR_ENV) or REPO_ROOT / "runtime" / "real2sim")


def critique_rounds_from_env() -> int:
    return clamp_rounds(os.environ.get(CRITIQUE_ROUNDS_ENV, "1"))


def valid_draft_id(draft_id: Any) -> bool:
    return isinstance(draft_id, str) and bool(_DRAFT_ID.match(draft_id))


# --- source validation -------------------------------------------------------------------------------------------

_MAGIC = {"image/jpeg": b"\xff\xd8\xff", "image/png": b"\x89PNG\r\n\x1a\n", "application/pdf": b"%PDF-"}
_MEDIABOX = re.compile(rb"/MediaBox\s*\[\s*(-?[0-9.]+)\s+(-?[0-9.]+)\s+(-?[0-9.]+)\s+(-?[0-9.]+)\s*\]")
_ROTATE = re.compile(rb"/Rotate\s+(-?[0-9]+)")


def _pdf_page_size(data: bytes) -> tuple[float, float, str]:
    """Page 1 size in points from the first MediaBox, or a declared A4-landscape default.

    Pages in compressed object streams hide their MediaBox; the default is then declared, not guessed silently.
    """
    match = _MEDIABOX.search(data)
    if match:
        try:
            x0, y0, x1, y1 = (float(value) for value in match.groups())
        except ValueError:
            x0 = y0 = x1 = y1 = 0.0
        width, height = abs(x1 - x0), abs(y1 - y0)
        if width > 0 and height > 0 and 0.2 <= width / height <= 5.0:
            rotate = _ROTATE.search(data)
            if rotate and int(rotate.group(1)) % 180 == 90:
                width, height = height, width
            return width, height, "mediabox"
    return A4_LANDSCAPE_PT[0], A4_LANDSCAPE_PT[1], "assumed_a4_landscape"


def decode_source(image_base64: Any, mime_type: Any, source_kind: str) -> tuple[SourceDocument, List[str]]:
    """Validate an uploaded source. Returns the document and plain-language notes about what was normalized."""
    if mime_type not in SOURCE_MIME_TYPES:
        raise Real2SimError("unsupported_mime_type", 415)
    if not isinstance(image_base64, str) or not image_base64:
        raise Real2SimError("source_required", 422)
    if len(image_base64) > MAX_BASE64_CHARS:
        raise Real2SimError("source_too_large", 413)
    try:
        data = base64.b64decode(image_base64, validate=True)
    except (binascii.Error, ValueError):
        raise Real2SimError("invalid_source_encoding", 422) from None
    if not data:
        raise Real2SimError("source_required", 422)
    if len(data) > MAX_SOURCE_BYTES:
        raise Real2SimError("source_too_large", 413)
    if (mime_type == "application/pdf") != (source_kind == "pdf"):
        raise Real2SimError("source_kind_mismatch", 422)
    if not data.startswith(_MAGIC[mime_type]):
        raise Real2SimError("source_mime_mismatch", 422)
    notes: List[str] = []
    if mime_type == "application/pdf":
        width_pt, height_pt, basis = _pdf_page_size(data)
        canvas_h = max(1, min(MAX_IMAGE_DIMENSION, round(PDF_CANVAS_WIDTH_PX * height_pt / width_pt)))
        if basis != "mediabox":
            notes.append("PDF page size unreadable; assumed A4 landscape (declared)")
        notes.append("PDF page 1 only; the overlay is drawn on a blank page of the same proportions")
        image = SourceImage(PDF_CANVAS_WIDTH_PX, canvas_h, hashlib.sha256(data).hexdigest(), mime_type)
        return SourceDocument(data, mime_type, source_kind, image, basis), notes
    expected_format = "JPEG" if mime_type == "image/jpeg" else "PNG"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as opened:
                width, height = opened.size
                if (opened.format != expected_format or min(width, height) <= 0
                        or max(width, height) > MAX_IMAGE_DIMENSION or width * height > MAX_IMAGE_PIXELS):
                    raise Real2SimError("invalid_source_dimensions", 422)
                opened.verify()
            with Image.open(io.BytesIO(data)) as opened:
                opened.load()
                orientation = opened.getexif().get(0x0112, 1)
                if orientation in (2, 3, 4, 5, 6, 7, 8):
                    # What Argon reads, what the overlay is drawn on and what the operator sees must agree.
                    upright = ImageOps.exif_transpose(opened)
                    if upright.mode not in ("RGB", "L") and expected_format == "JPEG":
                        upright = upright.convert("RGB")
                    buffer = io.BytesIO()
                    upright.save(buffer, format=expected_format, **({"quality": 92} if expected_format == "JPEG" else {}))
                    data = buffer.getvalue()
                    width, height = upright.size
                    notes.append(f"rotated upright from EXIF orientation {orientation}")
    except Real2SimError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise Real2SimError("invalid_source_image", 422) from None
    image = SourceImage(width, height, hashlib.sha256(data).hexdigest(), mime_type)
    return SourceDocument(data, mime_type, source_kind, image, None), notes


# --- event log (SSE replay) --------------------------------------------------------------------------------------

@dataclass(frozen=True)
class DraftEvent:
    id: int
    event: str
    data: Dict[str, Any]

    def encode(self) -> str:
        return f"id: {self.id}\nevent: {self.event}\ndata: {json.dumps(self.data, separators=(',', ':'))}\n\n"


class EventLog:
    """Bounded, replayable per-draft log. Single event loop; ``stream`` replays after ``Last-Event-ID`` then
    follows live events, sends ``: ping`` comments while idle and ends after the terminal event."""

    def __init__(self, max_events: int = MAX_EVENTS):
        self.max_events = max_events
        self.events: List[DraftEvent] = []
        self.next_id = 1
        self.closed = False
        self._changed: Optional[asyncio.Event] = None

    @property
    def last_id(self) -> int:
        return self.next_id - 1

    def append(self, event: str, data: Dict[str, Any], terminal: bool = False) -> Optional[DraftEvent]:
        if self.closed:
            return None
        entry = DraftEvent(self.next_id, event, data)
        self.next_id += 1
        self.events.append(entry)
        if len(self.events) > self.max_events:
            del self.events[0]
        if terminal:
            self.closed = True
        if self._changed is not None:
            self._changed.set()
            self._changed = None
        return entry

    def after(self, last_id: int) -> List[DraftEvent]:
        return [entry for entry in self.events if entry.id > last_id]

    async def _wait(self, timeout: float) -> bool:
        if self._changed is None:
            self._changed = asyncio.Event()
        changed = self._changed
        try:
            await asyncio.wait_for(changed.wait(), timeout)
            return True
        except (asyncio.TimeoutError, TimeoutError):
            return False

    async def stream(self, last_event_id: int = 0, ping_seconds: float = DEFAULT_PING_SECONDS) -> AsyncIterator[str]:
        cursor = max(0, int(last_event_id))
        # A cursor beyond this log means the log was rebuilt (server restart or eviction) with fresh ids; following it
        # would skip everything, including the terminal event, on every reconnect. Replay the retained log instead.
        if cursor > self.last_id:
            cursor = 0
        while True:
            pending = self.after(cursor)
            for entry in pending:
                yield entry.encode()
                cursor = entry.id
            if self.closed and not self.after(cursor):
                return
            if not pending and not await self._wait(ping_seconds):
                yield ": ping\n\n"


# --- service -----------------------------------------------------------------------------------------------------

@dataclass
class _Run:
    draft_id: str
    revision: int
    payload: Dict[str, Any]
    log: EventLog
    source: SourceDocument
    overlay_base: bytes
    directory: Path
    preview_venue_id: str
    venue_name: Optional[str]
    compile_provenance: Optional[str]
    thinking_level: str
    started: float = field(default_factory=time.monotonic)


def _default_compile(*args: Any, **kwargs: Any) -> CompileResult:
    from backend.app.venues.compiler import compile_draft  # compiler teammate's module; imported on use
    return compile_draft(*args, **kwargs)


def _default_overlay(image_bytes: bytes, draft: VenueDraftV1, result: CompileResult) -> bytes:
    from backend.app.ai.real2sim.overlay import render_overlay
    return render_overlay(image_bytes, draft, result)


def _default_topdown(venue: Any) -> bytes:
    from backend.app.ai.real2sim.overlay import render_topdown
    return render_topdown(venue)


def slug_venue_id(label: Optional[str], seed: str) -> str:
    """A readable venue id from the name or title plus a short hash: ``^[a-z0-9-]{3,40}$``, never building-v2."""
    base = re.sub(r"[^a-z0-9]+", "-", (label or "").lower()).strip("-")[:30].strip("-") or "venue"
    venue_id = f"{base}-{hashlib.sha256(seed.encode()).hexdigest()[:6]}"
    return venue_id if venue_id != BUILTIN_VENUE_ID else f"venue-{venue_id[-6:]}"


def _compile_json(result: CompileResult) -> Dict[str, Any]:
    return {"venue": result.venue.to_json() if result.venue is not None else None,
            "report": json.loads(json.dumps(dataclasses.asdict(result.report))), "error": result.error}


def _checks_json(assessment: Assessment) -> Dict[str, Any]:
    counts = assessment.counts()
    venue = assessment.result.venue
    return {"issues": [issue.to_json() for issue in assessment.issues], "errors": counts["errors"],
            "warnings": counts["warnings"], "compile_error": assessment.compile_error,
            "geometry_revision": venue.geometry_revision if venue is not None else None}


def _draft_counts(draft: VenueDraftV1) -> Dict[str, int]:
    return {"rooms": len(draft.rooms), "doors": len(draft.doors), "exits": len(draft.exits)}


class Real2SimService:
    def __init__(
        self,
        adapter: GroundingAdapter,
        *,
        runtime_dir: Optional[Path] = None,
        extractor: Optional[DraftExtractor] = None,
        compile_fn: Optional[CompileFn] = None,
        check_fn: Optional[CheckFn] = None,
        overlay_fn: Optional[OverlayFn] = None,
        topdown_fn: Optional[TopdownFn] = None,
        critique_rounds: Optional[int] = None,
        critique_deadline_seconds: float = DEFAULT_CRITIQUE_DEADLINE_SECONDS,
        ping_seconds: float = DEFAULT_PING_SECONDS,
        registry_fn: Callable[[], Any] = venue_registry,
        max_logs: int = MAX_LOGS,
    ):
        self.adapter = adapter
        self.extractor = extractor or DraftExtractor(adapter)
        self._runtime_dir = runtime_dir
        self._compile = compile_fn or _default_compile
        self._check = check_fn or check_venue
        self._overlay = overlay_fn or _default_overlay
        self._topdown = topdown_fn or _default_topdown
        self.critique_rounds = clamp_rounds(critique_rounds) if critique_rounds is not None else critique_rounds_from_env()
        self.critique_deadline_seconds = critique_deadline_seconds
        self.ping_seconds = ping_seconds
        self._registry_fn = registry_fn
        self._max_logs = max_logs
        self._live_slot = asyncio.Semaphore(1)
        self._logs: "OrderedDict[str, EventLog]" = OrderedDict()
        self._tasks: Dict[str, asyncio.Task] = {}
        # Drafts persisted but whose task is not registered yet: never mistaken for an interrupted pipeline.
        self._pending: set[str] = set()

    # -- lifecycle --------------------------------------------------------------------------------------------

    def live_busy(self) -> bool:
        return self._live_slot.locked()

    def is_live_configured(self) -> bool:
        return self.extractor.is_live_configured()

    async def aclose(self) -> None:
        """Cancel running pipelines (application shutdown). Their logs end with ``error: cancelled``; the next read
        of such a draft records it as failed (``pipeline_interrupted``)."""
        running = [task for task in self._tasks.values() if not task.done()]
        for task in running:
            task.cancel()
        if running:
            await asyncio.gather(*running, return_exceptions=True)

    async def wait_idle(self) -> None:
        """Tests: wait until every background pipeline has finished."""
        while any(not task.done() for task in self._tasks.values()):
            await asyncio.gather(*list(self._tasks.values()), return_exceptions=True)

    def _registry(self) -> Any:
        return self._registry_fn()

    def _remember_log(self, draft_id: str, log: EventLog) -> None:
        self._logs[draft_id] = log
        self._logs.move_to_end(draft_id)
        while len(self._logs) > self._max_logs:
            oldest = next((key for key, value in self._logs.items() if value.closed), None)
            if oldest is None:
                break
            del self._logs[oldest]

    # -- create -----------------------------------------------------------------------------------------------

    async def create_live(self, source: SourceDocument, *, name: Optional[str] = None,
                          thinking_level: Optional[str] = None, notes: Iterable[str] = ()) -> Dict[str, Any]:
        if not self.is_live_configured():
            raise Real2SimError("configuration_missing", 503)
        if thinking_level is not None and thinking_level not in THINKING_LEVELS:
            raise Real2SimError("invalid_thinking_level", 422)
        if self._live_slot.locked():
            raise Real2SimError("real2sim_busy", 429)
        await self._live_slot.acquire()  # not contended: checked just above on the same loop
        try:
            level = thinking_level or self.extractor.thinking_level
            run = await self._create(
                source, mode="live", name=name, notes=list(notes), provenance="live",
                label="Live Gemini 4 Argon reading (proposal; checked locally, accepted by an operator)",
                fixture=None, compile_provenance=None, thinking_level=level)
        except BaseException:
            self._live_slot.release()
            raise
        self._start(run, self._live_pipeline(run), release_slot=True)
        return {"draft_id": run.draft_id, "revision": run.revision, "status": "extracting"}

    async def create_fixture(self, saved: SavedRun, *, name: Optional[str] = None) -> Dict[str, Any]:
        meta = saved.meta
        image = self._fixture_image(saved)
        source = SourceDocument(saved.source_bytes, saved.source_mime, meta.source_kind, image, None)
        label = provenance_label(meta)
        if meta.provenance == "synthetic":
            text = ("Compiled by the local compiler from a synthetic saved run (an image drawn by our own generator, "
                    "not a Gemini reading); operator-accepted; declared rates; not a surveyed plan.")
        else:
            text = (f"Compiled by the local compiler from a saved Gemini 4 Argon reading recorded "
                    f"{meta.recorded_at or 'at an unknown time'} (not a live call); operator-accepted; declared "
                    f"rates; not a surveyed plan.")
        fixture = {"fixture_id": meta.fixture_id, "title": meta.title, "provenance": meta.provenance,
                   "recorded_at": meta.recorded_at, "interaction_id_hash": meta.interaction_id_hash, "note": meta.note}
        run = await self._create(source, mode="fixture", name=name or meta.title, notes=[], provenance=meta.provenance,
                                 label=label, fixture=fixture, compile_provenance=text,
                                 thinking_level=self.extractor.thinking_level)
        self._start(run, self._fixture_pipeline(run, saved), release_slot=False)
        return {"draft_id": run.draft_id, "revision": run.revision, "status": "extracting"}

    @staticmethod
    def _fixture_image(saved: SavedRun) -> SourceImage:
        try:
            with Image.open(io.BytesIO(saved.source_bytes)) as opened:
                width, height = opened.size
        except (UnidentifiedImageError, OSError, ValueError):
            raise Real2SimError("invalid_fixture", 422) from None
        return SourceImage(width, height, saved.source_sha256, saved.source_mime)

    async def _create(self, source: SourceDocument, *, mode: str, name: Optional[str], notes: List[str],
                      provenance: str, label: str, fixture: Optional[Dict[str, Any]],
                      compile_provenance: Optional[str], thinking_level: str) -> _Run:
        draft_id = f"r2s-{secrets.token_hex(12)}"
        directory = runtime_root(self._runtime_dir) / draft_id
        suffix = SOURCE_SUFFIX[source.mime_type]
        overlay_base = source.data
        if source.mime_type == "application/pdf":
            canvas = Image.new("RGB", (source.image.width_px, source.image.height_px), PAPER)
            buffer = io.BytesIO()
            canvas.save(buffer, format="PNG")
            overlay_base = buffer.getvalue()

        def store() -> None:
            directory.parent.mkdir(parents=True, exist_ok=True)
            directory.mkdir(exist_ok=False)   # an existing directory is a colliding id: never overwrite its files
            (directory / f"source.{suffix}").write_bytes(source.data)
            if overlay_base is not source.data:
                (directory / "canvas.png").write_bytes(overlay_base)

        try:
            await asyncio.to_thread(store)
        except FileExistsError:
            raise Real2SimError("draft_id_conflict", 409) from None
        except OSError:
            raise Real2SimError("runtime_storage_unavailable", 503) from None
        payload: Dict[str, Any] = {
            "schema": "real2sim-draft-1", "mode": mode, "name": name, "provenance": provenance,
            "provenance_label": label, "fixture": fixture,
            "source": {"kind": source.source_kind, "mime_type": source.mime_type, "sha256": source.image.sha256,
                       "bytes": len(source.data), "width_px": source.image.width_px,
                       "height_px": source.image.height_px, "page_size_basis": source.page_size_basis,
                       "notes": notes, "stored_as": f"source.{suffix}"},
            "draft": None, "extracted_draft": None, "unreadable": [], "dropped": [], "repaired": [],
            "extracted_salvage": None, "compile": None, "checks": None,
            "rounds": [], "critique_note": None, "thoughts": [], "receipts": [], "errors": [], "timings_ms": {},
            "settings": {"thinking_level": thinking_level, "critique_rounds": self.critique_rounds,
                         "stream": self.extractor.stream},
            "overlay_available": False, "topdown_available": False, "accepted": None,
        }
        self._pending.add(draft_id)
        try:
            revision = await asyncio.to_thread(self._registry().create_draft, draft_id, "extracting", payload)
        except (RegistryConflict, sqlite3.IntegrityError):
            self._pending.discard(draft_id)
            # A 96-bit random id colliding is practically impossible; if it happens it is a conflict, not a 500.
            raise Real2SimError("draft_id_conflict", 409) from None
        except BaseException:
            self._pending.discard(draft_id)
            raise
        log = EventLog()
        self._remember_log(draft_id, log)
        run = _Run(draft_id=draft_id, revision=revision, payload=payload, log=log, source=source,
                   overlay_base=overlay_base, directory=directory,
                   preview_venue_id=slug_venue_id(name, f"{draft_id}:{source.image.sha256}"),
                   venue_name=name, compile_provenance=compile_provenance, thinking_level=thinking_level)
        self._emit_status(run, "extracting", "read")
        return run

    def _start(self, run: _Run, pipeline: Any, *, release_slot: bool) -> None:
        async def guarded() -> None:
            try:
                await pipeline
            except asyncio.CancelledError:
                # No blocking registry write while the loop shuts down: the next read of this draft finds it
                # in progress without a task and records it as failed (pipeline_interrupted).
                if not run.log.closed:
                    run.log.append("error", {"draft_id": run.draft_id, "status": "failed", "revision": run.revision,
                                             "code": "cancelled", "provenance": run.payload["provenance"]},
                                   terminal=True)
                raise
            except Exception:
                await self._fail(run, "local_processing_failure")
            finally:
                if release_slot:
                    self._live_slot.release()

        task = asyncio.get_running_loop().create_task(guarded())
        self._tasks[run.draft_id] = task
        self._pending.discard(run.draft_id)
        task.add_done_callback(lambda _task, draft_id=run.draft_id: self._tasks.pop(draft_id, None))

    # -- pipeline helpers -------------------------------------------------------------------------------------

    def _emit_status(self, run: _Run, status: str, phase: str) -> None:
        run.log.append("status", {"draft_id": run.draft_id, "status": status, "phase": phase,
                                  "revision": run.revision, "provenance": run.payload["provenance"]})

    async def _persist(self, run: _Run, status: str, phase: str) -> None:
        run.revision = await asyncio.to_thread(self._registry().update_draft, run.draft_id, run.revision, status,
                                               run.payload)
        self._emit_status(run, status, phase)

    def _thought_sink(self, run: _Run, phase: str, recorded: bool = False) -> Callable[[str], None]:
        def sink(text: str) -> None:
            thoughts = run.payload["thoughts"]
            if len(thoughts) >= MAX_PAYLOAD_THOUGHTS:
                return
            thoughts.append({"phase": phase, "text": text, "recorded": recorded})
            run.log.append("thought", {"phase": phase, "index": len(thoughts) - 1, "text": text, "recorded": recorded})
        return sink

    def _receipt(self, run: _Run, phase: str, call: ExtractionResult) -> None:
        run.payload["receipts"].append({
            "phase": phase, "status": call.status, "provenance": call.provenance, "provider_model": call.provider_model,
            "interaction_id_hash": hash_identifier(call.provider_interaction_id), "token_usage": call.token_usage,
            "latency_ms": round(call.latency_ms, 1),
            "first_thought_ms": round(call.first_thought_ms, 1) if call.first_thought_ms is not None else None,
            "first_output_ms": round(call.first_output_ms, 1) if call.first_output_ms is not None else None,
            "sdk_version": call.sdk_version, "thinking_level": call.thinking_level, "streamed": call.streamed,
            "errors": list(call.errors),
        })

    def _assess(self, run: _Run, draft: VenueDraftV1) -> Assessment:
        """Preview compile (no controllable doors, no headcount) and graph checks. Never raises."""
        try:
            result = self._compile(draft, run.source.image, venue_id=run.preview_venue_id,
                                   name=run.venue_name, provenance=run.compile_provenance)
        except Exception:
            result = CompileResult(None, CompileReport(), "compiler_failure")
        if result.venue is None:
            return Assessment(result=result, issues=[])
        try:
            issues = list(self._check(result.venue))
        except Exception:
            issues = [GraphIssue("graph_check_failure", "error", "The local graph checks could not run.")]
        return Assessment(result=result, issues=issues)

    def _record_draft(self, run: _Run, draft: VenueDraftV1, phase: str, dropped: Iterable[str] = (),
                      repaired: Iterable[str] = ()) -> None:
        run.payload["draft"] = draft.model_dump(mode="json")
        run.payload["unreadable"] = list(draft.unreadable)
        run.payload["dropped"] = list(dropped)
        run.payload["repaired"] = list(repaired)
        run.log.append("draft", {"phase": phase, "draft": run.payload["draft"], "unreadable": list(draft.unreadable),
                                 "dropped": run.payload["dropped"], "repaired": run.payload["repaired"],
                                 "counts": _draft_counts(draft)})

    def _record_assessment(self, run: _Run, assessment: Assessment, phase: str) -> None:
        run.payload["compile"] = _compile_json(assessment.result)
        run.payload["checks"] = _checks_json(assessment)
        run.log.append("checks", {"phase": phase, **run.payload["checks"]})

    def _render_overlay(self, run: _Run, draft: VenueDraftV1, assessment: Assessment) -> Optional[bytes]:
        try:
            return self._overlay(run.overlay_base, draft, assessment.result)
        except Exception:
            return None

    async def _render_final(self, run: _Run, draft: VenueDraftV1, assessment: Assessment) -> None:
        started = time.monotonic()

        def render() -> tuple[Optional[bytes], Optional[bytes]]:
            overlay = self._render_overlay(run, draft, assessment)
            topdown = None
            if assessment.result.venue is not None:
                try:
                    topdown = self._topdown(assessment.result.venue)
                except Exception:
                    topdown = None
            for name, data in (("overlay.png", overlay), ("topdown.png", topdown)):
                path = run.directory / name
                try:
                    if data:
                        path.write_bytes(data)
                    elif path.exists():
                        path.unlink()
                except OSError:
                    pass
            return overlay, topdown

        overlay, topdown = await asyncio.to_thread(render)
        run.payload["overlay_available"] = bool(overlay) and (run.directory / "overlay.png").is_file()
        run.payload["topdown_available"] = bool(topdown) and (run.directory / "topdown.png").is_file()
        if not overlay:
            run.payload["errors"].append("overlay_unavailable")
        if assessment.result.venue is not None and not topdown:
            run.payload["errors"].append("topdown_unavailable")
        run.payload["timings_ms"]["render"] = round((time.monotonic() - started) * 1000, 1)

    async def _finish(self, run: _Run, assessment: Assessment) -> None:
        run.payload["timings_ms"]["total"] = round((time.monotonic() - run.started) * 1000, 1)
        await self._persist(run, "ready", "done")
        counts = assessment.counts()
        run.log.append("done", {"draft_id": run.draft_id, "status": "ready", "revision": run.revision,
                                "errors": counts["errors"], "warnings": counts["warnings"],
                                "provenance": run.payload["provenance"]}, terminal=True)

    async def _fail(self, run: _Run, code: str) -> None:
        if run.log.closed:
            return
        run.payload["errors"].append(code)
        run.payload["timings_ms"]["total"] = round((time.monotonic() - run.started) * 1000, 1)
        try:
            run.revision = await asyncio.to_thread(self._registry().update_draft, run.draft_id, run.revision,
                                                   "failed", run.payload)
        except Exception:
            pass  # the log still ends in error; a later read reconciles a draft left in progress
        run.log.append("error", {"draft_id": run.draft_id, "status": "failed", "revision": run.revision,
                                 "code": code, "provenance": run.payload["provenance"]}, terminal=True)

    async def _check_phase(self, run: _Run, draft: VenueDraftV1, phase: str) -> Assessment:
        started = time.monotonic()
        assessment = await asyncio.to_thread(self._assess, run, draft)
        run.payload["timings_ms"].setdefault("compile_checks", []).append(round((time.monotonic() - started) * 1000, 1))
        self._record_assessment(run, assessment, phase)
        return assessment

    # -- pipelines --------------------------------------------------------------------------------------------

    async def _live_pipeline(self, run: _Run) -> None:
        call = await self.extractor.extract(run.source, on_thought=self._thought_sink(run, "extract"),
                                            thinking_level=run.thinking_level)
        self._receipt(run, "extract", call)
        run.payload["timings_ms"]["extract"] = round(call.latency_ms, 1)
        if call.status != "completed" or call.draft is None:
            await self._fail(run, call.errors[0] if call.errors else "extraction_failed")
            return
        draft = call.draft
        self._record_draft(run, draft, "extract", call.dropped, call.repaired)
        await self._persist(run, "checking", "check")
        assessment = await self._check_phase(run, draft, "extract")

        previous_id = call.provider_interaction_id
        for round_number in range(1, self.critique_rounds + 1):
            if not assessment.has_errors() or previous_id is None:
                break
            await self._persist(run, "critiquing", f"critique-{round_number}")
            overlay = await asyncio.to_thread(self._render_overlay, run, draft, assessment)
            outcome = await run_critique_round(
                self.adapter, round_number=round_number, previous_interaction_id=previous_id,
                assessment=assessment, recompile=lambda corrected: asyncio.to_thread(self._assess, run, corrected),
                overlay_png=overlay, thinking_level=run.thinking_level, stream=self.extractor.stream,
                deadline_seconds=self.critique_deadline_seconds,
                on_thought=self._thought_sink(run, f"critique-{round_number}"))
            self._receipt(run, f"critique-{round_number}", outcome.call)
            run.payload["rounds"].append(outcome.record.model_dump(mode="json"))
            run.log.append("round", outcome.record.model_dump(mode="json"))
            if not outcome.record.accepted or outcome.draft is None or outcome.assessment is None:
                break
            if run.payload["extracted_draft"] is None:
                run.payload["extracted_draft"] = run.payload["draft"]
                run.payload["extracted_salvage"] = {"dropped": run.payload["dropped"],
                                                    "repaired": run.payload["repaired"]}
            draft, assessment = outcome.draft, outcome.assessment
            self._record_draft(run, draft, f"critique-{round_number}", outcome.record.dropped,
                               outcome.record.repaired)
            self._record_assessment(run, assessment, f"critique-{round_number}")
            previous_id = outcome.call.provider_interaction_id or previous_id
        if not assessment.has_errors():
            run.payload["critique_note"] = "no critique needed: the graph checks found no errors"
        elif self.critique_rounds == 0:
            run.payload["critique_note"] = "critique disabled (0 rounds)"
        await self._render_final(run, draft, assessment)
        await self._finish(run, assessment)

    async def _fixture_pipeline(self, run: _Run, saved: SavedRun) -> None:
        sink = self._thought_sink(run, "saved_run", recorded=True)
        for text in saved.meta.thoughts:
            if isinstance(text, str) and text.strip():
                sink(text.strip()[:1500])
        draft = saved.draft
        self._record_draft(run, draft, "saved_run")
        await self._persist(run, "checking", "check")
        assessment = await self._check_phase(run, draft, "saved_run")
        run.payload["critique_note"] = "critique skipped: a saved run makes no provider call"
        await self._render_final(run, draft, assessment)
        await self._finish(run, assessment)

    # -- read -------------------------------------------------------------------------------------------------

    def _record(self, draft_id: Any) -> Dict[str, Any]:
        if not valid_draft_id(draft_id):
            raise Real2SimError("unknown_draft", 404)
        record = self._registry().draft(draft_id)
        if record is None or record.get("schema") != "real2sim-draft-1":
            raise Real2SimError("unknown_draft", 404)
        if record["status"] in IN_PROGRESS and draft_id not in self._tasks and draft_id not in self._pending:
            # A pipeline that no longer runs (process restart) is a failure, never a silent forever-spinner.
            payload = {key: value for key, value in record.items()
                       if key not in ("draft_id", "revision", "status", "created_at", "updated_at")}
            payload["errors"] = [*payload.get("errors", []), "pipeline_interrupted"]
            try:
                self._registry().update_draft(draft_id, record["revision"], "failed", payload)
            except RegistryConflict:
                pass
            record = self._registry().draft(draft_id) or record
        return record

    def view(self, draft_id: Any) -> Dict[str, Any]:
        record = self._record(draft_id)
        draft = record.get("draft")
        element_ids = ((record.get("compile") or {}).get("report") or {}).get("element_ids") or {}
        rooms = {room["key"]: room["name"] for room in (draft or {}).get("rooms", [])}
        candidates = [{"key": door["key"], "between": door["between"],
                       "room_names": [rooms.get(key, key) for key in door["between"]], "symbol": door["symbol"],
                       "confidence": door["confidence"], "venue_door_id": element_ids.get(door["key"])}
                      for door in (draft or {}).get("doors", [])]
        log = self._logs.get(record["draft_id"])
        # What blocks Accept on the preview compile (Accept recompiles with the operator's choices and re-checks).
        checks = record.get("checks") or {}
        blockers: List[str] = []
        if record["status"] != "ready":
            blockers.append(f"status:{record['status']}")
        if checks.get("compile_error"):
            blockers.append(f"compile:{str(checks['compile_error']).split(':')[0]}")
        blockers += sorted({issue["code"] for issue in checks.get("issues", []) if issue.get("severity") == "error"})
        return {**record, "controllable_door_candidates": candidates,
                "max_controllable_doors": MAX_CONTROLLABLE_DOORS, "accept_blockers": blockers,
                "last_event_id": log.last_id if log is not None else None}

    def image(self, draft_id: Any, name: str) -> bytes:
        record = self._record(draft_id)
        if name not in ("overlay.png", "topdown.png") or not record.get(name.replace(".png", "_available")):
            raise Real2SimError(f"{name.split('.')[0]}_unavailable", 404)
        path = runtime_root(self._runtime_dir) / record["draft_id"] / name
        try:
            return path.read_bytes()
        except OSError:
            raise Real2SimError(f"{name.split('.')[0]}_unavailable", 404) from None

    def event_log(self, draft_id: Any) -> EventLog:
        """The live log, or one re-synthesized from the persisted status (after a restart or eviction)."""
        record = self._record(draft_id)
        log = self._logs.get(record["draft_id"])
        if log is not None:
            return log
        log = EventLog()
        log.append("status", {"draft_id": record["draft_id"], "status": record["status"], "phase": "replay",
                              "revision": record["revision"], "provenance": record.get("provenance")})
        checks = record.get("checks") or {}
        if record["status"] == "failed":
            errors = record.get("errors") or ["extraction_failed"]
            log.append("error", {"draft_id": record["draft_id"], "status": "failed", "revision": record["revision"],
                                 "code": errors[-1], "provenance": record.get("provenance")}, terminal=True)
        else:
            log.append("done", {"draft_id": record["draft_id"], "status": record["status"],
                                "revision": record["revision"], "errors": checks.get("errors", 0),
                                "warnings": checks.get("warnings", 0), "provenance": record.get("provenance")},
                       terminal=True)
        return log

    # -- accept -----------------------------------------------------------------------------------------------

    async def accept(self, draft_id: Any, *, expected_revision: int, controllable_doors: List[str],
                     headcount: Optional[int] = None, building_width_m: Optional[float] = None,
                     venue_id: Optional[str] = None, make_active: bool = True) -> Dict[str, Any]:
        record = await asyncio.to_thread(self._record, draft_id)
        if record["status"] != "ready" or not record.get("draft"):
            raise Real2SimError("draft_not_ready", 409, status=record["status"])
        if expected_revision != record["revision"]:
            raise Real2SimError("stale_draft_revision", 409, revision=record["revision"])
        draft = VenueDraftV1.model_validate(record["draft"])
        door_keys = {door.key for door in draft.doors}
        if len(set(controllable_doors)) != len(controllable_doors):
            raise Real2SimError("duplicate_controllable_door", 422)
        if len(controllable_doors) > MAX_CONTROLLABLE_DOORS:
            raise Real2SimError("too_many_controllable_doors", 422, max=MAX_CONTROLLABLE_DOORS)
        unknown = sorted(key for key in controllable_doors if key not in door_keys)
        if unknown:
            raise Real2SimError("unknown_controllable_door", 422, keys=unknown)
        source = record["source"]
        if venue_id is None:
            label = record.get("name") or draft.title or None
            venue_id = slug_venue_id(label, f"{record['draft_id']}:{source['sha256']}")
        if not isinstance(venue_id, str) or not _VENUE_ID.match(venue_id) or venue_id == BUILTIN_VENUE_ID:
            raise Real2SimError("invalid_venue_id", 422)
        image = SourceImage(source["width_px"], source["height_px"], source["sha256"], source["mime_type"])
        fixture = record.get("fixture")
        if record.get("mode") == "fixture" and fixture:
            provenance_text = (f"Compiled by the local compiler from a {fixture['provenance'].replace('_', ' ')} "
                               f"({fixture['fixture_id']}; {record.get('provenance_label')}); operator-accepted; "
                               f"declared rates; not a surveyed plan.")
        else:
            provenance_text = None
        name = record.get("name") or draft.title or None

        def compile_and_check() -> tuple[CompileResult, List[GraphIssue]]:
            result = self._compile(draft, image, venue_id=venue_id, controllable_doors=list(controllable_doors),
                                   headcount=headcount, building_width_m=building_width_m, name=name,
                                   provenance=provenance_text)
            return result, (list(self._check(result.venue)) if result.venue is not None else [])

        try:
            result, issues = await asyncio.to_thread(compile_and_check)
        except Exception:
            raise Real2SimError("compiler_failure", 422) from None
        if result.venue is None:
            raise Real2SimError("compile_failed", 422, error=result.error)
        if errors_in(issues):
            raise Real2SimError("graph_check_errors", 422, issues=[issue.to_json() for issue in issues])
        venue = result.venue
        payload = {key: value for key, value in record.items()
                   if key not in ("draft_id", "revision", "status", "created_at", "updated_at")}
        accepted = {"venue_id": venue_id, "geometry_revision": venue.geometry_revision, "accepted_at": _now(),
                    "controllable_doors": list(controllable_doors), "headcount": headcount,
                    "building_width_m": building_width_m, "make_active": make_active,
                    "report": json.loads(json.dumps(dataclasses.asdict(result.report))),
                    "issues": [issue.to_json() for issue in issues]}
        payload["accepted"] = accepted
        venue_record = {
            "name": name or venue_id, "source_kind": source["kind"], "draft_id": record["draft_id"],
            "source_sha256": source["sha256"], "scale_basis": result.report.scale_basis,
            "provenance": record.get("provenance"), "provenance_label": record.get("provenance_label"),
            "interaction_id_hashes": [r["interaction_id_hash"] for r in record.get("receipts", [])
                                      if r.get("interaction_id_hash")],
            "checks": {"issues": accepted["issues"], **summary(issues)},
            "critique_rounds": record.get("rounds", []), "draft": record["draft"],
            "defaults": result.report.defaults, "controllable_doors": list(controllable_doors),
            "headcount": headcount, "building_width_m": building_width_m,
        }
        try:
            stored = await asyncio.to_thread(self._registry().accept_draft, record["draft_id"], expected_revision,
                                             venue, venue_record, payload, make_active)
        except RegistryConflict as conflict:
            raise Real2SimError(conflict.code, 409) from None
        return {**stored, "geometry_revision": venue.geometry_revision, "provenance": record.get("provenance"),
                "warnings": [issue.to_json() for issue in issues], "defaults": result.report.defaults}
