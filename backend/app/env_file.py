"""Load the repository .env at startup, so `uvicorn backend.app.main:app` sees GEMINI_API_KEY without a wrapper.

Variables already present in the process environment always win. SPATIALTWIN_ENV_FILE names another file;
an empty value disables loading (the offline test harness sets it before the app is imported). Only this app's
own settings are read: a .env can never set interpreter or loader variables such as PYTHONPATH or DYLD_*.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import MutableMapping, Optional

ENV_FILE_ENV = "SPATIALTWIN_ENV_FILE"
DEFAULT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
ALLOWED_KEYS = frozenset({"GEMINI_API_KEY", "SERIAL_PORT", "SERIAL_BAUD", "HOST", "PORT"})
ALLOWED_PREFIX = "SPATIALTWIN_"
_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")
_INLINE_COMMENT = re.compile(r"\s+#.*$")


def _value(raw: str) -> str:
    raw = raw.strip()
    if raw[:1] in ("'", '"'):
        # A quoted value ends at its closing quote; anything after it (an inline comment) is ignored.
        closing = raw.find(raw[0], 1)
        if closing > 0:
            return raw[1:closing]
    # Unquoted values end at an inline comment (a "#" after whitespace, spaces or tabs).
    return _INLINE_COMMENT.sub("", raw).rstrip()


def _allowed(name: str) -> bool:
    return name in ALLOWED_KEYS or (name.startswith(ALLOWED_PREFIX) and name != ENV_FILE_ENV)


def load_env_file(path: Optional[Path] = None, environ: Optional[MutableMapping[str, str]] = None) -> list[str]:
    """Set unset, allowed variables from the file. Returns the names it set; never their values."""
    environ = os.environ if environ is None else environ
    if path is None:
        configured = environ.get(ENV_FILE_ENV)
        if configured == "":
            return []
        path = Path(configured) if configured else DEFAULT_ENV_FILE
    try:
        # utf-8-sig: an editor's byte-order mark must not swallow the first variable.
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    loaded = []
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = _LINE.match(line)
        if match and _allowed(match.group(1)) and match.group(1) not in environ:
            environ[match.group(1)] = _value(match.group(2))
            loaded.append(match.group(1))
    return loaded
