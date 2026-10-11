"""Paper-mode measurement switches (#755 footprint, #758 coverage/errored trials, #759 confirmation).

Each switch is OPT-IN and the default behaviour is unchanged; these tests pin both halves:

  * the DEFAULT still masks / still drops / still pools (so main's results stay reproducible), and
  * the new key changes exactly that behaviour and is recorded on the step.

Reproductions r1 (footprint masking accepts a net-negative candidate) and r2 (candidate crashes and
marginal-only coverage) come from the campaign audit (`research/capevolve-paper/audit/repro`).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))

TASKS = [f"t{i:02d}" for i in range(30)]
SEED_PASS = TASKS[5:]                 # parent fails t00..t04
CAND_FIXES = TASKS[1:5]               # the tool edit fixes t01..t04 (they call refund_order)
CAND_BREAKS = TASKS[20:26]            # a prose rule breaks t20..t25


class _Adapter:
    """Behaviour comes from ``cfg.json`` in the candidate dir (invisible to the footprint regexes)."""

    def tasks(self, split):
        from cap_evolve import Task
        return [Task(id=t) for t in TASKS]

    def run_target(self, task, ctx, *, seed=0):
        from cap_evolve import Rollout
        cfg = json.loads((Path(ctx) / "cfg.json").read_text(encoding="utf-8"))
        trace = "call refund_order(1)" if task.id in cfg.get("refund", []) else "call lookup(2)"
        if task.id in cfg.get("err_candidate", []):
            return Rollout(task_id=task.id, error="tool raised", trace=trace,
                           metadata={"error_kind": "candidate"})
        if task.id in cfg.get("err_infra", []):
            return Rollout(task_id=task.id, error="429 from registry", trace=trace)
        return Rollout(task_id=task.id, output="pass" if task.id in cfg["pass"] else "fail", trace=trace)

    def score(self, task, rollout):
        from cap_evolve import Score
        r = 1.0 if rollout.output == "pass" else 0.0
        return Score(task_id=task.id, reward=r, trial_rewards=[r])

    def apply(self, candidate_dir, edits=None):
        return None


def _setup(tmp_path, seed_cfg):
    from cap_evolve import RunDir, harness
    from cap_evolve.splits import Splits
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "cfg.json").write_text(json.dumps(seed_cfg))
    (seed / "tools.py").write_text("def refund_order(o):\n    return o\n")
    (seed / "prompt.md").write_text("Be helpful.\n")
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="pm")
    run_dir.write_splits(Splits(train=[], val=list(TASKS), test=[], seed=0))
    run_dir.snapshot("seed", seed)
    run_dir.set_best("seed")
    adapter = _Adapter()
    base = harness.evaluate_candidate(adapter, run_dir.candidate_dir("seed"), run_dir=run_dir,
                                      split="val", tag="seed")
    return adapter, run_dir, base


def _optimizer(cand_cfg, *, tool_edit=True, prose_edit=True):
    code = (
        "import sys, pathlib, json\n"
        "w = pathlib.Path(sys.argv[1]); cfg = json.loads(pathlib.Path(sys.argv[2]).read_text())\n"
        "(w/'cfg.json').write_text(json.dumps(cfg))\n"
        + ("(w/'tools.py').write_text('def refund_order(o):\\n    return validate(o)\\n')\n" if tool_edit else "")
        + ("(w/'prompt.md').write_text('Be helpful.\\nNever transfer to a human agent.\\n')\n" if prose_edit else ""))
    import tempfile
    from cap_evolve import harness
    cfg_file = Path(tempfile.mkdtemp()) / "cand_cfg.json"    # a path: the command template is str.format-ed
    cfg_file.write_text(json.dumps(cand_cfg))
    return harness.optimizer_from_command(["python3", "-c", code, "{workdir}", str(cfg_file)])


def _step(tmp_path, seed_cfg, cand_cfg, gate_kwargs=None, **kw):
    from cap_evolve import harness
    adapter, run_dir, base = _setup(tmp_path, seed_cfg)
    step = harness.run_step(
        adapter, run_dir=run_dir, parent_dir=run_dir.candidate_dir("seed"),
        optimizer=_optimizer(cand_cfg), instructions="x", current_val=base,
        gate_kwargs={"mode": "paired", "k_se": 1.0, **(gate_kwargs or {})}, **kw)
    return run_dir, step


def _step_event(run_dir):
    evs = [json.loads(l) for l in run_dir.events_path.read_text().splitlines() if l.strip()]
    return [e for e in evs if e.get("kind") == "step"][-1]


# ---- r1: footprint masking ------------------------------------------------------------------

_R1_SEED = {"pass": SEED_PASS, "refund": CAND_FIXES}
_R1_CAND = {"pass": [t for t in SEED_PASS if t not in CAND_BREAKS] + CAND_FIXES, "refund": CAND_FIXES}


def test_default_footprint_masks_and_accepts_a_net_negative_candidate(tmp_path):
    """Pins the audited DEFAULT (D01): unchanged unless a key is set."""
    run_dir, step = _step(tmp_path, _R1_SEED, _R1_CAND)
    assert step["accepted"] is True
    ev = _step_event(run_dir)
    assert ev["delta_full"] < 0 < ev["delta_masked"]


def test_gate_footprint_false_gates_on_the_full_vector(tmp_path):
    run_dir, step = _step(tmp_path, _R1_SEED, _R1_CAND, gate_kwargs={"gate_footprint": False})
    assert step["accepted"] is False
    ev = _step_event(run_dir)
    assert ev["delta_full"] == pytest.approx(-2 / 30, abs=1e-5)
    assert ev["delta_masked"] == ev["delta_full"] and ev["se_masked"] == pytest.approx(ev["se_full"])


def test_step_event_logs_both_statistics_ses_and_joint_coverage(tmp_path):
    run_dir, _ = _step(tmp_path, _R1_SEED, _R1_CAND)
    ev = _step_event(run_dir)
    for key in ("delta_full", "delta_masked", "se_full", "se_masked", "joint_coverage"):
        assert ev[key] is not None, key
    assert ev["joint_coverage"] == 1.0


# ---- r2: candidate crashes, errored-trial policy, joint coverage ----------------------------

_R2_SEED = {"pass": SEED_PASS}
_R2_CRASH = {"pass": [t for t in SEED_PASS if t not in CAND_BREAKS] + CAND_FIXES,
             "err_candidate": CAND_BREAKS}


def test_default_drops_candidate_errors_so_a_crashing_candidate_is_accepted(tmp_path):
    _, step = _step(tmp_path, _R2_SEED, _R2_CRASH, gate_kwargs={"gate_footprint": False})
    assert step["accepted"] is True      # the audited default (D04): crashes vanish from the pair


def test_errored_trial_policy_fail_scores_candidate_errors_as_zero(tmp_path):
    run_dir, step = _step(tmp_path, _R2_SEED, _R2_CRASH,
                          gate_kwargs={"gate_footprint": False, "errored_trial_policy": "fail"})
    assert step["accepted"] is False
    assert _step_event(run_dir)["delta_full"] == pytest.approx(-2 / 30, abs=1e-5)


def test_exogenous_errors_stay_missing_under_fail(tmp_path):
    infra = {"pass": [t for t in SEED_PASS if t not in CAND_BREAKS] + CAND_FIXES, "err_infra": CAND_BREAKS}
    _, step = _step(tmp_path, _R2_SEED, infra,
                    gate_kwargs={"gate_footprint": False, "errored_trial_policy": "fail"})
    assert step["accepted"] is True      # no error_kind: infra stays missing and retryable


def test_split_result_from_rollouts_honours_the_policy(tmp_path):
    from cap_evolve import harness
    adapter, run_dir, base = _setup(tmp_path, _R2_SEED)
    cand = tmp_path / "cand"
    cand.mkdir()
    (cand / "cfg.json").write_text(json.dumps(_R2_CRASH))
    harness.evaluate_candidate(adapter, cand, run_dir=run_dir, split="val", tag="c1",
                               errored_policy="fail")
    kept = harness.split_result_from_rollouts(run_dir, "c1", "val")
    failed = harness.split_result_from_rollouts(run_dir, "c1", "val", errored_policy="fail")
    assert kept.n_scored == 24 and failed.n_scored == 30
    assert failed.reward < kept.reward


def _disjoint_missing(tmp_path):
    seed = {"pass": SEED_PASS, "err_infra": TASKS[:9]}                      # parent cov 0.70
    cand = {"pass": SEED_PASS, "err_infra": TASKS[21:]}                     # candidate cov 0.70
    return seed, cand


def test_joint_coverage_helper_sees_what_marginals_hide(tmp_path):
    from cap_evolve import harness
    seed, cand = _disjoint_missing(tmp_path)
    adapter, run_dir, base = _setup(tmp_path, seed)
    c = tmp_path / "c"
    c.mkdir()
    (c / "cfg.json").write_text(json.dumps(cand))
    cv = harness.evaluate_candidate(adapter, c, run_dir=run_dir, split="val", tag="c")
    assert base.coverage == pytest.approx(0.7) and cv.coverage == pytest.approx(0.7)
    assert harness.joint_coverage(base, cv) == pytest.approx(12 / 30)


def test_default_coverage_is_candidate_marginal_but_joint_is_indecisive(tmp_path):
    seed, cand = _disjoint_missing(tmp_path)
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    _, step = _step(tmp_path / "a", seed, cand, gate_kwargs={"gate_footprint": False})
    assert step["decision"]["indecisive"] is False
    run_dir, step = _step(tmp_path / "b", seed, cand,
                          gate_kwargs={"gate_footprint": False, "gate_coverage": "joint"})
    assert step["decision"]["indecisive"] is True and step["accepted"] is False
    assert _step_event(run_dir)["joint_coverage"] == pytest.approx(12 / 30, abs=1e-5)


def test_min_coverage_reaches_decide(tmp_path):
    seed, cand = _disjoint_missing(tmp_path)
    _, step = _step(tmp_path, seed, cand,
                    gate_kwargs={"gate_footprint": False, "gate_coverage": "joint", "min_coverage": 0.3})
    assert step["decision"]["indecisive"] is False       # 0.4 >= 0.3


# ---- plumbing: spec/CLI flags ---------------------------------------------------------------

def test_unset_switches_add_nothing():
    import argparse
    from cap_evolve import harness
    p = argparse.ArgumentParser()
    harness.add_paper_switch_arguments(p)
    assert harness.paper_switch_kwargs(p.parse_args([])) == {}
    ns = p.parse_args(["--gate-footprint", "off", "--min-coverage", "0.5",
                       "--gate-coverage", "joint", "--errored-trial-policy", "fail"])
    assert harness.paper_switch_kwargs(ns) == {
        "gate_footprint": False, "min_coverage": 0.5, "gate_coverage": "joint",
        "errored_trial_policy": "fail"}


def test_invalid_switch_values_are_refused():
    from cap_evolve import harness
    with pytest.raises(ValueError):
        harness.pop_paper_switches({"gate_coverage": "union"})
    with pytest.raises(ValueError):
        harness.pop_paper_switches({"errored_trial_policy": "ignore"})


@pytest.mark.parametrize("alg", ["hill-climb", "skillopt", "gepa"])
def test_every_gate_algorithm_accepts_the_flags(alg):
    script = REPO / "skills" / "algorithms" / alg / "scripts" / "run.py"
    out = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True,
                         env={"PYTHONPATH": str(CORE), "PATH": "/usr/bin:/bin"}).stdout
    for flag in ("--gate-footprint", "--min-coverage", "--gate-coverage", "--errored-trial-policy",
                 "--no-regression", "--gate-max-broke", "--k-se"):
        assert flag in out, (alg, flag)


def test_cli_forwards_spec_keys_only_when_set():
    src = (CORE / "cap_evolve" / "cli.py").read_text(encoding="utf-8")
    for key, flag in (("gate_footprint", "--gate-footprint"), ("gate_min_coverage", "--min-coverage"),
                      ("gate_coverage", "--gate-coverage"),
                      ("errored_trial_policy", "--errored-trial-policy"),
                      ("gate_no_regression", "--no-regression"), ("gate_max_broke", "--gate-max-broke")):
        assert f'spec.get("{key}")' in src and f'"{flag}"' in src, key


# ---- #759: fresh-only confirmation ----------------------------------------------------------

def _write_trial(run_dir, tid, tag, k, reward):
    d = run_dir.rollouts / "val"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{tid}__{tag}__t{k}.json").write_text(json.dumps({
        "input": None, "rollout": {"task_id": tid, "cost_usd": 0.01},
        "score": {"task_id": tid, "reward": reward, "metrics": []}}))


def test_min_trial_keeps_only_fresh_trials(tmp_path):
    from cap_evolve import RunDir, harness, objectives
    from cap_evolve.splits import Splits
    rd = RunDir.create(tmp_path / ".capevolve", ts="f")
    rd.write_splits(Splits(train=[], val=["a", "b"], test=[], seed=0))
    for tid in ("a", "b"):
        for k in range(3):
            _write_trial(rd, tid, "champ", k, 1.0)    # selection-era trials: all pass
        for k in range(3, 6):
            _write_trial(rd, tid, "champ", k, 0.0)    # fresh trials: all fail
    pooled = harness.split_result_from_rollouts(rd, "champ", "val")
    fresh = harness.split_result_from_rollouts(rd, "champ", "val", min_trial=3)
    assert pooled.reward == pytest.approx(0.5) and fresh.reward == 0.0
    assert len(objectives.load_trials(rd, "champ")) == 12
    f = objectives.load_trials(rd, "champ", min_trial=3)
    assert len(f) == 6 and {t.k for t in f} == {3, 4, 5} and all(t.reward == 0.0 for t in f)


def test_act_finalize_exposes_confirm_fresh_only():
    src = (REPO / "skills" / "algorithms" / "agent-optimize" / "scripts" / "act.py").read_text()
    assert "--confirm-fresh-only" in src and "cand_min_trial=fresh_from" in src
    gc = (REPO / "skills" / "algorithms" / "agent-optimize" / "scripts" / "gate_check.py").read_text()
    assert "--candidate-min-trial" in gc


# ---- review round: one rule on both sides, planned ids, gepa, spreadsheetbench tag ------------

@pytest.fixture
def _policy_env(monkeypatch):
    monkeypatch.delenv("CAPEVOLVE_ERRORED_TRIAL_POLICY", raising=False)
    return monkeypatch


def test_env_policy_reaches_the_baseline_and_resume_reads(tmp_path, _policy_env):
    """No explicit argument anywhere: the env var alone makes seed and candidate use one rule."""
    from cap_evolve import harness
    _policy_env.setenv("CAPEVOLVE_ERRORED_TRIAL_POLICY", "fail")
    cfg = {"pass": SEED_PASS, "err_candidate": TASKS[:3]}
    adapter, run_dir, base = _setup(tmp_path, cfg)         # baseline evaluated with NO argument
    assert base.n_scored == 30                              # the 3 tagged trials count as 0.0
    assert harness.split_result_from_rollouts(run_dir, "seed", "val").n_scored == 30   # resume path
    _policy_env.delenv("CAPEVOLVE_ERRORED_TRIAL_POLICY")
    assert harness.split_result_from_rollouts(run_dir, "seed", "val").n_scored == 27


def test_fail_policy_logs_the_reclassified_count_and_warns_when_zero(tmp_path, _policy_env):
    from cap_evolve import harness
    adapter, run_dir, _ = _setup(tmp_path, {"pass": SEED_PASS})
    c = tmp_path / "c"
    c.mkdir()
    (c / "cfg.json").write_text(json.dumps({"pass": SEED_PASS, "err_infra": TASKS[:2]}))
    harness.evaluate_candidate(adapter, c, run_dir=run_dir, split="val", tag="c", errored_policy="fail")
    evs = [json.loads(l) for l in run_dir.events_path.read_text().splitlines() if l.strip()]
    ep = [e for e in evs if e.get("kind") == "errored_trial_policy"][-1]
    assert ep["reclassified_trials"] == 0 and ep["still_missing_trials"] == 2
    assert any(e.get("kind") == "gate_warning" and e.get("mode") == "errored_trial_policy" for e in evs)
    (c / "cfg.json").write_text(json.dumps({"pass": SEED_PASS, "err_candidate": TASKS[:2]}))
    harness.evaluate_candidate(adapter, c, run_dir=run_dir, split="val", tag="c2", errored_policy="fail")
    evs = [json.loads(l) for l in run_dir.events_path.read_text().splitlines() if l.strip()]
    assert [e for e in evs if e.get("kind") == "errored_trial_policy"][-1]["reclassified_trials"] == 2
    assert sum(1 for e in evs if e.get("kind") == "gate_warning" and e.get("mode") == "errored_trial_policy") == 1


def test_joint_coverage_counts_unattempted_planned_tasks():
    from cap_evolve import harness
    from cap_evolve.loop import SplitResult
    pt = lambda t: {"task_id": t, "reward": 1.0, "raw": {"valid_trials": 1, "n_trials": 1}}
    a = SplitResult("val", 1.0, 0.0, per_task=[pt(t) for t in TASKS[:10]], n_tasks=10, n_scored=10)
    b = SplitResult("val", 1.0, 0.0, per_task=[pt(t) for t in TASKS[:10]], n_tasks=10, n_scored=10)
    assert harness.joint_coverage(a, b) == 1.0                       # union of attempted: looks perfect
    assert harness.joint_coverage(a, b, TASKS) == pytest.approx(10 / 30)   # frozen val ids


def test_run_step_uses_the_frozen_planned_ids(tmp_path):
    """Both sides ran only 10 of 30 planned tasks: joint coverage must be 1/3, not 1.0."""
    cfg = {"pass": SEED_PASS, "err_infra": TASKS[10:]}
    run_dir, step = _step(tmp_path, cfg, cfg, gate_kwargs={"gate_footprint": False})
    assert _step_event(run_dir)["joint_coverage"] == pytest.approx(10 / 30, abs=1e-5)


def test_gepa_rejects_gate_footprint_true_before_spending():
    from cap_evolve import gepa
    with pytest.raises(ValueError, match="gate_footprint"):
        gepa.gepa_loop(None, run_dir=None, optimizer=None, seed_val=None,
                       gate_kwargs={"gate_footprint": True})


def test_gepa_full_val_gate_logs_the_same_statistics(tmp_path):
    from cap_evolve import gepa, harness
    adapter, run_dir, base = _setup(tmp_path, {"pass": SEED_PASS})
    w = tmp_path / "w"
    w.mkdir()
    (w / "cfg.json").write_text(json.dumps({"pass": SEED_PASS + TASKS[:2]}))
    gepa._full_val_gate(adapter, run_dir=run_dir, workdir=w, parent_result=base, cid="g1", n_trials=1,
                        gate_kwargs={"gate_coverage": "joint", "errored_trial_policy": "drop"},
                        no_regression=False, parent_id="seed")
    ev = _step_event(run_dir)
    for key in ("delta_full", "delta_masked", "se_full", "se_masked", "joint_coverage"):
        assert key in ev, key
    assert ev["delta_full"] == ev["delta_masked"]


def test_spreadsheetbench_tags_candidate_vs_infra_errors():
    src = (REPO / "templates" / "adapters" / "spreadsheetbench" / "adapter.py").read_text()
    # the candidate's own unusable template is the candidate error ...
    i = src.index("return Rollout(task_id=task.id, error=tmpl_error")
    assert '"error_kind": "candidate"' in src[i:i + 200]
    # ... and every provider / sandbox / container failure is explicitly exogenous
    assert src.count('"error_kind": "infra"') >= 4


# ---- #759 behavioural: agent-optimize finalize --------------------------------------------------

def _fin_env(monkeypatch):
    sys.path.insert(0, str(REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"))
    sys.path.insert(0, str(CORE / "tests"))
    monkeypatch.setenv("CAPEVOLVE_OPTIMIZER_COST", "off")
    for k in ("COST_GATING", "ACTIVE_EVAL"):
        monkeypatch.delenv(f"CAPEVOLVE_{k}", raising=False)


def test_finalize_confirm_fresh_only_gates_on_fresh_trials_and_records_pooled(tmp_path, capsys, monkeypatch):
    _fin_env(monkeypatch)
    import test_digest_and_act_verbs as T
    rd, project, _, val = T._run(tmp_path)
    rd.snapshot("seed", rd.candidate_dir("cur"))
    T._ledger(rd, T._h(rd, "cur"), {v: [1, 0] for v in val})
    for v in val[:2]:                                   # selection-era trials t0, t1 on disk
        for k in (0, 1):
            _write_trial(rd, v, "cur", k, 1.0)
    sh = T.Sh(**{"gate_check.py": T._gate("accept"), "run.py": (0, json.dumps({"test_reward": 0.7}), "")})
    rc, out = T._act(monkeypatch, capsys, ["finalize", "--confirm-fresh-only", *T._args(rd, project)], sh)
    assert rc == 0, out
    gates = [c for c in sh.calls if any(x.endswith("gate_check.py") for x in c)]
    assert len(gates) == 2
    assert gates[0][gates[0].index("--candidate-min-trial") + 1] == "2"     # 1 + max existing k
    assert "--candidate-min-trial" not in gates[1]                         # pooled, secondary
    c = out["result"]["confirm"]
    assert c["fresh_only"] is True and c["fresh_from_trial"] == 2 and "pooled_verdict_vs_seed" in c


def test_finalize_confirm_fresh_only_refuses_before_any_spend_when_cost_gating_off(tmp_path, capsys, monkeypatch):
    _fin_env(monkeypatch)
    import test_digest_and_act_verbs as T
    monkeypatch.setenv("CAPEVOLVE_COST_GATING", "0")
    rd, project, _, val = T._run(tmp_path)
    rd.snapshot("seed", rd.candidate_dir("cur"))
    sh = T.Sh()
    rc, out = T._act(monkeypatch, capsys, ["finalize", "--confirm-fresh-only", *T._args(rd, project)], sh)
    assert rc == 2 and "nothing was spent" in out["error"]
    assert not any("--topup-to" in c for c in sh.calls)


def test_finalize_default_is_unchanged_without_the_flag(tmp_path, capsys, monkeypatch):
    _fin_env(monkeypatch)
    import test_digest_and_act_verbs as T
    rd, project, _, val = T._run(tmp_path)
    rd.snapshot("seed", rd.candidate_dir("cur"))
    T._ledger(rd, T._h(rd, "cur"), {v: [1, 0] for v in val})
    sh = T.Sh(**{"gate_check.py": T._gate("accept"), "run.py": (0, json.dumps({"test_reward": 0.7}), "")})
    rc, out = T._act(monkeypatch, capsys, ["finalize", *T._args(rd, project)], sh)
    assert rc == 0 and out["result"]["confirm"]["fresh_only"] is False
    assert sum(any(x.endswith("gate_check.py") for x in c) for c in sh.calls) == 1


# ---- agent mode: policy comes from the run's spec when the env var is absent --------------------

def _gate_check_paired_n(run_dir, env_extra=None):
    script = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts" / "gate_check.py"
    env = {"PYTHONPATH": str(CORE), "PATH": "/usr/bin:/bin", **(env_extra or {})}   # clean: no policy env
    p = subprocess.run([sys.executable, str(script), "--run-dir", str(run_dir.root), "--candidate", "c",
                        "--current", "seed", "--mode", "paired", "--no-footprint"],
                       capture_output=True, text=True, env=env)
    return json.loads(p.stdout)["paired_n"]


def test_gate_check_in_a_clean_shell_reads_the_policy_from_the_run_spec(tmp_path, _policy_env):
    from cap_evolve import harness
    adapter, run_dir, _ = _setup(tmp_path, {"pass": SEED_PASS})
    c = tmp_path / "c"
    c.mkdir()
    (c / "cfg.json").write_text(json.dumps({"pass": SEED_PASS, "err_candidate": TASKS[:3]}))
    harness.evaluate_candidate(adapter, c, run_dir=run_dir, split="val", tag="c", errored_policy="fail")
    run_dir.snapshot("c", c)
    assert _gate_check_paired_n(run_dir) == 27                      # no spec, no env: drop
    spec = tmp_path / "capevolve.yaml"
    spec.write_text("errored_trial_policy: fail\n")
    run_dir.log_event("run_config", spec=str(spec))
    assert _gate_check_paired_n(run_dir) == 30                      # spec says fail, env unset
    assert _gate_check_paired_n(run_dir, {"CAPEVOLVE_ERRORED_TRIAL_POLICY": "drop"}) == 27   # env wins


def test_resolve_policy_precedence(tmp_path, _policy_env):
    from cap_evolve import harness
    _, run_dir, _ = _setup(tmp_path, {"pass": SEED_PASS})
    spec = tmp_path / "capevolve.yaml"
    spec.write_text("errored_trial_policy: fail\n")
    run_dir.log_event("run_config", spec=str(spec))
    assert harness.resolve_errored_policy(None, run_dir) == "fail"
    assert harness.resolve_errored_policy("drop", run_dir) == "drop"
    _policy_env.setenv("CAPEVOLVE_ERRORED_TRIAL_POLICY", "drop")
    assert harness.resolve_errored_policy(None, run_dir) == "drop"
