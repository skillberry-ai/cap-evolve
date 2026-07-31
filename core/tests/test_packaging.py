"""The published distribution can actually run — version and data files.

Two failure modes this guards, both of which look fine in a checkout:

1. **Version drift.** ``cap_evolve.__version__`` is the single source of truth
   (``pyproject.toml`` reads it via ``[tool.setuptools.dynamic]``). ``CITATION.cff``
   is machine-read metadata that must agree, and it silently did not (#186).
2. **A wheel with no data.** ``skills/`` and ``templates/`` are runtime data, not
   docs: without them a pip install cannot resolve the manifest, read
   ``optimizers/registry.yaml``, or scaffold a project. That is #193's
   ``install.sh`` hole in pip shape. The wheel gets them from
   ``cap_evolve/_bundled/{skills,templates}`` — symlinks to the repo trees — and
   ``resource_root()`` picks whichever of the two is real.

Building a wheel here would need network + a build backend, so the artifact itself is
asserted in ``.github/workflows/release.yml``. These tests cover what is checkable
offline: the declarations that make the artifact correct, and the resolver that reads it.
"""

import re
from pathlib import Path

import cap_evolve
from cap_evolve.resources import resource_root

REPO = Path(__file__).resolve().parents[2]
PYPROJECT = (REPO / "core" / "pyproject.toml").read_text(encoding="utf-8")


def test_version_is_single_sourced():
    """pyproject reads __version__ dynamically — no second literal to forget."""
    assert 'dynamic = ["version"]' in PYPROJECT
    assert 'version = { attr = "cap_evolve.__version__" }' in PYPROJECT
    assert not re.search(r'^version = "', PYPROJECT, re.M), "hardcoded version in pyproject"


def test_citation_version_and_date_match_the_release():
    cff = (REPO / "CITATION.cff").read_text(encoding="utf-8")
    assert re.search(rf"^version: {re.escape(cap_evolve.__version__)}$", cff, re.M), (
        f"CITATION.cff version != cap_evolve.__version__ ({cap_evolve.__version__})")
    # v0.1.0's GitHub release publishedAt. A future release bumps both together.
    assert re.search(r"^date-released: 2026-07-27$", cff, re.M)


def test_distribution_name_is_cap_evolve():
    """The pip name users are told to type (#125), not the old cap-evolve-core."""
    assert 'name = "cap-evolve"' in PYPROJECT
    assert 'cap-evolve = "cap_evolve.cli:main"' in PYPROJECT


def test_runtime_data_is_declared_as_package_data():
    for pattern in ("_bundled/skills/**/*", "_bundled/templates/**/*"):
        assert pattern in PYPROJECT, f"{pattern} not in package-data — a wheel would ship no {pattern.split('/')[1]}"


# The surfaces where a `pip install` line is PUBLISHED rather than merely written down:
# core/README.md is rendered as the PyPI project page, docs/INSTALL.md is the doc it
# points at. A `pip install 'cap-evolve[x]'` there must name an extra that
# pyproject.toml actually declares — `[dashboard]` named `capevolve-dashboard`, which is
# 404 on PyPI and published by no workflow, and extras bake into the wheel METADATA
# where they cannot be corrected after a publish. #214 does this for documented CLI
# commands; this is the same idea for documented installs.
PUBLISHED_INSTALL_DOCS = ("core/README.md", "docs/INSTALL.md")


def test_documented_pip_installs_can_resolve():
    declared = set(re.findall(r"^(\w[\w.-]*) = \[", PYPROJECT.split("[project.optional-dependencies]")[1]
                              .split("\n[")[0], re.M))
    for rel in PUBLISHED_INSTALL_DOCS:
        text = (REPO / rel).read_text(encoding="utf-8")
        for name, extra in re.findall(r"pip install '?([A-Za-z][\w.-]*)\[([\w,-]+)\]'?", text):
            assert name == "cap-evolve", f"{rel}: extras documented for unknown dist {name}"
            for e in extra.split(","):
                assert e in declared, (
                    f"{rel} documents `pip install '{name}[{e}]'` but pyproject declares no "
                    f"[{e}] extra (declared: {sorted(declared)}) — that install cannot resolve")
        # A bare `pip install <name>` must be this dist or a local path, not an unpublished sibling.
        for name in re.findall(r"pip install (?:--[\w-]+ )*([A-Za-z][\w.-]*)\s*$", text, re.M):
            assert name == "cap-evolve", f"{rel}: `pip install {name}` names a dist this repo does not publish"


def test_pypi_page_counts_match_the_repo():
    """core/README.md is the rendered PyPI page — a stale count there is *published*.

    #189's counts guard covers ``README.md``/``llms.txt``/the site, not this file. The
    3-exec + 2-agent split is left to #189's own rule; these three are mechanical.
    """
    readme = (REPO / "core" / "README.md").read_text(encoding="utf-8")
    import yaml  # noqa: PLC0415 — dev-only, not a runtime dep

    actual = {
        "skills": len(list(REPO.glob("skills/*/*/SKILL.md"))),
        "algorithms": len([p for p in (REPO / "skills" / "algorithms").iterdir() if p.is_dir()]),
        "optimizers": len(yaml.safe_load(
            (REPO / "skills" / "optimizers" / "registry.yaml").read_text(encoding="utf-8"))),
    }
    for key, pattern in (("skills", r"\*\*(\d+) Agent\s*\n?Skills\*\*"),
                         ("algorithms", r"\*\*(\d+) algorithms\*\*"),
                         ("optimizers", r"\*\*(\d+) optimizer backends\*\*")):
        m = re.search(pattern, readme)
        assert m, f"core/README.md: no {key} count matching {pattern!r} — did the wording change?"
        assert int(m.group(1)) == actual[key], (
            f"core/README.md (the PyPI page) claims {m.group(1)} {key}, repo has {actual[key]}")


def test_bundled_symlinks_point_at_the_repo_trees():
    """One copy of skills/ and templates/, so the wheel can never drift from the repo."""
    bundled = REPO / "core" / "cap_evolve" / "_bundled"
    for name in ("skills", "templates"):
        link = bundled / name
        assert link.is_symlink(), f"{link} must be a symlink, not a second copy"
        assert link.resolve() == (REPO / name).resolve()


def test_resource_root_finds_the_runtime_data():
    """Whatever the layout, the files a run cannot start without are reachable."""
    root = resource_root()
    for rel in ("skills/optimizers/registry.yaml",
                "skills/_registry/manifest.json",
                "skills/algorithms/hill-climb/scripts/run.py",
                "templates/project/capevolve.yaml"):
        assert (root / rel).exists(), f"resource_root() cannot reach {rel}"


def test_resource_root_prefers_a_bundled_tree_when_there_is_no_repo(tmp_path, monkeypatch):
    """The pip-installed shape: no repo above the package, data inside it."""
    (tmp_path / "skills" / "optimizers").mkdir(parents=True)
    (tmp_path / "skills" / "optimizers" / "registry.yaml").write_text("mock: {}\n")
    monkeypatch.setenv("CAPEVOLVE_RESOURCE_ROOT", str(tmp_path))
    assert resource_root() == tmp_path


def test_no_parents_2_repo_walk_left_in_the_core():
    """``parents[2]`` is the repo-layout assumption a wheel breaks — route via resources."""
    offenders = []
    for py in (REPO / "core" / "cap_evolve").glob("*.py"):
        if py.name == "resources.py":
            continue  # the one module allowed to know the layout — it decides it
        if "parents[2]" in py.read_text(encoding="utf-8"):
            offenders.append(py.name)
    assert offenders == [], f"{offenders} assume the repo layout; use resources.resource_root()"
