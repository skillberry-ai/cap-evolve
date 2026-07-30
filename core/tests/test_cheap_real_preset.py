"""The cheap_real preset's honesty invariants — the things a "make it cheaper" edit breaks.

The preset (``examples/cheap_real/capevolve.yaml``) exists to be the CHEAP rung, so the
obvious future edit is to shrink it further. Two of its values are load-bearing and
would fail silently or confusingly if changed:

* the dataset size and split ratios must land ``val`` at or above the floors in
  ``splits`` — below ``MIN_VAL_TASKS`` a run dies mid-flight inside ``gate.decide``
  (#113) *after* the budget is spent, and below ``LOW_CONFIDENCE_VAL_TASKS`` every
  decision is branded low-confidence. So val is pinned by a test, not by a comment.
* ``protected_paths`` must stay ABSENT. Since #142/#197 an empty list is a hard error
  and a present list REPLACES the layout defaults, so the only way this preset gets the
  adapter + dataset + spec guarded is to omit the key entirely.

Both are cheap file reads: no model, no run.
"""

from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
PRESET = REPO / "examples" / "cheap_real" / "capevolve.yaml"
TASKS = REPO / "examples" / "cheap_real" / "tasks.jsonl"

sys.path.insert(0, str(REPO / "core"))


def _spec() -> dict:
    from cap_evolve.specfile import read_yaml
    return read_yaml(PRESET.read_text(encoding="utf-8"))


def _task_ids() -> list[str]:
    import json
    return [json.loads(ln)["id"]
            for ln in TASKS.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_split_clears_the_honest_gate_floors():
    from cap_evolve.splits import make_splits
    import cap_evolve.splits as splits

    spec = _spec()
    ids = _task_ids()
    assert len(ids) == len(set(ids)), "duplicate task ids would corrupt the split"
    sp = make_splits(ids, seed=int(spec["split_seed"]),
                     ratios=(float(spec["split_train"]), float(spec["split_val"]),
                             float(spec["split_test"])))
    # MIN_VAL_TASKS is the hard floor (gate.decide refuses below it); it only exists
    # once #113 lands, so tolerate its absence rather than skip the whole assertion.
    hard = getattr(splits, "MIN_VAL_TASKS", 2)
    soft = getattr(splits, "LOW_CONFIDENCE_VAL_TASKS", 5)
    assert len(sp.val) >= hard, (
        f"cheap_real val split is {len(sp.val)}, below the hard floor {hard}: the run "
        "would die inside gate.decide after spending its budget")
    assert len(sp.val) >= soft, (
        f"cheap_real val split is {len(sp.val)}, below {soft}: every gate decision "
        "would be branded LOW CONFIDENCE. Add tasks rather than lowering this.")
    assert sp.test, "the sealed test split must be non-empty"
    assert not (set(sp.train) & set(sp.val)), "train/val overlap makes val a fit metric"
    assert not (set(sp.test) & (set(sp.train) | set(sp.val))), "the test split leaked"


def test_protected_paths_is_omitted_not_empty():
    # An empty list is a hard error since #142/#197, and a present list replaces the
    # layout defaults — omission is what protects adapters/, the dataset and the spec.
    for line in PRESET.read_text(encoding="utf-8").splitlines():
        assert not line.strip().startswith("protected_paths:"), (
            "cheap_real must OMIT protected_paths: an empty list is a hard error and a "
            "declared list would silently replace the defaults that cover the grader.")


def test_dataset_source_names_the_real_file():
    # #142/#197's guard hashes the path `dataset_source` names, so `adapter` here would
    # leave the answer key unprotected.
    assert _spec()["dataset_source"] == "tasks.jsonl"


def test_budget_is_bounded():
    # The whole point of the rung: it cannot silently become the multi-hour run.
    spec = _spec()
    assert 0 < float(spec["max_usd"]) <= 5.0
    assert 0 < float(spec["max_optimizer_usd"]) <= float(spec["max_usd"])
    assert 0 < int(spec["max_iterations"]) <= 5
