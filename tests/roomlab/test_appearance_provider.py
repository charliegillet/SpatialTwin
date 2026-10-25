"""Offline unit tests for provider appearance normalization, legacy backward-compatibility,
citation filtering, floor-specific note inference, and geometry invariance.
"""
from __future__ import annotations

from backend.app.roomlab.contracts import RoomSceneV1, geometry_hash, render_hash
from backend.app.roomlab.provider_schema import (
    ProviderRoomPayload,
    infer_floor_material_from_floor_notes,
    normalize_hex_color,
    normalize_material_name,
    normalize_provider_payload,
    provider_response_json_schema,
)


def _legacy_payload_dict() -> dict:
    return {
        "name": "Legacy Mezzanine Room",
        "wall_height_m": 3.0,
        "wall_thickness_m": 0.15,
        "floor_vertices": [
            {"x_m": -4.0, "z_m": -3.0},
            {"x_m": 4.0, "z_m": -3.0},
            {"x_m": 4.0, "z_m": 3.0},
            {"x_m": -4.0, "z_m": 3.0},
        ],
        "floor_voids": [],
        "interior_walls": [
            {
                "id": "wall-glass-1",
                "role": "partition",
                "start_x_m": 0.5,
                "start_z_m": -3.0,
                "end_x_m": 0.5,
                "end_z_m": 3.0,
                "height_m": 3.0,
                "thickness_m": 0.12,
                "visibility": "observed",
                "evidence_frame_ids": ["frame-001"],
                "note": "Bronze framed glass storefront partition",
            }
        ],
        "openings": [
            {
                "id": "door-1",
                "wall_id": "wall-glass-1",
                "kind": "door",
                "offset_m": 2.0,
                "width_m": 1.2,
                "height_m": 2.2,
                "sill_m": 0.0,
                "visibility": "observed",
                "evidence_frame_ids": ["frame-001"],
            }
        ],
        "objects": [
            {
                "id": "counter-1",
                "label": "Marble Reception Counter",
                "category": "counter",
                "x_m": 2.2,
                "z_m": 0.0,
                "width_m": 0.9,
                "depth_m": 2.4,
                "height_m": 1.1,
                "yaw_deg": 0.0,
                "movable": False,
                "uncertainty_radius_m": 0.1,
                "visibility": "observed",
                "evidence_frame_ids": ["frame-002"],
                "note": "White marble counter with dark wood base",
            },
            {
                "id": "stool-1",
                "label": "Wooden Stool",
                "category": "stool",
                "x_m": 1.2,
                "z_m": -1.2,
                "width_m": 0.4,
                "depth_m": 0.4,
                "height_m": 0.48,
                "yaw_deg": 0.0,
                "movable": True,
                "uncertainty_radius_m": 0.1,
                "visibility": "observed",
                "evidence_frame_ids": ["frame-001"],
                "note": "Oak wood stool near window",
            },
        ],
        "notes": ["Scale uncalibrated; marble reception counter and wood stools visible."],
    }


def test_hex_and_material_normalizers() -> None:
    assert normalize_hex_color("#ABC") == "#aabbcc"
    assert normalize_hex_color(" #EF801a ") == "#ef801a"
    assert normalize_hex_color("not-a-color") is None
    assert normalize_hex_color("#12345") is None
    assert normalize_hex_color("") is None

    assert normalize_material_name("Terrazzo") == "terrazzo"
    assert normalize_material_name(" MARBLE ") == "marble"
    assert normalize_material_name("foliage") == "foliage"
    assert normalize_material_name("plush-velvet") == "unknown"
    assert normalize_material_name(None) == "unknown"


def test_legacy_payload_without_appearance_keeps_none_and_does_not_leak_object_materials_to_floor() -> None:
    raw = _legacy_payload_dict()
    parsed = ProviderRoomPayload.model_validate(raw)
    draft, _ = normalize_provider_payload(parsed, {"frame-001", "frame-002"})

    # Notes and object labels mention "marble counter" and "wood stools", NOT a marble/wood floor
    assert draft.floor_appearance is None
    assert draft.wall_appearance is None
    for w in draft.walls:
        assert w.appearance is None
    for o in draft.objects:
        assert o.appearance is None


def test_floor_specific_note_inference_never_triggers_on_counter_or_stool_notes() -> None:
    # Furniture / counter / partition notes -> unknown
    assert infer_floor_material_from_floor_notes(
        ["Marble reception counter and oak wood stools sit behind a bronze partition."]
    ) == "unknown"
    assert infer_floor_material_from_floor_notes(
        ["Floor-to-ceiling wooden partition divides the space."]
    ) == "unknown"

    # Negation -> unknown
    assert infer_floor_material_from_floor_notes(
        ["Floor is not wood."]
    ) == "unknown"
    assert infer_floor_material_from_floor_notes(
        ["The flooring is neither marble nor tile."]
    ) == "unknown"

    # Mixed / multiple materials -> unknown
    assert infer_floor_material_from_floor_notes(
        ["Floor is mixed wood and stone."]
    ) == "unknown"
    assert infer_floor_material_from_floor_notes(
        ["Floor transitions from terrazzo to carpet in the lounge."]
    ) == "unknown"

    # Single partial zone ('terrazzo landing' / 'terrazzo floor on the landing') or multiple zones -> unknown
    assert infer_floor_material_from_floor_notes(
        ["Mezzanine has a terrazzo landing overlooking the atrium and a carpeted lounge."]
    ) == "unknown"
    assert infer_floor_material_from_floor_notes(
        ["A terrazzo landing overlooks the lower atrium."]
    ) == "unknown"
    assert infer_floor_material_from_floor_notes(
        ["Mezzanine landing has a polished terrazzo floor overlooking the atrium."]
    ) == "unknown"

    # Conflicting floor statements across notes -> unknown
    assert infer_floor_material_from_floor_notes(
        ["The floor is polished terrazzo.", "The floor is hardwood."]
    ) == "unknown"

    # Unambiguous explicit whole-floor statements -> inferred material
    assert infer_floor_material_from_floor_notes(
        ["The floor is polished terrazzo throughout the room."]
    ) == "terrazzo"
    assert infer_floor_material_from_floor_notes(
        ["Room features a hardwood floor with a marble coffee table."]
    ) == "wood"


def test_provider_appearance_normalization_citations_and_geometry_invariance() -> None:
    schema = provider_response_json_schema()
    assert "floor_color" in schema["properties"]
    assert "floor_material" in schema["properties"]
    assert "wall_color" in schema["properties"]
    assert "wall_material" in schema["properties"]

    legacy_parsed = ProviderRoomPayload.model_validate(_legacy_payload_dict())
    legacy_draft, _ = normalize_provider_payload(legacy_parsed, {"frame-001", "frame-002"})

    rich_dict = _legacy_payload_dict()
    rich_dict.update(
        {
            "floor_color": "#CBC6BD",
            "floor_material": "terrazzo",
            "floor_evidence_frame_ids": ["frame-001", "invented-frame-999"],
            "wall_color": "#ede",
            "wall_material": "paint",
            "wall_evidence_frame_ids": ["frame-002", "hallucinated-777"],
        }
    )
    rich_dict["interior_walls"][0]["color"] = "#7B5A32"
    rich_dict["interior_walls"][0]["material"] = "glass"
    rich_dict["objects"][0]["color"] = "#ECE8E1"
    rich_dict["objects"][0]["material"] = "marble"
    rich_dict["objects"][1]["color"] = "invalid-hex"
    rich_dict["objects"][1]["material"] = "unsupported-material"

    rich_parsed = ProviderRoomPayload.model_validate(rich_dict)
    rich_draft, warnings = normalize_provider_payload(rich_parsed, {"frame-001", "frame-002"})

    # 1. Floor appearance normalized, exact citations only, user_override None
    assert rich_draft.floor_appearance is not None
    assert rich_draft.floor_appearance.color == "#cbc6bd"
    assert rich_draft.floor_appearance.material == "terrazzo"
    assert rich_draft.floor_appearance.provenance.source == "model_estimate"
    assert rich_draft.floor_appearance.provenance.evidence_frame_ids == ["frame-001"]
    assert rich_draft.floor_appearance.user_override is None

    # 2. Global wall appearance normalized and propagated to outer shell walls
    assert rich_draft.wall_appearance is not None
    assert rich_draft.wall_appearance.color == "#eeddee"
    assert rich_draft.wall_appearance.material == "paint"
    assert rich_draft.wall_appearance.provenance.source == "model_estimate"
    assert rich_draft.wall_appearance.provenance.evidence_frame_ids == ["frame-002"]
    assert rich_draft.wall_appearance.user_override is None

    shell_walls = [w for w in rich_draft.walls if w.role == "shell"]
    assert len(shell_walls) == 4
    for sw in shell_walls:
        assert sw.appearance is not None
        assert sw.appearance.color == "#eeddee"
        assert sw.appearance.material == "paint"
        assert sw.appearance.user_override is None

    # 3. Interior wall has its own individual appearance
    part_wall = next(w for w in rich_draft.walls if w.id == "wall-glass-1")
    assert part_wall.appearance is not None
    assert part_wall.appearance.color == "#7b5a32"
    assert part_wall.appearance.material == "glass"
    assert part_wall.appearance.provenance.source == "model_estimate"
    assert part_wall.appearance.provenance.evidence_frame_ids == ["frame-001"]
    assert part_wall.appearance.user_override is None

    # 4. Object with valid color/material vs invalid color/material
    counter = next(o for o in rich_draft.objects if o.id == "counter-1")
    assert counter.appearance is not None
    assert counter.appearance.color == "#ece8e1"
    assert counter.appearance.material == "marble"
    assert counter.appearance.provenance.source == "model_estimate"
    assert counter.appearance.provenance.evidence_frame_ids == ["frame-002"]
    assert counter.appearance.user_override is None

    stool = next(o for o in rich_draft.objects if o.id == "stool-1")
    assert stool.appearance is None

    assert any("Dropped unknown evidence frame IDs on floor_appearance" in w for w in warnings)
    assert any("Dropped unknown evidence frame IDs on wall_appearance" in w for w in warnings)

    # 5. Geometry coordinates and geometry_hash are 100% invariant when appearance is added
    scene_legacy = RoomSceneV1(scene_id="s-1", **legacy_draft.model_dump())
    scene_rich = RoomSceneV1(scene_id="s-1", **rich_draft.model_dump())
    assert geometry_hash(scene_legacy) == geometry_hash(scene_rich)
    assert render_hash(scene_legacy) != render_hash(scene_rich)
