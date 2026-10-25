"""Deterministic 2D Bird's-Eye View (BEV) PNG renderer for RoomLab scenes.

Renders `RoomSceneV1` in top-down plan coordinates (`+X` right/east, `+Z` down/south)
with floor polygon, non-walkable `floor_voids`, role-colored walls (`shell`, `partition`,
`railing`), door/window openings, oriented object footprints (`OBB`) with forward-facing
direction ticks and canonical IDs, scale legend, and a solver path
ONLY when `solve.scene_revision == scene.scene_revision` and
`solve.geometry_hash == geometry_hash(scene)`.
"""
from __future__ import annotations

import io
import math
from PIL import Image, ImageDraw, ImageFont, ImageColor

from backend.app.roomlab.contracts import RoomObject, RoomSceneV1, SolveResult, geometry_hash

CANVAS_WIDTH = 960
CANVAS_HEIGHT = 760
MARGIN_PX = 68


def _rotated_footprint_pts(obj: RoomObject) -> list[tuple[float, float]]:
    ang = math.radians(obj.yaw_deg)
    c, s = math.cos(ang), math.sin(ang)
    cx, cz = obj.center[0], obj.center[1]
    hw, hd = obj.width_m * 0.5, obj.depth_m * 0.5
    corners = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
    return [(cx + c * dx + s * dz, cz - s * dx + c * dz) for dx, dz in corners]


def _appearance_color(appearance, fallback):
    choice=appearance.user_override or appearance if appearance else None
    return (*ImageColor.getrgb(choice.color),255) if choice and choice.color else fallback


def render_scene_preview(
    scene: RoomSceneV1,
    solve: SolveResult | None = None,
) -> bytes:
    """Render a deterministic PNG top-down plan of `scene` and optional hash-matched `solve`."""
    img = Image.new("RGB", (CANVAS_WIDTH, CANVAS_HEIGHT), (246, 246, 242))
    draw = ImageDraw.Draw(img, "RGBA")
    font = ImageFont.load_default()

    # Collect world bounds across floor, walls, voids, and objects
    xs: list[float] = [p[0] for p in scene.floor]
    zs: list[float] = [p[1] for p in scene.floor]
    for w in scene.walls:
        xs.extend([w.start[0], w.end[0]])
        zs.extend([w.start[1], w.end[1]])
    for v in scene.floor_voids:
        xs.extend(p[0] for p in v.polygon)
        zs.extend(p[1] for p in v.polygon)
    for o in scene.objects:
        for px, pz in _rotated_footprint_pts(o):
            xs.append(px)
            zs.append(pz)

    min_x = min(xs) if xs else -5.0
    max_x = max(xs) if xs else 5.0
    min_z = min(zs) if zs else -5.0
    max_z = max(zs) if zs else 5.0

    span_x = max(1.0, max_x - min_x)
    span_z = max(1.0, max_z - min_z)
    mid_x = (min_x + max_x) * 0.5
    mid_z = (min_z + max_z) * 0.5

    usable_w = CANVAS_WIDTH - 2 * MARGIN_PX
    usable_h = CANVAS_HEIGHT - 2 * MARGIN_PX - 44
    scale = min(usable_w / (span_x * 1.12), usable_h / (span_z * 1.12))
    center_px_x = CANVAS_WIDTH * 0.5
    center_px_y = (CANVAS_HEIGHT - 36) * 0.5 + 14

    def to_px(wx: float, wz: float) -> tuple[float, float]:
        return (
            round(center_px_x + (wx - mid_x) * scale, 2),
            round(center_px_y + (wz - mid_z) * scale, 2),
        )

    # Bound grid work even for imported scenes with very large coordinates.
    grid_step = max(1.0, 10.0 ** math.floor(math.log10(max(span_x, span_z) / 40.0)))
    # 1. Background coordinate grid (normally 1m intervals)
    grid_start_x = math.floor(min_x / grid_step) - 1
    grid_end_x = math.ceil(max_x / grid_step) + 1
    for gx in range(grid_start_x, grid_end_x + 1):
        x0, y0 = to_px(float(gx) * grid_step, min_z - 1.0)
        x1, y1 = to_px(float(gx) * grid_step, max_z + 1.0)
        draw.line([x0, y0, x1, y1], fill=(228, 231, 223, 255), width=1)

    grid_start_z = math.floor(min_z / grid_step) - 1
    grid_end_z = math.ceil(max_z / grid_step) + 1
    for gz in range(grid_start_z, grid_end_z + 1):
        x0, y0 = to_px(min_x - 1.0, float(gz) * grid_step)
        x1, y1 = to_px(max_x + 1.0, float(gz) * grid_step)
        draw.line([x0, y0, x1, y1], fill=(228, 231, 223, 255), width=1)

    # 2. Outer floor polygon
    if len(scene.floor) >= 3:
        floor_pts = [to_px(p[0], p[1]) for p in scene.floor]
        draw.polygon(floor_pts, fill=_appearance_color(scene.floor_appearance,(231, 234, 225, 255)), outline=(156, 166, 148, 255))

    # 3. Non-walkable floor voids (atrium cutouts)
    for void in scene.floor_voids:
        if len(void.polygon) >= 3:
            v_pts = [to_px(p[0], p[1]) for p in void.polygon]
            draw.polygon(v_pts, fill=(246, 240, 228, 255), outline=(185, 140, 72, 255))
            for i in range(len(v_pts)):
                p1 = v_pts[i]
                p2 = v_pts[(i + 1) % len(v_pts)]
                draw.line([p1, p2], fill=(185, 140, 72, 255), width=3)
            vcx = sum(p[0] for p in void.polygon) / len(void.polygon)
            vcz = sum(p[1] for p in void.polygon) / len(void.polygon)
            lx, ly = to_px(vcx, vcz)
            draw.text((lx - 36, ly - 6), f"VOID: {void.id}", fill=(146, 94, 24, 255), font=font)

    # 4. Walls (shell, partition, railing) + Openings
    wall_map = {w.id: w for w in scene.walls}
    for w in scene.walls:
        p1 = to_px(w.start[0], w.start[1])
        p2 = to_px(w.end[0], w.end[1])
        if w.role == "railing":
            color = (182, 142, 84, 255)
            width_px = max(2, int(round(w.thickness_m * scale)))
        elif w.role == "partition":
            color = (94, 148, 132, 255)
            width_px = max(3, int(round(w.thickness_m * scale)))
        else:
            color = (108, 118, 104, 255)
            width_px = max(4, int(round(w.thickness_m * scale)))
        color=_appearance_color(w.appearance or scene.wall_appearance,color)
        draw.line([p1, p2], fill=color, width=width_px)

        mx, my = (p1[0] + p2[0]) * 0.5, (p1[1] + p2[1]) * 0.5
        w_len = math.dist(w.start, w.end)
        draw.text(
            (mx - 24, my - 10),
            f"{w.id} ({w_len:.1f}m)",
            fill=(55, 65, 58, 255),
            font=font,
        )

    for op in scene.openings:
        w = wall_map.get(op.wall_id)
        if w is None:
            continue
        w_len = math.dist(w.start, w.end)
        if w_len < 1e-5:
            continue
        t0 = max(0.0, min(1.0, op.offset_m / w_len))
        t1 = max(0.0, min(1.0, (op.offset_m + op.width_m) / w_len))
        ax = w.start[0] + (w.end[0] - w.start[0]) * t0
        az = w.start[1] + (w.end[1] - w.start[1]) * t0
        bx = w.start[0] + (w.end[0] - w.start[0]) * t1
        bz = w.start[1] + (w.end[1] - w.start[1]) * t1
        pa = to_px(ax, az)
        pb = to_px(bx, bz)
        op_color = (56, 152, 112, 255) if op.kind in ("door", "passage") else (112, 164, 185, 255)
        draw.line([pa, pb], fill=op_color, width=max(5, int(round(w.thickness_m * scale)) + 2))
        omx, omy = (pa[0] + pb[0]) * 0.5, (pa[1] + pb[1]) * 0.5
        draw.text((omx - 18, omy + 4), f"{op.id}", fill=(36, 92, 68, 255), font=font)

    # 5. Objects (oriented footprints, uncertainty halos, forward orientation tick, ID labels)
    for obj in scene.objects:
        corners_world = _rotated_footprint_pts(obj)
        corners_px = [to_px(x, z) for x, z in corners_world]
        is_fixed = not obj.movable
        fill_rgba = (196, 174, 136, 195) if is_fixed else (154, 179, 160, 195)
        outline_rgba = (118, 96, 62, 255) if is_fixed else (74, 108, 86, 255)
        draw.polygon(corners_px, fill=_appearance_color(obj.appearance,fill_rgba), outline=outline_rgba)

        # Orientation tick from center toward local +X
        ang = math.radians(obj.yaw_deg)
        c, s = math.cos(ang), math.sin(ang)
        cx, cz = obj.center[0], obj.center[1]
        fx = cx + c * (obj.width_m * 0.42)
        fz = cz - s * (obj.width_m * 0.42)
        draw.line([to_px(cx, cz), to_px(fx, fz)], fill=outline_rgba, width=2)

        ocx, ocy = to_px(cx, cz)
        draw.text((ocx - 24, ocy - 6), f"{obj.id}", fill=(32, 42, 36, 255), font=font)

    # 6. Hash-matched solver path (drawn ONLY if revision and geometry_hash match)
    current_hash = geometry_hash(scene)
    path_matched = (
        solve is not None
        and solve.scene_revision == scene.scene_revision
        and solve.geometry_hash == current_hash
    )
    if path_matched and solve is not None and len(solve.path) >= 2:
        path_px = [to_px(p[0], p[1]) for p in solve.path]
        path_color = (34, 164, 92, 255) if solve.status == "ROBUST_PASS" else (217, 119, 6, 255)
        for i in range(len(path_px) - 1):
            draw.line([path_px[i], path_px[i + 1]], fill=path_color, width=4)
        sx, sy = path_px[0]
        gx, gy = path_px[-1]
        draw.ellipse([sx - 5, sy - 5, sx + 5, sy + 5], fill=(22, 163, 74, 255))
        draw.ellipse([gx - 5, gy - 5, gx + 5, gy + 5], fill=(2, 132, 199, 255))

    # 7. Header, compass (+X East, +Z South), and 1m scale bar legend
    cal_tag = (
        f"Calibrated x{scene.calibration.scale_factor:.3f} ({scene.calibration.anchor_id}={scene.calibration.measured_m:.2f}m)"
        if scene.calibration
        else "Uncalibrated (model_estimate)"
    )
    header_text = (
        f"RoomLab BEV Plan | {scene.name} | {scene.scene_id} rev={scene.scene_revision} | {cal_tag}"
    )
    draw.rectangle([0, 0, CANVAS_WIDTH, 28], fill=(234, 237, 229, 255))
    draw.text((14, 8), header_text[:125], fill=(38, 46, 40, 255), font=font)

    # 1.0m scale bar at bottom-left
    bar_m = 10.0 ** math.floor(math.log10(100.0 / scale))
    bar_px = scale * bar_m
    bx0, by0 = 20.0, float(CANVAS_HEIGHT - 18)
    draw.line([bx0, by0, bx0 + bar_px, by0], fill=(45, 55, 48, 255), width=3)
    draw.line([bx0, by0 - 4, bx0, by0 + 4], fill=(45, 55, 48, 255), width=2)
    draw.line([bx0 + bar_px, by0 - 4, bx0 + bar_px, by0 + 4], fill=(45, 55, 48, 255), width=2)
    draw.text((bx0 + bar_px + 8, by0 - 6), f"{bar_m:g}m estimated | +X right, +Z down (Y-up)", fill=(45, 55, 48, 255), font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    return buf.getvalue()
