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
FAMILIES = [("F1", 20), ("F2", 16), ("F3", 13), ("F4", 10), ("F5", 7), ("F6", 4)]  # sums to the 70-task Suite A final set
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


D_PARAM = dict(seed_score=0.61, se=0.045, tasks=40, trials=5, seeds=3, bstar=550, heldout=65)
D_CELLS = [  # key, label, seeds, conditional. Approved Suite D Tier 1 only (no history, descriptions-only or skill cells)
    ("ctl", "One-shot control", 3, False), ("p", "Prompt only (P)", 3, False), ("t", "Tools only (T)", 3, False),
    ("pt", "Prompt and tools (PT), reference", 3, False), ("rulep", "PT with rule P", 3, False),
    ("onestage", "PT with one-stage gate", 3, False), ("gepa", "GEPA, prompt only", 3, False),
    ("nohist", "PT without fixed/broke history", 3, False),
]


def build_suite_d(rng):
    P = D_PARAM
    cells = {}
    for key, label, nseed, cond in D_CELLS:
        mu = 0.015 if key == "ctl" else 0.05
        d = rng.gauss(mu, 0.022)
        se = P["se"] * rng.uniform(0.9, 1.1) * (1.15 if nseed == 2 else 1.0)
        tcrit = 4.30 if nseed == 3 else 12.7
        tcrit = min(tcrit, 2.6)  # artifact-level interval over tasks, not seeds
        pr = [rng.randint(0, 2) if key == "rulep" else rng.randint(1, 6) for _ in range(nseed)]
        cands = [rng.randint(6, 12) for _ in range(nseed)]
        sd_ = [0.0 if p == 0 else d + rng.gauss(0, 0.015) for p in pr]
        d = sum(sd_) / len(sd_)
        cells[key] = dict(label=label, seeds=nseed, conditional=cond, delta=d, se=se, lo=d - tcrit * se, hi=d + tcrit * se,
                          promotions=pr, candidates=cands, seed_deltas=sd_, returned_seed=sum(1 for p in pr if p == 0),
                          regress=dict(pass_to_fail=max(0.0, rng.gauss(3.0, 1.0) * (0.3 if sum(pr) == 0 else 1.0))),
                          rollouts=550 if key != "ctl" else 200)
    for c in cells.values():  # print values: 0.1 point
        h = (c["hi"] - c["lo"]) / 2
        c["delta"] = round(c["delta"], 3)
        c["lo"], c["hi"] = round(c["delta"] - h, 3), round(c["delta"] + h, 3)
    ref = cells["pt"]
    cons = {}
    for k, c in cells.items():
        if k == "pt":
            continue
        dd = round(c["delta"] - ref["delta"], 3)
        se_c = P["se"] * 1.3 * 2.4
        cons[k] = dict(delta=dd, lo=round(dd - se_c, 3), hi=round(dd + se_c, 3), p=norm_p(dd / (se_c / 2.4)))
    # primary family D, m = 11: seven contrasts against PT, P versus T, and P, T and PT against the seed
    pvt = round(cells["p"]["delta"] - cells["t"]["delta"], 3)
    fam = [("vs_pt", k, v["p"]) for k, v in cons.items()]
    fam.append(("p_vs_t", "p", norm_p(pvt / (P["se"] * 1.3))))
    fam += [("vs_seed", k, norm_p(cells[k]["delta"] / cells[k]["se"])) for k in ("p", "t", "pt")]
    adj = holm([x[2] for x in fam])
    out_p = {}
    for (kind, k, _), q in zip(fam, adj):
        out_p[(kind, k)] = q
    for k, v in cons.items():
        v["p_holm"] = out_p[("vs_pt", k)]
    for k in ("p", "t", "pt"):
        cells[k]["p_holm_seed"] = out_p[("vs_seed", k)]
    inter = round(ref["delta"] - cells["p"]["delta"] - cells["t"]["delta"], 3)
    se_i = P["se"] * 2.0 * 2.4
    interaction = dict(delta=inter, lo=round(inter - se_i, 3), hi=round(inter + se_i, 3))
    p_vs_t = dict(delta=pvt, p_holm=out_p[("p_vs_t", "p")], m=len(fam))
    return dict(params=P, cells=cells, vs_pt=cons, interaction=interaction, p_vs_t=p_vs_t)


def build_null_pool(rng):
    """E22 empirical null pool, mock: false-accept rate per 10-candidate search for each gate (reference: simulation)."""
    out = {}
    n = 2000
    for key, sim in (("rulep", 0.07), ("onestage", 0.55), ("stock", 0.50)):
        p = min(max(sim * rng.uniform(0.7, 1.3), 0.005), 0.95)
        w = 1.96 * math.sqrt(p * (1 - p) / n)
        out[key] = dict(rate=p, lo=max(p - w, 0), hi=min(p + w, 1), sim=sim, n=n)
    return out


def build_decomposition(rng):
    """E25, mock: whole-artifact gain against the prompt-only and tool-only parts of the same champion."""
    rows = []
    for i, cell in enumerate(["pt", "pt", "pt", "rulep", "onestage", "onestage", "ctl", "pt"]):
        whole = rng.gauss(0.05, 0.03)
        fp = rng.uniform(0.2, 0.7)
        p_part = whole * fp + rng.gauss(0, 0.012)
        t_part = whole * (1 - fp) + rng.gauss(0, 0.012)
        rows.append(dict(cell=cell, seed=i % 3, whole=whole, p_part=p_part, t_part=t_part, gap=whole - p_part - t_part))
    return rows


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
        # round every delta to 0.1 point so score columns, delta columns and contrasts agree on the printed values
        for a, v in out.items():
            if a == "seed":
                continue
            half = (v["hi"] - v["lo"]) / 2
            v["delta"] = round(v["delta"], 3)
            v["lo"], v["hi"] = round(v["delta"] - half, 3), round(v["delta"] + half, 3)
            v["score"] = round(P["seed_score"] + v["delta"], 3)
            v["bound_pess"] = round(v["delta"] - v["missing"] / v["cells"], 3)
            v["bound_opt"] = round(v["delta"] + v["missing"] / v["cells"], 3)
        if os_ is not None:
            for a, v in out.items():
                if a in ("seed", "oneshot"):
                    continue
                se_c = rows[a]["se"] * 1.1 * 2.05
                dd = round(v["delta"] - os_["delta"], 3)
                v["vs_oneshot"] = dict(delta=dd, lo=round(dd - se_c, 3), hi=round(dd + se_c, 3))
        contrasts = {}
        for cap in ("hc", "ao"):
            for a in arms:
                if a in ("hc", "ao", "seed", "hcstock", "bestofk"):
                    continue
                se_c = P["se"] * 1.25
                dd = round(out[cap]["delta"] - out[a]["delta"], 3)
                contrasts[f"{cap}-{a}"] = dict(delta=dd, lo=round(dd - 2.05 * se_c, 3), hi=round(dd + 2.05 * se_c, 3))
        # S-stock secondary family (analysis plan 5P-1): hcstock vs seed and vs named competitors, own Holm
        s_stock = []
        if "hcstock" in out:
            comps = {"A": ["gepa", "skillopt", "metaharness", "wikiskill", "evoskill"], "C": ["gepa"]}.get(suite, [])
            fam = [("seed", out["hcstock"]["delta"], P["se"] * 1.0)] + [(a, out["hcstock"]["delta"] - out[a]["delta"], P["se"] * 1.25) for a in comps]
            pv = [norm_p(d / se) for _, d, se in fam]
            adjf = holm(pv)
            for (a, d, se), q in zip(fam, adjf):
                d = round(d, 3)
                s_stock.append(dict(vs=a, delta=d, lo=round(d - 2.05 * se, 3), hi=round(d + 2.05 * se, 3), p_holm=q))
            s_stock[0].update(delta=out["hcstock"]["delta"], lo=out["hcstock"]["lo"], hi=out["hcstock"]["hi"])  # one interval per contrast
            out["hcstock"]["p_holm"] = adjf[0]
            for a in comps:
                contrasts[f"hcstock-{a}"] = dict(delta=round(out["hcstock"]["delta"] - out[a]["delta"], 3),
                                                 lo=s_stock[1 + comps.index(a)]["lo"], hi=s_stock[1 + comps.index(a)]["hi"])
        # final-dependent extras: regressions vs seed, shrinkage, cost per point (mock)
        for a, v in out.items():
            if a == "seed" or a in ("oneshot", "bestofk") and False:
                continue
            if a == "seed":
                continue
            nprom = sum(v["promotions"]) if v.get("promotions") else 0
            v["regress"] = dict(pass_to_fail=max(0.0, rng.gauss(3.0, 1.2) * (0.3 if nprom == 0 else 1.0)),
                                fail_to_pass=max(0.0, rng.gauss(5.0, 1.5) * (0.3 if nprom == 0 else 1.0)),
                                protect_viol=max(0.0, rng.gauss(2.0, 0.8) * (0.3 if nprom == 0 else 1.0)))
            sel = v["delta"] + abs(rng.gauss(0.05, 0.03)) if nprom else 0.0
            v["shrink"] = dict(sel_gain=sel, final_gain=v["delta"], shrinkage=sel - v["delta"] if nprom else 0.0)
            gains = [100 * x for x in v.get("seed_deltas", [100 * v["delta"]])]
            total_gain = sum(gains)
            if total_gain > 0:
                boots = []
                for _ in range(400):
                    gg = sum(rng.choice(gains) for _ in gains)
                    boots.append(v["usd"] / gg if gg > 0 else float("inf"))
                boots.sort()
                v["usd_per_point"] = dict(est=v["usd"] / total_gain, lo=boots[10], hi=boots[389] if boots[389] != float("inf") else None)
            else:
                v["usd_per_point"] = None
        s = dict(params=P, arms=out, contrasts=contrasts, s_stock=s_stock)
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
    data["suites"]["D"] = build_suite_d(rng)
    data["null_pool"] = build_null_pool(rng)
    data["decomposition"] = build_decomposition(rng)
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
        if suite == "D":
            continue
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
    D = data["suites"]["D"]
    m["mockDTasks"] = str(D["params"]["tasks"])
    m["mockDTrials"] = str(D["params"]["trials"])
    m["mockDHeldout"] = str(D["params"]["heldout"])
    for k, c in D["cells"].items():
        key = f"mockD{k}"
        m[key + "Delta"] = fmt_d(c["delta"])
        m[key + "Lo"] = fmt_d(c["lo"])
        m[key + "Hi"] = fmt_d(c["hi"])
        m[key + "Prom"] = f"{sum(c['promotions']) / len(c['promotions']):.1f}"
        m[key + "Ret"] = f"{c['returned_seed']} of {len(c['promotions'])}"
    for k, v in D["vs_pt"].items():
        m[f"mockD{k}VsPt"] = fmt_d(v["delta"])
        m[f"mockD{k}VsPtLo"] = fmt_d(v["lo"])
        m[f"mockD{k}VsPtHi"] = fmt_d(v["hi"])
    it = D["interaction"]
    m["mockDInter"], m["mockDInterLo"], m["mockDInterHi"] = fmt_d(it["delta"]), fmt_d(it["lo"]), fmt_d(it["hi"])
    for k, v in data["null_pool"].items():
        m[f"mockNull{k}"] = f"{100 * v['rate']:.1f}"
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
