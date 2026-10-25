"""Sandbox environment for the Robustness lane: the solver kit plus this incident's inputs, network disabled.

Mounting (verified against agent-environment.md, read 23 Oct 2026, and google-genai 2.33):
- **Used at runtime: inline sources per interaction.** ``environment={"type": "remote", "network": "disabled",
  "sources": [{"type": "inline", "target": ..., "content": ...}]}``. Documented limits: 1 MB per inline file, 2 MB in
  total. The kit is ~70 KB, the inputs a few KB. ``.agents/AGENTS.md``, ``.agents/skills/*/SKILL.md`` and
  ``.agents/hooks.json`` are auto-discovered by the harness (custom-agents.md, agent-hooks.md).
- **Not used yet: a prepared base environment.** SDK 2.33 exposes ``client.aio.environments.create(network=...,
  sources=..., from_environment=...)`` (``_gaos/environments.py``) but the dated docs list only list/get/delete and
  the files API, so this path waits for a live probe (P11 in tools/probe_capabilities.py) before the app relies on it.

The kit's manifest is checked here (sha256 per file) so a stale or edited kit is refused, not mounted.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.venues.model import VenueV2

KIT_DIR = Path(__file__).parent / "sandbox_kit"
INLINE_FILE_LIMIT = 1_000_000
INLINE_TOTAL_LIMIT = 2_000_000
INPUT_TARGETS = {"venue": "workspace/inputs/venue.json", "hazards": "workspace/inputs/hazards.json",
                 "checked_plan": "workspace/inputs/checked_plan.json"}


class SandboxKitError(Exception):
    """Carries only a short code."""


@lru_cache(maxsize=1)
def load_kit(kit_dir: str = str(KIT_DIR)) -> Dict[str, Any]:
    """Manifest plus file contents, every sha256 verified. Raises SandboxKitError('sandbox_kit_invalid')."""
    root = Path(kit_dir)
    try:
        manifest = json.loads((root / "manifest.json").read_text())
        files = []
        for entry in manifest["files"]:
            data = (root / entry["path"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != entry["sha256"] or len(data) != entry["bytes"]:
                raise SandboxKitError("sandbox_kit_invalid")
            files.append({"target": entry["target"], "content": data.decode("utf-8")})
        manifest_text = (root / "manifest.json").read_text()
    except SandboxKitError:
        raise
    except Exception:
        raise SandboxKitError("sandbox_kit_invalid") from None
    files.append({"target": "workspace/kit/manifest.json", "content": manifest_text})
    return {"manifest": manifest, "files": files}


def input_documents(venue: VenueV2, horizon: int, hazards: List[dict], checked_plan: Dict[str, Any]) -> Dict[str, str]:
    """The incident inputs the sandbox reads (resolved hazards, so the sandbox needs no request validation)."""
    resolved = [{"id": h["id"], "type": h["type"], "zone_id": h["zone_id"], "untenable_s": h.get("untenable_s")}
                for h in hazards]
    return {
        "venue": json.dumps(venue.to_json(), sort_keys=True),
        "hazards": json.dumps({"horizon_seconds": horizon, "hazards": resolved}, sort_keys=True),
        "checked_plan": json.dumps(checked_plan, sort_keys=True),
    }


def sandbox_environment(inputs: Dict[str, str], *, network_disabled: bool = True,
                        kit_dir: Optional[str] = None) -> Dict[str, Any]:
    """Inline EnvironmentParam: kit + inputs, network disabled. Raises SandboxKitError on size limits."""
    kit = load_kit(kit_dir or str(KIT_DIR))
    sources = [{"type": "inline", "target": f["target"], "content": f["content"]} for f in kit["files"]]
    sources += [{"type": "inline", "target": INPUT_TARGETS[name], "content": content}
                for name, content in inputs.items()]
    sizes = [len(s["content"].encode("utf-8")) for s in sources]
    if any(size > INLINE_FILE_LIMIT for size in sizes):
        raise SandboxKitError("sandbox_source_too_large")
    if sum(sizes) > INLINE_TOTAL_LIMIT:
        raise SandboxKitError("sandbox_sources_too_large")
    environment: Dict[str, Any] = {"type": "remote", "sources": sources}
    if network_disabled:
        environment["network"] = "disabled"
    return environment


def kit_summary(kit_dir: Optional[str] = None) -> Dict[str, Any]:
    """For results and the trace: kit version, file count and bytes (no contents)."""
    try:
        manifest = load_kit(kit_dir or str(KIT_DIR))["manifest"]
    except SandboxKitError as error:
        return {"available": False, "error": str(error)}
    return {"available": True, "kit_version": manifest.get("kit_version"), "files": len(manifest.get("files", [])),
            "bytes": manifest.get("total_bytes")}
