"""intake — Phase 0: mine existing artifacts, then scaffold the cap-evolve project.

What the SCRIPT does (this file):
  1. **capture-intent / mine first** — scan the working dir for artifacts a run can
     reuse (task files, an existing capability/prompt/tools surface, an existing
     adapter, a benchmark runtime) so the agent doesn't re-author what already
     exists. The findings are reported under ``discovered``.
  2. **scaffold** — copy ``templates/project`` into ``.capevolve/project`` (adapter
     stub, inputs/, capevolve.yaml, PROJECT.md).

What the OPTIMIZER AGENT does (driven by SKILL.md, not this script): decide the
capability/optimizer/algorithm, **implement the 4 adapter methods**, and fill the
spec. What the USER does: supply NEEDED inputs the agent cannot infer.

Advancing past intake is gated by ``implement-and-check`` (runs ``cap-evolve
check`` and refuses to proceed until the adapter contract is green).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

# Filename hints used to mine reusable artifacts from the working directory.
_TASK_HINTS = ("tasks.jsonl", "tasks.json", "dataset.jsonl", "data.jsonl")
_CAP_HINTS = ("prompt.txt", "policy.md", "tools.json", "SKILL.md", "system_prompt.txt")


def find_templates() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        t = parent / "templates" / "project"
        if t.is_dir():
            return t
    raise FileNotFoundError("templates/project not found; run from the repo or set --templates")


def mine_artifacts(workdir: Path) -> dict:
    """Best-effort scan for things a run can reuse (mine existing work first)."""
    workdir = Path(workdir)
    skip = {".git", "__pycache__", ".capevolve", "node_modules", ".venv"}

    def _walk(pred):
        out = []
        for p in workdir.rglob("*"):
            if any(part in skip for part in p.parts):
                continue
            if p.is_file() and pred(p):
                out.append(str(p.relative_to(workdir)))
        return sorted(out)[:50]

    return {
        "task_files": _walk(lambda p: p.name in _TASK_HINTS),
        "capability_artifacts": _walk(lambda p: p.name in _CAP_HINTS),
        "existing_adapters": _walk(lambda p: p.name == "adapter.py"
                                   and ".capevolve" not in p.parts),
    }


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="intake")
    p.add_argument("--base", default=".capevolve")
    p.add_argument("--workdir", default=".", help="dir to mine for reusable artifacts")
    p.add_argument("--templates", default=None)
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    discovered = mine_artifacts(Path(args.workdir))

    tmpl = Path(args.templates) if args.templates else find_templates()
    project = Path(args.base) / "project"
    if project.exists() and not args.force:
        print(json.dumps({"project": str(project), "status": "exists",
                          "discovered": discovered,
                          "note": "use --force to overwrite"}, indent=2))
        return 0
    if project.exists():
        shutil.rmtree(project)
    shutil.copytree(tmpl, project)

    created = sorted(str(q.relative_to(project)) for q in project.rglob("*") if q.is_file())
    print(json.dumps({
        "project": str(project),
        "status": "scaffolded",
        "discovered": discovered,
        "created": created,
        "next": [
            "reuse the discovered artifacts where possible (don't re-author them)",
            "implement the 4 methods in adapters/adapter.py",
            "fill capevolve.yaml (capability / optimizer / algorithm / budget)",
            "resolve NEEDED inputs (ask the user for any that are missing)",
            "run: cap-evolve check " + str(project) + "  (implement-and-check gates this)",
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
