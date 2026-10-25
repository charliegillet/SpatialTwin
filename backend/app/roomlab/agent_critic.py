"""Optional direct Argon scene critic for RoomLab.

Reviews a canonical RoomSceneV1 and deterministic solver/validation receipts to suggest
which uncalibrated or occluded gap to measure next. Has zero scene-mutation or hardware
authority and never overrides deterministic solver verdicts.
"""
from __future__ import annotations

import time
from typing import Any

from google import genai
from pydantic import BaseModel, ConfigDict, Field

from backend.app.roomlab.contracts import RoomSceneV1, SolveResult
from backend.app.roomlab.provider_prompts import (
    CRITIC_SYSTEM_INSTRUCTION,
    build_critic_prompt,
)
from backend.app.roomlab.video_extractor import (
    MODEL_ID,
    _close_sdk_client,
    _extract_output_text,
    _resolve_api_key,
    _sanitize_provider_error,
)


class CriticNotes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    recommendations: list[str] = Field(default_factory=list)
    model: str = MODEL_ID
    provenance: str = "live"
    latency_ms: float = 0.0


async def critique_scene(
    scene: RoomSceneV1,
    solve: SolveResult | None = None,
    api_key: str | None = None,
    *,
    client: Any | None = None,
) -> CriticNotes:
    """Request concise, grounded measurement/layout recommendations from gemini-4-argon."""
    started = time.monotonic()
    resolved_key = _resolve_api_key(api_key)
    prompt = build_critic_prompt(scene, solve)

    owns_client = client is None
    active_client = client or genai.Client(api_key=resolved_key)
    try:
        interaction = await active_client.aio.interactions.create(
            model=MODEL_ID,
            system_instruction=CRITIC_SYSTEM_INSTRUCTION,
            input=[{"type": "text", "text": prompt}],
            generation_config={"thinking_level": "low", "max_output_tokens": 1024},
            store=True,
            stream=False,
        )
    except Exception as exc:
        raise RuntimeError(_sanitize_provider_error(exc)) from exc
    finally:
        if owns_client:
            await _close_sdk_client(active_client)

    status = getattr(interaction, "status", "completed")
    if status != "completed":
        raise RuntimeError(f"Gemini critic did not complete (status={status}).")

    text = _extract_output_text(interaction)
    lines = [
        line.lstrip("-*•0123456789. ").strip()
        for line in text.splitlines()
        if line.strip()
    ]
    summary = lines[0] if lines else text[:300]
    recs = lines[1:6] if len(lines) > 1 else [summary]
    latency_ms = round((time.monotonic() - started) * 1000.0, 2)
    return CriticNotes(
        summary=summary[:500],
        recommendations=[r[:300] for r in recs],
        model=getattr(interaction, "model", None) or MODEL_ID,
        provenance="live",
        latency_ms=max(0.01, latency_ms),
    )
