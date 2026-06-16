# Example: json_extract (a new benchmark from scratch)

Proof that a brand-new benchmark plugs in with **only an adapter + data** — no
core or skill changes. Different domain and a different scoring paradigm from
toy_calc: the scorer parses the agent's output as **JSON** and checks a field, so
the optimization (instruct the agent to emit strict JSON) is what raises the score.
Zero-API and deterministic; asserted by `core/tests/test_new_benchmark.py`.

## Files
- `adapter.py` — `CapabilityAdapter` with JSON-aware scoring (parse → check `answer`).
- `capability/prompt.txt` — seed prompt (no strict-JSON instruction).
- `mock_script.json` — the edit the `mock` optimizer applies (`[STRICT_JSON]`).
- `tasks.jsonl` — 8 field-extraction tasks.

## Run it
```bash
REPO=$PWD
export CAPEVOLVE_CORE=$REPO/core PYTHONPATH=$REPO/core CAPEVOLVE_SKILLS_DIR=$REPO/skills
export CAPEVOLVE_JSON_DATA=$REPO/examples/json_extract
export CAPEVOLVE_MOCK_SCRIPT=$REPO/examples/json_extract/mock_script.json

D=/tmp/jx; mkdir -p $D/.capevolve/project/adapters
cp $REPO/examples/json_extract/adapter.py $D/.capevolve/project/adapters/
cp -R $REPO/examples/json_extract/capability $D/seed_capability
cp $REPO/templates/project/capevolve.yaml $D/.capevolve/project/capevolve.yaml

python3 -m cap_evolve.cli run --spec $D/.capevolve/project/capevolve.yaml --project $D/.capevolve/project --run-ts demo
# -> baseline_val 0.0  ->  test_reward 1.0  + dashboard.html
```

## Why it matters
The only new code is `adapter.py` + `tasks.jsonl` + a seed prompt. The harness,
the splits/gate/seal, the algorithms, the optimizers, and the dashboard are all
reused unchanged — that's the extensibility guarantee.
