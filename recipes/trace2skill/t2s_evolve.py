#!/usr/bin/env python3
"""Run ONE upstream Trace2Skill skill-evolution CLI unmodified, with the exp895 surface contract injected.

Usage: t2s_evolve.py <error|combined> <upstream CLI args...>
  error    -> skill_evolver.run_parallel_skill_evolution.main()           (error-driven skill)
  combined -> skill_evolver.run_parallel_combined_skill_evolution.main()  (error + success records)

The ONLY runtime change (deviation D4 in deviations_trace2skill.json): after each ParallelSkillEvolver /
CombinedParallelSkillEvolver is constructed, its proposer system prompts (MAP, MAP-from-patterns, MERGE) get
one extra section, inserted just before their "## Output Format" section:
  exp895/arms/common/SURFACE_CONTRACT.md VERBATIM (incl. its last paragraph "Prefer deterministic helpers ..."),
  followed by a short note saying how this skill folder maps onto those surfaces in the port.
No upstream file is edited. The final prompts are dumped to $T2S_PROMPT_DUMP (JSON) for audit.

Must be run with CWD = a dir holding skills/skill-creator/scripts/quick_validate.py (upstream resolves that path
against the CWD). The upstream repo is put on sys.path explicitly.
"""
import json
import os
import sys
from pathlib import Path

EXP = Path("/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895")
UP = EXP / "competitors" / "trace2skill"
sys.path.insert(0, str(UP))

MARK = "## Editable surfaces in this experiment (exp895 surface contract, verbatim)"
CONTRACT = (EXP / "arms" / "common" / "SURFACE_CONTRACT.md").read_text(encoding="utf-8").strip()
MAPPING = """## How this skill folder maps onto those surfaces (exp895 Trace2Skill port)

- This skill folder is `skills/spreadsheet-helpers/`. Its SKILL.md (frontmatter dropped) is appended to the
  agent's system prompt. Only the first 6,000 characters of the SKILL.md body reach the agent, and every
  `references/*.md` file that is not a script (below) is inlined at the end of SKILL.md, so it counts too.
- A helper script `skills/spreadsheet-helpers/scripts/<module>.py` is written in this folder as the reference file
  `references/script_<module>.md` (`<module>` = lowercase letters, digits and underscores). That file must contain
  exactly ONE ```python fenced block holding the module's complete source. It is exported as the script and
  is imported in the agent's kernel as `from skills.spreadsheet_helpers import <module>`. It does NOT count toward
  the 6,000 characters. Link it from SKILL.md like any reference file, and say there when to call each function.
- prompt.md and task_template.md are not editable in this arm."""
NOTE = f"{MARK}\n\n{CONTRACT}\n\n{MAPPING}\n"


def inject(prompt: str) -> str:
    if MARK in prompt:
        return prompt
    idx = prompt.find("## Output Format")
    return prompt + "\n\n" + NOTE if idx < 0 else prompt[:idx] + NOTE + "\n" + prompt[idx:]


def main():
    mode, rest = sys.argv[1], sys.argv[2:]
    import skill_evolver.parallel_evolving_agent as pea
    import skill_evolver.parallel_success_evolving_agent as psea

    dumped = {}

    def wrap(cls):
        orig = cls.__init__

        def __init__(self, *a, **k):
            orig(self, *a, **k)
            for attr in ("_map_system_prompt", "_map_patterns_system_prompt", "_merge_system_prompt"):
                if isinstance(getattr(self, attr, None), str):
                    setattr(self, attr, inject(getattr(self, attr)))
                    dumped[attr] = getattr(self, attr)
            if os.environ.get("T2S_PROMPT_DUMP"):
                Path(os.environ["T2S_PROMPT_DUMP"]).write_text(json.dumps({"class": type(self).__name__, **dumped},
                                                                          indent=1), encoding="utf-8")

        cls.__init__ = __init__

    wrap(pea.ParallelSkillEvolver)
    wrap(psea.CombinedParallelSkillEvolver)
    if mode == "error":
        from skill_evolver import run_parallel_skill_evolution as cli
    elif mode == "combined":
        from skill_evolver import run_parallel_combined_skill_evolution as cli
    else:
        sys.exit(f"unknown mode {mode!r}")
    sys.argv = [cli.__file__] + rest
    cli.main()


if __name__ == "__main__":
    main()
