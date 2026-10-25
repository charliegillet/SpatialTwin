"""
SQLite-backed Event and Snapshot Store for SpatialTwin
Configured with WAL mode for fast concurrent reads and safe serialized writes.
"""

from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional


# Anchored to the repository so the database does not depend on the process's working directory.
REPO_ROOT = Path(__file__).resolve().parents[3]


class ProposalAlreadyReviewed(ValueError):
    """The grounding proposal is missing or was already used by another command."""


class SQLiteStore:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            runtime_dir = REPO_ROOT / "runtime"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            db_path = str(runtime_dir / "spatialtwin.sqlite3")
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
            # FULL: approval and idempotency records must survive power loss, not just a process crash.
            conn.execute("PRAGMA synchronous = FULL;")
            conn.row_factory = sqlite3.Row
            with conn:
                yield conn
        finally:
            conn.close()

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

                CREATE TABLE IF NOT EXISTS grounding_results (
                    proposal_id TEXT PRIMARY KEY,
                    capture_id TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    created_at_iso TEXT NOT NULL,
                    reviewed_command_id TEXT
                );

                CREATE TABLE IF NOT EXISTS ai_evaluations (
                    request_id TEXT PRIMARY KEY,
                    context_hash TEXT NOT NULL,
                    alternative_id TEXT NOT NULL,
                    envelope_json TEXT NOT NULL
                );
            """)

    def has_event_key(self, idempotency_key: str) -> bool:
        """Read-only check so a physical approval can be recorded only after the device acknowledges it."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM events WHERE idempotency_key = ? LIMIT 1", (idempotency_key,)
            ).fetchone()
        return row is not None

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
                if event_type == "APPLY_BLOCKAGE" and payload.get("proposal_id"):
                    cursor = conn.execute(
                        "UPDATE grounding_results SET reviewed_command_id = ? WHERE proposal_id = ? AND reviewed_command_id IS NULL",
                        (idempotency_key, payload["proposal_id"]),
                    )
                    if cursor.rowcount != 1:
                        raise ProposalAlreadyReviewed("Proposal is missing or already reviewed")
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
                INSERT OR IGNORE INTO investigations (investigation_id, status, result_json, created_at_iso)
                VALUES (?, ?, ?, ?)
                """,
                (investigation_id, status, result_json, created_at_iso),
            )

    def get_investigation(self, investigation_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT result_json FROM investigations WHERE investigation_id = ?", (investigation_id,)).fetchone()
            return json.loads(row["result_json"]) if row else None

    def save_capture(self, capture: Dict[str, Any], created_at_iso: str) -> bool:
        """Retain original image and capture-time metadata; never replace an ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO observations VALUES (?, ?, ?, ?, ?)",
                (capture["capture_id"], capture["source_kind"], capture["source_geometry_revision"],
                 json.dumps(capture, sort_keys=True), created_at_iso),
            )
            return cursor.rowcount == 1

    def save_grounding_result(self, proposal_id: str, capture_id: str, result: Dict[str, Any], created_at_iso: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO grounding_results (proposal_id, capture_id, result_json, created_at_iso) VALUES (?, ?, ?, ?)",
                (proposal_id, capture_id, json.dumps(result), created_at_iso),
            )

    def get_grounding_result(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM grounding_results WHERE proposal_id = ?", (proposal_id,)).fetchone()
            if row:
                return {"result": json.loads(row["result_json"]), "reviewed_command_id": row["reviewed_command_id"],
                        "capture_id": row["capture_id"], "created_at_iso": row["created_at_iso"]}
        return None

    def get_capture(self, capture_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT metadata_json FROM observations WHERE capture_id = ?", (capture_id,)).fetchone()
            return json.loads(row["metadata_json"]) if row else None

    def get_evaluation(self, request_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM ai_evaluations WHERE request_id = ?", (request_id,)).fetchone()
            return dict(row) if row else None

    def save_evaluation(self, request_id: str, context_hash: str, alternative_id: str, envelope_json: str) -> None:
        with self._get_connection() as conn:
            conn.execute("INSERT INTO ai_evaluations VALUES (?, ?, ?, ?)",
                         (request_id, context_hash, alternative_id, envelope_json))
