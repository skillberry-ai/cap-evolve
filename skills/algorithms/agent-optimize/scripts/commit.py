"""commit — persist one agent-optimize round's decision through the run dir.

Replaces the old SKILL.md shell heredoc, which was unrunnable: it used a *quoted*
heredoc (``<<'PY'``) so ``$R`` never expanded and ``RunDir.open("$R")`` opened a
literal ``$R``, and it carried bare ``<placeholder>`` tokens that aren't Python.

Does exactly what the deterministic loops do at the end of a step:
  * ``snapshot`` the working copy as a candidate (always — the audit trail should
    show rejects too),
  * ``set_best`` on accept only,
  * ``log_event`` the accept/reject (agent-mode detail the other scripts read), and
  * ``harness.record_iteration`` — the ONE shared iteration step every algorithm
    routes through (#216/#224): charges ``iterations=1`` **and** ``accepted=`` so the
    stall counter that ``budget_exhausted()`` reads actually moves, writes the
    canonical ``step`` record every consumer enumerates, and reconciles the
    run-level ``JOURNAL.md``. Do NOT open-code those three here again.

``--decision provisional`` is a THIRD outcome, distinct from accept/reject: the candidate
is directionally positive (Δ>0) but did not clear the significance gate, and the driver
wants to buy more trials on this SAME, UNMODIFIED candidate (``scripts/grow.py``) before a
final call. It snapshots and logs the event like the other two, but does NOT ``set_best``
and does NOT call ``record_iteration`` — the iteration is not over, so the stall counter,
LEDGER.md and JOURNAL.md must not advance for it. The same candidate id later gets a real
``accept``/``reject`` commit once ``grow.py`` has re-gated it at the pooled n.

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


def _prior_decision(run_dir: RunDir, candidate_id: str) -> dict | None:
    """The first accept/reject event already recorded for ``candidate_id``, if any.

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
                if ev.get("kind") in ("accept", "reject") and \
                        str(ev.get("candidate")) == str(candidate_id):
                    return {"kind": ev.get("kind"), "t": ev.get("t"),
                            "note": ev.get("note"), "val": ev.get("val")}
    except FileNotFoundError:
        return None
    return None


def _gate_row(run_dir: RunDir, candidate_id: str) -> dict | None:
    """This candidate's row from ``round.py``'s persisted table, if one exists.

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
                return row
    return None


def _gate_verdict(run_dir: RunDir, candidate_id: str) -> str | None:
    row = _gate_row(run_dir, candidate_id)
    return row.get("verdict") if row else None


def _gate_stats(run_dir: RunDir, candidate_id: str) -> dict:
    """Structured numeric gate fields for this candidate, straight from ``round.py``'s table
    (which reads them from ``gate_check.py``'s own JSON) — for attaching to events, IN ADDITION
    to the prose ``--note``, so the dashboard's gate-decision view no longer has to regex-parse
    a hand-typed note to recover Δ/SE/n/k·SE/resolvable-effect-size. Field names match what
    ``dashboard.py``'s ``gate_decisions`` already reports, so no dashboard schema change is
    needed to consume them. Empty dict (not an error) when this candidate was never gated via
    ``round.py`` (e.g. a single-candidate flow that called ``gate_check.py`` directly)."""
    row = _gate_row(run_dir, candidate_id) or {}
    return {
        "delta": row.get("gate_delta"),
        "threshold": row.get("gate_threshold"),
        "stderr": row.get("stderr"),
        "n": row.get("n"),
        "k_se": row.get("k_se"),
        "resolvable_effect_size": row.get("resolvable_effect_size"),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="commit")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--candidate-id", required=True,
                   help="candidate id == the tag its rollouts were written under")
    p.add_argument("--from-dir", required=True, help="the working copy to snapshot")
    p.add_argument("--decision", required=True, choices=["accept", "reject", "provisional"])
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
    provisional = args.decision == "provisional"
    if (accepted or provisional) and args.reject_basis:
        print(json.dumps({"error": f"--reject-basis is meaningless on --decision {args.decision}",
                          "fix": "drop it, or pass --decision reject"}, indent=2))
        return 2
    # `--reject-basis gate` asserts the gate rejected this candidate. On run 32871360361 it was
    # booked for cand2, which round_i1.json recorded as `verdict: accept` at +0.19 against a
    # concurrent control — so events.jsonl, the run's audit record, said the gate had rejected the
    # best candidate of the run when in fact the driver had overridden it. Overriding is
    # legitimate (round.py leaves the decision to the driver on purpose); misattributing it is
    # not, and it is the one thing this log exists to get right.
    gate_verdict = _gate_verdict(run_dir, args.candidate_id)
    overrode_gate = bool(not accepted and not provisional and gate_verdict == "accept")
    if overrode_gate and args.reject_basis == "gate":
        print(json.dumps({
            "error": f"--reject-basis gate, but the gate ACCEPTED {args.candidate_id} "
                     "(see its row in work/round_*.json)",
            "fix": "pass --reject-basis driver_judgement and say in --note why you are "
                   "overriding the gate — e.g. the verdict was unstable across control "
                   "replicates, or a task you care about regressed",
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
    # Structured gate numbers (delta/threshold/stderr/n/k_se/resolvable_effect_size), IN
    # ADDITION to the prose --note, so the dashboard can render them without regex-parsing a
    # hand-typed string. {} when this candidate was never gated via round.py.
    gate_stats = _gate_stats(run_dir, args.candidate_id)
    run_dir.log_event(args.decision, candidate=args.candidate_id, val=args.val,
                      gate_verdict=gate_verdict, overrode_gate=overrode_gate,
                      note=args.note,
                      reject_basis=args.reject_basis,
                      verdict=args.decision,
                      opt_cost_usd=args.optimizer_usd or None,
                      opt_tokens=args.optimizer_tokens or None,
                      opt_seconds=args.optimizer_seconds or None,
                      **gate_stats)
    run_dir.update_spent(optimizer_usd=args.optimizer_usd,
                         optimizer_tokens=args.optimizer_tokens,
                         optimizer_seconds=args.optimizer_seconds)
    # `provisional` books the decision above but stops here: the iteration is not over
    # (the SAME candidate gets a real accept/reject commit later, once `grow.py` has
    # re-gated it at a pooled n), so the stall counter, LEDGER.md and JOURNAL.md must not
    # advance for it — that would spend an iteration's worth of "the run learned something
    # new" bookkeeping on a decision that has not actually been made yet.
    if not provisional:
        # The shared iteration step: charges iterations/stall, writes the canonical ``step``
        # record, reconciles the run-level JOURNAL.md. ``parent_val`` is unknown in agent mode
        # (the agent gates via gate_check, which prints but does not persist the parent mean),
        # so it stays None rather than being guessed.
        harness.record_iteration(run_dir, src, args.candidate_id, parent_id=parent_id,
                                 accepted=accepted, reason=args.note or args.decision,
                                 val=args.val,
                                 opt_cost_usd=args.optimizer_usd or None,
                                 opt_tokens=args.optimizer_tokens or None,
                                 **gate_stats)
        # Re-seed JOURNAL.md onto whichever candidate is now $BEST (fresh accumulated run
        # journal + marker), so the NEXT round's `cp -r "$R/candidates/$BEST" "$R/work/$TAG"`
        # carries a clean append target forward — the round-2+ half of the fix in host.py's
        # `_stage_context` (which seeds round 1 the same way onto the seed candidate).
        # `record_iteration` above already folded THIS round's tail into the run-level file,
        # so the snapshot picks up the full history regardless of accept/reject. Falls back to
        # THIS candidate's own just-taken snapshot when there is no best_id yet (a run with no
        # baseline) — that dir always exists (``run_dir.snapshot`` above just created it) —
        # and is best-effort: losing this re-seed must not fail the commit itself.
        try:
            harness._seed_journal(
                run_dir.candidate_dir(run_dir.best_id or args.candidate_id), run_dir)
        except Exception as exc:  # noqa: BLE001
            run_dir.log_event("optimizer_context_warning", what="JOURNAL.md", error=str(exc)[:300])
    spent = run_dir.spent
    run_dir.record_spend_warnings()
    stop, reason = run_dir.budget_exhausted()
    print(json.dumps({"decision": args.decision, "candidate": args.candidate_id,
                      "reject_basis": args.reject_basis,
                      "gate_verdict": gate_verdict,
                      "overrode_gate": overrode_gate,
                      "best_id": run_dir.best_id, "spent": spent.to_dict(),
                      "stop": stop, "stop_reason": reason}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
