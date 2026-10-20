"""The allow-list seal (``editable_paths``, #871) in every algorithm, not only hill-climb (#276).

What is proved here:

* ``harness.seal_manifest`` / ``check_sealed`` use the run's SEED snapshot as the one reference,
  so a branch that descends from any candidate is still checked against the seed's bytes;
* skillopt (through ``run_step``) and gepa (its own optimizer call) make a candidate that changes
  a sealed file INDECISIVE before any rollout of it, and tell the optimizer which files are which;
* hc2 drops such a proposal before the evaluator sees it;
* agent-optimize: ``act.py`` refuses propose / probe / promote of such a candidate, before any
  rollout, and ``commit.py`` refuses to ACCEPT it;
* ``cap-evolve run`` passes ``--editable-paths`` to skillopt and gepa;
* off by default everywhere: no ``editable_paths`` ⇒ nothing changes.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "examples" / "toy_calc"
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"

sys.path.insert(0, str(CORE))
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).parent))

GATE = {"mode": "significant", "k_se": 1.0}
EDITABLE = ("prompt.txt",)


@pytest.fixture(autouse=True)
def _env():
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    os.environ["CAPEVOLVE_TOY_DATA"] = str(EXAMPLE)
    yield
    os.environ.clear()
    os.environ.update(old)


def _toy_adapter():
    spec = importlib.util.spec_from_file_location("toy_calc_adapter", EXAMPLE / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Adapter()


class CountingAdapter:
    def __init__(self, inner):
        self._inner = inner
        self.rollouts = 0

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def run_target(self, task, ctx, *, seed: int = 0):
        self.rollouts += 1
        return self._inner.run_target(task, ctx, seed=seed)


def _fresh_run(tmp_path: Path, adapter, ts: str, **budget):
    """Toy capability + a FRAME file that the allow-list must seal."""
    from cap_evolve import Budget, RunDir, harness
    seed = tmp_path / ts / "seed_capability"
    shutil.copytree(EXAMPLE / "capability", seed)
    (seed / "frame.md").write_text("FIXED FRAME\n", encoding="utf-8")
    rd = RunDir.create(tmp_path / ts / ".capevolve", ts=ts,
                       budget=Budget(**({"max_iterations": 3, "stall": 3} | budget)))
    harness.ensure_splits(adapter, rd, seed=0)
    return rd, harness.baseline(adapter, seed, run_dir=rd)


def _fix_prompt(workdir: Path, instructions: str):
    p = workdir / "prompt.txt"
    p.write_text(p.read_text(encoding="utf-8") + "\n[CALC] Compute and output only the number.\n",
                 encoding="utf-8")


def _edit_frame(workdir: Path, instructions: str):
    _fix_prompt(workdir, instructions)
    p = workdir / "frame.md"
    p.unlink()
    p.write_text("I REWROTE THE FRAME\n", encoding="utf-8")


def _events(run_dir, kind):
    return [json.loads(x) for x in (run_dir.root / "events.jsonl").read_text(encoding="utf-8").splitlines()
            if x.strip() and json.loads(x).get("kind") == kind]


# --- the shared reference ----------------------------------------------------

def test_check_sealed_compares_against_the_seed_snapshot(tmp_path):
    from cap_evolve import harness
    rd, _ = _fresh_run(tmp_path, _toy_adapter(), "ref")
    cand = tmp_path / "cand"
    shutil.copytree(rd.candidate_dir("seed"), cand)
    assert harness.check_sealed(cand, rd, None) is None                    # seal off
    assert harness.check_sealed(cand, rd, EDITABLE).ok
    (cand / "prompt.txt").write_text("edited", encoding="utf-8")           # editable: fine
    (cand / "notes.md").write_text("scratch", encoding="utf-8")            # addition: fine
    assert harness.check_sealed(cand, rd, EDITABLE).ok
    (cand / "frame.md").write_text("changed", encoding="utf-8")
    rep = harness.check_sealed(cand, rd, EDITABLE)
    assert not rep.ok and rep.modified == ["frame.md"]
    (cand / "frame.md").unlink()
    assert harness.check_sealed(cand, rd, EDITABLE).removed == ["frame.md"]


def test_seal_manifest_lists_the_non_editable_seed_files(tmp_path):
    from cap_evolve import harness
    rd, _ = _fresh_run(tmp_path, _toy_adapter(), "man")
    man = harness.seal_manifest(rd, EDITABLE)
    assert "frame.md" in man["files"] and "prompt.txt" not in man["files"]
    assert harness.seal_manifest(rd, None) is None


# --- skillopt (through run_step) ---------------------------------------------

def test_skillopt_tampered_step_is_indecisive_and_costs_no_rollout(tmp_path):
    from cap_evolve import skillopt
    adapter = CountingAdapter(_toy_adapter())
    rd, base = _fresh_run(tmp_path, adapter, "so")
    seen = []

    def opt(workdir, instructions):
        seen.append(instructions)
        _edit_frame(workdir, instructions)

    before = adapter.rollouts
    res = skillopt.skillopt_loop(adapter, run_dir=rd, optimizer=opt, current_val=base, epochs=1,
                                 batch_size=2, gate_kwargs=GATE, slow_update=False, store=None,
                                 editable_patterns=EDITABLE)
    steps = [s for s in res["steps"]]
    assert steps and all(s["candidate_val"] is None for s in steps)
    assert res["best_id"] == "seed" and res["accepts"] == 0
    assert adapter.rollouts == before, "a sealed-file change must not reach a rollout"
    assert len(_events(rd, "tamper_detected")) == len(steps)
    assert all("## Editable files" in i and "`frame.md`" in i for i in seen)


def test_skillopt_clean_edit_is_measured(tmp_path):
    from cap_evolve import skillopt
    adapter = _toy_adapter()
    rd, base = _fresh_run(tmp_path, adapter, "so_ok")
    res = skillopt.skillopt_loop(adapter, run_dir=rd, optimizer=_fix_prompt, current_val=base, epochs=1,
                                 batch_size=2, gate_kwargs=GATE, slow_update=False, store=None,
                                 editable_patterns=EDITABLE)
    assert res["steps"] and res["steps"][0]["candidate_val"] is not None
    assert not _events(rd, "tamper_detected")


# --- gepa (its own optimizer call) ------------------------------------------

def test_gepa_tampered_child_never_reaches_its_minibatch_eval(tmp_path):
    from cap_evolve import gepa
    adapter = CountingAdapter(_toy_adapter())
    rd, base = _fresh_run(tmp_path, adapter, "g", max_iterations=2, max_metric_calls=500)
    seen = []

    def opt(workdir, instructions):
        seen.append(instructions)
        _edit_frame(workdir, instructions)

    res = gepa.gepa_loop(adapter, run_dir=rd, optimizer=opt, seed_val=base, max_iterations=2,
                         store=None, editable_patterns=EDITABLE)
    assert res["accepts"] == 0 and res["best_id"] == "seed"
    assert res["steps"] and all(s["candidate_val"] is None and "tamper" in s for s in res["steps"])
    written = [p.name for p in (rd.root / "rollouts").rglob("*.json")]
    assert not [n for n in written if "mb_c" in n], "no child minibatch rollout for a sealed-file change"
    assert len(_events(rd, "tamper_detected")) == len(res["steps"])
    assert rd.spent.stall == 0
    assert all("## Editable files" in i for i in seen)


def test_gepa_default_off_is_unchanged(tmp_path):
    from cap_evolve import gepa
    adapter = _toy_adapter()
    rd, base = _fresh_run(tmp_path, adapter, "g_off", max_iterations=1, max_metric_calls=500)
    seen = []

    def opt(workdir, instructions):
        seen.append(instructions)
        _edit_frame(workdir, instructions)

    res = gepa.gepa_loop(adapter, run_dir=rd, optimizer=opt, seed_val=base, max_iterations=1, store=None)
    assert not any("tamper" in s for s in res["steps"])
    assert not any("## Editable files" in i for i in seen)


# --- hc2 (K parallel proposals) ---------------------------------------------

def test_hc2_drops_a_sealed_file_change_before_the_evaluator(tmp_path):
    from test_hc2 import FakeEvaluator, _loop  # noqa: E402  (shared fakes)
    from cap_evolve import Budget, RunDir, hc2
    import test_hc2
    rd = RunDir.create(tmp_path, ts="t", budget=Budget(max_iterations=5))
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "SKILL.md").write_text("base rule one\nbase rule two\n")
    (seed / "frame.md").write_text("FIXED FRAME\n")
    rd.snapshot("seed", seed)
    rd.set_best("seed")
    for t in test_hc2.F_IDS:
        test_hc2._write(rd, "feedback", t, "seed", 0, 0.0, test_hc2.FEEDBACK[t])

    seen = []

    def opt(workdir, instructions):
        seen.append(instructions)
        n = Path(workdir).name
        (Path(workdir) / "SKILL.md").write_text(f"base rule one\nunique edit for {n}\n")
        if n.endswith("1"):                                   # one proposal also rewrites the frame
            (Path(workdir) / "frame.md").write_text("REWRITTEN\n")

    ev = FakeEvaluator()
    ev.run_dir = rd
    from cap_evolve import harness
    hc2.hc2_loop(None, run_dir=rd, optimizer=opt, evaluator=ev, params=hc2.HC2Params(k=3, per_cluster=2),
                 ctx=harness.OptimizerContext(), max_iterations=1, workers=3, editable_patterns=("SKILL.md",))
    sent = ev.opened[0]
    assert sent and not [c for c in sent if c.endswith("1")], sent
    assert [e["candidate"] for e in _events(rd, "tamper_detected")] == ["cand_0001"]
    assert all("## Editable files" in i and "`frame.md`" in i for i in seen)
    assert _loop  # the shared helper still imports (seal off path is covered by test_hc2)


# --- agent-optimize ----------------------------------------------------------

def _ao_run(tmp_path, editable=True):
    from test_round_requires_screen_ladder import _staged_run_dir
    from cap_evolve.skillcheck import seed_capability_dir
    rd, project, work = _staged_run_dir(
        tmp_path, extra='editable_paths: ["level.txt", "prompt.md"]\n' if editable else "")
    seed_src = seed_capability_dir(tmp_path / "_seed", level=12)
    (seed_src / "frame.md").write_text("FIXED FRAME\n", encoding="utf-8")
    rd.snapshot("seed", seed_src)
    for d in (rd.candidate_dir("cur"), work / "cand_1"):
        (d / "frame.md").write_text("FIXED FRAME\n", encoding="utf-8")
    return rd, project, work


def _act(monkeypatch, capsys, argv, sh):
    import act
    monkeypatch.setattr(act, "sh", sh)
    rc = act.main(argv)
    return rc, json.loads(capsys.readouterr().out)


def _args(rd, project=None):
    return ["--run-dir", str(rd.root), *(["--project", str(project)] if project else [])]


def _spec_event(rd, project):
    rd.log_event("spec_resolved", spec=str(project / "capevolve.yaml"))


def test_act_propose_and_probe_refuse_a_sealed_file_change(tmp_path, capsys, monkeypatch):
    from test_digest_and_act_verbs import Sh
    monkeypatch.setenv("CAPEVOLVE_FAILURE_CLUSTERING", "0")
    rd, project, work = _ao_run(tmp_path)
    _spec_event(rd, project)
    sh = Sh(**{"pregate.py": (0, json.dumps({"ok": True}), "")})
    rc, out = _act(monkeypatch, capsys, ["propose", "cand_1", "--parent", "cur", *_args(rd, project)], sh)
    assert rc == 0, out                                           # frame.md matches the seed

    (work / "cand_1" / "frame.md").write_text("REWRITTEN\n", encoding="utf-8")
    rc, out = _act(monkeypatch, capsys, ["propose", "cand_1", "--parent", "cur", *_args(rd, project)], sh)
    assert rc == 2 and "sealed capability file" in out["error"] and out["sealed"]["modified"] == ["frame.md"]

    sh = Sh()
    rc, out = _act(monkeypatch, capsys, ["probe", "cand_1", "--tasks", rd.read_splits().ids("val")[0],
                                         *_args(rd, project)], sh)
    assert rc == 2 and "sealed capability file" in out["error"]
    assert not [c for c in sh.calls if any("evaluate" in x for x in c)], "no rollout for a sealed-file change"
    assert _events(rd, "tamper_detected")


def test_act_first_propose_names_the_editable_and_sealed_files(tmp_path, capsys, monkeypatch):
    from test_digest_and_act_verbs import Sh
    rd, project, work = _ao_run(tmp_path)
    _spec_event(rd, project)

    def prep(cmd):
        shutil.copytree(rd.candidate_dir("cur"), rd.root / "work" / "cand_9")
        return 0, "{}", ""
    rc, out = _act(monkeypatch, capsys, ["propose", "cand_9", "--parent", "cur", *_args(rd, project)],
                   Sh(**{"prepare_candidate.py": prep}))
    assert rc == 0, out
    res = out["result"]
    assert res["editable"] == ["level.txt", "prompt.md"] and "frame.md" in res["sealed"]
    assert "edit ONLY level.txt, prompt.md" in res["next"]


def test_act_seal_off_by_default(tmp_path, capsys, monkeypatch):
    from test_digest_and_act_verbs import Sh
    monkeypatch.setenv("CAPEVOLVE_FAILURE_CLUSTERING", "0")
    rd, project, work = _ao_run(tmp_path, editable=False)
    _spec_event(rd, project)
    (work / "cand_1" / "frame.md").write_text("REWRITTEN\n", encoding="utf-8")
    rc, out = _act(monkeypatch, capsys, ["propose", "cand_1", "--parent", "cur", *_args(rd, project)],
                   __import__("test_digest_and_act_verbs").Sh(**{"pregate.py": (0, json.dumps({"ok": True}), "")}))
    assert rc == 0, out
    assert Sh  # imported for the shared fake


def test_commit_refuses_to_accept_a_sealed_file_change(tmp_path, capsys):
    import commit
    rd, project, work = _ao_run(tmp_path)
    _spec_event(rd, project)
    (work / "cand_1" / "frame.md").write_text("REWRITTEN\n", encoding="utf-8")
    best = rd.best_id
    rc = commit.main(["--run-dir", str(rd.root), "--candidate-id", "cand_1", "--from-dir",
                      str(work / "cand_1"), "--decision", "accept", "--note", "x"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 2 and "sealed capability file" in out["error"]
    from cap_evolve import RunDir
    assert RunDir.open(rd.root).best_id == best


def test_commit_refusal_helper_allows_a_clean_candidate(tmp_path):
    import commit
    rd, project, work = _ao_run(tmp_path)
    _spec_event(rd, project)
    assert commit._sealed_refusal(rd, "cand_1", work / "cand_1") is None
    (work / "cand_1" / "frame.md").unlink()
    assert commit._sealed_refusal(rd, "cand_1", work / "cand_1")["sealed"]["removed"] == ["frame.md"]


# --- cap-evolve run wiring ---------------------------------------------------

@pytest.mark.parametrize("algo", ["skillopt", "gepa", "hill-climb"])
def test_algorithm_scripts_accept_editable_paths(algo):
    import subprocess
    script = REPO / "skills" / "algorithms" / algo / "scripts" / "run.py"
    p = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True,
                       env={**os.environ, "PYTHONPATH": str(CORE)})
    assert p.returncode == 0, p.stderr[-500:]
    assert "--editable-paths" in p.stdout


def test_cli_passes_editable_paths_to_every_deterministic_loop():
    src = (CORE / "cap_evolve" / "cli.py").read_text(encoding="utf-8")
    block = src[src.index("# Allow-list seal (opt-in)"):]
    block = block[:block.index("--editable-paths")]
    assert 'algorithm_name in ("hill-climb", "skillopt", "gepa")' in block
