"""Two knobs for comparing against published skill-optimization results.

SpreadsheetBench is an OJ-style benchmark: each instruction ships ~3 spreadsheet test cases
(the vendored README: "2,729 test cases … an average of three test cases per instruction").
That yields two metrics, and mixing them silently flatters us because soft >= hard:

  soft (our default)  matches / 3          — partial credit per test case
  hard                1.0 iff all 3 match  — the "native hard score" published comparisons use

The adapter already computed both and recorded them as metrics; only `reward` was pinned to
soft, so the gate optimized soft while a comparison would read hard. SPREADSHEETBENCH_SCORING
now selects which one is the target, defaulting to soft (previous behaviour).

Separately: a "no skill" control needs the capability to be genuinely absent. Our committed
seed_capability/prompt.md is already a short expert prompt, so a run against it measures
"refine an existing prompt" rather than "author a skill from nothing" — a much easier task.
An EMPTY prompt.md must therefore mean no system message at all, and must NOT fall back to
the adapter's built-in default (which would measure that prompt while claiming no skill).
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ADAPTER_DIR = REPO / "templates" / "adapters" / "spreadsheetbench"
RUN_SUITE = REPO / "ci" / "benchmarks" / "lib" / "run_suite.sh"
LOADER = REPO / "ci" / "benchmarks" / "lib" / "load_overrides.sh"
WORKFLOW = REPO / ".github" / "workflows" / "benchmarks.yml"


def _load(scoring: str | None = None):
    """Import the adapter with SPREADSHEETBENCH_SCORING set, since it is read at import."""
    for p in (REPO / "core", ADAPTER_DIR, ADAPTER_DIR.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    prev = os.environ.get("SPREADSHEETBENCH_SCORING")
    if scoring is None:
        os.environ.pop("SPREADSHEETBENCH_SCORING", None)
    else:
        os.environ["SPREADSHEETBENCH_SCORING"] = scoring
    try:
        spec = importlib.util.spec_from_file_location(f"_sb_score_{scoring}", ADAPTER_DIR / "adapter.py")
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        if prev is None:
            os.environ.pop("SPREADSHEETBENCH_SCORING", None)
        else:
            os.environ["SPREADSHEETBENCH_SCORING"] = prev


# --- the scoring switch ------------------------------------------------------------------


def test_default_is_soft_so_existing_history_stays_comparable():
    assert _load(None).SCORING == "soft"


def test_hard_mode_is_accepted_and_normalized():
    assert _load("HARD ").SCORING == "hard"


def test_an_unknown_scoring_mode_fails_loudly_at_import():
    """A typo must not silently score soft for a run whose whole purpose is the hard number."""
    with pytest.raises(RuntimeError) as e:
        _load("hard-restriction")
    assert "SPREADSHEETBENCH_SCORING" in str(e.value)


def test_reward_follows_the_selected_metric_and_both_are_always_recorded():
    """Verified against the adapter source: score() must pick reward by SCORING and keep BOTH
    metrics, so either number is recoverable from any past run without re-running it."""
    src = (ADAPTER_DIR / "adapter.py").read_text(encoding="utf-8")
    assert 'reward=hard if SCORING == "hard" else soft' in src
    assert '"name": "soft_restriction"' in src and '"name": "hard_restriction"' in src
    assert '"primary": SCORING == "soft"' in src and '"primary": SCORING == "hard"' in src
    # hard must remain all-or-nothing over the test cases.
    assert "hard = 1.0 if all(test_results) else 0.0" in src


# --- the no-skill control ----------------------------------------------------------------


def test_an_empty_prompt_means_no_system_message_not_an_empty_one(tmp_path):
    """An empty system turn is not the same as no skill, and some providers reject it."""
    src = (ADAPTER_DIR / "adapter.py").read_text(encoding="utf-8")
    assert 'if system_prompt.strip() else []' in src, "blank prompt must yield NO system message"
    assert '{"role": "user", "content": user_msg}' in src, "the task message must still be sent"


def test_an_empty_prompt_file_does_not_fall_back_to_the_builtin_default(tmp_path):
    """The trap: prompt.md exists but is blank. Falling back would measure the adapter's own
    default prompt while the run claims to measure an unskilled agent."""
    mod = _load(None)
    (tmp_path / "prompt.md").write_text("", encoding="utf-8")
    assert mod._read_system_prompt(tmp_path) == ""


def test_a_missing_prompt_file_still_falls_back(tmp_path):
    """Absent means 'never materialized', which is a different situation from 'deliberately
    blank' — keep the existing safety net there."""
    mod = _load(None)
    assert mod._read_system_prompt(tmp_path) == mod._DEFAULT_SYSTEM_PROMPT


def test_the_committed_seed_is_not_empty_so_the_default_run_is_not_a_no_skill_run():
    """Guards the claim this whole file rests on: the default seed IS a skill."""
    seed = (ADAPTER_DIR / "seed_capability" / "prompt.md").read_text(encoding="utf-8")
    assert seed.strip(), "the committed seed must be non-empty"
    assert len(seed.split()) > 50, "…and substantive enough that runs against it are not 'no skill'"


# --- CI wiring ---------------------------------------------------------------------------


def test_run_suite_threads_both_knobs_with_previous_behaviour_as_default():
    sh = RUN_SUITE.read_text(encoding="utf-8")
    assert 'SPREADSHEETBENCH_SCORING="${SB_SCORING:-soft}"' in sh
    assert 'if [ "${SB_EMPTY_SEED:-0}" = "1" ]; then' in sh
    assert ': > "$PROJ/seed_capability/prompt.md"' in sh
    # The .env the adapter actually reads must carry it too, not just the exported shell var.
    assert "SPREADSHEETBENCH_SCORING=${SB_SCORING:-soft}" in sh
    # And the committed-overrides channel must be wired, since these have no workflow input.
    assert 'load_overrides "$REPO/ci/benchmarks/$BENCH/$TIER/overrides.env"' in sh


def test_gate_strictness_is_already_a_dispatch_input():
    """No code needed for the gate — recorded here so nobody adds a redundant knob."""
    wf = WORKFLOW.read_text(encoding="utf-8")
    assert "gate_k_se:" in wf and "GATE_K_SE: ${{ github.event.inputs.gate_k_se || '1.0' }}" in wf


def test_the_workflow_is_untouched_by_this_feature():
    """These knobs deliberately need NO workflow edit: the input list is full (dispatch caps
    at 10), and a committed overrides.env gives better provenance than a mutable repo var."""
    wf = WORKFLOW.read_text(encoding="utf-8")
    assert "SB_SCORING" not in wf and "SB_EMPTY_SEED" not in wf


# --- the committed-overrides loader ------------------------------------------------------


def _run_loader(tmp_path, file_body: str, preset: dict[str, str] | None = None) -> dict:
    """Execute the REAL loader in bash and report the resulting environment."""
    ov = tmp_path / "overrides.env"
    ov.write_text(file_body, encoding="utf-8")
    presets = "".join(f"{k}={v}\n" for k, v in (preset or {}).items())
    script = (
        f". {LOADER}\n{presets}load_overrides {ov}\n"
        r'for k in SB_SCORING SB_EMPTY_SEED GATE_K_SE; do eval "v=\${$k-<unset>}"; echo "$k=$v"; done' "\n" 
    )
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return dict(l.split("=", 1) for l in out.stdout.strip().splitlines())


def test_overrides_fill_in_unset_keys(tmp_path):
    env = _run_loader(tmp_path, "# a comment\n\nSB_SCORING=hard\nSB_EMPTY_SEED=1\n")
    assert env["SB_SCORING"] == "hard" and env["SB_EMPTY_SEED"] == "1"


def test_the_environment_wins_over_the_file(tmp_path):
    """A dispatch input must never be silently overridden by a committed default."""
    env = _run_loader(tmp_path, "GATE_K_SE=0.2\n", preset={"GATE_K_SE": "0.9"})
    assert env["GATE_K_SE"] == "0.9"


def test_malformed_lines_are_ignored_not_executed(tmp_path):
    """The file is parsed, never sourced — a committed config cannot run anything."""
    env = _run_loader(tmp_path, "bad key=x\nnot-an-assignment\nSB_SCORING=hard\n")
    assert env["SB_SCORING"] == "hard"
    assert env["SB_EMPTY_SEED"] == "<unset>"


def test_a_missing_overrides_file_is_a_no_op(tmp_path):
    script = f'. {LOADER}\nload_overrides {tmp_path}/nope.env\necho "ok=$?"\n'
    out = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    assert out.returncode == 0 and "ok=0" in out.stdout


def test_exactly_the_expected_tiers_ship_overrides_and_only_with_known_keys():
    """Every committed override is a deliberate deviation from the default, so each one is
    pinned here: a tier acquiring a config silently is how a run's numbers stop meaning what
    the reader thinks they mean.

    spreadsheetbench pilot+full optimize the HARD score, to be comparable with published work
    that reports a benchmark's native hard score (soft >= hard by construction).

    The pilot ALSO sets `SB_WARM_SEED=1`, and that is exactly the kind of deviation this test
    exists to make loud. Learning was not cumulative across runs: pilot 30799393875 learned
    "spill/volatile functions do not survive LibreOffice recalculation — write the literal" and
    fixed tasks 47741 and 51958, while pilot 30890657732 carried none of it and both regressed —
    2 tasks lost to forgetting rather than variance. The pilot therefore starts from the previous
    champion (a verbatim optimizer artifact; see seed_capability_warm/PROVENANCE.md). Its
    base->opt delta is consequently NOT comparable to a pristine-seed run's: absolute score
    higher, measured optimizer gain smaller. runmeta.json records "warm_seed": true so the
    difference travels with the number. The `full` tier deliberately stays pristine, so the
    headline result remains a from-scratch measurement.
    """
    shipped = {
        str(p.relative_to(REPO)): dict(
            line.split("=", 1) for line in p.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        )
        for p in sorted((REPO / "ci" / "benchmarks").glob("*/*/overrides.env"))
    }
    assert shipped == {
        "ci/benchmarks/spreadsheetbench/full/overrides.env": {"SB_SCORING": "hard"},
        "ci/benchmarks/spreadsheetbench/pilot/overrides.env": {
            "SB_SCORING": "hard", "SB_WARM_SEED": "1",
        },
        "ci/benchmarks/swebench/full/overrides.env": {
            "SWEBENCH_ADAPTER": "harbor",
        },
    }, "a tier gained or changed a committed override — say which and why in the PR"


def test_the_full_tier_stays_pristine_so_the_headline_is_from_scratch():
    """A warm-started `full` run would publish a sealed number whose baseline was already
    optimized — the one number that must stay a from-scratch measurement."""
    full = (REPO / "ci" / "benchmarks" / "spreadsheetbench" / "full" / "overrides.env")
    assert "SB_WARM_SEED" not in full.read_text(encoding="utf-8")


def test_the_shipped_overrides_do_not_pretend_to_set_workflow_owned_vars():
    """The workflow always sets GATE_K_SE/NUM_TRIALS/ITERATIONS/AGENT_MODEL, and the loader
    lets the environment win — so putting them here would look configured but do nothing."""
    workflow_owned = {"GATE_K_SE", "NUM_TRIALS", "ITERATIONS", "AGENT_MODEL",
                      "OPTIMIZER_MODEL", "SPLIT_SEED", "TIER", "ALGORITHM_FOCUS"}
    for p in sorted((REPO / "ci" / "benchmarks").glob("*/*/overrides.env")):
        keys = {l.split("=", 1)[0] for l in p.read_text(encoding="utf-8").splitlines()
                if l.strip() and not l.startswith("#")}
        assert not (keys & workflow_owned), f"{p.name} sets workflow-owned {keys & workflow_owned}"
