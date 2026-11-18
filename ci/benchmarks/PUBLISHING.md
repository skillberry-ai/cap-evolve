# Publishing a run to the benchmarks page, by hand

The [benchmarks page](https://skillberry-runs.github.io/dashboard/) (the skillberry-runs dashboard) is
normally filled in by each bench job's `Publish results to skillberry-runs` step in
`.github/workflows/benchmarks.yml` (`ci/benchmarks/lib/publish_results.sh`). This document is for the
case where that step never ran or published nothing — a run that was interrupted and resumed by hand,
a run driven directly on the runner, or a job that died before publishing.

Nothing here is a special "manual mode": you are running the same scripts the CI job runs, in the
same order.

## How the page gets its data

```
run dir  --metrics.py-->  metrics.jsonl + steps.jsonl
                          + runmeta.json (hand-written here; CI writes it in a workflow step)
                                    |
                             record.py build
                                    |
          records/<run_id>__<tier>-<bench>.json   in skillberry-runs/dashboard   (step 5)
          ci_ui/<run_id>__<tier>-<bench>/          in the benchmark's repo         (optional)
          ci_runs/<run_id>__<tier>-<bench>/        in the benchmark's repo         (optional, run_folder.py)
                                    |
             the dashboard deploys on that push and renders benchmarks.json from records/
```

Steps 1–4 below build the record here, with cap-evolve's scripts. Step 5, adding it (and optionally
its "Open UI" data) to the dashboard, is documented in the dashboard's own
[PUBLISHING.md](https://github.com/skillberry-runs/dashboard/blob/main/PUBLISHING.md): there is no separate Pages step, merging deploys it.

## Step 1 — collect the run dir

You need the `run_suite` directory (the one holding `state.json`, `baseline.json`, `final.json`).
If the run happened on the self-hosted runner, copy it locally first; a later dispatch **wipes**
that path, so archive before re-running anything:

```bash
RD=~/.cache/capevolve-gh-runner/_work/cap-evolve/cap-evolve/ci/benchmarks/.work/suite_<tier>_<bench>_proj/.capevolve/run_suite
ssh skillberry-1 "tar czf - -C $RD ." > /tmp/run_suite.tgz
mkdir -p /tmp/pub/run_suite && tar xzf /tmp/run_suite.tgz -C /tmp/pub/run_suite
```

**Check that `final.json` exists before going on.** If it doesn't, nothing fails loudly: step 2
still exits 0, every task gets `reward_opt: —`, and the report is mislabelled `train==val==test`
(FIT) because `metrics.py` falls back to the no-holdout path. Verified against a run killed before
finalize. Finish or resume the run first — the sanity check in step 4 is what catches this if you
forget.

## Step 2 — build metrics.jsonl and steps.jsonl

From a repo checkout:

```bash
mkdir -p /tmp/pub
python3 ci/benchmarks/lib/metrics.py suite /tmp/pub/run_suite \
  --bench spreadsheetbench --tier pilot \
  --agent azure/gpt-5.5 --optimizer-model claude-opus-4-8 --iters 6 \
  --jsonl /tmp/pub/metrics.jsonl --steps-jsonl /tmp/pub/steps.jsonl \
  > /tmp/pub/report.md
```

Set `--bench`/`--tier`/`--agent`/`--optimizer-model`/`--iters` to what the run actually used —
they are recorded verbatim and shown on the page. Skim `report.md` before going further; on a
held-out tier its first line must NOT say `train-fit, no holdout`.

**What the published row compares depends on the tier.** On a held-out tier (`pilot`, `full`) both
sides come from `final.json`: `test_baseline` (the seed) vs `test` (the best candidate) on the same
sealed split. On a no-holdout tier (`smoke`, where train == val == test) it is `baseline.json`'s val
vs `final.json` — a train-fit number. Know which one you are publishing before you quote it.

## Step 3 — write runmeta.json

CI generates this in its "Write run metadata" step; by hand, copy this and fix the values:

```bash
cat > /tmp/pub/runmeta.json <<'JSON'
{
  "run_id": 30987147147,
  "run_url": "https://github.com/skillberry-ai/cap-evolve/actions/runs/30987147147",
  "bench": "spreadsheetbench",
  "tier": "pilot",
  "event": "workflow_dispatch",
  "source": "manual publish — resumed after a host reboot killed the job at iteration 4",
  "pr": null,
  "branch": "main",
  "sha": "b378b44e50c4f8abfe3af93731c30b73cc058f82",
  "date": "2026-08-05T12:00:00Z",
  "iterations": 6,
  "trials": 1,
  "agent_model": "azure/gpt-5.5",
  "optimizer_model": "claude-opus-4-8",
  "gate_k_se": 0.2,
  "warm_seed": true,
  "conclusion": "success"
}
JSON
```

Four fields decide whether the row is right:

| field | rule |
|---|---|
| `conclusion` | must be exactly `"success"`, or `record.py` stores `suite: null` and the page shows `—` for the reward. **Only set it when the run really finished** (`final.json` present, finalize done). |
| `run_id` | a JSON **number**, and part of the record's filename. Reuse the Actions run id the work belongs to; with no Actions run at all, use any unique integer (e.g. `date +%s`). |
| `source` | free text shown on the page — **this is where you disclose that the run was published or resumed by hand.** Do not launder a hand-finished run as a clean CI one. |
| `date` | ISO-8601 UTC; the aggregate step sorts records by it (newest first). |

`pr` is `null` (unquoted) for anything not from a pull request.

## Step 4 — build the record

```bash
python3 ci/benchmarks/lib/record.py build /tmp/pub/metrics.jsonl \
  --runmeta /tmp/pub/runmeta.json --steps /tmp/pub/steps.jsonl \
  > /tmp/pub/30987147147__pilot-spreadsheetbench.json

# sanity check: the rollup must not be null
python3 -c "import json;r=json.load(open('/tmp/pub/30987147147__pilot-spreadsheetbench.json'));print(r['suite'])"
```

The filename **must** be `<run_id>__<tier>-<bench>.json`. That is what keeps `smoke` and `full` of
the same benchmark from overwriting each other, and re-publishing under the same name is how you
correct a record (idempotent).

## Step 5 — add it to the dashboard

Follow the dashboard's [PUBLISHING.md](https://github.com/skillberry-runs/dashboard/blob/main/PUBLISHING.md):

- **section A** adds the record file you just built to `skillberry-runs/dashboard/records/` with a pull
  request (it runs the same validation CI does, and merging deploys the dashboard);
- **section F** adds the run's "Open UI" data, if you want the row's **Open UI** link to work: export it
  with `capevolve_dashboard.export_static` (below), copy the `data/` folder to
  `<benchmark repo>/ci_ui/<run_id>__<tier>-<bench>/`, mask it with the dashboard's
  `scripts/mask_secrets.py`, and set `"has_ui": true` in the record.

```bash
PYTHONPATH=dashboard/backend python3 -m capevolve_dashboard.export_static \
  --base /tmp/pub --run-id run_suite --out /tmp/pub/ui/data      # /tmp/pub holds run_suite/
```

Only the data is needed: the dashboard has one shared viewer for every run.

- **section G** adds the run's folder (README, report, metrics, the optimized capability, the recipe),
  in the same layout CI uses. Build it with `run_folder.py`, copy it to
  `<benchmark repo>/ci_runs/<run_id>__<tier>-<bench>/`, mask it like the Open UI data, and set the
  record's `report_url` to its README page (rebuild the record with `--report-url`):

```bash
# /tmp/pub/out holds runmeta.json, metrics.jsonl, steps.jsonl, report.md (and optimized/ if you have it);
# --project is the run's .capevolve/project, --run-dir its run dir (for final.json)
python3 ci/benchmarks/lib/run_folder.py /tmp/pub/out /tmp/pub/ci_runs/30987147147__pilot-spreadsheetbench \
  --project /tmp/pub/project --run-dir /tmp/pub/run_suite --tier-dir ci/benchmarks/spreadsheetbench/pilot \
  --repo spreadsheetbench --has-ui
python3 ci/benchmarks/lib/record.py build /tmp/pub/metrics.jsonl --runmeta /tmp/pub/runmeta.json \
  --steps /tmp/pub/steps.jsonl --has-ui \
  --report-url https://skillberry-runs.github.io/dashboard/spreadsheetbench/ci_runs/30987147147__pilot-spreadsheetbench/README.html \
  > /tmp/pub/30987147147__pilot-spreadsheetbench.json
```

With a token that can push to skillberry-runs, `ci/benchmarks/lib/publish_results.sh <out_dir> <run_id>
<tier>-<bench>` does all of this (run folder, Open UI data, record) in one go, exactly as CI does.

## Repairing a record that is already published

If the row exists but shows `—` in the reward column, the record was built before the pairing fix
(#284) or from a truncated artifact. Do not rebuild it from scratch — repair it from the run's
`final.json`:

```bash
git clone git@github.com:skillberry-runs/dashboard.git /tmp/dash
python3 ci/benchmarks/utils/rebuild_record.py /tmp/pub/run_suite/final.json \
  /tmp/dash/records/<run_id>__<tier>-<bench>.json
```

Then send it as a pull request to the dashboard (step 5). It is idempotent, so running it on an
already-correct record changes nothing.

## Related

- The dashboard's [PUBLISHING.md](https://github.com/skillberry-runs/dashboard/blob/main/PUBLISHING.md) — adding records, Open UI data, write-ups and new benchmarks.
- `ci/benchmarks/README.md` — the benchmarks suite, tiers, and where CI publishes results.
- `.github/workflows/benchmarks.yml` — the CI path these steps mirror (`Write run metadata`,
  `Export CapEvolve UI snapshot`, `Publish results to skillberry-runs`).
