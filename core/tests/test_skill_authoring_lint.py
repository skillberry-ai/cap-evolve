"""The framework's own bundled skills pass the authoring bar it ships to users.

Guards the dogfooding lint itself, not just its verdict: the discovery must be
dynamic, the count floor must actually fire, and each promoted warning must still
be reachable — so a reworded message in `skill-package/scripts/abstract.py` breaks a
test instead of silently turning a lint error back into a no-op.
"""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / "skills"
LINT = SKILLS / "_registry" / "lint_skills.py"


def _lint_module():
    spec = importlib.util.spec_from_file_location("lint_skills", LINT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_bundled_skills_pass_the_authoring_bar():
    out = subprocess.run([sys.executable, str(LINT), str(SKILLS)],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    assert "ERROR" not in out.stdout, out.stdout


def test_discovery_is_dynamic_and_sees_every_skill():
    """The lint globs; it never reads a committed list that could go stale."""
    mod = _lint_module()
    on_disk = {p.parent.relative_to(SKILLS).as_posix()
               for p in SKILLS.glob("*/*/SKILL.md")}
    _, _, n = mod.lint(SKILLS)
    assert n == len(on_disk) >= mod.MIN_SKILLS, (n, sorted(on_disk))


def test_count_floor_fires_when_a_skill_disappears(tmp_path):
    """Non-vacuity: renaming/removing a skill dir must FAIL, not silently shrink
    coverage (the failure mode #189's manifest guard and #192's denylist had)."""
    root = tmp_path / "skills"
    shutil.copytree(SKILLS, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.rmtree(root / "phases" / "gate")
    out = subprocess.run([sys.executable, str(LINT), str(root)],
                         capture_output=True, text=True)
    assert out.returncode == 1, out.stdout
    assert "lint coverage" in out.stdout, out.stdout


def _oversized_body(n_lines: int = 600) -> str:
    filler = "\n".join(f"Line {i} of deliberately verbose body prose." for i in range(n_lines))
    return ("---\nname: fixture-skill\ndescription: A fixture skill. Use when "
            "proving the lint fails a body over the bar.\n---\n\n# Fixture\n\n" + filler)


def test_an_oversized_body_fails_the_lint(tmp_path):
    root = tmp_path / "skills"
    shutil.copytree(SKILLS, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (root / "phases" / "fixture-skill").mkdir()
    (root / "phases" / "fixture-skill" / "SKILL.md").write_text(_oversized_body(),
                                                                encoding="utf-8")
    out = subprocess.run([sys.executable, str(LINT), str(root)],
                         capture_output=True, text=True)
    assert out.returncode == 1, out.stdout
    assert "phases/fixture-skill" in out.stdout and "lines (>" in out.stdout, out.stdout


def test_an_empty_placeholder_reference_fails_the_lint(tmp_path):
    """CONTRIBUTING: references count only when FILLED."""
    root = tmp_path / "skills"
    shutil.copytree(SKILLS, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    refs = root / "phases" / "gate" / "references"
    (refs / "stub.md").write_text("# Stub\n\nTODO: write this.\n", encoding="utf-8")
    out = subprocess.run([sys.executable, str(LINT), str(root)],
                         capture_output=True, text=True)
    assert out.returncode == 1, out.stdout
    assert "stub.md" in out.stdout, out.stdout


def test_promoted_fragments_still_match_the_validators_wording(tmp_path):
    """Each PROMOTED fragment must be reachable from a real violation. If abstract.py
    rewords a warning, this fails loudly rather than the lint quietly going blind."""
    mod = _lint_module()
    validator = mod._load_validator(SKILLS)
    cap = tmp_path / "cap"
    (cap / "references" / "nested").mkdir(parents=True)
    (cap / "SKILL.md").write_text(
        _oversized_body(1400) + "\n\nSee [gone](references/gone.md).\n", encoding="utf-8")
    long_ref = "\n".join(f"detail line {i}" for i in range(400))
    (cap / "references" / "long.md").write_text("# Long\n" + long_ref, encoding="utf-8")
    (cap / "references" / "nested" / "deep.md").write_text("# Deep\n", encoding="utf-8")

    warnings = validator.validate(cap)["warnings"]
    for frag in mod.PROMOTED:
        assert any(frag in w for w in warnings), (frag, warnings)
