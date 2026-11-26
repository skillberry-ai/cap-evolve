

## The agent harness (this benchmark): a third editable surface

Besides `policy/policy.md` and `tools/tools.py`, you may edit the harness around the model.
Full guidance: `./guidance/agent-harness/SKILL.md` (read its "Cross-run memory" section
before the first lesson).

**Files**

- `harness.json` — settings the tau2 adapter applies. Only these are wired; any other key
  changes nothing:

  | Setting | Effect in tau2 | Seed |
  |---|---|---|
  | `memory.mode` | `all`: every lesson is appended to the system prompt. `retrieved`: only the `memory.top_k` lessons whose `when`/`tags` best match the user's first message. `off`: none. | `all` |
  | `memory.top_k`, `memory.max_entries` | how many lessons are injected / kept | — / 30 |
  | `loop.think_tool` | adds a no-op `think(thought)` tool the agent can call between tool results | `false` |
  | `loop.repeat_limit` | `N >= 2`: the N-th identical tool call in a row is replaced by one re-generation with a "do not repeat, reconsider" note | `0` (off) |
  | `loop.max_steps` | step cap for one conversation | `100` |
  | `sampling.temperature` | the agent's temperature | unset (model default) |

- `memory/lessons.jsonl` — lessons from earlier runs, one JSON object per line:
  `{"id", "when", "do", "evidence", "source_split", "tags"?, "steps"?}`. The agent reads
  them at the start of each conversation; it never writes them.

Hooks (`hooks/*.py`) are NOT wired in tau2. Do not write any.

**Rules**

1. A lesson states a GENERAL rule from a failure CLUSTER: a trigger (`when`) the agent can
   recognize from the conversation, and the action (`do`). Never a reservation id, user id,
   flight number, date or amount from one task.
2. `evidence` names the cluster and how many traces show it; `source_split` is `train` or
   `val`, never `test`.
3. Add or update individual lines; do not rewrite the whole file. Keep the detail that
   makes the lesson usable.
4. A lesson and a `policy.md` rule must not disagree. If the policy already states the rule
   and the agent ignores it, a lesson is the right form only when it adds the trigger the
   agent misses; otherwise fix the policy or enforce it in `tools.py`.
5. `memory.write_during_eval` stays `false`.
6. In `PROCESS.md`, list each harness change (setting or lesson id) → cluster → tasks, as
   for any other edit.
