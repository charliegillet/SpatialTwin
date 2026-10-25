"""QR encoder structure. Decoding was cross-checked with macOS CoreImage for versions 1-40 at L/M/Q/H during
development (no decoder is a project dependency); these tests pin the parts a decoder relies on."""
import pytest

from backend.app.signs import qr


def test_reed_solomon_matches_the_published_hello_world_1m_example():
    data = [32, 91, 11, 120, 209, 114, 220, 77, 67, 64, 236, 17, 236, 17, 236, 17]
    assert qr._rs_remainder(data, qr._rs_divisor(10)) == [196, 35, 39, 119, 235, 215, 231, 226, 93, 23]


@pytest.mark.parametrize("version, ecl, codewords", [(1, "L", 19), (1, "M", 16), (1, "Q", 13), (1, "H", 9),
                                                     (7, "M", 124), (10, "M", 216), (40, "L", 2956), (40, "H", 1276)])
def test_data_capacity_matches_the_standard(version, ecl, codewords):
    assert qr._num_data_codewords(version, ecl) == codewords


def test_alignment_positions_match_the_standard():
    assert qr._alignment_positions(1) == []
    assert qr._alignment_positions(2) == [6, 18]
    assert qr._alignment_positions(7) == [6, 22, 38]
    assert qr._alignment_positions(32) == [6, 34, 60, 86, 112, 138]
    assert qr._alignment_positions(36) == [6, 24, 50, 76, 102, 128, 154]


def finder_at(m, x0, y0):
    return all(m[y0 + dy][x0 + dx] == (max(abs(dx - 3), abs(dy - 3)) != 2) for dy in range(7) for dx in range(7))


def read_format(m):
    size = len(m)
    first = [m[i][8] for i in range(6)] + [m[7][8], m[8][8], m[8][7]] + [m[8][14 - i] for i in range(9, 15)]
    second = [m[8][size - 1 - i] for i in range(8)] + [m[size - 15 + i][8] for i in range(8, 15)]
    to_int = lambda bits: sum(1 << i for i, bit in enumerate(bits) if bit)  # noqa: E731
    return to_int(first), to_int(second)


def test_short_url_is_a_version_1_symbol_with_valid_function_patterns():
    m = qr.encode(b"http://a/", "M")
    size = len(m)
    assert size == 21
    assert finder_at(m, 0, 0) and finder_at(m, size - 7, 0) and finder_at(m, 0, size - 7)
    assert [m[6][x] for x in range(8, size - 8)] == [x % 2 == 0 for x in range(8, size - 8)]
    assert [m[y][6] for y in range(8, size - 8)] == [y % 2 == 0 for y in range(8, size - 8)]
    assert m[size - 8][8] is True  # the dark module
    first, second = read_format(m)
    assert first == second
    raw = first ^ 0x5412
    data, remainder = raw >> 10, raw & 0x3FF
    check = data
    for _ in range(10):
        check = (check << 1) ^ ((check >> 9) * 0x537)
    assert check & 0x3FF == remainder
    assert data >> 3 in (0, 3, 2)  # M, possibly boosted to Q or H (format bits: M=00, Q=11, H=10)


def test_version_7_and_up_carry_the_version_block():
    m = qr.encode(b"x" * 110, "M", boost=False)
    size = len(m)
    assert (size - 17) // 4 == 7
    bits = 0
    for i in range(18):
        if m[size - 11 + i % 3][i // 3]:
            bits |= 1 << i
    assert bits == 0x07C94  # version 7 information word from the standard


def test_boost_raises_the_level_only_when_the_version_stays_the_same():
    plain = qr.encode(b"http://192.168.8.20:8000/s/x", "M", boost=False)
    boosted = qr.encode(b"http://192.168.8.20:8000/s/x", "M", boost=True)
    assert len(plain) == len(boosted)
    assert (read_format(boosted)[0] ^ 0x5412) >> 13 in (3, 2)


def test_a_sign_url_fits_a_small_symbol():
    url = "http://192.168.100.200:8000/s/v1.sign.building-v2.E1.1792966120.1792980520.b68509775366.-." + "A" * 43
    assert len(qr.encode(url.encode(), "M")) <= 53  # version 9 or smaller


def test_capacity_limit_is_enforced():
    assert len(qr.encode(b"a" * 2953, "L")) == 177
    with pytest.raises(qr.QrError):
        qr.encode(b"a" * 2954, "L")


def test_svg_is_static_markup_with_a_quiet_zone_and_a_sanitised_label():
    svg = qr.qr_svg("http://a/", label='Exit "E1"<script>alert(1)</script>')
    assert svg.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 29 29"')
    assert "<script" not in svg and "alert(1)" not in svg.replace("alert1", "")
    assert svg.count("<path") == 1 and 'fill="#ffffff"' in svg and "crispEdges" in svg
