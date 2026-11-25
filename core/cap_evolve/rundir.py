"""Run directory: the on-disk home of a single optimization run.

Layout under ``.capevolve/run_<ts>/``::

    state.json          # best candidate id, budget, spent, test_used
    splits.json         # the frozen train/val/test partition (sealed test)
    rejected.jsonl      # RejectedMemory
    history.jsonl       # accepted History
    candidates/<id>/    # snapshot of each candidate's capability dir
    rollouts/<split>/<task>__<cand>__t<k>.json
    events.jsonl        # append-only audit log

A sealed run (pooled mode's confirm stratum, or a split passed to ``seal_split``) keeps those rollouts in
``sealed_dir`` instead, outside the run tree; ``rollout_dir`` resolves the location. After ``seal_split`` the
split's id list (``splits.json``, merged back by ``read_splits``) and the per-task results filed under it in
``baseline.json`` / ``final.json`` (merged back by ``read_record`` / ``read_baseline``) are sealed too.

This is the only module that owns the run's state, so test-sealing and budget
accounting can't be bypassed by a skill. Pure stdlib.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .splits import Splits, TestSealError


def _atomic_write(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically (tmp file + ``os.replace``).

    A non-atomic ``path.write_text`` can leave a half-written / truncated file if
    the process dies mid-write — and state.json / splits.json carry the seal and
    budget, so a torn write is a correctness hazard. ``os.replace`` is atomic on a
    POSIX filesystem, so a reader sees either the old file or the new one, never a
    partial one. ``fsync`` before the replace so the bytes are durable first.
    """
    path = Path(path)
    # Unique per call (not only per process): two threads writing the same file at once
    # must not share a temp file, or one's replace moves it away under the other.
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}")
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


_HELD_LOCKS: list = []


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


#: Run records whose per-task results of a sealed split are kept in the sealed dir (``RunDir.write_record``).
SEALED_RECORDS = ("baseline.json", "final.json")


def merge_sealed_record(public: dict, private: dict) -> dict:
    """``public`` (a run-tree record with ``sealed_per_task`` already removed) with the sealed per-task results of ``private``
    merged back in place. Pure: callers that read the two files themselves (the dashboard, through its own path checks) use it."""
    for k, v in private.items():
        if isinstance(v, dict) and isinstance(public.get(k), dict):
            merge_sealed_record(public[k], v)
        else:
            public[k] = v
    return public


def _known_record(name: str) -> str:
    """The record file name for ``name``: one of ``SEALED_RECORDS``, returned as the CONSTANT from that list (never the caller's
    string), so ``write_record`` / ``read_record`` can only touch a known file. A path, ``..`` or an unknown name raises."""
    for known in SEALED_RECORDS:
        if name == known:
            return known
    raise ValueError(f"unknown run record {name!r}; known: {list(SEALED_RECORDS)}")


class BudgetExhausted(RuntimeError):
    """A rollout reservation does not fit what is left of ``max_metric_calls`` / ``max_usd``.

    Raised BEFORE any rollout is dispatched, so the caller decides what a refusal means: a rung is
    ``unfunded`` and the round ends, a confirmation is ``unconfirmed`` (pending, never a reject)."""


def _pid_alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except (PermissionError, ValueError, TypeError):
        return True
    return True


@dataclass
class Budget:
    max_iterations: int = 20
    max_metric_calls: int = 0     # 0 = unlimited
    max_usd: float = 0.0          # 0 = unlimited (total: runner + optimizer + intake)
    stall: int = 0                # consecutive no-accepts before stop; 0 = off
    max_optimizer_usd: float = 0.0  # 0 = off; separate cap on optimizer spend alone
    stop_at_reward: float = 0.0   # 0 = off; stop as soon as best val reward reaches this

    def to_dict(self) -> dict:
        return {
            "max_iterations": self.max_iterations,
            "max_metric_calls": self.max_metric_calls,
            "max_usd": self.max_usd,
            "stall": self.stall,
            "max_optimizer_usd": self.max_optimizer_usd,
            "stop_at_reward": self.stop_at_reward,
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
            stop_at_reward=float(d.get("stop_at_reward") or 0.0),
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
    best_val: float = 0.0            # best val reward seen so far (seed or accepted candidate)
    usersim_usd: float = 0.0         # user-simulator list-price estimate; already INSIDE ``usd``

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
                "intake_seconds": self.intake_seconds, "best_val": self.best_val,
                "usersim_usd": self.usersim_usd}

    @classmethod
    def from_dict(cls, d: dict) -> "Spent":
        d = d or {}
        return cls(int(d.get("iterations") or 0), int(d.get("metric_calls") or 0),
                   float(d.get("usd") or 0.0), int(d.get("stall") or 0),
                   int(d.get("runner_tokens") or 0), float(d.get("runner_seconds") or 0.0),
                   float(d.get("optimizer_seconds") or 0.0),
                   float(d.get("optimizer_usd") or 0.0), int(d.get("optimizer_tokens") or 0),
                   float(d.get("intake_usd") or 0.0), int(d.get("intake_tokens") or 0),
                   float(d.get("intake_seconds") or 0.0), float(d.get("best_val") or 0.0),
                   float(d.get("usersim_usd") or 0.0))


def _allow_test_rescore() -> bool:
    """Operator-only override for the re-score guard in ``begin_test_attempt``.

    Deliberately an env var and not a quiet default: the guard exists to stop a retry loop from
    turning the held-out split into a selection surface. Its name is kept OUT of every refusal
    message and every agent-visible skill doc (#799: an optimizer read it there and switched the
    guard off). Every use is recorded: a ``test_rescore_override`` event in events.jsonl, and a
    ``test_rescore_override`` field in final.json (see ``commit_test``).
    """
    return str(os.environ.get("CAPEVOLVE_ALLOW_TEST_RESCORE", "")).strip().lower() in {
        "1", "true", "yes", "on"}


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
        self._observers: list = []
        self._observer_state_path = self.root / "observer_state.json"

    # ---- creation / loading -------------------------------------------------
    @classmethod
    def create(cls, base: Path, *, ts: str | None = None, budget: Budget | None = None,
               exist_ok: bool = False) -> "RunDir":
        """Create (or, with ``exist_ok``, resume) the run dir under ``base``.

        ``exist_ok=True`` is the ``--resume`` path: if ``run_<ts>`` already has a
        ``state.json``, reopen it UNCHANGED — preserving ``best_id``/``budget``/``spent``
        so the loop keeps counting from prior progress instead of resetting. If the dir
        exists but has no ``state.json`` (a torn/partial create), initialize a fresh
        state into it. ``exist_ok=False`` (default) keeps the old strict behavior: a
        colliding ``run_<ts>`` raises ``FileExistsError``.
        """
        base = Path(base)
        ts = ts or time.strftime("%Y%m%d_%H%M%S")
        root = base / f"run_{ts}"
        if exist_ok and (root / "state.json").exists():
            return cls.open(root)  # resume: preserve existing state, never reset
        root.mkdir(parents=True, exist_ok=exist_ok)
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

    def set_best(self, candidate_id: str, val: float | None = None) -> None:
        """Move the champion. Semantics: ``spent.best_val`` is the val of ``best_id``. Pass the
        MEASURED val and it replaces ``spent.best_val`` under the same lock hold (not a
        high-water mark); omit it (unverified/unknown) and ``best_val`` is left untouched."""
        with _file_lock(self._state_lock):
            st = self._read_state()
            st["best_id"] = candidate_id
            if val is not None:
                sp = Spent.from_dict(st.get("spent"))
                sp.best_val = float(val)
                st["spent"] = sp.to_dict()
            self._write_state(st)

    def run_lock(self, name: str) -> None:
        """Fail fast if another live process holds ``locks/<name>.lock`` (#713 B7).

        flock, held until this process exits (released by the OS even on a crash, so there
        is no stale-lock case). Raises ``RuntimeError`` naming the holder's pid.
        """
        try:
            import fcntl
        except ImportError:  # non-POSIX: no lock (see _file_lock's note); say so, don't crash
            import warnings
            warnings.warn("run_lock is a no-op on this platform (no fcntl)")
            return
        if "/" in name or ".." in name:
            raise ValueError(f"bad lock name {name!r}")
        d = self.root / "locks"
        d.mkdir(parents=True, exist_ok=True)
        f = open(d / f"{name}.lock", "a+")
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            f.seek(0)
            holder = f.read().strip()
            f.close()
            raise RuntimeError(f"{name} is already running (holder: {holder or 'unknown'})")
        f.seek(0)
        f.truncate()
        f.write(f"pid={os.getpid()} start={int(time.time())}")
        f.flush()
        _HELD_LOCKS.append(f)  # keep the fd open for the life of the process

    # ---- reservations -------------------------------------------------------
    @staticmethod
    def _live_reservations(st: dict) -> dict:
        """Reservations whose holder process is still alive (a crashed holder frees its claim)."""
        return {k: v for k, v in (st.get("reserved") or {}).items() if _pid_alive(v.get("pid"))}

    def reserved_metric_calls(self) -> int:
        return sum(int(v.get("n") or 0) for v in self._live_reservations(self._read_state()).values())

    def remaining_metric_calls(self) -> int | None:
        """What is still free after spend and live reservations; ``None`` when uncapped."""
        st = self._read_state()
        cap = Budget.from_dict(st.get("budget")).max_metric_calls
        if not cap:
            return None
        used = Spent.from_dict(st.get("spent")).metric_calls
        held = sum(int(v.get("n") or 0) for v in self._live_reservations(st).values())
        return max(0, cap - used - held)

    def can_afford(self, n: int) -> bool:
        rem = self.remaining_metric_calls()
        return rem is None or n <= rem

    def reserve_metric_calls(self, n: int, *, label: str = "", est_usd: float = 0.0) -> str:
        """Claim ``n`` rollouts against ``max_metric_calls`` (and ``est_usd`` against ``max_usd``).

        Atomic under the state lock. Raises ``BudgetExhausted`` if ``spent + reserved + n`` would pass
        a cap. Returns a token for ``update_spent(release=token)`` (converts the claim into spend) or
        ``release_metric_calls`` (refunds it after a failed evaluation)."""
        n = int(n)
        with _file_lock(self._state_lock):
            st = self._read_state()
            b = Budget.from_dict(st.get("budget"))
            sp = Spent.from_dict(st.get("spent"))
            live = self._live_reservations(st)
            held_n = sum(int(v.get("n") or 0) for v in live.values())
            held_usd = sum(float(v.get("usd") or 0.0) for v in live.values())
            if b.max_metric_calls and sp.metric_calls + held_n + n > b.max_metric_calls:
                raise BudgetExhausted(
                    f"{label or 'evaluation'} needs {n} rollouts but only "
                    f"{max(0, b.max_metric_calls - sp.metric_calls - held_n)} of max_metric_calls="
                    f"{b.max_metric_calls} remain ({sp.metric_calls} spent, {held_n} reserved)")
            if b.max_usd and sp.total_usd + held_usd + est_usd > b.max_usd:
                raise BudgetExhausted(
                    f"{label or 'evaluation'} is estimated at ${est_usd:.2f}; "
                    f"${max(0.0, b.max_usd - sp.total_usd - held_usd):.2f} of max_usd remain")
            token = f"r{int(time.time() * 1000)}_{os.getpid()}_{len(live)}_{n}"
            while token in live:
                token += "x"
            live[token] = {"n": n, "usd": float(est_usd), "pid": os.getpid(), "label": label,
                           "ts": time.time()}
            st["reserved"] = live
            self._write_state(st)
            return token

    def mark_unfunded(self, why: str) -> None:
        """Record that a reservation was refused, so every loop's ``budget_exhausted`` check stops
        (reason ``budget_reserved``) instead of paying an optimizer call for a proposal it cannot test.
        Cleared by ``update_budget`` (extending the budget)."""
        with _file_lock(self._state_lock):
            st = self._read_state()
            st["unfunded"] = str(why)[:300]
            self._write_state(st)

    def _sealed_quarantine(self) -> Path | None:
        """Where the quarantine lives once a split is sealed (``seal_split``): its ids are that split's, so
        they stay out of state.json. ``None``: in state.json, as always."""
        sd = self.sealed_dir
        return sd / "quarantine.json" if sd is not None and self.sealed_splits else None

    def quarantined_tasks(self) -> list:
        """Task ids removed from the evaluable set for this run (still missing after the retries)."""
        sq = self._sealed_quarantine()
        if sq is not None and sq.exists():
            return sorted(json.loads(sq.read_text(encoding="utf-8")) or {})
        return sorted((self._read_state().get("quarantined") or {}))

    def quarantine(self, task_ids, reason: str = "") -> list:
        """Add ``task_ids`` to the quarantine (locked RMW); returns the ones newly added."""
        sq = self._sealed_quarantine()
        with _file_lock(self._state_lock):
            st = self._read_state()
            q = dict(st.get("quarantined") or {})
            if sq is not None and sq.exists():
                q.update(json.loads(sq.read_text(encoding="utf-8")) or {})
            new = [str(t) for t in task_ids if str(t) not in q]
            for t in new:
                q[t] = {"reason": reason, "ts": time.time()}
            if new and sq is not None:
                _atomic_write(sq, json.dumps(q, indent=2))
                if st.pop("quarantined", None) is not None:
                    self._write_state(st)
            elif new:
                st["quarantined"] = q
                self._write_state(st)
            return new

    def release_metric_calls(self, token: str | None) -> None:
        """Refund a reservation (idempotent)."""
        if not token:
            return
        with _file_lock(self._state_lock):
            st = self._read_state()
            res = st.get("reserved") or {}
            if token in res:
                res.pop(token)
                st["reserved"] = res
                self._write_state(st)

    def update_spent(self, *, iterations=0, metric_calls=0, usd=0.0, runner_tokens=0,
                     runner_seconds=0.0, optimizer_seconds=0.0, optimizer_usd=0.0,
                     optimizer_tokens=0, intake_usd=0.0, intake_tokens=0, intake_seconds=0.0,
                     accepted: bool | None = None, best_val: float | None = None,
                     usersim_usd=0.0, release=None) -> Spent:
        """Add to the spend counters (locked RMW). ``release`` = a ``reserve_metric_calls`` token whose
        claim is converted into this spend in the SAME lock hold (no window where it counts twice)."""
        with _file_lock(self._state_lock):
            st = self._read_state()
            if release and release in (st.get("reserved") or {}):
                st["reserved"].pop(release)
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
            sp.usersim_usd += usersim_usd
            if accepted is True:
                sp.stall = 0
            elif accepted is False:
                sp.stall += 1
            if best_val is not None:
                sp.best_val = max(sp.best_val, best_val)
            st["spent"] = sp.to_dict()
            self._write_state(st)
            return sp

    def update_budget(self, **overrides) -> Budget:
        """Overwrite selected budget fields (locked RMW). Used to EXTEND a resumed run.

        Only keys explicitly passed are changed (e.g. ``max_iterations=30`` to keep
        climbing past the original cap); everything else — and all ``spent`` — is
        preserved. Unknown keys are ignored so a stray CLI flag can't corrupt state.
        """
        allowed = {"max_iterations", "max_metric_calls", "max_usd", "stall", "max_optimizer_usd",
                   "stop_at_reward"}
        with _file_lock(self._state_lock):
            st = self._read_state()
            b = Budget.from_dict(st.get("budget")).to_dict()
            for k, v in overrides.items():
                if k in allowed and v is not None:
                    b[k] = v
            st["budget"] = b
            st.pop("unfunded", None)
            self._write_state(st)
            return Budget.from_dict(b)

    def freeze_state(self, **fields) -> tuple[dict, bool]:
        """Write ``fields`` into state.json ONCE (locked RMW); an existing value always wins.

        For facts computed from frozen inputs (the split, the baseline's trial count) that a
        later caller must read back rather than recompute under different arguments. Returns
        (the stored values of ``fields``' keys, whether this call wrote them).
        """
        with _file_lock(self._state_lock):
            st = self._read_state()
            wrote = not all(k in st for k in fields)
            if wrote:
                for k, v in fields.items():
                    st.setdefault(k, v)
                self._write_state(st)
            return {k: st[k] for k in fields}, wrote

    def budget_exhausted(self) -> tuple[bool, str]:
        b, s = self.budget, self.spent
        if hasattr(self, "_state_lock"):        # (duck-typed doubles in tests have no reservations)
            s = Spent.from_dict({**s.to_dict(), "metric_calls": s.metric_calls + self.reserved_metric_calls()})
            unfunded = self._read_state().get("unfunded")
            if unfunded:
                return True, f"budget_reserved: {unfunded}"
        if b.stop_at_reward and s.best_val >= b.stop_at_reward - 1e-9:
            return True, f"reward ceiling reached (best val {s.best_val:.4f} >= {b.stop_at_reward:.4f})"
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
    # ---- run records whose per-task results of a sealed split stay sealed ------------------------
    def write_record(self, name: str, payload: dict) -> None:
        """Write the run record ``name`` (``SEALED_RECORDS``: ``baseline.json``, ``final.json``).

        Under ``seal_split`` the ``per_task`` list of every SplitResult filed under a sealed split's key
        (``{"val": {..., "per_task": [...]}}``, at any depth) goes to ``<sealed_dir>/<name>``; the run-tree
        file keeps the aggregates (reward, stderr, pass@k, n_scored, n_tasks) and ``sealed_per_task: true``.
        ``read_record`` merges the two back. Without a sealed split the file is written whole, as always."""
        name = _known_record(name)
        keys, sd = set(self.sealed_splits), self.sealed_dir
        if not keys or sd is None:
            _atomic_write(self.root / name, json.dumps(payload, indent=2))
            return
        private: dict = {}

        def strip(node, priv):
            out = {}
            for k, v in node.items():
                if k in keys and isinstance(v, dict) and "per_task" in v:
                    out[k] = {kk: vv for kk, vv in v.items() if kk != "per_task"}
                    priv[k] = {"per_task": v["per_task"]}
                elif isinstance(v, dict):
                    sub: dict = {}
                    out[k] = strip(v, sub)
                    if sub:
                        priv[k] = sub
                else:
                    out[k] = v
            return out

        public = strip(dict(payload), private)
        public["sealed_per_task"] = True
        _atomic_write(sd / name, json.dumps(private, indent=2))
        _atomic_write(self.root / name, json.dumps(public, indent=2))

    def read_record(self, name: str) -> dict:
        """The run record ``name`` with its sealed per-task results merged back (see ``write_record``).
        A record written before the split was sealed (the old layout) is returned as it is on disk."""
        name = _known_record(name)
        d = json.loads((self.root / name).read_text(encoding="utf-8"))
        sd = self.sealed_dir
        if not d.pop("sealed_per_task", False) or sd is None or not (sd / name).exists():
            return d

        return merge_sealed_record(d, json.loads((sd / name).read_text(encoding="utf-8")))

    def read_baseline(self) -> dict:
        """``baseline.json`` with the seed's sealed per-task val results merged back (``read_record``)."""
        return self.read_record("baseline.json")

    def write_splits(self, splits: Splits) -> None:
        sealed = self.sealed_dir
        hidden = [k for k in self.sealed_splits if k in ("train", "val")] if sealed is not None else []
        if hidden and not splits.pooled:
            # A sealed legacy split (``seal_split``): its id list lives in the sealed dir with the full
            # partition; the run dir keeps everything else (the train ids the proposer reads, test, the seed).
            full = splits.to_dict()
            _atomic_write(sealed / "splits_full.json", json.dumps(full, indent=2))
            public = {**full, **{k: [] for k in hidden}, "sealed": True}
            _atomic_write(self.splits_path, json.dumps(public, indent=2))
            return
        if splits.pooled and sealed is not None:
            # The full partition (train/val/confirm ids) lives in the sealed dir; the run dir keeps
            # only what a proposer may know: F, test, the seed. C = pool minus F is NOT recoverable
            # from it because train/val are not listed either.
            full = splits.to_dict()
            _atomic_write(sealed / "splits_full.json", json.dumps(full, indent=2))
            public = {k: full[k] for k in ("test", "seed", "test_used", "pooled", "feedback", "pool_seed")}
            public.update(train=[], val=[], confirm=[], sealed=True)
            _atomic_write(self.splits_path, json.dumps(public, indent=2))
            return
        _atomic_write(self.splits_path, json.dumps(splits.to_dict(), indent=2))

    def read_splits(self) -> Splits:
        d = json.loads(self.splits_path.read_text(encoding="utf-8"))
        if d.get("sealed") and self.sealed_dir is not None:
            full = json.loads((self.sealed_dir / "splits_full.json").read_text(encoding="utf-8"))
            full["test_used"] = bool(d.get("test_used") or full.get("test_used"))
            return Splits.from_dict(full)
        return Splits.from_dict(d)

    # ---- sealed directory (pooled mode) ---------------------------------------------------------
    @property
    def sealed_dir(self) -> Path | None:
        """Where everything derived from the hidden confirm stratum C lives (None: not sealed).

        Deliberately OUTSIDE the run dir and the project: both optimizers can read the whole run tree
        (the agent-optimize host's cwd is the common parent of the run dir and the project; a
        hill-climb proposer runs in ``<run>/work/<cid>``)."""
        try:
            v = self._read_state().get("sealed_dir")
        except (OSError, ValueError):
            return None
        return Path(v) if v else None

    def seal(self, path=None) -> Path:
        """Create (once) and record the sealed directory. Default: ``<project>.sealed/<run name>``, a
        sibling of the project directory (the run dir is ``<project>/.capevolve/<run>``); override with
        ``path`` or ``CAPEVOLVE_SEALED_DIR`` (a parent: the run name is appended)."""
        have = self.sealed_dir
        if have is not None:
            return have
        env = os.environ.get("CAPEVOLVE_SEALED_DIR")
        if path:
            target = Path(path).resolve()
        elif env:
            target = Path(env).resolve() / self.root.name
        else:
            proj = self.root.resolve().parent.parent       # absolute: a relative run root has no usable parents
            target = proj.with_name(proj.name + ".sealed") / self.root.name
        target.mkdir(parents=True, exist_ok=True)
        with _file_lock(self._state_lock):
            st = self._read_state()
            st["sealed_dir"] = str(target)
            self._write_state(st)
        return target

    @property
    def sealed_splits(self) -> tuple:
        """Legacy splits whose rollouts live in the sealed dir (``seal_split``); ``()`` for most runs."""
        try:
            return tuple(self._read_state().get("sealed_splits") or ())
        except (OSError, ValueError):
            return ()

    def seal_split(self, split: str) -> int:
        """Move ``split``'s rollouts out of the run tree into the sealed dir, and keep every later one there.

        For a split the proposer must not read but the framework still scores (hill-climb's val under
        ``hc_feedback_split: train``). Idempotent, and safe to call again after a crash between the state
        write and the move: whatever is still under ``rollouts/<split>`` is moved (an existing sealed copy
        wins). Returns the number of files moved."""
        if split in ("test", "confirm"):
            raise ValueError(f"split {split!r} is sealed by its own mechanism")
        sd = self.seal()
        if split not in self.sealed_splits:
            with _file_lock(self._state_lock):
                st = self._read_state()
                st["sealed_splits"] = sorted(set(st.get("sealed_splits") or ()) | {split})
                q = st.pop("quarantined", None)          # its ids go with the split (see quarantine)
                if q:
                    _atomic_write(sd / "quarantine.json", json.dumps(q, indent=2))
                self._write_state(st)
        # The id list and every per-task result of the split leave the run tree too. A file still in the old
        # layout (written before the split was sealed, e.g. by a run started on an earlier version) is
        # migrated once; one already in the sealed layout is left alone.
        if self.splits_path.exists() and not json.loads(self.splits_path.read_text(encoding="utf-8")).get("sealed"):
            self.write_splits(self.read_splits())
        for name in SEALED_RECORDS:
            path = self.root / name
            if path.exists() and not json.loads(path.read_text(encoding="utf-8")).get("sealed_per_task"):
                self.write_record(name, self.read_record(name))
        src, dst = self.rollouts / split, sd / "rollouts" / split
        if not src.is_dir():
            return 0
        dst.mkdir(parents=True, exist_ok=True)
        n = 0
        for f in sorted(src.iterdir()):
            target = dst / f.name
            if target.exists():
                f.unlink() if f.is_file() else shutil.rmtree(f)
            else:
                shutil.move(str(f), str(target))
                n += 1
        with contextlib.suppress(OSError):
            src.rmdir()
        return n

    def rollout_dir(self, split: str) -> Path:
        """``rollouts/<split>``; the confirm stratum's rollouts, and those of any ``seal_split`` split, live
        in the sealed dir."""
        if split == "confirm" or (split != "test" and split in self.sealed_splits):
            sd = self.sealed_dir
            if sd is not None:
                return sd / "rollouts" / split
        return self.rollouts / split

    @property
    def private_dir(self) -> Path:
        """C-derived round state and aggregates: sealed when sealed, else ``<run>/private``."""
        sd = self.sealed_dir
        return (sd / "private") if sd is not None else self.root / "private"

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

    def begin_test_attempt(self) -> None:
        """Refuse a SECOND finalize attempt once test rollouts already exist.

        Seal-on-success (``reserve_test`` + ``commit_test``) deliberately lets a finalize that
        crashes mid-scoring be retried, so a transient failure does not destroy the run's headline
        number. It cannot, however, tell "crashed BEFORE scoring test" from "crashed AFTER scoring
        test but before commit" -- and in the second case the held-out set has already been
        observed. Observed in a real run: a finalize killed by a foreground timeout had already
        scored test, the retry scored it again, and the reported number was the second look.

        Called ONCE per finalize attempt, not per evaluation: one honest finalize scores test twice
        by design (the best as ``FINAL`` and the baseline as ``FINAL_seed``), so putting this check
        in ``reserve_test`` would reject the normal flow.
        """
        splits = self.read_splits()
        splits.check_test_unused()
        spent = sorted((self.rollouts / "test").glob("*.json")) if self.rollouts.exists() else []
        if not spent:
            return
        if not _allow_test_rescore():
            # Do NOT name the override here: the optimizer agent reads this text (#799).
            raise TestSealError(
                f"TEST split is sealed: it was already SCORED by an earlier finalize attempt in "
                f"this run ({len(spent)} test rollout(s) under {self.rollouts / 'test'}) even "
                "though the seal was never committed - a finalize that dies after scoring but "
                "before writing leaves exactly this state. The held-out set has been observed, so "
                "re-scoring it would make the headline number a SECOND look at test.\n"
                "  * To report what the earlier attempt computed, read those rollouts instead of "
                "re-running."
            )
        self._record_test_rescore_override(len(spent))

    def _record_test_rescore_override(self, n_spent: int) -> None:
        """Record that the seal was bypassed: an event now, and state so final.json gets marked."""
        rec = {"t": time.time(), "existing_test_rollouts": int(n_spent)}
        with _file_lock(self._state_lock):
            st = self._read_state()
            uses = st.get("test_rescore_override")
            uses = uses if isinstance(uses, list) else []
            uses.append(rec)
            st["test_rescore_override"] = uses
            self._write_state(st)
        self.log_event("test_rescore_override", existing_test_rollouts=int(n_spent),
                       note="test split re-scored with the seal guard overridden; "
                            "the headline number is a second look at test")

    def test_rescore_overrides(self) -> list:
        """Every recorded override of the re-score guard in this run (empty list if none)."""
        try:
            uses = self._read_state().get("test_rescore_override")
        except (OSError, ValueError):
            return []
        return uses if isinstance(uses, list) else []

    def _mark_final_with_overrides(self) -> None:
        """Stamp final.json with the recorded overrides, so a reader sees the seal was bypassed."""
        uses = self.test_rescore_overrides()
        final = self.root / "final.json"
        if not uses or not final.is_file():
            return
        try:
            payload = json.loads(final.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(payload, dict):
            return
        payload["test_rescore_override"] = {"used": True, "count": len(uses), "uses": uses}
        _atomic_write(final, json.dumps(payload, indent=2))

    def commit_test(self) -> Splits:
        """Burn the seal (flip + persist). Call ONLY after test is scored+written.

        Every caller writes final.json just before this, so this is also where a recorded
        override of the re-score guard is stamped into final.json.
        """
        with _file_lock(self._state_lock):
            splits = self.read_splits()
            splits.mark_test_used()  # raises TestSealError if already used (double commit)
            self.write_splits(splits)
        self._mark_final_with_overrides()
        self._record_test_reuse(splits)
        return splits

    def _record_test_reuse(self, splits: Splits) -> None:
        """Warn (never refuse) when another run folder already scored the same test ids.

        Keeps ``test_ledger.jsonl`` beside the runs; logs a ``test_reuse`` event and stamps
        ``test_reuse_count`` (only when > 0) into final.json.
        """
        try:
            th = hashlib.sha256(json.dumps(sorted(map(str, splits.test))).encode()).hexdigest()
            ledger = self.root.parent / "test_ledger.jsonl"
            earlier: list = []
            # Read and append under one lock hold, so two runs finalizing together each see the other.
            # An empty test split scored nothing: no ledger entry, no warning (count 0).
            with _file_lock(self.root.parent / "test_ledger.lock"):
                if splits.test and ledger.is_file():
                    for line in ledger.read_text(encoding="utf-8").splitlines():
                        try:
                            e = json.loads(line)
                        except ValueError:
                            continue
                        if isinstance(e, dict) and e.get("test_hash") == th and e.get("run") != self.root.name:
                            earlier.append(e["run"])
                if splits.test:
                    with ledger.open("a", encoding="utf-8") as f:
                        f.write(json.dumps({"test_hash": th, "run": self.root.name, "time": time.time()}) + "\n")
            earlier = sorted(set(earlier))
            if earlier:
                self.log_event("test_reuse", count=len(earlier), runs=earlier,
                               msg="this test split was already scored by another run")
            final = self.root / "final.json"
            if earlier and final.is_file():
                payload = json.loads(final.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    payload["test_reuse_count"] = len(earlier)
                    _atomic_write(final, json.dumps(payload, indent=2))
        except Exception:  # noqa: BLE001 - a warning aid must never break finalize
            pass

    # Back-compat shim: ``consume_test`` flipped+persisted the seal BEFORE scoring,
    # which permanently burned the headline number on a transient finalize crash.
    # Kept so existing callers/tests don't break, but it is now reserve→commit with
    # nothing in between (i.e. it still seals immediately when used standalone).
    def consume_test(self) -> Splits:
        self.reserve_test()
        return self.commit_test()

    # ---- candidates ---------------------------------------------------------
    def snapshot(self, candidate_id: str, src_dir: Path, ignore=None, seal_eval_surface: bool = True) -> Path:
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
        if candidate_id == "seed" and seal_eval_surface:
            self._seal_eval_surface_at_baseline()
        return dst

    def eval_surface_project(self) -> Path | None:
        """The project this run's eval surface belongs to: the one in its spec_resolved / run_config event,
        else the sibling ``<work>/.capevolve/project``; None when neither is a real project."""
        project = None
        try:  # (1) the project the run was started with, from its spec_resolved / run_config event
            with Path(self.events_path).open(encoding="utf-8") as f:
                for line in f:
                    try:
                        ev = json.loads(line)
                    except Exception:  # noqa: BLE001
                        continue
                    if ev.get("kind") in ("run_config", "spec_resolved") and ev.get("project"):
                        project = Path(str(ev["project"]))
                        break
        except Exception:  # noqa: BLE001
            pass
        if project is None:  # (2) the standard sibling <work>/.capevolve/project; (3) else nothing
            sib = self.root.resolve().parent / "project"
            if sib.is_dir():
                project = sib
        if project is None or not (
                (project / "adapters").is_dir() or (project / "adapter.py").is_file()):
            return None
        return project

    def _seal_eval_surface_at_baseline(self) -> None:
        """Record the project's eval-surface manifest when the seed is snapshotted, i.e. before the
        baseline is scored, so a scorer edited after the baseline is caught. The project is the one
        this run was started with (the ``project`` of its spec_resolved / run_config event); failing that, the standard
        sibling ``<work>/.capevolve/project`` next to the run folder. If no project is found for
        sure, nothing is recorded (act.py records it on its first call). Best effort."""
        try:
            from . import integrity
            path = self.private_dir / integrity.EVAL_SURFACE_MANIFEST
            if path.exists():
                return
            project = self.eval_surface_project()
            if project is None or not (
                    (project / "adapters").is_dir() or (project / "adapter.py").is_file()):
                return
            integrity.record_eval_surface(path, project)
            self.log_event("eval_surface_recorded", project=str(project), late=False, at="baseline")
        except Exception:  # noqa: BLE001 - sealing is an aid here; act.py records it later if this fails
            pass

    def candidate_dir(self, candidate_id: str) -> Path:
        return self.candidates / candidate_id

    # ---- observers -----------------------------------------------------------
    def add_observer(self, observer) -> None:
        """Register a :class:`~cap_evolve.observer.RunObserver`."""
        self._observers.append(observer)

    def save_observer_state(self) -> None:
        """Persist observer state so subsequent sub-processes can resume them."""
        states = []
        for obs in self._observers:
            try:
                s = obs.state()
                if isinstance(s, dict):
                    states.append(s)
            except Exception:  # noqa: BLE001
                pass
        if states:
            _atomic_write(self._observer_state_path,
                          json.dumps({"observers": states}, indent=2))

    def load_observer_state(self) -> list:
        """Read persisted observer state.  Returns ``[]`` if none."""
        if not self._observer_state_path.exists():
            return []
        try:
            data = json.loads(self._observer_state_path.read_text(encoding="utf-8"))
            return data.get("observers", [])
        except Exception:  # noqa: BLE001
            return []

    def close_observers(self) -> None:
        """Flush and close all observers, then persist their state.

        Closed in reverse order so exporters (OTel) flush before
        aggregators (MLflow) that may reference their output.
        """
        for obs in reversed(self._observers):
            try:
                obs.close()
            except Exception:  # noqa: BLE001
                pass
        self.save_observer_state()

    # ---- audit log ----------------------------------------------------------
    def log_event(self, kind: str, **fields) -> None:
        rec = {"t": time.time(), "kind": kind, **fields}
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        for obs in self._observers:
            try:
                obs.on_event(kind, rec)
            except Exception:  # noqa: BLE001
                pass
