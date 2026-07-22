"""Consuming-LLM capability profiles.

Distinct from ``optimizer_model`` (the model that PROPOSES edits): the *consuming*
model is the one the agent under test reads these capabilities with at runtime. A
declaration is either a tier keyword (frontier|strong|mid|weak) or a concrete model id
resolved to a tier via ``MODEL_MAP``. The resolved brief steers the optimizer prompt and
the capability guidance to optimize FOR that reader.

Zero-dependency by design: the built-in tiers live here as Python data (no YAML parse),
and a project may override a tier's brief with a raw-text file (``target_profile_file``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIER = "strong"

TIERS: dict[str, dict] = {
    "frontier": {
        "brief": (
            "The reader is a top-tier model: strong long-context reasoning, reliable "
            "instruction-following, and a tendency to OVER-comply. Prefer concise policy "
            "that explains the WHY over piling on ALL-CAPS MUSTs; soften brittle "
            "imperatives; trust multi-step reasoning; keep few-shot examples minimal. "
            "Over-constraining HURTS this reader."
        ),
        "suggested_num_trials": 1,
        "notes": "e.g. claude-opus, gpt-4-class, gemini-2.5-pro-class",
    },
    "strong": {
        "brief": (
            "The reader is a capable general model, but less robust than frontier on long "
            "or ambiguous context. Keep instructions clear and reasonably explicit; add a "
            "worked example for tricky formats; prefer code enforcement for behavioral "
            "rules over trusting inference."
        ),
        "suggested_num_trials": 3,
        "notes": "default when a named model is unknown",
    },
    "mid": {
        "brief": (
            "The reader is a mid-capability model (e.g. ~100B open weights). Be EXPLICIT: "
            "imperative step-by-step rules, at least one worked few-shot example per "
            "non-trivial behavior, short decision chains, and literal argument/slot-filling "
            "docs on every tool parameter. Lean HARD on deterministic tool-code "
            "enforcement — a behavioral rule it 'knows' but skips must be enforced in code, "
            "not restated in prose."
        ),
        "suggested_num_trials": 5,
        "notes": "e.g. gpt-oss-120b",
    },
    "weak": {
        "brief": (
            "The reader is a smaller/weaker model. Assume it will miss anything not made "
            "mechanical. Maximize explicitness and examples; minimize unaided reasoning; "
            "move as much correctness as possible into tool code/guards and rigid output "
            "contracts; keep each instruction short and single-purpose. Prose is the "
            "weakest lever here."
        ),
        "suggested_num_trials": 5,
        "notes": "e.g. gpt-oss-20b, small local models",
    },
}

# Known model id (lowercased) -> tier. Extensible; unknown ids fall back to DEFAULT_TIER.
MODEL_MAP: dict[str, str] = {
    "claude-opus-4-6": "frontier",
    "claude-opus-4-8": "frontier",
    "claude-sonnet-5": "strong",
    "claude-haiku-4-5": "mid",
    "gpt-4o": "frontier",
    "gpt-oss-120b": "mid",
    "gpt-oss-20b": "weak",
}


@dataclass
class TargetProfile:
    model: str = ""
    tier: str = ""
    brief: str = ""
    suggested_num_trials: int = 0
    notes: str = ""
    resolution_note: str = ""

    @property
    def is_agnostic(self) -> bool:
        return not self.tier


def resolve(target_model: str = "",
            target_profile_file: str | Path | None = None,
            project_dir: str | Path | None = None) -> TargetProfile:
    decl = (target_model or "").strip()
    if not decl:
        return TargetProfile()  # agnostic

    key = decl.lower()
    note = ""
    if key in TIERS:
        tier = key
    elif key in MODEL_MAP:
        tier = MODEL_MAP[key]
    else:
        tier = DEFAULT_TIER
        note = (f"unknown model id '{decl}'; defaulting to tier '{DEFAULT_TIER}' — "
                "set a tier keyword (frontier|strong|mid|weak) explicitly to override")

    spec = TIERS[tier]
    brief = spec["brief"]
    if target_profile_file:
        fp = Path(target_profile_file)
        if not fp.is_absolute() and project_dir is not None:
            cand = Path(project_dir) / fp
            if cand.exists():
                fp = cand
        try:
            if fp.exists():
                brief = fp.read_text(encoding="utf-8").strip()
        except OSError:
            pass  # unreadable override → keep the tier's built-in brief

    return TargetProfile(model=decl, tier=tier, brief=brief,
                         suggested_num_trials=int(spec["suggested_num_trials"]),
                         notes=str(spec["notes"]), resolution_note=note)


def reader_block(profile: TargetProfile) -> str:
    """Render the ``{{TARGET_READER}}`` block. Empty string when agnostic."""
    if profile.is_agnostic:
        return ""
    return (
        "## THE READER (who consumes what you edit)\n"
        f"At runtime these capabilities are read by `{profile.model}` — capability tier: "
        f"**{profile.tier}**. {profile.brief}\n"
        "Optimize your edits for THIS reader's capability level, not for your own. When "
        "the reader is weaker than you, prefer explicit rules, worked examples, and "
        "code enforcement over terse prose you would personally infer.\n"
    )
