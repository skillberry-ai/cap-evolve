"""Generic CI must describe tiers generically — no one benchmark's details in shared code.

A tier is a DIMENSION of the suite, not a feature of whichever benchmark happened to need it
first. `full_verified` was introduced for spreadsheetbench's verified 400-task re-release, and
more benchmarks are expected to gain their own verified releases. If the shared files explain
the tier in terms of spreadsheetbench — "the 400-task set", "~2,279 rollouts/seed" — then the
second benchmark to populate it inherits documentation that is wrong for it, and the dispatch
UI tells every operator about a benchmark they may not be running.

WHERE SPECIFICITY BELONGS
    ci/benchmarks/<bench>/**            the tier's data, overrides and README
    core/tests/test_<bench>_*.py        that benchmark's assertions
    the `<bench>)` case arm in the shared shell libs — per-bench by construction
    CHANGELOG.md                        a historical record of a specific change

WHERE IT DOES NOT
    .github/workflows/benchmarks.yml    tier list, dispatch inputs, planner
    ci/benchmarks/README.md             the suite's own tier overview
    site/benchmarks.js                  the live panel's tier matcher
    everything in the shared shell libs OUTSIDE a `<bench>)` arm

This file enforces that split so it cannot erode as tiers are added.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "benchmarks.yml"
SUITE_README = REPO / "ci" / "benchmarks" / "README.md"
SITE_JS = REPO / "site" / "benchmarks.js"
RUN_SUITE = REPO / "ci" / "benchmarks" / "lib" / "run_suite.sh"
CI_SETUP = REPO / "ci" / "benchmarks" / "lib" / "ci_setup.sh"

# Files that must stay benchmark-agnostic end to end.
GENERIC_FILES = [WORKFLOW, SUITE_README, SITE_JS]

# Benchmark names the suite knows about. A generic file may LIST these (the planner's BENCHES,
# the dispatch combobox, the live panel's allowlist) — what it may not do is explain a TIER in
# terms of one of them.
BENCH_NAMES = ["tau2", "swebench", "skillsbench", "spreadsheetbench", "rfe-creator"]

# Numbers that belong to one benchmark's data or cost model, never to a tier's definition.
BENCH_SPECIFIC_FACTS = [
    r"\b912\b", r"\b400[- ]task\b", r"\bverified_400\b", r"\bfull_912\b", r"\bsample_200\b",
    r"\b2,279\b", r"\b80/40/280\b", r"\b182 ?/ ?91 ?/ ?639\b",
]

TIER_TOKEN = "full_verified"


def _bench_arm(path: Path, bench: str) -> str:
    """The `<bench>)` case arm of a shared shell lib — legitimately benchmark-specific.

    Ends at whichever comes first: the next arm, a default `*)` arm, or `esac` (ci_setup.sh
    has no default arm, so anchoring only on `*)` would run past the end of the case).
    """
    src = path.read_text(encoding="utf-8")
    start = src.index(f"  {bench})")
    boundaries = [f"\n  {b})" for b in BENCH_NAMES if b != bench] + ["\n  *)", "\nesac"]
    ends = [src.index(m, start) for m in boundaries if m in src[start:]]
    return src[start:min(ends)] if ends else src[start:]


def _lines_mentioning(path: Path, token: str) -> list[tuple[int, str]]:
    return [(i, line) for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
            if token in line]


@pytest.mark.parametrize("path", GENERIC_FILES, ids=lambda p: p.name)
def test_generic_files_do_not_name_a_benchmark_alongside_the_tier(path):
    """`full_verified` and a benchmark name must not appear on the same line in shared code."""
    offenders = [
        f"{path.relative_to(REPO)}:{i}: {line.strip()[:120]}"
        for i, line in _lines_mentioning(path, TIER_TOKEN)
        for b in BENCH_NAMES if b in line
    ]
    assert not offenders, (
        "a generic file explains the tier in terms of one benchmark — move that to "
        f"ci/benchmarks/<bench>/README.md:\n" + "\n".join(offenders)
    )


@pytest.mark.parametrize("path", GENERIC_FILES, ids=lambda p: p.name)
def test_generic_files_carry_no_single_benchmarks_data_or_cost_facts(path):
    """Task counts, dataset variant names and rollout costs are per-benchmark facts.

    Checked over the whole file, not just tier lines: a shared file has no business asserting
    that any benchmark has 912 tasks or costs 2,279 rollouts, whatever it is describing.
    """
    text = path.read_text(encoding="utf-8")
    hits = [pat for pat in BENCH_SPECIFIC_FACTS if re.search(pat, text)]
    assert not hits, (
        f"{path.relative_to(REPO)} states one benchmark's data/cost facts {hits} — these belong "
        "in that benchmark's own README"
    )


@pytest.mark.parametrize("path", [RUN_SUITE, CI_SETUP], ids=lambda p: p.name)
def test_shared_shell_libs_only_mention_the_tier_inside_a_bench_arm(path):
    """The shell libs are shared, but their `<bench>)` arms are per-benchmark by construction.

    Wiring a tier to a dataset variant or a turn budget there is correct. Mentioning it in the
    libs' COMMON code would make a spreadsheetbench decision apply to every benchmark.
    """
    arms = "\n".join(_bench_arm(path, b) for b in BENCH_NAMES if f"  {b})" in
                     path.read_text(encoding="utf-8"))
    outside = [f"{path.relative_to(REPO)}:{i}: {line.strip()[:120]}"
               for i, line in _lines_mentioning(path, TIER_TOKEN) if line not in arms]
    assert not outside, (
        "the tier is referenced in shared shell code outside any per-benchmark arm:\n"
        + "\n".join(outside)
    )


def test_the_dispatch_description_defines_the_tier_without_naming_a_benchmark():
    """Operators of every benchmark read this combobox help text."""
    src = WORKFLOW.read_text(encoding="utf-8")
    desc = re.search(r'^\s*description: "(Which tier[^"]*)"', src, re.M)
    assert desc, "the tier input's description was not found"
    text = desc.group(1)
    assert TIER_TOKEN in text, "the description must still explain what full_verified means"
    named = [b for b in BENCH_NAMES if b in text]
    assert not named, f"the tier description names specific benchmarks: {named}"


def test_the_suite_readme_points_at_per_benchmark_docs_for_the_details():
    """Generic overview, then a pointer — not a copy of one benchmark's numbers.

    The pointer may serve the whole tier list rather than sitting in one bullet, so this looks
    at the tier section as a unit. What must NOT be here (a benchmark's sizes, datasets and
    costs) is enforced by test_generic_files_carry_no_single_benchmarks_data_or_cost_facts.
    """
    txt = SUITE_README.read_text(encoding="utf-8")
    assert f"**`{TIER_TOKEN}`**" in txt, "the suite README does not document the tier at all"
    section = txt.split("Runs come in several **tiers**", 1)[1].split("\n## ", 1)[0]
    assert f"**`{TIER_TOKEN}`**" in section, "the tier is documented outside the tier section"
    assert "<bench>/README.md" in section, (
        "the tier section must point readers at the per-benchmark READMEs rather than "
        "restating one benchmark's configuration"
    )


def test_the_suite_readme_tier_list_names_no_benchmark_at_all():
    """The tier overview describes DIMENSIONS, so no tier entry may name a benchmark.

    Applies to every tier, not just full_verified: "currently populated by <bench>" goes stale
    the moment a second benchmark populates that tier, and which benchmarks populate what is
    already discoverable from the `ci/benchmarks/<bench>/<tier>/` tree.

    Scoped to the tier list rather than the whole file on purpose — elsewhere the suite README
    legitimately names benchmarks (the benchmark roster, per-runner prerequisites, PR labels).
    """
    txt = SUITE_README.read_text(encoding="utf-8")
    section = txt.split("Runs come in several **tiers**", 1)[1].split("\n## ", 1)[0]
    # The per-benchmark prerequisites subsection is a labelled aside, not a tier entry.
    tier_list = section.split("**`spreadsheetbench` runner prerequisites**", 1)[0]
    named = sorted({b for b in BENCH_NAMES if b in tier_list})
    assert not named, (
        f"the tier list names benchmarks {named} — a tier is a dimension of the suite, so this "
        "goes stale as soon as another benchmark populates that tier"
    )


def test_every_tier_in_the_workflow_is_a_generic_name():
    """A tier name may not encode one benchmark's task count or identity."""
    src = WORKFLOW.read_text(encoding="utf-8")
    tiers = re.findall(r'"([^"]+)"', re.search(r"^\s*TIERS = \[([^\]]*)\]", src, re.M).group(1))
    for t in tiers:
        assert not re.search(r"\d", t), f"tier name encodes a number: {t}"
        assert not any(b in t for b in BENCH_NAMES), f"tier name names a benchmark: {t}"
