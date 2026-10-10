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

Beyond ``accept``/``reject`` there are two more outcomes, and they are NOT the same thing:

  * ``inconclusive`` — the measurement could not resolve the edit (the verdict flips between
    byte-identical control replicates). A booked round: it charges the iteration but not the
    stall, files no ``rejected.jsonl`` record, and must be re-measured under a FRESH tag.
  * ``provisional`` — the candidate is directionally positive (Δ>0) but under the significance
    bar, and the driver wants to buy more trials on this SAME, UNMODIFIED candidate
    (``scripts/grow.py``) before calling it. NOT a booked round: it snapshots and logs the
    event, but does NOT ``set_best`` and does NOT call ``record_iteration``, so the stall
    counter, LEDGER.md and JOURNAL.md do not advance. The same candidate id later gets a real
    ``accept``/``reject``/``inconclusive`` commit once ``grow.py`` has re-gated it at the
    pooled n.

Runner-side spend (metric_calls / usd / tokens / seconds) is already recorded by the
evaluate phase; ``--optimizer-*`` is for the *proposer's* own cost, which in agent
mode is you and would otherwise never be counted.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

# Imported for its side effect ONLY: seeds sys.path so `cap_evolve` resolves when
# this script is run standalone (`python <this-file>`). Must precede the
# cap_evolve imports below; not "unused" — deleting it breaks standalone runs.
import _bootstrap  # noqa: F401  # side-effect import, see above

from cap_evolve import RunDir, graph, harness, optimizer_cost

import meter


# #684 item 10: optimizer_seconds/optimizer_usd are always 0 across real agent-mode runs.
# meter.py's automatic metering only works under host.py's headless driver (it reads a
# claude-code session log that only exists there); in agent orchestration mode (this
# script, called directly by the conversational agent) nothing captures the proposer's own
# thinking time unless the agent passes --optimizer-seconds/--optimizer-usd itself — SKILL.md
# step 7 asks for this but never required or checked it. This is a cheap, automatic sanity
# check for that compliance gap: real wall-clock time clearly passed since the previous
# decision, yet this commit still reports zero optimizer cost.
_ZERO_OPTIMIZER_COST_WARN_S = 120  # ponytail: fixed heuristic threshold, tune if too noisy


def _decision_times(run_dir: RunDir) -> tuple[float | None, float | None]:
    """(first event time, previous decision time) of this run — bounds for the log harvest."""
    first = last = None
    try:
        with run_dir.events_path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                first = first if first is not None else rec.get("t")
                if rec.get("kind") in ("accept", "reject", "inconclusive", "provisional"):
                    last = rec.get("t")
    except OSError:
        pass
    return first, last


def _wallclock_since_last_decision(run_dir: RunDir) -> float | None:
    """Seconds since this run's previous accept/reject/inconclusive/provisional decision,
    or None when this is the first one (nothing to compare against)."""
    last_t = None
    try:
        with run_dir.events_path.open(encoding="utf-8") as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("kind") in ("accept", "reject", "inconclusive", "provisional"):
                    last_t = rec.get("t")
    except OSError:
        return None
    return (time.time() - last_t) if last_t is not None else None


def _memory_skill_from_spec(run_dir: RunDir) -> str | None:
    """``memory_skill`` from the sibling project spec, or ``None``.

    Agent mode invokes this script standalone with only ``--run-dir`` — no ``--project``,
    no spec object — so the choice has to be read off disk the same zero-dependency way
    ``dashboard.py``'s ``_algorithm_from_spec`` reads ``algorithm_skill``: flat ``key: value``
    lines only, from ``<base>/project/capevolve.yaml`` next to the run dir. Best-effort — a
    missing/unreadable spec just means the default (``md-files``) applies, same as today.
    """
    spec_path = run_dir.root.parent / "project" / "capevolve.yaml"
    if not spec_path.is_file():
        return None
    try:
        for line in spec_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("memory_skill:"):
                val = line.split(":", 1)[1].split("#", 1)[0].strip().strip("'\"")
                return val or None
    except OSError:
        pass
    return None


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
    # A grown candidate's POOLED row (``grow.py``) supersedes the round's pre-growth row by
    # construction: growth exists precisely to re-measure the same candidate at a larger n, so
    # the round table's numbers are the ones being superseded. Sorted by growth round, last wins.
    tables += sorted(work.glob(f"grow_{candidate_id}_r*.json"),
                     key=lambda p: int(p.stem.rsplit("_r", 1)[-1])
                     if p.stem.rsplit("_r", 1)[-1].isdigit() else 0)
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
    # The SE of the PAIRED per-task deltas — the number every ``gate_threshold`` in these
    # tables is ``k_se ×``, and therefore the only SE that belongs in the same row.
    # DERIVED, never read off a stderr column: neither table records the paired SE, and both
    # carry a ``stderr`` that is a mean-over-tasks SE instead. Publishing one of those is the
    # defect this is replacing — on run_finalrun6 it put an identical ``gate_stderr``
    # 0.0738 on rounds i0, i3 and i6 while the threshold it is supposed to generate moved
    # 0.0222 → 0.0244 → 0.0346, i.e. a constant beside three different bars derived from it.
    # ``resolvable_effect_size`` is ``2·SE``, written by ``gate.decide`` from the vector it
    # actually gated on, so halving it recovers that round's real SE exactly. Absent when the
    # gate reported no SE (threshold/strict modes, or too few paired samples), and a missing
    # measurement must stay missing rather than become a fabricated number.
    _res = entry.get("resolvable_effect_size")
    out = {
        "parent_val": parent.get("reward"),
        "gate_stderr": (round(float(_res) / 2.0, 6)
                        if isinstance(_res, (int, float)) else None),
        # The parent block is the round table's; a grow table has no parent, so fall back to the
        # candidate entry's own paired n — which IS what the gate used.
        "gate_n": parent.get("n_tasks", entry.get("n")),
        "gate_delta": entry.get("gate_delta"),
        "gate_threshold": entry.get("gate_threshold"),
        "gate_mode": (table.get("gated_against") or {}).get("mode"),
        "gate_table": tables[-1].name,
        # The significance multiplier the bar was built from, and the smallest true effect this
        # round could have resolved (2·SE). Without the latter a null result is unreadable: four
        # consecutive runs of nulls were read as "the edits were bad" when the measurement simply
        # could not resolve anything that small.
        "gate_k_se": entry.get("k_se"),
        "gate_resolvable_effect_size": entry.get("resolvable_effect_size"),
    }
    # The drift-free second opinion, when the round measured one. On run 32971129203 this is
    # the whole finding: cand_1 was rejected against the parent's STORED reward (Δ 0.0333 vs
    # threshold 0.0440) while the control-relative comparison ACCEPTED it (Δ 0.0556 vs 0.0341).
    # Recording only the booked verdict hides that the decision was reference-dependent.
    # What this candidate TRADED, from the round table's `movement` (gate_check's shared
    # `harness.movement`). On the step record because that is what LEDGER/RUNMAP, the dashboard
    # graph, the TUI and ci/benchmarks/lib/metrics.py all read — and because `r3_decide` was
    # booked ACCEPT in run 36175707483 with "BROKE vs both controls [33722]" recorded nowhere
    # but its own prose. Its sealed-split composition was 54 improved / 17 regressed, every
    # sampled regression a 1.000 → 0.000, and nothing in the run's machine-readable record said
    # a single task had been destroyed. Written only when the table HAS the movement (an older
    # table, or a `gate_check`-only round, has none) — a missing measurement stays missing.
    _mv = entry.get("movement") or {}
    if _mv:
        out["broke"] = list(_mv.get("broke") or [])
        out["fixed"] = list(_mv.get("fixed") or [])
        # Explicit counts, not derived by every reader: `0` here is a real measured claim
        # ("broke nothing"), which is why the lists above are written even when empty.
        out["n_broke"] = len(out["broke"])
        out["n_fixed"] = len(out["fixed"])
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


def _has_screen_record(run_dir: RunDir, candidate_id: str) -> bool:
    """Has ``screen.py`` ever written a ``<candidate_id>__screenN.json`` record?

    Same check ``round.py`` makes before it will run a full-val gate at all — read here so
    ``commit.py`` can tell a candidate that went through the screen ladder (and never reached
    the gate for some other reason, e.g. a screen kill) from one that bypassed BOTH.
    """
    screens_dir = run_dir.root / "screens"
    return screens_dir.is_dir() and any(screens_dir.glob(f"{candidate_id}__screen*.json"))


def _diagnosis_targets(src: Path) -> tuple[list[str], dict | None]:
    """``(cluster_ids, subset)`` this edit targeted, read from ``<from-dir>/DIAGNOSIS.json``.

    ``([], None)`` when the file is missing, unparseable, or an empty template — i.e. no
    cluster with both an ``id`` and at least one task (#611). ``cluster_ids`` are the clusters
    the edits name (all clusters when no edit names one); ``subset`` is those clusters' tasks.
    These feed the ``graph.jsonl`` node, whose ``cluster_ids``/``subset`` were empty on every
    entry of a real run because nothing ever passed them.
    """
    try:
        diag = json.loads((src / "DIAGNOSIS.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return [], None
    if not isinstance(diag, dict) or not isinstance(diag.get("clusters"), list):
        return [], None
    tasks_by = {str(c["id"]): [str(t) for t in c["tasks"]]
                for c in diag["clusters"]
                if isinstance(c, dict) and c.get("id") and isinstance(c.get("tasks"), list)
                and c["tasks"]}
    if not tasks_by:
        return [], None
    named = [str(cid) for e in (diag.get("edits") or []) if isinstance(e, dict)
             for cid in (e.get("clusters") or []) if str(cid) in tasks_by]
    cluster_ids = list(dict.fromkeys(named)) or list(tasks_by)
    task_ids = sorted({t for cid in cluster_ids for t in tasks_by[cid]})
    return cluster_ids, {"task_ids": task_ids, "rationale": "DIAGNOSIS.json clusters",
                         "tier": None}


#: Dashboard badge taxonomy for a candidate's self-reported edit classification (#665
#: workstream 4). Advisory only — an unrecognized/missing value just renders as "—",
#: never refuses a commit, since DIAGNOSIS.json's authoring is owned by SKILL.md
#: (a different workstream) and this field is optional.
CHANGE_TYPES = ("PROMPT_EDIT", "TOOL_CODE_EDIT", "VALIDATOR_ADD", "MIXED")


def _diagnosis_change_type(src: Path) -> str | None:
    """``change_type`` this edit self-reports, read from ``<from-dir>/DIAGNOSIS.json``.

    ``None`` when the file is missing/unparseable or the field is absent/not one of
    ``CHANGE_TYPES`` — optional and nullable, so an old DIAGNOSIS.json without it
    (or any run that predates this field) just shows no badge."""
    try:
        diag = json.loads((src / "DIAGNOSIS.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    ct = diag.get("change_type") if isinstance(diag, dict) else None
    return ct if isinstance(ct, str) and ct in CHANGE_TYPES else None


def _ranked_issue_rows(src: Path) -> int:
    """Data rows in ``<from-dir>/PROCESS.md``'s "Ranked issue list" table (#634).

    Scoped to that section only (up to the next ``## `` heading): the dashboard's
    ``harness._parse_process_md_tables`` regex can run past a header-only table into the
    "Changes made" table below it, which would count a blank ranked list as filled. A row
    counts when any cell after ``rank`` has text — a bare ``| 1 | | |`` is still blank.
    """
    try:
        text = (src / "PROCESS.md").read_text(encoding="utf-8")
    except OSError:
        return 0
    m = re.search(r"^##\s+Ranked issue list[^\n]*\n(.*?)(?=^##\s|\Z)", text,
                  re.IGNORECASE | re.MULTILINE | re.DOTALL)
    if not m:
        return 0
    rows = [ln.strip() for ln in m.group(1).splitlines() if ln.strip().startswith("|")]
    body = [r for r in rows[1:] if not re.fullmatch(r"[|\s:-]+", r)]  # drop header + separator
    return sum(1 for r in body if any(c.strip() for c in r.strip("|").split("|")[1:]))


#: Jaccard overlap of targeted task ids at/above which a new candidate counts as a retry of
#: an earlier refuted one (#634). ponytail: task-set overlap only — a retry aimed at different
#: tasks with the same idea slips through; add a mechanism/edit-text comparison if that bites.
RETRY_OVERLAP = 0.5


def _refuted_retries(run_dir: RunDir, candidate_id: str, task_ids: list[str]) -> list[dict]:
    """Earlier REJECTED candidates whose own DIAGNOSIS.json targeted (nearly) these tasks (#634).

    A ``reject`` is the gate measuring an edit flat or negative; ``inconclusive`` (unresolved,
    re-measure under a fresh tag) and ``--reject-basis infra`` (missing data, no judgement) are
    not refutations and never count. The prior's targets come from its SNAPSHOT's
    DIAGNOSIS.json, the same reader as this candidate's own (``_diagnosis_targets``).
    """
    new = set(task_ids)
    if not new:
        return []
    try:
        lines = run_dir.events_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    hits, seen = [], {str(candidate_id)}
    for line in lines:
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        cid = str(ev.get("candidate"))
        if ev.get("kind") != "reject" or ev.get("reject_basis") == "infra" or cid in seen:
            continue
        seen.add(cid)
        _, sub = _diagnosis_targets(run_dir.candidate_dir(cid))
        old = set(sub["task_ids"]) if sub else set()
        overlap = len(new & old) / len(new | old)
        if overlap >= RETRY_OVERLAP:
            hits.append({"candidate": cid, "overlap": round(overlap, 2),
                         "shared_task_ids": sorted(new & old), "note": ev.get("note")})
    return hits


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


def _control_relative_verdict(run_dir: RunDir, candidate_id: str) -> dict:
    """This candidate's drift-corrected verdict — ``round.py``'s ``control_relative``
    comparison against the round's own null-control replicate(s), read back from the same
    row ``_gate_row``/``_gate_verdict`` use. Distinct from the raw ``verdict`` (against the
    STORED parent reward, which can carry drift since the parent was last measured).

    ``stable`` is ``row["verdict_stable"]`` when the round had 2+ control replicates to check
    the verdict against (``round.py``'s two-seed-block agreement check); ``None`` when the
    round had only one, in which case there is nothing to check stability against and the
    single verdict stands on its own.
    """
    row = _gate_row(run_dir, candidate_id) or {}
    ctl = row.get("control_relative") or {}
    return {"verdict": ctl.get("verdict"), "stable": row.get("verdict_stable")}


def _has_grown(run_dir: RunDir, candidate_id: str) -> bool:
    """Has ``scripts/grow.py`` already bought this candidate at least one extra round of
    trials? True iff a ``work/grow_<candidate_id>_r*.json`` table exists.

    On run 33492876620 round 3 a candidate landed exactly on ``grow.py``'s reason for
    existing — Δ>0, below the significance bar, verdict flipping between control
    replicates — and was booked ``inconclusive`` and left there. The transcript shows the
    agent had read ``grow.py --help``, so this was not a discovery gap: the tool was
    optional, so it went unused. See ``main``'s guard below.
    """
    return any((run_dir.root / "work").glob(f"grow_{candidate_id}_r*.json"))


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
    #
    # ``provisional`` is a FOURTH outcome, and unlike ``inconclusive`` it does not book the
    # round at all: the candidate is directionally positive (Δ>0) but under the significance
    # bar, and the driver wants to buy more trials on this SAME, UNMODIFIED candidate
    # (``scripts/grow.py``) before making a call. The iteration is not over, so the stall
    # counter, LEDGER.md and JOURNAL.md must not advance for it.
    p.add_argument("--decision", required=True,
                   choices=["accept", "reject", "inconclusive", "provisional"],
                   help="accept=new champion; reject=the edit was judged and refuted; "
                        "inconclusive=the measurement could not resolve it (charges the "
                        "iteration, not the stall; re-measure under a FRESH tag); "
                        "provisional=Δ>0 but unresolved, buying more trials on the SAME "
                        "candidate next (books nothing; re-commit it once grown)")
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
                            "micro_test_fail", "driver_judgement", "drift_control"],
                   help="what evidence the reject rests on: gate=full-val paired gate ran AND "
                        "rejected; screen_kill=screen proved harm; ceiling=arithmetic proof no "
                        "accept was reachable, so full val was never paid; budget=screen "
                        "evidence plus a budget call; infra=missing data, not a judgement; "
                        "micro_test_fail=microcase.py proved the candidate's own targeted "
                        "mechanism does not fire, before any rollout was spent (#436); "
                        "drift_control=the raw parent-relative gate ACCEPTED, but round.py's "
                        "drift-corrected control_relative comparison (vs a same-round "
                        "null-control replicate) says reject and is verdict-stable — a "
                        "structured disagreement, not a one-off override. Since issue #684 "
                        "item 6 the control-relative comparison IS round.py's primary "
                        "verdict whenever a control was measured (the default), so this "
                        "disagreement should rarely arise any more; it is kept for the "
                        "--gate-against control / no-control-replicate edge cases and for "
                        "older round tables; "
                        "driver_judgement=the gate ACCEPTED and you are overriding it for any "
                        "OTHER reason (say why in --note)")
    p.add_argument("--bypassed-gate-justification", default=None,
                   help="required alongside --reject-basis driver_judgement when this "
                        "candidate has NEITHER a full-val gate row NOR a screen.py record — "
                        "the 'skip screen AND skip the gate entirely' escape hatch. Say why "
                        "no measurement was ever run for it (e.g. an infra failure before any "
                        "rollout, or a deliberate drop before evaluating it at all).")
    p.add_argument("--missing-handover-justification", default=None,
                   help="required when this candidate's <from-dir>/JOURNAL.md has no new "
                        "'## Iteration' entry for it — the escape hatch for committing without "
                        "one (#588). Say why the optimizer never got to write it (e.g. an infra "
                        "failure). Without it, commit.py refuses rather than silently booking "
                        "the framework's synthesized stub.")
    p.add_argument("--missing-diagnosis-justification", default=None,
                   help="required when this candidate's <from-dir>/DIAGNOSIS.json is missing or "
                        "an empty template (no cluster with an id AND tasks) — the escape hatch "
                        "for committing without one (#611). Say why no diagnosis exists (e.g. an "
                        "infra failure before the optimizer wrote it). Without it, commit.py "
                        "refuses: the graph.jsonl node's cluster_ids/subset and the dashboard's "
                        "diagnosis view come from this file.")
    p.add_argument("--missing-ranked-issues-justification", default=None,
                   help="required when this candidate's <from-dir>/PROCESS.md 'Ranked issue "
                        "list' table has no data rows (header-only) — the escape hatch for "
                        "committing without one (#634). Say why the full remaining-failure "
                        "landscape was not re-surveyed this round. Without it, commit.py refuses.")
    p.add_argument("--retry-justification", default=None,
                   help="required when this candidate's DIAGNOSIS.json targets (nearly) the same "
                        "tasks as an earlier candidate the gate REJECTED (#634). One line: what is "
                        "different this time, beyond cosmetic variation. Without it, commit.py "
                        "refuses rather than book a re-try of a refuted idea.")
    p.add_argument("--optimizer-usd", type=float, default=0.0)
    p.add_argument("--optimizer-tokens", type=int, default=0)
    p.add_argument("--optimizer-seconds", type=float, default=0.0)
    p.add_argument("--force", action="store_true",
                   help="commit even though this candidate id already has a decision "
                        "(audit/repair only — it overwrites the earlier snapshot); also "
                        "overrides the inconclusive-without-growth guard below")
    # graph.jsonl (#435): a MERGE candidate (integrate.py/funcmerge.py/merge_taskopt.py)
    # has 2+ parents this script has no other way to learn — those scripts produce a
    # merged artifact dir, not a commit. An ordinary edit's single parent is already
    # known (best_id at gate time, below) and needs no flag.
    p.add_argument("--parents", default=None,
                   help="comma-separated parent candidate ids, for a MERGE candidate "
                        "(2+ parents). Omit for an ordinary edit.")
    p.add_argument("--edit-kind", default=None, choices=["prompt", "code", "merge"],
                   help="graph.jsonl node kind; defaults to 'merge' when --parents has "
                        "2+ ids, else 'code'.")
    p.add_argument("--change-type", default=None, choices=list(CHANGE_TYPES),
                   help="dashboard badge for this edit's self-reported classification "
                        "(#665). Optional: when omitted, read from <from-dir>/"
                        "DIAGNOSIS.json's own 'change_type' field, else no badge is shown.")
    args = p.parse_args(argv)

    run_dir = RunDir.open(Path(args.run_dir))
    src = Path(args.from_dir)
    if not src.is_dir():
        print(json.dumps({"error": f"--from-dir does not exist: {src}"}, indent=2))
        return 2

    # Defensive: a workdir built by a bare `cp -r` (SKILL.md step 2's own documented pattern)
    # never gets LEDGER.md/JOURNAL.md/RUNMAP.md/PROCESS.md unless its source already had them.
    # This is snapshotted below (`run_dir.snapshot`), so guaranteeing it here also guarantees
    # every future candidate_dir built by copying THIS snapshot forward.
    harness.ensure_framework_memory(src, run_dir)

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
    provisional = args.decision == "provisional"

    # An inconclusive round is UNRESOLVED, not refuted — ``grow.py`` exists precisely to
    # resolve it by buying more trials on this same candidate, and issue #420 item 3 found
    # it had never run once across two real runs that hit this exact case. Making it
    # optional is why: the fix is a guard here, not a third restatement in SKILL.md prose
    # (the same argument round.py's own concurrency guard already makes). ``--force`` is
    # the deliberate override, for a candidate growth genuinely cannot help (e.g. Δ<=0).
    if indecisive and not args.force and not _has_grown(run_dir, args.candidate_id):
        print(json.dumps({
            "error": f"--decision inconclusive for {args.candidate_id!r}, but scripts/grow.py "
                     "has not bought it any extra trials yet",
            "why": "an inconclusive verdict means the measurement could not resolve the edit, "
                   "not that the edit was refuted. grow.py exists to buy more trials on this "
                   "SAME candidate and re-gate at the pooled n before it is left unresolved.",
            "fix": f"run scripts/grow.py --candidate {args.candidate_id} --growth-round 1 "
                   "--add-trials <n> first (it recommends promote/grow_again/abandon), then "
                   "commit its recommendation; or pass --force here if growth genuinely "
                   "cannot help this candidate (e.g. its delta is <= 0) and say why in --note.",
        }, indent=2))
        return 2

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
    # ``gate_verdict is None`` means no round table has a row for this candidate at all — no
    # gate ever ran. ``--reject-basis gate`` asserts a gate rejection happened; with no gate
    # row to back that up, that assertion is exactly as unsupported as the accept/inconclusive
    # cases above (found by review — the original check only handled the two DECIDED verdicts
    # and let the "nothing to attribute to" case slip through the same door it was built to
    # close).
    if args.reject_basis == "gate" and gate_verdict is None:
        print(json.dumps({
            "error": f"--reject-basis gate, but no round table has a gate row for "
                     f"{args.candidate_id} at all — nothing to attribute the rejection to",
            "gate_verdict": None,
            "fix": "pass --reject-basis driver_judgement and say in --note why you are "
                   "rejecting without a gate measurement (e.g. a micro-test failure, an "
                   "infra error, or a deliberate drop before ever evaluating it)",
        }, indent=2))
        return 2
    if args.reject_basis == "gate" and gate_verdict in ("accept", "inconclusive"):
        verb = ("ACCEPTED" if gate_verdict == "accept"
                else "could not resolve (verdict: inconclusive)")
        fix = ("pass --reject-basis drift_control if round.py's control_relative comparison "
               "against a same-round null-control replicate also says reject and is "
               "verdict-stable, or --reject-basis driver_judgement and say in --note why you "
               "are overriding the gate for some OTHER reason"
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
    # `--reject-basis drift_control`: the raw parent-relative gate accepted, but round.py's
    # control_relative comparison — the SAME round's byte-identical null-control replicate(s),
    # which removes drift since the parent was last measured — says reject and the verdict is
    # stable across whichever replicate is the reference. A real, structured disagreement
    # between the two comparisons (confirmed live: the driver had to fall back to
    # driver_judgement and hand-explain this exact situation in --note before this basis
    # existed), so it gets its own name rather than folding into the unstructured override.
    if args.reject_basis == "drift_control":
        ctl = _control_relative_verdict(run_dir, args.candidate_id)
        if ctl["verdict"] != "reject":
            print(json.dumps({
                "error": f"--reject-basis drift_control, but round.py's control_relative "
                         f"verdict for {args.candidate_id} is {ctl['verdict']!r}, not 'reject'",
                "control_relative": ctl,
                "fix": "pass --reject-basis driver_judgement instead and say why in --note, "
                       "or re-check work/round_*.json — this basis asserts the drift-corrected "
                       "comparison itself rejected",
            }, indent=2))
            return 2
        if ctl["stable"] is False:
            print(json.dumps({
                "error": f"--reject-basis drift_control, but {args.candidate_id}'s verdict is "
                         "NOT stable across the round's control replicates (verdict_stable: "
                         "false) — it flips depending on which byte-identical replicate is the "
                         "reference, so it is not evidence either way",
                "control_relative": ctl,
                "fix": "book it as --decision inconclusive instead and re-measure under a "
                       "FRESH tag",
            }, indent=2))
            return 2

    # The bare `driver_judgement` escape hatch: a candidate that never had a full-val gate
    # (gate_verdict is None, same condition `--reject-basis gate` above refuses on) AND never
    # had a screen.py record either has skipped the ENTIRE screen-then-gate structure — not an
    # override of a verdict that ran, but a candidate no measurement ever touched. Confirmed
    # live: a candidate was committed exactly this way, via `--reject-basis driver_judgement`
    # with no compliance or screen event on record for it at all. That is legitimate only when
    # said so explicitly, not as commit.py's silent default path.
    bypassed_screen_and_gate = bool(
        args.reject_basis == "driver_judgement" and gate_verdict is None
        and not _has_screen_record(run_dir, args.candidate_id))
    if bypassed_screen_and_gate and not args.bypassed_gate_justification:
        print(json.dumps({
            "error": f"--reject-basis driver_judgement for {args.candidate_id!r}, but it has "
                     "no full-val gate row AND no screen.py record — this is the "
                     "skip-screen-and-skip-gate escape hatch",
            "why": "driver_judgement is for overriding a gate verdict that DID run (see its "
                   "help text). Rejecting a candidate that was never screened OR gated needs "
                   "its own recorded reason, not a bare override.",
            "fix": "pass --bypassed-gate-justification \"<reason>\" explaining why neither "
                   "screen.py nor a full-val gate ran for this candidate before this commit "
                   "(e.g. an infra failure before any rollout, or a deliberate drop before "
                   "evaluating it at all).",
        }, indent=2))
        return 2

    # Precondition (#588): JOURNAL.md is the ONLY channel that carries a round's own
    # reasoning — not just its measured outcome — into the NEXT round, and the append step
    # was skipped often enough that a real ``optimizer_context_warning`` fired on some of a
    # run's most information-dense rounds, even though ``_reconcile_journal`` already
    # synthesizes a stub from ``--note`` as a fallback. A synthesized stub is strictly worse
    # than the optimizer's own entry, so hard-refuse here rather than let the fallback paper
    # over a skipped step — same shape as the screen-then-gate bypass above: a named escape
    # hatch that gets logged, not a silent default path. Does not apply to ``provisional``,
    # which books no iteration and never touches JOURNAL.md (see module docstring).
    handover = bool(harness.pending_handover(src, run_dir, args.candidate_id))
    if not provisional and not handover and not args.missing_handover_justification:
        print(json.dumps({
            "error": f"no JOURNAL.md handover found for {args.candidate_id!r} — commit.py "
                     "refuses to record this decision without one",
            "why": "the run-level JOURNAL.md is how the NEXT round learns what this one "
                   "tried and why; an empty handover breaks that even though the framework "
                   "can synthesize a stub from --note as a fallback.",
            "fix": f"append your entry to <from-dir>/JOURNAL.md as a "
                   f"'## Iteration {args.candidate_id} — <headline>' block (below the marker "
                   "line) and re-run commit.py, or pass --missing-handover-justification "
                   "\"<reason>\" if you are deliberately committing without one (e.g. an "
                   "infra failure before the optimizer had a chance to write it).",
        }, indent=2))
        return 2

    # Precondition (#611), same shape as the JOURNAL.md one above: DIAGNOSIS.json is the only
    # source of which failure cluster(s) this edit targeted and on which tasks. A real run
    # committed 0/17 candidates with one, so every graph.jsonl node carried empty
    # cluster_ids/subset and the dashboard's diagnosis view rendered nothing. Refuse rather
    # than silently book an unmapped change; a named escape hatch, logged as a warning.
    cluster_ids, diag_subset = _diagnosis_targets(src)
    change_type = args.change_type or _diagnosis_change_type(src)
    if not provisional and not cluster_ids and not args.missing_diagnosis_justification:
        print(json.dumps({
            "error": f"no real DIAGNOSIS.json found for {args.candidate_id!r} — commit.py "
                     "refuses to record this decision without one",
            "why": "DIAGNOSIS.json maps this change to the failure cluster(s) it targets and "
                   "the task subset it was aimed at; graph.jsonl's cluster_ids/subset and the "
                   "dashboard's diagnosis view are built from it. A missing or empty-template "
                   "file (no cluster with an id AND tasks) leaves both empty.",
            "fix": "write <from-dir>/DIAGNOSIS.json (schema in <from-dir>/PROCESS.md) with at "
                   "least one cluster {id, tasks: [...]} and edits naming the clusters they "
                   "target, and re-run commit.py, or pass --missing-diagnosis-justification "
                   "\"<reason>\" if you are deliberately committing without one.",
        }, indent=2))
        return 2

    # Precondition (#634), same shape again: the "Ranked issue list" is the round's survey of
    # the FULL remaining-failure landscape. A real run left it header-only on most candidates
    # and tunnel-visioned on 1-2 stubborn tasks while ~13 others sat unresolved. A merge
    # proposes nothing new (it combines already-surveyed parents), so it is exempt.
    is_merge = len([x for x in (args.parents or "").split(",") if x.strip()]) > 1 or \
        len((graph.latest_node(run_dir, args.candidate_id) or {}).get("parents") or []) > 1
    ranked_rows = _ranked_issue_rows(src)
    ranked_missing = not provisional and not is_merge and not ranked_rows
    if ranked_missing and not args.missing_ranked_issues_justification:
        print(json.dumps({
            "error": f"PROCESS.md's 'Ranked issue list' is empty for {args.candidate_id!r} — "
                     "commit.py refuses to record this decision without it",
            "why": "the ranked list is how each round re-surveys ALL current failures (clusters "
                   "by # failing tasks x trials) instead of fixating on 1-2 known-stubborn "
                   "tasks; a header-only table means no survey happened.",
            "fix": "fill <from-dir>/PROCESS.md's '## Ranked issue list' table with one row per "
                   "failure cluster in the current champion's val failures, and re-run "
                   "commit.py, or pass --missing-ranked-issues-justification \"<reason>\" if "
                   "you are deliberately committing without one.",
        }, indent=2))
        return 2

    # Precondition (#634): re-submitting an idea the gate already refuted, with cosmetic
    # variation ("cancel reason guard v2" after v1 failed), spends a full gate re-discovering
    # the same result. Same task targets as an earlier reject => say what is different.
    retry_of = ([] if provisional or is_merge
                else _refuted_retries(run_dir, args.candidate_id,
                                      (diag_subset or {}).get("task_ids") or []))
    if retry_of and not args.retry_justification:
        print(json.dumps({
            "error": f"{args.candidate_id!r} targets the same tasks as earlier candidate(s) the "
                     "gate already REJECTED — commit.py refuses a retry without saying what "
                     "is different this time",
            "refuted_priors": retry_of,
            "why": "a flat/negative result on these tasks is already measured; a near-variant "
                   "of the same component re-discovers it at the cost of a full gate.",
            "fix": "pass --retry-justification \"<one line: what is different this time>\" "
                   "(a different mechanism or root cause, not a rewording), or retarget "
                   "DIAGNOSIS.json at clusters from a fresh ranked issue list.",
        }, indent=2))
        return 2

    # The parent this candidate was gated against — ``gate_check --current`` defaults to
    # ``best_id``, so read it BEFORE ``set_best`` moves it.
    parent_id = run_dir.best_id or "seed"
    # None (not [parent_id]) when --parents is omitted, so record_iteration keeps the 2
    # parents round.py already recorded for a merge node it built (#438).
    parents = ([p.strip() for p in args.parents.split(",") if p.strip()]
               if args.parents else None)
    run_dir.snapshot(args.candidate_id, src)
    if accepted:
        run_dir.set_best(args.candidate_id)
    # Carry the proposer's own spend on the EVENT as well as into state.json. update_spent
    # alone leaves the dashboard's cost ledger unable to attribute it: state.json has the
    # total, but no cost-bearing event exists to explain it, so an agent-mode run reported
    # 100% of its optimizer spend as unattributed. opt_cost_usd/opt_tokens are the field
    # names the ledger already reads from headless optimizer backends.
    # The gate's NUMBERS, IN ADDITION to the prose --note, so the dashboard can render them
    # without regex-parsing a hand-typed string — read from round.py's persisted table, and
    # simply absent when it wrote none. On the EVENT as well as the step record below, because a
    # `provisional` decision never reaches record_iteration and would otherwise carry none.
    gate = _round_gate_numbers(run_dir, args.candidate_id)
    parent_val = gate.pop("parent_val", None)
    # #610: under host.py the proposer's spend is METERED, not guessed — the delta since this
    # session's previous checkpoint, read from claude-code's own session log (see meter.py).
    # A metered figure replaces the agent's self-report; USD is not knowable mid-session, so
    # host.py attributes it per candidate once the session's real total exists.
    metered = (meter.checkpoint(run_dir.root, time.time())
               if os.environ.get("CAPEVOLVE_HOST_METER") == "1" else None)
    meter_field = {}
    if metered is not None:
        args.optimizer_tokens = metered["tokens"]
        args.optimizer_seconds = round(metered["seconds"], 3)
        meter_field["opt_meter"] = metered["meter"]
    # #715: a conversational run has no host transcript, but Claude Code's own session log
    # (~/.claude/projects) has every message's usage. Harvest what is new since the previous
    # decision, deduped by message id, unless the host meter or the agent already accounted
    # for this round. USD is a list-price estimate; unpriced models are reported, not zeroed.
    harvested = None
    if (metered is None and not args.optimizer_usd and not args.optimizer_tokens
            and optimizer_cost.mode() != "off"):
        first_t, last_t = _decision_times(run_dir)
        since = (first_t if optimizer_cost.mode() == "session" else last_t) or first_t or 0.0
        harvested = optimizer_cost.harvest(
            run_dir, [run_dir.root.parent.parent, Path.cwd()], since)
        if harvested is not None:
            args.optimizer_usd = harvested["usd"]
            args.optimizer_tokens = harvested["tokens"]
            if not harvested["scoped"]:
                print("WARNING: CLAUDE_CODE_SESSION_ID unset - optimizer cost falls back to "
                      "ALL Claude sessions in this directory since the last decision (may "
                      "over-count other sessions).", file=sys.stderr)
    # #684 item 10: only fires when nothing else already accounted for the time (the host
    # meter above, or the agent's own --optimizer-* flags) — a real metered/self-reported
    # $0 round (e.g. a near-instant reject) is not a compliance problem.
    wallclock_elapsed = _wallclock_since_last_decision(run_dir)
    optimizer_cost_warning = None
    if (metered is None and harvested is None and not args.optimizer_seconds
            and not args.optimizer_usd and wallclock_elapsed is not None
            and wallclock_elapsed > _ZERO_OPTIMIZER_COST_WARN_S):
        optimizer_cost_warning = (
            f"{wallclock_elapsed:.0f}s elapsed since the previous decision but this commit "
            "carries optimizer_seconds=0/optimizer_usd=0 — pass --optimizer-seconds/"
            "--optimizer-usd/--optimizer-tokens for your own proposal cost (SKILL.md step 7).")
    run_dir.log_event(args.decision, candidate=args.candidate_id, val=args.val,
                      gate_verdict=gate_verdict, overrode_gate=overrode_gate,
                      note=args.note,
                      reject_basis=args.reject_basis,
                      bypassed_screen_and_gate=bypassed_screen_and_gate,
                      bypassed_gate_justification=args.bypassed_gate_justification,
                      retry_of=[h["candidate"] for h in retry_of] or None,
                      retry_justification=args.retry_justification if retry_of else None,
                      verdict=args.decision,
                      opt_cost_usd=args.optimizer_usd or None,
                      opt_tokens=args.optimizer_tokens or None,
                      opt_seconds=args.optimizer_seconds or None,
                      optimizer_cost_warning=optimizer_cost_warning,
                      opt_cost_basis="session_log_list_price_estimate" if harvested else None,
                      opt_cost_session_scoped=harvested["scoped"] if harvested else None,
                      opt_unpriced_tokens=(harvested or {}).get("unpriced_tokens") or None,
                      wallclock_since_last_decision=wallclock_elapsed,
                      **meter_field, **gate)
    run_dir.update_spent(optimizer_usd=args.optimizer_usd,
                         optimizer_tokens=args.optimizer_tokens,
                         optimizer_seconds=args.optimizer_seconds)
    # ``handover`` was already computed (and, absent a justification, enforced) above. Did the
    # agent write the INTENT half of its handover? ``_reconcile_journal`` (inside
    # record_iteration) folds ``<workdir>/JOURNAL.md`` into the run-level journal and, when
    # ``handover`` is False here, synthesizes an entry from ``--note`` instead of the silent
    # "(no handover written by the optimizer)" placeholder that every round of runs 32971129203
    # and 33046360451 recorded — see harness._reconcile_journal.
    reason = args.note or args.decision
    if indecisive:
        reason = f"indecisive (gate): {reason}"
    warnings: list[str] = []
    if optimizer_cost_warning:
        warnings.append(optimizer_cost_warning)
    if not provisional and not handover and args.missing_handover_justification:
        warnings.append(
            f"missing handover: {args.candidate_id!r} was committed with NO JOURNAL.md "
            "entry, justified as: "
            f"{args.missing_handover_justification!r} — the run-level JOURNAL.md will carry "
            "only a framework-synthesized stub for this round.")
    if not provisional and not cluster_ids and args.missing_diagnosis_justification:
        warnings.append(
            f"missing diagnosis: {args.candidate_id!r} was committed with NO real "
            "DIAGNOSIS.json, justified as: "
            f"{args.missing_diagnosis_justification!r} — its graph.jsonl node carries no "
            "cluster_ids and the dashboard shows no diagnosis for it.")
    if ranked_missing:
        warnings.append(
            f"missing ranked issues: {args.candidate_id!r} was committed with a header-only "
            "PROCESS.md 'Ranked issue list', justified as: "
            f"{args.missing_ranked_issues_justification!r}")
    if retry_of:
        warnings.append(
            f"refuted retry: {args.candidate_id!r} re-targets the tasks of rejected "
            f"{[h['candidate'] for h in retry_of]}, justified as: {args.retry_justification!r}")
    if bypassed_screen_and_gate:
        warnings.append(
            f"screen+gate bypass: {args.candidate_id!r} was rejected via driver_judgement "
            "with NO screen.py record and NO full-val gate row — justified as: "
            f"{args.bypassed_gate_justification!r}")
    # `provisional` books the decision event above but stops here: the iteration is not over
    # (the SAME candidate gets a real accept/reject/inconclusive commit later, once `grow.py`
    # has re-gated it at a pooled n), so the stall counter, LEDGER.md and JOURNAL.md must not
    # advance for it — that would spend an iteration's worth of "the run learned something new"
    # bookkeeping on a decision that has not actually been made yet. It files no memory record
    # either, for the same reason `inconclusive` does not: nothing has been refuted.
    if not provisional:
        memory_skill = _memory_skill_from_spec(run_dir)
        # The shared iteration step: charges iterations/stall, writes the canonical ``step``
        # record, reconciles the run-level JOURNAL.md. The gate's numbers ride along so the
        # dashboard's ``gate_decisions[]`` does not have to regex them out of an agent's prose.
        harness.record_iteration(run_dir, src, args.candidate_id, parent_id=parent_id,
                                 accepted=accepted, reason=reason,
                                 val=args.val,
                                 parent_val=parent_val,
                                 indecisive=indecisive, memory_skill=memory_skill,
                                 parents=parents, edit_kind=args.edit_kind,
                                 cluster_ids=cluster_ids, subset=diag_subset,
                                 change_type=change_type,
                                 opt_cost_usd=args.optimizer_usd or None,
                                 opt_tokens=args.optimizer_tokens or None,
                                 optimizer_seconds=args.optimizer_seconds or None,
                                 **gate)
        # Re-seed the framework's cross-iteration memory onto whichever candidate is now
        # $BEST, so the NEXT round's `cp -r "$R/candidates/$BEST" "$R/work/$TAG"` carries a
        # CURRENT copy forward — the round-2+ half of the fix in host.py's `_stage_context`
        # (which seeds round 1 the same way onto the seed candidate).
        # `record_iteration` above already folded THIS round's tail into the run-level journal
        # and wrote its `step` event, so the LEDGER/RUNMAP rebuilt here include this round.
        # Everything the staged CLAUDE.md pointer names, not JOURNAL.md alone: LEDGER.md,
        # RUNMAP.md and prior_iterations/<id>/diff.patch are the files the pointer (and
        # JOURNAL.md's own seed text) tell the agent to read, and re-seeding only the journal
        # is what left them absent for a whole run — see harness.seed_framework_memory.
        # Falls back to THIS candidate's own just-taken snapshot when there is no best_id yet
        # (a run with no baseline) — that dir always exists (``run_dir.snapshot`` above just
        # created it) — and is best-effort: losing the re-seed must not fail the commit.
        try:
            harness.resolve_memory(memory_skill).seed(
                run_dir.candidate_dir(run_dir.best_id or args.candidate_id), run_dir)
        except Exception as exc:  # noqa: BLE001
            run_dir.log_event("optimizer_context_warning", what="framework_memory",
                              error=str(exc)[:300])
        if indecisive:
            # The event the dashboard/TUI already read to render a step as `indecisive` rather
            # than rejected (``dashboard`` keys its status, badge and banner off this exact
            # kind), and the only thing that distinguishes an unresolved round from a refuted
            # one downstream.
            run_dir.log_event("step_indecisive", candidate=args.candidate_id, reason=reason,
                              val=args.val, gate_verdict=gate_verdict)
        else:
            # Deliberately NOT for an unresolved round: ``rejected.jsonl`` is fed back as "these
            # edits did not work", and an edit the measurement could not judge says nothing of
            # the kind — filing it there teaches the next round to avoid a change never
            # evaluated. Same reasoning as the deterministic hill-climb's own indecisive branch.
            _record_memory(run_dir, args.candidate_id, accepted=accepted,
                           reason=reason, val=args.val, parent_val=parent_val)
        # (missing-handover warning, if any, was already appended above — the precondition
        # earlier already refused the commit unless a justification was given.)
    spent = run_dir.spent
    run_dir.record_spend_warnings()
    stop, reason = run_dir.budget_exhausted()
    print(json.dumps({"decision": args.decision, "candidate": args.candidate_id,
                      "reject_basis": args.reject_basis,
                      "gate_verdict": gate_verdict,
                      "overrode_gate": overrode_gate,
                      "handover_recorded": handover,
                      "diagnosis_recorded": bool(cluster_ids),
                      "ranked_issue_rows": ranked_rows,
                      "warnings": warnings,
                      "best_id": run_dir.best_id, "spent": spent.to_dict(),
                      "stop": stop, "stop_reason": reason}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
