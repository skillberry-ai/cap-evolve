"""gate_k_se's blank-default contract (issue #544).

`gate_k_se` declared `default: "1.0"` and the workflow set
`GATE_K_SE: ${{ inputs.gate_k_se || '1.0' }}` unconditionally. Unlike
`optimizer_usd_per_iter` (see `test_benchmarks_optimizer_budget.py`), the bug here was not
just a dead tier-fallback branch: `ci/benchmarks/lib/load_overrides.sh` refuses to override a
key already present in the environment, so once the workflow set GATE_K_SE to *any* value —
even the literal '1.0' fallback — a tier's committed `overrides.env` could never correct it.
spreadsheetbench's full/pilot/full_verified tiers set SB_SCORING=hard (Bernoulli per-task
reward, wider gate SE) and need a paired GATE_K_SE=0.2, but could never actually get it: run
30890657732's cand_0003 scored 0.600, above the 0.580 champion, and was wrongly rejected
because gate_k_se=1.0 never let Δ=0.020 clear k_se·SE.

The fix, mirroring optimizer_usd_per_iter: the input default is "" (blank distinguishable from
an explicit value), and the workflow's GATE_K_SE assignment is a bare passthrough with NO
literal fallback — so a blank dispatch leaves GATE_K_SE unset for load_overrides.sh to fill
from overrides.env. The literal 1.0 fallback for tiers/benchmarks with no override moved to
run_suite.sh (`GATE_K_SE="${GATE_K_SE:-1.0}"`), which runs AFTER load_overrides.sh.
"""

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "benchmarks.yml"
RUN_SUITE = REPO / "ci" / "benchmarks" / "lib" / "run_suite.sh"
LOAD_OVERRIDES = REPO / "ci" / "benchmarks" / "lib" / "load_overrides.sh"

KEY = "gate_k_se"
ENV_KEY = "GATE_K_SE"


def _env_expr(key: str) -> str:
    for ln in WORKFLOW.read_text(encoding="utf-8").splitlines():
        if ln.strip().startswith(f"{key}:") and "${{" in ln:
            return ln.split(":", 1)[1].strip()
    raise AssertionError(f"no env expression for {key}")


def _input_block(name: str) -> str:
    src = WORKFLOW.read_text(encoding="utf-8")
    parts = src.split(f"\n      {name}:\n", 1)
    assert len(parts) == 2, f"no workflow_dispatch input named {name}"
    return re.split(r"\n {6}(?=\S)", parts[1], maxsplit=1)[0]


def _input_default(name: str) -> str:
    m = re.search(r'^\s+default:\s*"?([^"\n]*)"?\s*$', _input_block(name), re.M)
    assert m, f"input {name} declares no default"
    return m.group(1)


def test_the_input_default_is_empty_so_blank_is_distinguishable():
    """The fix itself: a non-empty default is truthy and makes overrides.env unreachable
    (this is worse than optimizer_usd_per_iter's dead-branch bug — see module docstring)."""
    assert _input_default(KEY) == "", (
        f"{KEY} declares default {_input_default(KEY)!r}; a non-empty default forces "
        "GATE_K_SE into the environment before load_overrides.sh runs, permanently blocking "
        "a tier's overrides.env from correcting it"
    )


def test_the_workflow_env_line_has_no_literal_fallback():
    """GATE_K_SE must NOT be assigned via a `|| 'literal'` chain in the workflow: any such
    fallback would set the env var unconditionally, which is exactly the bug. The literal
    fallback belongs in run_suite.sh, which runs after load_overrides.sh."""
    expr = _env_expr(ENV_KEY)
    assert "||" not in expr, (
        f"GATE_K_SE still has a workflow-level fallback ({expr!r}); this forces GATE_K_SE "
        "into the environment for every dispatch, blocking overrides.env"
    )


def test_a_blank_dispatch_resolves_to_the_input_default():
    """A blank workflow_dispatch resolves `inputs.gate_k_se` to the input's own default, so
    with no `||` fallback the env expression is just that default."""
    expr = _env_expr(ENV_KEY)
    assert re.fullmatch(r"\$\{\{\s*(?:github\.event\.)?inputs\.gate_k_se\s*\}\}", expr), expr


# --- run_suite.sh still supplies 1.0 for benchmarks/tiers with no override -----------------


def test_run_suite_still_defaults_gate_k_se_to_one_when_unset():
    p = subprocess.run(
        ["bash", "-c", 'GATE_K_SE="${GATE_K_SE:-1.0}"; printf "%s" "$GATE_K_SE"'],
        capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"},
    )
    assert p.returncode == 0, p.stderr
    assert p.stdout == "1.0"


def test_run_suite_source_still_contains_the_literal_fallback():
    src = RUN_SUITE.read_text(encoding="utf-8")
    assert 'GATE_K_SE="${GATE_K_SE:-1.0}"' in src, (
        "run_suite.sh must keep a literal 1.0 fallback for benchmarks/tiers that never set "
        "GATE_K_SE, so their behaviour is unchanged by this fix"
    )


# --- end to end: overrides.env can now actually correct GATE_K_SE, via the real script -----


def test_load_overrides_lets_a_blank_dispatch_pick_up_gate_k_se_from_overrides_env(tmp_path):
    """The crux of the fix, exercised against the real load_overrides.sh: an env var set to
    the EMPTY STRING (what a blank dispatch now produces) must not block the override, the way
    a non-empty '1.0' used to."""
    ov = tmp_path / "overrides.env"
    ov.write_text("GATE_K_SE=0.2\n")
    script = f'. "{LOAD_OVERRIDES}"; load_overrides "{ov}"; printf "%s" "$GATE_K_SE"'
    p = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", "GATE_K_SE": ""})
    assert p.returncode == 0, p.stderr
    assert p.stdout == "0.2", (
        f"blank-dispatch GATE_K_SE='' still blocked the override, got {p.stdout!r}"
    )


def test_load_overrides_still_respects_an_explicit_dispatch_value():
    ov_dir = REPO / "ci" / "benchmarks" / "spreadsheetbench" / "full"
    ov = ov_dir / "overrides.env"
    script = f'. "{LOAD_OVERRIDES}"; load_overrides "{ov}"; printf "%s" "$GATE_K_SE"'
    p = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", "GATE_K_SE": "0.7"})
    assert p.returncode == 0, p.stderr
    assert p.stdout == "0.7", "an explicit non-empty GATE_K_SE must still win over overrides.env"


# --- the paired override actually shipped --------------------------------------------------


def test_spreadsheetbench_hard_scoring_tiers_pair_gate_k_se_with_scoring():
    for tier in ("full", "pilot", "full_verified"):
        ov = REPO / "ci" / "benchmarks" / "spreadsheetbench" / tier / "overrides.env"
        text = ov.read_text(encoding="utf-8")
        assert "SB_SCORING=hard" in text, f"{tier}: expected SB_SCORING=hard"
        assert re.search(r"^GATE_K_SE=0\.2\s*$", text, re.M), (
            f"{tier}: expected a committed GATE_K_SE=0.2 pairing SB_SCORING=hard"
        )
