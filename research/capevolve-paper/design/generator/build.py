"""Build /home/dev/projects2/campaign-scratch/design/experimental_design.html (v2). Run: cd scripts/design_v2 && PYTHONPATH=. python3.12 build.py"""
import json
import os
import re

import cards
import est
import live
from h import callout, card, chip, h2, h3, kv, md, p, pend, table, ul

ROOT = live.ROOT
PAPER = "/home/dev/projects2/cap-evolve-campaign/research/capevolve-paper"
V1 = open(f"{ROOT}/design/experimental_design.v1.html").read()
HEAD = open(f"{ROOT}/scripts/design_v2/head_v1.html").read()
NOW = live.NOW


def v1sec(sid):
    m = re.search(r'<section id="%s">.*?</section>' % sid, V1, re.S)
    return m.group(0)


def sub(s, a, b, count=1):
    assert a in s, f"missing in v1 section: {a[:80]}"
    return s.replace(a, b, count)


EXTRA_CSS = """
<style>
.card { border: 1px solid var(--rule); background: var(--surface); margin: 12px 0 16px; }
.card > summary { cursor: pointer; padding: 10px 14px; font-weight: 600; background: var(--surface-2); border-bottom: 1px solid var(--rule); display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: baseline; }
.card > summary .ct { font-family: var(--font-head); font-size: 17px; margin-right: 6px; }
.card:not([open]) > summary { border-bottom: none; }
dl.kv2 { display: grid; grid-template-columns: minmax(140px, 220px) minmax(0, 1fr); margin: 0; }
dl.kv2 > dt, dl.kv2 > dd { margin: 0; padding: 7px 14px; border-bottom: 1px solid var(--rule); font-size: 14.5px; }
dl.kv2 > dt { font-size: 13px; font-weight: 600; color: var(--muted); }
dl.kv2 > dd { overflow-wrap: anywhere; }
dl.kv2 > dt:nth-last-of-type(1), dl.kv2 > dd:last-of-type { border-bottom: none; }
.cardnote { margin: 0; padding: 8px 14px; border-top: 1px solid var(--rule); color: var(--muted); font-size: 14px; }
@media (max-width: 620px) { dl.kv2 { grid-template-columns: 1fr; } dl.kv2 > dt { border-bottom: none; padding-bottom: 0; } }
dl.kv { overflow-wrap: anywhere; }
.stat { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0; border: 1px solid var(--rule); background: var(--surface); margin: 10px 0 16px; }
.stat > div { padding: 10px 14px; border-right: 1px solid var(--rule); border-bottom: 1px solid var(--rule); }
.stat b { display: block; font-size: 24px; font-family: var(--font-head); font-variant-numeric: tabular-nums; }
.stat span { font-size: 12.5px; color: var(--muted); }
.ctrl { display: flex; gap: 8px; margin: 8px 0; flex-wrap: wrap; }
.ctrl button { font: inherit; font-size: 13px; padding: 4px 10px; border: 1px solid var(--rule); background: var(--surface); color: var(--ink); cursor: pointer; }
.ctrl button:hover, .ctrl button:focus-visible { border-color: var(--accent); outline: none; }
.chip.planned { color: var(--planned); }
</style>
"""

NAV = [
    ("status", "Live status board"), ("deviations", "Running vs frozen design"), ("summary", "Decision table"),
    ("rq", "Research questions"), ("budget", "Budget"), ("gateway", "Gateway and admission"), ("models", "Model cards"),
    ("suite-a", "Suite A design"), ("suite-b", "Suite B design"), ("tiers", "Arms, tiers, tracks"),
    ("cards-a", "Config cards: Suite A"), ("cards-b", "Config cards: Suite B"), ("prs", "CapEvolve PRs"),
    ("failed", "Failed reproductions"), ("search", "Per-search budget, rule P"), ("final", "Final campaign"),
    ("transfer", "Transfer"), ("ablations", "Ablations, improvements"), ("controls", "Measurement controls"),
    ("stats", "Statistics and MDE"), ("estimates", "Estimates and 72 h fit"), ("cost", "Cost accounting"),
    ("registry", "Experiment registry"), ("integrity", "Defect map"), ("incidents", "Isolation incidents"),
    ("timeline", "Decision timeline"), ("diagram", "Dependencies"), ("pending", "Pending decisions"), ("sources", "Sources"),
]


def nav():
    li = "".join(f'<li><a href="#{i}">{md(t)}</a></li>' for i, t in NAV)
    return f'<nav class="toc" aria-label="Contents"><details open><summary class="toc-label">Contents</summary><ol>{li}</ol></details></nav>'


def status_counts():
    a = live.board_a()
    running = sum(1 for r in a if "running|running" in r[3])
    stopped = sum(1 for r in a if "stopped" in r[3])
    pending = sum(1 for r in a if "pending|pending" in r[3])
    b = live.board_b()
    runningb = sum(1 for r in b if "running|running" in r[2])
    return running, stopped, pending, runningb


def sec_top():
    ts = NOW.strftime("%Y-%m-%d %H:%M UTC")
    run_a, stop_a, pend_a, run_b = status_counts()
    hl = live.HEALTH or {}
    capped = hl.get("capped_tokens")
    rits = hl.get("rits_tokens")
    calls = hl.get("calls")
    s = ['<header class="top"><div class="eyebrow">Experimental design, version 2 with live status</div>',
         "<h1>CapEvolve Experimental Design</h1>",
         p("This page is the detailed design of the CapEvolve paper campaign: what is frozen, what is running, the full configuration of every arm, the measured cost of a rollout, and the estimates that follow from it. Values come from files in the campaign repository and scratch store, cited by path. A value that no file states is written as not recorded. Forecasts are arithmetic on measured inputs and are labelled."),
         f'<div class="meta"><span>generated {ts} (host clock)</span><span>campaign capevolve-paper-20261011</span><span>campaign ends 2026-10-14 00:05 UTC</span><span>dev window ends 2026-10-13 06:05 UTC</span></div>',
         '<div class="stat">',
         f"<div><b>{run_a}</b><span>Suite A arm-seeds running</span></div>",
         f"<div><b>{run_b}</b><span>Suite B arm-seeds running</span></div>",
         f"<div><b>{est.HRS_LEFT:.0f} h</b><span>wall clock left</span></div>",
         f"<div><b>{(capped or 0)/1e6:.2f}M</b><span>non-RITS tokens used of 100M cap</span></div>",
         f"<div><b>{(rits or 0)/1e6:.0f}M</b><span>RITS tokens used, uncapped</span></div>",
         f"<div><b>{calls or 0:,}</b><span>gateway calls logged</span></div>",
         "</div>",
         p("Note on clocks: decisions.md entries carry the coordinator's timestamps. Some are later than the host clock at generation time, so times in the decision timeline are quoted as written and not reconciled."),
         "</header>"]
    return "".join(s)


def sec_status():
    out = [h2("status", "Live status board", f"State at {NOW.strftime('%Y-%m-%d %H:%M UTC')}. Rollout counts come from each arm's counter file; PIDs from ps. ETAs divide the remaining planned rollouts by the arm's average rate since launch. They are forecasts, they ignore queueing changes as more arms start, and they are likely optimistic.")]
    out.append(h3("Suite A: SpreadsheetBench, Gemma-4-31B-it"))
    rows = live.board_a()
    out.append(table(["Arm", "Seed", "Tier", "Status", "PID", "Rollouts started", "Budget", "% of budget", "Rollouts per h", "ETA to planned use (forecast)"],
                     rows, caption="Rollouts started = the arm's hard counter (rollouts begun, including in-flight). CapEvolve rows count completed rollouts in `logs/rollouts.jsonl`. Planned use differs from budget for GEPA 555, EvoSkill 568, Trace2Skill 200, MCE 560. Stopped rows: capacity tiering, not outcome.",
                     num=(5, 6, 7, 8), raw=False))
    out.append(h3("Suite A arms not yet launched"))
    out.append(table(["Arm", "Tier", "Planned", "State"], [list(r) for r in live.A_NOT_LAUNCHED], wide=(3,)))
    mp = live.pids_for("mipro_run.py")
    if mp:
        out.append(p(f"MIPROv2 smoke process PID {mp[0][0]} is still running; RHO smoke PID {', '.join(str(x[0]) for x in live.pids_for('rho_sb_run.py')[:1]) or 'not found'}."))
    out.append(h3("Suite B: tau2 retail, gpt-oss-120b"))
    out.append(table(["Arm", "Seed", "Status", "Driver PID", "Counter / log", "Rollouts (est.)", "Budget", "% of budget", "Rollouts per h", "ETA (forecast)"],
                     live.board_b(), caption="Estimated rollouts = gateway calls for the arm's tag divided by 17.2 calls per rollout (measured in the pilots). Exact counters exist only for GEPA (batches started) and ctl-seed (log). hc, ao and ctl-oneshot have no counter file; their numbers are estimates. All hc/ao/one-shot seeds are still in the 49-task seed baseline.",
                     num=(5, 6, 7, 8)))
    out.append(h3("Superseded, stopped and smoke runs"))
    out.append(table(["Run", "State", "Why", "Evidence"], [
        ["Meta-Harness first launch (proposer as uid dev, gold readable)", "[[planned|superseded]]", "stopped 09:38 before any proposer iteration", "`runs/E10/superseded/metaharness-gold-readable-20261011/NOTE.txt`"],
        ["EvoSkill launch 1 (3 seeds, about 09:43)", "[[planned|superseded]]", "stopped for the Tier-2 hold; no proposer sessions", "`runs/E10/evoskill/s*_stopped_tier_hold_1009`"],
        ["EvoSkill launch 2 (concurrency 12)", "[[planned|superseded]]", "stopped after minutes; concurrency set to 4", "`runs/E10/evoskill/s*_infra_restart_conc12`"],
        ["GraphSkillEvo s1, s2", "[[planned|stopped]]", "capacity tiering (decided 09:00, not outcome-driven); 6 and 5 rollouts", "`runs/E10/graphskillevo/s{1,2}/STOPPED.json`"],
        ["MCE s1, s2", "[[planned|stopped]]", "capacity tiering; stopped 09:41:27/28 at 5 rollouts", "`runs/E10/mce/s{1,2}/STOPPED.json`"],
        ["Memento-Skills s1, s2", "[[planned|stopped]]", "capacity tiering; stopped 09:54:18/20 at 4 rollouts", "`runs/E10/memento/s{1,2}/STOPPED.json`"],
        ["hill-climb s99", "[[running|smoke]]", "30-rollout smoke with a 5-task val; running 3,200+ s without leaving the baseline, occupies capacity", "`runs/E10/hill-climb/s99/`"],
        ["pilot_ao s0 (Suite B)", "[[running|pilot]]", "still running; 26 metric calls, has proposed `cand_1`", "`runs/E10B/pilot_ao/s0/`"],
        ["pilot_hc s0, pilot_gepa s0 (Suite B)", "[[done|finished]]", "pilots: hc rejected both candidates (seed selected, sel 0.6); gepa best_idx 0 (identical to the seed)", "`runs/E10B/pilot_*`"],
    ], wide=(2, 3)))
    out.append("</section>")
    return "".join(out)


def sec_deviations():
    rows = [
        ["Suite B NL-assertion judge", "decisions.md: `azure/gpt-5.5` for every arm", "running arms judge with `rits/openai/gpt-oss-120b-a100` (adapter default `TAU_JUDGE_MODEL`; no env file overrides it; gateway log shows judge calls to gpt-oss, one gpt-5.5 probe only)", "[[pending|decision needed]] fix and relaunch, or accept and disclose. 29 of the 74 train tasks (opt 20, sel 9) carry NL assertions"],
        ["Suite B CapEvolve gate", "10:25 parity: both arms judge through rule P (k_se 1, n_conf 3, dmin 0.02, z_conf 2.0, min coverage 0.95, footprint off, joint coverage)", "hc: footprint off, joint coverage 0.95, no confirmation stage, no rule P; ao: stock `reward_gated`, footprint on. Code is wt-tau `fdc31881c` (pre-fix #779 only; no #783, #786, #788, #790). Launched 09:40-09:43", "[[pending|decision needed]] relaunch with parity while the seed baselines are 5% done, or label as pre-parity"],
        ["Suite B budget", "600 rollouts per search", "CapEvolve arms `max_metric_calls 550` (about 564 with finalize); GEPA 600", "[[pending|decision needed]] align or disclose"],
        ["Suite A CapEvolve gate", "10:25 parity: both arms through rule P module", "s0 started 10:04 from wt-run `f5906110b` (#779 + #783 only). hc: ad hoc rule P in `hc_paper.py`, n_conf 3. ao: stock `reward_gated`. Per 10:25 the running ao s0 becomes the E12 stock-gate reference", "main seeds (s0 redo, s1, s2) [[pending|pending]] launch under the merged #786 module"],
        ["analysis_plan section 8", "n_conf >= 10 fresh trials", "decisions.md 10:25 sets n_conf 3 for all CapEvolve arms", "[[pending|decision needed]] record as a deviation in the plan before freeze"],
        ["Optimizer isolation of CapEvolve arms", "every agentic proposer under a separate uid or container with a negative test before launch", "Suite A CapEvolve: uid `capopt` shim, no negative-test result on file for them. Suite B CapEvolve: uid `dev`, no uid separation, no negative test. MCE and RHO: no result on file", "[[pending|decision needed]] run and record negative tests before results count"],
        ["Rollout cost assumption", "09:00 decision: about 12 calls per rollout, 300 rollouts/h, 18k Suite A rollouts in about 60 h", f"measured now: {est.A_CALLS:.1f} calls and {est.A_TOK/1000:.1f}k tokens per started rollout (GEPA, SkillOpt, Trace2Skill pooled, {est.A_ROLL_BASIS} rollouts); Gemma {est.G30:.1f} calls/min over the last 30 min and {est.G120:.1f} over 2 h, so {est.A_RATE_LO:.0f} to {est.A_RATE_HI:.0f} rollouts/h", "forecasts below use the measured rates"],
        ["Remaining world-readable split files", "10:00 host fix removed other-read from `*split*.json`", "124 files were still world-readable when checked: 120 in `wt-e05`, 2 `splits.json` under the new HC/AO s0 `.capevolve` dirs, 2 `split_tasks.json` under harnesslens trees. Whether capopt can traverse `/home/dev` was not confirmed", "[[pending|decision needed]] re-run the chmod and the capopt check"],
        ["Stale text in deviations files", "deviations files describe the run", "`deviations_gepa.json` and `deviations_skillopt.json` say as-saved reward but the launcher uses `hard_restriction`; `deviations_metaharness.json` describes the pre-09:42 unisolated proposer", "correct before the competitor tables are written"],
        ["Provenance coverage", "all competitors pinned", "`PROVENANCE.json` covers only GEPA and SkillOpt. EvoSkill commit SHA is not recorded; Trace2Skill, Meta-Harness, GraphSkillEvo, MCE, Memento, RHO, ACE, WikiSkill, AHE, HarnessLens are pinned only in deviations files", "complete before the competitor tables are written"],
    ]
    return (h2("deviations", "Running configuration vs the frozen design", "Differences found by reading the run files. None is resolved by this page; each needs a decision (see the last section).")
            + table(["Item", "Frozen design", "What the files show", "Status"], rows, wide=(1, 2, 3)) + "</section>")


def sec_summary():
    rows = [
        ["Research questions RQ1-RQ5", "unchanged", "[[frozen|frozen]]"],
        ["Budget", "RITS uncapped, metered; non-RITS 100M tokens ex cache reads and $1000; 72 h; 25% reserve", "[[frozen|frozen]]"],
        ["Capacity decision (09:00)", "tiers: Tier 1 (3 seeds x 600) HC, AO, GEPA, SkillOpt, Meta-Harness, WikiSkill; Tier 1-cheap Trace2Skill, ACE, MIPROv2; Tier 2 (1 seed, exploratory) the rest; EvoSkill promoted to Tier 1 at 09:55", "[[frozen|frozen]]"],
        ["Suite A", "SpreadsheetBench verified-400, SkillOpt split, LO 25.8 recalculated reward, gold-free sandbox (#783 merged), Gemma-4-31B-it, 30 turns", "[[frozen|frozen]]"],
        ["Suite A fresh final set and size T", "candidates: 912 residual (lightly exposed) or SpreadsheetBench 2; T sized to at most 25% of capacity", "[[pending|pending]]"],
        ["Suite B", "tau2 retail @8ebb7499, gpt-oss-120b target and simulator, opt 49 / sel 25 (seed 42), test 40 sealed", "[[frozen|frozen]]"],
        ["Suite B judge, gate parity, budget", "see running vs frozen design", "[[pending|pending]]"],
        ["Optimizer", "Claude Sonnet 5.5 via gateway for all matched arms; proxy $2 / $10 per MTok", "[[frozen|frozen]]"],
        ["Promotion", "rule P (k_se 1, n_conf 3, dmin 0.02, z_conf 2.0, min coverage 0.95, footprint off, joint coverage) for both CapEvolve arms; competitors native", "[[frozen|frozen]]"],
        ["CapEvolve PRs", "#779, #783, #786, #788, #790 merged into the campaign branch; #791 merged", "[[done|done]]"],
        ["Algorithm improvements", "shared rule P module, interaction-aware merge, screen accounting: merged, default off, ablations only", "[[frozen|frozen]]"],
        ["Final campaign", "scored once, interleaved, one window; Suite A n=2, Suite B n=4; one shared baseline per suite", "[[frozen|frozen]]"],
        ["Ablations on Suite A", "limited to what Tier 1 runs already log plus at most one 3-seed ablation; others on Suite B or dropped", "[[frozen|frozen]] rule<br>[[pending|pending]] choice"],
        ["Failed reproductions", "VERSE, CoEvoSkills, HarnessLens on Suite A; RHO if blocked", "[[frozen|frozen]]"],
        ["Wall time", "does not fit at the measured rate (see estimates)", "[[pending|pending]]"],
    ]
    return h2("summary", "Decision table", "What is frozen, what is pending.") + table(["Item", "Design", "Status"], rows, wide=(1,), raw=False).replace("&lt;br&gt;", "<br>") + "</section>"


def sec_rq():
    s = v1sec("rq")
    return sub(s, "E04 to E07 (IDs proposed)", "E04 to E07")


def sec_budget():
    caps = live.jload(f"{ROOT}/logs/caps.json") or {}
    c = caps.get("concurrency", {})
    rows = [
        ["RITS-served target tokens", "uncapped", "user decision 2026-10-11; metered and reported"],
        ["All other tokens", "100M", "uncached input + output + cache-write; Anthropic cache reads are recorded and priced but excluded; OpenAI-style prompt tokens counted in full, cached or not"],
        ["Spend", "$1000", "proxy price for Sonnet; RITS and gpt-5.5 unknown, never $0"],
        ["Wall", "72 h", "start 2026-10-11 00:05 UTC, end 2026-10-14 00:05 UTC"],
        ["Reserve", "25%", "the last 18 h are for final evaluation and analysis; dev window ends 2026-10-13 06:05 UTC"],
        ["Rollout cap", "10,000 in campaign.yaml", "fallback from the mandate; superseded in practice by the uncapped-RITS decision. Whether it still applies is " + "[[pending|pending]]"],
        ["Per-search budget", "600 target rollouts, at most 4M non-cache-read optimizer tokens", "frozen 2026-10-11; hard counters per arm (see cards)"],
    ]
    return (h2("budget", "Budget", "Source: campaign.yaml, decisions.md.") + table(["Limit", "Value", "Rule"], rows, wide=(2,))
            + "</section>")


def sec_gateway():
    caps = live.jload(f"{ROOT}/logs/caps.json") or {}
    conc = caps.get("concurrency", {})
    last, r = est.last, est.rates
    g30 = r[("google/gemma-4-31B-it", 30)]; g120 = r[("google/gemma-4-31B-it", 120)]
    o30 = r[("openai/gpt-oss-120b-a100", 30)]; o120 = r[("openai/gpt-oss-120b-a100", 120)]
    h = live.HEALTH or {}
    out = [h2("gateway", "Gateway and admission control", "Single path for every model call: `experiments/tooling/campaign_gateway.py`, 127.0.0.1:4111. Live limits from `logs/caps.json` (re-read every 30 s).")]
    out.append(table(["Upstream (semaphore key)", "Live concurrency", "Wire route"], [
        ["`rits:google/gemma-4-31B-it`", str(conc.get("rits:google/gemma-4-31B-it")), "RITS alias `google-gemma-4-31b-it-a100`"],
        ["`rits:openai/gpt-oss-120b-a100`", str(conc.get("rits:openai/gpt-oss-120b-a100")), "RITS alias `gpt-oss-120b-a100`"],
        ["`rits:Qwen/Qwen3.6-35B-A3B`", str(conc.get("rits:Qwen/Qwen3.6-35B-A3B")), "RITS alias `qwen3-6-35b-a3b-a100`"],
        ["`litellm` (all gateway models)", str(conc.get("litellm")), "LiteLLM gateway; `/v1/messages` passed through verbatim for Claude Code"],
    ], num=(1,), caption="Code defaults are 4 per RITS deployment and 8 for litellm. decisions.md records the raises: Gemma 12 -> 32, gpt-oss 12 -> 24, Qwen 8, gateway 16."))
    out.append(h3("Rules"))
    out.append(ul([
        "**Routing:** a model id starting with `rits/` goes to the RITS deployment with the RITS key header; everything else goes to the LiteLLM gateway with a bearer key. Credentials are never logged.",
        "**Metering tag:** the bearer token or `x-api-key` is read; if it starts with `tag:` it is the call's tag, format `tag:<exp>:<arm>:<role>`, otherwise `untagged`.",
        "**Budget guard:** once `capped_tokens` reaches `max_nonrits_tokens_ex_cache_read` (100,000,000) every call gets HTTP 429 naming the cap. Counting uses `total_tokens` when usage has it (OpenAI shape), else input + output + cache-creation (Anthropic shape), so cache reads are excluded. RITS tokens are added to `rits_tokens` and never capped. The ledger is rebuilt from the call log on restart.",
        "**Retries and timeouts:** the gateway does no retries; upstream timeout 900 s; a transport exception returns 502.",
        "**Log fields** (`logs/gateway_calls.jsonl`): `t` (UTC, written at call end), `tag`, `model`, `upstream`, `api`, `stream`, `status`, `queue_s`, `latency_s`, `usage` (raw upstream object), `error` (first 300 chars).",
        f"**Live health:** capped (non-RITS) tokens {h.get('capped_tokens', 0):,} of 100,000,000; RITS tokens {h.get('rits_tokens', 0):,}; {h.get('calls', 0):,} calls; blocked = {h.get('blocked')}.",
    ]))
    out.append(h3("Priority design (staged, not deployed)"))
    out.append(p("`logs/caps.json` already carries `reserve_high` (Gemma 24, gpt-oss 12) and `low_priority_tags` (substring match on the tag: smoke, probe, E10-memento, E10-ahe, E10-mce, E10-rho, E10-evoskill, E10-harnesslens, E10-verse, E10-graphskillevo, E10-coevo). In the staged build a low-priority caller may only use slots beyond max(1, limit - reserve_high), so Tier 1 gets the reserved slots first. The staged build also binds with `SO_REUSEPORT` so a later restart can drain gracefully."))
    out.append(p("The running process (PID 1292380, started about 08:20) holds the pre-09:18 code and ignores both settings. `scripts/campaign_gateway.py` on disk is already the staged build. Restarting the old process would drop about 30 in-flight Gemma calls, because it cannot drain. Deploying the build is " + "[[pending|pending]]" + " (see decisions)."))
    out.append(h3("Measured saturation"))
    out.append(table(["Deployment", "Window", "Calls", "Calls per min", "Errors", "Latency p50 / p95 (s)", "Queue mean (s)"], [
        ["Gemma-4-31B-it", "last 30 min", str(g30['n']), f"{g30['cpm']:.1f}", str(g30['err']), f"{g30['p50']:.0f} / {g30['p95']:.0f}", f"{g30['qmean']:.0f}"],
        ["Gemma-4-31B-it", "last 120 min", str(g120['n']), f"{g120['cpm']:.1f}", str(g120['err']), f"{g120['p50']:.0f} / {g120['p95']:.0f}", f"{g120['qmean']:.0f}"],
        ["gpt-oss-120b", "last 30 min", str(o30['n']), f"{o30['cpm']:.1f}", str(o30['err']), f"{o30['p50']:.1f} / {o30['p95']:.1f}", f"{o30['qmean']:.0f}"],
        ["gpt-oss-120b", "last 120 min", str(o120['n']), f"{o120['cpm']:.1f}", str(o120['err']), f"{o120['p50']:.1f} / {o120['p95']:.1f}", f"{o120['qmean']:.0f}"],
    ], num=(2, 3, 4, 6), caption=f"Window ends at the last logged call, {last} UTC. Queue = time waiting for a gateway semaphore (queue_s)."))
    out.append(table(["20-min bin (start UTC)", "Gemma calls/min", "Gemma in-flight", "Gemma mean queue (s)", "Gemma p50 latency (s)", "gpt-oss calls/min", "gpt-oss in-flight", "gpt-oss mean queue (s)"], [
        ["08:16", "45.4", "13.0", "5.6", "16.6", "8.2", "1.6", "0"],
        ["08:36", "37.2", "30.8", "20.2", "44.4", "16.4", "3.2", "0"],
        ["08:56", "31.0", "32.5", "59.3", "55.4", "22.1", "4.6", "0"],
        ["09:16", "25.8", "30.7", "71.9", "72.1", "26.1", "5.9", "0"],
        ["09:36", "26.0", "32.2", "97.0", "66.3", "105.4", "19.6", "22.3"],
        ["09:56", "26.2", "32.3", "116.3", "68.3", "119.8", "24.0", "32.6"],
    ], num=(1, 2, 3, 4, 5, 6, 7), caption="Measured by a read-only analysis of gateway_calls.jsonl at 10:16 UTC (in-flight = sum of latency / bin length). Gemma sits at its 32-slot limit and throughput fell from 45 to about 26 calls/min as concurrency rose: the only Gemma-it deployment (six other aliases probed, all 404) is saturated and extra slots add queue and latency. gpt-oss latency stays near 9 s while calls/min scales, so its bottleneck is the 24-slot gateway semaphore, not the server."))
    out.append(p("The 09:00 decision measured 50 to 60 Gemma calls/min at lower concurrency. The recent log shows 26 to 29. The difference is not explained by the files read."))
    out.append("</section>")
    return "".join(out)


def sec_models():
    rows = [
        ["Gemma-4-31B-it", "RITS, alias `/google-gemma-4-31b-it-a100`", "`rits/google/gemma-4-31B-it`", "`google/gemma-4-31B-it`", "262,144", "Suite A target: temperature 0.0, `max_tokens` 8000, 30 turns, rollout seed 0, no reasoning effort", "unknown (tokens metered)"],
        ["gpt-oss-120b", "RITS, alias `/gpt-oss-120b-a100`", "`rits/openai/gpt-oss-120b-a100`", "`openai/gpt-oss-120b-a100`", "40,144", "Suite B target, user simulator, and currently the judge: temperature 0.0, `max_tokens` 8000, `max_steps` 100, `max_errors` 10, `reasoning_effort` unset (provider default)", "unknown"],
        ["Qwen3.6-35B-A3B", "RITS, alias `/qwen3-6-35b-a3b-a100`", "`rits/Qwen/Qwen3.6-35B-A3B`", "`Qwen/Qwen3.6-35B-A3B`", "262,144", "transfer target; thinking model that emits reasoning tokens; not used in any E10 run", "unknown"],
        ["GPT-5.5", "LiteLLM gateway", "`azure/gpt-5.5`", "not recorded", "not recorded", "intended Suite B NL judge and transfer target. tau2's `model_config` pins temperature for gpt-5 models, so no temperature is sent. Judge role not wired in the running arms", "unknown"],
        ["Claude Sonnet 5.5", "LiteLLM gateway (Anthropic passthrough for Claude Code)", "`aws/claude-sonnet-5-5`", "not recorded", "not recorded", "optimizer for all matched arms. Claude Code: `optimizer_max_turns` 80 (hc, Suite A), 300 (ao, Suite B), no temperature or effort flag recorded. GEPA reflection `max_tokens` 16000; SkillOpt optimizer temperature 0.7, `max_tokens` 16000; MIPROv2 proposer `max_tokens` 8000; Meta-Harness `--effort high`", "proxy only: $2 in / $10 out per MTok, cache read $0.20, cache write 5 min $2.50 (`protocol/pricing.json`, Anthropic list price)"],
    ]
    return (h2("models", "Model cards", "Sources: `protocol/model_registry.json` (status PROVISIONAL), `protocol/pricing.json`, adapters and runner scripts. The tau2 default NL judge `gpt-4.1` is not served by the gateway (403 'team not allowed'). aws/gpt-oss-120b on the gateway is a different serving stack and is never mixed with the RITS deployment.")
            + table(["Model", "Provider route", "Wire id", "Served id", "Max context", "Decoding and roles as configured", "Price"], rows, wide=(5, 6), mid=(0, 1)) + "</section>")


def sec_suite_a():
    s = v1sec("suite-a")
    s = sub(s, "Patch landed: <span class=\"chip pending\">pending</span>", "Patch landed: <span class=\"chip done\">done</span>, PR #783 merged 09:23 (<span class=\"mono\">6f9278025</span>), 20/20 isolation tests including the live podman sandbox test; safe default <span class=\"mono\">AGENT_VIEW=1</span>")
    s = sub(s, "The patch (<span class=\"src\">patches/adapter_gold_dir.patch</span> by bench-steward) gives", "PR #783 gives")
    return s


def sec_suite_b():
    s = v1sec("suite-b")
    # replace judge dd and work-list
    a = s.index("<dt>Judge</dt>")
    b = s.index("<dt>Editable surfaces</dt>")
    judge = ("<dt>Judge</dt><dd>Frozen: <span class=\"mono\">azure/gpt-5.5</span> grades NL assertions for every arm (deviation from the unavailable tau2 default gpt-4.1; gpt-oss is already target and simulator, self-leniency risk). Judge verdicts are stored per assertion for a later sensitivity sample. "
             "<strong>Running arms use gpt-oss as judge</strong> (see running vs frozen design). 29 of the 74 train tasks have NL assertions.</dd>\n    ")
    s = s[:a] + judge + s[b:]
    a = s.index("<h3>Work the audit says retail needs</h3>")
    b = s.index("</section>")
    work = ("<h3>Adapter status</h3><ul>"
            "<li>The retail adapter exists: <span class=\"mono\">wt-tau/examples/tau2_retail/adapters/adapter.py</span> (domain parameterized, seed capability, <span class=\"mono\">pregate_toolkit</span>). The evaluator replays tool calls on the pristine toolkit. Fault-injection test E05: <span class=\"chip pending\">planned</span></li>"
            "<li>Sealed test: the adapter raises <span class=\"mono\">RuntimeError</span> on any official-test id; test ids are not written into the project. Splits: <span class=\"mono\">wt-tau/protocol/tau_retail_splits.json</span> sha256 <span class=\"mono\">07d013b7bd0116...</span>.</li>"
            "<li>Adapter settings differ from tau2 defaults: <span class=\"mono\">max_steps=100</span> (default 200), <span class=\"mono\">max_errors=10</span>, simulator timeout 7200 s. These are disclosed in every Suite B table.</li>"
            "<li>The user simulator is an LLM, so noise is high; the audit expects retail not to certify +0.02 effects, as for airline.</li>"
            "<li>Retail exposure check: audit found no recorded CapEvolve exposure; off-repo use cannot be seen. <span class=\"chip pending\">pending</span> confirmation.</li></ul>")
    s = s[:a] + work + s[b:]
    return s


def sec_tiers():
    out = [h2("tiers", "Arms, tiers and tracks", "Capacity-driven scope decision, 2026-10-11 09:00, fixed before any search outcome was seen: the only Gemma-4-31B-it RITS deployment saturates, so the full roster (about 70k Suite A rollouts at the time) cannot run. EvoSkill was promoted to Tier 1 at 09:55 before any result.")]
    out.append(table(["Tier", "Rule", "Methods (Suite A)"], [
        ["Tier 1", "3 seeds x 600 rollouts, matched, headline, Holm family", "CapEvolve hill-climb, CapEvolve agent-optimize, GEPA, SkillOpt, Meta-Harness, WikiSkill (community implementation), EvoSkill"],
        ["Tier 1-cheap", "3 seeds, native budget <= 600 (usually far less); actual rollouts reported; budget is a cap", "Trace2Skill (about 200), ACE, MIPROv2"],
        ["Tier 2", "1 seed, <= 600, labelled EXPLORATORY, never in the Holm family or headline tables; launched only as capacity frees; promoted to 3 seeds only if capacity remains after Tier 1 completes, by capacity and never by the seed-0 result", "GraphSkillEvo, MCE, Memento-Skills, RHO, AHE, HarnessLens (blocked on A), VERSE and CoEvoSkills (failed reproductions)"],
        ["Controls", "reported in the matched table", "unoptimized seed; one-line compliance instruction (A); one-shot repair; matched-budget best-of-K"],
        ["Context only", "published numbers in the external-context table, never in matched tables", "SkillSmith, MESH-Harness, EvoTool, HarnessEvolve, Mixture of Self-Improving Branches, SBCO, DarwinX, AutoSaddler (code not released)"],
        ["Out of scope", "cited as prior art (different editable object, very high cost)", "DGM, HGM, SICA, Hyperagents, ADAS, AFlow. ActiveSaddler only if a curriculum claim is made"],
    ], wide=(1, 2)))
    out.append(h3("Tracks"))
    out.append(ul([
        "**Matched algorithm track:** same editable surface, models, feedback, evaluator and budget. GraphSkillEvo is the exception, run on the PRACTICAL track because it starts from its upstream `init_skill.md` rather than the shared seed.",
        "**Practical track:** each method in its native design, same total budget.",
        "**Disclosed data-exposure difference:** stock CapEvolve hill-climb and agent-optimize use VAL traces as optimizer feedback and VAL for gating (train-80 is never shown; D03). Competitors use train-80 feedback and val-40 selection. CapEvolve sees 40 tasks' traces, competitors see 80 plus 40. Recorded per run and discussed as a native-design difference.",
        "**Suite B roster:** CapEvolve hc and ao, GEPA, controls (seed, one-shot), plus MIPROv2, ACE, HarnessLens (prepared) and Meta-Harness if adaptable. SkillOpt, EvoSkill, Trace2Skill, CoEvoSkills, GraphSkillEvo, VERSE and WikiSkill are Suite A only.",
    ]))
    out.append(h3("Controls on Suite A and B"))
    out.append(table(["Control", "Definition", "Suites"], [
        ["Unoptimized seed", "the starting artifact; one shared measurement per suite serves every contrast", "A, B"],
        ["Compliance instruction", "one line: write literal values, recalculate. Tests how much of a gain is scorer compliance", "A"],
        ["One-shot repair", "a single optimizer proposal. Suite B: hill-climb with `max_iterations 1`, candidate selected unconditionally (`collect_cap.py` picks `cand_0001`); Suite A: from train failures (not launched)", "A, B"],
        ["Matched-budget best-of-K", "K one-shot proposals, choose on val; K " + "[[pending|pending]]" + " (depends on rollouts per proposal)", "A, B"],
    ], wide=(1,)))
    out.append("</section>")
    return "".join(out)


def sec_cards_a():
    out = [h2("cards-a", "Configuration cards: Suite A", "One card per method, from the run directories, launchers, adapters and deviations files. 'not recorded' means no file states the value. State fields are on the status board.")]
    out.append('<div class="ctrl"><button type="button" onclick="document.querySelectorAll(\'details.card\').forEach(function(d){d.open=true})">Expand all cards</button><button type="button" onclick="document.querySelectorAll(\'details.card\').forEach(function(d){d.open=false})">Collapse all cards</button></div>')
    out.append(cards.suite_a_common())
    out.extend(cards.suite_a_cards())
    out.append("</section>")
    return "".join(out)


def sec_cards_b():
    out = [h2("cards-b", "Configuration cards: Suite B", "tau2 retail, gpt-oss-120b. Sources: `runs/E10B/*`, `scripts/E10B/`, `/home/dev/projects2/wt-tau`.")]
    out.extend(cards.suite_b_cards())
    out.append("</section>")
    return "".join(out)


def sec_prs():
    out = [h2("prs", "CapEvolve code changes", "All PRs target the campaign branch `research/capevolve-paper-20261011`, none main. Merges use `gh pr merge --admin` under the repository's standing bypass for non-main branches; the main ruleset is never bypassed. Commits carry DCO sign-offs.")]
    out.append(table(["PR", "Purpose", "Merge commit", "Merged (UTC)", "Tests"], [
        ["#779", "paper-mode switches", "`b6ac28477c86`", "09:11", "18 new tests; core 2258 passed, 6 skipped, 2 unrelated pre-existing failures; coordinator re-ran 30/30 plus 315 gate/harness tests. Two independent review rounds (first: REQUEST CHANGES)"],
        ["#783", "gold isolation (#782)", "`6f9278025f4e`", "09:23", "20/20 isolation tests incl. live podman sandbox; safe default `AGENT_VIEW=1`; allowlist assertion; symlink refusal; rmtree guard. `runmeta.json` field patch not applied (push token lacks `workflow` scope; patch at `bench/patches/workflow_runmeta_gold_field.patch`)"],
        ["#786", "shared promotion rule P module", "`7883107b2091`", "09:35", "20 new tests; coordinator re-ran 330"],
        ["#788", "interaction-aware merge verification", "`cbdb3cf9030f`", "10:05 (decisions.md: 10:20)", "29 new tests; coordinator ran 441"],
        ["#790", "screen accounting", "`d8851c811`", "10:10 (decisions.md: 10:20)", "16 new tests; coordinator ran 428; trivial rebase over #788"],
        ["#791", "gate replay on historical artifacts", "`fbe754dd9637`", "10:21:59", "3 tests; byte-identical regeneration, md5 `e1c38c59...`"],
    ], wide=(1, 4)))
    out.append(h3("Spec keys, defaults and campaign values"))
    out.append(table(["Key", "PR", "Code default", "Campaign value"], [
        ["`gate_footprint`", "#779", "true (mask to the edit footprint; gepa never masks)", "false for rule P arms; E10B hc: false; E10 pilots: not set"],
        ["`gate_coverage`", "#779", "`candidate` (alternative `joint`)", "`joint`"],
        ["`gate_min_coverage`", "#779", "0.6 (0 disables)", "0.95 in E10B hc"],
        ["`errored_trial_policy`", "#779", "`drop` (alternative `fail`: scores adapter-tagged candidate errors 0.0)", "not set in any spec read"],
        ["`gate_no_regression`, `gate_max_broke`", "#779", "not enabled", "not set"],
        ["`confirm_fresh_only`", "#779", "off", "true in E10 agent-optimize s0 and E10B ao"],
        ["`promotion_rule: P`", "#786", "off", "required by the 10:25 decision; not present in any spec read"],
        ["`promotion_k_se`, `promotion_n_conf`, `promotion_dmin`, `promotion_z_conf`, `promotion_min_coverage`", "#786", "1.0, 10, 0.02, 2.0, 0.6", "1, 3, 0.02, 2.0, 0.95 (decisions.md 10:25)"],
        ["`merge_verify`", "#788", "off (code defaults `min_block` 5, `max_rounds` 3, pass at z >= 1.645)", "off (ablation only)"],
        ["`screen_accounting`; options `--accounting`, `--affected`, `--sentinels`, `--k-random`, `--screen-control random_subset`", "#790", "off", "off (ablation only)"],
        ["step-event fields `delta_full`, `delta_masked`, `se_full`, `se_masked`, `joint_coverage`", "#779", "always written", "available for the E11 footprint analysis"],
    ], wide=(0, 2, 3), caption="Campaign values for rule P come from decisions.md 10:25; no spec file read contains `promotion_*` keys. That is a pending item (see running vs frozen design)."))
    out.append(h3("Gate replay on historical artifacts (PR #791): preliminary, descriptive"))
    out.append(p("Source: `analysis/out/replay_gates.md` on branch `research/algo-p4-replay-gates`. Scope: 19 runs, 96 replayable decisions (67 hill-climb, 21 pre-metadata exports, 8 agent-optimize). The runs are replicates, not independent samples. Test deltas are from exposed (dev-exposed) test sets. No uncertainty is attached."))
    out.append(table(["Rule replayed", "Accepts", "Differ from recorded"], [
        ["recorded", "33", "-"], ["unmasked k=1", "23", "10"], ["k=0.2", "38", "7"], ["k=0.3", "36", "7"], ["reward_gated, reward stage only", "10", "23"],
    ], num=(1, 2)))
    out.append(ul([
        "**Champion path under unmasked k=1:** survives in 10 runs (mean test delta +0.3552) and is blocked in 6 of 16 runs (test deltas +0.033 to +0.298, mean +0.1717). Stricter gates also forfeit real gains. k=0.2 blocks 1 run, k=0.3 blocks 2, reward_gated blocks 12 of 16. Group means are not rule effects.",
        "**Not replayable:** rule P's confirmation stage (no fresh-trial re-measurement exists); footprint sets (no traces), so masking is only inferred; per-candidate test deltas.",
        "**Corrections after review (decisions.md 10:30 and 10:40):** all 4 recorded-vs-unmasked mismatches in historical hill-climb decisions are dropped-task cases (n=39 vs 40). The artifacts contain no evidence of footprint masking. The earlier wording that run `37204406089` cand_0005 was 'manufactured by footprint masking' is withdrawn: one task with delta -1 was dropped from the gated vector and the artifacts do not show why. Footprint-masking claims rest on code (D01) and simulation only.",
    ]))
    out.append("</section>")
    return "".join(out)


def sec_failed():
    rows = [
        ["VERSE (wzekai/VERSE @d8ff0adab0cf, MIT)", "A and B", "FAILED REPRODUCTION, not launched", "Its executor and all verification tools (replay, ablate, substitute, attribute, trace minimisation, step certificates) re-run recorded bash commands in SWE-rebench or Terminal-Bench containers; SpreadsheetBench is a Jupyter code-block loop in podman. Only `fix_probe` maps; a port that drops the rest is a reimplementation (paper ablation attributes 2.2 of about 4 points to attribution and minimisation). Budget: about 170 rollouts per round, paper runs 1,300-1,450 agent runs per search (Table 4). Endpoint plumbing is not the blocker", "attempts: read driver, executor, probes, attribute, intervener, edit_spaces, workspace, configs; model calls 0; cost 0", "`baselines/verse/blocker.json`"],
        ["CoEvoSkills (Zhang-Henry/CoEvoSkills, Apache-2.0; arXiv 2604.01687)", "A", "FAILED REPRODUCTION, not run", "The official loop is a Harbor Terminus-2 agent inside a per-task Docker container with a per-task surrogate verifier and ground-truth oracle (up to 5 iterations); the released setting is per-task and has no shared-skill counterpart over 80 train tasks, so what the verifier checks and how skills persist would be newly designed (a reimplementation). Requires harbor@3f28e5ce and Docker task packages. Cost: a handful of tasks would exceed the 4M-token cap. The only non-Claude oracle route is terminus-2, a different agent from the CapEvolve spreadsheet agent", "reading only; no rollouts or optimizer tokens; a Harbor dependency install probe was started (`coevo_dl/venv`, `pip_install.log`)", "`baselines/coevoskills_blocker.json`"],
        ["HarnessLens (jhxu5214/HarnessLens @369a5c8c7856, MIT)", "A blocked; B prepared", "BLOCKED on Suite A; Suite B native", "It evolves the user-configurable state of an existing coding-agent runtime (OpenCode / Codex CLI / Pi); every role runs through that runtime. Benchmarks are cells (tau2 retail/banking, Terminal-Bench 2.0, BIRD). SpreadsheetBench with the CapEvolve code-block loop is neither a supported cell nor harness; adding it means a new benchmark driver and harness adapter in a 31k-line codebase", "read README, architecture, configuration, benchmarks, cell_config, main_agent; model calls 0; cost 0", "`baselines/harnesslens/blocker_suiteA.json`; Suite B: `baselines/harnesslens/tau/`"],
        ["RHO (wbopan/retro-harness @e5f2d1a8a06a, MIT)", "A", "NOT blocked at this time; smoke only", "Needs the Codex CLI through our Responses-to-Chat shim and a namespace mask. Smoke PID " + (", ".join(str(x[0]) for x in live.pids_for("rho_sb_run.py")[:1]) or "not found") + "; one smoke rollout ended 'sandbox exec failed: 500'; no isolation negative-test result", "smoke counter 6/12 at last read", "`baselines/rho/deviations.json`; no blocker file"],
        ["AHE (MIT, @8b2a55d97590)", "A", "NOT adapted", "no adapter, deviations or smoke result", "-", "no blocker file"],
    ]
    return (h2("failed", "Failed and blocked reproductions", "Reported with attempts, errors and cost, never dropped silently (decisions.md 2026-10-11).")
            + table(["Method", "Suite", "Status", "Reason", "Attempts and cost", "Blocker file"], rows, wide=(3, 4), mid=(0,)) + "</section>")


def sec_search():
    out = [h2("search", "Per-search budget and promotion rule P")]
    out.append(p("Each search gets **600 target rollouts on dev data** (every evaluation counts, including screens, confirmations and the initial baseline) plus **at most 4M non-cache-read optimizer tokens**, seeds 0, 1 and 2, optimizer and reflection model `aws/claude-sonnet-5-5` for all matched arms. Enforcement is by hard counter per arm (see cards). Suite B CapEvolve arms run 550 plus finalize (about 564) and GEPA 600 (pending alignment)."))
    out.append(h3("Rule P (decisions.md 10:25; analysis_plan section 8; #786)"))
    out.append(table(["Parameter", "Value", "Source"], [
        ["promotion_rule", "P", "10:25 gate parity"],
        ["screen", "paired gate `promotion_k_se` = 1 on the full unmasked delta vector (`gate_footprint false`, `gate_coverage joint`)", "analysis_plan section 8"],
        ["confirmation", "fresh trials (new seeds) of candidate and incumbent on the same val tasks, `promotion_n_conf` = 3 per task (analysis plan says >= 10)", "decisions.md 10:25"],
        ["promote iff", "mean delta >= `promotion_dmin` 0.02 and delta / SE_paired >= `promotion_z_conf` 2.0", "analysis_plan section 8"],
        ["`promotion_min_coverage`", "0.95 (module default 0.6)", "decisions.md (#786 entry)"],
        ["agent-optimize", "keeps its stock ablation vector and `confirm_fresh_only`", "10:25"],
        ["competitors", "native acceptance rules, reported as such", "frozen"],
    ], wide=(1, 2)))
    out.append(table(["Rule (T=40, screen n=5, 10 iterations)", "P(at least 1 false promotion)", "Power at +0.08", "Power at +0.10"], [
        ["one-stage k_se=1", "0.57", "0.85", "0.92"], ["rule P (z=2.0, dmin 0.02, 10 confirm trials)", "0.037", "0.68", "0.87"],
    ], num=(1, 2, 3), caption="analysis/out/sim_promotion.md. The simulation used 10 confirmation trials; the campaign uses 3, whose operating characteristics are not in the simulation table (n_conf 5 gives 0.089 false promotion at z=1.645). Re-run before freeze."))
    out.append("</section>")
    return "".join(out)


def sec_final():
    return v1sec("final")


def sec_transfer():
    return h2("transfer", "Transfer") + p("Frozen Suite A artifacts are evaluated without re-optimization on Qwen3.6-35B-A3B (RITS, its own deployment, concurrency 8, reasoning tokens inflate cost) and GPT-5.5 (gateway, price unknown), on the Suite A final set, plus SpreadsheetBench 2 (deterministic categories, 297 tasks, rev `5a2215ed`) if available. Every transfer evaluation includes the seed on the same model. The smaller-optimized vs larger-unoptimized comparison (Gemma champion vs unoptimized GPT-5.5 seed) is in tokens and wall time per task because both prices are unknown.") + callout("Pending", ul([
        "which artifacts transfer: all frozen artifacts is up to 37 (see estimates), a subset (seed plus the best champion per method) is cheaper",
        f"GPT-5.5 rollouts count against the 100M non-RITS cap: at {est.A_TOK/1000:.0f}k tokens per rollout (unmeasured for GPT-5.5) the remaining cap allows about {int((100e6 - (live.HEALTH or {}).get('capped_tokens', 0))/est.A_TOK):,} rollouts in total, shared with every optimizer",
        "SpreadsheetBench 2 needs a new adapter, a one-time partition with the digest committed, and a larger turn budget",
    ])) + "</section>"


def sec_ablations():
    out = [h2("ablations", "Ablations and CapEvolve algorithm improvements", "Development data only, equal budgets. Capacity rule (09:00 decision): Suite A ablations are limited to those reusable from Tier 1 runs (footprint and gate statistics already logged as delta_full / delta_masked) plus at most one 3-seed ablation; the others move to Suite B (separate gpt-oss deployment) or are dropped and listed.")]
    out.append(table(["ID", "Ablation", "Compares", "Suite and cost", "Status"], [
        ["E11", "footprint masking on/off", "uses logged `delta_full` vs `delta_masked` from Tier 1 hill-climb steps; no extra rollouts. Historical artifacts show no masking evidence, so the claim rests on code and simulation", "A, 0 extra rollouts", "[[planned|planned]]"],
        ["E12", "gate: one-SE vs rule P, with improvement 1 (shared rule-P module)", "the running stock-gate agent-optimize s0 is the reference arm", "A, 1 seed already running", "[[running|reference running]]"],
        ["E13", "DAG vs single lineage (agent-optimize)", "`dag_parallel` true vs false", "Suite B or dropped", "[[pending|pending]]"],
        ["E14", "merge none / naive / verified / interaction-aware (improvement 2, #788)", "`smart_merge`, `merge_verify`", "Suite B or dropped; 1 arm x 3 seeds x 550 = 1,650 rollouts each", "[[pending|pending]]"],
        ["E15", "`active_eval` + screen accounting + random-subset control (improvement 3, #790)", "`active_eval`, `screen_accounting`, `--screen-control random_subset`", "Suite B or dropped; 2 to 3 arms", "[[pending|pending]]"],
        ["E16", "surface width: prompt-only vs tools-only vs prompt+tools", "per-surface budget reported (budget-splitting hazard)", "B, 2 added arms x 3 x 550 = 3,300 rollouts", "[[planned|planned]]"],
        ["E17", "optimizer mechanics 2x2 (output guard x delegation), Gemma optimizer", "lowest priority; first to cut", "A, 7,200 rollouts if 4 arms x 3 x 600", "[[pending|likely dropped]]"],
    ], wide=(1, 2, 3)))
    out.append(h3("CapEvolve algorithm improvements (merged, default off)"))
    out.append(table(["#", "Improvement", "PR", "Addresses", "Switch"], [
        ["1", "promotion rule P as a shared module used by both algorithms", "#786", "gate-strictness confound between hill-climb (effective bar about 0.04) and agent-optimize (about 0.085, #760)", "`promotion_rule: P`"],
        ["2", "interaction-aware merge verification: common-ancestor blocks, interaction delta(A+B) - delta(A) - delta(B), delta-debugging on failure", "#788", "the c_win merge failure (pooled delta -0.0146, SE 0.0181, z -0.81; raw blocks not committed)", "`merge_verify`"],
        ["3", "screen accounting: predicted + sentinel + random exploration tasks with recorded inclusion probabilities, plus an equal-size random-subset control", "#790", "bias of adaptive subset triage (S1; HarnessLens is the competitor)", "`screen_accounting`, `--screen-control random_subset`"],
    ], wide=(1, 3)))
    out.append(p("All three are merged into the campaign branch and default off. Main E10 CapEvolve arms use rule P through the existing runner paths (hill-climb confirmation stage; agent-optimize via `confirm_fresh_only`); the module only packages it, and any behavioral difference is labelled. A winning improvement is reported as an improvement and re-run as a separate arm."))
    out.append("</section>")
    return "".join(out)


def sec_controls():
    s = v1sec("controls")
    s = sub(s, "<caption>E04 to E07 are proposed IDs. The brief fixes the experiment list but not these numbers. <strong>Pending:</strong> confirm IDs.</caption>", "<caption>IDs E04 to E07 confirmed in decisions.md. Sizes pending.</caption>")
    return s


def sec_stats():
    s = v1sec("stats")
    s = sub(s, "The table has no row for the designed Suite A final (T about 150, n=2) or Suite B (T=40, n=4).", "The table has no row for the Suite A final (T about 40 to 70 now fits, n=2; see estimates) or Suite B (T=40, n=4).")
    return s


def sec_cost():
    s = v1sec("cost")
    a = s.index("<p><strong>Bound on optimizer spend")
    b2 = s.index("</section>")
    new = ("<p><strong>Optimizer spend: bound and measured.</strong> One search at the 4M-token ceiling costs between $8 (all input at $2/MTok) and $40 (all output at $10/MTok). The pilot mix is far from either end: pilot_hc spent about $0.54 for 136k non-cache-read tokens (cache writes and reads dominate), about $3.95 per MTok. At that mix a ceiling search is about $16 and a 10-iteration Claude-Code hill-climb about $2.7. Non-RITS spend so far is about $2.2 proxy across E10 and E10B. The $1000 cap does not bind at the forecast; the 100M-token cap binds only if most searches reach the ceiling. Competitor optimizer spend per search is not recorded yet.</p>\n")
    return s[:a] + new + s[b2:]


def sec_estimates():
    rows = est.estimate_rows()
    out = [h2("estimates", "Estimates and the 72 h fit", f"All numbers are forecasts computed from measured per-rollout costs. Gemma Suite A rollouts are taken at {est.A_CALLS:.1f} calls and about {est.A_TOK/1000:.0f}k tokens each, not the 41k of one task in version 1.")]
    out.append(h3("Inputs"))
    out.append(table(["Input", "Value", "Basis"], [
        ["Suite A tokens per started rollout", f"{est.A_TOK:,.0f}", f"GEPA, SkillOpt and Trace2Skill target-role tokens (prompt + completion) divided by their {est.A_ROLL_BASIS} started rollouts, from gateway_calls.jsonl and the counters. Started rollouts include in-flight partial calls, so this is approximate. Per method: GEPA 50.9k, SkillOpt 52.8k, Trace2Skill 50.1k, Meta-Harness 56.9k (relaunch only)"],
        ["Suite A calls per started rollout", f"{est.A_CALLS:.1f}", "same basis; the 09:00 note assumed about 12"],
        ["Suite B tokens per rollout", "80,000", "coordinator figure; pilots measured 71k to 83k (pilot hc 75.5k and 17.2 calls, pilot gepa 83k and 17.1 calls)"],
        ["Suite B calls per rollout", f"{est.B_CALLS}", "pilots (coordinator quoted about 19)"],
        ["Gemma throughput", f"{est.G30:.1f} calls/min (30 min), {est.G120:.1f} (2 h)", f"= {est.A_RATE_LO:.0f} to {est.A_RATE_HI:.0f} rollouts/h shared by every Suite A arm"],
        ["gpt-oss throughput", f"{est.O30:.0f} calls/min (30 min)", f"= {est.B_RATE:.0f} rollouts/h; gateway-semaphore bound (24 slots), server latency flat at about 9 s"],
        ["Time left", f"{est.HRS_LEFT:.0f} h to 2026-10-14 00:05; {est.HRS_DEV_LEFT:.0f} h of dev window; 18 h final", "campaign.yaml"],
        ["Optimizer cost per iteration (pilot_hc)", f"about {est.PILOT_HC_ITER_TOK/1000:.0f}k non-cache-read tokens; ${est.PILOT_USD_PER_MTOK:.2f} per MTok at the pilot mix", "pilot_hc: 8,131 in + 7,708 out + 120,326 cache-creation tokens over 2 iterations, 716k cache-read tokens, priced at the proxy rates ($0.54 total). Applies to Claude-Code-driven arms only; other optimizers' use is not recorded"],
    ], wide=(1, 2), caption="Optimizer ceiling per search is 4M non-cache-read tokens. Dollar columns use the pilot mix and are proxy prices: RITS and gpt-5.5 are unknown."))
    out.append(h3("Per experiment"))
    out.append(table(["Experiment", "Suite", "Target rollouts", "RITS tokens", "Non-RITS tokens", "Proxy USD", "Wall hours (one deployment)", "Note"],
                     [[a, b, c, d, e, f, g, h] for a, b, c, d, e, f, g, h in rows], num=(2, 3), wide=(0, 7),
                     caption="Suite A wall hours = rollouts divided by the measured shared rate (range = low and high rate); Suite B = rollouts divided by the gpt-oss rate. Suite A and B run on different deployments and overlap in time."))
    out.append(h3("Capacity vs demand, Suite A (Gemma deployment)"))
    t1 = est.TIER1_PLAN - est.TIER1_DONE
    dev_demand = t1 + est.CHEAP_T2S + est.CHEAP_CAP + est.T2_PLAN
    out.append(table(["Quantity", "Rollouts", "Hours at the shared rate"], [
        ["Capacity: remaining dev window", f"{est.DEV_CAP_LO:,.0f} to {est.DEV_CAP_HI:,.0f}", f"{est.HRS_DEV_LEFT:.0f}"],
        ["Capacity: whole remaining campaign", f"{est.TOTAL_CAP_ROLL_A_LO:,.0f} to {est.TOTAL_CAP_ROLL_A_HI:,.0f}", f"{est.HRS_LEFT:.0f}"],
        ["Demand: Tier 1 remaining (planned use)", est.fmt(t1), est.a_hours(t1)],
        ["Demand: + Tier 1-cheap (Trace2Skill plan; ACE, MIPROv2 at cap)", est.fmt(est.CHEAP_T2S + est.CHEAP_CAP), est.a_hours(est.CHEAP_T2S + est.CHEAP_CAP)],
        ["Demand: + Tier 2 s0 runs (planned)", est.fmt(est.T2_PLAN), est.a_hours(est.T2_PLAN)],
        ["Demand: all search rollouts above", est.fmt(dev_demand), est.a_hours(dev_demand)],
    ], num=(1, 2), caption="The numbers assume the shared rate stays at its recent level. More arms starting does not raise throughput: the deployment is saturated."))
    out.append(callout("What the numbers say", ul([
        f"Tier 1 alone ({est.fmt(t1)} planned rollouts remaining) needs about {t1/est.A_RATE_HI:.0f} to {t1/est.A_RATE_LO:.0f} h of Gemma time, against {est.HRS_DEV_LEFT:.0f} h left in the dev window and {est.HRS_LEFT:.0f} h in the whole campaign. At the measured rate it does not finish inside the dev window even with nothing else running on Gemma.",
        "Tier 1-cheap and Tier 2 add up to several thousand rollouts more. They compete with Tier 1 for the same slots, and with the final evaluation for the last 18 h.",
        "Version 1 assumed 41k tokens and 3 minutes per rollout at 4 to 32 slots. The measured throughput is below the 09:00 estimate of 300 rollouts/h.",
    ])))
    out.append(h3("Final Suite A set size that fits (n = 2 trials, at most 25% of remaining capacity)"))
    N23, N32, N37 = est.max_T(23), est.max_T(32), est.max_T(37)
    out.append(table(["Artifacts scored (N)", "T (tasks)", "Rollouts = 2 x N x T", "Gemma tokens", "Hours", "Fit in 25% of capacity"], est.final_a_rows(), num=(1, 2, 3),
                     caption=f"25% of remaining capacity is {est.FINAL_CAP_LO:,.0f} to {est.FINAL_CAP_HI:,.0f} rollouts. Largest T that fits: N=23: {N23[0]} to {N23[1]}; N=32: {est.max_T(32)[0]} to {est.max_T(32)[1]}; N=37: {N37[0]} to {N37[1]}. The v1 candidate of T about 150 does not fit for any N. T is fixed after the fresh-set decision."))
    out.append(h3("Suite B (gpt-oss deployment, separate capacity)"))
    main, cond, abl, fin = est.totals_B()
    cap_b = est.HRS_LEFT * est.B_RATE
    out.append(table(["Quantity", "Rollouts", "Hours at the gpt-oss rate", "gpt-oss tokens (80k each)"], [
        ["Capacity: remaining campaign", f"{cap_b:,.0f}", f"{est.HRS_LEFT:.0f}", "-"],
        ["E10B main (running)", est.fmt(main), est.b_hours(main), est.M(main * est.B_TOK)],
        ["+ conditional arms (MIPROv2, ACE, HarnessLens)", est.fmt(cond), est.b_hours(cond), est.M(cond * est.B_TOK)],
        ["+ ablations moved to B (E16, E14/E15)", est.fmt(abl), est.b_hours(abl), est.M(abl * est.B_TOK)],
        ["+ final Suite B (13 artifacts)", est.fmt(fin), est.b_hours(fin), est.M(fin * est.B_TOK)],
        ["Total", est.fmt(main + cond + abl + fin), est.b_hours(main + cond + abl + fin), est.M((main + cond + abl + fin) * est.B_TOK)],
    ], num=(1, 2, 3), caption="Suite B fits comfortably at the measured rate if the gateway semaphore stays at 24 and RITS does not slow. The judge fix (gpt-5.5) would add non-RITS tokens: about 0.27 judge calls per rollout at about 3k tokens each, so under 1k tokens per rollout."))
    out.append(h3("Non-RITS tokens and dollars"))
    out.append(p(f"Used so far: {(live.HEALTH or {}).get('capped_tokens', 0):,} tokens (all Claude optimizer and reflection calls), proxy cost about $2.2 across E10 and E10B. Searches planned or running: Suite A up to 21 Tier 1 + 9 cheap (Trace2Skill, ACE, MIPROv2 x 3) + 5 Tier 2 = 35; Suite B 12 running plus conditional. At the 4M ceiling: 35 x 4M = 140M for Suite A alone, above the 100M cap, but the pilots point to about 0.7M for a Claude-Code hill-climb search. Competitor optimizer spend per search is not recorded yet. The cap is therefore not binding at the forecast and would bind only if the ceiling were reached on most searches. The tag-level meter (`scripts/spend.py E10`) is the control."))
    out.append(h3("What gets cut first (proposed order; none applied except the Tier rules)"))
    out.append(table(["Order", "Cut", "Effect", "Status"], [
        ["1", "Tier 2 beyond s0; no promotion to 3 seeds unless Tier 1 finishes with capacity left (rule already fixed 09:00)", "keeps exploratory methods at one seed", "[[frozen|decided]]"],
        ["2", "AHE adapter, ACE and MIPROv2 seeds beyond the cheap budget, HarnessLens and conditional Suite B arms", "frees up to 5,300 Gemma rollouts", "[[pending|pending]]"],
        ["3", "Suite A ablations other than E11 (free) and E12 (reference running)", "frees 1,800 rollouts per dropped arm", "[[frozen|decided]]"],
        ["4", "Final Suite A size T and artifact count N (table above)", "T of about 40 to 70 instead of 150", "[[pending|pending]]"],
        ["5", "Stop slow Tier 1 searches at planned use (GEPA 555, EvoSkill 568, Trace2Skill 200) instead of the 600 cap", "small", "[[pending|pending]]"],
        ["6", "Reduce Gemma gateway concurrency from 32 to a value that does not queue (queue mean 135 s, p95 388 s now)", "does not change throughput; reduces latency spikes that cause 502 and read timeouts", "[[pending|pending]]"],
    ], wide=(1, 2)))
    out.append("</section>")
    return "".join(out)


def sec_registry():
    rows = [
        ["E00", "scorer and adapter audit", "[[done|done]]", "0", "scorer_audit.md, defects.csv"],
        ["E01", "model and concurrency preflight", "[[done|done]]", "probes", "model_registry.json; concurrency probes in `logs/concurrency_probes.jsonl`"],
        ["E02", "no-op repeated evaluation", "[[planned|planned]]", "pending", "supplies MDE inputs"],
        ["E03", "scorer-compliance diagnostic", "[[planned|planned]]", "120 per artifact per trial", "train 80 + val 40, both scorers"],
        ["E04", "null edits through each gate", "[[planned|planned]]", "pending", "confirmed ID"],
        ["E05", "injected scorer/adapter faults", "[[planned|planned]]", "pending", "confirmed ID; includes tau2 evaluator coupling"],
        ["E06", "gold-isolation negative test", "[[planned|planned]]", "0 model calls", "confirmed ID; negative tests exist per arm for EvoSkill, Memento, Meta-Harness, not for the others"],
        ["E07", "footprint false-exclusion audit", "[[planned|planned]]", "0", "confirmed ID; uses logged delta_full / delta_masked"],
        ["E10", "main comparison", "[[running|running]]", "see status board", "Suite A: 28 arm-seeds running; Suite B: 15 + 6 controls"],
        ["E11 to E15", "ablations and improvements", "[[planned|planned]]", "see ablations", "E12 reference arm running"],
        ["E16", "surface width (Suite B)", "[[planned|planned]]", "3,300", ""],
        ["E17", "optimizer mechanics 2x2", "[[planned|planned]]", "7,200", "likely dropped"],
        ["E20 to E22", "transfer", "[[planned|planned]]", "pending", "see transfer"],
        ["E30", "enterprise case study", "[[planned|planned]]", "-", "out of scope unless time allows"],
    ]
    return h2("registry", "Experiment registry") + table(["ID", "Experiment", "Status", "Rollouts", "Note"], rows, wide=(4,), num=(3,)) + "</section>"


def sec_integrity():
    s = v1sec("integrity")
    s = sub(s, '<span class="chip pending">pending</span> PR #779 review', '<span class="chip done">done</span> #779 merged; unmasked vector in rule P arms')
    s = sub(s, '<span class="chip pending">pending</span> classifier and switch', '<span class="chip pending">pending</span> classifier; joint coverage switch merged (#779)')
    s = sub(s, '<span class="chip pending">pending</span> exact interaction', '<span class="chip pending">pending</span> AO runs the stock gate until parity (E12 reference)')
    s = sub(s, '<span class="chip pending">pending</span> patches', '<span class="chip pending">pending</span> Suite A shim in place for CapEvolve/EvoSkill/Meta-Harness; Suite B CapEvolve optimizer runs as uid dev; no negative tests for CapEvolve arms')
    # #782 row
    a = s.index('<td class="mono">#782</td>')
    b = s.index("</tr>", a)
    s = s[:a] + ('<td class="mono">#782</td><td class="mid">Gold answers visible in the agent sandbox (critical).</td><td class="wide">Gold-free sandbox shipped in PR #783 (merged 09:23). The historical trajectory scan found no gold access in 2,049 retained agent rollouts, which is absence of evidence only (val-split rollouts only). The optimizer side is separate (#784): gold use is documented by the optimizer itself in at least 6 Opus 5 runs, and one run read a prior sealed-test evaluation. See isolation incidents.</td>') + s[b:]
    return s


def sec_incidents():
    rows = [
        ["2026-10-11 04:26", "Gold in the SpreadsheetBench sandbox (#782, critical)", "the sandbox bind-mounted the data dir read-write at `/mnt/data` with gold workbooks beside the inputs; `os.listdir` showed `1_<id>_golden.xlsx`", "PR #783 merged 09:23: gold-free copy mounted, scorer reads the pristine tree, safe default `AGENT_VIEW=1`, allowlist assertion, symlink refusal, rmtree guard; 20/20 tests incl. live podman test. Not done: `runmeta.json` field via workflow file (token lacks `workflow` scope)", "historical rollouts; campaign runs use `SPREADSHEETBENCH_AGENT_VIEW=1`"],
        ["2026-10-11 08:33", "Optimizer read gold historically (#784)", "optimizer notes document gold access in at least 6 Opus 5 runs (36175707483, 36466624841, 36711181652, 36841799223, 36862654281, 36887243479); run 36887243479 (GPT-5.5 run 3, test 87.1) read a prior run's sealed-test evaluation (280 per-task results, 55 test ids cited in its notes); its champion text is byte-identical to the prior run's `cand_0001`. The 3-run GPT-5.5 mean of 87.6 should be recomputed (runs 1-2 give 87.86)", "decision: every agentic proposer runs without read access to gold, split and test files (uid or container) with a negative test before launch, recorded in each manifest", "historical Opus 5 runs; the six Gemma-optimizer E-arms show no gold references; recommended actions in `audit/gold_access_scan.md` section 5, completion not verified"],
        ["2026-10-11 08:35 to 09:38", "Meta-Harness first launch", "proposer ran as uid `dev` with gold readable; stopped at 09:38 before the first proposer iteration; logs kept", "relaunch 09:38 with a rootless-podman container proposer; `isolation_negtest.txt` written 09:42:11 (uid=1006; gold, split_ids, baselines/runs/E10, _eval/split_ids.json denied; workspace writable)", "first launch's seed evaluations only; `runs/E10/superseded/metaharness-gold-readable-20261011/`"],
        ["2026-10-11 10:00", "capopt could read split-id files", "the shared proposer uid for CapEvolve and EvoSkill could read `*split*.json` in world-readable repo checkouts (task ids only; gold and credentials were already denied)", "other-read removed from all `*split*.json` under `/home/dev/projects2` and `/opt` (1,029 files incl. the user's main checkout); verified capopt finds no readable golden/answer/split file. Later check: 124 files world-readable again or not covered (120 in `wt-e05` mtime 09:58, 2 new `splits.json`, 2 `split_tasks.json`); capopt traversal of `/home/dev` not confirmed", "runs started before 10:00 record the window; EvoSkill smoke sessions"],
        ["not recorded", "`/opt/capevolve-eval-proto`", "frozen evaluator prototype tree; mode 700 root:root; `chattr +i`; `neg_test.sh` runs 17 checks as capopt and dev (`protocol/setup_log.md`)", "mode 700; time of the chmod not recorded", "isolation prototype only"],
        ["not recorded", "Credentials and `~/.claude`", "`~/.claude` mode 700; `rits-env` and `azure-openai-env` mode 600; `bench/data` 700", "decisions.md records 'go-rwx, credential files 600, bench data go-rwx'; timestamps not recorded", "-"],
        ["2026-10-11 (before 10:00)", "EvoSkill smoke sessions", "proposer uid could read split-id files before the 10:00 fix (`restart_note.txt`)", "smoke only; main launch 10:11 under capopt + private mount namespace, negative-tested", "smoke runs"],
    ]
    return (h2("incidents", "Isolation incidents and fixes", "Times are as recorded in decisions.md or file mtimes (UTC).")
            + table(["When", "Incident", "What happened", "Fix and verification", "Affected"], rows, wide=(2, 3, 4), mid=(1,)) + "</section>")


def sec_timeline():
    rows = [
        ["00:05", "Campaign started; base `e3cb513`; fallback envelope from the mandate (72 h, $50 preflight, $1000, 10k rollouts, 100M tokens, 25% reserve)"],
        ["early", "Runs local on this host; documents treated as hypotheses; credentials only via `provider_env.py`; historical test sets reclassified development-exposed"],
        ["early", "Reward = LO-recalculated; both scorers always reported. Rule P adopted for every CapEvolve arm. Gateway built; token-cap accounting (cache reads excluded)"],
        ["early", "Measured one Gemma rollout: 41.5k tokens, 177 s (task 58687)"],
        ["early", "USER: 'For RITS you can run as many as you need' -> RITS uncapped, metered"],
        ["early", "Frozen E10 parameters: 600 rollouts, <= 4M tokens, seeds 0-2, Sonnet 5.5 for all matched arms; Suite A and B definitions"],
        ["early", "CapEvolve arms run from a local integration worktree before review completes; affected arms re-run and earlier runs labelled superseded"],
        ["early", "Gateway concurrency raised to Gemma 12, gpt-oss 12, Qwen 8; then Gemma 32, gpt-oss 24, gateway 16"],
        ["early", "USER REQUEST: more SOTA competitors incl. harness optimizers and WikiSkill; roster fixed; no-code methods to the external-context table"],
        ["early", "Suite B judge = azure/gpt-5.5 for every arm; Suite B splits frozen (opt 49 / sel 25 / test 40)"],
        ["early", "Algorithm-improvement workstream started (rule P module, merge verification, screen accounting)"],
        ["early", "Integrity decision: no agentic proposer may read gold/answer/split/test files; negative test before launch"],
        ["early", "PR #779 review: REQUEST CHANGES; main seeds wait for the fix; earlier searches labelled pre-779-fix"],
        ["early", "Searches parallelized within a search (about 6 concurrent rollouts, equal across methods); restarts logged as infrastructure restarts"],
        ["09:00", "CAPACITY-DRIVEN SCOPE DECISION (Suite A): tiers fixed before any outcome"],
        ["data", "CapEvolve stock arms use VAL traces as feedback; accepted as a disclosed difference"],
        ["09:05", "GraphSkillEvo s1/s2 stopped; s0 continues as Tier 2 practical track; Trace2Skill running since 08:50"],
        ["09:11", "PR #779 merged (`b6ac28477`)"],
        ["unstamped", "USER: GEPA, SkillOpt, Meta-Harness, WikiSkill run from cloned repositories; WikiSkill has no official code -> community implementation Stahl-G/wikiskill"],
        ["unstamped", "Gateway priority reservation implemented, staged, not deployed"],
        ["09:23", "PR #783 merged (`6f9278025`)"],
        ["unstamped", "PR #786 merged (`7883107b2`); campaign `promotion_min_coverage` 0.95"],
        ["unstamped", "VERSE, CoEvoSkills failed reproductions; HarnessLens moved to Suite B"],
        ["09:45", "MCE s1/s2 stopped; s0 continues subject to a negative test"],
        ["09:55", "EvoSkill promoted to Tier 1 (3 seeds); Meta-Harness relaunched 09:38 container-isolated"],
        ["10:00", "Host fix: split-id files no longer world-readable"],
        ["10:05", "Memento s1/s2 stopped; arms running listed"],
        ["10:20", "PR #788 and #790 merged (`cbdb3cf90`, `d8851c811`); all five code PRs in the campaign branch"],
        ["unstamped", "Competitor provenance: GEPA v0.1.4 byte-identical, SkillOpt 79124b37 byte-identical; EvoSkill relaunched under capopt + mount namespace"],
        ["unstamped", "Gate replay (#791) first reported; corrected at 10:30 and 10:40"],
        ["10:25", "GATE PARITY: both E10 CapEvolve arms judge through rule P; running AO becomes the E12 stock-gate reference"],
        ["10:30", "Correction: the cand_0005 accept is 'a dropped task produced an accept', inferred, not proven footprint masking"],
        ["10:40", "#791 merged; all 4 recorded-vs-unmasked mismatches are dropped-task cases; no evidence of footprint masking in the artifacts"],
    ]
    return h2("timeline", "Decision timeline", "Condensed from decisions.md in file order. 'early' = entries stamped only with the date, listed before the 09:00 decision; 'unstamped' = date only.") + table(["Time (as written)", "Decision or event"], rows, wide=(1,)) + "</section>"


def sec_diagram():
    mm = """flowchart LR
  subgraph PRE["Merged gates"]
    G783["Gold-free sandbox 783, merged"]
    P779["Paper-mode switches 779, merged"]
    P786["Rule P module 786, merged"]
    P788["Merge verification 788, merged"]
    P790["Screen accounting 790, merged"]
  end
  subgraph GW["Gateway: caps.json limits, token guard"]
    PRIO["Priority reservation: staged, not deployed"]
  end
  subgraph DEV["Dev boundary: train-80 feedback, val-40 selection, recalculated scorer"]
    E00["E00 audit, done"]
    E01["E01 preflight, done"]
    T1["E10 Tier 1: 7 arms x 3 seeds"]
    T1C["E10 Tier 1-cheap: Trace2Skill, ACE, MIPROv2"]
    T2["E10 Tier 2: 1 seed each, exploratory"]
    E10B["E10B Suite B: hc, ao, gepa, controls"]
    E03["E03 compliance diagnostic"]
    E0407["E04 to E07 measurement controls"]
    ABL["E11 to E17 ablations, capacity permitting"]
  end
  subgraph FINAL["Final boundary: frozen manifest, one randomized window"]
    FRZ["Freeze list hashed"]
    FIN["Final scoring: Suite A n=2, Suite B n=4"]
  end
  subgraph TR["Transfer boundary"]
    E20["E20 Qwen3.6"]
    E21["E21 GPT-5.5"]
    E22["E22 SpreadsheetBench 2"]
  end
  G783 --> T1
  P779 --> T1
  P786 --> T1
  P786 --> E10B
  G783 --> E0407
  PRIO --> T1
  E00 --> E03
  E01 --> T1
  E03 --> FRZ
  T1 --> T1C
  T1 -->|capacity remains| T2
  T1 --> ABL
  E10B --> ABL
  E0407 --> FRZ
  T1 --> FRZ
  T1C --> FRZ
  E10B --> FRZ
  PROV["Fresh-set provenance and size T"] --> FRZ
  FRZ --> FIN
  FIN --> E20
  FIN --> E21
  FIN --> E22
  FIN --> ANA["Analysis, route A, B or C"]
  E20 --> ANA
  E21 --> ANA
  E22 --> ANA
"""
    return (h2("diagram", "Timeline and dependencies", "Evaluator boundaries and the experiment dependency graph. Budget windows: dev ends 2026-10-13 06:05 UTC, final window 18 h to 2026-10-14 00:05 UTC.")
            + f'<div class="mm"><pre class="mermaid">{mm}</pre></div></section>')


def sec_pending():
    rows = [
        ["Suite B judge: gpt-5.5 (frozen) vs gpt-oss (running)", "coordinator", "before any Suite B main result is scored or frozen; arms are in the seed baseline (about 5% done)", "29 of 74 train tasks have NL assertions; gpt-5.5 tokens count against the 100M cap (under 1k per rollout)"],
        ["Suite B CapEvolve parity with rule P and the 550 vs 600 budget", "coordinator", "now, while the seed baselines are 5% done; each hour adds baseline rollouts", "relaunch cost is the roughly 25 baseline rollouts per seed already spent"],
        ["Suite A main CapEvolve seeds under the #786 module (s0 redo, s1, s2)", "coordinator + runner", "before s1/s2 launch; s0 baselines are at about 2%", "the running s0 AO stays as the E12 reference"],
        ["amend analysis plan section 8: n_conf 3 instead of >= 10", "coordinator + stats-reviewer", "before the freeze", "operating characteristics of n_conf 3 not in sim_promotion"],
        ["negative tests for CapEvolve arms (A and B), MCE, RHO, ACE, MIPROv2, WikiSkill, GraphSkillEvo", "coordinator", "before each arm's results count", "files list which arms have results"],
        ["remaining world-readable split files and capopt traversal of `/home/dev`", "runner/coordinator", "before the next capopt-uid launch", "124 files found"],
        ["gateway priority build deployment", "coordinator", "before launching WikiSkill, ACE, MIPROv2 and CapEvolve s1/s2, which add load; old build cannot drain, about 30 in-flight Gemma calls are lost on restart", "Gemma queue mean 135 s now"],
        ["Gemma gateway concurrency (32) vs queueing", "coordinator", "with the gateway decision", "throughput does not rise with slots"],
        ["which competitors launch and when (WikiSkill, ACE, MIPROv2 Tier 1/cheap; RHO, AHE Tier 2)", "coordinator", "as capacity frees; Tier 1 first", "capacity table"],
        ["Tier 2 promotion to 3 seeds", "capacity rule", "only after Tier 1 completes with capacity left; never by seed-0 result", "-"],
        ["fresh Suite A final set (912 residual vs SpreadsheetBench 2) and size T, N", "provenance-auditor + coordinator", "before the freeze and before the dev window ends 2026-10-13 06:05 UTC", "T about 40 to 70 fits; T 150 does not"],
        ["Suite B retail test confirmed untouched", "provenance-auditor", "before the freeze", "audit found no recorded exposure"],
        ["K for best-of-K, rollouts for Suite A one-shot repair", "coordinator", "before those controls launch", "-"],
        ["which ablations run (E13 to E17)", "coordinator", "after Tier 1 reports; capacity decides", "E17 likely dropped"],
        ["GPT-5.5 transfer subset", "coordinator", "after E10", "token cap"],
        ["SpreadsheetBench 2 adapter and partition", "coordinator", "only if capacity remains", "-"],
        ["MDE re-run with pilot inputs and the designed T, n; Holm comparison family; non-inferiority margin; missingness classifier code", "stats-reviewer", "before the freeze", "placeholders in sim_mde"],
        ["Model registry freeze (currently PROVISIONAL)", "coordinator", "with the preregistration", "-"],
        ["Update stale deviations text; complete PROVENANCE.json (EvoSkill SHA, others)", "baseline-eng", "before competitor tables are written", "-"],
        ["E02 and E04 to E07 sizes; E22 size", "coordinator", "after the pilot reports", "-"],
        ["E30 enterprise case study", "user", "out of scope unless time allows", "-"],
    ]
    return h2("pending", "Pending decisions", "Each item with what decides it and by when. Deadlines are proposed from the budget windows; none is a recorded commitment.") + table(["Decision", "Decider", "By when", "What it depends on"], rows, wide=(0, 2, 3)) + "</section>"


def sec_sources():
    rows = [
        ["`research/capevolve-paper/decisions.md`, STATUS.md, issues.json, campaign.yaml", "decisions with timestamps, issues, budget envelope"],
        ["`protocol/*` (analysis_plan, benchmarks, scorer_audit, model_registry, pricing, setup_log)", "pins, estimands, rule P, models, prices"],
        ["`audit/*`, `reviews/methodology_preflight.md`, `literature/novelty_matrix.md`", "defects, exposure, gold access, competitor feasibility"],
        ["`analysis/out/sim_*.md`; `analysis/out/replay_gates.md` on branch `research/algo-p4-replay-gates`", "simulated and replayed operating characteristics"],
        ["`campaign-scratch/baselines/` (BRIEF_COMMON.txt, PROVENANCE.json, RUNBOOK.json, deviations_*.json, */deviations.json, *blocker*.json, code/*.py, launch scripts)", "competitor configuration, provenance, deviations, blockers"],
        ["`campaign-scratch/runs/E10/`, `runs/E10B/` (launcher.log, config.yaml, manifest.json, counters, STOPPED.json, negtest files, driver.sh, env.sh, specs)", "per-arm configuration and state"],
        ["`campaign-scratch/logs/caps.json`, `gateway_calls.jsonl`; `scripts/spend.py`; gateway `/health`", "live limits, throughput, spend"],
        ["`/home/dev/projects2/wt-run`, `/home/dev/projects2/wt-tau`", "Suite A and Suite B CapEvolve code and specs"],
        ["`campaign-scratch/scripts/design_v2/` (build.py, live.py, est.py, cards.py)", "generator: re-run to refresh the live sections and estimates"],
    ]
    return h2("sources", "Sources", "Paths are under `/home/dev/projects2/` unless relative to `cap-evolve-campaign/research/capevolve-paper/`.") + table(["Path", "Used for"], rows, wide=(0, 1)) + "<footer>CapEvolve paper campaign, design page v2. Pending items are marked in amber with a dashed edge. Re-run the generator to refresh the status board and estimates.</footer></section>"


def build():
    body = [sec_top(), sec_status(), sec_deviations(), sec_summary(), sec_rq(), sec_budget(), sec_gateway(), sec_models(),
            sec_suite_a(), sec_suite_b(), sec_tiers(), sec_cards_a(), sec_cards_b(), sec_prs(), sec_failed(), sec_search(),
            sec_final(), sec_transfer(), sec_ablations(), sec_controls(), sec_stats(), sec_estimates(), sec_cost(), sec_registry(),
            sec_integrity(), sec_incidents(), sec_timeline(), sec_diagram(), sec_pending(), sec_sources()]
    html = HEAD + EXTRA_CSS + '<div class="page">' + nav() + "<main>" + "".join(body) + "</main></div>"
    out = f"{ROOT}/design/experimental_design.html"
    open(out, "w").write(html)
    print(out, len(html.encode()))


if __name__ == "__main__":
    build()
