"""The DSPy program that MIPROv2 optimizes in the exp895 miprov2 arm. Its class source is what MIPRO's
program-aware proposer reads, so it is kept short and gold-free.

Its forward() never calls a DSPy LM: it hands the program's own instructions and demos to the arm,
which renders them into a candidate directory and scores it with the common exp895 rollout
(CommonRollout.evaluate, k=3 inside the call)."""
import dspy

ARM_HOOK = {"run": None}   # set by miprov2_arm.py: run(program, task_id, inputs) -> dspy.Prediction


class SolveSpreadsheetTask(dspy.Signature):
    """(replaced at start-up by the v2 seed prompt.md)"""

    instruction: str = dspy.InputField(desc="the spreadsheet manipulation question")
    instruction_type: str = dspy.InputField(desc="Cell-Level Manipulation or Sheet-Level Manipulation")
    answer_position: str = dspy.InputField(desc="the cell(s) or range the answer must be written to")
    solution_code: str = dspy.OutputField(desc="the final Python code that wrote the correct answer workbook")


class SpreadsheetAgentProgram(dspy.Module):
    """A SpreadsheetBench agent, optimized as two instruction modules.

- `agent`: its instructions are the agent's SYSTEM PROMPT (`prompt.md`), and its demos are appended to that
  prompt under "## Worked examples" (each demo = a solved task + the final solution code that solved it).
  The agent itself is a multi-turn Python code-execution agent: each turn it writes one Python code block,
  the code runs in a Jupyter kernel, and the output comes back, until the answer workbook is written.
- `skill`: its instructions are the full text of `skills/spreadsheet-helpers/SKILL.md`, which is appended to
  the same system prompt. Keep its YAML frontmatter (the `name:` and `description:` lines).
- Each candidate is scored by running the real agent 3 times per task and averaging the hard pass rate.

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

In this optimizer only two instruction texts are proposed: `prompt.md` (module `agent`) and `SKILL.md`
(module `skill`). `task_template.md` and the helper scripts stay fixed, and no helper scripts exist in
this candidate, so an instruction must never describe or call one.
"""

    def __init__(self):
        super().__init__()
        self.agent = dspy.Predict(SolveSpreadsheetTask)
        self.skill = dspy.Predict(SolveSpreadsheetTask)

    def forward(self, task_id, instruction, instruction_type, answer_position):
        return ARM_HOOK["run"](self, task_id, {"instruction": instruction, "instruction_type": instruction_type,
                                               "answer_position": answer_position})
