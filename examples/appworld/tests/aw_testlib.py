"""Shared helpers for the AppWorld example's offline tests (no AppWorld install, no model call)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
REPO = EX.parents[1]
for p in (EX / "adapters", EX / "altk", EX / "scripts", REPO / "core"):
    # core/ last-resort: cap_evolve normally comes from the installed package (examples/parsec does the same)
    if str(p) not in sys.path:
        sys.path.append(str(p)) if p.name == "core" else sys.path.insert(0, str(p))

TRAIN_INSTRUCTION = "Move all songs from my workout playlist to a new playlist called cardio mix please"


def make_root(tmp: Path) -> Path:
    """A tiny fake APPWORLD_ROOT: one train and one dev task, two apps of API docs."""
    data = tmp / "data"
    (data / "datasets").mkdir(parents=True)
    (data / "datasets" / "train.txt").write_text("aaa1111_1\n")
    (data / "datasets" / "dev.txt").write_text("bbb2222_1\n")
    for tid, instr, email in (("aaa1111_1", TRAIN_INSTRUCTION, "jane.roe@example.com"),
                              ("bbb2222_1", "How many alarms do I have set on my phone today", "joe@example.com")):
        (data / "tasks" / tid).mkdir(parents=True)
        (data / "tasks" / tid / "specs.json").write_text(json.dumps({
            "instruction": instr,
            "supervisor": {"first_name": "Jane", "last_name": "Roe", "email": email, "phone_number": "5550001111"}}))
    (data / "api_docs" / "standard").mkdir(parents=True)
    (data / "api_docs" / "standard" / "spotify.json").write_text(json.dumps({"login": {}, "show_playlist": {}}))
    (data / "api_docs" / "standard" / "phone.json").write_text(json.dumps({"show_alarms": {}}))
    return tmp
