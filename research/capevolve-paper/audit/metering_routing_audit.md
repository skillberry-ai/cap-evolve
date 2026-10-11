# Metering, routing and credential-exposure audit (E10 Suites A, B, C)

Auditor: metering-auditor. Snapshot: 2026-10-11 20:40 UTC. Read-only: no run was restarted or killed, no credential file was
opened, and every `*TOKEN*`/`*KEY*`/`*SECRET*` value seen in a process environment was reduced to `<REAL>` or `tag:<exp>`
before output. Reproduce the token numbers with `analysis/scripts/recover_bypassed_usage.py`.

## 0. Verdict

1. **No optimizer usage has bypassed the gateway. Missed tokens = 0, missed USD = 0.00** (19 runs reconciled, see section 2).
2. **The reported finding (0 optimizer calls for Suite A agent-optimize / evoskill / wikiskill, 4 for hill-climb) is expected, not a
   leak.** None of these four arms has reached its optimizer phase yet (section 1). The 4 hill-climb calls are the `s98` smoke test.
   The "3 candidates" in `agent-optimize/s0/.capevolve/run_*/candidates.jsonl` are three copies of the `seed` row written by the
   `make_candidates.py --loop 120` converter, not optimizer proposals (all three have `candidate_id=seed, parent_id=None`).
3. **Credential exposure is real in two places, neither of them the Claude-CLI arms:** the HarnessLens trial (OpenCode agent
   has the real `ANTHROPIC_AUTH_TOKEN` in its environment) and Trace2Skill's bash-tool analyst (real token in env and readable
   `~/.claude/settings.json`). Details in section 3, fixes in section 4.

## 1. Routing table (optimizer, proposer, reflection and judge calls)

"Ledger" = `campaign-scratch/logs/gateway_calls.jsonl`, role = 4th field of the tag `tag:<exp>-<arm>-s<seed>:<arm>:<role>`.

### Suite A (SpreadsheetBench; target gemma-4-31B; scoring is programmatic, so there is no judge role)

| arm | role | intended route | actual route | evidence |
|---|---|---|---|---|
| hill-climb | optimizer | `claude` on PATH is `_tools/shim/claude` -> `sudo -u capopt env -i` -> gateway, tag `$E10_TAG:optimizer` | **not started** (baseline phase, 76/600 rollouts). Route proven by smoke `s98` | `logs/hc.out`, `host.out` absent; baseline `run.py` pid 3742067 alive with PATH0=`_tools/shim`; no `/tmp/e10-opt-hill-climb-s{0,1,2}` homes (shim creates one on first call); ledger `E10-hill-climb-s98:...:optimizer` = 4 calls and equals the `/tmp/e10-opt-hill-climb-s98` transcript exactly (in 6, out 171, cr 45406, cc 22934); `negtest.txt` PASS (settings.json denied) |
| agent-optimize | optimizer (host.py -> run-optimizer `claude-code`) | same shim | **not started** (baseline `run.py` pid 3742071 alive, 70/600 rollouts; no `host.out`; `baseline.json` empty) | same as above; `run_ao.sh` exports `PATH=shim:$PATH` before baseline so host.py inherits it; `run-optimizer/scripts/run.py` resolves `claude` with `shutil.which` (PATH lookup, so the shim wins) |
| evoskill | proposer + generator (claude CLI via claude-agent-sdk) | `evo_bin/claude` -> `sudo` -> private mount ns -> `runuser capopt env -i`, key = tag from `ANTHROPIC_API_KEY`, base URL forced to 127.0.0.1:4111 | **not started**: baseline evaluation (34/40 in `launcher.log`), `candidates.jsonl` empty, no proposer call in ledger | `evoskill_run.py:42-45` sets `ANTHROPIC_BASE_URL=http://127.0.0.1:4111`, `ANTHROPIC_API_KEY=tag:...:optimizer`, `PATH=evo_bin:`; shim refuses non-`tag:` keys (exit 97); ledger has only `:evoskill:target` (559/545/563 calls) |
| wikiskill | maintainer / proposer | `openai.OpenAI(base_url=GATEWAY, api_key=tag:...:optimizer)` in-process tool loop (read_file, finish) | **not started**, no optimizer call yet | `community_run.py:157`; ledger only `:wikiskill:target` (779/802/763) |
| gepa | reflection | gepa_run.py -> gateway | gateway | ledger `E10-gepa-s{0,1,2}:...:reflection` 6/2/8 calls |
| skillopt | optimizer | `OPTIMIZER_OPENAI_COMPATIBLE_*` -> gateway tag | gateway | `skillopt_run.py:43-46`; ledger 19/20/20 calls |
| metaharness | proposer (claude CLI) | `sb/shim/claude` -> rootless podman, only workspace + claude binary mounted, env `ANTHROPIC_AUTH_TOKEN=tag:...:proposer` | gateway | `mh_sb_run.py:210-215`; ledger `E10-metaharness-s*:...:proposer` 9/10/9 calls with cache tokens (CLI signature) |
| trace2skill | optimizer (official ReAct analyst + evolver, OpenAI client) | `--base_url GW --api_key tag` | gateway | `t2s_run.py:115`; ledger 372/371/374 calls |
| ace | reflector, curator | gateway | gateway | ledger 19-24 calls each per seed |
| mipro | proposer | gateway | gateway | ledger 27 calls per seed |

### Suites B (tau2 retail) and C (tau2 airline)

Optimizer `claude` is `runs/E10B/_sbx_bin/claude` (first on PATH), a rootless mount-namespace sandbox that forwards only
`ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY` (must be `tag:`), `CAPEVOLVE_*`, `TAU*`, etc., and sets
`CLAUDE_CONFIG_DIR=<run>/claude_cfg`, `HOME=/tmp/home`. Live check on the running optimizer CLIs (pids 271011, 337019, 714809,
3455892, 3455993, 3459010): `ANTHROPIC_BASE_URL=http://127.0.0.1:4111`, `ANTHROPIC_API_KEY=tag:E10x-<arm>-s<k>...`, no
`ANTHROPIC_AUTH_TOKEN`, private `CLAUDE_CONFIG_DIR`, own mount and user namespaces.

| arm | role | intended route | actual route | evidence |
|---|---|---|---|---|
| hc (B, C) | optimizer | sandbox shim -> gateway | gateway | ledger optimizer calls B: 71/101/53, C: 22/15/16; transcripts reconcile (section 2) |
| ao (B, C) | optimizer | sandbox shim -> gateway | gateway | B: 149/145/176, C: 34/44/21 |
| ctl-oneshot (B, C) | optimizer | sandbox shim -> gateway | gateway | B: 53/65/45, C: 20/21/25 |
| gepa (B, C) | reflection | `gepa_tau.py` / `tau_lib.GATEWAY` | gateway | B: 10/11/10 calls, C: 1/1/2 (C is early) |
| all CapEvolve B arms, gepa B | judge (NL assertions, `TAU_JUDGE_MODEL=openai/azure/gpt-5.5`) | gateway | gateway | `:judge` rows for every B tag (ao 106/87/81, hc 120/125/115, gepa 84/77/77, ctl 82/86/87, ctl-seed, chaser) |
| all C arms | judge | none: airline reward has no LLM judge | n/a | `build_cap_project.py` (C) facts: "no LLM judge"; no `E10C-*:judge` rows is correct |
| harnesslens trial (B, `E10B-hl-trial-s9`) | optimizer (OpenCode agent + Sonnet role sessions), usersim | `DEEPSEEK_BASE_URL=http://127.0.0.1:4111/v1`, `DEEPSEEK_API_KEY=tag:E10B-hl-trial-s9` | gateway | live opencode pid 1983539 env; ledger `:harnesslens:optimizer` 14, `:usersim` 74, `:target` 153 |

## 2. Quantification of missed usage

Method: sum de-duplicated (by `message.id`) assistant `usage` from the Claude CLI session transcripts of each run, compare with the
ledger's optimizer rows for the same exp-arm-seed tag, bypass = max(0, transcript - ledger) per token class, priced at
`protocol/pricing.json` aws/claude-sonnet-5-5 ($2 in / $10 out / $0.20 cache-read / $2.50 cache-write per Mtok, proxy list price).
Output: `analysis/out/metrics/bypassed_usage.csv`.

| group | transcript vs ledger | bypassed tokens (in/out/cache_read/cache_creation) | USD |
|---|---|---|---|
| Suite C (9 runs) | identical to the token; ledger has exactly 1 extra call per run (a background/title call that is not written to the transcript) | 0 / 0 / 0 / 0 | 0.00 |
| Suite B (9 runs) | ledger is 20-60 percent **larger** than the transcripts (for example B ao-s0: transcript cache_read 8.82M, ledger 10.99M; 119 transcript messages vs 149 ledger calls) | 0 / 0 / 0 / 0 | 0.00 |
| Suite A smoke s98 | identical (4 calls) | 0 | 0.00 |
| Suite A hill-climb, agent-optimize s0-s2, evoskill, wikiskill | optimizer has not run: no capopt home, no `host.out` / `hc.out`, no proposer call | n/a (nothing to miss) | 0.00 |
| default `~/.claude/projects` sessions rooted in `campaign-scratch/runs` | none exist (5 project dirs, none for campaign runs) | 0 | 0.00 |

The Suite B surplus runs in the safe direction (ledger over-counts relative to transcripts), so it cannot hide spend. Probable
causes, not verified: CLI retries and compaction/sub-agent requests that are billed by the gateway but not persisted, and earlier
sessions of the same tag before `claude_cfg` was reset (`repair_ao.sh` documents a config correction and restart). It is a
cost-table accuracy question for the metrics owner, not a metering gap. Note also that the transcript check cannot see a process that
bypassed AND wrote no transcript; for that case the evidence is the live environments below (no Claude-CLI arm has a path to the real endpoint).

## 3. Credential exposure: can the tool subprocesses of each agentic optimizer see the real `ANTHROPIC_AUTH_TOKEN`?

Real token = value that does not start with `tag:`. Method: `/proc/<pid>/environ` (redacted), mount/user namespace comparison,
the launchers, and a probe from a fresh `unshare --user --map-root-user --mount` namespace that `/proc/<ancestor>/environ`
(the parents `run.py`, `host.py`, which do hold the real token) is not readable from a sandbox-style namespace.

| arm | agentic optimizer with shell/tools | sees real token? | evidence |
|---|---|---|---|
| Suite A hill-climb, agent-optimize (when they start) | claude CLI as uid `capopt` | **No** | shim uses `sudo -u capopt env -i`, forwards only `CAPEVOLVE_*`/eval socket; token = tag; HOME and CLAUDE_CONFIG_DIR private; different uid so parent `/proc/*/environ` unreadable; `negtest.txt` PASS (settings.json denied). Parents (`run.py`, `host.py`, daemons) do hold the real token, but they are not the agent |
| Suite A evoskill | claude CLI via claude-agent-sdk | **No** | `evo_bin/claude`: private mount ns with empty `/home` and `/tmp`, `runuser capopt env -i`, tag-only; `negtest_before_launch.txt`: settings.json "denied/absent" |
| Suite A metaharness | claude CLI in rootless podman | **No** | podman mounts only workspace + claude binary; passes only `ANTHROPIC_BASE_URL` and `ANTHROPIC_AUTH_TOKEN` (set to a tag in `mh_sb_run.py:211`) |
| Suite A wikiskill | tools are `read_file` / `finish` over staged files, no shell | n/a (no shell). The Python process itself holds the real token, but the agent cannot reach it | `community_run.py` RoleTools |
| Suite A gepa, skillopt, ace, mipro | plain chat completions, no tools | n/a | launchers |
| **Suite A trace2skill** | official error-analysis agent with a **bash tool** (`spreadsheet_agent/tools/bash.py`: `subprocess.run(command, shell=True)`, no `env=`) | **Yes** | `t2s_run.py:53` builds `envsub = dict(os.environ, ...)` and the bash tool inherits the parent's environment; pid 1640281 has the real `ANTHROPIC_AUTH_TOKEN` and the real `ANTHROPIC_BASE_URL`; runs as uid dev, `HOME=/home/dev`, so `~/.claude/settings.json` (mode 644) is also readable. Mitigating: I searched the s0 `error_analysis`/`success_analysis` transcripts for `printenv`, `settings.json`, `ANTHROPIC`, `/proc/..environ` and found no access (the only `environ` hits are the word "environment"); s1 and s2 were not searched with the same depth beyond the first pass that returned no hits. The analysis stages are finished (`evolve_*.done`), so the running processes are past the exposed phase |
| Suites B, C hc / ao / ctl-oneshot | claude CLI in `_sbx_bin` sandbox | **No** | live env of the CLIs has no `ANTHROPIC_AUTH_TOKEN`; `/home/dev` in the namespace contains only `projects2`; `negtest_output.txt` and `E10C/negtest_hc.txt`: settings.json denied; probe from a fresh user ns: parent `/proc/*/environ` not readable. Parents (`run.py` 271000 etc.) hold the real token, outside the sandbox |
| **Suite B harnesslens trial** | OpenCode agent (`--auto`, shell) inside `hl_sandbox.sh` | **Yes (environment)** | pid 1983539 and its parents carry `ANTHROPIC_AUTH_TOKEN` (real) and `ANTHROPIC_BASE_URL=https://ete-litellm...` (real gateway). `hl_sandbox.sh` ends in `exec "$@"` with no env scrub, so OpenCode's shell tool can `env`/`printenv` it. The filesystem part is sound (own mount ns, `/home/dev` is tmpfs, `/home/dev/.claude` absent), so `settings.json` is **not** readable |

## 4. Recommended fixes, ranked by cost

1. **Zero cost, no restart: nothing to recover.** `recover_bypassed_usage.py` reports 0 bypassed tokens and $0.00. Optionally add it
   to `analysis/scripts/refresh_metrics.sh` so any future bypass shows up in `bypassed_usage.csv` and can be added to the cost tables
   (it already prices each row from `pricing.json`).
2. **Zero cost, next invocation only: Suite A hill-climb / agent-optimize / evoskill / wikiskill need no change.** The route is
   proven by the s98 smoke test and the shims; they will be metered when the baseline phase ends. Keep the token watchdog (it keys
   on `$E10_TAG:optimizer`). Suggested spot check for the team lead: when the first Suite A optimizer call arrives, confirm that the
   ledger count for `E10-hill-climb-s0:hill-climb:optimizer` increases and that `/tmp/e10-opt-hill-climb-s0/.claude/projects` appears.
3. **Cheap, applies to the next HarnessLens run (do not restart the trial that is mid-call):** replace `exec "$@"` in
   `baselines/harnesslens/tau/hl_sandbox.sh` with
   `exec env -u ANTHROPIC_AUTH_TOKEN -u ANTHROPIC_BASE_URL -u ANTHROPIC_API_KEY "$@"` (or an `env -i` allowlist with PATH, HOME,
   `DEEPSEEK_*`, `HL_*`, `HAI_*`, `OPENCODE_*`, `XDG_*`, `TB_*`, `PYTHONPATH`) and add `ANTHROPIC_AUTH_TOKEN` to `negtest.sh`
   (check `env | grep -c AUTH_TOKEN`). The final HL seeds have not started (only `s9`), so this costs one edit.
4. **Cheap, Trace2Skill:** only needed if trace2skill is ever re-run. Pass `env={"PATH":..., "HOME":"/tmp/t2s", "OPENAI_*": tag}` to
   the bash tool's `subprocess.run`, or run the analysis stage through the capopt shim. For the current s0-s2 runs, the analysis
   stages are done; a scan of the agent logs for `printenv`/`env`/`settings.json` commands in s1 and s2 would close the question.
5. **Hygiene, moderate:** the real gateway token has been in the environment of long-lived dev-uid processes and in the HL trial's
   agent environment. If the team lead judges the HL trial agent could have printed it, rotate the token after the campaign; this
   costs a credential change, not compute. A restart is **not** required for any finding in this audit.

## 5. Open items

- Suite B ledger vs transcript surplus (20-60 percent) is unexplained; harmless for budgeting (over-counts).
- The trace2skill s1/s2 agent logs were only grepped, not read.
- The OpenCode session store of the HL trial (XDG_DATA_HOME of that run) was not searched for env-dumping commands.
- Claude sessions of this research team (uid dev, default config) are not in the campaign ledger by design; they are out of scope.

## 6. Error-label parity across arms (uniform infra/candidate classifier)

**Reporting is unified; search-time handling is not.** Every method's search-time feedback used that method's native handling of
errors (what it scored, retried, showed to its proposer, or dropped), exactly as published or as adapted for the campaign. That
stays a property of the method and is not changed or re-run. The uniform classifier below is applied only when the campaign metrics
and the final report count infrastructure versus candidate failures (analysis_plan.md section 6, R14). It never feeds back into a search.

Rule, implemented once in `analysis/scripts/collect_metrics.py` (`uniform_class`) and applied to every arm and suite:
- **infra**: the rollout has a transport, timeout or sandbox-HTTP error string (timeouts, connection errors, 429/5xx, "sandbox exec
  failed", "infrastructure", gateway/upstream), OR it made zero target-LLM calls and carries an error whose text the adapter did not keep.
- **candidate**: any other failure or error (including an error with a recorded non-infra string).
- blank: no error and reward >= 1.

Two refinements the rule needs, both visible in the data:
1. A recorded non-infra string wins over the zero-call test. SkillOpt's 120 "candidate" zeros (s0 80, s2 40) have 0 turns and
   0 target calls, but the per-step `results.jsonl` string is "task_template.md broke the placeholder contract": the candidate
   was invalid before any LLM call. A pure zero-calls rule would have turned these into infra; they stay candidate.
2. Error strings are recovered where they exist outside the metrics rows: SkillOpt (per-step `results.jsonl`), Trace2Skill
   (`pool.jsonl`, matched by task id, one-to-one), ACE and MIPROv2 (`events.jsonl` `err`), plus the capevolve rollout JSON.

Outputs (columns in `rollout_metrics.csv`: `error_kind_adapter` = original label, `error_class_uniform`, `error_rule_uniform`,
`error_text`; `error_kind` now carries the uniform class for rows that have an error): `analysis/out/metrics/error_label_parity.csv`
(per arm, seed, category) and `error_label_parity.md`. Totals across live seeds (counts are rollouts with an error):

| arm | errors | adapter label (infra / candidate) | uniform (infra / candidate) | candidate -> infra | infra -> candidate | note |
|---|---|---|---|---|---|---|
| Trace2Skill | 27 | 0 / 27 | 26 / 1 | **26** | 0 | the 1 left has no pool string and an unknown call count |
| WikiSkill | 8 | 0 / 8 | 8 / 0 | **8** | 0 | S0 (seed) rows, zero calls, no string; the seed cannot break its own template |
| Meta-Harness | 30 | 30 / 0 | 27 / 3 | 0 | 3 | 3 have no string and unknown call count |
| SkillOpt | 147 | 27 / 120 | 27 / 120 | 0 | 0 | 120 are candidate by recorded string |
| ACE | 2 | 2 / 0 | 2 / 0 | 0 | 0 | from event strings |
| MIPROv2 | 7 | 7 / 0 | 7 / 0 | 0 | 0 | from event strings |
| GEPA (A) | 7 | 7 / 0 | 0 / 7 | 0 | 7 | no string, unknown call count |
| CapEvolve hc / ao, EvoSkill (A) | 10 / 7 / 5 | all infra | hc 7/3, ao 5/2, evoskill 5/0 | 0 | hc 3, ao 2 | 0-call rows kept infra |
| Suites B, C (hc, ao, ctl-oneshot) | 10 B + 2 C ctl | all infra | see CSV | 0 | a few | B rows with calls > 0 and no string |

Open decision for the owner of R14: 18 rows are labelled infra by their adapter but have no error string and either more than zero or an
unknown number of target calls (GEPA 7, Meta-Harness 3, hc 3, ao 2, ctl-oneshot 3; column `adapter_infra_unverifiable`). The
rule as specified counts them as candidate. If the tau2/GEPA/Meta-Harness raw logs can supply the string, rerun `refresh_metrics.sh --once`;
the column `error_rule_uniform=adapter_infra_unverifiable` marks exactly these rows.
