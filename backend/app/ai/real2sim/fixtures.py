"""Saved Real2Sim runs ("fixture mode"): a source image plus the draft a reading returned, loaded from disk.

Layout (Contract 2): ``venue/real2sim/<fixture_id>/{source.png | source.jpg, draft.json, meta.json}``. A saved run is
either ``synthetic`` (an image our own generator drew, with the draft a perfect reading would return) or
``saved_run`` (a recorded live Argon reading, with its time and an interaction-id hash). The label always travels
with the draft and is shown on screen; a saved run never stands in for a live reading silently, and fixture mode is
only reachable when the caller's ``fixtures_enabled()`` allows it (the routes enforce that).

Nothing outside the fixtures directory is read: ids are a strict slug, every resolved path must stay inside the
directory, and symlinks that leave it are refused.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.app.ai.real2sim.schema import VenueDraftV1

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURES_DIR_ENV = "SPATIALTWIN_REAL2SIM_FIXTURES_DIR"
FIXTURE_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{1,47}$"
_FIXTURE_ID = re.compile(FIXTURE_ID_PATTERN)
SOURCE_FILES = (("source.png", "image/png"), ("source.jpg", "image/jpeg"), ("source.jpeg", "image/jpeg"))
MAX_FIXTURE_SOURCE_BYTES = 8 * 1024 * 1024
MAX_FIXTURE_JSON_BYTES = 256 * 1024
MAX_RECORDED_THOUGHTS = 40


class FixtureError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class SavedRunMeta(BaseModel):
    # Unknown keys are tolerated so the generator can add notes without breaking the list; known keys are strict.
    model_config = ConfigDict(extra="ignore")
    fixture_id: str = Field(pattern=FIXTURE_ID_PATTERN)
    title: str = Field(min_length=1, max_length=120)
    source_kind: Literal["photo", "sketch", "pdf"]
    provenance: Literal["saved_run", "synthetic"]
    recorded_at: Optional[str] = None
    interaction_id_hash: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{8,64}$")
    note: str = Field(default="", max_length=600)
    # Optional: thought summaries recorded with a saved live run, replayed and labelled as recorded.
    thoughts: List[str] = Field(default_factory=list, max_length=MAX_RECORDED_THOUGHTS)


@dataclass(frozen=True)
class SavedRun:
    meta: SavedRunMeta
    draft: VenueDraftV1
    source_bytes: bytes
    source_mime: str
    source_sha256: str


def fixtures_dir() -> Path:
    return Path(os.environ.get(FIXTURES_DIR_ENV) or REPO_ROOT / "venue" / "real2sim")


def provenance_label(meta: SavedRunMeta) -> str:
    """The words shown next to every saved-run draft. Never claims a live reading."""
    if meta.provenance == "synthetic":
        return "Synthetic saved run: an image drawn by our own generator, not a photograph and not a Gemini reading"
    when = meta.recorded_at or "unknown time"
    receipt = f", interaction #{meta.interaction_id_hash[:12]}" if meta.interaction_id_hash else ""
    return f"Saved run: a recorded Gemini 4 Argon reading from {when}{receipt}; not a live call"


def _inside(base: Path, path: Path) -> bool:
    try:
        return path.resolve().is_relative_to(base.resolve())
    except (OSError, RuntimeError):
        return False


def _read_bounded(path: Path, limit: int) -> bytes:
    try:
        if path.stat().st_size > limit:
            raise FixtureError("invalid_fixture")
        return path.read_bytes()
    except OSError:
        raise FixtureError("invalid_fixture") from None


def _run_dir(fixture_id: Any, base: Optional[Path]) -> Path:
    if not isinstance(fixture_id, str) or not _FIXTURE_ID.match(fixture_id):
        raise FixtureError("invalid_fixture_id")
    root = Path(base) if base is not None else fixtures_dir()
    path = root / fixture_id
    if not _inside(root, path):
        raise FixtureError("invalid_fixture_id")
    if not path.is_dir():
        raise FixtureError("unknown_fixture")
    return path


def load_saved_run(fixture_id: Any, base: Optional[Path] = None) -> SavedRun:
    """Load and validate one saved run. Codes: invalid_fixture_id, unknown_fixture, invalid_fixture."""
    path = _run_dir(fixture_id, base)
    root = Path(base) if base is not None else fixtures_dir()
    files = {name: path / name for name in ("meta.json", "draft.json")}
    if any(not file.is_file() or not _inside(root, file) for file in files.values()):
        raise FixtureError("invalid_fixture")
    sources = [(path / name, mime) for name, mime in SOURCE_FILES if (path / name).is_file()]
    if len(sources) != 1 or not _inside(root, sources[0][0]):
        raise FixtureError("invalid_fixture")
    try:
        meta = SavedRunMeta.model_validate(json.loads(_read_bounded(files["meta.json"], MAX_FIXTURE_JSON_BYTES)))
        draft = VenueDraftV1.model_validate(json.loads(_read_bounded(files["draft.json"], MAX_FIXTURE_JSON_BYTES)))
    except (ValueError, ValidationError):
        raise FixtureError("invalid_fixture") from None
    if meta.fixture_id != fixture_id:
        raise FixtureError("invalid_fixture")
    source_path, mime = sources[0]
    data = _read_bounded(source_path, MAX_FIXTURE_SOURCE_BYTES)
    magic = b"\x89PNG\r\n\x1a\n" if mime == "image/png" else b"\xff\xd8\xff"
    if not data.startswith(magic):
        raise FixtureError("invalid_fixture")
    return SavedRun(meta=meta, draft=draft, source_bytes=data, source_mime=mime,
                    source_sha256=hashlib.sha256(data).hexdigest())


def saved_run_summary(run: SavedRun) -> Dict[str, Any]:
    meta = run.meta
    return {
        "fixture_id": meta.fixture_id, "title": meta.title, "source_kind": meta.source_kind,
        "provenance": meta.provenance, "provenance_label": provenance_label(meta),
        "recorded_at": meta.recorded_at, "interaction_id_hash": meta.interaction_id_hash, "note": meta.note,
        "source_mime": run.source_mime, "source_sha256": run.source_sha256,
        "counts": {"rooms": len(run.draft.rooms), "doors": len(run.draft.doors), "exits": len(run.draft.exits)},
        "draft_title": run.draft.title, "image_kind": run.draft.image_kind,
    }


def list_saved_runs(base: Optional[Path] = None) -> Dict[str, Any]:
    """Every valid saved run, sorted by id, plus the ids of directories that failed validation."""
    root = Path(base) if base is not None else fixtures_dir()
    saved: List[Dict[str, Any]] = []
    invalid: List[str] = []
    try:
        candidates = sorted(entry.name for entry in root.iterdir() if entry.is_dir())
    except OSError:
        candidates = []
    for name in candidates:
        if not _FIXTURE_ID.match(name):
            continue
        try:
            saved.append(saved_run_summary(load_saved_run(name, root)))
        except FixtureError:
            invalid.append(name)
    return {"saved": saved, "invalid": invalid}
