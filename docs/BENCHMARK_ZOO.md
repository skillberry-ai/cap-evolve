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
`['adapters/adapter.py', 'benchmark.yaml', 'target.py', 'tasks.jsonl']` — and the
containment allowlist on every path key makes the layout *enforced* rather than merely
conventional. Anything else you add under `project/` that is code or an answer key is
either covered by the unioned globs or flagged by `verify`'s under-declaration sweep.

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
allow_saturated_baseline: false # opt out of the headroom requirement, loudly
```

An **unknown key is a hard error** — a silently-ignored key in an honesty-critical
config is how "I declared it" and "it applied" drift apart. For the same reason a
`score()` in the target module with anything but `scoring: custom` is *also* a hard
error: a code scorer silently overriding the declared mode made both the manifest and
`benchmark list` report a grading mode that was not the one in effect.

Scoring semantics, spelled out because a surprising scorer produces silent `0.0` rows:
`exact` is case-insensitive equality of stripped strings; `contains` is
case-insensitive substring (an empty target is rejected at load — it would match
everything); `regex` is `re.search`, i.e. the target is an **unanchored pattern**, so
target `7` credits `17` — anchor it yourself (`^7$`) and note every target is
`re.compile`-validated at load; `numeric` compares the **first** number on each side
with `math.isclose(rel_tol=1e-9, abs_tol=1e-12)` (relative, so large magnitudes are
not spuriously unequal) and accepts scientific notation.

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
2. dataset load **through the real adapter** — missing file, duplicate ids,
   **content-duplicate rows** (identical input+target under fresh ids, which split
   cleanly and made val a copy of train), an empty target under a matching mode, an
   uncompilable `regex` target, or an empty dataset all fail here;
3. `cap_evolve.check.run_check` on the generated project (stubs, task stability,
   scorer determinism, pure `materialize`);
4. seeded (or pinned) split + the **honesty floor**, asserted on the **realized**
   split: `val >= MIN_VAL_TASKS`, a non-empty sealed test, a **non-empty train**, and
   **genuine disjointness**. A 3-task dataset fails *here*, not mid-run inside
   `gate.decide` (#113) — and so does `train == val == test`, which is how #99's
   headline τ² number turned out to be a fit metric;
5. a **real zero-API smoke eval** — every val task through `live()` →
   `run_target()` → `score()`, **twice**, comparing rollout fingerprints and
   rewards. This is what catches a non-deterministic `run_target()`; `check` never
   runs the target at all. *Scope:* both passes run back-to-back in one process, so
   this catches an unseeded sampler, not drift on a coarser clock — a necessary
   condition, not a proof of reproducibility;
   - **5a. headroom** — a seed capability that already scores `1.0` on every smoke
     task is a **hard failure**, not a note. A benchmark that is perfect at baseline
     cannot demonstrate an improvement, which is the one thing `baseline` exists to
     confirm, and it is the signature of the two commonest reward hacks (a `score()`
     wired to a constant; a `run()` returning `task.target` or reading the answer key
     off disk). A genuinely saturated *reference fixture* opts out loudly with
     `allow_saturated_baseline: true`;
   - **5b. the degenerate-scorer probe** — `score()` is handed a synthetically
     **correct** rollout and a deliberately **wrong** one, and the two rewards must
     differ on at least one task. Correct-vs-wrong is a property of the scorer alone,
     so it holds at any baseline: a `score()` that ignores its input fails even on a
     benchmark whose baseline is imperfect;
6. **protected paths, checked against the artifact the runtime guard reads.** The
   assertion is on what `protect.resolve_protected()` resolves from the *generated*
   `capevolve.yaml` — not on what `benchmark.yaml` claims. Weakening only the
   generated spec used to leave `verify` reporting OK with
   `rep.protected == ['adapters/adapter.py']`, the same wrong-artifact bug as #189;
   - **6a. the under-declaration sweep** — every `.py` and answer-key-ish data file
     under `project/` (outside `capability_path/`) must be guard-hashed. The four
     hardcoded names only ever covered the two bundled examples, so anything a third
     author added was neither protected nor flagged.

Every path key (`tasks_file`, `target_module`, `capability_path`, `split_ids_file`)
must be a **plain relative path whose resolved parent is inside `project/`** — an
allowlist, checked once in `load_manifest`, so no use site can bypass it. Without it
`target_module: ../../pwned.py` executed code outside the project dir during
`verify`, from a location #142's guard structurally cannot hash.

`protected_paths` is **additive**: the manifest's list is UNIONed with the layout
defaults *and* #197's globs, never substituted for them. #197's own `protected_paths`
replaces its defaults wholesale, so declaring four paths silently switched off the
`*gold*` answer-key globs. Union is the only default that fails safe — declaring one
more path can never *un*protect something.

`verified.json` then records the measured val reward, split sizes, SHA-256 of the
**dataset, the grader and the manifest**, and the ordered list of steps that ran.
`cap-evolve benchmark list` reads that stamp from **disk** and **re-checks every
hash**: a hand-written stamp (no `steps`, no hashes) and a stale one (dataset or
`target.py` edited after verifying) both read `verified: false` with the reason in
`stale_reason`. Without that comparison the stamp was just a differently-located
claim.

## Overriding a generated file

`adapters/adapter.py` is generated, but `--refresh` no longer clobbers it. If its
bytes differ from the generated shim it is treated as an **authored override** and
left alone; `capevolve.yaml` is still re-derived, since it holds no logic to override.
`benchmark add --refresh` reports what it kept:

```json
{"kept_hand_edited": ["adapters/adapter.py"], "note": "left [...] untouched: ..."}
```

So overriding one `CapabilityAdapter` hook (`trajectories()`, a custom `live()`) is a
supported edit rather than something the next manifest change silently deletes.

Exit code is 1 on any problem, and stdout is exactly one JSON object on every path,
including errors.
