"""Model pricing — a LAST-RESORT fallback for ``cap-evolve estimate``.

Accuracy order the estimator uses:
  1. **Calibration from real runs** — observed ``$/metric-call`` and ``$/optimizer-call``
     read from prior ``run_*/state.json`` Spent (the agent CLI's *actual* reported
     ``total_cost_usd``). Exact; needs no table.
  2. **User-supplied prices** — ``--price-in``/``--price-out`` flags (the model's $/MTok).
  3. **This table** — official public list prices, verified against vendor docs on the
     date below. They go stale; EDIT when prices change.

Values are USD per million tokens, ``(input, output)`` at standard (non-batch, non-cached)
rates. Lookup is a case-insensitive substring match on the model id, longest key first,
so ``claude-opus-4-8`` matches the ``claude-opus`` row.

Sources (verified 2026-06-18):
  - Claude:  https://platform.claude.com/docs/en/about-claude/pricing
  - OpenAI:  https://developers.openai.com/api/docs/pricing
  - Gemini:  https://ai.google.dev/gemini-api/docs/pricing
"""
from __future__ import annotations

PRICING_VERIFIED = "2026-06-18"

# (input $/MTok, output $/MTok) — standard tier.
PRICING: dict[str, tuple[float, float]] = {
    # Claude (platform.claude.com)
    "claude-fable-5": (10.0, 50.0),
    "claude-opus-4-1": (15.0, 75.0),  # deprecated; older Opus 4.1/4.0 list price
    "claude-opus": (5.0, 25.0),       # Opus 4.5 / 4.6 / 4.7 / 4.8
    "claude-sonnet": (3.0, 15.0),     # Sonnet 4 / 4.5 / 4.6
    "claude-haiku-3": (0.80, 4.0),    # Haiku 3.5 (retired list price)
    "claude-haiku": (1.0, 5.0),       # Haiku 4.5
    # OpenAI (developers.openai.com)
    "gpt-5.5-pro": (30.0, 180.0),
    "gpt-5.5": (5.0, 30.0),
    "gpt-5.4-mini": (0.75, 4.50),
    "gpt-5.4-nano": (0.20, 1.25),
    "gpt-5.4-pro": (30.0, 180.0),
    "gpt-5.4": (2.50, 15.0),
    "gpt-5.3-codex": (1.75, 14.0),
    # Gemini (ai.google.dev) — ≤200k-token tier
    "gemini-2.5-pro": (1.25, 10.0),
    "gemini-2.5-flash": (0.30, 2.50),
}

# Rough tokens-per-call assumptions when pricing from $/MTok (no per-call telemetry
# until a run has happened). Deliberately conservative; calibration from real runs
# supersedes these, and the estimate prints a wide low/high band around them.
ASSUMED_TOKENS = {
    "optimizer": (10_000, 2_000),  # reads INSTRUCTIONS/MEMORY + proposes an edit
    "runner": (3_000, 800),        # one agent-under-test rollout
}


def lookup(model: str | None) -> tuple[float, float] | None:
    """Return ``(in, out)`` $/MTok for a model id, or ``None`` if unknown."""
    if not model:
        return None
    m = str(model).lower()
    for key in sorted(PRICING, key=len, reverse=True):
        if key in m:
            return PRICING[key]
    return None


def call_cost(model: str | None, role: str) -> float | None:
    """Approximate USD for one ``role`` (optimizer|runner) call of ``model``."""
    price = lookup(model)
    if price is None:
        return None
    tin, tout = ASSUMED_TOKENS.get(role, (3_000, 800))
    pin, pout = price
    return (tin * pin + tout * pout) / 1_000_000.0
