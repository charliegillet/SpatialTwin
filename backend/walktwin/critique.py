"""Chained Argon critique: twin renders vs. real video frames -> graph patch ops.

Each call chains onto the previous interaction (``previous_interaction_id``):
round 1 onto the extraction, later rounds onto the previous critique. The
walkthrough video therefore stays in server-side context and is not re-sent;
only optional, static, clipped zoom parts of the same file are added (behind
``zoom_enabled``, off until the Task 2 probe confirms clipped video parts).

Provider failures stay failures: ``critique`` never raises for provider or
parse errors and never fabricates ops.
"""
from __future__ import annotations

import base64
import json
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from .contracts import Door, Measure, VenueGraph, Zone
from .extract import gemini_schema
from .genai_client import Receipt, joined_text, run_background
from .patch import OP_NAMES, PatchOp

MODEL = "gemini-4-argon"
POLL_S = 3.0
MAX_PAIRS = 8
ZOOM_FPS = 5
PROMPT_PATH = Path(__file__).parent / "prompts" / "critique.md"
GENERATION_CONFIG = {"thinking_level": "high", "max_output_tokens": 65536,
                     "thinking_summaries": "auto"}

# JSON-schema keywords this schema is allowed to use (Gemini structured-output subset).
_ALLOWED = {"type", "properties", "required", "items", "enum", "description",
            "minItems", "maxItems"}

_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


class Discrepancy(BaseModel):
    model_config = ConfigDict(frozen=True)

    t_s: float
    element_id: str | None
    description: str = Field(max_length=500)


class CritiqueResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["completed", "failed", "timeout", "invalid"]
    discrepancies: list[Discrepancy]
    ops: list[PatchOp]
    interaction_id: str | None
    receipt: Receipt | None
    error: str | None = None
    # ops the model returned that did not validate as a PatchOp: (index, error)
    dropped_ops: list[tuple[int, str]] = Field(default_factory=list)


_OP_ADAPTER: TypeAdapter = TypeAdapter(PatchOp)


# --- schema ---------------------------------------------------------------------


def _strip(node: Any) -> Any:
    """Keep only the allowed keywords, recursively (drops minimum, prefixItems, ...)."""
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for k, v in node.items():
        if k not in _ALLOWED:
            continue
        if k == "properties":
            out[k] = {name: _strip(sub) for name, sub in v.items()}
        elif k == "items":
            out[k] = _strip(v)
        else:
            out[k] = v
    return out


def _num(desc: str) -> dict:
    return {"type": "number", "description": desc}


def _pair(desc: str, n: int) -> dict:
    return {"type": "array", "items": {"type": "number"}, "minItems": n, "maxItems": n,
            "description": desc}


@lru_cache(maxsize=1)
def _schema_json() -> str:
    door = _strip(gemini_schema(Door))
    zone = _strip(gemini_schema(Zone))
    measure = _strip(gemini_schema(Measure))
    for el in (door, zone):
        el["properties"]["evidence"]["minItems"] = 1
    door["description"] = "add_door only: the full new door."
    zone["description"] = "add_zone only: the full new zone."
    measure["description"] = "update_door only: new clear width range in meters."
    op = {
        "type": "object",
        "properties": {
            "op": {"type": "string", "enum": list(OP_NAMES)},
            "cite_t_s": _num("Video time in seconds that shows the evidence for this op."),
            "reason": {"type": "string",
                       "description": "What the video shows at cite_t_s (under 200 chars)."},
            "id": {"type": "string",
                   "description": "remove_*/update_* only: id of the existing element."},
            "door": door,
            "zone": zone,
            "position": _pair("update_door only: new [x, y] in meters.", 2),
            "clear_width": measure,
            "state": {"type": "string", "enum": ["open", "closed", "locked", "unknown"],
                      "description": "update_door only."},
            "kind": {"type": "string", "enum": ["door", "opening", "exit", "stair"],
                     "description": "update_door only."},
            "rect": _pair("update_zone only: new [x, y, w, h] in meters.", 4),
            "name": {"type": "string", "description": "update_zone only (under 40 chars)."},
            "furniture_seen": {"type": "boolean", "description": "update_zone only."},
        },
        "required": ["op", "cite_t_s", "reason"],
    }
    schema = {
        "type": "object",
        "properties": {
            "discrepancies": {
                "type": "array",
                "description": "Every place a render disagrees with the video; empty if none.",
                "items": {
                    "type": "object",
                    "properties": {
                        "t_s": _num("Video time where the disagreement is clearest."),
                        "element_id": {"type": ["string", "null"],
                                       "description": "Zone/door id, or null if missing."},
                        "description": {"type": "string",
                                        "description": "Video shows X; twin shows Y."},
                    },
                    "required": ["t_s", "element_id", "description"],
                },
            },
            "ops": {"type": "array", "items": op,
                    "description": "Minimal patch ops, each citing a video time."},
        },
        "required": ["discrepancies", "ops"],
    }
    return json.dumps(schema)


def critique_schema() -> dict:
    return json.loads(_schema_json())


# --- input ----------------------------------------------------------------------


def load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _mime(path: Path) -> str:
    try:
        return _MIME[Path(path).suffix.lower()]
    except KeyError:
        raise ValueError(f"unsupported image type: {path}") from None


def image_part(path: Path) -> dict:
    data = base64.b64encode(Path(path).read_bytes()).decode("ascii")
    return {"type": "image", "data": data, "mime_type": _mime(path)}


def _offset(s: float) -> str:
    return f"{max(s, 0.0):.1f}s"


def zoom_part(video_uri: str, start_s: float, end_s: float) -> dict:
    return {"type": "video", "uri": video_uri, "mime_type": "video/mp4", "resolution": "high",
            "processing": {"type": "static", "fps": ZOOM_FPS,
                           "start_offset": _offset(start_s), "end_offset": _offset(end_s)}}


def build_input(graph: VenueGraph, pairs: list[tuple[Path, Path, float]], *, video_uri: str,
                topdown: Path, zoom: list[tuple[str, float, float]],
                zoom_enabled: bool) -> list[dict]:
    parts: list[dict] = []
    for frame, render, t_s in pairs:
        parts += [{"type": "text", "text": f"t={t_s:g} VIDEO"}, image_part(frame),
                  {"type": "text", "text": "RENDER"}, image_part(render)]
    parts += [{"type": "text", "text": "TOP-DOWN PLAN"}, image_part(topdown)]
    if zoom_enabled:
        for door_id, start_s, end_s in zoom:
            if end_s <= max(start_s, 0.0):
                continue
            parts += [{"type": "text",
                       "text": f"ZOOM {door_id} {_offset(start_s)}-{_offset(end_s)}"},
                      zoom_part(video_uri, start_s, end_s)]
    parts.append({"type": "text",
                  "text": f"CURRENT GRAPH (revision {graph.revision})\n"
                          f"{graph.model_dump_json()}"})
    parts.append({"type": "text", "text": load_prompt()})
    return parts


# --- parsing --------------------------------------------------------------------

_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def _clean_op(raw: dict) -> dict:
    op = {k: v for k, v in raw.items() if v is not None}
    if isinstance(op.get("reason"), str):
        op["reason"] = op["reason"][:200]
    if isinstance(op.get("name"), str):
        op["name"] = op["name"][:60]
    for key in ("door", "zone"):
        el = op.get(key)
        if isinstance(el, dict):
            if key == "zone" and isinstance(el.get("name"), str):
                el["name"] = el["name"][:60]
            for ev in el.get("evidence") or []:
                if isinstance(ev, dict) and isinstance(ev.get("note"), str):
                    ev["note"] = ev["note"][:200]
    return op


def parse_critique(text: str) -> tuple[list[Discrepancy], list, list[tuple[int, str]], str | None]:
    """-> (discrepancies, ops, dropped_ops, error). ``error`` set means unusable output."""
    m = _FENCE.match(text)
    if m:
        text = m.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return [], [], [], f"invalid JSON: {e}"
    if not isinstance(data, dict) or not isinstance(data.get("discrepancies"), list) \
            or not isinstance(data.get("ops"), list):
        return [], [], [], "schema: expected an object with 'discrepancies' and 'ops' lists"
    try:
        discs = [Discrepancy.model_validate(
            {**d, "description": str(d.get("description", ""))[:500]})
            for d in data["discrepancies"]]
    except (ValidationError, TypeError, AttributeError) as e:
        return [], [], [], f"schema: discrepancies: {e}"[:1000]
    ops, dropped = [], []
    for i, raw in enumerate(data["ops"]):
        if not isinstance(raw, dict):
            dropped.append((i, "not an object"))
            continue
        try:
            ops.append(_OP_ADAPTER.validate_python(_clean_op(raw)))
        except ValidationError as e:
            first = e.errors()[0]
            dropped.append((i, f"{'.'.join(map(str, first['loc']))}: {first['msg']}"[:300]))
    return discs, ops, dropped, None


def _provider_error(interaction: Any) -> str:
    msgs = [str(getattr(e, "message", None) or e) for e in (getattr(interaction, "errors", None) or [])]
    return "; ".join(msgs)[:500]


# --- main entry -----------------------------------------------------------------


async def critique(client, graph: VenueGraph, pairs: list[tuple[Path, Path, float]], *,
                   previous_interaction_id: str, video_uri: str, topdown: Path,
                   zoom: list[tuple[str, float, float]] = [], deadline_s: float,
                   zoom_enabled: bool = False) -> CritiqueResult:
    """One chained critique round. ``pairs`` are (video frame, render, t_s), at most 8."""
    if len(pairs) > MAX_PAIRS:
        raise ValueError(f"at most {MAX_PAIRS} frame/render pairs, got {len(pairs)}")
    if not previous_interaction_id:
        raise ValueError("previous_interaction_id is required (chain onto the extraction)")
    started = time.monotonic()
    inp = build_input(graph, pairs, video_uri=video_uri, topdown=topdown, zoom=list(zoom),
                      zoom_enabled=zoom_enabled)

    def result(status, *, receipt=None, discs=(), ops=(), dropped=(), error=None):
        iid = receipt.interaction_id if receipt is not None and receipt.interaction_id else None
        return CritiqueResult(status=status, discrepancies=list(discs), ops=list(ops),
                              interaction_id=iid, receipt=receipt, error=error,
                              dropped_ops=list(dropped))

    try:
        remaining = max(deadline_s - (time.monotonic() - started), 0.001)
        interaction, receipt = await run_background(
            client, deadline_s=remaining, poll_s=POLL_S,
            model=MODEL,
            previous_interaction_id=previous_interaction_id,
            generation_config=dict(GENERATION_CONFIG),
            response_format={"type": "text", "mime_type": "application/json",
                             "schema": critique_schema()},
            input=inp,
        )
    except TimeoutError as e:
        return result("timeout", error=str(e) or "timeout")
    except Exception as e:  # noqa: BLE001 - provider/transport errors are results
        return result("failed", error=f"{type(e).__name__}: {e}"[:1000])

    if receipt.status != "completed":
        detail = _provider_error(interaction)
        err = f"provider status {receipt.status}" + (f": {detail}" if detail else "")
        return result("failed", receipt=receipt, error=err)

    discs, ops, dropped, err = parse_critique(joined_text(interaction))
    if err:
        return result("invalid", receipt=receipt, error=err)
    return result("completed", receipt=receipt, discs=discs, ops=ops, dropped=dropped)
