"""A dispatch that sets nothing must still get the spend ceiling the workflow claims to apply.

`optimizer_usd_per_iter` declared `default: "0"`. In a GitHub `||` chain only the EMPTY string
is falsy — `"0"` is truthy (only the NUMBER 0 is falsy) — so the input always won and

    OPTIMIZER_USD_PER_ITER: ${{ inputs.optimizer_usd_per_iter || (matrix.tier == 'smoke' && '50' || '0') }}

could never reach its own smoke branch. Two consequences: smoke's $50/iteration cap was dead
code, and because 0 means UNLIMITED (run_suite.sh omits the spend clause from the derived
agent-mode `stop_condition` entirely when the value is 0) every blank dispatch ran with no
dollar ceiling at all. On run 35861572021 the operator had to pass `optimizer_usd_per_iter=50`
by hand to bound an Opus 5 agent loop.

The repo already documents this exact rule, for the knob that got it right — from
`test_an_explicit_iterations_dispatch_reaches_smoke`:

    NUM_TRIALS already had this right, including the reason its input default is `""` (with a
    non-empty default, "asked for 10" and "asked for nothing" are indistinguishable).

`iterations` and `trials` both declare `""`. `optimizer_usd_per_iter` was the only input in the
file that broke the rule, so the last test here pins it for ALL of them rather than one.
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "benchmarks.yml"
RUN_SUITE = REPO / "ci" / "benchmarks" / "lib" / "run_suite.sh"

KEY = "optimizer_usd_per_iter"
ENV_KEY = "OPTIMIZER_USD_PER_ITER"


def _env_expr(key: str) -> str:
    for ln in WORKFLOW.read_text(encoding="utf-8").splitlines():
        if ln.strip().startswith(f"{key}:") and "${{" in ln:
            return ln.split(":", 1)[1].strip()
    raise AssertionError(f"no env expression for {key}")


def _input_block(name: str) -> str:
    """This input's own lines, up to the next input key.

    The terminator must be a line indented EXACTLY six spaces: splitting on `"\\n      "`
    also matches the eight-space body lines (`        description:`), which truncates the
    block to nothing.
    """
    src = WORKFLOW.read_text(encoding="utf-8")
    parts = src.split(f"\n      {name}:\n", 1)
    assert len(parts) == 2, f"no workflow_dispatch input named {name}"
    return re.split(r"\n {6}(?=\S)", parts[1], maxsplit=1)[0]


def _input_default(name: str) -> str:
    m = re.search(r'^\s+default:\s*"?([^"\n]*)"?\s*$', _input_block(name), re.M)
    assert m, f"input {name} declares no default"
    return m.group(1)


def _evaluate(expr: str, *, tier: str, value: str) -> str:
    """Evaluate the env expression as GitHub would. Python's truthiness matches GitHub's for
    these string operands — '' falsy, '0' truthy — so the expression translates directly."""
    body = expr.strip()
    assert body.startswith("${{") and body.endswith("}}"), body
    py = body[3:-2]
    py = re.sub(r"(?:github\.event\.)?inputs\.[a-z_]+", repr(value), py)
    py = py.replace("matrix.tier", repr(tier)).replace("&&", " and ").replace("||", " or ")
    out = eval(py, {"__builtins__": {}}, {})  # noqa: S307 - fixed, repo-owned expression
    return "" if out is False else str(out)


def _blank(tier: str) -> str:
    return _evaluate(_env_expr(ENV_KEY), tier=tier, value=_input_default(KEY))


# --- what a blank dispatch actually gets ---------------------------------------------------


def test_a_blank_smoke_dispatch_gets_the_fifty_dollar_cap():
    """The bug: this resolved to '0' (unlimited), so smoke's own cap never applied."""
    assert _blank("smoke") == "50", (
        f"blank smoke resolves to {_blank('smoke')!r}; the workflow's '50' branch is still "
        "unreachable because the input default is truthy"
    )


@pytest.mark.parametrize("tier", ["full", "full_verified", "pilot"])
def test_a_blank_dispatch_on_other_tiers_stays_unlimited(tier):
    """Unchanged behaviour: only smoke gains a ceiling from this fix."""
    assert _blank(tier) == "0"


def test_an_explicit_zero_still_means_unlimited():
    """`0` is documented as "disable the cap"; typing it deliberately must keep working."""
    assert _evaluate(_env_expr(ENV_KEY), tier="smoke", value="0") == "0"


@pytest.mark.parametrize("asked", ["4.0", "50", "0.5"])
@pytest.mark.parametrize("tier", ["smoke", "full_verified"])
def test_an_explicit_value_wins_on_every_tier(tier, asked):
    assert _evaluate(_env_expr(ENV_KEY), tier=tier, value=asked) == asked


def test_the_input_default_is_empty_so_blank_is_distinguishable():
    """The fix itself, and the rule the file already documents for NUM_TRIALS."""
    assert _input_default(KEY) == "", (
        f"{KEY} declares default {_input_default(KEY)!r}; a non-empty default is truthy in the "
        "`||` chain and makes every tier fallback below it unreachable"
    )


def test_the_description_no_longer_claims_unconditional_unlimited():
    """It said "default unlimited", which was accidentally true only because of the bug."""
    desc = _input_block(KEY)
    assert "default unlimited" not in desc, (
        "the description still claims an unconditional unlimited default"
    )
    assert "smoke" in desc, "the description should say which tier gets a ceiling by default"


# --- end to end: the ceiling reaches the agent's stop condition ----------------------------


def _algorithm_block() -> str:
    src = RUN_SUITE.read_text(encoding="utf-8")
    start = src.index("ALGORITHM=\"${ALGORITHM:-}\"")
    return src[start:src.index("# ---- end algorithm selection", start)]


def _stop_condition(**env: str) -> str:
    script = _algorithm_block() + '\nprintf "%s" "$STOP_CONDITION"\n'
    p = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", **env})
    assert p.returncode == 0, p.stderr
    return p.stdout


def test_a_blank_smoke_agent_run_now_carries_a_dollar_ceiling():
    """agent-optimize is ONE long agent process, so the per-iteration cap becomes a whole-loop
    cap of cap x rounds. Before this fix a blank dispatch produced no dollar clause at all."""
    stop = _stop_condition(ALGORITHM="agent-optimize", ITERATIONS="3",
                           OPTIMIZER_USD_PER_ITER=_blank("smoke"))
    assert "150.00" in stop, f"no whole-loop ceiling derived from the smoke default: {stop}"


def test_an_unlimited_tier_still_gets_no_dollar_clause():
    """Regression: 0 must keep meaning unlimited, with the clause omitted rather than $0."""
    stop = _stop_condition(ALGORITHM="agent-optimize", ITERATIONS="10",
                           OPTIMIZER_USD_PER_ITER=_blank("full_verified"))
    assert "spend reaches" not in stop, f"a $0 ceiling leaked into the stop condition: {stop}"


# --- the rule, for every input ------------------------------------------------------------


def _inputs_with_env_fallbacks() -> list[tuple[str, str, str]]:
    """(input name, declared default, env expression) for every input used in an `||` chain."""
    src = WORKFLOW.read_text(encoding="utf-8")
    out = []
    for ln in src.splitlines():
        m = re.search(r"\$\{\{\s*(?:github\.event\.)?inputs\.([a-z_]+)\s*\|\|", ln)
        if m and ln.strip().split(":", 1)[0].isupper():
            name = m.group(1)
            out.append((name, _input_default(name), ln.split(":", 1)[1].strip()))
    return out


def test_no_input_shadows_its_own_tier_fallback():
    """Generalizes the bug: an input with a NON-EMPTY default is always truthy, so every
    alternative in its `||` chain is dead code. Either the default is empty, or the fallback
    must be the identical literal (in which case the chain is a no-op and harmless).

    This is the guard that stops the next input added to this file repeating it.
    """
    offenders = []
    for name, default, expr in _inputs_with_env_fallbacks():
        if default == "":
            continue                        # falsy default: the chain works as written
        tail = expr.split("||", 1)[1]
        alternatives = set(re.findall(r"'([^']*)'", tail)) - {default}
        # A tier name inside a comparison is not an alternative VALUE.
        alternatives -= {"smoke", "pilot", "full", "full_verified", "all"}
        if alternatives:
            offenders.append(f"{name}: default={default!r} but fallback offers {sorted(alternatives)}")
    assert not offenders, (
        "these inputs have non-empty defaults that make their fallbacks unreachable:\n  "
        + "\n  ".join(offenders)
    )
