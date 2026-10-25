"""Offline tests must never reach a provider/device or the user's runtime DB."""
import os
import socket
from uuid import uuid4
import pytest
from backend.app.state.store import SQLiteStore

# Set before any test module imports the app: a developer's real .env must never reach offline tests.
os.environ["SPATIALTWIN_ENV_FILE"] = ""


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch, tmp_path):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setenv("SERIAL_PORT", "")
    monkeypatch.setenv("SPATIALTWIN_MODE", "demo")
    monkeypatch.setenv("SPATIALTWIN_RECEIPTS_DIR", str(tmp_path / "receipts"))

    def no_network(*args, **kwargs):
        raise AssertionError("Real network access is forbidden in offline tests")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket.socket, "connect_ex", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    init = SQLiteStore.__init__

    def isolated_store(self, db_path=None):
        init(self, db_path or str(tmp_path / f"store-{uuid4().hex}.sqlite3"))

    monkeypatch.setattr(SQLiteStore, "__init__", isolated_store)
    # The venue registry is created on first use; drop it so each test opens its own isolated database.
    from backend.app.venues.registry import set_venue_registry
    set_venue_registry(None)
    yield
    set_venue_registry(None)


@pytest.fixture(autouse=True)
def loopback_test_client(monkeypatch):
    """TestClient defaults to a non-loopback peer ("testclient"); the app's network guard would reject it."""
    from starlette.testclient import TestClient
    init = TestClient.__init__

    def loopback_init(self, app, *args, client=("127.0.0.1", 50000), **kwargs):
        init(self, app, *args, client=client, **kwargs)

    monkeypatch.setattr(TestClient, "__init__", loopback_init)
