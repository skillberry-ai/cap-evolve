"""commit — persist one agent-optimize round's decision through the run dir.

Replaces the old SKILL.md shell heredoc, which was unrunnable: it used a *quoted*
heredoc (``<<'PY'``) so ``$R`` never expanded and ``RunDir.open("$R")`` opened a
literal ``$R``, and it carried bare ``<placeholder>`` tokens that aren't Python.

Does exactly what the deterministic loops do at the end of a step:
  * ``snapshot`` the working copy as a candidate (always — the audit trail should
    show rejects too),
  * ``set_best`` on accept only,
  * ``log_event`` the accept/reject, and
  * ``update_spent`` with ``iterations=1`` **and** ``accepted=`` so the stall
    counter that ``budget_exhausted()`` reads actually moves.

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

from cap_evolve import RunDir


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


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="commit")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--candidate-id", required=True,
                   help="candidate id == the tag its rollouts were written under")
    p.add_argument("--from-dir", required=True, help="the working copy to snapshot")
    p.add_argument("--decision", required=True, choices=["accept", "reject"])
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
                   choices=["gate", "screen_kill", "ceiling", "budget", "infra"],
                   help="what evidence the reject rests on: gate=full-val paired gate ran; "
                        "screen_kill=screen proved harm; ceiling=arithmetic proof no accept "
                        "was reachable, so full val was never paid; budget=screen evidence "
                        "plus a budget call; infra=missing data, not a judgement")
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
    if accepted and args.reject_basis:
        print(json.dumps({"error": "--reject-basis is meaningless on an accept",
                          "fix": "drop it, or pass --decision reject"}, indent=2))
        return 2
    run_dir.snapshot(args.candidate_id, src)
    if accepted:
        run_dir.set_best(args.candidate_id)
    # Carry the proposer's own spend on the EVENT as well as into state.json. update_spent
    # alone leaves the dashboard's cost ledger unable to attribute it: state.json has the
    # total, but no cost-bearing event exists to explain it, so an agent-mode run reported
    # 100% of its optimizer spend as unattributed. opt_cost_usd/opt_tokens are the field
    # names the ledger already reads from headless optimizer backends.
    run_dir.log_event(args.decision, candidate=args.candidate_id, val=args.val,
                      note=args.note,
                      reject_basis=args.reject_basis,
                      opt_cost_usd=args.optimizer_usd or None,
                      opt_tokens=args.optimizer_tokens or None,
                      opt_seconds=args.optimizer_seconds or None)
    spent = run_dir.update_spent(iterations=1, accepted=accepted,
                                 optimizer_usd=args.optimizer_usd,
                                 optimizer_tokens=args.optimizer_tokens,
                                 optimizer_seconds=args.optimizer_seconds)
    run_dir.record_spend_warnings()
    stop, reason = run_dir.budget_exhausted()
    print(json.dumps({"decision": args.decision, "candidate": args.candidate_id,
                      "reject_basis": args.reject_basis,
                      "best_id": run_dir.best_id, "spent": spent.to_dict(),
                      "stop": stop, "stop_reason": reason}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
