"""The `no_skill` tier: measure the agent with NO capability, under identical conditions.

WHY IT EXISTS

Run 36175707483 produced a held-out SpreadsheetBench score of 0.764 for Gemma-4-31B-It against a
seed baseline of 0.632. WikiSkill (arXiv 2608.27454v1) reports 68.0 for the same model against a
**no-skill** baseline of 48.3. Our seed is a tuned prompt plus a task template, not an empty
context, so our +13.2 delta cannot be compared with their +19.7 — only the absolute figures can.

To state a comparable DELTA we need our own no-skill anchor. The mechanism to blank the capability
already existed (`SB_EMPTY_SEED=1`, run_suite.sh) but was reachable only by editing a committed
`overrides.env`: it is not a dispatch input, and `workflow_dispatch` already declares 11 inputs.
A tier is the right dimension anyway — "what is being measured" — and tiers are not capped.

THE ONE THING THIS TIER MUST GET RIGHT

A control is only a control if it differs from the thing it controls in EXACTLY one respect. So
`no_skill` must share `full_verified`'s dataset, task list, split, turn budget, container
concurrency and scoring, and differ only in having no capability. Every test below exists to pin
one of those, because a control measured under different conditions is worse than no control:
it produces a number that looks comparable and is not.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "benchmarks.yml"
RUN_SUITE = REPO / "ci" / "benchmarks" / "lib" / "run_suite.sh"
CI_SETUP = REPO / "ci" / "benchmarks" / "lib" / "ci_setup.sh"
SB = REPO / "ci" / "benchmarks" / "spreadsheetbench"
CONTROL, TREATMENT = SB / "no_skill", SB / "full_verified"


def _ids(p: Path) -> list[str]:
    return [str(e["id"]) for e in json.loads(p.read_text(encoding="utf-8"))]


def _overrides(tier: Path) -> dict[str, str]:
    out = {}
    for line in (tier / "overrides.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _tier_arm(path: Path, bench: str = "spreadsheetbench") -> str:
    src = path.read_text(encoding="utf-8")
    start = src.index(f"  {bench})")
    ends = [src.index(m, start) for m in ("\n  *)", "\nesac") if m in src[start:]]
    return src[start:min(ends)] if ends else src[start:]


# --- it is a control: identical to full_verified except for the capability ------------------


def test_the_control_measures_exactly_the_same_tasks():
    assert _ids(CONTROL / "tasks.json") == _ids(TREATMENT / "tasks.json"), (
        "the control's task list differs from full_verified's — the two numbers would not be "
        "comparable, which is the only reason this tier exists"
    )


def test_the_control_uses_the_same_split_byte_for_byte():
    """Same 280 sealed test tasks, or the no-skill anchor measures a different population."""
    assert (CONTROL / "split_ids.json").read_text(encoding="utf-8") == \
           (TREATMENT / "split_ids.json").read_text(encoding="utf-8")


def test_the_control_scores_on_the_same_metric():
    assert _overrides(CONTROL).get("SB_SCORING") == _overrides(TREATMENT).get("SB_SCORING") == "hard"


def test_the_control_gets_the_same_turn_budget_and_concurrency():
    """Fewer turns would understate no-skill and flatter the optimized result."""
    arm = _tier_arm(RUN_SUITE)
    for line in ("SB_CONCURRENCY_DEFAULT=8", "SB_MAX_TURNS_DEFAULT=30"):
        m = re.search(rf'case "\$TIER" in ([a-z_|]+)\) {re.escape(line)}', arm)
        assert m, f"could not find the tier arm setting {line}"
        tiers = set(m.group(1).split("|"))
        assert {"full_verified", "no_skill"} <= tiers, (
            f"no_skill is missing from the {line} arm ({sorted(tiers)}) — the control would run "
            "under different conditions from the thing it controls"
        )


def test_the_control_fetches_the_same_dataset_variant():
    arm = _tier_arm(CI_SETUP)
    # Shape-agnostic: the case arm is multi-line, so match the line that sets the variant and
    # read the tier alternatives in front of it rather than assuming a one-line `case`.
    m = re.search(r'^\s*([a-z_|]+)\)\s*SB_VARIANT="verified_400"', arm, re.M)
    assert m and {"full_verified", "no_skill"} <= set(m.group(1).split("|")), (
        "no_skill does not map to the verified_400 archive, so it would measure a different "
        "benchmark from full_verified"
    )


# --- and it differs in exactly one respect -------------------------------------------------


def test_the_control_blanks_the_capability():
    """The whole point: no system prompt at all, which is what makes it a no-skill number."""
    assert _overrides(CONTROL).get("SB_EMPTY_SEED") == "1"


def test_the_control_is_not_warm_started():
    """A warm seed is the opposite of a control."""
    assert "SB_WARM_SEED" not in _overrides(CONTROL)


def test_blanking_and_warm_starting_remain_mutually_exclusive():
    """run_suite refuses both at once; keep that guard, since this tier makes the flag reachable."""
    assert 'SB_EMPTY_SEED:-0}" = "1" ] && [ "${SB_WARM_SEED:-0}" = "1" ]' in \
        RUN_SUITE.read_text(encoding="utf-8")


def test_the_overrides_differ_from_full_verified_only_in_the_empty_seed_flag():
    ctrl, treat = _overrides(CONTROL), _overrides(TREATMENT)
    assert set(ctrl) - set(treat) == {"SB_EMPTY_SEED"}, (
        f"the control introduces settings beyond blanking the capability: "
        f"{sorted(set(ctrl) - set(treat))}"
    )
    assert not set(treat) - set(ctrl), f"the control drops {sorted(set(treat) - set(ctrl))}"


# --- it is dispatchable, and bounded -------------------------------------------------------


def _env_expr(key: str) -> str:
    for ln in WORKFLOW.read_text(encoding="utf-8").splitlines():
        if ln.strip().startswith(f"{key}:") and "${{" in ln:
            return ln.split(":", 1)[1].strip()
    raise AssertionError(f"no env expression for {key}")


def _evaluate(expr: str, *, tier: str, value: str = "") -> str:
    py = expr.strip()[3:-2]
    py = re.sub(r"(?:github\.event\.)?inputs\.[a-z_]+", repr(value), py)
    py = py.replace("matrix.tier", repr(tier)).replace("&&", " and ").replace("||", " or ")
    out = eval(py, {"__builtins__": {}}, {})  # noqa: S307 - fixed, repo-owned expression
    return "" if out is False else str(out)


def test_the_tier_is_registered_and_selectable():
    src = WORKFLOW.read_text(encoding="utf-8")
    tiers = re.findall(r'"([^"]+)"', re.search(r"^\s*TIERS = \[([^\]]*)\]", src, re.M).group(1))
    assert "no_skill" in tiers, f"unregistered tier cannot be dispatched: {tiers}"
    options = re.search(r"^\s*options: \[(all, smoke[^\]]*)\]", src, re.M).group(1)
    assert "no_skill" in options, f"tier picker cannot select it: {options}"


def test_the_tier_runs_only_when_named():
    """It is a one-off measurement, not something `tier=all` should sweep into every dispatch."""
    src = WORKFLOW.read_text(encoding="utf-8")
    explicit = re.search(r"EXPLICIT_ONLY_TIERS = \{([^}]*)\}", src).group(1)
    assert "no_skill" in explicit


def test_a_blank_dispatch_uses_one_trial():
    """280 sealed tasks x 10 trials would not finish inside timeout-minutes (see #526)."""
    assert _evaluate(_env_expr("NUM_TRIALS"), tier="no_skill") == "1"


def test_the_tier_name_stays_generic():
    """Same rule as full_verified: no digits, no benchmark name — any bench can populate it."""
    assert not re.search(r"\d", "no_skill")
    assert CONTROL.name == "no_skill"


# --- regenerable ---------------------------------------------------------------------------


def test_the_control_is_reproducible_from_the_committed_generator():
    """Guards drift: whatever regenerates full_verified must regenerate this identically."""
    gen = SB / "utils" / "make_split.py"
    out = subprocess.run(
        ["python3", str(gen), "--tasks", str(CONTROL / "tasks.json"),
         "--out", str(CONTROL / "split_ids.json")],
        capture_output=True, text=True, check=True,
    )
    assert out.stdout == (CONTROL / "split_ids.json").read_text(encoding="utf-8")


def test_shell_libs_stay_valid():
    for p in (RUN_SUITE, CI_SETUP):
        assert subprocess.run(["bash", "-n", str(p)]).returncode == 0
