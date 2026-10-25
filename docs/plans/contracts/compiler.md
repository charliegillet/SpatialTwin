# Compiler contract: VenueDraftV1 to VenueV2 (measured vs assumed)

Code: `backend/app/venues/compiler.py` (`compile_draft`), `backend/app/ai/real2sim/overlay.py`
(`render_overlay`, `render_topdown`). Fixtures: `venue/real2sim/{evac-office,sketch-home}` via
`tools/gen_real2sim_fixtures.py` (synthetic, drawn by our tool, `provenance: "synthetic"`).

The compiler is deterministic: same draft, image size and options give byte-identical JSON and the same
`geometry_revision = "geom-" + sha256(canonical JSON without geometry_revision)[:16]`. No model call, no randomness.
Nothing Argon returns reaches the planner except through the compiler, `graph_checks` and an operator's Accept.

## Coordinate transform

```
pixel    x_px = x/1000 * width_px          y_px = y/1000 * height_px         (draft point is [y, x]; image y grows down)
bbox     minx_px, maxy_px = west-most / south-most edge over every room box and extra box
metres   X = (x_px - minx_px) * metres_per_px
         Y = (maxy_px - y_px) * metres_per_px                                (venue y grows north; origin = south-west corner)
```

The south-west-most grid line is pinned to 0 when snapping, so the map stays exactly affine and the overlay inverts
it with `x_px = minx_px + X / metres_per_px`, `y_px = maxy_px - Y / metres_per_px`.

## Scale priority

| Priority | Source | `report.scale_basis` |
|---|---|---|
| 1 | operator `building_width_m` (east-west width of the drawn building) | `operator_input` |
| 2 | draft `scale` reference (`a`, `b`, `metres`) when it implies a 3-300 m building | the draft's basis (`scale_bar`, `dimension_label`, ...) |
| 3 | declared default width by `image_kind`: evacuation_map 30 m, architectural_plan 20 m, sketch 12 m, photo_of_plan 20 m, other 20 m | `default_width` (listed in `report.defaults`) |

An implausible reference (building outside 3-300 m) is ignored and listed in `report.dropped`.

## Snapping and geometry (assumed cleanup of what was read)

- Box edges are clustered per axis (gap <= max(0.4 m, 1.5 % of the axis extent), cluster span <= twice that) onto
  shared grid lines, rounded to 0.1 m. Snapping is monotone, so it cannot turn touching rooms into overlapping
  rooms. Every cluster that merged distinct values is listed in `report.edits`.
- `extra_boxes` are unioned with the main box into one rectilinear outline (counter-clockwise, collinear points
  removed). An extra box that does not touch the room is dropped and listed.
- Doors: the shared collinear wall of the two rooms is found; the door point is projected on it and clamped so the
  full width fits (width shrinks only if the wall is shorter). No wall >= 0.6 m shared: the door is dropped with a
  reason. Parallel doors between one room pair merge (widths add, capped by the wall length) because the venue model
  allows one door per pair.
- Exits: projected on the nearest exterior part of the room's boundary (the part no other room covers).
- Not handled: slanted or curved walls, rooms drawn as non-rectangles beyond three boxes, stacked floors, doors
  between a room and a courtyard.

## Declared defaults (assumed, not measured)

| Item | Value | Why |
|---|---|---|
| Door width, when the drawing gives none | 0.9 m (window exit 0.6 m) | common residential/office clear width |
| Door/exit width limits | 0.6 to 6.0 m | graph_checks `unusual_width` range |
| Door throughput | 1.0 person/s per metre of width (`width * 1.0`) | building-v2: 3.0 m door at 3.0 p/s |
| Door travel time | 2 s (one solver step) | building-v2 doors are 2 s (4 s for the dock) |
| Exit service rate | 0.6 p/s per metre (windows 0.3) | building-v2: 3.0 m at 2.0, 2.4 m at 1.5, 1.8 m at 1.0 |
| Room capacity | `max(2, floor(area_m2 * 1.0))` | building-v2 holds at most about 1 person per m² |
| Occupants, headcount given | spread by floor area over non-circulation rooms, capped by capacity, overflow to corridors | operator input |
| Occupants, no headcount | per-room `occupants_hint` read from the drawing (capped), else a density of 0.08 (evacuation map, plan), 0.12 (sketch), 0.10 (photo, other) people per m² of non-circulation floor | declared, shown in `report.defaults` |
| Circulation rooms (no default occupants) | kinds `corridor`, `lobby`, `stair` | people pass through them |
| Time step | 2 s | solver step |
| Horizon | `(width + height) / 1.6 m/s` plus `1.25 * occupants / total exit service`, rounded up to a multiple of 2, clamped to 30-120 s | sized to the building and the queue |
| LED map | 3 pixels per exit, then per controllable door, sequential from 0 | the planner sizes the strip |
| Hazard defaults | copied from building-v2 | declared |

## Door kinds

| Draft | Venue door |
|---|---|
| key in `controllable_doors` | `servo_door`, `actuation: motorized`, `default_state: closed`, `planner_can_open: true` |
| `symbol: fire_door` | `fire_door`, `hold_open`, open |
| `symbol: opening` | `opening`, `fixed`, open |
| anything else | `room_door`, `indicator_only`, open |

Unknown controllable keys are ignored and listed in `report.dropped` (`controllable KEY: ...`). More than three
controllable doors are kept: `graph_checks` reports `too_many_controllable_doors` (an error that blocks Accept).

## What the Q&A answer is

- **Measured from the drawing:** relative layout, which walls are shared, where along a wall a door or exit sits,
  room names, door symbols, and (when present) a scale reference.
- **Taken from the operator:** building width, headcount, which doors are controllable.
- **Assumed and declared:** every rate above, widths the drawing did not give, capacities, default occupants, the
  horizon, and the default building width when nothing measures scale. All are listed in `report.defaults` and the
  venue `provenance`. The result is "not a surveyed plan"; counts are modeled crossings.

## Report keys

`report.element_ids` maps draft key to venue id (rooms keep their key, prefixed `Z_` on a collision with a generated
`D#`/`E#`; doors become `D1..`, exits `E1..` in draft order). `report.evidence_points` maps venue id to the draft's
`[y, x]` point. Dropped entries start `door KEY:`, `exit KEY:`, `room KEY:`, `controllable KEY:` or
`scale reference:` so the overlay can draw them in red.
