"""Evaluate a hazard schedule with the existing planner; no planner logic lives here."""
from __future__ import annotations

from backend.app.contracts import AlternativeId, EvaluationEnvelope
from backend.app.planner.flow_solver import FlowPlanner

from .model import HazardSchedule, ToolContext


def solve_schedule(schedule: HazardSchedule, ctx: ToolContext, alternative_id: AlternativeId) -> EvaluationEnvelope:
    schedule.validate_against(ctx)
    portal_close_at = {e.element_id: e.close_at_s for e in schedule.events if e.element_id in ctx.venue.portals}
    boundary_close_at = {e.element_id: e.close_at_s for e in schedule.events if e.element_id in ctx.venue.boundaries}
    return FlowPlanner(ctx.venue).solve(
        ctx.base_context, alternative_id,
        set(ctx.blocked_portals), set(ctx.blocked_boundaries), p3_physical_open=ctx.p3_physical_open,
        horizon_seconds=ctx.horizon_seconds, time_step_seconds=ctx.time_step_seconds,
        portal_close_at=portal_close_at, boundary_close_at=boundary_close_at,
    )
