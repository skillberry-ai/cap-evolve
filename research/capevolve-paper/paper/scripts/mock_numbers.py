"""Generate MOCK results for the paper apparatus.

Outputs (all mock, never real):
  ../results_data.json       data consumed by make_tables.py and plots/make_plots.py (source = "mock")
  ../numbers_pending.tex     one \\newcommand per number, every value wrapped in \\pend{...}
  ../numbers_pending.json    flat macro -> string map (copy of the .tex content)

Design rules (PAPER_BRIEF.txt):
  * fixed seed, so reruns are byte-identical
  * no built-in winner: every optimizer arm draws its true effect from the SAME distribution,
    so the ordering is random and the intervals overlap
  * the seed row has delta 0 by definition; the one-shot control draws from a smaller mean

Run:  python3 -I mock_numbers.py
Real numbers replace this file's output by running real_numbers.py (same schema, source = "real").
"""
import json
import math
import random
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
SEED = 20261013

SUITE_ARMS = {
    "A": ["hc", "ao", "gepa", "skillopt", "metaharness", "evoskill", "wikiskill", "trace2skill", "ace", "mipro", "hcstock", "seed"],
    "B": ["hc", "ao", "gepa", "harnesslens", "oneshot", "seed"],
    "C": ["hc", "ao", "gepa", "harnesslens", "oneshot", "hcstock", "bestofk", "seed"],
}
SUITE_PARAM = {  # seed score, SE of a paired delta, tasks, trials per task, seeds, B* rollouts
    "A": dict(seed_score=0.50, se=0.030, tasks=70, trials=1, seed_trials=2, seeds=3, bstar=400, clusters=24),
    "B": dict(seed_score=0.55, se=0.040, tasks=40, trials=3, seed_trials=3, seeds=3, bstar=350, clusters=40),
    "C": dict(seed_score=0.40, se=0.060, tasks=20, trials=3, seed_trials=3, seeds=3, bstar=250, clusters=20),
}
PRICE = dict(unc=2.0, out=10.0, cr=0.2, cw=2.5)  # USD per Mtok, Sonnet 5.5 list-price proxy
FAMILIES = [("F1", 31), ("F2", 24), ("F3", 21), ("F4", 17), ("F5", 15), ("F6", 12)]
LABEL = {"hc": "CapEvolve HC", "ao": "CapEvolve AO", "gepa": "GEPA", "skillopt": "SkillOpt", "metaharness": "Meta-Harness",
         "evoskill": "EvoSkill", "wikiskill": "WikiSkill", "trace2skill": "Trace2Skill", "ace": "ACE", "mipro": "MIPROv2",
         "harnesslens": "HarnessLens", "oneshot": "the one-shot control", "seed": "the seed", "hcstock": "CapEvolve HC with the stock gate", "bestofk": "the best-of-k control"}
FAM_ARMS = ["hc", "ao", "gepa", "skillopt", "mipro"]


def norm_p(z):
    return math.erfc(abs(z) / math.sqrt(2))


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    out, run = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        out[i] = run
    return out


def curve(rng, seed_score, delta, bstar):
    grid = list(range(0, bstar + 1, 30))
    tau = rng.uniform(120, 260)
    seeds = []
    for _ in range(3):
        d = delta + rng.gauss(0, 0.012)
        best, ys = seed_score, []
        for r in grid:
            y = seed_score + d * (1 - math.exp(-r / tau)) + rng.gauss(0, 0.008)
            best = max(best, y)
            ys.append(best)
        seeds.append(ys)
    mean = [sum(s[i] for s in seeds) / 3 for i in range(len(grid))]
    lo = [min(s[i] for s in seeds) for i in range(len(grid))]
    hi = [max(s[i] for s in seeds) for i in range(len(grid))]
    return dict(rollouts=grid, mean=mean, lo=lo, hi=hi)


def build():
    rng = random.Random(SEED)
    data = dict(source="mock", seed=SEED, suites={})
    for suite, arms in SUITE_ARMS.items():
        P = SUITE_PARAM[suite]
        rows, ps = {}, []
        for a in arms:
            if a == "seed":
                continue
            mu = 0.02 if a == "oneshot" else 0.045  # same mean for every optimizer arm: no built-in winner
            d = rng.gauss(mu, 0.022)
            se = P["se"] * rng.uniform(0.85, 1.15)
            df = max(P["clusters"] - 1, 2)
            tcrit = {2: 4.30, 19: 2.09, 23: 2.07, 39: 2.02}.get(df, 2.05)
            rows[a] = dict(delta=d, se=se, lo=d - tcrit * se, hi=d + tcrit * se, p=norm_p(d / se))
            if a not in ("hcstock", "bestofk"):
                ps.append((a, rows[a]["p"]))
        adj = holm([p for _, p in ps])
        for (a, _), q in zip(ps, adj):
            rows[a]["p_holm"] = q
        for x in ("hcstock", "bestofk"):
            if x in rows:
                rows[x]["p_holm"] = None  # exploratory arms: outside the Holm family
        total_cells = P["tasks"] * P["trials"] * P["seeds"]
        out = {}
        for a in arms:
            if a == "seed":
                out[a] = dict(score=P["seed_score"], delta=0.0, lo=None, hi=None, p_holm=None, rollouts=0, promotions=None,
                              tok_unc=0.0, tok_cr=0.0, tok_cw=0.0, usd=0.0, wall_h=0.0,
                              missing=rng.randint(0, 3), cells=P["tasks"] * P["seed_trials"])
                continue
            r = rows[a]
            agentic = a in ("hc", "ao", "metaharness", "evoskill", "hcstock", "bestofk")
            unc = rng.uniform(1.5, 5.0) * (1.3 if agentic else 1.0) * (0.15 if a == "oneshot" else 1.0)  # millions, summed over 3 seeds; cap is 4M per search
            cr = rng.uniform(20, 120) if agentic else rng.uniform(0, 8)
            cw = rng.uniform(0.3, 1.5) if agentic else rng.uniform(0, 0.3)
            outt = unc * rng.uniform(0.08, 0.16)
            usd = unc * PRICE["unc"] + outt * PRICE["out"] + cr * PRICE["cr"] + cw * PRICE["cw"]
            out[a] = dict(score=P["seed_score"] + r["delta"], delta=r["delta"], lo=r["lo"], hi=r["hi"],
                          p_holm=r["p_holm"], rollouts=P["bstar"] - (rng.randint(0, 14) if a not in ("oneshot", "bestofk") else P["bstar"] - 10) if a != "bestofk" else 550,
                          tok_unc=unc, tok_cr=cr, tok_cw=cw, tok_out=outt, usd=usd, cap_used=100 * (unc + cw + outt) / 3 * 1.2 / 4.0,
                          wall_h=(P["bstar"] - 7) / (rng.uniform(11, 13) if a in ("hc", "ao", "hcstock") else rng.uniform(12, 40)) if a not in ("oneshot", "bestofk") else rng.uniform(0.4, 3.0),
                          missing=rng.randint(0, 9), cells=total_cells,
                          promotions=[rng.randint(0, 3) if a in ("hc", "ao") else rng.randint(1, 7) for _ in range(P["seeds"])],
                          candidates=[rng.randint(5, 14) for _ in range(P["seeds"])], exploratory=(a in ("hcstock", "bestofk")),
                          curve=curve(rng, P["seed_score"], r["delta"], P["bstar"]) if a != "oneshot" else None)
        # delta vs one-shot, per-seed deltas, missingness bounds, CapEvolve contrasts (all mock)
        os_ = out.get("oneshot")
        for a, v in out.items():
            if a == "seed":
                continue
            if a != "oneshot" and os_ is not None:
                se_c = rows[a]["se"] * 1.1
                dd = v["delta"] - os_["delta"]
                v["vs_oneshot"] = dict(delta=dd, lo=dd - 2.05 * se_c, hi=dd + 2.05 * se_c)
            v["seed_deltas"] = [v["delta"] + rng.gauss(0, 0.015) for _ in range(P["seeds"])]
            if v.get("promotions"):
                # a seed that promoted nothing returns the seed artifact, so its paired delta is exactly zero
                v["seed_deltas"] = [0.0 if p == 0 else d for p, d in zip(v["promotions"], v["seed_deltas"])]
                shift = sum(v["seed_deltas"]) / len(v["seed_deltas"]) - v["delta"]
                v["delta"] += shift
                v["lo"] += shift
                v["hi"] += shift
                v["score"] += shift
            frac = v["missing"] / v["cells"]
            v["bound_pess"] = v["delta"] - frac
            v["bound_opt"] = v["delta"] + frac
        contrasts = {}
        for cap in ("hc", "ao"):
            for a in arms:
                if a in ("hc", "ao", "seed", "hcstock", "bestofk"):
                    continue
                se_c = P["se"] * 1.25
                dd = out[cap]["delta"] - out[a]["delta"]
                contrasts[f"{cap}-{a}"] = dict(delta=dd, lo=dd - 2.05 * se_c, hi=dd + 2.05 * se_c)
        s = dict(params=P, arms=out, contrasts=contrasts)
        if suite == "A":
            fams = {}
            for fname, n in FAMILIES:
                fams[fname] = dict(n_tasks=n, arms={})
                for a in FAM_ARMS:
                    d = out[a]["delta"] + rng.gauss(0, 0.03)
                    h = 2.1 * 0.09 / math.sqrt(n)
                    fams[fname]["arms"][a] = dict(delta=d, lo=d - h, hi=d + h)
            s["families"] = fams
        data["suites"][suite] = s
    return data


def fmt_pct(x):
    return f"{100 * x:.1f}"


def fmt_d(x):
    return f"{100 * x:+.1f}".replace("-", "$-$")


def fmt_p(p):
    return "$<$0.001" if p < 0.001 else f"{p:.3f}"


def macros(data):
    m = {}
    for suite, s in data["suites"].items():
        P = s["params"]
        m[f"mockT{suite}"] = str(P["tasks"])
        m[f"mockTrials{suite}"] = str(P["trials"])
        m[f"mockSeeds{suite}"] = str(P["seeds"])
        m[f"mockBstar{suite}"] = str(P["bstar"])
        best = max((k for k in s["arms"] if k not in ("seed", "oneshot", "hcstock", "bestofk")), key=lambda k: s["arms"][k]["delta"])
        m[f"mockTopDelta{suite}"] = fmt_d(s["arms"][best]["delta"])
        m[f"mockTopArm{suite}"] = LABEL[best]
        m[f"mockNsig{suite}"] = str(sum(1 for k, v in s["arms"].items() if v["p_holm"] is not None and v["p_holm"] < 0.05))
        for a, v in s["arms"].items():
            k = f"mock{suite}{a.replace('trace2skill', 'tracetwoskill')}"
            m[k + "Score"] = fmt_pct(v["score"])
            m[k + "Delta"] = fmt_d(v["delta"])
            if v["lo"] is not None:
                m[k + "Lo"] = fmt_d(v["lo"])
                m[k + "Hi"] = fmt_d(v["hi"])
                m[k + "Pholm"] = fmt_p(v["p_holm"]) if v["p_holm"] is not None else "--"
            m[k + "Roll"] = str(v["rollouts"])
            m[k + "TokU"] = f"{v['tok_unc']:.1f}"
            m[k + "TokCr"] = f"{v['tok_cr']:.1f}"
            m[k + "TokCw"] = f"{v['tok_cw']:.1f}"
            m[k + "Usd"] = f"{v['usd']:.0f}"
            m[k + "Wall"] = f"{v['wall_h']:.1f}"
            m[k + "Miss"] = f"{v['missing']}/{v['cells']}"
    return m


def main():
    data = build()
    (PAPER / "results_data.json").write_text(json.dumps(data, indent=1))
    m = macros(data)
    lines = [f"% GENERATED by scripts/mock_numbers.py (seed {SEED}). MOCK VALUES. Do not edit.",
             "% Every macro is wrapped in \\pend; check_paper.py must fail if any survives with \\draftmodefalse."]
    for k in sorted(m):
        lines.append("\\newcommand{\\%s}{\\pend{%s}}" % (k, m[k]))
    (PAPER / "numbers_pending.tex").write_text("\n".join(lines) + "\n")
    (PAPER / "numbers_pending.json").write_text(json.dumps(m, indent=1, sort_keys=True))
    print(f"wrote {len(m)} macros")


if __name__ == "__main__":
    main()
