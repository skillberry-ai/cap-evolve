# Changelog

All notable changes to cap-evolve are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project adheres to
[Semantic Versioning](https://semver.org/) (currently `0.x` — anything may change).

[Unreleased]: https://github.com/skillberry-ai/cap-evolve/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/skillberry-ai/cap-evolve/releases/tag/v0.1.0

## [Unreleased]
### Fixed
- **A gate that never ran was published as a gate that decided nothing.** On run 33492876620
  round 3 the whole round table came back with `reward`, `gate_delta`, `gate_threshold` and
  `verdict` `null` for all three candidates *and* for the control, `control_replicates: []` and
  `evidence_bar: null` — while `eval_rc: 0` and all 100 rollouts sat on disk, fully scored. The
  round was booked anyway, and only the driver noticing by hand kept a garbage verdict out of
  the ledger. Three things had to line up: `round.py`'s `--mode` had no `choices=` at all, so
  argparse accepted `--mode val` (the caller meant `--split val`, which is the default and a
  no-op); `gate_check.py` *does* validate `--mode`, so it exited 2 with empty stdout; and
  `_gate` caught the `json.loads` failure and returned `{"error": ...}` — a dict with every
  verdict key **missing**, which the caller `.get()`s into `None`. A row that reads "this
  candidate did not move" for a candidate nothing judged is the most expensive kind of wrong
  this script can be. Fixed at all three levels: `--mode`'s `choices=` is now imported from
  `gate_check.GATE_MODES` rather than repeated, so the two cannot drift apart again; `_gate`
  raises `GateCheckFailed` on any non-zero rc, which also closes the **second** path to the same
  silent table — the two `return 2` branches in `gate_check.py` print well-formed JSON, so
  `json.loads` *succeeded* on them and `_gate` never noticed it had failed; and
  `assert_rows_were_judged` refuses to publish any row with no reward whose evaluation
  succeeded, as a backstop independent of the cause. The one case where a missing verdict is
  honest is preserved: a candidate whose own **evaluation** failed has no rollouts to gate, so
  `gate_unless_eval_failed` keeps that row in the table carrying its `eval_rc`/`eval_error`
  instead of killing the round — a real infrastructure failure stays a report rather than
  becoming a crash.
- **A live run was reported as `failed` for as long as it was scoring its baseline.** Run
  33492876620's live snapshot showed a red `failed` badge, "no baseline and no candidate was
  ever evaluated" and `0s elapsed` on a smoke-spreadsheetbench job that had been healthy and
  working for 37 minutes. `_derive_status` decided "nothing has been scored" *before* reading
  the clock, so every snapshot taken between `splits` and the first `baseline` event — the
  whole baseline, minutes on smoke and hours on the full tier — announced an outcome the run
  had not reached. Three fixes, all of them making the reducer state only what the log
  supports: (1) freshness is read first, so a moving log with nothing scored yet is `running`
  and says *why* ("the seed's baseline is still being scored"); (2) `evaluate_candidate` now
  brackets itself with an **`eval_start`** event (split, tag, task/trial counts, rollout
  count), because an evaluation is the longest silent stretch in a run and until now that
  silence carried no evidence at all — an open `eval_start` gets an 8-hour staleness window
  instead of 45 minutes, and a run that dies inside one is `interrupted` ("scoring the seed on
  the val split (10 rollouts) and never returned"), never `failed — nothing ran`; (3) a live
  run's `elapsed_seconds` is measured to *now* rather than to its last event, with a new
  `elapsed_open` flag so the header renders "9m 17s elapsed **so far**" instead of a false
  total of `0s`. The Δ-val KPI also stopped blaming "a zero baseline" for a null relative %
  when the real reason is that no baseline exists yet.

- **Review follow-ups (PR #399).** Three findings from code review, all in the agent-optimize
  host: (1) `_CODE_SUFFIXES` was a 14-entry allowlist, so a capability whose code is C, C++, C#,
  PHP, Swift, Kotlin or Objective-C was treated as prose and never got the "the form that works
  is a guard in the code" advice — the same silent miss this host was fixed for on `.py`/`.js`,
  relocated to whichever language nobody listed. The set is broadened across scripting, shell,
  compiled, functional and query languages and is now documented as **known-good, not
  exhaustive**, so absence reads as a gap to fill rather than a decision that the language is
  prose. (2) A *declared* capability with no matching skill package was skipped by
  `harness._stage_context` while the payload still said `staged: True`, making
  some-capabilities-missing indistinguishable from everything-staged — while the all-missing case
  had always been loud. The context now carries `guidance_missing` and emits a `::warning::`
  naming the capability, since silently optimizing a surface with no allowed-edit-space brief is
  the exact defect this host was opened to fix. (3) A stray blank line after the concurrency
  guard's `return 2`.

- **The end_turn diagnosis accused a complete run of abandoning work.** Run 32871360361 booked 4
  of 10 rounds, investigated a round-5 lever, judged the residual failure unfixable by the
  surfaces it owned, **sealed test itself**, wrote its report and stopped at 121 of 1650 turns.
  The host told the operator it had "stopped of its own accord … which is what a turn ending on
  outstanding work looks like … a backgrounded job … cannot resume a non-interactive run" —
  the exact defect the warning was written for, on a run that was complete and honest. Two facts
  already in the payload disprove it: `seal == "agent"` (a loop that dies mid-turn leaves the
  host to seal, as run 32814848187 did) and an empty `unbooked_rounds`. The diagnosis now
  branches on both and reports unspent rounds as **under-use** — "it stopped when it ran out of
  edits it trusted, not when it ran out of rounds" — while the foreground explanation is kept for
  the case that actually produced it. The "a candidate may never have been committed" hedge no
  longer fires when the backstop came back clean, since it sent readers hunting for a candidate
  that provably did not exist.

- **A parent-gated round discarded the drift-free comparison it had already paid to measure.**
  Run 32871360361 round 4 gated in `parent` mode: `cand4` at 0.53 against the seed's *stored* 0.38
  = +0.15, bar 0.11 (drift), so 1.4x — marginal. The same round's two concurrent controls both
  read **exactly 0.27**, so the drift-free answer from the identical rollouts is **+0.26 against a
  bar of 0.00**. The 0.11 belongs to *when* the seed was measured, not to `cand4`; parent-mode
  gating understated the effect and inflated the bar simultaneously. Each candidate now also
  carries `control_relative` — the same gate re-run against the concurrently-measured control,
  costing no rollouts since the controls are already evaluated — so where the two comparisons
  disagree, the difference is visibly drift rather than the edit. Reported rather than made the
  default: changing the default gate mode on one benchmark's drift would be a guess about every
  other workload, while an extra comparison is strictly more information and agrees with the
  primary one wherever there is no drift.

- **A reject that overrode the gate was recorded as the gate's own verdict.** `--reject-basis
  gate` is documented as "full-val paired gate ran", and run 32871360361 booked it for `cand2` —
  which `round_i1.json` recorded as `verdict: accept` at +0.19 against a concurrent control. So
  `events.jsonl`, the run's audit record, said the gate had rejected the best candidate of the
  run when the driver had in fact overridden it. Overriding is legitimate — `round.py` leaves the
  decision to the driver deliberately — but misattributing it is not, and provenance is the one
  thing that log exists to get right. `commit.py` now reads the candidate's verdict from the
  persisted round table (possible only because `round.py` stopped leaving stdout the sole copy),
  refuses `--reject-basis gate` when the gate accepted, and offers `driver_judgement` as the
  truthful basis for an override. Every booked decision now carries `gate_verdict` and
  `overrode_gate`, so a divergence is visible rather than lost.

- **A round's verdict could be decided by which control replicate happened to be the
  reference.** On run 32871360361 round 3, two byte-identical control replicates measured two
  minutes apart read **0.32 and 0.20** — a 0.12 gap. The gate reference was whichever carried the
  round-scoped tag (0.20), so `cand3` at 0.37 scored +0.17 and **accepted**; against the other
  replicate it is +0.05 and rejects. Nothing in the table said the verdict rested on that coin
  flip. Each candidate is now re-gated against *every* control replicate — which costs no new
  rollouts, since `gate_check.py` reads what is already stored — and the table reports
  `verdict_by_reference` plus `verdict_stable`. A verdict that flips is downgraded to
  `inconclusive`, because a round that cannot tell an edit from re-measurement has not measured
  anything, whatever the delta looked like against the replicate that happened to be picked.

  For context on why this matters at this scale, the same run's replicate gaps were 0.00, 0.01
  and 0.12 across three rounds: with two replicates the gap is itself a poor estimate of the
  noise, so the stability check — a direct observation rather than an estimate — is the more
  reliable signal.

- **The round table gave the driver two incompatible noise bars, and it rejected the run's best
  candidate on the wrong one.** On run 32871360361 round 2, `cand2` was gated against a control
  measured in that same round (0.24, its replicate 0.25 — agreeing to 0.01) and beat it by
  **+0.19**, three times the `k_se=1.0` threshold. The table also reported
  `noise_floor_from_control = 0.14`, which is the control-vs-**stored**-parent gap — temporal
  drift — and its `reading` said to treat any candidate at or below the floor as no evidence.
  Those are different baselines, so the driver resolved the contradiction conservatively:
  re-derived `+0.05` against the stored best and booked a **reject**, with the note *"round noise
  floor 0.14 > margin"*. A real improvement was discarded because the instrument asked it to
  compare a control-relative delta against a drift-derived floor. The table now reports a single
  `evidence_bar` matched to how the round actually gated — the replicate gap under
  `--gate-against control`, where drift is already cancelled; the larger of the replicate gap and
  the drift under `--gate-against parent`, where every delta carries it — and the `reading` says
  that drift bounds how far the **absolute** rewards can be trusted rather than being a bar a
  concurrently-gated candidate must clear, and explicitly tells the driver not to re-derive a
  delta against the stored parent and reject on that.

- **`round.py` reported the control's reward under the parent's tag, hiding the round's own
  drift.** Line 214 loaded `parent` from `gate_ref` — which under `--gate-against control` is
  the concurrently-measured control — while the output block emitted it with `"tag": best`. On
  run 32871360361 that printed `parent: {tag: "seed", reward: 0.34}` while `baseline.json`
  recorded the seed at 0.38, a discrepancy no reader could reconcile. Not cosmetic: the gap
  between the parent's stored reward and a byte-identical control measured *now* IS the round's
  temporal drift, and on this benchmark the same seed bytes scored 0.24 / 0.44 / 0.38 across
  three runs the same day (sd 0.103, ~3.7x the acceptance bar) — so collapsing the two erased
  the one number that says whether any delta in the table means anything. The table now carries
  `parent` (the candidate being climbed from, read from `best`), `gate_reference` (what deltas
  and thresholds are actually measured against), and `parent_vs_gate_ref_drift` with a reading
  that names it as re-measurement, not progress. `delta_vs_parent` is renamed
  `delta_vs_gate_ref`, because under control-mode gating it never was a delta against the
  parent.

- **Every candidate eval in agent mode could die `ModuleNotFoundError`, and did.** An arm's
  adapter deps are installed into exactly one venv, and `run_suite.sh` runs `cap-evolve run`
  with that interpreter — so on run 32861747778 the baseline scored 0.44 while *every* round-1
  eval (candidate and control alike) crashed importing the adapter, scoring `null` rather than
  zero. CI's `PATH` never contains that venv's bin, and SKILL.md tells the agent to run
  `python "$A/round.py"`, so bare `python` could never resolve to the interpreter that works;
  the run before it had survived on luck, and with no transcript kept not even the luck was
  inspectable. Fixed as a guard rather than as prose — the interpreter that launched the host
  *is* the correct one (`run_suite.sh` invokes `"$PY" host.py`), so its bin dir now goes first
  on the agent's `PATH` and every existing `python …` command in the skill becomes correct by
  construction. The briefing also names it as `$PY` and says not to substitute another
  interpreter, `uv run`, or a fresh venv.

- **A gate too coarse to resolve its own verdict is now refused, not warned about.** The same
  run gated at `--concurrency 100` *after* SKILL.md had told it "do not raise it to buy wall
  clock", and `round.py`'s own table then carried "a verdict from this round can therefore not
  resolve an effect smaller than roughly 0.08" while the run continued and booked decisions
  regardless. This skill's own edit-form rule applies to the skill itself: where the agent has
  the criterion and violates it anyway, the form that works is a guard in code, not a further
  restatement in prose. `round.py` now exits 2 above concurrency 25 — where the measured
  degradation is established — naming the value to use instead, with
  `--allow-high-concurrency` to record the trade deliberately. Refusal, not a silent clamp, is
  already this script's idiom for an incoherent request. The briefing states the concurrency
  alongside `num_trials` and `gate_k_se`, because a number it never states is a number the
  agent picks.

### Added
- **The run now keeps the agent's own transcript.** Four hours of run 32814848187 were
  unaccounted for *and unaccountable*: its 900 metric calls account for every evaluation in
  `events.jsonl` and none fall in the gap, so nothing was being measured — but the only record
  of what the agent itself did was an 800-char `stdout_tail`, which narrows the cause to
  "something hit the 4-hour Bash ceiling" and no further. `--output-format json` cannot close
  that: it returns one result object with the final text and the totals, never the turns. So
  `run-optimizer` takes `--transcript <path>`, and the registry carries a separate
  `transcript_flag` (`--output-format stream-json --verbose`, verified against Claude Code
  2.1.241) used *instead of* `json_flag` only when a transcript is requested — its last line is
  the same result object, so cost and stop parsing are unchanged and the deterministic
  per-iteration path is untouched. `host.py` points it at `$R/host/transcript.jsonl`, beside
  the `driver_prompt.md` it already writes, so the run dir holds both what was asked for and
  what was done. Secret values are scrubbed before the file is written: a transcript records
  tool results verbatim and the run dir is a published artifact, so one `env` the agent
  happened to run would otherwise leak the gateway token. It is published into the uploaded
  dir directly (gzipped), *not* through the UI export: the artifact path is `$OUT/**` while the
  run dir sits elsewhere, and `export_static` caps every file at 256 KiB keeping the FIRST
  chunk — one turn of stream-json is already 17 KB, so the cap would have discarded exactly the
  end-of-run evidence the transcript exists to provide. `terminal_reason` and
  `permission_denials` join the captured stop fields — the latter distinguishes "blocked by the
  tool allowlist" from "chose to stop", which were previously the same observation.

### Fixed
- **An explicit `iterations` dispatch was silently ignored on the smoke tier.**
  `ITERATIONS: ${{ matrix.tier == 'smoke' && '3' || inputs.iterations || '10' }}` put the tier
  pin first, and GitHub's `||` yields the first truthy operand — so dispatching smoke with
  `iterations: 10` ran 3, discoverable only by reading `ITERATIONS` in the job log after the
  budget had been spent on the wrong round count. Smoke is the tier the algorithm itself gets
  iterated on, which makes it the worst one to pin unreachably. `NUM_TRIALS` already had this
  right, including why its input default is `""` (with a non-empty default there is no way to
  tell "asked for 10" from "asked for nothing"); `iterations` now has the same shape, and a
  test asserts the two agree so the next edit to either notices.

- **The hosted agent ended its turn to wait for a notification, and the process exited under
  it.** With the turn budget raised to 600, run 32814848187 no longer ran out of turns — it
  used 78 and stopped anyway, on `subtype: success` / `stop_reason: end_turn`, rc 0. It had
  launched round 2's full-val gate in the background and ended its turn to await word back.
  In a non-interactive run there is nothing to come back to: ending a turn ends the process
  and orphans its children. The gate finished **14 minutes after the agent was gone**, wrote a
  real verdict (`r2_comm_search` val 0.44 vs parent 0.58 → reject) that nobody read, and left
  2 of 3 rounds unspent — while the orphaned evals were still hitting the runner as
  `measure.py` measured the seal. Three changes, none of which restricts concurrency: the
  briefing now states that the *main loop* runs in the foreground and that the turn which
  launched work is the turn that collects it — fanning out subagents or a whole round's evals
  stays encouraged, since delegating the work is not the same as detaching the wait; `round.py`
  persists its gate table under `$R/work/` instead of leaving stdout the only copy, so an
  abandoned round's verdict is evidence rather than a redirect the driver may have skipped; and
  the host reports `unbooked_rounds` — candidates a round gated to a verdict that no
  `commit.py` ever booked — which `spent.iterations` cannot distinguish from a round never
  attempted. It reports rather than books: which decision a verdict deserves is the driver's
  judgement, and booking an accept after `measure.py` had sealed against the old `best_id`
  would turn a visible gap into a wrong headline number.

- **`incomplete` gave turn-budget advice to an agent that was not turn-starved.** One message
  served both stop causes and fit only the first. Run 32733635494 died on `error_max_turns`,
  where "raise `optimizer_max_turns` or lower the round count" was exactly right; run
  32814848187 stopped at 78 of 600 turns, and the same sentence pointed the operator at a knob
  already 7× larger than what the agent used. The diagnosis now splits on the stop cause, and
  reads the agent's own `stop_reason` alongside the harness's `subtype` — the discriminator is
  the former (`end_turn`), while the latter says only `success`, which is why a voluntary stop
  was indistinguishable from a clean finish. `--seal-only`, the path an operator reaches for on
  a run that died mid-loop, reports abandoned rounds too.

- **Agent-mode optimizer cost was reported as $0.00 on every run.** `run-optimizer` nests the
  figure under `cost.total_cost_usd`; the host read a flat `cost_usd`/`usd` and booked `0.0`.
  Smoke run 32733635494 spent **$8.37** (68,432 tokens) and recorded nothing — and because that
  is indistinguishable from the genuinely-unmetered gateway the skill warns about, the wrong
  conclusion was drawn from it twice. A dollar ceiling cannot bind what it cannot see: with 0.0
  booked, `max_usd` and `spend.py`'s dollar predicates were inert for the whole run.

- **The host now says WHY the agent stopped, and refuses to let an unfinished run look
  finished.** `run-optimizer` passes through the agent CLI's termination fields (`subtype`,
  `num_turns`, `is_error`, …) — vendor-neutral, like its cost parsing, and useful to the
  deterministic path too, where an exit code of 0 also covers both "finished" and "hit
  `--max-turns` with work outstanding". The host reports `stop_reason` / `num_turns` /
  `rounds_booked` / `rounds_budget`, and emits an `incomplete` field plus a `::warning::` when
  rounds were left unspent. On the run that prompted this, that state had to be reconstructed
  from a truncated stdout tail.

- **Agent mode was starved of turns.** `optimizer_max_turns` (default 80) is a
  *deterministic-path* unit: there one optimizer invocation means "propose one edit and stop",
  and the harness owns diagnosis, evaluation and gating. In agent mode the same allowance must
  also cover Phase 0, diagnose, the null-control replicates, `round.py` orchestration,
  `gate_check` and `commit.py` — per round. At 240 turns (80 × 3) run 32733635494 bought **1.9
  rounds**: the agent stopped on `error_max_turns` having just evaluated a candidate at val
  **0.530**, the best of the run, and never reached the `commit.py` that would have booked it.
  So it reported 1 of 3 rounds and discarded its best result. The host budget is now
  `max(optimizer_max_turns, 150) × (rounds + 1)` — a floor of 150/round against the ~126
  measured, with the `+1` paying for the work that is not a round (Phase 0 and the seal). A
  raised `optimizer_max_turns` still wins, so the floor is not a clamp.

### Changed
- **`OptimizerContext` gained a public seam, and the agent-mode host now reuses it instead of
  hand-rolling equivalents.** The class docstring already said it exists so "an algorithm cannot
  silently run on a thinner prompt than its siblings"; the host was the one caller that
  re-authored the blocks, and the measured consequence was an optimizer that only ever edited
  prose. Two of those blocks turn out to be exactly the guidance it was missing:
  `harness._CAP_EDIT_SPACE["tools"]` ("HIGHEST-LEVERAGE EDIT: WRITE A NEW CODE-BEARING TOOL …
  a deterministic tool can't be 'forgotten' the way a prompt rule can") and the target-reader
  block ("when the reader is weaker than you, prefer explicit rules, worked examples, and code
  enforcement over terse prose") — the CI agent under test being `aws/gpt-oss-120b`, precisely
  that weak reader.

  New public surface, all additive: `OptimizerContext.from_spec()` (construct from a
  `capevolve.yaml` dict rather than argparse args, resolving the target profile the same way),
  `capability_brief()`, `reader_brief()`, `empty_seed_brief()`, and `render_template()` (fills a
  template's slots for a caller that is not a per-iteration one, blanking only the four
  genuinely per-iteration slots). Plus `specfile.resolve_instructions_file()`, now the single
  resolver for `optimizer_instructions_file` — `cli.py` calls it too, so the rule and its #252
  warning exist once.

  What the host deliberately does **not** reuse is `instructions()`: it renders the
  per-iteration contract ("fix many root causes in this ONE candidate and STOP; the harness
  re-scores you"), which is false where the agent owns the search, the evaluation and the gate.
  The blocks are composed instead. Recorded on the class so the next reader does not "fix" it.

  Net: three hand-rolled duplicates deleted from `host.py` (`_guidance_section`,
  `_arm_instructions`, `_strip_template_slots`), its registry lookup delegated to
  run-optimizer's own `load_registry`, and its code-vs-prose advice removed in favour of the
  shared block that states it better. `empty_seed_brief` also closes a real gap: a no-skill
  control arm (one that blanks the seed to measure "author from nothing") previously got no
  author-from-scratch guidance in agent mode at all.

### Fixed
- **Three ways the agent-mode host was accidentally shaped around one benchmark.** Found by
  auditing it against the repo's other workloads rather than by a failing run:

  - **A project's `optimizer_instructions_file` was silently dropped.** `cli.py` applies that key
    only for `algorithm_name in OPTIMIZER_CONTEXT_ALGORITHMS` (hill-climb / gepa / skillopt), so
    agent mode ignored it. That is dangerous, not merely lossy: one arm uses that file to state
    that the `{placeholders}` in its second editable file are load-bearing and that breaking one
    makes EVERY task score 0 (the agent is never told where to write its answer). An agent that
    never saw the warning could wipe the run's whole signal with an edit that looks harmless. The
    host now reads and includes it — and reports a spec-named path that does not exist instead of
    silently downgrading to generic guidance (the #252 failure mode).

    Included with its **scope stated**, not pasted in: that file is written for the deterministic
    per-iteration optimizer and tells the agent to stop after editing and not to evaluate, because
    there the harness re-scores the candidate. In agent mode the agent owns the evaluation and the
    gate, so an agent obeying that line would never gate anything. Benchmark facts bind; the
    process half is explicitly superseded. Its unrendered `{{SLOT}}` template markers are stripped
    too — the parity test already treats those as a defect on the deterministic side.

  - **Code-vs-prose advice was offered to capabilities with no code.** The briefing told every
    multi-file capability that "a rule the agent violates usually belongs in code as a guard".
    For a two-prose-file capability (a system prompt plus a task template) that sends the agent
    looking for code it does not own — how a prompt-only run once ended up editing `adapter.py`.
    Now conditional on the surface actually containing code.

  - **A large capability would have had every file listed.** A skill-package capability runs to
    dozens of files; enumerating them crowded out the rest of the briefing. Now grouped by
    directory above 20 files, stating the true total and how many are not listed individually,
    and telling the agent to enumerate the rest itself — a bounded listing that never reads as
    the complete surface.
- **The hosted agent now gets the same optimizer read-context as every other algorithm.** Two
  agent-optimize CI runs on a `[system-prompt, tools]` capability edited **only the prompt file**
  across 4 of 4 candidates; the tool code sat writable and unopened in the same candidate dir. The
  cause was not the spec and not the file list. `harness.OptimizerContext` exists so "an algorithm
  cannot silently run on a thinner prompt than its siblings" — it stages each declared
  capability's skill as `./guidance/<cap>/` *and* where the agent natively discovers skills, plus
  the diagnose method, `capability_sources`, and the agent's features reference. The host never
  called it, so the agent had guidance for prose and **none at all** for the tool code beside it,
  and did what it had guidance for.

  `test_optimizer_context_parity.py` had already named this hole in its own docstring:
  agent-optimize "declares none of the context flags and drives its own loop… an algorithm absent
  from [ALGORITHMS] is NOT covered — it can still run blind while this file stays green." It ran
  blind. `host.py` now calls `inject()` with the agent as the optimizer row, and reports whether
  staging succeeded — silently-off is indistinguishable from working while quietly optimizing less
  surface, which is exactly how this went unnoticed.

  Two consequences of reusing that path, both handled: the briefing points at the staged guidance
  (unread guidance is not guidance), and the always-on `CLAUDE.md` it writes opens with "read
  `./INSTRUCTIONS.md` FIRST" — true for the deterministic optimizer, which has one, so the host
  writes the briefing there too (same bytes as the run-dir audit copy) and states that
  `LEDGER.md` / `RUNMAP.md` / `prior_iterations/` belong to the other loop and are legitimately
  absent.

### Added
- **The benchmarks suite can run `agent-optimize`.** Until now `run_suite.sh` hardcoded
  `algorithm_skill: hill-climb`, so the fully-agentic algorithm was unreachable from CI — and
  selecting it by hand would have failed anyway, because it refuses a deterministic invocation and
  nothing in CI could pick up the agent-mode handoff. Three pieces close that:

  - **`scripts/host.py` in the `agent-optimize` skill** — the headless host for agent mode. It
    renders a driver briefing from the spec + handoff (absolute paths, `num_trials`, `gate_k_se`,
    the free-text `stop_condition`, the four primitives every round must go through, and an
    instruction not to ask questions) and delegates the CLI invocation to the existing
    `optimizers/run-optimizer` runner, so registry rows, `{model}` substitution, budget-flag
    mapping, cost capture and the CLI-present hard fail are the ones the deterministic path
    already uses rather than a second copy. `--agent` takes any registry row; `--prompt-only`
    renders the briefing free; `--seal-only` seals a run a previous host left open.

    Two failure modes it exists to prevent. It raises `BASH_DEFAULT_TIMEOUT_MS` and
    `BASH_MAX_TIMEOUT_MS` to 4h: at Claude Code's 10-minute default ceiling every full-val eval on
    a real benchmark is killed mid-flight, and a perfectly healthy run reads as a broken runner.
    And it **guarantees the seal** — an agent that exhausts its turns leaves no `final.json`, which
    is both unreportable and indistinguishable from a crash, so the host runs `measure.py` itself
    and labels the result `seal: host` so it is never mistaken for the agent's own judgement that
    it was finished. An already-sealed run reports `seal: agent` instead of raising
    `TestSealError`.

  - **An `algorithm` dispatch input**, replacing `algorithm_focus`:
    `hill-climb-all` (default, unchanged behaviour) | `hill-climb-cyclic` |
    `hill-climb-hardest-first` | `agent-optimize`. One token carries both algorithm and focus
    because `workflow_dispatch` caps a workflow at 10 inputs and that list is full. `ALGORITHM_FOCUS`
    is still honoured when `ALGORITHM` is unset, so committed `overrides.env` files and hand-run
    invocations keep producing the same run; `ALGORITHM` wins when both are set, so a stale alias
    can never override a deliberate dispatch choice. `runmeta.json` now records the algorithm — a
    hill-climb number and an agent-optimize number are not a like-for-like comparison, and the
    history page should not present them as one.

  - **A `stop_condition` derived from the same dispatch inputs**, since agent mode is bounded by
    free-text prose rather than a round schedule: `iterations` → max rounds,
    `optimizer_usd_per_iter` × rounds → a whole-loop $ ceiling (0 stays unlimited, as everywhere
    else in the workflow), `gate_k_se`/`trials` → the gate. `optimizer_max_turns` becomes a
    whole-loop turn cap the same way, because the entire search is one agent process instead of one
    call per iteration. It is emitted through `json.dumps`: interpolated raw, a paragraph
    containing `:` and `$` yields a spec that silently truncates at the first colon and hands the
    agent a stopping rule nobody wrote.

  `host.py` is deliberately **not** documented in `SKILL.md`. That file is the hosted agent's
  recurring per-trigger context with ~150 characters of headroom under the 5000-token budget, and
  the agent never invokes the host — the host invokes the agent. It is documented in
  `docs/AGENT_ORCHESTRATION.md` and `ci/benchmarks/README.md` instead, following the same
  convention as the skill's other non-loop scripts (`linkcheck.py`, `abstract.py`).

### Deprecated
- **`evograph`, the fifth algorithm.** It advertised one distinctive capability — a
  collaborative weakness graph with one solver agent per weakness — and neither half survived
  comparison with its siblings. The fan-out is `agent-optimize`'s: N sibling candidates from one
  parent, one diagnosed failure cluster each, every sibling in its own working copy (a git
  worktree when the capability is in git), gated one at a time with a re-gate after each accept,
  so several fixes accumulate into one lineage *honestly*. evograph instead kept a merge on a raw
  delta over a frozen ~3-task subset of **train**, self-reported by the solver subagent that made
  the edit — no val split, no standard error, no `Δ > k·SE`. Between `baseline` and `finalize` an
  evograph run took **no held-out measurement at all**, so the sealed test number was the first
  honest signal anyone saw; whole-round revert existed only as a one-round-late substitute for the
  gate it lacked. What is genuinely unique is the run-dir `wiki/`, but the dashboard renders the
  Weakness-graph tab from `wiki/` presence alone for any algorithm that writes the format — an
  output contract, not a search strategy, and not a reason to make agent-mode users choose between
  two algorithms whose difference is a file format.

  The skill and its code stay in place (deprecation is reversible; removal is not). `cap-evolve
  algorithms` lists it last and labelled `DEPRECATED`, `cap-evolve init` no longer offers it, and
  `cap-evolve doctor` now *warns* instead of reporting `ok` for an existing evograph spec — but
  `algorithm_skill: evograph` still resolves so an old spec and an old run dir keep working.
  Follow-up for the maintainer: move the wiki format contract into `agent-optimize` as an optional
  output, stop `dashboard.py` inferring `algorithm = "evograph"` from `wiki/` presence, then delete
  the directory.

### Fixed
- **Four of the repo's ref→ref authoring violations**, all in `evograph`: `clustering.md`,
  `graph.md` and `dashboard.md` cross-linked each other, so an agent that loaded one file got half
  a rule (the `affected_tasks` freeze rule was split across two files in opposite directions). The
  schemas each file needs are now inline; references are one level deep.
- **A root `conftest.py` excluding a path that no longer exists.** It skipped
  `skills/algorithms/evograph/dashboard/backend/tests/test_app_security.py`, deleted with the
  evograph dashboard in `bac04ebd` (#317). Also drops `custom_view.json` from `evograph`'s
  `meta.yaml` summary and `"custom dashboard view"` from `branding.py` — both named the extension
  point removed in that same commit.
- **`agent-optimize`'s gate rejected byte-identical copies of the seed.**
  `gate_check.regressions()` vetoed on *any* strictly lower per-task reward from *any* parent
  level, while its docstring claimed to "mirror the harness's no-regression rule exactly".
  `harness` vetoes only when the parent measured-and-**passed** (`par >= 1.0`), which is what
  `SKILL.md` specifies — so agent-optimize's gate was silently stricter than every other
  algorithm's, and uniquely broken above one trial. At `num_trials: 1` rewards are 0/1 and
  the rules coincide; above that a reward is a fraction and the parent's is frozen from one
  draw, so a task whose true rate is 0.45 that drew 4/5 vetoes almost any re-measurement of
  the same capability. Measured P(veto fires on a null edit): 0.983 at 5 trials and 0.990 at
  10 under the old rule — it got *worse* with more trials — versus 0.428 and 0.129 under the
  harness rule, which converges. Pinned by a test that compares both rules across every
  fifth and asserts the harness predicate's source text.
- **`diagnose` was hardcoded to `rollouts/val`**, making a train split unreachable as a
  learning surface for all five algorithms. Now takes `--split train|val`, default unchanged,
  with `test` excluded so the seal cannot be diagnosed against.
- **`spend.py`/`measure.py` located the run's spec by filename**, so every agent-mode run of
  a variant spec silently reported `predicates: []` — the entire re-read-your-constraints
  discipline no-opped without a word.
- **`commit.py` accepted duplicate candidate ids**, which is how two rejects came to share one
  set of rollouts (one edit judged on another's evidence). It now refuses a tag that already
  has an accept/reject event, read from `events.jsonl` so it holds across processes.
- **`cap-evolve check --project X` checked garbage.** `Path(argv[0])` made the path the
  literal string `--project`, so the hard gate reported "no adapter" for a project whose
  adapter was present — a false failure on the one command whose job is to be trustworthy
  before you spend money.
- **`cap-evolve run` printed two JSON documents on stdout**, so `| jq` failed. Invisible
  because the suite runs `--dashboard off`.
- **Every run leaked a second dashboard server**: `maybe_launch` ran twice and the port
  helper steps past an occupied port, so the "idempotent" second call spawned another server
  and reported *that* URL.
- **`diff --side-by-side` marked the wrong side**, putting `+` in the left column for lines
  that exist only on the right.
- **The home screen scrolled and wrapped at 80×24** (36 rows × 88 cols), losing the capybara,
  tagline and golden path — the branding was exactly what got lost. `home()` is adaptive in
  both axes now: 19–22 rows at 80×24 with all 14 command names kept, full table at ≥40 rows.
- **The dashboard could not name the algorithm on a real agent run.** The agent-optimize
  markers listed event kinds a real run never emits; its distinguishing event is `screen`.
- **Gate rationales rendered blank** — agent-mode commits record them in `note`, the reducer
  read only `reason`.
- **A candidate correctly killed by a cheap screen rendered as a red `failed` badge.** An
  explicit reject is a recorded verdict even with `val: null`.
- **Spend read `$0.000` for runs whose runner reports no per-call cost**, presenting missing
  data as a measurement. Now "not reported", worded so it is true both for a genuinely free
  zero-API adapter and for real-but-unpriced spend, which the run dir cannot distinguish.
- Plus: the per-task matrix never read `val_per_task.json`; the sealed test had no baseline
  to be read against; GEPA's minibatch tab read fields the event never wrote; Compare
  disagreed with the hub on candidate counts and mixed incomparable splits silently; the
  Memory tab was a 3,530px wall of harness bookkeeping; `convergence: true` was silently
  ignored by gepa/skillopt; agent mode drew 23 blank chart rows inside labelled axes; and
  `export_run_artifacts.sh` collapsed per-trial rollouts so `pass^k` was not real.
- **The self-contained `dashboard.html` rendered a seventh of its content.**
  `el.append(svg('text', …)).textContent = x` — `ParentNode.append()` returns `undefined`, so a
  `TypeError` on the first axis label aborted the inline script and silently dropped the heatmap,
  diffs, lineage, cost, evaluations and candidates. Measured on one run: 941 → 6,782 characters of
  rendered body text, zero JS errors. This is why costs and logs were invisible.
- **Run status was always wrong.** Everything unfinalized collapsed to `"live"`, so a run that died
  weeks ago reported as running. Now derived from event evidence, with `awaiting_agent` for the
  agent-mode handoff — which is a normal state, not a failure.
- **Indecisive verdicts rendered as `rejected`**, conflating "could not measure" with "measured and
  lost". Now a first-class status that never sets `best_so_far`.
- **Missing data rendered as confident values**: `pass^k NaN%` (a dict reached a percent
  formatter), a red `failed` badge for an absent status, and "nothing has been charged yet" for an
  absent cost ledger. All now degrade to an explicit missing state.
- **`cap-evolve run --project X` silently read a different project's `capevolve.yaml`**, which
  also changed `orchestration_mode` and so whether a paid optimizer subprocess ran at all.
- **Dashboard deep links returned HTTP 404** (`/runs/<id>`, `/compare`) — only in-app navigation
  worked; a shared link or page refresh broke.
- `agent-optimize`'s documented gate, commit and copy steps could not run; `check.py` now executes
  every command the skill documents. Prose budget parsing turned `$1,200` into `$1.00` and
  `2,000 USD` into `$0.00`.

### Added
- **`skill-package` optimizes the WHOLE package, and its rules are now enforced by the loop.**
  `materialize()` exposed only `SKILL.md` + `references/*.md`, so `scripts/` and `assets/` were
  not components of the artifact the capability claimed to own, and `validate()` — the entire
  "edits stay valid skills" story — was never called from `harness`/`gepa`/`skillopt`. Now:
  every file in the package is a component (binary assets as inventory stubs); `apply()` can
  create or rewrite any of them (a NEW bundled script included), refuses writes escaping the
  package, and honors an action policy (`policy.json`:
  `frontmatter|body|reference|script|asset|add|remove`) so a run can allow prose but forbid new
  code; `validate()` `ast.parse()`s every bundled script, rejects a stub body, and RUNS a
  declared `--self-check` with a timeout and a stripped env. `harness.run_step` calls each
  capability's own `validate()` after the optimizer returns and **before any rollout is paid
  for** (generic per-capability hook, no capability special-cased): hard problems make the step
  **indecisive** — no reward, stall counter untouched, best unchanged — with the reason filed in
  the rejected memory and the LEDGER's new "Not scored" section, and warnings carried into the
  optimizer's feedback. Problems the parent already had are excluded, so a pre-existing
  violation cannot wedge a run. Also: block-scalar (`description: >`) frontmatter is parsed
  instead of silently bypassing every description lint; body >500 lines is a hard problem;
  nested/orphan references and fake TOCs warn; `scripts/trigger_eval.py` makes held-out
  trigger-rate selection a deterministic script instead of prose; `examples/toy_skill/` is a
  zero-API run whose capability IS a skill package and whose score can only rise by adding
  bundled code. `skill-package/SKILL.md` shrank 122 → 100 lines while gaining the script lever.
- **Four real τ²-bench airline runs** on `aws/gpt-oss-120b` (agent + user simulator) with
  `aws/claude-opus-5` proposing edits, committed with `events.jsonl` at
  `examples/tau2_airline/run_agentopt_v{2,3,4}/`. **All four are null results** — `best_id =
  seed`, so every delta is 0 *by construction*, and train reached 0.5308 against a 0.90 target.
  They are kept because the diagnosis is the finding: a byte-identical copy of the seed,
  measured through the real gate, is rejected. At `num_trials: 1` the run-to-run noise is
  **1.7× what a single val task flip is worth** (SD 0.1423 vs 0.0833), so no edit of any
  quality could have been recognised. `num_trials: 5` cut that to SD 0.0479 exactly as
  predicted (3.0×), which then exposed that `gate_k_se: 0.2` sets a bar ~3.6× *below* the
  noise floor. Two defects were cancelling: an over-permissive significance bar and an
  over-strict regression veto. `gate_k_se` was deliberately **not** changed — the right value
  follows from a measured noise floor, which now exists.
- **`subsample.full_val_ceiling()`** — when a screen covers every failing val task, the
  candidate's best *conceivable* full-val mean is computable; if it is below the parent, no
  full-val eval can accept, so a promote escalates to a **provable** kill. No path to accept.
- **`commit.py --reject-basis {gate|screen_kill|ceiling|budget|infra}`** — a screen's
  `decision` is authoritative only as its own statistical verdict ("promote" = could not prove
  harm, never "reached full val"); the driver's disposition is now a separate machine-readable
  field, so the audit trail can no longer contradict itself.
- **A Screens tab** in the dashboard: agent-optimize's cheap-screening mechanism had no
  representation at all — subset ids, holdout/informative split, and kill/promote decisions
  were written to disk and never surfaced.
- **A background music bed for the demo video**, synthesised from a chord table with the
  stdlib `wave` module (`scripts/demo-video/music.py`) — nothing downloaded, no licence to
  clear, byte-reproducible, with a `--check` self-test.
- **`ci/e2e_all_algorithms.sh`** asserts the two algorithm classes differently, because
  conflating them is how a broken loop hides: the three deterministic algorithms must accept a
  candidate and seal test at 1.0, while the two agent-mode ones must hand off after baseline
  with `final.json` absent.
- **A real CLI surface**: branded home screen, `help <command>` with runnable examples, `init`,
  `doctor` (readiness check that names the fix for each failure), `algorithms`, and `cap-evolve
  diff` to read the edit that moved the number. Help was previously one usage line.
- **An algorithm-agnostic live view and dashboard.** The same panels and tabs for all five
  algorithms, with per-algorithm extras derived from event kinds that were already emitted and
  previously ignored. Includes a reconciled cost ledger that reports *unattributed* spend rather
  than hiding it, and a full event log.
- **Subset screening for `agent-optimize`** — a cheap tier that can only `kill` or `promote`, never
  accept; deterministic, recorded, and biased against false kills.
- `ci/e2e_all_algorithms.sh`, which drives every algorithm end to end on the zero-API example.

### Removed
- **The evograph dashboard iframe, and with it the `custom_view` extension point.** The
  weakness graph used to be a separate bundled React app + FastAPI backend
  (`skills/algorithms/evograph/dashboard/`, `scripts/view.py`) mounted into the main
  dashboard through `custom_view.py`. Every algorithm now renders in the *same* dashboard
  with the same visual language, and per-algorithm detail is a first-class tab rather than
  an embedded document — the weakness graph reads the run dir's `wiki/` directly. This
  supersedes the `custom_view` mechanism described under 0.1.0 below: an algorithm no
  longer ships its own view.
- **The "Insights" panel** and three duplicated cost sections in the static dashboard.

### Added
- **Live terminal progress: `cap-evolve run --follow` and `cap-evolve tail` (#116).** A
  classic run was silent for its whole duration — a hung multi-hour run looked exactly
  like a working one. Both new surfaces render human-readable progress (stage, baseline,
  per-candidate accept/reject + reason, budget warnings, optimizer errors, finalize, plus
  a running cost/token meter) from the run's `events.jsonl`. The byte-offset tail is now
  ONE shared helper — `cap_evolve.eventstream` — consumed by the CLI *and* by the
  dashboard's SSE route, so the terminal and the web view can never disagree. `--follow`
  writes to stderr, leaving stdout as the machine-readable final JSON; output is plain
  text on any non-TTY (piped, CI, `NO_COLOR`). Default behavior is unchanged.

  Hardened after review: a malformed event can no longer kill the follower (and if the
  follower does stop, it says so on stderr instead of going dark); every rendered line is
  stripped of control characters, so an optimizer's stderr cannot drive the terminal or
  forge a progress line; the cost meter counts runner spend from `evaluate` and optimizer
  spend from `step` exactly once, matching the run's own `Spent.total_usd`; `--follow` is
  disabled rather than falling back to stdout when stderr is closed (`2>&-`); and
  `follow_events` yields a typed `_follow_end` sentinel naming *why* it stopped
  (`stop_kind` / `idle` / `should_stop`). `cap-evolve tail` exits `2` on an impossible run
  dir and `3` on an idle timeout with no events.

### Fixed
- **The COVERAGE diagnostic measured the agent against the wrong denominator, and so scolded
  correct answers.** It compared how many cells the agent filled against the SIZE of
  `answer_position`, and complained when the ratio was low. But measured across all 912 tasks,
  the expected output fills **under a quarter of that range on 90 of them (10.1%)** and under 60%
  on 203 (22.8%) — so on a tenth of the benchmark a *perfect* answer was told *"Most of the target
  range was left unfilled — check where the data actually ends"*. Task `56427` in pilot
  30906175891 got exactly that: it filled 15 cells, the expected output fills 20, the span is 324.
  It was scolded for ~300 cells it was never meant to write while its real defects (14 numbers
  written as text, 5 cells left empty) went unnamed. Conversely `50051` filled 32 of 32 and was
  told nothing at all, when the expected output fills **3** — its whole bug was writing 29 cells
  that should stay empty. COVERAGE now states the expected fill alongside the span, and the
  "mostly unfilled" warning is measured against that expected fill. When the gold cannot be read
  no fill claim is made at all, rather than guessed — guessing is what made this wrong. Same
  defect class as the TYPE-direction bug below, and 10× the blast radius.
- **`answer_position` strings the parser could not read made a task silently invisible.** 23 of
  the 912 tasks (2.5%) quote their range in ways the strict pattern rejected, in seven families:
  `'Vendor!'A1:D101` (the `!` quoted with the sheet, 16 tasks), `'Data'!'A2:C150` (quote before
  the range), `'T_Data!A1:AB700'` (quotes wrapping sheet and range together),
  `'Received'!'Received!A1:G16'` (sheet named twice), `'Sheet1'!BD2:308` (end *column* omitted,
  not the row), and `G12：J15` (a full-width U+FF1A colon). Every localization signal AND the
  agent-facing `TARGET SIZE` line route through `_range_cells`, so those tasks received the
  one-sentence feedback PR #289 existed to eliminate — and their prompts carried no target size
  at all. Verified on the real dataset: **23 unparseable → 1**, the remaining case being bare
  `A:G`, which names no rows and is deliberately left skipped rather than given an invented bound.
  Task `450-9` goes from zero diagnostics to a full localization (212 of 447 cells differing, 38
  empty, 32 written past the end).
- **`pass^k` / `pass@k` report as N/A, never a fake `0.0`, when `k > num_trials` (#112).**
  The default `num_trials: 1` run used to print `pass^2 = 0.0`, which reads as "0%
  reliable" when the statistic is simply undefined — and `pass_at_k` was worse, since
  `stats.pass_at_k` clamps `k → n` and so reported a k=2 capability measured from a
  single trial. `aggregate_scores` now omits any `k` outside `1..min(trials per task)` (a
  missing key IS the N/A representation), and `stats.pass_k` returns `None` instead of a
  plausible `0.0` for an undefined `k` so a direct caller can't re-derive the bug. Two
  rendering surfaces that hardcoded `k in (1, 2)` — `report.md` and the dashboard KPI
  strip — would have dropped a measured `pass^3` while fabricating a `pass^2 N/A` nobody
  requested; both now render exactly the measured ks. The SPA KPI hint also showed
  `pass^k NaN%` because `types.ts` declared `test_pass_k` as `number | null` while the
  backend has always sent the `{k: value}` dict. CI now fails on a stale committed
  `dashboard/frontend/dist` bundle (see #188).
- **The TYPE diagnostic's advice was unconditionally backwards half the time.** PR #289 appended
  one static clause to every type mismatch — *"write real numbers/dates, not their text form"* —
  regardless of direction. On pilot 30890657732 it fired on 6 tasks and was **wrong on two**:
  `57232` held `float where str was expected` and `50630` held `datetime where str was expected`,
  and both were told to write real numbers. Pilot 30799393875's own `PROCESS.md` had already
  root-caused `50630` correctly — *"GT keeps the fragment as the original text string"* — so the
  optimizer was reading its correct diagnosis and our contradictory advice at once. Feedback that
  points the wrong way is worse than none: the optimizer writes capability rules from it, and a
  rule pushing the wrong direction can regress a passing task. Advice is now direction-aware, and
  a mismatch between two non-textual types (`int` vs `float`) gets no directional claim at all.

### Added
- **A `MISMATCH` diagnostic: how many cells differ, and in which named class.** Replaying each of
  pilot 30906175891's champion failures against the gold shows that **11 of its 17 failures
  received the line "the target range spans N cell(s); your output has a value in N of them" and
  nothing else** — full coverage, matching types, so every existing signal was silent. What that
  silence hid: task `56637` differed in **1 cell of 146**, `5192` in 1 of 3, `53367` in 1 of 1,
  `11842` in 2 of 96. "1 of 146 cells differs" and "wrong" are different instructions to an
  optimizer. Each differing cell is now assigned exactly one class, so the counts cannot
  double-count: the correct value stored as text (`325-44` ×15, `56427` ×14), an Excel error text
  the agent wrote out (`55931` ×8 `#N/A`), a cell whose expected value *is* an error marker while
  the agent computed a number (`57232` ×15), values written where the expected output has none
  (`50051` ×29), text that is a prefix of the expected text (`5192`), and numeric direction when
  every difference agrees (`11842`, `59743` low; `57090` high). A separate subset count names the
  cells CHANGED although the expected value equals the cell's own input — which is the entire bug
  in `56637`. Cheap because it reuses the pass the other signals already make; capped at 50,000
  cells (4 tasks of 912 span more), and the cap is disclosed in the note rather than silently
  truncating.
- **Learning now carries across runs (opt-in warm start).** Every run began from the pristine
  seed, so each explored a different subset of rules and forgot the rest. Measured across the two
  pilots' champions: 30799393875 learned "spill/volatile functions do not survive LibreOffice
  recalculation — write the literal" (`_xlfn`×4, `TEXTJOIN`×3) and fixed tasks `47741` and
  `51958`; 30890657732 carried **zero** of it and both regressed. That is 2 tasks (0.04 val) lost
  to forgetting, which also means part of the apparent run-to-run noise was lost knowledge rather
  than variance. `SB_WARM_SEED=1` now starts from `seed_capability_warm/` — a **verbatim optimizer
  artifact, never hand-edited** (see its `PROVENANCE.md`), because hand-authoring rules there
  would make the next measured "optimizer gain" partly ours (#276). A warm-started run's
  `base→opt` delta is **not** comparable to a pristine run's — absolute score higher, measured
  gain smaller — so it is opt-in, mutually exclusive with the `SB_EMPTY_SEED` no-skill control,
  disclosed in the log, and recorded as `"warm_seed"` in `runmeta.json`. Enabled for `pilot`;
  `full` deliberately stays pristine so the headline stays a from-scratch measurement, pinned by
  a test.
- **A loud warning when the acceptance gate is too strict for hard scoring.** The committed
  overrides already documented that hard scoring makes per-task reward Bernoulli, widening the
  gate's SE, and that it must be paired with `gate_k_se=0.2` — but `GATE_K_SE` is always set by
  the workflow, so `overrides.env` cannot enforce it and nothing warned. Both pilots consequently
  ran `k_se=1.0` against hard scoring, and 30890657732's `cand_0003` scored **0.600 — above its
  accepted champion's 0.580 — and was rejected** on a delta of 0.020. `run_suite.sh` now emits a
  `::warning::` whenever `SB_SCORING=hard` meets `gate_k_se >= 0.5`. `runmeta.json` also records
  `gate_k_se`, so a run's strictness travels with its number.
- **The agent is now told where the other two graded copies are, and how big its target is.**
  PR #289 fixed the *signal* — the optimizer duly named coverage as failure cluster rank 2 and
  added a "count non-empty cells versus range size" rule. It changed no behaviour: over pilot
  30799393875 turn usage went **3.52 → 3.32 against a cap of 30**, and −0.21 on the very tasks
  where reconnaissance was the prescribed fix. Prose cannot buy reconnaissance, so these facts
  are now stated rather than requested. Of the champion's 22 failures on 50 val tasks, **8
  passed only 1/3 or 2/3** — right for copy 1, wrong for the two other graded copies. The agent
  is told 201 times across 150 rollouts that its code is "replayed on two other copies" and
  referenced them **zero** times: nothing ever said where they are, and it never enumerated the
  directory, though they sit beside its input in the mount. `spreadsheet_content` now carries
  (a) `TARGET SIZE`, computed with `_range_cells` — the same helper the scorer grades with, so
  the agent sees exactly the denominator `COVERAGE` will hold it to; (b) the paths of copies 2
  and 3; and (c) each sheet's real data extent, from the already-parsed frame's shape and
  explicitly **not** `openpyxl`'s `max_row`, which counts formatted-but-empty cells and would
  teach overfilling. Task `110-2` is the archetype: it wrote 9 of 39 target cells, exactly
  `3 rows × 3 cols`, from a five-row preview; it is now told *39 cells* and *rows 1-13*.
  Deliberately **factual, not prescriptive** — nothing instructs the agent to self-test on the
  copies, so if that strategy emerges the gain belongs to the optimizer rather than to us
  (cf. #276). One hazard closed: cases 2 and 3 are produced by replaying the agent's *final*
  code block with filenames substituted, so a final block looping over copies would have those
  names rewritten and corrupt the graded outputs — the injected text states that the final
  block must read exactly one input. The added facts are computed after the preview and inside
  a `try`, because this call site was previously unwrapped and a pandas/PyArrow `SIGSEGV` here
  once cost a whole algorithm process (run 30634898569, ~68 min and ~$6).

### Fixed
- **`openpyxl`/`pandas` are now dev extras, so the spreadsheetbench tests actually run.** They
  were declared nowhere, so every test that builds or reads a real `.xlsx` hit
  `pytest.importorskip` and vanished — including the whole of PR #289's
  `test_spreadsheetbench_failure_localization.py`, in CI as well as locally. Enabling them
  surfaced a stale test: `test_preview_text_is_unchanged_by_the_backend_switch` re-implemented
  the preview's format string inline and compared against that, so it tested the format rather
  than the python-vs-pyarrow invariant the file exists to pin. It now compares
  `_spreadsheet_preview` against itself under both backends, and skips when `pyarrow` is absent.
- **Scoring now localizes a failure instead of only saying "values did not match".** On run
  30762167950, **197 of 639 sealed tasks failed all three test cases**, and the entire signal
  the optimizer got for each was one bit — *wrong* — plus the range name. So it could learn
  generic discipline ("do not hardcode", "verify your work") but had no way to discover that
  **locating and covering** the target range was the failing sub-step: our champion learned six
  of the nine rules comparable published work reports and missed exactly the two about full
  range coverage and cross-sheet location. Task `19-7` is the archetype — `answer_position` of
  `MINUS'!B2:E11,'PLUS'!B2:E5200`, two sheets and ~5,200 rows, and the agent spent two turns
  (write, then "Done.") from a five-row preview. A miss now reports **coverage** (cells written
  vs the span of the range it was given), **unchanged sheets** (parts of `answer_position`
  byte-identical to the input), and **type mismatches** (*"text where a date was expected"*).
  Gold safety: coverage and unchanged-sheet notes never open the gold file at all — they use
  the agent's own input and the range it was handed, both already known to it — and a test
  proves that by deleting the gold file. The type note discloses a value's *type*, never a
  value; that narrow disclosure is a deliberate judgment, being the most actionable diagnostic
  for this benchmark. Runs only on a miss, only on one test case, and is wrapped so a
  diagnostic can never cost a score.

### Fixed
- **The agent could not check its own answer: the loop ended the instant a file appeared.**
  Measured on run 30740145597, the agent used **2.2 of 30 available turns** (seed: 1.9) because
  the CodeAct loop did `if case1_path.exists(): break`. Every behaviour that has to happen
  *after* writing was therefore unreachable — and not hypothetically: that run's champion had
  itself rewritten the job description to add *"3. Verification code: re-open output_path …
  You are done only once that verification looks correct"*, and turn usage moved 1.9 → 2.2. The
  optimizer wrote the right skill and the harness refused to run it. It also explains the
  dominant failure mode, 40% of tasks producing a file whose values were wrong while **0%**
  failed to produce a file at all. The loop now continues after the first write, ending when the
  agent replies without code (its way of saying it is finished), when `VERIFY_TURNS` idle rounds
  have passed (default 3), or at `MAX_TURNS`. Two traps came with it, both covered by tests:
  cases 2 and 3 are scored by **replaying** the agent's code, so replay now uses the code that
  actually *wrote* the answer (tracked by an mtime/size stamp) rather than whatever ran last —
  replaying a trailing verification snippet writes nothing and would have scored 0 on two of
  three test cases, turning the fix into a large regression; and the post-answer phase is
  **bounded**, because each round is an LLM call and an unbounded 30-turn loop is ~15× the token
  cost per rollout. The seed job description was updated to match, since it still told the agent
  the old rule.
- **The editable job description was inert: the optimizer was never told it existed.** #282
  made `task_template.md` optimizable, and pilot 30736646559 showed the optimizer ignoring it
  entirely — its `PROCESS.md` reported *"Changes made this iteration (all in `prompt.md` — the
  system prompt)"*. Both files were in its workdir; the rendered instructions mentioned
  **neither filename**, and the shared prompt-only template speaks of "the prompt" in the
  singular, so editing only the obvious artifact was the reasonable reading. The
  spreadsheetbench arm now appends a section naming both files, stating what share of the
  agent's words each accounts for (~40% / ~60%), inviting deletion of unhelpful guidance
  (pointing at the "you are done once the file exists" line specifically), and spelling out the
  placeholder contract so the optimizer learns it from instructions rather than from a rejected
  candidate. Appended to the per-benchmark copy, so the shared template stays benchmark-neutral
  — a test asserts that.
- **A broken `task_template.md` would have aborted the whole run instead of costing one
  candidate.** #282's guard raised from `live()`, and `harness.run_step` wraps the *optimizer*
  call in `try/except` — with a comment saying a bad proposal "must not abort a long run" —
  but leaves the `evaluate_candidate` call directly below it unprotected. So one bad text edit
  would have propagated out and killed a multi-hour run, destroying the sealed evaluation it
  existed to produce. The validation now RETURNS the reason instead of raising: `live()` logs
  it once, loudly, and `run_target` returns it as each rollout's error before any LLM call,
  container or turn loop — so the candidate scores 0, the gate rejects it, the run continues,
  and the optimizer reads the reason in its next trajectories and learns the contract. Tests
  now assert `live()` cannot raise, including through the real `harness._live()` path, and that
  the check precedes `import litellm`/`_get_sandbox()` so a rejected candidate costs nothing.

### Added
- **The agent's job description is optimizable capability text now, not frozen code.** On run
  30714307266 the SpreadsheetBench agent read 359 words before starting a task: 144 in
  `prompt.md` (optimizable) and **215 frozen in `adapter.py`** — so 60% of its instruction
  surface could not be optimized. That frozen text is not boilerplate: it defines what
  `instruction_type` means (Cell-Level = exact cells, Sheet-Level = the *maximum* range you may
  modify), it defines the interaction contract, and it tells the agent **"once that file
  exists, you are done"** — which is the precise behaviour behind that run's dominant failure
  mode (40 of 91 val tasks produced an output file whose values were wrong). The one accepted
  candidate added a *"verify before you save"* checklist to `prompt.md`, i.e. it was arguing
  with a sentence it was not allowed to delete. Comparable published work optimizes a single
  skill document which, in a Claude Code / Codex harness, covers this same ground, so freezing
  it made our editable surface strictly smaller than what we were comparing against. A
  capability may now ship `task_template.md`; absent, the built-in is used, so existing
  capabilities are unchanged. Because a bad edit here would tell every rollout to write its
  answer to a path it was never given, `live()` validates the placeholder contract **once per
  evaluation** and rejects the candidate before any task runs — missing required placeholders,
  invented ones (a `KeyError` on every task), and unbalanced braces are all fatal, while the
  cosmetic `{max_turns}` may be dropped. The optimizer-facing contract is documented in an
  HTML comment inside the file, which is stripped before the agent sees it.
- **Two knobs for comparing SpreadsheetBench against published skill-optimization results**,
  both defaulting to existing behaviour so no current run changes.
  `BENCH_SB_SCORING=hard` optimizes and reports the benchmark's **hard** score (all three
  OJ-style test cases must match) instead of the default **soft** score (`matches/3`).
  Published comparisons report a benchmark's "native hard score", and the two are not
  interchangeable — soft ≥ hard by construction, so quoting soft against someone else's hard
  silently flatters us. On run 30714307266 the same champion is **63.4% soft but 56.0% hard**.
  Both metrics were already recorded on every rollout and still are, so either number is
  recoverable from any past run without re-running it; only which one is `reward` (and hence
  the gate's target) changes. `BENCH_SB_EMPTY_SEED=1` blanks the seed prompt to reproduce a
  "no skill" control: the committed seed is already a short expert prompt — it states the
  `answer_position` restriction, literal-values-over-formulas, the exact `output_path` and
  error recovery — so the default configuration measures *refining an existing prompt*, not
  *authoring a skill from nothing*, and the two have very different headroom. An **empty**
  `prompt.md` now means no system message at all and deliberately does **not** fall back to
  the adapter's built-in default, which would otherwise measure that prompt while the run
  claimed to measure an unskilled agent (a missing file still falls back — absent and
  deliberately-blank are different situations). Both are repo variables rather than workflow
  inputs because `workflow_dispatch` caps inputs at 10 and that list is full, following the
  existing `BENCH_SPLIT_SEED` precedent. Gate strictness needed no new knob — `gate_k_se` is
  already a dispatch input.

### Fixed
- **Held-out runs published no base→opt reward at all — the benchmarks page showed "—" for
  exactly the runs whose numbers matter.** `metrics.suite_report` paired per-task baseline
  from `baseline.json` (the **val** split) against optimized from `final.json` (the **test**
  split). That was correct while every tier was no-holdout, which its docstring stated
  outright — but #266 gave `full`/`pilot` genuinely disjoint splits, after which no task id
  could ever match. Every `reward_opt` came back `null`, `record.rollup` then returned `None`
  for the whole suite (it requires both sides), and `benchmarks.js` renders `—` when
  `suite` is null. Verified on the published record for run 30708908659: 50/50 tasks with
  `reward_baseline`, **0/50** with `reward_opt`, `suite: null`. The honest pairing was
  available all along: `final.json` carries `test_baseline` (the seed) and `test` (the best
  candidate) over the **same sealed tasks**, which is the comparison a held-out run exists to
  produce, so that is what a held-out run now reports — and the report stops claiming
  `train==val==test` on runs where it is false. Conditioned on the val and test splits being
  genuinely disjoint, so no-holdout `smoke` keeps byte-identical behaviour (a test pins
  this; an earlier draft of the fix would have quietly shifted smoke's numbers).
- **`ci/benchmarks/utils/rebuild_record.py`** repairs records that were already published,
  reconstructing the per-task rows and suite rollup from the run's artifact (which retains
  `final.json`) using the aggregate job's own `rollup`. Needed because the aggregate job
  checks out at the dispatch SHA, so a run already in flight when this merges still publishes
  a stale record. It refuses to touch any record whose rows already carry an opt reward, so it
  is safe to point at the whole directory, and it is idempotent.
- **tau2 runs reported $0.0000 of eval spend despite real rollouts, so they could not be
  costed at all.** `sim.agent_cost`/`sim.user_cost` come from tau2's `get_cost`, which is
  **all-or-nothing**: it returns `None` the moment any non-tool message lacks a per-message
  `cost`. The adapter's `sim.agent_cost or 0.0` collapsed that `None` into `0.0`, so "the
  provider did not price this" and "this was free" produced the identical number — and
  `litellm_proxy/...` gateway aliases, which is what every CI benchmark uses, are exactly the
  unpriced case. Run 30684845463 spent real money across 10 tasks × 3 iterations and reported
  eval $0.00, with only the $25.90 optimizer cost visible. The adapter now (a) recovers
  **tokens**, which tau2 exposes per message and which the adapter was discarding with a
  hardcoded `tokens=0` — the honest fallback unit, since spend can be derived from them
  out-of-band; (b) salvages a **partial** cost from whatever the provider did price, instead
  of dropping the whole run's cost over one unpriced message; and (c) records `cost_source`
  (`tau2` / `partial_messages` / `unpriced`) plus the missing-cost and missing-usage counts in
  the rollout metadata, so a `0.0` can be read as *unpriced* rather than *free*. It
  deliberately does **not** price tokens from a public rate table — the gateway's real rates
  are not knowable client-side, and a fabricated dollar figure sitting next to measured ones
  is worse than an absent one; a test enforces that. `Rollout.cost_usd` is a non-optional
  float that coerces `None` to `0.0`, so representing "unknown" in the field itself would
  need a `core/` change and is left alone.
- **Sandbox containers were never released, and the leftovers ran forever.** The vendored
  server reclaims a container only on a hardcoded 10-minute idle timeout
  (`api.py`'s `KERNEL_TIMEOUT`) or on a force-cleanup at SIGINT, and nothing released a
  kernel when its rollout ended — every rollout mints a fresh `conv_id`. At 8-way
  concurrency that leaves ~50 containers alive at all times, and the ones still alive when
  the server is asked to stop are stopped **serially** inside the adapter's flat 60s
  shutdown budget: whatever the budget doesn't reach is orphaned and then runs forever,
  because the only process that knew about it is gone. Run 30691123806 left **176**
  `conv-capevolve-*` containers running on the self-hosted runner (all "unhealthy", load
  average 14), with `ConnectionRefusedError: Failed to reconnect to kernel websocket`
  throughout its sandbox log — at three full seeds (2,279 rollouts each) that is a
  runner-health problem, not a cosmetic one. The adapter now releases each rollout's
  container in a `finally`, so the live count tracks concurrency instead of run length, and
  the shutdown budget scales with however many are actually left (~0 now) instead of being a
  flat 60s. Done **without touching `third_party/`** — that directory is a filtered subtree
  which must stay byte-identical to upstream for `git subtree pull` to work, so the adapter
  serves a small wrapper that imports the vendored `ExecuteHandler`/`cleanup_kernels`
  unchanged and adds `/release` (plus `/health`, which is what lets shutdown size its
  budget). Verified live on the runner: container created → released → `live_kernels: 0` →
  shutdown in 0.1s with nothing left to stop.
- **The 912-task dataset's own top-level directory locked the sandbox out of everything.**
  The upstream `spreadsheetbench_912_v0.1.tar.gz` stores its top-level dir as `drwx------`
  (the 200-task sample stores `0755`), and `tar` preserves stored modes. The adapter
  bind-mounts exactly that dir at `/mnt/data` in a container running as uid 1000, so a
  non-traversable root makes every path under the mount unreachable — **reads too, not just
  writes**: `open()` on an input workbook and even `Path.exists()` raise `EACCES`, because a
  missing search bit is not a missing file. Only the `full`/`pilot` tiers were affected;
  `smoke` uses the 200-task sample. Pilot run 30691123806 spent **$77.49 and ~3h** to
  discover this, scored 0.000 across 50 tasks with an EACCES traceback in all 50 rollouts,
  and blamed "the output dir is not writable" — a diagnosis that costs hours, because the
  output dir was fine and so were `spreadsheet/` and the workbooks (0755/0644). Fixed at
  three levels: `fetch_data.sh` normalizes modes on extract (`chmod -R a+rX` — traverse and
  read only; the dataset is read-only INPUT) and re-normalizes the root for trees cached by
  an older revision; the adapter widens the root it can own and then **verifies the mount
  before the first LLM call** (`_preflight_mount`), so an unusable mount aborts in seconds at
  ~$0 instead of burning a full eval; and the denial classifier now recognizes denied
  *reads* anywhere under the mount and reports the traverse fault distinctly from the
  output-dir fault, since the two need different fixes.
- **The optimizer was told to edit `tools.py` on a benchmark that has no tools.** The shared
  `templates/project/optimizer/INSTRUCTIONS.md` is written for a capability that includes
  tool CODE: it instructs "prefer code", names `tools.py` and tau2's `get_*_details`, and its
  self-check demands "edits across BOTH policy.md AND tools.py". SpreadsheetBench's
  capability is `[system-prompt]` — a single `prompt.md` — so that guidance contradicts the
  correctly-rendered "what you are editing" block and sends the optimizer hunting for code.
  In run 30691123806 it found some: `cand_0002` scored 0.567 by patching **`adapter.py`** to
  chmod the data root while leaving `prompt.md` byte-identical to the seed, so that run's
  apparent 0.000 → 0.567 gain was infrastructure repair, not capability. A prompt-only
  instructions template (`INSTRUCTIONS.prompt-only.md`) now ships alongside the default:
  prompt-appropriate levers (output contract, ordered/unavoidable step, worked method,
  narrowing predicate, consolidation), an explicit boundary that the adapter/harness/scorer
  are not editable, and a rule that an ENVIRONMENT fault is to be *diagnosed and handed
  back*, not worked around. `run_suite.sh` selects it for the spreadsheetbench arm at the
  path `cli.py` already defaults to, and additionally pins it by ABSOLUTE path — a relative
  `optimizer_instructions_file` resolves against different cwds in check vs run and can
  silently fall back to the generic template (#252), which would erase this fix with no
  error. That spec line is empty (a verified no-op in both the PyYAML and the fallback
  parser) for every other benchmark, so no `core/` change was needed and tau2's
  code-bearing guidance is untouched.
- **A running `pilot` leg was invisible on the benchmarks page.** `site/benchmarks.js`'s
  `JOB_RE` hardcoded `smoke|full`, so it never matched the `pilot / spreadsheetbench` job name:
  no "Running now" entry and no way to open the run's UI while it executed. Nothing errored —
  the run simply could not be seen. The tier is now matched generically (the bench allowlist
  stays explicit so "plan legs"/"aggregate history" still never match), and the history table's
  tier filter offers `pilot`. A test ties the site's matcher to the workflow's `TIERS` list so
  adding a tier cannot silently hide it again.

### Fixed
- **gpt-5.x rejected our temperature override, failing every rollout at $0.00 spend.** The
  gateway answers `400 Unsupported value: 'temperature' does not support 0.0 with this model.
  Only the default (1) value is supported.` — so run 30682720920 lost an entire pilot: all 60
  tasks errored on their first LLM call, the run finished in 9 minutes having billed nothing,
  and reported **success** with a clean-looking 0.000. `model_config` (shared by five adapters)
  now sends no `temperature` for model families that pin it, making the effective temperature
  the model's own default — 1 for gpt-5.x, the only value they accept. Safer than sending the
  value the error names, since a deployment may reject the parameter outright. A blank or
  `default`/`model`/`none` TEMPERATURE now also means "use the model default"; every other
  model still gets 0.0, so this is a no-op for tau2/swebench/skillsbench.
- **An infra-dominated run reported success.** Completion is not sufficient: a run whose every
  rollout died on infrastructure still writes `baseline.json`/`final.json`, records iterations,
  passes the gate, and publishes 0.000 to `benchmark-history` as though it measured something.
  `assert_run.py` now FAILS when more than `--max-infra-frac` (default 0.5) of baseline tasks
  are infrastructure errors, reusing `metrics.py`'s existing `_infra_task` rule — which already
  rendered those tasks as `⚠️ infra-error` in the report while the job went green. Verified by
  replaying run 30682720920's real `baseline.json`: the old gate exits 0, the new one exits 1.
  A genuine all-zero run with no infra errors still passes.

### Added
- **`pilot` tier — a cost/runtime measurement rig for SpreadsheetBench.** Answers the three
  things a ~$450 full run depends on and nobody has measured: cost and wall-clock per rollout at
  `MAX_TURNS=30` (every existing anchor is smoke at 5 turns, so it does not transfer), whether
  `azure/gpt-5.5` works on the gateway at all, and recalc throughput at non-trivial volume.
  60 tasks drawn **only from `full`'s train ids**, so `full`'s selection and test splits stay
  untouched. Its split is deliberately not 2:1:7 but 5/50/5 — `val` sized to be a solid anchor
  (full's is 91, so one pilot iteration extrapolates directly), `test` tiny because `finalize`
  evaluates it twice and teaches nothing new. **Pilot rewards are not comparable to anything**,
  which is why the tier is excluded from `tier=all`: the aggregate job publishes every leg to
  `benchmark-history` and sweeping it in would put meaningless rows on the benchmarks page.
- **Tiers are now populated per benchmark.** The planner only emits a leg when
  `ci/benchmarks/<bench>/<tier>/tasks.json` exists. `run_suite.sh` already no-opped on a missing
  file, but emitting the leg anyway claimed a slot on the single serialized self-hosted runner
  just to warn and exit — the waste the planner was introduced to remove. A partially-populated
  tier (only one benchmark ships `pilot/`) now costs the others nothing. Verified no-op: all 30
  pre-existing dispatch/label selections produce byte-identical legs.

### Added
- **SpreadsheetBench full tier can now produce a SkillOpt-comparable number.** Four gaps closed,
  all without touching `core/`:
  - **Held-out split.** A tier that commits `<bench>/<tier>/split_ids.json` now gets that exact
    disjoint split instead of the default no-holdout FIT split (`train == val == test`), so
    `finalize` yields a real generalization number rather than a fit. `full/split_ids.json` ships
    182/91/639 over all 912 tasks, generated by `spreadsheetbench/utils/make_split.py`, which
    reconstructs SkillOpt's *stated default* (`split_seed=42`, 2:1:7 — arXiv 2605.23904). Their
    SpreadsheetBench-specific split and task count are not published, so this is a documented
    reconstruction, **not** a reproduction; the tier README says so. The loader fails loudly on a
    split that overlaps, omits tier tasks, or has an empty val/test — a stale split silently
    evaluating a different task set would invalidate a whole comparison.
  - **Seeds.** `split_seed` is threaded into the generated spec (default 0 = previous behaviour).
    With a committed split the partition is fixed, so it varies only per-trial rollout seeding,
    which is what makes the "≥3 seeds" requirement possible on one split. Driven by the repo
    variable `BENCH_SPLIT_SEED` because `workflow_dispatch` caps inputs at 10 and that list is full.
  - **Agent turns.** SkillOpt runs SpreadsheetBench with up to **30** turns; the adapter default
    is 5, a real handicap on a multi-round benchmark. Full now uses 30; smoke stays at 5 so its
    numbers remain comparable to its own history.
  - **Scope labeling.** `actions: [edit]` is *not* machine-enforced (nothing in `core/` or
    `skills/` reads it); scope comes from `capabilities: [system-prompt]` over a single
    `prompt.md`, which is a closer match to "skill text only" than `skill-package` would be.

### Changed
- **SpreadsheetBench formula recalculation is no longer serialized.** The vendored
  `just_open_libreoffice` lets soffice use its default user profile, so concurrent instances
  conflict and it had to run behind a process-global lock — the full tier's scoring bottleneck at
  912 x 3 = 2,736 serialized soffice startups per evaluation, unaffected by
  `SPREADSHEETBENCH_CONCURRENCY`. `_recalc_workbook` replaces it, giving each invocation its own
  `-env:UserInstallation` profile, capturing output (the vendored helper printed on every failure
  path), leaving the workbook untouched when recalc fails, and reporting failure rather than
  raising. Verified against a fake soffice for profile uniqueness, concurrency, in-place
  replacement, timeout/exit/missing-binary handling and stdout silence.

### Fixed
- **SpreadsheetBench rollouts could segfault the whole run (pandas 3.x + PyArrow strings).**
  `_spreadsheet_preview` builds its preview with `pd.read_excel`; pandas 3.x makes `str`
  columns `ArrowStringArray`, so construction goes through pyarrow's C++ layer. Called
  concurrently from the rollout thread pool that crashed with SIGSEGV in
  `ArrowStringArray._from_sequence` — uncatchable, so one bad preview killed the algorithm
  process and every completed iteration with it (run 30634898569 lost 68 minutes and ~$6
  after an accepted baseline). The adapter now pins `mode.string_storage = "python"` once per
  process, so the crashing frame is never reached; verified on pandas 3.0.5 / pyarrow 25.0.0
  that the preview text is byte-identical to the default, so the agent's prompt — and result
  comparability — are unchanged. Set once at import rather than per call, because
  `pd.option_context` restores a process-global option on exit and would race the other
  rollout threads. Guarded by both runtime tests and dependency-free AST checks, since
  `core[dev]` has no pandas and a skipped guard is no guard.
- **A failed benchmark run was recorded as `"conclusion": "success"`.** The completion gate
  (`Assert the suite run completed`) ran *after* `Write run metadata`, and `job.status` is
  evaluated when a step runs — so a run that crashed mid-optimization and failed the gate still
  wrote `success` into `runmeta.json`, which the aggregate job then published to
  `benchmark-history`. Runs 30553822478 and 30608405812 are both recorded as successes on the
  history page despite failing. The gate now runs before the publishing steps; everything
  downstream is `if: always()`, so metrics/UI/artifacts/PR-comment are still published on
  failure — only the recorded conclusion changes.
- **Command-injection vector in the benchmark job's metadata step.** `github.head_ref` (an
  attacker-controlled PR branch name) was interpolated straight into an inline script on a
  **self-hosted** runner. It now travels via the environment, and both free-form fields
  (`branch`, `source`) are emitted as JSON string literals — shell quoting alone let a branch
  name containing a double quote produce an unparseable `runmeta.json`. Verified against 24
  combinations of hostile branch name x event x job status. `benchmarks.yml` is now
  actionlint-clean.

- **SpreadsheetBench formula recalculation was silently never running (#256).** #240 widened the
  *directories* the adapter creates so the uid-1000 container could write its output; the output
  *file* it writes is still owned by uid 1000 at ~0644, so the host-side scorer could not rewrite
  it. `just_open_libreoffice` recalculates into a `/tmp` tempdir and moves the result back —
  cross-filesystem, so `shutil.move` falls back to `copy2`, which opens the container-owned file
  for writing and dies with `[Errno 13] Permission denied: <n>_<id>_output.xlsx`. The adapter
  swallowed that with `except Exception: pass`, so comparisons ran on **stale cached values** and
  formula-only cells read as empty — every score a floor, and the noise looked like model variance
  (baseline 0.293 vs 0.393 on two runs of the same 10 tasks). `chmod` cannot fix this (you may not
  chmod a file you do not own), so `_reclaim_container_file` replaces the file with a byte-identical
  copy we own — the create and rename need write+execute on the *directory*, which is already
  `0o777` and deliberately non-sticky for per-rollout dirs. A recalc that still fails is now
  reported as an `INFRASTRUCTURE:` line in the task feedback instead of being swallowed, so the
  optimizer is told not to spend budget on it.
- **A native crash in a phase process left no evidence (#257).** Run 30608405812's algorithm step
  died with `{"returncode": -11, "signal": "SIGSEGV"}` and nothing usable: a segfault has no Python
  traceback, and `_step_failure` captured only `stderr[-8000:]` — a window filled entirely with
  routine per-rollout scoring chatter emitted long after the crash-relevant output. Now:
  `cap_evolve` enables `faulthandler` on import (stderr only, so the stdout JSON contract is
  untouched; opt out with `CAPEVOLVE_NO_FAULTHANDLER=1`), the captured stderr keeps a head *and* a
  tail with an explicit omission marker, and the signal hint is signal-specific — SIGSEGV no longer
  misdirects the reader to the OOM killer and `dmesg`.
- **A printing scorer no longer destroys a completed run (`cap-evolve run` stdout contract).**
  `harness.evaluate_candidate` now wraps the whole run+score body in
  `redirect_stdout(sys.stderr)`, not just the rollout pool. Only the RUN phase was guarded
  (`run_trials_pool`, for tau2's progress output); SCORING was free to print, and
  SpreadsheetBench's vendored comparator prints `"Cell values in the specified range are
  identical."` on every *passing* check (its LibreOffice recalc helper prints on every
  failure path). That prose landed on the baseline phase's stdout, so `cap-evolve run`'s
  `json.loads(proc.stdout)` died with `Expecting value: line 1 column 1` — *after* an
  11-minute, $2.65 baseline had already succeeded and been written to disk, and before any
  optimization iteration ran ([run 30553822478](https://github.com/skillberry-ai/cap-evolve/actions/runs/30553822478)).
  The bug was latent until spreadsheetbench first scored above zero: no passing comparison,
  no print. As a second line of defense, `cli._json_payload` now extracts a phase's JSON
  payload from stdout newest-object-first instead of assuming the buffer is pure JSON, so
  one stray `print` anywhere under an adapter can no longer discard finished work — while
  stdout carrying no JSON at all still fails loudly.
- **Benchmark CI robustness (skillberry-1 self-hosted runner).** Three fixes so a broken
  runner or gateway is *loud*, not a silent all-0.000 "success": (1) `ci_setup.sh` now
  installs + hard-verifies the `claude-code` optimizer CLI — when it was missing the
  optimizer failed every iteration (`cli_present:false`) and every task reported
  `best=seed`/0.000; (2) `ci_setup.sh` adds a **model-gateway budget preflight** — one
  tiny gpt-oss call that aborts with a clear error on `429 budget_exceeded` (the shared
  LiteLLM gateway hitting its spend cap 429s both the agent and the optimizer, killing
  every rollout with `INFRASTRUCTURE_ERROR`); (3) `run_suite.sh` iterates the task list on
  FD 3 (+ `run_task </dev/null`) so the optimizer subprocess reading stdin can no longer
  DRAIN the here-string and cut the suite off after one task. `metrics.py` now detects an
  infra-dominated eval (majority trials errored + reward≈0) and renders it as
  `⚠️ infra-error`, excluding it from the suite mean/flip counts so a gateway outage no
  longer looks like a capability regression.

### Added
- **`evograph` — evo-graph weakness-graph algorithm and dashboard view.** New agent-mode
  algorithm skill (`skills/algorithms/evograph/`, the 20th skill) that clusters failing
  tasks into a weakness graph to steer edits, plus its own mounted dashboard view
  (`scripts/view.py` + a self-contained frontend bundle) surfaced inside the cap-evolve
  dashboard.
- **Per-algorithm custom dashboard views.** The dashboard backend gains
  `custom_view.py`; an algorithm skill may ship its own view, iframe-mounted into the
  run deep-dive alongside the default template.
- **SWE-bench oracle mode + calibrated smoke selection.** The SWE-bench adapter gains
  `SWEBENCH_ORACLE=1`, which attaches the "Oracle" retrieval context (the file[s] the
  gold patch touches, from `princeton-nlp/SWE-bench_Lite_oracle`'s `text` field) to the
  prompt so a single-shot mid-tier reader (gpt-oss-120b) can produce a diff that actually
  applies — blind problem-statement-only prompting is near-hopeless for weaker readers.
  Scoring still runs on the base dataset (eval path unchanged); off by default. Adds
  `<patch>…</patch>` extraction for the oracle output contract. New offline dev tool
  `ci/benchmarks/swebench/utils/select_candidates.py` builds a candidate pool (Verified∩Lite,
  Easy `<15 min` difficulty, single-file/small-patch, oracle-context under a token budget)
  used to pick the swebench smoke tier's 5 tasks (`ci/benchmarks/swebench/smoke/tasks.json`),
  which now run through the same `run_suite.sh` path (baseline + optimized in one run) as
  every other benchmark's smoke tier. `select_candidates.py` and its output
  (`utils/smoke_candidates.json`) live under `utils/` — not read by CI, only for
  re-picking tasks later.
- **SkillsBench smoke tier aligned with tau2/swebench.** `ci/benchmarks/skillsbench/smoke/tasks.json`
  grows from 2 tasks (tag `hard`) to all 10 tasks the adapter's `TASK_IDS` allowlist
  supports (tag `repr`, matching tau2's count and the tau2/swebench tag convention) —
  the same pool already used and baselined in `docs/REPRODUCE_skillsbench.md` (baseline
  pass rate 0.333, not 0). `ci/benchmarks/README.md`'s "Hard-only suite" framing is
  reworded to "Calibrated-headroom suite" to match this and swebench's own
  `select_candidates.py` selection goal (nonzero but not saturated at baseline), rather
  than the stricter "every curated task has baseline reward 0" claim neither benchmark
  actually satisfies.
- **Adapter-native batch scoring (`score_batch`).** New optional adapter hook,
  `score_batch(tasks, rollouts) -> {task_id: Score}` — the scoring-side counterpart to
  `run_batch`/`run_trials` (see `docs/ADAPTER_CONTRACT.md`). The harness calls it once
  per trial instead of looping `score()` per task; any task id it omits falls back to a
  single `score()` call, so a partial implementation can never silently drop a score.
  The SWE-bench adapter now implements it, batching a trial's instances into **one**
  `swebench.harness.run_evaluation` call with a comma-separated `--instance_ids` list —
  previously every trial ran one Docker-harness subprocess per instance with nothing for
  `--max_workers` to parallelize over, so `SWEBENCH_MAX_WORKERS=10` (already set in CI)
  was a no-op. Adapters that don't implement `score_batch` are unaffected.

### Fixed
- **tau2 adapter no longer races tau2's global RNG seed** across concurrent trials
  (`templates/adapters/tau2_bench/adapter.py`), so per-trial `seed` is honest under
  parallelism.
- **Optimizer cost is recovered on a non-zero optimizer exit** (`core/cap_evolve/harness.py`)
  instead of being dropped, so a crashed optimizer iteration still reports its spend.

## [0.1.0] - 2026-07-27

Initial release. Tag [`v0.1.0`](https://github.com/skillberry-ai/cap-evolve/releases/tag/v0.1.0)
at commit `1a24604`; `core/pyproject.toml` version `0.1.0`. The date is the GitHub
release's `publishedAt` (`2026-07-27`), not the tag-commit date (`2026-07-26`), because
Keep a Changelog dates the *release*.

### Added
- Honest-eval core (`cap_evolve`): seeded splits with a sealed test set,
  significance gate, multi-trial variance, pass^k + pass@k, bootstrap CIs.
- **19 Agent Skills**: phases (intake, implement-and-check, baseline, evaluate,
  diagnose, gate, finalize, report), capabilities (system-prompt, tools, mcp-tool,
  skill-package), algorithms (**hill-climb** with `--focus all|cyclic|hardest-first`,
  **gepa**, **skillopt**, **agent-optimize**), one **run-optimizer** skill backed by
  `optimizers/registry.yaml` (claude-code, codex, gemini-cli, opencode, openclaw,
  ibm-bob, generic, mock), and orchestrate + a `using-cap-evolve` session-start router.
- **`gepa`** (flagship): real GEPA — two-stage minibatch-then-full-val economy,
  per-instance Pareto frontier with frequency-weighted parent sampling, trace-based
  reflective dataset, round-robin component focus, system-aware merge across lineages,
  rollout/metric-call budget, eval cache (arXiv:2507.19457).
- **`skillopt`** (flagship): epochs × mini-batches with a textual learning rate
  (integer edit budget on a constant|linear|cosine schedule), within-epoch
  rejected-edit buffer, and a gated epoch-boundary slow/meta update (arXiv:2605.23904).
- Git-backed iteration store (default) + optimizer memory (MEMORY.md/STATE.md/rejected.jsonl).
- **Self-contained** `dashboard.html` (no CDN): KPI strip, cumulative-best stair,
  tasks×iterations pass/fail heatmap, per-iteration diff, lineage tree (merges as
  multi-parent), optimizer-vs-runner cost/tokens/latency, annotations — plus the
  `report` phase's `--terminal` ANSI report for in-chat progress.
- **Claude Code plugin** (`plugins/cap-evolve/`, install `claude --plugin-dir
  ./plugins/cap-evolve`): every skill as `/cap-evolve:<skill>` (dual-mode: standalone
  slash command + orchestrator-callable + headless JSON), honesty **hooks** (PreToolUse
  denies edits to the sealed test/gold; Stop/SubagentStop block until `cap-evolve check`/
  the gate is green) in **core-owned scripts**, read-only diagnoser + writer proposer
  subagents, and the `using-cap-evolve` router.
- Host-agnostic installer.
- Examples: toy_calc, skillsbench, tau2_airline — the last a
  real 50-task × 10-trial run, val **0.536 → 0.712** (best candidate `cand_0007`,
  +0.176 / +32.8% relative; *fit metric*, `train == val == test`, so the test number
  0.694 pass@1 is not held out). Baseline val, best val and the delta come from
  [`examples/tau2_airline/run_full/ui/data/runs_run_full.json`](examples/tau2_airline/run_full/ui/data/runs_run_full.json)
  (`summary.baseline_val = 0.536`, `summary.best_val = 0.712`, `best_id = cand_0007`,
  `delta_abs = 0.176`, `delta_pct = 32.8`); the sealed-test `0.694` comes from
  [`examples/tau2_airline/run_full/final.json`](examples/tau2_airline/run_full/final.json)
  (`test.reward` / `test.pass_at_k.1`). Canonical prose:
  [`docs/RESULTS.md`](docs/RESULTS.md).
- **`cap-evolve run --resume`** — continue an interrupted run (pod eviction, crash,
  timeout) from its last completed state instead of starting over. Reopens the run dir
  (`--run-ts`, else the latest under the base) via `RunDir.create(exist_ok=True)` so it
  no longer fails with `FileExistsError`; skips the baseline when it already ran; picks
  the loop up at iteration N+1 from the current best (spend, journal, git history, and
  the test seal are all preserved); and skips a re-finalize when the test seal is already
  burned. Explicit budget flags (`--max-iterations`, …) **extend** a resumed run. Works
  across every algorithm — `hill-climb`/`skillopt` already resumed from rollouts, and
  **`gepa` now reconstructs its full pool/lineage/frontier** from the run dir (a tiny
  `gepa_state.json` checkpoint + rollouts) so its Pareto search continues where it stopped.
- **Consuming-LLM profiles.** Declare the runtime/consuming model via `target_model`
  (a concrete model id or a capability tier: `frontier|strong|mid|weak`) in
  `capevolve.yaml`. The optimizer prompt (new `{{TARGET_READER}}` block) and the
  capability guidance now adapt their proposed edits to that reader — a weaker reader
  gets more explicit rules, worked examples, literal slot-filling docs, and code
  enforcement; a frontier reader gets leaner prose that explains the *why*. This is
  DISTINCT from `optimizer_model` (which proposes the edits). `cap-evolve check` warns
  (non-blocking) when the declared consuming model's tier differs from the runner's
  actual model (via an optional `adapter.runner_model()` hook). Report + dashboard
  surface the consuming model alongside the optimizer model. Blank `target_model`
  preserves prior behavior exactly; optional `target_profile_file` overrides a tier's
  built-in brief. The tau2-airline example opts in (`gpt-oss-120b`, tier `mid`).
- **Six more coding agents as optimizers** — `cursor` (Cursor `cursor-agent`),
  `droid` (Factory Droid), `copilot` (GitHub Copilot CLI), `kimi` (Moonshot Kimi),
  `pi` (earendil-works Pi), and `antigravity` (Google `agy`, a configurable wrapper).
  This brings cap-evolve's supported coding-agent set to parity with
  [obra/superpowers](https://github.com/obra/superpowers). Each is **one row** in
  `skills/optimizers/registry.yaml` (verified headless command, except `antigravity`
  which reads `CAPEVOLVE_ANTIGRAVITY_CMD` because its auth is Google-Sign-In-only and
  its non-interactive approve flag is unconfirmed) plus a per-CLI
  `run-optimizer/references/<name>.md`. `install.sh --host` learns each one's skills
  dir. No core/runner changes — the registry-driven `run-optimizer` already generalizes.
- **Per-iteration optimizer dollar cap** (`optimizer_usd_per_iter` in `capevolve.yaml`):
  threaded through `run-optimizer --usd-budget` into a new registry `usd_budget_flag`,
  enforced natively by the optimizer CLI where supported (claude-code →
  `--max-budget-usd N`). Optimizers without a native $ cap (e.g. ibm-bob) ignore it and
  are bounded by `optimizer_max_turns` / the cumulative `max_optimizer_usd`.
- intake `INPUTS.md` now covers the **runner model + credentials + custom
  OpenAI-compatible/RITS endpoint** and **obtaining/installing a benchmark repo** (with
  the resolved commit recorded), aligning the interview contract with the README.

### Fixed
- Scaffolded project adapter template (`templates/project/adapters/adapter.py`) matched
  the real `CapabilityAdapter` contract: abstract `tasks` / `run_target(task, ctx, *, seed)`
  / `score`, with `materialize`/`live`/`apply`/`run_batch` documented as optional
  overrides. The old stub used a stale `run_target(task, candidate_dir, split)` signature
  and presented `apply` as a 4th abstract method, which a filled-in body could make the
  stub-probe silently pass.
- Honest-eval core (`cap_evolve`): seeded splits with a sealed test set,
  significance gate, multi-trial variance, pass^k + pass@k, bootstrap CIs.
- **20 Agent Skills** (one per `skills/<component>/<name>/SKILL.md`): phases (intake,
  implement-and-check, baseline, evaluate, diagnose, gate, finalize, report), capabilities
  (system-prompt, tools, mcp-tool, skill-package), 5 algorithms — 3 run-executable
  (**hill-climb** with `--focus all|cyclic|hardest-first`, **gepa**, **skillopt**) plus 2
  agent-mode (**agent-optimize**, **evograph**) — one **run-optimizer** skill backed by
  `optimizers/registry.yaml` (claude-code, codex, gemini-cli, opencode, openclaw, ibm-bob,
  generic, mock), and orchestrate + a `using-cap-evolve` session-start router.
- **`gepa`** (flagship): real GEPA — two-stage minibatch-then-full-val economy,
  per-instance Pareto frontier with frequency-weighted parent sampling, trace-based
  reflective dataset, round-robin component focus, system-aware merge across lineages,
  rollout/metric-call budget, eval cache (arXiv:2507.19457).
- **`skillopt`** (flagship): epochs × mini-batches with a textual learning rate
  (integer edit budget on a constant|linear|cosine schedule), within-epoch
  rejected-edit buffer, and a gated epoch-boundary slow/meta update (arXiv:2605.23904).
- Git-backed iteration store (default) + optimizer memory (MEMORY.md/STATE.md/rejected.jsonl).
- **Self-contained** `dashboard.html` (no CDN): KPI strip, cumulative-best stair,
  tasks×iterations pass/fail heatmap, per-iteration diff, lineage tree (merges as
  multi-parent), optimizer-vs-runner cost/tokens/latency, annotations — plus a
  `cap-evolve report --terminal` ANSI report for in-chat progress.
- **Claude Code plugin** (`plugins/cap-evolve/`, install `claude --plugin-dir
  ./plugins/cap-evolve`): every skill as `/cap-evolve:<skill>` (dual-mode: standalone
  slash command + orchestrator-callable + headless JSON), honesty **hooks** (PreToolUse
  denies edits to the sealed test/gold; Stop/SubagentStop block until `cap-evolve check`/
  the gate is green) in **core-owned scripts**, read-only diagnoser + writer proposer
  subagents, and the `using-cap-evolve` router.
- Host-agnostic installer.
- Examples: toy_calc, json_extract, date_tool, skills_bench, tau2_airline
  (real run: 0.46 → 0.80 on 50 tasks).
- `--resume` to continue a run from its current best.

### Changed
- **Skill library collapsed (26 → 19).** The 8 per-CLI optimizer skills became one
  `run-optimizer` skill + a one-row-per-optimizer `optimizers/registry.yaml`; the
  three hill-climb algorithm clones (all-at-once / cyclic / hardest-first) became one
  `hill-climb` skill with `--focus`. Adding an optimizer is now one YAML row.
- **Adapter contract changed** to `tasks(split)` · `run_target(task, ctx, *, seed)` ·
  `score(task, rollout)` · pure `materialize(candidate_dir, edits)` + a `live(candidate_dir)`
  context manager. `apply()` is retained as a back-compat hook. A per-trial `seed` is
  threaded into `run_target`, so pass^k measures real variance.
- **Honest-eval upgrades:** the **paired** significance gate is the default (the engine
  auto-selects it because candidate & current share the val tasks); test seal is now
  **seal-on-success** (a finalize crash no longer burns the headline); infra-vs-capability
  failures use a structured `Rollout.error` signal instead of substring-matching feedback.

### Fixed
- **Benchmark CI robustness (skillberry-1 self-hosted runner).** Three fixes so a broken
  runner or gateway is *loud*, not a silent all-0.000 "success": (1) `ci_setup.sh` now
  installs + hard-verifies the `claude-code` optimizer CLI — when it was missing the
  optimizer failed every iteration (`cli_present:false`) and every task reported
  `best=seed`/0.000; (2) `ci_setup.sh` adds a **model-gateway budget preflight** — one
  tiny gpt-oss call that aborts with a clear error on `429 budget_exceeded` (the shared
  LiteLLM gateway hitting its spend cap 429s both the agent and the optimizer, killing
  every rollout with `INFRASTRUCTURE_ERROR`); (3) `run_suite.sh` iterates the task list on
  FD 3 (+ `run_task </dev/null`) so the optimizer subprocess reading stdin can no longer
  DRAIN the here-string and cut the suite off after one task. `metrics.py` now detects an
  infra-dominated eval (majority trials errored + reward≈0) and renders it as
  `⚠️ infra-error`, excluding it from the suite mean/flip counts so a gateway outage no
  longer looks like a capability regression.
- Scaffolded project adapter template (`templates/project/adapters/adapter.py`) matched
  the real `CapabilityAdapter` contract: abstract `tasks` / `run_target(task, ctx, *, seed)`
  / `score`, with `materialize`/`live`/`apply`/`run_batch` documented as optional
  overrides. The old stub used a stale `run_target(task, candidate_dir, split)` signature
  and presented `apply` as a 4th abstract method, which a filled-in body could make the
  stub-probe silently pass.
- Skill names are hyphenated to comply with the Agent Skills `[a-z0-9-]` rule.
