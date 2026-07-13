# Run cost (one number, asked at the very end)

Report how much the **agents' conversation** cost to run EvoGraph — *not* the benchmark's eval API
spend. It is **one total for the whole optimization**, not per round.

**Timing — strict ordering.** Never stop the optimization in the middle to ask about cost: the
waiting-for-the-user time would otherwise count as optimization time and make the round timings
wrong. Only after **everything** has finished — stop condition met, final test done, all
`started_at`/`completed_at` stamped so the time comparison is fully ready — do you ask.

**Then ask the user for the cost** (don't leave it blank):

- **Claude Code:** ask the user to run **`/cost`** and tell you the dollar figure.
- **Other harnesses:** ask the user for their session usage/cost readout (or to read it from wherever
  their tool shows it).

Write the single number you get into **`wiki/results/final-test.json`** as **`cost_usd`** (one field,
the whole-run total). The dashboard shows it next to the total run time. Only omit `cost_usd` if the
user genuinely can't get a figure.
