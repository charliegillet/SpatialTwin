"""Estimated token cost of an agent lane, from the provider's usage counters. An estimate, never a bill.

Prices: CLAUDE_BUILD_HANDOFF/reference/google/pricing.md, "Gemini 4 Argon", paid tier, read 23 Oct 2026: input
$2.00 / 1M tokens and output (including thinking) $10.00 / 1M through 30 Nov 2026 ($4.00 / $20.00 from 1 Dec 2026);
implicit context caching $0.10 / 1M. Agent loops are billed at model list rates; environment compute is not billed
during the preview (pricing.md "Pricing for agents"). Usage semantics are taken from live receipts on 25 Oct 2026:
``total_tokens = total_input_tokens + total_output_tokens + total_thought_tokens`` and cached tokens are part of the
input count. Tool-use prompt tokens are billed as input.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Mapping, Optional

PRICES = {
    "gemini-4-argon": {"input": 2.00, "cached": 0.10, "output": 10.00, "valid_through": "2026-11-30",
                       "after": {"input": 4.00, "cached": 0.20, "output": 20.00}},
}
BASIS = "Estimate at Gemini 4 Argon paid-tier list prices (pricing.md, read 23 Oct 2026); not a bill."


def estimate_cost(model: Optional[str], usage: Mapping[str, Any], today: Optional[date] = None) -> Optional[Dict[str, Any]]:
    price = PRICES.get(model or "")
    if price is None or not isinstance(usage.get("total_input_tokens"), int):
        return None
    today = today or date.today()
    rates = price if today.isoformat() <= price["valid_through"] else price["after"]
    cached = min(int(usage.get("total_cached_tokens", 0) or 0), usage["total_input_tokens"])
    billed_input = usage["total_input_tokens"] - cached + int(usage.get("total_tool_use_tokens", 0) or 0)
    output = int(usage.get("total_output_tokens", 0) or 0) + int(usage.get("total_thought_tokens", 0) or 0)
    usd = (billed_input * rates["input"] + cached * rates["cached"] + output * rates["output"]) / 1_000_000
    return {"usd": round(usd, 4), "input_tokens": billed_input, "cached_tokens": cached, "output_tokens": output,
            "rates_per_million": {k: rates[k] for k in ("input", "cached", "output")}, "basis": BASIS}
