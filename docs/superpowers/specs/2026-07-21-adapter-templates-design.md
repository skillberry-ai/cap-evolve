# Adapter templates — design (closes #28, finishes PR #36)

**Date:** 2026-07-21 · **Branch:** `copilot/add-adapter-templates` (rebased on `main`)

## Context

Onboarding a benchmark into cap-evolve means writing an `adapter.py` from scratch.
[Issue #28](https://github.com/skillberry-ai/cap-evolve/issues/28) asks to make the
common cases **"config, not code"** with ready-to-use adapter templates under
`templates/adapters/` plus a reusable, provider-agnostic model-wiring helper.

[PR #36](https://github.com/skillberry-ai/cap-evolve/pull/36) added `model_config.py`
plus three **benchmark-specific** templates but (a) omitted the two *generic*
templates the issue asked for, (b) coupled `model_config.py` to IBM RITS, (c) had
three empty-`except` lint flags, (d) shipped stale config (`all-at-once`,
`claude-opus-4-6`), and (e) `swe_bench` used the *old* SWE-bench harness CLI so it
did not actually run. The branch was also behind `main` (its diff spuriously
deleted docs/site).

## Design

**Rebase** onto `main` (drops the spurious deletions), then:

### `model_config.py` — provider-agnostic, no RITS
One lazy helper (no network at import, so `cap-evolve check` stays offline). Resolves
`api_base`/`api_key`/`temperature`/`max_tokens` from env by the `MODEL` prefix, the
same routing litellm does. Providers: OpenAI, Anthropic, **Vertex AI** (ADC), Azure,
Ollama, **litellm_proxy**, any OpenAI-compatible. Added optional `MAX_TOKENS` (needed
for reasoning models and long outputs). RITS branch removed. Empty `except` → stderr warning.

### Two generic templates (the issue's core ask)
- `jsonl_litellm/` — tasks from a JSONL file; `run_target` calls the candidate system
  prompt via litellm; `score` = `exact`|`contains`|`regex` (env `SCORING`).
- `huggingface_litellm/` — same, tasks from `datasets.load_dataset(...)`, columns mapped
  by env (`HF_DATASET`/`INPUT_FIELD`/`TARGET_FIELD`/…).

Both forward the per-trial `seed`, set `Rollout.error` on API failure, and ship a
`__main__` assert self-check for the scoring logic.

### Three benchmark templates (polished)
- `tau2_bench/` — optimizes airline policy + tools via tau2's runner; de-RITS'd; config fixed.
- `skillsbench/` — optimizes shared Agent Skills via `bench eval run`; empty-`except`
  fixes; **`MODEL`/`AGENT`/`SANDBOX` made env-configurable**; **`run_batch` guards
  unknown task ids** so `cap-evolve check`'s stub-probe stays cheap/offline (it otherwise
  launched a real Docker run).
- `swe_bench/` — **rewrote `_evaluate_patch` to the current `swebench.harness.run_evaluation`
  CLI** (`--dataset_name/--split/--instance_ids/--predictions_path/--namespace/--run_id`),
  parsing `resolved_ids`; `--namespace none` for arm64 local builds; added a seed prompt,
  a `_looks_like_diff` guard (skips Docker on non-diff output — also keeps `check` offline),
  and a `SWEBENCH_INSTANCE_IDS` subset knob for cheap runs.

### Docs + GitHub Pages
- `docs/ADAPTER_TEMPLATES.md` (provider matrix, per-template env tables, write-your-own).
- README links (Documentation table + "optimize your own" callout).
- `site/adapter-templates.html` in the existing style + nav link on every page + index tile.

## Verification (real runs — agent `aws/gpt-oss-120b`, optimizer Claude Code `aws/claude-sonnet-5`, via the ete-litellm proxy)

- Self-checks: `jsonl_litellm`, `huggingface_litellm`, `swe_bench` `__main__` asserts pass.
- `cap-evolve check` green for `jsonl_litellm`, `swe_bench`, `tau2_bench`, `skillsbench`.
- **swe_bench** (1 instance, no-holdout): gold patch → reward 1.0 (harness verified);
  full run baseline_val 0.0 → optimizer edited the prompt (322s / $1.66) → gate rejected
  (Δ=0, n_trials=1 strict fallback) → sealed test 0.0. Dashboard generated.
- **tau2_bench** (airline task): real 24 KB agent/user conversation; baseline_val 1.0 →
  optimizer edited the policy (1034s / $4.53) → gate rejected (no headroom) → test 1.0.
- **skillsbench** (1 task, `offer-letter-generator`): in-sandbox Claude agent
  (`aws/claude-sonnet-5`) reached the gateway from inside Docker and passed the verifier —
  baseline_val 1.0 → optimizer edited `docx/SKILL.md` (438s / $2.32) → gate rejected (no
  headroom) → test 1.0. (Also caught + fixed here: `check`'s stub-probe was launching a real
  `bench eval run`; the `run_batch` unknown-id guard now keeps it offline.)

The 0.0/1.0 outcomes are honest: a single 1-iteration pass on one task is not expected to
move a hard benchmark — the demonstration is that each adapter drives the whole
evaluate → diagnose → propose → gate → seal loop with a real model and real optimizer,
with **one-line provider switching** and **no adapter code edits**.
