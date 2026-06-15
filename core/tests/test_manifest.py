"""The registry discovers every skill, with no errors and satisfiable wiring."""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SKILLS = REPO / "skills"


def test_build_manifest_clean(tmp_path):
    out = subprocess.run(
        [sys.executable, str(SKILLS / "_registry" / "build_manifest.py"), str(SKILLS)],
        capture_output=True, text=True,
    )
    assert out.returncode == 0, out.stderr
    manifest = json.loads((SKILLS / "_registry" / "manifest.json").read_text())
    assert manifest["errors"] == []
    names = set(manifest["skills"])
    # the proof-slice skills must all be present
    for required in ["intake", "implement-and-check", "baseline", "evaluate", "diagnose",
                     "gate", "finalize", "report", "all-at-once", "system-prompt",
                     "mock", "orchestrate"]:
        assert required in names, f"missing skill: {required}"


def test_every_skill_has_entry_and_check():
    manifest = json.loads((SKILLS / "_registry" / "manifest.json").read_text())
    for name, s in manifest["skills"].items():
        skill_dir = SKILLS / s["path"]
        assert (skill_dir / s["entry"]).exists(), f"{name}: missing entry {s['entry']}"
        assert (skill_dir / s["check"]).exists(), f"{name}: missing check {s['check']}"


def test_wiring_is_satisfiable():
    """Every `needs` token (except externally-supplied ones) is some skill's `provides`."""
    manifest = json.loads((SKILLS / "_registry" / "manifest.json").read_text())
    provided = set()
    for s in manifest["skills"].values():
        provided.update(s.get("provides", []))
    external = {"project", "tasks"}  # produced by intake/adapter at runtime
    for name, s in manifest["skills"].items():
        for tok in s.get("needs", []):
            assert tok in provided or tok in external, (
                f"{name} needs {tok!r} which no skill provides")
