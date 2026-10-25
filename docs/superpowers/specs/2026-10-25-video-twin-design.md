# Video walkthrough → furnished twin

Date: 2026-10-25 · Branch: `charlie` · Status: built on `charlie` (the user asked for no further questions; open points were settled as builder calls, listed below)

## Intent

Today "Build from a drawing" turns a photo, sketch or PDF of a floor plan into a checked venue twin. Once accepted, it behaves like building-v2: you drop hazards, doors close or open, exits turn red or green, and routes re-plan.

This adds a fourth source, **Video**. Someone films a walkthrough of a space on their phone. It becomes the same kind of twin, so hazards, exits, doors and routes all work. It also looks like the real space: floors and walls take the colours from the video, and the furniture seen in it appears as simple 3D models. The look matches the furniture rendering already built on the video branch (`charlie-video`, commit `6176fe4`); we reuse that look, not that branch's separate RoomLab app.

## Goals

1. A **Video** option sits next to Photo of a posted map / Sketch / PDF in the Build-from-a-drawing panel. Picking a file starts the reading straight away, as the other options do.
2. Gemini reads the whole video and proposes the venue draft: rooms, doors and exits, in the same draft shape real2sim already uses. It also proposes the appearance:
   - per room: wall colour, floor colour, floor material (wood / tile / carpet / stone / concrete / terrazzo / unknown);
   - furniture: label, category, position, footprint, height, rotation, colour.
3. The draft then goes through the existing pipeline unchanged: salvage/repair, local graph checks, critique rounds if the photo path uses them, review, and accept. Failed checks are explained as they are today. A failed or unavailable live call never turns into a fixture or an invented building.
4. **A video of a single room works.** One room, one or more exits, zero inside doors. The checks, door planner, playback and 3D view all handle it. Hazards can be placed and the result shows who gets out and through which exit.
5. **Look C** in the accepted twin's 3D view (the same `TwinScene3D` used for building-v2):
   - room floors use their floor colour and material texture, and walls use their wall colour;
   - furniture is drawn with the video branch's models (`RoomModels.tsx`: sofa, chair, stool, table, desk, shelf, bed, bin, plant, generic, …), each in its colour;
   - everything else stays as today: hazard placement, door states, exit signs, routes, playback, labels and the Labels toggle.
6. After reading, the review step offers **Accept** and **Edit** side by side. **Edit is optional**; Accept never requires editing first.
7. **Edit = furniture only**, like the video branch's editor: add a piece (pick a kind), select it, move it, resize it, rotate it, recolour it, relabel it, delete it. Editing works on one room at a time (pick a room, then edit its furniture), which the user said is fine. Saving the edits keeps them with the draft/venue, and Accept uses the edited furniture.

## Non-goals

- Editing rooms, walls, doors or exits by hand. The video branch can edit walls and openings; that is out of scope here.
- Furniture affecting evacuation. Furniture is **for looks only**: it never blocks, slows or re-routes anyone, and never changes a plan or the venue's geometry revision.
- Porting RoomLab as a separate app or route, or its calibration, clearance or reachability panels.
- Real measurement or scale calibration from the video.

## Anti-goals (a failure even if it technically works)

- **No "these sizes are estimates" note** or similar disclaimer anywhere in the UI. The user explicitly does not want the clutter. The existing provenance chip (Live Gemini / Fixture / Saved run, as on every run today) stays, since that labelling is already how the app works.
- A video upload that falls back to a made-up or fixture building when Gemini fails or no key is set.
- Furniture changing who gets out, or a furniture edit invalidating or re-running the door plan.
- Breaking anything about the photo / sketch / PDF paths or building-v2.

## Constraints

- **Video limits** (taken from the video branch's `backend/app/roomlab/media.py`): MP4, WebM or MOV; at most 120 s; at most 256 MB. Duration is measured by decoding with the bundled ffmpeg (`imageio-ffmpeg`), not taken from the browser.
- The upload path must cope with large files. The current draft route takes a base64 image in a JSON body, which is not suitable for hundreds of MB. Video needs a multipart or streamed upload (the video branch uses `python-multipart`). Both `python-multipart` and `imageio-ffmpeg` are on the video branch but not in main's `requirements.txt`.
- Gemini model and client follow what real2sim already uses (`gemini-4-argon`, the Interactions API, receipts). The video branch's `video_extractor.py` shows a working inline-video call (≤ 20 MB inline) and its prompt/schema asks for colours and objects; reuse that knowledge for the prompt and schema fields.
- `VenueV2` (`backend/app/venues/model.py`) is a strict pydantic model. Appearance and furniture are added as one **optional** `appearance` field that existing venues (building-v2, photo drafts, saved runs) do not have. The planner, checker and graph checks never read it, and the managed-agent sandbox gets the venue without it (`planning_json`). It *is* part of the `geometry_revision` hash: the registry refuses a changed venue body under a reused revision, and furniture is only edited before Accept, so no stored plan can go stale.
- The repo's invariants in `AGENTS.md` / `README.md` still apply: AI proposes, local checks decide, a human accepts; honest provenance; every occupant accounted for.
- `GEMINI_API_KEY` is set in the main checkout's `.env`, so live runs are possible locally.

## Decided by the user

- Look C: colours from the video plus furniture models.
- Single-room videos must work fully.
- No estimate disclaimer in the UI.
- Accept and Edit are both offered after reading, and Edit is optional.
- Edit covers furniture and similar objects, like the video branch, one room at a time.

## My calls (the user can override)

- Video goes through the **real2sim draft pipeline**, not RoomLab, so the result is a normal planable venue.
- Furniture models and floor textures are ported from `charlie-video`'s `frontend/src/roomlab/RoomModels.tsx`; there is no new 3D art.
- A room with no colour from Gemini falls back to today's dark twin look; furniture with no colour uses the video branch's kind-based or word-based colour guess.
- Photo, sketch and PDF drafts can carry the same optional appearance fields, but this work doesn't ask Gemini for them on those paths. Edit furniture is offered on every ready draft, not only video ones.
- **Edit happens before Accept only.** Edits are stored on the draft as a new revision (`PUT /api/real2sim/drafts/{id}/furniture`, compare-and-set like Accept) and applied to the venue Accept stores. An accepted venue is never edited in place.
- **Look C recolours today's twin** rather than porting the video branch's full-height walls: the 1.2 m cutaway walls, doors, signs, labels and camera stay. Floors take each room's colour and material texture; walls take the most common room wall colour; lighting turns neutral; hazard tints, occupant fills and room labels are strengthened so they read on light floors.
- **Video reaches Gemini inline**: ffmpeg measures the real duration (at most 120 s) and re-encodes once to a small silent H.264 MP4 (at most 640 px, a few frames per second, under 18 MB), sent as one `video` part sampled at 1 frame/s. Coordinates are on a square top-down plan canvas; scale comes from Gemini's `video_estimate` reference (a wall it judged), and the overlay is drawn on a blank canvas, as for a PDF.
- **Upload** is the raw file as the request body (`POST /api/real2sim/drafts/video`), streamed to disk, so no multipart dependency was added; `imageio-ffmpeg` was.

## Left to the builder

- How the video reaches Gemini: inline when small, the Files API when large, or extracted frames as the video branch does. The choice must respect the limits above and keep provenance honest.
- What the review step shows for a video in place of the photo overlay: a key frame, the top-down render, or both.
- Exact API shape for the upload and for saving furniture edits (a new revision of the draft, using the existing revision/conflict pattern, is the natural fit).
- Editor UI details inside the existing panel style: drag in the 3D view or number fields. The video branch does both.
- Test strategy. Fixtures for tests are fine as long as they are labelled as fixtures and never shown as live results.

## Update: RoomLab's reading (same prompt, schema, inputs)

At the user's request the video path now reads a walkthrough exactly as the RoomLab branch does, then converts the
room into a planable venue:

- **Reading** (`backend/app/ai/real2sim/room/`, ported unchanged from `charlie-video`): RoomLab's system prompt, provider
  schema and `normalize_provider_payload`; input = RoomLab's prompt naming every keyframe, the clip inline when it is at
  most 20 MB (otherwise a small re-encoded copy, where RoomLab sent frames only), and up to 48 timestamped keyframes
  (RoomLab's schedule, at most 960 px); thinking low, 8192 output tokens. The call still streams so any thought
  summaries show, and the receipt, model check and error codes are the real2sim ones.
- **Conversion** (`backend/app/venues/room_compiler.py`): turn the room so its main walls lie on the axes; cluster and
  round coordinates to 0.1 m; floor minus voids; split along every interior wall (partition, railing) that crosses it;
  cut through a void inside a room and join the halves with a wide open passage (it is open floor); trace any slanted
  room on a 0.1 m grid. Doors and passages on an interior wall between two rooms become doors (one per room pair, the
  widest); on the outer shell, exits. Windows, glass partitions and railings are kept as looks
  (`appearance.features`). People, rates and the horizon use the floor-plan compiler's declared defaults.
- **Review**: the keyframes are the evidence picture (where a drawing shows its overlay); there is no critique round
  (it corrects a drawn plan against its overlay); the controllable-door choices are the compiled doors (D1..); rooms
  cannot be left out (that is for drawn plans).
- **Live check** (the lobby walkthrough): 54 s, 31,708 tokens; RoomLab's reading (mezzanine landing + glass-fronted
  lobby, atrium void, glass partition with door and panels, railings, 9 objects) compiled to 2 rooms, 1 door and
  3 exits with no check errors; a fire in the lobby re-planned through the landing.
