"""A run that accepted NOTHING advertised an improvement it had not made.

On a no-holdout tier (`smoke`: train==val==test) `metrics.suite_report` takes the baseline
side from `baseline.json` (the val eval of the seed) and the optimized side from `final.json`
(the test eval of `best_id`). When `best_id == "seed"` — no candidate cleared the gate — those
two evals score the SAME BYTES, so every difference between them is re-measurement noise.
Nothing subtracted it, so the report published it as progress.

Measured on smoke spreadsheetbench run 32971129203, whose three rounds were all rejected:

    **Suite (train-fit):** mean reward 0.500 -> 0.544 (Δ +0.044 (+9% rel))
    · best = seed (no candidate beat baseline)

with per-task rows to match — `47484` "0.667 -> 1.000 (+0.333)" and `53161`
"1.000 -> 0.667 (-0.333)" — for a capability that was never edited. The +0.044 was exactly
the replicate noise `round.py` had measured that run at (`null_delta_between_control
_replicates: 0.0444`). The parenthetical "best = seed (no candidate beat baseline)" is the
only contradicting signal in the document, and it loses to the headline number.

This is not agent-optimize-specific: any run of any algorithm that accepts nothing hits it.
It reaches published history too, because `metrics.jsonl` feeds `record.rollup` and the
benchmarks page.

The held-out path was already correct (see test_benchmarks_holdout_base_opt.py) because
`final.json` carries `test_baseline` and `test` over the same sealed split, and with
`best_id == "seed"` those are the same numbers. Only the no-holdout fallback was exposed.
"""

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "ci" / "benchmarks" / "lib"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _metrics():
    if str(LIB) not in sys.path:
        sys.path.insert(0, str(LIB))
    return _load("_bench_metrics_null", LIB / "metrics.py")


def _pt(task_id, reward):
    return {"task_id": task_id, "reward": reward, "raw": {"errored": False}}


def _null_run(tmp: Path) -> Path:
    """A no-holdout run where NOTHING was accepted, so best_id stays `seed`.

    val and test carry the same task ids (train==val==test) and DIFFERENT rewards — the
    two independent measurements of one unchanged capability that the real run produced.
    val mean 0.500, test mean 0.667: a phantom +0.167.
    """
    rd = tmp / "run_suite"
    rd.mkdir(parents=True)
    ids = ["t1", "t2", "t3"]
    (rd / "baseline.json").write_text(json.dumps({
        "val": {"split": "val", "reward": 0.5, "stderr": 0.14,
                "per_task": [_pt("t1", 0.0), _pt("t2", 0.5), _pt("t3", 1.0)]},
        "best_id": "seed",
    }))
    (rd / "final.json").write_text(json.dumps({
        "test": {"split": "test", "reward": 0.6667, "stderr": 0.14,
                 "per_task": [_pt("t1", 0.5), _pt("t2", 0.5), _pt("t3", 1.0)]},
        "best_id": "seed",
    }))
    (rd / "state.json").write_text(json.dumps({
        "best_id": "seed",
        "spent": {"iterations": 3, "optimizer_usd": 7.95},
    }))
    (rd / "events.jsonl").write_text("")
    assert set(ids) == {"t1", "t2", "t3"}
    return rd


def test_a_null_run_publishes_a_zero_per_task_delta(tmp_path):
    m = _metrics()
    rd = _null_run(tmp_path)
    jsonl = tmp_path / "metrics.jsonl"
    m.suite_report(str(rd), "spreadsheetbench", "smoke", "Azure/gpt-5-mini-2025-08-07", 3,
                   jsonl_path=str(jsonl))
    rows = [json.loads(l) for l in jsonl.read_text().splitlines()]

    assert rows, "no per-task rows were written"
    assert all(r["reward_delta"] == 0.0 for r in rows), (
        "a run that accepted nothing published per-task gains from re-measurement noise: "
        f"{[(r['task'], r['reward_delta']) for r in rows]}")
    assert all(r["reward_opt"] == r["reward_baseline"] for r in rows), (
        "base and opt are the same bytes, so they must report the same reward: "
        f"{[(r['task'], r['reward_baseline'], r['reward_opt']) for r in rows]}")


def test_a_null_run_does_not_roll_up_into_published_history_as_a_gain(tmp_path):
    """metrics.jsonl feeds record.rollup and the benchmarks page — the durable harm."""
    m = _metrics()
    if str(LIB) not in sys.path:
        sys.path.insert(0, str(LIB))
    rec = _load("_bench_record_null", LIB / "record.py")

    rd = _null_run(tmp_path)
    jsonl = tmp_path / "metrics.jsonl"
    m.suite_report(str(rd), "spreadsheetbench", "smoke", "Azure/gpt-5-mini-2025-08-07", 3,
                   jsonl_path=str(jsonl))
    rows = [json.loads(l) for l in jsonl.read_text().splitlines()]

    suite = rec.rollup(rows, [])
    assert suite is not None
    assert suite["reward_base"] == suite["reward_opt"], (
        f"published history records a gain for a run that changed nothing: {suite}")


def test_the_report_headline_states_no_change_rather_than_noise(tmp_path):
    m = _metrics()
    md = m.suite_report(str(_null_run(tmp_path)), "spreadsheetbench", "smoke",
                        "Azure/gpt-5-mini-2025-08-07", 3)

    assert "+17% rel" not in md and "+0.167" not in md, (
        f"the headline still advertises re-measurement noise as a gain:\n{md}")
    assert "0.500 → 0.500" in md, f"the suite line must show no change:\n{md}"
    assert "no candidate beat baseline" in md


def test_the_re_measurement_is_still_reported_as_a_noise_reading(tmp_path):
    """Suppressing the phantom delta must not throw the information away: two evals of one
    unchanged capability are a free read on the tier's noise floor, and the reader needs it
    to judge whether the run could have resolved a real effect at all."""
    m = _metrics()
    md = m.suite_report(str(_null_run(tmp_path)), "spreadsheetbench", "smoke",
                        "Azure/gpt-5-mini-2025-08-07", 3)

    assert "0.667" in md, f"the seed's re-measurement is gone entirely:\n{md}"
    assert "noise" in md.lower(), (
        f"the re-measurement is shown without saying what it is:\n{md}")


def test_a_run_that_DID_accept_a_candidate_is_untouched(tmp_path):
    """The guard must key on best_id, not on the tier — a real smoke win still reports."""
    m = _metrics()
    rd = _null_run(tmp_path)
    for name in ("final.json", "state.json"):
        d = json.loads((rd / name).read_text())
        d["best_id"] = "cand_3"
        (rd / name).write_text(json.dumps(d))

    jsonl = tmp_path / "metrics.jsonl"
    md = m.suite_report(str(rd), "spreadsheetbench", "smoke", "Azure/gpt-5-mini-2025-08-07", 3,
                        jsonl_path=str(jsonl))
    rows = {json.loads(l)["task"]: json.loads(l) for l in jsonl.read_text().splitlines()}

    assert rows["t1"]["reward_baseline"] == 0.0 and rows["t1"]["reward_opt"] == 0.5
    assert rows["t1"]["reward_delta"] == 0.5, "a real accepted candidate lost its delta"
    assert "0.500 → 0.667" in md, f"an accepted candidate must still report its gain:\n{md}"
