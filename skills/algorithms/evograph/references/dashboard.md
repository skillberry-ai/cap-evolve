# Dashboard — the agent ↔ UI contract

The dashboard is a **read-only** viewer. A small FastAPI backend (launched by `bootstrap.py`,
`cwd = <run_dir>/`) reads the files below and serves a prebuilt React app at `/`. **Agents never call
the backend** — they only write these files, and the UI reflects them within a couple of seconds.

So: *anything you want the user to see, write into one of these files in this format.*

## Files agents write

### Per-round metrics → `wiki/results/round-<N>.json` (and `final-test.json`)

```json
{
  "round": 1,
  "split": "train",
  "started_at": "2026-06-28T14:00:00+03:00",
  "completed_at": "2026-06-28T14:04:12+03:00",
  "num_tasks": 30,
  "metrics": {
    "reward":   { "value": 0.62, "primary": true,  "direction": "higher" },
    "avg_steps":{ "value": 14.3, "primary": false, "direction": "lower"  }
  },
  "per_task": [ { "task_id": "0", "reward": 1.0, "avg_steps": 9 } ],
  "extra": { "num_trials": 3, "concurrency": 4, "note": "anything else worth keeping on the record" }
}
```

The UI builds the metric-over-rounds timeline from the **round** files. Write **one file per round**
(`round-1.json`, `round-2.json`, …) as that round completes — a missing round file is a gap on the
timeline.

`final-test.json` is the same shape with `"split": "test"` and `"round": "final"`. The held-out test
is rendered in its **own Final-test panel**, not plotted on the rounds line — so put it **only** in
`final-test.json`, never in a `round-<N>.json`, or it will look like just another round.

- **`metrics`** — every metric **must** be the wrapped object `{ value, primary, direction }`, never
  a flat number. The timeline reads each metric's `.value`, so a bare `"reward": 0.62` charts as an
  empty graph. Exactly one metric is `"primary": true`; `direction` is `"higher"` or `"lower"`.

- **`started_at` / `completed_at`** — round-start eval time and round-end time; their difference is
  the round's duration (the UI shows per-round bars + the total). Stamp both from the shared clock
  script so every file agrees on the time **and** timezone (the user's PC local time):
  `python scripts/now.py`. `completed_at` is absent while the round is still running
  (the UI shows it as "running"). (`timestamp` is still accepted as a legacy alias for `started_at`.)
- **`cost_usd`** (optional) — **one** number for the whole optimization (the agents' conversation
  cost, not the benchmark eval spend), recorded on **`final-test.json`** at the very end — never
  per-round. The UI shows it next to the total time. See [cost.md](cost.md).
- **`extra`** (optional, free-form) — a catch-all object for anything you want recorded but that the
  UI doesn't render: the run-params actually used (trials-per-task, concurrency), seeds, notes,
  links, whatever. **The dashboard ignores fields it doesn't know**, so adding your own keys here (or
  anywhere in these files) is always safe.

### Weakness nodes → `wiki/weaknesses/<slug>.md`

Front-matter drives the graph: `slug, status (open|in-progress|completed|solved|reverted), tags,
discovered_in_round, attacked_in_rounds, solved_in_round, reverted_in_rounds, branch,
affected_tasks, solutions`. Schema + example: [clustering.md](clustering.md).

### Solutions → `wiki/solutions/<weakness-slug>/<sol-id>/{solution.md,changes.diff}`

Front-matter drives the solution cards (`outcome, primary_metric, secondary_metrics, new_record,
timestamp, …`) and `changes.diff` drives the diff tabs. Schema: [graph.md](graph.md).

### Live progress → `runs/round-<N>/agents/<weakness-slug>.log`

Append-only, one line per step (free text). The solver assigned to a weakness appends here as it
works; the UI streams it live in the weakness detail panel. Just append — no format ceremony. If a
line doesn't already start with a `HH:MM[:SS]` time, the dashboard prefixes it with the **local time
of the machine running the dashboard** (i.e. your timezone), so timestamps stay consistent — the
same clock as `scripts/now.py`.

## API the backend exposes (for reference; agents don't call it)

- `GET /api/graph` → weakness nodes (`slug, status, tags, num_solutions, has_record, related, …`) +
  **edges between related weaknesses** (from each weakness's `related` field). The UI lays this out as
  a graph (dagre) and offers a status filter (solved / completed / in-progress / open / reverted). Solutions are not graph
  nodes — they live in the weakness detail.
- `GET /api/weakness/{slug}` → front-matter + rendered markdown + its solutions + per-task metric
  history.
- `GET /api/solution/{weakness}/{sol_id}` → rendered markdown + `changes.diff` + metric + record flag.
- `GET /api/results` → the metric-over-rounds series from `wiki/results/*.json`.
- `GET /api/run-config` → the run's `<run_dir>/run-config.json` (free-form; optional). If you drop a
  `run-config.json` in the `<run_dir>/` dir, a **Run config** button appears in the header and opens a
  pretty, generic view of whatever JSON is there — no schema required.
- `GET /api/progress/{slug}/stream` → Server-Sent Events tailing the weakness's latest agent log.

## What this buys the agents

No registration, no build step, no API client. Write a markdown file or append a log line and the
user sees it. The wiki stays the single source of truth (see
[the SKILL.md honesty rules](the SKILL.md honesty rules)).
