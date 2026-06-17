# core-wiring — threading optimizer cost into the iteration store

The runner already *emits* cost: `run.py --json` prints
`{"cost": {"total_cost_usd": <float|null>, "tokens": <int|null>}}` on stdout. What
the engine still needs is to (a) ask for it and (b) record it. Both are small,
**core-owned** changes — they are listed here for the core owner to apply (Wave 5
must not edit `core/cap_evolve/cli.py`, so this is a request, not a patch).

## Where cost is produced vs consumed
`cli.py::_cmd_run` does **not** call the optimizer directly. It builds `opt_cmd`
and passes it to the algorithm skill via `--optimizer`; the algorithm's `run.py`
shells `opt_cmd` once per proposal. So:

- **cli.py** only needs to *opt in* to JSON when the spec asks.
- the **algorithm run.py** (hill-climb / gepa / skillopt) is where the optimizer
  subprocess output is already read, so it parses the `cost` block and records it.

## Requested change 1 — cli.py opts the optimizer into JSON (≈2 lines)
In `_cmd_run`, after `opt_cmd` is assembled (around the `optimizer_model` block):

```python
# opt-in headless cost capture: spec `optimizer_json: true` (or env) appends --json
if spec.get("optimizer_json") or os.environ.get("CAPEVOLVE_OPTIMIZER_JSON") == "1":
    opt_cmd += " --json"
if spec.get("optimizer_json_schema"):
    opt_cmd += f" --json-schema {shlex.quote(str(spec['optimizer_json_schema']))}"
```

Default off → the prose-fed path and the offline `mock`/`generic` rows are
unchanged. `run-optimizer` already no-ops `--json` for rows with an empty
`json_flag`, so this is safe even if a spec turns it on with a non-JSON CLI.

## Requested change 2 — store the parsed cost (already supported)
`RunDir.update_spent(...)` already accumulates `usd` (runner cost). The optimizer
cost is conceptually separate ("optimizer vs runner" split in the dashboard), so
either:

- **Minimal:** fold it into `usd` at the call site in the algorithm run.py:
  `rd.update_spent(usd=cost_usd, optimizer_seconds=elapsed)` — works today, no
  core change.
- **Preferred (one field):** add `optimizer_usd` to `rundir.Spent` (mirroring the
  existing `runner_tokens`/`optimizer_seconds` split) and pass it through
  `update_spent(..., optimizer_usd=cost_usd)`. The dashboard's "optimizer vs
  runner cost" panel then has a clean source. This is the only field-level core
  change requested; everything else is additive at the call site.

## What the algorithm run.py does with the runner output (no core change)
When it shells `opt_cmd` (now possibly ending in `--json`), parse the JSON it
already captures:

```python
res = json.loads(proc.stdout.splitlines()[-1])     # run-optimizer's result line
cost = (res.get("cost") or {}).get("total_cost_usd")
if cost is not None:
    rd.update_spent(usd=cost)        # or optimizer_usd=cost once the field exists
```

`cost` is `None` whenever JSON wasn't requested or wasn't parseable, so this is a
pure best-effort add: the loop never breaks on a CLI that printed prose, and the
offline mock path (no `--json`, empty `json_flag`) never reaches it.

## Summary of what is needed from the core owner
1. cli.py: ~2 lines to append `--json` (+ optional `--json-schema`) when
   `optimizer_json` is set in the spec. **(blocked on you — W5 cannot touch cli.py)**
2. *(optional, preferred)* `rundir.Spent.optimizer_usd` field + a kwarg in
   `update_spent`, for a clean optimizer-vs-runner cost split.
3. algorithm run.py: read `result["cost"]["total_cost_usd"]` and call
   `update_spent`. (Owned by the algorithms; additive, no contract change.)
