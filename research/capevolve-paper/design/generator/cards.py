"""Configuration cards (Suite A and Suite B). Every value was read from a file on 2026-10-11; 'not recorded' means no file states it."""
from h import card, chip, md

NR = "not recorded"
SPLIT = "`ci/benchmarks/spreadsheetbench/full_verified/split_ids.json` (80 train / 40 val / 280 test; file sha256 `fd40cc4ea53027c3cdf733b153c21b01147bbcfe179b4ef500b5207d13523370`). Test ids are never evaluated. No per-split id-list hash is recorded by any method's launcher."
FEEDBACK = "Scorer feedback is gold-safe but gold-DERIVED: fill counts, mismatch classes, direction of numeric error, type names, sentinel hints. No gold cell values, answer files or test ids (decisions.md, baselines/PROVENANCE.json notes)."
SEED_SHA = "`prompt.md` sha256 `aacc289b4e666017ee2af06bb07a7b2309f4a5d43949852d07fba7246d4b1540`, `task_template.md` sha256 `841967412770441da3ba2785e37194524133aca50a49b489bb57f8e22bb84295` (templates/adapters/spreadsheetbench/seed_capability/)"


def t(kind, label):
    return chip(kind, label)


def suite_a_cards():
    c = []
    c.append(card("CapEvolve hill-climb, paper mode", [t("frozen", "Tier 1"), t("frozen", "matched"), t("running", "s0 running")], [
        ("Code and commit", "worktree `/home/dev/projects2/wt-run`, branch `research/run-integration`, HEAD `f5906110b` = campaign branch + PR #779 + gold isolation (#783). It does NOT contain #786 (rule P module), #788 or #790. Driver `runs/E10/_tools/hc_paper.py` (a custom loop) calls `harness.run_step` unchanged; the confirmation stage lives in `hc_paper.py` because `harness.hill_climb_loop` has no hook for it."),
        ("Editable / seed artifact", "`capabilities [system-prompt]`: `prompt.md` + `task_template.md`. Seed: " + SEED_SHA),
        ("Sees", "val traces in `./trajectories/` and a val-failure summary (D03: val is both feedback and gate). Train-80 is never run or shown (decisions.md, 'stock form'). " + FEEDBACK),
        ("Never sees", "gold, answer files, test ids (not in the daemon's dataset), the evaluator socket internals. Gold and adapter live behind the eval daemon socket."),
        ("Data", "`inputs/split_ids.json`, " + SPLIT + " Only val is ever evaluated (monkeypatch asserts `split==\"val\"`; daemon denies any id outside train+val)."),
        ("Spec keys (s0)", "`optimizer_skill claude-code`, `optimizer_model aws/claude-sonnet-5-5`, `target_model rits/google/gemma-4-31B-it`, `optimizer_max_turns 80`, `optimizer_usd_per_iter 0`, `algorithm_skill hill-climb`, `dataset_source adapter`, `split_seed <seed>`, `num_trials 1`, `gate_mode paired`, `gate_k_se 1.0`, `max_iterations 50`, `stall 0`, `store git`. `max_metric_calls` is a command-line flag (600). No `promotion_rule`, `errored_trial_policy`, `active_eval`, `cost_gating`, merge or DAG keys (single lineage; parent is always the best)."),
        ("Gate and confirmation (hard-coded in hc_paper.py)", "Screen: `k_se 1.0`, `gate_footprint False`, `gate_coverage joint`, `min_coverage 0.95`, `errored_trial_policy` left at default `drop`. A screen accept goes to confirmation: `n_conf 3` (command-line flag; the s99 smoke used 2), fresh trials with `trial_offset 1`, candidate and incumbent on the same val tasks. Promote iff paired mean delta >= 0.02 and delta/SE >= 2.0. An unconfirmed screen accept is reverted. Parent confirmation is reused until the incumbent changes. A confirmation that does not fit the remaining budget is rejected as 'not confirmed: budget'."),
        ("Target runner", "`env_search.sh`: `SPREADSHEETBENCH_MAX_TURNS=30`, `SCORING=hard`, `REWARD_RECALC=1`, LibreOffice 25.8, `MAX_TOKENS=8000`, `TEMPERATURE=0.0`. Rollout concurrency 6 (`E10_CONC`), `hc_paper.py` 8 workers (`E10_WORKERS`). Per-rollout timeout: " + NR + "."),
        ("Optimizer and invocation", "Claude Code CLI via `run-optimizer/scripts/run.py --name claude-code --model aws/claude-sonnet-5-5 --budget 80`; registry template `claude -p ... --permission-mode acceptEdits --allowedTools Bash --disallowedTools Monitor --max-turns 80`. No `--effort` flag. Token cap `--opt-token-cap 4,000,000` (non-cache-read, read from the gateway log under tag `tag:E10-hill-climb-s<k>:hill-climb:optimizer`), checked before each iteration with a 1.3x per-iteration margin."),
        ("Budget and hard counter", "`eval_daemon.py` (unix socket, runs as the harness uid) holds its own `started` counter under a lock and is started with `--max-rollouts 600` (30 for the s99 smoke). When `started >= max`, `run` returns an error rollout `E10_ROLLOUT_BUDGET_EXHAUSTED`. `hc_paper.py` also asserts `used + n_tasks <= max_rollouts` before every evaluation. Every completed rollout is appended to `logs/rollouts.jsonl`."),
        ("Isolation", "`shim/claude` runs the real claude binary as uid `capopt` through `sudo -n -u capopt env -i`, ACL write access only to the candidate workdir, fresh per-search `HOME` and `CLAUDE_CONFIG_DIR` (`/tmp/e10-opt-<arm>-s<k>`). `_eval`, `_priv` and the run dir are mode 700. **Negative-test result for this arm: " + NR + ".** The only capopt negative test on file is EvoSkill's (`runs/E10/evoskill/s*/negtest_before_launch.txt`). Sandbox probe script: `_tools/sandbox_probe_integration.py`."),
        ("Deviations", "Custom `hc_paper.py` stands in for the stock loop. `n_conf` 3, not the n_conf >= 10 of analysis_plan section 8. Rule P is ad hoc here, not the merged #786 module (decisions.md 10:25 gate-parity entry requires the module for main seeds). Val traces are optimizer feedback and gate."),
        ("Known caveats", "s0 started 10:04 and each of its first rollouts took 460-590 s (gateway queue). s99 is a 30-rollout smoke (5-task val) that has run 3,200+ s without leaving the baseline and occupies capacity."),
    ], note="Run state: see status board. s1 and s2 are not launched."))

    c.append(card("CapEvolve agent-optimize", [t("frozen", "Tier 1"), t("frozen", "matched"), t("running", "s0 running")], [
        ("Code and commit", "same worktree and HEAD as hill-climb (`f5906110b`; no #786/#788/#790). Agent loop `skills/algorithms/agent-optimize/scripts/host.py --agent claude-code --model aws/claude-sonnet-5-5 --budget 2000` (turn budget 2000). Gate and finalize scripts `act.py`, `gate_check.py`."),
        ("Editable / seed artifact", "same two files and seed hashes as hill-climb. " + SEED_SHA),
        ("Sees / never sees", "val traces and failure summaries; train-80 is never shown; test ids are not in the daemon's data. " + FEEDBACK),
        ("Spec keys (s0)", "base keys as hill-climb with `algorithm_skill agent-optimize`, `optimizer_max_turns 80`, plus `orchestration_mode agent`, `max_metric_calls 600`, `confirm_fresh_only true`, `gate_k_se 1.0`, `num_trials 1`, `max_iterations 50`, `stall 0`, and a text `stop_condition` that reserves 120 rollouts (3 x 40) for champion confirmation and ends with `act.py finalize`."),
        ("Ablation vector (explicit in spec)", "`dag_parallel true`, `active_eval false`, `smart_merge true`, `cost_gating true`, `failure_clustering true`, `pregate true`, `context_digest true` (all stock defaults). `cost_gating` is on, which is why `confirm_fresh_only` is legal."),
        ("Gate", "No `gate_footprint`, `gate_coverage` or `promotion_*` keys in the spec. The gate is `gate_check --mode reward_gated` with default settings; footprint masking stays on unless `--no-footprint` is passed. `errored_trial_policy` unset. `n_confirm` is the `act.py finalize` default (3 fresh trials per val task). Merge is the whole-file pairwise `smart_merge`; the #788 interaction-aware merge is not in this worktree."),
        ("Concurrency and timeouts", "`GATE_CONCURRENCY = 8` in `host.py`, `BASH_TIMEOUT_MS` = 4 h. Target settings as hill-climb."),
        ("Budget and counters", "same eval daemon (socket mode 711, `--max-rollouts 600`). `token_watchdog.py` SIGTERMs the host process group when non-cache-read optimizer tokens for the tag reach `E10_TOKCAP` = 3,900,000; results in `logs/optimizer_tokens.json`."),
        ("Isolation", "same `shim/claude` as hill-climb (uid `capopt`); `E10_EXTRA_RW` gives capopt write access to the project dir. **Negative test: " + NR + ".**"),
        ("Deviations", "Stock reward_gated gate differs from hill-climb's (the confound of #760). Per decisions.md 10:25, main AO seeds must judge through merged rule P with `gate_footprint false`, `gate_coverage joint`; the running s0 does not, and is designated the E12 stock-gate reference arm. Watchdog 3.9M vs the 4M design cap."),
    ], note="s1 and s2 are not launched."))

    c.append(card("GEPA (gepa 0.1.4)", [t("frozen", "Tier 1"), t("frozen", "matched"), t("running", "3 seeds running")], [
        ("Official repo, version, provenance", "github.com/gepa-ai/gepa. Running copy = PyPI `gepa==0.1.4` unpacked in `baselines/gepa_pypi`, byte-identical (92/92 git blobs) to tag v0.1.4 = commit `8b0ce6cd99a234f6b74daf37558a2ac0ce18f975` (PROVENANCE.json, verified 10:10Z). HEAD `462e437a09be` is 87 commits later; search logic unchanged in the diffs reviewed; one default-path change: truncated reflection outputs are skipped instead of salvaged. Kept. License MIT."),
        ("Editable / seed artifact", "two components, `prompt.md` and `task_template.md`, edited one per proposal by the round-robin module selector. Seed sha256: " + NR + " (the seed is the CapEvolve seed above)."),
        ("Sees / never sees", "reflector sees the full transcript (at most 20k chars) plus the gold-safe feedback string. " + FEEDBACK),
        ("Data", "train-80 for reflection minibatches, val-40 for pareto and selection (the initial val evaluation counts). " + SPLIT),
        ("Hyperparameters", "`max_metric_calls=555`, hard cap 600, `reflection_minibatch_size=3`, `use_merge=False` (official default), pareto candidate selection, round-robin module selector, epoch-shuffled batch sampler, `skip_perfect_score=True`, `perfect_score=1.0`, `cache_evaluation=False`, GEPA seed = run seed, 4 evaluation threads. Reflection LM `openai/aws/claude-sonnet-5-5`, `max_tokens=16000`, `num_retries=3`, temperature unset. Reasoning effort and max turns: " + NR + ". Rollout: Gemma, 30 turns, temperature 0.0, `max_tokens` 8000, rollout seed 0."),
        ("Budget and hard counter", "`sb_eval_lib.Counter.take()` (fcntl lock) runs before each real rollout and raises `RolloutCap` at the cap. Two counters: per-run `rollout_counter.json` capped by `BL_MAX_ROLLOUTS=600`, and `global_counter.json` capped by `BL_GLOBAL_CAP=100000`. GEPA's own `max_metric_calls` counts every example evaluation as 1; the last iteration may overshoot. Reflection tokens are metered under tag `...:reflection` with no in-code cap."),
        ("Proposer", "API call through the gateway (`gepa.lm.LM`), tag `E10-gepa-s<seed>:gepa:reflection`. No uid, no config dir."),
        ("Isolation", "none needed beyond text-only calls; no negative test on file."),
        ("Deviations (deviations_gepa.json)", "one rollout per example with the LO score as reward; transcript plus feedback as the reflective dataset; reflection LM is the gateway Claude; a candidate failing the placeholder contract is scored 0 with no model call but still debits metric calls; seed fixed at 0 (Gemma stays noisy at temperature 0); 4 threads; no merge, no objective frontier."),
        ("Known caveat", "the deviations text says the as-saved reward is the score; the launcher sets `BL_REWARD_METRIC=hard_restriction`, so the recalculated score is used."),
    ]))

    c.append(card("SkillOpt @79124b37", [t("frozen", "Tier 1"), t("frozen", "matched"), t("running", "3 seeds running")], [
        ("Official repo, version, provenance", "microsoft/SkillOpt at `79124b37e9a6371e13b753f8bcd7adb1e493ade1`; 442/442 blobs identical, no extras. HEAD `343db229dbd5` (44 commits, 50 files: plumbing, docs, other environments; reflect/aggregate/gate/optimizer/trainer logic unchanged). Latest release v0.2.0 `e4ea6a67`. Kept. License MIT."),
        ("Editable / seed artifact", "the two seed files packed into one document with `=== FILE: x ===` markers; a document with damaged markers scores 0 with no model call. Packed seed `runs/E10/skillopt/s0/skill_init.md` sha256 starts `f27e3470c2338debeb82` (full hash not recorded in the files read)."),
        ("Sees / never sees", "`conversation.json` = transcript plus a final system message with the gold-safe feedback. SkillOpt's native gold-to-agent retry and gold-vs-prediction reports were removed. " + FEEDBACK),
        ("Data", "train-80 and val-40 (`split/split_manifest.json`); test file is a 1-item stub, `eval_test=false`. " + SPLIT),
        ("Hyperparameters (runs/E10/skillopt/s0/config.yaml)", "`num_epochs=3`, `batch_size=40`, `train_size=80`; analyst `minibatch_size=8`, `analyst_workers=4`; optimizer `learning_rate=4`, slow update on, meta-skill on, edit budget 4 (code default; launcher does not override); `use_gate=true`, gate metric hard (val pass rate); rollout `max_turns=30`, 4 rollout threads (upstream 24); optimizer model `aws/claude-sonnet-5-5`, temperature 0.7, `max_tokens` 16000 (`skillopt_run.py`); reasoning effort not forwarded."),
        ("Budget and hard counter", "no native rollout budget; hard cap `BL_MAX_ROLLOUTS=600`, a breach aborts the run. Counter `by` key shows `skillopt_out/selection_eval_baseline`. Cost formula in `deviations_skillopt.json` and `RUNBOOK.json`. No optimizer token cap enforced in code."),
        ("Proposer", "API through the gateway (`openai_compatible` backend), tag `E10-skillopt-s<seed>:skillopt:optimizer`."),
        ("Isolation", "none needed (plain chat calls); no negative test on file."),
        ("Deviations", "rollout replaced by the CapEvolve rollout; one packed artifact; gold feedback removed; official analyst prompts used unchanged with the environment name forced to `spreadsheetbench`; no test evaluation (which also skips the end-of-run val promotion); 4 workers; candidate-hash val cache; reward is the LO score though the deviations text says as-saved."),
    ]))

    c.append(card("EvoSkill (official loop, adapted task interface)", [t("frozen", "Tier 1 (promoted 09:55)"), t("frozen", "matched"), t("running", "3 seeds running")], [
        ("Official repo, version, provenance", "sentient-agi/EvoSkill, main tarball fetched 2026-10-11; **commit SHA " + NR + "** (tarball has no .git); no PROVENANCE.json entry. Official `SelfImprovingLoop`, `ProgramManager`, frontier and `RunCache` run unmodified except the rollout, scorer and dataset replacements (each listed as a deviation). claude-agent-sdk 0.2.165 driving claude CLI 2.1.296. One official constant patched: the `evaluate.py` timeout 1020 s -> 7200 s. License Apache-2.0."),
        ("Editable / seed artifact", "`skill_only` mode: the seed `prompt.md` is fixed and evolved SKILL.md files are appended under a `## Skills` section; `task_template.md` fixed, so EvoSkill cannot edit the seed prompt or the template. Helper scripts unusable. Seed sha256 " + NR + "; `final/sha256.txt` is written at run end."),
        ("Sees / never sees", "proposer sees the transcript (at most 20k chars) plus gold-safe feedback `Agent Answer: fail` / `Ground Truth: pass`; the claude CLI has tools but runs sandboxed. " + FEEDBACK),
        ("Data", "train-80 pooled by category (Cell-Level / Sheet-Level) and shuffled with the seed; val-40 is the frontier set. " + SPLIT),
        ("Hyperparameters", "`max_iterations=12`, `no_improvement_limit` disabled (`max_iterations+1`; official 5), `concurrency=4`, `frontier_size=3`, `selection_strategy=\"best\"`, `failure_sample_count=3`, `categories_per_batch=3`, `samples_per_category=2` (4 train rollouts per iteration), `cache_enabled=True`, `reset_feedback=True`. Proposer and generator `max_turns=30`, `max_budget_usd=2.0` each, `permission_mode=bypassPermissions`, model `aws/claude-sonnet-5-5`. Planned budget 40 + 12 x (4 + 40) = 568."),
        ("Budget and hard counter", "counter increments per real rollout; cache hits are not counted. At the cap `RolloutCap` makes EvoSkill log a failed evaluation scored 0. Optimizer token limit '<= 4M' has no in-code enforcement."),
        ("Proposer", "claude CLI through the shim `evo_bin/claude`, as uid `capopt`, `ANTHROPIC_BASE_URL` at the gateway, tag `E10-evoskill-s<seed>:evoskill:optimizer`. Config dir " + NR + "."),
        ("Isolation and negative test", "private mount namespace with `/home` and `/tmp` as empty tmpfs. `runs/E10/evoskill/s0/negtest_before_launch.txt` (mtime 10:11:25) shows 'ok denied/absent' for the dataset, answer xlsx, split_ids, tasks, SkillOpt test items, adapter and eval lib, gateway log and `.claude.json`; workspace readable and writable; `neg_test exit=0`. Earlier smoke sessions (before the 10:00 host fix) could read split-id files (ids only), per `restart_note.txt`."),
        ("Deviations and caveats", "only skills are editable; Gemma gets skills as plain text; pass/fail is the only score; official timeout patched. Restart history: launch about 09:43 (3 seeds) stopped for the Tier-2 hold (dirs `s*_stopped_tier_hold_1009`, no proposer sessions); a concurrency-12 launch stopped after minutes (dirs `s*_infra_restart_conc12`); current launch 10:11 at concurrency 4."),
    ]))

    c.append(card("Trace2Skill @3d0b52a", [t("frozen", "Tier 1-cheap"), t("frozen", "matched"), t("running", "3 seeds running")], [
        ("Official repo, version, provenance", "Qwen-Applications/Trace2Skill at `3d0b52a140f002a512930252b613c49048f7d5ac` (main on 2026-10-11). The repo has no LICENSE file on the GitHub API (README says Apache-2.0): run privately, not redistributed. Files fetched one by one via raw.githubusercontent; no blob-identity check; no PROVENANCE.json entry."),
        ("Editable / seed artifact", "a skill directory (SKILL.md + references); seed body = the seed prompt. Export: `prompt.md` = SKILL.md body + references inlined; `task_template.md` unchanged. Seed sha256 " + NR + "."),
        ("Sees / never sees", "transcript plus gold-safe verification text, in single no-tool calls. No ground truth: the paper's ReAct error analyst with ground-truth access is NOT used. " + FEEDBACK),
        ("Data", "the pool is the seed artifact run on train-80, one rollout per id; selection on val-40. `t2s_run.py` asserts every id is in train or val. " + SPLIT),
        ("Hyperparameters", "`--batch-size 1`, `--prompt generic`, `--patch-pipeline json`, merge batch size 5 (CLI default; paper 32), `--workers 4` (target rollouts), `--llm-workers 8`, generation `{max_tokens: 16000}` plus CLI default temperature 0.6, variants {error, combined} each run once, `--seed` = run seed, `--max-rollouts 600`. Planned use 80 + 40 + 40 + 40 = 200."),
        ("Budget and hard counter", "`--max-rollouts 600` through the shared counter; optimizer tokens are read from `gateway_calls.jsonl` by tag and not enforced."),
        ("Proposer", "API through the gateway (`aws/claude-sonnet-5-5`), tag `E10-trace2skill-s<seed>:trace2skill:optimizer`, no tools."),
        ("Isolation", "none needed (text-only, no filesystem tools)."),
        ("Deviations", "deepening of the seed prompt, not creation from scratch; error analysis is LLM-only (likely weakens the baseline vs the paper); stand-in `quick_validate.py` because the repo omits it; candidates {seed, error, combined} are picked by val with strict improvement over the seed; target agent 30 turns instead of the repo's 100."),
    ]))

    c.append(card("Meta-Harness @8123cca", [t("frozen", "Tier 1"), t("frozen", "matched"), t("running", "3 seeds running")], [
        ("Official repo, version, provenance", "stanford-iris-lab/meta-harness at `8123ccabe2b19fa1123090b2e5f1bacc20963ce8`, MIT. Equals upstream HEAD per decisions.md; no PROVENANCE.json entry. `claude_wrapper.py` is the byte-identical official file (sha256 prefix `5ff005d6`)."),
        ("Editable / seed artifact", "the two seed files, written to `workspace/candidates/seed`; the agent ignores other files. Seed sha256 " + NR + "."),
        ("Sees / never sees", "proposer has Read, Glob, Grep, Agent, Write, Edit and Bash. It sees train traces (seed on all 80, then a 20-task batch per iteration) and only aggregate val scores. It never sees val tasks or val traces. " + FEEDBACK),
        ("Data", "train-80 (fed to the proposer) and val-40 (selection only, every candidate evaluated). " + SPLIT),
        ("Hyperparameters", "`--k 2` candidates per iteration, `--train-batch 20`, `--workers 3`, `--max-iters 100`, `--propose-timeout 2400`, `--effort high`, `--proposer-token-cap 4,000,000`; model `aws/claude-sonnet-5-5`; max turns " + NR + ". Planned: 4 iterations."),
        ("Budget and hard counter", "600 hard rollouts via the shared counter. The proposer token cap counts input + output + cache_creation, is checked between iterations and stops the run (usage in `proposer_usage.jsonl`)."),
        ("Proposer", "Claude Code CLI via `claude_wrapper` and the shim `metaharness/sb/shim/claude`, which runs the real CLI in a rootless podman container (`--userns=keep-id`) mounting only the workspace and the claude config dir (rw) and the binary (ro). `CLAUDE_CONFIG_DIR=<out>/claude_config`, tag `...:proposer`."),
        ("Isolation and negative test", "container negative test: `runs/E10/metaharness/s<N>/isolation_negtest.txt` (written 09:42:11) prints `uid=1006` and 'denied/missing' for a gold workbook, `split_ids.json`, `baselines/runs/E10` and `_eval/split_ids.json`, with `workspace_writable`. The launcher aborts on any READABLE line. First launch (08:35, proposer as uid dev, gold readable) was stopped at 09:38 before any proposer iteration; logs kept in `runs/E10/superseded/metaharness-gold-readable-20261011/`."),
        ("Deviations", "SKILL.md written by us (the upstream text-classification skill is not in the public repo); Opus 4.6 with max effort in the paper becomes Sonnet 5.5 with high effort; candidates are prompt files rather than Python harnesses; val is selection-only; final pick = highest val mean; 4 iterations vs about 20 in the paper."),
        ("Known caveat", "`deviations_metaharness.json` still says the proposer has Bash and filesystem access beyond its cwd; that text is stale because the 09:42 container isolation postdates it."),
    ]))

    c.append(card("GraphSkillEvo", [t("pending", "Tier 2 exploratory"), t("pending", "practical track"), t("running", "s0 running")], [
        ("Official repo, version, provenance", "ruisun7/GraphSkillEvo at commit `722a8a913b05...`, arXiv 2609.21749. **No license: private research use only, never vendored.** Upstream package imported unmodified from `baselines/graph_dl/repo` (not a git checkout). No PROVENANCE.json entry."),
        ("Editable / seed artifact", "one graph-structured markdown skill. Scored `prompt.md` = seed `prompt.md` + `\\n\\n# Skill (graph-structured)\\n\\n` + skill; `task_template.md` = seed. Seed skill = upstream `init_skill.md` (2,913 chars) as individual 0 (a human prior the other methods lack). Output `final/{prompt.md,task_template.md,best_graph_skill.md,sha256.txt}`; none exists yet."),
        ("Sees / never sees", "CapEvolve transcript plus the scorer's gold-safe message, for k=5 sampled failures per parent. `include_hidden_reference=false`, `build_reference_text()=''`, `use_eval_feedback` never used. " + FEEDBACK),
        ("Data", "split_dir with train 80, val 40 and a 1-item test stub; the adapter asserts every rolled-out id is in train or val."),
        ("Hyperparameters (config.yaml)", "population 4, generations 2 (default 5), `train_eval_num 15`, `reflection_failure_k 5`, `train.batch_size 40`, `train.train_size 80`, `evaluation.test_env_num 0`, `operator_max_completion_tokens 32000` (upstream 64000), `reasoning_effort` '' (not sent), 4 concurrent rollouts (upstream 8), `max_turns 30`, selection `valid_seen` (argmax val hard, no seed gating), `--max-rollouts 600`."),
        ("Budget and hard counter", "worst case 4 x 40 + 2 x (4 x 15 + 4 x 40) = 600 under the shared counter `rollout_counter.json`. 4M optimizer-token cap: not enforced in code."),
        ("Proposer", "plain chat completion through the gateway in openai_compatible mode, key `tag:E10-graphskillevo-s0:graphskillevo:optimizer`. No tools, no uid."),
        ("Isolation", "no negative test needed per the deviations file (text only); no `isolation_tests.json` exists."),
        ("Deviations", "rollout replaced by the shared CapEvolve rollout; upstream init skill is individual 0; population 4 / generations 2; 4 concurrent rollouts; operator tokens 32000; no seed gating."),
        ("Run history", "s1 and s2 were launched 09:00 before the tiering message and stopped (exit 143) at 6 and 5 rollouts: `STOPPED.json` 'capacity tiering (decided 09:00 before any result), not outcome-driven'; relaunch from scratch with the same config only if capacity frees."),
    ]))

    c.append(card("MCE (Meta Context Engineering)", [t("pending", "Tier 2 exploratory"), t("running", "s0 running")], [
        ("Official repo, version, provenance", "metaevo-ai/meta-context-engineering at `c4b7a7c2ce3f...`, MIT. Official code unmodified apart from monkeypatching in the runner. `claude-agent-sdk` pinned at 0.1.23 (lock-file version; 0.2+ ignores `can_use_tool` for `allowed_tools`). No PROVENANCE.json entry."),
        ("Editable / seed artifact", "`context/prompt.md` + `context/task_template.md`; seed copied into iter0; final = best-val iteration picked by `finalize_mce.py` (not run yet)."),
        ("Sees / never sees", "train batch tasks with gold-free fields only (id, instruction, instruction_type, answer_position); the meta-agent's `train.jsonl` holds all 80 gold-free task descriptions. Never sees gold or the 280 test ids (split check plus a per-call allow-list)."),
        ("Data", "64 of 80 train per iteration (`random.seed(1000+seed)`) in 2 sub-iterations of 32; val-40 every iteration."),
        ("Hyperparameters", "`--iterations 5`, `--train-limit 64`, `--batch 32`, `--cap 600`, `mce.eval.MAX_CONCURRENCY` 30 -> 8 queued, 4 rollout worker threads. The log shows iter0-5."),
        ("Budget and hard counter", "plan 40 baseline + 5 x (64 + 40) = 560 under a 600 shared fcntl counter. Optimizer guard stops before an iteration if used + 600k estimated would exceed 4M."),
        ("Proposer", "Claude Agent SDK driving the Claude Code CLI through the gateway, tag `tag:E10-mce-s<seed>:mce:optimizer`, all aliases map to Sonnet 5.5, a fresh `CLAUDE_CONFIG_DIR` per seed; helper calls under `...:optimizer-aux`. Uid " + NR + "."),
        ("Isolation and negative test", "decisions.md 09:45: s0 continues 'subject to a gold-isolation negative test of its SDK meta-agent'. **No `manifest.json` or `isolation_tests.json` exists in `runs/E10/mce/s0`; result " + NR + ".** The only guard on record is the SDK permission handler (read/write confinement)."),
        ("Deviations", "new environment `sb_context`; the target agent sees only 2 files; paper used MiniMax-M2.1 and deepseek-chat-v3.1, ours is Sonnet 5.5; concurrency cut; meta and base agents share one tag; final = best-val iteration (strict greater-than, seed included)."),
        ("Run history", "launched with 3 seeds 09:37 before 'go Tier 2'; s1/s2 stopped 09:41:27/28 by the coordinator at 5 rollouts each (their `run.log` shows the finalize script crashing on a missing `iter_results.jsonl`)."),
    ]))

    c.append(card("Memento-Skills", [t("pending", "Tier 2 exploratory"), t("running", "s0 running")], [
        ("Official repo, version, provenance", "Memento-Teams/Memento-Skills at `ee9b9a45efd0...`, Apache-2.0. Adapter `baselines/memento/memento_run.py` (sha256 `36d79450...2a90`) imports the repo unmodified. No PROVENANCE.json entry."),
        ("Editable / seed artifact", "skill folder `skills/spreadsheet-task/{SKILL.md,prompt.md,task_template.md}` seeded from the CapEvolve seed. `final/{prompt.md,task_template.md}` is the drop-in capability (not produced yet)."),
        ("Sees / never sees", "skill files plus, for one failed TRAIN task, its instruction, type, answer_position, the Gemma transcript (up to 14k chars), the gold-safe feedback string and the utility table. Never sees gold, any val trace or feedback, or test tasks. The proposer has no tools; the engine writes file contents only. " + FEEDBACK),
        ("Data", "train-80 for evolution, retry and gate rollouts; val-40 for selection only; the driver asserts every rollout id is in train or val."),
        ("Hyperparameters", "`--budget 600 --batch 8 --max-evolve-per-batch 3 --retries 2 --epochs 3 --workers 4`; attribution confidence >= 0.5; discovery rewrite when utility < 0.2 with >= 3 samples; `candidate_attempts 1`; `max_prompt_chars 60000`; proposer LLM `max_tokens 16000`, `context_window 100000`; retry K=2 after a deployed update."),
        ("Budget and hard counter", "every train, retry, gate and val rollout counts toward the shared hard counter of 600; the loop stops early if a worst-case batch plus a val pass would exceed 600. 4M optimizer-token cap not enforced in-process (metered by tag `tag:E10-memento-s0:memento:optimizer`)."),
        ("Proposer", "official `SkillEvolutionEngine` calling Sonnet 5.5 through `LLMClient` as `openai/aws/claude-sonnet-5-5`. API call, not a CLI agent."),
        ("Isolation and negative test", "`runs/E10/memento/s0/isolation_tests.json`, 2026-10-11T10:02:51Z, sha256 `676f80ff...1ec5`: ALL_PASSED 7/7 (T1-T6, with T4b). T3/T4 proposer checks use a stub LLM. T2 inspected 64 sandboxes: none mounted the gold tree. T6 is to be re-run at the end of the run."),
        ("Deviations (D1-D8)", "Memento runtime not used; scorer replaces the LLM judge; the synthetic gate is overridden with a counted regression rollout; a 2-line harness note is prepended; single skill, router not exercised, no tip memory in the released repo; batch-loop schedule; val-40 selection added; non-deterministic Gemma. Caveat: upstream `copytree` dereferences symlinks."),
        ("Run history", "launched with 3 seeds 09:52 by a helper agent before 'go Tier 2'; s1/s2 stopped 09:54:18/20 at 4 rollouts each, 'not to be relaunched'."),
    ]))

    c.append(card("RHO (Retrospective Harness Optimization)", [t("pending", "Tier 2"), t("pending", "smoke only, may be blocked")], [
        ("Official repo, version, provenance", "wbopan/retro-harness at `e5f2d1a8a06a...`, MIT. Adapter `baselines/rho/rho_sb_run.py`, launcher `launch_rho.sh`. Codex CLI 0.162.1. No PROVENANCE.json entry."),
        ("Editable / seed artifact", "harness directory `{prompt.md, task_template.md}`; extra files the optimizer adds are listed in `final_extra_files.json`. Smoke harness id `h_75c6ef0bb615`."),
        ("Sees / never sees", "label-free: no labels, grader or val set during optimization; rewards are logged for reporting only. Task prompts carry instruction, type and answer_position only."),
        ("Data", "train-80 plus val-40; val evaluated post hoc only."),
        ("Hyperparameters (official config kept)", "rounds 1, k=10 coreset, selector dpp theta 0.7, embeddings BAAI/bge-large-en-v1.5, group size G=3, optimize samples N=3, strategy diagnosis, accept iff mean pairwise self-preference > 0. Runner defaults `--hard-cap 600 --solve-workers 8 --codex-concurrency 8`; reasoning-effort flag omitted. Smoke run: `--n-train 3 --k 2 --samples 1 --selector difficulty --no-val --hard-cap 12 --solve-workers 3`."),
        ("Budget and hard counter", "per seed: 80 source rollouts + 30 group + 30 candidate re-solves + post-hoc val-40 for seed, final and each candidate = about 300 counted rollouts or fewer; hard cap 600. No optimizer-token cap described."),
        ("Proposer", "official CodexAgent (codex-cli 0.162.1) through `responses_shim.py` (our 150-line Responses-to-Chat translator at 127.0.0.1:4181), `codex_gw.toml` with `wire_api=responses`. Uid " + NR + "."),
        ("Isolation", "`codex_masked.sh` runs Codex in `unshare -Urm` with empty tmpfs over the gold data, `bench/out`, `bench/isolation`, `runs/`, `baselines/work` and the repos, with `danger-full-access` inside the namespace. **No negative-test result is recorded**; the smoke has no `isolation_tests.json`."),
        ("Deviations and caveats", "base agent replaced by the rollout wrapper; Codex runs Sonnet 5.5, not the paper's GPT-5.5; the shim is ours; trajectories converted to codex-style events; rollout counts include source trajectories. Codex warns 'Model metadata ... not found'; the sandbox mask depends on namespace support. One smoke rollout ended 'sandbox exec failed: 500'."),
        ("State", "no E10 seed run exists. The smoke (PID 3327723) counter was 6/12 at the last read; the coreset was ['105-24','10452']; no verdict recorded."),
    ]))

    c.append(card("ACE", [t("frozen", "Tier 1-cheap"), t("pending", "not launched")], [
        ("Official repo, version, provenance", "ace-agent/ace at `82709de050e1...`, Apache-2.0, patched copy in `dl_new/ace_patched` via `ace/prompt_patch.diff` (rewords a 'chain of thought' phrase because the gateway returns `content_filter` with an empty body). No PROVENANCE.json entry."),
        ("Editable / seed artifact", "a playbook injected at the end of `prompt.md` under a '## Playbook (ACE)' header; `task_template.md` = seed. Seed playbook is an empty section skeleton."),
        ("Sees / never sees", "Reflector and Curator get the scorer's gold-safe feedback plus the final output code (no-GT mode). Never gold cells."),
        ("Data", "train-80 for epochs (shuffled each epoch); val-40 at each epoch end and at the stopping point; best-val playbook is final."),
        ("Hyperparameters", "`--max-rollouts 600 --max-opt-tokens 3,900,000 --epochs 3 --rounds 1` (official max_num_rounds 3), `--workers 4`, `--token-budget 80000` (playbook), `--trace-chars 20000`; Reflector/Curator `max_tokens` 8000 (official 4096); curator_frequency 1, temperature 0.0; bulletpoint analyzer off; post-curator generation skipped."),
        ("Budget and hard counter", "all train and val rollouts count toward 600 via the shared counter; optimizer-token stop at `--max-opt-tokens 3.9M`."),
        ("Proposer", "OpenAI client to the gateway, tags `tag:E10-ace-s<seed>:ace:{reflector,curator}`. No uid."),
        ("Isolation", "proposer sees text only; no negative test recorded."),
        ("Deviations", "generator replaced by a target rollout; bullet-id harvesting by regex; no-GT mode; the prompt patch; `max_num_rounds=1`; the regenerated rollout gets no reflection slot; val selection and budget stopping rule."),
        ("State", "not launched (no `runs/E10/ace`). Smoke `baselines/runs/ace_smoke`: 6 rollouts (3 train, 3 val), 85,733 target tokens, 29,632 optimizer tokens in / 5,188 out, selected `epoch1_end` at val 1.0, 13 bullets."),
    ]))

    c.append(card("MIPROv2 (DSPy 3.4.0)", [t("frozen", "Tier 1-cheap"), t("pending", "not launched")], [
        ("Official repo, version, provenance", "DSPy 3.4.0 wheel (`dl_new/dspy_whl/dspy-3.4.0-py3-none-any.whl`), `dspy.teleprompt.MIPROv2` unmodified. Commit, license and PROVENANCE.json entry: " + NR + ". `venv_dspy`, `wheels_mipro` (optuna 5.0.0 etc.)."),
        ("Editable / seed artifact", "predictor instruction, starting as the full seed `prompt.md`, plus up to 3 bootstrapped demos. `forward()` builds `prompt.md` = instruction + '## Worked examples' demos; `task_template.md` = seed."),
        ("Sees / never sees", "trainset examples (instruction, type, answer_position) and demo solution code from correct runs. Gold exposure not described."),
        ("Data", "trainset = train-80 (bootstrapping and the data-aware proposer); valset = val-40 (minibatch trials, full evals, selection). Test ids asserted absent."),
        ("Hyperparameters", "`--max-rollouts 600 --candidates 6 --trials 40 --minibatch 8 --full-eval-steps 10 --max-demos 3 --threads 4 --demo-chars 3000`; prompt LM `max_tokens` 8000, `cache=False`; `auto=None`, `max_labeled_demos=0`, `max_errors=1e6`, `seed=<seed>`."),
        ("Budget and hard counter", "`rollout_counter.json` hard cap. Whether MIPROv2 stops itself before the cap, and any optimizer-token guard: " + NR + "."),
        ("Proposer", "`dspy.LM` calling the gateway, tag `tag:{prefix}:{arm}:proposer`."),
        ("Isolation", "pure LM, no tools; no negative test recorded. No `mipro/deviations.json` (directory empty)."),
        ("Deviations", "the DSPy LM is never called as a task model (`forward()` runs a rollout); the task LM tag is `target`. Others: " + NR + "."),
        ("State", "no E10 run. A smoke (PID 1730226, `--out runs/mipro_smoke --n-train 3 --val-from-train --candidates 4 --trials 2 --minibatch 2 --full-eval-steps 5 --max-demos 1 --max-rollouts 12 --threads 3`) has run 4,900+ s with counter 12/12 and still holds a process."),
    ]))

    c.append(card("WikiSkill (community implementation, no official code)", [t("frozen", "Tier 1"), t("pending", "not launched"), t("pending", "track " + "not recorded")], [
        ("Repo, version, provenance", "github.com/Stahl-G/wikiskill at `da6984caca09...`, release v0.2.1 (2026-09-29), MIT. NOTICE.md: 'not affiliated with the paper's authors' (arXiv 2608.27454). Official code verified absent (abstract, paper text, likely repos 404; the community ports say Google has not released code). Our paper-based reimplementation (`reimplementation_spec.json`) is paused as a fidelity reference. Not in PROVENANCE.json."),
        ("Editable / seed artifact", "a skill set appended to `prompt.md` as a `## Skills` section; seed = empty skill set; `task_template.md` unchanged. Output `final/{prompt.md,skill_text.md,task_template.md,sha256.txt,wiki}`."),
        ("Sees / never sees", "maintainer and proposer get pass/fail, score and the gold-safe scorer feedback; no predictions or ground-truth values. The wiki is hidden from the target agent."),
        ("Data", "train-80, val-40; assertions that train and val are disjoint and exclude test."),
        ("Hyperparameters", "`--max-rollouts 600 --iterations 8 --opt-token-cap 4,000,000 --max-turns 25` (proposer turns); optimizer `max_tokens` 16000 with cache_control markers; `BL_ROLLOUT_WORKERS` 4; `timeout` 1800; upstream behavior kept: <= 5 failing and <= 3 passing traces sampled, 15k-char trace cap, >= 4 trace reads, strict `>` gate, early stop at val 1.0."),
        ("Budget and hard counter", "the adapter stops before a train rollout when fewer than train + val (120) rollouts remain, so about 4 iterations fit. Non-cache-read optimizer tokens are counted in-process (`TokenCap`, 4M)."),
        ("Proposer", "Claude through the gateway driving upstream `RoleTools` (`read_file`, `finish`) in place of the Codex transport. API call; uid " + NR + "."),
        ("Isolation", "`wikiskill_community/code/negative_test.py` scans staged files for gold markers and checks that `RoleTools` refuses escapes. No result file was found."),
        ("Deviations", "rollout is the CapEvolve target rollout; transport is gateway Claude instead of the Codex CLI; budget stop; no ground truth shown; the paper's SpreadsheetBench prompt replaced by the CapEvolve prompt."),
        ("State", "not launched at E10. Smoke `baselines/runs/wikiskill_community_smoke` (3 train, 3 val): baseline val 1.0, `STOP early_stop_validation_ceiling` at iteration 0, 3 rollouts, 0 optimizer tokens."),
    ]))

    c.append(card("AHE (Agentic Harness Engineering)", [t("pending", "Tier 2"), t("pending", "not launched")], [
        ("Repo, version", "clone at `baselines/dlx_agentic-harness-engineering`, commit `8b2a55d97590...`, MIT. Not in PROVENANCE.json."),
        ("Everything else", NR + ". There is no adapter, no `deviations.json` and no smoke result; `baselines/ahe` is empty. The clone has `evolve.py`, `agents/{code_agent_simple,evolve_agent,explore_agent}`, `configs/{base.yaml,experiments}` and `scripts/evolve.sh`."),
    ]))
    return c


def suite_a_common():
    return card("Settings shared by every Suite A method", [t("frozen", "shared")], [
        ("Target rollout", "`baselines/code/sb_eval_lib.py`: Gemma-4-31B-it (`rits/google/gemma-4-31B-it`) through the gateway, 30 turns, temperature 0.0, `max_tokens` 8000, rollout seed fixed at 0, concurrency env 4, podman sandbox with the gold-free agent view (`SPREADSHEETBENCH_AGENT_VIEW=1`). Reward: LibreOffice 25.8 `hard_restriction` (`BL_REWARD_METRIC`); as-saved score also logged."),
        ("Split", SPLIT),
        ("Seed artifact", SEED_SHA),
        ("Feedback disclosure", FEEDBACK + " Every method receives the same feedback channel; CapEvolve hill-climb and agent-optimize additionally see only VAL traces (D03), competitors see train-80 traces and use val-40 for selection (decisions.md data-exposure entry, recorded as a disclosed difference)."),
        ("Optimizer", "`aws/claude-sonnet-5-5` for every matched arm."),
        ("Budget", "600 target rollouts per search (hard counter, rollouts rejected by the placeholder-contract pre-check cost nothing and are not counted), at most 4M non-cache-read optimizer tokens (enforcement varies by method: see cards), seeds 0/1/2."),
        ("Outputs", "`runs/E10/<method>/s<seed>/` with `final/` (frozen artifact + `sha256.txt`), logs, per-candidate selection scores, `rollout_counter.json`."),
    ])


def suite_b_cards():
    c = []
    common = ("tau2-bench pinned at `8ebb7499622fc2be9b9d510d6f7a7653461f4f29`; splits `wt-tau/protocol/tau_retail_splits.json` (sha256 `07d013b7bd011676e1dbab86e549229533e68bca8070918c81711a6a510ee90a`): official train 74 / test 40; `Random(42).shuffle` of the sorted train ids, first round(2/3 x 74) = 49 are opt, the other 25 are sel; test 40 sealed. Id-list hash prefixes: opt `6d4ef752`, sel `694b911b`, test `1e26a51b`. 29 of the 74 train tasks have NL assertions (opt 20, sel 9).")
    c.append(card("Settings shared by every Suite B arm", [t("frozen", "shared")], [
        ("Data", common),
        ("Roles of the splits", "CapEvolve arms: train = val = opt (49 tasks, used for feedback and the gate); 'test' = sel (25 tasks, hidden from the optimizer, scored once by finalize for seed and best). The official test ids are never written into the project; the adapter raises `RuntimeError` for sealed ids. GEPA: trainset = opt (49), valset = sel (25), so GEPA selects on the same sel set it is scored on."),
        ("Runner (wt-tau/examples/tau2_retail/adapters/adapter.py)", "`MAX_STEPS=100` (tau2 default 200), `max_errors=10`, temperature 0.0 for agent, user and judge roles, `max_tokens` 8000, `reasoning_effort` only if `TAU_REASONING_EFFORT` is set (no E10B env file sets it: provider default), `TAU2_SIM_TIMEOUT=7200`, `TAU2_MAX_CONCURRENCY=6`. Target and user simulator: `rits/openai/gpt-oss-120b-a100` through the gateway; role tags `target`, `user`, `judge`."),
        ("Judge: discrepancy", "decisions.md says the NL-assertion judge is `azure/gpt-5.5` for every arm. The adapter's `TAU_JUDGE_MODEL` default is `openai/rits/openai/gpt-oss-120b-a100`, no E10B script or env file sets it, and the gateway log shows `judge` calls going to gpt-oss in every E10B arm (92 gpt-oss judge calls when checked; the only gpt-5.5 call is a probe). The gpt-5.5 judge is NOT what is running. " + " [[pending|decision needed]]"),
        ("Editable surfaces", "CapEvolve arms: `capabilities [system-prompt, tools]`: `policy/policy.md` (a guidance addendum appended after the verbatim benchmark policy; seed content '(none)') and `tools/tools.py` (agent-side wrappers). Read-only `capability_sources`: `reference/data_model.py`, `reference/benchmark_policy.md`. The evaluator replays tool calls on the pristine toolkit. GEPA edits only the `policy.md` addendum."),
        ("Seed artifact sha256", "`policy/policy.md` `5dfecbf35de344dc6dc4b8a79c4e5327122b2737250403b04abf2060fbc3927f` (content '(none)'); `tools/tools.py` `8aa9a49538743e6fefe7356ecbb5d2d50c3cb74c7eae1425e1fa842058840017`; GEPA pilot seed policy sha prefix `552e4230`."),
        ("Optimizer token guard", "`scripts/E10B/cost_summary.py --guard <driver pid> --limit 3900000 --interval 60` sums optimizer or reflection input + output + cache-creation tokens from the gateway log (cache reads excluded) and SIGTERMs the driver's process group above the limit."),
        ("Isolation", "the CapEvolve optimizer runs as uid `dev`, not `capopt`, with `CLAUDE_CONFIG_DIR=<run>/claude_cfg`; no uid separation, no ACLs and no negative test recorded for Suite B arms. The tau2 task data and splits JSON remain readable by the optimizer. Sealed-test protection is the adapter assertion plus keeping test ids out of the project."),
        ("Code", "wt-tau, branch `research/tau-retail` at `fdc31881c`, which merges `origin/research/paper-mode-switches` (pre-fix #779 switches). It has none of #783, #786, #788, #790. Venv `venv-tau2-8ebb749`."),
    ]))

    c.append(card("CapEvolve hill-climb (Suite B, `hc`)", [t("frozen", "matched"), t("running", "3 seeds running")], [
        ("Driver", "`cap_evolve.cli run --spec ... --run-ts main --dashboard off` (framework hill-climb, deterministic orchestration). `scripts/E10B/{build_cap_project.py,launch_cap.sh,collect_cap.py}`; `runs/E10B/hc/s<k>/{driver.sh,env.sh,guard.log,run.log}`."),
        ("Spec keys", "`optimizer_skill claude-code`, `optimizer_model aws/claude-sonnet-5-5`, `optimizer_max_turns 80`, `optimizer_usd_per_iter 8.0`, `target_model rits/openai/gpt-oss-120b-a100`, `split_seed 42`, `num_trials 1`, `gate_mode paired`, `store copy`, `pregate.toolkit adapters/adapter.py:pregate_toolkit`, `algorithm_skill hill-climb`, `algorithm_focus all`, `orchestration_mode deterministic`, `gate_k_se 1.0`, `gate_footprint false`, `gate_coverage joint`, `gate_min_coverage 0.95`, `max_iterations 10`, `stall 0`, `max_metric_calls 550`."),
        ("Not set", "`errored_trial_policy` (so `drop`), any confirmation stage (`n_conf`), `promotion_rule` / rule P, `confirm_fresh_only`. Under the 10:25 gate-parity decision (rule P with n_conf 3, dmin 0.02, z_conf 2.0, promotion_min_coverage 0.95) these arms are NOT yet compliant. " + " [[pending|decision needed]]"),
        ("Budget", "only cap is `max_metric_calls 550` in the framework state. Expected consumption: baseline 49 + 10 candidates x 49 = 539 before finalize, plus finalize on sel (25 for seed and best): about 564 after. Token guard as shared card."),
        ("State", "all three seeds launched 09:40-09:42 and are still in the 49-task seed baseline (`state.json` metric_calls 0). Pilot `pilot_hc/s0` (10 opt, 5 sel, 2 iterations, 35 metric calls) rejected both candidates and selected the seed (sel 0.6 for both)."),
        ("Deviations", "gpt-oss judge instead of gpt-5.5; budget 550 rather than 600; CapEvolve edits policy and tools while GEPA edits only the policy addendum; sel is used as the CapEvolve 'test' split and as GEPA's selection set."),
    ]))

    c.append(card("CapEvolve agent-optimize (Suite B, `ao`)", [t("frozen", "matched"), t("running", "3 seeds running")], [
        ("Spec keys", "common keys as hill-climb plus `optimizer_max_turns 300`, `optimizer_usd_per_iter 8.0`, `max_optimizer_usd 40.0`, `algorithm_skill agent-optimize`, `orchestration_mode agent`, `gate_k_se 1.0`, `confirm_fresh_only true`, `max_iterations 10`, `stall 0`, `max_metric_calls 550`, `stop_condition 'stop when the rollout budget (max_metric_calls) is exhausted or after 10 candidates'`; driver adds `--agent-driver claude-code`."),
        ("Ablation vector", "all stock defaults: `dag_parallel true`, `active_eval false`, `smart_merge true`, `cost_gating true`, `failure_clustering true`, `pregate true`, `context_digest true` (recorded as `effective_ablation_vector_default_resolution`)."),
        ("Gate", "no `gate_footprint`, `gate_coverage` or `promotion_*` keys: the stock `reward_gated` gate with footprint masking on. Not compliant with the 10:25 parity decision. " + " [[pending|decision needed]]"),
        ("State", "launched about 09:43; all three in the seed baseline. `pilot_ao/s0` (10 opt, 5 sel, `max_metric_calls 80`, `max_optimizer_usd 5.0`) is still running: 26 metric calls, `runner_tokens` 1,850,829, has proposed `cand_1`."),
    ]))

    c.append(card("GEPA (Suite B)", [t("frozen", "matched"), t("running", "3 seeds running")], [
        ("Code", "PyPI `gepa==0.1.4` from `baselines/gepa_pypi`, `gepa.optimize` unmodified, driver `gepa_tau.py`, `launch_gepa.sh`."),
        ("Artifact", "only the `policy.md` addendum, seed '(none)'. Not the tools."),
        ("Settings", "`max_metric_calls 600`, `reflection_minibatch_size 3`, `use_merge False`, `seed=<seed>`; hard cap in `CountedEvaluator` 600 + 2 x 3 + 25 = 631; reflection LM `openai/aws/claude-sonnet-5-5`, `max_tokens 16000`, `num_retries 3`, tag `...:gepa:reflection`; `TAU2_MAX_CONCURRENCY=6`, `TAU2_SIM_TIMEOUT=7200`, `CAPEVOLVE_NATIVE_SIMS=0`."),
        ("Counter", "`rollout_counter.json` is bumped by the batch size before each batch runs; it counts every rollout attempt, including up to 3 retries on an errored rollout, and raises `RuntimeError` past the hard cap. Token guard `cost_summary --guard --limit 3900000`."),
        ("State", "launched about 09:41; each seed is in its first batches (counters 25 started, 0 recorded as done). Pilot `pilot_gepa/s0`: 27 counted rollouts, 1 retry, 2 candidates, best_idx 0 (identical to the seed), reflection tokens 45,275 in / 11,186 out."),
    ]))

    c.append(card("Controls (Suite B): ctl-seed and ctl-oneshot", [t("frozen", "controls"), t("running", "running")], [
        ("ctl-seed", "the unmodified seed capability evaluated by `eval_cap.py --splits opt,sel --trials 2 --seed <k>`: 49 x 2 on opt then 25 x 2 on sel = 148 rollouts; retries up to 3 on errored rollouts; `CAPEVOLVE_NATIVE_SIMS=0`; no optimizer. Concurrency " + NR + "."),
        ("ctl-oneshot (one-shot repair)", "spec identical to hill-climb except `max_iterations 1` and `max_metric_calls 200`: one claude-code optimizer iteration (80 turns, $8, gate k_se 1, footprint off, joint coverage 0.95) through the same driver. `collect_cap.py` selects `cand_0001` unconditionally, even if the gate rejected it. Finalize scores sel. Rollouts: baseline 49 + candidate 49 + finalize about 25-50, so about 125-150 of the 200 cap."),
    ]))

    c.append(card("HarnessLens (Suite B only), MIPROv2, ACE and Meta-Harness on Suite B", [t("pending", "prepared"), t("pending", "not launched")], [
        ("HarnessLens", "jhxu5214/HarnessLens at `369a5c8c7856...`, MIT; OpenCode harness v1.17.13, tau2 pinned at `8ebb7499` (HarnessLens' own pin is `d8e915f`). Native retail cell. Editable artifact: an OpenCode config patch (instructions, skills, prompt appends, tool descriptions), which the CapEvolve tau2 adapter cannot load: absolute numbers are NOT comparable to CapEvolve; only deltas against the unmodified OpenCode baseline are. TRAIN = 30 ids sampled with `Random(seed)` from the frozen 49-task opt split; the 25-task sel set is scored once after the search by `eval_sel.sh`; the sealed 40-task test is never visible. `HAI_TOTAL_CREATION_BUDGET` 600 (paper 200) counts LLM sessions and task trials in one unit; `hl_counter.py` reports target rollouts separately. `HAI_MAX_ROLLOUT_CONCURRENCY` 6, `HAI_TAU2_TIMEOUT_PER_TURN_S` 900. Baseline 30 tasks x 2 repeats = 60 trials. Roles use Sonnet 5.5; `reasoning_effort=high` is HarnessLens' own setting. Isolation: `hl_sandbox.sh` (`unshare --user --map-root-user --mount`, `/home/dev` replaced by empty tmpfs); `negtest.sh` aborts on any READABLE line or sealed id. **No negative-test result file exists; not launched** (`launch_e10b_hl.sh` ready; smoke baseline ended `exit=124`)."),
        ("MIPROv2 and ACE", "no tau adapter directories or runs exist (`baselines/mipro` empty; `baselines/ace` Suite A only)."),
        ("Meta-Harness", "Suite A only; no tau adapter."),
    ]))
    return c
