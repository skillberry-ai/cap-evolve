# Code review & extensibility assessment

A max-effort review (two independent finder passes + verification) plus an
honest assessment of how easy agent-capo is to extend and integrate.

## Findings fixed (this round)

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 1 | high | test split could be scored without flipping the seal (`seal_test=False`) | `evaluate_candidate` seals on ANY `split=="test"` |
| 2 | high | `acapo run` broke with an absolute `--project` (relative run_dir resolved against the wrong cwd) | all steps share one working dir; paths relative to it |
| 3 | high | `evaluate_candidate` assumed `run_batch` returns a dict | accepts dict **or** list parallel to tasks |
| 4 | high | adapters with helper modules (tau2's `tau2_runtime`) failed under `load_adapter` | `load_adapter` adds the adapter dir to `sys.path` |
| 5 | high | copy-install had no manifest and a flat layout `build_manifest` couldn't read | `build_manifest` handles flat + component layouts; `install.sh` builds into the install dir |
| 6 | med | template `check.py` misclassified arg-taking stubs as implemented | detect the `IMPLEMENT ME` marker by source scan |
| 7 | med | `diagnose` put the task id (not input) in the reflective dataset | rollout records now persist the task input |
| 8 | med | no-regression gate only caught binary 1.0→ drops | catches any graded reward decrease |
| 9 | low | YAML readers coerced `007`/`1_000` to ints | exact round-trip coercion only |
| 10 | low | configurable optimizers crashed on literal `{}` in a command template | brace-safe `.replace` substitution |
| 11 | low | required-field check used truthiness; `--help` truncation | presence check; widened range |

All 28 tests pass; flat-install and absolute-path `acapo run` verified.

## Extensibility — how easy is it?

**Add a capability / algorithm / optimizer — one folder, no core edits.**
`cp -R templates/skill skills/<component>/<name>`, fill `SKILL.md` + `meta.yaml`
+ `scripts/{abstract,check,run}.py`, run `build_manifest.py`. The registry
auto-discovers it and the orchestrator wires it by `needs`/`provides` tokens with
`compatible_with` globs (`*` = any). Proven: 4 algorithms, 2 capabilities, and 8
optimizers were all added this way; algorithms that share the hill-climb loop are
~40-line wrappers (`cyclic`/`hardest-first` differ only in a `FOCUS` constant).

**Different inputs.** The `intake` skill + `inputs/INPUTS.md` contract make inputs
declarative (needed vs recommended, with ask-the-user-if-missing). A dataset is a
jsonl/dir or `tasks()` in the adapter; splits are seeded by core.

**Integrate a new agent (optimizer).** Either add an optimizer skill (the 6 real
ones are ~40 lines each: build the headless command, `shutil.which` guard) or use
`generic` with `ACAPO_OPTIMIZER_CMD`. Any CLI that edits files in a dir works.

**Integrate a new benchmark/dataset.** Implement the 4-method `CapabilityAdapter`
(`tasks/run_target/score/apply`) and pass `acapo check`. Proven end-to-end three
times with *no framework changes*: `toy_calc` (deterministic), `json_extract`
(JSON-aware scoring, added from scratch with only an adapter + data), and
`tau2_airline` (real tau2-bench with gpt-oss-120b; helper module + batch runner).

**Friction that remains (see ROADMAP):** no auto-generated adapter stub per
benchmark type; the scorer library (match/regex/json/llm-judge/cost) is not yet
batteries-included, so each adapter writes its own `score`; cluster_cyclic /
skillopt_epochs / dspy and skill-package / composite capabilities are designed but
not yet shipped. None require core changes — they are drop-in skills.

## Verdict
The architecture delivers on "easy to extend and integrate": new capabilities,
algorithms, optimizers, inputs, agents, and benchmarks are additive and isolated,
validated by per-skill `check.py` and the honest-eval core. The biggest adoption
lever left is a batteries-included scorer library so new benchmarks need even less
adapter code.
