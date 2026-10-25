"""Model resolution: first provider-accepted candidate, cached for offline use."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

CANDIDATES = ("gemini-4-argon", "gemini-3.8-flash")
REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CACHE = str(REPO_ROOT / "runtime" / "probes" / "model_resolution.json")


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
                  cache_path: str | None = None) -> ModelResolution | None:
    """Offline: read the cached live result. Never calls a provider."""
    try:
        data = json.loads(Path(cache_path or DEFAULT_CACHE).read_text())
        # The live probe writes resolved_managed_model; "model" is accepted for older cache files.
        model = (data.get("resolved_managed_model") or data.get("model")) if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None
    return _resolution(model, candidates) if model in candidates else None


def _is_definitive_rejection(error: BaseException) -> bool:
    """True only for a typed HTTP 4xx the provider sent about the request (not auth, quota or timeout)."""
    code = getattr(error, "code", None) or getattr(error, "status_code", None)
    if code is None:
        code = getattr(getattr(error, "response", None), "status_code", None)
    return type(code) is int and code in (400, 404, 409, 422)


async def resolve_model_live(accept: Callable[[str], Awaitable[bool]],
                             candidates: tuple[str, ...] = CANDIDATES,
                             cache_path: str | None = None) -> ModelResolution | None:
    """Try candidates in order with a caller-supplied one-turn probe; cache the first accepted.

    Not called by default. ``accept`` must verify the provider echoed the same model. A candidate
    counts as rejected only when ``accept`` returns False or the provider answers with a definitive
    request rejection; any other error (timeout, network, quota, auth, a local bug) aborts without
    caching, so a transient failure never pins the fallback model.
    """
    for model in candidates:
        try:
            ok = await accept(model)
        except Exception as error:
            if _is_definitive_rejection(error):
                continue
            return None
        if ok:
            path = Path(cache_path or DEFAULT_CACHE)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"resolved_managed_model": model, "model": model,
                                        "candidates": list(candidates)}))
            return _resolution(model, candidates)
    return None
