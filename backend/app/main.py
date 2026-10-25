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
import hmac
import ipaddress
import re
from uuid import uuid4
from contextlib import asynccontextmanager
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import Body, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.app.ai.grounding.adapter import GroundingAdapter
from backend.app.ai.grounding.video import IMAGE_FALLBACK_ERROR, ground_video, video_enabled
from backend.app.ai.managed.model_probe import resolve_model
from backend.app.hazard.model import HazardToolError, ToolContext
from backend.app.hazard.tools import execute_hazard_tool
from backend.app.review.routes import build_review_router
from backend.app.venues.camera import build_camera_router
from backend.app.venues.routes import router as venues_router
from backend.app.venues.agent import build_door_agent_router
from backend.app.ai.managed.adapter import ManagedAgentAdapter
from backend.app.ai.requests import CommandRequest, GateApprovalRequest, GroundingRequest, InvestigationRequest, InvestigationCancellationRequest
from backend.app.contracts import (
    AlternativeId,
    ApplyBlockageCommand,
    Capture,
    ClearBlockageCommand,
    EntityType,
    GateObservedState,
    GateTarget,
    GroundingResult,
    HazardResult,
    HazardScheduleRequest,
    InvestigationResult,
    InvestigationStatus,
    OperatorPhysicalApprovalCommand,
    ResetScenarioCommand,
    RunContext,
    ScenarioLabRequest,
    TargetId,
)
from backend.app.hardware.bridge import HardwareBridge
from backend.app.state.manager import StateManager
from backend.app.state.store import ProposalAlreadyReviewed
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
# Physical approvals are serialised so one idempotency key can never send two movements.
_approval_lock = asyncio.Lock()
# Bounds concurrent provider investigations so one burst cannot exhaust the process.
_investigation_slots = asyncio.Semaphore(2)


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


API_TOKEN_ENV = "SPATIALTWIN_API_TOKEN"


def is_loopback_client(host: Optional[str]) -> bool:
    """True for 127.0.0.0/8, ::1 and IPv4-mapped loopback. Anything unparseable is not loopback."""
    try:
        address = ipaddress.ip_address(host or "")
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.is_loopback


class NetworkGuard:
    """Rejects non-loopback clients unless they present SPATIALTWIN_API_TOKEN in X-API-Token.

    Applies to every route, SSE and the static frontend. With the variable unset, remote clients are
    always rejected. The peer address is used as is: X-Forwarded-For is deliberately not trusted.
    """

    def __init__(self, inner):
        self.inner = inner

    @staticmethod
    def _token_ok(scope) -> bool:
        expected = os.environ.get(API_TOKEN_ENV, "")
        if not expected:
            return False
        presented = next((value for name, value in scope.get("headers", []) if name == b"x-api-token"), b"")
        # Digests make the comparison constant-time regardless of the presented length.
        return hmac.compare_digest(hashlib.sha256(presented).digest(), hashlib.sha256(expected.encode("utf-8")).digest())

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            client = scope.get("client")
            if not (client and is_loopback_client(client[0])) and not self._token_ok(scope):
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                else:
                    await JSONResponse(status_code=403, content={"detail": "remote_access_denied"})(scope, receive, send)
                return
        await self.inner(scope, receive, send)


app.add_middleware(NetworkGuard)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Do not echo image bytes or arbitrary request values.
    return JSONResponse(status_code=422, content={"detail": "Invalid request", "fields": [list(e["loc"]) for e in exc.errors()]})


OPERATOR_TOKEN_ENV = "SPATIALTWIN_OPERATOR_TOKEN"
OPERATORS_ENV = "SPATIALTWIN_OPERATORS"
_OPERATOR_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


def _operator_registry() -> Dict[str, str]:
    """Named operators from SPATIALTWIN_OPERATORS ("name:sha256hex,..."), plus the legacy shared token.

    Only token hashes are configured for named operators. A malformed entry fails closed rather than
    being skipped, so a typo can never silently remove the check.
    """
    registry: Dict[str, str] = {}
    for entry in filter(None, (part.strip() for part in os.environ.get(OPERATORS_ENV, "").split(","))):
        name, _, digest = entry.partition(":")
        digest = digest.strip().lower()
        if not _OPERATOR_NAME.match(name.strip()) or not _SHA256_HEX.match(digest) or name.strip() in registry:
            raise HTTPException(403, "operator_config_invalid")
        registry[name.strip()] = digest
    shared = os.environ.get(OPERATOR_TOKEN_ENV, "").strip()
    if shared:
        registry.setdefault("shared-operator", hashlib.sha256(shared.encode("utf-8")).hexdigest())
    return registry


def _authorize_physical_operator(token: Optional[str]) -> str:
    """Physical hardware requires an operator token. Returns the operator's configured name.

    Every configured hash is compared in constant time, with no early exit, so response timing does not
    reveal which operator entry matched. "shared-operator" means the legacy shared token was used.
    """
    registry = _operator_registry()
    if not registry:
        raise HTTPException(403, "operator_token_not_configured")
    presented = hashlib.sha256((token or "").encode("utf-8")).hexdigest()
    matched = None
    for name, digest in registry.items():
        if hmac.compare_digest(presented, digest) and token:
            matched = name
    if matched is None:
        raise HTTPException(403, "operator_token_rejected")
    return f"operator:{matched}"


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


app.include_router(build_review_router(
    state_manager, lambda: "simulator" if hardware_bridge.is_simulator else "physical_serial"))
app.include_router(venues_router)
app.include_router(build_camera_router(grounding_adapter, fixtures_enabled))
app.include_router(build_door_agent_router(managed_agent_adapter, _investigation_slots, fixtures_enabled))


@app.get("/api/ai/capabilities")
def ai_capabilities() -> Dict[str, Any]:
    """Receipt-gated capability flags. Reads local probe files only; no provider call."""
    resolution = resolve_model()
    return {
        "video_static": video_enabled("static"),
        "video_agentic": video_enabled("agentic"),
        "managed_model": resolution.model if resolution else None,
        "managed_model_fallback": resolution.is_fallback if resolution else False,
        "receipts_source": "runtime/probes",
    }


def _with_default_hazard_zones(event: Dict[str, Any], venue: Any) -> Dict[str, Any]:
    """A closure without explicit zones affects the zones its element connects.

    Exposure counts occupants in hazard zones, so an empty list would always report zero.
    Portals affect both endpoint zones; boundaries affect the zone they serve.
    """
    if event.get("hazard_zone_ids"):
        return event
    element = event["element_id"]
    if element in venue.portals:
        spec = venue.portals[element]
        zones = (spec.from_zone, spec.to_zone)
    elif element in venue.boundaries:
        zones = (venue.boundaries[element].from_zone,)
    else:
        zones = ()
    return {**event, "hazard_zone_ids": tuple(dict.fromkeys(zones))}


@app.post("/api/hazard/simulate")
def simulate_hazard(body: Any = Body(...)) -> Dict[str, Any]:
    """Local-only timed-closure simulation. Never echoes request values.

    element_id uses the venue graph ids accepted by hazard.model.HazardSchedule:
    portal ids (P1, P2, P3) and boundary ids (B1, B2) of the default venue graph.
    """
    invalid = HTTPException(422, detail={"code": "invalid_arguments"})
    try:
        request = HazardScheduleRequest.model_validate(body)
    except ValidationError:
        raise invalid from None
    context, blocked_portals, blocked_boundaries, p3_open = state_manager.hazard_inputs()
    envelopes = {}
    for alternative in (AlternativeId.KEEP_CURRENT, AlternativeId.OPEN_P3):
        try:
            envelopes[alternative] = scenario_service.evaluate_alternative(
                context, alternative, f"hazard-baseline-{alternative.value}-{uuid4().hex}")
        except ValueError:
            # The context changed while evaluating; the caller must retry on the new context.
            raise HTTPException(409, detail={"code": "stale_context"}) from None
        except Exception:
            logger.exception("Hazard baseline evaluation failed")
            raise HTTPException(500, detail={"code": "baseline_evaluation_failed"}) from None
    ctx = ToolContext(venue=state_manager.venue_graph, base_context=context, envelopes=envelopes,
                      blocked_portals=blocked_portals, blocked_boundaries=blocked_boundaries,
                      p3_physical_open=p3_open)
    arguments = {"alternative_id": request.alternative_id.value,
                 "events": [_with_default_hazard_zones(e.model_dump(), state_manager.venue_graph)
                            for e in request.events]}
    try:
        result = execute_hazard_tool("simulate_hazard_schedule", arguments, ctx)
        exposure = execute_hazard_tool("score_exposure", arguments, ctx)
    except HazardToolError as error:
        if error.code == "invalid_close_time":
            raise HTTPException(422, detail={"code": "invalid_close_time"}) from None
        if error.code == "invalid_arguments":
            raise invalid from None
        raise HTTPException(500, detail={"code": "evaluation_failed"}) from None
    result["modeled_exposure_people_seconds"] = exposure["modeled_exposure_people_seconds"]
    result["exposure_label"] = exposure["exposure_label"]
    try:
        return HazardResult.model_validate(result).model_dump(mode="json")
    except ValidationError:
        raise HTTPException(500, detail={"code": "evaluation_failed"}) from None


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "investigation_running": any(not task.done() for task, _ in active_investigations.values()),
        "live_api_configured": grounding_adapter.is_live_configured(),
        "hardware_mode": "simulator" if hardware_bridge.is_simulator else "physical_serial",
        # The device path is not disclosed; only whether a serial device is configured.
        "serial_port": ("MOCK_SIMULATOR" if hardware_bridge.is_simulator
                        else "SERIAL_CONNECTED" if hardware_bridge.transport_available()
                        else "SERIAL_UNAVAILABLE"),
        "current_context": state_manager.get_current_context().model_dump(),
        "physical_gate_state": state_manager.physical_gate_state.value,
        "ai": {
            "direct": {"configured": grounding_adapter.is_live_configured(), "verified": False},
            "managed": {"configured": managed_agent_adapter.is_live_configured(), "verified": False},
            "fixtures_enabled": fixtures_enabled(),
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
            record = await asyncio.to_thread(state_manager.store.get_grounding_result, cmd.proposal_id)
            if record and record["result"].get("provenance") == "fixture" and not fixtures_enabled():
                raise HTTPException(403, "Fixtures are disabled in production mode")
        try:
            success, err, envelope = await asyncio.to_thread(state_manager.apply_blockage, cmd)
        except ProposalAlreadyReviewed:
            raise HTTPException(409, "Proposal is missing or already reviewed") from None
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
        success, err, envelope = await asyncio.to_thread(state_manager.clear_blockage, cmd)
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
        success, err, envelope = await asyncio.to_thread(state_manager.reset_scenario, cmd)
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


async def _interpret_video(payload: GroundingRequest, ctx: RunContext) -> Dict[str, Any]:
    if payload.mode == "fixture" or payload.fixture_target is not None or payload.source_kind == "fixture":
        raise HTTPException(422, "Video requests cannot contain fixture controls")
    if not video_enabled(payload.video_mode):
        result = GroundingResult(status="unavailable", provenance="unavailable", errors=[IMAGE_FALLBACK_ERROR])
    else:
        try:
            clip = base64.b64decode(payload.video_base64 or payload.image_base64 or "", validate=True)
        except (ValueError, binascii.Error):
            raise HTTPException(422, "Invalid clip encoding")
        # The capture record lets a reviewed live video proposal be applied within the freshness window,
        # exactly like a still. The clip itself is not stored; its digest is.
        capture_record = {
            "capture_id": payload.capture_id, "timestamp_iso": payload.timestamp_iso,
            "source_kind": payload.source_kind, "source_geometry_revision": ctx.geometry_revision,
            "expected_scenario_revision": ctx.scenario_revision,
            "expected_physical_revision": ctx.physical_revision,
            "source_context": ctx.model_dump(mode="json"), "dimensions": list(payload.dimensions),
            "media_kind": "video", "video_mode": payload.video_mode, "video_mime": payload.video_mime,
            "video_duration_seconds": payload.video_duration_seconds,
            "video_sha256": hashlib.sha256(clip).hexdigest(),
        }
        if not await asyncio.to_thread(state_manager.store.save_capture, capture_record, state_manager._now_iso()):
            raise HTTPException(409, "Capture ID already exists; recapture with a fresh ID")
        result = await ground_video(
            clip, payload.video_mime, ctx, payload.video_mode, adapter=grounding_adapter,
            captured_at_iso=payload.timestamp_iso, duration_seconds=payload.video_duration_seconds,
            thinking_level=payload.thinking_level,
            deadline_seconds=payload.deadline_seconds)
        if result.proposal and not ctx.is_current(state_manager.get_current_context()):
            result.proposal = None
            result.status = "failed"
            result.errors.append("stale_context")
    result.proposal_id = f"proposal-{uuid4().hex}"
    await asyncio.to_thread(state_manager.store.save_grounding_result, result.proposal_id, payload.capture_id,
                            result.model_dump(mode="json"), state_manager._now_iso())
    return result.model_dump(mode="json")


@app.post("/api/scenarios/{scenario_id}/grounding")
async def interpret_grounding(scenario_id: str, payload: GroundingRequest) -> Dict[str, Any]:
    ctx = require_context(payload.source_context)
    if payload.media_kind == "video":
        return await _interpret_video(payload, ctx)
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
    if not await asyncio.to_thread(state_manager.store.save_capture, capture.model_dump(mode="json"), state_manager._now_iso()):
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
    await asyncio.to_thread(state_manager.store.save_grounding_result, result.proposal_id, capture.capture_id,
                            result.model_dump(mode="json"), state_manager._now_iso())
    return result.model_dump(mode="json")


@app.get("/api/scenarios/{scenario_id}/matrix")
def get_scenario_matrix(scenario_id: str) -> Dict[str, Any]:
    """Legacy response shape for the explicitly closed-reserve benchmark."""
    if scenario_id != "facility-demo":
        raise HTTPException(404, "Unknown scenario")
    ctx = state_manager.get_current_context()
    try:
        lab = scenario_service.get_scenario_lab(ctx, "closed_benchmark")
    except ValueError as error:
        raise HTTPException(409, str(error)) from error
    cases = {case["id"]: case for case in lab["cases"]}
    return {
        "context": ctx.model_dump(),
        "hypothetical": True,
        "reserve_basis": "closed_benchmark",
        "provenance": "local_scenario_lab",
        "comparable": lab["comparable"],
        "scenarios": {
            "baseline": cases["baseline"]["keep_current"],
            "p1_blocked": cases["p1_blocked"]["keep_current"],
            **{key: {field: cases[key][field] for field in ("keep_current", "open_p3", "net_gain")} for key in ("p2_blocked", "b2_blocked")},
        },
    }


@app.post("/api/scenarios/{scenario_id}/lab")
def run_scenario_lab(scenario_id: str, payload: ScenarioLabRequest) -> Dict[str, Any]:
    if scenario_id != "facility-demo":
        raise HTTPException(404, "Unknown scenario")
    context = require_context(payload.expected_context)
    try:
        return scenario_service.get_scenario_lab(context, payload.reserve_basis)
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


@app.post("/api/scenarios/{scenario_id}/investigate")
async def run_investigation(scenario_id: str, payload: InvestigationRequest) -> Dict[str, Any]:
    ctx = require_context(payload.expected_context)
    if payload.mode == "local" and not fixtures_enabled():
        raise HTTPException(403, "Local demo investigations are disabled in production mode")
    inv_id = payload.investigation_id
    if inv_id in active_investigations:
        raise HTTPException(409, "Investigation already running; inspect progress or cancel it")
    if _investigation_slots.locked():
        raise HTTPException(429, "Too many investigations are running; try again shortly")
    async with _investigation_slots:
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
        await asyncio.to_thread(
            state_manager.store.save_investigation,
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
async def operator_approve_gate(payload: GateApprovalRequest,
                                x_operator_token: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    """
    Operator physical approval flow:
    Requires human confirmation before motor movement begins.
    """
    # Authorize before anything else, so an unauthenticated caller learns nothing about investigations.
    physical = not hardware_bridge.is_simulator
    operator = _authorize_physical_operator(x_operator_token) if physical else "simulator-local"
    payload = payload.model_dump(mode="json")
    candidate = payload.get("candidate_alternative", "OPEN_P3")
    ctx = require_context(payload.get("expected_context"))
    if candidate != "OPEN_P3":
        raise HTTPException(422, "Only the reviewed OPEN_P3 candidate can use this approval endpoint")
    raw = await asyncio.to_thread(state_manager.store.get_investigation, payload.get("investigation_id", ""))
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
    if investigation.provenance != "live" and not hardware_bridge.is_simulator:
        raise HTTPException(409, "physical_approval_requires_live_evidence")

    approval_id = payload.get("idempotency_key")
    if not isinstance(approval_id, str) or not 1 <= len(approval_id) <= 128:
        raise HTTPException(422, "An approval idempotency_key is required")

    async with _approval_lock:
        if await asyncio.to_thread(state_manager.store.has_event_key, approval_id):
            raise HTTPException(409, "Approval already submitted; inspect observed state before a new request")
        success, cmd_id = await hardware_bridge.request_gate_target(target_enum)
        if not success:
            # Nothing was acknowledged, so nothing is recorded and the key stays reusable.
            raise HTTPException(status_code=502, detail=f"device_not_acknowledged:{cmd_id}")
        recorded = await asyncio.to_thread(
            state_manager.store.save_event, "facility-demo", ctx.scenario_revision, "PHYSICAL_APPROVAL",
            {"context": ctx.model_dump(), "investigation_id": investigation.investigation_id,
             "candidate_run_id": opened.run_id, "candidate_hash": opened.candidate_hash,
             "operator": operator, "command_id": cmd_id},
            approval_id, state_manager._now_iso())
        if not recorded:
            raise HTTPException(409, "Approval already submitted; inspect observed state before a new request")

    return {
        "status": "APPROVED_AND_COMMANDED",
        "acknowledged": True,
        "command_id": cmd_id,
        "target": target_enum.value,
        "operator": operator,
        "notice": "Device acknowledged the command. Movement is not confirmed until the endpoint switches report it.",
    }


@app.post("/api/hardware/reset-gate")
async def reset_gate(x_operator_token: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    """Reset for the next judge: close the reserve gate P3. Arrival is confirmed only by the endpoint observation."""
    physical = not hardware_bridge.is_simulator
    operator = _authorize_physical_operator(x_operator_token) if physical else "simulator-local"
    if any(not task.done() for task, _ in active_investigations.values()):
        raise HTTPException(409, "investigation_running")
    async with _approval_lock:
        if state_manager.physical_gate_state == GateObservedState.CLOSED:
            return {"status": "ALREADY_CLOSED"}
        success, cmd_id = await hardware_bridge.request_gate_target(GateTarget.CLOSED)
        if not success:
            raise HTTPException(status_code=502, detail=f"device_not_acknowledged:{cmd_id}")
        ctx = state_manager.get_current_context()
        await asyncio.to_thread(
            state_manager.store.save_event, "facility-demo", ctx.scenario_revision, "PHYSICAL_RESET",
            {"operator": operator, "command_id": cmd_id}, f"reset-{uuid4().hex}", state_manager._now_iso())
    return {"status": "CLOSE_ACKNOWLEDGED", "command_id": cmd_id}


@app.post("/api/hardware/stop")
async def emergency_stop(x_operator_token: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    """Emergency stop: asks the device to stop outputs. Requires the operator token on physical hardware."""
    if not hardware_bridge.is_simulator:
        _authorize_physical_operator(x_operator_token)
    ok, detail = await hardware_bridge.request_stop()
    if not ok:
        raise HTTPException(status_code=502, detail=f"stop_not_acknowledged:{detail}")
    return {"status": "STOP_ACKNOWLEDGED", "command_id": detail}


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
frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
