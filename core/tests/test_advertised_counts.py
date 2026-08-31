"""The skill/algorithm/optimizer counts advertised in docs and on the site match the repo.

Counting rule (the ambiguity that let 18-vs-19 and 3-vs-4 drift in the first place):
a SKILL is one ``skills/<component>/<name>/SKILL.md`` (equivalently one row of the
generated ``skills/_registry/manifest.json``) — phases, capabilities, algorithms,
optimizers and orchestrate all count. An ALGORITHM is a skill under
``skills/algorithms/``, including the agent-mode-only ones. An algorithm is
*run-executable* unless its ``meta.yaml`` declares it agent-mode only, in which case
``cap-evolve run`` hands off after baseline and its ``scripts/run.py`` is a loud guard
rather than a loop. An OPTIMIZER BACKEND is one top-level row of
``skills/optimizers/registry.yaml``.

Ground truth here is the FILESYSTEM, not the committed manifest: a contributor who
adds a skill and forgets ``build_manifest.py`` must still fail this guard — a stale
manifest would otherwise agree with the stale advertised number and pass. Manifest
freshness is asserted separately, since a stale committed manifest is its own defect.
The glob is on ``*/*/SKILL.md`` (a FILE), so ``skills/_registry/__pycache__/`` and any
other non-skill directory cannot inflate the count.

TO ADD A SURFACE: append a ``(file, regex-with-one-capturing-group, expected)`` row to
``CLAIMS``. Anchor the regex on a distinctive nearby string so a reflow does not break
it. EVERY occurrence in the file must match, so a stale duplicate lower down cannot
hide behind a fresh first hit.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / "skills"

# rglob, not */*/: a component may GROUP its skills one level deeper
# (interventions/llm-proxies/spa), and a fixed depth would silently undercount.
SKILL_MDS = sorted(p for p in SKILLS.rglob("SKILL.md") if "_registry" not in p.parts)
ALGO_DIRS = sorted(p.parent for p in SKILL_MDS if p.parent.parent.name == "algorithms")

N_SKILLS = len(SKILL_MDS)
N_ALGOS = len(ALGO_DIRS)

# Agent-mode-only algorithms say so in their meta.yaml; the rest run under
# `cap-evolve run` (cli.py short-circuits agent mode right after baseline).
_AGENT_ONLY = re.compile(r"agent[- ]mode only", re.I)
AGENT_ONLY_ALGOS = sorted(
    d.name for d in ALGO_DIRS
    if _AGENT_ONLY.search((d / "meta.yaml").read_text(encoding="utf-8")))
N_AGENT_ALGOS = len(AGENT_ONLY_ALGOS)
N_EXEC_ALGOS = N_ALGOS - N_AGENT_ALGOS

N_OPTIMIZERS = len(re.findall(
    r"^[a-z0-9_-]+:$",
    (SKILLS / "optimizers" / "registry.yaml").read_text(encoding="utf-8"), re.M))

# (file, regex with one capturing group holding the advertised number, expected)
CLAIMS = [
    ("README.md", r"agent%20skills-(\d+)-", N_SKILLS),
    ("llms.txt", r"## Skills \((\d+)\)", N_SKILLS),
    # Changelogs intentionally preserve historical counts; unlike the other
    # surfaces, they are not current claims.
    ("docs/ARCHITECTURE.md", r"(\d+) skills · \d+ algorithms", N_SKILLS),
    ("docs/ARCHITECTURE.md", r"\d+ skills · (\d+) algorithms", N_ALGOS),
    ("site/index.html", r"(\d+) skills · \d+ algorithms", N_SKILLS),
    ("site/index.html", r"\d+ skills · (\d+) algorithms", N_ALGOS),
    ("site/architecture.html", r"(\d+) skills · \d+ algorithms", N_SKILLS),
    ("site/architecture.html", r"\d+ skills · (\d+) algorithms", N_ALGOS),
    ("llms.txt", r"algorithms \((\d+)\):", N_ALGOS),
    # The executable-vs-agent-mode split, so "N algorithms" cannot read as
    # "N things you can run" on the surfaces a first-time visitor sees.
    ("docs/ARCHITECTURE.md", r"algorithms \((\d+) run-executable", N_EXEC_ALGOS),
    ("docs/ARCHITECTURE.md", r"run-executable \+ (\d+) agent-mode\)", N_AGENT_ALGOS),
    ("site/index.html", r"algorithms \((\d+) run-executable", N_EXEC_ALGOS),
    ("site/index.html", r"run-executable \+ (\d+) agent-mode\)", N_AGENT_ALGOS),
    ("site/architecture.html", r"algorithms \((\d+) run-executable", N_EXEC_ALGOS),
    ("site/architecture.html", r"run-executable \+ (\d+) agent-mode\)", N_AGENT_ALGOS),
    ("llms.txt", r"(\d+) run-executable", N_EXEC_ALGOS),
    ("llms.txt", r"run-executable \+ (\d+) agent-mode", N_AGENT_ALGOS),
    # Optimizer backends — one top-level row of optimizers/registry.yaml.
    ("docs/ARCHITECTURE.md", r"(\d+) optimizer backends", N_OPTIMIZERS),
    ("docs/ARCHITECTURE.md", r"registry\.yaml` \((\d+) backends", N_OPTIMIZERS),
    ("site/index.html", r"(\d+) optimizer backends", N_OPTIMIZERS),
    ("site/architecture.html", r"(\d+) optimizer backends", N_OPTIMIZERS),
    ("site/architecture.html", r"registry\.yaml</code> \((\d+) backends", N_OPTIMIZERS),
]

# Every place algorithms are enumerated. The last two are the library tables; the
# first three are what a user COPIES into capevolve.yaml, where an omission
# silently costs them a working config.
ALGORITHM_LISTS = [
    ("templates/project/capevolve.yaml", "algorithm_skill:"),
    ("docs/OPTIMIZE_YOUR_OWN.md", "algorithm_skill:"),
    ("site/optimize-your-own.html", "algorithm_skill:"),
    ("docs/ARCHITECTURE.md", "| algorithms |"),
    ("site/architecture.html", "<td>algorithms</td>"),
]


def test_manifest_is_fresh():
    """The committed manifest agrees with the skills on disk."""
    manifest = json.loads((SKILLS / "_registry" / "manifest.json").read_text())
    assert sorted(manifest["skills"]) == sorted(p.parent.name for p in SKILL_MDS), (
        "skills/_registry/manifest.json is stale — run "
        "`python skills/_registry/build_manifest.py skills` and commit the result."
    )
    by_meta = sorted(n for n, s in manifest["skills"].items() if s["component"] == "algorithm")
    assert by_meta == sorted(d.name for d in ALGO_DIRS), (
        f"algorithms by meta.yaml component ({by_meta}) disagree with the "
        f"skills/algorithms/ layout ({[d.name for d in ALGO_DIRS]})"
    )


def test_advertised_counts_match_repo():
    for rel, pattern, expected in CLAIMS:
        text = (REPO / rel).read_text(encoding="utf-8")
        found = re.findall(pattern, text)
        assert found, f"{rel}: no count matching {pattern!r} — did the wording change?"
        assert all(int(n) == expected for n in found), (
            f"{rel} advertises {found} but the repo has {expected} "
            f"(pattern {pattern!r}). Update the doc, or the counting rule in "
            f"docs/ARCHITECTURE.md if the definition really changed."
        )


def test_every_algorithm_is_listed_where_algorithms_are_enumerated():
    algos = [d.name for d in ALGO_DIRS]
    for rel, anchor in ALGORITHM_LISTS:
        text = (REPO / rel).read_text(encoding="utf-8")
        row = next((ln for ln in text.splitlines() if anchor in ln and "hill-climb" in ln), None)
        assert row, f"{rel}: no algorithm list line containing {anchor!r} and 'hill-climb'"
        for name in algos:
            assert name in row, f"{rel}: algorithm list omits {name!r}"
