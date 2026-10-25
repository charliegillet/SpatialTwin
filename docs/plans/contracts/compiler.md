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
it with `x_px = minx_px + X / metres_per_px`, `y_px = maxy_px - Y / metres_per_px`. The bbox includes void boxes
(the drawn building), so when a void lies along the west or south edge the rooms start east or north of 0: the
lowest cluster is pinned only when it holds the frame origin, and nothing is shifted.

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
  removed). An extra box that does not touch the room is dropped and listed (its outline still blocks exits, below).
- Doors: the shared collinear wall of the two rooms is found; the door point is projected on it and clamped so the
  full width fits (width shrinks only if the wall is shorter). No wall >= 0.6 m shared: the door is dropped with a
  reason. Parallel doors between one room pair merge (widths add, capped by the wall length) because the venue model
  allows one door per pair.
- Voids (room kind `void`: OPEN TO BELOW, atria, light wells, shafts) frame the drawing but never become zones;
  doors and exits into a void are dropped and listed.
- Door and window exits: projected on the nearest outside part of the room's boundary, the part that no other room
  covers and that faces no void and no extra box the compiler could not attach (both are drawn but not outside;
  void edges snap to the room grid lines within the same tolerance). When that moves an exit off the wall nearest
  its point, `report.edits` says which outline the wall faces. No outside wall >= 0.6 m: the exit is dropped.
- Interior exit stairs (venue exit `kind: "stair"`): a draft exit of kind `stair` never becomes a wall opening (on
  an upper floor a stair drawn as a facade door is an exit into the air; on a shared wall it cuts into the next
  room). It skips the outside-wall search and is placed strictly inside its room. A door or window exit of a room of
  kind `stair` with no outside wall is placed the same way.
  - Allowed rooms: kinds `stair`, `lobby` and `corridor`. A stair exit in any other room (office, bedroom, hall,
    ...) is dropped: `exit KEY: an exit stair in ROOM (kind); an interior exit stair must be in a stair, lobby or
    corridor; dropped`.
  - Point, first that qualifies, rounded to 0.01 m: the drawn point if it is at least 0.5 m from every wall of the
    room; else the room's label point under the same 0.5 m rule; else the centre of the room's bounding box if it
    is strictly inside. None qualifies: dropped (`no point inside ROOM clear of its walls ...`).
  - Width is the drawn width or the 0.9 m default (service rate as for a door exit). Each placement is listed in
    `report.edits` (`placed inside ROOM at (x, y) m (drawn point|room label point|room centre), not in a wall`).
  - `graph_checks` requires a `stair` exit to be strictly inside its zone (`stair_exit_not_inside_its_room`) and
    refuses a wall exit whose gap overlaps a door's gap on the same wall line (`exit_overlaps_door`). The 3D scene
    cuts no wall gap for it and draws a floor marker; the overlay draws a small box at its point.
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
