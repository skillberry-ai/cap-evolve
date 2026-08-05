"""The committed SpreadsheetBench held-out split must stay valid, disjoint and reproducible.

Everything downstream of a benchmark comparison rests on the split being what it claims:
disjoint (so `finalize` is a real held-out number, not a fit), covering exactly the tier's
tasks (so a stale file cannot silently evaluate a different task set), and regenerable from
the committed generator (so the provenance claim in the README is checkable).

The split reconstructs SkillOpt's stated default — split_seed=42, 2:1:7 train/selection/test
(arXiv 2605.23904). Their SpreadsheetBench-specific split and task count are NOT published,
so this is a documented reconstruction, not a reproduction. See
ci/benchmarks/spreadsheetbench/utils/make_split.py.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BENCH = REPO / "ci" / "benchmarks" / "spreadsheetbench"
SPLIT = BENCH / "full" / "split_ids.json"
TASKS = BENCH / "full" / "tasks.json"
GEN = BENCH / "utils" / "make_split.py"


def _gen_module():
    spec = importlib.util.spec_from_file_location("_make_split", GEN)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def split():
    return json.loads(SPLIT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def task_ids():
    return [str(e["id"]) for e in json.loads(TASKS.read_text(encoding="utf-8"))]


def test_split_is_disjoint(split):
    """The whole point: a genuine held-out split, not the no-holdout FIT split."""
    tr, va, te = set(split["train"]), set(split["val"]), set(split["test"])
    assert not tr & va, f"train/val overlap on {len(tr & va)} tasks"
    assert not tr & te, f"train/test overlap on {len(tr & te)} tasks"
    assert not va & te, f"val/test overlap on {len(va & te)} tasks — test is NOT held out"


def test_split_covers_exactly_the_full_tier(split, task_ids):
    covered = set(split["train"]) | set(split["val"]) | set(split["test"])
    assert covered == set(task_ids), (
        f"split covers {len(covered)} ids but the tier has {len(set(task_ids))}"
    )
    # no id counted twice across the three parts
    assert len(split["train"]) + len(split["val"]) + len(split["test"]) == len(set(task_ids))


def test_split_matches_skillopts_stated_ratio(split):
    """2:1:7 over 912 tasks -> 182 / 91 / 639."""
    assert (len(split["train"]), len(split["val"]), len(split["test"])) == (182, 91, 639)


def test_committed_split_is_reproducible_from_the_generator():
    """Guards drift: the file must be exactly what the documented generator produces."""
    out = subprocess.run([sys.executable, str(GEN)], capture_output=True, text=True, check=True)
    assert out.stdout == SPLIT.read_text(encoding="utf-8"), (
        "committed split_ids.json differs from `make_split.py` output — regenerate with "
        "`python3 ci/benchmarks/spreadsheetbench/utils/make_split.py --write`"
    )


def test_generator_is_deterministic_and_seed_sensitive():
    mod = _gen_module()
    ids = [f"t{i}" for i in range(100)]
    a = mod.build_split(ids, seed=42, ratios=(2, 1, 7))
    b = mod.build_split(ids, seed=42, ratios=(2, 1, 7))
    c = mod.build_split(ids, seed=43, ratios=(2, 1, 7))
    assert a == b, "same seed must reproduce the same split"
    assert a != c, "a different seed must produce a different split"
    # order of the input must not matter — only the id SET
    assert mod.build_split(list(reversed(ids)), seed=42, ratios=(2, 1, 7)) == a


def test_generator_rejects_duplicate_ids():
    mod = _gen_module()
    with pytest.raises(ValueError, match="duplicate"):
        mod.build_split(["a", "b", "a"], seed=42, ratios=(2, 1, 7))


def test_generator_supports_the_alternative_4_1_5_reading():
    """Table 2's caption says 4:1:5 for an ablation panel; regenerating must be one flag."""
    mod = _gen_module()
    ids = [f"t{i}" for i in range(100)]
    s = mod.build_split(ids, seed=42, ratios=(4, 1, 5))
    assert (len(s["train"]), len(s["val"]), len(s["test"])) == (40, 10, 50)


def test_smoke_tier_still_has_no_committed_split():
    """Smoke must keep the no-holdout FIT split — the held-out path is opt-in per tier."""
    assert not (BENCH / "smoke" / "split_ids.json").exists(), (
        "a committed smoke split would silently change the smoke tier's meaning"
    )


def test_no_other_benchmark_opted_into_a_committed_split():
    """The run_suite hook is behaviour-neutral only while no OTHER benchmark ships this file.

    SpreadsheetBench deliberately ships two: `full` (the held-out comparison split) and
    `pilot` (the measurement rig). Any third path here means another benchmark's tier just
    changed meaning from FIT to held-out — which should be a deliberate decision, not a
    side effect, so this test is the place it gets noticed.
    """
    expected = {"ci/benchmarks/spreadsheetbench/full/split_ids.json",
                "ci/benchmarks/spreadsheetbench/pilot/split_ids.json"}
    found = {p.relative_to(REPO).as_posix()
             for p in (REPO / "ci" / "benchmarks").glob("*/*/split_ids.json")}
    unexpected = sorted(found - expected)
    assert not unexpected, f"unexpected committed splits would change those tiers: {unexpected}"
    assert found == expected, f"a documented split went missing: {sorted(expected - found)}"


# ---- the pilot tier (a measurement rig, not a comparison) --------------------

PILOT = BENCH / "pilot"


def test_pilot_tasks_come_only_from_fulls_train_split(split):
    """A pilot must never touch tasks whose scores will later be reported."""
    ids = {str(e["id"]) for e in json.loads((PILOT / "tasks.json").read_text(encoding="utf-8"))}
    assert ids <= set(split["train"]), "pilot tasks must be a subset of full's TRAIN split"
    assert not ids & set(split["val"]), "pilot touches full's selection split"
    assert not ids & set(split["test"]), "pilot touches full's SEALED test split"


def test_pilot_split_is_sized_for_measurement_not_comparison():
    """val large (that is what each iteration evaluates), train/test small and cheap."""
    ps = json.loads((PILOT / "split_ids.json").read_text(encoding="utf-8"))
    assert (len(ps["train"]), len(ps["val"]), len(ps["test"])) == (5, 50, 5)
    tr, va, te = set(ps["train"]), set(ps["val"]), set(ps["test"])
    assert not (tr & va) and not (tr & te) and not (va & te)


def test_pilot_split_covers_exactly_the_pilot_tasks():
    ids = {str(e["id"]) for e in json.loads((PILOT / "tasks.json").read_text(encoding="utf-8"))}
    ps = json.loads((PILOT / "split_ids.json").read_text(encoding="utf-8"))
    assert set(ps["train"]) | set(ps["val"]) | set(ps["test"]) == ids


def test_pilot_is_reproducible_from_its_generator():
    gen = BENCH / "utils" / "make_pilot.py"
    before = ((PILOT / "tasks.json").read_text(encoding="utf-8"),
              (PILOT / "split_ids.json").read_text(encoding="utf-8"))
    subprocess.run([sys.executable, str(gen), "--write"], capture_output=True, text=True, check=True)
    after = ((PILOT / "tasks.json").read_text(encoding="utf-8"),
             (PILOT / "split_ids.json").read_text(encoding="utf-8"))
    assert before == after, "pilot tier differs from make_pilot.py output — regenerate it"


def test_pilot_pins_the_skillopt_comparison_model():
    """The pilot exists partly to prove azure/gpt-5.5 works on the gateway at all."""
    tasks = json.loads((PILOT / "tasks.json").read_text(encoding="utf-8"))
    assert {t["agent"] for t in tasks} == {"azure/gpt-5.5"}
    assert {t["tag"] for t in tasks} == {"pilot"}
