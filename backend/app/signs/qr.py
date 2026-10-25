"""A minimal QR Code (Model 2) encoder: byte mode, versions 1-40, error correction L/M/Q/H, SVG output.

Why it exists: the presenter screen shows a QR per exit sign, and the project must not take a new dependency for
it. Only what a URL needs is implemented: byte mode (no numeric/alphanumeric/kanji segments, no ECI, no structured
append). The construction follows ISO/IEC 18004 step by step (data bits, Reed-Solomon blocks, interleaving, function
patterns, zigzag placement, the 8 masks scored by the 4 penalty rules, format and version information), in the
same order as Project Nayuki's MIT-licensed reference generator so it can be checked against it; the code and the
tables here were written for this project from the standard. ``tests/signs/test_qr.py`` pins known structure, and
the module matrix was cross-checked by decoding the rendered PNGs with macOS CoreImage during development.

The SVG contains only rectangles derived from the module matrix: no text, no user-controlled markup, so it is safe
to embed. ``<img src="data:image/svg+xml;...">`` is still the recommended way to show it.
"""
from __future__ import annotations

from typing import List, Literal, Sequence, Tuple

Ecl = Literal["L", "M", "Q", "H"]

# Index 0 is unused so that the version number indexes the tables directly.
_ECC_CODEWORDS_PER_BLOCK = {
    "L": (-1, 7, 10, 15, 20, 26, 18, 20, 24, 30, 18, 20, 24, 26, 30, 22, 24, 28, 30, 28, 28, 28, 28, 30, 30, 26, 28,
          30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
    "M": (-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26, 26, 28, 28, 28, 28, 28,
          28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28),
    "Q": (-1, 13, 22, 18, 26, 18, 24, 18, 22, 20, 24, 28, 26, 24, 20, 30, 24, 28, 28, 26, 30, 28, 30, 30, 30, 30, 28,
          30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
    "H": (-1, 17, 28, 22, 16, 22, 28, 26, 26, 24, 28, 24, 28, 22, 24, 24, 30, 28, 28, 26, 28, 30, 24, 30, 30, 30, 30,
          30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
}
_NUM_ERROR_CORRECTION_BLOCKS = {
    "L": (-1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4, 4, 4, 4, 4, 6, 6, 6, 6, 7, 8, 8, 9, 9, 10, 12, 12, 12, 13, 14, 15, 16, 17,
          18, 19, 19, 20, 21, 22, 24, 25),
    "M": (-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26, 28, 29,
          31, 33, 35, 37, 38, 40, 43, 45, 47, 49),
    "Q": (-1, 1, 1, 2, 2, 4, 4, 6, 6, 8, 8, 8, 10, 12, 16, 12, 17, 16, 18, 21, 20, 23, 23, 25, 27, 29, 34, 34, 35, 38,
          40, 43, 45, 48, 51, 53, 56, 59, 62, 65, 68),
    "H": (-1, 1, 1, 2, 4, 4, 4, 5, 6, 8, 8, 11, 11, 16, 16, 18, 16, 19, 21, 25, 25, 25, 34, 30, 32, 35, 37, 40, 42, 45,
          48, 51, 54, 57, 60, 63, 66, 70, 74, 77, 81),
}
# Format-information bits for each level (ISO/IEC 18004 table 12): note M is 00 and L is 01.
_ECL_FORMAT_BITS = {"L": 1, "M": 0, "Q": 3, "H": 2}
_BOOST_ORDER: Tuple[Ecl, ...] = ("L", "M", "Q", "H")
_PENALTY_N1, _PENALTY_N2, _PENALTY_N3, _PENALTY_N4 = 3, 3, 40, 10


class QrError(ValueError):
    """The data does not fit in a version-40 symbol at the requested level."""


# -- Reed-Solomon over GF(2^8) with the QR polynomial x^8 + x^4 + x^3 + x^2 + 1 --------------------------------------

def _gf_multiply(x: int, y: int) -> int:
    z = 0
    for i in reversed(range(8)):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _rs_divisor(degree: int) -> List[int]:
    """Coefficients (highest power first, leading 1 omitted) of prod_{i<degree} (x - 2^i)."""
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _gf_multiply(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _gf_multiply(root, 0x02)
    return result


def _rs_remainder(data: Sequence[int], divisor: Sequence[int]) -> List[int]:
    result = [0] * len(divisor)
    for byte in data:
        factor = byte ^ result.pop(0)
        result.append(0)
        for i, coefficient in enumerate(divisor):
            result[i] ^= _gf_multiply(coefficient, factor)
    return result


# -- capacity ----------------------------------------------------------------------------------------------------

def _num_raw_data_modules(version: int) -> int:
    """Modules left for data and ECC after every function pattern (and the format/version areas) is removed."""
    result = (16 * version + 128) * version + 64
    if version >= 2:
        num_align = version // 7 + 2
        result -= (25 * num_align - 10) * num_align - 55
        if version >= 7:
            result -= 36
    return result


def _num_data_codewords(version: int, ecl: Ecl) -> int:
    return (_num_raw_data_modules(version) // 8
            - _ECC_CODEWORDS_PER_BLOCK[ecl][version] * _NUM_ERROR_CORRECTION_BLOCKS[ecl][version])


def _data_bits_needed(length: int, version: int) -> int:
    count_bits = 8 if version <= 9 else 16
    return 4 + count_bits + 8 * length


def _alignment_positions(version: int) -> List[int]:
    if version == 1:
        return []
    num_align = version // 7 + 2
    step = (version * 8 + num_align * 3 + 5) // (num_align * 4 - 4) * 2
    size = version * 4 + 17
    positions = [size - 7 - i * step for i in range(num_align - 1)]
    return [6] + sorted(positions)


# -- symbol ------------------------------------------------------------------------------------------------------

class _Symbol:
    def __init__(self, version: int, ecl: Ecl):
        self.version = version
        self.ecl = ecl
        self.size = version * 4 + 17
        self.modules = [[False] * self.size for _ in range(self.size)]
        self.is_function = [[False] * self.size for _ in range(self.size)]

    def set_function(self, x: int, y: int, dark: bool) -> None:
        self.modules[y][x] = dark
        self.is_function[y][x] = True

    def draw_function_patterns(self) -> None:
        size = self.size
        for i in range(size):
            self.set_function(6, i, i % 2 == 0)
            self.set_function(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < size and 0 <= y < size:
                        self.set_function(x, y, max(abs(dx), abs(dy)) not in (2, 4))
        positions = _alignment_positions(self.version)
        last = len(positions) - 1
        for i, cx in enumerate(positions):
            for j, cy in enumerate(positions):
                # The three corners hold finder patterns.
                if (i, j) in ((0, 0), (0, last), (last, 0)):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self.set_function(cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)
        self.draw_format_bits(0)  # reserves the area; the real mask is drawn later
        self.draw_version()

    def draw_format_bits(self, mask: int) -> None:
        data = _ECL_FORMAT_BITS[self.ecl] << 3 | mask
        remainder = data
        for _ in range(10):
            remainder = (remainder << 1) ^ ((remainder >> 9) * 0x537)
        bits = (data << 10 | remainder) ^ 0x5412
        bit = lambda i: (bits >> i) & 1 == 1  # noqa: E731
        size = self.size
        for i in range(6):
            self.set_function(8, i, bit(i))
        self.set_function(8, 7, bit(6))
        self.set_function(8, 8, bit(7))
        self.set_function(7, 8, bit(8))
        for i in range(9, 15):
            self.set_function(14 - i, 8, bit(i))
        for i in range(8):
            self.set_function(size - 1 - i, 8, bit(i))
        for i in range(8, 15):
            self.set_function(8, size - 15 + i, bit(i))
        self.set_function(8, size - 8, True)  # the dark module

    def draw_version(self) -> None:
        if self.version < 7:
            return
        remainder = self.version
        for _ in range(12):
            remainder = (remainder << 1) ^ ((remainder >> 11) * 0x1F25)
        bits = self.version << 12 | remainder
        for i in range(18):
            dark = (bits >> i) & 1 == 1
            a, b = self.size - 11 + i % 3, i // 3
            self.set_function(a, b, dark)
            self.set_function(b, a, dark)

    def draw_codewords(self, data: Sequence[int]) -> None:
        size = self.size
        total_bits = len(data) * 8
        i = 0
        right = size - 1
        while right >= 1:
            if right == 6:  # the vertical timing column is skipped
                right = 5
            upward = ((right + 1) & 2) == 0
            for vert in range(size):
                y = size - 1 - vert if upward else vert
                for j in range(2):
                    x = right - j
                    if not self.is_function[y][x] and i < total_bits:
                        self.modules[y][x] = (data[i >> 3] >> (7 - (i & 7))) & 1 == 1
                        i += 1
            right -= 2

    def apply_mask(self, mask: int) -> None:
        for y in range(self.size):
            for x in range(self.size):
                if self.is_function[y][x]:
                    continue
                if mask == 0:
                    invert = (x + y) % 2 == 0
                elif mask == 1:
                    invert = y % 2 == 0
                elif mask == 2:
                    invert = x % 3 == 0
                elif mask == 3:
                    invert = (x + y) % 3 == 0
                elif mask == 4:
                    invert = (x // 3 + y // 2) % 2 == 0
                elif mask == 5:
                    invert = x * y % 2 + x * y % 3 == 0
                elif mask == 6:
                    invert = (x * y % 2 + x * y % 3) % 2 == 0
                else:
                    invert = ((x + y) % 2 + x * y % 3) % 2 == 0
                if invert:
                    self.modules[y][x] = not self.modules[y][x]

    def penalty(self) -> int:
        size = self.size
        grid = self.modules
        score = 0
        lines = [row for row in grid] + [[grid[y][x] for y in range(size)] for x in range(size)]
        finder_a = [True, False, True, True, True, False, True, False, False, False, False]
        finder_b = list(reversed(finder_a))
        for line in lines:
            run_color, run = line[0], 1
            for value in line[1:]:
                if value == run_color:
                    run += 1
                else:
                    if run >= 5:
                        score += _PENALTY_N1 + run - 5
                    run_color, run = value, 1
            if run >= 5:
                score += _PENALTY_N1 + run - 5
            # Finder-like 1:1:3:1:1 with 4 light modules on one side; outside the symbol counts as light.
            padded = [False] * 4 + list(line) + [False] * 4
            for start in range(len(padded) - 10):
                window = padded[start:start + 11]
                if window == finder_a or window == finder_b:
                    score += _PENALTY_N3
        for y in range(size - 1):
            for x in range(size - 1):
                value = grid[y][x]
                if value == grid[y][x + 1] == grid[y + 1][x] == grid[y + 1][x + 1]:
                    score += _PENALTY_N2
        dark = sum(sum(1 for value in row if value) for row in grid)
        total = size * size
        k = (abs(dark * 20 - total * 10) + total - 1) // total - 1
        score += k * _PENALTY_N4
        return score


def _codewords(data: bytes, version: int, ecl: Ecl) -> List[int]:
    capacity_bits = _num_data_codewords(version, ecl) * 8
    bits: List[int] = []

    def append(value: int, length: int) -> None:
        bits.extend((value >> i) & 1 for i in reversed(range(length)))

    append(0b0100, 4)  # byte mode
    append(len(data), 8 if version <= 9 else 16)
    for byte in data:
        append(byte, 8)
    append(0, min(4, capacity_bits - len(bits)))  # terminator
    append(0, (-len(bits)) % 8)
    pad = 0xEC
    while len(bits) < capacity_bits:
        append(pad, 8)
        pad ^= 0xEC ^ 0x11
    data_codewords = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]

    num_blocks = _NUM_ERROR_CORRECTION_BLOCKS[ecl][version]
    ecc_len = _ECC_CODEWORDS_PER_BLOCK[ecl][version]
    raw = _num_raw_data_modules(version) // 8
    num_short = num_blocks - raw % num_blocks
    short_len = raw // num_blocks
    divisor = _rs_divisor(ecc_len)
    blocks: List[List[int]] = []
    k = 0
    for i in range(num_blocks):
        length = short_len - ecc_len + (0 if i < num_short else 1)
        block = data_codewords[k:k + length]
        k += length
        ecc = _rs_remainder(block, divisor)
        if i < num_short:
            block = block + [0]  # placeholder so every block has the same length; skipped when interleaving
        blocks.append(block + ecc)
    result: List[int] = []
    for i in range(len(blocks[0])):
        for j, block in enumerate(blocks):
            if i != short_len - ecc_len or j >= num_short:
                result.append(block[i])
    assert len(result) == raw
    return result


def encode(data: bytes, ecl: Ecl = "M", boost: bool = True) -> List[List[bool]]:
    """Module matrix (row-major, True = dark) of the smallest symbol holding ``data`` at level ``ecl`` or better.

    With ``boost`` the level is raised while the data still fits the same version: a QR read off a projector or a
    laptop screen benefits from the spare error correction.
    """
    for version in range(1, 41):
        if _data_bits_needed(len(data), version) <= _num_data_codewords(version, ecl) * 8:
            break
    else:
        raise QrError("data_too_long")
    if boost:
        for level in _BOOST_ORDER[_BOOST_ORDER.index(ecl) + 1:]:
            if _data_bits_needed(len(data), version) <= _num_data_codewords(version, level) * 8:
                ecl = level
    codewords = _codewords(data, version, ecl)
    best: List[List[bool]] = []
    best_score = None
    for mask in range(8):
        symbol = _Symbol(version, ecl)
        symbol.draw_function_patterns()
        symbol.draw_codewords(codewords)
        symbol.apply_mask(mask)
        symbol.draw_format_bits(mask)
        score = symbol.penalty()
        if best_score is None or score < best_score:
            best_score, best = score, symbol.modules
    return best


def to_svg(modules: List[List[bool]], border: int = 4, label: str = "QR code") -> str:
    """A scalable SVG: viewBox in modules, one path of horizontal runs, crisp edges, white quiet zone."""
    size = len(modules)
    dim = size + 2 * border
    parts: List[str] = []
    for y, row in enumerate(modules):
        x = 0
        while x < size:
            if row[x]:
                start = x
                while x < size and row[x]:
                    x += 1
                parts.append(f"M{start + border} {y + border}h{x - start}v1h-{x - start}z")
            else:
                x += 1
    safe_label = "".join(ch for ch in label if ch.isalnum() or ch in " .,:-")[:80]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {dim} {dim}" shape-rendering="crispEdges" '
            f'role="img" aria-label="{safe_label}"><rect width="{dim}" height="{dim}" fill="#ffffff"/>'
            f'<path fill="#000000" d="{"".join(parts)}"/></svg>')


def qr_svg(text: str, ecl: Ecl = "M", label: str = "QR code") -> str:
    return to_svg(encode(text.encode("utf-8"), ecl), label=label)
