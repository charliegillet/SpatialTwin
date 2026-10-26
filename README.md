# SpatialTwin

Turn a short translated room walkthrough into an **estimated, editable 3D room**. Inspect the source frames, correct furniture position/rotation/dimensions, calibrate against a measured reference, and save/export the versioned scene.

This branch is a standalone application derived from SpatialTwin's project history. Its checked-out application source contains no board, hardware, evacuation, actuator or legacy scenario runtime. The original main checkout and server remain separate.

## Run locally

Python 3.12 and Node 26 were used for this implementation.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
cd frontend
npm ci
npm run build
cd ..
# Set GEMINI_API_KEY in the backend environment, or in a local ignored .env.
.venv/bin/python -m tools.run_server
```

Open **http://127.0.0.1:8001**. For UI development, `cd frontend && npm run dev` uses port 5174 and proxies to the backend. Credentials are never part of the frontend bundle. The default bind address is loopback-only. Set `ROOMLAB_HOST=0.0.0.0` in the local `.env` to accept network connections, including Tailscale. Open the server’s IP address on port 8001 from the other computer. Same-origin writes are supported; unrelated browser origins remain blocked.

## Use

1. Upload an MP4, WebM or MOV, at most 10 minutes and 1 GiB. Walk with overlapping viewpoints; a stationary pan has less geometric information.
2. SpatialTwin decodes the actual video and stores up to 48 timestamped evidence frames across its duration locally. Start extraction to make a direct `gemini-4-argon` request. Native video is included up to 20 MiB; larger clips use the timestamped frames with an explicit sampling warning. A missing key or provider error is shown; it never substitutes a canned room.
3. Inspect the estimated shell and objects in orbit/top views. Select furniture to move, rotate or resize it; source frames remain available for comparison. Numeric editing also works independently of pointer interaction.
4. Save before calibration. Select a wall/object dimension and supply its actual measured length. An optional held-out measurement reports a residual without participating in the scale fit. Calibrating one dimension does not confirm the rest of the geometry.
5. Save/export your JSON. Reloading retains server-side scenes; importing JSON creates a new scene identity. Scene edits and long-running results carry revisions so stale changes can be rejected.
6. Optionally test a circular 2D agent's clearance. The same scene drives rendering and the deterministic geometry checks. Opening-width intervals use conservative and optimistic bounds with fixed opening offsets; unknown topology remains unresolved. Bounded furniture suggestions are final-layout candidates, not globally optimal or physically executed movements.

## Sample and verification

Generate a visibly labelled synthetic walkthrough:

```sh
.venv/bin/python -m tools.create_sample_video
```

The source video and held-out geometry record are written to ignored `runtime/roomlab/`. The reference geometry is not given to the provider and is not an extraction fallback. The sample exercises the integration; it does not establish accuracy on real room recordings.

```sh
.venv/bin/python -m pytest -q tests/roomlab
.venv/bin/python -m tools.export_contracts
cd frontend && npm test && npm run build
```

Backend tests explicitly inject fake perception where labelled; live verification uses the real model separately. See `VERIFICATION.txt` for actual observed results when available.

## Architecture and limits

`backend/app/roomlab/contracts.py` is canonical. `tools/export_contracts.py` generates the schema and frontend types. The provider emits a simpler draft which the application normalizes into the scene contract. `store.py` persists revisions atomically; `geometry.py`, `validation.py`, `reachability.py` and `optimizer.py` implement local checks. `media.py` decodes with the packaged FFmpeg executable. `video_extractor.py` performs direct model calls. The optional critic does not determine geometric truth.

World coordinates are metres, +Y up, and floor pairs are literal `[x,z]`. Positive yaw matches Three.js rotation about +Y. Object dimensions are named width/depth/height. Furniture centres render at height/2. The first version assumes one level room and floor-supported, upright boxes. Shell boundaries and object geometry inferred from video may be wrong even when internally valid. Atrium polygons are removed from both rendered floor and pathfinding. Interior partitions and railings are independent wall segments with attached openings. A topology-review flag blocks clearance if extraction repairs or omits structural geometry; clearing it requires visual review and correction. Floor voids, interior partitions and railings are supported; staircases remain fixed obstruction placeholders with an unsupported warning. No camera poses, dense metric reconstruction, stair travel, turning-radius model, headroom or survey accuracy are claimed.

Path statuses concern only the declared model and uncertainty bounds. A verified common path in conservative free space supports `ROBUST_PASS`; disconnection even in optimistic space supports `ROBUST_BLOCKED`. Failure of a sampled path search alone is `INCONCLUSIVE`. User-specified uncertainty is not calibrated probability. Any optional normal-distribution lesson is explicitly conditional on its assumed distribution.

Application state and source media stay in ignored `runtime/roomlab/`. Dependency environments/build products and credentials are also ignored. The tracked tree retains Git history and authorship through the parent project; dependency licences remain with their packages.

## Visual editing and review

The full-height two-column workspace keeps all project controls in the left
sidebar and the entire right column for the room. Illustrated category proxies
(stairs, furniture, plants and bicycles) fit inside the canonical object bounds;
they are visual aids, not recovered meshes. Switch to Bounding boxes to inspect
the solver's rectangular footprints. Camera-facing shell walls can be cut away
visually; partitions, openings and solver geometry retain their declared positions.
Door frames and glass are shown without inventing hinges or door swing states.

Select an object, choose Move or Rotate, then drag the in-canvas control. Translation
stays on the XZ floor and rotation on Y, with 5 cm / 5 degree snapping. Each gesture
is one undoable edit; Escape cancels an active gesture. Numeric dimension editing
remains in Objects. Save changes before requesting server-side analysis.

Analysis includes two separate optional actions:
- **Preview box separation** proposes bounded translations of movable overlapping
  boxes. Gold/green bounds show current/proposed poses in 3D and the SVG plan.
  Apply stages a local edit, with explicit geometry_fit provenance; save and check
  again. Coarse overlapping boxes may reflect intentional arrangements.
- **Review scene with Argon** sends a labelled plan, deterministic validation/solve
  result and up to six source JPEGs to Gemini. Findings are advisory and link to
  actual supplied frames. It never edits the scene or replaces solver verdicts.
  Missing/unknown citations, stale revisions, changed source evidence and invalid
  response receipts fail the review. Cancel is available; results are session-local.

Furniture search tries bounded single-object translations (up to 0.8 m), or selected
15/45/90 degree yaw changes, with a 120-candidate / 4-second budget. It verifies final
poses only; it does not plan a physical movement sweep or guarantee a global optimum.
One-anchor isotropic calibration and independent residual checks remain the scale
model; separate X/Z stretching is intentionally unsupported.

## Appearance controls

Objects → Appearance provides floor/default-wall and selected-object/wall controls.
Material choices, color swatches and an explicit Apply color action create undoable
presentation edits. Reset restores the estimate/default beneath a user override.
Appearance saves, exports, imports and reloads with the scene; it never changes
measurements, uncertainty, dimensions, calibration or source evidence.

New extractions may supply approximate colors and material hints with independent
appearance provenance and actual frame citations. Legacy scenes use neutral defaults
or narrowly scoped description hints, labelled heuristic. A marble counter or wood
stool does not determine the floor. Floor inference rejects negation, conflicts and
partial/mixed zones. Colors are model estimates under the video's lighting and white
balance, not pixel measurements. Procedural floor patterns have an illustrative
2-scene-unit repeat anchored to world X/Z. Textures can be disabled, and Bounds/SVG
views remain available. Glass wall framing requires material metadata or a disclosed
wall-specific hint/user choice; partition or railing role alone does not imply glass.
Doors retain frames only when their operating state is unknown.

Presentation fields and their provenance are excluded from `geometry_hash` at a
fixed revision. Scene identity, revision and geometric provenance remain included;
normal saves increment the revision and invalidate earlier solver receipts. Visual
reviews additionally bind a `render_hash`, covering appearance and floor-note hints,
so stale recolorings cannot publish results. This is not a cache that reuses reviews
across edits. Floors currently have one global finish; mixed-material zoning remains
unsupported. No external texture assets or arbitrary uploaded shaders are used.

Stair proxies climb the positive longer local footprint axis: +Z when depth is
longer, otherwise +X. Their treads and bounded sloped rail are illustrative;
neither the proxy step count nor its riser dimensions are recovered measurements.
Extraction prompts now specify that orientation explicitly. A clearly observed
static door leaf can be represented as a fixed `door_leaf` object box, with source
citations and pose uncertainty, so a closed/propped leaf is also an obstacle in
clearance checks. Unsupported leaf poses are not invented. This represents a video
snapshot, not articulated door operation or a guaranteed future door state.

## My rooms and extraction recovery

The left-side My rooms library lists actual local uploads, source thumbnails, saved
outputs, and build status. Search or filter Ready/Processing, open a room, or upload
another walkthrough without replacing the right-side canvas. Outputs from the same
upload are grouped; scene revisions do not create duplicate submissions. Unsaved
edits block room switches until saved or undone. Processing is indeterminate because
the provider does not report a reliable percentage.

Extraction jobs are journaled locally. Completed and failed results survive restarts;
interrupted jobs become retryable failures at server startup rather than pretending
to resume. Older failures from before journaling cannot be recovered. Visual-review
jobs remain in memory. Dense walkthrough extraction uses a 32,768-token output budget
and asks for at most 25 prominent objects/contiguous furniture groups with concise
notes. An incomplete response is rejected; no partial room is saved. Grouped proxies
and omitted small details still require source review. Reference-size presets are
examples and require actual measurement confirmation before applying scale.


Adaptive extraction: clips up to 60 seconds use one model request (16K output tokens
for clips up to 15 seconds, otherwise 32K). Longer clips are analyzed sequentially
in overlapping 60-second segments, followed by a visual/text synthesis pass.
An incomplete request retries once at 64K output tokens; truncated JSON is never
accepted. The job deadline scales with the number of segments (up to about 170
minutes in the worst case with all calls using their timeout/retry budget).
Ten-minute uploads retain up to 200 source frames, approximately one every three
seconds. Sampling can miss brief events. Longer video support does not turn this
single-level estimated scene editor into measured whole-building reconstruction:
unconnected rooms/floors and uncertain cross-segment alignment require review.

## Detailed reconstruction and geometry evidence

In **Source**, choose **Detailed** before creating a room. The server decodes a
bounded 2 fps candidate pool, selects up to 96 sharp views across the timeline with
perceptual duplicate filtering, attempts CPU COLMAP camera/point reconstruction,
and asks Gemini for an editable semantic draft. Stairs, doors, glass and uncertain
items receive additional source views around their timestamps (quarter-second
spacing, up to 48 detail frames, at up to 1600 px). A second model pass reinspects
those views and several wider views. It is rejected if it adds validation errors
or removes existing architecture/furniture. Topology review flags are preserved.
This is estimated source reinspection, not a proven accuracy increase. Initial and
refined drafts and diagnostics are saved under the ignored media runtime folder.

**Check footage** reports image-quality heuristics; a temporal coverage ratio is
not the percentage of room surfaces observed. **Reconstruct cameras** runs an
isolated, cancellable COLMAP CPU process. **Inspect 3D evidence** shows its largest
connected sparse component and camera positions. Automatically recovered sparse geometry is also available in the same inspector.
Geometry jobs/results survive reloads; interrupted jobs become retryable. Reprojection error is in image pixels,
not a dimensional error in meters. More frames can help matching but cannot resolve
invisible, reflective or textureless surfaces reliably.

For a geometry-backed editable proposal, select at least three actual floor
landmarks in perimeter order, supply the measured first-edge length, confirm one
floor level/no drop-offs, and create a **separate floor proposal**. Non-coplanar or
crossing outlines are rejected. Wall height is an explicit estimate. After that,
select at least four object landmarks including sides/top and use **Fit furniture**
to create a separate OBB proposal in the same measured coordinate frame. Missing
surfaces may exceed fitted bounds; the displayed margin is a heuristic. A review
flag remains until the user resolves topology, openings and missing furniture.
No convex-hull floor, walking-speed scale, gravity, or automatic alignment between
Gemini's room and the sparse cloud is assumed. This implementation is sparse SfM
plus editable primitives, not a dense textured mesh or Gaussian splat.

**Import RoomPlan JSON** accepts a single-level CapturedRoom export with rigid
column-major transforms and a closed wall outline. It imports dimensioned walls,
attached openings and object boxes as sensor estimates, with a topology review
flag and no fabricated video evidence or calibration. USDZ, curved/nonuniform walls,
multiple stories, disconnected rooms and conflicting floor boundaries are rejected
for explicit conversion. Native device capture itself is not part of the web app.
The importer has fixture/API coverage; a real device export is still needed to
verify compatibility with the particular iOS/exporter version being used.

In **Analysis → Check actual dimensions**, enter independent measured dimensions.
The app reports per-reference error, MAE and maximum error; the API additionally
provides RMSE, angular checks and object-center distances. The scale-fitting anchor
is excluded from validation statistics. Reports survive reloads and recompute against
the current revision without changing geometry. Do not use example furniture sizes
as measured validation data.

References: [COLMAP capture guidance](https://colmap.github.io/tutorial),
[PyCOLMAP](https://colmap.github.io/pycolmap/index.html),
[Gemini video processing](https://ai.google.dev/gemini-api/docs/video-understanding.md),
[Apple RoomPlan](https://developer.apple.com/augmented-reality/roomplan/).

Detailed extraction can now consume up to six model-directed inspection requests.
Only known scene elements and finite timestamps inside the uploaded clip are accepted;
requests are deduplicated and share the existing eight-target/48-detail-frame budget
with validation-driven and heuristic fallback. The refiner receives the initial BEV,
validation diagnostics, wider source views and targeted detail views. This is one
bounded model-directed reinspection pass, not an open-ended autonomous tool loop.

The Source panel shows persisted processing-stage events. Completion is recorded
only after the room has been saved; failures/cancellation retain their terminal
stages. Added bed, shelf, appliance and TV proxies remain inside canonical OBBs.
Category labels take precedence over incidental words in object names.
