"""The helper gate's findings reach the optimizer, and the gate sees its fixtures, in every loop (#895 follow-up).

exp895 (issue #895) showed four ways a refusal was lost or the gate was weaker than intended. Each section
proves one fix:

* HC-2 files a helper-gate refusal where the next proposer reads it: rejected memory, the proposer's notes,
  and the "Not scored" section of LEDGER.md. Before, a refusal was a silent "dropped".
* ``helper_smoke.fixture_traces`` finds the P2 evaluator's round-tagged rollouts, so an HC-2 champion's own
  traces become smoke fixtures for its children. Before, only the seed's were found.
* The SpreadsheetBench adapter's feedback calls a candidate fault the candidate's fault. Before, every errored
  rollout said "Infrastructure error ... do not optimize against it", refusals included.
* The optimizer can run the gate itself before it submits: ``python -m cap_evolve.helper_gate``, with a config
  the framework writes into its working dir (without task ids or gold paths). Without helpers nothing changes.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "benchmarks" / "toy" / "examples" / "calc"
sys.path.insert(0, str(CORE))

CHEAT = 'def answer(task_id):\n    if task_id == "t1":\n        return 42\n    return None\n'
CLEAN = "def f(x):\n    return x\n"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("CAPEVOLVE_CORE", str(CORE))
    monkeypatch.setenv("CAPEVOLVE_TOY_DATA", str(EXAMPLE))
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    monkeypatch.delenv("CAPEVOLVE_HELPER_GATE", raising=False)


def _events(rd, kind):
    out = []
    for line in (rd.root / "events.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip() and json.loads(line).get("kind") == kind:
            out.append(json.loads(line))
    return out


def _helper(workdir, script, salt):
    cfg = json.loads((Path(workdir) / "cfg.json").read_text())
    cfg.update(default=0.85, salt=salt)                       # would win the round if it were measured
    (Path(workdir) / "cfg.json").write_text(json.dumps(cfg, indent=1))
    d = Path(workdir) / "skills" / "s" / "scripts"
    d.mkdir(parents=True, exist_ok=True)
    (Path(workdir) / "skills" / "s" / "SKILL.md").write_text("s\n")
    (d / "h.py").write_text(script)


def _hc2(tmp_path, opt, rounds):
    from p2_fakes import make_run
    from cap_evolve import evaluator, harness as h, hc2, promotion
    adapter, rd = make_run(tmp_path, n_train=24, n_val=24, default=0.4, max_metric_calls=6000)
    h.baseline_pooled(adapter, tmp_path / "seed", run_dir=rd, n_trials=2)
    params = promotion.P2Params.from_spec({"promotion_rule": "P2", "p2_conf_n": 96, "p2_ctrl_m": 4})
    ev = evaluator.P2Evaluator(adapter, rd, params)
    out = hc2.hc2_loop(adapter, run_dir=rd, optimizer=opt, evaluator=ev,
                       params=hc2.HC2Params(k=3, per_cluster=2), ctx=h.OptimizerContext(),
                       max_iterations=rounds, workers=2)
    return rd, out


# ---- HC-2: the refusal reaches the next proposer ------------------------------------------------------

def test_an_hc2_refusal_reaches_the_next_rounds_proposer(tmp_path):
    seen, prompts = [], {}

    def opt(workdir, instructions):
        seen.append(Path(workdir).name)
        prompts[Path(workdir).name] = instructions
        _helper(workdir, CHEAT, len(seen))

    rd, _ = _hc2(tmp_path, opt, rounds=2)
    refused = [e["candidate"] for e in _events(rd, "helper_gate_refused")]
    rounds = _events(rd, "hc2_round")
    assert refused and len(rounds) == 2
    first = refused[0]
    later = [c for c in rounds[1]["candidates"] if c in prompts]
    assert later, "round 2 must have run a proposer"

    # 1. filed in rejected memory with the finding
    rej = [json.loads(x) for x in Path(rd.rejected_path).read_text().splitlines() if x.strip()]
    filed = {r["candidate_id"]: r["reason"] for r in rej}
    assert first in filed and "branches on task identity" in filed[first]
    # 2. in the next proposer's prompt, with the finding (not cut before it)
    assert all("branches on task identity" in prompts[c] for c in later)
    # 3. in LEDGER.md's "Not scored" section of the next proposer's working dir
    ledger = (rd.root / "work" / later[0] / "LEDGER.md").read_text(encoding="utf-8")
    assert "Not scored" in ledger and first in ledger.split("Not scored", 1)[1]
    # still never measured, and still not counted as a rejected (measured) edit
    assert not [p for p in (rd.root / "rollouts").rglob(f"*__{first}__*")]


def test_a_diversity_drop_is_still_not_filed_as_a_rejection(tmp_path):
    # unchanged: an empty or duplicate diff is not a lesson for the proposer
    from cap_evolve import hc2
    pend = {"dropped": {"c1": "empty diff"}}
    status, reason, indecisive = hc2._status(pend, "c1", None, None, None)
    assert status == "dropped" and indecisive and reason.startswith("hc2 diversity gate")


# ---- smoke fixtures from P2's round-tagged rollouts ---------------------------------------------------

def test_fixture_traces_reads_both_rollout_namings(tmp_path):
    from cap_evolve import helper_smoke
    fb, conf = tmp_path / "feedback", tmp_path / "confirm"
    fb.mkdir(), conf.mkdir()
    want = [fb / "t1__cand_0001__t0.json",                          # run_step / baseline naming
            fb / "t2__r000__cand_0001__rung1_0__t100.json",         # P2 rung
            fb / "t3__r001__cand_0001__inc_p0_0__t7.json"]          # P2 incumbent draw
    other = [fb / "t1__cand_00012__t0.json", fb / "t2__r000__cand_00012__rung1_0__t1.json",
             fb / "t4__r000__seed__rung1_0__t1.json",
             conf / "t5__r000__cand_0001__conf_0__t1.json"]          # C is never a fixture source
    for p in want + other:
        p.write_text("{}")
    got = helper_smoke.fixture_traces(tmp_path, "cand_0001", ["feedback", "train"])
    assert got == sorted(want)


def test_an_hc2_champion_s_own_rollouts_are_its_childrens_fixtures(tmp_path):
    from cap_evolve import helper_smoke
    seen = []

    def opt(workdir, instructions):
        seen.append(Path(workdir).name)
        _helper(workdir, CLEAN, len(seen))

    rd, _ = _hc2(tmp_path, opt, rounds=1)
    champ = rd.best_id
    assert champ != "seed", "the scenario must accept a champion"
    found = helper_smoke.fixture_traces(rd.rollouts, champ, ["feedback", "train"])
    assert found and all(f"__{champ}__" in p.name for p in found)
    assert all(p.parent.name == "feedback" for p in found)


# ---- the SpreadsheetBench adapter's feedback --------------------------------------------------------------

def _sb_adapter():
    for p in (REPO / "benchmarks" / "spreadsheetbench" / "template", REPO / "benchmarks" / "_shared"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("_sb_adapter_feedback",
                                                  REPO / "benchmarks" / "spreadsheetbench" / "template" / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("meta,is_candidate", [
    ({"error_kind": "candidate", "helper_gate": "failed"}, True),
    ({"error_kind": "candidate", "helper_fault": "ZeroDivisionError in h.py"}, True),
    ({"error_kind": "infra"}, False),
    ({}, False),
])
def test_score_names_a_candidate_fault_as_the_candidates(monkeypatch, meta, is_candidate):
    mod = _sb_adapter()
    monkeypatch.delenv("CAPEVOLVE_HELPERS_SPEC", raising=False)
    task = mod.Task(id="1", input={"instruction": "", "spreadsheet_path": "", "instruction_type": "",
                                   "answer_position": "A1"})
    sc = mod.Adapter().score(task, mod.Rollout(task_id="1", error="boom", metadata=meta))
    assert sc.reward == 0.0 and "boom" in sc.feedback
    if is_candidate:
        assert "fault in the candidate" in sc.feedback and "do not optimize against it" not in sc.feedback
    else:
        assert "Infrastructure error" in sc.feedback


# ---- the optimizer's own check ------------------------------------------------------------------------------

def _cand(root, script):
    d = root / "skills" / "s" / "scripts"
    d.mkdir(parents=True, exist_ok=True)
    (root / "skills" / "s" / "SKILL.md").write_text("s\n")
    if script is not None:
        (d / "h.py").write_text(script)
    return root


def test_the_cli_says_ok_or_lists_the_findings(tmp_path, capsys):
    from cap_evolve import helper_gate
    assert helper_gate.main([str(_cand(tmp_path / "ok", CLEAN))]) == 0
    assert "helper gate: ok" in capsys.readouterr().out
    assert helper_gate.main([str(_cand(tmp_path / "bad", CHEAT))]) == 1
    out = capsys.readouterr().out
    assert "REFUSED" in out and "[helper_lint]" in out and "h.py" in out
    assert helper_gate.main([str(tmp_path / "ok"), "--config", str(tmp_path / "nope.json")]) == 2


def test_the_cli_runs_as_a_module(tmp_path):
    import subprocess
    r = subprocess.run([sys.executable, "-m", "cap_evolve.helper_gate", str(_cand(tmp_path, CHEAT))],
                       capture_output=True, text=True, env={"PYTHONPATH": str(CORE), "PATH": "/usr/bin:/bin"})
    assert r.returncode == 1 and "REFUSED" in r.stdout


def _fresh_run(tmp_path, spec_text):
    from cap_evolve import Budget, RunDir, harness
    seed = tmp_path / "seed_capability"
    import shutil
    shutil.copytree(EXAMPLE / "capability", seed)
    rd = RunDir.create(tmp_path / ".capevolve", ts="fb", budget=Budget(max_iterations=2, stall=5))
    spec = tmp_path / "capevolve.yaml"
    spec.write_text(spec_text, encoding="utf-8")
    rd.log_event("spec_resolved", spec=str(spec), project=str(tmp_path))
    return rd, seed


def test_inject_writes_the_self_check_without_what_the_optimizer_must_not_see(tmp_path):
    from cap_evolve import harness, helper_gate
    ids = tmp_path / "ids.txt"
    ids.write_text("10452\n105-24\n")
    rd, seed = _fresh_run(tmp_path, f"helpers:\n  enabled: true\n  ids_file: {ids}\n"
                                    f"  forbidden_literals: ['SECRET-ANSWER']\n  deny_roots: ['/gold']\n")
    rd.snapshot("seed", seed)
    wd = tmp_path / "work"
    wd.mkdir()
    ctx = harness.OptimizerContext()
    helper_gate.write_self_check(rd, wd)
    cfg_text = (wd / helper_gate.SELF_CHECK_CONFIG).read_text()
    cfg = json.loads(cfg_text)
    assert cfg["ids_file"] is None and cfg["task_ids"] == [] and cfg["deny_roots"] == []
    assert cfg["forbidden_literals"] == [] and "10452" not in cfg_text and "/gold" not in cfg_text
    note = ctx.augment_instructions("do the task", wd, rd)
    assert note.startswith("do the task") and "python -m cap_evolve.helper_gate" in note
    # the self-check agrees with the gate on a real finding
    _cand(wd, CHEAT)
    assert helper_gate.main([str(wd), "--config", str(wd / helper_gate.SELF_CHECK_CONFIG)]) == 1


def test_the_self_check_config_is_not_part_of_the_candidate(tmp_path):
    from cap_evolve import harness, helper_gate
    rd, seed = _fresh_run(tmp_path, "helpers:\n  enabled: true\n")
    wd = tmp_path / "work"
    _cand(wd, CLEAN)
    helper_gate.write_self_check(rd, wd)
    rd.snapshot("cand_x", wd, ignore=harness._SNAPSHOT_IGNORE)
    assert not (rd.candidate_dir("cand_x") / helper_gate.SELF_CHECK_CONFIG).exists()
    assert (rd.candidate_dir("cand_x") / "skills" / "s" / "scripts" / "h.py").exists()


def test_without_helpers_nothing_is_written_and_the_instructions_are_unchanged(tmp_path, monkeypatch):
    from cap_evolve import harness, helper_gate
    monkeypatch.delenv("CAPEVOLVE_HELPERS", raising=False)
    rd, _ = _fresh_run(tmp_path, "helpers:\n  enabled: false\n")
    wd = tmp_path / "work"
    wd.mkdir()
    assert helper_gate.write_self_check(rd, wd) is False
    assert not (wd / "guidance").exists()
    ctx = harness.OptimizerContext()
    plain = harness.resolve_memory(ctx.memory_skill).augment_instructions("do the task", wd, rd)
    assert ctx.augment_instructions("do the task", wd, rd) == plain


def test_with_the_gate_off_nothing_is_written(tmp_path):
    from cap_evolve import helper_gate
    rd, _ = _fresh_run(tmp_path, "helpers:\n  enabled: true\n  gate: false\n")
    wd = tmp_path / "work"
    wd.mkdir()
    assert helper_gate.write_self_check(rd, wd) is False
