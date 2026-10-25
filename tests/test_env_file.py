"""The startup .env loader fills only unset variables and never reports values."""
import os

from backend.app.env_file import load_env_file


def test_sets_unset_keys_only(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# comment\nGEMINI_API_KEY=abc123 # inline\nexport SERIAL_BAUD='9600'\nEMPTY=\nNOT A LINE\n")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("SERIAL_BAUD", raising=False)
    monkeypatch.delenv("EMPTY", raising=False)
    monkeypatch.setenv("SPATIALTWIN_MODE", "production")
    (tmp_path / "other").write_text("SPATIALTWIN_MODE=demo\n")
    assert load_env_file(env) == ["GEMINI_API_KEY", "SERIAL_BAUD", "EMPTY"]
    assert os.environ["GEMINI_API_KEY"] == "abc123" and os.environ["SERIAL_BAUD"] == "9600" and os.environ["EMPTY"] == ""
    assert load_env_file(tmp_path / "other") == []
    assert os.environ["SPATIALTWIN_MODE"] == "production"


def test_disabled_by_empty_setting_and_missing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SPATIALTWIN_ENV_FILE", "")
    assert load_env_file() == []
    monkeypatch.setenv("SPATIALTWIN_ENV_FILE", str(tmp_path / "missing.env"))
    assert load_env_file() == []
