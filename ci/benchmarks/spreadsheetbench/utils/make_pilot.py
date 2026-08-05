#!/usr/bin/env python3
"""Generate the SpreadsheetBench `pilot` tier — a MEASUREMENT RIG, not a comparison.

WHY
    Before spending ~$450 and many hours on 912 tasks x 3 seeds, two numbers have to be
    measured rather than guessed:
      1. cost and wall-clock per rollout at `MAX_TURNS=30` (full's setting). Every existing
         anchor comes from smoke at 5 turns, so it is not transferable.
      2. whether `azure/gpt-5.5` — the SkillOpt comparison model — actually works on the
         gateway at all. Nothing has exercised it yet.
    Recalc throughput at non-trivial volume falls out of the same run.

DESIGN — deliberately NOT 2:1:7
    The split is ~5 train / 50 selection / 5 test, because the pilot's job is measurement:
      - `val` (selection) is what every iteration evaluates, so it is sized to be a solid
        anchor. Full's val is 91, so one pilot iteration costs ~50/91 of one full iteration
        and extrapolates directly.
      - `test` is tiny because `finalize` evaluates it TWICE (best + baseline) and those
        rollouts teach us nothing new about per-rollout cost.
      - `train` is tiny because with `algorithm_focus: all` the train split is never
        evaluated (only `hardest-first` scores it).

    >>> The pilot's REWARD NUMBERS ARE NOT COMPARABLE TO ANYTHING. A 5-task test split and a
    >>> 50-task selection split exist to measure cost, not quality. Never report a pilot
    >>> reward against SkillOpt, against the full tier, or on the benchmarks page.

TASK PROVENANCE
    Pilot tasks are drawn ONLY from full's **train** ids, so full's selection and test splits
    stay pristine — a pilot must not touch tasks whose scores will later be reported.

USAGE
    python3 ci/benchmarks/spreadsheetbench/utils/make_pilot.py            # print a summary
    python3 ci/benchmarks/spreadsheetbench/utils/make_pilot.py --write    # write the tier
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
BENCH_DIR = HERE.parent
FULL_SPLIT = BENCH_DIR / "full" / "split_ids.json"
PILOT_DIR = BENCH_DIR / "pilot"

SEED = 42                      # same seed discipline as make_split.py
N_TASKS = 60
RATIOS = (5, 50, 5)            # train : selection : test — see DESIGN above
AGENT = "azure/gpt-5.5"        # the SkillOpt comparison model this pilot exists to validate


def _build_split():
    spec = importlib.util.spec_from_file_location("_make_split", HERE / "make_split.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build_split


def pilot_task_ids() -> list[str]:
    """Deterministically pick N_TASKS ids from full's TRAIN split only."""
    train = sorted(str(i) for i in json.loads(FULL_SPLIT.read_text(encoding="utf-8"))["train"])
    if len(train) < N_TASKS:
        raise SystemExit(f"full train split has only {len(train)} ids, need {N_TASKS}")
    picked = list(train)
    random.Random(SEED).shuffle(picked)
    return sorted(picked[:N_TASKS])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="write pilot/tasks.json + split_ids.json")
    args = ap.parse_args(argv)

    ids = pilot_task_ids()
    tasks = [{"id": i, "tag": "pilot", "agent": AGENT} for i in ids]
    split = _build_split()(ids, seed=SEED, ratios=RATIOS)

    tasks_payload = json.dumps(tasks, indent=2) + "\n"
    split_payload = json.dumps(split, indent=2, sort_keys=True) + "\n"

    # A pilot task must never come from full's val/test — that is the whole point of drawing
    # from train, so assert it rather than trusting the code above.
    full = json.loads(FULL_SPLIT.read_text(encoding="utf-8"))
    leak = (set(ids) & set(map(str, full["val"]))) | (set(ids) & set(map(str, full["test"])))
    if leak:
        raise SystemExit(f"pilot would touch full's held-out tasks: {sorted(leak)[:5]}")

    if args.write:
        PILOT_DIR.mkdir(parents=True, exist_ok=True)
        (PILOT_DIR / "tasks.json").write_text(tasks_payload, encoding="utf-8")
        (PILOT_DIR / "split_ids.json").write_text(split_payload, encoding="utf-8")
        print(f"wrote {PILOT_DIR}/: {len(ids)} tasks, "
              f"train={len(split['train'])} val={len(split['val'])} test={len(split['test'])} "
              f"agent={AGENT}")
    else:
        print(f"{len(ids)} tasks; train={len(split['train'])} "
              f"val={len(split['val'])} test={len(split['test'])}; agent={AGENT}")
        print("all drawn from full's train split (val/test untouched)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
