# Publishing a run to the benchmarks page, by hand

The [benchmarks page](https://skillberry-ai.github.io/cap-evolve/benchmarks.html) is normally
filled in by the `aggregate history` job in `.github/workflows/benchmarks.yml`. This document is
for the case where that job never ran or produced nothing — a run that was interrupted and
resumed by hand, a run driven directly on the runner, or a job that died before uploading its
artifact.

Nothing here is a special "manual mode": you are running the same three scripts the CI job runs,
in the same order.

## How the page gets its data

```
run dir  --metrics.py-->  metrics.jsonl + steps.jsonl
                          + runmeta.json (hand-written here; CI writes it in a workflow step)
                                    |
                             record.py build
                                    |
                     records/<run_id>__<tier>-<bench>.json   on the benchmark-history branch
                                    |
                          record.py aggregate
                                    |
                       benchmarks.json + meta.json           on the benchmark-history branch
                                    |
                    site/benchmarks.js fetches it from raw.githubusercontent
```

The page reads `benchmarks.json` **straight from the `benchmark-history` branch** with a
cache-buster (`site/benchmarks.js`, line 1). So **a push to that branch is live immediately — no
Pages deploy is needed.** A Pages deploy is only needed for the optional per-run "Open UI"
snapshot (see the last section).

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

## Step 5 — push to benchmark-history

```bash
git clone --depth 1 --branch benchmark-history \
  git@github.com:skillberry-ai/cap-evolve.git /tmp/hist
cp /tmp/pub/30987147147__pilot-spreadsheetbench.json /tmp/hist/records/
python3 ci/benchmarks/lib/record.py aggregate /tmp/hist/records \
  --now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --out /tmp/hist
cd /tmp/hist
git add records benchmarks.json meta.json
git commit -m "bench: record run 30987147147 (manual publish)"
git push origin benchmark-history
```

Never hand-edit `benchmarks.json` or `meta.json` — `aggregate` regenerates both from every file in
`records/`, so editing the aggregate is always lost on the next run. Edit or add a record instead.

CI treats this branch as single-writer (`concurrency: benchmark-history-write`). A manual push while
a benchmarks run is finishing can lose the race; if `git push` is rejected, delete `/tmp/hist` and
redo this step rather than force-pushing.

## Step 6 — verify

Reload <https://skillberry-ai.github.io/cap-evolve/benchmarks.html>. The new row should appear
immediately, with a real base→opt reward rather than `—`. To check the data without the browser:

```bash
curl -s "https://raw.githubusercontent.com/skillberry-ai/cap-evolve/benchmark-history/benchmarks.json" \
  | python3 -c "import json,sys;print([(r['run_id'],r['tier'],r['bench'],r['suite']) for r in json.load(sys.stdin)][:3])"
```

## Optional — the per-run "Open UI" snapshot

Only needed if you want the row's dashboard link to work. It is a full dashboard shell plus the
run's exported data, and unlike the table it **does** require a Pages deploy:

```bash
PYTHONPATH=dashboard/backend python3 -m capevolve_dashboard.export_static \
  --base /tmp/pub --run-id run_suite --out /tmp/pub/ui/data      # /tmp/pub holds run_suite/
cd dashboard/frontend && npm ci && VITE_STATIC=1 npx vite build --outDir /tmp/pub/ui_shell && cd -

mkdir -p /tmp/hist/runs/30987147147__pilot-spreadsheetbench/ui
cp -R /tmp/pub/ui_shell/. /tmp/hist/runs/30987147147__pilot-spreadsheetbench/ui/
cp -R /tmp/pub/ui/data    /tmp/hist/runs/30987147147__pilot-spreadsheetbench/ui/data
```

Then set `"has_ui": true` in the record (or rebuild it with `record.py build --has-ui`), re-run
`aggregate`, commit, push, and trigger **Actions → Pages → Run workflow** so the deploy folds
`runs/**` into `benchmark-ui/runs/**`.

## Repairing a record that is already published

If the row exists but shows `—` in the reward column, the record was built before the pairing fix
(#284) or from a truncated artifact. Do not rebuild it from scratch — repair it from the run's
`final.json`:

```bash
python3 ci/benchmarks/utils/rebuild_record.py /tmp/pub/run_suite/final.json \
  /tmp/hist/records/<run_id>__<tier>-<bench>.json
```

Then re-run `aggregate`, commit and push (steps 5–6). It is idempotent, so running it on an
already-correct record changes nothing.

## Related

- `ci/benchmarks/README.md` — the benchmarks suite, tiers, and how to bootstrap the
  `benchmark-history` branch.
- `.github/workflows/benchmarks.yml` — the CI path these steps mirror (`Write run metadata`,
  `Export CapEvolve UI snapshot`, `aggregate history`).
