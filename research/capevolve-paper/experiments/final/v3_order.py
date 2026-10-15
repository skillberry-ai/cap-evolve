#!/usr/bin/env python3
"""V3 final tests (two benchmarks): champion collection, order builder, dry run.  No scoring happens here.

  B1  tau2 airline, agent / user simulator / judge = openai/aws/gpt-oss-120b through :4113, official 20 test ids, k = 10 trials per task.
      Runs through the tau worker of run_final.py as suite "E" (airline), with per-job overrides: V3 adapter (scripts/V3/adapters/airline, sha 8d4cf8b7),
      models, gateway :4113, max_infra_retries.  Tag prefix FINAL-E-V3B1.
  B2  SpreadsheetBench, Gemma-4-31B via RITS (:4113 pool).  Runs through the A worker (suite "A") with main's adapter (helpers carrier) like the v2 A window.
      Test set is selectable: clean70 (the frozen Suite A T = 70 draw) or test280 (SkillOpt's test-280 of the verified-400, ci split_ids.json).  Tag prefix FINAL-A-V3B2.

  python3 -I v3_order.py collect --bench B1 [--runs-root runs/V3]           champions_V3_<B>.json from runs/V3/<B>/<framework>/s<k>/final/
  python3 -I v3_order.py build   --bench B1 --champions champions_V3_B1.json [--trials 10 --seed-trials 20 --seedcheck-trials 10]
  python3 -I v3_order.py build   --bench B2 --taskset clean70|test280 --champions champions_V3_B2.json [--seed-dir DIR]
  add --smoke to build a dry-run order on SEARCH-split tasks (B1: 2 train tasks; tags FE-smoke-...), never the test ids.

Every cell is a (framework, search seed) champion artifact; the seed artifact and a seed-check are in the same interleaved randomized order (order.py's HashRng).  An inert champion
(tree hash equal to the seed's) is mapped to the seed-check cell and not rescored (amendment 11 erratum 11 (3)).  Registration with the statistics reviewer precedes any rollout.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fe_common as C  # noqa: E402
import order as O  # noqa: E402
import reconstruct as R  # noqa: E402
import v2_window as V  # noqa: E402

V3_ADAPTER_AIRLINE = C.SCRATCH / "scripts/V3/adapters/airline/adapter.py"
V3_ADAPTER_SHA_PREFIX = "9c797d8a"      # 8d4cf8b7 for the searches; 9c797d8a = same adapter + a uuid suffix on the native-sims results filename (tau-runner: test_tool_consistency.py passes; registered by stats-reviewer, amendment 12 erratum 1)
HL_V3 = C.SCRATCH / "baselines/harnesslens/tau_v3"
HL_V3_FILES = ("src/harnesslens/benchmarks/opencode_tau2.py", "hl_final_eval_v3.py", "hl_fe_worker_v3.py")
GPT_OSS = "openai/aws/gpt-oss-120b"
GATEWAY_V3 = "http://127.0.0.1:4113/v1"
MAX_INFRA_RETRIES_V3 = 30          # V3 brief rule 5: zero LLM errors (retry until success; the adapter's run_trials wrapper also loops, V3_MAX_RETRIES)
SPLIT_IDS_SB = C.REPO / "ci/benchmarks/spreadsheetbench/full_verified/split_ids.json"
BENCH = {
    "B1": dict(suite="E", kind="tau_cap", tag="FINAL-E-V3B1", ver="V3B1"),
    "B2": dict(suite="A", kind="sb_files_v2", tag="FINAL-A-V3B2", ver="V3B2"),
}


def collect(bench, runs_root):
    """champions_V3_<bench>.json from <runs_root>/<bench>/<framework>/s<k>/final/ (the brief's output layout); reports frameworks/seeds that are incomplete."""
    kind = BENCH[bench]["kind"]
    out, problems = {}, []
    base = Path(runs_root) / bench
    skip = ("smoke", "archive", "failed", "run1", "premature")      # smoke runs and archived / superseded run dirs are not frameworks
    for fw in sorted(p.name for p in base.iterdir() if p.is_dir() and not any(w in p.name for w in skip)) if base.is_dir() else []:
        for s in range(3):
            fin = base / fw / ("s%d" % s) / "final"
            if not fin.is_dir():
                problems.append("%s s%d: no final/ yet" % (fw, s))
                continue
            if fw == "harnesslens":        # HarnessLens: the champion is a VERSION of its OpenCode harness (final/selected.json), not a policy/tools tree
                sel = C.jload(fin / "selected.json")
                if not sel or not sel.get("selected_version"):
                    problems.append("%s s%d: final/selected.json missing or has no selected_version" % (fw, s))
                    continue
                out.setdefault(fw, {})[str(s)] = {"hl_version": sel["selected_version"], "final_dir": str(fin),
                                                  "src_run_dir": str(base / fw / ("s%d" % s) / ("hl_s%d" % s) / "runs/train" / ("v3-hl-s%d" % s))}
                continue
            files = C.tree_files(fin, kind)
            if not files:
                problems.append("%s s%d: final/ has no artifact files for kind %s" % (fw, s, kind))
                continue
            out.setdefault(fw, {})[str(s)] = str(fin)
    return out, problems


def _taskset_file(taskset, out_dir):
    """order.py reads {tasks: [{id, family}]} from FINAL_A_TASKS; write the test-280 list in that format."""
    if taskset == "clean70":
        return O.FINAL_A_TASKS
    d = C.jload(SPLIT_IDS_SB)
    ids = [str(x) for x in d["test"]]
    p = Path(out_dir) / "suiteA_v3_test280_tasks.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    C.write_json_atomic(p, {"source": "ci/benchmarks/spreadsheetbench/full_verified/split_ids.json (SkillOpt test split)", "n": len(ids),
                            "tasks": [{"id": i, "family": O.family_of_sb_id(i)} for i in ids]})
    return p


def build(bench, champions_path, out_root, manifests, a):
    cfg = BENCH[bench]
    suite, kind, ver = cfg["suite"], cfg["kind"], cfg["ver"]
    champ = json.load(open(champions_path))
    frameworks = sorted(champ)
    base_v1 = json.load(open(Path(C.MANIFESTS) / ("artifacts_%s.json" % suite)))
    if a.seed_dir:
        seed_dst = Path(out_root) / "artifacts" / "seed"
        if not seed_dst.exists():
            R.freeze_copy(Path(a.seed_dir), seed_dst, kind)
        th, files = C.tree_hash(seed_dst, kind)
        seed_art = {"status": "ok", "frozen_dir": str(seed_dst), "tree_sha256": th, "files": files, "source_dir": a.seed_dir,
                    "normalized_tree_sha256": C.tree_hash_normalized(seed_dst, kind)}
    else:
        seed_art = base_v1["seed_artifact"]
    entries = []
    for fw in frameworks:
        for s in range(3):
            src = champ[fw].get(str(s))
            if not src:
                sys.exit("champions file has no %s seed %d" % (fw, s))
            if isinstance(src, dict):          # HarnessLens version champion
                ver_ = src["hl_version"]
                snap = Path(src["src_run_dir"]) / "rollout_evidence" / ("v3-hl-s%d" % s) / "versions_percell/airline" / ver_
                if ver_ == "v0":
                    th, files = "hl-v0-unmodified", {}
                else:
                    files = {str(p.relative_to(snap)): C.sha256_file(p) for p in sorted(snap.rglob("*")) if p.is_file()}
                    if not files:
                        sys.exit("HarnessLens %s s%d: version snapshot %s is empty or missing" % (ver_, s, snap))
                    fz = Path(src["final_dir"]).parent / "frozen" / ver_      # bl-harness: frozen/<vN> (read-only) and final/ hold byte-identical copies of the snapshot
                    if fz.is_dir():
                        fzf = {str(p.relative_to(fz)): C.sha256_file(p) for p in sorted(fz.rglob("*")) if p.is_file()}
                        if fzf != files:
                            sys.exit("HarnessLens %s s%d: frozen/%s differs from the evaluated snapshot %s" % (ver_, s, ver_, snap))
                    import hashlib
                    th = hashlib.sha256("".join("%s\0%s\n" % (k, files[k]) for k in sorted(files)).encode()).hexdigest()
                entries.append({"suite": suite, "mode": "B", "arm": fw, "seed": s, "status": "ok", "source_dir": src["final_dir"], "frozen_dir": str(snap), "tree_sha256": th, "files": files,
                                "candidate_id": ver_, "hl_version": ver_, "hl_src_run_dir": src["src_run_dir"], "normalized_tree_sha256": th,
                                "identical_to_seed": ver_ == "v0", "inert": ver_ == "v0", "dagger": False})
                continue
            dst = Path(out_root) / "artifacts" / "B" / fw / ("s%d" % s)
            if not dst.exists():
                R.freeze_copy(Path(src), dst, kind)
            (th, files), nh = C.tree_hash(dst, kind), C.tree_hash_normalized(dst, kind)
            entries.append({"suite": suite, "mode": "B", "arm": fw, "seed": s, "status": "ok", "source_dir": str(src), "frozen_dir": str(dst), "tree_sha256": th, "files": files,
                            "normalized_tree_sha256": nh, "identical_to_seed": th == seed_art["tree_sha256"], "inert": th == seed_art["tree_sha256"], "dagger": False})
    man = {"suite": suite, "window": ver, "bstar": "final-state", "entries": entries, "seed_artifact": seed_art, "frameworks": frameworks,
           "champions_file": str(champions_path), "champions_file_sha256": C.file_sha(champions_path), "generated_utc": C.now_utc()}
    blk = "_traineval" if a.block == "traineval" else ""
    if a.block == "traineval":
        if suite != "E" or a.smoke:
            sys.exit("--block traineval is for B1 (suite E), not --smoke")
        spl = C.jload(O.WT_TAU.parent / "wt-airE" / "protocol" / "tau_airline_splits.json") or C.jload(Path("/home/dev/projects2/wt-airE/protocol/tau_airline_splits.json"))
        tr = [str(x) for x in spl["opt"] + spl["sel"]]
        assert not (set(tr) & set(str(x) for x in spl["sealed_test"])), "train ids overlap the sealed test"
        _orig = O.load_tasks
        O.load_tasks = lambda suite_, which, k, rng: ([{"id": i, "family": i, "split": "train"} for i in tr], "final", C.sha256_bytes("\n".join(sorted(tr)).encode()))
    mpath = Path(manifests) / ("artifacts_%s%s%s.json" % (ver, blk, "_smoke" if a.smoke else ""))
    C.write_json_atomic(mpath, man)
    out = Path(manifests) / ("order_%s%s%s.jsonl" % (ver, blk, "_smoke" if a.smoke else ""))
    argv = ["--suite", suite, "--manifest", str(mpath), "--tasks", "smoke" if a.smoke else "final", "--arms", ",".join(frameworks), "--no-end",
            "--trials-arm", str(a.trials), "--trials-seed", str(a.seed_trials if a.block == "test" else a.trials), "--k", str(a.smoke_tasks),
            "--tag-exp", ("FE-smoke-V3%s" % bench) if a.smoke else cfg["tag"], "--out", str(out)]
    if "harnesslens" in frameworks and suite == "E":
        argv += ["--hl-v0"]                    # the unmodified OpenCode harness as HarnessLens's own baseline cell (order.py's hl-v0 arm, seed-like n)
    if suite == "A":
        if a.smoke:
            argv += ["--extra", "dryazure"]
        else:
            tf = _taskset_file(a.taskset, manifests)
            O.FINAL_A_TASKS = tf
            if a.taskset == "test280":
                argv += ["--agent-view", str(C.SCRATCH / "baselines/work/agent_view_verified400"), "--gold-dir", str(C.SCRATCH / "bench/data/extracted/spreadsheetbench_verified_400")]
        argv += ["--adapter-path", str(Path(a.code_root) / "templates/adapters/spreadsheetbench/adapter.py")]
    if O.main(argv):
        sys.exit("order.py failed")
    rows = [json.loads(l) for l in open(out)]
    meta, jobs = rows[0], [r for r in rows[1:] if r.get("type") == "job"]
    if a.block == "traineval":
        jobs = [j for j in jobs if j["arm_label"] != "seed-check"]
        for j in jobs:
            j["final_split"] = False
            j["block"] = "traineval"
            j["tag"] = "tag:FINAL-E-V3B1-TRAIN-%s-s%d:traineval" % (j["arm_label"], j["seed"])
        meta["canary_jobs"] = []
        meta["block"] = "traineval"
    if suite == "E" and not a.smoke and a.block == "test":                      # official 20 test ids only (the E 'final' task set also holds sel)
        jobs = [j for j in jobs if j.get("split") != "sel"]
        meta["tasks"] = [t for t in meta["tasks"] if any(j["task"] == t for j in jobs)]
    inert = sorted((e["arm"], e["seed"]) for e in entries if e["identical_to_seed"])
    jobs = [j for j in jobs if (j["arm"], j["seed"]) not in inert]
    meta["inert_mapped_to_seed_check"] = [{"arm": x, "seed": y} for x, y in inert if x != "harnesslens"]
    meta["inert_mapped_to_hl_v0"] = [{"arm": x, "seed": y} for x, y in inert if x == "harnesslens"]      # a HarnessLens champion that kept v0 is the unmodified harness: its anchor is the hl-v0 cell
    if suite == "E":
        hlfiles = {rel: C.file_sha(HL_V3 / rel) for rel in HL_V3_FILES}
        by_hl = {(e["arm"], e["seed"]): e for e in entries if e.get("hl_version")}
        for j in jobs:
            if j["arm"] == "harnesslens":
                e = by_hl[(j["arm"], j["seed"])]
                j["hl"] = {"entry": "v3", "version": e["hl_version"], "src_run_dir": e["hl_src_run_dir"], "snapshot_sha256": e["tree_sha256"], "files_sha256": hlfiles}
            elif j["arm"] == "hl-v0":
                j["hl"] = {"entry": "v3", "version": "v0", "src_run_dir": None, "snapshot_sha256": "hl-v0-unmodified", "files_sha256": hlfiles}
        meta["hl_v3_files_sha256"] = hlfiles if any(j.get("hl") for j in jobs) else None
        assert V3_ADAPTER_AIRLINE.exists() and C.file_sha(V3_ADAPTER_AIRLINE).startswith(V3_ADAPTER_SHA_PREFIX), "V3 airline adapter sha != %s" % V3_ADAPTER_SHA_PREFIX
        for j in jobs + meta.get("canary_jobs", []):
            j.update(adapter_py=str(V3_ADAPTER_AIRLINE), target_model=GPT_OSS, user_model=GPT_OSS, judge_model=GPT_OSS, gateway=GATEWAY_V3,
                     max_infra_retries=MAX_INFRA_RETRIES_V3)
            j["env"] = dict(j.get("env") or {}, TAU_JUDGE_TEMPERATURE="0", V3_MAX_RETRIES="30")
        meta["scorer"] = {"window": ver, "adapter_py": str(V3_ADAPTER_AIRLINE), "adapter_sha256": C.file_sha(V3_ADAPTER_AIRLINE), "models": GPT_OSS, "gateway": GATEWAY_V3,
                          "TAU_SEED_DIR": "unset", "max_infra_retries": MAX_INFRA_RETRIES_V3,
                          "tool_consistency": "candidate fault (error_class tool_consistency), reward 0, not retried (V3 brief rule 5a)"}
    else:
        hd = V.build_harness_dir(a.code_root, Path(out_root) / "harness")
        for j in jobs + meta.get("canary_jobs", []):
            j["gateway"] = a.sb_gateway
        V.apply_a_overrides(jobs + meta.get("canary_jobs", []), meta, a.code_root, hd)
        meta["scorer"].update(gateway=a.sb_gateway, taskset=a.taskset if not a.smoke else "smoke")
    meta.update(n_jobs=len(jobs), window=ver, counts_by_arm={}, capped_stop=V.V2_CAPPED_STOP if suite == "A" else 228_000_000, trials_per_task=a.trials,
                seed_trials=a.seed_trials, tau_seed_dir=None)
    for j in jobs:
        k = "%s/s%d" % (j["arm_label"], j["seed"])
        meta["counts_by_arm"][k] = meta["counts_by_arm"].get(k, 0) + 1
    for i, j in enumerate(jobs):
        j["idx"] = i
    with open(out, "w") as f:
        f.write(json.dumps(meta, sort_keys=True) + "\n")
        for j in jobs:
            f.write(json.dumps(j, sort_keys=True) + "\n")
    sha = C.sha256_file(out)
    out.with_suffix(".sha256").write_text("%s  %s\n" % (sha, out.name))
    return out, sha, meta


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["collect", "build"])
    ap.add_argument("--bench", required=True, choices=sorted(BENCH))
    ap.add_argument("--runs-root", default=str(C.SCRATCH / "runs/V3"))
    ap.add_argument("--champions", default=None)
    ap.add_argument("--taskset", default="clean70", choices=["clean70", "test280"])
    ap.add_argument("--seed-dir", default=None, help="shared seed artifact dir (default: the frozen seed of the v1 manifest of that suite)")
    ap.add_argument("--trials", type=int, default=10, help="trials per task for a champion cell (brief: k = 10 on B1)")
    ap.add_argument("--seed-trials", type=int, default=20, help="trials per task for the seed anchor cell (default 2 x k; to be ruled by the statistics reviewer)")
    ap.add_argument("--block", default="test", choices=["test", "traineval"], help="traineval (B1 only): every champion + the seed on the 30 official train ids, k = --trials, no seed-check, tag suffix :traineval")
    ap.add_argument("--smoke", action="store_true", help="dry-run order on SEARCH-split tasks")
    ap.add_argument("--smoke-tasks", type=int, default=2)
    ap.add_argument("--code-root", default=V.V2_CODE_ROOT, help="B2: main checkout carrying the adapter (helpers carrier)")
    ap.add_argument("--sb-gateway", default=GATEWAY_V3)
    ap.add_argument("--root", default=None)
    ap.add_argument("--manifests", default=str(C.MANIFESTS))
    a = ap.parse_args()
    if a.cmd == "collect":
        champs, problems = collect(a.bench, a.runs_root)
        outp = C.SCRATCH / "final_eval" / ("champions_V3_%s.json" % a.bench)
        C.write_json_atomic(outp, champs)
        print("frameworks:", {fw: sorted(s) for fw, s in champs.items()}, "->", outp)
        for p in problems:
            print("  not ready:", p)
        sys.exit(0)
    if not a.champions:
        sys.exit("--champions required")
    root = a.root or str(C.SCRATCH / "final_eval" / BENCH[a.bench]["ver"] / ("smoke" if a.smoke else "main"))
    out, sha, meta = build(a.bench, a.champions, root, a.manifests, a)
    print("%s order %s: %d jobs, %d tasks, sha256 %s" % (a.bench, out, meta["n_jobs"], len(meta["tasks"]), sha))
    print("counts by arm:", {k: v for k, v in sorted(meta["counts_by_arm"].items())})
    print("inert mapped to seed-check:", meta["inert_mapped_to_seed_check"])
