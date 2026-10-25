"""Robustness sweep inside the agent sandbox (network disabled). Run from /workspace/kit:

    python3 -m spatialtwin_kit.sweep                       # checked best, N-1 + sensitivity + second hazards
    python3 -m spatialtwin_kit.sweep --candidate D4=open,D9=open --only-single
    python3 -m spatialtwin_kit.sweep --scenario stuck_closed:D3 --scenario jam:D9@0.50

Reads /workspace/inputs/{venue,hazards,checked_plan}.json (read-only), writes /workspace/out/sweep.json and prints a
short summary. With networkx it runs the exact copy of the local solver ("exact copy"); without it, the pure-Python
max-flow estimator ("sandbox estimate", crossings only). Either way these are sandbox numbers: the laptop's local
checker re-runs every claim and decides.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from typing import Any, Dict, List, Optional

from .effects_v2 import compute_effects
from .estimate import max_completed
from .model import VenueV2
from .scenarios import HAZARD_TYPES, Scenario, ScenarioError, fault_fields, parse_scenario, scenario_hazards

try:  # networkx is not pre-installed in the sandbox image; the copy needs it for the exact solve
    import networkx  # noqa: F401
    from .flow_solver_v2 import FlowSolverV2
    ENGINE = "exact"
except ImportError:  # pragma: no cover - depends on the sandbox image
    from .flow_solver_v2 import FlowSolverV2  # importable without networkx; only solve() needs it
    ENGINE = "estimate"

INPUTS = os.environ.get("SPATIALTWIN_INPUTS", "/workspace/inputs")
OUT = os.environ.get("SPATIALTWIN_OUT", "/workspace/out")
ENGINE_LABEL = {"exact": "exact copy of the local solver", "estimate": "sandbox estimate"}
JAM = 0.5
MAX_CLAIMS = 12


def load_inputs(directory: str = INPUTS) -> Dict[str, Any]:
    def read(name: str) -> Any:
        with open(os.path.join(directory, name)) as handle:
            return json.load(handle)
    venue = VenueV2.from_json(read("venue.json"))
    hazards = read("hazards.json")
    plan = read("checked_plan.json")
    return {"venue": venue, "horizon": int(hazards["horizon_seconds"]), "hazards": hazards["hazards"], "plan": plan}


class Sandbox:
    def __init__(self, data: Dict[str, Any], engine: str = ENGINE):
        self.venue = data["venue"]
        self.horizon = data["horizon"]
        self.hazards = data["hazards"]
        self.engine = engine
        self.solver = FlowSolverV2(self.venue)
        self.default_closed = frozenset(d.id for d in self.venue.doors if d.default_state == "closed")
        self.defaults = {k: v.untenable_s for k, v in self.venue.hazard_defaults.items()}
        self.zones = frozenset(z.id for z in self.venue.zones)
        self._fx: Dict[Any, Any] = {}
        self._cache: Dict[Any, Dict[str, Any]] = {}

    def effects(self, scenario: Scenario):
        key = (scenario.untenable, scenario.second_hazard)
        if key not in self._fx:
            hazards = self.hazards
            if scenario.changes_hazards:
                hazards = scenario_hazards(self.hazards, scenario, horizon=self.horizon,
                                           dt=self.venue.time_step_seconds, defaults=self.defaults, zones=self.zones)
            fx = compute_effects(self.venue, hazards, self.horizon)
            free = sorted(d.id for d in self.venue.doors if d.planner_can_open and d.default_state == "closed"
                          and d.id not in fx.gas_locked_doors)
            self._fx[key] = (fx, free)
        return self._fx[key]

    def solve(self, opened: frozenset, scenario: Scenario) -> Dict[str, Any]:
        fx, free = self.effects(scenario)
        opened = frozenset(opened) & frozenset(free)
        key = (scenario.label, opened)
        if key in self._cache:
            return self._cache[key]
        base = replace(fx.inputs_base, closed_doors=self.default_closed - opened)
        closed, exits, mult = fault_fields(base.closed_doors, base.exit_closed_from, base.multipliers, scenario)
        inputs = replace(base, closed_doors=closed, exit_closed_from=exits, multipliers=mult)
        dt = self.venue.time_step_seconds
        candidate_hash = self.solver.candidate_hash(inputs, self.horizon, dt)
        if self.engine == "exact":
            outcome = self.solver.solve(inputs, self.horizon)
            result = {"completed_crossings": outcome.completed_crossings,
                      "is_valid": bool(outcome.validator_report["is_valid"]), "candidate_hash": candidate_hash}
        else:
            result = {"completed_crossings": max_completed(self.venue, inputs, self.horizon, dt), "is_valid": None,
                      "candidate_hash": candidate_hash}
        result["door_states"] = {d: ("open" if d in opened else "closed") for d in free}
        self._cache[key] = result
        return result

    def evaluate(self, candidate: Dict[str, str], scenario: Scenario | str) -> Dict[str, Any]:
        scenario = parse_scenario(scenario) if isinstance(scenario, str) else scenario
        fx, free = self.effects(scenario)
        opened = frozenset(d for d, s in candidate.items() if s == "open")
        mine = self.solve(opened, scenario)
        options = []
        for mask in range(1 << len(free)):
            state = frozenset(d for i, d in enumerate(free) if mask >> i & 1)
            options.append(self.solve(state, scenario))
        best = max(o["completed_crossings"] for o in options)
        return {"scenario": scenario.label, **mine, "best_completed_crossings": best,
                "holds": mine["completed_crossings"] >= best}

    def single_failures(self, candidate: Dict[str, str]) -> List[str]:
        opened = {d for d, s in candidate.items() if s == "open"}
        fx, _ = self.effects(parse_scenario("baseline"))
        open_doors = sorted(d.id for d in self.venue.doors if d.id not in (self.default_closed - opened))
        closed_exits = {x for x, t in fx.inputs_base.exit_closed_from.items() if t == 0}
        usable = sorted(x.id for x in self.venue.exits if x.id not in closed_exits)
        out = [f"stuck_closed:{d}" for d in open_doors] + [f"exit_blocked:{x}" for x in usable]
        return out + [f"jam:{d}@{JAM:.2f}" for d in sorted(opened)] + [f"jam:{x}@{JAM:.2f}" for x in usable]


def run(data: Dict[str, Any], candidate: Optional[Dict[str, str]] = None, scenarios: Optional[List[str]] = None,
        only_single: bool = False, engine: str = ENGINE) -> Dict[str, Any]:
    box = Sandbox(data, engine)
    plan = data["plan"]
    candidate = candidate or dict(plan["checked_best_door_states"])
    results: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []
    labels = scenarios or (["baseline"] + box.single_failures(candidate))
    if not scenarios and not only_single:
        dt = box.venue.time_step_seconds
        for hazard in box.hazards:
            if hazard["type"] != "WATER" and hazard.get("untenable_s") is not None:
                labels += [f"untenable:{hazard['id']}={s}" for s in range(max(2, dt), min(38, box.horizon - dt) + 1, dt)
                           if s % dt == 0]
        hazard_zones = {h["zone_id"] for h in box.hazards}
        labels += [f"second_hazard:{k}@{z.id}" for z in box.venue.zones if z.id not in hazard_zones for k in HAZARD_TYPES]
    for label in labels:
        try:
            results.append(box.evaluate(candidate, label))
        except (ScenarioError, KeyError, ValueError) as error:
            errors.append({"scenario": label, "error": str(error)[:80]})
    single = [r for r in results if r["scenario"].split(":")[0] in ("stuck_closed", "exit_blocked", "jam")]
    held = sum(1 for r in single if r["holds"])
    claims = [{"scenario": r["scenario"], "completed_crossings": r["completed_crossings"],
               "candidate_hash": r["candidate_hash"]} for r in results[:MAX_CLAIMS]]
    return {"engine": engine, "engine_label": ENGINE_LABEL[engine], "candidate": candidate,
            "single_failures_total": len(single), "single_failures_held": held,
            "breaks": [r["scenario"] for r in single if not r["holds"]], "results": results, "errors": errors,
            "suggested_claims": claims,
            "note": "Sandbox numbers. Modeled crossings of a synthetic population, never survival. "
                    "The local checker re-runs every claim and decides."}


def _parse_candidate(text: str) -> Dict[str, str]:
    out = {}
    for part in text.split(","):
        door, _, state = part.partition("=")
        if state not in ("open", "closed"):
            raise SystemExit(f"bad candidate term {part!r}")
        out[door.strip()] = state
    return out


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", default="")
    parser.add_argument("--scenario", action="append", default=[])
    parser.add_argument("--only-single", action="store_true")
    parser.add_argument("--inputs", default=INPUTS)
    parser.add_argument("--out", default=os.path.join(OUT, "sweep.json"))
    args = parser.parse_args(argv)
    data = load_inputs(args.inputs)
    report = run(data, _parse_candidate(args.candidate) if args.candidate else None, args.scenario or None,
                 args.only_single)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as handle:
        json.dump(report, handle, indent=1, sort_keys=True)
    print(json.dumps({k: report[k] for k in ("engine_label", "candidate", "single_failures_held",
                                              "single_failures_total", "breaks")}))
    print(f"wrote {args.out}; suggested_claims has {len(report['suggested_claims'])} entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
