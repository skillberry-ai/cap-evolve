#!/usr/bin/env python3
"""Append the Suite D pre-registration items to experiments/registry.jsonl (same append-only, hash-chained line format as
experiments/final/freeze.py: every line carries the sha256 of the previous line).  Idempotent per (item, sha256).

    python3 -I register_suite_d.py            # run from anywhere; paths are relative to the paper directory
"""
import glob
import hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

PAPER = Path(__file__).resolve().parents[2]
REG = PAPER / "experiments" / "registry.jsonl"
ITEMS = [
    ("suite_D_registration", PAPER / "experiments/configs/suite_D_registration.json", "cells, contrasts, Holm families, margin, final set"),
    ("analysis_plan_suite_D_amendment7", PAPER / "protocol/analysis_plan.md", "analysis plan incl. 5-AMENDMENT 7 (Suite D)"),
    ("analysis_plan_amendment12_v3", PAPER / "protocol/analysis_plan.md", "analysis plan incl. 5-AMENDMENT 12 (V3 analysis plan; registered before any V3 final rollout)"),
    ("v3_registration.json", PAPER / "experiments/configs/v3_registration.json", "machine-readable copy of amendment 12"),
    ("analysis_plan_amendment9", PAPER / "protocol/analysis_plan.md", "analysis plan incl. 5-AMENDMENT 9 (headline estimand, amendments table, inert rule, equivalence scope, AO dagger, E12B)"),
    ("suite_E_registration", PAPER / "experiments/configs/suite_E_registration.json", "Suite E (airline replication) cells, families, split hash, MDE"),
    ("suite_E_split_file", Path("/home/dev/projects2/wt-tau/protocol/tau_airline_splits.json"), "tau_airline_splits.json used by every Suite E cell and competitor"),
    ("v2_registration", PAPER / "experiments/configs/v2_registration.json", "CapEvolve v2 reruns (amendment 11)"),
    ("v2_plan", PAPER / "improve/V2_PLAN.md", "CapEvolve v2 synthesis and build plan (amendment 11 source)"),
    ("v2_version_2_0", PAPER / "experiments/configs/v2_version_2_0.json", "11E version line v2.0: code SHA, P2 defaults, Suite E scaling rule, AO-2 parameters"),
    ("v2_1_AO2_version_line", PAPER / "experiments/configs/v2_1_AO2.json", "11E version line v2.1-AO2 (secondary AO-2 version: ao_plateau_floor 0.8)"),
    ("suite_D_experiment_design", PAPER / "redesign/EXPERIMENTS.md", "experiment-designer proposal the registration was written against"),
]


SCRATCH = Path("/home/dev/projects2/campaign-scratch/scripts/E20")
WT_TAU = Path("/home/dev/projects2/wt-tau")
E30_FILES = ["build_e.py", "launch_e.sh", "launch_gepa_e.sh", "launch_nohist_e.sh", "metrics_loop_e.sh", "guard_marker.py", "cand_logger.py"]
EXTRA_FILES = ["build_d.py", "launch_d.sh", "launch_gepa_d.sh", "gepa_tau.py", "eval_cap.py", "collect_cap.py", "guard_marker.py",
               "cand_logger.py", "make_sbx_data.py"]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    lines = [l for l in (REG.read_text().splitlines() if REG.exists() else []) if l.strip()]
    have = {(json.loads(l).get("item"), json.loads(l).get("sha256")) for l in lines}
    head = subprocess.check_output(["git", "-C", str(PAPER), "rev-parse", "HEAD"], text=True).strip()
    added = 0
    items = [(i, p, n, None) for i, p, n in ITEMS]
    wt = subprocess.check_output(["git", "-C", str(WT_TAU), "rev-parse", "HEAD"], text=True).strip()
    items.append(("suite_D_wt_tau_commit", None, "wt-tau HEAD at registration time (Suite D searches were built from the commit registered earlier under this item): " + wt, hashlib.sha256(wt.encode()).hexdigest()))
    wte = subprocess.check_output(["git", "-C", "/home/dev/projects2/wt-airE", "rev-parse", "HEAD"], text=True).strip()
    items.append(("suite_E_wt_airE_commit", None, "Suite E worktree wt-airE commit: " + wte, hashlib.sha256(wte.encode()).hexdigest()))
    ADAPTERS_FINAL = [("suite_B_final_scorer_adapter", WT_TAU / "examples/tau2_retail/adapters/adapter.py"),
                      ("suite_C_final_scorer_adapter", WT_TAU / "examples/tau2_airline_c/adapters/adapter.py"),
                      ("suite_E_adapter", Path("/home/dev/projects2/wt-airE/examples/tau2_airline_c/adapters/adapter.py"))]
    for it, fp in ADAPTERS_FINAL:
        if fp.exists():
            items.append((it, fp, "tau2 adapter with infra_detail logging (analysis plan amendment 10 erratum 1)", None))
    E32_AO = [("suite_E32_ao_launch_e32_ao.sh", SCRATCH.parent / "E30" / "launch_e32_ao.sh", "E32-ao (CapEvolve agent-optimize, stock gate, E30-PT build) launcher"),
              ("suite_E32_launch_w4.sh", SCRATCH.parent / "E30" / "launch_w4.sh", "W4 wrapper adding driver.pid to competitor launchers"),
              ("suite_E_admission_loop.sh", SCRATCH.parent / "E30" / "admission_loop.sh", "Suite E admission loop (queues W1-W4, ADAPTER_REGISTERED gate)"),
              ("suite_E32_ao_optimizer_shim_claude", SCRATCH.parent.parent / "runs" / "E32" / "_sbx_bin" / "claude", "E32-ao optimizer shim (E10B shim + second bridge for :4112)")]
    for it, fp, note in E32_AO:
        if fp.exists():
            items.append((it, fp, note, None))
    TAU_AIRE = Path("/home/dev/projects2/campaign-scratch/baselines/tau_airE")
    for f in ("launch_airE.sh", "ace_tau_air.py", "mipro_tau_air.py"):
        if (TAU_AIRE / f).exists():
            items.append(("suite_E32_" + f, TAU_AIRE / f, "Suite E competitor launch/script (W4), registered before launch", None))
    _v2 = json.loads((PAPER / "experiments/configs/v2_version_2_0.json").read_text())["code"]["commit"]
    items.append(("v2_0_code_commit", None, "skillberry-ai/cap-evolve main commit of CapEvolve v2.0: " + _v2, hashlib.sha256(_v2.encode()).hexdigest()))
    V2 = Path("/home/dev/projects2/campaign-scratch/runs/V2")
    V2_FILES = [("A_hc2_s98_spec", V2 / "A/hc2/s98/project/capevolve.yaml", "HC-2 Suite A spec, s98 instance of the real spec (per-seed specs differ only in split_seed)"),
                ("A_ao2_s98_spec", V2 / "A/ao2/s98/project/capevolve.yaml", "AO-2 Suite A spec, s98 instance of the real spec"),
                ("A_project_shim_adapter", V2 / "_tools/project_template/adapters/adapter.py", "client-side project shim adapter (forwards run/score to the evaluator daemon)"),
                ("A_spreadsheetbench_adapter", Path("/home/dev/projects2/wt-v2run/templates/adapters/spreadsheetbench/adapter.py"), "spreadsheetbench adapter at the v2.0 SHA"),
                ("A_code_exec_api.py", Path("/home/dev/projects2/wt-v2run/third_party/spreadsheetbench/code_exec_docker/api.py"), "code_exec_docker api.py (KERNEL_TIMEOUT 10 min)"),
                ("A_code_exec_jupyter.py", Path("/home/dev/projects2/wt-v2run/third_party/spreadsheetbench/code_exec_docker/jupyter.py"), "code_exec_docker jupyter.py"),
                ("A_eval_daemon.py", V2 / "_tools/eval_daemon.py", "evaluator daemon (infra retry, 3 h hang watchdog, hard cap, counters)"),
                ("A_shim_claude", V2 / "_tools/shim/claude", "optimizer sandbox shim claude"),
                ("A_shim_inner.sh", V2 / "_tools/shim/inner.sh", "inner.sh (private tmpfs /tmp, run dir + .sealed blanked, project ro)"),
                ("A_sbx_bin_claude", V2 / "_sbx_bin/claude", "runs/V2/_sbx_bin/claude launcher"),
                ("A_run_v2.sh", V2 / "_tools/run_v2.sh", "Suite A v2 launcher (may be re-hashed at launch)"),
                ("A_env_v2.sh", V2 / "_tools/env_v2.sh", "Suite A v2 env"),
                ("A_scaffold_v2.sh", V2 / "_tools/scaffold_v2.sh", "Suite A v2 scaffold (may be re-hashed at launch)"),
                ("A_pysite_sitecustomize.py", V2 / "_tools/pysite/sitecustomize.py", "shutil.rmtree permission fallback for the read-only checkout"),
                ("A_make_candidates.py", V2 / "_tools/make_candidates.py", "candidate extraction"),
                ("A_make_metrics.py", V2 / "_tools/make_metrics.py", "metrics extraction"),
                ("A_start_daemon_v2.sh", V2 / "_tools/start_daemon_v2.sh", "evaluator daemon start script"),
                ("A_post_hc2.sh", V2 / "_tools/post_hc2.sh", "post-step after the hill-climb driver exits: harness.skip_finalize(run_dir) (finalize false), writes champion.json, evaluates nothing"),
                ("A_token_watchdog.py", V2 / "_tools/token_watchdog.py", "optimizer token guard"),
                ("A_capopt_egress.sh", V2 / "_tools/capopt_egress.sh", "egress check"),
                ("A_negtest_capopt.sh", V2 / "_tools/negtest_capopt.sh", "negative test for the optimizer user"),
                ("A_pooled_split_file", V2 / "_eval/split_ids.json", "pooled split file (train 80 / val 40 / test [])")]
    A_hc2_seed_files = []
    for k in (0, 1, 2):
        base = V2 / f"A/hc2/s{k}"
        A_hc2_seed_files += [(f"A_hc2_s{k}_spec", base / "project/capevolve.yaml", f"HC-2 Suite A seed {k} spec (split_seed {k})"),
                             (f"A_hc2_s{k}_split_ids", base / "project/inputs/split_ids.json", f"HC-2 Suite A seed {k} proposer-visible split ids"),
                             (f"A_hc2_s{k}_instructions", base / "project/optimizer/INSTRUCTIONS.md", f"HC-2 Suite A seed {k} optimizer instructions")]
        for sd in sorted((V2 / f"A/hc2/s{k}.sealed").glob("run_*/splits_full.json")):
            A_hc2_seed_files.append((f"A_hc2_s{k}_splits_full_sealed", sd, f"HC-2 Suite A seed {k} sealed full pool partition F/C (hash only; content not read)"))
    A_ao2_seed_files = []
    for k in (0, 1, 2):
        base = V2 / f"A/ao2/s{k}"
        A_ao2_seed_files += [(f"A_ao2_s{k}_spec", base / "project/capevolve.yaml", f"AO-2 Suite A seed {k} spec (split_seed {k})"),
                             (f"A_ao2_s{k}_split_ids", base / "project/inputs/split_ids.json", f"AO-2 Suite A seed {k} proposer-visible split ids"),
                             (f"A_ao2_s{k}_instructions", base / "project/optimizer/INSTRUCTIONS.md", f"AO-2 Suite A seed {k} optimizer instructions")]
        for sd in sorted((V2 / f"A/ao2/s{k}.sealed").glob("run_*/splits_full.json")):
            A_ao2_seed_files.append((f"A_ao2_s{k}_splits_full_sealed", sd, f"AO-2 Suite A seed {k} sealed full pool partition F/C (hash only; content not read)"))
    E_hc2_seed_files = []
    for k in (0, 1, 2):
        base = V2 / f"E/hc2/s{k}"
        E_hc2_seed_files += [(f"E_hc2_s{k}_build_record", base / "BUILD_RECORD.json", f"HC-2 Suite E seed {k} build record (spec/adapter/shim/splits hashes at launch)"),
                             (f"E_hc2_s{k}_spec", base / ".capevolve/project/capevolve.yaml", f"HC-2 Suite E seed {k} run spec"),
                             (f"E_hc2_s{k}_split_ids", base / ".capevolve/project/split_ids.json", f"HC-2 Suite E seed {k} proposer-visible split ids"),
                             (f"E_hc2_s{k}_driver", base / "driver.sh", f"HC-2 Suite E seed {k} driver"),
                             (f"E_hc2_s{k}_env", base / "env.sh", f"HC-2 Suite E seed {k} env")]
        for sd in sorted((V2 / f"E/hc2/s{k}.sealed").glob("run_*/splits_full.json")):
            E_hc2_seed_files.append((f"E_hc2_s{k}_splits_full_sealed", sd, f"HC-2 Suite E seed {k} sealed full pool partition F/C (hash only; content not read)"))
    D_hc2_seed_files = []
    for k in (0, 1, 2):
        base = V2 / f"D/hc2/s{k}"
        D_hc2_seed_files += [(f"D_hc2_s{k}_build_record", base / "BUILD_RECORD.json", f"HC-2 Suite D seed {k} build record"),
                             (f"D_hc2_s{k}_spec", base / ".capevolve/project/capevolve.yaml", f"HC-2 Suite D seed {k} run spec"),
                             (f"D_hc2_s{k}_split_ids", base / ".capevolve/project/split_ids.json", f"HC-2 Suite D seed {k} proposer-visible split ids"),
                             (f"D_hc2_s{k}_driver", base / "driver.sh", f"HC-2 Suite D seed {k} driver"),
                             (f"D_hc2_s{k}_env", base / "env.sh", f"HC-2 Suite D seed {k} env")]
        for sd in sorted((V2 / f"D/hc2/s{k}.sealed").glob("run_*/splits_full.json")):
            D_hc2_seed_files.append((f"D_hc2_s{k}_splits_full_sealed", sd, f"HC-2 Suite D seed {k} sealed full pool partition F/C (hash only; content not read)"))
    AO2_DE_seed_files = []
    for sname in ("D", "E"):
        for k in (0, 1, 2):
            base = V2 / f"{sname}/ao2/s{k}"
            if not base.exists():
                continue
            AO2_DE_seed_files += [(f"{sname}_ao2_s{k}_build_record", base / "BUILD_RECORD.json", f"AO-2 Suite {sname} seed {k} build record"),
                                  (f"{sname}_ao2_s{k}_spec", base / ".capevolve/project/capevolve.yaml", f"AO-2 Suite {sname} seed {k} run spec"),
                                  (f"{sname}_ao2_s{k}_split_ids", base / ".capevolve/project/split_ids.json", f"AO-2 Suite {sname} seed {k} proposer-visible split ids"),
                                  (f"{sname}_ao2_s{k}_driver", base / "driver.sh", f"AO-2 Suite {sname} seed {k} driver"),
                                  (f"{sname}_ao2_s{k}_env", base / "env.sh", f"AO-2 Suite {sname} seed {k} env")]
            for sd in sorted((V2 / f"{sname}/ao2/s{k}.sealed").glob("run_*/splits_full.json")):
                AO2_DE_seed_files.append((f"{sname}_ao2_s{k}_splits_full_sealed", sd, f"AO-2 Suite {sname} seed {k} sealed full pool partition F/C (hash only; content not read)"))
    V2_FILES += A_hc2_seed_files + A_ao2_seed_files + E_hc2_seed_files + D_hc2_seed_files + AO2_DE_seed_files
    _unused_marker = None
    for it, fp, note in V2_FILES:
        if fp.exists():
            items.append(("v2_11E_" + it, fp, "11E line (v2.0, Suite A): " + note, None))
    _ao = json.loads((PAPER / "experiments/configs/v2_version_2_0.json").read_text()).get("per_arm_code_pins", {}).get("AO-2", {}).get("commit")
    if _ao:
        items.append(("v2_0_code_commit_AO2", None, "AO-2 arm code pin (a3f5eeb6d + #836 + #835): " + _ao, hashlib.sha256(_ao.encode()).hexdigest()))
    CS = Path("/home/dev/projects2/campaign-scratch")
    V2DE_FILES = [("D_E_build_v2.py", CS / "scripts/V2/build_v2.py", "Suite D/E v2 project builder"),
                  ("D_E_launch_v2.sh", CS / "scripts/V2/launch_v2.sh", "Suite D/E v2 launcher (env scrub, CAPEVOLVE_OPTIMIZER_COST=off)"),
                  ("D_E_admit_v2.py", CS / "scripts/V2/admit_v2.py", "Suite D/E v2 admission rule (own 429 >= 2% or queue >= 30 s hold; v1 protection; max 6 V2 searches)"),
                  ("D_E_cost_summary.py", CS / "scripts/E30/cost_summary.py", "cost/guard helper"),
                  ("D_E_cand_logger.py", CS / "scripts/E30/cand_logger.py", "candidate logger"),
                  ("D_E_shim_claude_hc2", CS / "runs/V2/_sbx_bin/claude", "HC-2 optimizer shim (binds .capevolve/project, run_main, claude_cfg)"),
                  ("D_E_shim_claude_ao2", CS / "runs/V2/_sbx_bin_ao/claude", "AO-2 optimizer shim (WT=wt-v2run-ao)")]
    S2 = CS / "scripts/V2"
    V2DE_FILES += [("D_hc2_spec", S2 / "specs/D_hc2.capevolve.yaml", "Suite D HC-2 spec (seed-0 build; seeds do not change the spec)"),
                   ("D_ao2_spec", S2 / "specs/D_ao2.capevolve.yaml", "Suite D AO-2 spec"),
                   ("E_hc2_spec", S2 / "specs/E_hc2.capevolve.yaml", "Suite E HC-2 spec"),
                   ("E_ao2_spec", S2 / "specs/E_ao2.capevolve.yaml", "Suite E AO-2 spec"),
                   ("retail_adapter", S2 / "adapters/retail/adapter.py", "V2 retail adapter (v1 file + read-only reference/ guard)"),
                   ("airline_adapter", S2 / "adapters/airline/adapter.py", "V2 airline adapter (v1 file + read-only reference/ guard)"),
                   ("tau_retail_splits.json", S2 / "data/tau_retail_splits.json", "retail splits data"),
                   ("tau_airline_splits.json", S2 / "data/tau_airline_splits.json", "airline splits data"),
                   ("wave_v2.sh", S2 / "wave_v2.sh", "waits for admit_v2 then calls launch_v2.sh; only schedules")]
    for it, fp, note in V2DE_FILES:
        if fp.exists():
            items.append(("v2_11E_" + it, fp, "11E line (v2.0, Suites D/E): " + note, None))
    WTAO = Path("/home/dev/projects2/wt-v2run-ao")
    AO2_CODE = [("conductor.py", "skills/algorithms/agent-optimize/scripts/conductor.py"), ("conductor_backend.py", "skills/algorithms/agent-optimize/scripts/conductor_backend.py"),
                ("proposer.py", "skills/algorithms/agent-optimize/scripts/proposer.py"), ("optimizer_cost.py", "core/cap_evolve/optimizer_cost.py")]
    for nm, rel in AO2_CODE:
        if (WTAO / rel).exists():
            items.append(("v2_11E_AO2_code_" + nm, WTAO / rel, "AO-2 code file at d68775bbd (changed vs a3f5eeb6d)", None))
    for mf in sorted((PAPER / "experiments/manifests").glob("v2_run_files_*.json")):
        items.append(("v2_11E_run_files_" + mf.stem.split("_")[-1], mf, "static files of each real V2 run, hashed from disk after launch", None))
    AO2_BUILD = CS / "runs/V2/_build_records_ao2"
    for sname in ("D", "E"):
        fp = AO2_BUILD / f"{sname}_ao2_build_record.json"
        if fp.exists():
            items.append((f"v2_11E_{sname}_ao2_seed0_build_record_prelaunch", fp, f"AO-2 Suite {sname} seed-0 build record, before launch (code d68775bbd, partition equals HC-2)", None))
    _new = CS / "scripts/V2/admit_v2.py.new"
    if _new.exists():
        items.append(("v2_11E_D_E_admit_v2_cap9_candidate", _new, "admit_v2.py candidate: V2 concurrency cap 9 after the last v1 Azure-mini user ends (same bytes as admit_v2.py after the swap)", None))
    TOKEN_FILES = [("optimizer_tokens_" + x, PAPER / f"experiments/final/manifests/optimizer_tokens_{x}.json") for x in "ABCDE"]
    TOKEN_FILES += [("optimizer_tokens_" + x + "_end_of_window", CS / f"final_eval/token_recheck/optimizer_tokens_{x}_end_of_window.json") for x in "ABC"]
    for nm, fp in TOKEN_FILES:
        if fp.exists():
            items.append(("tokens_final_" + nm, fp, "final optimizer-token manifest/evidence (amendment 9 erratum 14)", None))
    for nm, rel in (("hc2", "runs/V2/_sbx_bin/claude.new"), ("ao2", "runs/V2/_sbx_bin_ao/claude.new")):
        if (CS / rel).exists():
            items.append(("v2_11E_shim_events_overlay_candidate_" + nm, CS / rel, "optimizer shim candidate: /dev/null bound over run_main/events.jsonl (confirm-chunk events isolation fix)", None))
    _h = CS / "runs/V2/_tools/harden_rundirs.sh"
    if _h.exists():
        items.append(("v2_11E_A_harden_rundirs.sh", _h, "Suite A run-dir hardening (removes group/other permissions on .capevolve, logs, manifest, .sealed)", None))
    for nm, fp in (("hc2", CS / "runs/V2/_sbx_bin/SWAP_TIME_hc2"), ("ao2", CS / "runs/V2/_sbx_bin_ao/SWAP_TIME_ao2")):
        if fp.exists():
            items.append(("v2_11E_shim_swap_time_" + nm, fp, "shim swap time (events.jsonl overlay isolation fix)", None))
    for nm, fp in (("hc2_live", CS / "runs/V2/_sbx_bin/claude"), ("ao2_live", CS / "runs/V2/_sbx_bin_ao/claude")):
        if fp.exists():
            items.append(("v2_11E_shim_live_" + nm, fp, "live optimizer shim after the isolation fix", None))
    _eq = PAPER / "experiments/final/check_scorer_equivalence_A.py"
    if _eq.exists():
        items.append(("v2_11E_A_check_scorer_equivalence.py", _eq, "Suite A v2-vs-v1 scorer equivalence check script (40 of 40 identical)", None))
    _er = PAPER / "experiments/final/manifests/scorer_equivalence_A_result.json"
    if _er.exists():
        items.append(("v2_11E_A_scorer_equivalence_result", _er, "40-row Suite A v2-vs-v1 scorer equivalence result", None))
    S21 = CS / "scripts/V2"
    for nm, fp, note in (("build_v21.py", S21 / "build_v21.py", "v2.1-AO2 builder (copy of build_v2.py adding arm ao21)"),
                         ("launch_v21.sh", S21 / "launch_v21.sh", "v2.1-AO2 launcher (copy of launch_v2.sh calling build_v21.py)"),
                         ("E_ao21_spec", S21 / "specs/E_ao21.capevolve.yaml", "v2.1-AO2 Suite E spec (v2.0 AO-2 spec + ao_plateau_floor 0.8)"),
                         ("D_ao21_spec", S21 / "specs/D_ao21.capevolve.yaml", "v2.1-AO2 Suite D spec (v2.0 AO-2 spec + ao_plateau_floor 0.8)"),
                         ("champions_V2_E.json", CS / "final_eval/champions_V2_E.json", "Suite E v2.0 champions (all six searches ended; frozen dirs equal the run candidates)")):
        if fp.exists():
            items.append(("v2_1_AO2_" + nm, fp, "11E v2.1-AO2 / v2.0 record: " + note, None))
    FE = CS / "final_eval"
    RESULT_NAMES = ["results_long.csv", "results_long_end.csv", "results_long_infra_missing.csv", "results_long_first_attempt_infra_zero.csv",
                    "results_long_end_infra_missing.csv", "results_long_end_first_attempt_infra_zero.csv", "results_trials.csv", "results_trials_end.csv",
                    "per_arm_report.json", "per_artifact_infra_rates.json", "infra_diagnostic.json", "rollout_log.csv", "raw/rollouts.jsonl",
                    "interruptions.jsonl", "canary.jsonl"]
    for win in ("A", "B", "C", "D", "E", "V2/E", "V2/D", "V2/A", "V21/D", "V21/A", "V3B1/main", "V3B1/traineval", "V3B1LATE/main", "V3B1CHAIN/main", "V3B1REJ/main", "V4B1S2/main", "ABLW1/main", "ABLW2/main", "MERGED/main", "BRIDGE1/main"):   # add V2/D and V2/A only after their windows have ended
        for rn in RESULT_NAMES:
            fp = FE / win / rn
            if fp.exists():
                items.append(("results_" + win.replace("/", "_") + "_" + rn.replace("/", "_"), fp, f"final-window results file, window {win}, hashed BEFORE any analysis (content not read by the registrar)", None))
    AO21_SEED = []
    for sname in ("A", "D", "E"):
        for k in (0, 1, 2):
            base = V2 / f"{sname}/ao21/s{k}"
            if not base.exists():
                continue
            proj = base / "project" if sname == "A" else base / ".capevolve/project"
            sid = proj / ("inputs/split_ids.json" if sname == "A" else "split_ids.json")
            AO21_SEED += [(f"{sname}_ao21_s{k}_spec", proj / "capevolve.yaml", f"v2.1-AO2 Suite {sname} seed {k} run spec"),
                          (f"{sname}_ao21_s{k}_split_ids", sid, f"v2.1-AO2 Suite {sname} seed {k} proposer-visible split ids"),
                          (f"{sname}_ao21_s{k}_build_record", base / "BUILD_RECORD.json", f"v2.1-AO2 Suite {sname} seed {k} build record"),
                          (f"{sname}_ao21_s{k}_driver", base / "driver.sh", f"v2.1-AO2 Suite {sname} seed {k} driver"),
                          (f"{sname}_ao21_s{k}_env", base / "env.sh", f"v2.1-AO2 Suite {sname} seed {k} env")]
            for sd in sorted((V2 / f"{sname}/ao21/s{k}.sealed").glob("run_*/splits_full.json")):
                AO21_SEED.append((f"{sname}_ao21_s{k}_splits_full_sealed", sd, f"v2.1-AO2 Suite {sname} seed {k} sealed full pool partition (hash only; content not read)"))
    for it, fp, note in AO21_SEED:
        if fp.exists():
            items.append(("v2_1_AO2_" + it, fp, "11E v2.1-AO2 per-seed file: " + note, None))
    for nm, fp, note in (("A_harden_rundirs_ao21.sh", V2 / "_tools/harden_rundirs_ao21.sh", "harden_rundirs.sh with the arm loop changed to ao21 (same chmod sweep; no effect on search)"),
                         ("A_scaffold_v21.sh", V2 / "_tools/scaffold_v21.sh", "Suite A v2.1-AO2 scaffold (v2.0 scaffold + ao_plateau_floor 0.8)"),
                         ("A_run_v21.sh", V2 / "_tools/run_v21.sh", "Suite A v2.1-AO2 launcher"),
                         ("make_champions_ao21.py", CS / "scripts/V2/make_champions_ao21.py", "champions extraction for the ao21 arm"),
                         ("champions_V2_D.json", CS / "final_eval/champions_V2_D.json", "Suite D v2.0 champions (all six = seed)"),
                         ("champions_V2_E_ao21.json", CS / "final_eval/champions_V2_E_ao21.json", "Suite E v2.1-AO2 champions (all three seeds ended; frozen/seed per run)"),
                         ("champions_V2_D_ao21.json", CS / "final_eval/champions_V2_D_ao21.json", "Suite D v2.1-AO2 champions (all three seeds ended; frozen/seed per run)"),
                         ("ao21_voided_accept_evidence_A_s0", V2 / "A/ao21/s0/logs/host.err", "evidence for erratum 43: host.err of A ao21 s0 with the 51 commit.py refusals (hash only)"),
                         ("ao21_voided_accept_evidence_A_s1", V2 / "A/ao21/s1/logs/host.err", "evidence for erratum 43: host.err of A ao21 s1 with the 51 commit.py refusals (hash only)"),
                         ("ao21_voided_accept_evidence_A_s2", V2 / "A/ao21/s2/logs/host.err", "evidence for erratum 43: host.err of A ao21 s2 with the 51 commit.py refusals (hash only)"),
                         ("ao21_voided_accept_evidence_D_s0", V2 / "D/ao21/s0/run.log", "evidence for erratum 43: run.log of D ao21 s0 with the 51 commit.py refusals (hash only)"),
                         ("champions_V2_A_ao21.json", CS / "final_eval/champions_V2_A_ao21.json", "Suite A v2.1-AO2 champions = P2-accepted candidates cand_11/cand_5/cand_10 (erratum 43/44)"),
                         ("champions_V2_A_ao21_surface.json", CS / "final_eval/champions_V2_A_ao21_surface.json", "surface hashes of the Suite A v2.1-AO2 champions (erratum 44)"),
                         ("frozen_V2_A_ao21_s0_prompt.md", CS / "final_eval/frozen_V2_A_ao21/s0/prompt.md", "frozen A v2.1-AO2 champion s0 surface file prompt.md (hash only)"),
                         ("frozen_V2_A_ao21_s0_task_template.md", CS / "final_eval/frozen_V2_A_ao21/s0/task_template.md", "frozen A v2.1-AO2 champion s0 surface file task_template.md (hash only)"),
                         ("frozen_V2_A_ao21_s0_skills_spreadsheet-helpers_SKILL.md", CS / "final_eval/frozen_V2_A_ao21/s0/skills/spreadsheet-helpers/SKILL.md", "frozen A v2.1-AO2 champion s0 surface file skills/spreadsheet-helpers/SKILL.md (hash only)"),
                         ("frozen_V2_A_ao21_s1_prompt.md", CS / "final_eval/frozen_V2_A_ao21/s1/prompt.md", "frozen A v2.1-AO2 champion s1 surface file prompt.md (hash only)"),
                         ("frozen_V2_A_ao21_s1_task_template.md", CS / "final_eval/frozen_V2_A_ao21/s1/task_template.md", "frozen A v2.1-AO2 champion s1 surface file task_template.md (hash only)"),
                         ("frozen_V2_A_ao21_s1_skills_spreadsheet-helpers_SKILL.md", CS / "final_eval/frozen_V2_A_ao21/s1/skills/spreadsheet-helpers/SKILL.md", "frozen A v2.1-AO2 champion s1 surface file skills/spreadsheet-helpers/SKILL.md (hash only)"),
                         ("frozen_V2_A_ao21_s2_prompt.md", CS / "final_eval/frozen_V2_A_ao21/s2/prompt.md", "frozen A v2.1-AO2 champion s2 surface file prompt.md (hash only)"),
                         ("frozen_V2_A_ao21_s2_task_template.md", CS / "final_eval/frozen_V2_A_ao21/s2/task_template.md", "frozen A v2.1-AO2 champion s2 surface file task_template.md (hash only)"),
                         ("frozen_V2_A_ao21_s2_skills_spreadsheet-helpers_SKILL.md", CS / "final_eval/frozen_V2_A_ao21/s2/skills/spreadsheet-helpers/SKILL.md", "frozen A v2.1-AO2 champion s2 surface file skills/spreadsheet-helpers/SKILL.md (hash only)"),
                         ("champions_V2_D_ao21_erratum43.json", CS / "final_eval/champions_V2_D_ao21_erratum43.json", "Suite D v2.1-AO2 champions after erratum 43: s0 = P2-accepted cand_5, s1/s2 = seed"),
                         ("D_ao21_s0_cand5_provenance", V2 / "D/ao21/s0" / "CAND5_PROVENANCE.json", "provenance of D ao21 s0 cand_5 (erratum 43)"),
                         ("D_ao21_s0_events_jsonl_at_ruling", V2 / "D/ao21/s0" / ".capevolve/run_main/events.jsonl", "search-split events of D ao21 s0 (verdict bits; hash only) at the time of erratum 43"),
                         ("D_ao21_s0_cand5_policy", V2 / "D/ao21/s0" / "frozen_manual/cand_5/policy/policy.md", "D ao21 s0 cand_5 policy.md"),
                         ("D_ao21_s0_cand5_tools", V2 / "D/ao21/s0" / "frozen_manual/cand_5/tools/tools.py", "D ao21 s0 cand_5 tools.py (equals the seed's)"),
                         ("A_ao21_s0_events_jsonl_at_ruling", Path(glob.glob(str(V2 / "A/ao21/s0/.capevolve/run_*/events.jsonl"))[0]), "search-split events of A ao21 s0 (verdict bits; hash only) at the time of erratum 43"),
                         ("A_ao21_s1_events_jsonl_at_ruling", Path(glob.glob(str(V2 / "A/ao21/s1/.capevolve/run_*/events.jsonl"))[0]), "search-split events of A ao21 s1 (verdict bits; hash only) at the time of erratum 43"),
                         ("A_ao21_s2_events_jsonl_at_ruling", Path(glob.glob(str(V2 / "A/ao21/s2/.capevolve/run_*/events.jsonl"))[0]), "search-split events of A ao21 s2 (verdict bits; hash only) at the time of erratum 43"),
                         ("V21_A_order", PAPER / "experiments/final/manifests/order_V21_A.jsonl", "Suite A v2.1-AO2 window order file (630 jobs), registered before the first rollout (erratum 46)"),
                         ("V21_A_comparison_family", PAPER / "experiments/final/manifests/comparison_family_V21_A.json", "Suite A v2.1-AO2 window comparison family (ao21 vs seed, ao21 vs GEPA, Holm m = 2)"),
                         ("V21_A_artifact_manifest", PAPER / "experiments/final/manifests/artifacts_V21_A.json", "Suite A v2.1-AO2 window artifact manifest"),
                         ("ao21_A_accept_records.json", CS / "final_eval/ao21_accept_records.json", "P2-accept verdict records of A ao21 s0-s2 (status only; line sha256 verified by the reviewer)"),
                         ("V21_D_order", PAPER / "experiments/final/manifests/order_V21_D.jsonl", "Suite D v2.1-AO2 window order file (1,400 jobs), registered before the first rollout (erratum 47)"),
                         ("V21_D_comparison_family", PAPER / "experiments/final/manifests/comparison_family_V21_D.json", "Suite D v2.1-AO2 window comparison family (ao21 vs seed, ao21 vs GEPA, Holm m = 2)"),
                         ("V21_D_artifact_manifest", PAPER / "experiments/final/manifests/artifacts_V21_D.json", "Suite D v2.1-AO2 window artifact manifest"),
                         ("V3_B1_airline_adapter", CS / "scripts/V3/adapters/airline/adapter.py", "V3 B1 airline adapter; 8d4cf8b7 used by all finished runs (decisions.md 2026-10-15 00:52 UTC), then 9c797d8a (uuid suffix on the native-sims results filename; no scoring change), for future runs only"),
                         ("V3B1_artifact_manifest", PAPER / "experiments/final/manifests/artifacts_V3B1.json", "V3 B1 artifact manifest (33 champion cells, none inert), registered before the order (amendment 12 erratum 2)"),
                         ("V3B1_competitor_list", PAPER / "experiments/final/manifests/v3_b1_competitors.json", "V3 B1 competitor list as of erratum 2 (8 in the order; ace and harnesslens pending)"),
                         ("V3B1_version_freeze", PAPER / "experiments/final/manifests/v3_b1_version_freeze.json", "V3 B1 version-freeze lines of HC-stock, HC-3, AO-2.2 (heads read after the runs; to be confirmed by the runners)"),
                         ("V3B1_champions_competitors", CS / "final_eval/champions_V3_B1_competitors.json", "V3 B1 champions file"),
                         ("V3B1_order_final", PAPER / "experiments/final/manifests/order_V3B1.jsonl", "V3 B1 test window order (7,200 jobs, adapter pin 9c797d8a); supersedes 48abbd4c which was never registered (amendment 12 erratum 4)"),
                         ("V3B1_artifact_manifest_final", PAPER / "experiments/final/manifests/artifacts_V3B1.json", "V3 B1 artifact manifest paired with the final test order"),
                         ("V3B1_traineval_order", PAPER / "experiments/final/manifests/order_V3B1_traineval.jsonl", "V3 B1 descriptive train-30 re-evaluation order (5,100 jobs, k = 5, split train)"),
                         ("V3B1_traineval_artifact_manifest", PAPER / "experiments/final/manifests/artifacts_V3B1_traineval.json", "V3 B1 descriptive train re-evaluation artifact manifest"),
                         ("V3B1_competitor_list_final", PAPER / "experiments/final/manifests/v3_b1_competitors.json", "V3 B1 competitor list (8 in the order; ace and harnesslens pending, follow-up window), updated with the final orders"),
                         ("V3B1LATE_order", PAPER / "experiments/final/manifests/order_V3B1LATE.jsonl", "V3 B1 late-competitor window order (3,400 jobs; ACE, hl-v0, 9 CapEvolve champions, seed n = 20, seed-check), registered before launch (amendment 12 erratum 11)"),
                         ("V3B1LATE_artifact_manifest", PAPER / "experiments/final/manifests/artifacts_V3B1LATE.json", "V3 B1 LATE artifact manifest"),
                         ("V3B1LATE_cells", PAPER / "experiments/final/manifests/v3_b1_late_cells.json", "V3 B1 LATE cell list with tree hashes"),
                         ("V3B1LATE_champions", CS / "final_eval/champions_V3B1LATE.json", "V3 B1 LATE champions file"),
                         ("V3B1LATE_comparison_family", PAPER / "experiments/final/manifests/comparison_family_V3B1LATE.json", "V3 B1 LATE comparison families LC-ACE and LC-HL (written by the reviewer)"),
                         ("V3B1_hl_tau_v3_opencode_tau2.py", CS / "baselines/harnesslens/tau_v3/src/harnesslens/benchmarks/opencode_tau2.py", "HarnessLens tau_v3 scorer file pinned for the LATE window"),
                         ("V3B1_hl_tau_v3_hl_final_eval_v3.py", CS / "baselines/harnesslens/tau_v3/hl_final_eval_v3.py", "HarnessLens tau_v3 final-eval entrypoint pinned for the LATE window"),
                         ("V3B1_hl_tau_v3_hl_fe_worker_v3.py", CS / "baselines/harnesslens/tau_v3/hl_fe_worker_v3.py", "HarnessLens tau_v3 worker pinned for the LATE window"),
                         ("V3B1_ace_s0_run_summary", CS / "runs/V3/B1/ace/s0/run_summary.json", "ACE s0 V3 B1 run summary (R binding)"),
                         ("V3B1_ace_s1_run_summary", CS / "runs/V3/B1/ace/s1/run_summary.json", "ACE s1 V3 B1 run summary (R binding)"),
                         ("V3B1_ace_s2_run_summary", CS / "runs/V3/B1/ace/s2/run_summary.json", "ACE s2 V3 B1 run summary (R binding)"),
                         ("V3B1_hl_s0_run_summary", CS / "runs/V3/B1/harnesslens/s0/run_summary.json", "HarnessLens s0 V3 B1 run summary (native end, accepted_versions empty)"),
                         ("V3B1_hl_s1_run_summary", CS / "runs/V3/B1/harnesslens/s1/run_summary.json", "HarnessLens s1 V3 B1 run summary (native end, accepted_versions empty)"),
                         ("V3B1_hl_s2_run_summary", CS / "runs/V3/B1/harnesslens/s2/run_summary.json", "HarnessLens s2 V3 B1 run summary (native end, accepted_versions empty)"),
                         ("V3B1CHAIN_order", PAPER / "experiments/final/manifests/order_V3B1CHAIN.jsonl", "V3 B1 CHAIN descriptive window order (4,400 jobs: 19 accepted intermediate candidates, seed n = 20, seed-check), registered before launch (amendment 12 erratum 15)"),
                         ("V3B1CHAIN_artifact_manifest", PAPER / "experiments/final/manifests/artifacts_V3B1CHAIN.json", "V3 B1 CHAIN artifact manifest"),
                         ("V3B1CHAIN_cells", PAPER / "experiments/final/manifests/v3_b1_chain_cells.json", "V3 B1 CHAIN cell list"),
                         ("V3B1CHAIN_champions", CS / "final_eval/champions_V3B1CHAIN.json", "V3 B1 CHAIN cells file"),
                         ("V3B1REJ_order", PAPER / "experiments/final/manifests/order_V3B1REJ.jsonl", "V3 B1 REJ descriptive window order (9,600 jobs: 45 rejected HC-stock candidates, seed n = 20, seed-check), registered before launch (amendment 12 erratum 19)"),
                         ("V3B1REJ_artifact_manifest", PAPER / "experiments/final/manifests/artifacts_V3B1REJ.json", "V3 B1 REJ artifact manifest"),
                         ("V3B1REJ_cells", PAPER / "experiments/final/manifests/v3_b1_rej_cells.json", "V3 B1 REJ cell list (candidate, parent, gate reason, tree hash)"),
                         ("V3B1REJ_champions", CS / "final_eval/champions_V3B1REJ.json", "V3 B1 REJ cells file"),
                         ("rej_analysis.py", PAPER / "analysis/scripts/rej_analysis.py", "REJ-versus-accepted descriptive analysis script (amendment 12 erratum 20), registered after its first run"),
                         ("V4B1S2_order", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "order_V4B1S2.jsonl", "V4 B1 single-champion descriptive window order (800 jobs: hcv4 s2 cand_0002 x 200, seed n = 20, seed-check), registered before launch (amendment 12 erratum 21); file lives in the paper repo checkout mlsys2027-cap-evolve-paper"),
                         ("V4B1S2_artifact_manifest", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "artifacts_V4B1S2.json", "V4 B1 S2 artifact manifest"),
                         ("V4B1S2_champions", CS / "final_eval/champions_V4B1S2.json", "V4 B1 S2 champions file (hcv4 s2)"),
                         ("V4B1_hcv4_s2_run_summary", CS / "runs/V4/B1/hcv4/s2/run_summary.json", "hcv4 s2 run summary"),
                         ("V4B1_hcv4_s2_candidates", CS / "runs/V4/B1/hcv4/s2/candidates.jsonl", "hcv4 s2 candidates.jsonl (selection by train score)"),
                         ("v4b1s2_analysis.py", PAPER / "analysis/scripts/v4b1s2_analysis.py", "V4B1S2 descriptive analysis script (amendment 12 erratum 23), registered after its first run"),
                         ("ABL_CAP-P_s0_run_summary", CS / "runs/ABL/CAP-P/s0/run_summary.json", "ablation CAP-P seed 0 run summary (amendment 12 erratum 24)"),
                         ("ABL_CAP-TD_s0_run_summary", CS / "runs/ABL/CAP-TD/s0/run_summary.json", "ablation CAP-TD seed 0 run summary (amendment 12 erratum 24)"),
                         ("ABL_CAP-TC_s0_run_summary", CS / "runs/ABL/CAP-TC/s0/run_summary.json", "ablation CAP-TC seed 0 run summary (amendment 12 erratum 24)"),
                         ("ABL_HIST-NONE_s0_run_summary", CS / "runs/ABL/HIST-NONE/s0/run_summary.json", "ablation HIST-NONE seed 0 run summary (amendment 12 erratum 24)"),
                         ("ABL_HIST-STATE_s0_run_summary", CS / "runs/ABL/HIST-STATE/s0/run_summary.json", "ablation HIST-STATE seed 0 run summary (amendment 12 erratum 24)"),
                         ("ABL_INFO-REWARD_s0_run_summary", CS / "runs/ABL/INFO-REWARD/s0/run_summary.json", "ablation INFO-REWARD seed 0 run summary (amendment 12 erratum 24)"),
                         ("ABL_INFO-EVAL_s0_run_summary", CS / "runs/ABL/INFO-EVAL/s0/run_summary.json", "ablation INFO-EVAL seed 0 run summary (amendment 12 erratum 24)"),
                         ("ABL_INFO-FAIL_s0_run_summary", CS / "runs/ABL/INFO-FAIL/s0/run_summary.json", "ablation INFO-FAIL seed 0 run summary (amendment 12 erratum 24)"),
                         ("ABL_GATE-K0.5_s0_run_summary", CS / "runs/ABL/GATE-K0.5/s0/run_summary.json", "ablation GATE-K0.5 seed 0 run summary (amendment 12 erratum 24)"),
                         ("ABL_GATE-K2_s0_run_summary", CS / "runs/ABL/GATE-K2/s0/run_summary.json", "ablation GATE-K2 seed 0 run summary (amendment 12 erratum 24)"),
                         ("ABL_GATE-NONE_s0_run_summary", CS / "runs/ABL/GATE-NONE/s0/run_summary.json", "ablation GATE-NONE seed 0 run summary (amendment 12 erratum 24)"),
                         ("ABL_GATE-DISJOINT_s0_run_summary", CS / "runs/ABL/GATE-DISJOINT/s0/run_summary.json", "ablation GATE-DISJOINT seed 0 run summary (amendment 12 erratum 24)"),
                         ("ABLW1_champions_draft", CS / "final_eval/champions_ABL_W1.json", "ABL-W1 champions file as first sent (12 ablation champions, no HC-stock reference cell); the window needs a rebuilt order (amendment 12 erratum 24)"),
                         ("ABLW1_order", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "order_ABLW1.jsonl", "ABL-W1 held-out window order (3,200 jobs: 12 ablation champions, HC-stock s0 reference, seed n = 20, seed-check), registered before launch (amendment 12 erratum 25); file lives in the paper repo checkout"),
                         ("ABLW1_artifact_manifest", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "artifacts_ABLW1.json", "ABL-W1 artifact manifest"),
                         ("ABLW1_champions", CS / "final_eval/champions_ABL_W1.json", "ABL-W1 champions file (13 cells including the HC-stock reference)"),
                         ("ablw1_analysis.py", PAPER / "analysis/scripts/ablw1_analysis.py", "ABL-W1 analysis script (amendment 12 erratum 29), registered after its first run"),
                         ("NC_NC-1SHOT_session_json", CS / "runs/NC" / "NC-1SHOT/session_1.json", "NC-1SHOT Claude Code session record (cost, turns; hash only)"),
                         ("NC_NC-1SHOT_BUILD_RECORD", CS / "runs/NC" / "NC-1SHOT/BUILD_RECORD.json", "NC-1SHOT build record"),
                         ("NC_NC-1SHOT_final_policy", CS / "runs/NC" / "NC-1SHOT/final/policy/policy.md", "NC-1SHOT final policy.md"),
                         ("NC_NC-1SHOT_final_tools", CS / "runs/NC" / "NC-1SHOT/final/tools/tools.py", "NC-1SHOT final tools.py"),
                         ("NC_NC-LOOP_session_json", CS / "runs/NC" / "NC-LOOP/session_1.json", "NC-LOOP Claude Code session record (cost, turns; hash only)"),
                         ("NC_NC-LOOP_BUILD_RECORD", CS / "runs/NC" / "NC-LOOP/BUILD_RECORD.json", "NC-LOOP build record"),
                         ("NC_NC-LOOP_final_policy", CS / "runs/NC" / "NC-LOOP/final/policy/policy.md", "NC-LOOP final policy.md"),
                         ("NC_NC-LOOP_final_tools", CS / "runs/NC" / "NC-LOOP/final/tools/tools.py", "NC-LOOP final tools.py"),
                         ("NC_NC-SKILLS_session_json", CS / "runs/NC" / "NC-SKILLS/session_1.json", "NC-SKILLS Claude Code session record (cost, turns; hash only)"),
                         ("NC_NC-SKILLS_BUILD_RECORD", CS / "runs/NC" / "NC-SKILLS/BUILD_RECORD.json", "NC-SKILLS build record"),
                         ("NC_NC-SKILLS_final_policy", CS / "runs/NC" / "NC-SKILLS/final/policy/policy.md", "NC-SKILLS final policy.md"),
                         ("NC_NC-SKILLS_final_tools", CS / "runs/NC" / "NC-SKILLS/final/tools/tools.py", "NC-SKILLS final tools.py"),
                         ("ABLW2_order", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "order_ABLW2.jsonl", "ABL-W2 held-out window order (1,400 jobs: NC-1SHOT, NC-LOOP, NC-SKILLS, HC-stock s0 reference, seed n = 20, seed-check), registered before launch (amendment 12 erratum 32); file lives in the paper repo checkout"),
                         ("ABLW2_artifact_manifest", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "artifacts_ABLW2.json", "ABL-W2 artifact manifest"),
                         ("ABLW2_champions", CS / "final_eval/champions_ABL_W2.json", "ABL-W2 champions file"),
                         ("ABL2_WINDOW_DESIGN_md", CS / "scripts/ABL2/WINDOW_DESIGN.md", "ABL-V2 pre-registration file WINDOW_DESIGN.md as submitted by ablation-lead before any ABL-V2 search launches (amendment 12 addendum 11)"),
                         ("ABL2_DESIGN_md", CS / "scripts/ABL2/DESIGN.md", "ABL-V2 pre-registration file DESIGN.md as submitted by ablation-lead before any ABL-V2 search launches (amendment 12 addendum 11)"),
                         ("ABL2_SURFACE_PARAGRAPHS_txt", CS / "scripts/ABL2/SURFACE_PARAGRAPHS.txt", "ABL-V2 pre-registration file SURFACE_PARAGRAPHS.txt as submitted by ablation-lead before any ABL-V2 search launches (amendment 12 addendum 11)"),
                         ("ABL2_build_abl2_py", CS / "scripts/ABL2/build_abl2.py", "ABL-V2 pre-registration file build_abl2.py as submitted by ablation-lead before any ABL-V2 search launches (amendment 12 addendum 11)"),
                         ("ABL2_finalize_abl2_py", CS / "scripts/ABL2/finalize_abl2.py", "ABL-V2 pre-registration file finalize_abl2.py as submitted by ablation-lead before any ABL-V2 search launches (amendment 12 addendum 11)"),
                         ("ABL2_launch_abl2_sh", CS / "scripts/ABL2/launch_abl2.sh", "ABL-V2 pre-registration file launch_abl2.sh as submitted by ablation-lead before any ABL-V2 search launches (amendment 12 addendum 11)"),
                         ("NC2_nc2_build.py", CS / "scripts/NC2/nc2_build.py", "NC2 script nc2_build.py used by the ABL-V2 native Claude Code searches; registered after their launch (amendment 12 erratum 39)"),
                         ("NC2_nc2_driver.sh", CS / "scripts/NC2/nc2_driver.sh", "NC2 script nc2_driver.sh used by the ABL-V2 native Claude Code searches; registered after their launch (amendment 12 erratum 39)"),
                         ("NC2_nc2_shim", CS / "scripts/NC2/nc2_shim", "NC2 script nc2_shim used by the ABL-V2 native Claude Code searches; registered after their launch (amendment 12 erratum 39)"),
                         ("NC2_eval_candidate", CS / "scripts/NC2/eval_candidate", "NC2 script eval_candidate used by the ABL-V2 native Claude Code searches; registered after their launch (amendment 12 erratum 39)"),
                         ("NC2_eval_daemon.py", CS / "scripts/NC2/eval_daemon.py", "NC2 script eval_daemon.py used by the ABL-V2 native Claude Code searches; registered after their launch (amendment 12 erratum 39)"),
                         ("NC2_sandbox_negative_test.sh", CS / "scripts/NC2/sandbox_negative_test.sh", "NC2 script sandbox_negative_test.sh used by the ABL-V2 native Claude Code searches; registered after their launch (amendment 12 erratum 39)"),
                         ("NC2_parity_check.py", CS / "scripts/NC2/parity_check.py", "NC2 script parity_check.py used by the ABL-V2 native Claude Code searches; registered after their launch (amendment 12 erratum 39)"),
                         ("NC2_gw_bridge.py", CS / "scripts/NC2/gw_bridge.py", "NC2 script gw_bridge.py used by the ABL-V2 native Claude Code searches; registered after their launch (amendment 12 erratum 39)"),
                         ("ABL2_A2a_s0_INSTRUCTIONS", CS / "runs/ABL2/A2a/s0/.capevolve/project/optimizer/INSTRUCTIONS.md", "ABL-V2 A2a s0 proposer instructions as launched (hash only)"),
                         ("ABL2_A2a_s1_INSTRUCTIONS", CS / "runs/ABL2/A2a/s1/.capevolve/project/optimizer/INSTRUCTIONS.md", "ABL-V2 A2a s1 proposer instructions as launched (hash only)"),
                         ("ABL2_A2b_s0_INSTRUCTIONS", CS / "runs/ABL2/A2b/s0/.capevolve/project/optimizer/INSTRUCTIONS.md", "ABL-V2 A2b s0 proposer instructions as launched (hash only)"),
                         ("ABL2_A2b_s1_INSTRUCTIONS", CS / "runs/ABL2/A2b/s1/.capevolve/project/optimizer/INSTRUCTIONS.md", "ABL-V2 A2b s1 proposer instructions as launched (hash only)"),
                         ("ABL2_A3a_s0_INSTRUCTIONS", CS / "runs/ABL2/A3a/s0/.capevolve/project/optimizer/INSTRUCTIONS.md", "ABL-V2 A3a s0 proposer instructions as launched (hash only)"),
                         ("ABL2_A3a_s1_INSTRUCTIONS", CS / "runs/ABL2/A3a/s1/.capevolve/project/optimizer/INSTRUCTIONS.md", "ABL-V2 A3a s1 proposer instructions as launched (hash only)"),
                         ("ABL2_A3b_s0_INSTRUCTIONS", CS / "runs/ABL2/A3b/s0/.capevolve/project/optimizer/INSTRUCTIONS.md", "ABL-V2 A3b s0 proposer instructions as launched (hash only)"),
                         ("ABL2_A3b_s1_INSTRUCTIONS", CS / "runs/ABL2/A3b/s1/.capevolve/project/optimizer/INSTRUCTIONS.md", "ABL-V2 A3b s1 proposer instructions as launched (hash only)"),
                         ("ABL_GATE-K2_s3_run_summary", CS / "runs/ABL/GATE-K2/s3/run_summary.json", "GATE-K2 seed 3 run summary (amendment 12 erratum 40)"),
                         ("ABL_GATE-K2_s3_candidates", CS / "runs/ABL/GATE-K2/s3/candidates.jsonl", "GATE-K2 seed 3 candidates.jsonl"),
                         ("ABL_GATE-K2_s3_final_policy", CS / "runs/ABL/GATE-K2/s3/final/policy/policy.md", "GATE-K2 seed 3 champion policy.md"),
                         ("ABL_GATE-K2_s3_final_tools", CS / "runs/ABL/GATE-K2/s3/final/tools/tools.py", "GATE-K2 seed 3 champion tools.py"),
                         ("ABL_GATE-K2_s3_events", CS / "runs/ABL/GATE-K2/s3/.capevolve/run_main/events.jsonl", "GATE-K2 seed 3 search events (search-split; hash only)"),
                         ("k2_search_labels.csv", Path("/home/dev/projects2/mlsys-k2-notes/paper/data/derived/k2_search_labels.csv"), "paper label to registered run ID mapping for the GATE-K2 searches, as released with the paper data (amendment 12 erratum 45)"),
                         ("MERGED_order", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "order_MERGED.jsonl", "MERGED window order (8,600 jobs; K2 s0-s3, 8 optimizers x 3, ACE x 3, hl-v0, NC-LOOP, six ABL-V2 s0 champions, seed n = 20, seed-check), registered before launch (amendment 12 erratum 47); file lives in the paper repo checkout"),
                         ("MERGED_artifact_manifest", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "artifacts_MERGED.json", "MERGED window artifact manifest"),
                         ("MERGED_champions", CS / "final_eval/champions_MERGED.json", "MERGED window champions file (41 cells)"),
                         ("ABL2_A2a_s0_run_summary.json", CS / "runs/ABL2/A2a/s0/run_summary.json", "ABL-V2 A2a seed 0 run_summary.json"),
                         ("ABL2_A2a_s0_candidates.jsonl", CS / "runs/ABL2/A2a/s0/candidates.jsonl", "ABL-V2 A2a seed 0 candidates.jsonl"),
                         ("ABL2_A2b_s0_run_summary.json", CS / "runs/ABL2/A2b/s0/run_summary.json", "ABL-V2 A2b seed 0 run_summary.json"),
                         ("ABL2_A2b_s0_candidates.jsonl", CS / "runs/ABL2/A2b/s0/candidates.jsonl", "ABL-V2 A2b seed 0 candidates.jsonl"),
                         ("ABL2_A3a_s0_run_summary.json", CS / "runs/ABL2/A3a/s0/run_summary.json", "ABL-V2 A3a seed 0 run_summary.json"),
                         ("ABL2_A3a_s0_candidates.jsonl", CS / "runs/ABL2/A3a/s0/candidates.jsonl", "ABL-V2 A3a seed 0 candidates.jsonl"),
                         ("ABL2_A3b_s0_run_summary.json", CS / "runs/ABL2/A3b/s0/run_summary.json", "ABL-V2 A3b seed 0 run_summary.json"),
                         ("ABL2_A3b_s0_candidates.jsonl", CS / "runs/ABL2/A3b/s0/candidates.jsonl", "ABL-V2 A3b seed 0 candidates.jsonl"),
                         ("NC2_A1a_s0_BUILD_RECORD.json", CS / "runs/NC2/A1a/s0/BUILD_RECORD.json", "NC2 A1a seed 0 BUILD_RECORD.json"),
                         ("NC2_A1a_s0_final_policy_policy.md", CS / "runs/NC2/A1a/s0/final/policy/policy.md", "NC2 A1a seed 0 final/policy/policy.md"),
                         ("NC2_A1a_s0_final_tools_tools.py", CS / "runs/NC2/A1a/s0/final/tools/tools.py", "NC2 A1a seed 0 final/tools/tools.py"),
                         ("NC2_A1a_s0_host_counter.json", CS / "runs/NC2/A1a/s0/host/counter.json", "NC2 A1a seed 0 host/counter.json"),
                         ("NC2_A1b_s0_BUILD_RECORD.json", CS / "runs/NC2/A1b/s0/BUILD_RECORD.json", "NC2 A1b seed 0 BUILD_RECORD.json"),
                         ("NC2_A1b_s0_final_policy_policy.md", CS / "runs/NC2/A1b/s0/final/policy/policy.md", "NC2 A1b seed 0 final/policy/policy.md"),
                         ("NC2_A1b_s0_final_tools_tools.py", CS / "runs/NC2/A1b/s0/final/tools/tools.py", "NC2 A1b seed 0 final/tools/tools.py"),
                         ("NC2_A1b_s0_host_counter.json", CS / "runs/NC2/A1b/s0/host/counter.json", "NC2 A1b seed 0 host/counter.json"),
                         ("merged_analysis.py", PAPER / "analysis/scripts/merged_analysis.py", "MERGED window analysis script, written and registered BEFORE the data exist (amendment 12 erratum 49)"),
                         ("k02_analysis.py", PAPER / "analysis/scripts/k02_analysis.py", "K02 exploratory window analysis script, written and registered before the data exist (amendment 12 erratum 56)"),
                         ("merged_holm_m10.json", PAPER / "analysis/out/unblind_20261014/merged/holm_m10.json", "K2 vs ten comparators with Holm recomputed for m = 10 (NC-LOOP removed from the paper's family), from the registered MERGED data (amendment 12 erratum 58)"),
                         ("K02_DESIGN.md", CS / "runs/K02/DESIGN.md", "K02 exploratory run design file by ablation-lead, as present at the search launch (amendment 12 erratum 60)"),
                         ("K02_BUILD_RECORD.json", CS / "runs/K02/BUILD_RECORD.json", "K02 build record"),
                         ("K02_driver.sh", CS / "runs/K02/driver.sh", "K02 driver script"),
                         ("K02_env.sh", CS / "runs/K02/env.sh", "K02 environment"),
                         ("K02_spec_capevolve.yaml", CS / "runs/K02/.capevolve/project/capevolve.yaml", "K02 run spec (gate_k_se 0.2) as launched"),
                         ("K02_optimizer_INSTRUCTIONS.md", CS / "runs/K02/.capevolve/project/optimizer/INSTRUCTIONS.md", "K02 proposer instructions as launched (sha 14cca74c per the design file)"),
                         ("K02_optimizer_FACTS.md", CS / "runs/K02/.capevolve/project/optimizer/FACTS.md", "K02 benchmark-facts block written fresh by ablation-lead"),
                         ("BRIDGE1_order", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "order_BRIDGE1.jsonl", "BRIDGE1 window order (1,000 jobs: NC-1SHOT x 200, GATE-K2-s0 x 200, seed x 400, seed-check x 200; paper repo commit c3b0ed4), registered before launch (amendment 12 erratum 61)"),
                         ("BRIDGE1_artifact_manifest", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "artifacts_BRIDGE1.json", "BRIDGE1 window artifact manifest"),
                         ("BRIDGE1_champions", CS / "final_eval/champions_BRIDGE1.json", "BRIDGE1 window champions file (2 cells)"),
                         ("bridge1_analysis.py", PAPER / "analysis/scripts/bridge1_analysis.py", "BRIDGE1 window analysis script (variant of k02_analysis.py), written and registered BEFORE the data exist (amendment 12 erratum 61)"),
                         ("unblind_analysis.py", PAPER / "analysis/scripts/unblind_analysis.py", "analysis script run once under the erratum 36 unblinding (registered after the first run; see erratum 37)"),
                         ("unblind_results.json", PAPER / "analysis/out/unblind_20261014/unblind_results.json", "machine-readable output of unblind_analysis.py, erratum 37"),
                         ("unblind_SUMMARY.md", PAPER / "analysis/out/unblind_20261014/SUMMARY.md", "summary tables of the unblinded analysis, erratum 37"),
                         ("v2_1_D_no_order.json", PAPER / "experiments/final/manifests/v2_1_D_no_order.json", "manifest note: no v2.1 D window or order (inert champions)"),
                         ("v2_1_E_no_order.json", PAPER / "experiments/final/manifests/v2_1_E_no_order.json", "manifest note: no v2.1 E window or order (inert champions)")):
        if fp.exists():
            items.append(("v2_1_AO2_" + nm, fp, "11E record: " + note, None))
    for nm in ("counts_only.py", "status_report.py"):
        fp = PAPER / "experiments/final" / nm
        if fp.exists():
            items.append(("v2_blind_helper_" + nm, fp, "counts-only helper: reads infra/error count fields by whitelist, never prints reward fields (blind period before the v2 freeze)", None))
    for f in E30_FILES:
        fp = SCRATCH.parent / "E30" / f
        if fp.exists():
            items.append(("suite_E_script_" + f, fp, "Suite E launch/eval script (campaign-scratch/scripts/E30)", None))
    for extra, note in ((SCRATCH.parent.parent / "runs" / "E36_INSTRUCTIONS.nohist.md", "E36 no-history instructions"),
                        (SCRATCH.parent / "E00" / "admission_check.py", "Suite E admission check (every 15 minutes)")):
        if extra.exists():
            items.append(("suite_E_" + extra.name, extra, note, None))
    for f in EXTRA_FILES:
        if (SCRATCH / f).exists():
            items.append(("suite_D_script_" + f, SCRATCH / f, "Suite D launch/eval script (campaign-scratch/scripts/E20)", None))
    for item, path, note, h0 in items:
        h = h0 or sha(path)
        if (item, h) in have:
            continue
        prev = hashlib.sha256(lines[-1].encode()).hexdigest() if lines else None
        d = {"item": item, "sha256": h, "path": (str(path.relative_to(PAPER)) if path and PAPER in Path(path).parents else (str(path) if path else None)), "t_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "script_commit": head, "prev_line_sha256": prev, "note": note}
        lines.append(json.dumps(d, sort_keys=True)); have.add((item, h)); added += 1
    REG.write_text("\n".join(lines) + "\n")
    print(f"registry: {added} line(s) added, {len(lines)} total")


if __name__ == "__main__":
    sys.exit(main())
