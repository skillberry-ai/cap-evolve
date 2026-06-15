"""Run directory: the on-disk home of a single optimization run.

Layout under ``.agentcapo/run_<ts>/``::

    state.json          # best candidate id, budget, spent, test_used
    splits.json         # the frozen train/val/test partition (sealed test)
    rejected.jsonl      # RejectedMemory
    history.jsonl       # accepted History
    candidates/<id>/    # snapshot of each candidate's capability dir
    rollouts/<split>/<task>__<cand>__t<k>.json
    events.jsonl        # append-only audit log

This is the only module that owns the run's state, so test-sealing and budget
accounting can't be bypassed by a skill. Pure stdlib.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from .splits import Splits


@dataclass
class Budget:
    max_iterations: int = 20
    max_metric_calls: int = 0   # 0 = unlimited
    max_usd: float = 0.0        # 0 = unlimited
    stall: int = 0              # consecutive no-accepts before stop; 0 = off

    def to_dict(self) -> dict:
        return {
            "max_iterations": self.max_iterations,
            "max_metric_calls": self.max_metric_calls,
            "max_usd": self.max_usd,
            "stall": self.stall,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Budget":
        d = d or {}
        return cls(
            max_iterations=int(d.get("max_iterations") or 20),
            max_metric_calls=int(d.get("max_metric_calls") or 0),
            max_usd=float(d.get("max_usd") or 0.0),
            stall=int(d.get("stall") or 0),
        )


@dataclass
class Spent:
    iterations: int = 0
    metric_calls: int = 0
    usd: float = 0.0                 # RUNNER cost (summed over rollouts)
    stall: int = 0
    runner_tokens: int = 0           # RUNNER tokens
    runner_seconds: float = 0.0      # RUNNER wall time (in evaluation)
    optimizer_seconds: float = 0.0   # OPTIMIZER wall time (proposing edits)

    def to_dict(self) -> dict:
        return {"iterations": self.iterations, "metric_calls": self.metric_calls,
                "usd": self.usd, "stall": self.stall, "runner_tokens": self.runner_tokens,
                "runner_seconds": self.runner_seconds, "optimizer_seconds": self.optimizer_seconds}

    @classmethod
    def from_dict(cls, d: dict) -> "Spent":
        d = d or {}
        return cls(int(d.get("iterations") or 0), int(d.get("metric_calls") or 0),
                   float(d.get("usd") or 0.0), int(d.get("stall") or 0),
                   int(d.get("runner_tokens") or 0), float(d.get("runner_seconds") or 0.0),
                   float(d.get("optimizer_seconds") or 0.0))


class RunDir:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.candidates = self.root / "candidates"
        self.rollouts = self.root / "rollouts"
        self.state_path = self.root / "state.json"
        self.splits_path = self.root / "splits.json"
        self.rejected_path = self.root / "rejected.jsonl"
        self.history_path = self.root / "history.jsonl"
        self.events_path = self.root / "events.jsonl"

    # ---- creation / loading -------------------------------------------------
    @classmethod
    def create(cls, base: Path, *, ts: str | None = None, budget: Budget | None = None) -> "RunDir":
        base = Path(base)
        ts = ts or time.strftime("%Y%m%d_%H%M%S")
        root = base / f"run_{ts}"
        root.mkdir(parents=True, exist_ok=False)
        rd = cls(root)
        rd.candidates.mkdir(parents=True, exist_ok=True)
        rd.rollouts.mkdir(parents=True, exist_ok=True)
        rd._write_state({
            "best_id": None,
            "budget": (budget or Budget()).to_dict(),
            "spent": Spent().to_dict(),
        })
        return rd

    @classmethod
    def open(cls, root: Path) -> "RunDir":
        rd = cls(root)
        if not rd.state_path.exists():
            raise FileNotFoundError(f"no run state at {rd.state_path}")
        return rd

    @classmethod
    def latest(cls, base: Path) -> "RunDir":
        base = Path(base)
        runs = sorted(p for p in base.glob("run_*") if (p / "state.json").exists())
        if not runs:
            raise FileNotFoundError(f"no runs under {base}")
        return cls.open(runs[-1])

    # ---- state --------------------------------------------------------------
    def _read_state(self) -> dict:
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _write_state(self, state: dict) -> None:
        self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    @property
    def budget(self) -> Budget:
        return Budget.from_dict(self._read_state().get("budget"))

    @property
    def spent(self) -> Spent:
        return Spent.from_dict(self._read_state().get("spent"))

    @property
    def best_id(self) -> str | None:
        return self._read_state().get("best_id")

    def set_best(self, candidate_id: str) -> None:
        st = self._read_state()
        st["best_id"] = candidate_id
        self._write_state(st)

    def update_spent(self, *, iterations=0, metric_calls=0, usd=0.0, runner_tokens=0,
                     runner_seconds=0.0, optimizer_seconds=0.0, accepted: bool | None = None) -> Spent:
        st = self._read_state()
        sp = Spent.from_dict(st.get("spent"))
        sp.iterations += iterations
        sp.metric_calls += metric_calls
        sp.usd += usd
        sp.runner_tokens += runner_tokens
        sp.runner_seconds += runner_seconds
        sp.optimizer_seconds += optimizer_seconds
        if accepted is True:
            sp.stall = 0
        elif accepted is False:
            sp.stall += 1
        st["spent"] = sp.to_dict()
        self._write_state(st)
        return sp

    def budget_exhausted(self) -> tuple[bool, str]:
        b, s = self.budget, self.spent
        if b.max_iterations and s.iterations >= b.max_iterations:
            return True, f"max_iterations reached ({s.iterations}/{b.max_iterations})"
        if b.max_metric_calls and s.metric_calls >= b.max_metric_calls:
            return True, f"max_metric_calls reached ({s.metric_calls}/{b.max_metric_calls})"
        if b.max_usd and s.usd >= b.max_usd:
            return True, f"max_usd reached (${s.usd:.2f}/${b.max_usd:.2f})"
        if b.stall and s.stall >= b.stall:
            return True, f"stalled ({s.stall} rejects in a row >= {b.stall})"
        return False, ""

    # ---- splits (with test seal) -------------------------------------------
    def write_splits(self, splits: Splits) -> None:
        self.splits_path.write_text(json.dumps(splits.to_dict(), indent=2), encoding="utf-8")

    def read_splits(self) -> Splits:
        return Splits.from_dict(json.loads(self.splits_path.read_text(encoding="utf-8")))

    def consume_test(self) -> Splits:
        """Return splits with the test seal flipped and persisted. Raises on reuse."""
        splits = self.read_splits()
        splits.mark_test_used()  # raises TestSealError if already used
        self.write_splits(splits)
        return splits

    # ---- candidates ---------------------------------------------------------
    def snapshot(self, candidate_id: str, src_dir: Path) -> Path:
        dst = self.candidates / candidate_id
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src_dir, dst)
        return dst

    def candidate_dir(self, candidate_id: str) -> Path:
        return self.candidates / candidate_id

    # ---- audit log ----------------------------------------------------------
    def log_event(self, kind: str, **fields) -> None:
        rec = {"t": time.time(), "kind": kind, **fields}
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
