"""
SpatialTwin Backend Application
FastAPI Server providing authoritative state, numerical flow planning,
Argon vision grounding, Antigravity managed agent investigation,
hardware serial bridge, and live SSE event streams.
"""

from __future__ import annotations
import asyncio
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

from backend.app.ai.grounding.adapter import GroundingAdapter
from backend.app.ai.managed.adapter import ManagedAgentAdapter
from backend.app.contracts import (
    AlternativeId,
    ApplyBlockageCommand,
    Capture,
    EntityType,
    GateTarget,
    OperatorPhysicalApprovalCommand,
    ResetScenarioCommand,
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting SpatialTwin Backend Server...")
    await hardware_bridge.start()
    yield
    logger.info("Shutting down SpatialTwin Backend Server...")
    await hardware_bridge.stop()


app = FastAPI(
    title="SpatialTwin API",
    description="Deterministic tabletop evacuation twin with Gemini 4 Argon & Managed Agents",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "live_api_configured": grounding_adapter.is_live_configured(),
        "hardware_mode": "simulator" if hardware_bridge.is_simulator else "physical_serial",
        "serial_port": hardware_bridge.port if not hardware_bridge.is_simulator else "MOCK_SIMULATOR",
        "current_context": state_manager.get_current_context().model_dump(),
        "physical_gate_state": state_manager.physical_gate_state.value,
    }


@app.get("/api/scenarios/{scenario_id}")
def get_scenario(scenario_id: str) -> Dict[str, Any]:
    return state_manager.get_current_snapshot()


@app.post("/api/scenarios/{scenario_id}/commands")
async def handle_command(scenario_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    cmd_type = payload.get("type", "APPLY_BLOCKAGE")

    if cmd_type == "APPLY_BLOCKAGE":
        cmd = ApplyBlockageCommand(
            scenario_id=scenario_id,
            expected_scenario_revision=payload.get("expected_scenario_revision", 1),
            idempotency_key=payload.get("idempotency_key", f"cmd-{os.urandom(4).hex()}"),
            target_type=EntityType(payload.get("target_type", "portal")),
            target_id=TargetId(payload.get("target_id", "P2")),
            source=payload.get("source", "manual_override"),
        )
        success, err, envelope = state_manager.apply_blockage(cmd)
        if not success:
            raise HTTPException(status_code=400, detail=err)
        await hardware_bridge.update_display()
        return {
            "status": "applied",
            "snapshot": state_manager.get_current_snapshot(),
            "plan": envelope.model_dump() if envelope else None,
        }

    elif cmd_type == "RESET_SCENARIO":
        cmd = ResetScenarioCommand(
            scenario_id=scenario_id,
            expected_scenario_revision=payload.get("expected_scenario_revision", 1),
            idempotency_key=payload.get("idempotency_key", f"reset-{os.urandom(4).hex()}"),
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
async def interpret_grounding(scenario_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    ctx = state_manager.get_current_context()
    thinking_level = payload.get("thinking_level", "low")
    capture = Capture(
        capture_id=payload.get("capture_id", f"cap-{os.urandom(4).hex()}"),
        timestamp_iso=state_manager._now_iso(),
        source_kind=payload.get("source_kind", "tabletop_camera"),
        source_geometry_revision=ctx.geometry_revision,
        expected_scenario_revision=ctx.scenario_revision,
        expected_physical_revision=ctx.physical_revision,
        image_base64=payload.get("image_base64"),
        notes=payload.get("target_override"),
    )

    force_target = payload.get("force_target")
    proposal, provenance = await grounding_adapter.interpret_capture(
        capture=capture,
        context=ctx,
        force_target=force_target,
        thinking_level=thinking_level,
    )

    return {
        "proposal": proposal.model_dump(),
        "provenance": provenance,
        "is_live_api": provenance == "live",
        "thinking_level": thinking_level,
    }


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
async def run_investigation(scenario_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    ctx = state_manager.get_current_context()
    inv_id = payload.get("investigation_id")
    result = await managed_agent_adapter.investigate_scenario(
        context=ctx,
        investigation_id=inv_id,
        deadline_seconds=payload.get("deadline_seconds", 30.0),
    )

    state_manager.store.save_investigation(
        investigation_id=result.investigation_id,
        status=result.status.value,
        result_json=result.model_dump_json(),
        created_at_iso=state_manager._now_iso(),
    )

    return {
        "investigation": result.model_dump(),
        "is_live_configured": managed_agent_adapter.is_live_configured(),
    }


@app.post("/api/hardware/operator-approve")
async def operator_approve_gate(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Operator physical approval flow:
    Requires human confirmation before motor movement begins.
    """
    candidate = payload.get("candidate_alternative", "OPEN_P3")
    target_enum = GateTarget.OPEN if candidate == "OPEN_P3" else GateTarget.CLOSED

    # Check that context matches
    ctx = state_manager.get_current_context()
    expected_scen = payload.get("expected_scenario_revision", ctx.scenario_revision)
    if expected_scen != ctx.scenario_revision:
        raise HTTPException(status_code=400, detail="Cannot actuate gate on stale scenario context")

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
