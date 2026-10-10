"""#709: heading-section block verdict for .md in merge_search.is_mergeable (mdblocks).

Fixture = real archived run_20261008_150326 seed/cand_3/cand_4/cand_5 policy.md. Finding: those
three actually edit the SAME lines (preamble insert at line 8, Modify-flight lines 110-113), so
every pair stays a genuine conflict at section granularity; the disjoint case is therefore
exercised on real seed text with the real candidates' hunks applied to different sections.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"))
sys.path.insert(0, str(REPO / "core"))

import merge_search  # noqa: E402
from cap_evolve import mdblocks  # noqa: E402

FIX = Path(__file__).parent / "fixtures" / "md_blocks"


def _txt(c: str) -> str:
    return (FIX / c / "policy" / "policy.md").read_text(encoding="utf-8")


def _cap(root: Path, name: str, text: str) -> Path:
    (root / name / "policy").mkdir(parents=True)
    (root / name / "policy" / "policy.md").write_text(text, encoding="utf-8")
    return root / name


def test_real_cand345_still_conflict_on_shared_sections_but_off_is_whole_file():
    for a, b in itertools.combinations(["cand_3", "cand_4", "cand_5"], 2):
        on = merge_search.is_mergeable(FIX / a, FIX / b, FIX / "seed")
        assert not on["mergeable"]
        assert all("::" in c for c in on["conflicts"])           # block-level, not whole file
        assert any("Modify flight" in c for c in on["conflicts"])
        off = merge_search.is_mergeable(FIX / a, FIX / b, FIX / "seed", md_blocks=False)
        assert off["conflicts"] == ["policy/policy.md"]


def test_real_hunks_in_different_sections_are_mergeable(tmp_path):
    seed, c3, c4 = _txt("seed"), _txt("cand_3"), _txt("cand_4")
    old = "If any portion of the flight has already been flown, the agent cannot help and transfer is needed."
    new = next(l for l in c3.splitlines() if l.startswith(old))
    a = seed.replace(old, new)                                    # Cancel flight section only
    ins = next(l for l in c4.splitlines() if l.startswith("- Whenever cabin class or flights change"))
    anchor = "\n".join(seed.splitlines()[119:120])
    b = seed.replace(anchor, anchor + "\n" + ins, 1)              # Modify flight section only
    assert a != seed and b != seed
    A, B, S = _cap(tmp_path, "a", a), _cap(tmp_path, "b", b), _cap(tmp_path, "s", seed)
    r = merge_search.is_mergeable(A, B, S)
    assert r["mergeable"] and r["conflicts"] == []
    assert not merge_search.is_mergeable(A, B, S, md_blocks=False)["mergeable"]   # legacy
    assert mdblocks.three_way(seed, a, b)["merged_text"] == seed.replace(old, new).replace(anchor, anchor + "\n" + ins, 1)


def test_same_section_different_edit_conflicts_identical_does_not():
    base = "# T\n## A\nx\n## B\ny\n"
    r = mdblocks.three_way(base, base.replace("x", "x1"), base.replace("x", "x2"))
    assert r["conflicts"] == ["T/A"] and r["merged_text"] is None
    r = mdblocks.three_way(base, base.replace("x", "x1"), base.replace("x", "x1"))
    assert r["conflicts"] == [] and r["identical"] == ["T/A"]


def test_fenced_hash_is_not_heading_and_split_roundtrips():
    t = "pre\n# H\n```\n# not a heading\n```\n## S\ntext\n"
    blocks = mdblocks.split(t)
    assert [i for i, _ in blocks] == ["", "H", "H/S"]
    assert "".join(x for _, x in blocks) == t


def test_added_deleted_sections_and_paragraph_fallback():
    base = "# T\n## A\nx\n"
    r = mdblocks.three_way(base, base + "## C\nnew\n", base.replace("x", "y"))
    assert r["conflicts"] == [] and r["merged_text"] == "# T\n## A\ny\n## C\nnew\n"
    assert mdblocks.three_way(base, "# T\n", base.replace("x", "y"))["conflicts"] == ["T/A"]
    para = "one\n\ntwo\n\nthree\n"                                # no headings -> paragraphs
    r = mdblocks.three_way(para, para.replace("one", "ONE"), para.replace("three", "THREE"), max_block_lines=1)
    assert r["conflicts"] == [] and r["merged_text"] == "ONE\n\ntwo\n\nTHREE\n"
