"""exp895 Meta-Harness arm (issue skillberry-ai/cap-evolve#895 §7.6).

Upstream: stanford-iris-lab/meta-harness @ 8123ccabe2b19fa1123090b2e5f1bacc20963ce8.
  * `claude_wrapper.py` is used BYTE-IDENTICAL (sha256 checked against the pinned clone before use). It is copied
    into the proposer's working directory, which is where upstream keeps it (EVOLVE_DIR), so its
    `.empty_plugins` dir is visible inside the optimizer sandbox.
  * The outer loop follows upstream's reference loops (text_classification/meta_harness.py and
    terminal_bench_2/meta_harness.py): Phase 0 baseline -> per iteration: propose (claude_wrapper.run with the
    meta-harness skill, PROPOSER_ALLOWED_TOOLS, effort="max", timeout 2400 s) -> read pending_eval.json ->
    validate -> benchmark -> update frontier_val.json + evolution_summary.jsonl.
  * Only the evaluation is replaced: every candidate is scored ONLY through
    CommonRollout(run_dir, arm="meta_harness", ...).evaluate(candidate_dir, task_ids, k=3, split=...).
  * Upstream's import check is replaced by the placeholder-contract check, the skills-tree check and the common
    helper lint + smoke (the adapter's own functions, identical to what each rollout runs).

Issue §7.6 specifics:
  * proposer = Claude Code on GLM-5.3 through exp895/tools/sandbox/claude (bwrap; cwd-only writes; GLM gateway only);
  * candidate = {prompt.md, task_template.md, skills/};
  * the proposer sees TRAIN traces only; val 40 x 3 is exposed only as one aggregate score per candidate;
  * k=2 candidates per iteration; selection = highest val mean (not the Pareto frontier);
  * seed traced on all train tasks; each later candidate traced on a rotating 20-task train batch.

Layout of RUN (= runs/meta_harness/<NAME>):
  rollouts.jsonl, budget_state.json        CommonRollout (outside the sandbox)
  frozen/<name>/                           the exact bytes evaluated (copied right after the proposal)
  val_private/<name>.json                  per-task val scores (NEVER under work/, never shown to the proposer)
  work/                                    the proposer's cwd (= upstream EVOLVE_DIR), the only dir it can see
    claude_wrapper.py, .empty_plugins/     upstream, byte-identical
    .claude/skills/meta-harness-spreadsheetbench/SKILL.md
    check_candidate.py
    candidates/<name>/                     seed + every proposal
    traces/<name>/<task_id>.json, _summary.json     train traces
    logs/evolution_summary.jsonl, frontier_val.json, reports/, pending_eval.json, claude_sessions/
  run_summary.json, champion/

Usage: python meta_harness_arm.py --run-dir RUN --seed S --R R --train-ids F --val-ids F [--iterations N]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import random
import re
import shutil
import sys
import time
from pathlib import Path

EXP = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895")
REPO = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/sbv400-main")
UPSTREAM = EXP / "competitors/meta-harness"
UPSTREAM_PIN = "8123ccabe2b19fa1123090b2e5f1bacc20963ce8"
UPSTREAM_WRAPPER = UPSTREAM / "reference_examples/terminal_bench_2/claude_wrapper.py"  # == text_classification copy
ARMDIR = EXP / "arms/meta_harness"
SEED_DIR = REPO / "templates/adapters/spreadsheetbench/seed_capability_v2"
CONTRACT = EXP / "arms/common/SURFACE_CONTRACT.md"
sys.path.insert(0, str(EXP / "arms/common"))

from rollout import BudgetStop, CommonRollout  # noqa: E402
import adapter as _sb  # noqa: E402  (same module CommonRollout wraps)
from cap_evolve import helpers as _helpers  # noqa: E402

ARM = "meta_harness"
K = 3                       # trials per task (§5)
CANDIDATES_PER_ITER = 2     # §7.6 "k=2 candidates per iteration"
TRAIN_BATCH = 20            # §7.6 rotating 20-task train batch
SKILL_NAME = "meta-harness-spreadsheetbench"
SURFACES = ("prompt.md", "task_template.md", "skills")
OPT_TOKEN_CAP = 20_000_000  # §5 runaway guard: non-cache-read optimizer tokens per search
SEED_SHA256 = {  # exp895/BUILD_RECORD.json seed_v2.files_sha256
    "prompt.md": "efa493dd57aee05d5563e4f709d5c9e2fde1fb9fc9f71a3b5a3472a40b723c72",
    "task_template.md": "841967412770441da3ba2785e37194524133aca50a49b489bb57f8e22bb84295",
    "skills/spreadsheet-helpers/SKILL.md": "6679c3f28a9fa25ca376d7d143e32a9d8783bd41e2f6b1829de756b3893dae1f",
}
# Upstream text_classification/meta_harness.py PROPOSER_ALLOWED_TOOLS (TB2 uses the same list), unchanged.
PROPOSER_ALLOWED_TOOLS = ["Read", "Glob", "Grep", "Agent", "Write", "Edit", "Bash"]
NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def tree_sha(d: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(x for x in d.rglob("*") if x.is_file() and "__pycache__" not in x.parts):
        h.update(p.relative_to(d).as_posix().encode() + b"\0" + p.read_bytes() + b"\0")
    return h.hexdigest()


def _ts():
    return time.strftime("[%H:%M:%S]")


def log(msg):
    print(f"{_ts()} {msg}", flush=True)


# ---------------------------------------------------------------------------------------------------------
class Workspace:
    def __init__(self, run: Path):
        self.run = run
        self.work = run / "work"
        self.cands = self.work / "candidates"
        self.traces = self.work / "traces"
        self.logs = self.work / "logs"
        self.frozen = run / "frozen"
        self.val_private = run / "val_private"
        self.pending = self.logs / "pending_eval.json"
        # AUTHORITATIVE selection state lives OUTSIDE the proposer's writable cwd (work/). The proposer only ever
        # sees a mirror copy (frontier_mirror), rewritten from the authoritative file after every update, so an
        # edit to the mirror cannot change which candidate the arm selects.
        self.frontier = run / "selection" / "frontier_val.json"
        self.frontier_mirror = self.logs / "frontier_val.json"
        self.summary = self.logs / "evolution_summary.jsonl"
        self.skill_dir = self.work / ".claude/skills" / SKILL_NAME

    def setup(self):
        for d in (self.cands, self.traces, self.logs / "reports", self.logs / "claude_sessions", self.frozen,
                  self.val_private, self.skill_dir, self.frontier.parent):
            d.mkdir(parents=True, exist_ok=True)
        # upstream claude_wrapper.py, byte-identical, where upstream keeps it (the proposer's cwd)
        up = UPSTREAM_WRAPPER.read_bytes()
        (self.work / "claude_wrapper.py").write_bytes(up)
        # the SpreadsheetBench meta-harness skill, with the common surface contract inserted verbatim
        tmpl = (ARMDIR / "skill" / SKILL_NAME / "SKILL.md.in").read_text(encoding="utf-8")
        assert tmpl.count("<!-- SURFACE_CONTRACT -->") == 1
        (self.skill_dir / "SKILL.md").write_text(
            tmpl.replace("<!-- SURFACE_CONTRACT -->", CONTRACT.read_text(encoding="utf-8").strip()), encoding="utf-8")
        shutil.copy2(ARMDIR / "check_candidate.py", self.work / "check_candidate.py")
        # seed = v2 seed, byte-identical
        for rel, h in SEED_SHA256.items():
            got = _sha((SEED_DIR / rel).read_bytes())
            assert got == h, f"seed file {rel} sha256 {got} != BUILD_RECORD {h}"
        self.freeze_from(SEED_DIR, "seed")
        shutil.copytree(self.frozen / "seed", self.cands / "seed")

    def freeze_from(self, src: Path, name: str) -> Path:
        """Copy ONLY the three surfaces (no __pycache__) to frozen/<name>: these exact bytes are evaluated."""
        dst = self.frozen / name
        if dst.exists():
            raise FileExistsError(dst)
        dst.mkdir(parents=True)
        for s in SURFACES:
            p = src / s
            if p.is_dir():
                shutil.copytree(p, dst / s, ignore=shutil.ignore_patterns("__pycache__"), symlinks=True)
            elif p.is_file():
                shutil.copy2(p, dst / s)
        return dst

    def restore_tampered(self, known: list[str]) -> list[str]:
        """Earlier candidates are read-only by contract: restore any the proposer edited from frozen/ (logged)."""
        fixed = []
        for n in known:
            w = self.cands / n
            fz = self.frozen / n
            if not w.exists() or tree_sha(_surfaces_view(w)) != tree_sha(fz):
                if w.exists():
                    shutil.rmtree(w)
                shutil.copytree(fz, w)
                fixed.append(n)
        return fixed


def _surfaces_view(d: Path) -> Path:
    """A temp view of d holding only its surfaces, for hashing (other files in a candidate dir are ignored)."""
    v = d.parent.parent.parent / ".hashview"
    if v.exists():
        shutil.rmtree(v)
    v.mkdir()
    for s in SURFACES:
        p = d / s
        if p.is_dir():
            shutil.copytree(p, v / s, ignore=shutil.ignore_patterns("__pycache__"), symlinks=True)
        elif p.is_file():
            shutil.copy2(p, v / s)
    return v


# ---------------------------------------------------------------------------------------------------------
def validate_candidate(cdir: Path) -> str | None:
    """Replaces upstream's import check: the adapter's placeholder contract, its skills-tree check, and the
    common helper lint + smoke (cap-evolve's lint_candidate / run_smoke via adapter._helper_gate_error).
    Returns the failure text or None. A failing candidate is STILL evaluated through CommonRollout, where every
    rollout fails the same check before any LLM call: it scores 0 and its full evaluation is debited (the
    common rule for every arm, decisions.md 2026-10-21)."""
    probs = []
    for f in ("prompt.md", "task_template.md"):
        if not (cdir / f).is_file():
            probs.append(f"{f} missing")
    err = _sb._task_template_error(cdir)  # noqa: SLF001
    if err:
        probs.append(err)
    if (cdir / "skills").is_dir():
        bad = _helpers.skills_tree_problems(cdir / "skills")
        if bad:
            probs.append("skills/ tree refused: " + "; ".join(bad[:5]))
        else:
            g = _sb._helper_gate_error(cdir)  # noqa: SLF001
            if g:
                probs.append(g)
    return " | ".join(probs) if probs else None


def render_trace_file(task, cand: str, tr) -> dict:
    trials = []
    for j in range(len(tr.trials)):
        msgs = []
        for m in (tr.traces[j] if j < len(tr.traces) else None) or []:
            if not isinstance(m, dict):
                msgs.append({"role": "?", "content": str(m)})
                continue
            if m.get("role") == "system":   # = this candidate's prompt.md + SKILL.md, already in candidates/
                continue
            c = m.get("content", "")
            if isinstance(c, list):
                c = "\n".join(str(x.get("text", x)) if isinstance(x, dict) else str(x) for x in c)
            msgs.append({"role": m.get("role", "?"), "content": c})
        infra = bool(tr.infra[j]) if j < len(tr.infra) else False
        trials.append({"trial": j, "reward": None if infra else tr.trials[j],
                       "status": "infra_error_not_scored" if infra else ("candidate_error" if tr.errors[j] else "ok"),
                       "scorer_feedback": None if infra else tr.feedback[j],
                       "candidate_error": tr.errors[j], "transcript": msgs})
    return {"task_id": task.id, "candidate": cand, "instruction": task.input["instruction"],
            "instruction_type": task.input["instruction_type"], "answer_position": task.input["answer_position"],
            "mean_reward": None if tr.missing else tr.mean, "trials": trials}


class Evaluator:
    def __init__(self, ro: CommonRollout, ws: Workspace):
        self.ro, self.ws = ro, ws

    def _eval(self, cdir: Path, ids: list[str], split: str, name: str):
        res = self.ro.evaluate(cdir, ids, k=K, candidate_id=name, split=split)
        per_task = dict(res.per_task)
        for _ in range(2):   # a task whose every trial stayed infra is MISSING (§0.3): re-run it, up to 2x
            missing = [t for t in ids if per_task[t].missing]
            if not missing:
                break
            again = self.ro.evaluate(cdir, missing, k=K, candidate_id=name, split=split)
            per_task.update(again.per_task)
        ok = [per_task[t].mean for t in ids if not per_task[t].missing]
        mean = sum(ok) / len(ok) if ok else 0.0
        return per_task, mean, [t for t in ids if per_task[t].missing]

    def train(self, name: str, ids: list[str]) -> tuple[float, list[str]]:
        cdir = self.ws.frozen / name
        per_task, mean, missing = self._eval(cdir, ids, "train", name)
        out = self.ws.traces / name
        out.mkdir(parents=True, exist_ok=True)
        tasks = self.ro._tasks  # noqa: SLF001
        for t, tr in per_task.items():
            (out / f"{t}.json").write_text(json.dumps(render_trace_file(tasks[t], name, tr), indent=1, default=str))
        (out / "_summary.json").write_text(json.dumps({
            "candidate": name, "split": "train", "k": K, "n_tasks": len(ids), "train_mean": round(mean, 4),
            "per_task_mean": {t: (None if r.missing else round(r.mean, 4)) for t, r in per_task.items()},
            "per_task_trials": {t: [None if bad else x for x, bad in zip(r.trials, r.infra)]
                                for t, r in per_task.items()}}, indent=1))
        return mean, missing

    def val(self, name: str, ids: list[str]) -> tuple[float, list[str]]:
        cdir = self.ws.frozen / name
        per_task, mean, missing = self._eval(cdir, ids, "val", name)
        (self.ws.val_private / f"{name}.json").write_text(json.dumps({
            "candidate": name, "val_mean": mean, "missing": missing,
            "per_task_mean": {t: (None if r.missing else r.mean) for t, r in per_task.items()}}, indent=1))
        return mean, missing


# ---------------------------------------------------------------------------------------------------------
def load_claude_wrapper(work: Path):
    """Import the byte-identical upstream claude_wrapper.py from the proposer's working directory."""
    f = work / "claude_wrapper.py"
    assert _sha(f.read_bytes()) == _sha(UPSTREAM_WRAPPER.read_bytes()), "claude_wrapper.py differs from upstream"
    spec = importlib.util.spec_from_file_location("claude_wrapper", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def render_task_prompt(ws: Workspace, iteration: int, n_train: int, n_val: int, batch: list[str], parent: str):
    """Upstream TB2 render_task_prompt, with its benchmark-specific lines replaced for SpreadsheetBench."""
    return (
        f"Run iteration {iteration} of the harness evolution loop (SpreadsheetBench). "
        f"Agent model: Gemma-4-31B-it (fixed). "
        f"Start from candidates/{parent} (the current frontier) as the parent, or any other candidate.\n\n"
        f"## Eval split: {n_train} train tasks (traces visible) + {n_val} held-out selection tasks "
        f"(aggregate score only) x {K} trials\n\n"
        f"Each new candidate is traced on a rotating batch of {len(batch)} train tasks and scored on all "
        f"{n_val} selection tasks. Produce exactly {CANDIDATES_PER_ITER} candidates.\n\n"
        f"## Run directories\n"
        f"All logs and results for this run are under `{ws.logs}/`.\n"
        f"- `{ws.cands}/` — every candidate harness so far (read-only; copy one to start)\n"
        f"- `{ws.traces}/` — full train trajectories per candidate\n"
        f"- `{ws.summary}` — past results\n"
        f"- `{ws.frontier_mirror}` — frontier\n"
        f"- `{ws.logs / 'reports'}/` — post-eval reports\n"
        f"- `{ws.work / 'check_candidate.py'}` — candidate validator\n"
        f"- Write pending_eval.json to: `{ws.pending}`"
    )


def propose_claude(cw, ws: Workspace, task_prompt: str, iteration: int, timeout: int, model: str):
    """Upstream propose_claude, unchanged except model= (the GLM id the sandbox shim serves) and the skill path."""
    os.environ.pop("CLAUDECODE", None)
    saved_key = os.environ.pop("ANTHROPIC_API_KEY", None)
    result = cw.run(
        prompt=task_prompt,
        model=model,
        allowed_tools=PROPOSER_ALLOWED_TOOLS,
        skills=[str(ws.skill_dir)],
        cwd=str(ws.work),
        log_dir=str(ws.logs / "claude_sessions"),
        name=f"iter{iteration}",
        timeout_seconds=timeout,
        effort="max",
    )
    if saved_key:
        os.environ["ANTHROPIC_API_KEY"] = saved_key
    if result.exit_code != 0:
        log(f"  proposer failed exit={result.exit_code}")
        if result.stderr:
            log(f"  {result.stderr[:500]}")
        return False, result
    result.show()
    return ws.pending.exists(), result


def update_frontier(ws: Workspace, scores: dict[str, float]):
    """Selection = highest val mean (§7.6). Ties keep the incumbent. Only aggregates are written (val is hidden)."""
    fr = json.loads(ws.frontier.read_text()) if ws.frontier.exists() else {"candidates": {}}
    for n, v in scores.items():
        fr["candidates"][n] = round(100 * v, 1)
        best = fr.get("_best")
        if best is None or v > best["val_mean_raw"] + 1e-9:   # raw vs raw: ties keep the incumbent (§7.6, D8)
            fr["_best"] = {"system": n, "avg_val": round(100 * v, 1), "val_mean_raw": v}
    ws.frontier.write_text(json.dumps(fr, indent=2))
    ws.frontier_mirror.write_text(json.dumps(fr, indent=2))   # read-only view for the proposer
    return fr


def append_summary(ws, iteration, c, avg_val, best_before, train_mean, batch, gate, timing=None, val_missing=0):
    row = {"iteration": iteration, "system": c["name"], "base": c.get("base", "?"),
           "avg_val": None if avg_val is None else round(100 * avg_val, 1),
           "train_batch_mean": None if train_mean is None else round(100 * train_mean, 1),
           "train_batch": batch, "hypothesis": c.get("hypothesis", ""), "changes": c.get("changes", ""),
           "delta": None if avg_val is None else round(100 * (avg_val - best_before), 1),
           "outcome": ("failed: " + gate[:300]) if gate else
           (f"{100 * avg_val:.1f}% ({100 * (avg_val - best_before):+.1f})" if avg_val is not None else "not evaluated"),
           "val_tasks_missing": val_missing}
    if timing:
        row["timing_s"] = timing
    with open(ws.summary, "a") as f:
        f.write(json.dumps(row) + "\n")


def optimizer_tokens(run: Path, tag: str) -> int:
    """Non-cache-read optimizer tokens so far (gateway ledger), for the §5 20M runaway guard."""
    n = 0
    f = run / "calls_glm.jsonl"
    if not f.exists():
        return 0
    for ln in f.read_text().splitlines():
        try:
            r = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if r.get("event") == "retry" or r.get("tag") != tag:
            continue
        n += int(r.get("prompt_total") or r.get("prompt_tokens") or 0) - int(r.get("cached_tokens") or 0)
        n += int(r.get("completion_tokens") or 0)
    return n


def _ids(path) -> list[str]:
    return [ln.strip() for ln in Path(path).read_text().splitlines() if ln.strip()]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--R", type=int, required=True)
    ap.add_argument("--train-ids", required=True)
    ap.add_argument("--val-ids", required=True)
    ap.add_argument("--iterations", type=int, default=1000, help="upstream --iterations; R binds first by default")
    ap.add_argument("--propose-timeout", type=int, default=2400, help="upstream default 2400 s")
    ap.add_argument("--model", default=os.environ.get("EXP895_OPT_MODEL", "rits/zai-org/glm-5-3"))
    a = ap.parse_args(argv)
    run = Path(a.run_dir)
    t0 = time.time()
    ws = Workspace(run)
    ws.setup()
    cw = load_claude_wrapper(ws.work)
    train, val = _ids(a.train_ids), _ids(a.val_ids)
    ro = CommonRollout(run, arm=ARM, search_seed=a.seed, R=a.R)
    ev = Evaluator(ro, ws)
    opt_tag = os.environ.get("EXP895_OPT_TAG", f"exp895-{ARM}-s{a.seed}:optimizer")
    rng = random.Random(a.seed)
    perm = list(train)
    rng.shuffle(perm)
    bsz = min(TRAIN_BATCH, len(train))
    known = ["seed"]
    stop_reason = ""
    n_eval = 0
    events = []

    # ── Phase 0: baseline = the seed, traced on ALL train tasks, scored on val ──
    log(f"Phase 0: seed  train={len(train)} val={len(val)} k={K} R={a.R}")
    try:
        tm, tmiss = ev.train("seed", train)
        vm, vmiss = ev.val("seed", val)
    except BudgetStop as e:
        raise RuntimeError("R is too small to trace and score the seed") from e
    n_eval += 1
    update_frontier(ws, {"seed": vm})
    append_summary(ws, 0, {"name": "seed", "base": "-", "hypothesis": "v2 seed (baseline)"}, vm, vm, tm, "all",
                   None, val_missing=len(vmiss))
    log(f"  seed: train={100 * tm:.1f}% val={100 * vm:.1f}% spent={ro.spent}/{a.R}")

    per_cand_cost = (bsz + len(val)) * K
    for i in range(a.iterations):
        iteration = i + 1
        if ro.remaining() < per_cand_cost:
            stop_reason = f"budget: remaining {ro.remaining()} < one candidate ({per_cand_cost})"
            break
        used = optimizer_tokens(run, opt_tag)
        if used >= OPT_TOKEN_CAP:
            stop_reason = f"optimizer_token_cap: {used} >= {OPT_TOKEN_CAP}"
            break
        it0 = time.time()
        off = (i * bsz) % len(perm)
        batch = (perm[off:] + perm[:off])[:bsz]
        fr = json.loads(ws.frontier.read_text())
        best_name, best_val = fr["_best"]["system"], fr["_best"]["val_mean_raw"]
        log(f"Iteration {iteration}  frontier={best_name} @ {100 * best_val:.1f}%  batch={len(batch)} tasks")
        if ws.pending.exists():
            ws.pending.unlink()
        ok, _res = propose_claude(cw, ws, render_task_prompt(ws, iteration, len(train), len(val), batch, best_name),
                                  iteration, a.propose_timeout, a.model)
        propose_time = time.time() - it0
        fixed = ws.restore_tampered(known)
        if fixed:
            events.append({"iteration": iteration, "event": "restored_edited_candidates", "names": fixed})
            log(f"  restored earlier candidates the proposer edited: {fixed}")
        if not ok:
            log(f"  FAIL proposer returned no candidates after {propose_time:.0f}s")
            events.append({"iteration": iteration, "event": "no_pending_eval", "propose_s": round(propose_time, 1)})
            continue
        try:
            cands = json.loads(ws.pending.read_text()).get("candidates", [])
        except (json.JSONDecodeError, AttributeError) as e:
            log(f"  FAIL pending_eval.json unreadable: {e}")
            events.append({"iteration": iteration, "event": "pending_eval_unreadable"})
            continue
        # structural checks (upstream would crash or skip): name, dir exists, new this iteration, <= 2 candidates
        valid = []
        for c in cands:
            name = str(c.get("name", ""))
            cdir = ws.cands / name
            why = None
            if not NAME_RE.match(name):
                why = "bad name"
            elif name in known or (ws.frozen / name).exists():
                why = "name already used"
            elif not cdir.is_dir() or cdir.is_symlink():
                why = "candidate dir missing"
            elif any(p.is_symlink() for p in [cdir / "prompt.md", cdir / "task_template.md"] + list(cdir.rglob("*"))):
                # freeze_from runs OUTSIDE the sandbox: a symlink would be followed on the host, so refuse it
                why = "candidate contains a symlink"
            if why:
                log(f"    SKIP {name!r}: {why}")
                events.append({"iteration": iteration, "event": "skipped_candidate", "name": name, "why": why})
                continue
            valid.append(c)
        if len(valid) > CANDIDATES_PER_ITER:
            events.append({"iteration": iteration, "event": "extra_candidates_dropped",
                           "names": [c["name"] for c in valid[CANDIDATES_PER_ITER:]]})
            valid = valid[:CANDIDATES_PER_ITER]
        log(f"  proposed {len(cands)} candidate(s), {len(valid)} structurally usable, in {propose_time:.0f}s")
        if not valid:
            continue
        bench0 = time.time()
        scores = {}
        for c in valid:
            name = c["name"]
            if not ro.would_fit(len(batch) + len(val), K):   # never start a candidate whose train+val cannot finish
                stop_reason = f"budget: remaining {ro.remaining()} < one candidate ({per_cand_cost}); {name} not run"
                events.append({"iteration": iteration, "event": "not_run_budget", "name": name})
                break
            ws.freeze_from(ws.cands / name, name)
            known.append(name)
            gate = validate_candidate(ws.frozen / name)
            log(f"    [{name}] check: {'FAIL ' + gate[:200] if gate else 'OK (contract + lint + smoke)'}")
            try:
                tm, _ = ev.train(name, batch)
                vm, vmiss = ev.val(name, val)
            except BudgetStop as e:
                stop_reason = f"BudgetStop: {e}"
                append_summary(ws, iteration, c, None, best_val, None, batch, gate)
                break
            n_eval += 1
            scores[name] = vm
            append_summary(ws, iteration, c, vm, best_val, tm, batch, gate,
                           timing={"propose": round(propose_time, 1), "bench": round(time.time() - bench0, 1)},
                           val_missing=len(vmiss))
            log(f"    [{name}] train_batch={100 * tm:.1f}% avg_val={100 * vm:.1f}% "
                f"delta={100 * (vm - best_val):+.1f} spent={ro.spent}/{a.R}")
        if scores:
            fr = update_frontier(ws, scores)
            log(f"  {'NEW BEST ' + fr['_best']['system'] if fr['_best']['system'] != best_name else 'no improvement'}")
        if stop_reason:
            break
    else:
        stop_reason = stop_reason or f"iterations={a.iterations} done"

    fr = json.loads(ws.frontier.read_text())
    champ = fr["_best"]["system"]
    if (run / "champion").exists():
        shutil.rmtree(run / "champion")
    shutil.copytree(ws.frozen / champ, run / "champion")
    wrapper_intact = _sha((ws.work / "claude_wrapper.py").read_bytes()) == _sha(UPSTREAM_WRAPPER.read_bytes())
    rows = [json.loads(x) for x in ws.summary.read_text().splitlines() if x.strip()]
    summary = {
        "arm": ARM, "seed": a.seed, "R": a.R, "rollouts_used": ro.spent,
        "binding_on_R": ro.remaining() < per_cand_cost or stop_reason.startswith("BudgetStop"),
        "stop_reason": stop_reason, "champion": champ, "champion_avg_val": fr["_best"]["avg_val"],
        "n_candidates_evaluated": n_eval, "iterations": max([r["iteration"] for r in rows] + [0]),
        "accepted": sum(1 for r in rows if r["iteration"] > 0 and r.get("delta") is not None and r["delta"] > 0),
        "rejected": sum(1 for r in rows if r["iteration"] > 0 and (r.get("delta") is None or r["delta"] <= 0)),
        "candidates": {r["system"]: r.get("avg_val") for r in rows},
        "events": events, "train_ids_n": len(train), "val_ids_n": len(val), "train_batch": bsz,
        "candidates_per_iter": CANDIDATES_PER_ITER, "k": K, "optimizer_tokens_noncache": optimizer_tokens(run, opt_tag),
        "claude_wrapper_byte_identical_at_end": wrapper_intact, "upstream_pin": UPSTREAM_PIN,
        "wall_s": round(time.time() - t0, 1),
    }
    (run / "run_summary.json").write_text(json.dumps(summary, indent=1))
    print("META_HARNESS_ARM_DONE", json.dumps({k: summary[k] for k in ("rollouts_used", "R", "stop_reason", "champion",
                                                                      "n_candidates_evaluated", "iterations")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
