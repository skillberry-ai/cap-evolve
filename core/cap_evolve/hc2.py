"""HC-2: K parallel proposals per round, evaluated by the shared P2 evaluator.

Hill-climb with rule P judges ONE candidate per iteration. HC-2 is the K-round special case of the
same scheduler the agent-optimize conductor uses (``evaluator.P2Evaluator``): one incumbent, K
candidates from K distinct failure clusters, kill-only rungs on the feedback stratum F, a fresh
confirmation of the survivors on the hidden stratum C, at most one champion per round. There is no
second evaluation code path here; this module only builds the proposer's context and runs the
propose -> evaluate -> record loop around ``P2Evaluator``.

Everything is opt-in (``hc2: true`` in the spec, forwarded as ``--hc2``). Without it ``hill_climb_loop``
and rule P run exactly as before.

Proposer context (all benchmark-agnostic):

* fresh failures from F only. Each round takes a rotating minibatch of the incumbent's failing F tasks
  and splits it into clusters; proposal j gets cluster j's traces FIRST and a few traces of every other
  cluster after them, so each proposal can fix the failure types it sees, not one patch. With
  ``hc2_broad_slot`` one proposal per round sees the failing traces of ALL clusters and is asked for the
  single edit with the largest expected gain; with ``hc2_merge_survivors`` the positive-screen
  candidates of the previous round are merged (3-way, file by file) into one candidate that is screened
  like any other; A trace for a task in C is never
  copied, whatever directory it sits in (``scrub_confirm_traces`` enforces it after every write);
* contrastive pairs: for a task the incumbent both passed and failed across its pooled draws, one
  passing and one failing trace side by side;
* a diversity gate: a proposal whose diff overlaps one of the last K rejected diffs (or an earlier
  proposal of the same round) above a threshold is re-proposed once with a "different cluster" note,
  then dropped at no rollout cost;
* an optional consolidation mode: a cross-trace summary of what recurs across the cluster's failures,
  and instructions to write per-trace lessons and merge the recurring ones into a single edit.
"""

from __future__ import annotations

import difflib
import json
import math
import re
import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from .evaluator import thread_map


@dataclass(frozen=True)
class HC2Params:
    """Spec keys are ``hc2_<field>``; ``hc2: true`` turns HC-2 on."""
    k: int = 4                       # proposals per round (shrunk by ``plan_round`` to what fits)
    minibatch: int = 12              # failing F tasks the clusters are drawn from, per round
    per_cluster: int = 4             # failing traces shown per proposal
    pairs: int = 3                   # contrastive pass/fail pairs shown per proposal
    cluster_sim: float = 0.3         # token-Jaccard above which two failures share a cluster
    diversity_threshold: float = 0.6  # diff overlap at/above which a proposal is a near-duplicate
    diversity_window: int = 0        # last-N rejected diffs compared against (0 = K)
    retries: int = 1                 # re-proposals for a near-duplicate before it is dropped
    consolidate: bool = False        # cross-trace consolidation mode
    broad_slot: bool = False         # one proposal per round sees the failing traces of ALL clusters
    broad_max: int = 24              # failing tasks (one trace each) the broad slot is shown
    cross_traces: int = 2            # traces of each OTHER cluster shown to a cluster slot (0 = its cluster only)
    merge_survivors: bool = False    # merge last round's positive-screen candidates into one candidate
    merge_max: int = 3               # candidates merged at most
    cheap_accept: bool = False       # accept on the rung-2 screen; validate the accepted chain once at the end
    cheap_z: float = 1.0             # rung-2 paired z a cheap accept needs (mean >= the P2 dmin as well)
    validate_trials: int = 0         # trials per C task of each end-of-search validation arm (0 = num_trials)
    max_rounds: int = 0              # 0 = the run's max_iterations
    final_estimate_trials: int = 4   # trials per arm of the closing champion-vs-seed estimate on C;
                                     # 0 = no reservation and no estimate (for budgets that cannot afford it)

    @classmethod
    def from_spec(cls, spec: dict | None):
        """``None`` unless ``hc2: true``; else validated params. Requires rule P2 on pooled splits."""
        spec = spec or {}
        if not spec.get("hc2"):
            return None
        if spec.get("promotion_rule") != "P2" or spec.get("split_mode") != "pooled":
            raise ValueError("hc2: true requires promotion_rule: P2 and split_mode: pooled "
                             "(HC-2 runs on the shared P2 evaluator and its F/C partition)")
        d = cls()
        out = cls(
            k=int(spec.get("hc2_k", spec.get("p2_k", d.k))),
            minibatch=int(spec.get("hc2_minibatch", d.minibatch)),
            per_cluster=int(spec.get("hc2_per_cluster", d.per_cluster)),
            pairs=int(spec.get("hc2_pairs", d.pairs)),
            cluster_sim=float(spec.get("hc2_cluster_sim", d.cluster_sim)),
            diversity_threshold=float(spec.get("hc2_diversity_threshold", d.diversity_threshold)),
            diversity_window=int(spec.get("hc2_diversity_window", d.diversity_window)),
            retries=int(spec.get("hc2_retries", d.retries)),
            consolidate=bool(spec.get("hc2_consolidate", d.consolidate)),
            broad_slot=bool(spec.get("hc2_broad_slot", d.broad_slot)),
            broad_max=int(spec.get("hc2_broad_max", d.broad_max)),
            cross_traces=int(spec.get("hc2_cross_traces", d.cross_traces)),
            merge_survivors=bool(spec.get("hc2_merge_survivors", d.merge_survivors)),
            merge_max=int(spec.get("hc2_merge_max", d.merge_max)),
            cheap_accept=bool(spec.get("hc2_cheap_accept", d.cheap_accept)),
            cheap_z=float(spec.get("hc2_cheap_z", d.cheap_z)),
            validate_trials=int(spec.get("hc2_validate_trials", d.validate_trials)),
            max_rounds=int(spec.get("hc2_max_rounds", d.max_rounds)),
            final_estimate_trials=int(spec.get("hc2_final_estimate_trials", d.final_estimate_trials)))
        if min(out.k, out.minibatch, out.per_cluster, out.broad_max) < 1 or out.pairs < 0 or out.retries < 0 \
            or out.final_estimate_trials < 0 or out.cross_traces < 0 or out.merge_max < 2:
            raise ValueError("hc2_k, hc2_minibatch and hc2_per_cluster must be >= 1; "
                             "hc2_pairs, hc2_retries and hc2_final_estimate_trials >= 0")
        if not 0.0 < out.diversity_threshold <= 1.0:
            raise ValueError("hc2_diversity_threshold must be in (0, 1]")
        return out


# ---- reading F traces ---------------------------------------------------------------------------

@dataclass
class Trace:
    task_id: str
    tag: str
    trial: int
    reward: float
    path: Path
    signature: str = ""


_TOKEN = re.compile(r"[a-z0-9_]{3,}")


def tokens(text: str) -> frozenset:
    return frozenset(_TOKEN.findall((text or "").lower()))


def jaccard(a, b) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def _parse_name(stem: str, task_ids) -> tuple | None:
    """``<task>__<tag>__t<k>`` -> (task, tag, k) for a task in ``task_ids``; None otherwise."""
    head, sep, k = stem.rpartition("__t")
    if not sep or not k.isdigit():
        return None
    pos = head.find("__")
    while pos != -1:
        if head[:pos] in task_ids:
            return head[:pos], head[pos + 2:], int(k)
        pos = head.find("__", pos + 2)
    return None


def _signature(rec: dict) -> str:
    sc, ro = rec.get("score") or {}, rec.get("rollout") or {}
    out = ro.get("output")
    return " ".join(str(x) for x in (sc.get("feedback"), ro.get("error"),
                                     (out if isinstance(out, str) else "")[-400:]) if x)


def read_traces(run_dir, split_dirs, feedback_ids, tag_ok) -> list:
    """Every rollout in ``split_dirs`` whose task is in F and whose tag satisfies ``tag_ok``.

    Filtering by F ids here is what keeps a C trace out, even if an evaluator wrote C rollouts into one
    of the directories scanned.
    """
    ids = set(map(str, feedback_ids))
    out = []
    for sd in split_dirs:
        d = Path(run_dir.rollouts) / sd
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.json")):
            parsed = _parse_name(f.stem, ids)
            if not parsed or not tag_ok(parsed[1]):
                continue
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            reward = float((rec.get("score") or {}).get("reward", 0.0) or 0.0)
            out.append(Trace(parsed[0], parsed[1], parsed[2], reward, f, _signature(rec)))
    return out


def incumbent_tag_ok(cid: str):
    """The incumbent's draws: its own tag, or a round tag (``<round>__<cid>__...``) the evaluator wrote."""
    return lambda tag: cid in tag.split("__")


# ---- clusters, pairs ----------------------------------------------------------------------------

def failing_tasks(traces) -> dict:
    """{task_id: [failing traces]} for tasks with at least one failing draw (reward < 1)."""
    out: dict = {}
    for t in traces:
        if t.reward < 1.0:
            out.setdefault(t.task_id, []).append(t)
    return out


def rotating_minibatch(task_ids, size: int, round_index: int) -> list:
    """A deterministic rotation: sorted ids, window of ``size`` starting at ``round_index * size``."""
    ids = sorted(task_ids)
    if not ids:
        return []
    start = (round_index * size) % len(ids)
    return (ids[start:] + ids[:start])[:size]


def cluster_failures(failed: dict, task_ids, sim: float) -> list:
    """Greedy leader clustering of failing tasks by token overlap of their failure text.

    Returns clusters (lists of task ids) largest first. Tasks with no text of their own each fall into
    a singleton, so a benchmark with opaque feedback still yields distinct clusters.
    """
    toks = {t: frozenset().union(*(tokens(tr.signature) for tr in failed[t])) for t in task_ids}
    clusters: list = []     # [union_tokens, [ids]]
    for t in task_ids:
        best, best_s = None, 0.0
        for c in clusters:
            s = jaccard(toks[t], c[0])
            if s > best_s:
                best, best_s = c, s
        if best is not None and best_s >= sim:
            best[0] = best[0] | toks[t]
            best[1].append(t)
        else:
            clusters.append([toks[t], [t]])
    return [c[1] for c in sorted(clusters, key=lambda c: -len(c[1]))]


def split_to_k(clusters: list, k: int) -> list:
    """Top ``k`` clusters; if there are fewer, halve the largest (interleaved) so each proposal still
    gets a different slice of the failures."""
    clusters = [list(c) for c in clusters]
    while len(clusters) < k:
        clusters.sort(key=len, reverse=True)
        if not clusters or len(clusters[0]) < 2:
            break
        big = clusters.pop(0)
        clusters += [big[0::2], big[1::2]]
    return sorted(clusters, key=len, reverse=True)[:k]


def contrastive_pairs(traces, task_ids, limit: int) -> list:
    """(pass_trace, fail_trace) for tasks the incumbent both passed and failed across its draws."""
    by: dict = {}
    for t in traces:
        if t.task_id in task_ids:
            by.setdefault(t.task_id, []).append(t)
    pairs = []
    for tid in sorted(by):
        good = [t for t in by[tid] if t.reward >= 1.0]
        bad = [t for t in by[tid] if t.reward < 1.0]
        if good and bad:
            pairs.append((good[0], bad[0]))
    return pairs[:limit]


# ---- writing the proposer's view ----------------------------------------------------------------

def scrub_confirm_traces(workdir: Path, confirm_ids) -> int:
    """Delete anything under ``workdir/trajectories`` and ``workdir/contrast`` for a C task id."""
    ids = set(map(str, confirm_ids))
    removed = 0
    for sub in ("trajectories", "contrast"):
        root = workdir / sub
        if not root.is_dir():
            continue
        for f in root.rglob("*"):
            if f.is_file() and any(f.name.startswith(i + "__") for i in ids):
                f.unlink()
                removed += 1
    return removed


def write_cluster_context(workdir: Path, *, cluster, failed: dict, traces, params: HC2Params,
                          confirm_ids, others=(), limit: int | None = None) -> dict:
    """Replace ``workdir/trajectories`` with this proposal's F failures; add ``contrast/`` pairs.

    ``cluster`` tasks come first (``limit`` of them, default ``per_cluster``); ``others`` are the tasks of
    the other clusters, one failing trace each, so the proposer sees every failure type."""
    dst = workdir / "trajectories"
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    shown = []
    for tid in list(cluster)[:limit or params.per_cluster]:
        tr = failed[tid][0]
        shutil.copyfile(tr.path, dst / tr.path.name)
        shown.append(tid)
    extra = []
    for tid in others:
        if tid in shown or tid not in failed:
            continue
        tr = failed[tid][0]
        shutil.copyfile(tr.path, dst / tr.path.name)
        extra.append(tid)
    contrast = workdir / "contrast"
    if contrast.exists():
        shutil.rmtree(contrast)
    pairs = contrastive_pairs(traces, set(cluster), params.pairs) if params.pairs else []
    for i, (good, bad) in enumerate(pairs):
        d = contrast / f"pair_{i}_{good.task_id}"
        d.mkdir(parents=True)
        shutil.copyfile(good.path, d / ("PASS__" + good.path.name))
        shutil.copyfile(bad.path, d / ("FAIL__" + bad.path.name))
    scrub_confirm_traces(workdir, confirm_ids)
    return {"tasks": shown, "others": extra, "pairs": [g.task_id for g, _ in pairs]}


def cross_trace_summary(cluster, failed: dict) -> str:
    """Terms that recur across the cluster's failing traces (deterministic; no model call)."""
    per = [tokens(" ".join(t.signature for t in failed[tid])) for tid in cluster]
    counts: dict = {}
    for s in per:
        for w in s:
            counts[w] = counts.get(w, 0) + 1
    common = sorted((w for w, c in counts.items() if c >= 2), key=lambda w: (-counts[w], w))[:25]
    lines = [f"# Cross-trace summary ({len(cluster)} failing tasks)", "",
             "Terms that appear in the failure text of 2 or more of these tasks:", ""]
    lines += [f"- {w} (in {counts[w]} of {len(per)})" for w in common] or ["- (no recurring terms)"]
    return "\n".join(lines) + "\n"


CONSOLIDATE_NOTE = (
    "Consolidation mode: for each trace under trajectories/ write one short lesson to "
    "notes/lessons.md (what went wrong, in general terms). Then merge the lessons that recur across "
    "two or more distinct traces into ONE general edit. Do not encode any single task's specifics. "
    "See cross_trace_summary.md for recurring terms.")


GOAL_NOTE = ("Aim for the edit with the largest expected reward gain on the WHOLE task distribution, not for "
             "the single task in front of you: prefer a general rule, check or procedure that lifts many "
             "tasks and failure types over a patch for one task, and ship as many such fixes as you can "
             "support with the traces.")


def build_instructions(ctx, adapter_val, cluster, *, parent_dir: Path, algorithm: str, params: HC2Params,
                       shown: dict, rejected_notes, retry_note: str = "", role: str = "cluster") -> str:
    if role == "broad":
        label = f"failing traces of {len(cluster)} task(s) across ALL failure types on the feedback stratum"
        lead = ("This proposal is one of several made in parallel from the same incumbent. Your traces in "
                "trajectories/ span ALL failure types of the incumbent (there is no single primary cluster). "
                "Read them, find the root causes that cost the most reward in total, and fix as many of them "
                "as you can in this one edit.")
    else:
        label = f"failure cluster of {len(cluster)} task(s) on the feedback stratum"
        lead = ("This proposal is one of several made in parallel from the same incumbent. The first traces in "
                "trajectories/ are your primary cluster (listed below); the remaining traces are failures of "
                "the other clusters. Fix the primary cluster's root cause first, then any other failure type "
                "you can see; siblings start from other clusters, so do not skip a fix because a sibling "
                "might also make it.")
    extra = [lead + " contrast/ holds pass/fail pairs of the same task.", GOAL_NOTE,
             "Cluster tasks: " + ", ".join(map(str, cluster[:params.broad_max]))]
    if rejected_notes:
        extra.append("Recent rejected edits (do not repeat them or their near-duplicates):\n"
                     + "\n".join(f"- {n}" for n in rejected_notes))
    if params.consolidate:
        extra.append(CONSOLIDATE_NOTE)
    if retry_note:
        extra.append(retry_note)
    return ctx.instructions(adapter_val, list(cluster), label, algorithm=algorithm,
                            parent_dir=parent_dir, extra="\n\n".join(extra))


# ---- merging survivors --------------------------------------------------------------------------

def merge_trees(base_dir: Path, ours_dir: Path, variants, out_dir: Path) -> dict:
    """Three-way merge of ``variants`` ([(cid, dir)]) onto ``ours_dir``, with ``base_dir`` as the common
    ancestor. ``out_dir`` starts as a copy of ``ours_dir``. File by file: a file only a variant changed is
    taken; a file both changed is merged with ``git merge-file`` when that is clean, otherwise the change
    already in place wins and the file is reported in ``skipped``. Returns ``{"merged": [cid], "skipped": [...]}``."""
    import subprocess
    import tempfile
    base_dir, ours_dir, out_dir = Path(base_dir), Path(ours_dir), Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(ours_dir, out_dir)
    base = {r: (base_dir / r).read_bytes() for r in _files(base_dir)}
    merged, skipped = [], []
    for cid, vdir in variants:
        vdir, took = Path(vdir), False
        theirs = {r: (vdir / r).read_bytes() for r in _files(vdir)}
        for rel in sorted(set(base) | set(theirs)):
            t, b = theirs.get(rel), base.get(rel)
            if t == b:
                continue
            path = out_dir / rel
            cur = path.read_bytes() if path.is_file() else None
            if cur == t:
                continue
            if cur == b:                                   # nobody else touched it: take the variant's
                if t is None:
                    path.unlink(missing_ok=True)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(t)
                took = True
                continue
            if cur is None or t is None or b is None:
                skipped.append(f"{cid}:{rel}")
                continue
            with tempfile.TemporaryDirectory() as td:
                paths = []
                for name, data in (("cur", cur), ("base", b), ("theirs", t)):
                    q = Path(td) / name
                    q.write_bytes(data)
                    paths.append(str(q))
                r = subprocess.run(["git", "merge-file", "-p", *paths], capture_output=True)
            if r.returncode == 0:
                path.write_bytes(r.stdout)
                took = True
            else:
                skipped.append(f"{cid}:{rel}")
        if took:
            merged.append(cid)
    return {"merged": merged, "skipped": skipped}


def _pool_path(run_dir) -> Path:
    return Path(run_dir.root) / "hc2_merge_pool.json"


def save_merge_pool(run_dir, base_id: str, items: list) -> None:
    """Remember last round's positive-screen candidates (``[{cid, z, mean}]``, best first)."""
    path = _pool_path(run_dir)
    if not items:
        path.unlink(missing_ok=True)
        return
    from .rundir import _atomic_write
    _atomic_write(path, json.dumps({"base": base_id, "items": items}))


def take_merge_pool(run_dir) -> dict | None:
    path = _pool_path(run_dir)
    try:
        pool = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    path.unlink(missing_ok=True)                  # consumed once: a failed merge is never retried
    return pool


# ---- diversity gate -----------------------------------------------------------------------------

_SKIP_DIRS = {"trajectories", "contrast", "guidance", "notes", "__pycache__"}
_SKIP_FILES = {"INSTRUCTIONS.md", "MEMORY.md", "STATE.md", "LEDGER.md", "JOURNAL.md", "RUNMAP.md",
               "PROCESS.md", "cross_trace_summary.md", "DIAGNOSIS.json"}


def _files(root: Path) -> dict:
    from .harness import _SNAPSHOT_IGNORE      # the optimizer's injected scratch is not part of the edit
    skip = _SKIP_DIRS | set(_SNAPSHOT_IGNORE)
    out = {}
    for f in sorted(root.rglob("*")):
        rel = f.relative_to(root)
        if not f.is_file() or rel.parts[0] in skip or rel.name in _SKIP_FILES \
                or rel.parts[0].startswith("."):
            continue
        try:
            out[str(rel)] = f.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            out[str(rel)] = [f"<binary {f.stat().st_size}>"]
    return out


def diff_lines(parent_dir: Path, cand_dir: Path) -> frozenset:
    """The set of changed lines (``+``/``-`` tagged, whitespace-normalised) of cand vs parent."""
    a, b = _files(Path(parent_dir)), _files(Path(cand_dir))
    changed = set()
    for rel in sorted(set(a) | set(b)):
        for ln in difflib.unified_diff(a.get(rel, []), b.get(rel, []), lineterm="", n=0):
            if ln[:1] in "+-" and not ln.startswith(("+++", "---")) and ln[1:].strip():
                changed.add(f"{rel}\t{ln[0]}" + " ".join(ln[1:].split()))
    return frozenset(changed)


def _shingles(lines: frozenset, n: int = 3) -> frozenset:
    """Word n-grams within each changed line (a short line is one shingle), tagged by file and +/-."""
    out = set()
    for ln in lines:
        head, _, body = ln.partition("\t")
        w = body[1:].split()
        out.update((head, body[:1], " ".join(w[i:i + n])) for i in range(max(1, len(w) - n + 1)))
    return frozenset(out)


def diff_overlap(x: frozenset, y: frozenset) -> float:
    """Similarity of two diffs, 0.0 when either is empty: the larger of the Jaccard of the changed lines
    and the Jaccard of their word 3-grams, so a lightly reworded copy of an edit still counts."""
    if not x or not y:
        return 0.0
    lines = len(x & y) / len(x | y)
    sx, sy = _shingles(x), _shingles(y)
    return max(lines, len(sx & sy) / len(sx | sy))


def near_duplicate(diff: frozenset, others, threshold: float):
    """Index of the first diff in ``others`` overlapping ``diff`` at/above ``threshold``, else None."""
    for i, o in enumerate(others):
        if diff_overlap(diff, o) >= threshold:
            return i
    return None


class RejectedDiffs:
    """The last diffs that did not win, persisted in the run dir so a resumed run keeps its memory."""

    def __init__(self, run_dir):
        self.path = Path(run_dir.root) / "hc2_rejected_diffs.json"

    def load(self) -> list:
        try:
            return [frozenset(d["lines"]) for d in json.loads(self.path.read_text(encoding="utf-8"))]
        except (OSError, ValueError, KeyError):
            return []

    def add(self, cid: str, diff: frozenset) -> None:
        try:
            cur = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cur = []
        cur.append({"cid": cid, "lines": sorted(diff)})
        self.path.write_text(json.dumps(cur), encoding="utf-8")

    def last(self, n: int) -> list:
        return self.load()[-n:] if n > 0 else []


# ---- the loop -----------------------------------------------------------------------------------

def _pooled_split_result(traces, tasks):
    """The incumbent's pooled F draws as a ``SplitResult`` for the shared prompt template."""
    from .loop import SplitResult
    by: dict = {}
    for t in traces:
        by.setdefault(t.task_id, []).append(t)
    rows = []
    for tid in sorted(tasks if tasks is not None else by):
        ts = by.get(tid, [])
        if ts:
            rows.append({"task_id": tid, "reward": sum(t.reward for t in ts) / len(ts),
                         "feedback": next((t.signature for t in ts if t.reward < 1.0), "")[:500]})
    mean = sum(r["reward"] for r in rows) / len(rows) if rows else 0.0
    return SplitResult(split="feedback", reward=mean, stderr=0.0, per_task=rows,
                       n_tasks=len(rows), n_scored=len(rows))


def _propose(optimizer, workdir: Path, instructions: str):
    try:
        return optimizer(workdir, instructions), None
    except Exception as e:  # noqa: BLE001 - a failed proposal costs a slot, never the run
        return getattr(e, "cost", None), str(e)


FINAL_TRIALS = 4            # ``P2Evaluator.final_estimate`` default n_trials (champion and seed each)


def final_estimate_cost(evaluator, n_trials: int = FINAL_TRIALS) -> int:
    """Rollouts the final estimate needs: champion and seed, ``n_trials`` each, on every C task."""
    return 2 * int(n_trials) * len(evaluator.confirm_ids())


def _pending_path(run_dir) -> Path:
    return Path(run_dir.root) / "hc2_pending.json"


def _save_pending(run_dir, pend: dict) -> None:
    from .rundir import _atomic_write
    _atomic_write(_pending_path(run_dir), json.dumps(pend))


def _next_cid_base(run_dir) -> int:
    """Highest ``cand_NNNN`` number on disk. Ids cannot come from ``spent.iterations``: a round is one
    iteration but K candidates."""
    best = 0
    for root in (Path(run_dir.root) / "candidates", Path(run_dir.root) / "work"):
        for p in root.glob("cand_*") if root.is_dir() else []:
            m = re.fullmatch(r"cand_(\d+)", p.name.split(".")[0])
            if m:
                best = max(best, int(m.group(1)))
    return best


def _rounds_done(run_dir) -> int:
    """One iteration is recorded per round (``count_iteration``), dropped-only rounds included."""
    return run_dir.spent.iterations


def hc2_loop(adapter, *, run_dir, optimizer, evaluator, params: HC2Params, ctx, max_iterations: int,
             store=None, algorithm: str = "hill-climb:hc2", workers: int = 1) -> dict:
    """Rounds of K parallel proposals judged by ``evaluator`` (a ``P2Evaluator``).

    Concurrency is bounded by ``workers`` in total: jobs fan out over ``thread_map(workers)`` and each
    job runs its rollouts serially (the evaluator's own ``workers`` is forced to 1), so nesting cannot
    multiply the two. An interrupted round (``hc2_pending.json`` + its ``p2/r*.json``) is resumed on
    entry, not re-proposed. One round counts as one iteration and one stall step.
    """
    from . import harness
    rejected, history, store = harness._init_memory_store(run_dir, store)
    rdiffs = RejectedDiffs(run_dir)
    n_rounds = params.max_rounds or max_iterations
    window = params.diversity_window or params.k
    if hasattr(evaluator, "workers"):
        evaluator.workers = 1
    env = dict(adapter=adapter, run_dir=run_dir, evaluator=evaluator, ctx=ctx, rejected=rejected,
               history=history, store=store, rdiffs=rdiffs, workers=workers, algorithm=algorithm, params=params)
    steps, stop = [], ""

    pend = _load_pending(run_dir)
    if pend:
        steps += _finish_round(pend, **env)

    while _rounds_done(run_dir) < n_rounds:
        exhausted, _ = run_dir.budget_exhausted()
        if exhausted:
            break
        # The final estimate is paid for up front, so a budget-bound search cannot spend it: hold
        # its cost while planning, release it before the estimate itself reserves.
        hold = None
        if params.cheap_accept and not (Path(run_dir.root) / "chain_validation.json").exists():
            try:                  # seed + the latest accepted + one fallback arm
                hold = run_dir.reserve_metric_calls(
                    3 * _val_trials(params, evaluator) * len(evaluator.confirm_ids()), label="hc2_validate_chain")
            except Exception:  # noqa: BLE001
                hold = None
        elif params.final_estimate_trials > 0 and _internal_estimate_pending(run_dir):
            try:
                hold = run_dir.reserve_metric_calls(
                    final_estimate_cost(evaluator, params.final_estimate_trials), label="hc2_final_estimate")
            except Exception:  # noqa: BLE001 - cannot be held: the estimate will be skipped and recorded
                hold = None
        try:
            plan = evaluator.plan_round(params.k, incumbent_dir=run_dir.candidate_dir(run_dir.best_id))
        finally:
            run_dir.release_metric_calls(hold)
        if not plan.funded:
            stop = "budget_unfunded"
            break
        pend = _propose_round(plan.k, window, _rounds_done(run_dir), **env, optimizer=optimizer)
        if pend is None:
            stop = "no_failures"
            break
        steps += _finish_round(pend, **env)
    _, why = run_dir.budget_exhausted()
    validation = validate_accepted_chain(evaluator, run_dir, params) if params.cheap_accept else None
    internal = (None if params.cheap_accept
                else final_estimate(evaluator, run_dir, params.final_estimate_trials))
    result = {"algorithm": algorithm, "best_id": run_dir.best_id, "iterations": len(steps),
              "accepts": sum(1 for s in steps if s["accepted"]),
              **({"internal_estimate": internal} if internal is not None else {}),
              **({"chain_validation": validation} if validation is not None else {}),
              "stop_reason": why or stop or "max_iterations", "steps": steps}
    (Path(run_dir.root) / "summary.json").write_text(
        json.dumps({k: v for k, v in result.items() if k != "steps"}, indent=2), encoding="utf-8")
    return result


def _load_pending(run_dir):
    try:
        return json.loads(_pending_path(run_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _internal_estimate_pending(run_dir) -> bool:
    return not (Path(run_dir.root) / "internal_estimate.json").exists()


def _prepare(adapter, run_dir, evaluator, ctx, params, view, cid, cl, *, incumbent_dir, traces, failed,
             c_ids, algorithm, notes, retry_note="", others=(), role="cluster"):
    """Build the workdir and the full prompt for one proposal (used for the first try AND retries, so a
    retry never loses the memory/consolidation parts)."""
    wd = Path(run_dir.root) / "work" / cid
    if wd.exists():
        shutil.rmtree(wd)
    wd.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(incumbent_dir, wd)
    ctx.inject(adapter, run_dir, wd, split=evaluator.proposer_split)
    shown = write_cluster_context(wd, cluster=cl, failed=failed, traces=traces, params=params,
                                  confirm_ids=c_ids, others=others,
                                  limit=params.broad_max if role == "broad" else None)
    if params.consolidate:
        (wd / "cross_trace_summary.md").write_text(cross_trace_summary(cl, failed), encoding="utf-8")
    instr = ctx.augment_instructions(
        build_instructions(ctx, view, cl, parent_dir=incumbent_dir, algorithm=algorithm, params=params,
                           shown=shown, rejected_notes=notes, retry_note=retry_note, role=role), wd, run_dir)
    return wd, instr, shown


def _add_cost(costs: dict, cid: str, rep) -> None:
    if isinstance(rep, dict):
        c = costs.setdefault(cid, {"usd": 0.0, "tokens": 0})
        c["usd"] += float(rep.get("cost_usd") or 0.0)
        c["tokens"] += int(rep.get("tokens") or 0)


def _propose_round(k, window, round_index, *, params, adapter, run_dir, evaluator, ctx, rejected, history,
                   store, rdiffs, workers, algorithm, optimizer):
    """Cluster, propose in parallel, apply the diversity gate; persist ``hc2_pending.json``."""
    incumbent_id = run_dir.best_id
    incumbent_dir = run_dir.candidate_dir(incumbent_id)
    f_ids = [str(i) for i in evaluator.feedback_ids()]
    c_ids = [str(i) for i in evaluator.confirm_ids()]
    traces = read_traces(run_dir, (evaluator.proposer_split, "train", "val"), f_ids,
                         incumbent_tag_ok(incumbent_id))
    failed = failing_tasks(traces)
    batch = rotating_minibatch(failed, params.minibatch, round_index)
    all_clusters = cluster_failures(failed, batch, params.cluster_sim)
    if not all_clusters:
        return None
    base = _next_cid_base(run_dir)
    view = _pooled_split_result(traces, None)
    notes = _rejected_notes(run_dir, window)
    kw = dict(incumbent_dir=incumbent_dir, traces=traces, failed=failed, c_ids=c_ids,
              algorithm=algorithm, notes=notes)

    # slots: [merged survivors] + [broad] + clusters, K in all; the merged candidate needs no proposer
    merged = _build_merged(run_dir, incumbent_id, incumbent_dir, base + 1, params) if params.merge_survivors else None
    n_prop = k - (1 if merged else 0)
    slots = []                      # (role, cluster tasks, other tasks shown)
    if params.broad_slot and n_prop >= 1:
        order = sorted(failed, key=lambda t: (-len(failed[t]), t))
        slots.append(("broad", order[:params.broad_max], ()))
    n_cl = n_prop - len(slots)
    for cl in (split_to_k(all_clusters, n_cl) if n_cl > 0 else []):
        others = [t for o in all_clusters if not set(o) & set(cl) for t in o[:params.cross_traces]]
        slots.append(("cluster", cl, others))
    if not slots and not merged:
        return None
    cids = ([merged["cid"]] if merged else []) + [f"cand_{base + (2 if merged else 1) + j:04d}" for j in range(len(slots))]
    prop_cids = cids[1:] if merged else cids
    workdirs, instr, shown = {}, {}, {}
    if merged:
        workdirs[merged["cid"]] = Path(run_dir.root) / "work" / merged["cid"]
        shown[merged["cid"]] = {"tasks": [], "others": [], "pairs": [], "merged_from": merged["from"]}
    for cid, (role, cl, others) in zip(prop_cids, slots):
        workdirs[cid], instr[cid], shown[cid] = _prepare(adapter, run_dir, evaluator, ctx, params, view,
                                                         cid, cl, others=others, role=role, **kw)
    slot_of = {cid: sl for cid, sl in zip(prop_cids, slots)}
    costs, errors = {}, {}
    with ThreadPoolExecutor(max_workers=max(1, min(len(cids), workers))) as pool:
        for cid, (rep, err) in zip(prop_cids, pool.map(lambda c: _propose(optimizer, workdirs[c], instr[c]),
                                                       prop_cids)):
            _add_cost(costs, cid, rep)
            errors[cid] = err

    # diversity gate: against the last K rejected diffs and against earlier proposals this round
    recent = rdiffs.last(window)
    diffs, dropped = {}, {}
    for cid in cids:
        d = diff_lines(incumbent_dir, workdirs[cid])
        if cid not in slot_of:                    # the merged candidate overlaps its sources by design
            if d:
                diffs[cid] = d
            else:
                dropped[cid] = "empty diff"
            continue
        role, cl, others = slot_of[cid]
        for attempt in range(params.retries + 1):
            if not d:
                break
            if near_duplicate(d, recent + list(diffs.values()), params.diversity_threshold) is None:
                break
            if attempt == params.retries:
                dropped[cid] = "near-duplicate of a recent or sibling diff"
                break
            note = ("Your previous attempt duplicated an edit that was already tried. Make a "
                    "different kind of edit, aimed at a different root cause in this cluster.")
            workdirs[cid], i2, shown[cid] = _prepare(adapter, run_dir, evaluator, ctx, params, view, cid,
                                                     cl, retry_note=note, others=others, role=role, **kw)
            rep, err = _propose(optimizer, workdirs[cid], i2)
            _add_cost(costs, cid, rep)            # every attempt is paid for
            errors[cid] = err
            d = diff_lines(incumbent_dir, workdirs[cid])
        if cid in dropped:
            continue
        if not d:
            dropped[cid] = "empty diff" + (f" (optimizer error: {errors[cid][:200]})" if errors[cid] else "")
            continue
        diffs[cid] = d
    for c in costs.values():
        run_dir.update_spent(optimizer_usd=c["usd"], optimizer_tokens=c["tokens"])
    pend = {"incumbent": incumbent_id, "cids": cids, "round_id": None, "dropped": dropped, "shown": shown,
            "merged": merged["from"] if merged else [], "merge_cid": merged["cid"] if merged else None,
            "merge_on": params.merge_survivors,
            "diffs": {c: sorted(d) for c, d in diffs.items()}, "recorded": []}
    _save_pending(run_dir, pend)
    return pend


def _build_merged(run_dir, incumbent_id, incumbent_dir, num, params):
    """Merge last round's positive-screen candidates into ``work/cand_<num>``; None when there is nothing
    new to try (fewer than two survivors on an unchanged incumbent, or a merge that changes nothing)."""
    pool = take_merge_pool(run_dir)
    if not pool:
        return None
    items = [i for i in pool["items"] if Path(run_dir.candidate_dir(i["cid"])).is_dir()][:params.merge_max]
    if len(items) < (2 if pool["base"] == incumbent_id else 1):
        return None
    cid = f"cand_{num:04d}"
    out = Path(run_dir.root) / "work" / cid
    out.parent.mkdir(parents=True, exist_ok=True)
    res = merge_trees(run_dir.candidate_dir(pool["base"]), incumbent_dir,
                      [(i["cid"], run_dir.candidate_dir(i["cid"])) for i in items], out)
    if not res["merged"] or not diff_lines(incumbent_dir, out):
        shutil.rmtree(out, ignore_errors=True)
        return None
    run_dir.log_event("hc2_merge", cid=cid, sources=res["merged"], skipped=res["skipped"])
    return {"cid": cid, "from": res["merged"]}


def _verdicts(d, cls) -> dict:
    return {c: cls(**v) for c, v in (d or {}).items()}


def _open_or_resume(evaluator, run_dir, pend, live, incumbent):
    """The round of this pending set: the one already on disk if there is one, else a new one."""
    if pend.get("round_id"):
        return evaluator.resume_round(pend["round_id"])
    pdir = evaluator._round_dir()   # moved under private/ by the gate; ask it, do not hard-code
    for f in sorted(pdir.glob("r*.json"), reverse=True) if pdir.is_dir() else []:
        try:
            st = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if set(st.get("candidates", {})) == set(live):
            return evaluator.resume_round(st["round_id"])
    return evaluator.open_round(live, (pend["incumbent"], run_dir.candidate_dir(pend["incumbent"])))


def _cheap_confirm(rnd, rung2, cheap_z, dmin):
    """``hc2_cheap_accept``: the best rung-2 survivor with mean >= dmin and z >= cheap_z is the champion
    without a C confirmation (the accepted chain is validated once at the end of the search)."""
    from .evaluator import ConfirmVerdict
    ok = [(v.z, c, v) for c, v in rung2.items() if v.status == "advance" and v.mean >= dmin and v.z >= cheap_z]
    out = {c: ConfirmVerdict(c, "reject", v.mean, v.z, v.n, "cheap screen: below the accept bar")
           for c, v in rung2.items() if v.status == "advance"}
    if ok:
        _, cid, v = max(ok)
        out[cid] = ConfirmVerdict(cid, "accept", v.mean, v.z, v.n,
                                  f"cheap accept on the screen (mean {v.mean:+.3f}, z {v.z:.2f}); validated at the end")
        rnd.state["champion"] = cid
    rnd.state["confirms"] = {c: vars(v) for c, v in out.items()}
    rnd.state["stage"] = "closed"
    rnd._save()
    return out


def _drive(rnd, map_fn, params=None):
    """Run (or finish) a round. Idempotent: finished jobs are skipped, a closed round is only read."""
    from .evaluator import ConfirmVerdict, RungVerdict
    st = rnd.state
    if st.get("stage") == "closed":
        return (_verdicts(st["rungs"].get("1"), RungVerdict), _verdicts(st["rungs"].get("2"), RungVerdict),
                _verdicts(st.get("confirms"), ConfirmVerdict))
    rung1 = rnd.run_rung(1, map_fn=map_fn)
    rung2, confirm = {}, {}
    if any(v.status == "advance" for v in rung1.values()):
        rung2 = rnd.run_rung(2, map_fn=map_fn)
        if any(v.status == "advance" for v in rung2.values()):
            if params is not None and params.cheap_accept:
                confirm = _cheap_confirm(rnd, rung2, params.cheap_z, rnd.ev.params.dmin)
            else:
                confirm = rnd.confirm(map_fn=map_fn)
    return rung1, rung2, confirm


def _finish_round(pend, *, adapter, run_dir, evaluator, ctx, rejected, history, store, rdiffs, workers,
                  algorithm, params=None):
    """Evaluate (or resume) a proposed round, apply its champion, record every candidate once."""
    from . import harness
    from .evaluator import thread_map
    cids = pend["cids"]
    workdirs = {c: Path(run_dir.root) / "work" / c for c in cids}
    live = {c: workdirs[c] for c in cids if c in pend["diffs"]}
    rung1 = rung2 = confirm = {}
    champion = None
    if live:
        rnd = _open_or_resume(evaluator, run_dir, pend, live, None)
        if pend.get("round_id") != rnd.round_id:
            pend["round_id"] = rnd.round_id
            _save_pending(run_dir, pend)
        rung1, rung2, confirm = _drive(rnd, thread_map(workers), params)
        champion = rnd.champion
        if _merge_on(pend):
            pos = sorted((c for c, v in rung1.items()
                          if v.mean > 0 and c != champion and c not in pend.get("merged", [])
                          and c != pend.get("merge_cid")), key=lambda c: -rung1[c].z)
            save_merge_pool(run_dir, pend["incumbent"],
                            [{"cid": c, "z": rung1[c].z, "mean": rung1[c].mean} for c in pos])
    if champion and run_dir.best_id != champion:
        run_dir.snapshot(champion, workdirs[champion], ignore=_snap_ignore(harness))
        run_dir.set_best(champion)
        if params is not None and params.cheap_accept:
            _chain_add(run_dir, champion)
    statuses = {c: _status(pend, c, rung1.get(c), rung2.get(c), confirm.get(c)) for c in cids}
    round_indecisive = champion is None and all(s[2] for s in statuses.values())
    lead = champion or next((c for c in cids if c in live), cids[0])
    steps = []
    for cid in cids:
        if cid in pend["recorded"]:
            continue
        status, reason, indecisive = statuses[cid]
        steps.append(_record(
            run_dir, harness, cid, pend["incumbent"], workdirs[cid], status, reason,
            indecisive=(round_indecisive if cid == lead and champion is None else indecisive),
            accepted=cid == champion, counts=cid == lead, rv=rung2.get(cid) or rung1.get(cid),
            ctx=ctx, rejected=rejected, history=history, store=store, shown=pend["shown"][cid],
            diff=frozenset(pend["diffs"][cid]) if cid in pend["diffs"] else None, rdiffs=rdiffs))
        pend["recorded"].append(cid)
        _save_pending(run_dir, pend)
    run_dir.log_event("hc2_round", incumbent=pend["incumbent"], candidates=cids,
                      dropped=sorted(pend["dropped"]), champion=champion, k=len(cids))
    _pending_path(run_dir).unlink(missing_ok=True)
    return steps


def _chain_path(run_dir) -> Path:
    return Path(run_dir.root) / "hc2_chain.json"


def _chain(run_dir) -> list:
    try:
        return list(json.loads(_chain_path(run_dir).read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return []


def _chain_add(run_dir, cid) -> None:
    from .rundir import _atomic_write
    chain = _chain(run_dir)
    if cid not in chain:
        _atomic_write(_chain_path(run_dir), json.dumps(chain + [cid]))


def _val_trials(params, evaluator) -> int:
    return params.validate_trials or int(getattr(getattr(evaluator, "params", None), "trials", 1) or 1)


def validate_accepted_chain(evaluator, run_dir, params) -> dict | None:
    """``hc2_cheap_accept``: measure the accepted chain on C once and keep the latest accepted candidate that
    beats the seed there (else the previous one, down to the seed). C only ever decides here, so the
    screen-time winner's curse cannot reach the returned champion. ``None`` when nothing was accepted."""
    chain = _chain(run_dir)
    out_path = Path(run_dir.root) / "chain_validation.json"
    if out_path.exists():
        return json.loads(out_path.read_text(encoding="utf-8"))
    if not chain:
        return None
    res = evaluator.validate_chain([(c, run_dir.candidate_dir(c)) for c in chain], run_dir.candidate_dir("seed"),
                                   n_trials=_val_trials(params, evaluator))
    out_path.write_text(json.dumps(res, indent=2), encoding="utf-8")
    if res["chosen"] != run_dir.best_id:
        run_dir.set_best(res["chosen"])
    return res


def _merge_on(pend) -> bool:
    return bool(pend.get("merge_on"))


def _snap_ignore(harness):
    return tuple(harness._SNAPSHOT_IGNORE) + ("contrast", "notes", "cross_trace_summary.md")


def _status(pend, cid, v1, v2, cv):
    """(status, reason, indecisive) for one candidate. Only the C verdict BIT is ever written."""
    if cid in pend["dropped"]:
        return "dropped", f"hc2 diversity gate: {pend['dropped'][cid]}", True
    if cv is not None:
        return cv.status, f"P2 confirmation {cv.bit()}", cv.status == "unconfirmed"
    rv = v2 or v1
    if rv is not None:
        return rv.status, f"P2 rung {'2' if v2 else '1'}: {rv.status}", rv.status == "unfunded"
    return "unevaluated", "not evaluated", True


def _rejected_notes(run_dir, n: int) -> list:
    p = Path(run_dir.rejected_path)
    try:
        recs = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    except (OSError, ValueError):
        return []
    return [f"{r.get('candidate_id')}: {r.get('summary', '')[:160]} ({r.get('reason', '')[:120]})"
            for r in recs[-n:]]


def _record(run_dir, harness, cid, parent_id, workdir, status, reason, *, indecisive, accepted, counts, rv,
            ctx, rejected, history, store, shown, diff, rdiffs) -> dict:
    """Write one candidate's record. Only the round's lead candidate counts as an iteration / stall step."""
    run_dir.snapshot(cid, workdir, ignore=_snap_ignore(harness))
    harness.record_iteration(run_dir, workdir, cid, parent_id=parent_id, accepted=accepted,
                             reason=reason, val=None, parent_val=None, indecisive=indecisive,
                             memory_skill=ctx.memory_skill, count_iteration=counts,
                             hc2={"status": status, "tasks": shown["tasks"], "pairs": shown["pairs"],
                                  "feedback_mean": getattr(rv, "mean", None)}, round_status=status)
    summary = f"candidate {cid} ({status})"
    if accepted:
        if history is not None:
            history.add(cid, summary, getattr(rv, "mean", 0.0) or 0.0)
    elif not indecisive and rejected is not None:
        rejected.add(cid, summary, reason, getattr(rv, "mean", None))
    if not indecisive and not accepted and diff is not None:
        rdiffs.add(cid, diff)
    if store is not None and not indecisive:
        store.commit(f"hc2 {'ACCEPT' if accepted else 'reject'} {summary}",
                     tag=("best" if accepted else None), accepted=accepted)
    return {"candidate_id": cid, "accepted": accepted, "status": status, "reason": reason,
            "workdir": str(workdir)}


def final_estimate(evaluator, run_dir, n_trials: int = FINAL_TRIALS):
    """Champion vs seed on C with fresh trials, once, as a FINAL phase after the search.

    Same file and schema as ``harness._internal_estimate`` (which ``hill_climb_loop`` uses), so whichever
    runs first wins and the estimate is never paid for twice. It is charged against ``max_metric_calls``
    through the evaluator's reservation (``budget_reserve``); when the remaining budget cannot fund it the
    estimate is skipped and recorded, never run over budget. ``None`` when the champion is the seed.
    ``n_trials == 0`` disables it: nothing is reserved or run, and ``skipped="disabled"`` is logged."""
    from .rundir import BudgetExhausted
    if n_trials <= 0:
        run_dir.log_event("p2_final_estimate", skipped="disabled")
        return {"skipped": "disabled"}
    best = run_dir.best_id
    path = Path(run_dir.root) / "internal_estimate.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if not best or best == "seed":
        return None
    left = run_dir.remaining_metric_calls()
    need = final_estimate_cost(evaluator, n_trials)
    try:
        if left is not None and need > left:
            # Both arms or neither: running the champion arm alone would spend and then fail.
            raise BudgetExhausted(f"the final estimate needs {need} rollouts, {left} remain")
        out = evaluator.final_estimate(run_dir.candidate_dir(best), run_dir.candidate_dir("seed"),
                                       n_trials=n_trials)
    except BudgetExhausted as e:
        out = {"skipped": "budget", "reason": str(e)[:200]}
        run_dir.log_event("p2_final_estimate", skipped="budget")
    out = {k: (None if isinstance(v, float) and not math.isfinite(v) else v)
           for k, v in out.items()}
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out
