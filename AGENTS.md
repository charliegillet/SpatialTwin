# RoomLab working agreement

The human approved a clean, isolated video-to-editable-room product on this branch. These instructions replace the inherited board/evacuation application instructions. Do not modify the separate SpatialTwin main checkout or its running server.

Codex owns root manifests, lockfiles, entrypoints, canonical contracts, generated types, routes/store, geometry/uncertainty/pathfinding, and integration tests. Hermes owns leaf frontend files in frontend/src/roomlab (except contracts.generated.ts and api.ts), and backend/app/roomlab/{media,video_extractor,provider_schema,provider_prompts,agent_critic}.py plus provider/media tests. Request shared interface changes; do not edit another owner's files concurrently.

Integration handoff: Hermes reported its leaf modules complete. Codex now owns ALL frontend files for final integration/browser fixes. Hermes retains only backend provider/media modules and their tests. Older queued frontend feedback messages are superseded by this handoff; do not modify frontend while Codex is verifying it.

One canonical scene drives rendering and collision. Model extraction is an estimated draft, never a measured reconstruction. One scale reference confirms only that dimension. No fabricated provider success, fallback scene disguised as extraction, inferred confidence disguised as calibrated probability, or global optimality claims for bounded searches. Preserve source evidence and revisions. Credentials stay server-side; runtime and environments are ignored. No hardware modules or legacy application routes belong in this branch.

V2 APPROVED OWNERSHIP: Codex owns all shared contracts, API/routes, store, optimizer/overlap repair, UI integration, RoomCanvas3D, transform/preview controls, workspace/styles and manifests. Hermes owns ONLY new RoomObjectVisual.tsx, OpeningVisual.tsx, visualBounds helpers/tests, scene_preview.py, agent_critic.py, critic_prompts.py and test_scene_preview_and_critic.py. Do not edit another owner's files. Earlier provider/media assignments are superseded for this iteration. Codex commits after integration.

V2 FINAL HANDOFF: Hermes completed its leaf modules and is hands-off. Codex owns all files for final edge fixes, verification and commit.
