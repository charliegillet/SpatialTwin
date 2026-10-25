#!/usr/bin/env python3
"""post_tool_execution audit: append one JSON line per sandbox tool call to /workspace/out/audit.jsonl.

Records the tool name, the target path or a sha256 and length of the code (never the code itself), and whether the
tool reported an error. A guardrail, not authority: hooks fail open and only see code_execution and filesystem tools.
"""
import hashlib
import json
import os
import sys
import time

LOG = os.environ.get("SPATIALTWIN_AUDIT", "/workspace/out/audit.jsonl")


def record(event):
    call = event.get("tool_call") or {}
    args = call.get("args") if isinstance(call.get("args"), dict) else {}
    code = str(args.get("code") or "")
    entry = {"ts": round(time.time(), 3), "tool": str(call.get("name") or "")[:64],
             "error": bool(event.get("error"))}
    for key in ("path", "file_path", "target_file", "TargetFile", "AbsolutePath"):
        if args.get(key):
            entry["path"] = str(args[key])[:200]
            break
    if code:
        entry["code_sha256"] = hashlib.sha256(code.encode()).hexdigest()[:16]
        entry["code_chars"] = len(code)
    return entry


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        event = {}
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as handle:
            handle.write(json.dumps(record(event if isinstance(event, dict) else {})) + "\n")
    except OSError:
        pass
    print("{}")


if __name__ == "__main__":
    main()
