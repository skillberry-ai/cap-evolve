"""Every `site/results.html` run section maps to a `docs/RESULTS.md` section.

Issue #100: the surfaces had diverged and the source-of-truth relationship was
*inverted* — `site/results.html` published two Qwen 2.5 14B runs (`#qwen-tools`,
`#qwen-all`) that `docs/RESULTS.md` did not contain, while `site/README.md` told readers
to "cross-check against `docs/RESULTS.md`". The canonical doc was a subset of the site.

The rule (stated in the preamble of `docs/RESULTS.md`): **`docs/RESULTS.md` is the
superset.** A run may be published on a site page only if it already has a section in the
canonical doc. This guard enforces exactly that, by anchor id — which is the issue's own
acceptance criterion ("every `site/results.html` run anchor maps to a `RESULTS.md`
section").

Anchor ids, not numbers: a numeric scrape over HTML cannot tell a reward from an SVG
coordinate or an external paper's figure without a growing allowlist of exceptions, and a
guard whose allowlist keeps growing stops guarding. Section identity is the invariant that
actually broke, so that is what is pinned.

The mapping is written out explicitly rather than derived from `<a id="...">` markers,
because those markers are introduced by a sibling honesty PR (#182 / issue #99) — deriving
from them would make this guard's result depend on merge order. An explicit table also
fails loudly on a *renamed* section, which a set-difference would silently accept.

TO ADD A RUN TO THE SITE: add its `docs/RESULTS.md` section first, then its
`site/results.html` section, then a row here. That ordering is the fix.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

# site/results.html <h2 id>  ->  a substring that must appear in a docs/RESULTS.md `## ` heading.
# One row per PUBLISHED RUN. `None` marks a non-run section (presentation scaffolding).
ANCHOR_TO_CANON_HEADING = {
    "toy-calc": "toy_calc",
    "tau2-fit": "no-holdout fit-metric run",
    "tau2-heldout": "held-out 30(=val)/20 run",
    "tau2-agent": "agent orchestration mode",
    "qwen-tools": "Qwen 2.5 14B (tools only",
    "qwen-all": "Qwen 2.5 14B, all capabilities",
    "skillsbench-87-baselines": "full 87-task baselines",
    "skillsbench-87": "full 87-task optimization",
    "skillsbench": "skill-package optimization",
    "at-a-glance": None,
}


def _read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def test_every_site_results_run_section_exists_in_the_canonical_doc():
    site_anchors = re.findall(r'<h2 id="([^"]+)"', _read("site/results.html"))
    assert site_anchors, "no <h2 id=...> run sections found — the site page changed shape"

    unmapped = [a for a in site_anchors if a not in ANCHOR_TO_CANON_HEADING]
    assert not unmapped, (
        f"site/results.html section(s) with no canonical mapping: {unmapped}\n"
        "docs/RESULTS.md is the superset — add the section there (with its split label "
        "and evidence marker) first, then add a row to ANCHOR_TO_CANON_HEADING."
    )

    headings = re.findall(r"^## (.+)$", _read("docs/RESULTS.md"), re.M)
    missing = {
        a: ANCHOR_TO_CANON_HEADING[a] for a in site_anchors
        if ANCHOR_TO_CANON_HEADING[a]
        and not any(ANCHOR_TO_CANON_HEADING[a] in h for h in headings)
    }
    assert not missing, (
        f"site/results.html publishes run section(s) whose docs/RESULTS.md heading is "
        f"gone or renamed: {missing}\nHeadings present: {headings}"
    )


def test_site_results_toc_matches_its_sections():
    """The on-page TOC lists exactly the sections that exist (no dead/absent entries)."""
    site = _read("site/results.html")
    sections = re.findall(r'<h2 id="([^"]+)"', site)
    toc_block = site.split('<nav class="toc"', 1)[1]
    toc = re.findall(r'<a href="#([^"]+)"', toc_block)
    assert toc == sections, (
        f"results.html TOC and section order disagree.\nTOC:      {toc}\n"
        f"Sections: {sections}"
    )


def test_no_blanket_artifact_claim_on_the_surfaces_this_guard_owns():
    """No aggregate "all our numbers are verified" claim.

    Not every published number is artifact-backed (the τ²-bench held-out runs and both
    SkillsBench 87-task runs are reported-only), and an aggregate claim rots the moment a
    run is added — so evidence is stamped per section instead. Scoped to the surfaces
    reconciled under #100; `README.md`, `site/index.html`, `site/results.html`'s lead and
    `presentation/`'s slide-6 copy are #99/#182's to rewrite.
    """
    banned = re.compile(r"hand-verified|cross-check against|every result is committed", re.I)
    hits = {}
    for rel in ("site/README.md", "site/benchmarks.html"):
        for i, line in enumerate(_read(rel).splitlines(), 1):
            if banned.search(line):
                hits.setdefault(rel, []).append(f"{i}: {line.strip()[:120]}")
    assert not hits, (
        f"blanket verification claim(s) still present: {hits}\n"
        "Point at the per-section evidence markers instead of asserting an average."
    )
