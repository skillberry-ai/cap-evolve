#!/usr/bin/env python3
"""freeze.py: the pre-scoring freeze of analysis plan section 8/10 ("Before any untouched-final scoring").

    freeze.py --suites A,B,C [--registry experiments/registry.jsonl] [--allow-dirty] [--dry]

Appends one line per frozen item to experiments/registry.jsonl (append-only, hash-chained: every line carries the sha256 of the
previous line).  Items: analysis plan; final-task manifests (A task file, B/C split files + sealed id-list hashes); model registry and the
frozen run settings (temperature, tokens, turn limits, judge, gateway); evaluator/scorer code (patched SpreadsheetBench adapter and
vendored scorer, tau adapters, LibreOffice binary, tau2 pin, run_final/worker); the section 6 classifier (collect_metrics.py and the
text of uniform_class + INFRA_RE); the section 5 comparison family (generated here from the arms present; written to
manifests/comparison_family.json); content hashes of every artifact (artifact manifests, order files, B* files, seed artifact);
analysis scripts and this directory at the script commit.  Idempotent: an item already registered with the same sha256 is skipped.
Refuses to run with uncommitted changes under experiments/final or analysis/scripts unless --allow-dirty (dry runs).
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fe_common as C  # noqa: E402

WT_TAU = Path("/home/dev/projects2/wt-tau")
REGISTRY = C.PAPER / "experiments" / "registry.jsonl"

FROZEN_SETTINGS = {
    "target_models": {"A": "rits/google/gemma-4-31B-it", "B": "rits/openai/gpt-oss-120b-a100", "C": "rits/openai/gpt-oss-120b-a100"},
    "user_simulator": {"B": "rits/openai/gpt-oss-120b-a100", "C": "rits/openai/gpt-oss-120b-a100"},
    "judge": {"B": "azure/gpt-5.5 (provider defaults)", "C": "n/a for the primary reward (DB + COMMUNICATE); NL judge azure/gpt-5.5 if the task has NL assertions"},
    "temperature": 0.0, "max_tokens": 8000, "tau_max_steps": 100, "spreadsheetbench_max_turns": 30, "spreadsheetbench_exec_timeout_s": 180,
    "spreadsheetbench_scoring": "hard", "reward_A": "LibreOffice 25.8.7.3 recalculated hard score (metric hard_restriction); as-saved hard logged",
    "gateway": "http://127.0.0.1:4111/v1 (extras: 4112)", "hang_rule_s": 10800, "infra_retries": 3, "hang_retries": 1,
    "e25_placement": {"D": "merged into the main window (--merge-decomp)", "E": "separate extra order after the main window", "B/C": "separate extra order, n=1, run last"}, "sandbox_KERNEL_TIMEOUT_S": 10800, "sandbox_SB_DRAIN_ERROR": 1, "order_seed": C.ORDER_SEED, "cutoff_utc": C.CUTOFF_UTC,
}


def git(*args, cwd=C.REPO):
    return subprocess.check_output(["git", "-C", str(cwd)] + list(args), text=True).strip()


SUITE_D_FAMILY = {   # registered by stats-reviewer (suite_D_registration.json, amendment 8A/9H): sealed test-40 on both sides; H65 is a descriptive recomputation with its own Holm
    "primary_D_holm_m11": [("p", "pt"), ("t", "pt"), ("p", "t"), ("rulep", "pt"), ("1s", "pt"), ("pt", "ctl"), ("p", "gepa"), ("p", "seed"), ("t", "seed"), ("pt", "seed"), ("nohist", "pt")],
    "secondary_D_sec_holm_m4": [("gepa", "seed"), ("rulep", "seed"), ("1s", "seed"), ("ctl", "seed")],
    "descriptive_only": ["interaction pt - p - t + seed", "E25 decomposition", "selection-to-final shrinkage (non-inert seeds)", "promotions per search", "E26 gate ROC", "exploratory cells"],
    "surface_lock_rule_9H": "a seed whose champion edits outside its cell's lock stays in its cell (ITT), gets a dagger, and every row involving that cell is recomputed excluding violating seeds (Holm denominator unchanged)",
}


SUITE_E_FAMILY = {   # amendment 10D/10L: primary = official test-20 on both sides; H30 = sel-10 + test-20 descriptive recomputation with its own Holm
    "primary_E_holm_m11": SUITE_D_FAMILY["primary_D_holm_m11"],
    "secondary_E_sec_holm_m4": SUITE_D_FAMILY["secondary_D_sec_holm_m4"],
    "E_comp_own_holm": [("pt", "ace"), ("pt", "mipro"), ("pt", "gepafull"), ("pt", "ao")], "ao_dagger_9F": True,
    "harnesslens": "1 exploratory seed, outside Holm", "no_equivalence_claim": True,
    "descriptive_only": SUITE_D_FAMILY["descriptive_only"],
}


def comparison_family(suites):
    """analysis_plan 5A/5B, per suite.  Arms with an incomplete seed under the B* rule are removed by the caller from the manifests, and the
    family here is generated only from arms that have a usable B* artifact for all seeds."""
    fam = {}
    for s in suites:
        if s == "D":
            fam[s] = SUITE_D_FAMILY
            continue
        if s == "E":
            fam[s] = SUITE_E_FAMILY
            continue
        man = C.jload(C.MANIFESTS / ("artifacts_%s.json" % s)) or {}
        ok = {}
        for e in man.get("entries", []):
            if e["mode"] == "B":
                ok.setdefault(e["arm"], []).append(e["status"] != "impossible")
        usable = {a for a, v in ok.items() if v and all(v)}
        base = {"A": ["seed", "gepa", "skillopt", "metaharness", "wikiskill", "evoskill"],
                "B": ["seed", "oneshot", "gepa", "harnesslens"], "C": ["seed", "oneshot", "gepa"]}[s]
        primary = [{"arm": m, "vs": b} for m in ("hc", "ao") for b in base if (m in usable) and (b == "seed" or b in usable)]
        secondary_i = [{"arm": b, "vs": "seed"} for b in C.suite_arms(s) if b not in ("hc", "ao", "oneshot") and b in usable]
        cheap = [x for x in C.SUITES[s]["cheap"] if x in usable]
        secondary_ii = [{"arm": "hc", "vs": "ao"}] + [{"arm": m, "vs": c} for m in ("hc", "ao") for c in cheap]
        s_stock = [{"arm": "hcstock", "vs": b} for b in ("seed", "gepa", "harnesslens")] if s == "B" else []   # E12B, amendment 9G: secondary family S-stock-B, Holm m = 3
        nod = [r for r in primary if (s, r["arm"]) not in C.DAGGER]
        fam[s] = {"primary_5A": primary, "primary_5A_without_dagger_arms": nod, "secondary_S_stock_B_holm_m3": s_stock, "dagger_arms": sorted(a for (ss, a) in C.DAGGER if ss == s), "secondary_5B_i": secondary_i, "secondary_5B_ii": secondary_ii, "holm_denominator_primary": len(primary),
                  "note": "generated by freeze.py from arms with a usable B* artifact for every seed; hc/ao are CapEvolve rule-P arms; analysis_plan 5A/5B"}
    return fam


def hash_text_of(*objs):
    return hashlib.sha256("\n".join(inspect.getsource(o) for o in objs).encode()).hexdigest()


class Registry:
    def __init__(self, path):
        self.path = Path(path)
        self.lines = [l for l in (self.path.read_text().splitlines() if self.path.exists() else []) if l.strip()]
        self.have = set()
        for l in self.lines:
            try:
                d = json.loads(l)
                self.have.add((d.get("item"), d.get("sha256")))
            except Exception:
                pass

    def add(self, item, sha, path=None, note="", **extra):
        if (item, sha) in self.have:
            return False
        prev = hashlib.sha256(self.lines[-1].encode()).hexdigest() if self.lines else None
        d = {"item": item, "sha256": sha, "path": str(path) if path else None, "t_utc": C.now_utc(), "script_commit": C.git_head(), "prev_line_sha256": prev, "note": note}
        d.update(extra)
        line = json.dumps(d, sort_keys=True)
        self.lines.append(line)
        self.have.add((item, sha))
        return True

    def write(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(self.lines) + ("\n" if self.lines else ""))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--suites", default="A,B,C")
    ap.add_argument("--registry", default=str(REGISTRY))
    ap.add_argument("--allow-dirty", action="store_true")
    ap.add_argument("--note", default="", help="reason attached to every item that is NEW in this run (e.g. a post-freeze deviation)")
    ap.add_argument("--dry", action="store_true", help="print what would be registered; write nothing")
    ap.add_argument("--manifests", default=str(C.MANIFESTS))
    a = ap.parse_args(argv)
    suites = a.suites.split(",")
    mdir = Path(a.manifests)
    dirty = subprocess.check_output(["git", "-C", str(C.REPO), "status", "--porcelain", "--", str(C.HERE), str(C.PAPER / "analysis/scripts"), str(C.PAPER / "protocol")], text=True).strip()
    if dirty and not a.allow_dirty:
        sys.exit("uncommitted changes under final/, analysis/scripts, protocol (commit first, or --allow-dirty for dry runs):\n" + dirty)
    reg = Registry(a.registry)
    items = []

    def item(name, path, note=""):
        p = Path(path)
        if not p.exists():
            items.append((name, None, p, "MISSING " + note))
        else:
            items.append((name, C.sha256_file(p), p, note))

    item("analysis_plan", C.PAPER / "protocol/analysis_plan.md")
    item("model_registry", C.PAPER / "protocol/model_registry.json")
    item("pricing", C.PAPER / "protocol/pricing.json")
    item("benchmarks_md", C.PAPER / "protocol/benchmarks.md")
    item("scorer_audit", C.PAPER / "protocol/scorer_audit.md")
    settings = C.MANIFESTS / "final_settings.json"
    if not a.dry:
        C.write_json_atomic(settings, FROZEN_SETTINGS)
    item("final_settings", settings, "temperature, tokens, turn limits, judge, gateway, hang rule")
    # final-task manifests
    item("final_tasks_A", C.PAPER / "protocol/final_set/suiteA_final_tasks.json", "Suite A drawn final set with family ids")
    item("sb912_pool", C.PAPER / "protocol/final_set/sb912_residual_pool.json")
    for s, f in (("B", "tau_retail_splits.json"), ("C", "tau_airline_splits.json")):
        item("final_split_file_%s" % s, WT_TAU / "protocol" / f, "sealed_test list is the final set; family = task id")
    # evaluator / scorer code
    for name, p in (("scorer_A_patched_adapter", C.SCRATCH / "bench/patches/new/adapter.py"),
                    ("scorer_A_vendored_evaluation", C.REPO / "third_party/spreadsheetbench/evaluation/evaluation.py"),
                    ("scorer_A_vendored_open_spreadsheet", C.REPO / "third_party/spreadsheetbench/evaluation/open_spreadsheet.py"),
                    ("scorer_A_agent_view_builder", C.SCRATCH / "bench/local/make_agent_view.py"),
                    ("scorer_B_adapter", WT_TAU / "examples/tau2_retail/adapters/adapter.py"),
                    ("scorer_C_adapter", WT_TAU / "examples/tau2_airline_c/adapters/adapter.py"),
                    ("scorer_E_adapter_wt_airE_b797886c8_on_eb112a08", Path("/home/dev/projects2/wt-airE") / "examples/tau2_airline_c/adapters/adapter.py"),
                    ("scorer_libreoffice_25_8_binary", C.SCRATCH / "bench/lo258/root/opt/libreoffice25.8/program/soffice.bin"),
                    ("runner_run_final", C.HERE / "run_final.py"), ("runner_order", C.HERE / "order.py"), ("runner_reconstruct", C.HERE / "reconstruct.py"),
                    ("runner_bstar", C.HERE / "bstar.py"), ("runner_common", C.HERE / "fe_common.py"), ("runner_draw", C.HERE / "draw_final_a.py"),
                    ("scorer_B_harnesslens_final_eval", C.SCRATCH / "baselines/harnesslens/tau/hl_final_eval.py"),
                    ("scorer_B_harnesslens_campaign_patch", C.SCRATCH / "baselines/harnesslens/tau/campaign_patch.diff"),
                    ("scorer_B_harnesslens_trial_flags", C.SCRATCH / "baselines/harnesslens/tau/hl_trial_flags.py"),
                    ("scorer_A_sandbox_api_py_kernel_timeout_10800", C.REPO / "third_party/spreadsheetbench/code_exec_docker/api.py"),
                    ("scorer_A_sandbox_jupyter_py_drain_error", C.REPO / "third_party/spreadsheetbench/code_exec_docker/jupyter.py"),
                    ("scorer_A_egress_check", C.SCRATCH / "baselines/code/check_sandbox_egress.py"),
                    ("runner_rejudge", C.HERE / "rejudge.py"),
                    ("analysis_paired_cluster_bootstrap", C.PAPER / "analysis/scripts/paired_cluster_bootstrap.py"),
                    ("analysis_collect_metrics_classifier", C.PAPER / "analysis/scripts/collect_metrics.py"),
                    ("analysis_real_numbers", C.PAPER / "paper/scripts/real_numbers.py")):
        item(name, p)
    cm = C.collect_metrics()
    items.append(("classifier_uniform_class_source", hash_text_of(cm.uniform_class) + ":" + hashlib.sha256(cm.INFRA_RE.pattern.encode()).hexdigest()[:16],
                  Path("collect_metrics.uniform_class+INFRA_RE"), "function text hash + INFRA_RE pattern hash"))
    for sub in ("tau2-8ebb749",):
        pin = C.SCRATCH / "bench/src" / sub
        try:
            items.append(("tau2_pin_commit", hashlib.sha256(git("rev-parse", "HEAD", cwd=pin).encode()).hexdigest(), pin, git("rev-parse", "HEAD", cwd=pin)))
        except Exception:
            items.append(("tau2_pin_commit", None, pin, "MISSING"))
    try:
        items.append(("wt_tau_commit", hashlib.sha256(git("rev-parse", "HEAD", cwd=WT_TAU).encode()).hexdigest(), WT_TAU, git("rev-parse", "HEAD", cwd=WT_TAU)))
    except Exception:
        items.append(("wt_tau_commit", None, WT_TAU, "MISSING"))
    # comparison family
    fam = comparison_family(suites)
    famf = mdir / "comparison_family.json"
    if not a.dry:
        C.write_json_atomic(famf, fam)
    item("comparison_family", famf, "analysis_plan 5A/5B rows generated from usable arms")
    # artifacts, orders, bstar
    for s in suites:
        item("bstar_%s" % s, mdir / ("bstar_%s.json" % s))
        item("artifact_manifest_%s" % s, mdir / ("artifacts_%s.json" % s), "tree hashes of every artifact incl. the seed")
        for suf in ("", "_end", "_transfer", "_rejudge"):
            p = mdir / ("order_%s%s.jsonl" % (s, suf))
            if p.exists():
                item("order_%s%s" % (s, suf), p)
        man = C.jload(mdir / ("artifacts_%s.json" % s)) or {}
        h = hashlib.sha256()
        for e in sorted(man.get("entries", []), key=lambda e: (e["mode"], e["arm"], e["seed"])):
            h.update(("%s|%s|%d|%s\n" % (e["mode"], e["arm"], e["seed"], e.get("tree_sha256"))).encode())
        items.append(("artifact_tree_hashes_%s" % s, h.hexdigest(), mdir / ("artifacts_%s.json" % s), "sha over (mode|arm|seed|tree hash) lines; seed artifact %s" % (man.get("seed_artifact", {}).get("tree_sha256"))))
    head = C.git_head()
    items.append(("script_commit", hashlib.sha256((head or "").encode()).hexdigest(), C.REPO, head))
    n_new = 0
    missing = []
    for name, sha, path, note in items:
        if sha is None:
            missing.append((name, str(path)))
            continue
        if a.dry:
            print("%-40s %s %s" % (name, sha[:16], note))
            continue
        n_new += 1 if reg.add(name, sha, path, ((a.note + " | ") if a.note else "") + note, suites=suites) else 0
    if not a.dry:
        reg.write()
    print("registered %d new items (%d total lines) -> %s" % (n_new, len(reg.lines), a.registry))
    if missing:
        print("NOT REGISTERED (missing):")
        for m in missing:
            print("  ", m)
        return 1 if not a.allow_dirty else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
