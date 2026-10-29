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
    for win in ("A", "B", "C", "D", "E", "V2/E", "V2/D", "V2/A", "V21/D", "V21/A", "V3B1/main", "V3B1/traineval", "V3B1LATE/main", "V3B1CHAIN/main", "V3B1REJ/main", "V4B1S2/main", "ABLW1/main", "ABLW2/main", "MERGED/main", "BRIDGE1/main", "TRAINRS1/main", "K02WIN/main", "K2GATEWIN/main", "K30/main", "R4E1E6/main", "R4MQ/main", "E1X/main"):   # add V2/D and V2/A only after their windows have ended
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
                         ("trainrs1_analysis.py", PAPER / "analysis/scripts/trainrs1_analysis.py", "TRAINRS1 transfer-ratio analysis script, written and registered BEFORE the data exist (amendment 12 addendum 18)"),
                         ("mw_fig_data.py", Path("/home/dev/projects2/mlsys-v2/paper/scripts/figs/mw_fig_data.py"), "paper figure loader holding pooled_ratio(), the estimator behind the paper's 0.28 (ratio of sums of MERGED gains over search re-score gains, 8 comparators); registered as the estimator reference for addendum 18"),
                         ("TRAINRS1_order", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "order_TRAINRS1_traineval.jsonl", "TRAINRS1 window order (4,500 train-30 jobs, no test id; seed k = 10, seed-check k = 5), registered before launch (amendment 12 erratum 62); the earlier 4,800-job build b1a0b84e... is withdrawn by ablation-lead and not used"),
                         ("TRAINRS1_artifact_manifest", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "artifacts_TRAINRS1_traineval.json", "TRAINRS1 window artifact manifest"),
                         ("TRAINRS1_champions", CS / "final_eval/champions_TRAINRS1.json", "TRAINRS1 champions file (8 published x 3 seeds, GATE-K2-search1/2/3)"),
                         ("trainrs1_order.py", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/trainrs1_order.py"), "TRAINRS1 order builder (v3_order.py with three lines changed)"),
                         ("trainrs1_gamma.py", PAPER / "analysis/scripts/trainrs1_gamma.py", "TRAINRS1 transfer-ratio script implementing the estimator of the paper's 0.28, written and registered BEFORE the data exist (amendment 12 erratum 62; supersedes trainrs1_analysis.py)"),
                         ("K02WIN_order", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "order_K02WIN.jsonl", "K02 window order (1,000 test jobs: K02 champion cand_0011 x 200, GATE-K2-search1 x 200, seed x 400, seed-check x 200; agent, user and judge on RITS gpt-oss-120b-a100), registered before launch (amendment 12 erratum 72)"),
                         ("K02WIN_artifact_manifest", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "artifacts_K02WIN.json", "K02 window artifact manifest"),
                         ("K02WIN_champions", CS / "final_eval/champions_K02WIN.json", "K02 window champions file (K02 cand_0011, GATE-K2-search1)"),
                         ("k02win_order.py", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/k02win_order.py"), "K02 window order builder (v3_order.py with the model id line changed)"),
                         ("K02_DESIGN_after_stop.md", CS / "runs/K02/DESIGN.md", "K02 DESIGN.md as amended after the early stop and the route change (the version registered at launch has sha c95f3bcd...)"),
                         ("K02_final_policy.md", CS / "runs/K02/final/policy/policy.md", "K02 champion cand_0011 policy as frozen"),
                         ("K02_final_tools.py", CS / "runs/K02/final/tools/tools.py", "K02 champion cand_0011 tools as frozen"),
                         ("K02R_s1_DESIGN.md", CS / "runs/K02R/K02R-s1/DESIGN.md", "K02R-s1 design file as launched 2026-10-26 09:41 UTC (amendment 12 erratum 74)"),
                         ("K02R_s1_driver.sh", CS / "runs/K02R/K02R-s1/driver.sh", "K02R-s1 driver as launched 2026-10-26 09:41 UTC (amendment 12 erratum 74)"),
                         ("K02R_s1_env.sh", CS / "runs/K02R/K02R-s1/env.sh", "K02R-s1 environment as launched 2026-10-26 09:41 UTC (amendment 12 erratum 74)"),
                         ("K02R_s1_capevolve.yaml", CS / "runs/K02R/K02R-s1/.capevolve/project/capevolve.yaml", "K02R-s1 run spec as launched 2026-10-26 09:41 UTC (amendment 12 erratum 74)"),
                         ("K02R_s2_DESIGN.md", CS / "runs/K02R/K02R-s2/DESIGN.md", "K02R-s2 design file as launched 2026-10-26 09:41 UTC (amendment 12 erratum 74)"),
                         ("K02R_s2_driver.sh", CS / "runs/K02R/K02R-s2/driver.sh", "K02R-s2 driver as launched 2026-10-26 09:41 UTC (amendment 12 erratum 74)"),
                         ("K02R_s2_env.sh", CS / "runs/K02R/K02R-s2/env.sh", "K02R-s2 environment as launched 2026-10-26 09:41 UTC (amendment 12 erratum 74)"),
                         ("K02R_s2_capevolve.yaml", CS / "runs/K02R/K02R-s2/.capevolve/project/capevolve.yaml", "K02R-s2 run spec as launched 2026-10-26 09:41 UTC (amendment 12 erratum 74)"),
                         ("K02R_s3_DESIGN.md", CS / "runs/K02R/K02R-s3/DESIGN.md", "K02R-s3 design file as launched 2026-10-26 09:41 UTC (amendment 12 erratum 74)"),
                         ("K02R_s3_driver.sh", CS / "runs/K02R/K02R-s3/driver.sh", "K02R-s3 driver as launched 2026-10-26 09:41 UTC (amendment 12 erratum 74)"),
                         ("K02R_s3_env.sh", CS / "runs/K02R/K02R-s3/env.sh", "K02R-s3 environment as launched 2026-10-26 09:41 UTC (amendment 12 erratum 74)"),
                         ("K02R_s3_capevolve.yaml", CS / "runs/K02R/K02R-s3/.capevolve/project/capevolve.yaml", "K02R-s3 run spec as launched 2026-10-26 09:41 UTC (amendment 12 erratum 74)"),
                         ("GATE_NAIVE_DESIGN.md", CS / "runs/K02R/GATE-NAIVE/DESIGN.md", "GATE-NAIVE design file as launched 2026-10-26 09:41 UTC (amendment 12 erratum 74)"),
                         ("GATE_NAIVE_driver.sh", CS / "runs/K02R/GATE-NAIVE/driver.sh", "GATE-NAIVE driver as launched 2026-10-26 09:41 UTC (amendment 12 erratum 74)"),
                         ("GATE_NAIVE_env.sh", CS / "runs/K02R/GATE-NAIVE/env.sh", "GATE-NAIVE environment as launched 2026-10-26 09:41 UTC (amendment 12 erratum 74)"),
                         ("GATE_NAIVE_capevolve.yaml", CS / "runs/K02R/GATE-NAIVE/.capevolve/project/capevolve.yaml", "GATE-NAIVE run spec as launched 2026-10-26 09:41 UTC (amendment 12 erratum 74)"),
                         ("GATE_NONE_DESIGN.md", CS / "runs/K02R/GATE-NONE/DESIGN.md", "GATE-NONE design file as launched 2026-10-26 09:41 UTC (amendment 12 erratum 74)"),
                         ("GATE_NONE_driver.sh", CS / "runs/K02R/GATE-NONE/driver.sh", "GATE-NONE driver as launched 2026-10-26 09:41 UTC (amendment 12 erratum 74)"),
                         ("GATE_NONE_env.sh", CS / "runs/K02R/GATE-NONE/env.sh", "GATE-NONE environment as launched 2026-10-26 09:41 UTC (amendment 12 erratum 74)"),
                         ("GATE_NONE_capevolve.yaml", CS / "runs/K02R/GATE-NONE/.capevolve/project/capevolve.yaml", "GATE-NONE run spec as launched 2026-10-26 09:41 UTC (amendment 12 erratum 74)"),
                         ("k02r_analysis.py", PAPER / "analysis/scripts/k02r_analysis.py", "K02R follow-up window analysis script, written and registered BEFORE the data exist (amendment 12 addendum 19 and erratum 74)"),
                         ("gate2_analysis.py", PAPER / "analysis/scripts/gate2_analysis.py", "GATE2 window analysis script (two gate ablations on the K2 configuration), written and registered BEFORE the data exist (amendment 12 addendum 20 and erratum 75)"),
                         ("GATE_NAIVE_K2_DESIGN.md", CS / "runs/K2GATE/GATE-NAIVE-K2/DESIGN.md", "GATE-NAIVE-K2 DESIGN.md before launch (amendment 12 erratum 76)"),
                         ("GATE_NAIVE_K2_env.sh", CS / "runs/K2GATE/GATE-NAIVE-K2/s0/env.sh", "GATE-NAIVE-K2 env.sh before launch (amendment 12 erratum 76)"),
                         ("GATE_NAIVE_K2_capevolve.yaml", CS / "runs/K2GATE/GATE-NAIVE-K2/s0/.capevolve/project/capevolve.yaml", "GATE-NAIVE-K2 capevolve.yaml before launch (amendment 12 erratum 76)"),
                         ("GATE_NAIVE_K2_INSTRUCTIONS.md", CS / "runs/K2GATE/GATE-NAIVE-K2/s0/.capevolve/project/optimizer/INSTRUCTIONS.md", "GATE-NAIVE-K2 INSTRUCTIONS.md before launch (amendment 12 erratum 76)"),
                         ("GATE_NAIVE_K2_BUILD_RECORD.json", CS / "runs/K2GATE/GATE-NAIVE-K2/s0/BUILD_RECORD.json", "GATE-NAIVE-K2 BUILD_RECORD.json before launch (amendment 12 erratum 76)"),
                         ("GATE_NONE_K2_DESIGN.md", CS / "runs/K2GATE/GATE-NONE-K2/DESIGN.md", "GATE-NONE-K2 DESIGN.md before launch (amendment 12 erratum 76)"),
                         ("GATE_NONE_K2_env.sh", CS / "runs/K2GATE/GATE-NONE-K2/s0/env.sh", "GATE-NONE-K2 env.sh before launch (amendment 12 erratum 76)"),
                         ("GATE_NONE_K2_capevolve.yaml", CS / "runs/K2GATE/GATE-NONE-K2/s0/.capevolve/project/capevolve.yaml", "GATE-NONE-K2 capevolve.yaml before launch (amendment 12 erratum 76)"),
                         ("GATE_NONE_K2_INSTRUCTIONS.md", CS / "runs/K2GATE/GATE-NONE-K2/s0/.capevolve/project/optimizer/INSTRUCTIONS.md", "GATE-NONE-K2 INSTRUCTIONS.md before launch (amendment 12 erratum 76)"),
                         ("GATE_NONE_K2_BUILD_RECORD.json", CS / "runs/K2GATE/GATE-NONE-K2/s0/BUILD_RECORD.json", "GATE-NONE-K2 BUILD_RECORD.json before launch (amendment 12 erratum 76)"),
                         ("K2GATE_build_k2gate.py", CS / "scripts/K02/build_k2gate.py", "builder of the two K2-configuration gate-ablation runs"),
                         ("K2GATE_launch_k2gate.sh", CS / "scripts/K02/launch_k2gate.sh", "launcher of the two K2-configuration gate-ablation runs"),
                         ("K2GATE_gate_override.py", Path("/home/dev/projects2/wt-k2gate/core/cap_evolve/gate_override.py"), "gate_override module of the switch commit 329399b13"),
                         ("K2GATE_K2s0_capevolve.yaml_recovered", Path("/tmp/k2g_x/runs/ABL/GATE-K2/s0/.capevolve/project/capevolve.yaml"), "K2 search 1 (ABL GATE-K2 s0) run spec recovered from the data-archive release by ablation-lead; the diff base of the two gate arms"),
                         ("GATE_NAIVE_K2_driver.sh", CS / "runs/K2GATE/GATE-NAIVE-K2/s0/driver.sh", "GATE-NAIVE-K2 driver as launched 2026-10-26 11:07 UTC (amendment 12 erratum 77)"),
                         ("GATE_NONE_K2_driver.sh", CS / "runs/K2GATE/GATE-NONE-K2/s0/driver.sh", "GATE-NONE-K2 driver as launched 2026-10-26 11:07 UTC (amendment 12 erratum 77)"),
                         ("K2GATE_shim_sitecustomize.py", CS / "scripts/K02/k2gate_shim/sitecustomize.py", "transport-only shim lifting tau2 httpx max_connections from 10 to K2GATE_HTTPX_MAX_CONNECTIONS (amendment 12 erratum 78)"),
                         ("K2GATE_tau2_llm_utils.py", CS / "bench/src/tau2-8ebb749/src/tau2/utils/llm_utils.py", "tau2 8ebb749 llm_utils.py holding the httpx_limits cap of 10 (lines 52 to 54) that the shim replaces"),
                         ("GATE_NAIVE_K2_env.sh_shim", CS / "runs/K2GATE/GATE-NAIVE-K2/s0/env.sh", "GATE-NAIVE-K2 env.sh AFTER the transport-shim restart (amendment 12 erratum 79)"),
                         ("GATE_NAIVE_K2_env.sh_pre_shim", CS / "runs/K2GATE/GATE-NAIVE-K2/s0/env.sh.pre_shim", "GATE-NAIVE-K2 env.sh before the shim (the acked version of erratum 76)"),
                         ("GATE_NAIVE_K2_driver.sh_shim", CS / "runs/K2GATE/GATE-NAIVE-K2/s0/driver.sh", "GATE-NAIVE-K2 driver.sh AFTER the transport-shim restart (amendment 12 erratum 79)"),
                         ("GATE_NAIVE_K2_driver.sh_pre_shim", CS / "runs/K2GATE/GATE-NAIVE-K2/s0/driver.sh.pre_shim", "GATE-NAIVE-K2 driver.sh before the shim (the acked version of erratum 76)"),
                         ("GATE_NONE_K2_env.sh_shim", CS / "runs/K2GATE/GATE-NONE-K2/s0/env.sh", "GATE-NONE-K2 env.sh AFTER the transport-shim restart (amendment 12 erratum 79)"),
                         ("GATE_NONE_K2_env.sh_pre_shim", CS / "runs/K2GATE/GATE-NONE-K2/s0/env.sh.pre_shim", "GATE-NONE-K2 env.sh before the shim (the acked version of erratum 76)"),
                         ("GATE_NONE_K2_driver.sh_shim", CS / "runs/K2GATE/GATE-NONE-K2/s0/driver.sh", "GATE-NONE-K2 driver.sh AFTER the transport-shim restart (amendment 12 erratum 79)"),
                         ("GATE_NONE_K2_driver.sh_pre_shim", CS / "runs/K2GATE/GATE-NONE-K2/s0/driver.sh.pre_shim", "GATE-NONE-K2 driver.sh before the shim (the acked version of erratum 76)"),
                         ("GATE_NAIVE_K2A_DESIGN.md", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/DESIGN.md", "GATE-NAIVE-K2A DESIGN.md before launch, aws route (amendment 12 erratum 82)"),
                         ("GATE_NAIVE_K2A_env.sh", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s0/env.sh", "GATE-NAIVE-K2A env.sh before launch, aws route (amendment 12 erratum 82)"),
                         ("GATE_NAIVE_K2A_capevolve.yaml", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s0/.capevolve/project/capevolve.yaml", "GATE-NAIVE-K2A capevolve.yaml before launch, aws route (amendment 12 erratum 82)"),
                         ("GATE_NAIVE_K2A_INSTRUCTIONS.md", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s0/.capevolve/project/optimizer/INSTRUCTIONS.md", "GATE-NAIVE-K2A INSTRUCTIONS.md before launch, aws route (amendment 12 erratum 82)"),
                         ("GATE_NAIVE_K2A_BUILD_RECORD.json", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s0/BUILD_RECORD.json", "GATE-NAIVE-K2A BUILD_RECORD.json before launch, aws route (amendment 12 erratum 82)"),
                         ("GATE_NONE_K2A_DESIGN.md", CS / "runs/K2GATE_AWS/GATE-NONE-K2A/DESIGN.md", "GATE-NONE-K2A DESIGN.md before launch, aws route (amendment 12 erratum 82)"),
                         ("GATE_NONE_K2A_env.sh", CS / "runs/K2GATE_AWS/GATE-NONE-K2A/s0/env.sh", "GATE-NONE-K2A env.sh before launch, aws route (amendment 12 erratum 82)"),
                         ("GATE_NONE_K2A_capevolve.yaml", CS / "runs/K2GATE_AWS/GATE-NONE-K2A/s0/.capevolve/project/capevolve.yaml", "GATE-NONE-K2A capevolve.yaml before launch, aws route (amendment 12 erratum 82)"),
                         ("GATE_NONE_K2A_INSTRUCTIONS.md", CS / "runs/K2GATE_AWS/GATE-NONE-K2A/s0/.capevolve/project/optimizer/INSTRUCTIONS.md", "GATE-NONE-K2A INSTRUCTIONS.md before launch, aws route (amendment 12 erratum 82)"),
                         ("GATE_NONE_K2A_BUILD_RECORD.json", CS / "runs/K2GATE_AWS/GATE-NONE-K2A/s0/BUILD_RECORD.json", "GATE-NONE-K2A BUILD_RECORD.json before launch, aws route (amendment 12 erratum 82)"),
                         ("GATE_NAIVE_K2_ABORTED.txt", CS / "runs/K2GATE/GATE-NAIVE-K2/s0/ABORTED.txt", "GATE-NAIVE-K2 RITS run abort note"),
                         ("GATE_NONE_K2_ABORTED.txt", CS / "runs/K2GATE/GATE-NONE-K2/s0/ABORTED.txt", "GATE-NONE-K2 RITS run abort note"),
                         ("K2GATE_AWS_build_k2gate_aws.py", CS / "scripts/K02/build_k2gate_aws.py", "builder of the two aws-route gate-ablation runs"),
                         ("K2GATE_AWS_launch_k2gate_aws.sh", CS / "scripts/K02/launch_k2gate_aws.sh", "launcher of the two aws-route gate-ablation runs"),
                         ("GATE_NAIVE_K2A_driver.sh", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s0/driver.sh", "GATE-NAIVE-K2A driver as written before launch (amendment 12 erratum 83); the launcher rewrites the same bytes at launch"),
                         ("GATE_NONE_K2A_driver.sh", CS / "runs/K2GATE_AWS/GATE-NONE-K2A/s0/driver.sh", "GATE-NONE-K2A driver as written before launch (amendment 12 erratum 83); the launcher rewrites the same bytes at launch"),
                         ("K2GATEWIN_order", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "order_K2GATEWIN.jsonl", "K2GATEWIN window order (1,200 test jobs: GATE-NAIVE-K2 x 200, GATE-NONE-K2 x 200, GATE-K2-search1 x 200, seed x 400, seed-check x 200; aws route), registered before launch (amendment 12 erratum 86)"),
                         ("K2GATEWIN_artifact_manifest", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "artifacts_K2GATEWIN.json", "K2GATEWIN window artifact manifest"),
                         ("K2GATEWIN_champions", CS / "final_eval/champions_K2GATEWIN.json", "K2GATEWIN window champions file"),
                         ("v3_order.py", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/v3_order.py"), "v3_order.py as used unchanged to build the K2GATEWIN order (first registered by hash here, amendment 12 erratum 86; the TRAINRS1 and K02WIN builders are variants of it)"),
                         ("GATE_NAIVE_K2A_final_policy.md", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s0/final/policy/policy.md", "GATE-NAIVE-K2 champion cand_0016 policy as frozen"),
                         ("GATE_NAIVE_K2A_final_tools.py", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s0/final/tools/tools.py", "GATE-NAIVE-K2 champion cand_0016 tools as frozen"),
                         ("GATE_NONE_K2A_final_policy.md", CS / "runs/K2GATE_AWS/GATE-NONE-K2A/s0/final/policy/policy.md", "GATE-NONE-K2 champion cand_0019 policy as frozen"),
                         ("GATE_NONE_K2A_final_tools.py", CS / "runs/K2GATE_AWS/GATE-NONE-K2A/s0/final/tools/tools.py", "GATE-NONE-K2 champion cand_0019 tools as frozen"),
                         ("k2gate_prewindow.py", CS / "scripts/K02/k2gate_prewindow.py", "pre-window audit script for the K2GATE runs"),
                         ("k30_analysis.py", PAPER / "analysis/scripts/k30_analysis.py", "K30 window analysis script, written and registered BEFORE the data exist (amendment 12 addendum 21 and erratum 90)"),
                         ("posthoc_reanalysis.py", PAPER / "analysis/scripts/posthoc_reanalysis.py", "POST HOC re-analysis script (Holm m = 10 on AppWorld, sign-flip maxT and pooled test on tau2), registered before it is run (amendment 12 addendum 21)"),
                         ("aw_testall_vs_cape.csv", PAPER / "analysis/inputs/aw_testall_vs_cape.csv", "AppWorld one-session TEST_ALL: published CapEvolve-vs-comparator contrasts as transcribed by mlsys-lead (input of the post hoc part C; transcription of issue comments, not per-task data)"),
                         ("aw_testall.csv", PAPER / "analysis/inputs/aw_testall.csv", "AppWorld one-session TEST_ALL per-arm table as transcribed by mlsys-lead"),
                         ("aw_v2_SOURCE.txt", PAPER / "analysis/inputs/aw_v2_SOURCE.txt", "source note of the AppWorld transcriptions"),
                         ("power_analysis_20261027.md", PAPER / "analysis/inputs/power_analysis_20261027.md", "mlsys-lead power analysis (planning document for addendum 21; not a registered analysis)"),
                         ("k30_order.py", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/k30_order.py"), "K30 window order builder: v3_order.py with the trial-seed salt K30 (recorded in meta.seed_salt); seed-check at the cells' trial count (amendment 12 erratum 91)"),
                         ("K30_order", Path("/tmp/k30_final/order_K30.jsonl"), "K30 window order (7,200 test jobs, 12 cells x 600 at 30 trials; aws route; trial-seed salt K30), staged copy hashed before the manifests-directory copy; the copy must have this hash (amendment 12 erratum 92)"),
                         ("K30_artifact_manifest", Path("/tmp/k30_final/artifacts_K30.json"), "K30 window artifact manifest (staged copy)"),
                         ("K30_champions", CS / "final_eval/champions_K30.json", "K30 window champions file"),
                         ("k30_analysis_shiftfix.py", PAPER / "analysis/scripts/k30_analysis.py", "K30 analysis script AFTER the one-line fix of the session-shift key format (amendment 12 erratum 94); the version registered before the data has sha256 b4e3820e... and is superseded for the shift section only"),
                         ("GATE_NAIVE_K2A_s1_env.sh", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s1/env.sh", "GATE-NAIVE-K2A s1 env.sh before launch (amendment 12 erratum 95)"),
                         ("GATE_NAIVE_K2A_s1_capevolve.yaml", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s1/.capevolve/project/capevolve.yaml", "GATE-NAIVE-K2A s1 capevolve.yaml before launch (amendment 12 erratum 95)"),
                         ("GATE_NAIVE_K2A_s1_BUILD_RECORD.json", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s1/BUILD_RECORD.json", "GATE-NAIVE-K2A s1 BUILD_RECORD.json before launch (amendment 12 erratum 95)"),
                         ("GATE_NAIVE_K2A_s3_env.sh", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s3/env.sh", "GATE-NAIVE-K2A s3 env.sh before launch (amendment 12 erratum 95)"),
                         ("GATE_NAIVE_K2A_s3_capevolve.yaml", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s3/.capevolve/project/capevolve.yaml", "GATE-NAIVE-K2A s3 capevolve.yaml before launch (amendment 12 erratum 95)"),
                         ("GATE_NAIVE_K2A_s3_BUILD_RECORD.json", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s3/BUILD_RECORD.json", "GATE-NAIVE-K2A s3 BUILD_RECORD.json before launch (amendment 12 erratum 95)"),
                         ("GATE_NONE_K2A_s1_env.sh", CS / "runs/K2GATE_AWS/GATE-NONE-K2A/s1/env.sh", "GATE-NONE-K2A s1 env.sh before launch (amendment 12 erratum 95)"),
                         ("GATE_NONE_K2A_s1_capevolve.yaml", CS / "runs/K2GATE_AWS/GATE-NONE-K2A/s1/.capevolve/project/capevolve.yaml", "GATE-NONE-K2A s1 capevolve.yaml before launch (amendment 12 erratum 95)"),
                         ("GATE_NONE_K2A_s1_BUILD_RECORD.json", CS / "runs/K2GATE_AWS/GATE-NONE-K2A/s1/BUILD_RECORD.json", "GATE-NONE-K2A s1 BUILD_RECORD.json before launch (amendment 12 erratum 95)"),
                         ("GATE_NONE_K2A_s3_env.sh", CS / "runs/K2GATE_AWS/GATE-NONE-K2A/s3/env.sh", "GATE-NONE-K2A s3 env.sh before launch (amendment 12 erratum 95)"),
                         ("GATE_NONE_K2A_s3_capevolve.yaml", CS / "runs/K2GATE_AWS/GATE-NONE-K2A/s3/.capevolve/project/capevolve.yaml", "GATE-NONE-K2A s3 capevolve.yaml before launch (amendment 12 erratum 95)"),
                         ("GATE_NONE_K2A_s3_BUILD_RECORD.json", CS / "runs/K2GATE_AWS/GATE-NONE-K2A/s3/BUILD_RECORD.json", "GATE-NONE-K2A s3 BUILD_RECORD.json before launch (amendment 12 erratum 95)"),
                         ("gate_seeds_diffs_20261028.txt", PAPER / "analysis/inputs/gate_seeds_diffs_20261028.txt", "gate-seeds-runner diff listing of the four new gate-ablation search directories against s0 and the K2 reference"),
                         ("gate6_analysis.py", PAPER / "analysis/scripts/gate6_analysis.py", "GATE6 window analysis script (three searches per gate arm against three noise-aware-gate searches), written and registered BEFORE the searches finish and before any data exist (amendment 12 addendum 22 and erratum 95)"),
                         ("GATE_NAIVE_K2A_s1_driver.sh", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s1/driver.sh", "GATE-NAIVE-K2A s1 driver as launched 2026-10-28 12:05 UTC (amendment 12 erratum 96)"),
                         ("GATE_NAIVE_K2A_s3_driver.sh", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s3/driver.sh", "GATE-NAIVE-K2A s3 driver as launched 2026-10-28 12:05 UTC (amendment 12 erratum 96)"),
                         ("GATE_NONE_K2A_s1_driver.sh", CS / "runs/K2GATE_AWS/GATE-NONE-K2A/s1/driver.sh", "GATE-NONE-K2A s1 driver as launched 2026-10-28 12:05 UTC (amendment 12 erratum 96)"),
                         ("GATE_NONE_K2A_s3_driver.sh", CS / "runs/K2GATE_AWS/GATE-NONE-K2A/s3/driver.sh", "GATE-NONE-K2A s3 driver as launched 2026-10-28 12:05 UTC (amendment 12 erratum 96)"),
                         ("GATE_NAIVE_K2A_s1_driver_24w.sh", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s1/driver.sh", "GATE-NAIVE-K2A s1 driver as restarted at 24 workers 2026-10-28 12:07 UTC (amendment 12 erratum 98)"),
                         ("GATE_NAIVE_K2A_s3_driver_24w.sh", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s3/driver.sh", "GATE-NAIVE-K2A s3 driver as restarted at 24 workers 2026-10-28 12:07 UTC (amendment 12 erratum 98)"),
                         ("GATE_NONE_K2A_s1_driver_24w.sh", CS / "runs/K2GATE_AWS/GATE-NONE-K2A/s1/driver.sh", "GATE-NONE-K2A s1 driver as restarted at 24 workers 2026-10-28 12:07 UTC (amendment 12 erratum 98)"),
                         ("GATE_NONE_K2A_s3_driver_24w.sh", CS / "runs/K2GATE_AWS/GATE-NONE-K2A/s3/driver.sh", "GATE-NONE-K2A s3 driver as restarted at 24 workers 2026-10-28 12:07 UTC (amendment 12 erratum 98)"),
                         ("gate6n_analysis.py", PAPER / "analysis/scripts/gate6n_analysis.py", "GATE6N analysis script (NAIVE vs the noise-aware gate; NONE dropped), written and registered before any data (amendment 12 erratum 99)"),
                         ("r4_generic_analysis.py", PAPER / "analysis/scripts/r4_generic_analysis.py", "R4 generic window analysis driven by a registered DESIGN.json, written and registered BEFORE any R4 data (amendment 12 addendum 23)"),
                         ("design_R4WIN.json", PAPER / "analysis/inputs/design_R4WIN.json", "R4WIN design: groups and contrasts fixed before the searches finish (addendum 23)"),
                         ("design_R4E1E6_schema.json", PAPER / "analysis/inputs/design_R4E1E6_schema.json", "R4 E1/E6 design schema (primary and secondaries fixed; generated groups registered later)"),
                         ("design_R4E4_schema.json", PAPER / "analysis/inputs/design_R4E4_schema.json", "R4 E4 cross-model design schema"),
                         ("r4_experiments_20261028.md", PAPER / "analysis/inputs/r4_experiments_20261028.md", "experiment-designer-r4 design document of the overnight experiments (planning input; the registered text is addendum 23)"),
                         ("A2b_s2_env.sh", CS / "runs/ABL2/A2b/s2/env.sh", "A2b s2 env.sh before launch (amendment 12 erratum 103)"),
                         ("A2b_s2_capevolve.yaml", CS / "runs/ABL2/A2b/s2/.capevolve/project/capevolve.yaml", "A2b s2 capevolve.yaml before launch (amendment 12 erratum 103)"),
                         ("A2b_s2_BUILD_RECORD.json", CS / "runs/ABL2/A2b/s2/BUILD_RECORD.json", "A2b s2 BUILD_RECORD.json before launch (amendment 12 erratum 103)"),
                         ("A2b_s2_INSTRUCTIONS.md", CS / "runs/ABL2/A2b/s2/.capevolve/project/optimizer/INSTRUCTIONS.md", "A2b s2 INSTRUCTIONS.md before launch (amendment 12 erratum 103)"),
                         ("A2b_s3_env.sh", CS / "runs/ABL2/A2b/s3/env.sh", "A2b s3 env.sh before launch (amendment 12 erratum 103)"),
                         ("A2b_s3_capevolve.yaml", CS / "runs/ABL2/A2b/s3/.capevolve/project/capevolve.yaml", "A2b s3 capevolve.yaml before launch (amendment 12 erratum 103)"),
                         ("A2b_s3_BUILD_RECORD.json", CS / "runs/ABL2/A2b/s3/BUILD_RECORD.json", "A2b s3 BUILD_RECORD.json before launch (amendment 12 erratum 103)"),
                         ("A2b_s3_INSTRUCTIONS.md", CS / "runs/ABL2/A2b/s3/.capevolve/project/optimizer/INSTRUCTIONS.md", "A2b s3 INSTRUCTIONS.md before launch (amendment 12 erratum 103)"),
                         ("E3B_K165_s0_env.sh", CS / "runs/E3B/GATE-K1.65/s0/env.sh", "E3B_K165 s0 env.sh before launch (amendment 12 erratum 103)"),
                         ("E3B_K165_s0_capevolve.yaml", CS / "runs/E3B/GATE-K1.65/s0/.capevolve/project/capevolve.yaml", "E3B_K165 s0 capevolve.yaml before launch (amendment 12 erratum 103)"),
                         ("E3B_K165_s0_BUILD_RECORD.json", CS / "runs/E3B/GATE-K1.65/s0/BUILD_RECORD.json", "E3B_K165 s0 BUILD_RECORD.json before launch (amendment 12 erratum 103)"),
                         ("E3B_K165_s0_INSTRUCTIONS.md", CS / "runs/E3B/GATE-K1.65/s0/.capevolve/project/optimizer/INSTRUCTIONS.md", "E3B_K165 s0 INSTRUCTIONS.md before launch (amendment 12 erratum 103)"),
                         ("E3B_K165_s1_env.sh", CS / "runs/E3B/GATE-K1.65/s1/env.sh", "E3B_K165 s1 env.sh before launch (amendment 12 erratum 103)"),
                         ("E3B_K165_s1_capevolve.yaml", CS / "runs/E3B/GATE-K1.65/s1/.capevolve/project/capevolve.yaml", "E3B_K165 s1 capevolve.yaml before launch (amendment 12 erratum 103)"),
                         ("E3B_K165_s1_BUILD_RECORD.json", CS / "runs/E3B/GATE-K1.65/s1/BUILD_RECORD.json", "E3B_K165 s1 BUILD_RECORD.json before launch (amendment 12 erratum 103)"),
                         ("E3B_K165_s1_INSTRUCTIONS.md", CS / "runs/E3B/GATE-K1.65/s1/.capevolve/project/optimizer/INSTRUCTIONS.md", "E3B_K165 s1 INSTRUCTIONS.md before launch (amendment 12 erratum 103)"),
                         ("E3B_K165_s2_env.sh", CS / "runs/E3B/GATE-K1.65/s2/env.sh", "E3B_K165 s2 env.sh before launch (amendment 12 erratum 103)"),
                         ("E3B_K165_s2_capevolve.yaml", CS / "runs/E3B/GATE-K1.65/s2/.capevolve/project/capevolve.yaml", "E3B_K165 s2 capevolve.yaml before launch (amendment 12 erratum 103)"),
                         ("E3B_K165_s2_BUILD_RECORD.json", CS / "runs/E3B/GATE-K1.65/s2/BUILD_RECORD.json", "E3B_K165 s2 BUILD_RECORD.json before launch (amendment 12 erratum 103)"),
                         ("E3B_K165_s2_INSTRUCTIONS.md", CS / "runs/E3B/GATE-K1.65/s2/.capevolve/project/optimizer/INSTRUCTIONS.md", "E3B_K165 s2 INSTRUCTIONS.md before launch (amendment 12 erratum 103)"),
                         ("K2_INSTRUCTIONS_ref.md", CS / "scripts/ABL2/ref/K2_INSTRUCTIONS.md", "K2 s0 proposer instructions recovered from the data-archive release (sha 42761766)"),
                         ("build_e3b.py", CS / "scripts/E3B/build_e3b.py", "builder of the three k=1.65 gate searches"),
                         ("build_abl2_after_ref_edit.py", CS / "scripts/ABL2/build_abl2.py", "ABL-V2 builder AFTER the two edits that read K2 instructions and BUILD_RECORD from scripts/ABL2/ref/ (amendment 12 erratum 103); the version registered in addendum 11 has sha 316601f1"),
                         ("e2e3_launch_diffs_20261028.txt", PAPER / "analysis/inputs/e2e3_launch_diffs_20261028.txt", "experiment-designer-r4 diff listing for the E2/E3b launch package"),
                         ("A2b_s2_driver.sh", CS / "runs/ABL2/A2b/s2/driver.sh", "A2b_s2 driver as launched 2026-10-28 23:45 UTC (amendment 12 erratum 104)"),
                         ("A2b_s3_driver.sh", CS / "runs/ABL2/A2b/s3/driver.sh", "A2b_s3 driver as launched 2026-10-28 23:45 UTC (amendment 12 erratum 104)"),
                         ("E3B_K165_s0_driver.sh", CS / "runs/E3B/GATE-K1.65/s0/driver.sh", "E3B_K165_s0 driver as launched 2026-10-28 23:45 UTC (amendment 12 erratum 104)"),
                         ("e1_K2_s0_events.jsonl", CS / "e1_cands/runs/ABL/GATE-K2/s0/.capevolve/run_main/events.jsonl", "K2 search s0 candidate events recovered from the archived tarball (input of E1/E3a/E6; amendment 12 erratum 104)"),
                         ("e1_K2_s1_events.jsonl", CS / "e1_cands/runs/ABL/GATE-K2/s1/.capevolve/run_main/events.jsonl", "K2 search s1 candidate events recovered from the archived tarball (input of E1/E3a/E6; amendment 12 erratum 104)"),
                         ("e1_K2_s3_events.jsonl", CS / "e1_cands/runs/ABL/GATE-K2/s3/.capevolve/run_main/events.jsonl", "K2 search s3 candidate events recovered from the archived tarball (input of E1/E3a/E6; amendment 12 erratum 104)"),
                         ("r4_order.py", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/r4_order.py"), "R4 window order builder: v3_order.py with the per-window trial-seed salt R4W or R4E (--seed-salt required) and meta.cell_map (amendment 12 erratum 107)"),
                         ("design_R4E4.json", PAPER / "analysis/inputs/design_R4E4.json", "E4 cross-model design: groups and contrasts fixed before any smoke or order (addendum 24)"),
                         ("e4_smoke_as_received.py", CS / "scripts/R4/e4_smoke.py", "E4 smoke script as received 2026-10-28 23:59 UTC (to be replaced by the version with the Qwen marker and empty-turn rule of addendum 24, registered before it runs)"),
                         ("e1_incumbents_as_received.py", CS / "scripts/R4/e1_incumbents.py", "E1 incumbent script as received 2026-10-28 23:59 UTC; it may not be run before the reviewer has read it"),
                         ("mw_k2_search_20261029.csv", PAPER / "analysis/inputs/mw_k2_search_20261029.csv", "paper-side search-cost table of K2 searches 1-3 (list optimizer, list agent+user, metered USD); the list-price basis of the paper's cost comparisons, input of the E1 cost-matched incumbent (amendment 12 erratum 108)"),
                         ("DESIGN_R4E1E6_generated_v1.json", CS / "final_eval/DESIGN_R4E1E6.json", "E1/E6 design generated at 2026-10-28 23:48 UTC by the incumbent script BEFORE the reviewer read it; superseded after the cost-basis amendment and the end of NAIVE s1 (amendment 12 erratum 108)"),
                         ("champions_R4E1E6_generated_v1.json", CS / "final_eval/champions_R4E1E6.json", "E1/E6 champions file generated at the same time (35 staged trees, 30 unique); superseded as above"),
                         ("e4_smoke_v1_5cd6c3fe.py", CS / "scripts/R4/e4_smoke_v1_5cd6c3fe.py", "E4 smoke script v1 (unamended; its run was killed, no result)"),
                         ("e4_smoke_amended_0cf91c0d.py", CS / "scripts/R4/e4_smoke_amended.py", "E4 smoke script variant by cross-model-runner (batch-time estimate); NOT the one acked (amendment 12 erratum 109)"),
                         ("e4_smoke_acked.py", CS / "scripts/R4/e4_smoke.py", "E4 smoke script acked by the reviewer: per-rollout wall time, empty-turn and format counts, arguments for model, gateway and thinking (amendment 12 erratum 109)"),
                         ("e4_adapter_variant.py", CS / "scripts/R4/adapters_e4/adapter.py", "E4 adapter: V3 airline adapter 9c797d8a plus five lines routing only the agent role to TAU_AGENT_GATEWAY with TAU_AGENT_EXTRA_BODY (amendment 12 erratum 109)"),
                         ("e4_smoke_env.sh", CS / "runs/E4_SMOKE/env.sh", "E4 smoke environment (agent on :4114 with thinking off; user and judge on :4113 aws gpt-oss)"),
                         ("r4m_order_draft.py", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final") / "r4m_order.py", "E4 order builder draft (salt R4M, per-job agent gateway and extra_body, meta.e4); registered as a draft, to be acked after a dry run (amendment 12 erratum 109)"),
                         ("mw_k2_search_repriced_20261029.csv", PAPER / "analysis/inputs/mw_k2_search_repriced_20261029.csv", "paper-side search-cost table AFTER the re-pricing of 2026-10-26 (Sonnet 5.5 at 1.52/7.60 per Mtok, gpt-oss 0.15/0.60): K2 list optimizer 63.94, 48.71, 59.65; the basis of the paper's current costs and of SkillOpt's 68.01 (amendment 12 erratum 110)"),
                         ("k2_cost_s0_repriced_20261029.json", PAPER / "analysis/inputs/k2_cost_s0_repriced_20261029.json", "K2 s0 token counts and re-priced cost (amendment 12 erratum 110)"),
                         ("e1_incumbents_v2_as_received.py", CS / "scripts/R4/e1_incumbents.py", "E1/E6 incumbent script v2 (list basis) as received; reads the older cost table and is SUPERSEDED by erratum 110"),
                         ("e1_incumbents_v4.py", CS / "scripts/R4/e1_incumbents.py", "E1/E6 incumbent script v4: current repriced cost table with hash assert, CE68reg and CE68old sensitivities, neighbours printed (amendment 12 erratum 112)"),
                         ("holm_m9.json", PAPER / "analysis/out/unblind_20261014/merged/holm_m9.json", "K2 vs nine comparators with Holm recomputed for m = 9 (HarnessLens removed from the paper's family), from the registered MERGED raw p (amendment 12 erratum 112)"),
                         ("e4_smoke_acked_run_start.txt", CS / "runs/E4_SMOKE/smoke_acked_start.txt", "start time of the E4 smoke from the acked script 0cf91c0d (2026-10-29 00:09:46 UTC)"),
                         ("e4_smoke_withdrawn_run_log.err", CS / "runs/E4_SMOKE/smoke_qwen_withdrawn_e6099429.err", "log of the e6099429 smoke run stopped after about 30 seconds, no result"),
                         ("posthoc_reanalysis9.py", PAPER / "analysis/scripts/posthoc_reanalysis9.py", "POST HOC re-analysis, nine-comparator version (HarnessLens dropped), registered BEFORE it is run (amendment 12 erratum 113)"),
                         ("K165_s2_driver.sh", CS / "runs/E3B/GATE-K1.65/s2/driver.sh", "K165-s2 driver as launched 2026-10-29 00:10:12 UTC (amendment 12 erratum 114)"),
                         ("K165_s1_driver.sh", CS / "runs/E3B/GATE-K1.65/s1/driver.sh", "K165-s1 driver as launched 2026-10-29 00:00:09 UTC (amendment 12 erratum 114)"),
                         ("e5a_analysis.py", PAPER / "analysis/scripts/e5a_analysis.py", "E5a AppWorld test_challenge analysis script, written and registered BEFORE any episode (amendment 12 addendum 25)"),
                         ("e5a_arm_manifest.json", PAPER / "analysis/inputs/e5a_arm_manifest.json", "E5a frozen artifacts: rule S or F hash of each of 11 arms and the sha256 of every file (reviewer's recomputation, equal to the runner's)"),
                         ("appworld_test_challenge_ids.txt", PAPER / "analysis/inputs/appworld_test_challenge_ids.txt", "AppWorld test_challenge task ids (417 tasks, 139 scenarios of 3), copy of the data root file"),
                         ("e5a_run_window.py", CS / "e5a/scripts/run_window.py", "E5a window runner (one episode per subprocess; records per cell; infra retried 3 times)"),
                         ("e5a_aw_agent.py", CS / "e5a/harness/examples/appworld/adapters/aw_agent.py", "E5a agent (SimplifiedReAct, gpt-oss-120b, 50 steps) of the test-all branch, stated unchanged by the runner"),
                         ("e5a_hash_arms.py", CS / "e5a/hash_arms.py", "E5a artifact hashing rules S (surface hash of 4 files) and F (full tree)"),
                         ("r4_e5a_notes.md", Path("/tmp/review_story/r4_e5a.md"), "E5a notes by aw-e5a-runner"),
                         ("aw_gatearms_20261029.csv", PAPER / "analysis/inputs/aw_gatearms_20261029.csv", "AppWorld naive-gate ablation vs the k = 0.2 reference as transcribed by mlsys-lead (amendment 12 erratum 115)"),
                         ("aw_gatearms_PROVENANCE_20261029.txt", PAPER / "analysis/inputs/aw_gatearms_PROVENANCE_20261029.txt", "provenance note of that transcription"),
                         ("GATE_NONE_K2A_s1_final_events.jsonl", CS / "runs/K2GATE_AWS/GATE-NONE-K2A/s1/.capevolve/run_main/events.jsonl", "NONE s1 events at its end (dropped arm; kept on record, amendment 12 erratum 115)"),
                         ("GATE_NONE_K2A_s3_final_events.jsonl", CS / "runs/K2GATE_AWS/GATE-NONE-K2A/s3/.capevolve/run_main/events.jsonl", "NONE s3 events at its end (dropped arm)"),
                         ("DESIGN_R4E1E6_v2.json", CS / "final_eval/DESIGN_R4E1E6_v2.json", "E1/E6 generated design (groups CE68, CE68reg, CE68old, CE1000/1500/2000, CEfinal, SkillOpt; 30 chain links), generated 2026-10-29 02:07 UTC by the acked script v4 after NAIVE s1 ended (amendment 12 erratum 116)"),
                         ("champions_R4E1E6_v2.json", CS / "final_eval/champions_R4E1E6_v2.json", "E1/E6 champions file: 35 staged trees, 30 unique (amendment 12 erratum 116)"),
                         ("GATE_NAIVE_K2A_s1_final_events.jsonl", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s1/.capevolve/run_main/events.jsonl", "NAIVE s1 events at its end (19 scored, champion cand_0013)"),
                         ("GATE_NAIVE_K2A_s1_candidates.jsonl", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s1/candidates.jsonl", "NAIVE s1 candidates log"),
                         ("GATE_NAIVE_K2A_s0_candidates.jsonl", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s0/candidates.jsonl", "NAIVE s0 candidates log"),
                         ("GATE_NAIVE_K2A_s3_candidates.jsonl", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s3/candidates.jsonl", "NAIVE s3 candidates log"),
                         ("GATE_NAIVE_K2A_s0_final_events.jsonl", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s0/.capevolve/run_main/events.jsonl", "NAIVE s0 events at its end"),
                         ("GATE_NAIVE_K2A_s3_final_events.jsonl", CS / "runs/K2GATE_AWS/GATE-NAIVE-K2A/s3/.capevolve/run_main/events.jsonl", "NAIVE s3 events at its end"),
                         ("design_R4E1E6.json", PAPER / "analysis/inputs/design_R4E1E6.json", "E1/E6 analysis DESIGN.json generated from the registered v2 design (groups, 5 secondaries, 5 sensitivities, 30 chains), BEFORE the order is built (amendment 12 erratum 117)"),
                         ("champions_R4E1E6_v2_unique.json", CS / "final_eval/champions_R4E1E6_v2_unique.json", "E1/E6 champions file, one cell per unique tree (30 cells); the three SkillOpt champions are NOT in it and are added by the order (amendment 12 erratum 118)"),
                         ("cellmap_R4E1E6_v2.json", CS / "final_eval/cellmap_R4E1E6_v2.json", "E1/E6 cell map: every staged label to the canonical cell scored for its tree (35 entries, five duplicate pairs) (amendment 12 erratum 118)"),
                         ("R4E1E6_order", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "order_R4E1E6.jsonl", "R4E1E6 window order (14,000 test jobs, 35 cells x 400 at 20 trials; salt R4E; aws route), registered before launch (amendment 12 erratum 119)"),
                         ("R4E1E6_artifact_manifest", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "artifacts_R4E1E6.json", "R4E1E6 window artifact manifest"),
                         ("R4E1E6_champions", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "champions_R4E1E6.json", "R4E1E6 window champions file (build version)"),
                         ("R4E1E6_cellmap", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "cellmap_R4E1E6.json", "R4E1E6 cell map (35 labels to 30 cells; five duplicate pairs named by the E6 label)"),
                         ("expand_r4e1e6.py", PAPER / "analysis/scripts/expand_r4e1e6.py", "R4E1E6 results expansion by the order cell map and three aliases, written and registered BEFORE the window ends (amendment 12 erratum 122)"),
                         ("e5a_run_window_root020.py", CS / "e5a/scripts/run_window.py", "E5a window runner AFTER the one-line ROOT change to root_020 (AppWorld data 0.2.0); the old file (sha 335f48ff, ROOT aw_snapshot/root) is reproduced by reversing that line (amendment 12 erratum 124)"),
                         ("e5a_venv_freeze.txt", CS / "e5a/venv_freeze.txt", "pip freeze of venv-e5a (fastapi 0.119.1, starlette 0.48-0.49; amendment 12 erratum 124)"),
                         ("e5a_root020_tree.sha256", CS / "e5a/root_020_tree.sha256", "tree hash of root_020 as computed by aw-e5a-runner (rule not stated by the sender)"),
                         ("e5a_env.sh", CS / "e5a/env.sh", "E5a environment script"),
                         ("e5a_smoke_tasks.txt", CS / "e5a/smoke/tasks.txt", "E5a smoke task ids (train)"),
                         ("e5a_smoke_order.sha256", CS / "e5a/smoke/state/order.sha256", "E5a smoke order hash"),
                         ("e5a_root020_data_manifest.json", PAPER / "analysis/inputs/e5a_root020_data_manifest.json", "sha256 of every file of root_020 data/datasets and data/tasks (14,861 files), computed by the reviewer (amendment 12 erratum 124)"),
                         ("e5a_prelaunch.sh", CS / "e5a/scripts/prelaunch.sh", "E5a launch-time re-hash script (arms, harness files, data root, order sha), amendment 12 erratum 125"),
                         ("e4_smoke_acked_result.json", CS / "runs/E4_SMOKE/smoke_qwen_acked.json", "E4 smoke result from the acked script 0cf91c0d, run once: Qwen3.6-35B-A3B, thinking off (amendment 12 erratum 126)"),
                         ("e4_smoke_acked_result.err", CS / "runs/E4_SMOKE/smoke_qwen_acked.err", "E4 smoke stderr"),
                         ("appworld_data_CHANGELOG_020.md", PAPER / "analysis/inputs/appworld_data_CHANGELOG_020.md", "AppWorld data changelog as shipped in data 0.2.0 (amendment 12 erratum 127)"),
                         ("e5a_prelaunch_out.txt", CS / "e5a/prelaunch_out.txt", "E5a launch-time re-hash output of aw-e5a-runner (arms, harness files, data tree hash, order sha)"),
                         ("e5a_root020_basedbs_apidocs_manifest.json", PAPER / "analysis/inputs/e5a_root020_basedbs_apidocs_manifest.json", "sha256 of every file of root_020 data/base_dbs (13 files) and data/api_docs (55 files), computed by the reviewer after the E5a launch (amendment 12 erratum 128)"),
                         ("e5a_notes_v2.md", Path("/tmp/review_story/r4_e5a.md"), "aw-e5a-runner notes after the data comparison"),
                         ("R4MQ_order", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "order_R4MQ.jsonl", "E4 cross-model window order (3,600 test jobs; agent Qwen3.6-35B-A3B thinking off on :4114; user and judge aws gpt-oss; salt R4M), registered before launch (amendment 12 erratum 129)"),
                         ("R4MQ_artifact_manifest", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests") / "artifacts_R4MQ.json", "E4 window artifact manifest"),
                         ("R4MQ_champions", CS / "final_eval/champions_R4M.json", "E4 window champions file"),
                         ("design_R4WIN_v2.json", PAPER / "analysis/inputs/design_R4WIN_v2.json", "R4WIN design v2: the registered gate and ablation family unchanged (amendment 12 addendum 26)"),
                         ("design_R4WIN_CC.json", PAPER / "analysis/inputs/design_R4WIN_CC.json", "R4WIN Claude Code contrast: K2 three searches against V2-A1a three searches, own family m = 1, fixed before the A1a searches exist (amendment 12 addendum 26)"),
                         ("NC2_A1a_s1_STOPPED.txt", CS / "runs/NC2/A1a/s1/STOPPED.txt", "A1a seed-1 run stopped by addendum 14, 'do not score or use' (kept on record; amendment 12 addendum 26)"),
                         ("NC2_A1a_s0_session_1.json", CS / "runs/NC2/A1a/s0/session_1.json", "A1a s0 Claude Code session record (154 turns, USD 18.39, ended by itself)"),
                         ("NC2_A1a_s0_driver.log", CS / "runs/NC2/A1a/s0/driver.log", "A1a s0 driver log"),
                         ("NC2_A1a_s0_task_prompt.txt", CS / "runs/NC2/A1a/s0/task_prompt.txt", "A1a s0 prompt (221 bytes, sha f3b4d28a)"),
                         ("nc2_build_s23_proposed.py", CS / "scripts/NC2/nc2_build_s23_proposed.py", "nc2_build.py variant for A1a seeds 2 and 3: seed choices 0 to 3 and the K2 inputs read from scripts/NC2/ref_k2 (reviewer's two-line variant; amendment 12 erratum 133)"),
                         ("nc2_build_new_token_only.py", Path("/tmp/nc2_build_new.py"), "ablation-lead's staged one-token variant of nc2_build.py (seed choices only); fails because the K2 project directory is gone (amendment 12 erratum 133)"),
                         ("nc2_ref_k2_manifest.json", PAPER / "analysis/inputs/nc2_ref_k2_manifest.json", "sha256 of every file of scripts/NC2/ref_k2 (161 files): K2 s0 project inputs from the recovered extract and cand_0001 seed trajectories and instructions from the archived tarball (amendment 12 erratum 133)"),
                         ("e5a_analysis_v2.py", PAPER / "analysis/scripts/e5a_analysis.py", "E5a analysis v2: adds the PAIRWISE-COMPLETE mode for an incomplete window; written and registered BEFORE any E5a outcome was read (amendment 12 erratum 134); the v1 registered earlier has sha 8c2683cb"),
                         ("R4MQ_run_log_0453.txt", CS / "final_eval/R4MQ/run.log", "R4MQ runner log at 04:53 UTC (progress record)"),
                         ("NC2_A1a_s2_BUILD_RECORD.json", CS / "runs/NC2/A1a/s2/BUILD_RECORD.json", "A1a s2 BUILD_RECORD.json before launch (amendment 12 erratum 135)"),
                         ("NC2_A1a_s2_env.sh", CS / "runs/NC2/A1a/s2/env.sh", "A1a s2 env.sh before launch (amendment 12 erratum 135)"),
                         ("NC2_A1a_s2_task_prompt.txt", CS / "runs/NC2/A1a/s2/task_prompt.txt", "A1a s2 task_prompt.txt before launch (amendment 12 erratum 135)"),
                         ("NC2_A1a_s2_train_ids.json", CS / "runs/NC2/A1a/s2/train_ids.json", "A1a s2 train_ids.json before launch (amendment 12 erratum 135)"),
                         ("NC2_A1a_s3_BUILD_RECORD.json", CS / "runs/NC2/A1a/s3/BUILD_RECORD.json", "A1a s3 BUILD_RECORD.json before launch (amendment 12 erratum 135)"),
                         ("NC2_A1a_s3_env.sh", CS / "runs/NC2/A1a/s3/env.sh", "A1a s3 env.sh before launch (amendment 12 erratum 135)"),
                         ("NC2_A1a_s3_task_prompt.txt", CS / "runs/NC2/A1a/s3/task_prompt.txt", "A1a s3 task_prompt.txt before launch (amendment 12 erratum 135)"),
                         ("NC2_A1a_s3_train_ids.json", CS / "runs/NC2/A1a/s3/train_ids.json", "A1a s3 train_ids.json before launch (amendment 12 erratum 135)"),
                         ("e5a_order_reordered_tier1_first.json", PAPER / "analysis/inputs/e5a_order_reordered_tier1_first.json", "E5a reordered cell sequence: Tier 1 (trial 0 of seed, cape_k02, trace2skill, gepa_full, skillopt), then ace and gepa trial 0, then trial 1 of all seven arms; a permutation of the registered 5,838 cells with idx and fields preserved (amendment 12 erratum 136)"),
                         ("e5a_run_window_reordered.py", CS / "e5a/scripts/run_window_reordered.py", "E5a runner variant: reads the cell sequence from the registered reordered file and refuses to run if its sha256 differs; order.json is not rewritten (amendment 12 erratum 137)"),
                         ("e5a_switch_reordered.sh", CS / "e5a/scripts/switch_reordered.sh", "E5a switch script: SIGTERM the running runner, wait for the exit, start the variant (amendment 12 erratum 137); not run before the ack"),
                         ("e5a_order_registered_copy.json", CS / "e5a/window/state/order_registered.json", "copy of the registered E5a order.json (sha rule 0dc3d27e), made before the switch (amendment 12 erratum 137)"),
                         ("e5a_order_registered_copy.sha256", CS / "e5a/window/state/order_registered.sha256", "copy of the registered E5a order.sha256"),
                         ("NC2_A1a_s2_session_start.txt", CS / "runs/NC2/A1a/s2/session_start.txt", "A1a s2 session start (2026-10-29 04:56:56 UTC)"),
                         ("NC2_A1a_s3_session_start.txt", CS / "runs/NC2/A1a/s3/session_start.txt", "A1a s3 session start (2026-10-29 04:57:00 UTC)"),
                         ("e5a_order_reordered_inflight_last.json", PAPER / "analysis/inputs/e5a_order_reordered_inflight_last.json", "E5a reordered sequence with the single cell in flight at the drain (idx 314) moved to the end; otherwise identical to the acked reordered file (amendment 12 erratum 138)"),
                         ("e5a_run_reordered_log_0647.txt", CS / "e5a/window/run_reordered.log", "E5a reordered runner log (start 2026-10-29 06:46:24 UTC; amendment 12 erratum 140)"),
                         ("e5a_switch_log.txt", CS / "e5a/window/switch.log", "E5a switch log (SIGTERM 05:04:08 UTC)"),
                         ("design_R4E1E6_curve.json", PAPER / "analysis/inputs/design_R4E1E6_curve.json", "E1 budget-curve design file written AFTER the registered primary was read (amendment 12 erratum 141): each curve point and SkillOpt against the seed, descriptive"),
                         ("r4e1e6_r4.md", PAPER / "analysis/out/unblind_20261014/r4e1e6/r4.md", "R4E1E6 registered analysis output (primary, secondary, sensitivity, 30 chain links)"),
                         ("r4e1e6_r4.json", PAPER / "analysis/out/unblind_20261014/r4e1e6/r4.json", "R4E1E6 registered analysis output, json"),
                         ("r4e1e6_curve_r4.md", PAPER / "analysis/out/unblind_20261014/r4e1e6_curve/r4.md", "R4E1E6 budget-curve output (added after the primary)"),
                         ("r4e1e6_expanded_results_long.csv", PAPER / "analysis/out/unblind_20261014/r4e1e6_expanded/results_long.csv", "R4E1E6 results expanded by the registered cell map and aliases (no value changed)"),
                         ("r4e1e6_expanded_results_trials.csv", PAPER / "analysis/out/unblind_20261014/r4e1e6_expanded/results_trials.csv", "R4E1E6 trials expanded by the registered cell map and aliases"),
                         ("rr_primary_protocol_md", Path("/tmp/rr/paper/research_revision/primary_protocol.md"), "research revision output of 2026-10-29 (erratum/addendum 27 series)"),
                         ("rr_analysis_registry_csv", Path("/tmp/rr/paper/research_revision/analysis_registry.csv"), "research revision output of 2026-10-29 (erratum/addendum 27 series)"),
                         ("rr_issue_resolution_stats_csv", Path("/tmp/rr/paper/research_revision/issue_resolution_stats.csv"), "research revision output of 2026-10-29 (erratum/addendum 27 series)"),
                         ("rr_family2_R4WIN_prereg_md", Path("/tmp/rr/paper/research_revision/family2_R4WIN_prereg.md"), "research revision output of 2026-10-29 (erratum/addendum 27 series)"),
                         ("fam1_PLAN_md", Path("/tmp/rr/paper/research_revision/exp1/PLAN.md"), "family 1 (2x2 recipe vs prose) pre-registration input, addendum 28, registered before any arm exists"),
                         ("fam1_build_arms_py", Path("/tmp/rr/paper/research_revision/exp1/build_arms.py"), "family 1 (2x2 recipe vs prose) pre-registration input, addendum 28, registered before any arm exists"),
                         ("fam1_check_arms_py", Path("/tmp/rr/paper/research_revision/exp1/check_arms.py"), "family 1 (2x2 recipe vs prose) pre-registration input, addendum 28, registered before any arm exists"),
                         ("fam1_prose_DRAFTER_PROMPT_txt", Path("/tmp/rr/paper/research_revision/exp1/prose/DRAFTER_PROMPT.txt"), "family 1 (2x2 recipe vs prose) pre-registration input, addendum 28, registered before any arm exists"),
                         ("fam1_prose_prose_s0_md", Path("/tmp/rr/paper/research_revision/exp1/prose/prose_s0.md"), "family 1 (2x2 recipe vs prose) pre-registration input, addendum 28, registered before any arm exists"),
                         ("fam1_prose_prose_s3_md", Path("/tmp/rr/paper/research_revision/exp1/prose/prose_s3.md"), "family 1 (2x2 recipe vs prose) pre-registration input, addendum 28, registered before any arm exists"),
                         ("fam1_prose_seed_primitives_py", Path("/tmp/rr/paper/research_revision/exp1/prose/seed_primitives.py"), "family 1 (2x2 recipe vs prose) pre-registration input, addendum 28, registered before any arm exists"),
                         ("fam1_PLAN_md_sections1to14", Path("/tmp/rr/paper/research_revision/exp1/PLAN.md"), "family 1 PLAN, sections 1 to 14 (addendum 29)"),
                         ("exp1_order.py", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/exp1_order.py"), "family 1 order builder: r4_order.py plus the salt R4X (addendum 30)"),
                         ("exp1_order_v2.py", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/exp1_order.py"), "family 1 order builder v2 (drops the seed-check cell; addendum 31)"),
                         ("fam1_PLAN_v15", Path("/tmp/rr/paper/research_revision/exp1/PLAN_v15.md"), "family 1 PLAN v15 (seed anchor, build_arms answer; addendum 31)"),
                         ("fam1_analysis.py", PAPER / "analysis/scripts/fam1_analysis.py", "family 1 analysis script, tested on a synthetic stand-in only (addendum 32)"),
                         ("order_E1X_jsonl", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests/order_E1X.jsonl"), "family 1 (E1X) order package, acked in erratum 145"),
                         ("artifacts_E1X_json", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests/artifacts_E1X.json"), "family 1 (E1X) order package, acked in erratum 145"),
                         ("champions_E1X_json", Path("/home/dev/projects2/mlsys2027-cap-evolve-paper/experiments/final/manifests/champions_E1X.json"), "family 1 (E1X) order package, acked in erratum 145"),
                         ("fam1_PLAN_v16", Path("/tmp/rr/paper/research_revision/exp1/PLAN_v16.md"), "family 1 PLAN v16 (2,000 jobs; erratum 146)"),
                         ("fam1_secondary.py", PAPER / "analysis/scripts/fam1_secondary.py", "family 1 secondary outcomes script, written after the primary was read (erratum 148)"),
                         ("e1x_fam1_md", PAPER / "analysis/out/unblind_20261029/e1x/fam1.md", "family 1 (E1X) analysis output (erratum 148)"),
                         ("e1x_fam1_json", PAPER / "analysis/out/unblind_20261029/e1x/fam1.json", "family 1 (E1X) analysis output (erratum 148)"),
                         ("e1x_fam1_secondary_md", PAPER / "analysis/out/unblind_20261029/e1x/fam1_secondary.md", "family 1 (E1X) analysis output (erratum 148)"),
                         ("e1x_fam1_secondary_json", PAPER / "analysis/out/unblind_20261029/e1x/fam1_secondary.json", "family 1 (E1X) analysis output (erratum 148)"),
                         ("e1x_cell_means_json", PAPER / "analysis/out/unblind_20261029/e1x/cell_means.json", "family 1 (E1X) analysis output (erratum 148)"),
                         ("e1x_RESULTS_registered_md", Path("/tmp/rr/paper/research_revision/exp1/RESULTS_registered.md"), "family 1 (E1X) results summary for team-lead (erratum 148)"),
                         ("awx_PLAN_AW_md", Path("/tmp/rr/paper/research_revision/exp1/aw/PLAN_AW.md"), "family 1 AppWorld part (AWX) registration input, erratum 150"),
                         ("awx_subset_rule_py", Path("/tmp/rr/paper/research_revision/exp1/aw/subset_rule.py"), "family 1 AppWorld part (AWX) registration input, erratum 150"),
                         ("awx_subset_out_tasks_txt", Path("/tmp/rr/paper/research_revision/exp1/aw/subset_out/tasks.txt"), "family 1 AppWorld part (AWX) registration input, erratum 150"),
                         ("awx_subset_out_subset_json", Path("/tmp/rr/paper/research_revision/exp1/aw/subset_out/subset.json"), "family 1 AppWorld part (AWX) registration input, erratum 150"),
                         ("awx_build_aw_arms_py", Path("/tmp/rr/paper/research_revision/exp1/aw/build_aw_arms.py"), "family 1 AppWorld part (AWX) registration input, erratum 150"),
                         ("awx_check_aw_arms_py", Path("/tmp/rr/paper/research_revision/exp1/aw/check_aw_arms.py"), "family 1 AppWorld part (AWX) registration input, erratum 150"),
                         ("awx_DRAFTER_PROMPT_AW_txt", Path("/tmp/rr/paper/research_revision/exp1/aw/DRAFTER_PROMPT_AW.txt"), "family 1 AppWorld part (AWX) registration input, erratum 150"),
                         ("awx_prose_paged_md", Path("/tmp/rr/paper/research_revision/exp1/aw/prose_paged.md"), "family 1 AppWorld part (AWX) registration input, erratum 150"),
                         ("awx_aw_order_py", Path("/tmp/rr/paper/research_revision/exp1/aw/aw_order.py"), "family 1 AppWorld part (AWX) registration input, erratum 150"),
                         ("awx_run_awx_py", Path("/tmp/rr/paper/research_revision/exp1/aw/run_awx.py"), "family 1 AppWorld part (AWX) registration input, erratum 150"),
                         ("awx_order_order_AWX_json", Path("/home/dev/projects2/campaign-scratch/final_eval/AWX/order/order_AWX.json"), "family 1 AppWorld part (AWX) registration input, erratum 150"),
                         ("awx_order_order_AWX_sha256", Path("/home/dev/projects2/campaign-scratch/final_eval/AWX/order/order_AWX.sha256"), "family 1 AppWorld part (AWX) registration input, erratum 150"),
                         ("awx_arms_arms_json", Path("/home/dev/projects2/campaign-scratch/final_eval/AWX/arms/arms.json"), "family 1 AppWorld part (AWX) registration input, erratum 150"),
                         ("awx_arms_rewrites_txt", Path("/home/dev/projects2/campaign-scratch/final_eval/AWX/arms/rewrites.txt"), "family 1 AppWorld part (AWX) registration input, erratum 150"),
                         ("awx_arms_check_aw_json", Path("/home/dev/projects2/campaign-scratch/final_eval/AWX/arms/check_aw.json"), "family 1 AppWorld part (AWX) registration input, erratum 150"),
                         ("rr2_canonical_aw_holm_m10_csv", Path("/tmp/rr/paper/research_revision/canonical/aw_holm_m10.csv"), "research revision canonical comparator family and E1X post hoc (erratum 152)"),
                         ("rr2_canonical_aw_holm_m10_py", Path("/tmp/rr/paper/research_revision/canonical/aw_holm_m10.py"), "research revision canonical comparator family and E1X post hoc (erratum 152)"),
                         ("rr2_canonical_tau2_holm_m10_csv", Path("/tmp/rr/paper/research_revision/canonical/tau2_holm_m10.csv"), "research revision canonical comparator family and E1X post hoc (erratum 152)"),
                         ("rr2_canonical_tau2_holm_m10_py", Path("/tmp/rr/paper/research_revision/canonical/tau2_holm_m10.py"), "research revision canonical comparator family and E1X post hoc (erratum 152)"),
                         ("rr2_primary_protocol_md", Path("/tmp/rr/paper/research_revision/primary_protocol.md"), "research revision canonical comparator family and E1X post hoc (erratum 152)"),
                         ("rr2_exp1_RESULTS_registered_md", Path("/tmp/rr/paper/research_revision/exp1/RESULTS_registered.md"), "research revision canonical comparator family and E1X post hoc (erratum 152)"),
                         ("fam1_posthoc.py", PAPER / "analysis/scripts/fam1_posthoc.py", "family 1 post hoc code - prose script (erratum 152)"),
                         ("e1x_fam1_posthoc_md", PAPER / "analysis/out/unblind_20261029/e1x/fam1_posthoc.md", "family 1 post hoc output (erratum 152)"),
                         ("pricing_json", PAPER / "protocol/pricing.json", "first-party list price table, retrieved 2026-10-11 (erratum 152)"),
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
