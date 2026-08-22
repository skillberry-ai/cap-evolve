"""The skill authoring lint itself is under test, not merely its verdict.

Two halves:

1. **Rule table.** A known-good fixture skill must pass every rule, and one
   deliberately-broken fixture per rule must fail with a message that names the
   problem. Without this, a reworded or accidentally-dead check turns the lint into
   a silent no-op and nobody notices.
2. **Lint plumbing.** Discovery must stay dynamic, the coverage-drift guard must
   fire, every PROMOTED fragment must be reachable from a real violation, and the
   baseline must suppress exactly the known lines and nothing else.
"""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / "skills"
LINT = SKILLS / "_registry" / "lint_skills.py"
BASELINE = SKILLS / "_registry" / "authoring-baseline.txt"

GOOD_DESC = ("Extracts tabular data from spreadsheets and writes a tidy CSV. Use when "
             "the user has an xlsx/csv and wants columns reshaped, filtered, or joined.")


def _lint_module():
    spec = importlib.util.spec_from_file_location("lint_skills", LINT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def validator():
    return _lint_module()._load_validator(SKILLS)


def _skill(tmp: Path, *, name="fixture-skill", desc=GOOD_DESC, body="# Fixture\n\nDo the thing.\n",
           refs: dict[str, str] | None = None, frontmatter: str | None = None) -> Path:
    """Write one skill package and return its directory."""
    cap = tmp / "cap"
    cap.mkdir(parents=True, exist_ok=True)
    fm = frontmatter if frontmatter is not None else f"name: {name}\ndescription: {desc}"
    (cap / "SKILL.md").write_text(f"---\n{fm}\n---\n\n{body}", encoding="utf-8")
    for rel, text in (refs or {}).items():
        target = cap / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return cap


def _lines(n: int, prefix: str = "Line") -> str:
    return "\n".join(f"{prefix} {i} of prose that carries no real weight." for i in range(n))


def _long_ref_without_toc(n: int = 400) -> str:
    return "# Long reference\n\n## An ordinary first section, not a TOC\n\n" + _lines(n)


def _long_ref_with_toc(n: int = 400) -> str:
    toc = "\n".join(f"- [Section {i}](#section-{i})" for i in range(4))
    return f"# Long reference\n\n{toc}\n\n## Section 0\n\n" + _lines(n)


# (rule id, kwargs for _skill, expected fragment, hard problem or warning)
BROKEN = [
    ("name-missing", dict(frontmatter=f"description: {GOOD_DESC}"),
     "missing 'name'", "problems"),
    ("name-too-long", dict(name="a" * 65), "must be <=64 chars", "problems"),
    ("name-bad-charset", dict(name="Fixture_Skill"), "lowercase [a-z0-9-]", "problems"),
    ("name-xml", dict(frontmatter=f'name: "<x>fixture</x>"\ndescription: {GOOD_DESC}'),
     "name must not contain XML tags", "problems"),
    ("desc-missing", dict(frontmatter="name: fixture-skill"),
     "missing a non-empty 'description'", "problems"),
    ("desc-empty", dict(frontmatter='name: fixture-skill\ndescription: ""'),
     "missing a non-empty 'description'", "problems"),
    ("desc-too-long", dict(desc="Reshapes data. Use when asked. " + "x" * 1024),
     "chars (>1024)", "problems"),
    ("desc-xml", dict(desc="Routes <phase> requests. Use when the user names a phase."),
     "description must not contain XML tags", "problems"),
    ("desc-no-when-clause", dict(desc="Processes documents and returns extracted text."),
     "should say WHEN to use the skill", "warnings"),
    ("body-over-500-lines", dict(body="# Fixture\n\n" + _lines(600)),
     "lines (>500)", "warnings"),
    ("reference-nested-dir", dict(refs={"references/deep/inner.md": "# Inner\n"}),
     "level deep", "warnings"),
    ("reference-links-reference",
     dict(refs={"references/a.md": "# A\n\nSee [b](b.md).\n", "references/b.md": "# B\n"}),
     "references must be one level deep", "warnings"),
    ("long-reference-without-toc", dict(refs={"references/long.md": _long_ref_without_toc()}),
     "table of contents", "warnings"),
    ("broken-link-from-body", dict(body="# Fixture\n\nSee [gone](references/gone.md).\n"),
     "'references/gone.md' which does not exist", "warnings"),
    ("broken-link-from-reference",
     dict(refs={"references/a.md": "# A\n\nSee [script](../scripts/gone.py).\n"}),
     "does not exist", "warnings"),
]


def test_a_well_formed_skill_passes_every_rule(tmp_path, validator):
    """The known-good fixture exercises every rule's happy path: a long reference WITH
    a TOC, a reference linked only from SKILL.md, and a live relative link."""
    cap = _skill(
        tmp_path,
        body=("# Fixture\n\nDo the thing.\n\n"
              "Read [the long reference](references/long.md) for the details, and "
              "[the short one](references/short.md#a-heading) for the summary.\n"),
        refs={"references/long.md": _long_ref_with_toc(),
              "references/short.md": "# Short\n\n## A heading\n\nSummary.\n"},
    )
    v = validator.validate(cap)
    assert v == {"ok": True, "name": "fixture-skill", "problems": [], "warnings": []}


@pytest.mark.parametrize("rule,kwargs,fragment,bucket",
                         BROKEN, ids=[b[0] for b in BROKEN])
def test_each_broken_fixture_fails_its_rule(tmp_path, validator, rule, kwargs, fragment, bucket):
    v = validator.validate(_skill(tmp_path, **kwargs))
    found = v[bucket]
    assert any(fragment in m for m in found), (rule, fragment, v)
    if bucket == "problems":
        assert not v["ok"], (rule, v)


STRUCTURAL = [b for b in BROKEN
              if b[3] == "warnings" and b[0] != "desc-no-when-clause"]


@pytest.mark.parametrize("rule,kwargs,fragment,bucket", STRUCTURAL,
                         ids=[b[0] for b in STRUCTURAL])
def test_structural_warnings_are_promoted_to_lint_errors(rule, kwargs, fragment, bucket):
    """`validate()` keeps structural findings as warnings so a mid-run optimizer is not
    hard-blocked by a style budget; the repo's own lint promotes them to errors. If
    abstract.py rewords one, PROMOTED stops matching and the lint silently goes blind —
    so the promotion is asserted per rule, not just in aggregate."""
    mod = _lint_module()
    assert any(frag in fragment for frag in mod.PROMOTED), (rule, fragment, mod.PROMOTED)


def test_the_when_clause_advisory_stays_advisory():
    """Judgement calls are reported, never failed: "say WHEN" is a heuristic on prose,
    so it must not be promoted into a build-breaking error."""
    mod = _lint_module()
    assert not any(frag in "should say WHEN to use the skill" for frag in mod.PROMOTED)


def _repo_skills_copy(tmp_path: Path) -> Path:
    root = tmp_path / "skills"
    shutil.copytree(SKILLS, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return root


def _run(root: Path, *args: str):
    return subprocess.run([sys.executable, str(LINT), str(root), *args],
                          capture_output=True, text=True)


def test_the_repo_is_clean_against_its_recorded_baseline():
    """Report-only mode: every violation on the tree today is recorded, so CI reports
    the list without going red. A NEW violation is not in the baseline and fails."""
    out = _run(SKILLS, "--baseline")
    assert out.returncode == 0, out.stdout + out.stderr
    assert "no violations outside the baseline" in out.stdout, out.stdout


def test_the_baseline_matches_the_tree_exactly():
    """A baseline that drifts stale is worse than none: it would mask a real regression
    or nag about violations already fixed."""
    mod = _lint_module()
    errors, _, _ = mod.lint(SKILLS)
    assert mod._flatten(errors) == [
        ln for ln in BASELINE.read_text(encoding="utf-8").splitlines() if ln.strip()
    ], "regenerate with: python skills/_registry/lint_skills.py skills --write-baseline"


def test_a_new_violation_fails_even_with_the_baseline(tmp_path):
    root = _repo_skills_copy(tmp_path)
    (root / "phases" / "gate" / "SKILL.md").write_text(
        f"---\nname: gate\ndescription: {GOOD_DESC}\n---\n\n# Gate\n\n" + _lines(600),
        encoding="utf-8")
    out = _run(root, f"--baseline={BASELINE}")
    assert out.returncode == 1, out.stdout
    assert "phases/gate" in out.stdout and "lines (>500)" in out.stdout, out.stdout


def test_a_fixed_baselined_violation_is_reported_as_stale(tmp_path):
    root = _repo_skills_copy(tmp_path)
    tools = root / "capabilities" / "tools" / "SKILL.md"
    head, _, _ = tools.read_text(encoding="utf-8").partition("\n---\n")
    tools.write_text(head + "\n---\n\n# Tools\n\nShort body now.\n", encoding="utf-8")
    out = _run(root, f"--baseline={BASELINE}")
    assert "are now FIXED" in out.stdout and "capabilities/tools" in out.stdout, out.stdout


def test_discovery_is_dynamic_and_sees_every_skill():
    """The lint globs; it never reads a committed list that could go stale."""
    mod = _lint_module()
    on_disk = {p.parent.relative_to(SKILLS).as_posix() for p in SKILLS.glob("*/*/SKILL.md")}
    _, _, n = mod.lint(SKILLS)
    assert n == len(on_disk), (n, sorted(on_disk))
    assert not mod._manifest_drift(SKILLS)


def test_coverage_drift_fires_on_rename_away_plus_add_new(tmp_path):
    """Non-vacuity: removing one skill and adding another in the same commit nets to the
    same count, so a `n < MIN_SKILLS` floor would miss it. Comparing PATH SETS against
    the committed manifest catches it, and needs no magic number."""
    root = _repo_skills_copy(tmp_path)
    shutil.rmtree(root / "phases" / "gate")
    replacement = root / "phases" / "newskill"
    replacement.mkdir()
    (replacement / "SKILL.md").write_text(
        f"---\nname: newskill\ndescription: {GOOD_DESC}\n---\n\n# New\n\nBody.\n",
        encoding="utf-8")
    out = _run(root, f"--baseline={BASELINE}")
    assert out.returncode == 1, out.stdout
    assert "renamed/moved/removed" in out.stdout, out.stdout
    assert "phases/gate" in out.stdout, out.stdout


def test_block_scalar_descriptions_are_actually_parsed(tmp_path, validator):
    """`description: >-` used to parse as the literal '>-' (len 2), so EVERY description
    check — including the XML-tag hard problem — passed vacuously on it. The parser must
    read the folded value, and the checks must then fire on it."""
    for mark, joined in ((">-", "first line second line"), ("|", "first line\nsecond line")):
        fm, body = validator._parse_frontmatter(
            f"---\nname: fixture\ndescription: {mark}\n  first line\n"
            f"  second line\ncomponent: phase\n---\n\nBody.\n")
        assert fm["description"] == joined, (mark, fm)
        assert fm["component"] == "phase", fm     # keys AFTER the block still parse
        assert body.strip() == "Body."

    cap = _skill(tmp_path, frontmatter=("name: fixture\ndescription: >-\n"
                                        "  Does a thing. Use when proving the parser reads a\n"
                                        "  folded scalar. Wrap it in <X> tags."))
    assert any("XML tags" in p for p in validator.validate(cap)["problems"])

    # every shipped description is really parsed, not silently truncated to a marker
    for skill_md in sorted(SKILLS.glob("*/*/SKILL.md")):
        fm, _ = validator._parse_frontmatter(skill_md.read_text(encoding="utf-8"))
        assert len(fm.get("description", "")) > 100, (skill_md, fm.get("description"))


def test_an_anchor_in_a_link_is_not_part_of_the_path(tmp_path, validator):
    """`references/x.md#a-heading` used to be existence-checked verbatim, so every deep
    link read as broken — a false positive on a correct skill."""
    cap = _skill(tmp_path, body="# F\n\nSee [detail](references/x.md#deep-heading).\n",
                 refs={"references/x.md": "# X\n\n## Deep heading\n\nDetail.\n"})
    assert validator.validate(cap)["warnings"] == []


def test_say_when_advisory_accepts_positional_when_phrasing(validator):
    """The advisory demanded the literal bigram 'use when', so descriptions that state
    WHEN positionally ('Use after intake') were false positives. Rewording good prose to
    green a regex would be a downgrade; the check accepts both forms instead."""
    for desc in ("Scores a candidate. Use when you need a number.",
                 "Establishes the starting point. Use after implement-and-check.",
                 "Applies the acceptance decision. Use to inspect one decision.",
                 "Extracts the learning signal. Use between evaluation and edits."):
        assert validator.SAYS_WHEN_RE.search(desc), desc
    assert not validator.SAYS_WHEN_RE.search("Processes documents and returns text.")


def test_promoted_fragments_still_match_the_validators_wording(tmp_path, validator):
    """Each PROMOTED fragment must be reachable from a real violation. If abstract.py
    rewords a warning, this fails loudly rather than the lint quietly going blind."""
    mod = _lint_module()
    cap = _skill(
        tmp_path,
        body="# F\n\n" + _lines(1400) + "\n\nSee [gone](references/gone.md).\n",
        refs={"references/long.md": _long_ref_without_toc(),
              "references/a.md": "# A\n\nSee [long](long.md).\n",
              "references/nested/deep.md": "# Deep\n"},
    )
    warnings = validator.validate(cap)["warnings"]
    for frag in mod.PROMOTED:
        assert any(frag in w for w in warnings), (frag, warnings)
