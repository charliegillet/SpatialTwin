"""Durable local escalation records. Nothing here sends or dispatches anything."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import closing
from typing import List, Literal

from pydantic import BaseModel, ConfigDict

from .watch import DELIVERY_NOTICE, WatchReport


class EscalationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_id: str
    created_at_iso: str
    context_hash: str
    run_id: str
    escalation: Literal["escalated"] = "escalated"
    reasons: List[str]
    next_step: str
    delivery: Literal["local_record_only"] = "local_record_only"
    notice: str = DELIVERY_NOTICE


class EscalationLog:
    def __init__(self, path: str):
        self._path = path
        self._lock = threading.Lock()
        with closing(self._connect()) as connection, connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS review_escalations_v1 (
                    record_id TEXT PRIMARY KEY, context_hash TEXT NOT NULL,
                    run_id TEXT NOT NULL, created_at_iso TEXT NOT NULL, record_json TEXT NOT NULL
                )""")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path, timeout=1.0)
        connection.row_factory = sqlite3.Row
        return connection

    def record(self, watch: WatchReport, created_at_iso: str) -> EscalationRecord:
        """One record per escalated context and run; repeated reviews return the first."""
        if watch.escalation != "escalated":
            raise ValueError("only escalated watches create records")
        digest = hashlib.sha256(f"{watch.base_context.context_hash}:{watch.run_id}".encode("utf-8")).hexdigest()
        candidate = EscalationRecord(record_id=f"esc-{digest[:20]}", created_at_iso=created_at_iso,
                                     context_hash=watch.base_context.context_hash, run_id=watch.run_id,
                                     reasons=watch.escalation_reasons, next_step=watch.next_step)
        with self._lock, closing(self._connect()) as connection, connection:
            connection.execute(
                "INSERT OR IGNORE INTO review_escalations_v1 VALUES (?, ?, ?, ?, ?)",
                (candidate.record_id, candidate.context_hash, candidate.run_id, created_at_iso,
                 candidate.model_dump_json()))
            row = connection.execute("SELECT record_json FROM review_escalations_v1 WHERE record_id=?",
                                     (candidate.record_id,)).fetchone()
        return EscalationRecord.model_validate(json.loads(row["record_json"]))

    def records(self, limit: int = 32) -> List[EscalationRecord]:
        with self._lock, closing(self._connect()) as connection, connection:
            rows = connection.execute("SELECT record_json FROM review_escalations_v1 ORDER BY rowid DESC LIMIT ?",
                                      (max(1, min(64, limit)),)).fetchall()
        return [EscalationRecord.model_validate(json.loads(row["record_json"])) for row in rows]
