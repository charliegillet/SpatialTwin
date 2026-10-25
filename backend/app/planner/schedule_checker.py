"""Independent accounting of sampled schedules and the solver's flow witness."""

from collections import defaultdict
from typing import Any

FIELDS = {"EVENT": "event_occupancy", "WEST": "west_occupancy",
          "EAST": "east_occupancy", "RESERVE": "reserve_occupancy"}


def validate_schedule(venue, timeline, population, completed, residual, breakdown,
                      horizon, dt, blocked_portals, blocked_boundaries, flow=None,
                      portal_close_at=None, boundary_close_at=None):
    checks = ["timeline_population_conservation", "timeline_boundary_rates",
              "timeline_terminal_consistency", "timeline_time_grid", "timeline_zone_capacities"]
    reasons = []
    if not isinstance(timeline, list) or type(dt) is not int or type(horizon) is not int or dt <= 0 or horizon <= 0 or horizon % dt:
        return checks, ["Timeline requires a finite, complete time grid"]
    steps = horizon // dt
    if len(timeline) != steps + 1:
        return checks, ["Timeline is missing scheduled frames"]
    previous = {"B1": 0, "B2": 0}
    integer_fields = [*FIELDS.values(), "in_transit_occupancy", "b1_cumulative", "b2_cumulative", "total_completed"]
    for t, frame in enumerate(timeline):
        if not isinstance(frame, dict) or any(type(frame.get(k)) is not int or frame[k] < 0 for k in integer_fields):
            reasons.append(f"Timeline frame {t} contains missing, negative or non-integer counts")
            continue
        if type(frame.get("step")) is not int or type(frame.get("time_seconds")) is not int or frame.get("step") != t or frame.get("time_seconds") != t * dt:
            reasons.append(f"Timeline frame {t} is off the time grid")
        if sum(frame[k] for k in FIELDS.values()) + frame["in_transit_occupancy"] + frame["total_completed"] != population:
            reasons.append(f"Timeline frame {t} does not conserve every occupant")
        if frame["b1_cumulative"] + frame["b2_cumulative"] != frame["total_completed"]:
            reasons.append(f"Timeline frame {t} boundary counts disagree")
        for zone, key in FIELDS.items():
            if zone in venue.zones and frame[key] > venue.zones[zone].max_capacity:
                reasons.append(f"Timeline frame {t} exceeds {zone} holding capacity")
        for boundary, key in (("B1", "b1_cumulative"), ("B2", "b2_cumulative")):
            value = frame[key]
            spec = venue.boundaries.get(boundary)
            limit = max(1, int(spec.service_rate_per_sec * dt)) if spec else 0
            if value < previous[boundary] or value - previous[boundary] > limit:
                reasons.append(f"Timeline frame {t} violates {boundary} service rate")
            if boundary in blocked_boundaries and value:
                reasons.append(f"Timeline crosses blocked boundary {boundary}")
            previous[boundary] = value
    first, last = timeline[0], timeline[-1]
    if not isinstance(first, dict) or first.get("event_occupancy") != population or any(first.get(k, -1) != 0 for k in ["west_occupancy", "east_occupancy", "reserve_occupancy", "in_transit_occupancy", "total_completed"]):
        reasons.append("Timeline initial frame differs from the declared population")
    if not isinstance(last, dict) or last.get("total_completed") != completed or last.get("in_transit_occupancy") != 0 or any(last.get(key) != residual.get(zone, 0) for zone, key in FIELDS.items()) or any(last.get(key) != breakdown.get(boundary, 0) for boundary, key in (("B1", "b1_cumulative"), ("B2", "b2_cumulative"))):
        reasons.append("Timeline final frame differs from the checked result")

    if flow is not None:
        checks += ["schedule_allowed_edges", "schedule_flow_conservation", "timeline_matches_flow"]
        portal_close_at = portal_close_at or {}
        boundary_close_at = boundary_close_at or {}
        if portal_close_at or boundary_close_at:
            checks.append("schedule_timed_closures")
        closed_edges = {}  # edge -> closed element label; absent from `allowed`
        # Enumerate allowed model edges independently of the solver's graph builder.
        allowed = {("SOURCE", ("EVENT", 0)): population}
        transfers = {}
        services = {}
        for zone, spec in venue.zones.items():
            for t in range(steps):
                allowed[((zone, t), (zone, t + 1))] = spec.max_capacity
            allowed[((zone, steps), "UNASSIGNED_COLLECTOR")] = spec.max_capacity
        for portal, spec in venue.portals.items():
            if portal in blocked_portals:
                continue
            duration = max(1, spec.travel_time_seconds // dt)
            for t in range(steps - duration + 1):
                edge = ((spec.from_zone, t), (spec.to_zone, t + duration))
                if portal in portal_close_at and t * dt >= portal_close_at[portal]:
                    closed_edges[edge] = f"portal {portal}"
                    continue
                allowed[edge] = max(1, int(spec.throughput_per_sec * dt))
                transfers[edge] = (spec.from_zone, spec.to_zone, t, t + duration)
        for boundary, spec in venue.boundaries.items():
            if boundary in blocked_boundaries:
                continue
            for t in range(steps + 1):
                mid = f"B_{boundary}_{t}"
                edge = ((spec.from_zone, t), mid)
                if boundary in boundary_close_at and t * dt >= boundary_close_at[boundary]:
                    closed_edges[edge] = f"boundary {boundary}"
                    continue
                allowed[edge] = allowed[(mid, "EXIT_COLLECTOR")] = max(1, int(spec.service_rate_per_sec * dt))
                services[edge] = (boundary, spec.from_zone, t)
        incoming, outgoing = defaultdict(int), defaultdict(int)
        # A second reconstruction uses event deltas rather than waiting-arc counts.
        departures = defaultdict(int)
        arrivals = defaultdict(int)
        exits = defaultdict(int)
        for source, destinations in flow.items():
            for destination, amount in destinations.items():
                if type(amount) is not int or amount < 0:
                    reasons.append("Flow witness contains a negative or non-integer amount")
                    continue
                if not amount:
                    continue
                edge = (source, destination)
                if edge in closed_edges:
                    reasons.append(f"Flow witness moves occupants through {closed_edges[edge]} at or after its close time")
                    continue
                if edge not in allowed or amount > allowed[edge]:
                    reasons.append("Flow witness uses an unavailable edge or exceeds its capacity")
                    continue
                outgoing[source] += amount
                incoming[destination] += amount
                if edge in transfers:
                    before, after, departure, arrival = transfers[edge]
                    departures[(before, departure)] += amount
                    arrivals[(after, arrival)] += amount
                if edge in services:
                    boundary, zone, t = services[edge]
                    exits[(boundary, zone, t)] += amount
        if outgoing["SOURCE"] != population or incoming["EXIT_COLLECTOR"] != completed or incoming["UNASSIGNED_COLLECTOR"] != sum(residual.values()):
            reasons.append("Flow witness source or terminal totals differ from the result")
        for node in set(incoming) | set(outgoing):
            if node not in {"SOURCE", "EXIT_COLLECTOR", "UNASSIGNED_COLLECTOR"} and incoming[node] != outgoing[node]:
                reasons.append("Flow witness fails conservation at an internal node")
                break
        held = {zone: population if zone == "EVENT" else 0 for zone in FIELDS}
        in_transit = 0
        cumulative = {"B1": 0, "B2": 0}
        for t, frame in enumerate(timeline):
            if t:
                for zone in held:
                    leaving = departures[(zone, t - 1)]
                    arriving = arrivals[(zone, t)]
                    held[zone] += arriving - leaving
                    in_transit += leaving - arriving
            for (boundary, zone, time), amount in exits.items():
                if time == t:
                    held[zone] -= amount
                    cumulative[boundary] += amount
            expected = {key: held[zone] for zone, key in FIELDS.items()}
            expected.update(in_transit_occupancy=in_transit, b1_cumulative=cumulative["B1"], b2_cumulative=cumulative["B2"], total_completed=sum(cumulative.values()))
            if not isinstance(frame, dict) or any(frame.get(k) != value for k, value in expected.items()):
                reasons.append(f"Timeline frame {t} disagrees with the independent flow reconstruction")
    return checks, list(dict.fromkeys(reasons))
