"""Thin async helpers over the google-genai 2.x Interactions API.

All calls go through ``client.aio``. Nothing here touches the network at import
time; ``make_client`` raises a clear error when no key is configured.
"""
from __future__ import annotations

import asyncio
import mimetypes
import os
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

# Statuses that mean "keep polling". Everything else is terminal and returned
# to the caller (completed, requires_action, failed, cancelled, incomplete,
# budget_exceeded, ...).
_NON_TERMINAL = {"in_progress", "queued"}

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_SEARCH: list[Path] = [Path.cwd() / ".env", _REPO_ROOT / ".env"]


class UploadedFile(BaseModel):
    uri: str
    mime_type: str
    name: str


class Receipt(BaseModel):
    interaction_id: str
    provider_model: str | None
    status: str
    usage: dict
    elapsed_ms: int
    processing_calls: int


def _load_dotenv(paths: list[Path]) -> None:
    """Minimal .env reader: KEY=VALUE lines, optional quotes, never overrides env."""
    for path in paths:
        try:
            text = path.read_text()
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip().removeprefix("export ").strip()
            val = val.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = val


def make_client():
    """Return a ``genai.Client`` using ``GEMINI_API_KEY`` (env, else a ``.env`` file)."""
    if not os.environ.get("GEMINI_API_KEY"):
        _load_dotenv(_ENV_SEARCH)
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Export it or put GEMINI_API_KEY=... in .env "
            "(live Gemini calls are unavailable without it).")
    from google import genai
    return genai.Client(api_key=key)


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _steps(interaction: Any) -> list:
    return list(_get(interaction, "steps", None) or [])


def count_steps(interaction: Any, step_type: str) -> int:
    return sum(1 for s in _steps(interaction) if _get(s, "type") == step_type)


def joined_text(interaction: Any) -> str:
    """Concatenate every text block of every ``model_output`` step, in order."""
    parts: list[str] = []
    for step in _steps(interaction):
        if _get(step, "type") != "model_output":
            continue
        for block in _get(step, "content", None) or []:
            if _get(block, "type") == "text":
                parts.append(_get(block, "text", "") or "")
    return "".join(parts)


def _provider_model(interaction: Any) -> str | None:
    model = _get(interaction, "model")
    if model:
        return str(model)
    cfg = _get(interaction, "agent_config")
    cfg_model = _get(cfg, "model") if cfg is not None else None
    return str(cfg_model) if cfg_model else None


def _usage_dict(interaction: Any) -> dict:
    usage = _get(interaction, "usage")
    if usage is None:
        return {}
    if isinstance(usage, dict):
        return usage
    return usage.model_dump(exclude_none=True, mode="json")


def make_receipt(interaction: Any, started: float) -> Receipt:
    return Receipt(
        interaction_id=str(_get(interaction, "id", "") or ""),
        provider_model=_provider_model(interaction),
        status=str(_get(interaction, "status", "")),
        usage=_usage_dict(interaction),
        elapsed_ms=int((time.monotonic() - started) * 1000),
        processing_calls=count_steps(interaction, "processing_call"),
    )


async def run_background(client, *, deadline_s: float, poll_s: float = 3.0,
                         **create_kwargs: Any):
    """Create a background, stored interaction and poll it until it is terminal.

    Returns ``(interaction, receipt)``. ``requires_action``, ``failed``,
    ``cancelled``, ``incomplete`` (any non-running status) are returned for the
    caller to handle. On deadline the interaction is cancelled and
    ``TimeoutError`` is raised.
    """
    started = time.monotonic()
    create_kwargs = {**create_kwargs, "background": True, "store": True}
    interactions = client.aio.interactions
    interaction = await interactions.create(**create_kwargs)
    iid = _get(interaction, "id")
    while str(_get(interaction, "status")) in _NON_TERMINAL:
        remaining = deadline_s - (time.monotonic() - started)
        if remaining <= 0:
            try:
                await interactions.cancel(iid)
            finally:
                raise TimeoutError(
                    f"interaction {iid} not terminal after {deadline_s}s; cancelled")
        await asyncio.sleep(min(poll_s, remaining))
        interaction = await interactions.get(iid)
    return interaction, make_receipt(interaction, started)


async def upload_video(client, path: Path, *, poll_s: float = 2.0,
                       deadline_s: float = 300.0) -> UploadedFile:
    """Upload through the Files API and wait until the file is ACTIVE."""
    path = Path(path)
    mime = mimetypes.guess_type(path.name)[0] or "video/mp4"
    files = client.aio.files
    f = await files.upload(file=str(path), config={"mime_type": mime})
    started = time.monotonic()

    def state_of(file: Any) -> str:
        st = _get(file, "state")
        return str(getattr(st, "name", st) or "").upper().removeprefix("FILESTATE.")

    while state_of(f) not in ("ACTIVE",):
        if state_of(f) == "FAILED":
            raise RuntimeError(f"file {f.name} failed processing: {_get(f, 'error')}")
        if time.monotonic() - started > deadline_s:
            raise TimeoutError(f"file {f.name} not ACTIVE after {deadline_s}s")
        await asyncio.sleep(poll_s)
        f = await files.get(name=f.name)
    return UploadedFile(uri=f.uri, mime_type=f.mime_type or mime, name=f.name)
