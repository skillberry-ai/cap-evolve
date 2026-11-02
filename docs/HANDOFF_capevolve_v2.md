# Handoff: capevolve_v2 (re-run CapEvolve on main + PR #914, k_se 0.2) — exp895

Written 2026-10-25 by the exp895 monitoring session for a NEW, dedicated Claude session.
Read this whole file before doing anything. You own ONLY the `capevolve_v2` arm.

## 1. What you are doing and why

exp895 (GitHub issue skillberry-ai/cap-evolve#895) compares CapEvolve against 9 competitor optimizers on
SpreadsheetBench verified_400:
- **Agent:** Gemma-4-31B on RITS.
- **Optimizer:** GLM-5.3 via Curve Bender.
- **Budget:** R = 2,160 counted rollouts per search, k = 3 trials, 3 seeds.
- **Held-out test:** 280 official test tasks, each champion paired with the seed in the same window.

The first CapEvolve arm (`capevolve`) ran from branch `exp/sbv400-895` (old main + 2 commits) with `gate_k_se: 0.5`. So far:
- s1 test: +0.066 ± 0.033 over the seed.
- s2 test: +0.061 ± 0.041.
- s0 test: still running.

Osher and Erez since merged **PR #914** (main 75b3bcdd0): optimizer instructions "Improvement 2", and default `gate_k_se` 0.2.
Osher asked for **CapEvolve only, re-run with the latest main, with a fresh intake, at k = 0.2**. Answers from Osher (via Boaz):
1. **#903 (container retry): cherry-pick, do not merge.** Done.
2. **gate_footprint: use the default Osher and Erez use.** On main that key is absent, so masking is on. Do NOT set `gate_footprint: false`.
3. and 4. **More throughput:** Boaz added more RITS keys. Spread the load by giving each job its own key. See §4.

## 2. What is already prepared (by the monitoring session)

| Item | Path | State |
|---|---|---|
| Worktree and branch | `cap-evolve-spread-worktrees/sbv400-k02`, branch `exp/sbv400-895-k02` | from origin/main 75b3bcdd0, plus cherry-picks 777e111b3 (= #903 container retry) and 0d791eeb7 (common pre-rollout helper gate). Not pushed. |
| Venv | `exp895/venv_k02` | built on a compute node; editable install of `sbv400-k02/core` (verified). The old `exp895/venv` stays pinned to `sbv400-main`. Never mix them. |
| Node env | `exp895/tools/node_env_k02.sh` | = `node_env.sh` with REPO=sbv400-k02 and venv_k02 |
| Search launcher | `exp895/tools/lsf_capevolve_v2_search.sh` | = `lsf_capevolve_search.sh` with node_env_k02, `runs/capevolve_v2/`, template `arms/capevolve_v2/template`, tag `exp895-capevolve_v2-s<seed>`, and `KEY_SLOT` support |
| Arm dir | `exp895/arms/capevolve_v2/` | **empty: you build `template/` (§3)** |
| Auto test launcher | `exp895/tools/auto_test_launcher.py` | already knows `capevolve_v2`; when a v2 search finishes with `CAPEVOLVE_RC=0`, the monitoring session's watcher launches its test window |
| Gateway multi-key | `exp895/tools/gateway.py` | `GW_RITS_KEY_SLOT=<n>` selects `RITS_API_KEY_<n>` from `~/secrets/rits_keys.env`; unset = the original key. `/healthz` reports `key_slot` |
| Test window | `exp895/tools/lsf_test_window.sh` | accepts an optional `KEY_SLOT` env |
| Old INSTRUCTIONS addendum | `exp895/arms/capevolve/INSTRUCTIONS.exp895_addendum.md` | the 77-line block exp895 inserted into the optimizer INSTRUCTIONS (see §3.3) |

Code check: `templates/adapters/spreadsheetbench/adapter.py` in sbv400-k02 has the SAME sha256 (c035c75e…) as the frozen
`capevolve` run, and `seed_capability_v2` is byte-identical. So the agent, scorer and seed are unchanged. Only the
cap-evolve optimizer, algorithm and gate code and config change.

## 3. Your steps

Run nothing heavy on a login node. Image builds, venv builds, checks and smokes all go through LSF (`bsub`).
Never pass `-W`.

### 3.1 Read first
- `exp895/decisions.md`: the full decision log. Skim it, and read the CapEvolve, gate and helper-gate entries.
- `sbv400-k02/docs/how-to/ccc/CCC_PODMAN_SETUP.md` §Batch (LSF) mode: CCC podman and LSF rules.
- `exp895/arms/capevolve/template/.capevolve/project/capevolve.yaml`: the old spec, fully commented.
- `git -C sbv400-k02 diff 73103f429 HEAD --stat`: what changed in main (PR #914 and #907).

### 3.2 Fresh intake on the new code
Run the `intake` skill from `sbv400-k02/skills/phases/intake/` (SKILL.md) to scaffold a fresh project, in a scratch
dir such as `exp895/arms/capevolve_v2/intake_scratch/`, against the SpreadsheetBench adapter. The point is to pick
up the NEW template defaults: `templates/project/capevolve.yaml` and `templates/project/optimizer/INSTRUCTIONS.md`.

Then build `exp895/arms/capevolve_v2/template/.capevolve/project/` from that scaffold. Keep the new defaults, and
re-apply ONLY these exp895 experiment settings, each one justified in the old spec's comments:
- **Capability and seed:**
  - `capabilities: [system-prompt, skill-package]`
  - `capability_path: seed_capability_v2` (copy it from the old template: byte-identical)
- **Optimizer:**
  - `optimizer_skill: claude-code`
  - `optimizer_model: rits/zai-org/glm-5-3`
  - `optimizer_max_turns: 80`
  - `optimizer_usd_per_iter: 0`
  - `optimizer_instructions_file: <abs path to v2 template>/optimizer/INSTRUCTIONS.md`
  - `memory_skill: md-files` (or the new default, if the intake picks one; record which)
- **Data and trials:**
  - `target_model: google/gemma-4-31B-it`
  - `dataset_source: adapter`
  - `split_ids_file: split_ids.json` (copy; train = val = 120 ids, `test: []`)
  - `split_seed: 0`
  - `num_trials: 3`
  - `errored_trial_policy: fail`
- **Search and gate:**
  - `algorithm_skill: hill-climb`
  - `algorithm_focus: all`
  - `orchestration_mode: deterministic`
  - `store: copy`
  - `gate_mode: paired`
  - **`gate_k_se`: the new default, 0.2.** Leave the key at the template value. Do not override it to 0.5.
  - **`gate_footprint`: leave it absent, as the main default** (Osher's answer). Do not copy `false`.
- **Budget:**
  - `max_iterations: 1000`
  - `stall: 0`
  - `max_metric_calls: 2160`
  - `budget_reserve: true`
  - `finalize: false`
- **Helpers and surface:**
  - copy the whole `surface:` and `helpers:` blocks from the old spec;
  - re-point `ids_file` and `deny_roots` to the v2 paths;
  - `deny_roots` must include `sbv400-k02/third_party/spreadsheetbench/evaluation` and `exp895/data`.
- **Adapter files:** copy `adapters/adapter.py` and `adapters/model_config.py` from `sbv400-k02/templates/adapters/`.
  They match the old ones byte for byte; check with sha256. Also copy `all_task_ids.txt`.

Write a short `PROJECT.md` (the intake template) recording every value above, and which ones changed relative to
the `capevolve` arm. Any key you are unsure exists in this SHA: grep `sbv400-k02/core` and the skills for it,
as the old "spec-key audit" did.

### 3.3 Optimizer INSTRUCTIONS
The old arm used the old main's `INSTRUCTIONS.md`, with exp895's 77-line block
(`arms/capevolve/INSTRUCTIONS.exp895_addendum.md`) inserted right after the `{{BENCH_REPO}}` line. The block
contains the common surface contract, SpreadsheetBench facts, and "move procedure into code".

For v2:
- take the NEW `sbv400-k02/templates/project/optimizer/INSTRUCTIONS.md`;
- insert the same block right after its `{{BENCH_REPO}}` line (line 47 now);
- check every `{{PLACEHOLDER}}` is still present exactly once;
- record the sha256 of the result in PROJECT.md.

The surface contract must stay identical for every arm; that is why the block is kept.

### 3.4 Check and smoke (LSF only)
- `exp895/tools/lsf_capevolve_check.sh` exists for the old arm. Make a v2 copy that sources `node_env_k02.sh` and points at the v2 project. Run cap-evolve's own check and fix whatever it reports.
- Smoke one short search, for example `SEED=0 R=24 NAME=smoke_k02 MAX_ITERS=1 TRAIN_IDS=$EXP/arms/capevolve/smoke_train2.txt KEY_SLOT=2`, through `tools/lsf_exclusive_wrapper.sh tools/lsf_capevolve_v2_search.sh`. Then confirm:
  - `run_meta.txt` shows `code_sha` = the sbv400-k02 HEAD (0d791eeb7) and `key_slot=2`;
  - cap-evolve.log shows the gate running with k_se 0.2 and footprint at default;
  - the optimizer ran in the bwrap sandbox (`claude` resolves to `exp895/tools/sandbox/claude`) and produced a candidate;
  - `gw_gemma.log` and `calls_gemma.jsonl` exist, and the gateway `/healthz` reports `key_slot: "2"`.
- Then move the smoke dir aside (do not delete it) so `runs/capevolve_v2/` holds only real searches.

### 3.5 Launch the 3 seeds
One job per seed, each with a different key slot (§4), on dedicated hosts:
```
EXP=/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895
RES='^cccxc(6[0-3][0-9]|70[1247]|71[01]|535|575)$'
busy=$(bjobs -noheader -w -u $USER | awk '$7 ~ /^exp895_/ {split($6,a,":"); print a[1]}' | sort -u)
hosts=$(bhosts -w | awk 'NR>1 && ($2=="ok"||$2=="closed_Full") && $1 ~ /^cccxc/ {print $1}' | grep -v -E "$RES" | grep -v -x -F -f <(echo "$busy") | tr '\n' ' ')
bsub -q normal -n 2 -R 'span[hosts=1]' -M 64G -m "$hosts" -Q 99 -J exp895_capevolve_v2_s0 \
  -env "all,SEED=0,R=2160,NAME=search_s0,CONC=10,KEY_SLOT=2" \
  -oo $EXP/logs/capevolve_v2_s0.%J.out -eo $EXP/logs/capevolve_v2_s0.%J.err \
  bash $EXP/tools/lsf_exclusive_wrapper.sh $EXP/tools/lsf_capevolve_v2_search.sh
```
- Repeat for s1 and s2 with other slots.
- Rebuild `busy` and `hosts` between submissions, and `sleep 3`.
- The job name MUST start with `exp895_`: the host lock and busy-host filters rely on that prefix.
- Record the job IDs, hosts and key slots in `decisions.md`.

## 4. RITS keys (Boaz, 2026-10-25)
- **Where they are:** 6 extra keys in `~/secrets/rits_keys.env` (mode 600) as `RITS_API_KEY_1..6`. The original key is in `~/secrets/rits.env`. The source file `cap-evolve-spread-worktrees/rits_keys.txt` is now mode 600 too.
- **Never print, log or commit a key.** Refer to a key only by its slot number. The gateway reads keys into memory.
- **Key check** (`tools/keycheck/check_rits_keys.py`, job 330550):
  - current and slots 1, 2, 3, 5 and 6 work;
  - **slot 4 returns 403 "Authentication failed". Do not use slot 4.**
- **Load probe** (`tools/keycheck/key_load_probe.py`, job 331105), bursts of 16 short completions:

  | Burst | Wall time |
  |---|---|
  | current key | 168 s |
  | slot 2 | 133 s |
  | 8 + 8 split | 155 s |
  | 32 split over 2 keys | 121 s, all 200 |

  So a second key did not slow anything down, and 2N requests over 2 keys finished as fast as N over one. That suggests per-key limits exist and spreading keys helps. The test was small and noisy (median latency 2–5 s, tail 120–170 s, the same queueing as the main run), so treat it as "no harm, likely helps", not as a measured speed-up.
- **Suggested allocation:**
  - capevolve_v2 s0, s1, s2 → slots 2, 3 and 5;
  - slot 6 (and 1, which answered slowly) kept for capevolve_v2 test windows (`KEY_SLOT` env) or for the monitoring session to rebalance competitors.
  - Everything already running stays on the original key. Do not restart running jobs to move keys.

## 5. Coexistence rules with the monitoring session (MUST follow)
- **Job ownership:**
  - you act only on jobs named `exp895_capevolve_v2*` and your own setup and smoke jobs;
  - the monitoring session acts on all other `exp895_*` jobs, and will not touch `capevolve_v2`.
  - Same UID: **kill only by exact job ID**, never by pattern or name (a sibling session's kill once caught other jobs).
- **Shared files:** do not edit `tools/node_env.sh`, `tools/lsf_capevolve_search.sh`, the old `venv`, `sbv400-main`, or anything under `runs/` except `runs/capevolve_v2/`.
- **Shared tools:** `gateway.py`, `auto_test_launcher.py` and `lsf_test_window.sh` are shared. Change them only in a backward-compatible way, and log the change.
- **`decisions.md`:** append-only. Prefix each entry with `[v2-session]`.
- **The monitoring session's watcher** launches test windows. For capevolve_v2 it runs `lsf_test_window.sh`, which sources the OLD `node_env.sh`. The test-window adapter is byte-identical, so that is fine, but the helper-gate spec it passes is the OLD capevolve template. If you want v2 test windows to use the v2 spec and venv, make a `lsf_test_window_v2.sh` and tell Boaz. The monitoring session will then switch `auto_test_launcher.py` for that arm.
- **Standing rules:**
  - `-n 2` per search job; `-n 1` for single-eval jobs;
  - no `-W`;
  - dedicated host per podman job;
  - kill finished-but-hung jobs by exact ID once the log shows the end marker (`CAPEVOLVE_SEARCH_DONE` / `TEST_JOB_RC`);
  - artifacts go to the workarea, never `/tmp`;
  - install tools in the user env or venv, never rely on node OS packages;
  - `git commit -s` if you commit, and check CI before calling a PR done;
  - if in doubt, change nothing and ask Boaz.

## 6. Known issues you will meet
- **Gemma (RITS) is overloaded and degraded.** About 20 to 30 exp895 jobs share it. In bad stretches 20 to 100% of episodes end in infra errors, mostly `ReadTimeout` at the 90 s gateway limit, and episodes time out at about 1,800 s. CapEvolve drops infra trials as missing, never scored 0, and has not crashed so far.
- **Chronic slow tasks: 6239, 22-47, 398-14, 7902.** Their clean episodes take 1,600 to 6,500 s, so they hit the agent-call timeout often. They stopped GEPA s0 and s1 and WikiSkill s1 and s2, which are parked pending Boaz's decision. CapEvolve copes, but loses wall-clock time on them. Do NOT change the timeout for v2 without Boaz's approval: comparability with the old `capevolve` arm matters.
- **Finished-but-hung jobs.** A finished job can stay in RUN (podman daemons). The launcher kills them by pidfile, but check the log end marker and `bkill <exact id>` if needed.
- **Host collisions.** The exclusive wrapper exits 99 (requeue) if another exp895 job holds the host. That is normal.
- **Clock skew.** Compute-node clocks differ from login nodes by up to about 1.5 h. Don't trust file mtimes across hosts; use ledger timestamps.

## 7. Report back to Boaz
When the three seeds are running, send Boaz a short table:
- per seed: job ID, host, key slot, R, k_se, footprint;
- the spec diff vs the `capevolve` arm (key → old → new);
- the INSTRUCTIONS sha256;
- smoke evidence.

Then monitor your three jobs. When each one ends with `CAPEVOLVE_RC=0`, the monitoring session's watcher starts its test window automatically.
