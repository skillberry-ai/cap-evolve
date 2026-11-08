"""``_find_skills_dir`` must skip a directory that is not actually a built skills
registry, not just one that exists.

A host's own ``.claude/skills/`` (or ``~/.claude/skills/``) can legitimately hold
skills unrelated to cap-evolve's own registry — editor/agent-UX skills with no
``_registry/manifest.json`` — and an ``is_dir()``-only check picked that candidate
over the real tree, then crashed downstream with "no manifest" (cap-evolve PR
#960's own ``.claude/skills/`` reproduced this against ``core/tests`` run from the
repo root).
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_candidate_without_manifest_is_never_returned(tmp_path, monkeypatch):
    """CAPEVOLVE_SKILLS_DIR unset, cwd has a manifest-less ./.claude/skills/: the
    real _find_skills_dir must fall through to the repo's own skills/, not return
    the manifest-less dir and crash later in _resolve_skills."""
    from cap_evolve import cli

    unrelated = tmp_path / ".claude" / "skills"
    unrelated.mkdir(parents=True)
    (unrelated / "some-dev-skill").mkdir()

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("CAPEVOLVE_SKILLS_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "nonexistent-home"))

    found = cli._find_skills_dir()
    assert found != unrelated, "a directory with no _registry/manifest.json must never be picked"
    # Falls through to the repo's own skills/ (cli.py lives under <repo>/core/cap_evolve/).
    assert found == REPO / "skills"
    assert (found / "_registry" / "manifest.json").is_file()
