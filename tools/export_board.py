"""
Board Schematic Exporter
Generates printable SVG visualization from reviewed venue and device configuration.
"""

import json
from pathlib import Path


def export_svg(venue_path: str, output_path: str) -> None:
    with open(venue_path, "r") as f:
        data = json.load(f)

    width = 800
    height = 600

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" style="background-color: #0b1120; font-family: monospace;">',
        '<!-- SpatialTwin Board Schematic -->',
        f'<rect x="20" y="20" width="{width - 40}" height="{height - 40}" fill="#0f172a" stroke="#334155" stroke-width="2" rx="8"/>',
        f'<text x="40" y="55" fill="#f8fafc" font-size="20" font-weight="bold">SpatialTwin Tabletop Twin — {data.get("geometry_revision")}</text>',
        f'<text x="40" y="80" fill="#94a3b8" font-size="12">{data.get("provenance")}</text>',
    ]

    # Draw zones
    for zone in data.get("zones", []):
        z_id = zone["id"]
        poly = zone["polygon"]
        points = " ".join([f"{p[0] * 1.8 + 40},{p[1] * 1.1 + 80}" for p in poly])
        color = "#1e293b"
        if z_id == "EVENT":
            color = "#1e1b4b"
        elif z_id == "RESERVE":
            color = "#312e81"

        svg.append(f'<polygon points="{points}" fill="{color}" stroke="#475569" stroke-width="2"/>')
        center_x = sum([p[0] for p in poly]) / len(poly) * 1.8 + 40
        center_y = sum([p[1] for p in poly]) / len(poly) * 1.1 + 80
        svg.append(f'<text x="{center_x}" y="{center_y}" fill="#e2e8f0" font-size="14" text-anchor="middle" font-weight="bold">{zone["name"]}</text>')
        svg.append(f'<text x="{center_x}" y="{center_y + 20}" fill="#94a3b8" font-size="11" text-anchor="middle">Cap: {zone["max_capacity"]}</text>')

    # Draw token pads
    for pad in data.get("token_pads", []):
        t_id = pad["id"]
        # Position token pads
        coords = {
            "T_P1": (220, 360),
            "T_P2": (580, 360),
            "T_B2": (600, 520),
        }.get(t_id, (400, 300))

        svg.append(f'<circle cx="{coords[0]}" cy="{coords[1]}" r="24" fill="#7f1d1d" stroke="#ef4444" stroke-width="2" stroke-dasharray="4 2"/>')
        svg.append(f'<text x="{coords[0]}" y="{coords[1] + 4}" fill="#fecaca" font-size="11" font-weight="bold" text-anchor="middle">{t_id}</text>')
        svg.append(f'<text x="{coords[0]}" y="{coords[1] + 36}" fill="#fca5a5" font-size="10" text-anchor="middle">{pad["label"]}</text>')

    # Draw LED sticks
    led_labels = [
        ("Portal P1 (Stick 0..7)", 160, 300),
        ("Portal P2 (Stick 8..15)", 520, 300),
        ("Gate P3 (Stick 16..23)", 370, 360),
    ]
    for lbl, x, y in led_labels:
        svg.append(f'<rect x="{x}" y="{y}" width="60" height="14" fill="#065f46" rx="3" stroke="#10b981" stroke-width="1"/>')
        svg.append(f'<text x="{x + 30}" y="{y + 11}" fill="#a7f3d0" font-size="9" text-anchor="middle">{lbl}</text>')

    svg.append('</svg>')

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(svg))
    print(f"Exported schematic to {output_path}")


if __name__ == "__main__":
    export_svg("venue/reviewed_venue.json", "venue/board_schematic.svg")
