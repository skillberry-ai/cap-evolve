"""Durable synthesized priors — INSIGHTS.md (#128).

Split out of ``harness.py`` (#115). "What was accepted / what was rejected / what is
still open", re-derived from the run record every iteration and bounded so it survives
context loss without eating the prompt budget. Its only caller is
``handover._augment_instructions``; keeping it here makes the bound (``MAX_INSIGHT_CHARS``
and the ``+N more`` truncation markers) reviewable in one place.
"""

from __future__ import annotations

from pathlib import Path

from .capdiff import _candidate_task_impact, _parent_map, _per_task_rewards
from .rundir import RunDir, _atomic_write, iteration_candidate

# ---- durable synthesized insight (issue #128) -----------------------------

# Bounds on the priors block. It is re-synthesized from ``events.jsonl`` + persisted
# rollouts every iteration, so it does NOT grow monotonically with the run — but the
# INPUT does, and an unbounded render would silently eat the prompt budget
# (``optimizer_context.MAX_INSTRUCTIONS_CHARS``) over a 100-iteration run.
#
# Eviction policy differs PER SECTION, because the two sections rank for different things:
#   * REJECTED rows — by |Δ| on val. Every row here is damage or noise, and |Δ| IS the
#     damage: a −0.20 regression is the prior worth re-testing, a −0.001 reject is not.
#   * ACCEPTED rows — by RECENCY. Every row here already cleared the gate, so |Δ| only
#     re-ranks winners, and it evicts the systematically-small-but-real effect FOREVER:
#     six +0.30 accepts permanently crowd out a reproducible +0.02 and the optimizer never
#     learns that direction works. What makes an accept a useful prior is whether the
#     direction GENERALIZES, which |Δ| does not measure — so rotate coverage instead of
#     freezing a top-6 (review of #219, non-blocking 8).
# Ties break toward the newer iteration. The char cap is the backstop for pathologically
# long task ids / reject reasons; it RESERVES the truncation notice's length (below).
_INSIGHT_KEEP = 6          # accepted / rejected rows each


_INSIGHT_OPEN = 10         # still-failing task ids


_INSIGHT_TASKS = 8         # task ids per broke/fixed set (a "+N more" marker follows)


MAX_INSIGHT_CHARS = 4_000  # ≈1k tokens, ~6% of MAX_INSTRUCTIONS_CHARS


_INSIGHT_TRUNC = ("\n\n... (priors truncated to stay inside the optimizer prompt budget; "
                  "the full record is LEDGER.md)\n")


_REASON_MAX = 200


def _insight_reason(raw) -> str:
    """One flat, bounded line for a gate reason rendered inside the priors block.

    Every ``reason`` written today is framework-authored (``gate.decide`` f-strings over
    floats, plus the no-regression suffix over adapter task ids), so there is no live
    injection. But nothing in the type constrains it, and the priors block is a
    FRAMEWORK-AUTHORED region of the prompt: a reason containing a newline plus
    ``## What HELPED`` would render a forged section inside it — precisely the
    misdirection this block exists to prevent. So: collapse all whitespace (no reason can
    start a new line, hence no heading and no list item), backslash-escape the two
    structural markdown characters that still matter mid-line (``#`` and a backtick, which
    could otherwise open an unbalanced code span), and bound the length so one reason
    cannot eat the block's char budget — which is also what made the cap overflow
    (review of #219, non-blocking 4).
    """
    text = " ".join(str(raw or "").split())    # collapses \n, \r, \t and runs of spaces
    text = text.replace("#", "\\#").replace("`", "\\`")
    return text[:_REASON_MAX - 1] + "…" if len(text) > _REASON_MAX else text


def _insight_rows(run_dir: RunDir) -> tuple[list[dict], list[dict]]:
    """Split every evaluated iteration into (accepted, rejected) and evict per section.

    Reads ``RunDir.iteration_events()`` — NOT ``kind == "step"``, which omits GEPA's
    ``gepa_val_gate`` entirely and is the exact bug #199 fixed. Δ is the val delta vs the
    candidate's parent, taken from the event when both sides are present (``None`` when
    either side is missing, so an UNKNOWN Δ is never rendered as a measured ``+0.000``);
    the per-task broke/fixed lists come from the persisted rollouts via
    ``_candidate_task_impact`` — the same read ``_build_ledger`` uses, so the two
    artifacts read the same SOURCE. Their RENDERING still differs (this block truncates
    task lists at ``_INSIGHT_TASKS`` and rows at ``_INSIGHT_KEEP``, and says so).

    Eviction is per-section: accepted rows keep the most RECENT, rejected rows keep the
    largest |Δ|. See the policy note above ``_INSIGHT_KEEP``.
    """
    parent_of = _parent_map(run_dir)
    accepted: list[dict] = []
    rejected: list[dict] = []
    for i, rec in enumerate(run_dir.iteration_events(), 1):
        cid = iteration_candidate(rec)
        if not cid:
            continue
        val, pval = rec.get("val"), rec.get("parent_val")
        delta = (float(val) - float(pval)
                 if isinstance(val, (int, float)) and isinstance(pval, (int, float))
                 else None)
        imp = _candidate_task_impact(run_dir, cid, "val", parent_of=parent_of) or {}
        row = {"iter": i, "cid": cid, "delta": delta,
               "accept": bool(rec.get("accept")),
               "reason": _insight_reason(rec.get("reason")),
               "broke": [str(t) for t in (imp.get("broke") or [])],
               "fixed": [str(t) for t in (imp.get("fixed") or [])]}
        (accepted if row["accept"] else rejected).append(row)
    # A missing Δ sorts LAST among rejects (it carries no damage signal) but must not be
    # confused with a measured 0.0 in the rendering — see ``_delta_str``.
    by_damage = lambda r: (abs(r["delta"]) if r["delta"] is not None else -1.0, r["iter"])  # noqa: E731
    return (sorted(accepted, key=lambda r: r["iter"], reverse=True)[:_INSIGHT_KEEP],
            sorted(rejected, key=by_damage, reverse=True)[:_INSIGHT_KEEP])


def _build_insights(workdir: Path, run_dir: RunDir, *,
                    max_chars: int = MAX_INSIGHT_CHARS) -> str:
    """Write the durable synthesized priors block (INSIGHTS.md) and return it.

    "What was accepted / what was rejected / what's still open", distilled from the
    objective record: the gate outcome + val Δ of every prior iteration, the exact tasks
    each one broke or fixed, and the tasks the current best still fails. Written to BOTH
    the run dir (the durable copy, which is what survives across iterations) and the
    optimizer's workdir (the copy that reaches the prompt). The dashboard does NOT read
    it — ``dashboard._DIFF_SKIP`` deliberately EXCLUDES it, because it is framework read
    context, not a capability edit.

    **Zero LLM calls.** The synthesis is pure Python over ``events.jsonl`` + persisted
    rollouts, like every other auxiliary step in core (reflection distillation, the
    ledger, the runmap, failure clustering). Distilling this with a model would add a
    per-iteration model call to every run for a signal that is already fully determined
    by the run's own numbers — see the ``aux_model`` tier (#132) if a future version
    wants prose instead of rows.

    Honesty: every line is labelled a CANDIDATE PRIOR, not truth. Nothing here bypasses
    the val gate — a prior that says "X helped" is a hypothesis to re-test, and the block
    says so. Only val rewards and val/train task ids are read; the sealed test split is
    never touched (``_per_task_rewards`` is called with ``split="val"`` only).
    """
    accepted, rejected = _insight_rows(run_dir)
    best = run_dir.best_id or "seed"
    best_rewards = _per_task_rewards(run_dir, best, "val")
    still_open = sorted(t for t, r in best_rewards.items() if r < 1.0 - 1e-9)

    def _tasks(label: str, ids: list[str]) -> str:
        """A bounded task-id set with an HONEST "+N more" marker.

        LEDGER.md renders up to 20 ids; this block renders ``_INSIGHT_TASKS``. Silently
        cutting at 8 made an edit that broke 20 tasks read as breaking 8, so an optimizer
        reading only this block UNDER-WEIGHTED a catastrophic regression with nothing in
        the text saying the list was partial (review of #219, blocking 3)."""
        if not ids:
            return ""
        shown = ", ".join(ids[:_INSIGHT_TASKS])
        extra = len(ids) - _INSIGHT_TASKS
        return f" — {label} {{{shown}{f', +{extra} more' if extra > 0 else ''}}}"

    def _delta_str(d) -> str:
        # ``None`` = one side of the comparison was not recorded. Rendering that as
        # "+0.000" would be indistinguishable from a measured zero.
        return "Δ ?" if d is None else f"Δ {d:+.3f}"

    lines = ["# INSIGHTS — durable priors carried across iterations (framework-synthesized)",
             "",
             "A compact, continually-updated summary of what this run has LEARNED SO FAR, "
             "re-derived from the objective record every iteration so it survives even when "
             "the transcript does not. Read it BEFORE proposing.",
             "",
             "**These are CANDIDATE PRIORS, not truth.** Each one is a hypothesis worth "
             "re-testing, and every edit you make is still judged by the val significance "
             "gate — a prior can be wrong, and acting on one earns no exemption.",
             "",
             f"Bounded on purpose: at most {_INSIGHT_KEEP} rows per section and "
             f"{_INSIGHT_TASKS} task ids per set, with a `+N more` count when there are "
             "more. `LEDGER.md` is the full, untruncated record — read it whenever a count "
             "here is marked partial.",
             "", "## What was ACCEPTED by the gate (most recent first)"]
    lines += ([f"- iter {r['iter']} `{r['cid']}` val {_delta_str(r['delta'])}"
               f"{_tasks('fixed', r['fixed'])}{_tasks('but broke', r['broke'])}"
               for r in accepted]
              or ["- _nothing accepted yet — this is still the baseline._"])
    # NOT "What HURT": a candidate rejected by the SIGNIFICANCE bar can have a POSITIVE Δ
    # and have broken nothing — it was merely indistinguishable from noise. Filing that
    # under "HURT" tells the optimizer to avoid a direction that may well be right.
    lines += ["", "## What was REJECTED by the gate (largest movers first — a reject is "
              "not necessarily a regression; read the reason)"]
    lines += ([f"- iter {r['iter']} `{r['cid']}` val {_delta_str(r['delta'])} "
               f"({r['reason']}){_tasks('broke', r['broke'])}"
               # Rejects' `fixed` set matters as much as `broke`: "broke t1 WHILE fixing
               # t2" is what tells you whether the direction is salvageable. Omitting it
               # systematically under-reported what rejected edits achieved.
               f"{_tasks('while fixing', r['fixed'])}"
               for r in rejected]
              or ["- _nothing rejected yet._"])
    lines += ["", f"## Still OPEN — tasks the current best (`{best}`) does NOT pass",
              "",
              "**These names are a DIAGNOSTIC of where the capability is weak, not a "
              "target list.** Fix the general defect they expose; your edit must generalize "
              "beyond them. The gate runs on val, so a task-specific special case for these "
              "ids will pass the gate and FAIL the sealed test — that is a val overfit, not "
              "progress.", ""]
    if still_open:
        lines += [f"{len(still_open)} of {len(best_rewards)} val tasks still failing: "
                  + ", ".join(f"`{t}`" for t in still_open[:_INSIGHT_OPEN])
                  + (f" (+{len(still_open) - _INSIGHT_OPEN} more)"
                     if len(still_open) > _INSIGHT_OPEN else "")]
    elif best_rewards:
        lines += [f"- _none — `{best}` passes all {len(best_rewards)} scored val tasks._"]
    else:
        # Distinguish "perfect" from "no rollouts on disk". Rendering both as "nothing
        # failing" told the optimizer there was nothing left to fix on a run where
        # rollout persistence had failed.
        lines += [f"- _UNKNOWN: no persisted val rollouts for `{best}`, so this section "
                  "could not be computed. Do NOT read this as 'everything passes'._"]
    text = "\n".join(lines) + "\n"
    if len(text) > max_chars:
        # RESERVE the notice's length before cutting, or the "bounded" output overshoots
        # ``max_chars`` by exactly len(notice) (review of #219, blocking 2). A cap too
        # small to hold even the notice is degenerate — hard-cut and stay inside the bound
        # rather than emit a notice that itself breaks it.
        room = max_chars - len(_INSIGHT_TRUNC)
        text = (text[:room].rstrip() + _INSIGHT_TRUNC) if room > 0 else text[:max_chars]
        text = text[:max_chars]   # rstrip can only shorten, so this is the hard backstop
    _atomic_write(run_dir.root / "INSIGHTS.md", text)          # durable copy
    _atomic_write(workdir / "INSIGHTS.md", text)               # the copy that reaches the prompt
    return text
