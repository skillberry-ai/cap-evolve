
####################################################################################################
### EVO repository
ADOPT:
  ▸ Replace CapEvolve's hardcoded if/elif strategy chain in loop.select_parent with a registry-of-pickers exactly like frontier_strategies.py.
     how: Create core/cap_evolve/selection.py (or strategies.py) with STRATEGIES: dict[name->{label, description, params:[{name,type,min,max,default}]}] as the
          single source of truth, PICKERS: dict[name->callable(candidates, params, rng)->ranked], a validate_strategy(obj)->{kind,params} that
          casts/range-checks, and a pick(candidates, strategy, seed)->(ranked, seed_used) that logs the seed into the run dir. Port the existing
          best/top_k/epsilon_greedy/pareto bodies into pickers unchanged. The optimizer-algorithm skills then read `cap-evolve frontier --strategy
          ...` instead of hardcoding selection.
  ▸ Introduce a typed Backend/Workspace protocol + name->constructor registry so 'where a candidate is built and evaluated' is pluggable (local dir, git
     worktree, remote sandbox), separate from the adapter.
     how: Define core/cap_evolve/backends/protocol.py with a Backend Protocol (allocate_candidate_dir(ctx)->result, discard, reset) and dataclass contexts, a
          backends/__init__.py with _construct_backend(name, cfg) + load_backend(precedence cascade), and start with a LocalDirBackend that codifies
          today's behavior. Persist the chosen backend+config on each candidate record (like evo nodes persist `backend`). This makes 'optimize a
          Claude Code skill in a worktree' vs 'optimize a remote agent in a sandbox' a config choice, not a fork.
  ▸ Adopt a persisted candidate GRAPH (tree of nodes) with status lifecycle + advisory-locked atomic mutation, replacing flat per-run candidate lists.
     how: Add core/cap_evolve/graph.py: a JSON graph {root, next_id, nodes} mirroring evo's node shape (id, parent, children, status, val/test scores,
          gate_result, candidate_dir, created_at), an update_node(run_dir, id, mutator) that locks+atomic-writes, allocate_candidate(parent_id,
          hypothesis) that does id-gen+parent-linking then delegates dir creation to the backend, and frontier(graph) = gated leaves with no live
          child. Wire loop.select_parent to read frontier(graph) instead of an ad-hoc list.
  ▸ Make gates a per-node, tree-inherited, named, pre/post-phased construct collected root->leaf — not a single global regression gate.
     how: Generalize gate.py to store gates on graph nodes as {name, command|callable, phase}; add collect_gates_from_path(graph, node_id) that walks ancestors
          deduping by name; run pre-gates before run_target/score and post-gates after, discarding any candidate that fails even if its val score
          beats parent. Keep the existing held-out regression gate as the auto-attached root gate (evo's discover does exactly this).
  ▸ Split the orchestration loop (a SKILL) from the deterministic engine (Python CLI verbs), and surface shared state through a single 'scratchpad'
     command.
     how: Ensure every loop-policy decision is in a SKILL.md driving CLI verbs, not in loop.py. Add a `cap-evolve scratchpad` that emits a bounded JSON/text
          summary (tree, ranked frontier, candidates awaiting decision, effective gates per frontier node, recent failures, 'what not to try' from
          discards). Have the optimizer skill spawn read-only scan subagents to aggregate per-candidate outcome.json into cross-cutting failure
          patterns before writing the next round's briefs — the structured-brief-per-subagent pattern is what prevents parallel duplication.
  ▸ Persist a per-attempt, phased, resumable run record with a strict result.json contract and a logged seed — not just an in-memory SplitResult.
     how: Write attempt_state.json per evaluation with the phase you're in; read scores strictly from a published result.json (raise on empty/malformed rather
          than silently scoring 0); stamp the driver PID and refuse a second concurrent evaluation of the same candidate unless forced; on crash,
          salvage partial per-task scores from whatever traces landed. Log the strategy RNG seed into the run record for replay.
 METRICS/OBS:
   - EVO ships a dashboard (dashboard.py, ~1200 lines) with tabs for Frontier strategy (live-pickable, param-driven from the strategy registry), Backend
     selection, and experiment tree visualization; the param schema in FRONTIER_STRATEGIES auto-generates the strategy picker UI. Lesson for
     CapEvolve: if strategy params are declared as data with type/min/max/default, the same declaration drives validation AND any dashboard/CLI picker
     for free.
   - infra_log.json records strategy events (frontier selections with seed, epoch bumps, harness changes) as an append-only audit trail via
     append_frontier_log / append_infra_event — a lightweight observability pattern: every non-deterministic or state-changing decision logs a
     timestamped event with enough to replay (e.g. the RNG seed). CapEvolve should log each parent-selection with strategy+seed+returned ids.
   - Per-attempt outcome.json with structured gates[] {name,passed,phase}, benchmark.result.tasks (per-task scores), and error fields is what makes EVO's
     cross-cutting failure-pattern aggregation possible (scan subagents intersect gate_failures and zero-score task IDs across candidates). CapEvolve
     already has per_task in SplitResult; persist it per-candidate in a stable outcome.json so cross-candidate aggregation (co-occurring failures,
     shared failing tasks) is a simple batch read.
 AGENT_FEATURES:
   - Per-host parallel-subagent dispatch is abstracted in optimize/SKILL.md into three shapes (background+notify for claude-code/codex; batch-parallel for
     opencode/pi; extension-provided) — if CapEvolve targets multiple hosts, encode the same per-host spawn-shape table so the loop skill is portable.
     For Claude Code specifically, EVO uses Bash(run_in_background=true) per brief so completion notifications arrive turn-by-turn and the
     orchestrator reviews each result before the next round.
   - EVO offers an optional deterministic Workflow-tool driver (skills/optimize/workflows/evo-optimize.js) on Claude Code that self-drives the round loop
     instead of relying on turn-by-turn stop-nudges; consider a per-step slash-command or workflow that runs orient->scan->brief->fan-
     out->collect->select so the loop survives context compaction.
   - `evo direct` injects user-authoritative mid-run directives wrapped in an authenticity banner that the orchestrator must `evo ack`; useful if CapEvolve
     wants to steer a long autonomous run without restarting it.
   - `evo wait --for process=/log-growth=/gpu-idle/experiments/ideators` is a bounded structured replacement for `while true; sleep` polling — worth having
     as a CapEvolve verb so subagents waiting on long agent rollouts don't block indefinitely on a crashed process.
 PITFALLS:
   ! Do not copy EVO's git-worktree-and-commit machinery wholesale: EVO optimizes CODE in a git repo, so its candidate = a branch + commit. CapEvolve
     optimizes agent CAPABILITIES (skills/prompts/tool configs) where a candidate is a directory of components, not necessarily a git commit. Adopt
     the Backend PROTOCOL and graph model, but let the default backend be a plain candidate-dir snapshot; don't force every user into git worktrees +
     refs/evo-anchor.
   ! EVO's cli.py is 6900 lines and _cmd_run_impl alone is ~600 lines handling local+pool+remote+resume inline. The protocol/registry seams are clean but
     the run loop itself is monolithic and hard to follow. When adopting the phased run, keep the phases as small composable functions from the start
     rather than one giant function with `if remote:` branches everywhere.
   ! The registry-as-single-source-of-truth pattern only pays off if EVERYTHING reads it (validator, UI, picker). If CapEvolve adds a strategy registry but
     the skills still hardcode strategy names in prose, you get drift. Make the skill query `cap-evolve frontier --list-strategies` (engine-emitted)
     rather than restating the list.
   ! EVO leans heavily on the agent doing the right thing via long prose SKILL.md instructions (mandatory scan subagents, diversity checks, ack
     discipline). These are nudges, not enforced invariants — e.g. subagents-only mode is explicitly 'a nudge, not a hard block' on an alternating
     cadence. Don't assume prose rules are guarantees; anything that must hold (honesty, gating, no-cheat) belongs in the Python engine where it can't
     be skipped, exactly as EVO keeps scoring/gating/splits out of the adapter.
   ! Lazy-import optional providers and catch ImportError with an actionable message (EVO does this well). If CapEvolve pulls every optional integration as
     a hard dependency, install becomes heavy and brittle; mirror the `[extra]` + friendly RemoteBackendUnavailable pattern.
   ! EVO's eval-epoch mechanism (bumping current_eval_epoch to invalidate the whole tree when the benchmark itself was wrong) is subtle but important:
     without it, fixing a scoring bug silently makes old and new scores incomparable. If CapEvolve lets users change the benchmark/scorer mid-run, add
     an epoch/version tag on candidates so frontier and best-score only compare within an epoch.

####################################################################################################
### EVO repository
ADOPT:
  ▸ Materialize a graph/DAG view from the event log, not just a flat timeline.
     how: Add a reducer that folds the jsonl event log into a nodes[] structure (id, parent, children, status, score, iteration, hypothesis, diff_ref, per-task
          scores) and emit that as the dashboard's data model. Even staying static-HTML, render a parent->child indented/tree layout and a cumulative-
          best step line over iterations.
  ▸ Cumulative-best 'stair' line over the score scatter.
     how: Compute running-best over accepted iterations and draw a step polyline (SVG) on top of the per-iteration score dots; mark the champion with a star +
          value label and earlier record-holders with a ring. report.py shows how to do this in both SVG and ANSI.
  ▸ Per-node drawer with Summary / Diff / Tasks / Logs tabs.
     how: For each iteration node, render (a) hypothesis + score-delta vs parent, (b) the prompt/skill diff syntax-highlighted, (c) a per-task pass/fail grid
          linking to that task's trace/transcript, (d) the raw run log. CapEvolve already has the jsonl events; add per-iteration diff + per-task
          outcome artifacts to feed these tabs.
  ▸ Per-task pass/fail heatmap/grid sorted worst-first, with drill-down.
     how: Emit per-task score in each iteration's event/outcome file. Render a tasks×iterations heatmap (green/red cells) so the user sees which tasks each
          candidate fixed or broke; clicking a cell opens that task's transcript.
  ▸ Self-rearming client poll + view-signature diffing instead of full rebuilds.
     how: If CapEvolve adds any live mode, copy the pattern: poll the jsonl (or a derived stats endpoint) on an interval, hash a compact signature of the
          visible state, and only re-render the DOM when it changes.
  ▸ Host-aware terminal report alongside the HTML.
     how: Add an `evo report`-style command that prints a colored ANSI cumulative-best chart + stat strip + top-N table sized to /dev/tty, with the same
          CLAUDECODE margin trick, so progress shows in-chat without opening the browser.
  ▸ Live log tailing via incremental byte-offset reads.
     how: Expose the current iteration's run log with ?offset= support and a size header; the dashboard tails it on a 2s interval while an iteration is active.
  ▸ Server-side secret redaction before anything reaches the UI/JSON.
     how: Run a recursive redactor over any config/env CapEvolve surfaces in the dashboard or report so a shared dashboard.html never leaks credentials.
  ▸ Watchdog supervisor with rotated logs and give-up sentinel (only if CapEvolve gets a live server).
     how: Only relevant if CapEvolve moves beyond static HTML to a served dashboard; reuse the backoff + sentinel + single-instance-lock pattern.
 METRICS/OBS:
   - Cumulative-best 'stair' step line over a per-iteration score scatter (running best vs iteration index), with champion star + value label and record-
     holder rings — both as SVG in HTML and as an ANSI terminal chart.
   - Stat strip / KPI cards: best score, baseline score, %-improvement-vs-baseline delta, total experiments, counts by status (accepted/kept,
     rejected/discarded, failed/error, active, pending, pruned), frontier (open-branch) count, current eval epoch/round.
   - Lineage/genealogy tree of candidates: parent->child DAG with depth lanes, a highlighted best-lineage spine, branch collapse/expand, and three view
     modes (all / best-lineage / frontier-only). Reduce CapEvolve's jsonl into this graph.
   - Per-task pass/fail grid for the selected iteration (sorted worst-first, pass/total header, per-task duration) AND a cross-iteration tasks×iterations
     heatmap (green/red cells) to expose regressions, persistent failures, and per-task specialists that the mean accuracy hides.
   - Per-iteration code/prompt/skill DIFF view, syntax-highlighted, split + unified toggle — so the user sees exactly what changed between a candidate and
     its parent.
   - Per-task trace/transcript drill-down: target vs model_output, failure_reason, and the full event transcript (user/assistant/tool turns), opened by
     clicking a task cell.
   - Latest run-check summary per node: status (passed/failed), score, trace_count, has_benchmark_log, artifact path, error message on failure.
   - Live log tailing for the active iteration via incremental byte-offset reads (?offset= + X-Log-Size header) with a 2s autorefresh and a manual refresh
     control.
   - Training/agent-metric sparklines per iteration (loss, lr, reward, kl, grad_norm or for CapEvolve: per-iteration accuracy, cost, tokens, latency) as
     tiny inline-SVG polylines with last-value labels; pulled optionally and degrading to a link if unavailable.
   - Frontier panel: strategy-ranked list of candidate branch points (id, score, epoch, hypothesis) with a selectable/configurable frontier strategy
     (greedy / epsilon-greedy / softmax / pareto-per-task), seeded for reproducible display.
   - Cost / token / latency accounting per iteration and cumulative (EVO surfaces duration per task and run-check timing; CapEvolve should add explicit
     $-cost, prompt/completion tokens, and wall-clock latency columns + a cumulative-cost-vs-best-score frontier plot, since these are first-class for
     an LLM-capability optimizer).
   - Multi-run switcher + per-run charts so several optimization runs in one workspace can be compared (run-select dropdown, active-run pointer, stacked
     terminal charts).
   - Diagnoses/annotations stream: free-text findings (per-run global and per-task) written by reviewer/verifier/ideator steps, shown inline next to the
     score and the failing task — turning the dashboard into a record of WHY each change was tried and whether it worked.
   - Hover tooltips on every dot/bar showing id, status, score, and delta-from-parent; click-through from any chart element to the corresponding node
     drawer (tight cross-linking between scatter, timeline, and detail panel).
   - View-signature-gated 5s polling so the dashboard is near-live without flicker or losing scroll/zoom/selection state.
 AGENT_FEATURES:
   - evo-report style slash command / per-step hook that prints a colored ANSI cumulative-best chart + KPI strip + top-N table directly into the Claude
     Code / Codex tool-output stream (CLAUDECODE=1 margin-aware), so optimizer progress is visible in-chat without opening a browser.
   - Dashboard auto-start on the discover/optimize step that prints the live URL in chat (EVO prints 'Dashboard live: http://127.0.0.1:8080 (pid …)' and
     auto-increments the port if taken) — CapEvolve could emit the dashboard.html path (or served URL) the same way at run start.
   - Dashboard write-back controls wired to agent directives: prune / spawn / retry / 'direct' a steering note to the running optimizer, so the human can
     redirect the search from the UI mid-run (queued as events the orchestrator skill reads).
 PITFALLS:
   ! Don't over-build a Flask server + supervisor if CapEvolve's value is a portable static artifact. EVO needs the live server because experiments run for
     a long time and the user steers them mid-run (prune/spawn/direct). If CapEvolve runs are short/batch, a richer self-contained static HTML (graph
     reduced from jsonl, embedded JS, no server) captures most of the value without the supervisor/lifecycle complexity.
   ! No persistence layer is a feature, not a gap: EVO deliberately has no sqlite — re-reading graph.json each request keeps it simple and crash-safe.
     Resist adding a DB to CapEvolve; the jsonl event log + a derived in-memory/JSON graph is sufficient and more inspectable.
   ! Score-only dashboards hide the real signal. EVO's lesson is that the aggregate score scatter is the LEAST useful tab — the diff, per-task pass/fail,
     and trace transcripts are where users actually debug. A minimal dashboard that shows only per-iteration scores leaves the 'why' invisible.
   ! Polling re-renders must be guarded by a signature/diff or the UI flickers and loses scroll/zoom/selection state on every tick. EVO explicitly skips
     canvas re-render on tab switches and persists scroll/zoom to avoid resetting the user's view.
   ! ANSI charts wrap badly inside host tool-output frames; if CapEvolve prints progress in-chat, it must reserve right-margin (EVO checks CLAUDECODE=1 and
     subtracts ~6 cols) or the chart breaks.
   ! Optional integrations (Trackio sparklines, HF parquet) must degrade silently — EVO wraps the whole metric-pull in try/except and falls back to a bare
     link if deps/data are missing, so a missing optional dependency never breaks the panel.

####################################################################################################
### obra/superpowers
ADOPT:
  ▸ Make every pipeline step (intake, baseline, evaluate, diagnose, gate, finalize, report, each algorithm) its own skill directory with a SKILL.md whose
     description states ONLY when to run it, and a single-exit handoff naming the next step.
     how: Author skills/intake/SKILL.md ... skills/report/SKILL.md, each with frontmatter description 'Use when <entry condition>'. End each skill body with an
          explicit 'Next: invoke capevolve:<next-step>' marker and a rule forbidding other transitions, so chaining is deterministic. Algorithms
          (GEPA, etc.) become sibling skills the evaluate/diagnose steps name conditionally.
  ▸ Back each step with a tiny CLI script + an on-disk ledger so a step is both standalone-runnable and resumable, and never re-run if already done.
     how: Give each step a script (e.g. bin/capevolve-baseline RUN_DIR, bin/capevolve-evaluate RUN_DIR ITER) that reads/writes a run directory and appends a
          line to a per-run ledger (run_dir/progress.jsonl) recording step, iteration, commit/artifact hash, and metrics. The orchestrator skips steps
          already recorded; a human can invoke any single script directly with the same run_dir.
  ▸ Pass each step PRECISELY constructed context via files (brief in, report out), not conversation history.
     how: Each step reads a small typed input file (config + prior-step interface/metrics) and writes a typed output/report file under run_dir/iter-N/. The
          diagnose step consumes evaluate's report file, not the eval transcript; the report file is the durable evidence record.
  ▸ Put a hard verification gate before finalize/gate steps using the 5-step evidence function.
     how: Make the gate step REQUIRE a freshly-run baseline-vs-candidate eval command, read its exit code and full metric output, and only then emit
          accept/reject. Treat hedging or reuse of a prior iteration's numbers as an automatic abort. Record the proving command and its output in the
          ledger.
  ▸ Structure the diagnose step as the 4-phase root-cause loop with a '3 failures -> question the architecture' escape hatch.
     how: diagnose reads the eval failure report, forms ONE hypothesis about why the candidate regressed/plateaued, proposes the smallest change, and tracks a
          failure counter in the ledger; after 3 non-improving iterations it escalates to switching algorithm or re-scoping rather than another local
          edit.
  ▸ Use an always-on session-start injection of a 'using-capevolve' meta-skill so steps auto-trigger without the user typing slash commands.
     how: Ship a using-capevolve meta-skill (the entry/router) and a Claude Code session-start hook that injects it as hookSpecificOutput.additionalContext. The
          meta-skill routes 'optimize <X>' to intake and documents the step chain; individual steps stay invocable as slash commands for
          manual/standalone use.
  ▸ Adopt the writing-plans 'interface contract' pattern between steps — each step declares what it consumes and produces with exact names/types.
     how: Define a small schema per step (inputs it reads from run_dir, outputs it writes) and document it at the top of each SKILL.md. The orchestrator
          validates the produced artifact against the next step's expected input schema before handoff.
 METRICS/OBS:
   - Per-task report files (task-N-report.md) capturing the command run, results, and concerns — adapt as per-iteration report files so a CapEvolve
     dashboard can read durable evidence per step rather than scraping logs.
   - On-disk ledger (progress.md with commit ranges) as the single source of truth for run progress — a natural backing store for an accuracy/iteration
     chart: each ledger line = one point (iteration, metric, accept/reject, proving-command).
   - Claim-typed evidence table (claim -> required evidence) — surface in the report/gate UI so each accept decision shows the exact metric output and exit
     code that justified it.
 AGENT_FEATURES:
   - Claude Code session-start hook injecting context via hookSpecificOutput.additionalContext (platform-aware JSON shape) — use to force-load a 'using-
     capevolve' router skill at session start so the pipeline is automatic without the user invoking anything.
   - Skills are invoked through the Claude Code `Skill` tool (never read with file tools), enabling each pipeline step to ALSO be exposed as a standalone
     slash command while the same SKILL.md drives the automatic chain.
   - Per-step CLI scripts shipped inside the skill directory (like task-brief/review-package) that the agent runs via Bash — gives true standalone
     execution and lets a human run any single step from the terminal with the same run_dir contract.
   - Repo-scoped state via `git rev-parse --git-path sdd` for concurrency-safe per-run ledgers/briefs — useful if CapEvolve runs multiple optimization
     sessions in one repo.
   - Multi-harness packaging via per-agent plugin dirs (.claude-plugin with plugin.json + marketplace.json, plus .codex-plugin, .cursor-plugin, hooks-
     codex.json etc.) — pattern to follow if CapEvolve must run under codex/gemini/bob as well as Claude Code.
 PITFALLS:
   ! Description-as-workflow: writing a skill description that summarizes what the skill does instead of ONLY when to trigger it. This breaks the scan-to-
     load gate and the agent either over-loads or fails to trigger. Descriptions must start 'Use when...' and list symptoms.
   ! Using @-file references or eagerly loading supporting files — force-loads everything and burns the context budget the progressive-disclosure design
     exists to protect. Reference other steps by name with an explicit REQUIRED-BACKGROUND marker instead.
   ! Passing session history / pasted transcripts into a step instead of a precisely constructed brief — the #1 context-bloat failure; defeats the
     standalone property and makes long optimizer runs blow context.
   ! Multi-exit handoffs / letting a step jump to several possible successors — superpowers enforces single-exit gated transitions; ambiguous transitions
     make the pipeline non-deterministic and hard to resume.
   ! Claiming success from stale or agent-reported numbers — 'prior runs, agent-reported success, or linter passage cannot substitute for fresh complete
     verification output.' For an optimizer this means accepting a candidate on cached metrics.
   ! Re-dispatching already-completed steps after a context compaction because completion lived only in conversation memory — the ledger must be on disk
     and consulted before every step.
   ! Stacking fixes during diagnose (multiple speculative changes at once) — violates 'smallest possible change, one hypothesis' and makes it impossible to
     attribute which change helped; also skips the 3-failure architecture-questioning escape.
   ! Skipping the baseline/RED step — superpowers' iron law is 'no skill without a failing baseline test first'; an optimizer that doesn't establish a real
     baseline can't prove improvement.
   ! Oversized SKILL.md bodies — exceeding the <500-word budget defeats the at-a-glance scannability; push detail into separate on-demand files.

####################################################################################################
### Anthropic Agent Skills authoring best-practices
ADOPT:
  ▸ Rewrite every CapEvolve skill's description to the 'what + when, third person, trigger-rich' pattern and validate against the hard frontmatter limits.
     how: For each CapEvolve skill, write: '<concrete capabilities>. Use when <explicit triggers: user phrases, phase names, file/artifact types>.' e.g.
          'Profiles an agent's failing traces and proposes targeted prompt edits. Use when the user wants to diagnose why an agent is failing
          tau2/skills-bench tasks, cluster failure modes, or generate candidate prompt mutations.' Run a quick validator (port quick_validate.py from
          skill-creator) asserting name<=64 lowercase/hyphen, no 'claude'/'anthropic', description non-empty<=1024, no XML. Rename any skill
          containing reserved words.
  ▸ Restructure each oversized SKILL.md into a thin <500-line table-of-contents body plus references/ split by phase or domain, linked exactly one level
     deep.
     how: Move long optimizer rubrics, prompt-mutation templates, GEPA/SkillOpt scoring schemas, and example traces out of SKILL.md into references/ (e.g.
          references/scoring-rubric.md, references/mutation-operators.md, references/eval-schema.md), each starting with a Contents block if >100
          lines. SKILL.md keeps only: purpose, quick start, the numbered workflow, and 'See references/X.md for …' pointers — all linked directly from
          SKILL.md, never reference→reference.
  ▸ Express the optimizer as an explicit numbered multi-phase workflow with a copyable progress checklist and per-phase 'load reference/run script'
     instructions, mirroring mcp-builder's Phase 1–4 layout.
     how: Author SKILL.md bodies as 'Phase 1: Capture intent / baseline … (load references/baseline.md), Phase 2: Diagnose failures (run
          scripts/cluster_failures.py) …' with a copyable checklist block at the top of the workflow. Gate later phases on earlier outputs ('do not
          propose mutations before the baseline score is recorded').
  ▸ Add a 'Capture Intent / discover' opening phase to the top-level CapEvolve optimizer skill that mines existing artifacts before interrogating the
     user.
     how: Add a Phase 0 to the orchestrator skill: read the target agent's prompt, prior run folders (jobs/agent-*/), tau2 trace outputs and .env config FIRST;
          summarize what's known; then ask only the unresolved questions (what to optimize for, success metric, budget, whether to set up held-out
          evals). Capture answers into a structured intent.json the later phases consume.
  ▸ Make CapEvolve evaluation-driven: ship an evals/ dir with 3+ scenarios and always run a no-optimization baseline before proposing changes.
     how: Standardize evals/evals.json ({skills, query, files, expected_behavior[]}) per CapEvolve skill, and have the optimizer ALWAYS record a baseline metric
          (e.g. tau2 pass rate with the unmodified prompt) before generating mutations, then report delta vs baseline. Reuse skill-creator's
          run_eval.py / aggregate_benchmark.py as the harness.
  ▸ Embed plan-validate-execute feedback loops with verifiable intermediate artifacts wherever CapEvolve mutates prompts/skills or runs batch evals.
     how: Before applying mutations, write a structured plan (e.g. mutations.json listing each candidate edit + rationale + target metric), run a
          scripts/validate_mutations.py that checks well-formedness and that originals are snapshotted, and only apply when it passes. Make the
          validator emit specific errors ('mutation 3 targets section X which no longer exists').
  ▸ Convert ad-hoc generated helper code into bundled, documented scripts in scripts/, with explicit execute-vs-read intent and no magic constants.
     how: Promote recurring CapEvolve helpers (trace clustering, score aggregation, baseline runner, packager) into scripts/ with --help and self-documenting
          constants (comment why a temperature, sample count, or retry limit is what it is). In SKILL.md say 'Run scripts/aggregate_scores.py'
          (execute) vs 'See scripts/mutate.py for the operator set' (reference) explicitly.
  ▸ Adopt a single repo-wide skill quality rubric/checklist (R1–R14 above) and run it as a review gate when authoring or editing any CapEvolve skill.
     how: Store the rubric as references/skill-quality-rubric.md in a meta 'authoring-skills' skill (or reuse superpowers:writing-skills) and add a /skill-lint
          style check (port quick_validate.py + the checklist) that must pass before a CapEvolve skill is committed. Apply gerund naming consistently
          across the collection (optimizing-agents, diagnosing-failures, evaluating-variants).
 METRICS/OBS:
   - with-skill vs baseline delta as the core metric (pass rate / win rate) reported per iteration — skill-creator spawns both in the same turn and
     aggregates via aggregate_benchmark.py; CapEvolve should always report improvement-over-baseline, never raw scores alone.
   - Variance analysis across repeated runs (the skill-creator description mentions 'benchmark skill performance with variance analysis') — run each
     variant N times and report mean ± spread so noise isn't mistaken for improvement.
   - HTML eval/iteration viewer (eval-viewer/, generate_report.py) showing per-eval expected_behavior pass/fail and per-iteration trend — reuse CapEvolve's
     accuracy-chart skill to visualize variant scores across hypothesis iterations.
   - Per-iteration directories (iteration-1/, iteration-2/) and a skill-snapshot/ baseline for diff — gives an auditable trail of what each mutation
     changed and its measured effect.
   - Description-triggering accuracy as its own tracked metric (improve_description.py optimizes for it) — CapEvolve can measure how often each skill
     correctly fires on a labelled set of trigger/non-trigger prompts.
 AGENT_FEATURES:
   - Claude Code supports subagents — skill-creator runs with-skill and baseline evaluations in parallel subagents in the same turn; CapEvolve's optimizer
     can fan out variant evaluations (one subagent per candidate mutation) via the parallel-agents pattern.
   - Per-step slash commands map cleanly onto the multi-phase workflow: expose /capevolve-baseline, /capevolve-diagnose, /capevolve-mutate, /capevolve-
     eval, /capevolve-package as thin commands that each invoke the corresponding skill phase, so users can drive the optimizer step-by-step or let
     the orchestrator chain them.
   - Claude Code reads skill files via bash on demand and executes scripts without loading source — lean on this for CapEvolve's heavy reference docs and
     helper scripts (zero context cost until used).
   - An eval-viewer (skill-creator ships generate_report.py / eval-viewer/) produces an HTML review surface; CapEvolve can reuse the existing accuracy-
     chart skill to render per-iteration variant scores. Generate the viewer BEFORE self-grading so human review comes first.
   - skill-creator's improve_description.py is a packaged 'description optimizer' run as the final step — CapEvolve should expose the same as a terminal
     phase that tunes each skill's trigger description after the body is finalized.
   - Environment-adaptive behavior (Claude Code vs claude.ai vs Cowork) is encoded in skill-creator; CapEvolve skills should branch similarly (e.g.
     subagents/baseline only when available).
 PITFALLS:
   ! Vague or first-person descriptions ('Helps optimize things', 'I can help you...') — the top cause of skills never triggering; descriptions must be
     third person and trigger-rich.
   ! Reserved words 'claude'/'anthropic' or >64-char/non-lowercase names in the frontmatter name field — silently breaks skill loading. CapEvolve must scan
     for this since the repo theme is Claude tooling.
   ! Stuffing rubrics, schemas, long prompt templates, and example traces inline in SKILL.md — blows past the <500-line target and pays the token cost on
     every load. Push to references/.
   ! Nested references (SKILL.md → a.md → b.md) — Claude only partially reads downstream files (head -100) and misses content; keep all references one
     level deep and add a Contents block to any file >100 lines.
   ! Reference/example files >100 lines with no table of contents — partial reads hide their scope.
   ! ALL-CAPS MUST/NEVER walls instead of explaining the 'why' — a documented 'yellow flag'; over-constrains and reads as low quality. Reserve strict
     imperative templates for genuinely fragile steps.
   ! Listing many tool/approach options ('use pypdf or pdfplumber or PyMuPDF...') — confuses the model; give one default plus a single escape hatch.
   ! Magic constants / 'voodoo' numbers in bundled scripts (TIMEOUT=47) and scripts that punt errors back to Claude instead of handling them — undermines
     determinism, the whole point of bundling scripts.
   ! Skipping the baseline / writing docs before evals — you end up optimizing for imagined problems; without a baseline you can't prove the optimizer
     actually improved anything.
   ! Time-sensitive instructions ('before August 2025 use the old API') baked into the body — use a collapsible 'Old patterns' section instead.
   ! Inconsistent terminology and Windows-style backslash paths — both degrade Claude's ability to follow the skill and break on Unix.
   ! Unqualified MCP tool names — use Server:tool form (e.g. for the RITS/Bob/tau2 tooling CapEvolve drives) or Claude may fail to locate the tool.

####################################################################################################
### GEPA paper
ADOPT:
  ▸ Two-stage minibatch-gate-then-full-val economy in the gepa loop (concretely: a gepa algorithm skill that does NOT call run_step's always-full-val
     path).
     how: Add a minibatch stage: (a) sample k train ids; (b) evaluate parent on it with traces (CapEvolve already captures rollouts+feedback via
          adapter.run_target/score and writes per-rollout JSON); (c) run the optimizer to produce the child; (d) evaluate child on the SAME minibatch;
          (e) cheap local gate sum(child)>sum(parent); (f) ONLY on pass call the existing evaluate_candidate(split='val') + gate.decide() + frontier
          update. Count rollouts in run_dir.update_spent(metric_calls=...) for BOTH evals. Expose --minibatch-size (default 3-5) and --skip-perfect
          (skip proposing when the parent aces the minibatch).
  ▸ Per-instance Pareto frontier with frequency-weighted parent sampling, replacing whole-vector domination + uniform sampling.
     how: Port gepa_utils.select_program_candidate_from_pareto_front + remove_dominated_programs into core/cap_evolve/loop.py. Build program_at_pareto_front
          from each candidate's per_task rewards: per task id, the set of candidates achieving the max (ties => all); prune dominated; sample by
          front-membership frequency. Keep the existing whole-vector helper as a fallback for tiny task sets. Seed the rng from run config for
          reproducibility.
  ▸ Put the agent's actual output/trajectory (not just feedback) into the reflective dataset, structured per-record like GEPA.
     how: CapEvolve already persists per-rollout JSON {input, rollout.to_dict(), score} under run_dir.rollouts/<split>. Build the reflective dataset from those
          files for the parent's failing tasks: include task input, the agent's final output and/or a compacted trajectory, and the full feedback;
          render per-example markdown like InstructionProposalSignature; instruct the optimizer to find the common root cause + generalizable fix +
          niche facts to bake in. Cap by token budget, not a flat 500 chars. Write it as REFLECTION.md into the optimizer workdir (agents read files
          better than huge prompts).
  ▸ Add a system-aware merge step gated behind accepts, using a real ancestor graph and a component model.
     how: Record a structured parent graph (each accepted candidate -> parent id(s)) in the run dir. After an accept, with GEPA-style merges_due cadence, find
          two frontier dominators sharing a common ancestor that both beat; for a file/section-decomposed capability take each component from
          whichever descendant changed it (or the higher-val descendant when both changed). Evaluate the merged candidate on a minibatch first (>=
          max(parents)), then full val + the standard gate. Bound with --max-merges. For monolithic single-file capabilities, decompose by markdown
          section or skip merge.
  ▸ Switch the gepa loop's budget to rollouts/metric-calls and add a (candidate, example) evaluation cache.
     how: run_dir.update_spent already tracks metric_calls; make the gepa loop primarily budget-driven (--max-metric-calls) with max_iterations secondary. Add a
          content-hash cache keyed by (hash of candidate files, task_id) -> reward/feedback in the run dir, checked in evaluate_candidate before
          running a rollout (mirroring state.EvaluationCache.evaluate_with_cache_full).
  ▸ Introduce a named-component model with round-robin component selection for multi-file capabilities.
     how: Define a capability's components as its editable files (or named markdown sections). Per candidate keep a round-robin pointer to the next component;
          write 'focus your edit on <component>' into FOCUS.md in the optimizer workdir for that iteration (offer --component-selector
          round_robin|all). This also gives merge its crossover unit.
 METRICS/OBS:
   - Track rollouts/metric-calls as the primary budget axis and chart accepted-edits-per-1k-rollouts to demonstrate the sample-efficiency win over the
     hill-climb loops on the same splits.
   - Log per iteration: selected parent id + its frontier frequency, minibatch Δ (gate-1), full-val Δ (gate-2), accept/reject + reason, and whether the
     iteration was a reflective mutation or a merge — mirroring GEPA's run_log.json.
   - Visualize the candidate lineage tree (parents -> children, merges as multi-parent nodes) and per-instance frontier coverage (which candidate owns
     which val task) so it's visible that specialists are retained.
   - Report the gap between best-mean (finalize point) and the frontier's per-task oracle ceiling — a large gap signals merge/ensembling headroom.
 AGENT_FEATURES:
   - Expose the gepa loop's stages as inspectable run-dir artifacts (minibatch eval, the reflective dataset shown to the optimizer, child minibatch eval,
     full val eval, merge attempts) and a per-iteration 'proposals' record (prompt, the optimizer's edit, accept/reject + reason) — GEPA's
     run_log.json + proposals/candidates tables are invaluable for debugging an agent optimizer.
   - A per-iteration slash command could let the operator approve/skip a proposed merge or component focus, since merge crossovers are high-leverage but
     occasionally nonsensical.
   - Because CapEvolve invokes the OPTIMIZER as a subprocess agent (optimizer_from_command writes INSTRUCTIONS.md + MEMORY.md/STATE.md into a workdir),
     write the reflective dataset and the chosen component focus as files (REFLECTION.md, FOCUS.md) in that workdir rather than only inlining them —
     large traces exceed prompt budgets and agents read files well.
 PITFALLS:
   ! Do not make the minibatch the FINAL acceptance — GEPA's minibatch gate is only a cheap PRE-filter; final acceptance/frontier-update is on the full val
     eval. Conflating them lets a child that got lucky on 3 minibatch tasks pollute the frontier. Keep CapEvolve's honest val significance gate as the
     real gate and add the minibatch gate strictly in front of it.
   ! The per-instance frontier needs all candidates scored on the SAME val instances to compare per-task. GEPA enforces val-support overlap
     (val_overlap_floor) before merging and uses an eval cache so coverage is shared. If CapEvolve scores different candidates on different val
     subsets, per-instance domination is ill-defined — score every candidate on the full val split (or track coverage explicitly) before building the
     frontier.
   ! Merge requires a real ancestor graph and component decomposition; doing it on a monolithic blob produces nonsense crossovers. Don't ship merge until
     capabilities have a component/section model and parent lineage is recorded. GEPA's invariant (ancestor score <= both descendants) is load-bearing
     — preserve it.
   ! Reflection quality collapses with binary, explanation-free feedback. GEPA and CapEvolve's own SKILL.md say to fall back to a hill-climb when feedback
     is uninformative. Stacking more machinery (frontier, merge) on a no-signal scorer wastes budget — the adopt items assume the adapter emits rich
     per-task feedback.
   ! Counting budget in iterations rather than rollouts undercounts once minibatch + full + merge evals coexist (one 'iteration' can cost very different
     rollout counts). Adding the minibatch stage while keeping iteration-based budgeting can blow far past the intended rollout budget.
   ! Truncating the reflective dataset (current 500-char/10-task cap) and dropping the trajectory discards exactly the actionable side information that
     distinguishes GEPA from a scalar hill-climb — more iterations won't recover signal never shown to the optimizer.
   ! Uniform parent sampling over the frontier (current behavior) under-explores broad specialists and over-explores narrow ones; without frequency
     weighting the quality-diversity benefit is muted.
   ! Don't let the optimizer subprocess see or score the test split. CapEvolve's seal (run_dir.consume_test) is correct; any new minibatch/merge eval paths
     must draw from train/val only and never touch test, or the held-out guarantee breaks.

####################################################################################################
### SkillOpt
ADOPT:
  ▸ Add a new CapEvolve algorithm skill `skills/algorithms/skillopt/` implementing epoch + mini-batch + textual-learning-rate (edit budget) hill-climb
     with a strict val gate, a within-epoch rejected-edit buffer, and an epoch-boundary slow/meta update — a disciplined single-lineage climber that
     sits between all-at-once (one shot, whole trainset) and gepa-reflective (Pareto frontier).
     how: Create skills/algorithms/skillopt/ mirroring gepa-reflective's layout exactly: SKILL.md (frontmatter: name=skillopt, component=algorithm,
          provides=[candidate], needs=[scores,traces,candidate], sources=[skillopt], argument-hint with --run-dir/--project/--optimizer), meta.yaml
          (entry scripts/run.py, abstract scripts/abstract.py, check scripts/check.py, compatible_with capabilities/optimizers '*'),
          references/concepts.md (cite arXiv:2605.23904, explain the DL analogy), and scripts/{run.py, abstract.py, check.py, _bootstrap.py}.
          abstract.py is a no-op like all-at-once (the loop composes contract methods; the optimizer skill supplies the proposer). run.py is a thin
          wrapper that parses args and calls a NEW core.harness.skillopt_loop. INPUTS to run.py: --run-dir, --project, --optimizer 'CMD {workdir}
          {prompt}', --epochs (default 4), --batch-size (mini-batch of train tasks per accumulation, default = min(8,len(train))), --accumulation
          (default 1), --edit-budget / --lr (max edits per step, default 4), --lr-schedule (constant|linear|cosine, default cosine), --min-edit-budget
          (default 2), --n-trials (default 1), --gate-mode (default significant) / --k-se, --slow-update/--no-slow-update (default on), --no-
          regression, --store. Requires baseline.json first (seed_val) like every sibling.  PER-EPOCH / PER-STEP ALGORITHM in
          core.harness.skillopt_loop (model it on hill_climb_loop, lines 414+): 1. Init memory+store via _init_memory_store. Compute steps_per_epoch =
          ceil(len(train)/(batch_size*accumulation)); total_steps = epochs*steps_per_epoch; build an LR schedule list edit_budget[step] =
          cosine(max=edit_budget, min=min_edit_budget, total=total_steps) — port skillopt/optimizer/scheduler.py (constant/linear/cosine; trivial
          integer fns). 2. For each epoch: shuffle train ids (seeded by epoch); reset a per-epoch step_buffer (list of dicts). Snapshot skill at epoch
          start as prev_epoch_skill. 3. For each step in epoch: take the next mini-batch(es) of train ids (accumulation of them); build focus
          instructions over ONLY those tasks' current per-task val/train feedback (reuse _focus_instructions but pass focus_ids = the minibatch ids)
          AND append the step_buffer block (see _augment_instructions) telling the optimizer the edit budget L=edit_budget[step] ('make at most L
          bounded add/delete/replace edits') plus 'avoid these previously-rejected edits' + 'these failure patterns remain unsolved'. Parent is always
          the current best (single-lineage climb — NOT a Pareto frontier; that is gepa's job). 4. Call harness.run_step(... instructions=that,
          current_val, gate_kwargs, no_regression, rejected, history, store ...) — this already does materialize→optimize→evaluate-on-
          VAL→gate→accept/reject, snapshots+sets best on accept, and writes RejectedMemory/History. Capture decision + cand_val. 5. Append to
          step_buffer: {step, accepted, n_fail (from cand_val.per_task reward<1), failure_patterns (group per-task feedback prefixes with task_ids),
          and IF rejected: the optimizer's proposed diff summary + score_before/after}. (To get the proposed edits, diff parent vs workdir capability
          files, or just record the rejected candidate_id + val delta — start with the latter for v1.) Update current_val only on accept (run_step
          already sets best; read it back like hill_climb_loop does). 6. END OF EPOCH (epoch>=2, if --slow-update): re-evaluate prev_epoch_skill and
          current best on a sampled subset of TRAIN tasks; categorize each task improved/regressed/persistent_fail/stable_success; build a 'slow-
          update' instruction that says 'epoch N vs N-1: these tasks REGRESSED [ids+feedback], these PERSIST as failures [ids] — make targeted edits
          to fix regressions without breaking stable_success tasks', and run ONE extra run_step with that instruction, GATED on val exactly like a
          normal step (paper Section 3.6 gated mode — simplest + safest in CapEvolve; skip force-accept). This is the slow/meta update. 7. After all
          epochs: return the same result dict shape gepa/hill_climb return (best candidate, val reward, accept/reject counts, per-epoch stats); test
          stays sealed for finalize.  HOW IT DIFFERS from siblings (put this verbatim in SKILL.md 'When to use' / 'Selection-focus-acceptance'): vs
          all-at-once — all-at-once reflects on the WHOLE trainset once per iteration with no schedule; skillopt shards train into mini-batches,
          sweeps them in epochs, and DECAYS an explicit edit budget so early steps make big structural edits and late steps make small refinements
          (anneal). vs cyclic/hardest-first — those also climb one lineage but only change WHICH tasks they focus; skillopt adds the LR schedule +
          rejected-edit buffer + epoch slow-update on top. vs gepa-reflective — gepa keeps a per-task PARETO FRONTIER and samples diverse parents
          (quality-diversity, anti-overfit); skillopt is a STRICT SINGLE-LINEAGE hill-climb (parent = current best always) whose stability comes
          instead from the decaying edit budget, the rejected-edit buffer, and the regression-catching epoch slow-update. Use skillopt when you have a
          medium/large train set worth sweeping in epochs and want reproducible, monotone, budget-controlled improvement; use gepa when rollouts are
          scarce and diversity/specialists matter; use all-at-once as the baseline yardstick.
  ▸ Port SkillOpt's edit-budget LR schedule as a tiny reusable core utility (constant/linear/cosine integer schedules over total_steps) and surface --lr /
     --lr-schedule on the skillopt skill.
     how: Add core/cap_evolve/lr_schedule.py with build_schedule(mode, max_lr, min_lr, total_steps) -> list[int] (port scikit-simple cosine/linear/constant from
          skillopt/optimizer/scheduler.py). The skillopt_loop indexes it per global step and passes 'You may make at most L edits this step' into the
          optimizer instructions. Keep it a plain integer cap — the optimizer (Claude/Codex/etc.) is told the budget in NL; no need to mechanically
          enforce, but record requested vs applied edit counts in the step event for observability.
  ▸ Generalize the within-epoch rejected-edit buffer into the optimizer instructions, beyond CapEvolve's existing per-run RejectedMemory.
     how: In skillopt_loop, build a per-epoch step_buffer and format it like trainer._format_step_buffer: '### Step k — REJECT (n_fail/n_total): failure
          patterns [...]; Rejected edits (score x→y): [op] target → content'. Inject via the same _augment_instructions hook run_step already calls.
          v1 can record rejected candidate_id + val Δ + the per-task feedback clusters; v2 can add a real parent-vs-workdir capability-file diff to
          capture the actual add/delete/replace ops.
  ▸ Adopt the epoch-boundary longitudinal slow-update as a regression guard, expressed in CapEvolve's existing val gate.
     how: At each epoch boundary (epoch>=2) sample a subset of train tasks, evaluate prev_epoch_skill vs current best on them via evaluate_candidate, categorize
          per task (improved/regressed/persistent_fail/stable_success — port build_comparison_pairs logic, which is just comparing two per_task reward
          maps), and run one extra gated run_step whose instructions emphasize fixing regressed+persistent tasks while preserving stable_success. Gate
          on val (paper Section 3.6). This reuses 100% of existing harness machinery — no new gate.
 METRICS/OBS:
   - SkillOpt writes a rich per-step history.json (action accept/reject/skip, rollout_hard/soft, edit_budget, n_edits_merged→n_edits_ranked,
     selection_hard/soft, candidate_gate_score, per-stage timing, per-step token deltas by stage) plus a summary.json (baseline vs best, total
     accepts/rejects/skips, per-epoch stats, test delta, total tokens). CapEvolve's run_dir.log_event already records step accept/val/cost/tokens —
     extend the skillopt step event with: epoch, step_in_epoch, edit_budget(L), requested_vs_applied_edits, and slow_update action, so a dashboard can
     plot the edit-budget anneal curve and accept-rate per epoch.
   - Useful chart from the paper (skillopt-assets/epoch-trends): per-epoch best-score and accept/reject counts — directly buildable from CapEvolve history
     + the new epoch field. Also a 'rejected-edit reuse avoided' counter (how often the buffer suppressed a repeat) is a good observability metric for
     the buffer's value.
   - Token/cost accounting separated by optimizer vs target model (SkillOpt tracks optimizer and target backends separately) maps onto CapEvolve's existing
     optimizer_seconds/runner_seconds/cost_usd/tokens in the step event — keep that split so the dashboard shows optimization cost vs evaluation cost
     per epoch.
 AGENT_FEATURES:
   - The --optimizer is already a pluggable command 'CMD {workdir} {prompt}' (claude-code / codex / gemini / bob), so skillopt reuses the existing
     optimizer skills unchanged — the edit budget and rejected-edit buffer are passed purely as NL in {prompt}. Expose a per-step slash-command-
     friendly knob (--edit-budget / --lr-schedule) so a human can dial the textual learning rate the way they'd dial an optimizer LR.
   - Because the rejected-edit buffer and slow-update are just structured text injected into the optimizer prompt, they work identically across Claude Code
     / Codex / Gemini backends — no backend-specific code, matching CapEvolve's existing optimizer-agnostic design (optimizer_from_command).
   - SkillOpt ships agent-specific deployment plugins (plugins/claude-code, plugins/codex, plugins/copilot) for SkillOpt-Sleep that run the same gated-
     bounded-edit engine as a nightly /sleep cycle over a user's real sessions — a model for a future CapEvolve 'continuous/online' mode where the
     optimized capability keeps improving on held-out replayed tasks behind a gate.
 PITFALLS:
   ! Strict-greater gate on a tiny held-out set rejects almost everything: with few selection items, hard exact-match accuracy is coarse and 'cand >
     current' is rarely true, so the skill never moves. SkillOpt mitigates with soft/mixed gate metrics for small sel sets. In CapEvolve, default
     skillopt to the existing 'significant' gate (k_se) and document raising --n-trials or using a soft/graded reward when the val split is small — do
     NOT use a naive strict-greater hard gate on <=10 val tasks.
   ! Force-accept slow-update can regress the best skill: SkillOpt's newer main default injects epoch slow-update guidance into current AND best
     UNCONDITIONALLY, which can degrade a validated best. The paper protocol (Section 3.6) and the provided ckpt/ skills use the GATED variant. For
     CapEvolve, only implement the gated slow-update — never bypass the val gate to mutate best.
   ! The rejected-edit buffer must reset per epoch and stay bounded: an unbounded buffer balloons the optimizer prompt across a long run and re-injects
     stale patterns. Scope it to the current epoch (as SkillOpt does) and cap the number of patterns/rejections shown (it truncates task_ids to 3,
     failures to 10).
   ! Edit-budget annealing only matters with bounded add/delete/replace edits: SkillOpt's LR is meaningful because edits are discrete ops on one document.
     CapEvolve optimizers edit free-form capability files via an LLM agent, so the budget L can only be COMMUNICATED in NL, not mechanically clipped —
     set expectations accordingly and log requested-vs-applied to detect an optimizer that ignores the budget.
   ! Mini-batch focus can overfit the current shard: focusing each step only on its mini-batch's failures (without the epoch slow-update + val gate) lets
     the skill chase one shard and forget others. The slow-update + strict val gate are what keep it honest — don't ship the mini-batch loop without
     them.
   ! Don't conflate selection (val) and test: SkillOpt's gate uses valid_seen and keeps valid_unseen sealed for the final report. CapEvolve already
     enforces val-only gating + sealed test in finalize — preserve that; the skillopt_loop must gate on val and never touch test, matching the rest of
     the family.
   ! Cost: re-rolling prev-epoch vs current skill on a train sample every epoch boundary adds rollouts. Keep the slow-update sample small (SkillOpt default
     ~20 items) and make --slow-update toggleable; account for it in the run budget.

####################################################################################################
### Current docs for coding-agent CLIs
ADOPT:
  ▸ Make every CapEvolve pipeline phase a dual-mode skill: a standalone slash command AND an orchestrator-callable step. Author each phase once as
     skills/phases/<phase>/SKILL.md (it already is) so it is invocable as /cap-evolve:<phase> for manual/debug use, and have the orchestrator invoke
     the SAME skill headlessly. On Claude Code commands-merged-into-skills means this is free; the directory name is the command name.
     how: Add to each skills/phases/<phase>/SKILL.md frontmatter: argument-hint matching its run.py args (e.g. '--run-dir DIR --tag ID'), arguments: [run_dir,
          tag] for $run_dir/$tag substitution, and a body whose 'How to run' block already shells run.py. Keep the existing meta.yaml needs/provides
          tokens as the orchestration contract. Document the /cap-evolve:<phase> invocation in each SKILL.md and in the plugin README.
  ▸ Add a fully-automatic mode that calls each step headless + JSON-schema'd, parsing .structured_output / .result instead of scraping prose. For the
     gate/diagnose/evaluate steps that produce decisions or scores, define a JSON schema and run the step as `claude -p '/cap-evolve:<phase> ...'
     --output-format json --json-schema '<schema>'` (or codex exec --json --output-last-message, gemini -p --output-format json).
     how: Extend core/agent_capo/harness.py (or a new headless runner) to invoke steps with --output-format json and, for decision steps, --json-schema. Add a
          per-optimizer 'json_output' note to each optimizer SKILL.md (Claude: --output-format json/--json-schema; Codex: --json + --output-last-
          message <file>; Gemini: --output-format json). Record total_cost_usd from the JSON into the iteration store for the report dashboard.
  ▸ Run independent steps (and parallel diagnose/evaluate fan-out) as forked subagents. On Claude Code set context: fork + agent: Explore (read-only) on
     the diagnose/baseline skills and a custom agent for propose, so each runs in its own isolated context window and returns only a summary; use the
     same pattern to launch N parallel evaluators.
     how: For read-only analysis phases (diagnose, baseline) add `context: fork` + `agent: Explore` to SKILL.md. Define .claude/agents/capo-proposer.md (or a
          plugin agents/ entry) with a strong model + write tools for the optimizer step. Where the orchestrate skill fans out, document the
          subagent/Task pattern. Provide a generic fallback (sequential) for non-Claude optimizers that lack subagents.
  ▸ Enforce the honesty gates with hooks instead of trusting the model. Ship plugin hooks (hooks/hooks.json) that block on the hard rules: a PreToolUse
     hook denying any Edit/Write that touches the sealed test split or eval gold files; a Stop/SubagentStop hook (exit 2) that refuses to let an
     optimizer 'finish' an iteration until acapo check / the no-regression gate passes; a PostToolUse hook that runs the gate after edits.
     how: Add plugins/agent-capo/hooks/hooks.json: PreToolUse matcher Edit|Write with a script that reads tool_input.file_path from stdin (jq) and exits 2 if it
          matches the test-split/gold globs; Stop hook running core's gate and emitting {decision:block, reason} on failure. Keep these in core-owned
          scripts (not editable skill content) to preserve the 'honesty only in core' invariant.
  ▸ Inject live run-dir data into each step-command via dynamic context injection rather than asking the model to go read files. In the diagnose/propose
     skill bodies use !`...` / ```! blocks and ${CLAUDE_SKILL_DIR} to inline the candidate's scores, the reflective_dataset, the git diff, and
     MEMORY.md/rejected.jsonl before the model sees the prompt.
     how: In skills/phases/diagnose/SKILL.md and the optimizer propose path, add fenced ```! blocks calling the run.py/abstract.py scripts via
          ${CLAUDE_SKILL_DIR}/scripts/... to emit the reflective dataset + clusters + kept_good, plus !`git -C $run_dir diff`. Gemini equivalent: a
          .gemini/commands/capo-diagnose.toml using @{file} and !{shell}. Codex: precompute into INSTRUCTIONS.md (no inline injection in exec).
  ▸ Package the whole pipeline as one namespaced Claude Code plugin published via a marketplace, and provide standalone-config fallbacks for non-plugin
     use. Bundle all phase + optimizer skills under skills/, the honesty hooks under hooks/, any scorer/proposer subagents under agents/, and an
     .mcp.json for eval-harness MCP servers, all under the existing plugin.json (name cap-evolve).
     how: Confirm plugins/agent-capo/.claude-plugin/plugin.json points skills at the full phase+optimizer tree; add hooks/hooks.json, agents/, and optional
          .mcp.json under the plugin root (NOT inside .claude-plugin/). Verify the top-level .claude-plugin/marketplace.json lists it. Document
          `claude --plugin-dir ./plugins/agent-capo` for dev and `--plugin-url <zip>` for CI; for other agents, document copying skills into
          .claude/skills (Claude), .gemini/commands TOML (Gemini), AGENTS.md (Codex).
  ▸ Use --bare + explicit context flags for reproducible CI runs of the loop, and assert the plugin loaded. Run automated CapEvolve in claude --bare -p
     mode (skips ambient hooks/skills/MCP/CLAUDE.md), passing exactly what the run needs via --plugin-dir/--plugin-url, --mcp-config, --settings,
     --append-system-prompt-file, and check the system/init stream event's plugins/plugin_errors.
     how: Add a CI entrypoint that invokes the loop with claude --bare and the explicit --plugin-dir/--mcp-config flags, sets ANTHROPIC_API_KEY (bare skips
          OAuth/keychain), and parses the first stream-json system/init event to assert cap-evolve is in .plugins and .plugin_errors is empty before
          proceeding. Note in the claude-code optimizer SKILL.md that --bare will become the -p default.
 METRICS/OBS:
   - claude -p --output-format json returns total_cost_usd plus a per-model cost breakdown per invocation — feed this straight into the existing report
     dashboard (skills/phases/report) for exact per-step RUNNER/OPTIMIZER cost without consulting a usage dashboard.
   - stream-json events give live observability: system/init (model, tools, MCP servers, loaded plugins, plugin_errors), system/api_retry (attempt,
     max_retries, retry_delay_ms, error category), and partial-message token deltas — a runner can show per-iteration progress + retry/backoff and
     fail fast on plugin_errors.
   - Codex --json (NDJSON events) + --output-last-message <file> give a machine-readable event stream and a captured final summary per exec run for logging
     cost/turns; Gemini --output-format json gives structured per-run output. Normalize all three into the iteration store so the dashboard can chart
     cost/tokens/time per step across optimizers.
   - Plugin background monitors (monitors/monitors.json: name/command/description, one notification per stdout line) could tail a long eval-harness log and
     surface failures to the orchestrator in-session without polling.
 AGENT_FEATURES:
   - Claude Code — custom slash commands merged into skills: .claude/commands/x.md AND .claude/skills/x/SKILL.md both create /x; directory name = command
     name; plugin skills become /<plugin>:<skill>.
   - Claude Code — skill/command frontmatter: description, when_to_use, argument-hint, arguments (+$ARGUMENTS/$ARGUMENTS[N]/$N/$name), disable-model-
     invocation, user-invocable, allowed-tools, disallowed-tools, model, effort, context:fork, agent:<type>, hooks, paths, shell.
   - Claude Code — dynamic context injection in skill/command bodies: inline !`cmd`, fenced ```! blocks; vars ${CLAUDE_SKILL_DIR}, ${CLAUDE_SESSION_ID},
     ${CLAUDE_EFFORT}; output spliced as text, run once, not re-scanned; disableSkillShellExecution to turn off.
   - Claude Code — headless: claude -p/--print; --bare (skip auto-discovery, force ANTHROPIC_API_KEY; will become -p default); slash commands expand inside
     -p prompt; --continue / --resume <session_id> (scoped to project dir); stdin piped (10MB cap).
   - Claude Code — structured output: --output-format text|json|stream-json; --json-schema '<JSONSchema>' -> .structured_output; json result has
     total_cost_usd + per-model cost; stream-json + --verbose + --include-partial-messages for token deltas; system/init reports plugins +
     plugin_errors; system/api_retry events.
   - Claude Code — permission modes: --permission-mode default|acceptEdits|plan|dontAsk|bypassPermissions (bypassPermissions == --dangerously-skip-
     permissions); --allowedTools/--disallowedTools with rule syntax e.g. Bash(git diff *).
   - Claude Code — subagents: .claude/agents/<name>.md (name, description, tools, model); delegated via Task tool; can preload skills via skills: field;
     built-ins Explore/Plan/general-purpose; skills can run forked via context:fork + agent:.
   - Claude Code — hooks: events PreToolUse, PostToolUse, UserPromptSubmit, Stop, SubagentStop, SessionStart, PreCompact, Notification; configured in
     settings.json or plugin hooks/hooks.json; JSON stdin (tool_name/tool_input/cwd/session_id); exit 2 blocks (stderr -> model); exit-0 JSON:
     permissionDecision allow/deny/ask, decision:block+reason, additionalContext, updatedInput; matchers support regex + mcp__server__.*.
   - Claude Code — plugins: .claude-plugin/plugin.json (name=namespace, version); bundles skills/, agents/, hooks/hooks.json, .mcp.json, .lsp.json,
     monitors/, bin/ (PATH), settings.json (agent key activates a default agent); marketplace.json catalog; install via /plugin; dev via --plugin-dir
     <dir|.zip> (repeatable), --plugin-url <zip>; --agents/--mcp-config/--settings/--append-system-prompt-file; CLAUDE_CODE_SYNC_PLUGIN_INSTALL emits
     plugin_install events; claude plugin init/validate.
   - Claude Code — MCP: configured via .mcp.json (project/plugin) or --mcp-config <file|json>; MCP tools matchable in hooks as mcp__<server>__<tool>;
     servers reported in system/init.
   - Codex CLI — headless: codex exec '<prompt>' (alias codex e), prompt positional or '-' stdin; --sandbox read-only|workspace-write|danger-full-access
     (--full-auto deprecated); -m/--model; --cd <dir>; --json (NDJSON) + --output-last-message <file>; -c key=value overrides (model_reasoning_effort,
     profile=<name>); --skip-git-repo-check; reads AGENTS.md (workdir+parents); profiles; MCP available in exec.
   - Gemini CLI — headless: gemini -p/--prompt (forces non-interactive; also non-TTY); --approval-mode default|auto_edit|yolo (--yolo deprecated);
     -m/--model; --output-format text|json|stream-json; --include-directories; --sandbox/-s; reads GEMINI.md; /memory, /mcp, /extensions.
   - Gemini CLI — custom slash commands: TOML at .gemini/commands/<name>.toml (project) or ~/.gemini/commands/ (user), namespaced by subdirectory; `prompt`
     field with injections {{args}} (user args), !{shell} (shell output), @{file} (file content).
 PITFALLS:
   ! Treating 'step = slash command' as Claude-only. Only Claude Code merges commands into skills with rich frontmatter + context:fork + hooks. Codex has
     thinner custom prompts and no per-command subagent fork; Gemini uses TOML commands with {{args}}/!{shell}/@{file} but a different
     approval/automation model. The generic optimizer must keep a sequential, prose-fed fallback so the pipeline still runs where these features are
     absent.
   ! Putting honesty logic into skill/command content. Skills and slash commands are model-facing text the optimizer could read or rewrite; if the gate,
     no-leak, or sealed-test rules live there, a clever optimizer can subvert them. Keep enforcement in core-owned hooks/scripts (exit-2 blocking) so
     it is deterministic and not editable by the proposing agent.
   ! Relying on prose stdout from headless runs. Without --output-format json (+ --json-schema on Claude, --json/--output-last-message on Codex, --output-
     format json on Gemini) the harness ends up regex-scraping model prose for scores/decisions, which is brittle and silently breaks on wording
     changes. Always request structured output for any step that returns a number or a decision.
   ! Forgetting that bundled-skill/auto-discovery context differs from --bare. A loop tuned interactively (with ambient hooks, CLAUDE.md, MCP) can behave
     differently under claude --bare -p in CI because bare skips all auto-discovery and OAuth. Pin context explicitly via flags and don't assume local
     config is present.
   ! context: fork on a knowledge-only skill yields nothing. Forking a skill that contains guidelines but no actionable task gives the subagent guidelines
     and no prompt, so it returns empty. Only fork steps that contain an explicit task (diagnose/propose/evaluate), not reference-style capability
     skills.
   ! Permission-mode over-reach. bypassPermissions / --dangerously-skip-permissions and codex --sandbox danger-full-access remove all gates; acceptEdits
     also auto-approves mkdir/mv/cp/rm-ish fs commands. On a throwaway candidate dir that's fine, but if a step ever runs against the real repo (or
     the eval harness) it can corrupt state. Scope auto-approve to the workdir and prefer acceptEdits/workspace-write over full bypass.
   ! Plugin directory-layout mistakes. commands/, skills/, agents/, hooks/ must sit at the plugin ROOT; only plugin.json goes inside .claude-plugin/.
     Putting them inside .claude-plugin/ silently fails to load. Also project .claude/agents override same-named plugin agents, so leftover standalone
     files can shadow the plugin version.
   ! Deprecated flags drift. codex --full-auto (use --sandbox workspace-write) and gemini --yolo/-y (use --approval-mode=yolo) are deprecated; these CLIs
     change fast. Probe `<cli> --help` / pin versions rather than hardcoding, exactly as the existing optimizer SKILLs warn.
   ! Stdin/cost caps in headless mode. Claude -p piped stdin is capped at 10MB (write large traces to a file and reference the path instead), and
     background tasks a -p run spawns are killed ~5s after the final result — don't rely on a step leaving a long-running process behind.
