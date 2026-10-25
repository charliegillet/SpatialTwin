"""Zone watch: independent deterministic watchers over one checked run.

Each watcher reads a frozen view of the accepted run and emits typed records.
The orchestrator only aggregates them into an escalation level and a next
workflow step. It predicts no benefit, sends nothing and commands nothing.
"""

from __future__ import annotations

from typing import Callable, List, Literal, Optional, Sequence, Tuple

from pydantic import BaseModel, ConfigDict

from backend.app.contracts import GateObservedState, RunContext
from .basis import (
    BOUNDARY_FIELDS, OBSERVED_GATE_STATES, ZONE_FIELDS, EvidencePointer, Frame, ReviewBasis,
    boundary_quota, checked_frames,
)

Severity = Literal["info", "advisory", "alert"]
RecordKind = Literal[
    "NOMINAL", "RESIDUAL_HOLDING", "CAPACITY_PRESSURE", "PASSAGE_UNAVAILABLE",
    "BOUNDARY_UNAVAILABLE", "BOUNDARY_AT_QUOTA", "BOUNDARY_IDLE",
    "RESERVE_OBSERVED", "RESERVE_UNCONFIRMED", "TELEMETRY_MISSING", "SIMULATED_ENDPOINT",
]
NextStep = Literal["none", "compare_alternatives", "await_endpoint", "no_allowed_alternative"]
SEVERITY_RANK = {"info": 0, "advisory": 1, "alert": 2}
# Display threshold for a holding zone close to its declared storage capacity.
CAPACITY_PRESSURE_RATIO = 0.9
DELIVERY_NOTICE = ("Local simulated escalation record. No message, notification, authority "
                   "dispatch or device command was sent.")


class WatchRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_id: str
    watcher_id: str
    kind: RecordKind
    severity: Severity
    summary: str
    value: Optional[int] = None
    limit: Optional[int] = None
    unit: Optional[str] = None
    at_seconds: Optional[int] = None
    evidence: List[EvidencePointer]


class WatcherStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    watcher_id: str
    label: str
    scope: Literal["zone", "passage", "boundary", "reserve"]
    severity: Severity
    record_ids: List[str]


class WatchReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal["zone-watch-v1"] = "zone-watch-v1"
    base_context: RunContext
    run_id: str
    candidate_hash: str
    watchers: List[WatcherStatus]
    records: List[WatchRecord]
    escalation: Literal["nominal", "advisory", "escalated"]
    escalation_reasons: List[str]
    next_step: NextStep
    delivery: Literal["local_record_only"] = "local_record_only"
    notice: str = DELIVERY_NOTICE


def _record(watcher_id: str, kind: str, severity: str, summary: str, evidence: List[EvidencePointer],
            **values) -> WatchRecord:
    return WatchRecord(record_id=f"{watcher_id}:{kind}", watcher_id=watcher_id, kind=kind,
                       severity=severity, summary=summary, evidence=evidence, **values)


def watch_zone(basis: ReviewBasis, frames: Sequence[Frame], zone_id: str) -> List[WatchRecord]:
    spec, key, plan = basis.venue.zones[zone_id], ZONE_FIELDS[zone_id], basis.plan
    watcher, last = f"zone:{zone_id}", len(frames) - 1
    peak_index = max(range(len(frames)), key=lambda index: frames[index][key])
    peak, residual = frames[peak_index][key], frames[last][key]
    records = []
    if residual:
        records.append(_record(watcher, "RESIDUAL_HOLDING", "alert",
            f"{residual} synthetic occupants still holding in {spec.name} at {plan.horizon_seconds}s.",
            [basis.plan_pointer(f"timeline[{last}].{key}"), basis.plan_pointer(f"zone_occupancy.{zone_id}")],
            value=residual, unit="synthetic occupants", at_seconds=plan.horizon_seconds))
    if spec.max_capacity and peak >= CAPACITY_PRESSURE_RATIO * spec.max_capacity:
        records.append(_record(watcher, "CAPACITY_PRESSURE", "advisory",
            f"{spec.name} peaked at {peak} of {spec.max_capacity} declared holding capacity.",
            [basis.plan_pointer(f"timeline[{peak_index}].{key}"), basis.venue_pointer(f"zones.{zone_id}.max_capacity")],
            value=peak, limit=spec.max_capacity, unit="synthetic occupants",
            at_seconds=frames[peak_index]["time_seconds"]))
    if not records:
        records.append(_record(watcher, "NOMINAL", "info",
            f"{spec.name} peaked at {peak} of {spec.max_capacity}; none held at {plan.horizon_seconds}s.",
            [basis.plan_pointer(f"timeline[*].{key}"), basis.venue_pointer(f"zones.{zone_id}.max_capacity")],
            value=peak, limit=spec.max_capacity, unit="synthetic occupants"))
    return records


def watch_passage(basis: ReviewBasis, frames: Sequence[Frame], portal_id: str) -> List[WatchRecord]:
    watcher = f"passage:{portal_id}"
    if portal_id in basis.blocked_portals:
        return [_record(watcher, "PASSAGE_UNAVAILABLE", "alert",
            f"{portal_id} is unavailable in the accepted scenario; the server checker admits no transfer through it.",
            [basis.state_pointer("blocked_portals"), basis.plan_pointer("validator_report.checks_run.schedule_allowed_edges")])]
    return [_record(watcher, "NOMINAL", "info", f"{portal_id} is available in the accepted scenario.",
                    [basis.state_pointer("blocked_portals")])]


def watch_boundary(basis: ReviewBasis, frames: Sequence[Frame], boundary_id: str) -> List[WatchRecord]:
    plan, key, watcher = basis.plan, BOUNDARY_FIELDS[boundary_id], f"boundary:{boundary_id}"
    crossings, quota = plan.boundary_breakdown.get(boundary_id, 0), boundary_quota(basis, boundary_id)
    evidence = [basis.plan_pointer(f"boundary_breakdown.{boundary_id}"),
                basis.venue_pointer(f"boundaries.{boundary_id}.service_rate_per_sec")]
    values = {"value": crossings, "limit": quota, "unit": "modeled crossings"}
    limiting = "advisory" if plan.remaining_population else "info"
    if boundary_id in basis.blocked_boundaries:
        return [_record(watcher, "BOUNDARY_UNAVAILABLE", "alert",
            f"{boundary_id} is unavailable in the accepted scenario; it serviced {crossings} crossings.",
            [basis.state_pointer("blocked_boundaries"), basis.plan_pointer(f"timeline[*].{key}")], **values)]
    if crossings >= quota:
        return [_record(watcher, "BOUNDARY_AT_QUOTA", limiting,
            f"{boundary_id} serviced {crossings} of its {quota} finite-horizon quota.", evidence, **values)]
    if crossings == 0:
        return [_record(watcher, "BOUNDARY_IDLE", limiting,
            f"{boundary_id} is available but serviced 0 of {quota}; no modeled route reached it in this run.",
            evidence, **values)]
    return [_record(watcher, "NOMINAL", "info",
        f"{boundary_id} serviced {crossings} of its {quota} finite-horizon quota.", evidence, **values)]


def watch_reserve(basis: ReviewBasis, frames: Sequence[Frame], portal_id: str) -> List[WatchRecord]:
    watcher, state = f"reserve:{portal_id}", basis.gate_state
    records = []
    if state not in OBSERVED_GATE_STATES:
        records.append(_record(watcher, "RESERVE_UNCONFIRMED", "alert",
            f"{portal_id} is reported {state.value}; the reserve stays unavailable until a fresh endpoint observation.",
            [basis.state_pointer("physical_gate_state")]))
    elif not basis.hardware_boot_id:
        records.append(_record(watcher, "TELEMETRY_MISSING", "advisory",
            f"{portal_id} is reported {state.value}, but no device telemetry receipt has been received.",
            [basis.state_pointer("physical_gate_state"), basis.state_pointer("last_hardware_boot_id")]))
    else:
        records.append(_record(watcher, "RESERVE_OBSERVED", "info",
            f"{portal_id} reported {state.value} by endpoint telemetry (epoch {basis.gate_epoch}).",
            [basis.state_pointer("physical_gate_state"), basis.state_pointer("last_gate_epoch")]))
    if basis.hardware_mode == "simulator":
        records.append(_record(watcher, "SIMULATED_ENDPOINT", "info",
            "Simulator endpoint. This is not a physical gate observation.",
            [basis.state_pointer("hardware_mode")]))
    return records


Watcher = Callable[[ReviewBasis, Sequence[Frame], str], List[WatchRecord]]


def _watchers(basis: ReviewBasis) -> List[Tuple[str, str, str, Watcher, str]]:
    venue = basis.venue
    plan = [(f"zone:{zone_id}", spec.name, "zone", watch_zone, zone_id) for zone_id, spec in venue.zones.items()]
    plan += [(f"passage:{portal_id}", f"{portal_id} passage", "passage", watch_passage, portal_id)
             for portal_id, spec in venue.portals.items() if spec.can_be_blocked]
    plan += [(f"boundary:{boundary_id}", f"{boundary_id} boundary", "boundary", watch_boundary, boundary_id)
             for boundary_id in venue.boundaries]
    plan += [(f"reserve:{portal_id}", f"{portal_id} reserve gate", "reserve", watch_reserve, portal_id)
             for portal_id, spec in venue.portals.items() if spec.is_actuated]
    return plan


def run_zone_watch(basis: ReviewBasis) -> WatchReport:
    frames = checked_frames(basis)
    statuses, records = [], []
    for watcher_id, label, scope, watcher, element in _watchers(basis):
        # Every watcher receives the same immutable frames; one cannot change another's input.
        found = watcher(basis, frames, element)
        if not found or any(record.watcher_id != watcher_id for record in found):
            raise ValueError("watcher returned records outside its scope")
        severity = max((record.severity for record in found), key=SEVERITY_RANK.__getitem__)
        statuses.append(WatcherStatus(watcher_id=watcher_id, label=label, scope=scope, severity=severity,
                                      record_ids=[record.record_id for record in found]))
        records.extend(found)
    alerts = [record.record_id for record in records if record.severity == "alert"]
    advisories = [record.record_id for record in records if record.severity == "advisory"]
    escalation = "escalated" if alerts else "advisory" if advisories else "nominal"
    residual = basis.plan.remaining_population > 0
    if basis.gate_state not in OBSERVED_GATE_STATES:
        next_step = "await_endpoint"
    elif escalation == "escalated" and residual:
        next_step = "compare_alternatives" if basis.gate_state == GateObservedState.CLOSED else "no_allowed_alternative"
    else:
        next_step = "none"
    return WatchReport(base_context=basis.context, run_id=basis.plan.run_id,
                       candidate_hash=basis.plan.candidate_hash, watchers=statuses, records=records,
                       escalation=escalation, escalation_reasons=alerts or advisories, next_step=next_step)
