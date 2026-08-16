"""The no-regression (dual) gate rejects a mean-improving candidate that breaks a
previously-passing task (SWE-bench FAIL_TO_PASS + PASS_TO_PASS discipline)."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))


class _Adapter:
    """3 tasks A/B/C; a task passes iff the config file contains its letter."""
    def __init__(self, cfg_name="cfg.txt"):
        self.cfg = cfg_name

    def tasks(self, split):
        from cap_evolve import Task
        return [Task(id=t) for t in ("A", "B", "C")]

    def run_target(self, task, ctx, *, seed=0):
        from cap_evolve import Rollout
        candidate_dir = ctx
        cfg = (Path(candidate_dir) / self.cfg).read_text() if (Path(candidate_dir) / self.cfg).exists() else ""
        return Rollout(task_id=task.id, output=("pass" if task.id in cfg else "fail"))

    def score(self, task, rollout):
        from cap_evolve import Score
        ok = rollout.output == "pass"
        return Score(task_id=task.id, reward=1.0 if ok else 0.0, trial_rewards=[1.0 if ok else 0.0])

    def apply(self, candidate_dir, edits=None):
        return None


def test_no_regression_gate_rejects_breaking_candidate(tmp_path):
    from cap_evolve import RunDir, harness

    adapter = _Adapter()
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "cfg.txt").write_text("A")          # A passes, B & C fail -> baseline 1/3

    run_dir = RunDir.create(tmp_path / ".capevolve", ts="rg")
    # all three tasks in val so the gate sees them
    from cap_evolve.splits import Splits
    run_dir.write_splits(Splits(train=[], val=["A", "B", "C"], test=[], seed=0))
    run_dir.snapshot("seed", seed)
    run_dir.set_best("seed")

    base = harness.evaluate_candidate(adapter, run_dir.candidate_dir("seed"), run_dir=run_dir,
                                      split="val", tag="seed")
    assert abs(base.reward - 1 / 3) < 1e-9

    # optimizer rewrites cfg to "B C" -> B,C pass, A regresses. mean 2/3 > 1/3.
    opt = harness.optimizer_from_command(
        ["python3", "-c",
         "import sys,pathlib; (pathlib.Path(sys.argv[1])/'cfg.txt').write_text('B C')",
         "{workdir}"])

    # without the dual gate: accepted (mean improved)
    step1 = harness.run_step(adapter, run_dir=run_dir, parent_dir=run_dir.candidate_dir("seed"),
                             optimizer=opt, instructions="x", current_val=base,
                             gate_kwargs={"mode": "strict"})
    assert step1["accepted"] is True
    assert abs(harness.SplitResult.from_dict(step1["candidate_val"]).reward - 2 / 3) < 1e-9

    # with the dual gate: rejected because task A regressed
    step2 = harness.run_step(adapter, run_dir=run_dir, parent_dir=run_dir.candidate_dir("seed"),
                             optimizer=opt, instructions="x", current_val=base,
                             gate_kwargs={"mode": "strict"}, no_regression=True)
    assert step2["accepted"] is False
    assert "A" in step2["regressions"]


# --- agent-optimize's gate must MIRROR the harness's rule, not out-strict it ------

def _load_gate_check():
    """Import the agent-optimize skill's gate_check without a package install."""
    import importlib.util
    p = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts" / "gate_check.py"
    sys.path.insert(0, str(p.parent))
    spec = importlib.util.spec_from_file_location("_gc_under_test", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Side:
    def __init__(self, per_task):
        self.per_task = [{"task_id": t, "reward": r, "trials": [{"reward": r}]}
                         for t, r in per_task.items()]


def test_gate_check_regression_matches_the_harness_rule():
    """Both must veto only a task the parent measured-and-PASSED (reward 1.0).

    gate_check used to veto on ANY strict drop from ANY parent level, which made
    agent-optimize's gate stricter than hill-climb/gepa/skillopt -- and uniquely
    broken above 1 trial, where a reward is a fraction and the parent's is frozen
    from a single draw. A task whose true rate is 0.45 that happened to draw 4/5
    then vetoes almost any re-measurement of the SAME capability.
    """
    gc = _load_gate_check()
    from cap_evolve import harness

    # parent did NOT fully pass (0.8) and the candidate drew lower: NOT a regression.
    parent, cand = {"t1": 0.8}, {"t1": 0.6}
    assert gc.regressions(_Side(parent), _Side(cand)) == []

    # parent fully passed and the candidate dropped: that IS a regression.
    assert gc.regressions(_Side({"t1": 1.0}), _Side({"t1": 0.8})) == ["t1"]

    # equal, and improvements, never veto
    assert gc.regressions(_Side({"t1": 1.0}), _Side({"t1": 1.0})) == []
    assert gc.regressions(_Side({"t1": 0.4}), _Side({"t1": 1.0})) == []

    # The harness's rule, written out once. gate_check must agree on every
    # combination of fifths -- the reward granularity at num_trials=5.
    eps = 1e-9
    def harness_rule(par, cand):
        return sorted(t for t in cand if t in par
                      and par[t] >= 1.0 - eps and cand[t] < par[t] - eps)

    fifths = [i / 5 for i in range(6)]
    for pr in fifths:
        for cd in fifths:
            mine = gc.regressions(_Side({"t1": pr}), _Side({"t1": cd}))
            assert mine == harness_rule({"t1": pr}, {"t1": cd}), (pr, cd, mine)

    # And pin the harness source, so changing ITS rule fails here and forces the two
    # to be re-synced rather than silently diverging again.
    src = (CORE / "cap_evolve" / "harness.py").read_text()
    assert "par[t] >= 1.0 - eps and cand[t] < par[t] - eps" in src, (
        "harness's no-regression predicate changed -- re-sync "
        "skills/algorithms/agent-optimize/scripts/gate_check.py:regressions()")
    assert harness is not None      # the import is the point: keep it live


def test_a_null_edit_is_not_vetoed_just_for_redrawing_a_noisy_task():
    """The concrete failure this fixes: a byte-identical seed copy was rejected.

    Val task 8's true rate is ~0.45; the baseline drew 4/5 = 0.80. Under the old
    any-drop rule that one lucky draw vetoed all five gates in the v4 run, three of
    which were byte-identical copies of the seed.
    """
    gc = _load_gate_check()
    baseline = {"8": 0.80, "12": 0.60, "20": 0.40, "36": 1.00}
    redraw = {"8": 0.45, "12": 0.60, "20": 0.20, "36": 1.00}   # same capability, new draw
    assert gc.regressions(_Side(baseline), _Side(redraw)) == []
    # but genuinely breaking the task the parent PASSED still vetoes
    broke = dict(redraw, **{"36": 0.80})
    assert gc.regressions(_Side(baseline), _Side(broke)) == ["36"]
