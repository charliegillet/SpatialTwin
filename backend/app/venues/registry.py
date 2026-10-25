"""Venue registry: drafts, accepted venues and the active-venue pointer, in the runtime SQLite database.

building-v2 is built in and read-only; it is always listed and is the default active venue. Every other venue
starts as a draft (a Gemini reading compiled into a VenueV2) and becomes usable only when an operator accepts it.
Drafts and the active pointer change under compare-and-set revisions, so a stale screen gets a conflict instead
of silently overwriting a newer reading.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.app.state.store import SQLiteStore
from backend.app.venues.model import BUILTIN_VENUE_ID, VenueV2, load_building_v2


class RegistryConflict(Exception):
    """The caller's expected revision is no longer current."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class VenueRegistry:
    def __init__(self, db_path: Optional[str] = None):
        # The same runtime database as the scenario store; the offline tests isolate it by patching SQLiteStore.
        self.db_path = db_path or SQLiteStore().db_path
        self._lock = threading.Lock()
        with self._connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS venues (
                    venue_id TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL,
                    venue_json TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    created_at_iso TEXT NOT NULL,
                    updated_at_iso TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS venue_drafts (
                    draft_id TEXT PRIMARY KEY,
                    revision INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at_iso TEXT NOT NULL,
                    updated_at_iso TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS venue_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    revision INTEGER NOT NULL
                );
            """)

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0, isolation_level=None)
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = FULL;")
            conn.row_factory = sqlite3.Row
            yield conn
        finally:
            conn.close()

    @contextmanager
    def _transaction(self):
        """One writer at a time, so a compare-and-set reads and writes the same state."""
        with self._lock, self._connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")

    # --- accepted venues ------------------------------------------------------------------------------------

    def accepted_venue(self, venue_id: str) -> Optional[VenueV2]:
        if venue_id == BUILTIN_VENUE_ID:
            return load_building_v2()
        with self._connection() as conn:
            row = conn.execute("SELECT venue_json FROM venues WHERE venue_id = ?", (venue_id,)).fetchone()
        return VenueV2.model_validate(json.loads(row["venue_json"])) if row else None

    def venue_record(self, venue_id: str) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM venues WHERE venue_id = ?", (venue_id,)).fetchone()
        if row is None:
            return None
        return {"venue_id": row["venue_id"], "revision": row["revision"], "created_at": row["created_at_iso"],
                "updated_at": row["updated_at_iso"], **json.loads(row["record_json"])}

    def list_venues(self) -> List[Dict[str, Any]]:
        builtin = load_building_v2()
        listed = [{"venue_id": builtin.venue_id, "revision": 1, "builtin": True, "name": "building-v2 (built in)",
                   "geometry_revision": builtin.geometry_revision, "provenance": builtin.provenance,
                   "zones": len(builtin.zones), "doors": len(builtin.doors), "exits": len(builtin.exits),
                   "created_at": None, "source_kind": "authored"}]
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM venues ORDER BY created_at_iso").fetchall()
        for row in rows:
            venue = json.loads(row["venue_json"])
            record = json.loads(row["record_json"])
            listed.append({"venue_id": row["venue_id"], "revision": row["revision"], "builtin": False,
                           "name": record.get("name") or row["venue_id"],
                           "geometry_revision": venue["geometry_revision"], "provenance": venue["provenance"],
                           "zones": len(venue["zones"]), "doors": len(venue["doors"]), "exits": len(venue["exits"]),
                           "created_at": row["created_at_iso"], "source_kind": record.get("source_kind")})
        return listed

    def _save_venue(self, conn: sqlite3.Connection, venue: VenueV2, record: Dict[str, Any]) -> int:
        if venue.venue_id == BUILTIN_VENUE_ID:
            raise RegistryConflict("builtin_venue_read_only")
        now = _now()
        row = conn.execute("SELECT revision FROM venues WHERE venue_id = ?", (venue.venue_id,)).fetchone()
        revision = (row["revision"] + 1) if row else 1
        payload = (json.dumps(venue.to_json(), sort_keys=True), json.dumps(record, sort_keys=True))
        if row:
            conn.execute("UPDATE venues SET revision = ?, venue_json = ?, record_json = ?, updated_at_iso = ? "
                         "WHERE venue_id = ?", (revision, *payload, now, venue.venue_id))
        else:
            conn.execute("INSERT INTO venues VALUES (?, ?, ?, ?, ?, ?)", (venue.venue_id, revision, *payload, now, now))
        return revision

    def save_venue(self, venue: VenueV2, record: Dict[str, Any]) -> int:
        """Store an accepted venue directly (seeded saved runs and tests). Returns its new revision."""
        with self._transaction() as conn:
            return self._save_venue(conn, venue, record)

    # --- active venue ---------------------------------------------------------------------------------------

    def _active(self, conn: sqlite3.Connection) -> tuple[str, int]:
        row = conn.execute("SELECT value, revision FROM venue_settings WHERE key = 'active_venue'").fetchone()
        if row is None:
            return BUILTIN_VENUE_ID, 0
        # A pointer to a venue that no longer exists falls back to the built-in venue.
        if row["value"] != BUILTIN_VENUE_ID and conn.execute(
                "SELECT 1 FROM venues WHERE venue_id = ?", (row["value"],)).fetchone() is None:
            return BUILTIN_VENUE_ID, row["revision"]
        return row["value"], row["revision"]

    def active(self) -> Dict[str, Any]:
        with self._connection() as conn:
            venue_id, revision = self._active(conn)
        return {"venue_id": venue_id, "revision": revision}

    def _set_active(self, conn: sqlite3.Connection, venue_id: str, expected_revision: Optional[int]) -> int:
        current_id, current_revision = self._active(conn)
        if expected_revision is not None and expected_revision != current_revision:
            raise RegistryConflict("stale_active_revision")
        if venue_id != BUILTIN_VENUE_ID and conn.execute(
                "SELECT 1 FROM venues WHERE venue_id = ?", (venue_id,)).fetchone() is None:
            raise RegistryConflict("unknown_venue")
        revision = current_revision + 1
        conn.execute("INSERT INTO venue_settings (key, value, revision) VALUES ('active_venue', ?, ?) "
                     "ON CONFLICT(key) DO UPDATE SET value = excluded.value, revision = excluded.revision",
                     (venue_id, revision))
        return revision

    def set_active(self, venue_id: str, expected_revision: Optional[int]) -> Dict[str, Any]:
        with self._transaction() as conn:
            revision = self._set_active(conn, venue_id, expected_revision)
        return {"venue_id": venue_id, "revision": revision}

    # --- drafts ---------------------------------------------------------------------------------------------

    def create_draft(self, draft_id: str, status: str, payload: Dict[str, Any]) -> int:
        now = _now()
        with self._transaction() as conn:
            conn.execute("INSERT INTO venue_drafts VALUES (?, 1, ?, ?, ?, ?)",
                         (draft_id, status, json.dumps(payload, sort_keys=True), now, now))
        return 1

    def draft(self, draft_id: str) -> Optional[Dict[str, Any]]:
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM venue_drafts WHERE draft_id = ?", (draft_id,)).fetchone()
        if row is None:
            return None
        return {"draft_id": row["draft_id"], "revision": row["revision"], "status": row["status"],
                "created_at": row["created_at_iso"], "updated_at": row["updated_at_iso"],
                **json.loads(row["payload_json"])}

    def update_draft(self, draft_id: str, expected_revision: int, status: str, payload: Dict[str, Any]) -> int:
        with self._transaction() as conn:
            return self._update_draft(conn, draft_id, expected_revision, status, payload)

    def _update_draft(self, conn: sqlite3.Connection, draft_id: str, expected_revision: int, status: str,
                      payload: Dict[str, Any]) -> int:
        row = conn.execute("SELECT revision, status FROM venue_drafts WHERE draft_id = ?", (draft_id,)).fetchone()
        if row is None:
            raise RegistryConflict("unknown_draft")
        if row["revision"] != expected_revision:
            raise RegistryConflict("stale_draft_revision")
        if row["status"] in ("accepted", "discarded"):
            raise RegistryConflict("draft_closed")
        revision = expected_revision + 1
        conn.execute("UPDATE venue_drafts SET revision = ?, status = ?, payload_json = ?, updated_at_iso = ? "
                     "WHERE draft_id = ?", (revision, status, json.dumps(payload, sort_keys=True), _now(), draft_id))
        return revision

    def accept_draft(self, draft_id: str, expected_revision: int, venue: VenueV2, record: Dict[str, Any],
                     payload: Dict[str, Any], make_active: bool = True) -> Dict[str, Any]:
        """Atomically: close the draft at the expected revision, store the venue and (by default) activate it."""
        with self._transaction() as conn:
            row = conn.execute("SELECT status FROM venue_drafts WHERE draft_id = ?", (draft_id,)).fetchone()
            if row is not None and row["status"] != "ready":
                raise RegistryConflict("draft_not_ready")
            draft_revision = self._update_draft(conn, draft_id, expected_revision, "accepted", payload)
            venue_revision = self._save_venue(conn, venue, record)
            active_revision = self._set_active(conn, venue.venue_id, None) if make_active else None
        return {"venue_id": venue.venue_id, "venue_revision": venue_revision, "draft_revision": draft_revision,
                "active_revision": active_revision}


_registry: Optional[VenueRegistry] = None
_registry_lock = threading.Lock()


def venue_registry() -> VenueRegistry:
    """Created on first use, so importing the app never opens the database."""
    global _registry
    with _registry_lock:
        if _registry is None:
            _registry = VenueRegistry()
        return _registry


def set_venue_registry(registry: Optional[VenueRegistry]) -> None:
    """Tests install an isolated registry; None drops the cached one."""
    global _registry
    with _registry_lock:
        _registry = registry
