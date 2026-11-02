## Surface contract (identical for every arm in this experiment)

You may edit **three surfaces**, and nothing else.

- `prompt.md`: the system prompt.
- `task_template.md`: the per-task user message.
  - Keep every placeholder it contains, exactly as written.
  - A candidate that breaks a placeholder scores 0 without running.
- `skills/<name>/SKILL.md` and `skills/<name>/scripts/*.py`: skills and their helper scripts.
  - Each `SKILL.md` is appended to the agent's system prompt.
  - Each script is importable inside the agent's kernel as `skills.<name>.<script>`. A hyphen in `<name>` becomes `_`, so `skills/spreadsheet-helpers/scripts/x.py` is imported as `skills.spreadsheet_helpers.x`.
  - Scripts cannot be run as a CLI: there is no `__main__`.

What the agent has:

- The agent's only tool is **Python code execution** in a Jupyter kernel.
- The task's input files are under `/mnt/data`, read-only.
- The answer must be written to the output workbook path given in the task message.

Rules for helper scripts:

- A helper must be **general, offline, deterministic and fast**.
- It must hold no task ids, no answer values and no task-specific branches.
- It must not use the network.
- It must never read gold files or the scorer.
- A lint and a smoke test enforce these rules before any rollout. A candidate that fails either scores 0 for that candidate and spends no agent rollouts.

**Prefer deterministic helpers for procedural failures.** When a recurring failure is a *procedure* the model gets wrong, move it into a helper and tell the agent when to call it. Examples are finding the header row, parsing dates or numbers, writing to the exact target range, and re-opening and checking the saved workbook. Do this rather than adding more prose. Keep prompt text for *judgment* calls.
