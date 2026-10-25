"""Compiles and runs the firmware's pure SET_DISPLAY parser (px_codec.h) on the host with `cc`."""
import glob
import shutil
import subprocess
from pathlib import Path

import pytest

FIRMWARE = Path(__file__).resolve().parents[2] / "firmware"
CC = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")


def _build(output: Path):
    """Tries the default toolchain, then each installed macOS SDK (a newer SDK's stubs may not link)."""
    base = [CC, "-Wall", "-Wextra", "-Werror", f"-I{FIRMWARE / 'spatialtwin_board'}",
            str(FIRMWARE / "tests" / "test_px_codec.c"), "-o", str(output)]
    attempts = [base] + [base + ["-isysroot", sdk]
                         for sdk in sorted(glob.glob("/Library/Developer/CommandLineTools/SDKs/MacOSX*.sdk"))]
    last = None
    for command in attempts:
        last = subprocess.run(command, capture_output=True, text=True)
        if last.returncode == 0:
            return None
    return last.stderr[-400:]


@pytest.mark.skipif(CC is None, reason="no C compiler (cc/gcc/clang) on PATH")
def test_px_codec_c_parser(tmp_path):
    binary = tmp_path / "test_px_codec"
    error = _build(binary)
    if error is not None:
        pytest.skip(f"C toolchain present but cannot link a host binary: {error}")
    result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "all checks passed" in result.stdout
