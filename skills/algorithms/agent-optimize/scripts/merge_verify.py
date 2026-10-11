"""merge_verify -- interaction-aware verification of a merged candidate (opt-in: spec ``merge_verify``).

``merge_n`` builds M = A+B by a mechanical 3-way fold and predicts interference with a heuristic. This
module MEASURES it: parent P, both branches and the merge are evaluated on the SAME block of tasks and
the SAME fresh trial indices, so interaction = Delta(M) - Delta(A) - Delta(B) is a paired quantity.

Fresh trials matter. The block is chosen from A's and B's observed wins, so measuring A and B on the
trials that produced those wins inflates Delta(A), Delta(B) (winner's curse) and biases the interaction
negative; every arm is therefore run at one common trial offset ``k0`` beyond any trial it already has.

Verdicts (parameters in :class:`MergeVerifyParams`): ``pass`` -> eligible for the normal promote (full
unmasked val, rule P when enabled); ``loses`` -> the merge is worse than the better parent or the
interaction is significantly negative: the parents are RETAINED and :func:`ddmin` can localize the
interfering hunks; ``inconclusive`` -> buy another round of fresh trials, up to ``max_rounds``, then stop
(an inconclusive merge is not promoted).

Pure except :func:`hunks` / :func:`materialize` (files). Prior art: Zeller's ddmin; no novelty claim.
"""

from __future__ import annotations

import math
import random
import shutil
from dataclasses import dataclass
from pathlib import Path

import _bootstrap  # noqa: F401
from cap_evolve import mdblocks

import funcmerge

EPS = 1e-9
ARMS = ("P", "A", "B", "M")


@dataclass(frozen=True)
class MergeVerifyParams:
    n: int = 3                  # fresh trials per cell per round
    max_rounds: int = 3
    n_sentinels: int = 3
    dmin: float = 0.02          # min gain of M over the better parent on the block
    z_pass: float = 1.645
    min_block: int = 5          # fewer paired tasks than this is never enough (SE=0 would pass on infinity)
    z_lose: float = 1.0
    z_int: float = 1.645
    dd_budget: int = 12
    seed: int = 0


def enabled(spec: dict | None = None) -> bool:
    import os
    env = os.environ.get("CAPEVOLVE_MERGE_VERIFY", "").strip().lower()
    if env:
        return env in ("1", "true", "yes", "on")
    return bool((spec or {}).get("merge_verify"))


def params_from_spec(spec: dict | None) -> MergeVerifyParams:
    raw = (spec or {}).get("merge_verify")
    raw = raw if isinstance(raw, dict) else {}
    return MergeVerifyParams(**{k: type(getattr(MergeVerifyParams, k))(v) for k, v in raw.items()
                                if k in MergeVerifyParams.__dataclass_fields__})


# ---- block ------------------------------------------------------------------------------------

def wins_losses(per_task: dict[str, float], base: dict[str, float], eps: float = EPS):
    """(wins, losses): tasks where ``per_task`` is above / below ``base`` (shared tasks only)."""
    shared = set(per_task) & set(base)
    return ({t for t in shared if per_task[t] > base[t] + eps}, {t for t in shared if per_task[t] < base[t] - eps})


def select_block(wins: dict[str, set], losses: dict[str, set], all_tasks, n_sentinels: int = 3,
                 seed: int = 0) -> dict:
    """Union of each branch's observed wins and known losses plus ``n_sentinels`` random draws from the
    rest (seeded, so reproducible). Inclusion probabilities are recorded: 1.0 for the deterministic part,
    ``k / n_rest`` for a sentinel, so the sentinels can be reweighted to the unselected tasks."""
    det = set().union(*wins.values(), *losses.values()) if (wins or losses) else set()
    det = {str(t) for t in det}
    rest = sorted({str(t) for t in all_tasks} - det)
    k = min(max(0, int(n_sentinels)), len(rest))
    sent = sorted(random.Random(seed).sample(rest, k)) if k else []
    p = (k / len(rest)) if rest else 0.0
    return {"ids": sorted(det | set(sent)), "deterministic": sorted(det), "sentinels": sent,
            "n_rest": len(rest), "inclusion": {**{t: 1.0 for t in det}, **{t: p for t in sent}}}


# ---- statistics -----

def _paired(v) -> tuple[float, float, int]:
    """(mean, SE, n) of a per-task vector; SE = sd/sqrt(n), 0.0 when n < 2."""
    n = len(v)
    if n == 0:
        return 0.0, 0.0, 0
    m = sum(v) / n
    return m, (math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1) / n) if n > 1 else 0.0), n


def _z(m: float, se: float) -> float:
    return m / se if se > 0 else (math.inf if m > 0 else -math.inf if m < 0 else 0.0)


def arm_task_means(cells: dict[str, dict[tuple, float]], ids) -> dict[str, dict[str, float]]:
    """``cells[arm][(task, k)] = reward`` -> ``{arm: {task: mean}}`` over the (task, k) cells that EVERY
    arm has, so each arm sees identical seeds. A task with no common cell is dropped."""
    common = None
    for arm in ARMS:
        keys = {c for c in cells.get(arm, {}) if c[0] in set(map(str, ids))}
        common = keys if common is None else common & keys
    out = {arm: {} for arm in ARMS}
    for task in sorted({t for t, _ in (common or ())}):
        ks = [c for c in common if c[0] == task]
        for arm in ARMS:
            out[arm][task] = sum(cells[arm][c] for c in ks) / len(ks)
    return out


def analyse(means: dict[str, dict[str, float]]) -> dict:
    """Interaction and gain statistics from per-task means ``{P, A, B, M}``."""
    tasks = sorted(set.intersection(*(set(means[a]) for a in ARMS)))
    P, A, B, M = (means[a] for a in ARMS)
    dA = {t: A[t] - P[t] for t in tasks}
    dB = {t: B[t] - P[t] for t in tasks}
    dM = {t: M[t] - P[t] for t in tasks}
    i_vec = [dM[t] - dA[t] - dB[t] for t in tasks]
    mA, mB = (sum(d.values()) / len(tasks) if tasks else 0.0 for d in (dA, dB))
    best = "A" if mA >= mB else "B"
    g_vec = [M[t] - (A if best == "A" else B)[t] for t in tasks]

    def st(v):
        m, se, n = _paired(v)
        z = _z(m, se) if n >= 2 else 0.0
        return {"mean": m, "se": se, "z": z, "n": n}
    return {"tasks": tasks, "delta": {"A": st([dA[t] for t in tasks]), "B": st([dB[t] for t in tasks]),
                                      "M": st([dM[t] for t in tasks])},
            "interaction": st(i_vec), "best_parent": best, "gain": st(g_vec),
            "interference_tasks": [t for t, g in zip(tasks, g_vec) if g < -EPS]}


def verdict(stats: dict, p: MergeVerifyParams) -> tuple[str, str]:
    g, i = stats["gain"], stats["interaction"]
    if g["n"] < p.min_block:
        return "inconclusive", f"only {g['n']} paired task(s) (< min_block {p.min_block}): too few to judge"
    neg_int = i["z"] <= -p.z_int and i["mean"] <= -p.dmin   # significant AND at least dmin large
    if g["mean"] >= p.dmin and g["z"] >= p.z_pass and not neg_int:
        return "pass", f"merge beats {stats['best_parent']} by {g['mean']:+.4f} (z {g['z']:.2f}); interaction {i['mean']:+.4f} (z {i['z']:.2f})"
    if (g["mean"] < 0 and g["z"] <= -p.z_lose) or (neg_int and g["mean"] < p.dmin):
        return "loses", f"merge vs {stats['best_parent']} {g['mean']:+.4f} (z {g['z']:.2f}); interaction {i['mean']:+.4f} (z {i['z']:.2f})"
    return "inconclusive", f"merge vs {stats['best_parent']} {g['mean']:+.4f} (z {g['z']:.2f}); interaction z {i['z']:.2f}"


def run_verification(measure, ids, k0: int, p: MergeVerifyParams) -> dict:
    """Evaluate P, A, B, M on ``ids`` at fresh trial indices and decide, buying rounds while the verdict
    is inconclusive. ``measure(arm, ids, offset, n) -> {(task, k): reward}`` runs one arm (the verb wraps
    ``evaluate/run.py --trial-offset``). Every arm uses the SAME offset in a round."""
    cells = {a: {} for a in ARMS}
    stats, why, v = None, "", "inconclusive"
    rounds = 0
    for r in range(max(1, p.max_rounds)):
        offset = k0 + r * p.n
        for arm in ARMS:
            cells[arm].update(measure(arm, ids, offset, p.n))
        rounds = r + 1
        means = arm_task_means(cells, ids)
        stats = analyse(means)
        v, why = verdict(stats, p)
        if v != "inconclusive":
            break
    return {"verdict": v, "reason": why, "rounds": rounds, "k0": k0, "n": p.n, "stats": stats, "means": means,
            "rollouts": sum(len(c) for c in cells.values())}


# ---- delta debugging --------------------------------------------------------------------------

def ddmin(units: list, is_bad, max_tests: int = 12) -> dict:
    """Zeller's ddmin, bounded. ``is_bad(subset)`` is True when applying only ``subset`` still shows the
    failure. Returns the smallest bad subset found; ``exhausted`` when the test budget ran out first."""
    cache: dict = {}
    log: list = []

    def test(sub):
        key = frozenset(sub)
        if key not in cache:
            if len(cache) >= max_tests:
                raise _Budget
            cache[key] = bool(is_bad(sorted(sub, key=units.index)))
            log.append({"subset": sorted(sub, key=units.index), "bad": cache[key]})
        return cache[key]

    cur, n, exhausted = list(units), 2, False
    try:
        if not test(cur):
            return {"minimal": None, "tests": len(cache), "exhausted": False, "reproducible": False, "log": log}
        while len(cur) >= 2:
            size = max(1, len(cur) // n)
            chunks = [cur[i:i + size] for i in range(0, len(cur), size)]
            for ch in chunks:
                if test(ch):
                    cur, n = ch, 2
                    break
            else:
                for ch in chunks:
                    comp = [u for u in cur if u not in ch]
                    if comp and test(comp):
                        cur, n = comp, max(n - 1, 2)
                        break
                else:
                    if n >= len(cur):
                        break
                    n = min(len(cur), n * 2)
    except _Budget:
        exhausted = True
        bad = [k for k, v in cache.items() if v]
        cur = sorted(min(bad, key=len), key=units.index) if bad else cur
    return {"minimal": cur, "tests": len(cache), "exhausted": exhausted, "reproducible": True, "log": log}


class _Budget(Exception):
    pass


# ---- hunks ------------------------------------------------------------------------------------

def _files(root: Path) -> dict[str, Path]:
    from merge import _capability_files
    from cap_evolve.harness import _SNAPSHOT_IGNORE
    return _capability_files(root, set(_SNAPSHOT_IGNORE) | {"PROCESS.md", "__pycache__", "DIAGNOSIS.json"})


def _py_units(base_txt: str, merged_txt: str):
    """{name: (base_src|None, merged_src|None)} for changed functions, or None to coarsen to the file."""
    try:
        bp, bb = funcmerge.blocks(base_txt)
        mp, mb = funcmerge.blocks(merged_txt)
    except SyntaxError:
        return None
    if bp != mp or any(n not in mb for n in bb):
        return None                       # preamble edited or a function deleted: whole file
    changed = {n: (bb.get(n), mb[n]) for n in mb if bb.get(n) != mb[n]}
    if any(merged_txt.count(m) != 1 for _, m in changed.values()):
        return None                       # a changed def whose text is not unique cannot be reverted in place
    return changed


def hunks(base_dir: Path, merged_dir: Path) -> list[dict]:
    """The independently revertible edits that turn ``base_dir`` into ``merged_dir``:
    ``{"id", "file", "kind"}`` with ids ``rel`` (whole file) or ``rel::block`` (md section / python def)."""
    bf, mf = _files(base_dir), _files(merged_dir)
    out = []
    for rel in sorted(set(bf) | set(mf)):
        b = bf[rel].read_bytes() if rel in bf else None
        m = mf[rel].read_bytes() if rel in mf else None
        if b == m:
            continue
        units = None
        if b is not None and m is not None:
            try:
                bt, mt = mdblocks.decode(b), mdblocks.decode(m)
            except ValueError:
                bt = mt = None
            if bt is not None and rel.endswith((".md", ".txt")):
                B, M = dict(mdblocks.split(bt)), dict(mdblocks.split(mt))
                units = sorted(k for k in set(B) | set(M) if B.get(k) != M.get(k))
            elif bt is not None and rel.endswith(".py"):
                pu = _py_units(bt, mt)
                units = None if pu is None else sorted(pu)
        if units:
            out += [{"id": f"{rel}::{u}", "file": rel, "kind": "block"} for u in units]
        else:
            out.append({"id": rel, "file": rel, "kind": "file"})
    return out


def _revert_md(base_txt: str, merged_txt: str, revert: set[str]) -> str:
    bs, ms = mdblocks.split(base_txt), mdblocks.split(merged_txt)
    B = dict(bs)
    out = [(i, B[i] if i in revert and i in B else t) for i, t in ms if not (i in revert and i not in B)]
    have = {i for i, _ in out}
    for idx, (i, t) in enumerate(bs):       # blocks the merge deleted, whose deletion is reverted
        if i in revert and i not in dict(ms) and i not in have:
            prev = next((p for p, _ in reversed(bs[:idx]) if p in have), None)
            pos = 0 if prev is None else 1 + next(k for k, (q, _) in enumerate(out) if q == prev)
            out.insert(pos, (i, t))
            have.add(i)
    return "".join(t for _, t in out)


def _revert_py(base_txt: str, merged_txt: str, revert: set[str]) -> str:
    _, bb = funcmerge.blocks(base_txt)
    _, mb = funcmerge.blocks(merged_txt)
    text = merged_txt
    for n in sorted(revert):
        if n not in mb or text.count(mb[n]) != 1:
            raise ValueError(f"cannot revert python hunk {n!r}: its merged text is not unique in the file")
        text = text.replace(mb[n], bb.get(n, ""), 1)
    return text


def materialize(base_dir: Path, merged_dir: Path, keep: set[str], out_dir: Path) -> Path:
    """``merged_dir`` with every hunk NOT in ``keep`` reverted to its ``base_dir`` state, in ``out_dir``.
    keep = all hunks -> the merge; keep = none -> the base."""
    hs = hunks(base_dir, merged_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(merged_dir, out_dir, ignore=shutil.ignore_patterns("__pycache__"))
    bf = _files(base_dir)
    by_file: dict[str, list[dict]] = {}
    for h in hs:
        by_file.setdefault(h["file"], []).append(h)
    for rel, hl in by_file.items():
        dst = out_dir / rel
        reverted = [h for h in hl if h["id"] not in keep]
        if not reverted:
            continue
        if hl[0]["kind"] == "file":
            if rel in bf:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(bf[rel].read_bytes())
            else:
                dst.unlink(missing_ok=True)
            continue
        names = {h["id"].split("::", 1)[1] for h in reverted}
        bt = mdblocks.decode(bf[rel].read_bytes())
        mt = mdblocks.decode(dst.read_bytes())
        dst.write_text(_revert_md(bt, mt, names) if rel.endswith((".md", ".txt")) else _revert_py(bt, mt, names),
                       encoding="utf-8")
    return out_dir
