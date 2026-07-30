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

Section identity is pinned in **both** directions (a doc-only section is exactly the #236
divergence this PR fixes), and numbers are pinned by a scrape *confined to declared results
tables*: `<td class="num">` / `<td class="gain">` inside a `<section>` whose `<h2 id>` is in
the mapping below, matched row-by-row against the same-labelled `docs/RESULTS.md` table row.

That scope is what makes it allowlist-free. A *whole-file* numeric scrape cannot tell a
reward from a font weight (`site/results.html:23` `wght@400;500;600;700;800`), an arXiv id
(`2603.04900`), an external paper's figure, or an SVG path coordinate — it needs an
allowlist entry per exception, and a guard whose allowlist keeps growing stops guarding.
Inside a results `<td class="num">` none of those live, so the confined scrape needs
**zero** allowlist entries (see `test_site_results_numbers_match_the_canonical_doc`).

Known limits, stated rather than implied: only `site/results.html` is read, so a *new*
surface or a *new* results page publishing runs is not covered, and evidence-marker (⚠️)
parity between the surfaces is not enforced. Those are section-registration problems; this
guard covers the surface #100 was filed about.

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

# docs/RESULTS.md `## ` headings that deliberately have no site section, with the reason.
# Empty today: every canonical run is published. Add here (never silently) if that changes.
SITE_OPTIONAL: dict[str, str] = {}


def _read(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


def _text(html: str) -> str:
    """Tag-stripped, entity-decoded, whitespace- and emphasis-normalised cell text."""
    out = re.sub(r"<[^>]+>", " ", html)
    for ent, ch in (("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                    ("&middot;", "·")):
        out = out.replace(ent, ch)
    return re.sub(r"\s+", " ", re.sub(r"[*`\\]", "", out)).strip()


def _numbers(cell: str) -> frozenset:
    """Numbers in a cell, dropping percent restatements of a value already present.

    The site writes `0.536 (53.6%)` where the doc writes `0.536`; the doc's own rule is to
    label percentages explicitly, so `53.6` alongside `0.536` is the same number twice.
    """
    vals = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", _text(cell))]
    return frozenset(v for v in vals if not any(abs(v - 100 * o) < 1e-9 for o in vals))


def _site_sections() -> dict[str, str]:
    parts = re.split(r'<h2 id="([^"]+)"', _read("site/results.html"))
    return dict(zip(parts[1::2], parts[2::2]))


def _doc_sections() -> dict[str, str]:
    doc = _read("docs/RESULTS.md")
    out = {}
    for m in re.finditer(r"^## (.+)$", doc, re.M):
        end = doc.find("\n## ", m.end())
        out[m.group(1)] = doc[m.end(): end if end != -1 else len(doc)]
    return out


def _doc_table_rows(section: str) -> list[list[str]]:
    rows = []
    for line in section.splitlines():
        line = line.strip()
        if not (line.startswith("|") and line.endswith("|")):
            continue
        cells = line.strip("|").split("|")
        if all(set(_text(c)) <= set("-: ") for c in cells):  # markdown separator row
            continue
        rows.append(cells)
    return rows


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


def test_every_canonical_run_section_is_published_on_the_site():
    """The reverse direction — the one that actually broke in #236.

    #236 added a `docs/RESULTS.md` section the site never got. Checking site → doc alone
    pins the *original* #100 direction and lets the *current* one reopen silently.
    """
    site_anchors = set(_site_sections())
    published = {v for k, v in ANCHOR_TO_CANON_HEADING.items() if v and k in site_anchors}
    unpublished = [
        h for h in _doc_sections()
        if h not in SITE_OPTIONAL and not any(c in h for c in published)
    ]
    assert not unpublished, (
        f"docs/RESULTS.md section(s) with no site/results.html section: {unpublished}\n"
        "Add the site section (with its split label and evidence marker), or add the "
        "heading to SITE_OPTIONAL with a reason."
    )


def test_site_results_numbers_match_the_canonical_doc():
    """Every number in a mapped site results table equals the canonical doc's.

    Confined to `<td class="num">` / `<td class="gain">` inside mapped sections, matched to
    the `docs/RESULTS.md` row with the same label and the same column count — so a number
    edited in place, or a split label falsified, fails. No allowlist: fonts, arXiv ids and
    SVG coordinates are all outside a results `<td>`.
    """
    doc_sections = _doc_sections()
    problems = []
    for anchor, body in _site_sections().items():
        canon = ANCHOR_TO_CANON_HEADING.get(anchor)
        if not canon:
            continue
        doc_rows = next(
            (_doc_table_rows(v) for k, v in doc_sections.items() if canon in k), None
        )
        if doc_rows is None:  # missing heading: test 1's assertion, reported there
            continue
        for row in re.findall(r"<tr>(.*?)</tr>", body, re.S):
            cells = re.findall(r"(<t[dh][^>]*>)(.*?)</t[dh]>", row, re.S)
            cols = [i for i, (tag, _) in enumerate(cells)
                    if 'class="num"' in tag or 'class="gain"' in tag]
            if not cols:
                continue
            label = _text(cells[0][1])
            want = [_numbers(cells[i][1]) for i in cols]
            same_label = [
                r for r in doc_rows
                if re.sub(r"\s+", "", _text(r[0])) == re.sub(r"\s+", "", label)
                and len(r) == len(cells)
            ]
            if not same_label:
                problems.append(
                    f"{anchor}: no docs/RESULTS.md table row labelled {label!r} "
                    f"({len(cells)} columns) — split label falsified, or the row is "
                    "published on the site only"
                )
            elif not any([_numbers(r[i]) for i in cols] == want for r in same_label):
                problems.append(
                    f"{anchor}: row {label!r} publishes {[sorted(w) for w in want]}, "
                    f"docs/RESULTS.md says "
                    f"{[[sorted(_numbers(r[i])) for i in cols] for r in same_label]}"
                )
    assert not problems, (
        "site/results.html results tables disagree with docs/RESULTS.md:\n  "
        + "\n  ".join(problems)
        + "\ndocs/RESULTS.md is the superset — fix the value there first, then the site."
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
