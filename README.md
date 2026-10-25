# RoomLab

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

1. Upload an MP4, WebM or MOV, at most 120 seconds and 256 MiB. Walk with overlapping viewpoints; a stationary pan has less geometric information.
2. RoomLab decodes the actual video and stores up to 48 timestamped evidence frames across its duration locally. Start extraction to make a direct `gemini-4-argon` request. Native video is included up to 20 MiB; larger clips use the timestamped frames with an explicit sampling warning. A missing key or provider error is shown; it never substitutes a canned room.
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
