#!/usr/bin/env python3
"""pre_tool_execution guardrail: deny writes to /workspace/inputs/** and .agents/**.

A guardrail, not authority. Hooks fail open (a crash, timeout or odd output is an allow), they only see the sandbox's
code_execution and filesystem tools (never client functions), and an agent with shell access could edit this file.
The authority is the laptop's local checker, which re-runs every number. Shell detection is a heuristic.
"""
import json
import re
import sys

PROTECTED = ("/workspace/inputs", "workspace/inputs", "/.agents", ".agents/")
PATH_KEYS = ("path", "file_path", "target_file", "TargetFile", "AbsolutePath", "absolute_path", "file", "target")
WRITE_HINT = re.compile(
    r"(>>?|\btee\b|\brm\b|\bmv\b|\bcp\b|\bsed\s+-i|\btruncate\b|\bchmod\b|\bln\b|\bunlink\b|\brmdir\b|"
    r"\.write\(|\.write_text\(|\.write_bytes\(|open\([^)]*['\"][wax+]|os\.remove|os\.rename|shutil\.)")


def decide(event):
    call = event.get("tool_call") or {}
    name = str(call.get("name") or "")
    args = call.get("args") or {}
    if not isinstance(args, dict):
        return {"decision": "allow"}
    if name in ("write_to_file", "replace_file_content", "delete_file"):
        for key in PATH_KEYS:
            value = str(args.get(key) or "")
            if any(marker in value for marker in PROTECTED):
                return {"decision": "deny",
                        "reason": "Read-only: /workspace/inputs and .agents are protected. Write under /workspace/out/."}
        return {"decision": "allow"}
    if name == "code_execution":
        code = str(args.get("code") or "")
        for line in code.splitlines():
            if any(marker in line for marker in PROTECTED) and WRITE_HINT.search(line):
                return {"decision": "deny",
                        "reason": "Read-only: this command appears to write to /workspace/inputs or .agents. "
                                  "Write under /workspace/out/ instead."}
    return {"decision": "allow"}


def main():
    try:
        event = json.load(sys.stdin)
    except ValueError:
        event = {}
    print(json.dumps(decide(event if isinstance(event, dict) else {})))


if __name__ == "__main__":
    main()
