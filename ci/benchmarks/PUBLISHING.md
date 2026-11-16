# Publishing a run to the benchmarks page, by hand

The [benchmarks page](https://skillberry-ai.github.io/cap-evolve/benchmarks.html) is normally
filled in by the `aggregate history` job in `.github/workflows/benchmarks.yml`. This document is
for the case where that job never ran or produced nothing — a run that was interrupted and
resumed by hand, a run driven directly on the runner, or a job that died before uploading its
artifact.

Nothing here is a special "manual mode": you are running the same three scripts the CI job runs,
in the same order.

## Where the record goes

Steps 1–4 build one record file. **Where you put it** (step 5) depends on where you want it to show:

| Destination | Use it for | What it needs |
|---|---|---|
| **The dashboard** — [`skillberry-runs/dashboard`](https://github.com/skillberry-runs/dashboard), shown at <https://skillberry-runs.github.io/dashboard/> | Hand-published runs and new experiments. **The recommended place.** | A pull request adding the record there |
| **`benchmark-history`** on this repo | What CI still does; also shows the row on this site's benchmarks page | A push to the branch, then a Pages deploy |

The two do not feed each other automatically. A row added only to the dashboard does **not** appear on
this site's `benchmarks.html`, and a row on `benchmark-history` reaches the dashboard only when its
**Sync from cap-evolve** workflow is run. The dashboard's
[PUBLISHING.md](https://github.com/skillberry-runs/dashboard/blob/main/PUBLISHING.md) covers everything on
that side: adding rows, write-ups, new benchmarks, syncing, and tokens.

## How the page gets its data

```
run dir  --metrics.py-->  metrics.jsonl + steps.jsonl
                          + runmeta.json (hand-written here; CI writes it in a workflow step)
                                    |
                             record.py build
                                    |
                     records/<run_id>__<tier>-<bench>.json   on the benchmark-history branch
                                    |
                       (Pages deploy clones benchmark-history, runs record.py aggregate)
                                    |
                       benchmarks.json + meta.json           rendered into the Pages artifact,
                                    |                          NOT committed to the branch
                    site/benchmarks.js fetches it same-origin from the deployed site
```

`benchmarks.json`/`meta.json` are rendered fresh from `records/` **at Pages-deploy time**
(`.github/workflows/pages.yml`) — they are never committed to `benchmark-history`. So **a push to
that branch is NOT enough on its own**: `pages.yml` only auto-runs off the *Benchmarks* workflow
completing, and a manual publish bypasses that trigger entirely. After pushing your record (step
5), you must also trigger **Actions → Deploy GitHub Pages → Run workflow** (`workflow_dispatch`)
before the new row shows up on the page.

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

## Step 5 — publish the record

### Option 1 (recommended): the dashboard

```bash
git clone git@github.com:skillberry-runs/dashboard.git /tmp/dash && cd /tmp/dash
git switch -c add-<label>
cp /tmp/pub/30987147147__pilot-spreadsheetbench.json records/
python3 scripts/check_records.py records/30987147147__pilot-spreadsheetbench.json   # must say 0 errors
git add records && git commit -m "records: add pilot-spreadsheetbench (manual publish)"
git push -u origin HEAD        # then open a pull request
```

Merging the pull request deploys the dashboard automatically; there is no separate Pages step. Record
names there are `<id>__<label>.json` (any sortable id; see the dashboard's PUBLISHING.md, section A). The
per-run "Open UI" snapshot (the optional section below) is not hosted on the dashboard yet.

### Option 2: push to benchmark-history (what CI does)

```bash
git clone --depth 1 --branch benchmark-history \
  git@github.com:skillberry-ai/cap-evolve.git /tmp/hist
cp /tmp/pub/30987147147__pilot-spreadsheetbench.json /tmp/hist/records/
cd /tmp/hist
git add records
git commit -m "bench: record run 30987147147 (manual publish)"
git push origin benchmark-history
```

Only `records/` (and `runs/`, for the optional UI snapshot) get committed here — `benchmarks.json`/
`meta.json` are no longer persisted on this branch at all; they're rendered fresh from `records/` at
Pages-deploy time, so there's nothing to hand-edit or regenerate locally. Adding the record file is
the entire publish step.

To get this record onto the dashboard as well, run **Sync from cap-evolve** there (Actions → Run
workflow in `skillberry-runs/dashboard`; section D of its PUBLISHING.md). It copies records it does
not have yet, and skips the ones it does.

CI treats this branch as single-writer (`concurrency: benchmark-history-write`). A manual push while
a benchmarks run is finishing can lose the race; if `git push` is rejected, delete `/tmp/hist` and
redo this step rather than force-pushing.

## Step 6 (Option 2 only) — trigger a Pages deploy, then verify

Trigger **Actions → Deploy GitHub Pages → Run workflow** (`workflow_dispatch`) — this is the step
that actually renders your new record into `benchmarks.json`. Once it completes, reload
<https://skillberry-ai.github.io/cap-evolve/benchmarks.html>; the new row should appear, with a real
base→opt reward rather than `—`. To check the data without the browser:

```bash
curl -s "https://skillberry-ai.github.io/cap-evolve/benchmarks.json" \
  | python3 -c "import json,sys;print([(r['run_id'],r['tier'],r['bench'],r['suite']) for r in json.load(sys.stdin)][:3])"
```

## Optional — the per-run "Open UI" snapshot (`benchmark-history` only)

Only needed if you want the row's dashboard link to work. These snapshots are still served from this
repo's `benchmark-history` branch and site, for rows on either page. It is a full dashboard shell plus the
run's exported data, and unlike the table it **does** require a Pages deploy:

```bash
PYTHONPATH=dashboard/backend python3 -m capevolve_dashboard.export_static \
  --base /tmp/pub --run-id run_suite --out /tmp/pub/ui/data      # /tmp/pub holds run_suite/
cd dashboard/frontend && npm ci && VITE_STATIC=1 npx vite build --outDir /tmp/pub/ui_shell && cd -

mkdir -p /tmp/hist/runs/30987147147__pilot-spreadsheetbench/ui
cp -R /tmp/pub/ui_shell/. /tmp/hist/runs/30987147147__pilot-spreadsheetbench/ui/
cp -R /tmp/pub/ui/data    /tmp/hist/runs/30987147147__pilot-spreadsheetbench/ui/data
```

Then set `"has_ui": true` in the record (or rebuild it with `record.py build --has-ui`), commit,
push, and trigger **Actions → Deploy GitHub Pages → Run workflow** so the deploy both folds
`runs/**` into `benchmark-ui/runs/**` and renders the updated record into `benchmarks.json`.

## Repairing a record that is already published

If the row exists but shows `—` in the reward column, the record was built before the pairing fix
(#284) or from a truncated artifact. Do not rebuild it from scratch — repair it from the run's
`final.json`:

```bash
python3 ci/benchmarks/utils/rebuild_record.py /tmp/pub/run_suite/final.json \
  /tmp/hist/records/<run_id>__<tier>-<bench>.json
```

Then commit, push, and trigger a Pages deploy (steps 5–6). It is idempotent, so running it on an
already-correct record changes nothing. For a record on the dashboard, point it at that repo's
`records/<name>.json` and send the fix as a pull request; the sync workflow's *update existing* option
copies a correction made on `benchmark-history`.

## Related

- [`skillberry-runs/dashboard` PUBLISHING.md](https://github.com/skillberry-runs/dashboard/blob/main/PUBLISHING.md)
  — adding rows to the dashboard, publishing write-ups and new benchmarks, syncing from this repo.
- `ci/benchmarks/README.md` — the benchmarks suite, tiers, and how to bootstrap the
  `benchmark-history` branch.
- `.github/workflows/benchmarks.yml` — the CI path these steps mirror (`Write run metadata`,
  `Export CapEvolve UI snapshot`, `aggregate history`).
