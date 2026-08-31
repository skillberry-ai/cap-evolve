"""commit — persist one agent-optimize round's decision through the run dir.

Replaces the old SKILL.md shell heredoc, which was unrunnable: it used a *quoted*
heredoc (``<<'PY'``) so ``$R`` never expanded and ``RunDir.open("$R")`` opened a
literal ``$R``, and it carried bare ``<placeholder>`` tokens that aren't Python.

Does exactly what the deterministic loops do at the end of a step:
  * ``snapshot`` the working copy as a candidate (always — the audit trail should
    show rejects too),
  * ``set_best`` on accept only,
  * ``log_event`` the decision (agent-mode detail the other scripts read), and
  * ``harness.record_iteration`` — the ONE shared iteration step every algorithm
    routes through (#216/#224): charges ``iterations=1`` **and** ``accepted=`` so the
    stall counter that ``budget_exhausted()`` reads actually moves, writes the
    canonical ``step`` record every consumer enumerates, and reconciles the
    run-level ``JOURNAL.md``. Do NOT open-code those three here again.

Runner-side spend (metric_calls / usd / tokens / seconds) is already recorded by the
evaluate phase; ``--optimizer-*`` is for the *proposer's* own cost, which in agent
mode is you and would otherwise never be counted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Imported for its side effect ONLY: seeds sys.path so `cap_evolve` resolves when
# this script is run standalone (`python <this-file>`). Must precede the
# cap_evolve imports below; not "unused" — deleting it breaks standalone runs.
import _bootstrap  # noqa: F401  # side-effect import, see above

from cap_evolve import RunDir, harness


def _round_gate_numbers(run_dir: RunDir, candidate_id: str) -> dict:
    """The gate's NUMBERS for ``candidate_id``, read back from ``round.py``'s own table.

    ``dashboard.reduce_run`` builds the published ``gate_decisions[]`` (read by the dashboard,
    the TUI and CI's live snapshot) by regex-parsing the deterministic gate's reason string
    (``Δ̄ = …, SE=…, n=…, k·SE=…``). An agent writes free prose, so nothing matched and every
    numeric column came back null — on run 32971129203 the deltas and thresholds existed only
    inside sentences like "delta +0.033 within control noise 0.044". This function is why that
    is now avoidable: ``round.py`` persists the whole gate table to ``$R/work/round_i<N>.json``,
    so the numbers are on disk, structured, already.

    ``N`` is ``spent.iterations`` at gate time, and ``record_iteration`` has not charged this
    round yet — so the current count still names this round's table. A same-iteration re-gate
    gets a ``.r<k>`` suffix rather than overwriting; the highest suffix is the operative one,
    because a re-gate is run to supersede the first.

    Returns {} when there is no table (``gate_check``-only rounds never write one, and
    ``round.py``'s write is best-effort) — a missing measurement must stay missing, never
    become a fabricated 0.
    """
    work = run_dir.root / "work"
    stem = f"round_i{int(run_dir.spent.iterations)}"
    # Numeric, not lexical: a plain string sort ranks `.r10` below `.r2`, so the tenth re-gate
    # would lose to the second. Re-gates are rare but a wrong one here is silently wrong.
    def _suffix(p: Path) -> int:
        tail = p.name[len(stem):].removesuffix(".json")
        return int(tail[2:]) if tail.startswith(".r") and tail[2:].isdigit() else 0
    tables = sorted(work.glob(f"{stem}.json")) + sorted(work.glob(f"{stem}.r*.json"),
                                                        key=_suffix)
    if not tables:
        return {}
    try:
        table = json.loads(tables[-1].read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    entry = next((c for c in (table.get("candidates") or [])
                  if c.get("tag") == candidate_id), None)
    if entry is None:
        return {}
    parent = table.get("parent") or {}
    out = {
        "parent_val": parent.get("reward"),
        "gate_stderr": parent.get("stderr"),
        "gate_n": parent.get("n_tasks"),
        "gate_delta": entry.get("gate_delta"),
        "gate_threshold": entry.get("gate_threshold"),
        "gate_mode": (table.get("gated_against") or {}).get("mode"),
        "gate_table": tables[-1].name,
    }
    # The drift-free second opinion, when the round measured one. On run 32971129203 this is
    # the whole finding: cand_1 was rejected against the parent's STORED reward (Δ 0.0333 vs
    # threshold 0.0440) while the control-relative comparison ACCEPTED it (Δ 0.0556 vs 0.0341).
    # Recording only the booked verdict hides that the decision was reference-dependent.
    ctl = entry.get("control_relative") or {}
    if ctl:
        out["control_relative_verdict"] = ctl.get("verdict")
        out["control_relative_delta"] = ctl.get("gate_delta")
    bar = (table.get("evidence_bar") or {}).get("value")
    if bar is not None:
        out["evidence_bar"] = bar
    return {k: v for k, v in out.items() if v is not None}


def _record_memory(run_dir: RunDir, candidate_id: str, *, accepted: bool, reason: str,
                   val: float | None, parent_val: float | None) -> None:
    """File this round in the optimizer memory every OTHER algorithm already writes.

    ``rejected.jsonl`` / ``history.jsonl`` are what ``memory.py`` calls the readers of its two
    audit records: the dashboard's Memory panel (``GET /api/runs/{id}/memory`` and the static
    export) and any optimizer prompt that greps ``rejected.jsonl`` for approaches already
    refuted. The deterministic loops write them inline — ``harness``'s hill-climb, ``gepa``
    (including its merge paths) and ``skillopt`` all call ``.add`` themselves. Agent mode never
    did, so run 33046360451 published ``{"history": [], "rejected": []}``: a whole run of
    rejected approaches that the run itself could not enumerate.

    NOT hoisted into ``harness.record_iteration`` alongside the other three per-iteration
    records, though that is where it belongs by the argument in that docstring: gepa's
    local-gate merge reject (``_try_merge``) files a rejection WITHOUT routing through
    record_iteration, so centralising there would silently drop it, and the deterministic
    callers pass richer, algorithm-specific summaries than record_iteration's arguments can
    reconstruct. Both are fixable; neither is fixable safely in the same change as this.
    """
    from cap_evolve.memory import History, RejectedMemory

    delta = (val - parent_val if isinstance(val, (int, float))
             and isinstance(parent_val, (int, float)) else None)
    bits = [f"candidate {candidate_id}"]
    if isinstance(val, (int, float)):
        bits.append(f"(val {val:.3f}" + (f", Δ {delta:+.3f})" if delta is not None else ")"))
    summary = " ".join(bits)
    try:
        if accepted:
            History(run_dir.history_path).add(candidate_id, summary, float(val or 0.0))
        else:
            RejectedMemory(run_dir.rejected_path).add(candidate_id, summary, reason, val)
    except OSError as e:
        # Memory is an audit record, not the decision. Never lose a booked round over it.
        run_dir.log_event("optimizer_context_warning", what="memory", error=str(e)[:300])


def _prior_decision(run_dir: RunDir, candidate_id: str) -> dict | None:
    """The first decision event already recorded for ``candidate_id``, if any.

    ``inconclusive`` counts: an unresolved round is a booked round, and resolving it needs a
    FRESH tag anyway (re-running a tag REPLACES its rollouts — see ``harness``'s
    ``rollout_overwrite_warning``), so silently re-booking the old one is the same collision
    this guard exists for.

    Reads ``events.jsonl`` (the audit log, not memory) so the guard holds across
    processes — which is the only way it can catch two concurrent drivers, the exact
    failure it exists for.
    """
    try:
        with run_dir.events_path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except Exception:  # noqa: BLE001 — a torn line is not a decision
                    continue
                # NB: log_event writes the event name under "kind", not "event".
                if ev.get("kind") in ("accept", "reject", "inconclusive") and \
                        str(ev.get("candidate")) == str(candidate_id):
                    return {"kind": ev.get("kind"), "t": ev.get("t"),
                            "note": ev.get("note"), "val": ev.get("val")}
    except FileNotFoundError:
        return None
    return None


def _gate_verdict(run_dir: RunDir, candidate_id: str) -> str | None:
    """The verdict ``round.py`` recorded for this candidate, from its persisted table.

    Readable only because ``round.py`` now writes its table to ``work/`` instead of leaving
    stdout the sole copy — before that, ``commit.py`` had no way to know what the gate had said
    and could not tell an agreeing reject from an override.

    Newest table wins: a same-iteration re-gate is written alongside the first (``.r1.json``),
    and the later measurement is the one being booked against.
    """
    work = run_dir.root / "work"
    if not work.is_dir():
        return None
    for log in sorted(work.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not log.is_file() or log.suffix != ".json":
            continue
        try:
            payload = json.loads(log.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — not a round table
            continue
        if not isinstance(payload, dict):
            continue
        for row in payload.get("candidates") or []:
            if isinstance(row, dict) and str(row.get("tag")) == str(candidate_id):
                return row.get("verdict")
    return None


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="commit")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--candidate-id", required=True,
                   help="candidate id == the tag its rollouts were written under")
    p.add_argument("--from-dir", required=True, help="the working copy to snapshot")
    # ``inconclusive`` is the third outcome ``round.py`` can actually return (``verdict_stable:
    # false`` — the verdict flips depending on which byte-identical control replicate is the
    # reference, so the round cannot separate the edit from re-measurement). Without it an
    # unresolvable round had to be booked as one of two things it was not, and booking it as a
    # reject moves the STALL counter — the signal that means "the optimizer has run out of
    # ideas", which is the one thing an ambiguous measurement is no evidence of.
    p.add_argument("--decision", required=True, choices=["accept", "reject", "inconclusive"],
                   help="accept=new champion; reject=the edit was judged and refuted; "
                        "inconclusive=the measurement could not resolve it (charges the "
                        "iteration, not the stall; re-measure under a FRESH tag)")
    p.add_argument("--val", type=float, default=None, help="candidate's full-val mean")
    p.add_argument("--note", default="", help="one line: why this edit, in general terms")
    # The DRIVER's disposition, recorded machine-readably alongside the screen's own
    # verdict. screen.py may only say kill/promote (invariant 1), so a candidate the
    # screen PROMOTED can still never reach full val — the driver may drop it on an
    # arithmetic ceiling or a budget call. Without this field the two artifacts read as a
    # contradiction ("promote" + a prose commit note saying "not promoted to full val");
    # with it, "promote" + basis=ceiling is one coherent story. `gate` is the only basis
    # that asserts a full-val paired gate actually ran.
    p.add_argument("--reject-basis", default=None,
                   choices=["gate", "screen_kill", "ceiling", "budget", "infra",
                            "driver_judgement"],
                   help="what evidence the reject rests on: gate=full-val paired gate ran AND "
                        "rejected; screen_kill=screen proved harm; ceiling=arithmetic proof no "
                        "accept was reachable, so full val was never paid; budget=screen "
                        "evidence plus a budget call; infra=missing data, not a judgement; "
                        "driver_judgement=the gate ACCEPTED and you are overriding it (say why "
                        "in --note)")
    p.add_argument("--optimizer-usd", type=float, default=0.0)
    p.add_argument("--optimizer-tokens", type=int, default=0)
    p.add_argument("--optimizer-seconds", type=float, default=0.0)
    p.add_argument("--force", action="store_true",
                   help="commit even though this candidate id already has a decision "
                        "(audit/repair only — it overwrites the earlier snapshot)")
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    src = Path(args.from_dir)
    if not src.is_dir():
        print(json.dumps({"error": f"--from-dir does not exist: {src}"}, indent=2))
        return 2

    if not args.force:
        prior = _prior_decision(run_dir, args.candidate_id)
        if prior:
            print(json.dumps({
                "error": f"candidate id {args.candidate_id!r} already has a "
                         f"{prior.get('kind')!r} decision in this run — refusing.",
                "why": "Rollouts are <task>__<tag>__t<k>.json, so two candidates sharing "
                       "a tag write into the same files: one edit gets judged on the "
                       "other's evidence and the second snapshot overwrites the first. "
                       "This happened for real (see docs/RESULTS.md, cand_r2).",
                "prior_event": prior,
                "fix": "pick a tag no sibling has used (e.g. suffix the round AND the "
                       "cluster: cand_r3_bags), or pass --force if you are deliberately "
                       "repairing this candidate's record.",
            }, indent=2))
            return 2

    accepted = args.decision == "accept"
    indecisive = args.decision == "inconclusive"
    if args.decision != "reject" and args.reject_basis:
        print(json.dumps({
            "error": f"--reject-basis is meaningless on an {args.decision}",
            "why": "it records what evidence a REJECT rests on. An unresolved round rests on "
                   "no evidence about the edit at all — that is what makes it unresolved.",
            "fix": "drop it, or pass --decision reject"}, indent=2))
        return 2
    # `--reject-basis gate` asserts the gate rejected this candidate. On run 32871360361 it was
    # booked for cand2, which round_i1.json recorded as `verdict: accept` at +0.19 against a
    # concurrent control — so events.jsonl, the run's audit record, said the gate had rejected the
    # best candidate of the run when in fact the driver had overridden it. Overriding is
    # legitimate (round.py leaves the decision to the driver on purpose); misattributing it is
    # not, and it is the one thing this log exists to get right.
    # An ``inconclusive`` gate verdict is the same misattribution one step further: the gate did
    # not refute the edit, it failed to resolve it. Observed live on run 33046360451 i1, where
    # cand_2's verdict was `{ctl_null_i1: reject, ctl_null_i1r1: accept}` — booking that as
    # "the gate rejected it" makes events.jsonl assert a judgement no measurement supports.
    gate_verdict = _gate_verdict(run_dir, args.candidate_id)
    overrode_gate = bool(args.decision == "reject" and gate_verdict == "accept")
    if args.reject_basis == "gate" and gate_verdict in ("accept", "inconclusive"):
        verb = ("ACCEPTED" if gate_verdict == "accept"
                else "could not resolve (verdict: inconclusive)")
        fix = ("pass --reject-basis driver_judgement and say in --note why you are overriding "
               "the gate — e.g. a task you care about regressed"
               if gate_verdict == "accept" else
               "book it as --decision inconclusive (charges the iteration, not the stall) and "
               "re-measure under a FRESH tag; or, if you are choosing to drop the edit anyway, "
               "pass --reject-basis driver_judgement and say so in --note")
        print(json.dumps({
            "error": f"--reject-basis gate, but the gate {verb} {args.candidate_id} "
                     "(see its row in work/round_*.json)",
            "gate_verdict": gate_verdict,
            "fix": fix,
        }, indent=2))
        return 2

    # The parent this candidate was gated against — ``gate_check --current`` defaults to
    # ``best_id``, so read it BEFORE ``set_best`` moves it.
    parent_id = run_dir.best_id or "seed"
    run_dir.snapshot(args.candidate_id, src)
    if accepted:
        run_dir.set_best(args.candidate_id)
    # Carry the proposer's own spend on the EVENT as well as into state.json. update_spent
    # alone leaves the dashboard's cost ledger unable to attribute it: state.json has the
    # total, but no cost-bearing event exists to explain it, so an agent-mode run reported
    # 100% of its optimizer spend as unattributed. opt_cost_usd/opt_tokens are the field
    # names the ledger already reads from headless optimizer backends.
    run_dir.log_event(args.decision, candidate=args.candidate_id, val=args.val,
                      gate_verdict=gate_verdict, overrode_gate=overrode_gate,
                      note=args.note,
                      reject_basis=args.reject_basis,
                      opt_cost_usd=args.optimizer_usd or None,
                      opt_tokens=args.optimizer_tokens or None,
                      opt_seconds=args.optimizer_seconds or None)
    run_dir.update_spent(optimizer_usd=args.optimizer_usd,
                         optimizer_tokens=args.optimizer_tokens,
                         optimizer_seconds=args.optimizer_seconds)
    # The shared iteration step: charges iterations/stall, writes the canonical ``step``
    # record, reconciles the run-level JOURNAL.md. The gate's numbers ride along so the
    # dashboard's ``gate_decisions[]`` does not have to regex them back out of an agent's
    # prose — read from round.py's persisted table, and simply absent when it wrote none.
    gate = _round_gate_numbers(run_dir, args.candidate_id)
    parent_val = gate.pop("parent_val", None)
    # Did the agent write the INTENT half of its handover? ``_reconcile_journal`` (inside
    # record_iteration) folds ``<workdir>/JOURNAL.md`` into the run-level journal and silently
    # substitutes "(no handover written by the optimizer)" when there is none — which is what
    # every round of runs 32971129203 and 33046360451 recorded, because nothing asked the agent
    # for one. Read it BEFORE booking, and report the answer so a forgotten handover is
    # correctable while rounds remain rather than discovered when the run is over.
    handover = bool(harness._journal_tail(src).strip())
    reason = args.note or args.decision
    if indecisive:
        reason = f"indecisive (gate): {reason}"
    harness.record_iteration(run_dir, src, args.candidate_id, parent_id=parent_id,
                             accepted=accepted, reason=reason,
                             val=args.val,
                             parent_val=parent_val,
                             indecisive=indecisive,
                             opt_cost_usd=args.optimizer_usd or None,
                             opt_tokens=args.optimizer_tokens or None,
                             optimizer_seconds=args.optimizer_seconds or None,
                             **gate)
    if indecisive:
        # The event the dashboard/TUI already read to render a step as `indecisive` rather than
        # rejected (``dashboard`` keys its status, badge and banner off this exact kind), and the
        # only thing that distinguishes an unresolved round from a refuted one downstream.
        run_dir.log_event("step_indecisive", candidate=args.candidate_id, reason=reason,
                          val=args.val, gate_verdict=gate_verdict)
    else:
        # Deliberately NOT for an unresolved round: ``rejected.jsonl`` is fed back as "these
        # edits did not work", and an edit the measurement could not judge says nothing of the
        # kind — filing it there teaches the next round to avoid a change never evaluated. Same
        # reasoning as the deterministic hill-climb's own indecisive branch.
        _record_memory(run_dir, args.candidate_id, accepted=accepted,
                       reason=reason, val=args.val, parent_val=parent_val)
    warnings: list[str] = []
    if not handover:
        warnings.append(
            "no handover recorded for this round: the run-level JOURNAL.md now reads "
            "'(no handover written by the optimizer)' for "
            f"{args.candidate_id}, so the next round can see WHICH tasks moved but not what you "
            "tried or why. Before the next commit.py, write your entry to "
            "<from-dir>/JOURNAL.md as a '## Iteration <candidate> — <headline>' block (changes "
            "made, expected effect, hypotheses prior RESULT lines already refuted, focus next).")
    spent = run_dir.spent
    run_dir.record_spend_warnings()
    stop, reason = run_dir.budget_exhausted()
    print(json.dumps({"decision": args.decision, "candidate": args.candidate_id,
                      "reject_basis": args.reject_basis,
                      "gate_verdict": gate_verdict,
                      "overrode_gate": overrode_gate,
                      "handover_recorded": handover,
                      "warnings": warnings,
                      "best_id": run_dir.best_id, "spent": spent.to_dict(),
                      "stop": stop, "stop_reason": reason}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
