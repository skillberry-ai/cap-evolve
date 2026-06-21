#!/usr/bin/env python3
"""Walk ``skills/**/meta.yaml`` and emit a VALIDATED ``manifest.json``.

``meta.yaml`` is the single source of truth for a skill's name/component/wiring;
this script is the gate that keeps that truth honest. It (1) discovers every
skill, (2) validates each meta against a real vocabulary, (3) checks the
referenced ``entry``/``abstract``/``check`` files exist, (4) checks the SKILL.md
frontmatter ``name``/``component`` agree with the meta, and (5) **fails the build
loudly** (nonzero exit, errors listed) on any violation — so a typo in a
``component`` or a ``needs`` token can never silently produce a broken pipeline.

Re-runnable any time; the installer runs it after copying skills. Zero deps
beyond ``cap_evolve.specfile`` (the canonical tolerant YAML reader).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Components are SINGULAR (matching what meta.yaml actually carries); the old list
# had plurals that matched nothing, so validation was dead. The directory layout
# uses the plural (skills/<plural>/<skill>/) but the meta `component` is singular.
COMPONENTS = {"phase", "capability", "algorithm", "optimizer", "orchestrate"}

# The needs/provides token vocabulary. Every needs/provides entry must be one of
# these; a misspelling ("score" for "scores") fails the build instead of silently
# breaking the orchestrate DAG.
TOKENS = {
    "project", "tasks", "splits", "baseline", "candidate", "scores", "traces",
    "reflective_dataset", "decision", "report", "checked",
}

REQUIRED = ["component", "name", "entry", "check"]


_CORE = Path(__file__).resolve().parents[2] / "core"
if str(_CORE) not in sys.path:
    sys.path.insert(0, str(_CORE))
try:
    from cap_evolve.specfile import read_frontmatter, read_yaml
except Exception as e:  # pragma: no cover
    raise SystemExit(f"build_manifest needs cap_evolve.specfile (expected at {_CORE}): {e}")


def _validate_meta(meta: dict, skill_dir: Path, skill_md: Path, errors: list[str]) -> None:
    """Append a message to ``errors`` for each violation in this skill's meta."""
    where = skill_dir.name

    missing = [k for k in REQUIRED if k not in meta or meta.get(k) in (None, "")]
    if missing:
        errors.append(f"{where}: missing required meta fields {missing}")
        return

    comp = meta.get("component")
    if comp not in COMPONENTS:
        errors.append(f"{where}: component {comp!r} not in {sorted(COMPONENTS)}")

    for field in ("needs", "provides"):
        for tok in meta.get(field, []) or []:
            if tok not in TOKENS:
                errors.append(f"{where}: {field} token {tok!r} not in the token vocabulary "
                              f"{sorted(TOKENS)}")

    # Referenced script paths must exist.
    for field in ("entry", "abstract", "check"):
        rel = meta.get(field)
        if rel and not (skill_dir / rel).exists():
            errors.append(f"{where}: {field} path {rel!r} does not exist")

    # Frontmatter must agree with meta (single source of truth).
    if skill_md.exists():
        fm = read_frontmatter(skill_md)
        if fm.get("name") and fm["name"] != meta["name"]:
            errors.append(f"{where}: SKILL.md frontmatter name {fm['name']!r} "
                          f"!= meta name {meta['name']!r}")
        if fm.get("component") and fm["component"] != comp:
            errors.append(f"{where}: SKILL.md frontmatter component {fm['component']!r} "
                          f"!= meta component {comp!r}")
    else:
        errors.append(f"{where}: no SKILL.md")


def build(skills_root: Path) -> dict:
    """Discover + validate skills under ``skills_root``."""
    skills_root = Path(skills_root)
    manifest = {"skills": {}, "errors": []}
    meta_paths = sorted(p for p in skills_root.rglob("meta.yaml")
                        if "_registry" not in p.parts)
    for meta_path in meta_paths:
        skill_dir = meta_path.parent
        skill_md = skill_dir / "SKILL.md"
        meta = read_yaml(meta_path.read_text(encoding="utf-8"))

        before = len(manifest["errors"])
        _validate_meta(meta, skill_dir, skill_md, manifest["errors"])
        if len(manifest["errors"]) > before:
            continue  # don't register an invalid skill

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

    # Cross-skill: every needs token must be some skill's provides, or external.
    external = {"project", "tasks"}
    provided = set(external)
    for s in manifest["skills"].values():
        provided.update(s.get("provides", []) or [])
    for name, s in manifest["skills"].items():
        for tok in s.get("needs", []) or []:
            if tok not in provided:
                manifest["errors"].append(
                    f"{name}: needs {tok!r} which no skill provides")
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
        print("VALIDATION ERRORS:", file=sys.stderr)
        for e in manifest["errors"]:
            print(f"  - {e}", file=sys.stderr)
        return 1
    by_comp: dict[str, list[str]] = {}
    for name, s in sorted(manifest["skills"].items()):
        by_comp.setdefault(s["component"], []).append(name)
    for comp in sorted(by_comp):
        print(f"  {comp}: {', '.join(by_comp[comp])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
