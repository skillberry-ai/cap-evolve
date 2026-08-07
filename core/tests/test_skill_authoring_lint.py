"""The framework's own bundled skills pass the authoring bar it ships to users.

Guards the dogfooding lint itself, not just its verdict: the discovery must be
dynamic, the coverage-drift check must actually fire, and each promoted warning must still
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
    assert n == len(on_disk), (n, sorted(on_disk))
    assert not mod._manifest_drift(SKILLS)


def test_coverage_drift_fires_when_a_skill_disappears(tmp_path):
    """Non-vacuity: renaming/removing a skill dir must FAIL, not silently shrink
    coverage (the failure mode #189's manifest guard and #192's denylist had)."""
    root = tmp_path / "skills"
    shutil.copytree(SKILLS, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.rmtree(root / "phases" / "gate")
    out = subprocess.run([sys.executable, str(LINT), str(root)],
                         capture_output=True, text=True)
    assert out.returncode == 1, out.stdout
    assert "renamed/moved/removed" in out.stdout, out.stdout


def test_coverage_drift_fires_on_rename_away_plus_add_new(tmp_path):
    """The case a `n < MIN_SKILLS` floor could NOT see: removing one skill and adding
    another in the same commit nets to the same count. Comparing PATH SETS against the
    committed manifest catches it; comparing counts would not."""
    root = tmp_path / "skills"
    shutil.copytree(SKILLS, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.rmtree(root / "phases" / "gate")
    (root / "phases" / "newskill").mkdir()
    (root / "phases" / "newskill" / "SKILL.md").write_text(
        "---\nname: newskill\ndescription: A replacement skill. Use when proving the "
        "coverage guard sees a rename balanced by an addition.\n---\n\n# New\n\nBody.\n",
        encoding="utf-8")
    out = subprocess.run([sys.executable, str(LINT), str(root)],
                         capture_output=True, text=True)
    assert out.returncode == 1, out.stdout
    assert "phases/newskill" in out.stdout and "phases/gate" in out.stdout, out.stdout


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


def test_block_scalar_descriptions_are_actually_parsed(tmp_path):
    """`description: >-` used to parse as the literal '>-' (len 2), so EVERY
    description check — including the XML-tag hard problem — passed vacuously on
    `algorithms/evograph`. The parser must read the folded value, and the checks must
    then fire on it."""
    mod = _lint_module()
    validator = mod._load_validator(SKILLS)

    for mark, joined in ((">-", "first line second line"), ("|", "first line\nsecond line")):
        fm, body = validator._parse_frontmatter(
            f"---\nname: fixture\ndescription: {mark}\n  first line\n"
            f"  second line\ncomponent: phase\n---\n\nBody.\n")
        assert fm["description"] == joined, (mark, fm)
        assert fm["component"] == "phase", fm     # keys AFTER the block still parse
        assert body.strip() == "Body."

    cap = tmp_path / "cap"
    cap.mkdir()
    (cap / "SKILL.md").write_text(
        "---\nname: fixture\ndescription: >-\n  Does a thing. Use when proving the\n"
        "  parser reads a folded scalar. Wrap it in <X> tags.\n---\n\n# Fixture\n",
        encoding="utf-8")
    problems = validator.validate(cap)["problems"]
    assert any("XML tags" in p for p in problems), problems

    # every shipped description is really parsed, not silently truncated to a marker
    for skill_md in sorted(SKILLS.glob("*/*/SKILL.md")):
        fm, _ = validator._parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        assert len(fm.get("description", "")) > 100, (skill_md, fm.get("description"))


def test_say_when_advisory_accepts_positional_when_phrasing():
    """The advisory demanded the literal bigram 'use when', so nine descriptions that
    state WHEN positionally ('Use after intake') were false positives. Rewording them
    to green a regex would be a downgrade; the check accepts both forms instead."""
    mod = _lint_module()
    validator = mod._load_validator(SKILLS)
    for desc in ("Scores a candidate. Use when you need a number.",
                 "Establishes the starting point. Use after implement-and-check.",
                 "Applies the acceptance decision. Use to inspect one decision.",
                 "Extracts the learning signal. Use between evaluation and edits."):
        assert validator.SAYS_WHEN_RE.search(desc), desc
    assert not validator.SAYS_WHEN_RE.search("Processes documents and returns text.")


def test_long_reference_needs_a_real_toc_not_just_a_heading(tmp_path):
    """The TOC check was near-tautological: any '## ' in the first 1500 chars satisfied
    it, so a 400-line reference whose first heading is ordinary prose passed. It must
    require an actual list of anchor links."""
    mod = _lint_module()
    validator = mod._load_validator(SKILLS)
    long_body = "\n".join(f"detail line {i}" for i in range(400))

    cap = tmp_path / "noToc"
    (cap / "references").mkdir(parents=True)
    (cap / "SKILL.md").write_text(
        "---\nname: fixture\ndescription: A fixture. Use when proving the TOC check "
        "needs anchor links.\n---\n\n# F\n", encoding="utf-8")
    (cap / "references" / "long.md").write_text(
        "# Long\n\n## Just a normal first section, no TOC at all\n\n" + long_body,
        encoding="utf-8")
    assert any("table of contents" in w for w in validator.validate(cap)["warnings"])

    toc = "\n".join(f"- [Section {i}](#section-{i})" for i in range(4))
    (cap / "references" / "long.md").write_text(
        f"# Long\n\n{toc}\n\n## Section 0\n\n" + long_body, encoding="utf-8")
    assert not any("table of contents" in w for w in validator.validate(cap)["warnings"])


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
