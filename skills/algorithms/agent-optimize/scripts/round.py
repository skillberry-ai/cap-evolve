"""round — evaluate a whole round's candidates PLUS a null control, then gate them.

Why this exists. Three things went wrong the same way in every prior agent-optimize run,
and all three are round-level bookkeeping the driver was doing by hand:

  1. **No null control.** A candidate's val mean was compared against a parent mean measured
     in an earlier round, so ordinary re-measurement noise looked like a signal in both
     directions. Three runs discovered this reactively, after the fact. Here the byte-identical
     copy ``ctl_null`` is a first-class member of every round, so the round reports its OWN
     noise floor and a candidate inside that band is visibly not evidence.
  2. **Serial evals wasted the wall clock.** A multi-turn agent rollout is tail-dominated (measured: 6 to
     40 minutes at ``max_steps=100``), so one candidate's full-val eval costs about as long as
     its slowest single rollout. Evaluating candidates one after another multiplies that tail by
     the number of candidates for no statistical benefit. Each eval is an independent process
     with its own adapter ``apply()``, so they parallelise safely — the reason this is a script
     and not prose is that ``apply()`` mutates a process-global registry, which is exactly the
     kind of footgun a driver should not have to remember.
  3. **The gate must stay serial.** ``set_best`` mutates run state, so gating is done after all
     evals land, one candidate at a time, re-reading ``best_id`` each time.

In front of the gate sits the default cascade (#437/#438, see ``merge_stage``): every candidate
is screened here unless a skip flag says why not, screen kills are never gated, disjoint
survivors are pairwise-merged and each merge screened, and every survivor is gated once. Each
step appends a ``graph.jsonl`` transition (#435).

This script does NOT commit. It prints the table; the driver reads it, decides, and calls
``commit.py`` — because choosing which part of a bundled edit to keep is a judgement that
belongs to the driver, and ``regressions`` is the input to it.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import _bootstrap  # noqa: F401  # side-effect import: seeds sys.path for cap_evolve

# Sibling script, imported for GATE_MODES: --mode is forwarded to it verbatim, so its list of
# accepted values is the only correct source for ours. Importable on the same terms as
# _bootstrap above — this directory is already on sys.path or that import would have failed.
import gate_check
import pregate

from cap_evolve import RunDir, eval_index, graph, harness, lineage, mdblocks, optimizer_config, posterior
from cap_evolve.gate import ParetoObjectiveError, _DEFAULT_PARETO_OBJECTIVES
from cap_evolve.pareto_archive import ArchivePoint, ParetoArchive
from cap_evolve.specfile import spec_for_run

#: Gate measurement concurrency. The default is deliberately low; the ceiling is where the
#: measured degradation is established (~0.08 at the arm level above 25, ~0.03 at 8), so above
#: it a verdict cannot resolve the effect the round is looking for and the round is refused.
DEFAULT_CONCURRENCY = 8
MAX_RESOLVING_CONCURRENCY = 25

#: Issue #676: round 1 of the abandoned multi-objective run defaulted to --max-parallel 2
#: (SKILL.md's own worked example), serializing a 3-candidate round for no reason — the
#: round only had 3 candidates, nowhere near enough to need throttling. Separately, a human
#: running 4 full-val evals BY HAND (outside round.py) at once hit real gateway
#: contention/timeouts. Both point at the same fix: --max-parallel should default to running
#: every candidate THIS round actually has, not a fixed low number, while the TOTAL
#: concurrent rollout requests across all of them stays under one shared ceiling — so N
#: candidates each get budget/N connections instead of N independent copies of
#: --concurrency (which is how the 4-at-once contention happened). ponytail: a flat number,
#: not measured per-gateway; raise it once real headroom is measured.
DEFAULT_TOTAL_CONCURRENCY_BUDGET = 24


def effective_concurrency(concurrency: int | None, max_parallel: int, budget: int) -> int | None:
    """Per-eval rollout concurrency when up to ``max_parallel`` evals run at once.

    Divides the shared TOTAL budget across the evals actually running concurrently (the
    ThreadPoolExecutor's own worker count), so ``max_parallel`` candidates never each
    independently open ``concurrency`` connections for ``max_parallel * concurrency`` total
    — the real-world failure mode this exists to prevent (#676). Never raises ``concurrency``
    above what was asked; only ever scales it down to fit the shared budget.
    """
    if not concurrency:
        return concurrency
    return max(1, min(concurrency, budget // max(1, max_parallel)))

#: issue #585: --skip-screen-justification stopped being a fresh per-candidate judgment and
#: became copy-pasted boilerplate ("consistent with cand_1/2/...", "...consistent with prior
#: rounds", "...per prior rounds cand_2-...") — every candidate from the second on skipped the
#: cheap screen and paid full-val (300 rollouts) instead of 8-25, and full-val rejected most of
#: them anyway. Measured on the issue's own examples with difflib.SequenceMatcher: real boilerplate
#: variants (same template, different candidate list tacked on) score 0.80-0.99; a justification
#: describing THIS candidate's actual edit surface scores 0.09-0.3 against them. 0.75 sits well
#: inside that gap.
JUSTIFICATION_SIMILARITY_THRESHOLD = 0.75

#: issues #630/#631: run-wide budgets for declining a step of the default cascade. Wording-based
#: checks (#585/#613's near-duplicate detector) were defeated by an optimizer that held the SAME
#: strategy — always skip — while varying the sentence every round (12/16 candidates unscreened,
#: 7/9 rounds `--no-merge`). A count cannot be reworded. Each budget is how many times a run may
#: decline that step WHEN IT APPLIED; once spent, round.py refuses with no override flag, because
#: whether the step pays is arithmetic (the frozen screening_economics; a merge costs one subset
#: screen and saves a full-val gate), not a judgement to re-argue every round. Per-benchmark
#: overrides live in capevolve.yaml (`max_screen_skips`, `max_merge_skips`).
DEFAULT_MAX_SCREEN_SKIPS = 1
DEFAULT_MAX_MERGE_SKIPS = 1

HERE = Path(__file__).resolve().parent
SKILLS = Path(os.environ.get("CAPEVOLVE_SKILLS_DIR", HERE.parents[2]))


def _events(run_dir, kind: str) -> list[dict]:
    """Every earlier ``kind`` event in this run. Read straight from ``events.jsonl`` — the file
    ``log_event`` appends to — so this sees every earlier round of THIS run, not just this
    process's own candidates, and needs no state file of its own.
    """
    if not run_dir.events_path.exists():
        return []
    out = []
    for line in run_dir.events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("kind") == kind:
            out.append(rec)
    return out


def _compliance_events(run_dir) -> list[dict]:
    return _events(run_dir, "agent_optimize_compliance")


def _prior_screen_skips(run_dir) -> set[str]:
    """Tags that already went to full val UNSCREENED under a skip flag (#631's budget unit).

    Distinct tags, so re-gating a candidate already charged does not charge it again. A
    candidate refused for having no skip flag is logged too, and is not a skip.
    """
    return {rec.get("tag") for rec in _compliance_events(run_dir)
            if not rec.get("screened_before_fullval")
            and (rec.get("skip_screen_ladder") or (rec.get("skip_justification") or "").strip())}


def _prior_merge_skips(run_dir) -> set[tuple]:
    """Rounds that passed ``--no-merge`` while a merge applied (#630's budget unit), keyed by
    candidate set so re-running the same round does not charge it twice."""
    return {tuple(sorted(rec.get("candidates") or []))
            for rec in _events(run_dir, "agent_optimize_round_batch")
            if rec.get("no_merge") and rec.get("merge_eligible_pairs")}


def _budget(spec: dict, key: str, default: int) -> int:
    v = spec.get(key)
    return default if v is None else max(0, int(v))


def _prior_skip_justifications(run_dir) -> list[tuple[str, str]]:
    """(tag, skip_justification) for every earlier compliance event with a non-empty one."""
    return [(rec.get("tag"), rec["skip_justification"].strip())
            for rec in _compliance_events(run_dir)
            if (rec.get("skip_justification") or "").strip()]


def _near_duplicate_justification(justification, prior):
    """Tag of the most similar prior justification, if its similarity clears
    ``JUSTIFICATION_SIMILARITY_THRESHOLD``, else ``None``.

    ``difflib.SequenceMatcher`` (stdlib, no new dependency — CONTRIBUTING.md's zero-runtime-deps
    rule) rather than an embedding model: the issue's own evidence is literal copy-pasted
    sentences, which a character-level ratio catches directly and cheaply.
    """
    if not justification or not justification.strip():
        return None
    best_tag, best_ratio = None, 0.0
    for tag, prior_just in prior:
        ratio = difflib.SequenceMatcher(None, justification.strip().lower(),
                                         prior_just.lower()).ratio()
        if ratio > best_ratio:
            best_tag, best_ratio = tag, ratio
    return best_tag if best_ratio >= JUSTIFICATION_SIMILARITY_THRESHOLD else None


def _all_tables(run_dir) -> list[tuple[int, int, Path]]:
    """Every round table on disk as (iteration, attempt, path), oldest first.

    The name is matched strictly rather than by glob: ``round_i1*.json`` also matches
    ``round_i10.json``, so a glob would count iteration 10's tables as re-gates of iteration 1
    and shift every name in this round — quietly, and worse the further a run gets.
    """
    work = run_dir.root / "work"
    if not work.is_dir():
        return []
    found = []
    for path in work.iterdir():
        if not path.is_file():
            continue
        m = re.fullmatch(r"round_i(\d+)(?:\.r(\d+))?\.json", path.name)
        if m:
            found.append((int(m.group(1)), int(m.group(2) or 0), path))
    return sorted(found)


def _round_tables(run_dir) -> list[tuple[int, Path]]:
    """This iteration's tables as (attempt, path), lowest attempt first."""
    it = int(run_dir.spent.iterations)
    return [(att, path) for i, att, path in _all_tables(run_dir) if i == it]


def round_attempt(run_dir) -> int:
    """How many times this iteration has already been gated: 0 for the first attempt.

    A round's identity is (iteration, attempt), and BOTH halves have to reach the names on
    disk. The table already had the attempt half — a same-iteration re-run is written
    ``round_i1.r1.json`` rather than overwriting ``round_i1.json`` — but the control ROLLOUTS
    did not, so the one operation this script explicitly supports re-measured the previous
    attempt's control under the same tag and deleted the numbers the first table cites.
    Counting the tables here is what keeps the two halves in agreement.
    """
    tables = _round_tables(run_dir)
    # max+1 rather than len, so a hand-deleted table cannot hand out a name that is still taken.
    return max((att for att, _ in tables), default=-1) + 1


def table_stem(run_dir) -> str:
    """Filename stem for this attempt's table: ``round_i1``, then ``round_i1.r1``, …"""
    it = int(run_dir.spent.iterations)
    a = round_attempt(run_dir)
    return f"round_i{it}" if a == 0 else f"round_i{it}.r{a}"


def control_tag(run_dir) -> str:
    """Round-scoped control tag, e.g. ``ctl_null_i2`` — and ``ctl_null_i2a1`` on a re-gate.

    Rollout files are ``<task>__<tag>__t<k>.json``, so a fixed ``ctl_null`` tag makes each
    round's control OVERWRITE the previous round's on disk — destroying the one measurement
    that proves what zero change looked like at that point in the run. The noise floor is
    evidence, and it is per-round (it moves with the parent and with the provider's mood),
    so it gets its own tag per iteration.

    The same argument applies WITHIN an iteration, which is what the ``a<k>`` suffix is for. A
    re-gate is normally run to buy MORE evidence about the same round, and without the suffix it
    bought none: on run 33046360451 the second attempt at iteration 1 re-measured
    ``ctl_null_i1`` (0.4967 -> 0.5067) and ``ctl_null_i1r1`` (0.4800 -> 0.4367) under those exact
    tags, spending 200 metric calls to swap two readings for two others. The round's replicate
    spread went 0.0167 -> 0.0700 and ``round_i1.json`` was left quoting an ``evidence_bar``
    computed from two numbers that no longer existed. With the suffix the attempts accumulate,
    ``prior_attempt_controls`` pools them, and the re-gate gets the four samples it paid for.
    """
    it = int(run_dir.spent.iterations)
    a = round_attempt(run_dir)
    return f"ctl_null_i{it}" if a == 0 else f"ctl_null_i{it}a{a}"


def prior_attempt_controls(run_dir) -> list[dict]:
    """Control replicates measured by EARLIER attempts at this same iteration.

    Read from those attempts' tables rather than from rollouts, because the table is the record
    that survives: a pre-fix run has tables whose rollouts were already overwritten, and the
    table is then the only place the destroyed reading still exists.

    They are byte-identical copies of the same parent measured in the same round, so they are
    samples of the same null and belong in it. Pooling them is the entire point of re-gating.
    """
    out: list[dict] = []
    for att, path in _round_tables(run_dir):
        try:
            table = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(table, dict):
            continue
        for row in table.get("control_replicates") or []:
            if isinstance(row, dict) and row.get("reward") is not None:
                out.append({**row, "from_attempt": att})
    return out


def measurement_context(split: str, n_trials: int, concurrency: int | None) -> dict:
    """What a control replicate's reward is only comparable WITHIN.

    Recorded in the table so a later round can tell whether an existing replicate was measured
    under the same conditions. Trial count and load both move the reading — the concurrency
    numbers this script refuses above are exactly that effect — so a replicate measured at a
    different n or a different load is not a sample of this round's null.
    """
    return {"split": split, "n_trials": int(n_trials), "concurrency": concurrency}


def prior_round_settings(run_dir) -> dict | None:
    """The most recent EARLIER iteration's ``--concurrency``/``--max-parallel``, or ``None``.

    Issue #420 item 9: round 3 of a real run got ``--max-parallel`` 4 (the default) after
    rounds 1-2 both explicitly passed 2, doubling how many candidate evals ran concurrently
    against the same target — a load change that makes the round's own noise floor
    incomparable with the rounds before it, and nobody noticed because nothing was recorded
    to notice it from.
    """
    it = int(run_dir.spent.iterations)
    for i, _att, path in reversed(_all_tables(run_dir)):
        if i >= it:
            continue
        try:
            table = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        return {"concurrency": table.get("measurement_concurrency"),
                "max_parallel": table.get("measurement_max_parallel")}
    return None


def parallel_drift_warning(prior: dict | None, concurrency: int | None,
                           max_parallel: int) -> str | None:
    """Did this round's load settings drift from the previous round's, unannounced?

    ``None`` on a prior round that never recorded ``max_parallel`` (a table written before
    this field existed) — a missing measurement is not evidence of drift.
    """
    if not prior:
        return None
    if prior["concurrency"] in (None, concurrency) and prior["max_parallel"] in (None, max_parallel):
        return None
    return (f"this round used --concurrency {concurrency} --max-parallel {max_parallel}, but "
            f"the previous round used --concurrency {prior['concurrency']} --max-parallel "
            f"{prior['max_parallel']}. Gate settings that drift between rounds make the "
            "rounds' noise floors incomparable — confirm this was a deliberate change.")


def _rollouts_present(run_dir, tag: str, split: str, n_trials: int) -> bool:
    """Are ``tag``'s persisted rollouts still on disk at the trial depth this round needs?

    Rollouts are ``<task>__<tag>__t<k>.json`` for k in range(n_trials), so the presence of the
    LAST index is what says the measurement went as deep as this round is asking for.
    """
    d = run_dir.rollouts / split
    return d.is_dir() and any(d.glob(f"*__{tag}__t{n_trials - 1}.json"))


def reusable_controls(run_dir, best: str, measurement: dict, want: int) -> dict | None:
    """Control replicates of THIS SAME parent, already measured in an EARLIER iteration.

    A null control is a byte-identical copy of the parent, re-measured to establish the round's
    noise floor. When ``best_id`` has not moved, the parent is the same bytes as it was, so its
    noise floor has already been paid for and re-measuring it buys nothing: across six real runs
    the controls consumed about 40% of every rollout spent, nearly as much as all candidates
    combined. Reuse only removes the redundant re-measurement — the requirement itself is
    untouched. A NEW parent (any accept) has no established floor and must be measured fresh,
    which is what the ``parent.tag`` check below enforces.

    Reuse requires ALL of:

    * an earlier iteration's table whose ``parent.tag`` is the current ``best`` — i.e. the same
      parent bytes were the parent then, so nothing has been accepted since;
    * the same ``measurement`` context (split, trials, concurrency): a reading taken at a
      different n or load is not a sample of this round's null;
    * at least ``want`` replicates with a reward, all of whose rollouts are still on disk —
      the gate re-reads them, so a pruned run dir falls back to measuring.

    The most recent qualifying iteration wins. Returns None when nothing qualifies, which is the
    signal to measure.
    """
    it = int(run_dir.spent.iterations)
    for i, _att, path in reversed(_all_tables(run_dir)):
        if i >= it:
            continue                      # this iteration's own attempts: prior_attempt_controls
        try:
            table = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(table, dict):
            continue
        if (table.get("parent") or {}).get("tag") != best:
            continue
        if table.get("measurement") != measurement:
            continue
        rows = [r for r in (table.get("control_replicates") or [])
                if isinstance(r, dict) and r.get("reward") is not None and r.get("tag")]
        if len(rows) < want:
            continue
        if not all(_rollouts_present(run_dir, r["tag"], measurement["split"],
                                     measurement["n_trials"]) for r in rows):
            continue
        return {"from_iteration": i, "from_table": str(path),
                "tags": [str(r["tag"]) for r in rows]}
    return None


def _eval_env(concurrency: int | None) -> dict:
    env = dict(os.environ)
    if concurrency:
        # Canonical, benchmark-neutral name. A runner whose knob predates this convention gets it
        # through CAPEVOLVE_CONCURRENCY_ENV (comma-separated extra names), so nothing here is
        # specific to one benchmark's environment variable.
        env["CAPEVOLVE_MAX_CONCURRENCY"] = str(concurrency)
        for name in [n.strip() for n in
                     os.environ.get("CAPEVOLVE_CONCURRENCY_ENV", "").split(",") if n.strip()]:
            env[name] = str(concurrency)
    return env


def _run_json(cmd: list[str], tag: str, concurrency: int | None) -> dict:
    p = subprocess.run(cmd, capture_output=True, text=True, env=_eval_env(concurrency))
    try:
        return {"tag": tag, "rc": p.returncode, **json.loads(p.stdout)}
    except Exception:  # noqa: BLE001
        return {"tag": tag, "rc": p.returncode, "error": (p.stderr or p.stdout)[-800:]}


def _evaluate(run_dir: Path, project: Path, tag: str, split: str, n_trials: int,
              concurrency: int | None, ids: list[str] | None = None,
              trial_offset: int = 0) -> dict:
    """Run the evaluate phase for one tag in its own process (optionally a subset / top-up)."""
    cmd = eval_index.eval_cmd(run_dir, project, tag, split, n_trials, ids=ids,
                              trial_offset=trial_offset, skills_dir=SKILLS)
    return _run_json(cmd, tag, concurrency)


# --------------------------------------------------------------------------------------------
# The default cascade in front of the full-val gate (#437, #438):
#
#   screen every candidate  ->  drop screen kills  ->  pairwise-merge disjoint survivors
#   ->  screen each merge   ->  gate each survivor ONCE, inside the best merge that carries it
#
# Run v18 (17 iterations) is why this is code and not SKILL.md prose: 0/17 candidates were
# screened (the same boilerplate --skip-screen-justification every time), merge.py was never
# called once, and three hand-built sibling unions each paid a second full 300-rollout gate.
# A driver no longer has to REMEMBER either step; skipping the screen is the thing that now
# needs a flag, and every step writes a graph.jsonl transition so a skipped one is visible.
# --------------------------------------------------------------------------------------------


def load_plan(path: str | None) -> dict:
    """``--plan`` JSON: ``{tag: {ids, rationale, cluster_ids, edit_kind}}``, every key optional.

    ``ids`` is the screen subset THIS edit plausibly touches (list or comma string) and
    ``rationale`` says why; ``cluster_ids`` are the diagnose() clusters it targets, used to
    skip merging two alternative fixes of the same cluster. A tag with no entry is screened
    on screen.py's tier heuristic, which writes its own rationale.
    """
    if not path:
        return {}
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    plan = {}
    for tag, e in (raw or {}).items():
        e = dict(e or {})
        for key in ("ids", "cluster_ids"):
            v = e.get(key)
            if isinstance(v, str):
                e[key] = [i.strip() for i in v.split(",") if i.strip()]
        plan[str(tag)] = e
    return plan


def cluster_ids_for(run_dir, plan: dict, tag: str) -> list[str]:
    """The diagnose clusters ``tag`` targets: ``--plan``'s, else its own DIAGNOSIS.json (#611),
    read by the SAME parser commit.py's precondition uses, so the two can never disagree."""
    import commit

    return list((plan.get(tag) or {}).get("cluster_ids")
                or commit._diagnosis_targets(run_dir.root / "work" / tag)[0])


# --------------------------------------------------------------------------------------------
# Pre-gate validity check (#632). run_full's own work/replay_gold.py (gold actions replayed
# through the candidate's tools vs the pristine ones) flagged cand_13 4/30 BEFORE its gate; the
# agent read that as "expected", paid the 300-rollout gate, then carried the same guard into the
# bundle cand_15 and paid a second one. A benchmark-specific check like that is the agent's to
# write, so round.py cannot ship it — but once registered it is run here on EVERY tag's bytes
# (and every merge's) before any screen or eval, and a failure refuses the round. Running it on
# the bytes, not on provenance, is what catches a bundle that carries a known-invalid edit.
# --------------------------------------------------------------------------------------------

#: A nonzero diff count on the summary line replay_gold.py prints ("4 of 30 val tasks differ
#: from pristine under gold replay") counts as a failure even at exit 0 — that script, as
#: written in both real runs, never exits nonzero, so exit code alone would pass cand_13.
_DIFF_SUMMARY = re.compile(r"^\s*(\d+)\s+of\s+\d+\b.*\bdiffer", re.M | re.I)


def _pregate_check_path(run_dir) -> Path:
    return run_dir.root / "work" / "pregate_check.json"


def resolve_pregate_check(run_dir, cmd: str | None) -> str | None:
    """The run's registered pre-gate check command, registering ``cmd`` when given.

    Sticky: once registered it applies to every later round without the flag, so a check the
    agent wrote in round 6 cannot be forgotten in round 8 (cand_15's exact failure).
    """
    path = _pregate_check_path(run_dir)
    if cmd and cmd.strip():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"cmd": cmd.strip()}, indent=2), encoding="utf-8")
        return cmd.strip()
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("cmd") or None
    except (OSError, ValueError):
        return None


def run_pregate_check(cmd: str, cand_dir: Path) -> str | None:
    """Run ``cmd <cand_dir>``. ``None`` = valid; else the failure output (the reason)."""
    import shlex

    p = subprocess.run([*shlex.split(cmd), str(cand_dir)], capture_output=True, text=True)
    out = ((p.stdout or "") + (p.stderr or "")).strip()
    m = _DIFF_SUMMARY.search(p.stdout or "")
    if p.returncode != 0 or (m and int(m.group(1)) > 0):
        return f"rc={p.returncode}: {out[-800:]}"
    return None


def pregate_failure(run_dir, project, parent_tag: str, cand_dir: Path, cmd: str | None) -> str | None:
    """The built-in deterministic pre-gate (#708, ``ablation.pregate``) first, then the
    agent-registered check (#632). ``None`` = valid; else the reason. With the ablation off only
    the legacy check runs."""
    spec = spec_for_run(run_dir, project)
    if pregate.enabled(spec):
        cfg = spec.get("pregate") if isinstance(spec.get("pregate"), dict) else {}
        tk = cfg.get("toolkit")
        if tk and ".py:" in tk and not os.path.isabs(tk):  # path relative to the project dir
            tk = str(Path(project) / tk)
        cfg = {**cfg, "toolkit": tk}
        parent = run_dir.candidate_dir(parent_tag)
        try:  # a broken pre-gate must never crash the round (fail-open, loudly)
            res = pregate.run(
                cand_dir, parent if parent.is_dir() else None,
                fixtures=run_dir.root / "tool_fixtures.jsonl", toolkit=cfg.get("toolkit"),
                traces=[Path(t) for t in cfg.get("traces") or []],
                max_growth=None if cfg.get("max_policy_growth") is None
                else float(cfg["max_policy_growth"]),
                strict=bool(cfg.get("strict")), write_tools=cfg.get("write_tools"),
                tool_dirs=tuple(cfg.get("tool_paths") or ("tools",)))
        except Exception as e:  # noqa: BLE001
            res = {"ok": True, "failure": "", "warnings": [f"built-in pre-gate crashed: {type(e).__name__}: {e}"]}
        if res["warnings"]:  # surfaced in events.jsonl for the digest; never a refusal
            run_dir.log_event("agent_optimize_pregate_warning", tag=cand_dir.name,
                              warnings=res["warnings"])
        if not res["ok"]:
            return "built-in pre-gate: " + res["failure"]
    return run_pregate_check(cmd, cand_dir) if cmd else None


def known_invalid(run_dir) -> list[str]:
    """Tags an earlier round's pre-gate check already disqualified in this run."""
    if not run_dir.events_path.exists():
        return []
    tags = []
    for line in run_dir.events_path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("kind") == "agent_optimize_pregate_invalid" and rec.get("tag") not in tags:
            tags.append(rec.get("tag"))
    return tags


def latest_screen(run_dir, tag: str) -> dict | None:
    """The newest ``screens/<tag>__screenN.json`` payload (highest tier), or ``None``."""
    d = run_dir.root / "screens"
    files = sorted(d.glob(f"{tag}__screen*.json")) if d.is_dir() else []
    for f in reversed(files):
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
    return None


def _screen(run_dir: Path, project: Path, tag: str, *, ids: list[str] | None, tier: int,
            rationale: str | None, concurrency: int | None) -> dict:
    """screen.py on one tag, in its own process (same apply()-isolation reason as evals)."""
    cmd = [sys.executable, str(HERE / "screen.py"), "--run-dir", str(run_dir),
           "--project", str(project), "--candidate", str(Path(run_dir) / "work" / tag),
           "--tag", tag]
    cmd += ["--ids", ",".join(ids)] if ids else ["--tier", str(tier)]
    if rationale:
        cmd += ["--rationale", rationale]
    return _run_json(cmd, tag, concurrency)


def screen_summary(payload: dict | None, auto: bool) -> dict | None:
    if not payload:
        return None
    sub = payload.get("subset") or {}
    return {"decision": payload.get("decision"), "mean_delta": payload.get("mean_delta"),
            "se": payload.get("se"), "n": payload.get("n"), "tier": payload.get("tier"),
            "subset_ids": sub.get("ids"), "rationale": sub.get("rationale"),
            "fired": (payload.get("savings") or {}).get("fired", len(payload.get("fired_ids")
                                                                      or [])),
            "auto": auto}


def _paired(payload: dict) -> dict[str, float]:
    pair = payload.get("paired") or {}
    return dict(zip([str(i) for i in pair.get("ids") or []], pair.get("deltas") or []))


def _recorded_parents(run_dir, tag: str, best: str):
    """Parent recorded at creation (``prepare_candidate --parent``, #714) when set, else
    ``[best]`` (legacy). ``None`` (carry the prior record forward) if ``best`` is the tag
    itself -- the self-parent seen on cand_4. ``optimizer.ablation.dag_parallel: false`` / ``CAPEVOLVE_DAG_PARALLEL=0`` forces legacy."""
    prior = [p for p in (graph.latest_node(run_dir, tag) or {}).get("parents") or [] if p != tag]
    if prior and optimizer_config.enabled("dag_parallel", spec_for_run(run_dir)):
        return prior
    return [best] if best != tag else None


def keeps_parent_gain(merge_payload: dict, parent_payload: dict) -> bool:
    """Does the merge keep what ``parent`` showed on ITS OWN screened tasks?

    ``integrate.py``'s rule — verified per-branch gains do not compose, so measure after
    each addition — applied with the screens already paid for: on the tasks both screens
    measured, the merge's summed paired delta must be at least the parent's. Both deltas are
    against the same round parent, so they are directly comparable. No common task means no
    evidence the merge kept the gain, so the answer is no (the parent is then gated alone).
    """
    m, p = _paired(merge_payload), _paired(parent_payload)
    common = set(m) & set(p)
    return bool(common) and sum(m[i] for i in common) >= sum(p[i] for i in common) - 1e-9


def merge_canaries(parent_per_task: list, union_ids: list[str], seed: int) -> list[str]:
    """Fresh regression canaries for a merge screen, drawn from the WHOLE suite.

    docs/archive/agent-optimize-legacy/per-task-fanout.md's rule: a canary set that only covers what the branches aimed at
    cannot catch what the merge hit by accident. Tasks the parent passes that neither
    parent's screen covered, seeded, about a third of the union's size (screen.py's own
    holdout fraction).
    """
    import random

    taken = set(union_ids)
    passing = sorted(str(pt.get("task_id")) for pt in parent_per_task or []
                     if str(pt.get("task_id")) not in taken
                     and float(pt.get("reward") or 0.0) >= 1.0 - 1e-9)
    n = min(len(passing), max(1, round(0.34 * len(union_ids))))
    return sorted(random.Random(seed).sample(passing, n)) if n else []


def choose_merges(merges: list[dict]) -> tuple[list[str], dict[str, str]]:
    """Which built+screened merges to gate: each survivor is gated ONCE, in one artifact.

    A merge qualifies when its screen promoted AND it kept both parents' screened gains
    (``keeps_parent_gain``). Qualifying merges are taken greedily by screen mean Δ, each only
    if neither parent is already inside a chosen one — a matching, so no survivor's bytes
    are paid for twice at full val. Returns (chosen merge tags, {parent: merge it is in}).
    """
    ok = sorted((m for m in merges if m.get("qualifies")),
                key=lambda m: (-(m["screen"].get("mean_delta") or 0.0), m["tag"]))
    chosen, covered = [], {}
    for m in ok:
        a, b = m["parents"]
        if a in covered or b in covered:
            continue
        chosen.append(m["tag"])
        covered[a] = covered[b] = m["tag"]
    return chosen, covered


def dominated_siblings(base_dir: Path, work: Path, tags: list[str]) -> dict[str, str]:
    """{tag: sibling whose diff strictly contains it} among this round's tags (#633).

    A literal strict subset of a sibling's edit, against the same round parent, cannot show
    an effect its superset does not also carry, so paying it a full-val gate of its own is
    waste. Strict containment is acyclic, so a chain A < B < C keeps only C.
    """
    import merge as merge_mod

    return {a: b for a in tags for b in tags
            if a != b and merge_mod.diff_contained(base_dir, work / a, work / b)
            } if len(tags) >= 2 else {}


def mergeable_pairs(run_dir, plan: dict, survivors: list[str], best: str,
                    md_blocks: bool | None = None) -> tuple[list, list]:
    """(pairs merge_stage tries to build, pairs it skips as structurally conflicting).

    The ONE definition of "a merge applied this round", shared by merge_stage and #630's
    --no-merge budget, so the budget can never count a pair the merge stage would not try.

    Disjointness is GEPA's Appendix D mergeable-ness check (``merge_search.is_mergeable``):
    two siblings are attempted iff, for every module (file / per-function block — see that
    function), at most one of them diverged from the round's parent ``best`` (their common
    ancestor). This replaced an earlier same-diagnose-cluster heuristic that skipped siblings
    sharing a cluster WITHOUT ever looking at their files — the common real case (two children
    of one parent fixing the same cluster via different, disjoint files/components) was never
    even attempted under that heuristic (#684 item 4's confirmed gap).
    """
    import itertools

    import merge_search

    base_dir = run_dir.candidate_dir(best)
    work = run_dir.root / "work"
    pairs, skipped = [], []
    for a, b in itertools.combinations(sorted(survivors), 2):
        ca, cb = set(cluster_ids_for(run_dir, plan, a)), set(cluster_ids_for(run_dir, plan, b))
        check = merge_search.is_mergeable(work / a, work / b, base_dir, md_blocks=md_blocks)
        if not check["mergeable"]:
            skipped.append({"pair": [a, b], "reason": "both independently diverged from the "
                            f"round parent {best!r} on the same module(s) — a real edit "
                            "collision, not a complementary pair",
                            "conflicts": check["conflicts"]})
        else:
            pairs.append((a, b, ca, cb))
    return pairs, skipped


def merge_stage(run_dir, project: Path, best: str, survivors: list[str], plan: dict,
                concurrency: int | None, max_parallel: int,
                pregate_cmd: str | None = None, md_blocks: bool | None = None) -> dict:
    """Build, screen and select pairwise merges among this round's screen survivors (#438)."""
    import merge as merge_mod
    from cap_evolve import graph

    work = run_dir.root / "work"
    base_dir = run_dir.candidate_dir(best)
    parent_per_task = harness.split_result_from_rollouts(run_dir, best, "val").per_task or []
    seed = int(run_dir.read_splits().seed)
    screens = {t: latest_screen(run_dir, t) for t in survivors}
    merges = []
    pairs, skipped = mergeable_pairs(run_dir, plan, survivors, best, md_blocks)
    for a, b, ca, cb in pairs:
        tag = f"merge_{a}_{b}"
        built = merge_mod.build_merge_dir(base_dir, work / a, work / b, work / tag,
                                          md_blocks=md_blocks)
        if not built["built"]:
            skipped.append({"pair": [a, b], "reason": "edit collision",
                            "conflicts": built["conflicts"]})
            continue
        # #632: two valid parents can still compose into an invalid merge — check before its
        # screen spends a rollout, same as the round's own candidates.
        bad = pregate_failure(run_dir, project, best, work / tag, pregate_cmd)
        if bad:
            run_dir.log_event("agent_optimize_pregate_invalid", tag=tag, parents=[a, b],
                              output=bad)
            skipped.append({"pair": [a, b], "reason": "merge fails the pre-gate check",
                            "pregate_output": bad})
            continue
        harness.ensure_framework_memory(work / tag, run_dir)
        union = sorted(set((screens[a] or {}).get("subset", {}).get("ids") or [])
                       | set((screens[b] or {}).get("subset", {}).get("ids") or []))
        canary = merge_canaries(parent_per_task, union, seed)
        rationale = (f"pairwise merge of screen survivors {a} + {b}: union of both parents' "
                     f"screened tasks {union} + {len(canary)} fresh whole-suite regression "
                     f"canaries {canary} the parent passes")
        graph.append_node(run_dir, node_id=tag, parents=[a, b], status="proposed",
                          edit_kind="merge", cluster_ids=sorted(ca | cb), gate={},
                          note=rationale, merged_files=built["three_way_merged"])
        merges.append({"tag": tag, "parents": [a, b], "ids": sorted(set(union) | set(canary)),
                       "rationale": rationale, "cluster_ids": sorted(ca | cb)})

    with ThreadPoolExecutor(max_workers=max(1, max_parallel)) as pool:
        results = list(pool.map(
            lambda m: _screen(run_dir.root, project, m["tag"], ids=m["ids"], tier=1,
                              rationale=m["rationale"], concurrency=concurrency), merges))
    for m, res in zip(merges, results):
        payload = latest_screen(run_dir, m["tag"]) if not res.get("rc") else None
        m["screen"] = screen_summary(payload, auto=True) or {"error": res.get("error")}
        m["qualifies"] = bool(payload and payload.get("decision") == "promote"
                              and all(screens[p] and keeps_parent_gain(payload, screens[p])
                                      for p in m["parents"]))
        graph.append_node(run_dir, node_id=m["tag"], parents=m["parents"], status="screened",
                          gate={})
    chosen, covered = choose_merges(merges)
    for m in merges:
        if m["tag"] in chosen:
            continue
        m["not_gated_because"] = (
            "merge screen did not run" if "error" in m["screen"] else
            "merge screen killed it" if m["screen"].get("decision") == "kill" else
            "lost a parent's screened gain (composition cost) — its parents are gated alone"
            if not m["qualifies"] else
            "both parents already carried by a better-screening merge")
        if m["screen"].get("decision") != "kill":
            graph.append_node(run_dir, node_id=m["tag"], parents=m["parents"],
                              status="superseded", gate={}, reason=m["not_gated_because"])
    for parent, tag in covered.items():
        graph.append_node(run_dir, node_id=parent, parents=[best], status="superseded",
                          gate={}, merged_into=tag,
                          reason=f"its bytes are gated inside {tag}, never twice")
    return {"merges": merges, "skipped_pairs": skipped, "chosen": chosen,
            "subsumed": covered}


class GateCheckFailed(RuntimeError):
    """The gate did not run. That is NOT the same as a gate that decided against a candidate.

    On run 33492876620 round 3 this distinction did not exist. ``_gate`` returned
    ``{"error": ...}`` — a dict with every verdict key MISSING — and the caller ``.get()``s the
    keys it wants, so the table was written with ``reward``, ``gate_delta``, ``gate_threshold``
    and ``verdict`` all ``null`` for all three candidates AND the control, ``eval_rc: 0``,
    100/100 rollouts scored on disk. A row that reads "this candidate did not move" for a
    candidate nothing judged is the most expensive kind of wrong this script can be.
    """

    def __init__(self, tag: str, rc: int, detail: str):
        self.tag, self.rc, self.detail = tag, rc, detail
        super().__init__(
            f"gate_check.py failed for tag {tag!r} (rc={rc}): {detail}\n"
            "The round is NOT booked. Nothing was written to the round table, because a failed "
            "gate is not a verdict — fix the cause and re-run this round; the rollouts are "
            "already on disk, so re-gating costs nothing.")


def _objective_metrics(run_dir: RunDir, tags, split: str, names: set[str]) -> tuple[dict, dict]:
    """``({name: value}, {name: stderr})`` for every declared non-reward objective/constraint
    NAME this script can actually source, for ``--mode pareto``/``epsilon_constraint``
    (issue #684 items 1-2).

    Only "cost" is derivable today — ``harness.candidate_cost_objective`` is the only
    per-task secondary metric #676 persisted alongside reward (see its docstring for why
    latency/tokens are not). Any OTHER declared name is simply left out of both dicts, which
    makes ``gate.py``'s own ``ParetoObjectiveError`` fire with its existing "no value on this
    run" refusal — the same hard-refuse discipline gate.py already applies, not a new one
    invented here. ``tags`` may be a sequence (pooled control replicates), same as
    ``harness.split_result_from_rollouts``.
    """
    values, stderrs = {}, {}
    if "cost" in names:
        mean_c, se_c = harness.candidate_cost_objective(run_dir, tags, split)
        if mean_c is not None:
            values["cost"], stderrs["cost"] = mean_c, se_c
    return values, stderrs


def _gate(run_dir: Path, tag: str, k_se: float, mode: str, veto: bool,
          current: str | None = None, *, objectives: list | None = None,
          metrics_candidate: dict | None = None, metrics_current: dict | None = None,
          metrics_stderr_candidate: dict | None = None, metrics_stderr_current: dict | None = None,
          constraints: list | None = None) -> dict:
    """Run gate_check.py for one tag. ``objectives``/``metrics-*``/``constraints`` are forwarded
    verbatim for ``--mode pareto``/``epsilon_constraint`` (issue #684 items 1-2) — see
    ``_objective_metrics`` for where the candidate's own ``metrics_candidate`` values come from.
    """
    cmd = [sys.executable, str(HERE / "gate_check.py"), "--run-dir", str(run_dir),
           "--candidate", tag, "--k-se", str(k_se), "--mode", mode]
    if current:
        cmd += ["--current", current]
    if veto:
        cmd.append("--veto-regressions")
    if objectives is not None:
        cmd += ["--objectives", json.dumps(objectives)]
    if metrics_candidate is not None:
        cmd += ["--metrics-candidate", json.dumps(metrics_candidate)]
    if metrics_current is not None:
        cmd += ["--metrics-current", json.dumps(metrics_current)]
    if metrics_stderr_candidate is not None:
        cmd += ["--metrics-stderr-candidate", json.dumps(metrics_stderr_candidate)]
    if metrics_stderr_current is not None:
        cmd += ["--metrics-stderr-current", json.dumps(metrics_stderr_current)]
    if constraints is not None:
        cmd += ["--constraints", json.dumps(constraints)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    # A non-zero rc is a failure whether or not its stdout parses. gate_check.py's own two
    # `return 2` paths (no --current and no best_id; no rollouts for the tag) print WELL-FORMED
    # JSON, so `json.loads` succeeds on them and the old code handed the error dict straight
    # back as if it were a result. Checking rc first is what closes that second path — fixing
    # the --mode flag alone would have left it wide open.
    if p.returncode != 0:
        raise GateCheckFailed(tag, p.returncode, ((p.stderr or p.stdout) or "").strip()[-800:])
    try:
        return json.loads(p.stdout)
    except Exception as exc:  # noqa: BLE001
        raise GateCheckFailed(
            tag, p.returncode,
            f"exited 0 but stdout is not JSON: {(p.stdout or '').strip()[-800:]}") from exc


def gate_unless_eval_failed(ev: dict, run_dir: Path, tag: str, k_se: float, mode: str,
                            veto: bool, current: str | None = None, **gate_kwargs) -> dict:
    """Gate a tag, unless its own EVALUATION failed — then there was never anything to gate.

    The distinction the round needs and did not have. A candidate whose eval died has no
    rollouts, so ``gate_check.py`` exits 2 for a legitimate reason and the row belongs in the
    table carrying its ``eval_rc``/``eval_error``. A candidate whose eval SUCCEEDED and whose
    gate still failed is a framework bug, and the round stops.

    ``**gate_kwargs`` (``objectives``/``metrics_*``/``constraints``) are forwarded to ``_gate``
    verbatim — see its docstring.
    """
    try:
        return _gate(run_dir, tag, k_se, mode, veto, current, **gate_kwargs)
    except GateCheckFailed:
        if ev.get("rc") or ev.get("error"):
            return {}
        raise


def assert_rows_were_judged(rows: list[dict]) -> None:
    """Refuse to publish a round table row that no gate actually decided.

    The backstop for the invariant itself, independent of any particular cause: a row whose
    ``eval_rc`` is 0 was measured — its rollouts exist and were scored — so a missing reward can
    only mean the GATE failed. A row whose evaluation genuinely failed keeps its ``None`` and its
    ``eval_rc``/``eval_error``, because a real infrastructure failure must stay a REPORT rather
    than becoming a crash: that is the one case where "no verdict" is the honest answer.
    """
    unjudged = [r["tag"] for r in rows
                if r.get("reward") is None and not r.get("eval_rc") and not r.get("eval_error")]
    if unjudged:
        raise GateCheckFailed(
            ", ".join(unjudged), 0,
            "the evaluation succeeded (eval_rc 0, rollouts scored) but no gate verdict came "
            "back, so these rows would publish as 'no movement' for candidates nothing judged")


#: Minimum sibling candidates a round is expected to carry. Below this, going serial requires
#: a recorded reason — either an explicit justification or an auto-detected budget block from
#: spend.py — never a silent default. See `sibling_justification`.
MIN_SIBLINGS = 3


class SingleCandidateUnjustified(RuntimeError):
    """Fewer than MIN_SIBLINGS candidates with no recorded reason why.

    Audited runs (`.capevolve/run_20260928_v13_.../events.jsonl`,
    `.capevolve/run_20260924_v7_.../events.jsonl`) showed every single round proposing exactly
    one candidate, never the N>=3 SKILL.md step 2 already recommends — because the guidance was
    prose an agent could always skip under time pressure, and it always did. This is the
    edit-form table applied to the skill itself: where the agent has the criterion (can I
    afford 3?) and violates it regardless, the form that works is a guard in the code, not a
    fourth restatement in prose (issue tracked from PR #522 onward). The guard does not make 1
    candidate impossible — narrow_scope rounds and unaffordable budgets are real — it makes
    going serial require a REASON on the record, in events.jsonl, so it is auditable.
    """

    def __init__(self, n: int):
        super().__init__(
            f"{n} candidate(s) passed via --candidates, below the default MIN_SIBLINGS="
            f"{MIN_SIBLINGS}. agent-optimize's default is N>=3 sibling candidates per round "
            "(SKILL.md step 2) because every audited run that skipped this ran serially every "
            "round and paid for it in wall clock. Fix ONE of: "
            "(1) propose 3 siblings and pass --candidates cand_1,cand_2,cand_3; "
            "(2) pass --single-candidate-justification \"<why only 1 this round>\" (e.g. "
            "\"diagnose surfaced only one well-evidenced cluster this round\"); "
            "(3) pass --afford-check-file <path to spend.py's JSON output with --n-siblings "
            f"{MIN_SIBLINGS}> when it reports affordable: false — the block is then read "
            "automatically as the justification.")


def sibling_justification(n_candidates: int, explicit: str | None,
                          afford_check_file: str | None,
                          new_engine: bool = False) -> tuple[str | None, str | None]:
    """Resolve why this round runs below MIN_SIBLINGS, or raise if it cannot.

    Returns ``(justification, source)`` — both ``None`` when ``n_candidates`` already meets
    the default and no justification was needed. ``source`` is ``"explicit"`` or
    ``"afford_unaffordable"``, recorded on the round_batch event so a later audit can tell an
    agent's own reasoning from an automatically-detected budget block.
    """
    if n_candidates >= MIN_SIBLINGS:
        return None, None
    if new_engine:  # dag_parallel + active_eval: the ledger makes one good idea affordable
        return "new engine: no sibling minimum", "new_engine"
    if explicit and explicit.strip():
        return explicit.strip(), "explicit"
    if afford_check_file:
        try:
            data = json.loads(Path(afford_check_file).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise SingleCandidateUnjustified(n_candidates) from exc
        afford = data.get("afford", data) if isinstance(data, dict) else {}
        if isinstance(afford, dict) and afford.get("affordable") is False:
            blockers = afford.get("blockers") or ["no blockers listed"]
            return (f"spend.py reports {MIN_SIBLINGS} siblings unaffordable: "
                    + "; ".join(str(b) for b in blockers)), "afford_unaffordable"
    raise SingleCandidateUnjustified(n_candidates)


def _write_table(run_dir, work: Path, stem: str, attempt: int, out: dict) -> None:
    """Persist the round table as well as printing it.

    Until the table was persisted the ONLY copy lived on stdout, so whether a round's verdict
    survived depended on the driver remembering to redirect (run 32814848187). Per-iteration
    name for the same reason ``control_tag`` is per-iteration, and a same-iteration re-run gets
    a suffix rather than overwriting. The name comes from the SAME attempt index the control
    tags were built from, so the table and the rollouts it cites cannot disagree.
    """
    try:
        work.mkdir(parents=True, exist_ok=True)
        table = work / f"{stem}.json"
        n = attempt
        while table.exists():  # belt-and-braces: never overwrite a sibling attempt's table
            n += 1
            table = work / f"round_i{int(run_dir.spent.iterations)}.r{n}.json"
        table.write_text(json.dumps(out, indent=2), encoding="utf-8")
        out["table_path"] = str(table)
    except OSError as exc:  # noqa: BLE001 — the printed table is still the primary output
        out["table_write_error"] = str(exc)


def _next_steps(killed: list[str], merge: dict | None, dominated: dict | None = None) -> str:
    steps = ["read regressions, then commit.py --decision accept|reject|inconclusive per gated "
             "candidate — `inconclusive` for any row whose `verdict` is inconclusive, so the "
             "round is not recorded as refuting an edit it could not judge"]
    if killed:
        steps.append(f"commit each screen kill {killed} with --decision reject --reject-basis "
                     "screen_kill (it was never gated)")
    if merge and merge.get("chosen"):
        steps.append(f"a gated merge {merge['chosen']} needs no --parents: graph.jsonl already "
                     "records both; its parents "
                     f"{sorted(merge['subsumed'])} are inside it and need no commit of their "
                     "own (graph status `superseded`, `merged_into`)")
    if dominated:
        steps.append(f"{sorted(dominated)} were not gated: each one's diff is a strict subset of "
                     f"a sibling's ({dominated}, graph status `superseded`, `dominated_by`). If "
                     "its superset is rejected, the subset may still be worth gating alone in a "
                     "later round")
    return "; ".join(steps)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="round")
    p.add_argument("--run-dir", required=True)
    p.add_argument("--project", required=True)
    p.add_argument("--candidates", required=True,
                   help="comma-separated tags that already exist under $R/work/")
    p.add_argument("--n-trials", type=int, required=True)
    p.add_argument("--k-se", type=float, default=1.0)
    # choices= derived from gate_check.py's GATE_MODES verbatim: this value is forwarded to
    # _gate() and a value only one side accepts empties the whole round table (run 33492876620
    # round 3, `--mode val` — the caller meant `--split val`, which is the default anyway).
    # "pareto" and "epsilon_constraint" (issue #684 items 1-2) are first-class choices here:
    # _gate() forwards --objectives/--metrics-*/--constraints to gate_check.py, and --mode
    # pareto additionally builds/updates a persistent cap_evolve.pareto_archive.ParetoArchive
    # (see the gate stage below) rather than a one-shot pairwise comparison.
    p.add_argument("--mode", default="paired", choices=gate_check.GATE_MODES)
    p.add_argument("--split", default="val")
    p.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                   help="rollout concurrency per eval process (total = this x n_tags). Default "
                        "8, deliberately LOW, because the noise this script exists to expose is "
                        "largely load-induced and therefore fixable. Measured on byte-identical "
                        "code at identical seeds: mean per-task movement 0.250 at conc 25 vs "
                        "0.100 at conc 8, tasks moving 10/12 vs 5/12, arm-level |delta| 0.1167 "
                        "vs 0.0333. A gate at conc 25 cannot resolve any effect smaller than "
                        "0.08, which is larger than most real edits. Explore fast, gate slow.")
    p.add_argument("--max-parallel", type=int, default=None,
                   help="how many candidate evals run at once. Default: this round's own "
                        "candidate count (every tag passed to --candidates runs concurrently) "
                        "— never throttled down just because N is small. --concurrency is then "
                        "scaled down per eval (see --max-total-concurrency) so this is NOT "
                        "max_parallel independent copies of --concurrency.")
    p.add_argument("--max-total-concurrency", type=int, default=DEFAULT_TOTAL_CONCURRENCY_BUDGET,
                   help=f"shared ceiling on TOTAL concurrent rollout requests across every "
                        f"simultaneously-running eval this invocation starts (default "
                        f"{DEFAULT_TOTAL_CONCURRENCY_BUDGET}). --concurrency is divided across "
                        "the --max-parallel evals actually running at once rather than applied "
                        "to each independently, so running more candidates in parallel lowers "
                        "each one's own concurrency instead of multiplying the total load (#676: "
                        "4 full-val evals run by hand at once caused real gateway contention).")
    p.add_argument("--gate-against", choices=["parent", "control"], default="parent",
                   help="'control' pairs each candidate against THIS round's null control "
                        "instead of the stored parent rollouts. Use it whenever this round's "
                        "--n-trials differs from the trial count the parent was measured at: "
                        "the control is a byte-identical copy of the parent measured in this "
                        "same round at this same n, so pairing against it removes a precision "
                        "mismatch the parent comparison would silently carry into the delta.")
    p.add_argument("--veto-regressions", action="store_true")
    p.add_argument("--control-replicates", type=int, default=2,
                   help="how many byte-identical copies of the parent to evaluate. Default 2, "
                        "because ONE control cannot bound run-to-run noise: two identical "
                        "controls on identical seeds differed by 0.0800 paired on this "
                        "benchmark, enough to pass the gate on their own. The gap between the "
                        "replicates is the round's real bar.")
    p.add_argument("--allow-high-concurrency", action="store_true",
                   help="run the gate above MAX_RESOLVING_CONCURRENCY anyway. An explicit, "
                        "recorded choice: the verdicts cannot resolve a small effect")
    p.add_argument("--no-reuse-control", action="store_true",
                   help="measure fresh control replicates even when this parent's own replicates "
                        "already exist from an earlier round. Reuse is on by default and is "
                        "only ever applied when best_id has NOT changed since those replicates "
                        "were measured, so the same bytes are not re-measured every round; a new "
                        "parent always gets fresh ones.")
    p.add_argument("--no-control", action="store_true",
                   help="skip the null control (NOT recommended — you lose the noise floor)")
    p.add_argument("--steal-lock", action="store_true",
                   help="take over $R/driver.lock even if its holder looks alive or is on "
                        "another host (use only when that driver is known dead)")
    p.add_argument("--skip-screen-ladder", action="store_true",
                   help="run full-val on a candidate with no screen.py record for it. Unless "
                        "the run's frozen screening_structurally_uneconomical is true, each "
                        "such candidate spends the run-wide max_screen_skips budget "
                        f"(capevolve.yaml, default {DEFAULT_MAX_SCREEN_SKIPS}); once spent it is "
                        "refused, with no override (#631). Prefer "
                        "--skip-screen-justification, which records WHY.")
    p.add_argument("--skip-screen-justification", default=None,
                   help="same effect as --skip-screen-ladder (run full-val on a candidate with "
                        "no screen.py record), but records WHY screening was skipped on the "
                        "compliance event instead of just the bare choice — e.g. "
                        "'spend.py: break-even unreachable on this split size' or 'pure "
                        "additive READ tool, screening cost exceeds expected savings'. Spends "
                        "the same max_screen_skips budget: the reason is recorded, it never "
                        "buys an extra skip.")
    p.add_argument("--plan", default=None,
                   help="JSON file {tag: {ids, rationale, cluster_ids, edit_kind}} (every key "
                        "optional): the screen subset each candidate plausibly touches and WHY, "
                        "and the diagnose() clusters it targets. A tag with no entry is screened "
                        "on screen.py's --tier heuristic. Recorded on graph.jsonl.")
    p.add_argument("--screen-tier", type=int, default=1, choices=[1, 2, 3],
                   help="screen.py rung for the automatic screen of a tag with no --plan ids")
    p.add_argument("--no-merge", action="store_true",
                   help="skip the automatic pairwise merge of disjoint screen survivors; "
                        "every survivor is gated alone. When a merge APPLIED (2+ screened "
                        "survivors on disjoint clusters) this logs merge_compliance_warning "
                        "immediately and spends the run-wide max_merge_skips budget "
                        f"(capevolve.yaml, default {DEFAULT_MAX_MERGE_SKIPS}); once spent it is "
                        "refused, with no override (#630). A round where no merge applied "
                        "spends nothing.")
    p.add_argument("--pregate-check", default=None,
                   help="command run as `CMD <candidate_dir>` on every tag (and every merge) "
                        "before any screen or eval (#632) — e.g. `python $R/work/replay_gold.py`. "
                        "Nonzero exit, or a nonzero 'N of M ... differ' summary line, refuses "
                        "the round. Registered in $R/work/pregate_check.json on first use and "
                        "applied to every later round without the flag.")
    p.add_argument("--single-candidate-justification", default=None,
                   help=f"required (or --afford-check-file) when --candidates has fewer than "
                        f"{MIN_SIBLINGS} tags — free text, e.g. \"diagnose surfaced only one "
                        "cluster this round\". Recorded on the agent_optimize_round_batch "
                        "event so going serial is auditable, not silent.")
    p.add_argument("--afford-check-file", default=None,
                   help=f"path to spend.py's JSON output (run with --n-siblings {MIN_SIBLINGS}). "
                        "When it reports afford.affordable: false, that block is read as the "
                        "auto-detected justification for fewer than "
                        f"{MIN_SIBLINGS} candidates — no hand-typed reason needed.")
    return p


def main(argv=None) -> int:
    try:
        return _main(argv)
    except GateCheckFailed as exc:
        # A traceback would be loud enough, but the driver reads this output to decide what to do
        # next, so say it in the words the skill uses: the round is not booked, re-gating is free.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except SingleCandidateUnjustified as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except ParetoObjectiveError as exc:
        # Same hard-refuse discipline gate_check.py's own --mode pareto/epsilon_constraint
        # CLI path already uses (issue #684 items 1-2): a declared objective/constraint this
        # script cannot source a value for is refused, not silently gated on reward alone.
        print(json.dumps({"error": f"pareto/epsilon_constraint gate: {exc}"}, indent=2))
        return 2


def _main(argv=None) -> int:
    args = build_parser().parse_args(argv)

    # A gate too coarse to resolve its own verdict is refused, not warned about. Measured on
    # run 32861747778: the driver gated at --concurrency 100 after SKILL.md had told it "do not
    # raise it to buy wall clock", and this script's own table then carried "a verdict from this
    # round can therefore not resolve an effect smaller than roughly 0.08" while the run
    # continued and booked decisions anyway. The skill's own edit-form rule applies to the
    # skill: where the agent has the criterion and violates it regardless, the form that works
    # is a guard in the code, not a third restatement in prose. Refusal (not a silent clamp) is
    # already this script's idiom for an incoherent request — see --gate-against control
    # --no-control below.
    if args.concurrency and args.concurrency > MAX_RESOLVING_CONCURRENCY \
            and not args.allow_high_concurrency:
        print(json.dumps({
            "error": f"--concurrency {args.concurrency} exceeds {MAX_RESOLVING_CONCURRENCY}: "
                     "byte-identical code at identical seeds moves ~0.08 at this load versus "
                     "~0.03 at 8, so no verdict from the round could resolve an effect smaller "
                     "than the noise the concurrency itself adds",
            "fix": f"re-run with --concurrency {DEFAULT_CONCURRENCY} (buy wall clock with "
                   "fewer candidates per round, not with load), or pass "
                   "--allow-high-concurrency to record the trade deliberately",
        }, indent=2))
        return 2

    run_dir = RunDir.open(Path(args.run_dir))
    project = Path(args.project)
    work = Path(args.run_dir) / "work"
    work.mkdir(parents=True, exist_ok=True)
    best = run_dir.best_id
    if not best:
        print(json.dumps({"error": "no best_id in the run dir — run baseline first"}, indent=2))
        return 2
    try:
        lineage.acquire_driver_lock(run_dir.root, steal=args.steal_lock)
    except lineage.DriverBusy as e:
        print(json.dumps({"error": str(e)}, indent=2))
        return 2

    tags = [t.strip() for t in args.candidates.split(",") if t.strip()]
    try:  # #713 B7: a second launch on the same tag(s) fails fast instead of clobbering
        for t in tags:
            run_dir.run_lock(f"round_{t}")
    except RuntimeError as exc:
        print(json.dumps({"error": str(exc)}, indent=2))
        return 3
    missing = [t for t in tags if not (work / t).is_dir()]
    if missing:
        print(json.dumps({"error": f"tags not found under {work}: {missing}"}, indent=2))
        return 2

    # #676: default to running every candidate THIS round has, never a fixed low number —
    # the bottleneck was serializing small (2-3 candidate) rounds for no reason. An explicit
    # --max-parallel is always honored verbatim.
    if args.max_parallel is None:
        args.max_parallel = max(1, len(tags))
    EFFECTIVE_CONCURRENCY = effective_concurrency(
        args.concurrency, args.max_parallel, args.max_total_concurrency)

    # Default N>=3 sibling candidates per round, ENFORCED rather than merely recommended
    # (SKILL.md step 2) — see SingleCandidateUnjustified's docstring for why. Resolved before
    # any work-dir mutation or spend below, so an unjustified serial round fails fast with
    # nothing charged.
    NEW_ENGINE = optimizer_config.new_engine(spec_for_run(run_dir, project))
    if NEW_ENGINE and args.gate_against != "control":
        args.no_control = True  # ledger pooling replaces the per-round null control
    JUSTIFICATION, JUSTIFICATION_SOURCE = sibling_justification(
        len(tags), args.single_candidate_justification, args.afford_check_file, NEW_ENGINE)

    # #632: the registered pre-gate check (e.g. gold replay) is a HARD precondition, run on
    # every tag's bytes before any screen or eval is paid for. One invalid tag refuses the
    # whole round, the same idiom as the screen-ladder refusal below.
    PREGATE = resolve_pregate_check(run_dir, args.pregate_check)
    if PREGATE or pregate.enabled(spec_for_run(run_dir, project)):  # #708: built-in needs no registration
        prior_invalid = known_invalid(run_dir)
        invalid = {t: r for t in tags if (r := pregate_failure(run_dir, project, best, work / t, PREGATE))}
        for t, r in invalid.items():
            run_dir.log_event("agent_optimize_pregate_invalid", tag=t, output=r,
                              iteration=int(run_dir.spent.iterations))
        # #708: a sibling failing only the BUILT-IN pre-gate is dropped, not the whole round; the
        # legacy registered check (#632) still refuses the round, and so does "every tag invalid".
        builtin = {t: r for t, r in invalid.items() if r.startswith("built-in pre-gate:")}
        if builtin and len(builtin) == len(invalid) and len(builtin) < len(tags):
            tags = [t for t in tags if t not in builtin]
            print(json.dumps({"pregate_dropped": builtin}), file=sys.stderr)
            invalid = {}
        if invalid:
            print(json.dumps({
                "error": f"candidate(s) {sorted(invalid)} fail the run's pre-gate check "
                         f"({PREGATE!r}) — refused before any screen or full-val eval",
                "invalid": invalid,
                "known_invalid_earlier_in_run": prior_invalid,
                "why": "a nonzero gold-replay diff means the edit changes the target it is "
                       "scored against (cand_13 in run_full: 4/30 differ, one task spuriously "
                       "'fixed', one broken), so its score is not evidence about the edit. "
                       "A bundle carrying such an edit fails for the same reason — check "
                       "whether it contains any tag in known_invalid_earlier_in_run.",
                "fix": "drop the invalid edit (or the invalid component from the bundle) and "
                       "re-run; book a dropped tag with commit.py --decision reject "
                       "--reject-basis driver_judgement --bypassed-gate-justification "
                       "\"pre-gate check failed: <output>\".",
            }, indent=2))
            return 2

    # Defensive: a workdir built by a bare `cp -r` (SKILL.md step 2's own documented pattern)
    # never gets LEDGER.md/JOURNAL.md/RUNMAP.md/PROCESS.md unless its source already had them
    # — this guarantees them regardless of how each tag's dir came to exist.
    for t in tags:
        harness.ensure_framework_memory(work / t, run_dir)

    # Compliance instrumentation (issue #401): log, per candidate, whether screen.py was
    # invoked for it BEFORE this full-val eval — a distinct, auditable event rather than
    # something only inferable (or not) from SKILL.md prose. `screen.py` writes
    # `<run_dir>/screens/<tag>__screenN.json`; its absence means this candidate skipped
    # straight to full-val, which the dashboard can now show as its own event kind.
    screens_dir = run_dir.root / "screens"
    skip_justified = bool(args.skip_screen_ladder or args.skip_screen_justification)
    # issue #585: the justification text itself is compared against every earlier round's, so a
    # copy-pasted "reason" is visible on the recorded event rather than only inferable (or not)
    # from re-reading every round's prose by hand.
    near_dup_of = _near_duplicate_justification(
        args.skip_screen_justification, _prior_skip_justifications(run_dir))
    screened_by_tag = {t: screens_dir.is_dir() and any(screens_dir.glob(f"{t}__screen*.json"))
                       for t in tags}
    unscreened = [t for t in tags if not screened_by_tag[t]]
    # issue #631: a skip is priced by arithmetic, not argued in prose. The near-duplicate TEXT
    # refusal (#585/#613) was defeated by rewording every round while the strategy — always
    # skip — held constant, so similarity is now only RECORDED (justification_near_duplicate_of,
    # above), never enforced. Enforcement is the frozen screening_economics plus a COUNT:
    #   * structurally uneconomical (tier-1 break-even > SCREEN_BREAKEVEN_CEILING, i.e. a tiny
    #     val) — the arithmetic already settled it once, so a skip is unrestricted;
    #   * otherwise screening is mandatory, and at most max_screen_skips distinct candidates
    #     per run may reach full val unscreened. Past that it is refused — before any spend and
    #     before any compliance event, so a refused attempt is never itself counted — with
    #     deliberately NO override flag: a fresh justification is exactly what was gamed.
    spec = spec_for_run(run_dir, project)
    ECONOMICS = harness.freeze_screening_economics(run_dir, int(spec.get("num_trials") or 1))
    UNECONOMICAL = bool(ECONOMICS["screening_structurally_uneconomical"])
    MAX_SCREEN_SKIPS = _budget(spec, "max_screen_skips", DEFAULT_MAX_SCREEN_SKIPS)
    prior_skips = _prior_screen_skips(run_dir)
    screen_skips_used = len(prior_skips | (set(unscreened) if skip_justified else set()))
    if skip_justified and unscreened and not UNECONOMICAL \
            and screen_skips_used > MAX_SCREEN_SKIPS:
        print(json.dumps({
            "error": f"candidate(s) {unscreened} would reach full val unscreened, but this run "
                     f"already spent its max_screen_skips={MAX_SCREEN_SKIPS} budget on "
                     f"{sorted(prior_skips)} (this round would make it {screen_skips_used})",
            "why": "screening is NOT structurally uneconomical on this run (frozen at baseline: "
                   f"a tier-1 screen fires {ECONOMICS['tier1_fired']} rollouts against "
                   f"{ECONOMICS['full_val_rollouts']} for full val, break-even kill rate "
                   f"{ECONOMICS['breakeven_kill_rate']} <= {ECONOMICS['ceiling']}), so a skip is "
                   "a cost, not a judgement call (#631). There is no override flag: the budget "
                   "is a count, and no wording of a justification changes a count.",
            "fix": "drop --skip-screen-ladder/--skip-screen-justification: round.py then screens "
                   "these tags itself (tier 1), kills proven harm, and gates the survivors. To "
                   "allow more skips on this benchmark, raise max_screen_skips in capevolve.yaml "
                   "— a recorded per-benchmark decision, not a per-round one.",
            "screening_economics": ECONOMICS,
        }, indent=2))
        return 2
    if near_dup_of:
        print(f"NOTE: this skip repeats {near_dup_of}'s earlier in this run — recorded as "
              "justification_near_duplicate_of on the compliance event.", file=sys.stderr)

    # #437: the screen is the DEFAULT step, run here rather than left for the driver to
    # remember. Only a skip flag (within #631's skip budget, above) bypasses it.
    plan = load_plan(args.plan)
    auto_screened: dict[str, dict] = {}
    if unscreened and not skip_justified:
        with ThreadPoolExecutor(max_workers=max(1, args.max_parallel)) as pool:
            res = list(pool.map(lambda t: _screen(
                Path(args.run_dir), project, t, ids=(plan.get(t) or {}).get("ids"),
                tier=args.screen_tier, rationale=(plan.get(t) or {}).get("rationale"),
                concurrency=EFFECTIVE_CONCURRENCY), unscreened))
        for t, r in zip(unscreened, res):
            auto_screened[t] = r
            screened_by_tag[t] = not r.get("rc") and latest_screen(run_dir, t) is not None
        unscreened = [t for t in unscreened if not screened_by_tag[t]]

    # Screen KILLS leave the gate set: a kill is proven harm on the subset, and paying full val
    # to confirm it is the waste the screen exists to stop.
    screen_payloads = {t: latest_screen(run_dir, t) if screened_by_tag[t] else None for t in tags}
    killed = [t for t in tags if (screen_payloads[t] or {}).get("decision") == "kill"]
    survivors = [t for t in tags if t not in killed]
    # #633: a survivor whose diff is a STRICT subset of a sibling survivor's (same round, same
    # parent) is never gated on its own — purely structural, no eval spent to learn it. Taken
    # out BEFORE #630's merge-eligibility count, so a (subset, superset) pair is never charged
    # to max_merge_skips; its graph.jsonl transition is written below, after every refusal.
    dominated = dominated_siblings(run_dir.candidate_dir(best), work, survivors)
    survivors = [t for t in survivors if t not in dominated]

    # #630: --no-merge, priced like a screen skip. A merge APPLIED this round when merge_stage
    # would have run and found a pair to build — its own trigger condition and its own pair
    # rule (mergeable_pairs). Declining one is announced IMMEDIATELY (merge_compliance_warning,
    # stderr, the table's merge_skip) rather than once at finalize, when it can no longer change
    # anything, and counted; past max_merge_skips it is refused with no override — before any
    # compliance event or graph.jsonl transition, so a refused attempt leaves only its warning.
    # Obeying is free: the screens are on disk, and a pair that collides at build time is
    # skipped by merge_stage for zero rollouts. (An unscreened survivor means no merge applied,
    # so the screen budget above and this one never charge the same round twice.)
    merge_applies = len(survivors) >= 2 and all(screened_by_tag[t] for t in survivors)
    MD_BLOCKS = mdblocks.enabled(spec)  # #709 ablation: merge.md_blocks / CAPEVOLVE_MD_BLOCKS
    eligible_pairs = ([[a, b] for a, b, _, _ in mergeable_pairs(run_dir, plan, survivors, best, MD_BLOCKS)[0]]
                      if merge_applies else [])
    MERGE_SKIP = None
    if args.no_merge and eligible_pairs:
        max_merge_skips = _budget(spec, "max_merge_skips", DEFAULT_MAX_MERGE_SKIPS)
        prior_merge_skips = _prior_merge_skips(run_dir)
        merge_skips_used = len(prior_merge_skips | {tuple(sorted(tags))})
        refused = merge_skips_used > max_merge_skips
        MERGE_SKIP = {"reason": "no_merge_with_eligible_pairs", "realtime": True,
                      "candidates": list(tags), "disjoint_pairs": eligible_pairs,
                      "merge_skips_used": len(prior_merge_skips) if refused else merge_skips_used,
                      "max_merge_skips": max_merge_skips, "refused": refused,
                      "iteration": int(run_dir.spent.iterations)}
        run_dir.log_event("merge_compliance_warning", **MERGE_SKIP)
        if refused:
            print(json.dumps({
                "error": f"--no-merge declines merging screened, mergeable survivors "
                         f"{eligible_pairs}, and this run already spent its "
                         f"max_merge_skips={max_merge_skips} budget",
                "why": "a merge costs one subset screen and gates two survivors' bytes once "
                       "instead of twice; hand-building the same union later pays a THIRD "
                       "full-val gate (#630). There is no override flag: the budget is a count.",
                "fix": "re-run this exact command without --no-merge — the screens are already "
                       "on disk, so nothing is re-screened. To allow more on this benchmark, "
                       "raise max_merge_skips in capevolve.yaml.",
            }, indent=2))
            return 2
        print(f"WARNING: --no-merge declined merging {eligible_pairs} "
              f"({merge_skips_used}/{max_merge_skips} of this run's max_merge_skips); "
              "the next such round is refused. Logged as merge_compliance_warning.",
              file=sys.stderr)

    for t in tags:
        run_dir.log_event("agent_optimize_compliance", tag=t,
                          screened_before_fullval=screened_by_tag[t],
                          auto_screened=t in auto_screened and screened_by_tag[t],
                          skip_screen_ladder=bool(args.skip_screen_ladder),
                          skip_justification=args.skip_screen_justification,
                          justification_near_duplicate_of=near_dup_of,
                          screening_structurally_uneconomical=UNECONOMICAL,
                          screen_skips_used=screen_skips_used,
                          max_screen_skips=MAX_SCREEN_SKIPS,
                          iteration=int(run_dir.spent.iterations))

    # Made a hard refusal, not a logged fact: issue #420 item 4 found that EVERY candidate
    # in a whole run skipped screen.py, even the ones (`cand_scope`, harmful;
    # `cand_e2_verifytype`, flat) it exists to kill for a quarter of the price — because
    # using it was optional, so a real, working, cheap tool never ran once. The compliance
    # event above already proved this cannot be caught after the fact by inference; making
    # it a warning would just be a third restatement of the same prose SKILL.md already
    # carried. `--skip-screen-ladder` is the deliberate, recorded override (e.g. a
    # candidate whose val is small enough that screening buys nothing).
    # Since #437 round.py screens every such candidate itself, so reaching this means that
    # automatic screen FAILED (e.g. the parent has no val rollouts to pair against).
    if unscreened and not skip_justified:
        print(json.dumps({
            "error": f"candidate(s) {unscreened} went straight to a full-val eval without a "
                     "screen.py record under $R/screens/ — round.py's automatic screen failed",
            "screen_errors": {t: (auto_screened.get(t) or {}).get("error") for t in unscreened},
            "why": "screen.py triages a candidate on a cheap val SUBSET before this full-val "
                   "eval is paid — see its own docstring. Skipping it because it is optional "
                   "is the exact failure issue #420 item 4 found: every candidate paid full "
                   "val, including ones a quarter-price screen would have killed.",
            "fix": "run screen.py --tier 1 (then --tier 2 if it promotes) on each of these "
                   "tags first, or pass --skip-screen-justification \"<reason>\" to record WHY "
                   "screening was skipped (e.g. break-even unreachable on this split size per "
                   "spend.py, or a zero-risk additive edit where screening costs more than it "
                   "could save) — or the bare --skip-screen-ladder if you don't want a reason "
                   "recorded.",
        }, indent=2))
        return 2

    # Screen results -> graph.jsonl (kills were already taken out of `survivors`, above).
    from cap_evolve import graph

    input_tags = list(tags)
    screen_stage = {}
    node_parents = {t: _recorded_parents(run_dir, t, best) for t in tags}
    for t in tags:
        payload = screen_payloads[t]
        screen_stage[t] = screen_summary(payload, auto=t in auto_screened)
        if payload is None:
            continue
        graph.append_node(run_dir, node_id=t, parents=node_parents[t], status="screened", gate={},
                          cluster_ids=cluster_ids_for(run_dir, plan, t),
                          edit_kind=(plan.get(t) or {}).get("edit_kind"))

    for t, sup in dominated.items():
        graph.append_node(run_dir, node_id=t, parents=node_parents.get(t), status="superseded", gate={},
                          dominated_by=sup,
                          reason=f"its diff is a strict subset of sibling {sup}'s, which is "
                                 "gated instead")

    # #438: pairwise merges of disjoint survivors, each screened, BEFORE any full-val gate.
    MERGE = None
    if not args.no_merge and merge_applies:
        MERGE = merge_stage(run_dir, project, best, survivors, plan, EFFECTIVE_CONCURRENCY,
                            args.max_parallel, pregate_cmd=PREGATE, md_blocks=MD_BLOCKS)
        for m in MERGE["merges"]:
            node_parents[m["tag"]] = m["parents"]
        tags = [t for t in survivors if t not in MERGE["subsumed"]] + MERGE["chosen"]
    else:
        tags = survivors

    # The null control is built here, not by the driver, so it cannot silently be skipped
    # or accidentally differ from the parent.
    # Derive the round's identity ONCE: the table name and the control tags are two halves of
    # it, and independently derived halves can disagree about which attempt this is.
    ATTEMPT = round_attempt(run_dir)
    STEM = table_stem(run_dir)
    PRIOR_CTL = prior_attempt_controls(run_dir)
    CTL = control_tag(run_dir)
    MEASUREMENT = measurement_context(args.split, args.n_trials, EFFECTIVE_CONCURRENCY)
    # One shared identifier for every candidate THIS invocation gates, so the dashboard can
    # group same-round candidates instead of showing them as if they had run sequentially
    # (they are gated together but committed one at a time, serially, by the driver).
    # Logged as its own event, decoupled from commit.py's per-candidate bookkeeping: by the
    # time a later candidate in this same round is committed, `record_iteration` may already
    # have advanced `spent.iterations` for an earlier one, so re-deriving this round's stem
    # from a candidate's OWN commit-time iteration count would rename it out from under the
    # candidates committed after the first. STEM is already unique per invocation
    # (iteration + attempt), so it doubles as the batch id — no separate id needed.
    run_dir.log_event("agent_optimize_round_batch", batch_id=STEM, candidates=input_tags,
                      n_candidates=len(input_tags),
                      single_candidate_justification=JUSTIFICATION,
                      single_candidate_justification_source=JUSTIFICATION_SOURCE,
                      gated=list(tags), screen_killed=killed, dominated=dominated,
                      merge_candidates=[m["tag"] for m in (MERGE or {}).get("merges", [])],
                      merges_gated=(MERGE or {}).get("chosen", []),
                      no_merge=bool(args.no_merge), merge_eligible_pairs=eligible_pairs)
    CASCADE = {
        "screen_stage": screen_stage,
        "screen_killed": killed,
        "dominated": dominated,
        "merge_stage": MERGE,
        "merge_skip": MERGE_SKIP,
        "gated": list(tags),
        "reading": ("every candidate is screened first (round.py runs screen.py itself unless a "
                    "skip flag is passed), screen kills are never gated, disjoint survivors are "
                    "pairwise-merged and the merge screened, and each survivor is gated ONCE — "
                    "inside the chosen merge that carries it, or alone"),
    }
    if not tags:
        out = {"attempt": ATTEMPT, "batch_id": STEM, "candidates": [], "control": None,
               "control_replicates": [], **CASCADE,
               "next": _next_steps(killed, MERGE, dominated)}
        _write_table(run_dir, work, STEM, ATTEMPT, out)
        print(json.dumps(out, indent=2))
        return 0
    ctl_tags: list[str] = []
    REUSED = None
    # Not under --gate-against control: that mode's whole premise is a control measured
    # CONCURRENTLY with the candidates, so that the drift between the two cancels. A reused
    # replicate is by definition not concurrent, and pairing against it would put the drift
    # back into every delta while the output still claimed it had been removed. Reuse is a
    # rollout saving, never a change to what a comparison means.
    # Nor on a re-gate: a second attempt at the same iteration is run precisely to BUY more
    # replicate evidence, so handing it the readings it already has would answer the question
    # with the numbers that failed to answer it.
    if not args.no_control and not args.no_reuse_control \
            and args.gate_against != "control" and ATTEMPT == 0:
        # Same parent bytes as the round that already measured this parent's noise floor, so
        # there is nothing new to learn from measuring it again — see reusable_controls.
        REUSED = reusable_controls(run_dir, best, MEASUREMENT,
                                   max(1, args.control_replicates))
    if REUSED:
        # No copytree, no eval: the rollouts these tags name are already on disk and the gate
        # reads them from there, so everything downstream is unchanged.
        ctl_tags = REUSED["tags"]
        CTL = ctl_tags[0]
    elif not args.no_control:
        # MORE THAN ONE control replicate, because one control does not bound the noise. Measured
        # here: a byte-identical control, re-run on the SAME seeds at temperature 0, moved
        # 0.6467 -> 0.7267 — a paired delta of +0.0800 that PASSES a k_se=1.0 bar on identical
        # code. A candidate measured against a single control reading therefore inherits a
        # coin-flip: the same candidate read +0.0867 against one control run and +0.0067 against
        # the other. Two replicates give the round its own null delta, which is the only bar
        # worth comparing a candidate to.
        for i in range(max(1, args.control_replicates)):
            tag = CTL if i == 0 else f"{CTL}r{i}"
            if (work / tag).exists():
                shutil.rmtree(work / tag)
            shutil.copytree(run_dir.candidate_dir(best), work / tag)
            ctl_tags.append(tag)
        tags = ctl_tags + tags

    with ThreadPoolExecutor(max_workers=max(1, args.max_parallel)) as pool:
        evals = list(pool.map(
            lambda t: _evaluate(Path(args.run_dir), project, t, args.split,
                                args.n_trials, EFFECTIVE_CONCURRENCY), tags))
    if REUSED:
        # Reused replicates are gated exactly like measured ones (gate_check reads persisted
        # rollouts), so they join the row set here without an eval behind them.
        evals = [{"tag": t, "rc": 0, "reused": True} for t in ctl_tags] + evals

    # Gate serially against the CURRENT best; the driver commits, so best_id is stable here.
    #
    # issue #684 item 6: PRIMARY reference, inverted. Measurement drift between rounds
    # (~0.10 on a real run) is comparable in magnitude to the real effects being chased
    # (~0.02-0.09), so a verdict computed against the stored PARENT reward carries that
    # drift baked in as if it were the edit. When this round measured null-control
    # replicates (the standard case — ``--control-replicates 2`` is the default), gate
    # PRIMARILY against them instead: byte-identical copies of the parent measured in
    # THIS round, pooled per task, so drift is cancelled by construction. The
    # raw-vs-stored-parent comparison is kept below as a SECONDARY diagnostic
    # (``r["raw_vs_parent"]``) — useful for detecting drift itself, no longer the
    # deciding factor. Falls back to the stored parent, unchanged, whenever no control
    # was measured this round (``--no-control``) — nothing to be control-relative to.
    gate_ref = best
    if args.gate_against == "control":
        if args.no_control:
            print(json.dumps({"error": "--gate-against control needs the control: drop "
                                       "--no-control"}, indent=2))
            return 2
        gate_ref = CTL
    elif ctl_tags:
        gate_ref = list(ctl_tags)  # pooled control replicates — now the PRIMARY reference
    # TWO distinct objects, kept distinct. `gate_res` is what deltas and thresholds are measured
    # against (the control, pooled, whenever one was measured this round); `parent_res` is the
    # candidate this round is climbing from. They coincide only when no control exists.
    #
    # Conflating them reported the CONTROL's reward under the PARENT's tag: on run 32871360361
    # the table said `parent: {tag: 'seed', reward: 0.34}` while baseline.json said the seed
    # scored 0.38, which no reader could reconcile. Worse, the gap between the two IS this
    # round's temporal drift — measured at 0.24/0.44/0.38 on identical seed bytes across three
    # runs, i.e. several times the gate bar — so collapsing them erased the one number that says
    # whether any delta in the table means anything.
    gate_res = harness.split_result_from_rollouts(run_dir, gate_ref, args.split)
    parent_res = (gate_res if gate_ref == best
                  else harness.split_result_from_rollouts(run_dir, best, args.split))
    parent = gate_res  # deltas/thresholds are always against the gate reference

    # #684 items 1-2: declared multi-objective config, resolved ONCE for this round. Native
    # support in round.py — no longer "pareto excluded from --mode, gate by hand" — forwards
    # these through _gate() to gate_check.py exactly as --objectives/--metrics-*/--constraints
    # already accept when called directly.
    PARETO_OBJECTIVES = None
    CONSTRAINTS = None
    OBJ_NAMES: set[str] = set()
    if args.mode in ("pareto", "epsilon_constraint"):
        if args.mode == "pareto":
            PARETO_OBJECTIVES = spec.get("objectives") or [dict(o) for o in _DEFAULT_PARETO_OBJECTIVES]
            OBJ_NAMES = {o["name"] for o in PARETO_OBJECTIVES if o["name"] != "reward"}
        else:
            CONSTRAINTS = spec.get("constraints")
            if not CONSTRAINTS:
                print(json.dumps({
                    "error": "gate_mode epsilon_constraint requires a non-empty `constraints:` "
                             "list in capevolve.yaml, e.g. constraints: [{name: cost, max: 1.0}]",
                }, indent=2))
                return 2
            OBJ_NAMES = {c["name"] for c in CONSTRAINTS}

    # The subprocess `--current` flag for gate_check.py — a comma-joined tag list when
    # gate_ref is the pooled control, else the single tag, else unset (gate_check.py's own
    # default: the run's stored best_id).
    gate_ref_arg = (",".join(gate_ref) if isinstance(gate_ref, list)
                    else (gate_ref if gate_ref != best else None))
    rows = []
    for ev in evals:
        tag = ev["tag"]
        # The candidate's own non-reward objective/constraint values (e.g. cost), sourced
        # from its own persisted rollouts — never from the reference side, which gets its
        # OWN call below with ITS tag.
        cand_values, cand_stderrs = ((_objective_metrics(run_dir, tag, args.split, OBJ_NAMES))
                                     if OBJ_NAMES else ({}, {}))
        gate_kwargs = {}
        if args.mode == "pareto":
            ref_values, ref_stderrs = _objective_metrics(run_dir, gate_ref, args.split, OBJ_NAMES)
            gate_kwargs = dict(objectives=PARETO_OBJECTIVES,
                               metrics_candidate=cand_values, metrics_current=ref_values,
                               metrics_stderr_candidate=cand_stderrs,
                               metrics_stderr_current=ref_stderrs)
        elif args.mode == "epsilon_constraint":
            gate_kwargs = dict(constraints=CONSTRAINTS, metrics_candidate=cand_values,
                               metrics_stderr_candidate=cand_stderrs)
        elif args.mode == "reward_gated" and spec.get("objectives"):
            # #711: role-tagged plug-in metrics (gate|pareto|display); the verdict is gate_check's
            # own and is NOT overwritten by the archive below (that block is pareto-only).
            gate_kwargs = dict(objectives=spec["objectives"])
        if tag == CTL:
            g = gate_unless_eval_failed(ev, Path(args.run_dir), tag, args.k_se, args.mode,
                                        args.veto_regressions, **gate_kwargs)
        else:
            g = gate_unless_eval_failed(ev, Path(args.run_dir), tag, args.k_se, args.mode,
                                        args.veto_regressions,
                                        current=gate_ref_arg, **gate_kwargs)
        rows.append({
            "tag": tag,
            "reward": (g.get("candidate") or {}).get("reward"),
            "delta_vs_gate_ref": (None if (g.get("candidate") or {}).get("reward") is None
                                  else round((g["candidate"]["reward"] or 0.0)
                                             - gate_res.reward, 4)),
            "gate_delta": (g.get("gate") or {}).get("delta"),
            "gate_threshold": (g.get("gate") or {}).get("threshold"),
            # Structured numeric fields from gate_check.py's own JSON, kept alongside
            # gate_delta/gate_threshold above so commit.py can attach them to the events it
            # writes, rather than only a hand-typed prose note (dashboard.py's gate_decisions
            # previously had to regex-parse these back out of that note — see commit.py).
            "stderr": (g.get("candidate") or {}).get("stderr"),
            "n": g.get("paired_n"),
            "k_se": args.k_se,
            "resolvable_effect_size": (g.get("gate") or {}).get("resolvable_effect_size"),
            # Which val tasks the delta was actually measured over. A row whose footprint is
            # `restricted: false` was measured across the whole split, so its SE carries the
            # noise of every task the edit cannot reach — the defect that made SE(paired Δ)
            # 0.022-0.035 on run_finalrun6 while real per-edit effects were 0.011-0.05.
            "footprint": g.get("footprint"),
            "verdict": g.get("verdict"),
            # #706 ablation.active_eval (default off): advisory paired-posterior read-out from
            # the evidence ledger; the gate verdict above is unchanged.
            **({"posterior": posterior.safe_summarize(run_dir, tag, best, args.split)}
               if tag != CTL and posterior.enabled(spec) else {}),
            "regressions": g.get("regressions"),
            # What the candidate TRADED (gate_check's `movement`): the broke ids AND the fixed
            # ids. Persisted so `commit.py` can put them on the step record instead of leaving
            # the trade-off to the agent's prose — the gate decides on the mean and is
            # indifferent to composition, so an accept can and does destroy solved tasks.
            "movement": g.get("movement"),
            "n_broke": g.get("n_broke"),
            "n_fixed": g.get("n_fixed"),
            "eval_rc": ev.get("rc"),
            "eval_error": ev.get("error"),
            # True only for a control replicate this round read back instead of measuring.
            "reused": bool(ev.get("reused")),
            # #684 items 1-2: this candidate's own non-reward objective/constraint values
            # (e.g. {"cost": 0.42}), sourced from ITS persisted rollouts — {} on every
            # single-metric mode, unchanged from before this feature existed.
            **({"objective_values": cand_values, "objective_stderrs": cand_stderrs}
               if OBJ_NAMES else {}),
        })

    # Nothing derived from these rows — the drift-free re-gate, the evidence bar, the noise
    # floor, the written table — is meaningful if a row was never judged. Check before any of it.
    assert_rows_were_judged(rows)

    # #684 item 1: the NATIVE pareto gate. gate_check.py's own --mode pareto verdict (above,
    # per row) is still a one-shot pairwise comparison against gate_ref — useful as a sanity
    # diagnostic, but it is not what decides acceptance here. The archive IS: a candidate is
    # accepted iff it actually gets a slot in the run's persistent frontier, which is the
    # structural fix issue #684 asked for (today's gate had no persistent frontier at all).
    PARETO_ARCHIVE_RESULT = None
    if args.mode == "pareto":
        archive_path = run_dir.root / "pareto_archive.json"
        archive = ParetoArchive.load_or_create(archive_path, PARETO_OBJECTIVES)
        if not archive.points:
            # First pareto gate of this run: seed the archive with the current gate reference
            # (parent or control) itself, so the first candidate is judged against a real
            # baseline point rather than joining an empty frontier for free.
            ref_obj_values, ref_obj_stderrs = _objective_metrics(
                run_dir, gate_ref, args.split, OBJ_NAMES)
            archive.points.append(ArchivePoint(
                tag=gate_ref,
                values={"reward": gate_res.reward, **ref_obj_values},
                stderr={"reward": gate_res.stderr, **ref_obj_stderrs},
                round=int(run_dir.spent.iterations)))
        for r in rows:
            if r["tag"] in ctl_tags or r.get("reward") is None:
                continue
            values = {"reward": r["reward"], **(r.get("objective_values") or {})}
            stderrs = {"reward": r.get("stderr") or 0.0, **(r.get("objective_stderrs") or {})}
            inserted, reason = archive.try_insert(
                r["tag"], values, stderrs, k_se=args.k_se,
                round_num=int(run_dir.spent.iterations))
            # THE verdict for pareto mode: accept iff the archive insertion succeeded. This
            # overrides gate_check.py's own one-shot pairwise verdict recorded above.
            r["verdict"] = "accept" if inserted else "reject"
            r["pareto_archive"] = {"inserted": inserted, "reason": reason, "values": values,
                                   "stderrs": stderrs, "capacity": archive.capacity,
                                   "size_after": len(archive.points)}
        archive.save(archive_path)
        PARETO_ARCHIVE_RESULT = archive.to_dict()

    # issue #684 item 6: TWO cross-checks, kept distinct, with the PRIMARY/secondary roles
    # inverted from before. `verdict`/`gate_delta`/`gate_threshold` on each row are now
    # computed primarily against the pooled control (set via `gate_ref`/`gate_ref_arg`
    # above) whenever one was measured this round — see the comment at `gate_ref`'s
    # assignment. The two blocks below:
    #
    #   * `control_relative` — kept at its PRE-#684 field name/shape for backward
    #     compatibility (commit.py's `--reject-basis drift_control`, the dashboard's
    #     control_relative_verdict/_delta panels). It is the SAME control-pooled
    #     comparison the top-level fields now use as primary, so under the new default it
    #     is intentionally REDUNDANT with `verdict`/`gate_delta` — there is no longer a
    #     disagreement for `drift_control` to resolve, because the thing it used to
    #     escalate TO is now what decided in the first place.
    #   * `raw_vs_parent` — NEW: the comparison that used to be primary (against the
    #     parent's STORED reward from an earlier round), demoted to secondary. Where it
    #     disagrees with the (now-primary) control-relative verdict, the gap IS drift, not
    #     the edit — useful for detecting drift itself, never for deciding.
    #
    # On run 32871360361 round 4 the table showed cand4 at +0.15 against the seed's stored
    # 0.38 with a bar of 0.11 (drift), i.e. marginal; the same round's two concurrent
    # controls both read exactly 0.27, so the drift-free (now PRIMARY) answer from the
    # identical rollouts is +0.26 against a bar of 0.00 — the 0.11 belonged to WHEN the
    # seed was measured, not to cand4. Costs no rollouts — both sides are already evaluated
    # and gate_check reads stored data.
    #
    # Skipped for pareto/epsilon_constraint (#684 items 1-2): this diagnostic re-gates against
    # the control with the SAME --mode but no objective/constraint metrics threaded through —
    # ponytail: a real drift-free multi-objective comparison would need the control's own
    # cand_values too; add if a multi-objective run's drift turns out to matter in practice.
    # pareto's real verdict is decided by the archive above, not by this diagnostic anyway.
    if args.mode not in ("pareto", "epsilon_constraint") and args.gate_against != "control" and ctl_tags:
        for r in rows:
            if r["tag"] in ctl_tags or r.get("reward") is None:
                continue
            # POOLED over every control replicate this round has, not just the one carrying
            # the round-scoped tag — the same reference the primary verdict above now uses.
            g_ctl = _gate(Path(args.run_dir), r["tag"], args.k_se, args.mode,
                         args.veto_regressions, current=",".join(ctl_tags))
            r["control_relative"] = {
                "reference": ctl_tags if len(ctl_tags) > 1 else CTL,
                "gate_delta": (g_ctl.get("gate") or {}).get("delta"),
                "gate_threshold": (g_ctl.get("gate") or {}).get("threshold"),
                "verdict": g_ctl.get("verdict"),
                "reading": ("this is now the PRIMARY comparison (issue #684 item 6): the same "
                            "numbers as `verdict`/`gate_delta` above, kept under this field name "
                            "for backward compatibility with commit.py's --reject-basis "
                            "drift_control and the dashboard's control_relative panels."
                            if not REUSED else
                            f"this candidate against a byte-identical control of the SAME parent "
                            f"measured in iteration {REUSED['from_iteration']} and reused here. "
                            "It removes the parent's own measurement error but NOT the drift "
                            "since that iteration, so it is not the drift-free comparison a "
                            "concurrent control gives — re-run with --no-reuse-control (or "
                            "--gate-against control, which never reuses) to buy that."),
            }
            g_par = _gate(Path(args.run_dir), r["tag"], args.k_se, args.mode,
                         args.veto_regressions, current=best)
            r["raw_vs_parent"] = {
                "reference": best,
                "gate_delta": (g_par.get("gate") or {}).get("delta"),
                "gate_threshold": (g_par.get("gate") or {}).get("threshold"),
                "verdict": g_par.get("verdict"),
                "reading": ("SECONDARY — no longer the deciding comparison (issue #684 item "
                            "6). This candidate against the parent's reward as STORED from an "
                            "earlier round, carrying whatever re-measurement drift happened "
                            "since. The PRIMARY verdict (`verdict`/`gate_delta` above, == "
                            "`control_relative`) cancels that drift by construction. Where the "
                            "two disagree, the difference is drift, not the edit; this field "
                            "exists to show you that gap, not to override the primary verdict."),
            }

    # Would the verdict have survived a different control replicate? On run 32871360361 round 3
    # two byte-identical replicates read 0.32 and 0.20 two minutes apart, and the reference was
    # simply whichever carried the round-scoped tag (0.20) — so cand3 scored +0.17 and accepted
    # where against the other replicate it is +0.05 and rejects. The table said nothing about the
    # verdict resting on that choice. Re-gating costs no rollouts, so there is no reason not to
    # check; a verdict that flips is not evidence, whatever the picked replicate showed.
    #
    # MANDATORY two-seed-block sign agreement: this used to run only under
    # --gate-against control, so a parent-gated round (the default) never checked whether its
    # accept survived the choice of control replicate — measured on a real run to have called a
    # null result positive exactly that way, unchecked because the round gated against the stored
    # parent. With --control-replicates 2 the default, this check now always runs whenever there
    # is more than one control block, in EITHER gate mode.
    #
    # Skipped for pareto/epsilon_constraint, same reason as the control_relative block above:
    # this diagnostic's re-gate carries no objective/constraint metrics.
    if args.mode not in ("pareto", "epsilon_constraint") and len(ctl_tags) > 1:
        for r in rows:
            if r["tag"] in ctl_tags or r.get("reward") is None:
                continue
            by_ref = {}
            for ref in ctl_tags:
                g = _gate(Path(args.run_dir), r["tag"], args.k_se, args.mode,
                          args.veto_regressions, current=ref)
                by_ref[ref] = g.get("verdict")
            r["verdict_by_reference"] = by_ref
            verdicts = {v for v in by_ref.values() if v is not None}
            r["verdict_stable"] = (len(verdicts) <= 1)
            if not r["verdict_stable"]:
                r["verdict"] = "inconclusive"

    # issue #684 item 6: true whenever the PRIMARY verdict above is control-relative — the
    # explicit --gate-against control mode, or (now the default) a parent-mode round that
    # measured null-control replicates. False only when no control exists at all this round
    # (--no-control), in which case gate_ref falls back to best, unchanged from before.
    CONTROL_PRIMARY = gate_ref != best

    ctl = next((r for r in rows if r["tag"] == CTL), None)
    # The floor must be the control's delta against the STORED parent, never against whatever
    # this round gated on. Under a control-primary verdict the control IS the reference, so
    # delta_vs_parent is 0.0 by construction — reporting that as the noise floor would claim
    # zero re-measurement noise, the single most dangerous number this script can print.
    floor = None
    if ctl is not None:
        if CONTROL_PRIMARY:
            floor = abs(ctl["gate_delta"]) if ctl.get("gate_delta") is not None else None
        elif ctl["delta_vs_gate_ref"] is not None:
            floor = abs(ctl["delta_vs_gate_ref"])
    # The gap BETWEEN identical control replicates is the round's empirical bar. It is a
    # stronger statement than any single control's delta, because both replicates are the same
    # bytes on the same seeds: whatever separates them is pure re-measurement. Two such
    # replicates differed by 0.0800 paired on this benchmark — enough to pass a k_se=1.0 gate on
    # zero change — so a candidate that does not clear this number has shown nothing.
    #
    # Earlier attempts at THIS iteration are pooled in. They are the same parent bytes on the
    # same seeds in the same round, so they are samples of the same null, and a re-gate is run
    # precisely to buy more of them: reporting only this attempt's two would discard half the
    # evidence the round has already paid for. `max - min` needs no change to accept them.
    ctl_rows = [r for r in rows if r["tag"] in ctl_tags and r.get("reward") is not None]
    pooled_rows = [{**r, "from_attempt": ATTEMPT} for r in ctl_rows] + PRIOR_CTL
    null_delta = None
    if len(pooled_rows) > 1:
        rewards = [r["reward"] for r in pooled_rows]
        null_delta = round(max(rewards) - min(rewards), 4)
    conc_warning = None
    if EFFECTIVE_CONCURRENCY and EFFECTIVE_CONCURRENCY > 12:
        conc_warning = (
            f"GATE RAN AT CONCURRENCY {EFFECTIVE_CONCURRENCY}. Measured on this benchmark, "
            "byte-identical code at identical seeds moves ~0.08 at the arm level above conc 25 "
            "and ~0.03 at conc 8. A verdict from this round can therefore not resolve an effect "
            "smaller than roughly 0.08. Re-run the gate at --concurrency 8 before believing an "
            "accept.")

    prior_settings = prior_round_settings(run_dir)
    parallel_warning = parallel_drift_warning(prior_settings, EFFECTIVE_CONCURRENCY,
                                              args.max_parallel)
    out = {
        # Which gate of this iteration this is. On the live run nothing in the output
        # distinguished "second opinion on iteration 1" from "iteration 1", so an operator
        # watching the stream saw two identical control evaluations and no statement that the
        # second had replaced the first.
        "attempt": ATTEMPT,
        "batch_id": STEM,
        "attempt_reading": (
            f"RE-GATE: attempt {ATTEMPT} at iteration {int(run_dir.spent.iterations)}. Its "
            f"{len(PRIOR_CTL)} earlier control replicate(s) are pooled into `null_delta_...` "
            "below, so the bar here rests on every replicate this round has paid for. This "
            "attempt's candidate rollouts are written under fresh tags; the earlier attempt's "
            "table is still on disk beside this one."
            if ATTEMPT else "first gate of this iteration"),
        "parent": {"tag": best, "reward": parent_res.reward, "stderr": parent_res.stderr,
                   "n_tasks": len(parent_res.per_task or [])},
        # What the deltas and thresholds in `candidates` are actually measured against.
        "gate_reference": {"tag": gate_ref, "mode": args.gate_against,
                           "reward": gate_res.reward, "stderr": gate_res.stderr},
        # issue #684 item 6: the de-facto PRIMARY accept/reject signal this round actually
        # used — distinct from `gate_reference.mode`, which only echoes the --gate-against
        # flag. "control" whenever a control was measured (the default, now), "parent" only
        # when none exists (--no-control) and the stored-parent fallback applies.
        "primary_signal": "control" if CONTROL_PRIMARY else "parent",
        # The round's OWN drift: identical-or-parent bytes measured now versus what the parent
        # measured when it was scored. Non-null only when they are different measurements.
        "parent_vs_gate_ref_drift": (None if gate_ref == best else
                                     round((gate_res.reward or 0.0)
                                           - (parent_res.reward or 0.0), 4)),
        "drift_reading": (
            "the parent's stored reward and a byte-identical control measured in THIS round "
            "differ by this much. It is re-measurement drift, not progress, and any candidate "
            "delta of comparable size is not evidence — whatever its verdict says."
            if gate_ref != best else
            "gated against the parent's stored reward, so this round cannot see how far that "
            "reward has drifted since it was measured; --gate-against control measures it."),
        # What these rewards are comparable within, and therefore what a LATER round has to
        # match before it may reuse this round's control replicates (see reusable_controls).
        "measurement": MEASUREMENT,
        # Did this round pay for its own control replicates, or read back the ones this SAME
        # parent already has? Reuse happens only while best_id has not moved: the parent is the
        # same bytes, so its noise floor is already established. Any accept invalidates it and
        # the next round measures fresh — the two-replicate requirement is unchanged either way.
        "control_reuse": ({"reused": True, **REUSED,
                           "rollouts_saved": len(REUSED["tags"]),
                           "reading": "the control replicates below were measured in iteration "
                                      f"{REUSED['from_iteration']}, when this same parent was "
                                      "already the parent. No new control rollouts were spent. "
                                      "The replicate GAP is still this parent's own null; what "
                                      "it no longer contains is drift since that iteration, so "
                                      "prefer the parent-mode reading of `evidence_bar` here."}
                          if REUSED else
                          {"reused": False,
                           "reason": ("--no-control" if args.no_control else
                                      "--no-reuse-control" if args.no_reuse_control else
                                      "--gate-against control needs a CONCURRENT control"
                                      if args.gate_against == "control" else
                                      "a re-gate is run to BUY replicate evidence, so it always "
                                      "measures" if ATTEMPT else
                                      "no earlier round measured THIS parent's replicates under "
                                      "this same measurement context — a new parent has no "
                                      "established noise floor, so it must be measured")}),
        "measurement_concurrency": EFFECTIVE_CONCURRENCY,
        "requested_concurrency": args.concurrency,
        "max_total_concurrency": args.max_total_concurrency,
        "concurrency_warning": conc_warning,
        "measurement_max_parallel": args.max_parallel,
        "parallel_warning": parallel_warning,
        "null_delta_between_control_replicates": null_delta,
        "null_delta_replicates": len(pooled_rows),
        "null_delta_reading": (
            "identical bytes on identical seeds, so this is pure re-measurement noise. Any "
            "candidate delta at or below it is NOT evidence, whatever its verdict says."
            + (f" Pooled over {len(pooled_rows)} replicates of this iteration, "
               f"{len(PRIOR_CTL)} of them from earlier attempts." if PRIOR_CTL else "")
            if null_delta is not None else
            "only one control replicate — run with --control-replicates 2 to measure the bar "
            "instead of assuming a formula gives it"),
        "gated_against": {"tag": gate_ref, "mode": args.gate_against},
        "noise_floor_from_control": floor,
        "noise_floor_basis": ("control vs the STORED parent rollouts (differing trial counts are "
                              "part of this floor, which is the point)" if CONTROL_PRIMARY
                              else "control vs the parent it was copied from"),
        # ONE bar, matched to how this round actually gated. Reporting several numbers and
        # leaving the driver to choose is not neutral: on run 32871360361 round 2 the table
        # showed cand2 beating its CONCURRENT control by +0.19 (three times the k_se threshold,
        # nineteen times the 0.01 gap between the control's own replicates) alongside a
        # `noise_floor_from_control` of 0.14 — which is the control-vs-STORED-parent gap, i.e.
        # temporal drift. The reading told the driver to treat any delta at or below the floor as
        # no evidence, so it compared a control-relative delta against a drift-derived floor,
        # resolved the contradiction conservatively, and booked a REJECT on the best candidate of
        # the run.
        #
        # Which bar is right depends entirely on what the delta was measured against (issue
        # #684 item 6: now a function of CONTROL_PRIMARY, not literally args.gate_against —
        # the default parent-mode round is control-primary too, whenever it measured one):
        #   * control-primary — the delta is against a control measured in THIS round, so
        #     drift is already cancelled and the bar is the gap between identical replicates.
        #   * parent-primary  — the delta is against a reward measured in an earlier round
        #     (only when no control exists at all this round), so drift is inside it and the
        #     bar has to include the control's drift as well.
        "evidence_bar": {
            "value": (null_delta if CONTROL_PRIMARY
                      else (None if (null_delta is None and floor is None)
                            else max(null_delta or 0.0, floor or 0.0))),
            "basis": ("gap between byte-identical control replicates measured in THIS round — "
                      "drift is cancelled by gating against the (now primary) control"
                      if CONTROL_PRIMARY else
                      "the larger of the replicate gap and the control's drift against the "
                      "stored parent, because this round's deltas ARE against that stored "
                      "reward and carry its drift"),
        },
        "reading": (
            "A candidate marked `verdict_stable: false` has an UNSTABLE verdict and is "
            "INCONCLUSIVE, never accepted: its "
            "verdict changed depending on which byte-identical control replicate happened to be "
            "the reference, so the round cannot tell its edit from re-measurement. Run "
            "`scripts/grow.py --candidate <tag> --growth-round 1 --add-trials <n>` on it BEFORE "
            "booking anything — commit.py refuses `--decision inconclusive` until grow.py has "
            "bought this candidate at least one extra round of trials (issue #420 item 3: this "
            "exact case was read-and-skipped, never run, across two prior runs). grow.py pools "
            "the new trials onto the SAME candidate and re-gates at the pooled n; commit its "
            "recommendation (promote/grow_again/abandon) once it has one. Only if growth "
            "genuinely cannot help (e.g. delta <= 0) book `commit.py --decision inconclusive "
            "--force` and say why in --note — that still charges the iteration but NOT the "
            "stall counter, because a measurement that could not resolve is no evidence you "
            "have run out of ideas, and it keeps the edit out of `rejected.jsonl` so a later "
            "round is not taught to avoid a change nothing ever judged. "
            "rollouts are written `<task>__<tag>__t{k}.json` for k in range(n_trials), so "
            "re-running the SAME tag REPLACES t0..t9 rather than adding t10..t19 — it swaps a "
            "reading for another reading and buys no extra evidence; grow.py's own throwaway "
            "tag avoids that. The control side is handled for you — a re-gate of the "
            "same iteration gets its own `ctl_null_i<N>a<k>` replicates and POOLS the earlier "
            "attempt's into `null_delta_between_control_replicates`, so re-running this script "
            "adds control evidence instead of replacing it. Do not re-use a candidate tag to "
            "get that; there is no pooling for candidates. "
            "Judge every candidate's delta against `evidence_bar` rather than any other noise "
            "number here — but clearing it is NECESSARY, not sufficient: `gate_threshold` "
            "(k·SE on the paired per-task differences) is what each `verdict` is actually "
            "computed from and is usually the stricter of the two, so a delta above "
            "`evidence_bar` and below `gate_threshold` is not an accept. "
            "`noise_floor_from_control` is the gap between a byte-identical control "
            "measured now and the parent's STORED reward: that is re-measurement DRIFT, and it "
            "bounds how far the ABSOLUTE rewards in this table can be trusted — it is not a bar "
            "a candidate gated against a concurrent control has to clear, because that "
            "comparison never contained the drift. Do not re-derive a delta against the stored "
            "parent and reject on it; that puts the drift back in."
            if CONTROL_PRIMARY else
            "ctl_null is a byte-identical copy of the parent, so its delta is what ZERO change "
            "measures today. No control exists this round (--no-control), so every verdict "
            "fell back to the parent's STORED reward and that drift is inside every candidate "
            "delta here: treat any candidate at or below `evidence_bar` as no evidence, even if "
            "its verdict is accept. Drop --no-control to get the drift-free, control-primary "
            "verdict instead."
            if floor is not None or null_delta is not None else
            "no null control in this round — you cannot separate a small gain from re-measurement."
        ),
        "candidates": sorted((r for r in rows if r["tag"] not in ctl_tags),
                             key=lambda r: (r["reward"] is None, -(r["reward"] or 0.0))),
        "control": ctl,
        # `control_replicates` stays THIS attempt's own measurements — that is what a later
        # attempt reads back to pool, and storing the pooled set here would make attempt 2
        # count attempt 0's replicates twice. The pooled view is reported separately.
        "control_replicates": ctl_rows,
        "pooled_control_replicates": pooled_rows if PRIOR_CTL else None,
        # #684 items 1-2: present (non-None) only for the two multi-objective modes. For
        # pareto, `pareto_archive` is the authoritative frontier state this round wrote to
        # `pareto_archive.json` — each candidate row's own `pareto_archive`/`verdict` is what
        # actually decided it, not `gate_delta`/`gate_threshold` (those stay as diagnostics).
        "objectives": PARETO_OBJECTIVES,
        "constraints": CONSTRAINTS,
        "pareto_archive": PARETO_ARCHIVE_RESULT,
        **CASCADE,
        "next": _next_steps(killed, MERGE, dominated),
    }
    _write_table(run_dir, work, STEM, ATTEMPT, out)
    # One "gated" transition per candidate the full-val gate judged (#435). A node gated with
    # no screen carries the override that let it through, so `subset: null` is never silent.
    for r in out["candidates"]:
        graph.append_node(run_dir, node_id=r["tag"], parents=node_parents.get(r["tag"], [best]),
                          status="gated", val_mean=r.get("reward"), gate=r,
                          screen_skip_justification=(
                              None if screened_by_tag.get(r["tag"], True) else
                              args.skip_screen_justification or "--skip-screen-ladder"))
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
