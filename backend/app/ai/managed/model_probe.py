"""Model resolution: first provider-accepted candidate, cached for offline use."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

CANDIDATES = ("gemini-4-argon", "gemini-3.8-flash")
DEFAULT_CACHE = "runtime/probes/model_resolution.json"


@dataclass(frozen=True)
class ModelResolution:
    model: str
    is_fallback: bool

    @property
    def provenance(self) -> str:
        return "live (fallback model)" if self.is_fallback else "live"


def _resolution(model: str, candidates: tuple[str, ...]) -> ModelResolution:
    return ModelResolution(model, model != candidates[0])


def resolve_model(candidates: tuple[str, ...] = CANDIDATES,
                  cache_path: str = DEFAULT_CACHE) -> ModelResolution | None:
    """Offline: read the cached live result. Never calls a provider."""
    try:
        data = json.loads(Path(cache_path).read_text())
        model = data.get("model") if isinstance(data, dict) else None
    except Exception:
        return None
    return _resolution(model, candidates) if model in candidates else None


async def resolve_model_live(accept: Callable[[str], Awaitable[bool]],
                             candidates: tuple[str, ...] = CANDIDATES,
                             cache_path: str = DEFAULT_CACHE) -> ModelResolution | None:
    """Try candidates in order with a caller-supplied one-turn probe; cache the first accepted.

    Not called by default. ``accept`` must verify the provider echoed the same model.
    """
    for model in candidates:
        try:
            ok = await accept(model)
        except Exception:
            ok = False
        if ok:
            path = Path(cache_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"model": model, "candidates": list(candidates)}))
            return _resolution(model, candidates)
    return None
