"""When did Gemini last complete a live call on this machine? Feeds the stage preflight.

Two sources; the newest wins:
- live completions recorded by the adapters (``record_live_receipt``), kept in runtime/receipts/last_live.json;
- passing probe receipts in runtime/probes/*.json (their ``timestamp_utc``).

Only the call kind, model and time are kept: never prompts, images, provider ids or keys.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
RECEIPTS_DIR_ENV = "SPATIALTWIN_RECEIPTS_DIR"
_write_lock = threading.Lock()


def receipts_dir() -> Path:
    return Path(os.environ.get(RECEIPTS_DIR_ENV) or REPO_ROOT / "runtime" / "receipts")


def record_live_receipt(kind: str, model: Optional[str], now: Optional[datetime] = None) -> None:
    """Called after a provider call completed live and its model was verified."""
    record = {"kind": kind, "model": model, "at": (now or datetime.now(timezone.utc)).isoformat()}
    path = receipts_dir() / "last_live.json"
    with _write_lock:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            staging = path.with_suffix(".tmp")
            staging.write_text(json.dumps(record))
            staging.replace(path)
        except OSError:
            # A read-only runtime must never turn a completed live call into a failure.
            pass


def _timestamp(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _read_json(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def last_live_receipt(probe_dir: Path, now: Optional[datetime] = None) -> Optional[dict]:
    """The newest live receipt as {kind, model, at, age_seconds}, or None when there is none."""
    found: list[tuple[datetime, str, Optional[str]]] = []
    recorded = _read_json(receipts_dir() / "last_live.json")
    if recorded and (at := _timestamp(recorded.get("at"))):
        found.append((at, str(recorded.get("kind") or "live_call"), recorded.get("model")))
    try:
        probe_files = sorted(Path(probe_dir).glob("*.json"))
    except OSError:
        probe_files = []
    for path in probe_files:
        data = _read_json(path)
        # Probe receipts write both "pass" and "passed"; only an explicit True counts.
        if data and data.get("pass") is True and (at := _timestamp(data.get("timestamp_utc"))):
            found.append((at, f"probe:{data.get('probe_id') or path.stem}", data.get("requested_model")))
    if not found:
        return None
    at, kind, model = max(found, key=lambda item: item[0])
    age = ((now or datetime.now(timezone.utc)) - at).total_seconds()
    return {"kind": kind, "model": model if isinstance(model, str) else None,
            "at": at.isoformat(), "age_seconds": max(0.0, age)}
