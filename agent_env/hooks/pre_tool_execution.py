#!/usr/bin/env python3
"""WalkTwin audit hook (pre_tool_execution) for the managed-agent sandbox.

Contract (Gemini agent hooks): the runtime writes the event JSON to stdin,
``{"tool_call": {"name": ..., "args": {...}}, "environment_id": ...}``, and reads
``{"decision": "allow"}`` or ``{"decision": "deny", "reason": ...}`` from stdout.

Audit-hooked paths:
- per-investigation inputs ``/workspace/inv-<id>/{graph,scenario,params}.json`` are
  write-once: creating a missing one is allowed, changing an existing one is denied;
- ``accepted_graph.json`` and the hook files under ``.agents/hooks*`` are always denied.

This is an *audit* hook, not an authority: the runtime fails open on a crash,
timeout or unrecognised output, and hooks never fire for custom functions. The
accepted graph only changes through a human approve on the WalkTwin server.
The code_execution check is a best-effort line heuristic (a path held in a
variable is not seen).
"""
from __future__ import annotations

import json
import os
import re
import sys

MARKER = "WALKTWIN_AUDIT_DENY"
WRITE_TOOLS = {"write_to_file", "replace_file_content", "delete_file"}
PATH_KEYS = {"path", "file_path", "filepath", "target_file", "TargetFile", "AbsolutePath",
             "absolute_path", "file", "filename", "target"}
_REASON = (f"{MARKER}: this investigation's inputs (/workspace/inv-<id>/graph.json, "
           "scenario.json, params.json) are write-once and audit-hooked, and the hook "
           "files may not be changed. Copy the graph to /workspace/inv-<id>/work/ and edit "
           "the copy; only a human approve changes the accepted graph.")

_ALWAYS = re.compile(r"accepted_graph\.json|\.agents/hooks")
_INPUT = re.compile(r"(?:/workspace/)?inv-[\w-]+/(?:graph|scenario|params)\.json")
_P = r"""['"]?\S*?(?:accepted_graph\.json|\.agents/hooks[\w./-]*|inv-[\w-]+/(?:graph|scenario|params)\.json)"""
_SEG = r"""[^;&|\n]*?"""  # rest of one shell command segment
# Each pattern ends on (or contains) the protected path in a *destination* role.
_WRITE_PATTERNS = [re.compile(p) for p in (
    r"""open\(\s*""" + _P + r"""['"]?\s*,\s*(?:mode\s*=\s*)?['"][^'"]*[wax+]""",
    r""">>?\s*""" + _P,                                             # redirect into it
    r"""\b(?:rm|mv|truncate|touch|unlink|shred)\b""" + _SEG + r"""\s""" + _P,
    r"""\btee\b""" + _SEG + r"""\s""" + _P,                         # tee writes its args
    r"""\bsed\s+(?:-\w*\s+)*-i""" + _SEG + _P,
    r"""\b(?:cp|ln|install|rsync)\b""" + _SEG + r"""\s""" + _P + r"""['"]?\s*(?:$|[;&|])""",
    _P + r"""['"]?\s*\)\s*\.(?:write_text|write_bytes|unlink|rename|replace|touch)\(""",
    r"""os\.(?:remove|unlink|rename|replace)\([^)]*""" + _P,
    r"""shutil\.(?:move|rmtree)\([^)]*""" + _P,
    r"""shutil\.copy\w*\([^,]+,\s*""" + _P,                          # destination arg
)]


def _hits(text: str, exists) -> bool:
    if _ALWAYS.search(text):
        return True
    for m in _INPUT.finditer(text):
        p = m.group(0)
        if exists(p if p.startswith("/") else "/workspace/" + p):
            return True
    return False


def _decide(payload, exists) -> dict:
    call = payload.get("tool_call") or {}
    name = str(call.get("name") or "")
    args = call.get("args") or {}
    if name in WRITE_TOOLS:
        targets = [v for k, v in args.items() if k in PATH_KEYS and isinstance(v, str)]
        if any(_hits(t, exists) for t in targets):
            return {"decision": "deny", "reason": _REASON}
    elif name == "code_execution":
        code = args.get("code", "")
        for line in (code if isinstance(code, str) else "").splitlines():
            for pat in _WRITE_PATTERNS:
                if any(_hits(m.group(0), exists) for m in pat.finditer(line)):
                    return {"decision": "deny", "reason": _REASON}
    return {"decision": "allow"}


def decide(payload, exists=os.path.exists) -> dict:
    """Total: any unexpected input or internal error means allow."""
    try:
        return _decide(payload, exists)
    except Exception:  # noqa: BLE001
        return {"decision": "allow"}


def main() -> None:
    try:
        out = decide(json.load(sys.stdin))
    except Exception:  # noqa: BLE001 - malformed input: allow (runtime fails open anyway)
        out = {"decision": "allow"}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
