"""The skill/algorithm counts advertised in docs and on the site match the registry.

Counting rule (the ambiguity that let 18-vs-19 and 3-vs-4 drift in the first place):
a SKILL is one row of ``skills/_registry/manifest.json`` (equivalently one
``skills/<component>/<name>/SKILL.md``) — phases, capabilities, algorithms, optimizers
and orchestrate all count. An ALGORITHM is a skill whose ``component`` is ``algorithm``,
including the agent-mode-only ones. This test is the guard: add a skill, and every
surface that prints a number fails until it is updated.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MANIFEST = json.loads((REPO / "skills" / "_registry" / "manifest.json").read_text())

N_SKILLS = len(MANIFEST["skills"])
N_ALGOS = sum(1 for s in MANIFEST["skills"].values() if s["component"] == "algorithm")

# (file, regex with one capturing group holding the advertised number, expected)
CLAIMS = [
    ("README.md", r"agent%20skills-(\d+)-", N_SKILLS),
    ("llms.txt", r"## Skills \((\d+);", N_SKILLS),
    ("CHANGELOG.md", r"\*\*(\d+) Agent Skills\*\*", N_SKILLS),
    ("docs/ARCHITECTURE.md", r"(\d+) skills · \d+ algorithms", N_SKILLS),
    ("docs/ARCHITECTURE.md", r"\d+ skills · (\d+) algorithms", N_ALGOS),
    ("site/index.html", r"(\d+) skills · \d+ algorithms", N_SKILLS),
    ("site/index.html", r"\d+ skills · (\d+) algorithms", N_ALGOS),
    ("site/architecture.html", r"(\d+) skills · \d+ algorithms", N_SKILLS),
    ("site/architecture.html", r"\d+ skills · (\d+) algorithms", N_ALGOS),
    ("llms.txt", r"algorithms \((\d+)\):", N_ALGOS),
]


def test_advertised_counts_match_registry():
    for rel, pattern, expected in CLAIMS:
        text = (REPO / rel).read_text(encoding="utf-8")
        m = re.search(pattern, text)
        assert m, f"{rel}: no count matching {pattern!r} — did the wording change?"
        assert int(m.group(1)) == expected, (
            f"{rel} advertises {m.group(1)} but the registry has {expected} "
            f"(pattern {pattern!r}). Update the doc, or the counting rule in "
            f"docs/ARCHITECTURE.md if the definition really changed."
        )


def test_every_algorithm_is_listed_in_the_skill_library_tables():
    """The algorithms table must name every algorithm skill, not just the deterministic ones."""
    algos = [n for n, s in MANIFEST["skills"].items() if s["component"] == "algorithm"]
    for rel in ("docs/ARCHITECTURE.md", "site/architecture.html"):
        text = (REPO / rel).read_text(encoding="utf-8")
        row = next(ln for ln in text.splitlines()
                   if "algorithms" in ln and "hill-climb" in ln)
        for name in algos:
            assert name in row, f"{rel}: algorithms table omits {name!r}"
