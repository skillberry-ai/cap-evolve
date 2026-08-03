# Example: toy_calc — the worked reference project (zero-API, deterministic)

The smallest end-to-end proof, and the **filled reference** for what a real
`.capevolve/project/` looks like. No model calls, fully deterministic, runs in seconds.

A deterministic stand-in "agent" answers arithmetic tasks; it only succeeds when the
system prompt contains the marker `[CALC]`, so the optimization (the `mock` optimizer
adds `[CALC]`) provably raises the score. Used as the CI gate.

> **To start your own project, copy [`templates/project/`](../../templates/project) —
> it carries the full option list with every knob documented.** Read *this* directory to
> see a finished one: every choice made with a note on why, plus an explicit list of what
> the example does **not** prove.

## Files
- [`PROJECT.md`](PROJECT.md) — the **filled** `templates/project/PROJECT.md`: what is
  optimized, how it runs, how it scores, the splits, the budget, and an *Honest limits*
  section naming what this example does not demonstrate.
- [`capevolve.yaml`](capevolve.yaml) — the **filled** run spec, one comment per decision.
- [`adapter.py`](adapter.py) — a `CapabilityAdapter`: the **3 required** methods
  (`tasks`, `run_target`, `score`) plus an override of the optional `apply` hook.
- `capability/prompt.txt` — the seed system prompt (no `[CALC]`).
- `mock_script.json` — the deterministic edit the `mock` optimizer applies.
- `tasks.jsonl` — 8 arithmetic tasks.

## Run it
```bash
bash examples/toy_calc/run.sh
# -> {"ok": true}                             (cap-evolve check, the hard gate)
# -> baseline_val 0.0  ->  test_reward 1.0     (gate-accepted, test sealed) + dashboard.html
```
`run.sh` builds the project dir, runs `cap-evolve check`, then the full pipeline.
`core/tests/test_e2e_slice.py::test_worked_reference_runs_end_to_end` drives these same
files through `check` → run → sealed test, so a contract change breaks a test rather than
rotting this README.

Or by hand, to see the pieces:
```bash
REPO=$PWD                       # cap-evolve repo root
export CAPEVOLVE_CORE=$REPO/core PYTHONPATH=$REPO/core CAPEVOLVE_SKILLS_DIR=$REPO/skills
export CAPEVOLVE_TOY_DATA=$REPO/examples/toy_calc
export CAPEVOLVE_MOCK_SCRIPT=$REPO/examples/toy_calc/mock_script.json

D=/tmp/toy; mkdir -p $D/.capevolve/project/adapters
cp $REPO/examples/toy_calc/adapter.py     $D/.capevolve/project/adapters/
cp -R $REPO/examples/toy_calc/capability  $D/seed_capability
cp $REPO/examples/toy_calc/capevolve.yaml $D/.capevolve/project/capevolve.yaml
cp $REPO/examples/toy_calc/PROJECT.md     $D/.capevolve/project/PROJECT.md

python3 -m cap_evolve.cli check $D/.capevolve/project      # {"ok": true}
python3 -m cap_evolve.cli run --spec $D/.capevolve/project/capevolve.yaml \
                              --project $D/.capevolve/project --run-ts demo
```

## What it proves, and what it doesn't

Proves: the adapter contract, the frozen splits, the gate wiring, the optimizer handoff,
the sealed test, and the run-dir artifacts — reproducibly and for free.

Does **not** prove: that the significance gate rejects noise (a deterministic scorer has
none, so the gate takes its documented `SE=0 → STRICT` fallback here), nor that
optimization works on a real benchmark. [`PROJECT.md`](PROJECT.md)'s *Honest limits*
section spells out all five caveats. For real benchmarks see
[`../tau2_airline`](../tau2_airline) and [`../skillsbench`](../skillsbench).

## Related
- [`docs/ADAPTER_CONTRACT.md`](../../docs/ADAPTER_CONTRACT.md) — the contract this
  adapter implements: 3 required `@abstractmethod`s, defaulted hooks, `hasattr`-probed
  optional fast paths.
- [`templates/project/`](../../templates/project) — the blank scaffold to copy.
- `benchmarks/toy_calc/` — the **declarative** form of this same benchmark: a
  `benchmark.yaml` manifest plus a one-function `project/target.py`, with the spec
  *generated* by `cap-evolve benchmark add`. Take that path when the manifest fits; this
  directory is the reference for the hand-written `CapabilityAdapter` when it doesn't.
  The two are deliberately paired — the zoo entry links back here for the adapter form,
  and this is the "before" side of its boilerplate measurement. *(Lands with #233; the
  path is intentionally unlinked until then.)*
