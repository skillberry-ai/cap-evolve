"""Prompt templating: the per-iteration INSTRUCTIONS body and every block inside it.

Split out of ``harness.py`` (#115). ``_focus_instructions`` renders the shipped
``templates/project/optimizer/INSTRUCTIONS.md`` by substituting the dynamic blocks —
the failure index, the passing set to preserve, the capability edit-space brief, the
algorithm brief, the parallel-subagents note and the empty-seed note — plus the failure
classification those blocks are built from.

Pure text assembly: nothing here writes a file, runs an eval, or touches a gate, which
is why it can be read (and its bounds audited) without the loop in view.
"""

from __future__ import annotations

from pathlib import Path

from .loop import SplitResult

# ---- shared hill-climb loop (parameterized by focus) ----------------------

def _is_infra(pt) -> bool:
    """Structured infra signal: did ANY of this task's trials carry ``error``?

    The harness records ``raw.errored = True`` when any trial's ``Rollout.error``
    was set (a timeout, API/run error, omitted batch result). This is the raw
    *signal* — true the moment a single trial errored. It does NOT by itself mean
    the task is uncontrollable; ``_is_infra_ignore`` adds the majority-errored +
    low-mean condition that justifies telling the optimizer to ignore the task.
    We use the STRUCTURED field — not substring-matching feedback prose, which
    dropped real "error" bugs and misfired on feedback that merely *mentions* an
    exception.
    """
    return bool((pt.get("raw") or {}).get("errored"))


def _is_infra_ignore(pt) -> bool:
    """Is this task TRULY uncontrollable (safe to tell the optimizer to ignore)?

    A task belongs in the ignore/infra bucket ONLY when MOST of its trials errored
    AND its mean reward is ≈ 0 — i.e. the failure is dominated by infrastructure
    noise, not by capability. A mostly-passing task that merely had ONE errored
    trial is solid/flaky and must be PROTECTED, never called "noise / no edit can
    fix it" — that misclassification is what let prior regressions hide.

    Trial-level data: ``raw.errored_trials`` / ``raw.n_trials`` give the exact
    counts when present. We fall back to the boolean ``raw.errored`` (any-trial
    errored) combined with the aggregate reward when the per-trial counts are not
    recorded (older rollouts), still requiring mean ≈ 0 so a passing task is never
    bucketed as ignore.
    """
    raw = pt.get("raw") or {}
    if not raw.get("errored"):
        return False
    eps = 1e-9
    mean_reward = float(pt.get("reward", 0) or 0)
    if mean_reward > eps:
        return False  # it passes (at least partially) — controllable, protect it
    errored_trials = raw.get("errored_trials")
    n_trials = raw.get("n_trials") or pt.get("n")
    if errored_trials is not None and n_trials:
        return int(errored_trials) * 2 > int(n_trials)  # strict majority errored
    # No per-trial counts: any-trial-errored + mean≈0 is the best we can do.
    return True


# Per-capability edit-space brief surfaced to the optimizer. Kept short and
# general; the long-form guidance lives in each capability skill's SKILL.md, which
# the optimizer can open via the pointer we emit. ``summary`` is read from the
# capability's meta.yaml at runtime so this never drifts from the skill.
_CAP_EDIT_SPACE = {
    "tools": "Edit tool names/descriptions, per-parameter docs, in-description examples, "
             "the JSON schema, and the handler code. HIGHEST-LEVERAGE EDIT: WRITE A NEW "
             "CODE-BEARING TOOL (a real body — loops, validation, calls to existing tools), "
             "because a deterministic tool can't be 'forgotten' the way a prompt rule can. "
             "Two patterns to prefer: (1) a VALIDATION/RULE-ENFORCEMENT tool that wraps a "
             "primitive — validate/normalize inputs, enforce a GENERAL rule, then delegate "
             "to the primitive (e.g. cancel_record_safely(id) checks cancellable then calls "
             "cancel_record), and REMOVE the raw primitive so the only path is the safe one; "
             "(2) a WORKFLOW/LOOP tool that collapses a recurring multi-step sequence or N "
             "repeated calls into ONE call with real loops (e.g. loop get_record over a list "
             "of ids). Keep the toolset LEAN — REPLACE/consolidate, don't accumulate. The "
             "body must be real code, never '...' or docstring-only. Selection is driven by "
             "the name+description; argument-filling by the parameter schema/enums.",
    "system-prompt": "Edit the prompt/policy text: instructions, decision policy, and the "
                     "output contract. Prefer sharpening rules the traces show the agent "
                     "breaking; do not just append more preamble.",
    "skill-package": "Edit the SKILL.md (frontmatter + body), its references, and bundled "
                     "scripts, staying within skill-creator rules (valid frontmatter, "
                     "progressive disclosure, one-level references, concise body).",
    "mcp-tool": "ONLY safe edits: tool/parameter documentation, in-description examples, and "
                "adding/removing tools from the exposed set. The wire schema and tool code "
                "are owned by the external server and are NOT editable here.",
}


def _capability_brief(capabilities) -> str:
    """A compact 'what you are allowed to edit' block for the optimizer prompt.

    ``capabilities`` is the list from the spec (e.g. ``["system-prompt", "tools"]``).
    For each we emit its one-line meta summary plus the allowed edit space, and a
    pointer to the full capability SKILL.md so the optimizer can use the whole
    edit space (e.g. composite tools) rather than guessing from the files alone.
    Returns "" when no capabilities are known (older callers) so behavior is additive.
    """
    caps = [c for c in (capabilities or []) if c]
    if not caps:
        return ""
    skills_root = Path(__file__).resolve().parents[2] / "skills" / "capabilities"
    lines = ["## What you are editing (the allowed edit space)",
             "The capability under optimization is composed of these editable artifact(s). "
             "Use the FULL edit space below — do not limit yourself to trivial wording tweaks."]
    for c in caps:
        summary = ""
        meta = skills_root / c / "meta.yaml"
        if meta.exists():
            for ln in meta.read_text(encoding="utf-8").splitlines():
                if ln.startswith("summary:"):
                    summary = ln.split(":", 1)[1].strip()
                    break
        edit = _CAP_EDIT_SPACE.get(c, "")
        skill_md = skills_root / c / "SKILL.md"
        lines.append(f"- **{c}** — {summary}")
        if edit:
            lines.append(f"  - Allowed edits: {edit}")
        if skill_md.exists():
            # The full skill is copied into the workdir at ./guidance/<c>/ (see
            # run_step) so the optimizer can read it without leaving its dir.
            lines.append(f"  - Full guidance (read it): ./guidance/{c}/SKILL.md")
    return "\n".join(lines)


def _algorithm_brief(current_val: SplitResult, algorithm: str) -> str:
    """How acceptance works, so the optimizer aims for a real, significant gain."""
    return (
        "## How your edit is judged\n"
        f"Algorithm: {algorithm}. Your edited candidate is re-scored on the SAME held-out "
        f"val tasks and compared to the current best (val reward {current_val.reward:.3f}). "
        "It is ACCEPTED only if the per-task improvement clears a significance bar (a noise "
        "margin), so a tiny or lucky change is rejected. Aim for a real, generalizing gain "
        "across a CLASS of failures — not a one-off patch to a single task (that overfits "
        "and gets rejected or hurts the held-out test)."
    )


def _classify(per):
    """Split focus tasks into infra-ignore / always-failing / flaky / solid.

    Uses the AGGREGATE reward (mean over trials), so a task that passes only some
    of the time is 'flaky' (0 < reward < 1) — a sometimes-good behavior to make
    CONSISTENT — distinct from an always-failing task (reward ~ 0) whose root cause
    must be fixed. (Per-task feedback is from the last trial and can disagree with a
    graded mean; the reward is the honest signal, so we classify by it.)

    The infra-IGNORE bucket is reserved for TRULY uncontrollable tasks
    (``_is_infra_ignore``: most trials errored AND mean ≈ 0). A task that merely had
    an errored trial but still mostly passes is NOT ignored — it falls through to
    solid/flaky and is therefore PROTECTED. Returns the four buckets; ``solid`` is
    the protected set callers must not regress."""
    errored = [pt for pt in per if _is_infra_ignore(pt)]
    rest = [pt for pt in per if not _is_infra_ignore(pt)]
    eps = 1e-9
    always_fail = [pt for pt in rest if (pt.get("reward", 0) or 0) <= eps]
    flaky = [pt for pt in rest if eps < (pt.get("reward", 0) or 0) < 1.0 - eps]
    solid = [pt for pt in rest if (pt.get("reward", 0) or 0) >= 1.0 - eps]
    return errored, always_fail, flaky, solid


def _fmt(pt) -> str:
    return f"- {pt.get('task_id')} (reward {float(pt.get('reward', 0) or 0):.2f}): " \
           f"{str(pt.get('feedback', '')).strip()[:400]}"


def _passing_block(solid, *, max_ids: int = 60) -> str:
    """A block listing currently-PASSING (solid, reward≈1) task ids to PROTECT.

    The optimizer is only ever shown failures; without the wins it cannot tell
    which behaviors its edit must preserve, and prior candidates fixed a few tasks
    while silently breaking many passing ones (net ≈ 0). Surfacing the passing ids
    makes non-regression a checkable, explicit constraint."""
    if not solid:
        return ""
    ids = [str(pt.get("task_id")) for pt in solid]
    shown = ", ".join(ids[:max_ids])
    more = f" … (+{len(ids) - max_ids} more)" if len(ids) > max_ids else ""
    return (
        f"## Currently PASSING ({len(solid)} task(s)) — your edit MUST NOT regress these\n"
        f"These tasks already score ~1.0. Preserve their behavior: any edit that changes "
        f"their trajectory is a regression and will be rejected. Protect: {shown}{more}\n"
    )


# The optimizer-instructions template ships in the repo as a project default and is
# what the intake phase copies + customizes per benchmark. The harness renders it by
# substituting the per-iteration dynamic blocks below; nothing benchmark-specific lives
# here. ``{{...}}`` placeholders: FOCUS_SUMMARY, FAILURES, PASSING, CAP_BRIEF, ALGO_BRIEF, BENCH_REPO.
_DEFAULT_INSTRUCTIONS_TEMPLATE = (
    Path(__file__).resolve().parents[2] / "templates" / "project" / "optimizer" / "INSTRUCTIONS.md"
)


def _failures_block(always_fail, flaky, errored) -> str:
    """The per-iteration (a)/(b)/errored failure index for the prompt."""
    lines: list[str] = []
    if always_fail:
        lines.append(f"## (a) {len(always_fail)} ALWAYS-failing task(s) — fix the shared "
                     "root cause (full traces in ./trajectories/):")
        lines += [_fmt(pt) for pt in always_fail[:10]]
        lines.append("")
    if flaky:
        lines.append(f"## (b) {len(flaky)} FLAKY task(s) — pass sometimes; make the good "
                     "behavior consistent (full traces in ./trajectories/):")
        lines.append("(reward is the mean over trials — the honest signal; the feedback line is "
                     "from the LAST trial and may say 'passed' even when the mean is below 1.)")
        lines += [_fmt(pt) for pt in flaky[:8]]
        lines.append("")
    if not always_fail and not flaky:
        lines.append("## No actionable failures in focus — seek a robustness/generalization gain "
                     "that does not regress the solid tasks.")
        lines.append("")
    if errored:
        ids = ", ".join(str(pt.get("task_id")) for pt in errored[:25])
        lines += [
            f"## Ignore — {len(errored)} task(s) are uncontrollable infrastructure errors",
            "These tasks had MOST of their trials abort with a run/infrastructure error "
            "AND a mean reward of ~0 — truly environment noise (timeouts/aborted runs), NOT "
            "a capability problem; no edit can fix them, so do not change anything on their "
            "account: " + ids,
            "(A task that merely had one errored trial but still mostly PASSES is NOT listed "
            "here — it is solid/flaky and must be protected, not ignored.)",
            "",
        ]
    return "\n".join(lines)


def _optimizer_parallel(optimizer_name: str | None) -> bool:
    """Whether the resolved optimizer's harness can spawn parallel subagents.

    Reads the optional ``parallel: "true"`` flag from the optimizer registry row.
    Best-effort: an unknown agent / unreadable registry ⇒ False (sequential). This
    gates ONLY the parallel fan-out guidance in {{PARALLEL_NOTE}}.
    """
    if not optimizer_name:
        return False
    try:
        repo_root = Path(__file__).resolve().parents[2]
        reg_path = repo_root / "skills" / "optimizers" / "registry.yaml"
        if not reg_path.is_file():
            return False
        from .specfile import read_yaml
        registry = read_yaml(reg_path.read_text(encoding="utf-8")) or {}
        row = registry.get(optimizer_name) or {}
        return str(row.get("parallel") or "").strip().lower() == "true"
    except Exception:  # noqa: BLE001
        return False


def _parallel_note(parallel: bool, optimizer_name: str | None) -> str:
    """The {{PARALLEL_NOTE}} block — gates the fan-out on the agent's capability."""
    if parallel:
        ref = f"./guidance/optimizer/{optimizer_name}.md" if optimizer_name else "./guidance/optimizer/"
        return ("Your agent supports parallel subagents/worktrees (see " + ref + "). FAN OUT to "
                "cover MANY clusters at once: one read-only subagent per trajectory-group to "
                "diagnose, then one edit-subagent per issue (each in its own worktree), then "
                "MERGE every edit into this ONE candidate with no conflicts. This is how a single "
                "iteration fixes many issues across many trajectories, not just the biggest one.")
    return ("Your agent runs single-threaded (no subagents). Still address as MANY clusters as you "
            "can in this ONE candidate — work through them in turn, drafting and keeping every "
            "real, safe fix, not just the biggest one.")


def _capability_is_empty(capabilities, cand_dir: Path) -> bool | None:
    """Whether the candidate is an EMPTY seed, from the capabilities' own ``is_empty()``.

    Imports each ``skills/capabilities/<name>/scripts/abstract.py`` (same loader pattern
    as ``check.py``) and calls ``is_empty(cand_dir)``. Returns True only if EVERY
    capability reports empty, False if ANY reports non-empty, and None when the signal
    can't be obtained (no capabilities, missing abstract, or no ``is_empty`` — older
    capabilities) so callers fall back to the reward heuristic.
    """
    caps = [c for c in (capabilities or []) if c]
    if not caps:
        return None
    import importlib.util

    skills_root = Path(__file__).resolve().parents[2] / "skills" / "capabilities"
    complete = True  # did we get a usable is_empty() from EVERY requested capability?
    for name in caps:
        abstract_path = skills_root / name / "scripts" / "abstract.py"
        if not abstract_path.exists():
            complete = False
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                f"capevolve_cap_{name}_isempty", abstract_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
            is_empty = getattr(mod, "is_empty", None)
            if is_empty is None:
                complete = False
                continue
            if not is_empty(cand_dir):
                return False  # any non-empty capability => definitely not an empty seed
        except Exception:  # noqa: BLE001 — never break the loop over instructions rendering
            complete = False
            continue
    # No capability reported non-empty. Only claim "empty" if we heard a reliable
    # signal from EVERY capability; otherwise return None so the caller falls back
    # to the reward heuristic rather than over-claiming emptiness.
    return True if complete else None


def _empty_seed_note(current_val: SplitResult, seed_empty: bool | None = None) -> str:
    """Return a guidance block when the capability started from an empty seed.

    ``seed_empty`` is the authoritative signal — computed from the capability's own
    ``is_empty()`` on the current best candidate (see ``_capability_is_empty``). When it
    is provided we trust it directly. Only when it is ``None`` (the abstract has no
    ``is_empty``, or the caller could not compute it) do we fall back to the reward
    heuristic: reward ≈ 0 with every task failing. That fallback is deliberately NOT
    used when we have the real signal, because a genuinely hard benchmark whose real
    (non-empty) seed scores 0 at baseline would otherwise be wrongly told the directory
    is empty and to "create from scratch".
    """
    if seed_empty is False:
        return ""
    if seed_empty is None:
        # No authoritative signal — fall back to the reward heuristic.
        if current_val.reward > 1e-9:
            return ""
        per = current_val.per_task
        if not per:
            return ""
        eps = 1e-9
        if any((pt.get("reward", 0) or 0) > eps for pt in per):
            return ""
    return (
        "## EMPTY SEED — create the capability from scratch\n"
        "The capability directory is EMPTY (no pre-existing content). This is the first "
        "iteration starting from a blank slate. Your job is to CREATE the initial capability "
        "content — not edit existing files (there are none). Analyze the failing trajectories "
        "in `./trajectories/` to understand what the agent needs, then create the capability "
        "files from scratch (e.g. SKILL.md, prompt.txt, tools.json, policy.md — whatever the "
        "capability type requires). Read `./guidance/<cap>/SKILL.md` for the expected file "
        "format and structure. A good initial capability addresses the most common failure "
        "patterns visible in the trajectories.\n"
    )


def _focus_instructions(current_val: SplitResult, focus_ids, label: str,
                        capabilities=None, algorithm: str = "hill-climb",
                        instructions_file=None, bench_repo: str | None = None,
                        optimizer_name: str | None = None,
                        seed_empty: bool | None = None,
                        target_reader: str = "") -> str:
    """Render one iteration's INSTRUCTIONS by substituting dynamic blocks into the
    optimizer-instructions template.

    The static framing (analyze → ideate → edit, the read-pointers, the code-bearing
    tools guidance, the economy footer) lives in the template file — authored by the
    intake phase per benchmark, with a generic default shipped in ``templates/``. Only
    the per-iteration data (the focus summary, the failure index, the capability/algorithm
    briefs, the benchmark-repo pointer) is computed here and substituted.

    ``focus_ids`` must name tasks that are IN ``current_val`` — it narrows that result,
    it cannot add to it. Callers passing ids from a different split (SkillOpt handed
    train minibatch ids against a val result, and splits are disjoint by construction)
    would otherwise filter the failure index down to nothing and get a confident
    "0 failing of 0 tasks" prompt. On zero overlap we do NOT filter, and we say so.
    """
    per = current_val.per_task
    scoped = True
    if focus_ids is not None:
        known = {pt.get("task_id") for pt in per}
        if set(focus_ids) & known:
            per = [pt for pt in per if pt.get("task_id") in set(focus_ids)]
        else:
            scoped = False  # disjoint id sets: filtering would empty the failure index
    errored, always_fail, flaky, solid = _classify(per)
    n = len(per)

    focus_summary = (
        f"Focus: {label}. Current val reward {current_val.reward:.3f}: "
        f"{len(solid)} solid / {len(flaky)} flaky / {len(always_fail)} failing"
        + (f" / {len(errored)} infra-errored" if errored else "") + f" of {n} tasks."
        + ("" if scoped else
           " (The failure index below covers ALL scored tasks: this step's focus ids "
           "are from a different split than the scored result, so there is no per-focus "
           "breakdown — fix the shared root cause, which is what generalizes anyway.)")
    )
    failures = _failures_block(always_fail, flaky, errored)
    passing = _passing_block(solid)
    cap = _capability_brief(capabilities)
    algo = _algorithm_brief(current_val, algorithm)
    bench = (f"- The benchmark / runner source is at `{bench_repo}` — read-only context "
             "you may consult to understand tools, scoring, or task structure."
             if bench_repo else "")

    parallel_note = _parallel_note(_optimizer_parallel(optimizer_name), optimizer_name)
    empty_note = _empty_seed_note(current_val, seed_empty=seed_empty)
    repl = {
        "{{FOCUS_SUMMARY}}": focus_summary,
        "{{FAILURES}}": failures,
        "{{PASSING}}": passing,
        "{{CAP_BRIEF}}": cap,
        "{{ALGO_BRIEF}}": algo,
        "{{BENCH_REPO}}": bench,
        "{{PARALLEL_NOTE}}": parallel_note,
        "{{EMPTY_SEED}}": empty_note,
        "{{TARGET_READER}}": target_reader,
    }

    tmpl_path = Path(instructions_file) if instructions_file else _DEFAULT_INSTRUCTIONS_TEMPLATE
    tmpl = None
    try:
        if tmpl_path.exists():
            tmpl = tmpl_path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        tmpl = None
    if tmpl and "{{FOCUS_SUMMARY}}" in tmpl:
        for k, v in repl.items():
            tmpl = tmpl.replace(k, v)
        return tmpl

    # Fallback (template unreadable): assemble a minimal but complete prompt so a run
    # never breaks just because the template file is missing.
    parts = [
        "# Optimize the capability — analyze this step's trajectories in ./trajectories/, "
        "then fix MANY root causes in this ONE candidate and STOP.",
        target_reader,
        focus_summary, "",
        empty_note,
        "FIRST read ./guidance/<cap>/SKILL.md for EVERY capability and "
        "./guidance/optimizer/<name>.md (your subagent/parallelism features) IN FULL "
        "before diagnosing. Then read ./trajectories/ (full traces), ./guidance/sources/ "
        "(data models/types — read before writing tool code), ./INSIGHTS.md (durable "
        "priors — hypotheses, not truth), ./LEDGER.md (facts), the "
        "whole ./JOURNAL.md (handover) and ./RUNMAP.md + ./prior_iterations/; fill "
        "./PROCESS.md and APPEND your entry to ./JOURNAL.md. "
        "The prompt and the tools are equally fair game.",
        bench, "", failures, passing, cap, "", algo, "",
        "Address EVERY failure cluster you found, not just the biggest. The DEFAULT fix "
        "for a violated rule/precondition/formula is to move it INTO THE CODE BODY of the "
        "EXISTING tool it governs — an in-body validation/normalization that raises an "
        "ACTIONABLE error — NOT a docstring or prompt restatement. Editing the CODE of "
        "MANY existing tools is the expected shape of a strong iteration; adding one new "
        "tool while leaving rules as prose is the failure mode to avoid. Prose/docstring "
        "edits are reserved for genuine KNOWLEDGE gaps (a format/criterion the agent "
        "cannot derive); rule VIOLATIONS go in code. A strong iteration also ships, where "
        "useful: validation/workflow/composite tools for behavioral clusters, enriched "
        "tool returns + actionable error messages, corrected handlers, and new tools. "
        "Non-regression is a design constraint on each INDIVIDUAL fix (scope each guard "
        "so it doesn't alter a passing task's code path), NOT a reason to make fewer "
        "fixes. If you edited the BODY of fewer than ~3 EXISTING tools or converted fewer "
        "than half the rule-violations you found into in-code checks, you under-used the "
        "iteration — new tools and docstring edits do NOT count toward that bar. The "
        "measure is how MANY real clusters you fix in-code, not how much you spend.",
    ]
    return "\n".join(p for p in parts if p is not None)
