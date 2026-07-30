# The benchmark zoo — declarative benchmarks + `cap-evolve benchmark`

Onboarding a benchmark was a from-scratch, per-user effort: write a
`CapabilityAdapter` subclass, prune a ~100-line `capevolve.yaml`, and author a
bespoke `optimizer/INSTRUCTIONS.md`. This page documents the lighter path — a
declarative `benchmark.yaml`, one file of real code, and a `verify` command that
actually exercises the benchmark.

`benchmarks/` is the curated library. `docs/ADAPTER_CONTRACT.md` still governs the
full-adapter path, which stays the escape hatch for anything the manifest cannot
express.

## What actually repeats (the measurement)

Diffing the two *generic* bundled templates (`templates/adapters/jsonl_litellm` vs
`huggingface_litellm`) — 78 changed lines out of 127, but the changes are almost
entirely the dataset-loading block:

| Repeats verbatim across every benchmark | Genuinely per-benchmark |
|---|---|
| module preamble + `sys.path` juggling | **how the target agent runs** |
| the JSONL/dataset → `Task` loop | a bespoke match predicate (sometimes) |
| `if rollout.error:` infra-noise branch of `score` | |
| the `exact`/`contains`/`regex` match helper | |
| `Score(task_id=…, reward=…, feedback=…, trial_rewards=[…])` construction | |
| the whole `capevolve.yaml` except ~6 values | |

So the manifest declares the left column and `target.py` keeps the right one. There
is deliberately **no config language for `run()`** — running an agent is real logic,
and a DSL that reimplemented Python would be worse than the Python it replaced.

### Measured reduction (same benchmark, `toy_calc`, hand-authored non-blank lines)

| | Before (hand-written adapter) | After (manifest) |
|---|---|---|
| Python | 43 (`adapter.py`: 3 methods + `apply`) | **18** (`target.py`: one `run()`) |
| YAML | 35 (`capevolve.yaml` from the template) | **18** (`benchmark.yaml`) |
| `adapters/adapter.py` | — | 0 — **generated** |
| `capevolve.yaml` | — | 0 — **generated** |
| **Total** | **78** | **36** (−54%) |

For the documented generic LLM case (`jsonl_litellm`) the before number is 101
(88 Python + 13 YAML) against the same 36.

## Layout

```
benchmarks/<name>/
  README.md
  mock_script.json        # optional: the deterministic edit the `mock` optimizer applies
  verified.json           # written by `verify` — the measured evidence
  project/                # ← this IS the cap-evolve project dir
    benchmark.yaml        # you write this
    target.py             # you write this
    tasks.jsonl
    seed_capability/
    adapters/adapter.py   # GENERATED (a bare ManifestAdapter subclass)
    capevolve.yaml        # GENERATED from the manifest
```

Everything the grader depends on lives **inside** `project/`, because #142's tamper
guard can only hash paths under the project dir. A manifest or scorer at the
benchmark root would be declared-but-unprotected (the guard logs
`protected_paths_unmatched` and moves on). This layout closes that by construction —
`resolve_protected` on a scaffolded benchmark returns
`['adapters/adapter.py', 'benchmark.yaml', 'target.py', 'tasks.jsonl']`.

## The manifest

```yaml
name: toy_calc
description: Arithmetic accuracy of a deterministic zero-API stand-in agent.

tasks_file: tasks.jsonl        # one JSON object per line
id_field: id
input_field: input
target_field: target

scoring: exact                 # exact | contains | regex | numeric | custom
metric_direction: higher       # higher | lower

capability_path: seed_capability
target_module: target.py

split_seed: 0
split_train: 0.5
split_val: 0.25
split_test: 0.25
split_ids_file: ""             # pin an official split instead of ratios
num_trials: 1                  # raise if the runner is stochastic

protected_paths: [adapters, benchmark.yaml, target.py, tasks.jsonl]
verified: false
```

An **unknown key is a hard error** — a silently-ignored key in an honesty-critical
config is how "I declared it" and "it applied" drift apart.

## The code

```python
def run(task, ctx, *, seed: int = 0):
    """ctx is the live candidate dir. Return a str, or a dict of Rollout fields."""
    prompt = (Path(ctx) / "prompt.txt").read_text(encoding="utf-8")
    ...
    return {"output": answer, "trace": transcript, "cost_usd": spend}
```

If the runner is stochastic you **must** forward `seed`, or pass^k and the
significance gate degenerate. For a bespoke predicate set `scoring: custom` and add
`score(task, rollout) -> Score` in the same file — see `benchmarks/json_extract`,
which does per-field partial credit over parsed JSON.

## Commands

```bash
cap-evolve benchmark list                        # the zoo + each entry's verified status
cap-evolve benchmark add my_bench --description "what it measures"
cap-evolve benchmark add my_bench --from-zoo toy_calc
cap-evolve benchmark add my_bench --refresh      # regenerate the derived project files
cap-evolve benchmark verify my_bench             # check gate + REAL smoke eval, then stamp
cap-evolve run --spec my_bench/project/capevolve.yaml --project my_bench/project
```

`add` writes a benchmark that is **runnable and verifiable from the first minute**:
the placeholder `run()` echoes the task input when the candidate prompt contains
`[ECHO]`, so `verify` passes and `run` shows a real gate decision before you have
written a line.

## What `verify` executes

Every guard in this area that measured the wrong artifact passed its own test
vacuously, so `verify` deliberately runs the benchmark rather than parsing it:

1. manifest parse + field validation;
2. dataset load **through the real adapter** — missing file, duplicate ids or an
   empty dataset all fail here;
3. `cap_evolve.check.run_check` on the generated project (stubs, task stability,
   scorer determinism, pure `materialize`);
4. seeded split + the **honest-gate floor**: `val >= MIN_VAL_TASKS` and a non-empty
   sealed test split. A 3-task dataset fails *here*, not mid-run inside
   `gate.decide` (#113);
5. a **real zero-API smoke eval** — every val task through `live()` →
   `run_target()` → `score()`, **twice**, comparing rollout fingerprints and
   rewards. This is what catches a non-deterministic `run_target()`; `check` never
   runs the target at all;
6. protected-paths resolution — the grader, dataset and manifest must all be
   covered by what the spec declares.

`verified.json` then records the measured val reward, split sizes, dataset SHA-256
and the ordered list of steps that ran. `cap-evolve benchmark list` reads that stamp
from **disk**, not the manifest's `verified:` flag: a committed flag is a claim, the
stamp is evidence.

Exit code is 1 on any problem, and stdout is exactly one JSON object on every path,
including errors.
