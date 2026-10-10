"""The evidence ledger pools trials by candidate bytes and top-ups never repeat a seed."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))

from cap_evolve import Budget, RunDir, eval_index, harness  # noqa: E402
from cap_evolve.types import Rollout, Score, Task  # noqa: E402


class _A:
    def __init__(self):
        self.seeds = []

    def tasks(self, split):
        return [Task(id="a"), Task(id="b")]

    def run_target(self, task, ctx, *, seed=0):
        self.seeds.append((task.id, seed))
        return Rollout(task_id=task.id, cost_usd=0.01, tokens=5)

    def score(self, task, rollout):
        return Score(task_id=task.id, reward=1.0 if task.id == "a" else 0.0)


def _rd(tmp_path):
    rd = RunDir.create(tmp_path / ".capevolve", ts="t", budget=Budget(max_iterations=1))
    harness.ensure_splits(_A(), rd, seed=0, split_ids={"train": [], "val": ["a", "b"], "test": []})
    return rd


def _cand(tmp_path, name, text="policy"):
    d = tmp_path / name
    d.mkdir()
    (d / "p.md").write_text(text)
    return d


def test_identical_bytes_under_different_tags_pool_on_one_hash(tmp_path):
    rd, ad = _rd(tmp_path), _A()
    s, c = _cand(tmp_path, "seed"), _cand(tmp_path, "ctl")
    harness.evaluate_candidate(ad, s, run_dir=rd, split="val", n_trials=2, tag="seed")
    harness.evaluate_candidate(ad, c, run_dir=rd, split="val", n_trials=1, tag="ctl_null")
    h = eval_index.cap_hash(s)
    assert h == eval_index.cap_hash(c)
    assert eval_index.counts(rd, h) == {"a": (3.0, 3), "b": (0.0, 3)}
    assert eval_index.next_trial_idx(rd, h, "a") == 3
    assert eval_index.missing(rd, h, ["a", "b", "z"], 4) == {"a": 1, "b": 1, "z": 4}


def test_changed_bytes_get_their_own_hash(tmp_path):
    assert eval_index.cap_hash(_cand(tmp_path, "x")) != eval_index.cap_hash(_cand(tmp_path, "y", "other"))


def test_subset_topup_adds_trials_with_fresh_seeds(tmp_path):
    rd, ad = _rd(tmp_path), _A()
    c = _cand(tmp_path, "c")
    harness.evaluate_candidate(ad, c, run_dir=rd, split="val", n_trials=2, tag="c", base_seed=10)
    ad.seeds.clear()
    harness.evaluate_candidate(ad, c, run_dir=rd, split="val", n_trials=2, tag="c", base_seed=10,
                               ids=["b"], trial_offset=2)
    assert ad.seeds == [("b", 12), ("b", 13)]
    files = sorted(p.name for p in (rd.rollouts / "val").glob("b__c__t*.json"))
    assert files == [f"b__c__t{k}.json" for k in range(4)]  # t0,t1 kept; t2,t3 added
    got = eval_index.counts(rd, eval_index.cap_hash(c))
    assert got["b"] == (0.0, 4) and got["a"] == (2.0, 2)


def test_recording_is_idempotent_and_can_be_disabled(tmp_path, monkeypatch):
    rd, ad = _rd(tmp_path), _A()
    c = _cand(tmp_path, "c")
    harness.evaluate_candidate(ad, c, run_dir=rd, split="val", n_trials=1, tag="c")
    assert eval_index.record(rd, c, "val", "c", ["a", "b"], range(1)) == 0
    monkeypatch.setenv("CAPEVOLVE_EVAL_LEDGER", "0")
    harness.evaluate_candidate(ad, c, run_dir=rd, split="val", n_trials=1, tag="d")
    assert len(eval_index.rows(rd)) == 2


def test_eval_cmd_carries_subset_and_offset(tmp_path):
    cmd = eval_index.eval_cmd(tmp_path, tmp_path, "t", "val", 3, ids=["1", "2"], trial_offset=3)
    assert cmd[cmd.index("--ids") + 1] == "1,2" and cmd[cmd.index("--trial-offset") + 1] == "3"
    assert "--ids" not in eval_index.eval_cmd(tmp_path, tmp_path, "t", "val", 3)


def test_injected_scratch_does_not_change_the_hash(tmp_path):
    a, b = _cand(tmp_path, "a"), _cand(tmp_path, "b")
    (b / "MEMORY.md").write_text("m")
    (b / "CLAUDE.md").write_text("c")
    (b / "trajectories").mkdir()
    (b / "trajectories" / "x.json").write_text("{}")
    (b / "guidance").mkdir()
    (b / "guidance" / "g.md").write_text("g")
    assert eval_index.cap_hash(a) == eval_index.cap_hash(b)


def test_a_new_tag_of_identical_bytes_gets_fresh_seeds(tmp_path):
    rd, ad = _rd(tmp_path), _A()
    harness.evaluate_candidate(ad, _cand(tmp_path, "s"), run_dir=rd, split="val", n_trials=2, tag="s", base_seed=0)
    ad.seeds.clear()
    harness.evaluate_candidate(ad, _cand(tmp_path, "k"), run_dir=rd, split="val", n_trials=1, tag="ctl", base_seed=0)
    assert {sd for _, sd in ad.seeds} == {2}
    h = eval_index.cap_hash(tmp_path / "s")
    assert sorted(r["trial_idx"] for r in eval_index.rows(rd) if r["task"] == "a") == [0, 1, 2]
    assert eval_index.next_trial_idx(rd, h) == 3


def test_concurrent_records_do_not_lose_or_duplicate_rows(tmp_path):
    import threading
    rd, ad = _rd(tmp_path), _A()
    cs = [_cand(tmp_path, f"c{i}") for i in range(4)]
    for i, c in enumerate(cs):
        harness.evaluate_candidate(ad, c, run_dir=rd, split="val", n_trials=1, tag=f"c{i}")
    eval_index.backfill(rd)
    (rd.root / eval_index.LEDGER).unlink()
    ts = [threading.Thread(target=eval_index.record, args=(rd, c, "val", f"c{i}", ["a", "b"], range(1)))
          for i, c in enumerate(cs)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(eval_index.rows(rd)) == 8


def test_test_split_is_never_indexed(tmp_path):
    rd = _rd(tmp_path)
    c = _cand(tmp_path, "c")
    f = rd.rollouts / "test" / "a__c__t0.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text('{"rollout": {}, "score": {"reward": 1}}')
    assert eval_index.record(rd, c, "test", "c", ["a"], range(1)) == 0


def test_reevaluated_tag_replaces_its_rows_and_backfill_rebuilds(tmp_path):
    rd, ad = _rd(tmp_path), _A()
    c = _cand(tmp_path, "c")
    harness.evaluate_candidate(ad, c, run_dir=rd, split="val", n_trials=1, tag="c")
    h = eval_index.cap_hash(c)
    f = rd.rollouts / "val" / "a__c__t0.json"
    f.write_text(f.read_text().replace('"reward": 1.0', '"reward": 0.0'))
    eval_index.record(rd, c, "val", "c", ["a"], range(1))
    assert eval_index.counts(rd, h)["a"] == (0.0, 1)
    (rd.root / eval_index.LEDGER).unlink()
    (rd.work if hasattr(rd, "work") else rd.root / "work").mkdir(exist_ok=True)
    assert eval_index.backfill(rd) == 2 and eval_index.counts(rd, eval_index.cap_hash(rd.candidate_dir("c")))["a"] == (0.0, 1)
