# Design: tau2-bench airline + RITS — dogfood cap-evolve from scratch, harden it, record it

**Date:** 2026-06-18
**Author:** Osher Elhadad
**Status:** Draft for review (v2 — reframed after user feedback)

## What this actually is

This is **not** "hand-write a bespoke tau2 example." It is a **dogfooding + hardening
exercise**: I act **only as the user** of cap-evolve and drive its *own* documented
flow (RUN.md → intake → implement-and-check → baseline → algorithm → finalize →
report) to optimize tau2-bench airline via RITS. **Nothing is assumed or pre-built** —
not the tau2 integration, not RITS support, not the adapter. Each of those must be
*produced by the cap-evolve flow itself*.

Wherever the flow cannot collect or build something a user would need — its
**prompts, inputs, templates, skills, optimizer registry, or core** — that is a
**framework gap**. I fix the gap in the framework and then **start over from a clean
environment** (including `rm -rf .venv` and re-running setup), repeating until a user
can run this example **end to end, autonomously, from just the prompt**.

The deliverable is therefore a **hardened cap-evolve** (skills/templates/inputs/
prompts/core good enough that this run "just works") + the new tau2_airline example
that the flow produces + a recorded run + production docs.

## Goal

A user opens their coding agent (Claude Code) at the repo, gives the tau2-airline+RITS
prompt, and cap-evolve runs the whole optimization autonomously and honestly,
producing a dashboard and an honest (fit-metric) number — with zero hand-holding and
zero undocumented assumptions.

## Non-goals
- Hand-authoring `rits.py` / `adapter.py` from a private design (the flow produces them).
- Maintaining a tau2-bench fork.
- Hitting a target score (the honest number is whatever the run yields; no-holdout ⇒ reported as a fit metric).
- Changing cap-evolve's honesty machinery (splits/gate/seal) — used as-is.

## Dogfooding discipline (the rules I follow)
1. **I am the user.** I provide inputs/answers a user would; I let intake/implement-and-check/orchestrate and the optimizer do the building. I don't shortcut by pre-writing integration code from my own design.
2. **Nothing assumed.** RITS, tau2-from-upstream, per-iteration optimizer budget, `num_trials=10`, `TAU2_MAX_CONCURRENCY=100`, no-holdout — each must be either (a) already supported by the flow, or (b) added to the flow as a framework change.
3. **Fix the framework, not the example.** When the flow is deficient, the change goes into `skills/`, `templates/`, intake `inputs/INPUTS.md`, `optimizers/registry.yaml`, `run-optimizer`, `RUN.md`, or `core/` — never a one-off hack buried in the example.
4. **Clean-room restart.** After a framework change, blow away derived state (`rm -rf .venv`, regenerated project dirs, run dirs) and re-run from `setup` so we always validate the *true* from-nothing path. Repeat until clean.
5. **General bugs → core.** Non-tau-specific bugs are fixed in `core/` (and noted in CHANGELOG), not patched around in the example.

## The run, exactly (the inputs I feed as the user)

| Knob | Value |
|---|---|
| Benchmark | tau2-bench **airline**, cloned fresh from `github.com/sierra-research/tau2-bench` (**latest main**; record resolved SHA) |
| Tasks / splits | all **50** airline tasks as **train = val = test** (no-holdout fit metric; engine logs `splits_warning`) |
| Runner (agent + user sim) | `openai/gpt-oss-120b` via **IBM RITS** |
| RITS integration | **litellm config shim (Approach A)** — produced via the flow; `RITS_API_KEY` from repo-root `.env` |
| Concurrency | `TAU2_MAX_CONCURRENCY=100` |
| num_trials | **10** |
| Optimizer | **claude-code** @ **`claude-opus-4-6`** |
| Per-iteration optimizer budget | ≈ **$40** — passed to the optimizer CLI at the intake/run-optimizer step, enforced by the optimizer's own mechanism where it exists (see below) |
| Total budget | `max_usd: 400`, `max_optimizer_usd: 400` |
| Algorithm | **hill-climb** `--focus all` |
| Capabilities | `[system-prompt, tools]` |
| max_iterations | **10** |

**Cost/time reality (acknowledged):** ~6,000 full airline conversations for the full
run; many hours of RITS load at concurrency 100. RITS runner cost is not
dollar-tracked; the $400 governs the Claude optimizer.

## Per-iteration optimizer budget (framework change, no assumptions)

Requirement: the per-iteration **optimizer-call** budget ($40) must be **passed to the
optimizer CLI** at the step where intake/run-optimizer constructs the optimizer
invocation, and enforced **by the optimizer itself where possible** (Claude Code), with
graceful degradation where not (Bob: no such control).

Plan (research, don't assume, when I reach it):
- Inspect each relevant optimizer CLI for a native per-run budget/cost/limit control (`claude --help`, etc.). **Record what actually exists** — do not invent flags.
- Make per-iteration budget a first-class config field surfaced by **intake** and
  threaded through **run-optimizer** into the registry row's budget mechanism
  (today: `budget_flag`). Per-optimizer: map to the native control if present; else
  fall back to the turn cap (`--max-turns`) and/or the cumulative `max_optimizer_usd`,
  and **clearly document** that it's a proxy, not a hard per-iteration $ stop.
- Update `intake/inputs/INPUTS.md`, `templates/project/capevolve.yaml`,
  `optimizers/registry.yaml` + per-optimizer reference docs, and the `cli.py`/run-optimizer
  plumbing as needed.

## RITS integration (Approach A — produced via the flow)
- A `rits.py`-style shim: resolve the per-model RITS endpoint (info API, retried), set litellm globals (`HOSTED_VLLM_API_BASE`, `HOSTED_VLLM_API_KEY`, `litellm.headers={"RITS_API_KEY": …}`), hand tau2 the model string `hosted_vllm/openai/gpt-oss-120b`. No monkeypatch of `litellm.acompletion`, no tau2 fork.
- Robustness (gpt-oss empty-turn retry, timeouts, infra retries, batch watchdog) included.
- If the intake/implement-and-check flow doesn't naturally lead a user to produce this, that's a **framework gap** (e.g., intake lacks a "runner via OpenAI-compatible/RITS endpoint" input, or the docs don't guide it) → fix the framework.

## Setup / reproducibility
- A `setup` path (script or documented steps the flow relies on) clones tau2-bench latest main into `../tau2-bench`, `pip install -e` it + `./core`, records the resolved tau2 SHA, and verifies imports / RITS reachability / `claude` / `cap-evolve`. Must fail loudly with precise remediation, never silently.
- Interpreter is pinned/printed (repo has miniforge `cap-evolve` + a `.venv`).

## Recording (asciinema + DEMO.md + dashboard)
- `brew install asciinema agg`; record clean-env setup → smoke → full run launch → dashboard open into a `.cast`.
- `DEMO.md`: storyboard + exact commands + `.cast`→GIF/MP4 render + narration + resolved tau2 SHA.
- Ship `dashboard.html` + `report.md` + `events.jsonl` under `run_full/`.

## Process / sequencing

0. **Clean room.** From a fresh environment (remove `.venv` and any derived project/run dirs), install per the *documented* path only.
1. **Drive intake as the user** with the inputs above; record every place the flow asks for something it shouldn't have to / fails to ask for something it needs → framework gap list.
2. **implement-and-check**: let the flow build the adapter + RITS shim + seed caps; `cap-evolve check` must go green. Gaps → fix framework, then **clean-room restart** (incl. `rm -rf .venv`).
3. **Per-iteration optimizer budget** framework change (above), wired through intake/run-optimizer.
4. **smoke** (2 tasks / 1 trial / 1 iter, cheap optimizer): prove autonomous end-to-end. Fix all bugs (general → core). Clean-room restart until smoke is clean from nothing.
5. **Full `cap-evolve run`** (10 iters, background) and record. Monitor terminal failure signatures (`Traceback|INFRASTRUCTURE|FAILED|Killed|max_usd`) + progress.
6. **Re-measure Results** from the real run; capture dashboard/report/cast.
7. **Cleanup + docs to production:** delete `date_tool`, `json_extract`, `skills_bench`, old `tau2_airline`; keep + verify `toy_calc` (CI zero-API gate, must match README). Rewrite README Quickstart + tau2 worked example + Results, `docs/REPRODUCE_tau2.md`, examples table, counts; purge all references to deleted examples; update CI.
8. **Final clean-room validation:** from nothing, the documented commands run verbatim; `cap-evolve check` + toy_calc gate green.

## Risks & mitigations
- **tau2 latest-main API drift** → record SHA; flow/adapter defensive about tau2 imports; fix + note on breakage.
- **litellm globals not honored by a tau2 call path** → Approach A first; if a path bypasses globals, add the narrowest framework hook (still no fork).
- **Long wall-clock / RITS load** → smoke first; full run in background with a Monitor.
- **No native per-iteration $ cap in some optimizers** → research actual CLI capabilities; map to native control where present (Claude Code), else turn-cap/total-cap proxy, clearly documented.
- **Repeated clean-room restarts cost time + some RITS/optimizer $** → accepted by user; smoke keeps it cheap before the full run.

## Deliverables
Hardened framework (`skills/`, `templates/`, intake `INPUTS.md`, `optimizers/registry.yaml` + refs, `run-optimizer`, `RUN.md`, `core/` as needed) such that the run is autonomous from the prompt; the flow-produced `examples/tau2_airline/` (setup + rits shim + adapter + seed_caps + capevolve.yaml + run/smoke + README + DEMO.md + run_full artifacts); refactored README + `docs/REPRODUCE_tau2.md`; deleted examples; verified toy_calc + CI; CHANGELOG entries for core/framework changes.

## Confirmed with user
RITS = Approach A. tau2 = latest main (+ record SHA). Optimizer = claude-opus-4-6 with per-iteration budget passed to the optimizer CLI (native enforcement where possible, e.g. Claude Code; proxy + documented where not, e.g. Bob). Recording = asciinema + DEMO.md + dashboard. Execution = smoke→full. Examples = remove all but keep/verify toy_calc. **I play only the user; nothing assumed; framework gaps fixed in the framework with clean-room (`rm -rf .venv`) restarts.**
