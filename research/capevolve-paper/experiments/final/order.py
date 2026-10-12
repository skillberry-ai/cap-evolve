#!/usr/bin/env python3
"""order.py: builds the interleaved, randomized final-evaluation order of one suite (analysis plan 5H).

    order.py --suite A --manifest manifests/artifacts_A.json --tasks final|smoke [--k 2] [--trials-arm 1 --trials-seed 2]
             [--extra transfer] [--out manifests/order_A.jsonl] [--tag-exp FINAL-A]

Every rollout of the suite (all arms' B* artifacts, the native end-of-run artifacts, the seed artifact, the one-shot control) is one
line of a single file, in ONE seeded random permutation (seed 20261013, sha256-counter PRNG so the permutation does not depend on the
Python version).  The seed artifact gets at least 2 trials per task.  The file is hashed (order_<S>.sha256) before the first rollout;
run_final.py refuses to start on a different hash.  Trial seeds are common random numbers: H(suite, task, trial), identical across arms.

`--tasks final` reads the sealed final sets (A: protocol/final_set/suiteA_final_tasks.json written by draw_final_a.py at freeze;
B/C: sealed_test of the tau split files).  It is meant to be run by the coordinator at freeze; development uses `--tasks smoke`
(a few SEARCH-split tasks, tags contain "smoke").

An END artifact identical (tree hash) to the same arm/seed's B* artifact is not run twice: the B job is flagged also_end and its
rows are written to both result sets.  Cells whose reconstruction status is `impossible` are skipped and listed in meta.skipped.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fe_common as C  # noqa: E402

WT_TAU = Path("/home/dev/projects2/wt-tau")
SPLIT_FILE_A = C.REPO / "ci/benchmarks/spreadsheetbench/full_verified/split_ids.json"
FINAL_A_TASKS = C.PAPER / "protocol/final_set/suiteA_final_tasks.json"
DEFAULT_TRIALS = {"A": (1, 2), "B": (3, 3), "C": (3, 3), "D": (5, 10), "E": (5, 10)}   # pinned in decisions.md 22:30          # (trials per task for a method artifact, for the seed artifact)
TAU_SPLITS = {"B": "tau_retail_splits.json", "C": "tau_airline_splits.json", "D": "tau_retail_splits.json", "E": "tau_airline_splits.json"}
D_TIER2_TRIALS = 3        # Suite D: Tier 1 champions 5 trials, Tier 2 champions 3, the seed 10 (experiment-designer, EXPERIMENTS.md section 6)
D_MODELS = {"target_model": "openai/azoai/gpt-4.1-mini-2025-04-14", "user_model": "openai/azoai/gpt-4.1-2025-04-14", "judge_model": "openai/azoai/gpt-4.1-2025-04-14",
            "gateway": "http://127.0.0.1:4112/v1"}
EXTRA = {
    "transfer": {"E": {"target_model": "openai/azoai/gpt-4.1-2025-04-14", "exp_suffix": "xfer"}, "D": {"target_model": "openai/azoai/gpt-4.1-2025-04-14", "exp_suffix": "xfer"}, "A": {"target_model": "azoai/gpt-5-mini-2025-08-07", "gateway": "http://127.0.0.1:4112/v1", "exp_suffix": "xfer",
               "env": {"TEMPERATURE": "1.0"}},     # gpt-5-mini rejects temperature 0 (probed 2026-10-11); provider default 1
                 "B": {"target_model": "openai/azoai/gpt-4.1-2025-04-14", "gateway": "http://127.0.0.1:4112/v1", "exp_suffix": "xfer"},
                 "C": {"target_model": "openai/azoai/gpt-4.1-2025-04-14", "gateway": "http://127.0.0.1:4112/v1", "exp_suffix": "xfer"}},
    # dry-run path on Azure-direct only: real adapters / scorer / worker, but no RITS (smoke tags starve on the saturated RITS deployments) and
    # no impact on the running searches.  Never used for results.
    "decomp": {"A": {}, "B": {}, "C": {}, "D": {"exp_suffix": "decomp"}, "E": {"exp_suffix": "decomp"}},
    "dryazure": {"A": {"target_model": "azoai/gpt-5-mini-2025-08-07", "gateway": "http://127.0.0.1:4112/v1", "exp_suffix": "dry", "env": {"TEMPERATURE": "1.0"}},
                 "B": {"target_model": "openai/azoai/gpt-4.1-2025-04-14", "user_model": "openai/azoai/gpt-4.1-2025-04-14", "judge_model": "openai/azoai/gpt-4.1-2025-04-14",
                       "gateway": "http://127.0.0.1:4112/v1", "exp_suffix": "dry"},
                 "C": {"target_model": "openai/azoai/gpt-4.1-2025-04-14", "user_model": "openai/azoai/gpt-4.1-2025-04-14", "judge_model": "openai/azoai/gpt-4.1-2025-04-14",
                       "gateway": "http://127.0.0.1:4112/v1", "exp_suffix": "dry"}},
}


class HashRng:
    """deterministic PRNG: sha256(seed | stream | counter); independent of Python's random module versions"""

    def __init__(self, seed, stream):
        self.seed, self.stream, self.i = int(seed), str(stream), 0

    def u32(self):
        h = hashlib.sha256(("%d|%s|%d" % (self.seed, self.stream, self.i)).encode()).digest()
        self.i += 1
        return int.from_bytes(h[:8], "big")

    def randbelow(self, n):
        # rejection-free enough: 64-bit draw, bias < n / 2^64
        return self.u32() % n

    def shuffle(self, xs):
        for i in range(len(xs) - 1, 0, -1):
            j = self.randbelow(i + 1)
            xs[i], xs[j] = xs[j], xs[i]
        return xs

    def sample(self, xs, k):
        xs = list(xs)
        self.shuffle(xs)
        return xs[:k]


def trial_seed(suite, task, trial, salt=""):
    return int.from_bytes(hashlib.sha256(("%s|%s|%s|%d" % (suite, salt, task, trial)).encode()).digest()[:4], "big") % (2 ** 31 - 7919 * 8)


def family_of_sb_id(i):
    s = str(i)
    if s.startswith("CF_"):
        return "CF"
    if "-" in s:
        return s.split("-")[0]
    return s


def load_tasks(suite, which, k, rng):
    if which == "final":
        if suite == "A":
            d = C.jload(FINAL_A_TASKS)
            if not d:
                sys.exit("final Suite A task file missing: run draw_final_a.py at freeze")
            return [{"id": str(t["id"]), "family": str(t.get("family") or family_of_sb_id(t["id"]))} for t in d["tasks"]], "final", C.file_sha(FINAL_A_TASKS)
        sp = C.jload(WT_TAU / "protocol" / TAU_SPLITS[suite])
        ids = [str(x) for x in sp["sealed_test"]]
        tasks = [{"id": i, "family": i, "split": "test"} for i in ids]
        if suite in ("D", "E"):      # D: H65 (sel-25 + test-40); E: H30 (sel-10 + test-20) = sel-25 + test-40 (amendment 7); both sets are built so that either primary choice works (split column)
            sel = [str(x) for x in sp["sel"]]
            tasks = [{"id": i, "family": i, "split": "sel"} for i in sel] + tasks
            ids = sel + ids
        return tasks, "final", hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()
    # smoke: search-split tasks only
    if suite == "A":
        d = C.jload(SPLIT_FILE_A)
        pool = sorted(str(x) for x in d["val"])
    else:
        sp = C.jload(WT_TAU / "protocol" / TAU_SPLITS[suite])
        pool = sorted(str(x) for x in sp["sel"])
    pick = sorted(rng.sample(pool, k))
    return [{"id": i, "family": family_of_sb_id(i) if suite == "A" else i, "split": "sel" if suite != "A" else "val"} for i in pick], "smoke", hashlib.sha256("\n".join(pick).encode()).hexdigest()


def canary_tasks(suite, rng, n=5):
    if suite == "A":
        pool = sorted(str(x) for x in C.jload(SPLIT_FILE_A)["val"])
    else:
        pool = sorted(str(x) for x in C.jload(WT_TAU / "protocol" / TAU_SPLITS[suite])["sel"])
    return sorted(rng.sample(pool, min(n, len(pool))))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", required=True, choices=sorted(C.SUITES))
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--tasks", choices=["final", "smoke"], default="smoke")
    ap.add_argument("--k", type=int, default=2, help="smoke: number of tasks")
    ap.add_argument("--trials-arm", type=int, default=None)
    ap.add_argument("--trials-seed", type=int, default=None)
    ap.add_argument("--extra", choices=sorted(EXTRA), default=None)
    ap.add_argument("--end-only", action="store_true", help="write only the distinct END (5D) jobs: run after the primary window (decisions 22:50)")
    ap.add_argument("--hl-v0", action="store_true", help="Suite B: add arm hl-v0 (HarnessLens's unmodified OpenCode harness, run_test_baseline path)")
    ap.add_argument("--decomp-manifest", default=None, help="with --extra decomp: manifest written by decompose.py")
    ap.add_argument("--no-end", action="store_true", help="skip the native end-of-run (5D) artifacts")
    ap.add_argument("--arms", default=None, help="restrict to these arms (dry runs)")
    ap.add_argument("--tag-exp", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--agent-view", default=None)
    ap.add_argument("--gold-dir", default=None)
    ap.add_argument("--adapter-path", default=str(C.SCRATCH / "bench/patches/new/adapter.py"))
    a = ap.parse_args(argv)
    suite = a.suite
    man = C.jload(a.manifest)
    if not man:
        sys.exit("cannot read manifest " + a.manifest)
    ta, ts = DEFAULT_TRIALS[suite]
    n_arm = a.trials_arm or ta
    n_seed = max(2, a.trials_seed or ts)
    rng = HashRng(C.ORDER_SEED, "%s|tasks" % suite)
    tasks, split_kind, tasks_sha = load_tasks(suite, a.tasks, a.k, rng)
    smoke = split_kind == "smoke"
    ex = dict(D_MODELS) if suite in ("D", "E") else {}
    ex.update(EXTRA[a.extra][suite] if a.extra else {})
    tag_exp = a.tag_exp or (("FE-smoke-%s" % suite) if smoke else ("FINAL-%s" % suite))
    if ex.get("exp_suffix"):
        tag_exp += "-" + ex["exp_suffix"]
    if a.extra == "dryazure" and not smoke:
        sys.exit("dryazure is for smoke orders only")
    if smoke and "smoke" not in tag_exp and not tag_exp.startswith("FE-dry"):
        sys.exit("smoke orders must carry 'smoke' in the tag (or the coordinator-approved FE-dry prefix)")
    if not smoke and not tag_exp.startswith("FINAL-%s" % suite):
        sys.exit("final tags must start with FINAL-%s" % suite)
    kind = C.SUITES[suite]["artifact_kind"]
    if suite == "A":
        agent_view = a.agent_view or (str(C.SCRATCH / "baselines/work/agent_view_verified400") if smoke else str(C.final_dir("A") / "agent_view_912"))
        gold_dir = a.gold_dir or str(C.SCRATCH / "bench/data/extracted" / ("spreadsheetbench_verified_400" if smoke else "all_data_912_v0.1"))
    jobs, skipped = [], []

    def make_job(arm, seed, mode, art, task, trial, n_trials, also_end=False):
        label = arm if mode != "END" else arm + "-end"
        if arm == "seed":
            label = "seed"
        j = {"type": "job", "suite": suite, "arm": arm, "arm_label": label, "seed": seed, "mode": mode, "task": task["id"], "family": task["family"], "split": task.get("split"),
             "trial": trial, "trial_seed": trial_seed(suite, task["id"], trial, a.extra or ""), "artifact_dir": art["frozen_dir"],
             "artifact_tree_sha256": art["tree_sha256"], "artifact_kind": kind, "tag": "tag:%s-%s-s%d:%s" % (tag_exp, label, seed, label),
             "also_end": also_end, "extra_set": a.extra, "final_split": (not smoke) and task.get("split") != "sel"}
        if suite == "A":
            j.update(agent_view=agent_view, gold_dir=gold_dir, adapter_path=a.adapter_path)
        j["job_id"] = "%s|%s|s%d|%s|%s|t%d" % (suite, label, seed, task["id"], mode, trial)
        if arm in ("harnesslens", "hl-v0", "hlext"):
            j["hl"] = {"version": art.get("candidate_id") if arm == "harnesslens" else "v0",
                       "src_run_dir": (None if (arm == "hl-v0" or art.get("candidate_id") == "v0") else str(Path(art.get("run_dir", "")) / ("hl_s%d" % seed) / "runs/train" / ("e10b-hl-s%d" % seed)))}
        for k in ("target_model", "gateway", "env", "user_model", "judge_model"):
            if ex.get(k):
                j[k] = ex[k]
        return j

    def add_cell(arm, seed, mode, art, n_trials, also_end=False):
        for t in tasks:
            if suite in ("D", "E") and not smoke and arm in ("gepa", "gepafull") and t.get("split") == "sel":
                continue          # GEPA selects on sel-25: its cells are test-40 only
            for k in range(n_trials):
                jobs.append(make_job(arm, seed, mode, art, t, k, n_trials, also_end))

    seed_art = None
    if a.extra == "decomp":                           # E25: P-only / T-only sub-artifacts written by decompose.py; no seed, no arms loop
        dm = C.jload(a.decomp_manifest)
        if not dm:
            sys.exit("--extra decomp needs --decomp-manifest")
        nd = a.trials_arm or (3 if suite in ("D", "E") else 1)
        for e in dm["entries"]:
            add_cell(e["arm_label"], e["seed"], "B", e, nd)
            for j in jobs[-len(tasks) * nd:]:
                j["arm"] = e["arm_label"]
    else:
        seed_art = man["seed_artifact"]
        if seed_art.get("status") not in ("ok", "partial"):
            sys.exit("no usable seed artifact in manifest")
        if not a.end_only:
            add_cell("seed", 0, "B", seed_art, n_seed, also_end=True)
            if not a.extra:       # amendment 9A: ONE extra labelled seed-check cell (the seed artifact again, the arms' n); feeds no test
                add_cell("seed-check", 0, "B", seed_art, n_arm, also_end=True)
        if a.hl_v0 and suite == "B" and not a.end_only:
            add_cell("hl-v0", 0, "B", {"frozen_dir": str(C.final_dir("B") / "artifacts/hl-v0"), "tree_sha256": "hl-v0-unmodified", "candidate_id": "v0"}, n_seed, also_end=True)
        entries = {(e["mode"], e["arm"], e["seed"]): e for e in man["entries"]}
        arms = a.arms.split(",") if a.arms else C.suite_arms(suite)
        for arm in arms:
            n_a = D_TIER2_TRIALS if (suite == "D" and arm in C.SUITES["D"]["cheap"] and not a.trials_arm) else n_arm
            for seed in C.SEEDS:
                b = entries.get(("B", arm, seed))
                e = entries.get(("END", arm, seed))
                if not b or b["status"] == "impossible":
                    skipped.append({"arm": arm, "seed": seed, "mode": "B", "reason": (b or {}).get("reason", "no entry")})
                    b = None
                same = b and e and e.get("tree_sha256") == b.get("tree_sha256") and e["status"] != "impossible"
                if b and not a.end_only:
                    add_cell(arm, seed, "B", b, n_a, also_end=bool(same) or arm == "oneshot")
                if e and not a.no_end and (not a.extra or a.extra == "dryazure") and arm != "oneshot":
                    if e["status"] == "impossible":
                        skipped.append({"arm": arm, "seed": seed, "mode": "END", "reason": e.get("reason", "")})
                    elif not same and a.end_only:
                        add_cell(arm, seed, "END", e, n_a)
    # one permutation of everything (sorted first so the input order is canonical)
    jobs.sort(key=lambda j: (j["arm_label"], j["seed"], str(j["task"]), j["trial"], j["mode"]))
    HashRng(C.ORDER_SEED, "%s|order|%s" % (suite, a.extra or "primary")).shuffle(jobs)
    for i, j in enumerate(jobs):
        j["idx"] = i
    canary = []
    if (not a.extra or a.extra == "dryazure") and not a.end_only and seed_art:
        crng = HashRng(C.ORDER_SEED, "%s|canary" % suite)
        for tid in canary_tasks(suite, crng):
            cj = make_job("seed", 0, "B", seed_art, {"id": tid, "family": family_of_sb_id(tid) if suite == "A" else tid}, 0, 1)
            cj["arm_label"] = "canary"
            cj["tag"] = "tag:%s-canary-s0:canary" % tag_exp
            cj["final_split"] = False                      # canary tasks are SEARCH-split tasks
            cj["job_id"] = "canary|%s" % tid
            if suite == "A":
                cj["agent_view"] = str(C.SCRATCH / "baselines/work/agent_view_verified400")
                cj["gold_dir"] = str(C.SCRATCH / "bench/data/extracted/spreadsheetbench_verified_400")
            canary.append(cj)
    meta = {"type": "meta", "suite": suite, "order_seed": C.ORDER_SEED, "split_kind": split_kind, "tasks": [t["id"] for t in tasks], "tasks_sha256": tasks_sha,
            "n_jobs": len(jobs), "trials_arm": n_arm, "trials_seed": n_seed, "tag_exp": tag_exp, "extra": a.extra, "manifest": str(a.manifest),
            "manifest_sha256": C.file_sha(a.manifest), "bstar": man.get("bstar"), "decomp_manifest": a.decomp_manifest, "skipped": skipped, "canary_jobs": canary, "script_commit": C.git_head(),
            "order_py_sha256": C.file_sha(__file__), "cutoff_utc": C.CUTOFF_UTC,
            "counts_by_arm": {}}
    for j in jobs:
        k = "%s/s%d" % (j["arm_label"], j["seed"])
        meta["counts_by_arm"][k] = meta["counts_by_arm"].get(k, 0) + 1
    out = Path(a.out) if a.out else C.MANIFESTS / ("order_%s%s%s.jsonl" % (suite, ("_" + a.extra) if a.extra else "", "_end" if a.end_only else ""))
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        f.write(json.dumps(meta, sort_keys=True) + "\n")
        for j in jobs:
            f.write(json.dumps(j, sort_keys=True) + "\n")
    sha = C.sha256_file(out)
    out.with_suffix(".sha256").write_text("%s  %s\n" % (sha, out.name))
    print("order %s: %d jobs, %d tasks (%s), trials arm/seed %d/%d, skipped cells %d, sha256 %s" % (out, len(jobs), len(tasks), split_kind, n_arm, n_seed, len(skipped), sha))
    return 0


if __name__ == "__main__":
    sys.exit(main())
