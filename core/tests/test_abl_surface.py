"""abl_capability surface enforcement (CAP-P / CAP-TD / CAP-TC)."""
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))

from cap_evolve import abl  # noqa: E402
from cap_evolve.abl_surface import surface_violation  # noqa: E402

TOOLS = '''"""module doc"""
import os


def alpha(x):
    """Alpha tool."""
    # a comment
    return x + 1


def beta(x):
    """Beta tool."""
    return x * 2
'''


def seed(root: Path) -> Path:
    (root / "policy").mkdir(parents=True)
    (root / "tools").mkdir()
    (root / "reference").mkdir()
    (root / "policy/policy.md").write_text("be nice\n")
    (root / "tools/tools.py").write_text(TOOLS)
    (root / "reference/ref.md").write_text("ref\n")
    return root


@pytest.fixture
def pc(tmp_path):
    p = seed(tmp_path / "parent")
    c = tmp_path / "cand"
    shutil.copytree(p, c)
    return p, c


def edit(c, rel, fn):
    f = c / rel
    f.write_text(fn(f.read_text()))


def v(arm, pc):
    return surface_violation(arm, *pc)


def test_p(pc):
    p, c = pc
    edit(c, "policy/policy.md", lambda s: s + "more\n")
    (c / "PROCESS.md").write_text("notes")
    (c / "trajectories").mkdir()
    assert v("P", pc) is None
    edit(c, "tools/tools.py", lambda s: s.replace("x + 1", "x + 2"))
    assert "tools/tools.py" in v("P", pc)


def test_p_docstring_edit_rejected(pc):
    edit(pc[1], "tools/tools.py", lambda s: s.replace("Alpha tool.", "Alpha!"))
    assert v("P", pc)


def test_td(pc):
    p, c = pc
    edit(c, "tools/tools.py", lambda s: s.replace("Alpha tool.", "Alpha, better.").replace("# a comment", "# other"))
    assert v("TD", pc) is None
    edit(c, "tools/tools.py", lambda s: s.replace("x + 1", "x + 2"))
    assert "code changed" in v("TD", pc)


def test_td_rejects_policy_and_new_function(pc):
    p, c = pc
    edit(c, "policy/policy.md", lambda s: s + "x")
    assert "policy" in v("TD", pc)
    shutil.copy(p / "policy/policy.md", c / "policy/policy.md")
    edit(c, "tools/tools.py", lambda s: s + '\ndef gamma():\n    """new"""\n')
    assert v("TD", pc)


def test_tc(pc):
    p, c = pc
    edit(c, "tools/tools.py", lambda s: s + '\ndef gamma():\n    """New."""\n    return 3\n')
    assert v("TC", pc) is None
    edit(c, "tools/tools.py", lambda s: s.replace("x + 1", "x + 5"))
    assert v("TC", pc) is None
    edit(c, "tools/tools.py", lambda s: s.split("def beta")[0])  # removed function
    assert v("TC", pc) is None
    (c / "tools/helper.py").write_text("X = 1\n")
    assert v("TC", pc) is None


def test_tc_rejects(pc):
    p, c = pc
    edit(c, "tools/tools.py", lambda s: s.replace("Beta tool.", "Changed."))
    assert "beta" in v("TC", pc)
    shutil.copy(p / "tools/tools.py", c / "tools/tools.py")
    edit(c, "policy/policy.md", lambda s: s + "x")
    assert "policy" in v("TC", pc)


def test_tc_td_syntax_error_not_surface(pc):
    edit(pc[1], "tools/tools.py", lambda s: s + "\ndef broken(:\n")
    assert v("TC", pc) is None                       # stock validation owns a broken tools.py under TC
    assert "no longer parses" in v("TD", pc)          # ... but TD must not be dodged by breaking the file
    edit(pc[1], "policy/policy.md", lambda s: s + "x")
    assert "policy" in v("TC", pc)


@pytest.mark.parametrize("arm", ["P", "TD", "TC"])
def test_reference_rejected(pc, arm):
    edit(pc[1], "reference/ref.md", lambda s: s + "x")
    assert "reference/ref.md" in v(arm, pc)
    (pc[1] / "reference/new.md").write_text("n")
    assert "new.md added" in v(arm, pc)


def test_abl_load_validation():
    assert not abl.load({}).active
    assert abl.load({"abl_capability": "TC"}).capability == "TC"
    for bad in ({"abl_capability": "X"}, {"abl_capability": "P", "abl_info": "eval"},
                {"abl_gate": "disjoint"},
                {"abl_gate": "disjoint", "abl_feedback_ids": ["a"], "abl_gate_ids": ["a"]},
                {"abl_gate": "none", "abl_gate_ids": ["a"]}):
        with pytest.raises(ValueError):
            abl.load(bad)
    c = abl.load({"abl_gate": "disjoint", "abl_feedback_ids": ["a"], "abl_gate_ids": ["b"]})
    assert c.gate_ids == ("b",)


# ---- run_step wiring -----------------------------------------------------------

def test_run_step_violation_costs_nothing(tmp_path):
    from test_capability_validation_wiring import CountingAdapter, _adapter, _fresh_run
    from cap_evolve import harness
    from cap_evolve.memory import RejectedMemory  # noqa
    adapter = CountingAdapter(_adapter())
    rd, base = _fresh_run(tmp_path, adapter, "abl")
    spec = tmp_path / "abl.yaml"
    spec.write_text("abl_capability: P\n")
    rd.log_event("spec_resolved", spec=str(spec))
    before = adapter.rollouts

    def opt(workdir, instr):
        (workdir / "scripts").mkdir(exist_ok=True)
        (workdir / "scripts/x.py").write_text("x=1\n")

    rejected, history, store = harness._init_memory_store(rd, None)
    step = harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"),
                            optimizer=opt, instructions="go", current_val=base,
                            ctx=harness.OptimizerContext(), rejected=rejected,
                            gate_kwargs={"mode": "significant", "k_se": 1.0})
    assert adapter.rollouts == before
    assert step["accepted"] is False and step["decision"]["indecisive"] is False
    assert step["candidate_val"] is None
    assert "SURFACE VIOLATION (P)" in step["decision"]["reason"]
    assert "SURFACE VIOLATION (P)" in (rd.root / "rejected.jsonl").read_text()
    evs = [json.loads(l) for l in (rd.root / "events.jsonl").read_text().splitlines() if l.strip()]
    assert any(e.get("kind") == "surface_violation" for e in evs)
    assert harness._surface_streak(rd) == 1


def test_root_level_scratch_files_are_not_capability_edits(tmp_path):
    """The harness injects INSTRUCTIONS.md (and the proposer writes DIAGNOSIS.json) at the workdir root; the
    adapter never reads them, so they must not count as a surface violation (found in the smoke, all CAP arms)."""
    import shutil
    from cap_evolve import abl_surface
    seed = tmp_path / "seed"; (seed / "policy").mkdir(parents=True); (seed / "tools").mkdir()
    (seed / "policy/policy.md").write_text("p"); (seed / "tools/tools.py").write_text('def f():\n    """d"""\n    return 1\n')
    cand = tmp_path / "cand"; shutil.copytree(seed, cand)
    for n in ("INSTRUCTIONS.md", "DIAGNOSIS.json", "NOTES.txt"):
        (cand / n).write_text("x")
    for arm in ("P", "TD", "TC"):
        assert abl_surface.surface_violation(arm, seed, cand) is None, arm
    (cand / "reference").mkdir(); (cand / "reference/x.md").write_text("y")
    assert "reference/x.md" in abl_surface.surface_violation("P", seed, cand)


# ---- review hardening (PR #890) ------------------------------------------------------------------

def _mini(tmp_path, body='def f():\n    """d"""\n    return 1\n'):
    import shutil
    seed = tmp_path / "seed"; (seed / "policy").mkdir(parents=True); (seed / "tools").mkdir()
    (seed / "policy/policy.md").write_text("p"); (seed / "tools/tools.py").write_text(body)
    cand = tmp_path / "cand"; shutil.copytree(seed, cand)
    return seed, cand


def test_tc_rejects_runtime_docstring_rewrite_and_module_docstring(tmp_path):
    from cap_evolve import abl_surface as s
    seed, cand = _mini(tmp_path)
    (cand / "tools/tools.py").write_text('def f():\n    """d"""\n    return 1\nf.__doc__ = "hacked"\n')
    assert "runtime docstring rewrite" in s.surface_violation("TC", seed, cand)
    (cand / "tools/tools.py").write_text('"""new module doc"""\ndef f():\n    """d"""\n    return 1\n')
    assert "module docstring" in s.surface_violation("TC", seed, cand)


def test_td_not_skipped_for_non_utf8_or_unparseable(tmp_path):
    from cap_evolve import abl_surface as s
    seed, cand = _mini(tmp_path, '# -*- coding: latin-1 -*-\ndef f():\n    """d \xe9"""\n    return 1\n')
    (seed / "tools/tools.py").write_bytes('# -*- coding: latin-1 -*-\ndef f():\n    """d \xe9"""\n    return 1\n'.encode("latin-1"))
    (cand / "tools/tools.py").write_bytes('# -*- coding: latin-1 -*-\ndef f():\n    """d \xe9"""\n    return 2\n'.encode("latin-1"))
    assert "code changed" in s.surface_violation("TD", seed, cand)
    (cand / "tools/tools.py").write_text("def f(:\n")
    assert s.surface_violation("TD", seed, cand)          # unparseable and different: a violation under TD


def test_symlinks_do_not_crash_the_check(tmp_path):
    import os
    from cap_evolve import abl_surface as s
    seed, cand = _mini(tmp_path)
    (cand / "reference").mkdir(); os.symlink("/nonexistent/x", cand / "reference/x")
    os.symlink(str(tmp_path), cand / "reference/d")
    for arm in ("P", "TD", "TC"):
        assert "reference/x" in s.surface_violation(arm, seed, cand)


def test_abl_load_is_case_insensitive_and_checks_tipping():
    import pytest
    from cap_evolve import abl
    assert abl.load({"abl_info": "Reward"}).info == "reward"
    assert abl.load({"abl_capability": "tc"}).capability == "TC"
    with pytest.raises(ValueError):
        abl.load({"abl_gate": "disjoint", "abl_feedback_ids": ["1"], "abl_gate_ids": ["2"], "coverage_policy": "tipping"})
    with pytest.raises(ValueError):
        abl.load({"abl_capability": "P", "abl_info": "fail"})


def test_hist_none_clean_carryover_removes_earlier_step_files(tmp_path, monkeypatch):
    from cap_evolve import abl_context
    seed = tmp_path / "cands" / "seed"; (seed / "policy").mkdir(parents=True); (seed / "tools").mkdir(); (seed / "reference").mkdir()
    wd = tmp_path / "wd"
    for d in ("policy", "tools", "reference", "notes"): (wd / d).mkdir(parents=True)
    for f in ("PROCESS.md", "DIAGNOSIS.json"): (wd / f).write_text("earlier step")
    class RD:
        root = tmp_path
        def candidate_dir(self, c): return tmp_path / "cands" / c
    monkeypatch.setattr(abl_context, "settings", lambda rd: ("none", None))
    removed = abl_context.clean_carryover(RD(), wd)
    assert set(removed) == {"PROCESS.md", "DIAGNOSIS.json", "notes"}
    assert sorted(p.name for p in wd.iterdir()) == ["policy", "reference", "tools"]
    monkeypatch.setattr(abl_context, "settings", lambda rd: (None, "reward"))
    (wd / "PROCESS.md").write_text("x")
    assert abl_context.clean_carryover(RD(), wd) == []


def test_hidden_paths_cover_per_task_state_files():
    from cap_evolve import abl_context
    for args in (("none", None), ("state", None), (None, "reward"), (None, "fail"), (None, None, "disjoint")):
        h = abl_context.hidden_paths(*args)
        assert {"baseline.json", "champion.json", "state.json", "rollouts", "native_sims"} <= set(h), args
    assert "candidates" in abl_context.hidden_paths("state", None)
