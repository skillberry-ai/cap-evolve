"""Self-check for memory/wiki: the format contract SKILL.md still documents the file
paths ``harness.WikiMemory`` and its pointer text promise the optimizer."""

from __future__ import annotations

import sys
from pathlib import Path

_REQUIRED_MENTIONS = ("wiki/weaknesses", "wiki/solutions", "wiki/results")


def main() -> int:
    skill_md = Path(__file__).resolve().parents[1] / "SKILL.md"
    text = skill_md.read_text(encoding="utf-8")
    missing = [m for m in _REQUIRED_MENTIONS if m not in text]
    if missing:
        print(f"check failed: {skill_md} no longer documents {missing}")
        return 1
    print("ok")
    return 0


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        sys.exit(main())
    sys.exit(main())
