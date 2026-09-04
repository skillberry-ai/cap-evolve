"""memory/wiki has no executable step of its own — the format is applied by the optimizer
writing files directly under <run_dir>/wiki/ (see SKILL.md), and the copy-into-guidance
step lives in harness.py's `_inject_memory_skill_guidance`. This entry just points there,
so `entry:` in meta.yaml resolves to real, working code rather than a stub."""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    print("memory/wiki is a format contract, not a run step — read "
          f"{Path(__file__).resolve().parents[1] / 'SKILL.md'} and write to "
          "<run_dir>/wiki/ directly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
