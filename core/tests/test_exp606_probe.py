"""Temp-branch tests for issue #606's reader-profile experiment (branch exp/606-reader-profile, never merged)."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))
WF = (REPO / ".github/workflows/benchmarks.yml").read_text(encoding="utf-8")
RS = (REPO / "ci/benchmarks/lib/run_suite.sh").read_text(encoding="utf-8")
PROBE = REPO / "ci/benchmarks/spreadsheetbench/full_verified_probe"
PARENT = REPO / "ci/benchmarks/spreadsheetbench/full_verified"
UTILS = REPO / "ci/benchmarks/spreadsheetbench/utils"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"_exp606_{name}", UTILS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _j(p):
    return json.loads(p.read_text(encoding="utf-8"))


# ---- workflow ---------------------------------------------------------------------------------

def test_opus_5_5_is_an_agent_and_optimizer_option():
    assert WF.count('- "ibm-ete-int/aws/claude-opus-5-5"') == 2


def test_reader_variant_input_reaches_the_job_and_runmeta():
    assert "      reader_variant:\n" in WF and "options: [A, B, C, R]" in WF
    assert "SB_READER: ${{ github.event.inputs.reader_variant }}" in WF
    assert '"reader_variant": "${SB_READER:-A}"' in WF


def test_probe_tier_is_selectable_and_explicit_only():
    assert "full_verified, full_verified_probe]" in WF
    assert 'EXPLICIT_ONLY_TIERS = {"pilot", "full_verified", "full_verified_probe"}' in WF


def test_bench_job_is_pinned_to_skillberry_1():
    # skillberry-2's sandbox lost 15/40 val rollouts to exec timeouts (run 36746122576)
    assert "runs-on: [self-hosted, ibm-vpc, skillberry-1]" in WF


def test_queued_dispatches_are_never_cancelled():
    # one group per run: the single pinned runner serializes them, and GitHub never drops a pending one
    assert "group: benchmarks-${{ matrix.tier }}-${{ matrix.bench }}-${{ github.ref }}-${{ github.run_id }}" in WF


# ---- probe tier ------------------------------------------------------------------------------

def test_probe_split_shares_train_val_and_subsets_test():
    s, parent = _j(PROBE / "split_ids.json"), _j(PARENT / "split_ids.json")
    assert sorted(s["train"]) == sorted(parent["train"])
    # val-hard: 40 val ids drawn from the parent's TEST split, disjoint from the probe test subset
    assert len(s["val"]) == 40 and set(s["val"]) <= set(parent["test"]) and not set(s["val"]) & set(s["test"])
    assert len(s["test"]) == len(set(s["test"])) == 100 and set(s["test"]) <= set(parent["test"])


def test_probe_tasks_cover_the_split_exactly():
    s = _j(PROBE / "split_ids.json")
    ids = [str(t["id"]) for t in _j(PROBE / "tasks.json")]
    assert len(ids) == len(set(ids)) == 220
    assert set(ids) == set(s["train"]) | set(s["val"]) | set(s["test"])


def test_subset_digest_and_baseline_are_pinned():
    src, s = _j(PROBE / "subset_source.json"), _j(PROBE / "split_ids.json")
    for k in ("train", "test"):
        assert hashlib.sha256("\n".join(sorted(s[k])).encode()).hexdigest() == src["sha256_sorted_ids"][k]
    vh = _j(PROBE / "val_hard_source.json")
    assert hashlib.sha256("\n".join(sorted(s["val"])).encode()).hexdigest() == vh["sha256_sorted_ids"]["val"]
    assert vh["seed"] == 607 and vh["groups"]["mixed"] == 31 and abs(vh["val_seed_reward"] - 0.40) < 1e-9
    assert src["seed"] == 606 and sum(src["counts_by_type"].values()) == 100
    assert src["slot_run_id"] == "36622615059" and src["seed_test_n_scored_on_subset"] == 100
    assert not set(src["parent_test_unscored"]) & set(s["test"]), "every subset task must be paired"
    assert abs(src["seed_test_reward_on_subset"] - src["seed_test_reward_on_parent"]) < 0.02


def test_probe_overrides_never_touch_the_live_slot():
    env = dict(line.split("=", 1) for line in (PROBE / "overrides.env").read_text().splitlines()
               if line and not line.startswith("#"))
    assert env["SB_KEEP_LATEST_RUN"] == "0"
    assert env["SB_LATEST_DIR"] == "/home/skillberry/.cache/capevolve-latest/spreadsheetbench-606"
    assert env["SB_REUSE_FROM_TIER"] == "full_verified" and env["SB_EMPTY_SEED"] == "1"
    assert env["SB_REUSE_LATEST_BASELINE"] == "1" and env["SB_SCORING"] == "hard" and env["GATE_K_SE"] == "0.2"
    assert env["CAPEVOLVE_SKIP_FINAL_TRAIN"] == "1"


def test_skip_final_train_skips_only_the_train_bookend(tmp_path, monkeypatch):
    from cap_evolve import harness
    from cap_evolve.rundir import RunDir
    from cap_evolve.splits import Splits
    rd = RunDir.create(tmp_path)
    rd.write_splits(Splits(train=["t1"], val=["v1"], test=["x1"], seed=0))
    monkeypatch.setenv("CAPEVOLVE_SKIP_FINAL_TRAIN", "1")

    def boom(*a, **k):
        raise AssertionError("train must not be evaluated")
    monkeypatch.setattr(harness, "evaluate_candidate", boom)
    out = harness._finalize_train_val(None, rd, "seed", "seed", n_trials=1)
    assert out["train"]["status"].startswith("skipped: CAPEVOLVE_SKIP_FINAL_TRAIN")


def test_reader_files_are_whole_blocks_that_render_verbatim():
    from cap_evolve import target_profile as tp
    r = (PROBE / "reader/R_results_driven.md").read_text()
    b = (PROBE / "reader/B_frontier.md").read_text()
    assert r.startswith("## THE READER") and "gemma" not in r.lower() and "tier" not in r.lower()
    assert b.startswith("## THE READER") and "**frontier**" in b and "gemma-4-31B-it" in b
    a = tp.reader_block(tp.resolve("rits/google/gemma-4-31B-it"))
    # A and B differ only in the tier word and the brief
    assert b.replace("**frontier**", "**strong**").replace(tp.TIERS["frontier"]["brief"], tp.TIERS["strong"]["brief"]) == a
    for f in (r, b):
        assert tp.reader_block(tp.resolve("rits/google/gemma-4-31B-it", PROBE / "reader" / (
            "R_results_driven.md" if f is r else "B_frontier.md"))) == f


def test_probe_tier_uses_the_verified_data_and_comparison_budgets():
    setup = (REPO / "ci/benchmarks/lib/ci_setup.sh").read_text()
    assert 'full_verified|full_verified_probe) SB_VARIANT="verified_400"' in setup
    assert RS.count("full|pilot|full_verified|full_verified_probe) SB_") == 2


# ---- run_suite plumbing ------------------------------------------------------------------------

def test_run_suite_rejects_unknown_reader_and_missing_file():
    assert "SB_READER must be A, B, C or R" in RS
    assert "is missing or empty" in RS and "not the file" in RS
    assert "$TARGET_MODEL_LINE\n$TARGET_PROFILE_LINE\n" in RS


def test_reuse_allows_a_parent_tier_and_a_test_subset_only():
    assert '"${SB_REUSE_FROM_TIER:-$TIER}"' in RS and '--target-split "$PROJ/inputs/split_ids.json"' in RS
    assert "if not wv <= pv | set(" in RS and "if not wt <= pt:" in RS


def test_run_suite_records_optimizer_models_and_instructions():
    assert "optimizer_models.json" in RS and "optimizer_instructions" in RS


# ---- rescore_run --test-subset ------------------------------------------------------------------

def _pt(tid, r):
    return {"task_id": tid, "reward": r, "n": 1, "raw": {}, "trial_rewards": [r],
            "metrics": [{"name": "hard_no_recalc", "value": r, "primary": True, "direction": "higher"}]}


def _run(tmp, seed_test):
    rd = tmp / "run_suite"
    for split in ("val", "train"):
        (rd / "rollouts" / split).mkdir(parents=True)
    stored = {"split": "test", "reward": 0.0, "per_task": [_pt(t, r) for t, r in seed_test.items()]}
    (rd / "splits.json").write_text(json.dumps({"train": [], "val": [], "test": sorted(seed_test),
                                                "seed": 0, "test_used": True}))
    (rd / "baseline.json").write_text(json.dumps({"val": {"reward": 0.5, "per_task": [_pt("v", 0.5)]},
                                                 "best_id": "seed"}))
    (rd / "final.json").write_text(json.dumps({"best_id": "cand_0001", "baseline_id": "seed",
                                              "test": {"reward": 0.9}, "test_baseline": stored,
                                              "seed": {"test": stored}}))
    (rd / "state.json").write_text(json.dumps({"best_id": "cand_0001", "spent": {}}))
    (rd / "events.jsonl").write_text("")
    return rd


def test_rescore_restricts_seed_test_to_the_subset(tmp_path):
    rd = _run(tmp_path, {"a": 1.0, "b": 0.0, "c": 1.0, "d": 1.0})
    out = _load("rescore_run").rescore(rd, "hard_no_recalc", test_ids={"a", "b"})
    final = _j(rd / "final.json")
    assert out["test"] == 0.5 and out["test_n"] == 2
    assert {p["task_id"] for p in final["seed"]["test"]["per_task"]} == {"a", "b"}
    assert final["test_baseline"]["reward"] == 0.5 and final["test"]["reward"] == 0.9
    splits = _j(rd / "splits.json")
    assert splits["test"] == ["a", "b"] and splits["test_used"] is True  # reuse_baseline resets the seal


def test_rescore_without_subset_is_unchanged(tmp_path):
    rd = _run(tmp_path, {"a": 1.0, "b": 0.0, "c": 1.0, "d": 1.0})
    out = _load("rescore_run").rescore(rd, "hard_no_recalc")
    assert out["test"] == 0.75 and "test_n" not in out and _j(rd / "splits.json")["test"] == ["a", "b", "c", "d"]


def test_rescore_subset_with_an_unknown_id_fails(tmp_path):
    rd = _run(tmp_path, {"a": 1.0, "b": 0.0})
    with pytest.raises(SystemExit):
        _load("rescore_run").rescore(rd, "hard_no_recalc", test_ids={"a", "z"})


# ---- report ----------------------------------------------------------------------------------

READER_R = (PROBE / "reader/R_results_driven.md").read_text()


def _artifact(tmp, rid, opt, base, *, models=("claude-opus-5-5",), accept=True, block=READER_R,
              declared="R", instructions=None):
    d = tmp / rid / "benchmarks-full_verified_probe-spreadsheetbench"
    (d / "optimized/optimized_capability").mkdir(parents=True)
    (d / "ui/data").mkdir(parents=True)
    (d / "optimizer_instructions").mkdir()
    (d / "metrics.jsonl").write_text("".join(
        json.dumps({"task": t, "reward_baseline": base[t], "reward_opt": opt[t], "opt_infra": False}) + "\n"
        for t in opt))
    (d / "runmeta.json").write_text(json.dumps({"run_id": int(rid) if rid.isdigit() else rid,
                                                "reader_variant": declared, "iterations": 1}))
    (d / "reader_block.md").write_text(block)
    (d / "optimizer_instructions/cand_0001.md").write_text(
        instructions if instructions is not None else f"# Task\n\n{block}\n## Rules\n")
    (d / "optimizer_models.json").write_text(json.dumps({"models": {m: 3 for m in models}}))
    (d / "optimized/optimized_capability/prompt.md").write_text(
        "# Rules\n1. a\n2. b\n- c\n\nExample:\n```\nx\n```\nUse data_only; never a formula; round to 2 decimal.")
    (d / "optimized/optimized_capability/task_template.md").write_text("t")
    ev = [{"kind": "baseline_reused", "val": 0.5},
          {"kind": "step", "candidate": "cand_0001", "accept": accept, "val": 0.7,
           "opt_cost_usd": 12.0, "optimizer_seconds": 600},
          {"kind": "finalize", "best_id": "cand_0001" if accept else "seed"}]
    (d / "ui/data/runs_run_suite_file_path_events_jsonl.json").write_text(json.dumps(
        {"path": "events.jsonl", "text": "".join(json.dumps(e) + "\n" for e in ev)}))
    return tmp / rid


def test_summarize_reads_scores_cost_models_and_shape(tmp_path):
    rep = _load("exp606_report")
    s = rep.summarize(_artifact(tmp_path, "1", {"a": 1, "b": 1, "c": 0, "d": 1}, {"a": 0, "b": 1, "c": 0, "d": 0}))
    assert s["test_seed"] == 0.25 and s["test_opt"] == 0.75 and s["delta"] == 0.5 and s["n_tasks"] == 4
    assert s["variant"] == "R" and s["accepted"] == [True] and s["opt_usd"] == 12.0 and s["opt_minutes"] == 10
    assert s["val_seed"] == 0.5 and s["val_cand"] == [0.7]
    assert s["models"] == ["claude-opus-5-5"] and s["valid"] is True, s["problems"]
    sh = s["skill_shape"]
    assert sh["numbered_rules"] == 2 and sh["bullets"] == 1 and sh["code_examples"] == 1 and sh["grader_contract"]


@pytest.mark.parametrize("kw, problem", [
    ({"models": ("claude-opus-5-5", "claude-opus-5")}, "optimizer models"),
    ({"models": ()}, "optimizer models"),
    ({"declared": "B"}, "declared variant"),
    ({"instructions": "# Task\nno reader here\n"}, "not found verbatim"),
])
def test_bad_runs_are_marked_invalid(tmp_path, kw, problem):
    rep = _load("exp606_report")
    s = rep.summarize(_artifact(tmp_path, "2", {"a": 1}, {"a": 0}, **kw))
    assert s["valid"] is False and any(problem in p for p in s["problems"])


def test_variant_c_needs_no_reader_block_in_the_instructions(tmp_path):
    rep = _load("exp606_report")
    s = rep.summarize(_artifact(tmp_path, "3", {"a": 1}, {"a": 0}, block="", declared="C",
                                instructions="# Task\n## Rules\n"))
    assert s["variant"] == "C" and s["valid"] is True, s["problems"]


def test_compare_is_paired_on_common_tasks_and_averages_repeats(tmp_path):
    rep = _load("exp606_report")
    a = [rep.summarize(_artifact(tmp_path, "a1", {"x": 1, "y": 1}, {"x": 0, "y": 0})),
         rep.summarize(_artifact(tmp_path, "a2", {"x": 0, "y": 1}, {"x": 0, "y": 0}))]
    b = [rep.summarize(_artifact(tmp_path, "b1", {"x": 0, "y": 1, "z": 1}, {"x": 0, "y": 0, "z": 0}))]
    c = rep.compare(a, b)
    assert c["n_tasks"] == 2 and c["diff"] == pytest.approx(0.25)  # x: 0.5-0, y: 1-1


def test_target_split_moves_new_val_ids_from_the_seed_test_rows(tmp_path):
    rd = _run(tmp_path, {"a": 1.0, "b": 0.0, "c": 1.0, "d": 0.0})
    vdir = rd / "rollouts" / "val"
    (vdir / "v__seed__t0.json").write_text(json.dumps({"input": {}, "rollout": {"task_id": "v", "error": None},
                                                       "score": {"task_id": "v", "reward": 1.0, "metrics": []}}))
    s = _j(rd / "splits.json"); s["val"] = ["v"]; (rd / "splits.json").write_text(json.dumps(s))
    out = _load("rescore_run").rescore(rd, "hard_no_recalc", test_ids={"a", "b"}, val_ids={"c", "d"})
    assert out["val"] == 0.5 and out["val_copied_from_test"] == 2 and out["test"] == 0.5
    assert sorted(f.name for f in vdir.glob("*__seed__*")) == ["c__seed__t0.json", "d__seed__t0.json"]
    splits = _j(rd / "splits.json")
    assert splits["val"] == ["c", "d"] and splits["test"] == ["a", "b"]
    assert _j(rd / "baseline.json")["val"]["reward"] == 0.5


def test_target_split_rejects_a_val_id_with_no_seed_record(tmp_path):
    rd = _run(tmp_path, {"a": 1.0})
    with pytest.raises(SystemExit):
        _load("rescore_run").rescore(rd, "hard_no_recalc", test_ids={"a"}, val_ids={"zz"})
