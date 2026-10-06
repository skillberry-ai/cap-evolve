"""merge_rejects — combine K individually-rejected-but-SAFE candidates into one, before the
next single narrow edit gets written from scratch.

Why this exists. A full diagnostic audit of a real multi-hour run on a multi-turn tool-use
benchmark found the run reject 6 candidates in a row. Several of them — cand_4 and
cand_5 — each individually measured a positive, stable, ZERO-regression signal (empty
`broke`, non-negative `gate_delta`) that simply landed just under the gate's evidence bar at
that n. The optimizer noticed this by hand and improvised `cand_6` = union(cand_4, cand_5); it
measured a slightly larger, still-safe signal (still sub-threshold at n=30 in that run, but the
mechanical idea — bundle several small sub-threshold-but-safe effects so they might clear the
bar together — is exactly right, and it worked cleanly). Nothing made that anything but a
one-off: `merge_search.py`'s own compliance check (`check_merge_compliance`) only ever looks at
ACCEPTED candidates, so there was no systematic nudge for the REJECTED-but-safe case, which is
exactly where bundling has the most headroom to gain (a rejected candidate's signal is, by
construction, too small to have cleared the bar alone).

This script does not invent a new merge engine, a new disjointness rule, or a new gate. It
reuses `merge_search.py`'s own machinery end to end:

  * "safe reject" evidence comes from `events.jsonl`'s `"reject"` decision events — the exact
    record `commit.py` writes (candidate, note, reject_basis, and, when a gate table exists,
    `gate_delta` plus `movement`'s `broke`/`fixed` — see `gate_check.py`'s `regressions`/
    `movement` output and `references/algorithm.md`'s "Composition, not just the mean"). A
    reject is "safe" when `gate_delta >= 0` and `broke == []`: it did not clearly hurt, it just
    did not clear the bar. `rejected.jsonl` (`cap_evolve.memory.RejectedMemory`) is NOT read
    here — it stores only `{candidate_id, summary, reason, val}`, none of the structured gate
    numbers this needs, while the `"reject"` event `commit.py` logs in the SAME call carries
    `gate_delta`/`broke`/`fixed`/`reject_basis` directly (see `commit.py`'s `log_event(args.decision,
    ...,  reject_basis=args.reject_basis, **gate)`).
  * the compliance audit (`check_rejects_compliance`) mirrors `merge_search.check_merge_compliance`
    exactly: disjointness is by TARGET TASK IDS (`mechanisms.jsonl`, same `_mechanisms_targets`
    helper `merge_search.py` itself uses), not by file diff — a cheap, file-free check meant to
    run at finalize time alongside the accepted-candidate one.
  * `--propose` builds the actual candidate directory. Disjointness there is by CHANGED
    FUNCTIONS (`merge_search.changed_functions`, i.e. `funcmerge.py`'s own per-function split) —
    the provably-safe case `merge_search.py`'s module docstring already establishes. Assembly is
    one `integrate.py` call over ALL given branches in one shot: `integrate.py` already folds
    N branches ONE AT A TIME, measuring after each (see its own docstring for why a one-shot
    N-way merge does not compose) — this script does not reimplement that loop, it drives it.

Nothing here auto-commits or auto-accepts anything. A successfully proposed merge lands at
`$R/work/<tag>` as an ordinary candidate directory; screening/gating/accepting stays the
driver's job through `screen.py`/`round.py`/`commit.py`, unchanged.

    python merge_rejects.py --run-dir R --project P                      # report only
    python merge_rejects.py --run-dir R --project P --propose \\
        --rejects cand_4,cand_5 --base seed --n 10 --conc 8 --floor 0.0333
"""

from __future__ import annotations

import argparse
import contextlib
import io
import itertools
import json
import subprocess
import sys
from pathlib import Path

import mechanisms
import merge_search

HERE = Path(__file__).resolve().parent


def _reject_events(run_dir_root) -> dict[str, dict]:
    """Every ``"reject"`` decision event in ``events.jsonl``, keyed by candidate id.

    The event is exactly what ``commit.py`` writes on ``--decision reject``:
    ``log_event(args.decision, candidate=..., note=..., reject_basis=..., **gate)`` where
    ``gate`` (``commit.py``'s ``_round_gate_numbers``) contributes ``gate_delta``, ``broke``,
    ``fixed``, ``n_broke``, ``n_fixed`` etc. WHEN a gate table exists for that round — absent
    for a ``reject_basis`` that never reached a gate (``screen_kill``/``ceiling``/``infra``).
    A candidate rejected more than once (e.g. after a re-measurement under a fresh tag) keeps
    only its LATEST event: later evidence about the same id supersedes earlier evidence.
    """
    path = Path(run_dir_root) / "events.jsonl"
    if not path.exists():
        return {}
    out: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        if row.get("kind") != "reject":
            continue
        tag = row.get("candidate")
        if tag:
            out[tag] = row
    return out


def is_safe_reject(row: dict) -> bool:
    """A reject is "safe" when the measurement shows it did not clearly hurt: an empty
    ``broke`` list (zero regressions — `gate_check.py`'s `movement.broke`, the same rule
    `regressions()` feeds) AND a non-negative `gate_delta`. Both fields must be PRESENT —
    a reject with no gate table at all (``reject_basis`` never reached one) is unknowable,
    never assumed safe."""
    delta = row.get("gate_delta")
    broke = row.get("broke")
    return (isinstance(delta, (int, float)) and delta >= 0
            and isinstance(broke, list) and len(broke) == 0)


def find_safe_rejects(run_dir_root) -> dict[str, dict]:
    """``{candidate_id: reject_event}`` for every rejected candidate whose own recorded
    evidence is zero-regression and non-negative-delta — see ``is_safe_reject``."""
    return {tag: row for tag, row in _reject_events(run_dir_root).items()
            if is_safe_reject(row)}


def find_disjoint_group(footprints: dict[str, set], min_size: int) -> list[str] | None:
    """The largest subset of ``footprints`` (>= ``min_size``) that is PAIRWISE disjoint —
    no two members share anything in their footprint set. Brute force over
    ``itertools.combinations``: the input here is a handful of rejects per run, never a scale
    where this matters.
    # ponytail: O(2^n) brute force; fine at run-scale (single-digit rejects), revisit if a run
    # ever produces dozens of safe rejects in one go.
    """
    tags = sorted(footprints)
    for size in range(len(tags), min_size - 1, -1):
        for group in itertools.combinations(tags, size):
            seen: set = set()
            ok = True
            for t in group:
                if footprints[t] & seen:
                    ok = False
                    break
                seen |= footprints[t]
            if ok:
                return list(group)
    return None


def _already_attempted(run_dir_root) -> bool:
    """Was a merge-of-rejects already PROPOSED this run? Checked via this script's own
    ``merge_rejects_propose`` event (logged by ``--propose`` below on a successful build) —
    the one marker this script fully controls, so the check does not depend on the driver
    remembering to tag a later commit with a particular ``edit_kind``."""
    path = Path(run_dir_root) / "events.jsonl"
    if not path.exists():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        if row.get("kind") == "merge_rejects_propose":
            return True
    return False


def check_rejects_compliance(run_dir, min_safe: int = 3) -> dict | None:
    """Audit signal, not an enforcement — mirrors ``merge_search.check_merge_compliance``
    exactly, one level earlier in the loop: instead of asking "were 2+ ACCEPTED disjoint
    candidates ever merged", this asks "do 3+ REJECTED-but-safe disjoint candidates exist
    that were never even tried together".

    Disjointness here is by TARGET TASK IDS (``mechanisms.jsonl``'s ``tasks`` field per
    owner, via the same ``merge_search._mechanisms_targets`` helper `merge_search.py` itself
    falls back to) — cheap and file-free, matching the finalize-time audit this is meant to
    run alongside.

    Returns ``None`` when there is nothing to flag (fewer than ``min_safe`` safe rejects with
    known targets, no disjoint group of that size, or a merge-of-rejects was already proposed
    this run), else a dict of fields for ``RunDir.log_event``.
    """
    safe = find_safe_rejects(run_dir.root)
    if len(safe) < min_safe:
        return None

    targets: dict[str, set] = {}
    for tag in safe:
        ids = merge_search._mechanisms_targets(run_dir.root, tag)
        if ids:
            targets[tag] = set(ids)
    if len(targets) < min_safe:
        return None

    group = find_disjoint_group(targets, min_safe)
    if not group:
        return None

    if _already_attempted(run_dir.root):
        return None

    return {
        "reason": "safe_rejects_not_merged",
        "safe_reject_candidates": group,
        "evidence": {tag: {"gate_delta": safe[tag].get("gate_delta"),
                           "broke": safe[tag].get("broke", []),
                           "reject_basis": safe[tag].get("reject_basis"),
                           "note": safe[tag].get("note")}
                     for tag in group},
        "targets": {tag: sorted(targets[tag]) for tag in group},
    }


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="merge_rejects")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--project", required=True)
    ap.add_argument("--min-safe", type=int, default=3,
                    help="how many disjoint safe rejects trigger the compliance warning")
    ap.add_argument("--propose", action="store_true",
                    help="actually build the combined candidate under $R/work/<tag>")
    ap.add_argument("--rejects", default="",
                    help="comma-separated safe-reject tags to combine (--propose only)")
    ap.add_argument("--targets", action="append", default=[],
                    help="tag:comma,separated,task,ids. Repeatable. Falls back to "
                         "mechanisms.jsonl's `tasks` field for rows owned by that tag.")
    ap.add_argument("--base", default="seed", help="tag of the base each reject was measured against")
    ap.add_argument("--out-tag", default="", help="override the built candidate's tag")
    ap.add_argument("--file", default="tools/tools.py")
    ap.add_argument("--prose", default="policy/policy.md")
    ap.add_argument("--canary-auto", default="", help="see merge_search.py --canary-auto")
    ap.add_argument("--canary", default="")
    ap.add_argument("--canary-floor", type=float, default=0.9)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--conc", type=int, default=8)
    ap.add_argument("--base-seed", type=int, default=0)
    ap.add_argument("--floor", type=float, default=0.0)
    ap.add_argument("--json", dest="json_out", default="")
    return ap


def _propose(run_dir, project, args, safe: dict[str, dict]) -> dict:
    """Build the combined candidate: one ``integrate.py`` call, all given branches in one
    invocation, best-evidenced first — ``integrate.py`` itself measures branch by branch and
    drops whichever one regresses, per its own docstring, so a bad interaction is attributed
    to the specific branch that caused it, never lost in a one-shot N-way merge."""
    import _bootstrap  # noqa: F401
    from cap_evolve import RunDir

    rd = run_dir if isinstance(run_dir, RunDir) else RunDir.open(Path(run_dir))
    rejects = [t.strip() for t in args.rejects.split(",") if t.strip()]
    if len(rejects) < 2:
        return {"error": "--propose needs --rejects with 2+ tags"}

    unknown = [t for t in rejects if t not in safe]
    if unknown:
        return {"error": f"not a recorded SAFE reject this run: {unknown}", "safe_rejects": sorted(safe)}

    base_dir = rd.candidate_dir(args.base)
    base_file = base_dir / args.file
    if not base_file.exists():
        return {"error": f"base file not found: {base_file}"}
    base_src = base_file.read_text(encoding="utf-8")

    reject_dirs = {t: rd.candidate_dir(t) for t in rejects}
    missing = [t for t, d in reject_dirs.items() if not (d / args.file).exists()]
    if missing:
        return {"error": f"reject candidate file(s) missing: {missing}"}

    reject_srcs = {t: (d / args.file).read_text(encoding="utf-8") for t, d in reject_dirs.items()}
    changed = {t: merge_search.changed_functions(base_src, src) for t, src in reject_srcs.items()}
    for a, b in itertools.combinations(rejects, 2):
        shared = changed[a] & changed[b]
        if shared:
            return {"error": f"{a} and {b} both touch {sorted(shared)} — a real edit collision, "
                              "not a disjoint-safe-rejects merge",
                    "changed_functions": {t: sorted(v) for t, v in changed.items()}}

    explicit_targets: dict[str, list[str]] = {}
    for item in args.targets:
        tag, _, ids = item.partition(":")
        explicit_targets[tag.strip()] = [i.strip() for i in ids.split(",") if i.strip()]

    targets: dict[str, list[str]] = {}
    for tag in rejects:
        t = explicit_targets.get(tag) or merge_search._mechanisms_targets(rd.root, tag)
        if not t:
            return {"error": f"no target task ids for {tag!r} (pass --targets or record "
                              "them in mechanisms.jsonl)"}
        targets[tag] = t
    union_tasks = sorted({tid for ids in targets.values() for tid in ids})

    # best-evidenced first, per integrate.py's own docstring ("put the best-evidenced branch
    # first so a later regression is attributable").
    ordered = sorted(rejects, key=lambda t: -(safe[t].get("gate_delta") or 0.0))
    out_tag = args.out_tag or f"mergereject_{'_'.join(ordered)}"

    canary_auto = merge_search._canary_auto_file(args.canary_auto) if args.canary_auto else ""
    work = rd.root / "work"
    work.mkdir(parents=True, exist_ok=True)
    json_out = work / f".{out_tag}_integrate.json"
    cmd = [sys.executable, str(HERE / "integrate.py"),
           "--base", str(base_dir), "--project", str(project),
           "--branches", *[str(reject_dirs[t]) for t in ordered],
           "--out", str(work / out_tag), "--tasks", ",".join(union_tasks),
           "--n", str(args.n), "--conc", str(args.conc), "--base-seed", str(args.base_seed),
           "--floor", str(args.floor), "--file", args.file, "--prose", args.prose,
           "--taskeval", str(HERE / "taskeval.py"), "--json", str(json_out)]
    if canary_auto:
        cmd += ["--canary-auto", canary_auto, "--canary-floor", str(args.canary_floor)]
    elif args.canary:
        cmd += ["--canary", args.canary]
    p = subprocess.run(cmd, capture_output=True, text=True)
    result = {}
    if json_out.exists():
        try:
            result = json.loads(json_out.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
    if not result:
        result = {"error": (p.stderr or p.stdout)[-1200:], "rc": p.returncode}

    built = bool(result.get("out")) and (work / out_tag).is_dir() and "error" not in result
    out = {"rejects": ordered, "tag": out_tag, "built": built, "targets": union_tasks,
          "changed_functions": {t: sorted(v) for t, v in changed.items()}, "result": result}

    if built:
        rd.log_event("merge_rejects_propose", rejects=ordered, tag=out_tag, built=True,
                     targets=union_tasks)
        mechanisms.ledger(rd.root).parent.mkdir(parents=True, exist_ok=True)
        mechanisms_args = argparse.Namespace(
            run_dir=rd.root, owner=out_tag, status="proposed",
            mechanism=f"merge of {len(ordered)} safe-but-rejected candidates: {', '.join(ordered)}",
            evidence=f"each individually zero-regression, gate_delta>=0 (see events.jsonl); "
                     f"integrate.py accepted: {sorted(result.get('accepted', []))}; "
                     f"final_objective={result.get('final_objective')}",
            touches=sorted({fn for fns in changed.values() for fn in fns}),
            task=union_tasks, supersedes=[])
        with contextlib.redirect_stdout(io.StringIO()):
            mechanisms.add(mechanisms_args)
    return out


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    import _bootstrap  # noqa: F401
    from cap_evolve import RunDir

    run_dir = RunDir.open(Path(args.run_dir))
    safe = find_safe_rejects(run_dir.root)

    warning = check_rejects_compliance(run_dir, min_safe=args.min_safe)
    if warning:
        run_dir.log_event("merge_rejects_compliance_warning", **warning)

    out = {
        "safe_rejects": {tag: {"gate_delta": row.get("gate_delta"), "broke": row.get("broke", []),
                               "reject_basis": row.get("reject_basis"), "note": row.get("note")}
                        for tag, row in safe.items()},
        "compliance_warning": warning,
        "next": ("run with --propose --rejects tag1,tag2[,tag3] on a disjoint subset named "
                 "above" if warning else
                 "nothing to flag: fewer than --min-safe disjoint safe rejects, or a merge of "
                 "them was already proposed this run"),
    }

    if args.propose:
        out["propose"] = _propose(run_dir, Path(args.project), args, safe)

    text = json.dumps(out, indent=2)
    print(text)
    if args.json_out:
        Path(args.json_out).write_text(text, encoding="utf-8")
    if args.propose and not out["propose"].get("built") and "error" in out["propose"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
