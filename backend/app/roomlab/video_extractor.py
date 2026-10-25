"""Direct Gemini 4 Argon room layout extractor for RoomLab.

Reads decoded frame files from media_root / frame.relative_path (path-safe, no external URLs),
calls gemini-4-argon with a structured JSON schema, and normalizes the provider output into
a RoomDraftResult with real latency_ms and provenance='live'. Never substitutes a synthetic
fallback room when the provider or API key is unavailable.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import pathlib
import time
from typing import Any

import httpx
from google import genai
from google.genai import errors as genai_errors
from pydantic import ValidationError

from backend.app.roomlab.contracts import MediaRecord, RoomDraftResult
from backend.app.roomlab.provider_prompts import (
    EXTRACTION_SYSTEM_INSTRUCTION,
    build_extraction_prompt,
)
from backend.app.roomlab.provider_schema import (
    ProviderRoomPayload,
    normalize_provider_payload,
    provider_response_json_schema,
)

MODEL_ID = "gemini-4-argon"
MAX_OUTPUT_CHARS = 65_536
MAX_INLINE_VIDEO_BYTES = 20 * 1024 * 1024
SDK_TIMEOUT_MS = 450_000  # 450s, fitting inside the 480s root job timeout


def _resolve_api_key(explicit_key: str | None = None) -> str:
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.environ.get(var, "").strip()
        if val:
            return val
    raise RuntimeError(
        "Gemini API key is not configured. Set GEMINI_API_KEY on the server to extract a room from video."
    )


def _sanitize_provider_error(exc: Exception) -> str:
    """Map provider/network exceptions to bounded user-safe messages without echoing raw payloads or keys."""
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, httpx.TimeoutException)):
        return "Gemini provider request timed out (code=timeout)."
    if isinstance(exc, httpx.TransportError):
        return "Network transport error while contacting Gemini provider (code=network_error)."
    status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(status_code, int) and 100 <= status_code <= 599:
        if status_code in (401, 403):
            return f"Gemini provider rejected credentials or model entitlement (HTTP {status_code})."
        if status_code == 429:
            return "Gemini provider rate limit exceeded (HTTP 429). Please retry shortly."
        if status_code == 400:
            return "Gemini provider rejected the extraction request parameters (HTTP 400)."
        return f"Gemini provider returned HTTP {status_code}."
    if isinstance(exc, genai_errors.APIError):
        return "Gemini API error during room extraction."
    return f"Gemini provider call failed ({type(exc).__name__})."


async def _close_sdk_client(client_obj: Any) -> None:
    """Close both async and sync resources on google-genai Client safely."""
    aio_obj = getattr(client_obj, "aio", None)
    if aio_obj is not None:
        aio_aclose = getattr(aio_obj, "aclose", None)
        if callable(aio_aclose):
            try:
                res = aio_aclose()
                if asyncio.iscoroutine(res):
                    await res
            except Exception:
                pass
    sync_close = getattr(client_obj, "close", None)
    if callable(sync_close):
        try:
            sync_close()
        except Exception:
            pass


def _safe_media_child(media_root: pathlib.Path, rel_path: str) -> pathlib.Path:
    root = pathlib.Path(media_root).resolve()
    clean_rel = (rel_path or "").lstrip("/\\")
    if not clean_rel or ".." in pathlib.PurePath(clean_rel).parts:
        raise ValueError(f"Unsafe relative media path: {rel_path!r}")
    candidate = (root / clean_rel).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Media path escapes media_root: {rel_path!r}") from exc
    if not candidate.is_file():
        raise ValueError(f"Media frame file does not exist: {clean_rel}")
    return candidate


def _extract_output_text(interaction: Any) -> str:
    text = getattr(interaction, "output_text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()
    steps = getattr(interaction, "steps", None) or []
    parts: list[str] = []
    for step in steps:
        if getattr(step, "type", None) == "model_output":
            for content in getattr(step, "content", None) or []:
                if getattr(content, "type", None) == "text":
                    chunk = getattr(content, "text", None)
                    if isinstance(chunk, str) and chunk:
                        parts.append(chunk)
    joined = "".join(parts).strip()
    if joined:
        return joined
    raise RuntimeError("Gemini provider returned an empty response body.")


async def propose_room(
    media: MediaRecord,
    media_root: pathlib.Path,
    api_key: str | None = None,
    *,
    client: Any | None = None,
    include_video_stream: bool = True,
) -> RoomDraftResult:
    """Extract an estimated RoomDraft from a processed MediaRecord using direct gemini-4-argon."""
    started = time.monotonic()
    resolved_key = _resolve_api_key(api_key)

    if not media.frames:
        raise RuntimeError("MediaRecord contains no extracted frames for room analysis.")

    root = pathlib.Path(media_root).resolve()
    inputs: list[dict[str, Any]] = [
        {"type": "text", "text": build_extraction_prompt(media)},
    ]

    if include_video_stream and media.video_url:
        rel_video = media.video_url.removeprefix("/media/").lstrip("/")
        try:
            video_file = _safe_media_child(root, rel_video)
            video_size = video_file.stat().st_size
            if 0 < video_size <= MAX_INLINE_VIDEO_BYTES:
                video_bytes = video_file.read_bytes()
                static_fps = 1.0 if media.duration_s <= 30.0 else 0.5
                inputs.append(
                    {
                        "type": "video",
                        "data": base64.b64encode(video_bytes).decode("ascii"),
                        "mime_type": media.mime_type,
                        "processing": {"type": "static", "fps": static_fps},
                    }
                )
        except (ValueError, OSError):
            pass

    for frame in media.frames[:48]:
        frame_path = _safe_media_child(root, frame.relative_path)
        frame_bytes = frame_path.read_bytes()
        if not frame_bytes:
            raise RuntimeError(f"Decoded frame '{frame.frame_id}' is empty.")
        inputs.append(
            {
                "type": "text",
                "text": f"Frame ID: {frame.frame_id} | Timestamp: {frame.timestamp_s:.2f}s",
            }
        )
        inputs.append(
            {
                "type": "image",
                "data": base64.b64encode(frame_bytes).decode("ascii"),
                "mime_type": "image/jpeg",
            }
        )

    owns_client = client is None
    active_client = client or genai.Client(
        api_key=resolved_key,
        http_options={"timeout": SDK_TIMEOUT_MS},
    )
    try:
        interaction = await active_client.aio.interactions.create(
            model=MODEL_ID,
            system_instruction=EXTRACTION_SYSTEM_INSTRUCTION,
            input=inputs,
            generation_config={"thinking_level": "low", "max_output_tokens": 8192},
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": provider_response_json_schema(),
            },
            store=True,
            stream=False,
        )
    except Exception as exc:
        raise RuntimeError(_sanitize_provider_error(exc)) from exc
    finally:
        if owns_client:
            await _close_sdk_client(active_client)

    status = getattr(interaction, "status", "completed")
    if status == "cancelled":
        raise RuntimeError("Gemini room extraction was cancelled.")
    if status != "completed":
        raise RuntimeError(f"Gemini room extraction did not complete (status={status}).")
    if getattr(interaction, "errors", None):
        raise RuntimeError("Gemini provider reported interaction errors during room extraction.")

    provider_model = getattr(interaction, "model", None) or MODEL_ID
    if provider_model != MODEL_ID:
        raise RuntimeError(f"Unexpected provider model '{provider_model}' (expected '{MODEL_ID}').")

    raw_text = _extract_output_text(interaction)
    if len(raw_text) > MAX_OUTPUT_CHARS:
        raise RuntimeError("Gemini response exceeded maximum allowed character length.")

    try:
        parsed_json = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Gemini returned malformed JSON for room extraction.") from exc

    if not isinstance(parsed_json, dict):
        raise RuntimeError("Gemini room extraction output must be a JSON object.")

    try:
        payload = ProviderRoomPayload.model_validate(parsed_json)
        valid_ids = {f.frame_id for f in media.frames}
        draft, warnings = normalize_provider_payload(payload, valid_ids)
    except (ValidationError, ValueError) as exc:
        raise RuntimeError("Gemini room draft failed local schema or geometric validation.") from exc

    if not any(item.get('type')=='video' for item in inputs):
        warnings.append(f'Analyzed {min(48,len(media.frames))} timestamped frames across {media.duration_s:.2f}s; native video omitted (disabled, unavailable, or over the 20 MiB inline limit). Brief events between sampled frames may be missed.')
    latency_ms = round((time.monotonic() - started) * 1000.0, 2)
    return RoomDraftResult(
        draft=draft,
        model=provider_model,
        provenance="live",
        latency_ms=max(0.01, latency_ms),
        warnings=warnings,
    )
