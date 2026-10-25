"""Read-only review route: zone watch plus verification for the accepted run.

Mounted by the application entrypoint. It never mutates scenario state, calls a
provider or reaches the hardware bridge; its only write is the local escalation log.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.app.contracts import InvestigationResult, RunContext
from .basis import ReviewUnavailable, snapshot_basis
from .escalations import EscalationLog
from .verification import build_verification
from .watch import DELIVERY_NOTICE, run_zone_watch


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_context: RunContext
    investigation_id: Optional[str] = Field(default=None, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")


def build_review_router(state_manager: Any, hardware_mode: Callable[[], str],
                        escalation_log: Optional[EscalationLog] = None) -> APIRouter:
    router = APIRouter()
    log = escalation_log or EscalationLog(state_manager.store.db_path)

    @router.post("/api/scenarios/{scenario_id}/review")
    def review_accepted_run(scenario_id: str, payload: ReviewRequest) -> Dict[str, Any]:
        if scenario_id != "facility-demo":
            raise HTTPException(404, "Unknown scenario")
        basis = snapshot_basis(state_manager, hardware_mode())
        if not basis.context.is_current(payload.expected_context):
            raise HTTPException(409, "Stale full context; refresh and review again")
        investigation = None
        if payload.investigation_id:
            raw = state_manager.store.get_investigation(payload.investigation_id)
            if not raw:
                raise HTTPException(404, "Unknown investigation")
            try:
                investigation = InvestigationResult.model_validate(raw)
            except ValidationError:
                raise HTTPException(404, "Unknown investigation") from None
        try:
            watch = run_zone_watch(basis)
            verification = build_verification(basis, investigation)
        except ReviewUnavailable as error:
            raise HTTPException(409, f"No reviewable checked run: {error}") from None
        if not state_manager.get_current_context().is_current(basis.context):
            raise HTTPException(409, "Scenario changed during review. Review again")
        now = datetime.now(timezone.utc).isoformat()
        record = log.record(watch, now) if watch.escalation == "escalated" else None
        return {
            "provenance": "local_review", "generated_at_iso": now,
            "base_context": basis.context.model_dump(mode="json"),
            "run_id": watch.run_id, "candidate_hash": watch.candidate_hash,
            "hardware_mode": basis.hardware_mode,
            "watch": watch.model_dump(mode="json"),
            "verification": verification.model_dump(mode="json"),
            "escalation_record": record.model_dump(mode="json") if record else None,
            "notice": DELIVERY_NOTICE,
        }

    return router
