"""The cheap_real preset's honesty invariants — the things a "make it cheaper" edit breaks.

The preset (``examples/cheap_real/capevolve.yaml``) exists to be the CHEAP rung, so the
obvious future edit is to shrink it further. Several of its values are load-bearing and
would fail silently or confusingly if changed:

* the dataset size and split ratios must land ``val`` at or above the floors in
  ``splits`` — below ``MIN_VAL_TASKS`` a run dies mid-flight inside ``gate.decide``
  (#113) *after* the budget is spent, and below ``LOW_CONFIDENCE_VAL_TASKS`` every
  decision is branded low-confidence. So val is pinned by a test, not by a comment.
* ``protected_paths`` must stay ABSENT. Since #142/#197 an empty list is a hard error
  and a present list REPLACES the layout defaults. Precisely: an omitted key resolves
  to ``[*_DEFAULT_GLOBS, *spec['dataset_source']]`` (``protect.py:168-170``), and
  ``tasks.jsonl`` matches **none** of the default globs (``adapters``,
  ``capevolve.yaml``, ``*gold*`` suffixes) — the answer key is guarded *by the
  dataset_source fold-in*, which only happens when the key is absent. Omission is
  load-bearing for the dataset specifically, not merely tidier.
* ``optimizer_max_turns`` must stay at or above the MEASURED floor: at 12 the agent
  exits ``Reached max turns``, which cap-evolve correctly reports as a failed
  iteration, so every candidate is discarded and the run looks like "the optimizer
  proposed nothing".
* ``run.sh``'s YAML rewrite is a line-PREFIX string rewriter over this preset, so it
  silently no-ops if a key it targets is ever indented or renamed. Pinned here because
  a no-op means the paid rung runs with ``optimizer_skill: mock``.

All are cheap file reads: no model, no run.
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


def test_optimizer_max_turns_clears_the_measured_floor():
    # MEASURED, not guessed: at 12 the agent exits `Reached max turns (12)`, cap-evolve
    # reports a failed iteration, and every candidate is discarded — the run looks like
    # "the optimizer proposed nothing". A "tighten the caps" edit must not go back there.
    assert int(_spec()["optimizer_max_turns"]) >= 40, (
        "optimizer_max_turns below 40 was MEASURED to make every iteration fail with "
        "`Reached max turns`, so no candidate survives. Raise it back.")


def test_run_sh_yaml_rewrite_still_matches_the_preset():
    # run.sh flips the optimizer keys with a line-PREFIX rewriter, so it silently
    # no-ops if a targeted key is ever indented or renamed — and a no-op means the
    # paid rung quietly runs `optimizer_skill: mock`. Run the real heredoc, not a copy.
    import re
    import tempfile
    run_sh = (REPO / "examples" / "cheap_real" / "run.sh").read_text(encoding="utf-8")
    m = re.search(r"<<'SED'\n(.*?)\nSED\n", run_sh, re.S)
    assert m, "run.sh no longer has the SED heredoc this test pins"

    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "capevolve.yaml"
        target.write_text(PRESET.read_text(encoding="utf-8"), encoding="utf-8")
        old_argv = sys.argv
        sys.argv = ["-", str(target), "claude-code", "claude-haiku-4-5"]
        try:
            exec(compile(m.group(1), "run.sh:SED", "exec"), {"__name__": "__main__"})
        finally:
            sys.argv = old_argv
        out = target.read_text(encoding="utf-8")

    assert "optimizer_skill: claude-code\n" in out, "the optimizer_skill flip no-opped"
    assert "optimizer_model: claude-haiku-4-5\n" in out
    assert "proposer_model: claude-haiku-4-5\n" in out
    instr = [ln for ln in out.splitlines()
             if ln.startswith("optimizer_instructions_file:")]
    assert len(instr) == 1, f"expected exactly one instructions line, got {instr}"
    assert Path(instr[0].split(":", 1)[1].strip()).is_absolute(), (
        "the instructions path must be ABSOLUTE: cli.py resolves a relative one against "
        "its own cwd and silently falls back to the generic template (see #252)")
