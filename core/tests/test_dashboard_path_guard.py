"""``dashboard._safe_subpath`` is the containment guard every filesystem path in the
reducer is built through. It must refuse anything that leaves the base — ``..``, an
absolute path, a nested ``a/../../..``, a symlink pointing out — while resolving an
ordinary run-dir child unchanged.
"""

import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))


def test_safe_subpath_refuses_traversal_and_resolves_real_children():
    from cap_evolve import dashboard

    with tempfile.TemporaryDirectory() as d:
        base = Path(d).resolve() / "run_hillclimb"
        (base / "wiki" / "results").mkdir(parents=True)
        (base / "events.jsonl").write_text("", encoding="utf-8")
        (Path(d) / "secret.txt").write_text("nope", encoding="utf-8")

        # An ordinary child still resolves, and keeps resolving through nesting.
        assert dashboard._safe_subpath(base, "events.jsonl") == base / "events.jsonl"
        assert dashboard._safe_subpath(base, "wiki", "results") == base / "wiki" / "results"

        # ...and every escape is refused.
        for parts in (("..",),
                      ("../secret.txt",),
                      ("a/../../..",),
                      ("wiki", "../../secret.txt"),
                      ("..", "..", "etc"),
                      (os.sep + os.path.join("etc", "passwd"),),
                      (str(Path(d) / "secret.txt"),)):
            assert dashboard._safe_subpath(base, *parts) is None, parts

        # A symlink out of the base is an escape too (realpath runs before the check).
        (base / "escape").symlink_to(Path(d) / "secret.txt")
        assert dashboard._safe_subpath(base, "escape") is None

        # A sibling directory sharing the base's name prefix is not "inside" it.
        (Path(d) / "run_hillclimb_other").mkdir()
        assert dashboard._safe_subpath(base, "..", "run_hillclimb_other") is None


def test_evograph_wiki_slug_cannot_escape_the_run_dir():
    """The real vector: ``slug:`` is front matter an agent wrote, not a name we chose."""
    from cap_evolve import dashboard

    with tempfile.TemporaryDirectory() as d:
        root = Path(d).resolve() / "run_evograph"
        (root / "wiki" / "weaknesses").mkdir(parents=True)
        # solutions/ must exist: the kernel resolves ".." against a real directory, so
        # without it the pre-guard code was only accidentally safe (ENOENT, not a check).
        (root / "wiki" / "solutions").mkdir()
        outside = Path(d) / "outside"
        (outside / "child").mkdir(parents=True)  # would count as a "solution" if reached
        (root / "wiki" / "weaknesses" / "w1.md").write_text(
            "---\nslug: ../../../outside\ntitle: escape\n---\n", encoding="utf-8")

        (weak,) = dashboard._read_evograph(root)["weaknesses"]
        assert weak["num_solutions"] == 0, "traversal via slug must not be followed"
