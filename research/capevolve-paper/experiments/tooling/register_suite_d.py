#!/usr/bin/env python3
"""Append the Suite D pre-registration items to experiments/registry.jsonl (same append-only, hash-chained line format as
experiments/final/freeze.py: every line carries the sha256 of the previous line).  Idempotent per (item, sha256).

    python3 -I register_suite_d.py            # run from anywhere; paths are relative to the paper directory
"""
import hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

PAPER = Path(__file__).resolve().parents[2]
REG = PAPER / "experiments" / "registry.jsonl"
ITEMS = [
    ("suite_D_registration", PAPER / "experiments/configs/suite_D_registration.json", "cells, contrasts, Holm families, margin, final set"),
    ("analysis_plan_suite_D_amendment7", PAPER / "protocol/analysis_plan.md", "analysis plan incl. 5-AMENDMENT 7 (Suite D)"),
    ("analysis_plan_amendment9", PAPER / "protocol/analysis_plan.md", "analysis plan incl. 5-AMENDMENT 9 (headline estimand, amendments table, inert rule, equivalence scope, AO dagger, E12B)"),
    ("suite_E_registration", PAPER / "experiments/configs/suite_E_registration.json", "Suite E (airline replication) cells, families, split hash, MDE"),
    ("suite_E_split_file", Path("/home/dev/projects2/wt-tau/protocol/tau_airline_splits.json"), "tau_airline_splits.json used by every Suite E cell and competitor"),
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
