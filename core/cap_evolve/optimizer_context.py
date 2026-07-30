"""The ONE optimizer-context seam every algorithm routes through.

Before this module, ``hill-climb`` was the only algorithm that gave its optimizer a
full working context: ``harness.run_step`` called ``_inject_optimizer_context``
(trajectories + capability guidance + native-skill placement) and
``harness._focus_instructions`` rendered the benchmark-authored prompt template with
the capability brief, the failure index, the bench-repo pointer and the parallel-fan-out
note. ``gepa`` bypasses ``run_step`` entirely and ``skillopt`` called
``_focus_instructions`` with no capability/optimizer arguments, so both flagship
algorithms proposed edits from a thinner prompt than the basic climber.

This module is the shared seam that fixes that, and the extension point for future
work (see the issue cluster #114/#115/#128/#129/#130/#137/#140):

  * :class:`OptimizerContext` — the per-run bundle of "what context does the optimizer
    get" knobs, parsed once (from a spec/CLI) and threaded into every algorithm loop as
    ONE argument instead of eight.
  * :func:`inject` — the FILE side: everything copied into the optimizer's own workdir
    (``./trajectories/``, ``./guidance/<cap>/``, ``./guidance/sources/``,
    ``./guidance/diagnose/``, ``./guidance/optimizer/<name>.md`` and the native
    per-agent skills dir). Add a new injected artifact HERE and every algorithm gets it.
  * :func:`render_instructions` — the PROMPT side: the rendered per-iteration
    INSTRUCTIONS (template + capability brief + failure index + bench repo + parallel
    note + consuming-LLM reader block), plus an ``extra`` tail for an algorithm's own
    block (GEPA's reflective dataset pointer, SkillOpt's edit-budget/rejected buffer).
    Add a new prompt block HERE and every algorithm gets it.

Both functions delegate to the existing honesty-neutral helpers in ``harness`` (imported
lazily inside the bodies, since ``harness`` calls back into this module) — nothing about
splits, the gate, or the seal is touched here.

Pure stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .loop import SplitResult
from .rundir import RunDir


# Everything :func:`inject` writes into the optimizer's workdir. These are READ-context,
# never part of the capability, so they must be excluded from: the candidate snapshot
# (``harness._SNAPSHOT_IGNORE``), GEPA's editable-component list (``gepa._components``),
# the eval-cache content hash (``cache.hash_candidate_dir``), the capability-diff filters
# (``harness._CAP_DIFF_SKIP`` / ``dashboard._DIFF_SKIP``) and SkillOpt's applied-edit count
# (``skillopt._changed_components``). One list — add a newly injected artifact here and
# every consumer stays correct.
#
# The diff/count consumers need them for a non-obvious reason: their PARENT side is a
# snapshot (already stripped by ``_SNAPSHOT_IGNORE``) while their CHILD side is the live
# workdir, so an injected file that is missing from the filter shows up as a real
# capability ADDITION on every single iteration.
#
# The complementary set — framework-WRITTEN scratch, as opposed to this copied-in
# read-context — lives in ``rundir`` (``SCRATCH_NAMES`` / ``LEGACY_SCRATCH_NAMES`` /
# ``NON_CAPABILITY_NAMES``), split by OPERATION because the one destructive consumer must
# not take the retired names. See the tier note there; the read-side filters compose the
# two sets and ``rundir`` stays unaware of these.
INJECTED_DIRS = ("trajectories", "guidance", "prior_iterations",
                 ".claude", ".agents", ".gemini", ".opencode", ".bob", ".cursor")
# INSIGHTS.md is the durable synthesized priors block (#128). It is written by
# ``harness._build_insights``, not by ``inject``, but it is the same KIND of artifact —
# framework-owned read-context re-derived every iteration — so it belongs in the same
# list: it must not be snapshotted as capability, must not be an editable GEPA component,
# and must not perturb the eval-cache content hash (it changes as the run progresses, so
# leaving it in would make every iteration miss the cache).
INJECTED_NAMES = ("CLAUDE.md", "AGENTS.md", "GEMINI.md", "INSIGHTS.md")


def _csv(value) -> list[str]:
    """Accept a list OR a comma-separated string (the shape CLI flags arrive in)."""
    if not value:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    return [str(v).strip() for v in value if str(v).strip()]


@dataclass
class OptimizerContext:
    """What context the optimizer gets — identical for every algorithm.

    Every field was previously hill-climb-only plumbing. Constructing this once and
    passing it to ``hill_climb_loop`` / ``gepa_loop`` / ``skillopt_loop`` is what makes
    the three algorithms prompt-equivalent.
    """

    capabilities: list[str] = field(default_factory=list)
    optimizer_name: str | None = None
    instructions_file: str | None = None
    bench_repo: str | None = None
    capability_sources: list[str] = field(default_factory=list)
    project_dir: Path | None = None
    target_model: str = ""
    target_profile_file: str | None = None

    def __post_init__(self) -> None:
        self.capabilities = _csv(self.capabilities)
        self.capability_sources = _csv(self.capability_sources)
        if self.project_dir is not None:
            self.project_dir = Path(self.project_dir)
        self._reader: str | None = None
        self._profile = None

    @classmethod
    def from_args(cls, args) -> OptimizerContext:
        """Build from an argparse namespace using the standard algorithm flag names.

        Every deterministic algorithm's ``scripts/run.py`` declares the same flag set
        (``--capabilities --instructions-file --bench-repo --optimizer-name
        --capability-sources --target-model --target-profile-file``), so this is the one
        place that maps them onto the context. Missing attributes are tolerated.
        """
        get = lambda name, default=None: getattr(args, name, default)  # noqa: E731
        return cls(
            capabilities=get("capabilities", "") or "",
            optimizer_name=get("optimizer_name") or None,
            instructions_file=get("instructions_file") or None,
            bench_repo=get("bench_repo") or None,
            capability_sources=get("capability_sources", "") or "",
            project_dir=Path(get("project")) if get("project") else None,
            target_model=get("target_model", "") or "",
            target_profile_file=get("target_profile_file") or None,
        )

    @staticmethod
    def add_arguments(parser) -> None:
        """Declare the standard optimizer-context flags on an algorithm's argparse.

        Every deterministic algorithm's ``scripts/run.py`` calls this, so ``cap-evolve
        run`` can pass the flags unconditionally instead of gating them on
        ``algorithm == "hill-climb"`` (which silently dropped them for GEPA/SkillOpt).
        """
        parser.add_argument("--capabilities", default="",
                            help="comma-separated capability skills under optimization "
                                 "(e.g. 'system-prompt,tools'); surfaced to the optimizer "
                                 "so it knows the allowed edit space")
        parser.add_argument("--instructions-file", default=None,
                            help="optimizer-instructions template (intake-authored) to "
                                 "render the per-iteration prompt from; defaults to the "
                                 "shipped template")
        parser.add_argument("--bench-repo", default=None,
                            help="path to the benchmark/runner source, surfaced to the "
                                 "optimizer as read-only context")
        parser.add_argument("--optimizer-name", default=None,
                            help="resolved optimizer name (registry row); used to copy "
                                 "that optimizer's features reference + native skills "
                                 "into the optimizer workdir")
        parser.add_argument("--capability-sources", default="",
                            help="comma-separated supporting source files (data models / "
                                 "types the tools import) copied verbatim into the "
                                 "optimizer's ./guidance/sources/; relative to --project")
        parser.add_argument("--target-model", default="",
                            help="consuming/runtime model id or tier keyword "
                                 "(frontier|strong|mid|weak)")
        parser.add_argument("--target-profile-file", default=None,
                            help="optional project-local brief overriding the tier's "
                                 "built-in brief")

    def profile(self):
        """The resolved consuming-LLM ``TargetProfile`` (cached)."""
        if self._profile is None:
            from . import target_profile as _tp
            self._profile = _tp.resolve(self.target_model, self.target_profile_file,
                                        project_dir=self.project_dir)
        return self._profile

    def target_reader(self) -> str:
        """The consuming-LLM ("reader") brief block, resolved once and cached."""
        if self._reader is None:
            from . import target_profile as _tp
            self._reader = _tp.reader_block(self.profile())
        return self._reader

    def log_profile(self, run_dir: RunDir) -> None:
        """Record the resolved consuming-LLM profile so report + dashboard surface it.

        Called by every algorithm's ``run.py``; previously hill-climb-only.
        """
        prof = self.profile()
        if not prof.is_agnostic:
            run_dir.log_event("target_profile", model=prof.model, tier=prof.tier,
                              suggested_num_trials=prof.suggested_num_trials,
                              resolution_note=prof.resolution_note)


def inject(adapter, run_dir: RunDir, workdir: Path, *, split: str,
           ctx: OptimizerContext | None = None, tag: str | None = None) -> None:
    """Copy the optimizer's read-context into ``workdir`` (the FILE side of the seam).

    ``tag`` scopes ``./trajectories/`` to a specific eval tag — GEPA needs the *parent's
    minibatch* traces (not the run's current best), which is exactly the verbatim,
    untruncated data its ``REFLECTION.md`` only summarizes. Omit it to keep the
    best/parent-then-seed fallback chain used by hill-climb and SkillOpt.
    """
    from . import harness
    ctx = ctx or OptimizerContext()
    harness._inject_optimizer_context(
        adapter, run_dir, workdir, split=split,
        capabilities=ctx.capabilities, optimizer_name=ctx.optimizer_name,
        capability_sources=ctx.capability_sources, project_dir=ctx.project_dir,
        tag=tag,
    )


# Hard ceiling on ONE iteration's assembled INSTRUCTIONS. Every individual block is
# already bounded (``always_fail[:10]``, ``flaky[:8]``, ``errored[:25]``,
# ``actionable[:12]``, per-field ``[:800]``) but nothing bounded the SUM — and the
# cross-iteration blocks (LEDGER/RUNMAP rows, the JOURNAL, the rejected buffer) grow with
# the run, so a 100-iteration run could balloon the optimizer prompt. 60k chars ≈ 15k
# tokens, well above every measured render (largest observed: 4,655 B, GEPA iteration 1).
# ponytail: one global cap; per-block budgets only when a real run actually hits this.
MAX_INSTRUCTIONS_CHARS = 60_000


def render_instructions(scored_result: SplitResult, focus_ids, label: str, *,
                        ctx: OptimizerContext | None = None,
                        algorithm: str = "hill-climb",
                        run_dir: RunDir | None = None,
                        parent_id: str | None = None,
                        extra: str = "",
                        max_chars: int = MAX_INSTRUCTIONS_CHARS) -> str:
    """Render one iteration's INSTRUCTIONS (the PROMPT side of the seam).

    ``scored_result`` is the evaluated result the failure index is built FROM (full val
    for hill-climb / SkillOpt, the parent's minibatch for GEPA). ``focus_ids`` NARROWS
    that result, so it must name tasks that are IN it — ids from another split are
    disjoint by construction and would filter the failure index down to nothing.
    ``harness._focus_instructions`` refuses to filter on zero overlap and says so in the
    prompt instead of reporting a confident "0 failing of 0 tasks". The parameter is
    named ``scored_result`` (not ``current``) so that invariant is visible at every call
    site rather than living in this docstring.

    ``extra`` is the algorithm's own tail block and stays LAST. Blocks that EVERY
    algorithm should get belong in the shared body instead — it already receives
    ``run_dir``, so #128's ``INSIGHTS.md`` and #129's ``rejected.jsonl`` need no
    signature change.

    When ``run_dir`` is given the empty-seed signal is computed from the parent candidate
    (``parent_id``, default the run's best). The assembled text is capped at ``max_chars``.
    """
    from . import harness
    ctx = ctx or OptimizerContext()
    seed_empty = None
    if run_dir is not None:
        cid = parent_id or run_dir.best_id
        if cid:
            seed_empty = harness._capability_is_empty(ctx.capabilities,
                                                      run_dir.candidate_dir(cid))
    text = harness._focus_instructions(
        scored_result, focus_ids, label,
        capabilities=ctx.capabilities, algorithm=algorithm,
        instructions_file=ctx.instructions_file, bench_repo=ctx.bench_repo,
        optimizer_name=ctx.optimizer_name, seed_empty=seed_empty,
        target_reader=ctx.target_reader(),
    )
    out = f"{text}\n{extra}" if extra else text
    return cap_instructions(out, max_chars)


def cap_instructions(text: str, max_chars: int = MAX_INSTRUCTIONS_CHARS) -> str:
    """Enforce the one-iteration prompt ceiling, keeping the head and tail.

    Also called by ``harness._augment_instructions``, which appends the cross-iteration
    blocks (LEDGER pointer + #129 rejected-approach constraints) AFTER this module has
    rendered — so the FINAL assembled prompt, not just the rendered half, is capped.

    The kept TAIL is 30% of the budget (18 KB at the default 60 KB ceiling) and those
    appended blocks live in it, which is why the #129 constraint block survives an
    overflow whole — header, rows and footer — instead of being cut mid-list: it measures
    ~7 KB even at 200 rejections. Anything appended after this point must stay well under
    that 30%, or it starts eating itself rather than the middle.
    """
    if max_chars and len(text) > max_chars:
        # Keep the head (task framing, capability brief, failure index) and the tail
        # (the algorithm's own block); elide the middle, which is the part that grows.
        keep = max(max_chars - 200, 200)
        head, tail = text[: (keep * 7) // 10], text[-(keep * 3) // 10:]
        text = (f"{head}\n\n... [{len(text) - keep} chars elided to keep this prompt under "
                f"{max_chars} chars — the full record is in the run dir] ...\n\n{tail}")
    return text
