"""
SpatialTwin LED Display Controller
Projects independently checked numerical routing results onto 24 physical NeoPixels:
- P1 (Main West): LEDs 0..7
- P2 (Main East): LEDs 8..15
- P3 (Reserve Gate): LEDs 16..23
"""

from typing import Dict, List, Optional, Set
from backend.app.contracts import EvaluationEnvelope, GateObservedState

NUM_PIXELS = 24

# SET_DISPLAY wire code table: one ASCII character per pixel. The firmware keeps the same table
# (px_codec.h / spatialtwin_board.ino); change both together. Lowercase codes are the flashing
# variants (blinkPhase toggled every 400 ms on the device). The projector only emits steady codes
# today; the flashing codes are accepted by the device and decoded by the simulator.
PX_CODE_RGB: Dict[str, int] = {
    "0": 0x000000,  # off
    "G": 0x00A000,  # green: model flow / gate open
    "R": 0xB40000,  # red: blocked / fault
    "A": 0xB45000,  # amber: gate in transit
    "B": 0x000028,  # dim blue: idle / gate closed
    "U": 0x5A005A,  # purple: gate state unknown
    "g": 0x00A000,  # flashing green
    "r": 0xB40000,  # flashing red
    "a": 0xB45000,  # flashing amber
    "u": 0x5A005A,  # flashing purple
}
PX_ALPHABET = "".join(PX_CODE_RGB)
_STEADY_RGB_TO_CODE: Dict[int, str] = {rgb: code for code, rgb in PX_CODE_RGB.items() if code.isupper() or code == "0"}


def encode_px(pixels: List[int]) -> str:
    """Packs 24 steady 0xRRGGBB pixels into the 24-character SET_DISPLAY `px` string."""
    if len(pixels) != NUM_PIXELS:
        raise ValueError(f"expected {NUM_PIXELS} pixels, got {len(pixels)}")
    try:
        return "".join(_STEADY_RGB_TO_CODE[p] for p in pixels)
    except KeyError as error:
        raise ValueError(f"pixel colour {error.args[0]:#08x} has no px code") from None


def decode_px(px: str) -> List[int]:
    """Inverse of encode_px for the simulator; flashing codes decode to their steady colour."""
    if len(px) != NUM_PIXELS or any(c not in PX_CODE_RGB for c in px):
        raise ValueError("invalid px string")
    return [PX_CODE_RGB[c] for c in px]


class DisplayProjector:
    def __init__(self):
        # 24 pixels, each represented as 0xRRGGBB integer
        self.current_pixels: List[int] = [0] * 24
        self.current_px: str = "0" * NUM_PIXELS

    @staticmethod
    def rgb_to_int(r: int, g: int, b: int) -> int:
        return (r << 16) | (g << 8) | b

    def project(
        self,
        current_plan: Optional[EvaluationEnvelope],
        blocked_portals: Set[str],
        gate_state: GateObservedState,
    ) -> List[int]:
        pixels = [0] * 24

        # Colors (conservative brightness ~30% for bench comfort)
        COLOR_OFF = 0x000000
        COLOR_GREEN = self.rgb_to_int(0, 160, 0)
        COLOR_RED = self.rgb_to_int(180, 0, 0)
        COLOR_AMBER = self.rgb_to_int(180, 80, 0)
        COLOR_DIM_BLUE = self.rgb_to_int(0, 0, 40)
        COLOR_UNKNOWN = self.rgb_to_int(90, 0, 90)

        # Route LEDs show a plan only when its independent validator accepted it.
        plan_ok = bool(current_plan and current_plan.validator_report.is_valid)
        if not plan_ok:
            current_plan = None

        # 1. Portal P1 (indices 0..7)
        if "P1" in blocked_portals:
            p1_color = COLOR_RED
        else:
            p1_flow = current_plan.boundary_breakdown.get("B1", 0) if current_plan else 0
            p1_color = COLOR_GREEN if p1_flow > 0 else COLOR_DIM_BLUE
        for i in range(0, 8):
            pixels[i] = p1_color

        # 2. Portal P2 (indices 8..15)
        if "P2" in blocked_portals:
            p2_color = COLOR_RED
        else:
            p2_flow = current_plan.boundary_breakdown.get("B2", 0) if current_plan else 0
            p2_color = COLOR_GREEN if p2_flow > 0 else COLOR_DIM_BLUE
        for i in range(8, 16):
            pixels[i] = p2_color

        # 3. Portal P3 (indices 16..23)
        if gate_state == GateObservedState.OPEN:
            p3_color = COLOR_GREEN
        elif gate_state == GateObservedState.TRANSIT:
            p3_color = COLOR_AMBER
        elif gate_state == GateObservedState.FAULT:
            p3_color = COLOR_RED
        elif gate_state == GateObservedState.CLOSED:
            p3_color = COLOR_DIM_BLUE
        else:
            # UNKNOWN (no confirmed endpoint): distinct from CLOSED so it is never read as "safely shut".
            p3_color = COLOR_UNKNOWN
        for i in range(16, 24):
            pixels[i] = p3_color

        self.current_pixels = pixels
        self.current_px = encode_px(pixels)
        return pixels
