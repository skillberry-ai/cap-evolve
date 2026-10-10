"""merge_n -- N-way merge by merge-base fold, an interaction score, and a price for checking (#710).

Fold: tips are merged one at a time; each step 3-way merges (block level for prose via
``mdblocks``, per function for python via ``funcmerge``, both through ``merge.build_merge_dir``)
against ``lineage.fold_merge_base`` -- the common ancestor AT THAT STEP, not the round's parent.
A real collision (same block edited differently) is never merged silently: the branch is left
out and reported with a conflict-resolution proposal.

Interaction score ``I`` (weights are guesses, not fitted; see ``WEIGHTS``) predicts how likely
two edits are to interfere: shared blocks, shared tool names, overlapping touched tasks (the
mechanisms ledger), and overlapping WIN sets (two branches fixing the same tasks are redundant
or competing; branches winning different tasks compose). ``I < PROBE_AT`` merges without
measuring; otherwise a targeted probe plan (union of each branch's winning tasks + sentinels,
3 trials, cells already in the evidence ledger cost nothing) is emitted as an eval request.

Ablation ``smart_merge`` (spec ``optimizer.ablation.smart_merge``, legacy top-level
``ablation.smart_merge``, env ``CAPEVOLVE_SMART_MERGE``; env wins; default on). Off => the
legacy pairwise path (``merge.py`` / ``merge_search.py`` without ``--nway``).

Unknown interaction never merges silently: a pair with no win evidence (missing, or both win
sets empty) or no touched-task record is ``unknown`` and forces a probe. Tie-breaks are
deterministic: fold order = most wins first then tag name; a criss-cross merge base resolves per
``lineage.merge_base`` (smallest depth sum, then higher score, then lexicographic).
"""

from __future__ import annotations

import hashlib
import itertools
import re
import shutil
import sys
from pathlib import Path

import _bootstrap  # noqa: F401
import merge as merge_mod
import merge_search
from cap_evolve import eval_index, lineage, mdblocks, optimizer_config

import funcmerge

WEIGHTS = {"blocks": 0.35, "tools": 0.25, "tasks": 0.20, "wins": 0.20}
PROBE_AT = 0.2
PROBE_TRIALS = 3
N_SENTINELS = 3


def enabled(spec: dict | None = None) -> bool:
    """Single resolver: ``optimizer_config`` (env > optimizer.ablation > legacy ablation > on)."""
    return optimizer_config.enabled("smart_merge", spec)


# ---- features -------------------------------------------------------------------------------

def touched_blocks(base_dir: Path, x_dir: Path) -> set[str]:
    """``rel::block`` for every block ``x_dir`` changed vs ``base_dir`` (md heading section,
    python function; any other file is one block named by its path)."""
    base_f, x_f, _, ch, _ = merge_mod._changed_files(base_dir, x_dir, x_dir)
    out: set[str] = set()
    for rel in ch:
        a, b = merge_mod._read(base_f, rel), merge_mod._read(x_f, rel)
        try:
            if rel.endswith((".md", ".txt")) and a is not None and b is not None:
                A, B = (dict(mdblocks.split(mdblocks.decode(t))) for t in (a, b))
            elif rel.endswith(".py") and a is not None and b is not None:
                A, B = (funcmerge.blocks(t.decode("utf-8"))[1] for t in (a, b))
            else:
                raise ValueError
        except (ValueError, SyntaxError):  # UnicodeDecodeError is a ValueError
            out.add(rel)
            continue
        out |= {f"{rel}::{k}" for k in set(A) | set(B) if A.get(k) != B.get(k)}
    return out


_TOOL = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b")


def tool_names(base_dir: Path, x_dir: Path) -> set[str]:
    """snake_case identifiers on lines ``x_dir`` added or removed (tool/function names)."""
    base_f, x_f, _, ch, _ = merge_mod._changed_files(base_dir, x_dir, x_dir)
    names: set[str] = set()
    for rel in ch:
        a = (merge_mod._read(base_f, rel) or b"").decode("utf-8", "replace").splitlines()
        b = (merge_mod._read(x_f, rel) or b"").decode("utf-8", "replace").splitlines()
        for line in set(a) ^ set(b):
            names.update(_TOOL.findall(line))
    return names


def _jac(a, b) -> float:
    a, b = set(a), set(b)
    return len(a & b) / len(a | b) if a | b else 0.0


def interaction(f1: dict, f2: dict) -> dict:
    """``f = {"blocks", "tools", "tasks", "wins"}`` (sets; ``wins=None`` = no evidence).
    ``unknown`` (no win evidence, both win sets empty, or no touched-task record) forces a
    probe in :func:`plan`; the neutral 0.5 is only the displayed score for the wins term."""
    parts = {k: _jac(f1[k], f2[k]) for k in ("blocks", "tools", "tasks")}
    why = []
    if f1.get("wins") is None or f2.get("wins") is None or not (f1["wins"] or f2["wins"]):
        why.append("no per-task win evidence")
        parts["wins"] = 0.5
    else:
        parts["wins"] = _jac(f1["wins"], f2["wins"])
    if not (f1["tasks"] and f2["tasks"]):
        why.append("no touched-task record (mechanisms.jsonl missing or empty)")
    score = sum(WEIGHTS[k] * v for k, v in parts.items())
    out = {"I": round(score, 4), "parts": {k: round(v, 4) for k, v in parts.items()},
           "unknown": bool(why)}
    if why:
        out["warning"] = "; ".join(why)
        print(f"merge_n WARNING: interaction unknown, probe required: {out['warning']}", file=sys.stderr)
    return out


def wins_from_scores(per_task: dict[str, dict[str, float]], base: str, eps: float = 1e-9
                     ) -> dict[str, set[str]]:
    """``{tag: tasks where tag beat base}`` from ``{tag: {task: reward}}``."""
    b = per_task.get(base, {})
    return {t: {k for k, v in s.items() if v > b.get(k, 0.0) + eps}
            for t, s in per_task.items() if t != base}


def wins_from_run(run_dir, tags, base: str, split: str = "val") -> dict[str, set[str]] | None:
    """Per-task wins vs ``base`` from persisted val rollouts. A tag with no val rollouts is
    skipped (with a warning) and absent from the result; ``None`` only if ``base`` has none."""
    from cap_evolve import harness

    def load(t):
        try:
            rows = harness.split_result_from_rollouts(run_dir, t, split).per_task or []
        except Exception as e:  # noqa: BLE001
            print(f"merge_n WARNING: no val evidence for {t}: {e}", file=sys.stderr)
            return None
        if not rows:
            print(f"merge_n WARNING: no val evidence for {t}", file=sys.stderr)
            return None
        return {r["task_id"]: float(r.get("reward", 0.0)) for r in rows}

    per = {}
    for t in [base, *tags]:
        if (v := load(t)) is not None:
            per[t] = v
    return wins_from_scores(per, base) if base in per else None


# ---- planning -------------------------------------------------------------------------------

def features(base_dir: Path, tag_dir: Path, touched_tasks=(), wins=None) -> dict:
    return {"blocks": touched_blocks(base_dir, tag_dir), "tools": tool_names(base_dir, tag_dir),
            "tasks": set(map(str, touched_tasks)), "wins": None if wins is None else set(wins)}


def check_ids(ids, splits, what: str) -> list[str]:
    """User-supplied task ids must be in the val/train pool; a test or unknown id raises."""
    pool = {str(t) for sp in ("val", "train") for t in splits.ids(sp)}
    bad = sorted({str(i) for i in ids} - pool)
    if bad:
        raise ValueError(f"{what}: id(s) {bad} are not in the val/train pool of splits.json "
                         "(test ids and unknown ids are never allowed in a probe plan)")
    return [str(i) for i in ids]


def probe_plan(wins: dict[str, set[str]], all_tasks, tag: str, n_trials: int = PROBE_TRIALS,
               run_dir=None, out_dir: Path | None = None, canaries=None, reason: str = "") -> dict:
    """Eval request for the ledger: union of each branch's winning tasks + sentinels."""
    owned = sorted(set().union(*wins.values())) if wins else []
    rest = sorted((str(t) for t in all_tasks if str(t) not in owned),
                  key=lambda t: hashlib.sha256(t.encode()).hexdigest())
    sentinels = list(canaries) if canaries else rest[:N_SENTINELS]
    ids = owned + [s for s in sentinels if s not in owned]
    req = {"kind": "eval_request", "tag": tag, "split": "val", "task_ids": ids,
           "n_trials": n_trials, "sentinels": sentinels, "reason": reason}
    if run_dir is not None and out_dir is not None and out_dir.is_dir():
        h = eval_index.cap_hash(out_dir)
        req["cap_hash"] = h
        req["missing"] = eval_index.missing(run_dir, h, ids, n_trials)  # {} => free
    return req


def _resolution(a_tags, b_tag, where, wins) -> dict:
    score = lambda ts: sum(len(wins.get(t, ())) for t in ts)  # noqa: E731
    trunk, donor = (a_tags, [b_tag]) if score(a_tags) >= score([b_tag]) else ([b_tag], a_tags)
    return {"where": where, "trunk": trunk, "donor": donor,
            "proposal": (f"keep {'+'.join(trunk)}'s version of {where}; port the intent of "
                         f"{'+'.join(donor)}'s edit into it by hand (or funcmerge "
                         "--priority/--force-priority), then re-measure: this is a real "
                         "disagreement, not a mechanical merge")}


def merge_n(tags: list[str], dir_of, graph, out_dir: Path, *, wins=None, md_blocks=None) -> dict:
    """Fold ``tags`` (branch tips) into ``out_dir``. ``dir_of(tag)`` -> capability dir (also for
    ancestors). Steps run best-first by win count. Conflicting branches are skipped and
    reported with a resolution proposal; ``built`` is True only when none conflicted."""
    wins = wins or {}
    order = sorted(tags, key=lambda t: (-len(wins.get(t, ())), t))
    acc_tags, acc_dir = [order[0]], dir_of(order[0])
    steps, conflicts, unmerged, work = [], [], [], []
    for i, nxt in enumerate(order[1:], 1):
        base = lineage.fold_merge_base(graph, acc_tags, nxt)
        tmp = out_dir.parent / f".{out_dir.name}_step{i}"
        r = merge_mod.build_merge_dir(dir_of(base), acc_dir, dir_of(nxt), tmp, md_blocks)
        step = {"added": nxt, "base": base, "merged_with": list(acc_tags),
                "three_way_merged": r["three_way_merged"], "built": r["built"]}
        if not r["built"]:
            blocks = merge_search.is_mergeable(acc_dir, dir_of(nxt), dir_of(base), md_blocks)["conflicts"]
            files = [c["file"] for c in r["conflicts"]]
            where = blocks or files
            step["conflicts"] = where
            conflicts += [_resolution(acc_tags, nxt, w, wins) for w in where]
            unmerged.append(nxt)
        else:
            acc_tags.append(nxt)
            acc_dir = tmp
            work.append(tmp)
        steps.append(step)
    if len(acc_tags) > 1:
        if out_dir.exists():
            shutil.rmtree(out_dir)
        shutil.copytree(acc_dir, out_dir)
    for w in work:
        shutil.rmtree(w, ignore_errors=True)
    dropped = [{"branch": s["added"], "reason": "conflict", "conflicts": s["conflicts"]}
               for s in steps if not s["built"]]
    return {"order": order, "merged": acc_tags, "unmerged": unmerged, "dropped": dropped, "steps": steps,
            "conflicts": conflicts, "built": not unmerged and len(acc_tags) > 1,
            "out": str(out_dir) if len(acc_tags) > 1 else None}


def node_record(result: dict, out_tag: str, round_id=None) -> dict | None:
    """graph.jsonl extras for the merged node (docs/RUN_SCHEMA_V2.md), or ``None`` when fewer
    than two branches merged (no merge happened, so no merge node). ``parents`` are only the
    branches actually merged; skipped/conflicting ones are recorded in ``skipped``. The node is
    itself a tip you can branch from again; ``merge_base`` is the first fold step's base, the full
    per-step list is in ``merge_changes``, and ``fold_order`` records the order tried."""
    parents = result["merged"]
    if len(parents) < 2:
        return None
    steps = result["steps"]
    return {"id": out_tag, "parents": parents, "edit_kind": "merge",
            "merge_base": steps[0]["base"] if steps else None,
            "base_for_eval": parents[0],
            "parent_roles": {p: ("primary" if i == 0 else "donor") for i, p in enumerate(parents)},
            "stage": "built", "status": "proposed", "eval_state": "unevaluated",
            "round_id": round_id, "fold_order": result["order"],
            "skipped": result.get("dropped", []),
            "merge_changes": [{"added": s["added"], "base": s["base"],
                               "files": s["three_way_merged"]} for s in steps if s["built"]]}


def plan(tags: list[str], dir_of, graph, *, touched_tasks=None, wins=None, all_tasks=(),
         out_dir: Path, run_dir=None, md_blocks=None, canaries=None) -> dict:
    """Merge decision for the whole set: fold + pairwise interaction + probe-or-not.
    ``all_tasks`` = optimisation (val) task ids, the sentinel pool; never pass test ids."""
    touched_tasks, wins = touched_tasks or {}, wins or {}
    res = merge_n(tags, dir_of, graph, out_dir, wins=wins, md_blocks=md_blocks)
    pairs = []
    for a, b in itertools.combinations(sorted(tags), 2):
        base = dir_of(lineage.merge_base(graph, a, b))   # this pair's own LCA
        fa, fb = (features(base, dir_of(t), touched_tasks.get(t, ()), wins.get(t)) for t in (a, b))
        pairs.append({"pair": [a, b], **interaction(fa, fb)})
    top = max((p["I"] for p in pairs), default=0.0)
    unknown = [p["pair"] for p in pairs if p["unknown"]]
    res["interaction"], res["max_I"], res["unknown_pairs"] = pairs, top, unknown
    res["evidence_missing"] = sorted(t for t in tags if t not in wins or not touched_tasks.get(t))
    res["probe"] = bool(res["built"] and (top >= PROBE_AT or unknown))
    if res["probe"]:
        why = "unknown interaction (missing evidence)" if unknown else f"I={top} >= {PROBE_AT}"
        res["eval_request"] = probe_plan({t: wins.get(t, set()) for t in res["merged"]},
                                         all_tasks, out_dir.name, run_dir=run_dir,
                                         out_dir=out_dir, canaries=canaries, reason=why)
    return res


def select_merge_set(alternative_parents: list[dict], champion: str | None, k: int = 3,
                     graph=None) -> list[str]:
    """#638: parents for a merge round from per-instance ownership -- the champion plus the
    non-champions owning the most uncovered tasks (greedy). With ``graph``, an ancestor or
    descendant of an already-picked parent is skipped (merging it is a no-op)."""
    if not champion:
        return []
    picked, covered = [champion], set()
    pool = {a["candidate"]: set(a["tasks_uniquely_owned"]) for a in alternative_parents}

    def related(c):
        return graph is not None and any(c in lineage.ancestors(graph, p) or p in lineage.ancestors(graph, c)
                                         for p in picked)
    while pool and len(picked) < k:
        best = max(sorted(pool), key=lambda c: len(pool[c] - covered))
        tasks = pool.pop(best)
        if tasks - covered and not related(best):
            covered |= tasks
            picked.append(best)
    return picked
