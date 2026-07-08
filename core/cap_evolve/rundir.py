"""Run directory: the on-disk home of a single optimization run.

Layout under ``.capevolve/run_<ts>/``::

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

import contextlib
import json
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

from .splits import Splits

_log = logging.getLogger(__name__)


def _atomic_write(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically (tmp file + ``os.replace``).

    A non-atomic ``path.write_text`` can leave a half-written / truncated file if
    the process dies mid-write — and state.json / splits.json carry the seal and
    budget, so a torn write is a correctness hazard. ``os.replace`` is atomic on a
    POSIX filesystem, so a reader sees either the old file or the new one, never a
    partial one. ``fsync`` before the replace so the bytes are durable first.
    """
    path = Path(path)
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)  # atomic: readers see old or new, never partial
    except BaseException:
        # If anything fails before/at the replace, don't leave a dangling temp that
        # could be mistaken for state. The real file is untouched (replace is atomic).
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        raise


@contextlib.contextmanager
def _file_lock(lock_path: Path):
    """Advisory cross-process lock around a read-modify-write of run state.

    State mutations (``set_best``, ``update_spent``, the seal commit) are
    read-modify-write; two concurrent writers could lose an update. We take a
    best-effort advisory lock via ``O_CREAT|O_EXCL`` on a lock file with a short
    spin. Stdlib only (``fcntl`` would be POSIX-only and does not guard the RMW
    window across the read). The lock is advisory: it serializes *our* writers,
    which is all the engine needs.
    """
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = None
    deadline = time.time() + 10.0
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.time() > deadline:
                # Stale lock (a crashed holder): steal it rather than hang forever.
                with contextlib.suppress(FileNotFoundError):
                    os.unlink(lock_path)
                deadline = time.time() + 10.0
            time.sleep(0.02)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        with contextlib.suppress(FileNotFoundError):
            os.unlink(lock_path)


@dataclass
class Budget:
    max_iterations: int = 20
    max_metric_calls: int = 0     # 0 = unlimited
    max_usd: float = 0.0          # 0 = unlimited (total: runner + optimizer + intake)
    stall: int = 0                # consecutive no-accepts before stop; 0 = off
    max_optimizer_usd: float = 0.0  # 0 = off; separate cap on optimizer spend alone

    def to_dict(self) -> dict:
        return {
            "max_iterations": self.max_iterations,
            "max_metric_calls": self.max_metric_calls,
            "max_usd": self.max_usd,
            "stall": self.stall,
            "max_optimizer_usd": self.max_optimizer_usd,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Budget":
        d = d or {}
        return cls(
            max_iterations=int(d.get("max_iterations") or 20),
            max_metric_calls=int(d.get("max_metric_calls") or 0),
            max_usd=float(d.get("max_usd") or 0.0),
            stall=int(d.get("stall") or 0),
            max_optimizer_usd=float(d.get("max_optimizer_usd") or 0.0),
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
    optimizer_usd: float = 0.0       # OPTIMIZER cost (reported by the agent CLI)
    optimizer_tokens: int = 0        # OPTIMIZER tokens
    intake_usd: float = 0.0          # INTAKE cost (best-effort; interview phase)
    intake_tokens: int = 0           # INTAKE tokens (best-effort)
    intake_seconds: float = 0.0      # INTAKE wall time (best-effort)

    @property
    def total_usd(self) -> float:
        """All-role spend: what ``max_usd`` is checked against."""
        return self.usd + self.optimizer_usd + self.intake_usd

    def to_dict(self) -> dict:
        return {"iterations": self.iterations, "metric_calls": self.metric_calls,
                "usd": self.usd, "stall": self.stall, "runner_tokens": self.runner_tokens,
                "runner_seconds": self.runner_seconds, "optimizer_seconds": self.optimizer_seconds,
                "optimizer_usd": self.optimizer_usd, "optimizer_tokens": self.optimizer_tokens,
                "intake_usd": self.intake_usd, "intake_tokens": self.intake_tokens,
                "intake_seconds": self.intake_seconds}

    @classmethod
    def from_dict(cls, d: dict) -> "Spent":
        d = d or {}
        return cls(int(d.get("iterations") or 0), int(d.get("metric_calls") or 0),
                   float(d.get("usd") or 0.0), int(d.get("stall") or 0),
                   int(d.get("runner_tokens") or 0), float(d.get("runner_seconds") or 0.0),
                   float(d.get("optimizer_seconds") or 0.0),
                   float(d.get("optimizer_usd") or 0.0), int(d.get("optimizer_tokens") or 0),
                   float(d.get("intake_usd") or 0.0), int(d.get("intake_tokens") or 0),
                   float(d.get("intake_seconds") or 0.0))


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
        self._state_lock = self.root / ".state.lock"
        self._observers: list = []  # list[RunObserver]

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
        # Atomic: a torn state.json would corrupt the seal/budget. events.jsonl is
        # the append-only source of truth; state.json is a derived cache we never
        # leave half-written.
        _atomic_write(self.state_path, json.dumps(state, indent=2))

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
        with _file_lock(self._state_lock):
            st = self._read_state()
            st["best_id"] = candidate_id
            self._write_state(st)

    def update_spent(self, *, iterations=0, metric_calls=0, usd=0.0, runner_tokens=0,
                     runner_seconds=0.0, optimizer_seconds=0.0, optimizer_usd=0.0,
                     optimizer_tokens=0, intake_usd=0.0, intake_tokens=0, intake_seconds=0.0,
                     accepted: bool | None = None) -> Spent:
        with _file_lock(self._state_lock):
            st = self._read_state()
            sp = Spent.from_dict(st.get("spent"))
            sp.iterations += iterations
            sp.metric_calls += metric_calls
            sp.usd += usd
            sp.runner_tokens += runner_tokens
            sp.runner_seconds += runner_seconds
            sp.optimizer_seconds += optimizer_seconds
            sp.optimizer_usd += optimizer_usd
            sp.optimizer_tokens += optimizer_tokens
            sp.intake_usd += intake_usd
            sp.intake_tokens += intake_tokens
            sp.intake_seconds += intake_seconds
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
        if b.max_usd and s.total_usd >= b.max_usd:
            return True, (f"max_usd reached (${s.total_usd:.2f}/${b.max_usd:.2f}; "
                          f"run ${s.usd:.2f} + opt ${s.optimizer_usd:.2f} + intake ${s.intake_usd:.2f})")
        if b.max_optimizer_usd and s.optimizer_usd >= b.max_optimizer_usd:
            return True, f"max_optimizer_usd reached (${s.optimizer_usd:.2f}/${b.max_optimizer_usd:.2f})"
        if b.stall and s.stall >= b.stall:
            return True, f"stalled ({s.stall} rejects in a row >= {b.stall})"
        return False, ""

    def record_spend_warnings(self) -> list[dict]:
        """Emit a ``budget_warning`` event once per crossed soft threshold.

        Fires at 50%/80% of ``max_usd`` (on total spend) and 80% of
        ``max_metric_calls``. Crossings already announced are remembered in
        ``state.json`` so each fires at most once. Returns the warnings emitted
        this call (for callers/tests).
        """
        b, s = self.budget, self.spent
        checks: list[tuple[str, float, float, float]] = []  # (metric, frac, spent, limit)
        if b.max_usd:
            frac = s.total_usd / b.max_usd if b.max_usd else 0.0
            for thr in (0.5, 0.8):
                if frac >= thr:
                    checks.append(("max_usd", thr, s.total_usd, b.max_usd))
        if b.max_metric_calls:
            frac = s.metric_calls / b.max_metric_calls if b.max_metric_calls else 0.0
            if frac >= 0.8:
                checks.append(("max_metric_calls", 0.8, float(s.metric_calls), float(b.max_metric_calls)))
        emitted: list[dict] = []
        with _file_lock(self._state_lock):
            st = self._read_state()
            fired = set(st.get("warnings_fired") or [])
            for metric, thr, spent_v, limit_v in checks:
                key = f"{metric}@{int(thr * 100)}"
                if key in fired:
                    continue
                fired.add(key)
                rec = {"metric": metric, "pct": int(thr * 100), "spent": round(spent_v, 4), "limit": limit_v}
                emitted.append(rec)
            st["warnings_fired"] = sorted(fired)
            self._write_state(st)
        for rec in emitted:
            self.log_event("budget_warning", **rec)
        return emitted

    # ---- splits (with test seal) -------------------------------------------
    def write_splits(self, splits: Splits) -> None:
        _atomic_write(self.splits_path, json.dumps(splits.to_dict(), indent=2))

    def read_splits(self) -> Splits:
        return Splits.from_dict(json.loads(self.splits_path.read_text(encoding="utf-8")))

    def reserve_test(self) -> Splits:
        """Check the seal is unused (raise if not) WITHOUT flipping it.

        ``reserve_test`` + ``commit_test`` replace the old ``consume_test`` so the
        seal is burned *on success only*: a finalize that crashes mid-scoring (an
        adapter exception, a runner timeout) leaves the seal unused, and a retry
        can still score test exactly once. Call this at the start of finalize, then
        ``commit_test`` only after the test SplitResult has been computed + written.
        """
        splits = self.read_splits()
        splits.check_test_unused()  # raises TestSealError if already used
        return splits

    def commit_test(self) -> Splits:
        """Burn the seal (flip + persist). Call ONLY after test is scored+written."""
        with _file_lock(self._state_lock):
            splits = self.read_splits()
            splits.mark_test_used()  # raises TestSealError if already used (double commit)
            self.write_splits(splits)
            return splits

    # Back-compat shim: ``consume_test`` flipped+persisted the seal BEFORE scoring,
    # which permanently burned the headline number on a transient finalize crash.
    # Kept so existing callers/tests don't break, but it is now reserve→commit with
    # nothing in between (i.e. it still seals immediately when used standalone).
    def consume_test(self) -> Splits:
        self.reserve_test()
        return self.commit_test()

    # ---- candidates ---------------------------------------------------------
    def snapshot(self, candidate_id: str, src_dir: Path, ignore=None) -> Path:
        """Persist ``src_dir`` as candidate ``candidate_id``.

        ``ignore`` is an optional iterable of top-level names to exclude (e.g. the
        optimizer's injected scratch — ``trajectories/``, ``guidance/`` — and its
        prompt/memory files) so the stored candidate stays capability-only and
        diffs against the parent show only real edits.
        """
        dst = self.candidates / candidate_id
        if dst.exists():
            shutil.rmtree(dst)
        ig = shutil.ignore_patterns(*ignore) if ignore else None
        shutil.copytree(src_dir, dst, ignore=ig)
        return dst

    def candidate_dir(self, candidate_id: str) -> Path:
        return self.candidates / candidate_id

    # ---- audit log ----------------------------------------------------------
    def log_event(self, kind: str, **fields) -> None:
        rec = {"t": time.time(), "kind": kind, **fields}
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        self._notify_observers(rec)

    # ---- observers ----------------------------------------------------------
    def add_observer(self, observer) -> None:
        """Attach a :class:`~cap_evolve.observers.RunObserver` to this run.

        All subsequent ``log_event`` calls will also be forwarded to
        *observer*.  Multiple observers can be attached; each is called in
        order.  Failures in observers are logged but never propagate.
        """
        self._observers.append(observer)

    def notify_run_start(self, metadata: dict | None = None) -> None:
        """Signal observers that the optimisation run has started."""
        run_id = self.root.name
        for obs in self._observers:
            try:
                obs.on_run_start(run_id, metadata or {})
            except Exception:
                _log.warning("observer %s.on_run_start failed", type(obs).__name__, exc_info=True)

    def notify_run_end(self, summary: dict | None = None) -> None:
        """Signal observers that the run has finished, then flush + close."""
        for obs in self._observers:
            try:
                obs.on_run_end(summary or {})
            except Exception:
                _log.warning("observer %s.on_run_end failed", type(obs).__name__, exc_info=True)
        self.flush_observers()

    def flush_observers(self) -> None:
        """Flush all attached observers."""
        for obs in self._observers:
            try:
                obs.flush()
            except Exception:
                _log.warning("observer %s.flush failed", type(obs).__name__, exc_info=True)

    def close_observers(self) -> None:
        """Close all attached observers and release their resources."""
        for obs in self._observers:
            try:
                obs.close()
            except Exception:
                _log.warning("observer %s.close failed", type(obs).__name__, exc_info=True)

    def _notify_observers(self, event: dict) -> None:
        """Forward an event dict to every attached observer (fire-and-forget)."""
        for obs in self._observers:
            try:
                obs.on_event(event)
            except Exception:
                _log.warning("observer %s.on_event failed", type(obs).__name__, exc_info=True)
