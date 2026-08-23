"""The benchmarks page must recognise every tier the workflow can run.

`site/benchmarks.js` matches CI job names ("<tier> / <bench>") to build the "Running now"
panel and its "Open UI" links. That regex hardcoded `smoke|full`, so when the `pilot` tier
landed a live pilot run was **invisible on the page while it executed** — no panel entry, no
way to open its UI. Nothing failed; the run simply could not be seen.

This is cross-file drift: the tier list lives in .github/workflows/benchmarks.yml and the
matcher lives in the site. These tests tie them together so adding a tier cannot silently
hide it again.
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "benchmarks.yml"
JS = REPO / "site" / "benchmarks.js"
HTML = REPO / "site" / "benchmarks.html"

BENCHES = ["tau2", "swebench", "skillsbench", "spreadsheetbench"]


def _workflow_tiers() -> list[str]:
    """The planner's TIERS list — the single source of truth for what CI can run."""
    src = WORKFLOW.read_text(encoding="utf-8")
    m = re.search(r"^\s*TIERS\s*=\s*\[([^\]]*)\]", src, re.M)
    assert m, "TIERS not found in benchmarks.yml"
    tiers = re.findall(r'"([^"]+)"', m.group(1))
    assert tiers, m.group(1)
    return tiers


def _job_regex() -> re.Pattern:
    """Translate the JS JOB_RE into an equivalent Python pattern."""
    src = JS.read_text(encoding="utf-8")
    m = re.search(r"JOB_RE\s*=\s*/(.+?)/[gimsuy]*\s*;", src)
    assert m, "JOB_RE not found in site/benchmarks.js"
    pattern = m.group(1).replace("\\/", "/")
    return re.compile(pattern)


def test_live_panel_matches_every_tier_the_workflow_can_run():
    rx = _job_regex()
    missing = [f"{t} / {b}" for t in _workflow_tiers() for b in BENCHES
               if not rx.match(f"{t} / {b}")]
    assert not missing, (
        "site/benchmarks.js JOB_RE does not match these CI job names, so those runs would be "
        f"invisible in the live panel: {missing}"
    )


def test_live_panel_captures_tier_and_bench_groups():
    rx = _job_regex()
    m = rx.match("pilot / spreadsheetbench")
    assert m and m.group(1) == "pilot" and m.group(2) == "spreadsheetbench", (
        "the panel reads tier from group 1 and bench from group 2 to build its UI links"
    )


def test_live_panel_ignores_non_leg_jobs():
    """The other jobs in the workflow must never appear as benchmark legs."""
    rx = _job_regex()
    for name in ("plan legs", "aggregate history", "collect-pr-context", "Test Python (core)"):
        assert not rx.match(name), f"JOB_RE should not match the {name!r} job"


def test_tier_filter_offers_every_tier():
    """The history table filters on tier dynamically from records — no hardcoded list can drift.

    As of feat(site): "default to successful runs, derive the filter lists, show local time",
    the f-tier dropdown is populated at load time by hydrateFilter from the actual RECORDS data.
    Any tier present in benchmark-history will appear automatically; no markup change is needed.
    This test asserts that the JS uses that dynamic path (not a hardcoded option list), which is
    the invariant that prevents cross-file drift between benchmarks.yml TIERS and the UI.
    """
    # 1. The select element must exist in the HTML (as a pre-hydration stub).
    html = HTML.read_text(encoding="utf-8")
    assert re.search(r'<select[^>]*id="f-tier"', html), "f-tier select not found in benchmarks.html"

    # 2. benchmarks.js must call hydrateFilter for f-tier using record-derived values —
    #    not a hardcoded list of tier names.  If this call is absent the filter would be
    #    whatever the static HTML says, and a new tier would be invisible until someone
    #    remembered to update the markup.
    js = JS.read_text(encoding="utf-8")
    assert re.search(r'hydrateFilter\(\s*"#f-tier"', js), (
        'site/benchmarks.js must call hydrateFilter("#f-tier", …) to populate the tier '
        "dropdown from records; a static option list silently hides tiers not in the markup"
    )


def test_history_table_shows_which_algorithm_produced_the_number():
    """A hill-climb number and an agent-optimize number are not a like-for-like comparison.

    The benchmarks page is where numbers get compared across runs, so `runmeta.json` records
    the `algorithm` and the table has to surface it. Without the column the field exists in
    every record and is invisible exactly where the false comparison would be made.

    Column count matters too: the expandable detail row spans the whole table, so a header
    added without bumping its colspan leaves the per-task/per-step tables misaligned.
    """
    html = HTML.read_text(encoding="utf-8")
    js = JS.read_text(encoding="utf-8")

    assert re.search(r'<th data-k="algorithm">', html), (
        "the history table has no Algorithm column — the algorithm that produced a number "
        "would be invisible on the page where numbers are compared"
    )
    assert "r.algorithm" in js, "benchmarks.js never renders the record's algorithm field"

    header_block = html[html.index("<thead><tr>"):html.index("</thead>")]
    n_cols = len(re.findall(r"<th\b", header_block))
    spans = {int(m) for m in re.findall(r'colspan="(\d+)"', js)}
    assert spans == {n_cols}, (
        f"the table has {n_cols} columns but the detail row spans {sorted(spans)} — the "
        "expanded per-task table would not line up with the header"
    )


def test_a_record_without_an_algorithm_is_not_given_one():
    """Every record written before the field existed must render as unknown, not guessed.

    `algorithm_focus` was already dispatchable then, so an old run's schedule is genuinely
    unrecoverable. Defaulting the column to "hill-climb-all" would fabricate precisely the
    provenance the column exists to establish.
    """
    js = JS.read_text(encoding="utf-8")
    m = re.search(r"const algo = ([^;]+);", js)
    assert m, "the algorithm cell is not rendered through a reviewable expression"
    expr = m.group(1)
    assert '"—"' in expr or "'—'" in expr, (
        f"a missing algorithm must render as an em dash: {expr}")
    assert "hill-climb" not in expr, (
        f"a missing algorithm must not be back-filled with a guessed default: {expr}")
