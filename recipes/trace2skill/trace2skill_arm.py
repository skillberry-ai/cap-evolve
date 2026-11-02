#!/usr/bin/env python3
"""exp895 Trace2Skill arm (issue skillberry-ai/cap-evolve#895 §7.5): ONE search = one pass of the official method.

  1. POOL      the seed S0 (v2 seed, byte-identical) run on TRAIN x k through the common rollout.
               Every (task, trial) transcript is written as an upstream-format markdown agent log
               (pool_logs/seed_t<j>/exp895_common_rollout_<id>_<SUCCEED|FAILED>.md).
  2. ANALYSE   upstream LLM-only, gold-free analysts, UNMODIFIED, as subprocesses:
               analysis/run_error_analysis_llm.py on FAILED logs, analysis/run_success_analysis_llm.py on SUCCEED
               logs (--repeat k discovers the seed_* dirs). Upstream parses them into parsed_*_records.json.
  3. EVOLVE    upstream skill_evolver CLIs, unmodified, via t2s_evolve.py (adds the surface contract only):
               error-skill = run_parallel_skill_evolution (error records), combined =
               run_parallel_combined_skill_evolution (error + success records). Both start from S0 =
               the seed's skills/spreadsheet-helpers/ (SKILL.md; references/ empty).
  4. EXPORT    evolved folder -> candidate dir: references/script_<m>.md -> skills/spreadsheet-helpers/scripts/<m>.py
               (its ```python block); other references/*.md inlined at the end of SKILL.md; prompt.md and
               task_template.md = seed bytes.
  5. SELECT    {seed, error-skill, combined} on VAL x k. Champion = best of {error, combined} only if its val
               mean is STRICTLY greater than the seed's; ties keep the seed. A candidate byte-identical to the
               seed is not re-evaluated (it is the seed).
Every evaluation goes through CommonRollout.evaluate(candidate_dir, ids, k=3, split=...) (R enforced there).
Pool logs come from TaskResult.traces (every trial); trials flagged TaskResult.infra are missing, not failures.
The analysts run via t2s_analyse.py (upstream CLI + one runtime sort-key fix, deviation D9).
The seed-on-VAL evaluation runs concurrently with steps 2-4 (it cannot depend on them; the optimizer never sees
val results). Outputs: run_summary.json, cost_summary.json, candidates/, champion/, selection.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

EXP = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895")
REPO = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/sbv400-main")
UP = EXP / "competitors" / "trace2skill"
ARM = EXP / "arms" / "trace2skill"
SEED_SRC = REPO / "templates" / "adapters" / "spreadsheetbench" / "seed_capability_v2"
SKILL = "spreadsheet-helpers"
GLM_MODEL = "rits/zai-org/glm-5-3"   # served id; the gateway rewrites body.model anyway
AGENT_NAME = "exp895_common_rollout"

sys.path.insert(0, str(EXP / "arms" / "common"))
from rollout import BudgetStop, CommonRollout  # noqa: E402


def log(msg):
    print(f"[{datetime.now(timezone.utc).isoformat(timespec='seconds')}] {msg}", flush=True)


def tree_sha(d: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(p for p in d.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        h.update(f.relative_to(d).as_posix().encode() + b"\0" + f.read_bytes() + b"\0")
    return h.hexdigest()


def check_seed(seed_dir: Path):
    want = json.loads((EXP / "BUILD_RECORD.json").read_text())["seed_v2"]["files_sha256"]
    got = {f.relative_to(seed_dir).as_posix(): hashlib.sha256(f.read_bytes()).hexdigest()
           for f in seed_dir.rglob("*") if f.is_file()}
    assert got == want, f"seed bytes differ from BUILD_RECORD.json: {sorted(set(got.items()) ^ set(want.items()))}"


# ---- step 1: pool --------------------------------------------------------------------------------------------
def render_log(trace) -> str:
    """The upstream markdown logger format (spreadsheet_agent/agents/base.py), so the upstream analysts'
    strip_log_metadata() and prompts apply unchanged. Message 1 = system prompt, 2 = task; later user turns are
    execution results, written as upstream writes observations."""
    out = [f"# Chat History: {AGENT_NAME}\n\n", f"**Timestamp**: {datetime.now().isoformat()}\n\n", "---\n\n"]
    seen_task = False
    for i, m in enumerate(trace or [], 1):
        role, content = m.get("role", "user"), m.get("content", "")
        content = content if isinstance(content, str) else json.dumps(content)
        if role == "user":
            if seen_task:
                fence = "```"
                while fence in content:
                    fence += "`"
                content = f"Observation:\n{fence}\n{content}\n{fence}"
            seen_task = True
        out.append(f"## [{i}] {role.upper()}\n\n{content}\n\n---\n\n")
    return "".join(out)


def write_pool_logs(res, logs: Path) -> dict:
    """TaskResult.traces = every trial's transcript (trial order); TaskResult.infra marks trials still infra-errored
    after the common retries (their 0.0 is a placeholder): those are missing, not failures, and not in the pool."""
    counts = {"SUCCEED": 0, "FAILED": 0, "missing_infra": 0}
    for tid, tr in res.per_task.items():
        for j, reward in enumerate(tr.trials):
            if tr.infra[j]:
                counts["missing_infra"] += 1
                continue
            trace = tr.traces[j]
            outcome = "SUCCEED" if reward >= 1.0 - 1e-9 else "FAILED"
            counts[outcome] += 1
            d = logs / f"seed_t{j}"
            d.mkdir(parents=True, exist_ok=True)
            body = render_log(trace)
            body += f"## RESULT\n\n- Success: {outcome == 'SUCCEED'}\n- Total Turns: {sum(1 for m in (trace or []) if m.get('role') == 'assistant')}\n"
            (d / f"{AGENT_NAME}_{tid}_{outcome}.md").write_text(body, encoding="utf-8")
    return counts


# ---- steps 2-3: upstream subprocesses -------------------------------------------------------------------------
def run_cmd(cmd, logfile: Path, cwd: Path, env: dict) -> int:
    log(f"run: {' '.join(str(c) for c in cmd[:3])} ... > {logfile.name}")
    with open(logfile, "w") as f:
        p = subprocess.run([str(c) for c in cmd], cwd=cwd, stdout=f, stderr=subprocess.STDOUT, env=env)
    log(f"rc={p.returncode} {logfile.name}")
    return p.returncode


def analyse(run: Path, work: Path, args, env, pool_counts: dict) -> tuple[Path, Path]:
    py = sys.executable
    gen = json.dumps({"temperature": args.temperature, "max_tokens": args.max_tokens})
    common = ["--logs_dir", run / "pool_logs", "--model", GLM_MODEL, "--base_url", args.glm_base, "--api_key",
              "tag-not-a-secret", "--generation_config", gen, "--seed", args.seed, "--repeat", args.k]
    out_e, out_s = run / "analysis" / "error", run / "analysis" / "success"
    jobs = [([py, ARM / "t2s_analyse.py", "error", *common, "--output_dir", out_e,
              "--max_workers", args.workers], run / "analysis_error.log"),
            ([py, ARM / "t2s_analyse.py", "success", *common, "--output_dir", out_s,
              "--max_workers", args.workers], run / "analysis_success.log")]
    with ThreadPoolExecutor(2) as ex:
        rcs = list(ex.map(lambda j: run_cmd(j[0], j[1], work, env), jobs))
    pe, ps = out_e / "parsed_error_records.json", out_s / "parsed_success_records.json"
    for rc, n_logs, p in ((rcs[0], pool_counts["FAILED"], pe), (rcs[1], pool_counts["SUCCEED"], ps)):
        if n_logs and (rc != 0 or not p.is_file()):
            raise RuntimeError(f"upstream analyst failed (rc={rc}) on {n_logs} logs; see {p.parent.parent.parent}")
        # upstream exits 1 with no file only when there is no log of that outcome: an empty record list
        if not p.is_file():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("[]", encoding="utf-8")
    return pe, ps


def evolve(mode: str, run: Path, work: Path, args, env, pe: Path, ps: Path) -> Path:
    d = run / f"evolve_{mode}"
    sk = d / "skills" / SKILL
    shutil.copytree(run / "candidates" / "seed" / "skills" / SKILL, sk)
    cmd = [sys.executable, ARM / "t2s_evolve.py", mode]
    if mode == "error":
        cmd += ["--input-json", pe, "--prompt", "generic"]
    else:
        cmd += ["--error-json", pe, "--success-json", ps]
    cmd += ["--skill-dir", sk, "--model", GLM_MODEL, "--base-url", args.glm_base, "--api-key", "tag-not-a-secret",
            "--seed", args.seed, "--temperature", args.temperature, "--max-tokens", args.max_tokens,
            "--batch-size", "1", "--merge-batch-size", "5", "--max-workers", args.workers, "--patch-pipeline", "json",
            "--cache-path", d / "llm_cache", "--save-intermediates", "--intermediates-dir", d / "intermediates",
            "--parse-failure-dir", d / "parse_failures", "--changelog", d / "change.log", "--verbose"]
    e = dict(env, T2S_PROMPT_DUMP=str(d / "proposer_system_prompts.json"))
    rc = run_cmd(cmd, d / "evolve.log", work, e)
    (d / "rc.txt").write_text(str(rc))
    return sk


# ---- step 4: export -------------------------------------------------------------------------------------------
SCRIPT_REF = re.compile(r"^script_([a-z_][a-z0-9_]*)\.md$")
PY_BLOCK = re.compile(r"```python[^\n]*\n(.*?)```", re.S)


def export(evolved: Path, seed_dir: Path, dst: Path) -> dict:
    shutil.copytree(seed_dir, dst)
    sk = dst / "skills" / SKILL
    text = (evolved / "SKILL.md").read_text(encoding="utf-8")
    info = {"scripts": [], "inlined_references": [], "script_refs_without_code": []}
    refs = sorted((evolved / "references").glob("*.md")) if (evolved / "references").is_dir() else []
    inlined = []
    for r in refs:
        body = r.read_text(encoding="utf-8")
        m = SCRIPT_REF.match(r.name)
        blocks = PY_BLOCK.findall(body) if m else []
        if m and blocks:
            (sk / "scripts").mkdir(parents=True, exist_ok=True)
            (sk / "scripts" / f"{m.group(1)}.py").write_text("\n\n".join(b.rstrip() for b in blocks) + "\n",
                                                            encoding="utf-8")
            info["scripts"].append(f"{m.group(1)}.py")
            # the folder-internal link becomes the import the agent actually uses
            imp = f"`skills.spreadsheet_helpers.{m.group(1)}` (helper script)"
            text = text.replace(f"`references/{r.name}`", imp).replace(f"references/{r.name}", imp)
        else:
            if m:
                info["script_refs_without_code"].append(r.name)
            inlined.append(f"\n\n## Reference: references/{r.name}\n\n{body.strip()}\n")
            info["inlined_references"].append(r.name)
    (sk / "SKILL.md").write_text(text.rstrip("\n") + "\n" + "".join(inlined), encoding="utf-8")
    info["tree_sha256"] = tree_sha(dst)
    return info


def clean_mean(res) -> float | None:
    """Mean over tasks of each task's mean over its MEASURED trials. A trial still infra-errored after the common
    retries (TaskResult.infra) is missing, not a 0 (issue §0.3); a task with no measured trial is dropped."""
    per = []
    for tr in res.per_task.values():
        got = [x for x, bad in zip(tr.trials, tr.infra) if not bad]
        if got:
            per.append(sum(got) / len(got))
    return sum(per) / len(per) if per else None


# ---- cost ------------------------------------------------------------------------------------------------------
def ledger_summary(path: Path, tag: str) -> dict:
    s = {"calls": 0, "ok": 0, "retries": 0, "prompt_total": 0, "cached_tokens": 0, "completion_tokens": 0,
         "calls_without_usage": 0}
    if not path.is_file():
        return s
    for line in path.read_text().splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("event") == "retry" or r.get("tag") != tag:
            continue
        s["calls"] += 1
        s["retries"] += r.get("retries") or 0
        s["ok"] += r.get("status") == 200
        if r.get("prompt_total") is None:
            s["calls_without_usage"] += 1
        for k in ("prompt_total", "cached_tokens", "completion_tokens"):
            s[k] += r.get(k) or 0
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True, type=Path)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--R", type=int, required=True)
    ap.add_argument("--train-ids", required=True, type=Path)
    ap.add_argument("--val-ids", required=True, type=Path)
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--glm-base", required=True)        # http://127.0.0.1:4115/t/<tag>/v1
    ap.add_argument("--workers", type=int, default=8)   # GLM calls in flight per upstream stage (= the arm's GLM cap)
    ap.add_argument("--temperature", type=float, default=0.6)
    ap.add_argument("--max-tokens", type=int, default=16000)
    ap.add_argument("--parallel-candidates", action="store_true",
                    help="evaluate error-skill and combined concurrently (2x the arm's containers; smoke only)")
    args = ap.parse_args()
    t0 = time.time()
    run = args.run_dir
    work = run / "work"
    (work / "skills" / "skill-creator" / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ARM / "skill-creator" / "scripts" / "quick_validate.py", work / "skills" / "skill-creator" / "scripts")
    read = lambda f: [l.strip() for l in open(f) if l.strip()]
    train, val = read(args.train_ids), read(args.val_ids)
    check_seed(SEED_SRC)
    cands = run / "candidates"
    shutil.copytree(SEED_SRC, cands / "seed")
    seed_sha = tree_sha(cands / "seed")
    env = {k: v for k, v in os.environ.items()}
    env["PYTHONPATH"] = str(UP)   # upstream imports (analysis., skill_evolver., src.) resolve to the pinned clone
    summary = {"arm": "trace2skill", "seed": args.seed, "R": args.R, "k": args.k, "n_train": len(train),
               "n_val": len(val), "seed_tree_sha256": seed_sha, "iterations": 1, "stop_reason": "completed"}

    ro = CommonRollout(run, arm="trace2skill", search_seed=args.seed, R=args.R)
    evals = {}
    try:
        log(f"POOL: seed on train {len(train)} x {args.k}")
        pool = ro.evaluate(cands / "seed", train, k=args.k, candidate_id="seed@train", split="train")
        evals["seed@train"] = {"mean": clean_mean(pool), "counted": pool.counted, "infra_retries": pool.infra_retries,
                               "per_task": {t: r.trials for t, r in pool.per_task.items()},
                               "infra_missing": {t: sum(r.infra) for t, r in pool.per_task.items() if any(r.infra)}}
        summary["pool"] = write_pool_logs(pool, run / "pool_logs")
        log(f"POOL done: mean={clean_mean(pool)} logs={summary['pool']}")

        # seed on VAL concurrently with the optimizer (independent of it; the optimizer never sees val)
        with ThreadPoolExecutor(1) as bg:
            fut_seed_val = bg.submit(ro.evaluate, cands / "seed", val, k=args.k, candidate_id="seed@val",
                                     split="val")
            pe, ps = analyse(run, work, args, env, summary["pool"])
            summary["records"] = {"error": len(json.loads(pe.read_text())), "success": len(json.loads(ps.read_text()))}
            log(f"ANALYSIS done: {summary['records']}")
            with ThreadPoolExecutor(2) as ex:
                f_err = ex.submit(evolve, "error", run, work, args, env, pe, ps)
                f_cmb = ex.submit(evolve, "combined", run, work, args, env, pe, ps)
                evolved = {"error_skill": f_err.result(), "combined": f_cmb.result()}
            exports = {}
            for name, sk in evolved.items():
                exports[name] = export(sk, cands / "seed", cands / name)
                exports[name]["identical_to_seed"] = exports[name]["tree_sha256"] == seed_sha
            summary["candidates"] = exports
            log(f"EXPORT done: {json.dumps(exports)}")
            seed_val = fut_seed_val.result()
        evals["seed@val"] = {"mean": clean_mean(seed_val), "counted": seed_val.counted,
                             "infra_retries": seed_val.infra_retries,
                             "per_task": {t: r.trials for t, r in seed_val.per_task.items()}}
        todo = [n for n in ("error_skill", "combined") if not exports[n]["identical_to_seed"]]

        def ev(name):
            r = ro.evaluate(cands / name, val, k=args.k, candidate_id=f"{name}@val", split="val")
            return name, {"mean": clean_mean(r), "counted": r.counted, "infra_retries": r.infra_retries,
                          "per_task": {t: x.trials for t, x in r.per_task.items()},
                          "errors": {t: [e for e in x.errors if e] for t, x in r.per_task.items()}}

        if args.parallel_candidates and len(todo) == 2:
            with ThreadPoolExecutor(2) as ex:
                res = list(ex.map(ev, todo))
        else:
            res = [ev(n) for n in todo]
        for name, r in res:
            evals[f"{name}@val"] = r
    except BudgetStop as e:
        summary["stop_reason"] = f"BudgetStop: {e}"
        log(summary["stop_reason"])

    # ---- selection: strict improvement over the seed, ties keep the seed ----
    seed_mean = evals.get("seed@val", {}).get("mean")
    best, best_mean = "seed", seed_mean
    for name in ("error_skill", "combined"):   # listed order breaks an exact tie between the two
        m = evals.get(f"{name}@val", {}).get("mean")
        if m is not None and seed_mean is not None and m > best_mean:
            best, best_mean = name, m
    if seed_mean is None:
        best = "seed"
    shutil.copytree(cands / best, run / "champion")
    sel = {"selection_set": "val", "seed_val_mean": seed_mean,
           "candidate_val_means": {n: evals.get(f"{n}@val", {}).get("mean") for n in ("error_skill", "combined")},
           "rule": "champion = best non-seed candidate only if its val mean > seed val mean (strict); ties keep seed",
           "champion": best, "champion_val_mean": best_mean}
    (run / "selection.json").write_text(json.dumps(sel, indent=1))
    (run / "evaluations.json").write_text(json.dumps(evals, indent=1))

    # ---- R-counter probe: one evaluation past the remaining budget must raise BudgetStop and spend nothing ----
    st0, rows0 = (run / "budget_state.json").read_text(), (run / "rollouts.jsonl").read_text().count("\n")
    need = ro.remaining() // args.k + 1
    try:
        ro.evaluate(run / "champion", [train[0]] * need, k=args.k, candidate_id="budget_probe", split="train")
        probe = "NOT_RAISED"
    except BudgetStop as e:
        probe = f"BudgetStop raised: {e}"
    summary["budget_probe"] = {"verdict": probe, "requested_rollouts": need * args.k,
                               "state_unchanged": (run / "budget_state.json").read_text() == st0,
                               "rollout_rows_unchanged": (run / "rollouts.jsonl").read_text().count("\n") == rows0}

    tag = f"exp895-trace2skill-s{args.seed}"
    st = json.loads((run / "budget_state.json").read_text())
    n_eval = sum(1 for k in evals if k.endswith("@val") and k != "seed@val")
    summary.update({"rollouts_used": st["spent"], "eval_calls": st["eval_calls"],
                    "binding_on_R": summary["stop_reason"].startswith("BudgetStop"),
                    "champion": best, "champion_tree_sha256": tree_sha(run / "champion"),
                    "n_candidates_evaluated": n_eval, "rejected": n_eval - int(best != "seed"),
                    "accepted": int(best != "seed"),
                    "selection": sel, "wall_s": round(time.time() - t0, 1)})
    cost = {"optimizer": ledger_summary(run / "calls_glm.jsonl", f"{tag}:optimizer"),
            "target": ledger_summary(run / "calls_gemma.jsonl", f"{tag}:target"),
            "note": "token counts from the gateway ledgers; $ is recomputed offline from pricing (issue §2.3)"}
    (run / "cost_summary.json").write_text(json.dumps(cost, indent=1))
    summary["cost"] = cost
    (run / "run_summary.json").write_text(json.dumps(summary, indent=1))
    log("RUN_SUMMARY " + json.dumps({k: summary[k] for k in ("rollouts_used", "R", "stop_reason", "champion",
                                                             "n_candidates_evaluated", "wall_s")}))


if __name__ == "__main__":
    main()
