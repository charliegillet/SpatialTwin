"""
SQLite-backed Event and Snapshot Store for SpatialTwin
Configured with WAL mode for fast concurrent reads and safe serialized writes.
"""

from __future__ import annotations
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional


class SQLiteStore:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            runtime_dir = Path("runtime")
            runtime_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(runtime_dir / "spatialtwin.sqlite3")
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS scenarios (
                    scenario_id TEXT PRIMARY KEY,
                    geometry_revision TEXT NOT NULL,
                    scenario_revision INTEGER NOT NULL,
                    physical_revision INTEGER NOT NULL,
                    parameters_revision TEXT NOT NULL,
                    solver_version TEXT NOT NULL,
                    blocked_targets_json TEXT NOT NULL,
                    updated_at_iso TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scenario_id TEXT NOT NULL,
                    scenario_revision INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    idempotency_key TEXT UNIQUE,
                    payload_json TEXT NOT NULL,
                    created_at_iso TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    candidate_hash TEXT NOT NULL,
                    scenario_revision INTEGER NOT NULL,
                    physical_revision INTEGER NOT NULL,
                    alternative_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    envelope_json TEXT NOT NULL,
                    created_at_iso TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS observations (
                    capture_id TEXT PRIMARY KEY,
                    source_kind TEXT NOT NULL,
                    source_geometry_revision TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at_iso TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS investigations (
                    investigation_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at_iso TEXT NOT NULL
                );
            """)

    def save_event(
        self,
        scenario_id: str,
        scenario_revision: int,
        event_type: str,
        payload: Dict[str, Any],
        idempotency_key: Optional[str] = None,
        created_at_iso: str = "",
    ) -> bool:
        """
        Appends an event. Returns False if duplicate idempotency_key was rejected.
        """
        with self._get_connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO events (scenario_id, scenario_revision, event_type, idempotency_key, payload_json, created_at_iso)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        scenario_id,
                        scenario_revision,
                        event_type,
                        idempotency_key,
                        json.dumps(payload),
                        created_at_iso,
                    ),
                )
                return True
            except sqlite3.IntegrityError:
                # Duplicate idempotency key
                return False

    def save_run(
        self,
        run_id: str,
        candidate_hash: str,
        scenario_revision: int,
        physical_revision: int,
        alternative_id: str,
        status: str,
        envelope_json: str,
        created_at_iso: str,
    ) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO runs (run_id, candidate_hash, scenario_revision, physical_revision, alternative_id, status, envelope_json, created_at_iso)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    candidate_hash,
                    scenario_revision,
                    physical_revision,
                    alternative_id,
                    status,
                    envelope_json,
                    created_at_iso,
                ),
            )

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT envelope_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if row:
                return json.loads(row["envelope_json"])
            return None

    def save_investigation(self, investigation_id: str, status: str, result_json: str, created_at_iso: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO investigations (investigation_id, status, result_json, created_at_iso)
                VALUES (?, ?, ?, ?)
                """,
                (investigation_id, status, result_json, created_at_iso),
            )
