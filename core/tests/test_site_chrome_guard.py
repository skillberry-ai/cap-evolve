"""The sync-site-chrome guards that a silent failure would reopen.

Each of these three failure modes shipped once and reported green (PR #196
review): a lookalike region rewritten while the real chrome stayed drifted, an
unregistered page invisible to --check, and a deleted ?v= never restored
(issue #87). They are cheap to assert and expensive to rediscover.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "sync-site-chrome.py"
SITE = REPO / "site"


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(cwd / "scripts" / "sync-site-chrome.py"), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A throwaway copy of site/ + the script, so probes never touch the repo."""
    root = tmp_path / "repo"
    (root / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, root / "scripts" / "sync-site-chrome.py")
    shutil.copytree(SITE, root / "site")
    assert run("--check", cwd=root).returncode == 0, "fixture must start in sync"
    return root


def test_clean_tree_is_in_sync_and_idempotent(repo: Path) -> None:
    assert run(cwd=repo).stdout.startswith("synced 0/")
    assert run(cwd=repo).stdout.startswith("synced 0/")
    assert run("--check", cwd=repo).returncode == 0


def test_lookalike_region_is_not_the_sync_target(repo: Path) -> None:
    """A nav quoted in a comment must not absorb the generated nav."""
    page = repo / "site" / "results.html"
    text = page.read_text()
    decoy = '<!-- doc: <nav class="nav">old</nav> -->'
    page.write_text(
        text.replace("<body>", f"<body>\n{decoy}", 1).replace(
            ">Architecture</a>", ">Arch</a>", 1
        )
    )

    assert run("--check", cwd=repo).returncode == 1  # the drift is seen
    assert run(cwd=repo).returncode == 0

    fixed = page.read_text()
    assert ">Arch</a>" not in fixed  # the REAL nav was repaired
    assert fixed.count("nav-toggle") == 1  # chrome not duplicated
    assert decoy in fixed  # the decoy was left alone
    assert run("--check", cwd=repo).returncode == 0


def test_duplicate_sentinel_pair_fails_loudly(repo: Path) -> None:
    """More than one match must fail, not silently pick the first."""
    page = repo / "site" / "results.html"
    text = page.read_text()
    i = text.index("<!-- chrome:nav:start")
    j = text.index("<!-- chrome:nav:end -->") + len("<!-- chrome:nav:end -->")
    page.write_text(text[:i] + text[i:j] + "\n" + text[i:j] + text[j:])

    for args in ((), ("--check",)):
        got = run(*args, cwd=repo)
        assert got.returncode == 1
        assert "expected exactly 1 chrome:nav sentinel pair" in got.stderr


def test_unregistered_page_fails_the_guard(repo: Path) -> None:
    new = repo / "site" / "newpage.html"
    shutil.copy(repo / "site" / "getting-started.html", new)
    got = run("--check", cwd=repo)
    assert got.returncode == 1
    assert "unregistered=['newpage.html']" in got.stderr

    new.unlink()
    assert run("--check", cwd=repo).returncode == 0


def test_registered_page_missing_from_disk_fails(repo: Path) -> None:
    (repo / "site" / "results.html").unlink()
    got = run("--check", cwd=repo)
    assert got.returncode == 1
    assert "missing=['results.html']" in got.stderr


def test_deleted_cachebuster_is_flagged_and_restored(repo: Path) -> None:
    """issue #87: a ?v= that is gone must be reported AND rewritten."""
    page = repo / "site" / "index.html"
    spec = importlib.util.spec_from_file_location(
        "sync_site_chrome", repo / "scripts" / "sync-site-chrome.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    expected = mod.cachebust("js/site.js")

    page.write_text(page.read_text().replace(expected, "js/site.js"))
    assert 'src="js/site.js"' in page.read_text()

    assert run("--check", cwd=repo).returncode == 1
    assert run(cwd=repo).returncode == 0
    assert f'src="{expected}"' in page.read_text()


def test_conflict_markers_do_not_pass(repo: Path) -> None:
    page = repo / "site" / "index.html"
    text = page.read_text()
    page.write_text(
        text.replace('<nav class="nav">', '<<<<<<< HEAD\n<nav class="nav">', 1).replace(
            "</nav>", '</nav>\n=======\n<nav class="nav">x</nav>\n>>>>>>> other', 1
        )
    )
    got = run("--check", cwd=repo)
    assert got.returncode == 1
    assert "merge-conflict markers" in got.stderr


def test_page_specific_head_content_survives(repo: Path) -> None:
    """Content placed outside the sentinels is not the generator's business."""
    page = repo / "site" / "benchmarks.html"
    extra = '<script type="application/ld+json">{"@type":"Dataset"}</script>'
    page.write_text(
        page.read_text().replace(
            "<!-- chrome:head:end -->", f"<!-- chrome:head:end -->\n  {extra}", 1
        )
    )
    assert run(cwd=repo).returncode == 0
    assert extra in page.read_text()
    assert run("--check", cwd=repo).returncode == 0
