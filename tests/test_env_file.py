"""The startup .env loader fills only unset, allowed variables and never reports values."""
from backend.app.env_file import load_env_file


def test_sets_unset_allowed_keys_only(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# comment\nGEMINI_API_KEY=abc123 # inline\nexport SERIAL_BAUD='9600'\nSPATIALTWIN_ORIGINS=\n"
                   "PYTHONPATH=/evil\nDYLD_INSERT_LIBRARIES=/evil.dylib\nNOT A LINE\n")
    environ = {"SPATIALTWIN_MODE": "production"}
    assert load_env_file(env, environ) == ["GEMINI_API_KEY", "SERIAL_BAUD", "SPATIALTWIN_ORIGINS"]
    assert environ == {"SPATIALTWIN_MODE": "production", "GEMINI_API_KEY": "abc123", "SERIAL_BAUD": "9600",
                       "SPATIALTWIN_ORIGINS": ""}
    (tmp_path / "other").write_text("SPATIALTWIN_MODE=demo\n")
    assert load_env_file(tmp_path / "other", environ) == [] and environ["SPATIALTWIN_MODE"] == "production"


def test_quoted_values_comments_tabs_and_bom(tmp_path):
    env = tmp_path / ".env"
    env.write_bytes('﻿GEMINI_API_KEY="abc 123" # the key\nSERIAL_PORT=/dev/cu.usb\t# tab comment\n'
                    "HOST='127.0.0.1'\n".encode("utf-8"))
    environ: dict = {}
    load_env_file(env, environ)
    assert environ == {"GEMINI_API_KEY": "abc 123", "SERIAL_PORT": "/dev/cu.usb", "HOST": "127.0.0.1"}


def test_disabled_by_empty_setting_and_missing_file(tmp_path):
    assert load_env_file(environ={"SPATIALTWIN_ENV_FILE": ""}) == []
    assert load_env_file(environ={"SPATIALTWIN_ENV_FILE": str(tmp_path / "missing.env")}) == []
