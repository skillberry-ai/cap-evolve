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
    """The history table filters on tier; a tier missing from the dropdown is unselectable."""
    html = HTML.read_text(encoding="utf-8")
    sel = re.search(r'<select id="f-tier">(.*?)</select>', html, re.S)
    assert sel, "f-tier select not found"
    options = set(re.findall(r"<option[^>]*>([^<]+)</option>", sel.group(1)))
    missing = [t for t in _workflow_tiers() if t not in options]
    assert not missing, f"tier filter is missing {missing} (offers {sorted(options)})"
