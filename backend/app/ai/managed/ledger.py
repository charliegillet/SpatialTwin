"""Durable managed-run and tool claims; no credentials or raw provider errors."""
from __future__ import annotations
import json
import sqlite3
import threading
from typing import Any, Callable


class LedgerConflict(Exception):
    """Carries only an application-defined diagnostic code."""


class ManagedLedger:
    def __init__(self, path: str):
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(path, timeout=0.1, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        with self._connection:
            self._connection.executescript("""
                CREATE TABLE IF NOT EXISTS managed_runs_v1 (
                    investigation_id TEXT PRIMARY KEY, context_json TEXT NOT NULL,
                    mode TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'running',
                    interaction_id TEXT, environment_id TEXT, provider_model TEXT, provider_status TEXT,
                    usage_json TEXT NOT NULL DEFAULT '{}', result_json TEXT
                );
                CREATE TABLE IF NOT EXISTS managed_calls_v1 (
                    investigation_id TEXT NOT NULL, call_id TEXT NOT NULL,
                    function_name TEXT NOT NULL, arguments_json TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'requested', entry_json TEXT,
                    PRIMARY KEY (investigation_id, call_id)
                );
                CREATE TABLE IF NOT EXISTS managed_events_v1 (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    investigation_id TEXT NOT NULL, elapsed_ms REAL NOT NULL,
                    phase TEXT NOT NULL, data_json TEXT NOT NULL
                );
            """)
            if "provider_status" not in {row[1] for row in self._connection.execute("PRAGMA table_info(managed_runs_v1)")}:
                self._connection.execute("ALTER TABLE managed_runs_v1 ADD COLUMN provider_status TEXT")

    @staticmethod
    def encode(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)

    def begin(self, investigation_id: str, context: dict, mode: str) -> tuple[bool, dict]:
        encoded = self.encode(context)
        with self._lock, self._connection:
            return self._begin_row(investigation_id, encoded, mode)

    def _begin_row(self, investigation_id: str, encoded: str, mode: str) -> tuple[bool, dict]:
        inserted = self._connection.execute(
            "INSERT OR IGNORE INTO managed_runs_v1 (investigation_id, context_json, mode) VALUES (?, ?, ?)",
            (investigation_id, encoded, mode),
        ).rowcount == 1
        row = dict(self._connection.execute(
            "SELECT * FROM managed_runs_v1 WHERE investigation_id=?", (investigation_id,)
        ).fetchone())
        if row["context_json"] != encoded or row["mode"] != mode:
            raise LedgerConflict("investigation_identity_conflict")
        return inserted, row

    def begin_nowait(self, investigation_id: str, context: dict, mode: str) -> tuple[bool, dict]:
        """Claim ownership before the caller's first await, or fail closed.

        A threaded begin could insert a running row after its await was already
        cancelled, before the caller learned it was the owner. This metadata
        transaction has no worker that can outlive that ownership decision.
        """
        if not self._lock.acquire(blocking=False):
            raise LedgerConflict("investigation_storage_busy")
        try:
            self._connection.execute("PRAGMA busy_timeout=0")
            try:
                with self._connection:
                    self._connection.execute("BEGIN IMMEDIATE")
                    return self._begin_row(investigation_id, self.encode(context), mode)
            finally:
                self._connection.execute("PRAGMA busy_timeout=100")
        finally:
            self._lock.release()

    def progress(self, investigation_id: str, interaction_id: str | None,
                 environment_id: str | None, model: str | None, status: str, usage: dict) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE managed_runs_v1 SET interaction_id=?, environment_id=?, provider_model=?, provider_status=?, usage_json=? WHERE investigation_id=?",
                (interaction_id, environment_id, model, status, self.encode(usage), investigation_id),
            )

    def finish(self, investigation_id: str, result_json: str) -> None:
        """Stage an owner's result; a late worker cannot make it public.

        Only ``publish`` performs the terminal CAS.  A cancelled await does not
        stop its worker thread, so this write must never set ``finished``.
        """
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE managed_runs_v1 SET state='finalizing', result_json=? WHERE investigation_id=? AND state='running'",
                (result_json, investigation_id),
            )

    def publish(self, investigation_id: str, result_json: str, *,
                validate: Callable[[], str] | None = None) -> str:
        """Make one terminal decision without waiting for another worker/DB.

        Called without an intervening await after the adapter's locked context,
        deadline and cancellation checks.  Once finished, neither late staging
        nor another terminal decision may overwrite the canonical owner result.
        """
        if not self._lock.acquire(blocking=False):
            raise LedgerConflict("result_persistence_busy")
        try:
            # Unlike background ledger work, this small publication transaction
            # runs at the caller's cancellation boundary. Never wait for SQLite.
            self._connection.execute("PRAGMA busy_timeout=0")
            try:
                with self._connection:
                    self._connection.execute("BEGIN IMMEDIATE")
                    row = self._connection.execute(
                        "SELECT state, result_json FROM managed_runs_v1 WHERE investigation_id=?",
                        (investigation_id,),
                    ).fetchone()
                    if not row:
                        raise LedgerConflict("investigation_owner_missing")
                    if row["state"] == "finished":
                        return row["result_json"]
                    if validate is not None:
                        result_json = validate()
                    updated = self._connection.execute(
                        "UPDATE managed_runs_v1 SET state='finished', result_json=? "
                        "WHERE investigation_id=? AND state IN ('running', 'finalizing')",
                        (result_json, investigation_id),
                    ).rowcount
                    if updated != 1:
                        raise LedgerConflict("result_persistence_conflict")
                return result_json
            finally:
                self._connection.execute("PRAGMA busy_timeout=100")
        finally:
            self._lock.release()

    def result(self, investigation_id: str) -> str | None:
        """Read only the canonical owner result after its durable completion."""
        with self._lock:
            row = self._connection.execute(
                "SELECT result_json FROM managed_runs_v1 WHERE investigation_id=? AND state='finished'",
                (investigation_id,),
            ).fetchone()
            return row["result_json"] if row else None

    def claim(self, investigation_id: str, call_id: str, function_name: str,
              arguments: dict, max_calls: int) -> dict | None:
        """Claim a new call or replay a finished one; ``max_calls`` caps each tool name."""
        encoded = self.encode(arguments)
        with self._lock, self._connection:
            self._connection.execute("BEGIN IMMEDIATE")
            row = self._connection.execute(
                "SELECT * FROM managed_calls_v1 WHERE investigation_id=? AND call_id=?",
                (investigation_id, call_id),
            ).fetchone()
            if row:
                if row["function_name"] != function_name or row["arguments_json"] != encoded:
                    raise LedgerConflict("tool_call_identity_conflict")
                if row["state"] != "finished":
                    raise LedgerConflict("tool_execution_uncertain")
                return json.loads(row["entry_json"])
            count = self._connection.execute(
                "SELECT count(*) FROM managed_calls_v1 WHERE investigation_id=? AND function_name=?",
                (investigation_id, function_name)
            ).fetchone()[0]
            if count >= max_calls:
                raise LedgerConflict("tool_call_limit")
            self._connection.execute(
                "INSERT INTO managed_calls_v1 (investigation_id, call_id, function_name, arguments_json) VALUES (?, ?, ?, ?)",
                (investigation_id, call_id, function_name, encoded),
            )
            return None

    def finish_call(self, investigation_id: str, call_id: str, entry: dict) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "UPDATE managed_calls_v1 SET state='finished', entry_json=? WHERE investigation_id=? AND call_id=?",
                (self.encode(entry), investigation_id, call_id),
            )

    def calls(self, investigation_id: str) -> list[dict]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM managed_calls_v1 WHERE investigation_id=? ORDER BY rowid", (investigation_id,)
            ).fetchall()
            return [json.loads(row["entry_json"]) if row["entry_json"] else {
                "call_id": row["call_id"], "function_name": row["function_name"],
                "arguments": json.loads(row["arguments_json"]), "status": "requested",
                "result": None, "error": "tool_execution_uncertain", "execution_time_ms": 0.0,
            } for row in rows]

    def event(self, investigation_id: str, elapsed_ms: float, phase: str, data: dict) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO managed_events_v1 (investigation_id, elapsed_ms, phase, data_json) VALUES (?, ?, ?, ?)",
                (investigation_id, elapsed_ms, phase, self.encode(data)),
            )

    def events(self, investigation_id: str, limit: int = 64) -> list[dict]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT elapsed_ms, phase, data_json FROM managed_events_v1 WHERE investigation_id=? ORDER BY event_id DESC LIMIT ?",
                (investigation_id, max(1, min(64, limit))),
            ).fetchall()
            return [{"elapsed_ms": row["elapsed_ms"], "phase": row["phase"], **json.loads(row["data_json"])} for row in reversed(rows)]

    def close(self) -> None:
        with self._lock:
            self._connection.close()
