#!/usr/bin/env python3
"""Stage the exp895 results for the spreadsheet-history branch and the off-repo archive (run on an LSF node).

  stage_history.py branch  <out>   the branch tree: an explicit ALLOW-LIST of files, laid out like skillsbench-history
  stage_history.py archive <out>   the full raw record (ledgers, gateway call ledgers, logs, CapEvolve run folders) for cap-evolve-archive

The branch tree never contains: copies of the issue (it names an internal endpoint), scratch/smoke/probe/backup files, logs, gateway
call ledgers, raw per-rollout or per-episode ledgers, benchmark data, venvs or images. Every staged file is then checked for
credential values from ~/secrets and for internal endpoints; only paths are printed, never values.
"""
import collections, hashlib, json, re, shutil, sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
REPO = EXP.parent / "sbv400-main"
MODE, OUT = sys.argv[1], Path(sys.argv[2])
if OUT.exists():
    sys.exit(f"refusing to overwrite {OUT}")
ARMS = ["capevolve", "capevolve_v2", "skillopt", "trace2skill", "meta_harness", "evoskill", "gepa", "gepa_full", "miprov2", "wikiskill", "ace"]
INTERNAL = re.compile(r"https?://(?!127\.0\.0\.1|localhost|github\.com|schemas\.openxmlformats|arxiv)[a-z0-9-]+(\.[a-z0-9-]+){3,}", re.I)  # internal-looking hosts
copied, skipped = [], []


def cp(src: Path, dst: Path, max_bytes=5_000_000):
    if not src.exists() or src.is_symlink():
        return
    if src.is_dir():
        for f in sorted(src.rglob("*")):
            if f.is_file() and not f.is_symlink() and "__pycache__" not in f.parts:
                cp(f, dst / f.relative_to(src), max_bytes)
        return
    if src.stat().st_size > max_bytes:
        skipped.append(f"{src.stat().st_size/1e6:.1f}MB {src.relative_to(EXP.parent)}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    copied.append(dst)


# ---- recipes: the files a rerun needs, per arm (allow-list; everything else in arms/ is a build leftover)
RECIPE = {
    "ace": ["ace_arm.py", "ace_prompts_patch.py", "prompt_patch.diff", "isolation_scan.py", "budget_probe.py", "lsf_ace_search.sh",
            "lsf_ace_search_keyed.sh", "BUILD_RECORD.json", "deviations_ace.json"],
    "evoskill": ["evoskill_port.py", "isolation_scan.py", "budget_probe.py", "lsf_evoskill_search.sh", "BUILD_RECORD.json",
                 "deviations_evoskill.json"],
    "gepa": ["gepa_arm.py", "isolation_scan.py", "budget_probe.py", "lsf_gepa_search.sh", "lsf_gepa_search_keyed.sh", "BUILD_RECORD.json",
             "deviations_gepa.json"],
    "gepa_full": ["gepa_full_port.py", "isolation_scan.py", "lsf_gepa_full_search.sh", "BUILD_RECORD.json", "deviations_gepa_full.json"],
    "meta_harness": ["meta_harness_arm.py", "check_candidate.py", "skill", "isolation_scan.py", "budget_probe.py", "lsf_meta_harness_search.sh",
                     "BUILD_RECORD.json", "deviations_meta_harness.json"],
    "miprov2": ["miprov2_arm.py", "miprov2_program.py", "isolation_scan.py", "budget_probe.py", "lsf_miprov2_search.sh", "BUILD_RECORD.json",
                "deviations_miprov2.json"],
    "skillopt": ["skillopt_exp895.py", "skillopt_pack.py", "make_split.py", "scan_isolation.py", "lsf_skillopt_search.sh", "BUILD_RECORD.json",
                 "deviations_skillopt.json"],
    "trace2skill": ["trace2skill_arm.py", "t2s_analyse.py", "t2s_evolve.py", "skill-creator", "isolation_scan.py", "lsf_trace2skill_search.sh",
                    "BUILD_RECORD.json", "deviations_trace2skill.json"],
    "wikiskill": ["wikiskill_arm.py", "isolation_scan.py", "budget_probe.py", "lsf_wikiskill_search.sh", "lsf_wikiskill_search_keyed.sh",
                  "BUILD_RECORD.json", "deviations_wikiskill.json"],
    "capevolve": ["INSTRUCTIONS.exp895_addendum.md", "template"],
    "capevolve_v2": ["build_template.py", "template"],
    "common": ["rollout.py", "SPREADSHEETBENCH_GUIDANCE.md", "SURFACE_CONTRACT.md"],
}
SEARCH = ["run_summary.json", "run_meta.txt", "budget_probe.json", "isolation_scan.json", "val_evals.jsonl", "train_ids.txt", "val_ids.txt",
          "prompt_patch.diff"]
CEV_RUN = ["champion.json", "baseline.json", "state.json", "splits.json", "history.jsonl", "rejected.jsonl", "eval_index.jsonl",
           "JOURNAL.md", "INSIGHTS.md", "META_INSIGHTS.md", "FRAMEWORK_IMPROVEMENTS.md"]
TEST = ["summary.json", "summary_champion_only.json", "registry.json"]

OUT.mkdir(parents=True)
if MODE == "branch":
    for arm, files in RECIPE.items():
        for f in files:
            cp(EXP / "arms" / arm / f, OUT / "recipes" / arm / f)
    # CapEvolve's launchers live in tools/, not arms/
    cp(EXP / "tools" / "lsf_capevolve_search.sh", OUT / "recipes" / "capevolve" / "lsf_capevolve_search.sh")
    cp(EXP / "tools" / "lsf_capevolve_v2_search.sh", OUT / "recipes" / "capevolve_v2" / "lsf_capevolve_v2_search.sh")
    cp(REPO / "ci/benchmarks/spreadsheetbench/full_verified/split_ids.json", OUT / "recipes" / "split_ids.json")
    cp(REPO / "templates/adapters/spreadsheetbench/seed_capability_v2", OUT / "artifacts" / "seed")
    for arm in ARMS:
        for s in (0, 1, 2):
            run, tw = EXP / "runs" / arm / f"search_s{s}", EXP / "runs" / "test" / f"{arm}_s{s}"
            dst = OUT / "results" / arm / f"s{s}"
            for f in SEARCH:
                cp(run / f, dst / "search" / f)
            if arm.startswith("capevolve"):
                for f in CEV_RUN:
                    cp(run / "work/.capevolve/run_main" / f, dst / "search" / "run_main" / f)
            for f in TEST:
                cp(tw / f, dst / "test" / f)
            cp(tw / "champion", OUT / "artifacts" / arm / f"s{s}" / "champion")
            # per-task test means (compact stand-in for the per-episode ledger, which stays in the archive)
            rj = tw / "results.jsonl"
            if rj.exists():
                final = {}
                for line in rj.read_text().splitlines():
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if r["error_kind"] != "infra" or r["attempt"] >= 3:
                        final[(r["cell"], r["task_id"], r["trial"])] = r
                per = collections.defaultdict(lambda: collections.defaultdict(list))
                for (cell, tid, _), r in final.items():
                    if r["error_kind"] != "infra":
                        per[cell][str(tid)].append(r["reward"])
                o = {c: {t: round(sum(v) / len(v), 4) for t, v in sorted(d.items())} for c, d in per.items()}
                (dst / "test").mkdir(parents=True, exist_ok=True)
                (dst / "test" / "per_task_test_scores.json").write_text(json.dumps(o, indent=0, sort_keys=True))
    for f in ("test_window.py", "gateway.py", "auto_test_launcher.py", "results_table.py", "warmup.py", "stage_history.py",
              "lsf_exclusive_wrapper.sh", "lsf_test_window_v3.sh", "lsf_test_window_resume.sh", "lsf_test_window_keyed.sh"):
        cp(EXP / "tools" / f, OUT / "scripts" / f)
    cp(EXP / "decisions.md", OUT / "docs" / "decisions.md")
    cp(EXP / "HANDOFF_capevolve_v2.md", OUT / "docs" / "HANDOFF_capevolve_v2.md")
    cp(EXP / "runs/.watch/results_tables_avg_final_20261101.md", OUT / "reports" / "results_tables.md")
    cp(EXP / "runs/.watch/full_table.json", OUT / "results" / "full_table.json")
elif MODE == "archive":
    for arm in ARMS:
        for s in (0, 1, 2):
            cp(EXP / "runs" / arm / f"search_s{s}", OUT / "runs" / arm / f"search_s{s}", max_bytes=200_000_000)
            cp(EXP / "runs" / "test" / f"{arm}_s{s}", OUT / "runs" / "test" / f"{arm}_s{s}", max_bytes=200_000_000)
            cp(EXP / "runs" / "test" / f".gw_{arm}_s{s}", OUT / "runs" / "test" / f"gw_{arm}_s{s}", max_bytes=200_000_000)
    cp(EXP / "logs", OUT / "logs", max_bytes=200_000_000)
    cp(EXP / "arms", OUT / "arms", max_bytes=200_000_000)
    cp(EXP / "tools", OUT / "tools", max_bytes=5_000_000)
    for f in ("decisions.md", "HANDOFF_capevolve_v2.md"):
        cp(EXP / f, OUT / f)
    cp(EXP / "runs/.watch", OUT / "runs" / "watch", max_bytes=5_000_000)
else:
    sys.exit("mode must be branch or archive")

tot = sum(p.stat().st_size for p in copied)
print(f"MODE={MODE} STAGED files={len(copied)} bytes={tot} ({tot/1e6:.1f} MB) SKIPPED={len(skipped)}")
for s_ in skipped[:30]:
    print("  SKIP", s_)
top = collections.Counter()
for p in copied:
    top["/".join(p.relative_to(OUT).parts[:2])] += p.stat().st_size
for k, v in top.most_common(14):
    print(f"  {v/1e6:8.2f} MB  {k}")

vals = []
for envf in sorted((Path.home() / "secrets").glob("*.env")):
    for line in envf.read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            v = v.strip().strip("'\"")
            if len(v) >= 16 and not v.startswith("http") and any(w in k.upper() for w in ("KEY", "TOKEN", "SECRET", "PASS")):
                vals.append(v)
cred, internal = [], []
for p in copied:
    if p.stat().st_size > 60_000_000:
        continue
    t = p.read_text(errors="ignore")
    if any(v in t for v in vals):
        cred.append(str(p.relative_to(OUT)))
    if MODE == "branch" and INTERNAL.search(t):
        internal.append(str(p.relative_to(OUT)))
print(f"CREDENTIAL_VALUE_HITS {len(cred)} (checked {len(vals)} secret values)")
for h in cred[:20]:
    print("  CRED", h)
if MODE == "branch":
    print(f"INTERNAL_ENDPOINT_HITS {len(internal)}")
    for h in internal[:20]:
        print("  INTERNAL", h)
