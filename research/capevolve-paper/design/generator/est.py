"""Estimates from MEASURED per-rollout costs. All inputs are printed in the page's inputs table."""
import datetime as dt
import json
import os

import live

ROOT = live.ROOT
NOW = live.NOW
START = dt.datetime(2026, 10, 11, 0, 5)
END = START + dt.timedelta(hours=72)
DEV_END = START + dt.timedelta(hours=54)

last, rates = live.gemma_rates()
A_TOK, A_CALLS, A_ROLL_BASIS = live.pooled_tokens_per_rollout_A()
B_TOK = 80_000       # coordinator figure; pilots measured 71k-83k and 17.1-17.3 calls
B_CALLS = 17.2       # pilots (hc 17.2, gepa 17.1-17.3)
G30 = rates[("google/gemma-4-31B-it", 30)]["cpm"]
G120 = rates[("google/gemma-4-31B-it", 120)]["cpm"]
O30 = rates[("openai/gpt-oss-120b-a100", 30)]["cpm"]
A_RATE_LO = G30 * 60 / A_CALLS     # rollouts per hour
A_RATE_HI = G120 * 60 / A_CALLS
B_RATE = O30 * 60 / B_CALLS
HRS_LEFT = (END - NOW).total_seconds() / 3600
HRS_DEV_LEFT = max((DEV_END - NOW).total_seconds() / 3600, 0)
HRS_FINAL = 18.0
PILOT_USD_PER_MTOK = 0.5374 / 0.136165   # pilot_hc incl. cache reads/writes, proxy price
PILOT_HC_ITER_TOK = 136_165 / 2


def fmt(n):
    return f"{n:,.0f}"


def M(x):
    return f"{x/1e6:,.0f}M" if x >= 1e7 else f"{x/1e6:,.1f}M"


def hrs(r_lo, r_hi):
    return f"{r_lo/ A_RATE_HI:,.0f} to {r_hi / A_RATE_LO:,.0f}" if r_lo is not None else "-"


def a_hours(rollouts):
    lo, hi = rollouts / A_RATE_HI, rollouts / A_RATE_LO
    if f"{lo:,.0f}" == f"{hi:,.0f}":
        return f"{lo:,.0f}" if lo >= 1 else f"{lo:,.1f}"
    return f"{lo:,.0f} to {hi:,.0f}"


def b_hours(rollouts):
    return f"{rollouts / B_RATE:,.1f}"


def done(arm, seeds=(0, 1, 2)):
    t = 0
    for s in seeds:
        p = os.path.join(ROOT, "runs/E10", arm, f"s{s}")
        t += live.counter(p) or 0
    return t


# planned use per seed (file-derived) for Suite A arms
A_PLAN = {
    "CapEvolve hill-climb": (600, 3), "CapEvolve agent-optimize": (600, 3), "GEPA": (555, 3), "SkillOpt": (600, 3),
    "Meta-Harness": (600, 3), "EvoSkill": (568, 3), "WikiSkill (community)": (600, 3),
}
TIER1_PLAN = sum(a * b for a, b in A_PLAN.values())          # 12,369
TIER1_DONE = (sum(done(a) for a in ("gepa", "skillopt", "metaharness", "evoskill"))
              + sum(1 for _ in open(os.path.join(ROOT, "runs/E10/hill-climb/s0/logs/rollouts.jsonl")))
              + sum(1 for _ in open(os.path.join(ROOT, "runs/E10/agent-optimize/s0/logs/rollouts.jsonl"))))
CHEAP_T2S = 3 * 200
CHEAP_CAP = 2 * 3 * 600
T2_PLAN = 600 + 560 + 600 + 300 + 600

TOTAL_CAP_ROLL_A_LO = HRS_LEFT * A_RATE_LO
TOTAL_CAP_ROLL_A_HI = HRS_LEFT * A_RATE_HI
DEV_CAP_LO = HRS_DEV_LEFT * A_RATE_LO
DEV_CAP_HI = HRS_DEV_LEFT * A_RATE_HI
FINAL_CAP_LO = 0.25 * TOTAL_CAP_ROLL_A_LO
FINAL_CAP_HI = 0.25 * TOTAL_CAP_ROLL_A_HI


def final_a_rows():
    rows = []
    for N, label in ((23, "23: seed, compliance, 7 Tier-1 arms x 3 seeds"),
                     (32, "32: + Trace2Skill, ACE, MIPROv2 x 3"),
                     (37, "37: + 5 Tier-2 s0 runs")):
        for T in (40, 60, 100, 150):
            r = 2 * N * T
            fits = "fits" if r <= FINAL_CAP_LO else ("fits only at the high rate" if r <= FINAL_CAP_HI else "does not fit")
            rows.append([label if T == 40 else "", str(T), fmt(r), M(r * A_TOK), a_hours(r), fits])
    return rows


def max_T(N, n=2):
    return int(FINAL_CAP_LO // (n * N)), int(FINAL_CAP_HI // (n * N))


def estimate_rows():
    """[experiment, suite, rollouts, RITS tokens, non-RITS ceiling (forecast), proxy USD, wall h, note]"""
    r = []
    def A(name, roll, nsearch, note, forecast_nonrits=None):
        ceil = nsearch * 4_000_000
        usd = ceil / 1e6 * PILOT_USD_PER_MTOK
        r.append([name, "A", fmt(roll), M(roll * A_TOK),
                  (f"{M(ceil)} ceiling" + (f"; {forecast_nonrits} forecast" if forecast_nonrits else "")) if nsearch else "0",
                  f"up to ${usd:,.0f}" if nsearch else "$0", a_hours(roll) + " h", note])
    A("E10 Tier 1 remaining (7 arms x 3 seeds, planned use)", TIER1_PLAN - TIER1_DONE, 21,
      f"planned use {fmt(TIER1_PLAN)} minus {fmt(TIER1_DONE)} started so far. HC/AO/WikiSkill forecast = ~0.68M per search from the pilot (68k per iteration x 10).")
    A("E10 Tier 1-cheap: Trace2Skill x 3 (about 200 each)", CHEAP_T2S, 3, "plan from deviations file; actual rollouts reported, budget is a cap")
    A("E10 Tier 1-cheap: ACE and MIPROv2 x 3 (cap 600 each)", CHEAP_CAP, 6, "cap shown; actual use not recorded (ACE smoke used 6 rollouts)")
    A("E10 Tier 2 exploratory s0: GraphSkillEvo, MCE, Memento, RHO, AHE", T2_PLAN, 5, "plan 600 + 560 + 600 + ~300 + 600 (AHE not built); one seed each, never in the Holm family")
    r.append(["E03 compliance diagnostic (per artifact, per trial)", "A", "120", M(120 * A_TOK), "0", "$0", a_hours(120) + " h", "train 80 + val 40; both scorers from one rollout; number of historical champions not recorded"])
    r.append(["E11 footprint on/off", "A", "0 extra", "0", "0", "$0", "-", "re-use logged `delta_full` / `delta_masked` from Tier 1 hill-climb steps (#779 fields); replay evidence is code + simulation only"])
    r.append(["E12 stock-gate reference", "A", "0 extra", "0", "0", "$0", "-", "the running agent-optimize s0 (stock reward_gated) is designated the reference arm (decisions.md 10:25)"])
    # Suite B
    def B(name, roll, nsearch, note):
        ceil = nsearch * 4_000_000
        usd = ceil / 1e6 * PILOT_USD_PER_MTOK
        r.append([name, "B", fmt(roll), M(roll * B_TOK), (M(ceil) + " ceiling") if nsearch else "0", f"up to ${usd:,.0f}" if nsearch else "$0", b_hours(roll) + " h", note])
    B("E10B main (running): hc x3 550, ao x3 550, gepa x3 600, one-shot x3 cap 200, seed control x3 148", 1650 + 1650 + 1800 + 600 + 444, 12, "cap-sum; one-shot and seed control have little or no optimizer spend (one iteration)")
    B("E10B conditional: MIPROv2 and ACE x 3 (cap 600), HarnessLens 1 seed", 3600 + 600, 7, "no tau adapter exists for MIPROv2/ACE; HarnessLens ledger counts sessions and trials in one unit")
    B("E16 surface width (2 added arms x 3 seeds x 550)", 3300, 6, "prompt-only and tools-only vs the prompt+tools main arm")
    B("E14/E15 improvement arms on Suite B (merge verify; screen accounting + random control) 3 arms x 3 x 550", 4950, 9, "ablations moved to Suite B by the 09:00 capacity decision; selection pending")
    B("Final Suite B: 13 artifacts x 40 tasks x 4 trials", 13 * 40 * 4, 0, "13 = seed, 3 one-shot, 3 hc, 3 ao, 3 gepa; with MIPROv2 and ACE 19 artifacts = 3,040 rollouts")
    return r


def totals_B():
    main = 1650 + 1650 + 1800 + 600 + 444
    cond = 3600 + 600
    abl = 3300 + 4950
    fin = 13 * 160
    return main, cond, abl, fin
