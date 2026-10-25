"""Multimodal advisory Argon scene critic for RoomLab.

Accepts a canonical `CritiqueContext` (with `RoomSceneV1`, `ValidationReport`, optional
`SolveResult`, rendered `bev_png`, and bounded `CritiqueFrame` records) and returns a
validated `CritiqueResult` with `SceneReceipt` hashes. Also preserves backwards-compatible
`CriticNotes` support if `critique_scene` is called with a bare `RoomSceneV1`.
"""
from __future__ import annotations

import base64
import json
import time
from typing import Any

from google import genai
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.app.roomlab.contracts import (
    CritiqueContext,
    CritiqueFinding,
    CritiqueResult,
    RoomSceneV1,
    SolveResult,
)
from backend.app.roomlab.critic_prompts import (
    CRITIC_SYSTEM_INSTRUCTION,
    build_multimodal_critic_prompt,
    critic_response_json_schema,
)
from backend.app.roomlab.provider_prompts import build_critic_prompt
from backend.app.roomlab.video_extractor import (
    MODEL_ID,
    _close_sdk_client,
    _extract_output_text,
    _resolve_api_key,
    _sanitize_provider_error,
)

CRITIC_SDK_TIMEOUT_MS = 150_000
MAX_CRITIC_OUTPUT_CHARS = 32_768


class CriticNotes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    recommendations: list[str] = Field(default_factory=list)
    model: str = MODEL_ID
    provenance: str = "live"
    latency_ms: float = 0.0


class _ProviderFindingDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: str = "observation"
    element_ids: list[str] = Field(default_factory=list)
    frame_ids: list[str] = Field(default_factory=list)
    message: str = ""
    measurement_request: str | None = None


class _ProviderCritiquePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str = ""
    findings: list[_ProviderFindingDraft] = Field(default_factory=list)


def _validate_and_filter_findings(
    raw_findings: list[_ProviderFindingDraft],
    valid_element_ids: set[str],
    valid_frame_ids: set[str],
) -> list[CritiqueFinding]:
    cleaned: list[CritiqueFinding] = []
    for item in raw_findings[:12]:
        msg = (item.message or "").strip()[:1000]
        if not msg:
            continue
        if item.kind not in ("observation", "needs_evidence"):
            raise RuntimeError(f"Critic returned unsupported finding kind '{item.kind}'.")
        kind = item.kind

        el_ids: list[str] = []
        for eid in item.element_ids:
            if eid not in valid_element_ids:
                raise RuntimeError("Critic returned an unknown scene element citation.")
            if eid not in el_ids:
                el_ids.append(eid)
            if len(el_ids) >= 20:
                break

        fr_ids: list[str] = []
        for fid in item.frame_ids:
            if fid not in valid_frame_ids:
                raise RuntimeError("Critic returned an unknown evidence frame citation.")
            if fid not in fr_ids:
                fr_ids.append(fid)
            if len(fr_ids) >= 6:
                break

        # Enforce that every finding cites at least 1 supplied frame
        if not fr_ids:
            raise RuntimeError("Every critic finding must cite at least one supplied source frame.")

        meas = (item.measurement_request or "").strip()[:500] or None
        cleaned.append(
            CritiqueFinding(
                kind=kind,
                element_ids=el_ids,
                frame_ids=fr_ids,
                message=msg,
                measurement_request=meas,
            )
        )
    return cleaned


async def critique_scene(
    context_or_scene: CritiqueContext | RoomSceneV1,
    solve: SolveResult | None = None,
    api_key: str | None = None,
    *,
    client: Any | None = None,
) -> CritiqueResult | CriticNotes:
    """Run multimodal advisory critique on a `CritiqueContext` (or legacy `RoomSceneV1`)."""
    if isinstance(context_or_scene, RoomSceneV1):
        started = time.monotonic()
        resolved_key = _resolve_api_key(api_key)
        prompt = build_critic_prompt(context_or_scene, solve)
        owns_client = client is None
        active_client = client or genai.Client(
            api_key=resolved_key,
            http_options={"timeout": CRITIC_SDK_TIMEOUT_MS},
        )
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

    context = context_or_scene
    started = time.monotonic()
    resolved_key = _resolve_api_key(api_key)

    if not context.frames:
        raise RuntimeError("CritiqueContext must include at least one keyframe.")
    if not context.bev_png:
        raise RuntimeError("CritiqueContext is missing rendered BEV PNG bytes.")

    inputs: list[dict[str, Any]] = [
        {"type": "text", "text": build_multimodal_critic_prompt(context)},
        {"type": "text", "text": "Rendered 2D Bird's-Eye View (BEV) Plan of current RoomSceneV1:"},
        {
            "type": "image",
            "data": base64.b64encode(context.bev_png).decode("ascii"),
            "mime_type": "image/png",
        },
    ]

    reviewed_frame_ids: list[str] = []
    for cf in context.frames[:6]:
        if not cf.jpeg_bytes:
            raise RuntimeError(f"Keyframe '{cf.record.frame_id}' has empty JPEG bytes.")
        reviewed_frame_ids.append(cf.record.frame_id)
        inputs.append(
            {
                "type": "text",
                "text": f"Source Keyframe ID: {cf.record.frame_id} | Timestamp: {cf.record.timestamp_s:.2f}s",
            }
        )
        inputs.append(
            {
                "type": "image",
                "data": base64.b64encode(cf.jpeg_bytes).decode("ascii"),
                "mime_type": "image/jpeg",
            }
        )

    owns_client = client is None
    active_client = client or genai.Client(
        api_key=resolved_key,
        http_options={"timeout": CRITIC_SDK_TIMEOUT_MS},
    )
    try:
        interaction = await active_client.aio.interactions.create(
            model=MODEL_ID,
            system_instruction=CRITIC_SYSTEM_INSTRUCTION,
            input=inputs,
            generation_config={"thinking_level": "low", "max_output_tokens": 4096},
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": critic_response_json_schema(),
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
        raise RuntimeError("Gemini scene critique was cancelled.")
    if status != "completed":
        raise RuntimeError(f"Gemini scene critique did not complete (status={status}).")
    if getattr(interaction, "errors", None):
        raise RuntimeError("Gemini provider reported interaction errors during scene critique.")

    provider_model = getattr(interaction, "model", None) or MODEL_ID
    if provider_model != MODEL_ID:
        raise RuntimeError(f"Unexpected provider model '{provider_model}' (expected '{MODEL_ID}').")

    raw_text = _extract_output_text(interaction)
    if len(raw_text) > MAX_CRITIC_OUTPUT_CHARS:
        raise RuntimeError("Gemini critic response exceeded maximum allowed character length.")

    try:
        parsed_json = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Gemini critic returned malformed JSON.") from exc

    if not isinstance(parsed_json, dict):
        raise RuntimeError("Gemini critic output must be a JSON object.")

    try:
        payload = _ProviderCritiquePayload.model_validate(parsed_json)
    except ValidationError as exc:
        raise RuntimeError("Gemini critic output failed local schema validation.") from exc

    summary = (payload.summary or "").strip()[:1000]
    if not summary:
        raise RuntimeError("Gemini critic returned an empty summary.")

    scene = context.scene
    valid_element_ids = (
        {w.id for w in scene.walls}
        | {v.id for v in scene.floor_voids}
        | {o.id for o in scene.openings}
        | {obj.id for obj in scene.objects}
    )
    valid_frame_ids = set(reviewed_frame_ids)
    findings = _validate_and_filter_findings(payload.findings, valid_element_ids, valid_frame_ids)

    latency_ms = round((time.monotonic() - started) * 1000.0, 2)
    return CritiqueResult(
        scene_id=scene.scene_id,
        scene_revision=scene.scene_revision,
        geometry_hash=context.geometry_hash,
        evidence_hash=context.evidence_hash,
        render_hash=context.render_hash,
        summary=summary,
        findings=findings,
        reviewed_frame_ids=reviewed_frame_ids,
        model=MODEL_ID,
        provenance="live",
        latency_ms=max(0.01, min(180000.0, latency_ms)),
    )
