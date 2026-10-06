"""An adapter that cannot price its rollouts (e.g. an unmetered proxy/RITS target
model) tags this in ``Rollout.metadata["cost_source"]`` instead of letting
``cost_usd == 0.0`` read as "genuinely free" (see tau2's ``_cost_and_tokens``,
#443). This proves the harness aggregates that tag into the eval's
``cost_source_counts`` and ``SplitResult.cost_source`` — general to any adapter,
not just tau2 — so the dashboard can show "unpriced (tokens: N)" instead of a
bare $0.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))

from cap_evolve import Budget, RunDir, harness  # noqa: E402
from cap_evolve.types import Rollout, Score, Task  # noqa: E402


class _UnpricedAdapter:
    """Two tasks: one rollout has a real cost, one is unpriced but still burned
    real tokens — the mixed case that ``cost_usd or 0.0`` used to collapse."""

    def tasks(self, split):
        return [Task(id="t1"), Task(id="t2")]

    def run_target(self, task, ctx, *, seed=0):
        if task.id == "t1":
            return Rollout(task_id=task.id, cost_usd=0.01, tokens=100,
                           metadata={"cost_source": "tau2"})
        return Rollout(task_id=task.id, cost_usd=0.0, tokens=500,
                       metadata={"cost_source": "unpriced"})

    def score(self, task, rollout):
        return Score(task_id=task.id, reward=1.0)


def test_unpriced_rollouts_are_counted_not_silently_zeroed(tmp_path):
    adapter = _UnpricedAdapter()
    rd = RunDir.create(tmp_path / ".capevolve", ts="t", budget=Budget(max_iterations=1))
    harness.ensure_splits(adapter, rd, seed=0,
                          split_ids={"train": [], "val": ["t1", "t2"], "test": []})
    result = harness.evaluate_candidate(adapter, tmp_path / "seed", run_dir=rd,
                                        split="val", tag="seed")

    # cost is the real, partial figure (never fabricated for the unpriced rollout).
    assert result.cost_usd == 0.01
    assert result.tokens == 600
    # every rollout's attribution is counted, not silently absorbed into "$0 = free".
    assert result.cost_source == {"tau2": 1, "unpriced": 1}

    events = [
        __import__("json").loads(line)
        for line in (rd.root / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ev = next(e for e in events if e.get("kind") == "evaluate")
    assert ev["cost_source_counts"] == {"tau2": 1, "unpriced": 1}


def test_fully_priced_eval_has_no_cost_source_key(tmp_path):
    """An adapter that never tags cost_source (the common case) must not gain a
    fabricated field — absence, not an empty dict masquerading as data."""

    class _PricedAdapter(_UnpricedAdapter):
        def run_target(self, task, ctx, *, seed=0):
            return Rollout(task_id=task.id, cost_usd=0.02, tokens=50)

    adapter = _PricedAdapter()
    rd = RunDir.create(tmp_path / ".capevolve", ts="t", budget=Budget(max_iterations=1))
    harness.ensure_splits(adapter, rd, seed=0,
                          split_ids={"train": [], "val": ["t1", "t2"], "test": []})
    result = harness.evaluate_candidate(adapter, tmp_path / "seed", run_dir=rd,
                                        split="val", tag="seed")
    assert result.cost_source == {}

    events = [
        __import__("json").loads(line)
        for line in (rd.root / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ev = next(e for e in events if e.get("kind") == "evaluate")
    assert "cost_source_counts" not in ev
