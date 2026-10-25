"""Load the repository .env at startup, so `uvicorn backend.app.main:app` sees GEMINI_API_KEY without a wrapper.

Variables already present in the process environment always win. SPATIALTWIN_ENV_FILE names another file;
an empty value disables loading (the offline test harness sets it before the app is imported).
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

ENV_FILE_ENV = "SPATIALTWIN_ENV_FILE"
DEFAULT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")


def _value(raw: str) -> str:
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
    # Unquoted values end at an inline comment.
    return raw.split(" #", 1)[0].rstrip()


def load_env_file(path: Optional[Path] = None) -> list[str]:
    """Set unset variables from the file. Returns the names it set; never their values."""
    if path is None:
        configured = os.environ.get(ENV_FILE_ENV)
        if configured == "":
            return []
        path = Path(configured) if configured else DEFAULT_ENV_FILE
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    loaded = []
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = _LINE.match(line)
        if match and match.group(1) not in os.environ:
            os.environ[match.group(1)] = _value(match.group(2))
            loaded.append(match.group(1))
    return loaded
