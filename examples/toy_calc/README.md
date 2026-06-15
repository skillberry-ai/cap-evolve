# Example: toy_calc (zero-API, deterministic)

The smallest end-to-end proof — no model calls, fully deterministic, runs in
seconds. A deterministic stand-in "agent" answers arithmetic tasks; it only
succeeds when the system prompt contains the marker `[CALC]`, so the optimization
(the `mock` optimizer adds `[CALC]`) provably raises the score. Used as the CI gate.

## Files
- `adapter.py` — the 4-method `CapabilityAdapter` (deterministic agent + exact-match scorer).
- `capability/prompt.txt` — the seed system prompt (no `[CALC]`).
- `mock_script.json` — the deterministic edit the `mock` optimizer applies.
- `tasks.jsonl` — 8 arithmetic tasks.

## Run it
```bash
REPO=$PWD                       # agent-capo repo root
export AGENT_CAPO_CORE=$REPO/core PYTHONPATH=$REPO/core ACAPO_SKILLS_DIR=$REPO/skills
export ACAPO_TOY_DATA=$REPO/examples/toy_calc
export ACAPO_MOCK_SCRIPT=$REPO/examples/toy_calc/mock_script.json

D=/tmp/toy; mkdir -p $D/.agentcapo/project/adapters
cp $REPO/examples/toy_calc/adapter.py $D/.agentcapo/project/adapters/
cp -R $REPO/examples/toy_calc/capability $D/seed_capability
cp $REPO/templates/project/acapo.yaml $D/.agentcapo/project/acapo.yaml   # defaults: system-prompt / mock / all-at-once

python3 -m agent_capo.cli run --spec $D/.agentcapo/project/acapo.yaml --project $D/.agentcapo/project --run-ts demo
# -> baseline_val 0.0  ->  test_reward 1.0   (gate-accepted, test sealed) + dashboard.html
```
This is exactly what `core/tests/test_e2e_slice.py` asserts.
