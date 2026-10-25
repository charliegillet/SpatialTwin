"""Optional managed-agent registration and environment config. No provider call unless enabled."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]

AGENT_ID = "spatialtwin-evac-v1"
BASE_AGENT = "antigravity-preview-09-2026"
AGENT_MODEL = "gemini-4-argon"  # must equal adapter.MODEL; checked by tests
ENABLE_ENV = "SPATIALTWIN_CREATE_AGENT"
NETWORK_DENY_ENV = "SPATIALTWIN_NETWORK_DENY"
DEFAULT_CACHE = str(REPO_ROOT / "runtime" / "managed" / "agent_ref.json")
POLICY_FILE = Path(__file__).parent / "policy_files" / "AGENTS.md"

# SDK 2.33 EnvironmentParam: {"type": "remote", "network": "disabled" | {"allowlist": ...}}.
NETWORK_DENY_ENVIRONMENT = {"type": "remote", "network": "disabled"}


@dataclass(frozen=True)
class AgentRef:
    agent_id: str
    created: bool = False
    # Model read from the saved agent's own definition (agent_config.model) as returned at creation.
    # None means unverified; a cache written before this field existed is treated as unverified.
    verified_model: str | None = None


def _enabled(flag: bool | None) -> bool:
    return flag if flag is not None else os.environ.get(ENABLE_ENV, "") == "1"


def _definition_model(agent: Any) -> str | None:
    """Model in a saved agent's definition, only when it is the model this build pins."""
    config = agent.get("agent_config") if isinstance(agent, dict) else getattr(agent, "agent_config", None)
    model = config.get("model") if isinstance(config, dict) else getattr(config, "model", None)
    return model if model == AGENT_MODEL else None


def _read_cache(path: Path) -> AgentRef | None:
    try:
        data = json.loads(path.read_text())
        if isinstance(data, dict) and data.get("agent_id") == AGENT_ID:
            verified = data.get("verified_model")
            return AgentRef(AGENT_ID, verified_model=verified if verified == AGENT_MODEL else None)
    except (OSError, ValueError):
        pass  # missing or unreadable cache: treated as not cached
    return None


async def ensure_agent(client: Any = None, *, enabled: bool | None = None,
                       cache_path: str = DEFAULT_CACHE) -> AgentRef | None:
    """Return the cached or newly created agent, or None to use the base agent.

    Creation requires ``enabled`` (or SPATIALTWIN_CREATE_AGENT=1) and a client; any
    provider error yields None. Error text is never inspected or logged.
    """
    path = Path(cache_path)
    cached = _read_cache(path)
    if cached:
        return cached
    if not _enabled(enabled) or client is None:
        return None
    try:
        # A named agent fixes its model here; the provider refuses an interaction-time override.
        agent = await client.aio.agents.create(
            id=AGENT_ID, base_agent=BASE_AGENT, description="SpatialTwin evacuation twin",
            agent_config={"type": "antigravity", "model": AGENT_MODEL},
            system_instruction=POLICY_FILE.read_text(), timeout=30)
    except Exception:
        return None
    verified = _definition_model(agent)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"agent_id": AGENT_ID, "base_agent": BASE_AGENT, "verified_model": verified}))
    except OSError:
        # The remote agent exists; losing the cache must not orphan it.
        logger.warning("managed agent created but cache write failed (agent_ref_cache_unwritable)")
    return AgentRef(AGENT_ID, created=True, verified_model=verified)


def build_environment(enabled: bool | None = None) -> Any:
    """Network-deny environment when enabled, else the plain "remote" string."""
    if enabled is None:
        enabled = os.environ.get(NETWORK_DENY_ENV, "") == "1"
    return dict(NETWORK_DENY_ENVIRONMENT) if enabled else "remote"
