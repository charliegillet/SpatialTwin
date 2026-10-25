"""Guard: the forked v2 work must not change a single v1 planner number."""
import json
from pathlib import Path

import pytest

from tests.planner._golden_cases import CASES, run_case

GOLDENS = Path(__file__).parent / "goldens"


@pytest.mark.parametrize("name", sorted(CASES))
def test_v1_envelope_matches_golden(name):
    expected = json.loads((GOLDENS / f"{name}.json").read_text())
    assert run_case(name) == expected
