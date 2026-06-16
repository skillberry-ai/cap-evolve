"""intake — scaffold the per-run cap-evolve project from the template.

Creates ``.capevolve/project/`` (adapters stub, inputs/, capevolve.yaml, PROJECT.md) so
the agent can fill the 4-method adapter and run spec. This is the mechanical part
of intake; the *interview* (deciding capability/optimizer/algorithm/inputs and
asking the user for missing NEEDED inputs) is driven by SKILL.md + INPUTS.md.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def find_templates() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        t = parent / "templates" / "project"
        if t.is_dir():
            return t
    raise FileNotFoundError("templates/project not found; run from the repo or set --templates")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="intake")
    p.add_argument("--base", default=".capevolve")
    p.add_argument("--templates", default=None)
    p.add_argument("--force", action="store_true")
    args = p.parse_args(argv)

    tmpl = Path(args.templates) if args.templates else find_templates()
    project = Path(args.base) / "project"
    if project.exists() and not args.force:
        print(json.dumps({"project": str(project), "status": "exists",
                          "note": "use --force to overwrite"}))
        return 0
    if project.exists():
        shutil.rmtree(project)
    shutil.copytree(tmpl, project)

    created = sorted(str(p.relative_to(project)) for p in project.rglob("*") if p.is_file())
    print(json.dumps({
        "project": str(project),
        "status": "scaffolded",
        "created": created,
        "next": [
            "implement the 4 methods in adapters/adapter.py",
            "fill capevolve.yaml (capability / optimizer / algorithm / budget)",
            "resolve NEEDED inputs (ask the user for any that are missing)",
            "run: cap-evolve check " + str(project),
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
