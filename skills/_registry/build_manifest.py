#!/usr/bin/env python3
"""Walk skills/<component>/*/meta.yaml and emit manifest.json.

This is the discovery mechanism that makes the library extensible: drop a skill
directory under the right component, fill its meta.yaml, run this script, and the
orchestrator can find and wire it by its `needs`/`provides` tokens. Re-runnable
any time; the installer runs it after copying skills.

Zero dependencies: a tiny tolerant parser for the constrained YAML we author
ourselves (uses PyYAML if it happens to be installed, else the builtin reader).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

COMPONENTS = ["orchestrate", "phases", "capabilities", "algorithms", "optimizers"]
REQUIRED = ["component", "name", "entry", "check"]


# Use the canonical YAML reader from cap_evolve.specfile (no duplicate parser).
_CORE = Path(__file__).resolve().parents[2] / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))
try:
    from cap_evolve.specfile import read_frontmatter, read_yaml
except Exception as e:  # pragma: no cover
    raise SystemExit(f"build_manifest needs cap_evolve.specfile (expected at {_CORE}): {e}")


# ---- manifest build --------------------------------------------------------

def build(skills_root: Path) -> dict:
    """Discover skills under ``skills_root``.

    Handles BOTH layouts: the repo's ``<component>/<skill>/meta.yaml`` AND a flat
    install (``<skill>/meta.yaml`` directly under the root, as hosts lay skills
    out). Any directory containing a ``meta.yaml`` is a skill; its component comes
    from the meta. ``_registry`` is skipped.
    """
    skills_root = Path(skills_root)
    manifest = {"skills": {}, "errors": []}
    meta_paths = sorted(p for p in skills_root.rglob("meta.yaml")
                        if "_registry" not in p.parts)
    for meta_path in meta_paths:
        skill_dir = meta_path.parent
        skill_md = skill_dir / "SKILL.md"
        meta = read_yaml(meta_path.read_text(encoding="utf-8"))
        missing = [k for k in REQUIRED if k not in meta or meta.get(k) in (None, "")]
        if missing:
            manifest["errors"].append(f"{meta_path}: missing required fields {missing}")
            continue
        name = str(meta["name"])
        fm = read_frontmatter(skill_md) if skill_md.exists() else {}
        manifest["skills"][name] = {
                "component": meta["component"],
                "path": str(skill_dir.relative_to(skills_root)),
                "summary": meta.get("summary", fm.get("description", "")),
                "entry": meta.get("entry"),
                "abstract": meta.get("abstract"),
                "check": meta.get("check"),
                "prompt": meta.get("prompt"),
                "inputs": meta.get("inputs"),
                "needs": meta.get("needs", []),
                "provides": meta.get("provides", []),
                "compatible_with": meta.get("compatible_with", {}),
            }
    return manifest


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    skills_root = Path(argv[0]) if argv else Path(__file__).resolve().parent.parent
    manifest = build(skills_root)
    out = skills_root / "_registry" / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    n = len(manifest["skills"])
    print(f"wrote {out} ({n} skill(s))")
    if manifest["errors"]:
        print("errors:", file=sys.stderr)
        for e in manifest["errors"]:
            print(f"  - {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
