# Prompt template — <skill-name>

> This is the prompt handed to the model when this skill drives an LLM step.
> Replace `{{placeholders}}` with values resolved from `inputs/INPUTS.md`.
> If a skill performs no LLM step (pure mechanical run), this file documents the
> reasoning the agent should follow instead.

## Role
You are <the role this step plays, e.g. "the evaluator" / "the diagnoser" / "the optimizer">.

## Context
{{context}}

## Task
{{task_instructions}}

## Constraints
- Honest evaluation is sacred: never peek at or score the test split here.
- {{additional_constraints}}

## Output
{{output_contract}}   # e.g. "Print a single JSON object: {...}"
