"""The adapter contract — the small set of methods the OPTIMIZER agent implements.

This is cap-evolve's generalization device (prior agent-optimization work had 3 adapters, SkillOpt had 5;
we use 4, cleaner). The using-agent implements these once in
``.capevolve/project/adapters/`` so that *any* target agent, *any* benchmark, and
*any* capability can be driven by the same pipeline:

    tasks(split)                              -> list[Task]   # where eval data comes from
    run_target(task, ctx, *, seed)            -> Rollout      # run the agent under test
    score(task, rollout)                      -> Score        # 0..1 reward + ASI feedback
    materialize(candidate_dir, edits=None)    -> None         # write edits into the dir (pure)
    live(candidate_dir)                       -> ctx (CM)     # make the candidate LIVE for a rollout

Why ``materialize`` + ``live`` instead of a single ``apply``:
``apply(candidate_dir)`` used to be a *global* side effect (e.g. monkeypatching a
benchmark's policy), which (a) prevented two candidates being evaluated
concurrently — there is only one global slot — and (b) made the safety ``check``
mutate the host. We split the two concerns:

  * ``materialize(dir, edits)`` is **pure**: it only writes ``edits`` into ``dir``.
    No global effect, so it is safe to call any number of times, in parallel, and
    during ``check``. Default: write each ``{component: text}`` edit as a file.
  * ``live(dir)`` is a **context manager** that yields a ``ctx`` the runner uses
    for the duration of one evaluation, and tears the live state down on exit.
    The yielded ``ctx`` defaults to ``candidate_dir`` so ``run_target``/``run_batch``
    signatures line up unchanged. The default ``live`` calls the still-supported
    ``apply(candidate_dir)`` on enter, so adapters that define ``apply`` (e.g. tau2,
    which injects a policy) keep working with no edit.

``apply(edits=None)`` remains a supported back-compat hook: "make the capability
in ``candidate_dir`` the one the target actually uses" (prior work's *inject*).
With ``edits`` it also writes those edits first. Splits, trials, gating, pass^k,
memory and the run dir are provided by ``core`` and must NOT be reimplemented
here — that is what keeps eval honest.

Seed contract (W1): the harness threads an explicit per-trial ``seed`` into
``run_target``/``run_batch`` (``seed = base_seed + trial_index``). Adapters wrapping
a STOCHASTIC runner (an LLM agent, a sampler) **MUST** forward this ``seed`` to the
runner so distinct trials are genuinely independent draws — otherwise pass^k /
the significance gate degenerate (identical trials ⇒ stderr 0 ⇒ "any Δ>0 wins").
Deterministic adapters can ignore it.

Stub methods raise ``NotImplementedError`` with an ``IMPLEMENT ME`` marker so the
checker can detect and report exactly what is unfilled.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from pathlib import Path

from .types import Rollout, Score, Task

IMPLEMENT_MARKER = "IMPLEMENT ME"


class CapabilityAdapter(ABC):
    """Implement this in ``.capevolve/project/adapters/adapter.py``."""

    @abstractmethod
    def tasks(self, split: str) -> list[Task]:
        """Return the tasks for ``split`` ('train'|'val'|'test').

        Source is yours: a jsonl file, a benchmark export, a generator. Return
        the SAME tasks for the same split across calls (determinism).
        """
        raise NotImplementedError(f"{IMPLEMENT_MARKER}: tasks(split)")

    @abstractmethod
    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        """Run the target agent on ``task`` with the candidate live as ``ctx``.

        ``ctx`` is whatever ``live()`` yielded (default: the candidate dir Path).
        Capture output + trace + tool calls + cost into the returned ``Rollout``.
        Do NOT score here. If the runner is STOCHASTIC, forward ``seed`` to it so
        each trial is an independent draw (see module docstring). If the run could
        not be produced for an INFRASTRUCTURE reason (timeout, API/run error),
        set ``Rollout.error`` so the engine classifies it as uncontrollable noise.
        """
        raise NotImplementedError(f"{IMPLEMENT_MARKER}: run_target(task, ctx, *, seed)")

    @abstractmethod
    def score(self, task: Task, rollout: Rollout) -> Score:
        """Score one rollout in [0, 1] with natural-language ``feedback``.

        ``feedback`` is the learning signal (gepa's ASI) — describe WHY it scored
        as it did in general terms; never leak the gold answer into feedback.
        """
        raise NotImplementedError(f"{IMPLEMENT_MARKER}: score(task, rollout)")

    # ---- making a candidate live (materialize + live; apply is back-compat) ----

    def materialize(self, candidate_dir: Path, edits: dict | None = None) -> None:
        """Write ``edits`` into ``candidate_dir`` — PURE, no global effect.

        ``edits`` is ``{component -> text}`` (a file name / md-section -> new
        content). The default writes each component as a file under
        ``candidate_dir``. Override to support a capability-specific patch format.
        Calling this NEVER changes anything outside ``candidate_dir``, so it is
        safe to call repeatedly, in parallel, and from the safety ``check``.
        """
        if not edits:
            return
        cdir = Path(candidate_dir)
        cdir.mkdir(parents=True, exist_ok=True)
        for component, text in edits.items():
            dst = cdir / str(component)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(text if isinstance(text, str) else str(text), encoding="utf-8")

    @contextmanager
    def live(self, candidate_dir: Path):
        """Make ``candidate_dir`` the live capability for ONE evaluation.

        A context manager yielding the ``ctx`` the runner uses. The default yields
        ``candidate_dir`` itself (so ``run_target``/``run_batch`` keep their
        signatures) and, for back-compat, calls ``self.apply(candidate_dir)`` on
        enter — that is how adapters that historically defined ``apply`` (e.g. tau2
        injecting a policy) keep working unchanged. Override ``live`` when the live
        state needs explicit teardown, or to yield a richer ``ctx`` (a sandbox
        handle, a worktree path) so independent candidates can run concurrently
        without sharing a single global slot.
        """
        self.apply(candidate_dir)
        try:
            yield candidate_dir
        finally:
            pass

    def apply(self, candidate_dir: Path, edits: dict | None = None) -> None:
        """Back-compat hook: make ``candidate_dir`` the one the target uses.

        Still supported so existing adapters (tau2 → inject) need no change. New
        adapters should prefer the ``materialize`` (pure write) + ``live`` (context
        manager) split. The default ``apply`` materializes ``edits`` (if any) and
        otherwise does nothing global — a benchmark adapter overrides it to inject.
        """
        self.materialize(candidate_dir, edits)

    def trajectories(self, split: str, ctx=None):
        """OPTIONAL: the directory of raw trajectories from the most recent eval.

        Return a ``Path`` to a directory holding the runner's native trajectories
        for the last evaluation of ``split`` — *any* structure, files in *any*
        format. cap-evolve copies that directory **verbatim** into the optimizer's
        working dir (as ``./trajectories/``) so the optimizer can read the full,
        unmodified traces — not a lossy summary. The PATH comes from your inputs
        (e.g. the directory your benchmark writes its run logs/results to); how the
        objective metric is extracted from those traces lives in ``score()``.

        Return ``None`` (the default) if you have no separate native trajectory
        store — the harness then falls back to copying cap-evolve's own per-rollout
        JSON (which already embeds each rollout's trace).
        """
        return None


def stub_methods(adapter: object) -> list[str]:
    """Return the names of adapter methods that are still unimplemented.

    A method counts as a stub if calling it raises ``NotImplementedError`` whose
    message carries the IMPLEMENT marker. We probe with throwaway args; any other
    exception means the method is implemented (it ran far enough to fail on the
    fake input), so it is NOT reported as a stub.

    Only the three abstract methods are probed: ``materialize``/``live``/``apply``
    have working defaults on the base class, so they are never stubs.
    """
    from pathlib import Path as _P

    probes = {
        "tasks": lambda m: m("val"),
        "run_target": lambda m: m(Task(id="__probe__"), _P("."), seed=0),
        "score": lambda m: m(Task(id="__probe__"), Rollout(task_id="__probe__")),
    }
    stubs = []
    for name, probe in probes.items():
        m = getattr(adapter, name, None)
        if m is None:
            stubs.append(name)
            continue
        try:
            probe(m)
        except NotImplementedError as e:
            if IMPLEMENT_MARKER in str(e):
                stubs.append(name)
        except Exception:
            pass  # implemented (failed on fake input, which is fine)
    return stubs
