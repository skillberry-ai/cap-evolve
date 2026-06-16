# Full tau2-airline run recipe

The exact configuration used for the headline run: optimize the airline **policy**
with `all-at-once`, the **claude-code** optimizer at **claude-opus-4-6**, with the
agent *and* user simulator both **gpt-oss-120b** (watsonx/RITS), over **all 50**
airline tasks in train/val/test (a deliberate no-holdout fit on the full
benchmark), **10 iterations**, **num_trials 4**, tau **concurrency 7**.

- `acapo.yaml` — the run spec (capability=system-prompt on the policy, optimizer=
  claude-code @ claude-opus-4-6, algorithm=all-at-once, num_trials=4, 10 iters).
- `split_ids_all50.json` — train=val=test=all 50 task ids.

## Run it
```bash
REPO=/path/to/AgentCapTune
export AGENT_CAPO_CORE=$REPO/core PYTHONPATH=$REPO/core ACAPO_SKILLS_DIR=$REPO/skills
export ACAPO_TAU2_DATA=$REPO/examples/tau2_airline/data
export TAU2_MAX_CONCURRENCY=7          # tau2 batch parallelism
# .env (repo root) must hold RITS_API_KEY / WATSONX_* for gpt-oss-120b

R=/tmp/tau2_full
mkdir -p $R/.agentcapo/project/adapters
cp $REPO/examples/tau2_airline/adapter.py        $R/.agentcapo/project/adapters/
cp $REPO/examples/tau2_airline/tau2_runtime.py   $R/.agentcapo/project/adapters/
cp -R $REPO/examples/tau2_airline/policy         $R/seed_policy
cp $REPO/examples/tau2_airline/run_full/acapo.yaml          $R/.agentcapo/project/acapo.yaml
cp $REPO/examples/tau2_airline/run_full/split_ids_all50.json $R/split_ids.json

python3 -m agent_capo.cli run --spec $R/.agentcapo/project/acapo.yaml \
    --project $R/.agentcapo/project --run-ts full
# -> writes $R/.agentcapo/run_full/{report.md, dashboard.html, final.json}
```

## Cost / time
This is large: all-at-once evaluates the val split (50 tasks × 4 trials = 200
multi-turn tau2 conversations) every iteration, so ~200 (baseline) + 10×200 +
200 (test) ≈ 2,400 conversations plus 10 claude-opus-4-6 optimizer calls. Expect
several hours at concurrency 7. Reduce `max_iterations`/`num_trials` or use a
ratio split for a faster pass.
