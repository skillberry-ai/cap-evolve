"""Bounded parallel candidate evaluation with a serialized commit point.

The isolation unit is a **hermetic per-candidate workspace** under
``<run>/work/<candidate_id>/``: a private copy of the parent capability that the
optimizer mutates and the adapter evaluates, so ``materialize → run_target →
score`` for candidate A can never see or clobber candidate B's files. That
workspace already existed (``harness.run_step``); what this module adds is the two
things parallelism actually needs:

  1. ``workspace()`` — deterministic teardown of those workspaces on normal exit,
     on exception, AND on SIGINT/SIGTERM, so a crashed or interrupted run leaves no
     orphans behind.
  2. ``map_ordered()`` — bounded concurrency that returns results in INPUT order,
     with ``workers == 1`` running fully inline (no threads created at all), so the
     default serial path is byte-for-byte the code path it always was.

Why a directory workspace and not a ``git worktree``: a worktree of the run repo
checks out the *run dir's* shape (``candidates/``, ``state.json``, …), not the
capability-at-root shape every optimizer and adapter expects, and the capability's
own project is not required to be a git repo at all. The isolation property a
worktree would buy (a private tree + a clean diff vs the parent) is already
provided by the copy plus the existing per-iteration ``VersionStore`` commit, at
lower cost (no ``.git`` inside the candidate, nothing to leak into
``.git/worktrees``, no 200-500ms per candidate). See the PR for the full rationale.

**The honesty core stays single-threaded.** Nothing here gates, accepts, snapshots,
or touches the seal. Workers only produce a candidate + its val ``SplitResult``; the
caller applies every result serially, in a deterministic order — that serialized
commit point is what keeps the gate, ``best_id``, spend accounting and the test seal
free of races. Pure stdlib (``concurrent.futures`` + ``signal``).
"""

from __future__ import annotations

import contextlib
import shutil
import signal
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Iterable, Sequence, TypeVar

T = TypeVar("T")
R = TypeVar("R")

# Workspaces currently checked out, so an interrupt can clean up what a `finally`
# never gets to run for. Guarded by a lock because workers register concurrently.
_LIVE: set[Path] = set()
_LIVE_LOCK = threading.Lock()
_HANDLERS_INSTALLED = False


def resolve_workers(n) -> int:
    """Clamp a user-supplied ``--parallel`` value to a sane worker count.

    ``None``/0/negative/garbage all collapse to 1 (serial), which is the default
    everywhere: parallelism must be opt-in so no existing run changes behaviour.
    Capped at 16 — beyond that the run dir's serialized commit point, not the
    workers, is the bottleneck.
    """
    try:
        v = int(n)
    except (TypeError, ValueError):
        return 1
    return max(1, min(16, v))


def _cleanup_all() -> None:
    with _LIVE_LOCK:
        live = sorted(_LIVE)
        _LIVE.clear()
    for p in live:
        shutil.rmtree(p, ignore_errors=True)


def _install_handlers() -> None:
    """Chain SIGINT/SIGTERM cleanup in front of whatever handler is installed.

    A Ctrl-C during a parallel round unwinds the main thread but NOT the worker
    threads' ``finally`` blocks reliably, so workspaces could survive as orphans.
    We remove every live workspace first, then re-raise into the previous handler so
    the process still dies the way it would have. Best-effort: installing a handler
    is only legal on the main thread, and a run driven from a worker thread simply
    keeps the ``finally``-based cleanup.
    """
    global _HANDLERS_INSTALLED
    if _HANDLERS_INSTALLED:
        return
    if threading.current_thread() is not threading.main_thread():
        return
    import atexit

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            prev = signal.getsignal(sig)
        except (ValueError, OSError):  # pragma: no cover - platform without the signal
            continue

        def _handler(signum, frame, _prev=prev):
            _cleanup_all()
            if callable(_prev):
                _prev(signum, frame)
            elif _prev == signal.SIG_DFL:
                signal.signal(signum, signal.SIG_DFL)
                signal.raise_signal(signum)

        with contextlib.suppress(ValueError, OSError):
            signal.signal(sig, _handler)
    atexit.register(_cleanup_all)
    _HANDLERS_INSTALLED = True


@contextlib.contextmanager
def workspace(root: Path, candidate_id: str, parent_dir: Path, *, keep: bool = True):
    """Hermetic per-candidate workspace at ``root/<candidate_id>``, cleaned up always.

    Yields a fresh copy of ``parent_dir``. A pre-existing dir at that path (a resumed
    or retried iteration) is removed first, so a candidate never inherits a previous
    attempt's scratch. With ``keep=True`` (the default, matching today's behaviour)
    the directory survives for post-hoc inspection and only the interrupt registry
    entry is dropped; ``keep=False`` removes it on exit, on exception, and on
    SIGINT/SIGTERM.
    """
    root = Path(root)
    wd = root / candidate_id
    _install_handlers()
    if wd.exists():
        shutil.rmtree(wd)
    root.mkdir(parents=True, exist_ok=True)
    shutil.copytree(parent_dir, wd)
    with _LIVE_LOCK:
        _LIVE.add(wd)
    try:
        yield wd
    finally:
        with _LIVE_LOCK:
            _LIVE.discard(wd)
        if not keep:
            shutil.rmtree(wd, ignore_errors=True)


def live_workspaces() -> list[Path]:
    """Workspaces currently checked out (for tests / leak assertions)."""
    with _LIVE_LOCK:
        return sorted(_LIVE)


def map_ordered(fn: Callable[[T], R], items: Iterable[T], *, workers: int = 1) -> list[R]:
    """Apply ``fn`` over ``items`` with at most ``workers`` in flight, INPUT order out.

    ``workers <= 1`` runs inline — no executor, no threads — so the serial default is
    the same call sequence it always was. Exceptions propagate (the caller decides
    whether a failed candidate is fatal); order is preserved regardless of completion
    order, which is what makes the caller's serialized commit loop deterministic.
    """
    items = list(items)
    workers = resolve_workers(workers)
    if workers == 1 or len(items) <= 1:
        return [fn(x) for x in items]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fn, items))


def adapter_is_parallel_safe(adapter) -> tuple[bool, str]:
    """Whether ``adapter`` may be driven from several threads at once.

    DEFAULT DENY, because the adapter contract still supports ``apply()`` as a
    *global* inject ("make this candidate the one the runner uses") — exactly the
    single shared slot that makes two concurrent candidates clobber each other. So:

      * an explicit ``parallel_safe = True`` (or ``False``) on the adapter is
        authoritative — an adapter that knows it is hermetic says so;
      * otherwise it is safe only if it overrides NEITHER ``apply`` nor ``live``,
        i.e. it uses the base class's pure default which just yields the candidate
        dir and mutates nothing outside it.

    Returns ``(safe, reason)``; the reason is logged so a silent downgrade to serial
    never looks like a speedup that failed to materialize.
    """
    declared = getattr(adapter, "parallel_safe", None)
    if isinstance(declared, bool):
        return declared, ("adapter declares parallel_safe=True" if declared
                          else "adapter declares parallel_safe=False")
    from .adapter import CapabilityAdapter
    overrides = [name for name in ("apply", "live")
                 if getattr(type(adapter), name, None)
                 is not getattr(CapabilityAdapter, name, None)]
    if overrides:
        return False, (f"adapter overrides {'/'.join(overrides)}() — that hook may be a "
                       "GLOBAL inject (one shared slot), so concurrent candidates could "
                       "clobber each other; set `parallel_safe = True` on the adapter if "
                       "it is hermetic")
    return True, "adapter uses the pure default live()/apply() (no global state)"


def resolve_workers_for(adapter, n, *, run_dir=None) -> int:
    """``resolve_workers(n)``, downgraded to 1 when the adapter isn't concurrency-safe.

    Logs ``parallel_downgraded`` in the run dir on a downgrade so the fallback is in
    the audit trail rather than an unexplained absence of speedup.
    """
    workers = resolve_workers(n)
    if workers == 1:
        return 1
    safe, reason = adapter_is_parallel_safe(adapter)
    if safe:
        return workers
    if run_dir is not None:
        run_dir.log_event("parallel_downgraded", requested=workers, workers=1, reason=reason)
    return 1
