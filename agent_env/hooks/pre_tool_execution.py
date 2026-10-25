#!/usr/bin/env python3
"""WalkTwin audit hook (pre_tool_execution) for the managed-agent sandbox.

Contract (Gemini agent hooks): the runtime writes the event JSON to stdin,
``{"tool_call": {"name": ..., "args": {...}}, "environment_id": ...}``, and reads
``{"decision": "allow"}`` or ``{"decision": "deny", "reason": ...}`` from stdout.

This is an *audit* hook, not an authority: the runtime fails open on a crash,
timeout or unrecognised output, and hooks never fire for custom functions. The
accepted graph only changes through a human approve on the WalkTwin server.
The code_execution check is a best-effort line heuristic.
"""
from __future__ import annotations

import json
import re
import sys

MARKER = "WALKTWIN_AUDIT_DENY"
PROTECTED = ("accepted_graph.json", ".agents/hooks")  # the graph and this hook
WRITE_TOOLS = {"write_to_file", "replace_file_content", "delete_file"}
_REASON = (f"{MARKER}: /workspace/accepted_graph.json (the accepted graph) and the audit "
           "hook files are read-only in the sandbox. Copy the graph (e.g. to "
           "/workspace/work/graph.json) and edit the copy; only a human approve changes "
           "the accepted graph.")

_P = r"""\S*(accepted_graph\.json|\.agents/hooks)"""
# Applied to lines that name a protected file. Reading or copying *from* the
# file is allowed; writing, moving, removing or copying *onto* it is not.
_WRITE_PATTERNS = [re.compile(p) for p in (
    r"""open\([^)]*""" + _P + r"""[^)]*,\s*(mode\s*=\s*)?['"][^'"]*[wax+]""",
    r""">>?\s*['"]?""" + _P,                                   # shell redirect into it
    r"""\b(rm|mv|tee|truncate|touch|unlink)\b""",             # shell, any position
    r"""\bsed\s+(-\w*\s+)*-i""",
    r"""\b(cp|ln|install|rsync|dd)\b.*""" + _P + r"""\S*['"]?\s*;?\s*$""",  # destination
    r"""\.(write_text|write_bytes|unlink|rename|replace|touch)\(""",       # pathlib
    r"""os\.(remove|unlink|rename|replace)\(|shutil\.(move|rmtree)\(""",
    r"""shutil\.copy\w*\([^,]+,[^)]*""" + _P,                # destination
)]


def _strings(obj) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in _strings(v)]
    if isinstance(obj, (list, tuple)):
        return [s for v in obj for s in _strings(v)]
    return []


def _names_protected(text: str) -> bool:
    return any(p in text for p in PROTECTED)


def decide(payload) -> dict:
    try:
        call = payload.get("tool_call") or {}
        name = str(call.get("name") or "")
        args = call.get("args") or {}
    except AttributeError:
        return {"decision": "allow"}
    if name in WRITE_TOOLS:
        # Path argument names differ between tools; check every string argument
        # except the file body itself.
        targets = _strings({k: v for k, v in args.items()
                            if k not in ("content", "CodeContent", "ReplacementContent")})
        if any(_names_protected(t) for t in targets):
            return {"decision": "deny", "reason": _REASON}
    elif name == "code_execution":
        code = "\n".join(_strings(args.get("code", "")))
        for line in code.splitlines():
            if _names_protected(line) and any(p.search(line) for p in _WRITE_PATTERNS):
                return {"decision": "deny", "reason": _REASON}
    return {"decision": "allow"}


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except Exception:  # noqa: BLE001 - malformed input: allow (runtime fails open anyway)
        payload = {}
    print(json.dumps(decide(payload)))


if __name__ == "__main__":
    main()
