"""Offline tests must never reach a provider/device or the user's runtime DB."""
import socket
from uuid import uuid4
import pytest
from backend.app.state.store import SQLiteStore


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("SERIAL_PORT", "")
    monkeypatch.setenv("SPATIALTWIN_MODE", "demo")

    def no_network(*args, **kwargs):
        raise AssertionError("Real network access is forbidden in offline tests")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    init = SQLiteStore.__init__

    def isolated_store(self, db_path=None):
        init(self, db_path or str(tmp_path / f"store-{uuid4().hex}.sqlite3"))

    monkeypatch.setattr(SQLiteStore, "__init__", isolated_store)
