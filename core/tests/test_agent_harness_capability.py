"""Wiring proofs for the ``agent-harness`` capability.

The handlers are smoke-tested by the skill's own ``scripts/check.py``; this file proves
the capability is reachable from the optimization loop the same way the other
capabilities are:

* ``harness._capability_is_empty`` sees an empty dir as an empty seed and a dir with
  settings as non-empty;
* ``harness._capability_validate`` voids a candidate whose memory is written during a
  scored rollout, or whose lessons cite the sealed test split, and passes a clean one;
* a problem the parent already had is not blamed on the edit;
* the optimizer brief names the capability's edit space and points at its SKILL.md.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
SKILL = REPO / "skills" / "capabilities" / "agent-harness"
sys.path.insert(0, str(CORE))

CAPS = ["agent-harness"]
LESSON = {"id": "confirm-write", "when": "after a write tool call",
          "do": "read the record back and compare each requested field",
          "evidence": "train: 3 traces reported success after a wrong write",
          "source_split": "train"}


@pytest.fixture(autouse=True)
def _env():
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    os.environ["CAPEVOLVE_SKILLS_DIR"] = str(REPO / "skills")
    yield
    os.environ.clear()
    os.environ.update(old)


def _write(d: Path, cfg: dict, lessons=()):
    d.mkdir(parents=True, exist_ok=True)
    (d / "harness.json").write_text(json.dumps(cfg), encoding="utf-8")
    if lessons:
        (d / "memory").mkdir(exist_ok=True)
        (d / "memory" / "lessons.jsonl").write_text(
            "".join(json.dumps(x) + "\n" for x in lessons), encoding="utf-8")
    return d


def test_skill_check_is_green():
    r = subprocess.run([sys.executable, str(SKILL / "scripts" / "check.py")],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(r.stdout)["ok"] is True


def test_empty_seed_detection(tmp_path):
    from cap_evolve import harness
    empty = tmp_path / "empty"
    empty.mkdir()
    assert harness._capability_is_empty(CAPS, empty) is True
    full = _write(tmp_path / "full", {"loop": {"max_steps": 20}})
    assert harness._capability_is_empty(CAPS, full) is False


def test_clean_candidate_validates(tmp_path):
    from cap_evolve import harness
    cand = _write(tmp_path / "c", {"memory": {"mode": "all", "max_entries": 10}}, [LESSON])
    rep = harness._capability_validate(CAPS, cand)
    assert rep is not None and not rep.problems, rep.problems


@pytest.mark.parametrize("cfg,lessons,needle", [
    ({"memory": {"mode": "all", "write_during_eval": True}}, [LESSON], "write_during_eval"),
    ({"memory": {"mode": "all"}}, [{**LESSON, "source_split": "test"}], "sealed test"),
    ({"memory": {"mode": "all", "max_entries": 1}},
     [LESSON, {**LESSON, "id": "other", "do": "different rule"}], "max_entries"),
    ({"sampling": {"temperature": 9}}, [], "outside"),
    ({"memory": {"path": "../outside.jsonl"}}, [], "relative path"),
])
def test_invalid_candidate_is_reported(tmp_path, cfg, lessons, needle):
    from cap_evolve import harness
    cand = _write(tmp_path / "c", cfg, lessons)
    rep = harness._capability_validate(CAPS, cand)
    assert rep is not None
    assert any(needle in p for p in rep.problems), rep.problems


def test_problem_the_parent_had_is_not_blamed_on_the_edit(tmp_path):
    from cap_evolve import harness
    bad = {"memory": {"mode": "all", "write_during_eval": True}}
    parent = _write(tmp_path / "parent", bad)
    cand = _write(tmp_path / "cand", {**bad, "loop": {"max_steps": 40}})
    rep = harness._capability_validate(CAPS, cand, parent_dir=parent)
    assert rep is not None and not rep.problems, rep.problems


def test_optimizer_brief_names_the_edit_space():
    from cap_evolve import harness
    brief = harness._capability_brief(CAPS)
    assert "agent-harness" in brief
    assert "./guidance/agent-harness/SKILL.md" in brief
    assert "read-only while a rollout is scored" in brief
