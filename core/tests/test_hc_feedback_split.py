"""``hc_feedback_split``: the legacy hill-climb proposer learns from TRAIN, the gate decides on VAL.

With distinct train and val ids the default is ``train``: the proposer's trajectories, failure lists,
focus order, LEDGER broke/fixed and ``prior_iterations/`` come from TRAIN, every candidate is still gated
on val against its parent's val, and the proposer learns about val only the verdict and the aggregates.
Each accepted champion is measured on train once (budget-reserved); a rejected one never is. Val
rollouts are sealed outside the run tree. ``hc_feedback_split: val`` is the loop as it was.

Zero API: a deterministic adapter whose per-task outcome is looked up from the candidate's ``cfg.json``
NAME, so no task id is ever written into a candidate (a val id in a proposer's dir can only be a leak).
"""

import json
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "core"))

from cap_evolve import Budget, Rollout, RunDir, Score, Task, harness  # noqa: E402
from cap_evolve import gatecfg  # noqa: E402
from cap_evolve.splits import Splits  # noqa: E402

TR = [f"tr{i:02d}k" for i in range(8)]
VA = [f"vq{i:02d}z" for i in range(8)]
TE = [f"te{i:02d}x" for i in range(4)]

# name -> the tasks that pass under it. The candidate dir only ever holds the NAME.
PASS = {
    "seed": {*TR[:2], *VA[:2], *TE[:1]},
    "good": {*TR[:4], *VA[:6], *TE[:2]},                      # +4/8 on val: accepted
    "trade": {*TR[:6], *VA[1:8], *TE[:2]},                    # net +1/8 on val but BREAKS vq00z: vetoed
    "worse": {*TR[:1], *VA[:1]},                              # -5/8 on val: rejected
    "best": {*TR[:3], *TR[4:], *VA, *TE},                     # +2/8 on val; on train breaks tr03k
}


class Adapter:
    def __init__(self):
        self.calls = []

    def tasks(self, split):
        return [Task(id=t, input={"q": t}) for t in TR + VA + TE]

    def run_target(self, task, ctx, *, seed=0):
        name = json.loads((Path(ctx) / "cfg.json").read_text())["name"]
        self.calls.append(task.id)
        ok = task.id in PASS[name]
        return Rollout(task_id=task.id, output="pass" if ok else "fail", trace=f"agent trace for {task.id}")

    def score(self, task, rollout):
        r = 1.0 if rollout.output == "pass" else 0.0
        return Score(task_id=task.id, reward=r, trial_rewards=[r],
                     feedback="correct" if r else f"task {task.id}: wrong answer")

    def apply(self, candidate_dir, edits=None):
        return None


class Scripted:
    """Proposes the named configs in order; snapshots its whole working dir + the prompt it was given."""

    def __init__(self, names, capture):
        self.names, self.capture, self.calls = list(names), Path(capture), []

    def __call__(self, workdir, instructions):
        snap = self.capture / f"call{len(self.calls)}"
        shutil.copytree(workdir, snap)
        (snap / "__PROMPT__.txt").write_text(instructions, encoding="utf-8")
        self.calls.append({"snap": snap, "prompt": instructions})
        (Path(workdir) / "cfg.json").write_text(json.dumps({"name": self.names[len(self.calls) - 1]}))
        return None


def _setup(tmp_path, *, spec=None, max_metric_calls=0, n_trials=1, train=TR, val=VA):
    seed = tmp_path / "seed"
    seed.mkdir(parents=True, exist_ok=True)
    (seed / "cfg.json").write_text(json.dumps({"name": "seed"}))
    rd = RunDir.create(tmp_path / ".capevolve", ts="hcfb",
                       budget=Budget(max_iterations=50, max_metric_calls=max_metric_calls))
    rd.write_splits(Splits(train=list(train), val=list(val), test=list(TE), seed=7))
    if spec:
        f = tmp_path / "capevolve.yaml"
        f.write_text("".join(f"{k}: {str(v).lower() if isinstance(v, bool) else v}\n" for k, v in spec.items()))
        rd.log_event("run_config", spec=str(f))
    adapter = Adapter()
    base = harness.baseline(adapter, seed, run_dir=rd, n_trials=n_trials)
    return adapter, rd, base


def _events(rd, kind):
    return [json.loads(l) for l in rd.events_path.read_text().splitlines() if json.loads(l)["kind"] == kind]


def _leaks(root: Path, ids) -> list:
    pats = [(t, re.compile(r"(?<![A-Za-z0-9])" + re.escape(t) + r"(?![0-9])")) for t in ids]
    bad = []
    for dirpath, dirnames, files in os.walk(root):
        for name in dirnames + files:
            bad += [(os.path.join(dirpath, name), "name", t) for t, p in pats if p.search(name)]
        for name in files:
            text = Path(dirpath, name).read_text(errors="ignore")
            bad += [(os.path.join(dirpath, name), "content", t) for t, p in pats if p.search(text)]
    return bad


GATE = {"k_se": 0.2, "gate_footprint": False}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("CAPEVOLVE_HC_FEEDBACK_SPLIT", raising=False)
    monkeypatch.delenv("CAPEVOLVE_SEALED_DIR", raising=False)


# ---- resolution ---------------------------------------------------------------------------------

def test_default_is_train_when_the_train_and_val_ids_differ_and_it_is_logged(tmp_path):
    _, rd, _ = _setup(tmp_path)
    assert harness.resolve_hc_feedback_split(rd) == "train"
    ev = _events(rd, "hc_feedback_split")[-1]
    assert ev["value"] == "train" and ev["source"] == "default" and ev["requested"] == "auto"
    assert (ev["n_train"], ev["n_val"], ev["n_overlap"]) == (8, 8, 0) and ev["sealed_val"] is True
    assert json.loads(rd.state_path.read_text())["hc_feedback_split"] == "train"
    assert harness.feedback_split(rd) == "train" and harness.gate_split(rd) == "val"


def test_default_is_val_when_train_equals_val(tmp_path):
    _, rd, _ = _setup(tmp_path, train=VA, val=list(reversed(VA)))
    assert harness.resolve_hc_feedback_split(rd) == "val"
    ev = _events(rd, "hc_feedback_split")[-1]
    assert ev["value"] == "val" and ev["sealed_val"] is False
    assert rd.sealed_dir is None and harness.feedback_split(rd) == "val"


def test_an_explicit_spec_value_wins_over_the_default_and_env_wins_over_the_spec(tmp_path, monkeypatch):
    _, rd, _ = _setup(tmp_path / "a", spec={"hc_feedback_split": "val"})
    assert harness.resolve_hc_feedback_split(rd) == "val"
    assert _events(rd, "hc_feedback_split")[-1]["source"] == "spec"
    assert rd.sealed_dir is None and list((rd.root / "rollouts" / "val").glob("*.json"))

    monkeypatch.setenv("CAPEVOLVE_HC_FEEDBACK_SPLIT", "train")
    _, rd2, _ = _setup(tmp_path / "b", spec={"hc_feedback_split": "val"})
    assert harness.resolve_hc_feedback_split(rd2) == "train"
    ev = _events(rd2, "hc_feedback_split")[-1]
    assert ev["source"] == "env" and ev["requested"] == "train"


def test_the_setting_is_validated_and_train_needs_a_train_split(tmp_path):
    with pytest.raises(ValueError, match="hc_feedback_split"):
        gatecfg.GateConfig.from_mapping({"hc_feedback_split": "test"})
    assert gatecfg.hc_feedback_split_setting({}, environ={}) == ("auto", "default")
    assert gatecfg.hc_feedback_split_setting({"hc_feedback_split": "Val"}, environ={}) == ("val", "spec")
    assert gatecfg.hc_feedback_split_setting({}, {"CAPEVOLVE_HC_FEEDBACK_SPLIT": "train"}) == ("train", "env")
    _, rd, _ = _setup(tmp_path, spec={"hc_feedback_split": "train"}, train=[])
    with pytest.raises(ValueError, match="non-empty train"):
        harness.resolve_hc_feedback_split(rd)


def test_the_resolved_value_is_frozen_for_the_run(tmp_path, monkeypatch):
    _, rd, _ = _setup(tmp_path)
    assert harness.resolve_hc_feedback_split(rd) == "train"
    monkeypatch.setenv("CAPEVOLVE_HC_FEEDBACK_SPLIT", "val")
    assert harness.resolve_hc_feedback_split(rd) == "train"
    ev = _events(rd, "hc_feedback_split")[-1]
    assert ev["frozen"] is True and ev["requested"] == "val" and ev["value"] == "train"


def test_pooled_runs_do_not_use_it_and_an_explicit_train_is_a_logged_no_op(tmp_path):
    _, rd, _ = _setup(tmp_path, spec={"hc_feedback_split": "train"})
    assert harness.resolve_hc_feedback_split(rd, pooled=True) == "feedback"
    ev = _events(rd, "hc_feedback_split")[-1]
    assert ev["value"] == "feedback" and ev["ignored"] is True
    assert "hc_feedback_split" not in json.loads(rd.state_path.read_text()) and rd.sealed_dir is None
    assert harness.feedback_split(rd) == "val"


# ---- the seal -----------------------------------------------------------------------------------

def test_train_seals_the_val_rollouts_and_their_ledger_rows_but_the_framework_still_reads_them(tmp_path):
    _, rd, base = _setup(tmp_path)
    assert list((rd.root / "rollouts" / "val").glob("*__seed__t0.json"))
    harness.resolve_hc_feedback_split(rd)
    assert not (rd.root / "rollouts" / "val").exists()
    sealed = rd.rollout_dir("val")
    assert rd.sealed_dir in sealed.parents and rd.root not in sealed.parents
    assert len(list(sealed.glob("*__seed__t0.json"))) == len(VA)
    assert harness.split_result_from_rollouts(rd, "seed", "val").reward == base.reward
    assert rd.rollout_dir("train") == rd.root / "rollouts" / "train"
    run_ledger = [json.loads(l) for l in (rd.root / "eval_index.jsonl").read_text().splitlines()]
    assert run_ledger and all(r["split"] != "val" for r in run_ledger)
    assert any(json.loads(l)["split"] == "val" for l in (rd.sealed_dir / "eval_index.jsonl").read_text().splitlines())
    assert harness.resolve_hc_feedback_split(rd) == "train"          # idempotent


def test_free_text_hides_val_ids_only_where_they_are_ids(tmp_path):
    _, rd, _ = _setup(tmp_path, train=["7", "vq01zz", *TR], val=["7", "3", *VA])
    harness.resolve_hc_feedback_split(rd)
    txt = "broke ['vq00z', '3'] (fixed ['vq01z']) n=3 vq01zz tr00k 7"
    out = harness._hide_val_ids(rd, txt)
    assert "vq00z" not in out and "'3'" not in out and "'vq01z'" not in out
    assert "n=3" in out and "vq01zz" in out and "tr00k" in out and out.endswith(" 7")


# ---- the loop -----------------------------------------------------------------------------------

def _run(tmp_path, names, **kw):
    adapter, rd, base = _setup(tmp_path, **{k: kw.pop(k) for k in ("spec", "max_metric_calls", "n_trials")
                                            if k in kw})
    opt = Scripted(names, tmp_path / "captures")
    res = harness.hill_climb_loop(adapter, run_dir=rd, optimizer=opt, current_val=base,
                                  max_iterations=len(names), n_trials=kw.pop("n_trials_loop", 1),
                                  gate_kwargs=dict(GATE, **kw.pop("gate", {})), **kw)
    return rd, opt, res


def test_the_proposer_reads_train_and_the_gate_still_decides_on_val(tmp_path):
    rd, opt, res = _run(tmp_path, ["good"])
    step = res["steps"][0]
    assert step["accepted"] is True and step["candidate_val"]["split"] == "val"
    assert step["parent_val"]["split"] == "val" and step["candidate_val"]["reward"] == 0.75
    trajs = sorted(p.name for p in (opt.calls[0]["snap"] / "trajectories").iterdir())
    assert trajs == sorted(f"{t}__seed__t0.json" for t in TR)
    prompt = opt.calls[0]["prompt"]
    assert "every failing task on the train split" in prompt and "Current train reward 0.250" in prompt
    for t in TR[2:]:
        assert f"- {t} (reward 0.00)" in prompt
    assert "val reward 0.250" in prompt and "held-out VAL" in prompt
    gated = [e for e in _events(rd, "eval_start") if e["tag"] == "cand_0001"]
    assert [e["split"] for e in gated] == ["val", "train"]         # gate on val, then the champion on train


def test_no_val_task_id_reaches_the_proposer(tmp_path):
    rd, opt, res = _run(tmp_path, ["good", "trade", "worse", "best"], gate={"gate_max_broke": 0})
    assert [s["accepted"] for s in res["steps"]] == [True, False, False, True]
    assert "gate_max_broke" in res["steps"][1]["decision"]["reason"]
    assert "vq00z" in res["steps"][1]["decision"]["reason"]         # the gate's own record keeps the ids
    for call in opt.calls:                                           # what each proposer was given
        assert not _leaks(call["snap"], VA), _leaks(call["snap"], VA)[:5]
        assert any(t in call["prompt"] for t in TR)
    for work in (rd.root / "work").iterdir():                        # each working dir after its step
        assert not _leaks(work, VA), _leaks(work, VA)[:5]
    for f in (rd.rejected_path, rd.history_path, rd.root / "JOURNAL.md"):   # read via the run dir
        text = f.read_text()
        assert text and not [t for t in VA if re.search(r"(?<![A-Za-z0-9])" + t + r"(?![0-9])", text)], f
    rej = [json.loads(l) for l in rd.rejected_path.read_text().splitlines()]
    assert "gate_max_broke" in rej[0]["reason"] and "<val task>" in rej[0]["reason"]
    assert not list((rd.root / "rollouts").glob("val/*.json"))
    assert len(list(rd.rollout_dir("val").glob("*.json"))) == len(VA) * 5
    # LEDGER: an accepted step's per-task columns compare TRAIN results with the parent's train results;
    # a rejected one has the val verdict only.
    ledger = (opt.calls[3]["snap"] / "LEDGER.md").read_text()
    row = {l.split("|")[2].strip(): l for l in ledger.splitlines() if l.startswith("| ") and "cand_" in l}
    assert "{tr02k, tr03k}" in row["cand_0001"] and "ACCEPT" in row["cand_0001"]
    assert row["cand_0002"].count("—") >= 3 and row["cand_0003"].count("—") >= 3
    after = tmp_path / "ledger_after"
    after.mkdir()
    harness._build_ledger(after, rd)          # the LEDGER the next proposer would get
    last = [l for l in (after / "LEDGER.md").read_text().splitlines() if "| cand_0004 |" in l][0]
    assert "{tr03k}" in last and "{tr04k, tr05k, tr06k, tr07k}" in last and "ACCEPT" in last
    assert not _leaks(after, VA)
    # prior_iterations: only champions carry (train) trajectories
    prior = opt.calls[3]["snap"] / "prior_iterations"
    assert sorted(p.name for p in (prior / "cand_0001" / "trajectories").iterdir()) == \
        sorted(f"{t}__cand_0001__t0.json" for t in TR)
    assert not (prior / "cand_0002" / "trajectories").exists()


def test_an_accept_runs_the_champion_on_train_once_and_a_reject_never(tmp_path):
    rd, opt, res = _run(tmp_path, ["good", "worse"], n_trials=2, n_trials_loop=2)
    assert [s["accepted"] for s in res["steps"]] == [True, False]
    train_evals = [e for e in _events(rd, "eval_start") if e["split"] == "train"]
    assert [(e["tag"], e["rollouts"], e["n_trials"]) for e in train_evals] == \
        [("seed", 16, 2), ("cand_0001", len(TR) * 2, 2)]
    assert _events(rd, "champion_train")[0]["candidate"] == "cand_0001"
    assert res["steps"][0]["champion_train"]["split"] == "train"
    assert "champion_train" not in res["steps"][1]
    spent = sum(e["rollouts"] for e in _events(rd, "eval_start"))
    assert rd.spent.metric_calls == spent == 2 * (len(VA) + len(TR)) + 2 * len(VA) + 2 * len(TR) + 2 * len(VA)
    # the second proposer read the CHAMPION's train trajectories and failures
    trajs = sorted(p.name for p in (opt.calls[1]["snap"] / "trajectories").iterdir())
    assert trajs == sorted(f"{t}__cand_0001__t{k}.json" for t in TR for k in (0, 1))
    assert "Current train reward 0.500" in opt.calls[1]["prompt"]
    # finalize reuses the champion's train rollouts instead of buying them again
    payload = harness.finalize(Adapter(), run_dir=rd, best_dir=rd.candidate_dir(rd.best_id), n_trials=2,
                               baseline_dir=rd.candidate_dir("seed"))
    assert payload["best"]["train"].get("reused_rollouts") is True
    assert payload["best"]["val"]["reward"] == 0.75


def test_an_unfundable_champion_train_eval_stops_the_loop_cleanly(tmp_path):
    cap = len(VA) + len(TR) + len(VA) + len(TR) - 1          # baseline + one val gate + one short of train
    rd, opt, res = _run(tmp_path, ["good", "best"], spec={"budget_reserve": True}, max_metric_calls=cap)
    assert [s["accepted"] for s in res["steps"]] == [True]
    assert res["steps"][0].get("budget_unfunded") is True and res["steps"][0]["champion_train"] is None
    assert res["stop_reason"].startswith("budget_reserved") and res["best_val"] == 0.75
    ev = _events(rd, "champion_train_unfunded")
    assert ev and ev[0]["candidate"] == "cand_0001" and ev[0]["rollouts"] == len(TR)
    assert rd.spent.metric_calls == 2 * len(VA) + len(TR) <= cap
    assert rd.best_id == "cand_0001" and len(opt.calls) == 1
    assert not list(rd.rollout_dir("train").glob("*__cand_0001__*.json"))


def test_val_reproduces_the_old_loop(tmp_path):
    rd, opt, res = _run(tmp_path, ["good", "worse"], spec={"hc_feedback_split": "val"})
    assert [s["accepted"] for s in res["steps"]] == [True, False]
    trajs = sorted(p.name for p in (opt.calls[0]["snap"] / "trajectories").iterdir())
    assert trajs == sorted(f"{t}__seed__t0.json" for t in VA)
    prompt = opt.calls[0]["prompt"]
    assert "every failing task on the val split" in prompt and f"- {VA[2]} (reward 0.00)" in prompt
    assert not any(f"- {t} (reward" in prompt for t in TR)
    assert sorted(p.name for p in (opt.calls[1]["snap"] / "trajectories").iterdir()) == \
        sorted(f"{t}__cand_0001__t0.json" for t in VA)
    assert [e["tag"] for e in _events(rd, "eval_start") if e["split"] == "train"] == ["seed"]
    assert not _events(rd, "champion_train") and "champion_train" not in res["steps"][0]
    assert rd.sealed_dir is None and list((rd.root / "rollouts" / "val").glob("*__cand_0002__t0.json"))
    assert json.loads(rd.state_path.read_text())["hc_feedback_split"] == "val"


@pytest.mark.parametrize("focus", ["cyclic", "hardest-first"])
def test_a_narrow_focus_cycles_over_train_ids(tmp_path, focus):
    rd, opt, res = _run(tmp_path, ["worse", "worse"], focus=focus)
    for call in opt.calls:
        m = re.search(r"Focus: task (\S+)\.", call["prompt"])
        assert m and m.group(1) in TR
    if focus == "hardest-first":
        assert re.search(r"Focus: task (\S+)\.", opt.calls[0]["prompt"]).group(1) in TR[2:]


def test_a_p2_hill_climb_run_ignores_an_explicit_train_and_logs_it(tmp_path, monkeypatch):
    sys.path.insert(0, str(Path(__file__).parent))
    from p2_fakes import make_run
    monkeypatch.setenv("CAPEVOLVE_HC_FEEDBACK_SPLIT", "train")
    adapter, rd = make_run(tmp_path, n_train=12, n_val=12, default=0.4)
    base = harness.baseline_pooled(adapter, tmp_path / "seed", run_dir=rd, n_trials=2)

    def opt(workdir, instructions):
        (Path(workdir) / "cfg.json").write_text(json.dumps({"default": 0.9, "p": {}}))

    harness.hill_climb_loop(adapter, run_dir=rd, optimizer=opt, current_val=base, max_iterations=1,
                            gate_kwargs={"promotion_rule": "P2", "p2_conf_n": 48})
    ev = _events(rd, "hc_feedback_split")[-1]
    assert ev["value"] == "feedback" and ev["ignored"] is True and ev["source"] == "env"
    assert "hc_feedback_split" not in json.loads(rd.state_path.read_text())
    assert not rd.sealed_splits and harness.feedback_split(rd) == "feedback"
    assert not [e for e in _events(rd, "eval_start") if e["split"] == "train"]
