"""The `full_verified` tier: SpreadsheetBench's verified 400-task re-release, split as published.

WHY A FOURTH TIER

Recent skill-evolution work does not evaluate on the original 912-task SpreadsheetBench that
`full` runs. WikiSkill (arXiv 2608.27454v1) Table 6 reports, for SpreadSheet:

    Train 80 · Val 40 · Test 280        (= 400 tasks, exactly 2:1:7)

and states "All task splits and available toolsets are strictly matched with prior work
(Yang et al., 2026 [SkillOpt]; Alzubi et al., 2026 [EvoSkill])" — so the SkillOpt numbers
reported there are on the same 400 tasks. 80/40/280 also CONFIRMS the 2:1:7 reading that
`full`'s split was built on (Table 2's 4:1:5 is an ablation panel, not the headline).

So `full_verified` exists to produce a number that can sit next to those tables. It is a new tier
rather than a repointing of `full` so the 912 history stays interpretable and both can run.

WHY THE DATA CANNOT BE DERIVED FROM `full`

All 400 verified ids appear in the 912 set, which makes it look like a filter of
`full/tasks.json`. It is not — it is a re-release with corrected content:

  - 226 of the 400 instructions were rewritten (several substantively, not cosmetically)
  - 4 answer_positions changed
  - 61 of 394 resolvable golden workbooks differ byte-for-byte from the 912 answer
  - 1 graded test case per task, not 3, under different filenames (see _case_indices)

Filtering the 912 archive to these ids would score a DIFFERENT, older benchmark while
claiming comparability. The verified archive must be fetched as its own download.
"""

import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BENCH = REPO / "ci" / "benchmarks" / "spreadsheetbench"
TIER = BENCH / "full_verified"
TASKS = TIER / "tasks.json"
SPLIT = TIER / "split_ids.json"
GEN = BENCH / "utils" / "make_split.py"
FETCH_SH = BENCH / "fetch_data.sh"
CI_SETUP = REPO / "ci" / "benchmarks" / "lib" / "ci_setup.sh"
RUN_SUITE = REPO / "ci" / "benchmarks" / "lib" / "run_suite.sh"
WORKFLOW = REPO / ".github" / "workflows" / "benchmarks.yml"

# WikiSkill Table 6, SpreadSheet row.
PUBLISHED_SIZES = (80, 40, 280)


@pytest.fixture(scope="module")
def tasks():
    return json.loads(TASKS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def split():
    return json.loads(SPLIT.read_text(encoding="utf-8"))


# --- the task set -------------------------------------------------------------------------


def test_the_tier_ships_exactly_four_hundred_tasks(tasks):
    ids = [str(t["id"]) for t in tasks]
    assert len(ids) == 400, f"the verified release has 400 tasks, this tier has {len(ids)}"
    assert len(set(ids)) == 400, "duplicate task ids"


def test_every_verified_id_is_a_real_spreadsheetbench_id(tasks):
    """Cheap sanity check against the 912 list: the verified 400 is an id-subset of it.

    (The CONTENT is not a subset — see the module docstring — which is why the tier fetches
    its own archive rather than filtering full/tasks.json.)"""
    ids = {str(t["id"]) for t in tasks}
    known = {str(t["id"]) for t in json.loads((BENCH / "full" / "tasks.json").read_text(encoding="utf-8"))}
    assert ids <= known, f"{len(ids - known)} ids are in no known SpreadsheetBench release"


def test_the_tier_is_tagged_and_pins_one_agent_model(tasks):
    assert {t["tag"] for t in tasks} == {"full_verified"}
    models = {t["agent"] for t in tasks}
    assert len(models) == 1, f"a comparison tier must pin ONE agent model, got {models}"


def test_the_tier_uses_the_same_agent_model_as_full(tasks):
    """full_verified vs full must differ in the DATASET only, or the two numbers cannot be compared
    to each other. Changing the model axis is a separate, deliberate decision."""
    full = json.loads((BENCH / "full" / "tasks.json").read_text(encoding="utf-8"))
    assert {t["agent"] for t in tasks} == {t["agent"] for t in full}


# --- the split ----------------------------------------------------------------------------


def test_split_matches_the_published_train_val_test_sizes(split):
    sizes = (len(split["train"]), len(split["val"]), len(split["test"]))
    assert sizes == PUBLISHED_SIZES, (
        f"WikiSkill Table 6 reports {PUBLISHED_SIZES} for SpreadSheet; this split is {sizes}"
    )


def test_split_is_disjoint(split):
    tr, va, te = set(split["train"]), set(split["val"]), set(split["test"])
    assert not tr & va, f"train/val overlap on {len(tr & va)} tasks"
    assert not tr & te, f"train/test overlap on {len(tr & te)} tasks"
    assert not va & te, f"val/test overlap on {len(va & te)} tasks — test is NOT held out"


def test_split_covers_exactly_the_tier_tasks(split, tasks):
    ids = {str(t["id"]) for t in tasks}
    covered = set(split["train"]) | set(split["val"]) | set(split["test"])
    assert covered == ids, f"split covers {len(covered)} ids but the tier has {len(ids)}"


def test_split_is_reproducible_from_the_committed_generator():
    """Same generator, same seed 42, same 2:1:7 as `full` — only the task list differs."""
    out = subprocess.run(
        [sys.executable, str(GEN), "--tasks", str(TASKS), "--out", str(SPLIT)],
        capture_output=True, text=True, check=True,
    )
    assert out.stdout == SPLIT.read_text(encoding="utf-8"), (
        "committed split_ids.json differs from the generator's output — regenerate with "
        "`python3 ci/benchmarks/spreadsheetbench/utils/make_split.py "
        "--tasks ci/benchmarks/spreadsheetbench/full_verified/tasks.json "
        "--out ci/benchmarks/spreadsheetbench/full_verified/split_ids.json --write`"
    )


def test_split_does_not_reuse_fulls_partition(split):
    """A 2:1:7 draw over 400 ids is not the 912 draw restricted to those ids. Reusing the
    latter would leak `full`'s train tasks into `full_verified`'s test split."""
    full_split = json.loads((BENCH / "full" / "split_ids.json").read_text(encoding="utf-8"))
    ids = set(split["train"]) | set(split["val"]) | set(split["test"])
    restricted = {k: sorted(set(v) & ids) for k, v in full_split.items()}
    assert sorted(split["test"]) != restricted["test"]


# --- fetching the right archive -----------------------------------------------------------


def _resolve_variant(variant: str):
    """Run fetch_data.sh's real variant-resolution block and report what it picked."""
    src = FETCH_SH.read_text(encoding="utf-8")
    block = src[src.index('case "$VARIANT" in'):src.index("esac") + len("esac")]
    script = textwrap.dedent(f"""
        set -euo pipefail
        VARIANT={variant}
    """) + block + '\necho "URL=$URL"\necho "INNER=$INNER"\n'
    proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    return proc


def test_fetch_data_resolves_the_verified_400_variant():
    proc = _resolve_variant("verified_400")
    assert proc.returncode == 0, f"verified_400 is not a known variant: {proc.stderr}"
    out = dict(line.split("=", 1) for line in proc.stdout.strip().splitlines())
    assert out["URL"].endswith("spreadsheetbench_verified_400.tar.gz")
    assert out["INNER"] == "spreadsheetbench_verified_400", (
        "INNER must be the archive's real top-level dir, or the dataset.json check fails"
    )


def test_fetch_data_still_resolves_the_existing_variants():
    for variant, inner in (("sample_200", "sample_data_200"), ("full_912", "all_data_912_v0.1")):
        proc = _resolve_variant(variant)
        assert proc.returncode == 0, proc.stderr
        out = dict(line.split("=", 1) for line in proc.stdout.strip().splitlines())
        assert out["INNER"] == inner


def test_fetch_data_still_rejects_an_unknown_variant():
    proc = _resolve_variant("v2_321")
    assert proc.returncode != 0, "an unknown variant must fail loudly, not silently"
    assert "verified_400" in proc.stderr, "the error must list the variant that now exists"


def test_fetch_data_is_valid_bash():
    assert subprocess.run(["bash", "-n", str(FETCH_SH)]).returncode == 0


def test_ci_setup_fetches_the_verified_archive_for_this_tier():
    """full_verified must NOT get full_912's data — that would score the old benchmark."""
    sh = CI_SETUP.read_text(encoding="utf-8")
    arm = sh.split("  spreadsheetbench)", 1)[1].split("\n  *)", 1)[0]
    assert 'full_verified) SB_VARIANT="verified_400"' in arm, (
        "the full_verified tier must map to the verified_400 archive"
    )
    # and the existing mapping must be untouched
    assert 'full|pilot) SB_VARIANT="full_912"' in arm


# --- run configuration --------------------------------------------------------------------


def test_the_tier_gets_the_thirty_turn_budget_and_full_concurrency():
    """Turn budget is part of the comparison: smoke's 5 turns is not a comparable setting."""
    sh = RUN_SUITE.read_text(encoding="utf-8")
    arm = sh.split("  spreadsheetbench)", 1)[1].split("\n  *)", 1)[0]
    assert 'case "$TIER" in full|pilot|full_verified) SB_CONCURRENCY_DEFAULT=8;; esac' in arm
    assert 'case "$TIER" in full|pilot|full_verified) SB_MAX_TURNS_DEFAULT=30;; esac' in arm


def test_run_suite_is_valid_bash():
    assert subprocess.run(["bash", "-n", str(RUN_SUITE)]).returncode == 0


def _overrides() -> dict[str, str]:
    """The tier's real settings — assignments only, so prose about them does not count."""
    out = {}
    for line in (TIER / "overrides.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def test_the_tier_reports_the_hard_metric():
    assert _overrides().get("SB_SCORING") == "hard"


def test_the_tier_starts_from_the_pristine_seed():
    """A comparison tier's base->opt delta must be a from-scratch result, not the continuation
    of an earlier run's champion (contrast pilot, which sets SB_WARM_SEED=1 deliberately)."""
    assert "SB_WARM_SEED" not in _overrides()


def test_the_tier_is_a_known_tier_in_the_benchmarks_workflow():
    wf = WORKFLOW.read_text(encoding="utf-8")
    assert 'TIERS = ["smoke", "pilot", "full", "full_verified"]' in wf, (
        "an unregistered tier can never be dispatched — the planner emits no leg for it"
    )


def _tier_input_options() -> list[str]:
    """The `tier` dispatch input's choice list, parsed WITHOUT a YAML dependency.

    `core[dev]` ships pytest/openpyxl/pandas and nothing else, so `import yaml` fails in CI —
    and per pyproject's own note, a test that silently skips for a missing dep is worse than
    no test. The options are a one-line flow sequence, so the first `options:` after the
    `tier:` input key is unambiguous.
    """
    wf = WORKFLOW.read_text(encoding="utf-8")
    block = wf.split("\n      tier:\n", 1)
    assert len(block) == 2, "no `tier:` workflow_dispatch input found"
    m = re.search(r"^\s*options: \[([^\]]+)\]", block[1], re.M)
    assert m, "the tier input has no inline options list"
    return [o.strip() for o in m.group(1).split(",")]


def test_the_tier_name_carries_no_task_count():
    """The tier name is GENERIC on purpose: "this benchmark's verified/curated re-release".

    A name with the count baked in (`full400`) cannot be reused by another benchmark whose
    verified release is a different size, and goes stale if upstream re-cuts this one. The
    count belongs in the tier's assertions (see the tests above), not in its name.
    """
    assert TIER.name == "full_verified"
    assert not re.search(r"\d", TIER.name), f"tier name encodes a number: {TIER.name}"
    # and the tier registered in the workflow is the same generic name
    assert "full_verified" in _tier_input_options()
    assert not [t for t in _tier_input_options() if re.search(r"\d", t)], (
        "a tier option encodes a task count"
    )


def test_the_tier_is_dispatchable_from_the_workflow_ui():
    """`tier` is a `choice` input. A tier missing from its options cannot be selected, and
    since full_verified is deliberately excluded from `tier=all` that would leave it unreachable
    except by PR label."""
    options = _tier_input_options()
    # Guards the parser itself: if this stops finding the real list, the assertion below
    # would pass vacuously on some other `options:` line.
    assert options[:4] == ["all", "smoke", "pilot", "full"], f"parsed the wrong list: {options}"
    assert "full_verified" in options, f"tier input cannot select full_verified: {options}"


def test_the_tier_does_not_join_the_tier_all_sweep_yet():
    """`tier=all` already launches `full` (~2,279 rollouts/seed). Sweeping full_verified in as well
    would launch two four-figure legs per dispatch, and the tier's model axis is still open.
    It runs when named — `tier=full_verified`, or a `benchmark-full_verified-spreadsheetbench` label."""
    wf = WORKFLOW.read_text(encoding="utf-8")
    assert 'EXPLICIT_ONLY_TIERS = {"pilot", "full_verified"}' in wf


# --- documentation ------------------------------------------------------------------------


def test_the_tier_readme_warns_that_the_data_is_not_a_filter_of_the_912():
    """The single most expensive mistake available here is deriving this tier's tasks by
    filtering full/tasks.json. The README has to say why that is wrong."""
    txt = (BENCH / "README.md").read_text(encoding="utf-8")
    assert "full_verified" in txt
    lowered = txt.lower()
    assert "rewritten" in lowered or "re-release" in lowered
    assert "2608.27454" in txt, "cite the table the split sizes come from"
