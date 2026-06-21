# tau2-airline + RITS — dogfood & harden cap-evolve — Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make cap-evolve run a from-scratch, autonomous, recorded tau2-bench airline optimization over IBM RITS (`gpt-oss-120b` agent+user) with a `claude-opus-4-6` optimizer — by driving cap-evolve's own flow as the user and fixing every framework gap that blocks autonomy, until it "just works" from one prompt. Then make installation/run dead-simple and ship production docs.

**Architecture:** I act only as the user. Artifacts (RITS shim, adapter, seed caps, capevolve.yaml) are produced *through* cap-evolve's flow (RUN.md → intake → implement-and-check → baseline → hill-climb → finalize → report). Gaps in the flow are fixed in the framework (`skills/`, `templates/`, intake `INPUTS.md`, `optimizers/registry.yaml` + refs, `run-optimizer`, `RUN.md`, `core/`), followed by clean-room restarts (`rm -rf .venv`).

**Tech Stack:** Python 3.10+ stdlib core (`cap-evolve` CLI), tau2-bench (upstream, latest main), litellm + IBM RITS, Claude Code CLI optimizer (`claude-opus-4-6`), asciinema + agg.

## Global Constraints (verbatim from spec)
- I play ONLY the user; **nothing assumed** (RITS, tau2-from-upstream, per-iter optimizer budget, `num_trials=10`, `TAU2_MAX_CONCURRENCY=100`, no-holdout). Each is supported or becomes a framework change.
- Framework gaps → fixed in framework, never hacked into the example. General bugs → `core/` (+ CHANGELOG).
- After a framework change, **clean-room restart incl. `rm -rf .venv`** and re-run the documented path. Repeat until clean.
- RITS = litellm config shim (Approach A); **no tau2 fork, no `litellm.acompletion` monkeypatch**.
- tau2 = latest main; **record resolved commit SHA**.
- Run: airline, all 50 tasks as train=val=test (no-holdout fit metric), agent+user `openai/gpt-oss-120b` via RITS, `num_trials=10`, `TAU2_MAX_CONCURRENCY=100`, optimizer `claude-code @ claude-opus-4-6`, algorithm `hill-climb --focus all`, `max_iterations=10`, `max_usd=400`, `max_optimizer_usd=400`, per-iteration optimizer budget ≈ $40 passed to the optimizer CLI (native enforcement where it exists, proxy + documented where not).
- Git identity: Osher Elhadad; no Claude co-author/trailer. Work on branch `feat/tau2-airline-rits-from-scratch`.
- Make installation & run **as easy as possible** for users (ideally one `setup` command + one `run` command).
- Honesty machinery (splits/gate/seal) used as-is, never weakened.

---

## Phase 0 — Clean room + tooling baseline

**Files:** none yet (env only).

- [ ] Record current env facts: which interpreter has `cap_evolve` importable; presence of `.venv`; `claude`/`cap-evolve`/`docker`/`asciinema` on PATH; `.env` keys.
- [ ] `rm -rf .venv` and any stale `.capevolve/` derived dirs (clean room). Keep repo source.
- [ ] Decide the single documented interpreter path (prefer a fresh `python -m venv .venv` + `pip install ./core`, OR the miniforge `cap-evolve`). Whichever is chosen must be the ONLY thing the docs tell users to do.
- [ ] Install `asciinema` + `agg` (`brew install asciinema agg`); if unavailable, note fallback (script capture) in DEMO.md.
- [ ] **Gate:** from nothing, `cap-evolve version` works via the documented interpreter.

## Phase 1 — Drive intake as the user (discover gaps)

**Files (framework, only if gaps found):** `skills/phases/intake/**`, `templates/project/**`, `RUN.md`.

- [ ] As the user, follow `RUN.md` / load `intake` with the full input set (capability=[system-prompt,tools]; benchmark=tau2 airline upstream; runner=RITS gpt-oss-120b agent+user; scorer=tau2 reward; optimizer=claude-code@claude-opus-4-6 + $40/iter; algorithm=hill-climb; splits=all-50 no-holdout; num_trials=10; concurrency=100; max_iterations=10; max_usd=400).
- [ ] Log every gap: does intake have inputs for an OpenAI-compatible/RITS runner endpoint? tau2-from-upstream clone? per-iteration optimizer budget? concurrency? no-holdout? If missing → framework change in intake `INPUTS.md` / `templates/project/capevolve.yaml` / scaffolding.
- [ ] Confirm intake scaffolds `.capevolve/project/` (adapter stub + capevolve.yaml + PROJECT.md).
- [ ] **Gate:** intake completes and scaffolds without me hand-editing scaffolded files; gaps captured.

## Phase 2 — Per-iteration optimizer budget (framework change, researched)

**Files:** `optimizers/registry.yaml`, `skills/optimizers/run-optimizer/**`, `core/cap_evolve/cli.py`, `templates/project/capevolve.yaml`, `skills/phases/intake/inputs/INPUTS.md`, per-optimizer reference docs.

- [ ] Research actual CLI capability: `claude --help` for any native per-run cost/budget/limit control (record verbatim; do NOT invent). Note Bob has none.
- [ ] Add a first-class per-iteration optimizer budget concept surfaced by intake and threaded through run-optimizer into the registry budget mechanism. Map to the native control where present (Claude Code), else turn-cap/`max_optimizer_usd` proxy, **clearly documented as a proxy**.
- [ ] **Gate:** `cap-evolve estimate`/dry-run reflects the budget wiring; run-optimizer command for claude-code includes the budget mechanism.

## Phase 3 — implement-and-check: flow produces RITS shim + adapter + seed caps

**Files (flow-produced, in example):** `examples/tau2_airline/{rits.py-equivalent, adapter.py, seed_caps/**}`, `.capevolve/project/adapters/**`. **Framework fixes as needed.**

- [ ] `setup` path: clone tau2-bench latest main → `../tau2-bench`, `pip install -e`, record SHA, verify `import tau2` + RITS reachable + `claude` + `cap-evolve`. (Framework/example script; must fail loudly.)
- [ ] Drive `implement-and-check`: the flow + optimizer author the adapter (tasks/run_batch/score/materialize/live) and the RITS litellm shim (Approach A), seeded from tau2's airline domain. Where the flow doesn't guide a user to produce RITS/tau integration → fix framework (intake guidance, implement-and-check, templates), clean-room restart.
- [ ] Run `cap-evolve check .capevolve/project` → must print `{"ok": true}`. Fix stubs/non-determinism (general → core).
- [ ] **Gate:** `cap-evolve check` green from a clean room.

## Phase 4 — Smoke run (prove autonomy cheaply)

**Files:** `examples/tau2_airline/smoke.sh` (+ framework fixes).

- [ ] `smoke.sh`: `CAPEVOLVE_TAU2_TASK_IDS` = 2 ids, `num_trials=1`, `max_iterations=1`, optimizer `mock` (zero-API) then a 1-turn `claude` to validate the optimizer path + model id `claude-opus-4-6`.
- [ ] Run smoke end-to-end (intake→check→baseline→hill-climb→finalize→report). Capture every failure; fix in framework/core; **clean-room restart** until smoke is clean from nothing.
- [ ] **Gate:** smoke completes autonomously from `rm -rf .venv` → `setup` → `run` with no manual intervention; dashboard.html produced.

## Phase 5 — Full run (background) + record

**Files:** `examples/tau2_airline/{run.sh, DEMO.md, run_full/**}`.

- [ ] `run.sh`: sets env (`TAU2_MAX_CONCURRENCY=100`, timeouts, infra retries, PYTHONPATH, CAPEVOLVE_*), `cap-evolve run` with the full spec. One command.
- [ ] Start asciinema recording; run clean-env `setup` → `smoke` → `run.sh` launch → `open dashboard.html` for the cast.
- [ ] Launch full run (10 iters, 50 tasks, 10 trials, conc 100) in background; Monitor for `Traceback|INFRASTRUCTURE|FAILED|Killed|max_usd reached` + iteration progress. Notify on completion/terminal failure.
- [ ] On completion: capture `dashboard.html`, `report.md`, `events.jsonl`, `TAU2_COMMIT.txt`, `.cast` into `run_full/`.
- [ ] Write `DEMO.md` (storyboard + exact commands + `.cast`→GIF/MP4 via `agg` + narration + SHA).
- [ ] **Gate:** full run finalized; honest fit-metric number recorded; artifacts present.

## Phase 6 — Cleanup + production docs

**Files:** delete `examples/{date_tool,json_extract,skills_bench}` + old tau2; `examples/toy_calc/**` (verify); `README.md`; `docs/REPRODUCE_tau2.md`; `.github/**` CI; `CHANGELOG.md`; example counts.

- [ ] Delete `date_tool`, `json_extract`, `skills_bench`, and any old tau2 artifacts superseded by the new flow-produced example.
- [ ] Verify `examples/toy_calc` still runs (zero-API) and matches the README quickstart; align if drifted.
- [ ] Rewrite README Quickstart + tau2 worked example + **Results (re-measured)** + examples table + skill/example counts; **purge every reference** to deleted examples across README/docs.
- [ ] Rewrite `docs/REPRODUCE_tau2.md` to the new one-command setup + one-command run, zero assumptions.
- [ ] Update CI to depend only on toy_calc (the zero-API gate); ensure no deleted-example references remain.
- [ ] Add `CHANGELOG.md` entries for framework/core changes.
- [ ] **Gate:** `grep -r` finds no references to deleted examples; CI config valid.

## Phase 7 — Final clean-room validation

- [ ] From nothing (`rm -rf .venv`, fresh clone state of derived dirs), run the documented commands **verbatim**; confirm autonomous.
- [ ] `cap-evolve check` green; toy_calc zero-API gate green.
- [ ] Final commit(s) on `feat/tau2-airline-rits-from-scratch`; summarize for PR (do not push/PR unless asked).
- [ ] **Gate:** documented path reproduces from scratch; artifacts + docs complete.

## Self-review notes
- Spec coverage: every spec section maps to a phase (RITS=P3; per-iter budget=P2; dogfooding discipline=global+P1/P3; recording=P5; cleanup/docs=P6; clean-room=global+P7).
- Discovery-driven: P1/P3/P4 explicitly expect framework gaps; fixing-then-restart is the mechanism, not a placeholder.
- Risk gates: `cap-evolve check` (P3), smoke autonomy (P4), Monitor on full run (P5), final clean-room (P7).
