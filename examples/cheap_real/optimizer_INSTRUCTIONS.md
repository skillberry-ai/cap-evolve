# Optimize the date-normalization system prompt

{{FOCUS_SUMMARY}}

You are editing **one file**: `prompt.txt` in your working directory. It is the system
prompt of an agent that is shown a date written in some human format and must reply
with that same date in ISO form, `YYYY-MM-DD`. That is the ONLY job. The agent is not
a trivia assistant: nothing about the date's historical significance is wanted, and
any such text makes the answer wrong.

The scorer is **exact match**, case-insensitively, after stripping whitespace. So a
correct date wrapped in prose scores **0** — a reply must be the bare date and nothing
else. Read `./trajectories/` to see exactly what the agent said instead.

{{FAILURES}}

{{TARGET_READER}}

## Rules
- Edit **only** `prompt.txt`. Nothing else here is yours to change; there is no tool
  code in this project, so ignore any generic advice about editing tools.
- **Never** hard-code an answer, a task input, or a specific date into the prompt. The
  prompt is scored on held-out dates it has never seen, so a memorized date earns
  nothing and is reward hacking — the tamper guard and the sealed test split catch it.
- Prefer one precise, general rule over a list. The reader is a small local model
  (~3B): short, unambiguous, imperative instructions land; nuance does not.
- Keep the prompt under ~10 lines, then STOP. The harness re-scores you; do not run
  the evaluation yourself.

## What works here
State the output contract explicitly: the exact format, that it is the *only* thing to
emit, and that no explanation, greeting, or trailing punctuation may be added. Say
"four-digit year, two-digit month, two-digit day" out loud — small models otherwise
emit `2021-3-3`, which exact-match scores 0.
