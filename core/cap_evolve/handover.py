"""The cross-iteration handover system: LEDGER / JOURNAL / PROCESS / RUNMAP (+ INSIGHTS).

Split out of ``harness.py`` (#115) — this was the single largest concern tangled into
that module (~480 lines). Clean ownership, unchanged by the split:

  - ``LEDGER.md``  — FRAMEWORK-written facts: per-iteration outcome + tasks broke/fixed.
  - ``JOURNAL.md`` — OPTIMIZER-authored, append-only across the whole run (marker-guarded,
    reconciled after each step so an optimizer that edited above the line cannot silently
    rewrite history).
  - ``PROCESS.md`` — OPTIMIZER-authored explainability, fresh each iteration, snapshotted.
  - ``RUNMAP.md`` + ``prior_iterations/`` — framework manifest plus real copies of every
    prior iteration's PROCESS.md and capability diff.
  - ``INSIGHTS.md`` (``insights.py``) and the #129 dead-end constraints, both assembled in.

``_augment_instructions`` is the ONE function whose output reaches the optimizer prompt,
and all three algorithms route through it — so a new cross-iteration channel belongs
here, never in a per-algorithm block.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from . import optimizer_context as _oc
from .capdiff import _candidate_task_impact, _diff_capabilities, _parent_map
from .insights import _build_insights
from .rundir import RunDir, iteration_candidate

# The optimizer's working dir carries FIVE cross-iteration files, with clean ownership
# so there is never confusion about who writes what (the recurring user complaint about
# the old MEMORY.md/STATE.md pair):
#   LEDGER.md   — FRAMEWORK-owned, FACTUAL, regenerated each iter (the objective record:
#                 per-iteration outcomes + the exact tasks each candidate broke/fixed).
#   JOURNAL.md  — OPTIMIZER-owned, JUDGMENT, append-only across the WHOLE run (what was
#                 tried, what worked, what regressed, refuted hypotheses, focus-next).
#   PROCESS.md  — OPTIMIZER-owned, EXPLAINABILITY, fresh each iter, snapshotted with the
#                 candidate (how this iteration was done: ranked issues, edits, verify,
#                 subagents/features used, what to preserve).
#   RUNMAP.md   — FRAMEWORK-owned manifest of every prior iteration's working dir, with
#                 each prior PROCESS.md + capability diff copied into ./prior_iterations/.
#   INSIGHTS.md — FRAMEWORK-owned, SYNTHESIZED, re-derived each iter (#128): the compact
#                 durable priors — what helped, what hurt, what's still open. Bounded, so
#                 it survives context loss without eating the prompt budget.
# Rule: FACTS are deterministic + framework-owned; JUDGMENT and PROCESS are agent-owned.
# INSIGHTS is framework-owned and deterministic too — it is a *distillation* of the facts,
# labelled as hypotheses so a wrong prior can never masquerade as truth.

_JOURNAL_MARK = "<!-- cap-evolve:journal-append-below — add your Iteration entry under this line; do not edit anything above it -->"


_JOURNAL_SEED = (
    "# JOURNAL — optimizer handover (append-only, whole run)\n\n"
    "YOU (the optimizer) own this file. It is the running, accumulating handover across "
    "ALL iterations — accepted AND rejected — and it is NEVER reset. Each iteration you "
    "APPEND one new entry at the bottom (under the marker line); you do NOT edit or "
    "delete earlier entries. Read the whole journal before proposing, so you build on "
    "EVERY prior attempt (not just the last accepted one) and never re-test a refuted "
    "idea.\n\n"
    "You CANNOT know your own gate result while you write — the harness scores you AFTER "
    "you stop and stamps a **RESULT** line (outcome + Δ + the EXACT tasks you broke/fixed) "
    "right below your entry. So do NOT write 'what worked' as a guess. To learn what "
    "actually worked, READ the framework RESULT lines of prior entries (and LEDGER.md): an "
    "entry whose RESULT says `rejected` with `broke={...}` tells you which specific edits to "
    "drop or redesign — its diff.patch is in ./prior_iterations/<id>/.\n\n"
    "Append your entry for THIS iteration below the marker, using this shape (INTENT only — "
    "the framework appends the RESULT):\n\n"
    "    ## Iteration <your candidate id> — <one-line headline of what you tried>\n"
    "    - Changes I made (1 line per edit; name the file/tool + cluster it targets):\n"
    "    - Per change, the EXPECTED effect + why it's safe (which failing task it should fix;\n"
    "      why no passing task changes behavior):\n"
    "    - Building on prior RESULTS: which prior entries' broke/fixed I used, and what I\n"
    "      did NOT re-try because a prior RESULT showed it regressed (cite ids):\n"
    "    - Refuted hypotheses (a prior RESULT proved this is NOT the fix — never re-test):\n"
    "    - High-value clusters still NOT cracked (and the guard/tool designs already tried):\n"
    "    - Plateau signal (are the last few RESULTs flat/negative? if so, which LEVER to switch\n"
    "      to — e.g. a NEW composite tool instead of another guard, or prompt instead of code):\n"
    "    - Focus next iteration:\n"
)


_PROCESS_SEED = (
    "# PROCESS — what I did this iteration (explainability; REQUIRED)\n\n"
    "Fill this in as you work. It is the human-readable record of HOW this iteration was "
    "done and is snapshotted with the candidate, so anyone — and the next iteration via "
    "./prior_iterations/ — can see your reasoning. Be concrete.\n\n"
    "## Ranked issue list (clusters by # failing tasks × trials, biggest first)\n"
    "| rank | cluster | tasks | shared root cause | tag (KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP) | planned change class |\n"
    "| --- | --- | --- | --- | --- | --- |\n\n"
    "## Changes made this iteration (one row per edit — aim for MULTIPLE classes, incl. a NEW tool when a cluster needs one)\n"
    "| cluster | edit class | file / tool | what & why it generalizes | protects passing? |\n"
    "| --- | --- | --- | --- | --- |\n\n"
    "## Verify-the-fix (one line per change: the trace it targets → what the guard/computation/new-tool now does on those exact inputs)\n"
    "- \n\n"
    "## Process & features used\n"
    "- Subagents / worktrees / parallel features used (or: \"serial fallback because …\"):\n"
    "- Prior iterations I read from ./prior_iterations/ + ./RUNMAP.md (which, and what I learned):\n\n"
    "## Good things to PRESERVE (do not let a future iteration undo these)\n"
    "- \n\n"
    "## Deliberately skipped (cluster + why — already-passing / needs gold / infra noise)\n"
    "- \n"
)


def _journal_tail(workdir: Path) -> str:
    """The optimizer-authored text APPENDED below the journal marker this iteration.

    The harness seeds ``workdir/JOURNAL.md`` with the accumulated run journal ending in
    ``_JOURNAL_MARK``; the optimizer appends its new ``## Iteration …`` entry below it.
    This returns just that appended tail (trimmed), or "" when nothing was appended."""
    path = workdir / "JOURNAL.md"
    try:
        if not path.exists():
            return ""
        text = path.read_text(encoding="utf-8")
    except Exception:  # noqa: BLE001
        return ""
    if _JOURNAL_MARK in text:
        # Everything after the FIRST marker is the optimizer's new entry. Split on the
        # FIRST (not last) marker so a stray duplicate marker the optimizer may paste
        # inside its own entry doesn't truncate the entry to "".
        tail = text.split(_JOURNAL_MARK, 1)[1].strip()
    else:
        # Optimizer rewrote the file (no marker) — fall back to its last ## Iteration block.
        idx = text.rfind("\n## ")
        tail = text[idx:].strip() if idx != -1 else ""
    # Strip any marker the optimizer copied into its entry text.
    return tail.replace(_JOURNAL_MARK, "").strip()


def _build_ledger(workdir: Path, run_dir: RunDir) -> None:
    """Write the FACTUAL, framework-owned LEDGER.md: one row per prior iteration with
    its outcome + the exact tasks it broke/fixed. Deterministic — the objective record;
    the optimizer's own narrative lives in JOURNAL.md."""
    parent_of = _parent_map(run_dir)
    # Outcome per candidate from EVERY iteration event kind (accept/reject + val +
    # parent) — see RunDir.iteration_events; "step" alone omits GEPA entirely.
    rows = run_dir.iteration_events()

    table = ["| iter | candidate | parent | outcome | val | Δ vs parent | broke (were passing) | fixed |",
             "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for i, rec in enumerate(rows, 1):
        cid = str(iteration_candidate(rec))
        par = str(rec.get("parent") or rec.get("parent_id") or "seed")
        outcome = "ACCEPT" if rec.get("accept") else "reject"
        val = rec.get("val")
        pval = rec.get("parent_val")
        d = (f"{val - pval:+.3f}" if isinstance(val, (int, float))
             and isinstance(pval, (int, float)) else "")
        imp = _candidate_task_impact(run_dir, cid, "val", parent_of=parent_of) or {}

        def _set(ids) -> str:
            # Honest truncation: a silent cut makes a 40-task regression read as 20.
            ids = [str(t) for t in (ids or [])]
            extra = len(ids) - 20
            return ("{" + ", ".join(ids[:20])
                    + (f", +{extra} more" if extra > 0 else "") + "}")

        broke, fixed = _set(imp.get("broke")), _set(imp.get("fixed"))
        vstr = f"{val:.3f}" if isinstance(val, (int, float)) else ""
        table.append(f"| {i} | {cid} | {par} | {outcome} | {vstr} | {d} | {broke} | {fixed} |")
    if len(table) == 2:
        table.append("| — | (baseline only) | — | — | — | — | {} | {} |")

    best = run_dir.best_id or "seed"
    text = (
        "# LEDGER — factual run record (framework-maintained; READ-ONLY)\n\n"
        "The objective record of every iteration: which candidate, its parent, whether the "
        "gate ACCEPTED it, the val reward + Δ, and the EXACT tasks it broke / fixed. Facts "
        "only — your own narrative, lessons, and refuted hypotheses go in JOURNAL.md. Use "
        "this to never re-introduce a change that broke a task, and to see which approaches "
        "the gate accepted vs rejected.\n\n"
        "## Iterations\n" + "\n".join(table) + "\n\n"
        f"## Current best: {best}\n"
    )
    (workdir / "LEDGER.md").write_text(text, encoding="utf-8")


def _seed_journal(workdir: Path, run_dir: RunDir) -> None:
    """Copy the run-level append-only JOURNAL into the workdir (or seed it on iter 1).

    The run-level JOURNAL at ``run_dir.root/JOURNAL.md`` accumulates across ALL
    iterations (accepted and rejected). We copy it into the workdir so the optimizer
    reads the full handover history; it appends its new entry below ``_JOURNAL_MARK``,
    and ``_reconcile_journal`` folds that back into the run-level file after the step."""
    run_journal = run_dir.root / "JOURNAL.md"
    if run_journal.exists():
        try:
            text = run_journal.read_text(encoding="utf-8")
        except Exception:  # noqa: BLE001
            text = _JOURNAL_SEED
    else:
        text = _JOURNAL_SEED
    # The run-level file holds ONLY accumulated entries (no marker). Append the marker
    # transiently here so the optimizer appends its new entry below it; the marker is
    # stripped again when we fold the entry back into the run-level file.
    text = text.replace(_JOURNAL_MARK, "").rstrip()
    text = text + "\n\n" + _JOURNAL_MARK + "\n"
    (workdir / "JOURNAL.md").write_text(text, encoding="utf-8")


def _reconcile_journal(workdir: Path, run_dir: RunDir, cid: str, *,
                       accepted: bool, val: float, delta: float) -> None:
    """Fold the optimizer's newly-appended journal entry into the run-level JOURNAL,
    stamped with the framework's objective outcome. Append-only at the run level so the
    handover truly accumulates across accepted AND rejected iterations."""
    tail = _journal_tail(workdir)
    run_journal = run_dir.root / "JOURNAL.md"
    base = run_journal.read_text(encoding="utf-8") if run_journal.exists() else _JOURNAL_SEED
    # Run-level file is pure accumulated entries — strip any marker before appending.
    base = base.replace(_JOURNAL_MARK, "").rstrip()
    # Framework-owned RESULT: the objective gate outcome + the EXACT tasks this candidate
    # broke/fixed (vs its parent), folded VISIBLY into the journal so the next iteration
    # learns what actually worked/regressed from the narrative — not just a terse comment.
    impact = _candidate_task_impact(run_dir, cid, "val") or {}
    broke = ", ".join(str(t) for t in (impact.get("broke") or [])[:30]) or "—"
    fixed = ", ".join(str(t) for t in (impact.get("fixed") or [])[:30]) or "—"
    verdict = "ACCEPTED (new champion)" if accepted else "REJECTED (champion unchanged)"
    guidance = ("" if accepted else
                " — its WHOLE batch was reverted; re-introduce only the edits that did NOT "
                "break a task above, dropping/redesigning the ones that did.")
    stamp = (f"\n\n> **RESULT (framework, objective):** {verdict} · val={val:.3f} "
             f"Δ={delta:+.3f} · fixed={{{fixed}}} · broke={{{broke}}}.{guidance}\n"
             f"<!-- {cid}: {'ACCEPTED' if accepted else 'rejected'} "
             f"val={val:.3f} Δ={delta:+.3f} -->")
    tail = tail.strip()
    # Dedup guard: if the optimizer dropped the marker without appending (so the tail
    # fallback returned an entry already recorded in the run-level journal), do NOT
    # re-append it — that would duplicate a prior iteration's entry under this cid.
    if not tail or (tail and tail in base):
        tail = f"## Iteration {cid} — (no handover written by the optimizer)"
    new = base + "\n\n" + tail + stamp + "\n"
    try:
        run_journal.write_text(new, encoding="utf-8")
    except Exception as e:  # noqa: BLE001
        run_dir.log_event("optimizer_context_warning", what="JOURNAL.md", error=str(e)[:300])


def _build_runmap(workdir: Path, run_dir: RunDir) -> None:
    """Write RUNMAP.md + copy every prior iteration's PROCESS.md + capability diff into
    ``workdir/prior_iterations/<cid>/`` so the optimizer has REAL in-dir access to all
    prior iterations' working dirs (not just the parent's trajectories)."""
    parent_of = _parent_map(run_dir)
    # Every iteration event kind, not just "step" — GEPA emits "gepa_val_gate".
    rows = run_dir.iteration_events()

    prior_root = workdir / "prior_iterations"
    table = ["| iter | candidate | parent | outcome | val | ./prior_iterations/<id>/ |",
             "| --- | --- | --- | --- | --- | --- |"]
    for i, rec in enumerate(rows, 1):
        cid = str(iteration_candidate(rec))
        par = str(rec.get("parent") or rec.get("parent_id") or "seed")
        outcome = "ACCEPT" if rec.get("accept") else "reject"
        val = rec.get("val")
        vstr = f"{val:.3f}" if isinstance(val, (int, float)) else ""
        # Copy this prior iteration's PROCESS.md + diff-vs-parent into the workdir.
        dst = prior_root / cid
        try:
            dst.mkdir(parents=True, exist_ok=True)
            proc = run_dir.candidate_dir(cid) / "PROCESS.md"
            if proc.is_file():
                shutil.copyfile(proc, dst / "PROCESS.md")
            diff = _diff_capabilities(run_dir.candidate_dir(par), run_dir.candidate_dir(cid))
            if diff.strip():
                (dst / "diff.patch").write_text(diff, encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            run_dir.log_event("optimizer_context_warning",
                              what=f"prior_iterations/{cid}", error=str(e)[:300])
        present = [n for n in ("PROCESS.md", "diff.patch") if (dst / n).exists()]
        have = " + ".join(present) if present else "(none)"
        table.append(f"| {i} | {cid} | {par} | {outcome} | {vstr} | {have} |")
    if len(table) == 2:
        table.append("| — | (no prior iterations yet) | — | — | — | — |")

    text = (
        "# RUNMAP — every prior iteration's working dir (read these before proposing)\n\n"
        "For each prior iteration, its artifacts are copied into "
        "`./prior_iterations/<candidate>/`:\n"
        "- `PROCESS.md` — what that iteration did (ranked issues, changes, verify-the-fix, process)\n"
        "- `diff.patch` — the EXACT capability edit it made vs its parent\n\n"
        f"The live run dir (read-only) is at `{run_dir.root}` if you need "
        "`rollouts/<split>/` traces or the git log.\n\n"
        + "\n".join(table) + "\n\n"
        "Before proposing, read the PROCESS.md + diff.patch of the prior iterations that "
        "targeted the SAME cluster you are about to work on — so you BUILD ON them rather "
        "than repeat a rejected or already-tried edit. Cross-reference LEDGER.md for which "
        "of them the gate accepted vs rejected, and JOURNAL.md for the lessons.\n"
    )
    (workdir / "RUNMAP.md").write_text(text, encoding="utf-8")


# ---- rejected-approach constraints (#129) ---------------------------------
#
# Rejected candidates were already persisted to ``rejected.jsonl`` (audit + the
# dashboard's "what not to try" panel) but nothing put them in a proposal prompt, so the
# optimizer could — and did — re-propose an approach the gate had already killed. These
# two functions close that: ``approach_signature`` normalizes WHAT an edit did into a
# stable one-line signature, and ``dead_end_constraints`` renders the deduped
# signature+reason list as a bounded prompt block.
#
# Enforcement is ADVISORY (prompt text), not a hard block: the optimizer is a
# black-box agent CLI, so the framework cannot forbid it from emitting bytes. What IS
# hard is the gate — a re-proposed dead end still gets rejected on val. See RUN.md.

_MAX_DEAD_ENDS = 12        # most-recent distinct approaches injected


_MAX_APPROACH_CHARS = 300  # per-signature budget -> block <8 KB, well under the 60k cap


# Control chars stripped from a signature: it is quoted into a markdown prompt block and
# (once #191's format_event / #220's replay read rejected.jsonl) into a terminal writer.
# Closed here, once, for every present and future consumer rather than per renderer.
# C0 + DEL are the ANSI/escape half; the bidi overrides are the visual-spoofing half — a
# capability file can legitimately contain either, a dedupe key quoted into a prompt cannot.
_CTRL_STRIP = ({c: None for c in range(32)} | {127: None}
               | {c: None for c in range(0x202A, 0x202F)}      # LRE..PDF bidi embedding
               | {c: None for c in range(0x2066, 0x206A)})     # LRI..PDI bidi isolates


def approach_signature(parent_dir: Path, cand_dir: Path, *,
                       max_chars: int = _MAX_APPROACH_CHARS) -> str:
    """A stable, compact signature of WHAT an edit changed — the dedupe key for #129.

    Built from the capability diff (the same ``_diff_capabilities`` source the dashboard
    and RUNMAP use, so it never picks up injected read-context or algorithm scratch):
    per touched file, the added/removed content lines, whitespace-collapsed. Two edits
    that add the same text to the same file produce the same signature regardless of
    candidate id, ordering or indentation — which is exactly the "variation on an
    already-failed approach" the optimizer keeps re-proposing.

    The dedupe key must be a FUNCTION OF THE WHOLE EDIT, so when the readable form
    exceeds ``max_chars`` the overflow is closed with a digest of the full body rather
    than simply cut: a plain head-truncation makes two different edits that share a long
    prefix (any realistic SKILL.md or system prompt) collapse to one signature, and the
    block would then tell the optimizer "re-proposed 2x" about something it never
    proposed — strictly worse than injecting nothing.

    Returns "" when there is no capability diff (e.g. the optimizer errored and the
    workdir is still a verbatim parent copy) — a no-op is not an approach.

    ponytail: re-reads both capability trees (an ``rglob`` + ``read_text`` pass each)
    rather than threading a cached diff through the five rejection call sites. Negligible
    next to the rollouts that just ran, and it costs nothing on an ACCEPT. Upgrade path if
    a repo-sized capability makes it measurable: accept the already-computed
    ``_diff_capabilities`` text as an optional argument.
    """
    # Generous diff budget: the signature's digest must cover the whole edit, and
    # _diff_capabilities' own default (8 KB, for display) would silently cap it.
    diff = _diff_capabilities(parent_dir, cand_dir, max_chars=200_000)
    parts: list[str] = []
    fname = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            fname = line[6:].strip()
            continue
        if line[:1] not in ("+", "-") or line.startswith(("+++", "---")):
            continue
        body = " ".join(line[1:].split()).translate(_CTRL_STRIP)
        if not body:
            continue
        parts.append(f"{fname}: {line[0]}{body}")
    if not parts:
        return ""
    sig = " | ".join(parts)
    if len(sig) <= max_chars:
        return sig
    # Overflow: keep a readable head, then pin the identity of the WHOLE body with a
    # digest so distinct edits never share a signature (see the docstring).
    digest = hashlib.sha256(sig.encode("utf-8")).hexdigest()[:12]
    tail = f" … [+{len(sig) - max_chars} chars, sha {digest}]"
    return sig[:max_chars - len(tail)] + tail


def dead_end_constraints(run_dir: RunDir, *, limit: int = _MAX_DEAD_ENDS) -> str:
    """The "already tried & rejected (do not repeat)" prompt block, or "" when empty.

    Reads ``rejected.jsonl`` (the live record — #114 kept these writes precisely because
    they have real readers) and dedupes on ``approach``, keeping the FIRST rejection
    reason per approach and counting repeats, so an approach the optimizer has already
    re-proposed twice shows "re-proposed 2x" rather than two rows.

    Bounded three ways so a long run cannot balloon the prompt (#199's
    ``MAX_INSTRUCTIONS_CHARS``): each signature is capped (``_MAX_APPROACH_CHARS``, on
    write AND on read), each reason at 200 chars, and only the ``limit`` MOST RECENT
    distinct approaches are injected. Recency, not relevance: the newest rejections are
    the ones the current lineage is closest to re-proposing, and it needs no scoring
    model. Recency means LAST-seen, not first — a re-proposal requeues its row, so the
    single most predictive entry (the dead end the optimizer just re-emitted) can never be
    the one evicted in favour of an older one-off. ponytail: no LLM summarization — zero
    API cost, and a verbatim diff signature is more actionable than a paraphrase.
    """
    recs = []
    try:
        for line in run_dir.rejected_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        pass  # best-effort: no/partial memory file just means no constraints

    # dedupe by approach, newest-last ordering preserved; count repeats.
    seen: dict[str, dict] = {}
    for rec in recs:
        # Re-cap on READ as well as on write: a record may come from a direct
        # RejectedMemory caller (or an older/edited file) that never went through
        # approach_signature, and an unbounded row would defeat the block's budget.
        approach = (rec.get("approach") or "").strip()[:_MAX_APPROACH_CHARS]
        if not approach:
            continue  # no-op edit or a pre-#129 record: nothing to constrain against
        cid = rec.get("candidate_id") or "?"
        if approach in seen:
            row = seen.pop(approach)  # re-proposed => it IS the most recent; requeue it
            row["count"] += 1
            row["latest"] = cid
            seen[approach] = row
            continue
        seen[approach] = {"approach": approach, "count": 1,
                          "reason": (rec.get("reason") or "gate rejected")[:200],
                          "cid": cid, "latest": cid}
    if not seen:
        return ""
    rows = list(seen.values())[-limit:]

    lines = [
        "## ALREADY TRIED & REJECTED — do not re-propose these (framework, read-only)",
        "",
        f"The gate has rejected {len(seen)} distinct approach(es) on this run"
        + (f" (showing the {len(rows)} most recent)" if len(rows) < len(seen) else "")
        + ". Each row is the EXACT capability edit that failed and why:",
        "",
    ]
    for r in rows:
        # cid = where the approach FIRST died (whose reason is quoted); latest = the most
        # recent repeat, so "re-proposed 3x" cannot be misread as belonging to cid alone.
        rep = (f", re-proposed {r['count']}x (latest {r['latest']})"
               if r["count"] > 1 else "")
        lines.append(f"- **{r['cid']}**{rep} — `{r['approach']}`")
        lines.append(f"  - rejected because: {r['reason']}")
    lines += [
        "",
        "**Constraint:** do NOT propose any of the above again, and do not propose a "
        "cosmetic variation of one (same text, different wording/placement) — it shares "
        "the same hidden assumption and will fail the same way. If you believe a rejected "
        "direction is still right, you MUST state in `PROCESS.md` what is materially "
        "different this time and which specific lesson above it counters. Otherwise pick "
        "a genuinely different hypothesis.",
    ]
    return "\n".join(lines) + "\n"


def _augment_instructions(instructions: str, workdir: Path, run_dir: RunDir,
                          extra: str = "") -> str:
    """Give the optimizer its five cross-iteration files + a prompt pointer to each.

    ``extra`` is an algorithm-level block that must land LAST and must be inside whatever
    cap this function ends with (#129/PR222 makes it ``return cap_instructions(...)``).
    Appending such a block at the call site instead does two bad things: for GEPA it
    escapes the cap entirely, and for every algorithm it puts a *behavioural* instruction
    in the middle of the string, which is the part ``cap_instructions`` elides — so
    truncation would silently drop the one block that changes search behaviour while
    keeping the two that are only context. Passing it here puts it in the preserved tail.
    Used by ``cap_evolve.plateau.prompt_block``.

    Clean ownership (see the file-header comment near ``_JOURNAL_SEED``):
      - LEDGER.md  — framework-written facts (outcomes + per-task broke/fixed);
      - JOURNAL.md — optimizer-authored, append-only handover across the whole run;
      - PROCESS.md — optimizer-authored explainability, fresh each iteration;
      - RUNMAP.md + prior_iterations/ — framework manifest + copies of every prior
        iteration's PROCESS.md and capability diff (real prior-work-dir access).
      - INSIGHTS.md — framework-synthesized durable priors (#128): what helped, what
        hurt, what's still open, bounded and re-derived every iteration.

    Plus the #129 rejected-approach constraint block. This is the ONLY function whose
    output reaches the proposal prompt (#114), and all three algorithms route through it
    — so INSIGHTS and the dead-end constraints land identically for hill-climb, GEPA and
    SkillOpt with no per-algorithm wiring.
    """
    _build_insights(workdir, run_dir)
    _build_ledger(workdir, run_dir)
    _seed_journal(workdir, run_dir)
    if not (workdir / "PROCESS.md").exists():
        (workdir / "PROCESS.md").write_text(_PROCESS_SEED, encoding="utf-8")
    _build_runmap(workdir, run_dir)

    pointer = (
        "## Cross-iteration files in THIS working dir (clean ownership — read all five)\n"
        "- `INSIGHTS.md` — DURABLE PRIORS (framework, read-only): the compact "
        "what-was-accepted / what-was-rejected / what's-still-open summary of the whole run "
        "so far, re-synthesized every iteration so it survives context loss. Read it FIRST "
        "for orientation, then the detail below. Its priors are hypotheses to re-test, not "
        "truth — the val gate still judges every edit. It is BOUNDED and marks its own "
        "truncation (`+N more`); `LEDGER.md` below is the untruncated record.\n"
        "- `LEDGER.md` — FACTS (framework, read-only): every iteration's outcome + the exact "
        "tasks it broke/fixed. Never re-introduce a change that broke a task.\n"
        "- `JOURNAL.md` — HANDOVER (yours, append-only across the whole run): read the whole "
        "thing, then APPEND your entry for this iteration below the marker line. Do NOT edit "
        "earlier entries. This is how you avoid repeating refuted ideas and hitting the same "
        "plateau.\n"
        "- `PROCESS.md` — EXPLAINABILITY (yours, REQUIRED this iteration): fill it in as you "
        "work (ranked issues, every edit + class, verify-the-fix, subagents/features used, "
        "what to preserve, what you skipped). It is snapshotted with your candidate.\n"
        "- `RUNMAP.md` + `./prior_iterations/<id>/` — every prior iteration's PROCESS.md + "
        "capability diff, copied in for you. Read the ones targeting your cluster BEFORE "
        "proposing, so you build on prior work instead of repeating it.\n"
    )
    dead_ends = dead_end_constraints(run_dir)
    tail = f"\n{dead_ends}" if dead_ends else ""
    # ``extra`` is #221's algorithm-level block (the plateau intervention). It must land
    # LAST and INSIDE the cap: appended at the call site it escapes cap_instructions
    # entirely, and appended before the pointer it sits in the middle of the string —
    # exactly the part cap_instructions elides — silently dropping the one *behavioural*
    # block while keeping the context-only ones. Here it is in the preserved tail.
    if extra:
        tail = f"{tail}\n{extra}"
    # Re-cap: render_instructions capped its OWN output, but these blocks are appended
    # after it, so the final assembled prompt needs the ceiling applied once more.
    return _oc.cap_instructions(f"{instructions}\n\n{pointer}{tail}\n")
