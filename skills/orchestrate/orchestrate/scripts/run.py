"""orchestrate — resolve capevolve.yaml + the manifest into a validated run plan.

Builds the ordered sequence from the manifest + spec (NOT a hardcoded list) and
validates the needs/provides DAG: walking the sequence, each step's ``needs``
tokens must already be satisfied by an upstream step's ``provides`` (or be
externally supplied — ``project``/``tasks`` come from intake/the adapter). A typo
in a meta ``needs``/``provides`` token, or a step ordered before its producer,
fails the plan loudly instead of silently running a broken pipeline.

The sequence now includes intake + the cap-evolve check gate before baseline. With
``--execute`` it hands off to ``cap-evolve run``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve.specfile import read_yaml

# Tokens not produced by any skill — supplied by intake / the project adapter.
EXTERNAL_TOKENS = {"project", "tasks"}

# The fixed pipeline shape (phases + the spec-selected algorithm). Capability +
# optimizer skills are not sequenced steps — they are *bound into* the algorithm
# step (the algorithm calls the optimizer; the capability defines the edit surface).
PHASE_ORDER = ["intake", "implement-and-check", "baseline", "<algorithm>", "finalize", "report"]


def _skills_dir() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "_registry" / "manifest.json").exists():
            return parent
        if (parent / "skills" / "_registry" / "manifest.json").exists():
            return parent / "skills"
    return None


def _load_manifest(skills_dir: Path) -> dict:
    return json.loads((skills_dir / "_registry" / "manifest.json").read_text())["skills"]


def _resolve_algorithm(name: str) -> str:
    """Old hill-climb skill names collapse to the one ``hill-climb`` skill."""
    if name in ("all-at-once", "cyclic", "hardest-first"):
        return "hill-climb"
    return name or "hill-climb"


def build_sequence(spec: dict) -> list[str]:
    algo = _resolve_algorithm(spec.get("algorithm_skill", "hill-climb"))
    return [algo if s == "<algorithm>" else s for s in PHASE_ORDER]


def validate_dag(sequence: list[str], manifest: dict) -> dict:
    """Check that every step's needs are satisfied by an upstream provides.

    Returns ``{ok, satisfied: [...], problems: [...]}``.
    """
    available = set(EXTERNAL_TOKENS)
    problems, trace = [], []
    for step in sequence:
        s = manifest.get(step)
        if s is None:
            problems.append(f"step {step!r} is not in the manifest")
            continue
        needs = list(s.get("needs", []) or [])
        missing = [n for n in needs if n not in available]
        if missing:
            problems.append(
                f"step {step!r} needs {missing} which no upstream step provides "
                f"(available so far: {sorted(available)})")
        trace.append({"step": step, "needs": needs,
                      "provides": list(s.get("provides", []) or []),
                      "missing": missing})
        available.update(s.get("provides", []) or [])
    return {"ok": not problems, "trace": trace, "problems": problems}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="orchestrate")
    p.add_argument("--spec", default=".capevolve/project/capevolve.yaml")
    p.add_argument("--project", default=".capevolve/project")
    p.add_argument("--execute", action="store_true", help="run the plan via `cap-evolve run`")
    args = p.parse_args(argv)

    spec = read_yaml(Path(args.spec).read_text()) if Path(args.spec).exists() else {}
    skills_dir = _skills_dir()
    manifest = _load_manifest(skills_dir) if skills_dir else {}

    sequence = build_sequence(spec)
    dag = validate_dag(sequence, manifest) if manifest else {
        "ok": False, "problems": ["no manifest found — run build_manifest.py"], "trace": []}

    plan = {
        "sequence": sequence,
        "dag_valid": dag["ok"],
        "dag": dag,
        "capabilities": spec.get("capabilities"),
        "optimizer": spec.get("optimizer_skill"),
        "algorithm": _resolve_algorithm(spec.get("algorithm_skill", "hill-climb")),
        "focus": spec.get("algorithm_focus"),
        "gate_mode": spec.get("gate_mode", "significant"),
        "budget": {"max_iterations": spec.get("max_iterations"), "stall": spec.get("stall")},
        "rule": "cap-evolve check must be green before baseline; test scored once at finalize.",
    }

    if not dag["ok"]:
        print(json.dumps(plan, indent=2))
        return 1

    if args.execute:
        from cap_evolve.cli import main as cli_main
        return cli_main(["run", "--spec", args.spec, "--project", args.project])

    print(json.dumps(plan, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
