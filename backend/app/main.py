"""
SpatialTwin Backend Application
FastAPI Server providing authoritative state, numerical flow planning,
Argon vision grounding, Antigravity managed agent investigation,
hardware serial bridge, and live SSE event streams.
"""

from __future__ import annotations
import asyncio
import base64
import binascii
import hashlib
import importlib.metadata
from uuid import uuid4
from contextlib import asynccontextmanager
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.app.ai.grounding.adapter import GroundingAdapter
from backend.app.ai.managed.adapter import ManagedAgentAdapter
from backend.app.ai.requests import CommandRequest, GateApprovalRequest, GroundingRequest, InvestigationRequest, InvestigationCancellationRequest
from backend.app.contracts import (
    AlternativeId,
    ApplyBlockageCommand,
    Capture,
    ClearBlockageCommand,
    EntityType,
    GateTarget,
    InvestigationResult,
    InvestigationStatus,
    OperatorPhysicalApprovalCommand,
    ResetScenarioCommand,
    RunContext,
    TargetId,
)
from backend.app.hardware.bridge import HardwareBridge
from backend.app.state.manager import StateManager
from backend.app.state.service import ScenarioService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("spatialtwin.app")

# Singletons
state_manager = StateManager()
scenario_service = ScenarioService(state_manager)
hardware_bridge = HardwareBridge(state_manager)
grounding_adapter = GroundingAdapter()
managed_agent_adapter = ManagedAgentAdapter(scenario_service)
active_investigations: Dict[str, tuple[asyncio.Task, RunContext]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting SpatialTwin Backend Server...")
    try:
        await hardware_bridge.start()
        yield
    finally:
        logger.info("Shutting down SpatialTwin Backend Server...")
        running = [task for task, _ in active_investigations.values() if not task.done()]
        for task in running:
            if not task.cancelling():
                task.cancel()
        if running:
            await asyncio.gather(*running, return_exceptions=True)
        try:
            await hardware_bridge.stop()
        finally:
            try:
                await grounding_adapter.aclose()
            finally:
                await managed_agent_adapter.aclose()


app = FastAPI(
    title="SpatialTwin API",
    description="Deterministic tabletop evacuation twin with Gemini 4 Argon & Managed Agents",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("SPATIALTWIN_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Do not echo image bytes or arbitrary request values.
    return JSONResponse(status_code=422, content={"detail": "Invalid request", "fields": [list(e["loc"]) for e in exc.errors()]})


def fixtures_enabled() -> bool:
    return os.environ.get("SPATIALTWIN_MODE", "demo") != "production"


def require_context(value: Any) -> RunContext:
    try:
        ctx = RunContext.model_validate(value)
    except ValidationError:
        raise HTTPException(422, "A valid full expected_context is required")
    if not state_manager.get_current_context().is_current(ctx):
        raise HTTPException(409, "Stale full context; refresh and review again")
    return ctx


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "live_api_configured": grounding_adapter.is_live_configured(),
        "hardware_mode": "simulator" if hardware_bridge.is_simulator else "physical_serial",
        "serial_port": hardware_bridge.port if not hardware_bridge.is_simulator else "MOCK_SIMULATOR",
        "current_context": state_manager.get_current_context().model_dump(),
        "physical_gate_state": state_manager.physical_gate_state.value,
        "ai": {
            "direct": {"configured": grounding_adapter.is_live_configured(), "verified": False},
            "managed": {"configured": managed_agent_adapter.is_live_configured(), "verified": False},
            "fixtures_enabled": fixtures_enabled(),
            "sdk_version": importlib.metadata.version("google-genai"),
        },
    }


@app.get("/api/scenarios/{scenario_id}")
def get_scenario(scenario_id: str) -> Dict[str, Any]:
    return state_manager.get_current_snapshot()


@app.post("/api/scenarios/{scenario_id}/commands")
async def handle_command(scenario_id: str, payload: CommandRequest) -> Dict[str, Any]:
    payload = payload.model_dump(mode="json")
    require_context(payload.get("expected_context"))
    cmd_type = payload.get("type", "APPLY_BLOCKAGE")

    if cmd_type == "APPLY_BLOCKAGE":
        cmd = ApplyBlockageCommand(
            scenario_id=scenario_id,
            expected_scenario_revision=payload.get("expected_scenario_revision", 1),
            idempotency_key=payload.get("idempotency_key", f"cmd-{os.urandom(4).hex()}"),
            target_type=EntityType(payload.get("target_type", "portal")),
            target_id=TargetId(payload.get("target_id", "P2")),
            source=payload.get("source", "manual_override"),
            expected_context=RunContext.model_validate(payload["expected_context"]),
            proposal_id=payload.get("proposal_id"),
            reviewed=payload.get("reviewed") is True,
        )
        if cmd.source == "grounding_proposal" and (not cmd.proposal_id or not cmd.reviewed):
            raise HTTPException(422, "Saved proposal_id and explicit review are required")
        if cmd.proposal_id:
            record = state_manager.store.get_grounding_result(cmd.proposal_id)
            if record and record["result"].get("provenance") == "fixture" and not fixtures_enabled():
                raise HTTPException(403, "Fixtures are disabled in production mode")
        success, err, envelope = state_manager.apply_blockage(cmd)
        if not success:
            raise HTTPException(status_code=400, detail=err)
        await hardware_bridge.update_display()
        return {
            "status": "applied",
            "snapshot": state_manager.get_current_snapshot(),
            "plan": envelope.model_dump() if envelope else None,
        }

    elif cmd_type == "CLEAR_BLOCKAGE":
        cmd = ClearBlockageCommand(
            scenario_id=scenario_id,
            expected_scenario_revision=payload.get("expected_scenario_revision", 1),
            idempotency_key=payload.get("idempotency_key", f"clear-{os.urandom(4).hex()}"),
            target_type=EntityType(payload.get("target_type", "portal")),
            target_id=TargetId(payload.get("target_id", "P2")),
            expected_context=RunContext.model_validate(payload["expected_context"]),
        )
        success, err, envelope = state_manager.clear_blockage(cmd)
        if not success:
            raise HTTPException(status_code=400, detail=err)
        await hardware_bridge.update_display()
        return {
            "status": "cleared",
            "snapshot": state_manager.get_current_snapshot(),
            "plan": envelope.model_dump() if envelope else None,
        }

    elif cmd_type == "RESET_SCENARIO":
        cmd = ResetScenarioCommand(
            scenario_id=scenario_id,
            expected_scenario_revision=payload.get("expected_scenario_revision", 1),
            idempotency_key=payload.get("idempotency_key", f"reset-{os.urandom(4).hex()}"),
            expected_context=RunContext.model_validate(payload["expected_context"]),
        )
        success, err, envelope = state_manager.reset_scenario(cmd)
        if not success:
            raise HTTPException(status_code=400, detail=err)
        await hardware_bridge.update_display()
        return {
            "status": "reset",
            "snapshot": state_manager.get_current_snapshot(),
            "plan": envelope.model_dump() if envelope else None,
        }

    else:
        raise HTTPException(status_code=400, detail=f"Unknown command type: {cmd_type}")


@app.post("/api/scenarios/{scenario_id}/grounding")
async def interpret_grounding(scenario_id: str, payload: GroundingRequest) -> Dict[str, Any]:
    ctx = require_context(payload.source_context)
    if payload.mode == "fixture":
        if not fixtures_enabled():
            raise HTTPException(403, "Fixtures are disabled in production mode")
        if payload.fixture_target is None or payload.source_kind != "fixture" or payload.image_base64:
            raise HTTPException(422, "Choose an explicit fixture target without camera data")
    elif payload.fixture_target is not None or payload.source_kind == "fixture":
        raise HTTPException(422, "Live requests cannot contain fixture controls")
    image_digest = None
    if payload.image_base64:
        try:
            raw = base64.b64decode(payload.image_base64, validate=True)
        except (ValueError, binascii.Error):
            raise HTTPException(422, "Invalid capture encoding")
        image_digest = hashlib.sha256(raw).hexdigest()
        if payload.image_sha256 and image_digest != payload.image_sha256:
            raise HTTPException(422, "Capture digest mismatch")
    capture = Capture(
        capture_id=payload.capture_id,
        timestamp_iso=payload.timestamp_iso,
        source_kind=payload.source_kind,
        source_geometry_revision=ctx.geometry_revision,
        expected_scenario_revision=ctx.scenario_revision,
        expected_physical_revision=ctx.physical_revision,
        source_context=ctx,
        dimensions=payload.dimensions,
        image_sha256=image_digest,
        image_base64=payload.image_base64,
    )
    if not state_manager.store.save_capture(capture.model_dump(mode="json"), state_manager._now_iso()):
        raise HTTPException(409, "Capture ID already exists; recapture with a fresh ID")
    result = await grounding_adapter.interpret_capture(
        capture=capture,
        context=ctx,
        force_target=payload.fixture_target if payload.mode == "fixture" else None,
        thinking_level=payload.thinking_level,
        deadline_seconds=payload.deadline_seconds,
    )
    if result.proposal and not ctx.is_current(state_manager.get_current_context()):
        result.proposal = None
        result.status = "failed"
        result.errors.append("stale_context")
    result.proposal_id = f"proposal-{uuid4().hex}"
    state_manager.store.save_grounding_result(result.proposal_id, capture.capture_id, result.model_dump(mode="json"), state_manager._now_iso())
    return result.model_dump(mode="json")


@app.get("/api/scenarios/{scenario_id}/matrix")
def get_scenario_matrix(scenario_id: str) -> Dict[str, Any]:
    """
    Computes all 4 canonical benchmark scenarios side-by-side for judging comparison:
    1. Baseline (All Open)
    2. Portal P1 Blocked
    3. Portal P2 Blocked (Bottleneck rescued by OPEN_P3)
    4. Boundary B2 Blocked (No-benefit proof: OPEN_P3 +0 gain)
    """
    ctx = state_manager.get_current_context()
    planner = state_manager.planner

    # 1. Baseline
    base_env = planner.solve(ctx, AlternativeId.KEEP_CURRENT, set(), set())
    # 2. P1 Blocked
    p1_env = planner.solve(ctx, AlternativeId.KEEP_CURRENT, {"P1"}, set())
    # 3. P2 Blocked (Keep vs Open)
    p2_keep = planner.solve(ctx, AlternativeId.KEEP_CURRENT, {"P2"}, set())
    p2_open = planner.solve(ctx, AlternativeId.OPEN_P3, {"P2"}, set())
    # 4. B2 Blocked (Keep vs Open)
    b2_keep = planner.solve(ctx, AlternativeId.KEEP_CURRENT, set(), {"B2"})
    b2_open = planner.solve(ctx, AlternativeId.OPEN_P3, set(), {"B2"})

    return {
        "context": ctx.model_dump(),
        "scenarios": {
            "baseline": base_env.model_dump(),
            "p1_blocked": p1_env.model_dump(),
            "p2_blocked": {
                "keep_current": p2_keep.model_dump(),
                "open_p3": p2_open.model_dump(),
                "net_gain": p2_open.completed_crossings - p2_keep.completed_crossings,
            },
            "b2_blocked": {
                "keep_current": b2_keep.model_dump(),
                "open_p3": b2_open.model_dump(),
                "net_gain": b2_open.completed_crossings - b2_keep.completed_crossings,
            },
        },
    }


@app.post("/api/scenarios/{scenario_id}/investigate")
async def run_investigation(scenario_id: str, payload: InvestigationRequest) -> Dict[str, Any]:
    ctx = require_context(payload.expected_context)
    if payload.mode == "local" and not fixtures_enabled():
        raise HTTPException(403, "Local demo investigations are disabled in production mode")
    inv_id = payload.investigation_id
    if inv_id in active_investigations:
        raise HTTPException(409, "Investigation already running; inspect progress or cancel it")
    task = asyncio.create_task(managed_agent_adapter.investigate_scenario(
        context=ctx, investigation_id=inv_id, deadline_seconds=payload.deadline_seconds, mode=payload.mode,
    ))
    active_investigations[inv_id] = (task, ctx)
    try:
        result = await task
    finally:
        if active_investigations.get(inv_id, (None,))[0] is task:
            active_investigations.pop(inv_id, None)

    # A concurrent nonowner/conflicting request may return a transient failure.
    # Only the durable owning run may create the approval/evidence index.
    canonical = await managed_agent_adapter.get_saved_result(result.investigation_id)
    if canonical is not None and canonical.base_context.is_current(state_manager.get_current_context()):
        state_manager.store.save_investigation(
            investigation_id=canonical.investigation_id,
            status=canonical.status.value,
            result_json=canonical.model_dump_json(),
            created_at_iso=state_manager._now_iso(),
        )

    if result.status == InvestigationStatus.COMPLETED and not result.base_context.is_current(state_manager.get_current_context()):
        result = result.model_copy(update={"status": InvestigationStatus.FAILED, "recommended_alternative": None,
            "errors": [*result.errors, "stale_context"]})

    return {
        "investigation": result.model_dump(),
        "is_live_configured": managed_agent_adapter.is_live_configured(),
    }


@app.get("/api/scenarios/{scenario_id}/investigations/{investigation_id}/progress")
async def investigation_progress(scenario_id: str, investigation_id: str):
    result = await managed_agent_adapter.get_saved_result(investigation_id)
    progress = await managed_agent_adapter.get_progress(investigation_id)
    if investigation_id not in active_investigations and result is None:
        raise HTTPException(404, "Investigation not found")
    return {"investigation_id": investigation_id,
        "status": result.status.value if result else "running",
        "provider_progress": progress,
        "investigation": result.model_dump(mode="json") if result else None}


@app.post("/api/scenarios/{scenario_id}/investigations/{investigation_id}/cancel")
async def cancel_investigation(scenario_id: str, investigation_id: str, payload: InvestigationCancellationRequest):
    active = active_investigations.get(investigation_id)
    if active:
        task, original_context = active
        if not original_context.is_current(payload.expected_context):
            raise HTTPException(409, "Cancellation context does not match the investigation")
        # Give a newly scheduled owner its first turn before cancellation; this
        # lets the adapter persist a cancellation rather than dying before entry.
        await asyncio.sleep(0)
        if not task.done():
            if not task.cancelling():
                task.cancel()
            return {"status": "cancellation_requested"}
    result = await managed_agent_adapter.get_saved_result(investigation_id)
    if result is None:
        raise HTTPException(404, "Investigation not found")
    if not result.base_context.is_current(payload.expected_context):
        raise HTTPException(409, "Cancellation context does not match the investigation")
    return {"status": "already_finished", "investigation": result.model_dump(mode="json")}


@app.get("/api/scenarios/{scenario_id}/captures/{capture_id}")
def get_capture_evidence(scenario_id: str, capture_id: str):
    capture = state_manager.store.get_capture(capture_id)
    if capture is None:
        raise HTTPException(404, "Capture not found")
    return {"capture": capture}


@app.post("/api/hardware/operator-approve")
async def operator_approve_gate(payload: GateApprovalRequest) -> Dict[str, Any]:
    """
    Operator physical approval flow:
    Requires human confirmation before motor movement begins.
    """
    payload = payload.model_dump(mode="json")
    candidate = payload.get("candidate_alternative", "OPEN_P3")
    ctx = require_context(payload.get("expected_context"))
    if candidate != "OPEN_P3":
        raise HTTPException(422, "Only the reviewed OPEN_P3 candidate can use this approval endpoint")
    raw = state_manager.store.get_investigation(payload.get("investigation_id", ""))
    if not raw:
        raise HTTPException(409, "A saved current completed investigation is required")
    investigation = InvestigationResult.model_validate(raw)
    if (investigation.status.value != "completed" or investigation.errors
        or investigation.provenance not in ("live", "local")
        or not investigation.base_context.is_current(ctx)
        or investigation.recommended_alternative != AlternativeId.OPEN_P3
        or (investigation.provenance == "local" and not fixtures_enabled())):
        raise HTTPException(409, "Investigation does not authorize the current candidate")
    candidates = {item.alternative_id: item for item in investigation.candidate_envelopes}
    opened = candidates.get(AlternativeId.OPEN_P3)
    keep = candidates.get(AlternativeId.KEEP_CURRENT)
    if (not opened or not keep or not opened.is_publishable or not keep.is_publishable
        or not opened.base_context.is_current(ctx) or not keep.base_context.is_current(ctx)
        or opened.run_id != payload.get("candidate_run_id")
        or (opened.initial_population, opened.horizon_seconds, opened.time_step_seconds) !=
           (keep.initial_population, keep.horizon_seconds, keep.time_step_seconds)
        or opened.completed_crossings <= keep.completed_crossings):
        raise HTTPException(409, "Candidate must have a checked improvement under equal conditions")
    target_enum = GateTarget.OPEN

    approval_id = payload.get("idempotency_key")
    if not isinstance(approval_id, str) or not 1 <= len(approval_id) <= 128:
        raise HTTPException(422, "An approval idempotency_key is required")
    if not state_manager.store.save_event("facility-demo", ctx.scenario_revision, "PHYSICAL_APPROVAL",
        {"context": ctx.model_dump(), "investigation_id": investigation.investigation_id,
         "candidate_run_id": opened.run_id, "candidate_hash": opened.candidate_hash},
        approval_id, state_manager._now_iso()):
        raise HTTPException(409, "Approval already submitted; inspect observed state before a new request")

    # Send hardware command
    success, cmd_id = await hardware_bridge.request_gate_target(target_enum)
    if not success:
        raise HTTPException(status_code=500, detail=cmd_id)

    return {
        "status": "APPROVED_AND_COMMANDED",
        "command_id": cmd_id,
        "target": target_enum.value,
        "notice": "Movement initiated. Awaiting debounced endpoint switch confirmation.",
    }


@app.get("/api/scenarios/{scenario_id}/events")
async def sse_events(scenario_id: str):
    return StreamingResponse(
        state_manager.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> Dict[str, Any]:
    run = state_manager.store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run


# Mount built frontend if available
frontend_dist = Path("frontend/dist")
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
