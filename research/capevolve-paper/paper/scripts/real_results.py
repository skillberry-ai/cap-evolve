"""Everything in the results apparatus that is REAL today (no mock data, no watermark).

Reads repo files only:
  audit/recomputed_numbers.csv, audit/historical_results.md        historical audit
  analysis/out/sim_budget.json                                     rule P operating characteristic
  analysis/out/metrics/{metrics_by_arm,metrics_by_role}.csv,
  analysis/out/metrics/campaign_totals.json                        cost so far (IN PROGRESS, marked \\prov)

Writes:
  ../numbers_real_results.tex      \\realXxx macros (audit values plain, in-progress cost values in \\prov)
  ../tables/cost_so_far.tex        cost table by suite and arm
  ../tables/audit.tex              historical audit table (claim verdicts)
  ../figures/fig_audit.pdf, fig_rulep.pdf, fig_roles.pdf

Run:  python3 -I real_results.py     (needs matplotlib; use the venv-paper python)
"""
import collections
import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "plots"))
import common as C  # noqa: E402

C.style()
import matplotlib.pyplot as plt  # noqa: E402

REPO = C.REPO
PAPER = C.PAPER
OUTM = REPO / "analysis" / "out" / "metrics"
OPT_ROLES = {"optimizer", "proposer", "reflection", "reflector", "curator"}


def read_csv(p):
    return list(csv.DictReader(open(p)))


def f(x):
    return float(x) if x not in ("", None) else 0.0


# ---------------------------------------------------------------- audit
def audit():
    rows = read_csv(REPO / "audit" / "recomputed_numbers.csv")
    md = (REPO / "audit" / "historical_results.md").read_text()
    # values are parsed from the audit text so they follow the audit if it is revised
    gemma_recalc = float(re.search(r"Under recalculation the gain is \+(\d+\.\d+)", md).group(1))
    gpt_recalc = float(re.search(r"recalc gain \+(\d+\.\d+)", md).group(1))
    by = {r["claim_id"]: r for r in rows}
    gemma_rep = float(re.match(r"[\d.]+", by["SB-G-04"]["recomputed_value"]).group(0))
    gpt_rep = float(re.match(r"[\d.]+", by["SB-P-03"]["recomputed_value"]).group(0))
    verdict = collections.Counter()
    for r in rows:
        m = r["match"].lower()
        verdict["unverifiable" if m.startswith("unverifiable") else "no" if m.startswith("no") else "yes"] += 1
    return dict(gemma_rep=gemma_rep, gemma_recalc=gemma_recalc, gpt_rep=gpt_rep, gpt_recalc=gpt_recalc,
                verdict=verdict, n=len(rows), rows=rows)


def fig_audit(a):
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(C.FULL_W, 2.3), gridspec_kw=dict(width_ratios=[1.3, 1]))
    names = ["Gemma-4-31B", "GPT-5.5"]
    rep = [a["gemma_rep"], a["gpt_rep"]]
    rec = [a["gemma_recalc"], a["gpt_recalc"]]
    x = range(2)
    ax.bar([i - 0.19 for i in x], rep, 0.36, color="#999999", label="Reported (as-saved scorer)")
    ax.bar([i + 0.19 for i in x], rec, 0.36, color="#0072B2", label="Recalculated scorer")
    for i in x:
        ax.text(i - 0.19, rep[i] + 0.8, f"+{rep[i]:.1f}", ha="center", fontsize=8)
        ax.text(i + 0.19, rec[i] + 0.8, f"+{rec[i]:.1f}", ha="center", fontsize=8, weight="bold")
    ax.set_xticks(list(x)); ax.set_xticklabels(names)
    ax.set_ylabel("Gain over seed (points)")
    ax.set_ylim(0, 70)
    ax.legend(frameon=False, loc="upper center")
    ax.grid(axis="x", alpha=0)
    v = a["verdict"]
    labs = ["Reproduced", "Contradicted", "No artifact"]
    vals = [v["yes"], v["no"], v["unverifiable"]]
    cols = ["#009E73", "#D55E00", "#999999"]
    bx.barh(labs[::-1], vals[::-1], color=cols[::-1])
    for i, val in enumerate(vals[::-1]):
        bx.text(val + 0.3, i, str(val), va="center", fontsize=8)
    bx.set_xlabel(f"Historical claims recomputed (of {a['n']})")
    bx.grid(axis="y", alpha=0)
    fig.tight_layout()
    C.save(fig, "fig_audit", False)


def table_audit(a):
    keep = ["SB-G-04", "SB-P-03", "SB-P-04", "SB-A-04", "SB-P-05", "SK-03", "SW-01", "T2-01", "T2-03"]
    short = {
        "SB-G-04": ("Gemma +33.0 [29.1, 36.8]", "reproduces; interval is pooled over observations, task-clustered is [26.9, 39.2]; +18.7 under recalculation"),
        "SB-P-03": ("GPT-5.5 +49.1 [45.5, 52.8]", "reproduces; recalculated gain is +9.9"),
        "SB-P-04": ("GPT-5.5 recalculated baseline 77.5", "reproduces; 110 of 217 recalculated passes need formulas"),
        "SB-A-04": ("no-capability control 62.9", "same run's one-iteration hill climb scores 85.6, absent from the draft"),
        "SB-P-05": ("run excluded for different commit", "55 of 280 rollouts hit a budget error; baseline 28.9 is on 225 tasks"),
        "SK-03": ("SkillsBench 55.6 to 66.7 held out", "the whole delta is one trial of one task"),
        "SW-01": ("SWE-bench pilot 68.0, candidate 72.0", "candidate rejected; the seed scores 63.6 and 70.5 on the same 44 tasks"),
        "T2-01": ("tau2 retail 0.460 to 0.545", "arithmetic only; no per-task artifact exists"),
        "T2-03": ("tau2 held-out 30.0 to 47.5", "artifact never landed; runner identity differs between docs"),
    }
    by = {r["claim_id"]: r for r in a["rows"]}
    L = [r"\begin{table}[t]", r"\centering", r"\scriptsize",
         r"\caption{Selected historical claims and their recomputation from archived artifacts "
         r"(" + str(a["n"]) + r" claims in total).}",
         r"\label{tab:audit}", r"\begin{tabularx}{\columnwidth}{@{}p{0.9in}X@{}}", r"\toprule", r"Claim & Recomputation \\", r"\midrule"]
    for k in keep:
        assert k in by, k
        L.append(f"{short[k][0]} & {short[k][1]} \\\\")
    L += [r"\bottomrule", r"\end{tabularx}", r"\end{table}"]
    (PAPER / "tables" / "audit.tex").write_text("\n".join(L).replace("tau2", r"$\tau^2$") + "\n")


# ---------------------------------------------------------------- rule P
def fig_rulep():
    """Rule P against the one-stage gate, per suite, from the budget-exact simulations (10 candidates per search, real task counts)."""
    sims = {su: json.loads((REPO / "analysis" / "out" / f"sim_budget_{su}.json").read_text()) for su in "ABC"}
    RP, ONE = "c: P n_conf=3 z=1.282 dmin=0", "f: one-stage k=1"
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(C.FULL_W, 2.4), constrained_layout=True)
    w = 0.36
    for i, su in enumerate("ABC"):
        for j, (key, col) in enumerate(((RP, "#0072B2"), (ONE, "#D55E00"))):
            v = 100 * sims[su][key]["N=10"]["p_any_false_null_search"]
            ax.bar(i + (j - 0.5) * w, v, w, color=col, label=("Rule P" if key == RP else "One-stage gate") if i == 0 else None)
            ax.text(i + (j - 0.5) * w, v + 1, f"{v:.0f}", ha="center", fontsize=7.5)
    ax.set_xticks(range(3)); ax.set_xticklabels([f"Suite {su}" for su in "ABC"])
    ax.set_ylabel("False promotions (% of null searches)")
    ax.set_ylim(0, 85)
    ax.legend(frameon=False, loc="upper right", ncol=2)
    ax.grid(axis="x", alpha=0)
    styles = {"A": ("-", "o"), "B": ("--", "s"), "C": (":", "^")}
    for su in "ABC":
        for key, col in ((RP, "#0072B2"), (ONE, "#D55E00")):
            pw = sims[su][key]["power"]
            ks = sorted(pw, key=float)
            ls, mk = styles[su]
            bx.plot([float(k) * 100 for k in ks], [100 * pw[k] for k in ks], color=col, ls=ls, marker=mk, ms=3.5, lw=1.1)
    for su in "ABC":
        bx.plot([], [], color="#555555", ls=styles[su][0], marker=styles[su][1], ms=3.5, label=f"Suite {su}")
    bx.set_xlabel("True gain of the candidate (points)")
    bx.set_ylabel("Candidates promoted (%)")
    bx.set_ylim(0, 85)
    bx.legend(frameon=False, loc="upper left", fontsize=7, ncol=3)
    C.save(fig, "fig_rulep", False)


# ---------------------------------------------------------------- cost
def cost():
    arm_rows = [r for r in read_csv(OUTM / "metrics_by_arm.csv") if r["category"] == "main"]
    role_rows = [r for r in read_csv(OUTM / "metrics_by_role.csv") if r["category"] == "main"]
    opt = collections.defaultdict(lambda: collections.defaultdict(float))
    seed_nc = collections.defaultdict(float)  # per (suite, arm, seed): the tokens the optimizer cap counts
    for r in role_rows:
        if r["role"] in OPT_ROLES:
            seed_nc[(r["suite"], r["arm"], r["seed"])] += f(r["in_uncached"]) + f(r["output"]) + f(r["cache_write_5m"]) + f(r["cache_write_1h"])
            k = (r["suite"], r["arm"])
            for fld in ("in_uncached", "cache_read", "output", "usd_total"):
                opt[k][fld] += f(r[fld])
            opt[k]["cw"] += f(r["cache_write_5m"]) + f(r["cache_write_1h"])
            opt[k]["calls"] += f(r["calls"])
    # Optimizer usage that bypassed the gateway, recovered from CLI transcripts by the metering audit.
    # Columns: suite (E10/E10B/E10C), arm, seed, bypassed_input, bypassed_output, bypassed_cache_read,
    # bypassed_cache_creation, bypassed_usd. Added on top of the gateway-metered optimizer usage.
    SUITE_MAP = {"E10": "A", "E10B": "B", "E10C": "C"}
    ARM_MAP = {"hill-climb": "hc", "agent-optimize": "ao"}
    rec = collections.defaultdict(lambda: collections.defaultdict(float))
    bp = OUTM / "bypassed_usage.csv"
    if bp.exists():
        for r in read_csv(bp):
            k = (SUITE_MAP.get(r["suite"], r["suite"]), ARM_MAP.get(r["arm"], r["arm"]))
            rec[k]["in_uncached"] += f(r.get("bypassed_input"))
            rec[k]["output"] += f(r.get("bypassed_output"))
            rec[k]["cache_read"] += f(r.get("bypassed_cache_read"))
            rec[k]["cw"] += f(r.get("bypassed_cache_creation"))
            rec[k]["usd_total"] += f(r.get("bypassed_usd"))
            seed_nc[(k[0], k[1], r["seed"])] += f(r.get("bypassed_input")) + f(r.get("bypassed_output")) + f(r.get("bypassed_cache_creation"))
    for k in list(rec):
        if not any(rec[k][x] for x in ("in_uncached", "output", "cache_read", "cw")):
            del rec[k]  # the audit found nothing outside the gateway for this arm
    cap = max((f(r["optimizer_cap_tokens"]) for r in arm_rows), default=4e6) or 4e6
    g = collections.defaultdict(lambda: collections.defaultdict(float))
    for r in arm_rows:
        k = (r["suite"], r["arm"])
        g[k]["n"] += 1
        g[k]["roll"] += f(r["counted_rollouts"])
        g[k]["tgt"] += f(r["target_noncache_tokens"])
        g[k]["wall"] = max(g[k]["wall"], f(r["wall_clock_h_since_launch"]))
        g[k]["err"] += f(r["errors"])
        g[k]["active"] = max(g[k]["active"], 1.0 if r["active"] == "True" else 0.0)
    order = {"A": ["hc", "ao", "gepa", "skillopt", "metaharness", "evoskill", "wikiskill", "trace2skill", "ace", "mipro"],
             "B": ["hc", "ao", "gepa", "ctl-oneshot", "ctl-seed"], "C": ["hc", "ao", "gepa", "ctl-oneshot", "ctl-seed"]}
    nice = {"ctl-oneshot": "one-shot ctrl", "ctl-seed": "seed ctrl", "hc": "CapEvolve HC", "ao": "CapEvolve AO",
            "gepa": "GEPA", "skillopt": "SkillOpt", "metaharness": "Meta-Harness", "evoskill": "EvoSkill",
            "wikiskill": "WikiSkill", "trace2skill": "Trace2Skill", "ace": "ACE", "mipro": "MIPROv2"}
    L = [r"\begin{table*}[t]", r"\centering", r"\scriptsize", r"\setlength{\tabcolsep}{3pt}",
         r"\caption{Campaign cost so far, from the gateway ledger. In progress: searches are still "
         r"running, so every number is \prov{provisional}. Optimizer columns sum the optimizer, proposer, reflector and curator roles over seeds, in millions of tokens. "
         r"The optimizer cap counts non-cache-read tokens, which are uncached input plus output plus cache writes, and applies to each search separately; the table shows the largest seed against the cap of 4M. Cache reads are listed apart and are not counted by the cap. "
         r"``0 (not started)'' means the arm is still in its baseline phase and has made no optimizer call yet; the optimizer is metered at the gateway once it runs, and the metering audit found no optimizer usage outside the gateway. A double dagger would mark usage recovered from CLI transcripts. "
         r"USD is a Sonnet list-price proxy for metered optimizer calls only and is a lower bound. Target tokens are uncached plus output tokens of the "
         r"evaluated model. Wall is hours since launch for the longest seed. Errors count gateway calls that returned an error status, retries included. Rows count seeds that exist in the ledger.}",
         r"\label{tab:cost_so_far}", r"\begin{tabular}{llrrrrrrrrrr}", r"\toprule",
         r"Suite & Arm & Seeds & Rollouts & Opt.\ non-cache-read & Opt.\ cache write & Opt.\ cache read & Cap used (\%) & Opt.\ USD & Target tok. (M) & Wall (h) & Errors \\", r"\midrule"]
    first = True
    for su in "ABC":
        if not first:
            L.append(r"\midrule")
        first = False
        for a in order[su]:
            if (su, a) not in g:
                continue
            v, o = g[(su, a)], opt.get((su, a))
            nm = o is None or o["calls"] == 0
            recovered = False
            if (su, a) in rec:
                base = dict(o) if o else collections.defaultdict(float)
                o = collections.defaultdict(float, {x: base.get(x, 0.0) + rec[(su, a)][x] for x in ("in_uncached", "cache_read", "cw", "usd_total")})
                nm, recovered = False, True
            m = lambda x: f"{x / 1e6:.2f}"
            cells = [su, nice[a] + (r"$^{\ddagger}$" if recovered else ""), f"{int(v['n'])}", f"{int(v['roll'])}",
                     ("0 (no optimizer)" if a == "ctl-seed" else "0 (not started)") if nm else m(o["in_uncached"] + o["output"] + o["cw"]),
                     "0" if nm else m(o["cw"]), "0" if nm else m(o["cache_read"]),
                     "0" if nm else f"{100 * max([x for (a1, a2, _), x in seed_nc.items() if (a1, a2) == (su, a)] or [0]) / cap:.0f}",
                     "0" if nm else f"{o['usd_total']:.2f}", m(v["tgt"]), f"{v['wall']:.1f}", f"{int(v['err'])}"]
            L.append(" & ".join(f"\\prov{{{c}}}" if i >= 3 else c for i, c in enumerate(cells)) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]
    (PAPER / "tables" / "cost_so_far.tex").write_text("\n".join(L) + "\n")
    return opt


def table_zeros():
    """Per arm and seed: adapter label vs uniform label (infra / candidate / unverifiable). Source: analysis/out/metrics/error_label_parity.csv."""
    nice = {"ctl-oneshot": "One-shot control", "ctl-seed": "Seed control", "hc": "CapEvolve HC", "ao": "CapEvolve AO", "gepa": "GEPA",
            "skillopt": "SkillOpt", "metaharness": "Meta-Harness", "evoskill": "EvoSkill", "wikiskill": "WikiSkill",
            "trace2skill": "Trace2Skill", "ace": "ACE", "mipro": "MIPROv2", "harnesslens": "HarnessLens"}
    L = [r"\begin{table*}[t]", r"\centering\scriptsize", r"\setlength{\tabcolsep}{4pt}",
         r"\caption{Error rows per arm and seed under each adapter's own label and under one uniform rule. "
         r"The rule calls an error infrastructure if it has a transport, timeout or sandbox-HTTP string, or made no target call and kept no string. "
         r"Every other error is a candidate error, except rows an adapter labelled infrastructure that have no recoverable string and some target calls, "
         r"which stay unverifiable. Changed counts rows whose class differs from the adapter label. "
         r"Search used each method's native handling of these errors, and only the reporting is unified. Live runs only.}",
         r"\label{tab:zeros}", r"\begin{tabular}{@{}llrrrrrrrr@{}}", r"\toprule",
         r"Suite & Arm & Seed & Errors & Adapter infra & Adapter candidate & Uniform infra & Uniform candidate & Unverifiable & Changed \\", r"\midrule"]
    prev = None
    rows = [r for r in read_csv(OUTM / "error_label_parity.csv") if r["category"] == "main" and int(r["errors"] or 0) > 0]
    rows.sort(key=lambda r: (r["suite"], r["arm"], r["seed"]))
    for r in rows:
        g = int
        unv = g(r["uniform_unverifiable"] or 0)
        cand = g(r["uniform_candidate_error"] or 0)
        ch = g(r["changed_candidate_to_infra"] or 0) + g(r["changed_infra_to_candidate"] or 0) + g(r["changed_unlabelled_to_infra"] or 0)
        if prev and prev != r["suite"]:
            L.append(r"\midrule")
        prev = r["suite"]
        L.append(f"{r['suite']} & {nice.get(r['arm'], r['arm'])} & {r['seed']} & {r['errors']} & {r['adapter_infra']} & {r['adapter_candidate']} & "
                 f"{r['uniform_infra']} & {cand} & {unv} & {ch} \\\\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]
    (PAPER / "tables" / "zeros.tex").write_text("\n".join(L) + "\n")


ATTR = REPO / "analysis" / "out" / "attrib"
NICE_ARM = {"ctl-oneshot": "One-shot control", "ctl-seed": "Seed control", "oneshot": "One-shot control", "hc": "CapEvolve HC, rule P", "ao": "CapEvolve AO, rule P",
            "hcstock": "CapEvolve, stock gate", "bestofk": "One-shot best of $k$", "gepa": "GEPA", "skillopt": "SkillOpt", "metaharness": "Meta-Harness",
            "evoskill": "EvoSkill", "wikiskill": "WikiSkill", "trace2skill": "Trace2Skill", "ace": "ACE", "mipro": "MIPROv2", "harnesslens": "HarnessLens"}


def table_promotions():
    """Real, search-time: candidates, promotions and inert searches per arm (analysis/out/attrib/promotions_by_arm.csv)."""
    rows = read_csv(ATTR / "promotions_by_arm.csv")
    L = [r"\begin{table}[t]", r"\centering\scriptsize", r"\setlength{\tabcolsep}{3pt}",
         r"\caption{Promotions per search at search time, for every arm (in progress). Candidates are those generated, promotions are those the arm's own rule accepted, "
         r"and a search is inert when it promoted nothing. Counts come from the candidate logs and are not held-out results.}",
         r"\label{tab:promotions}", r"\begin{tabular}{@{}llrrrrr@{}}", r"\toprule",
         r"Suite & Arm & Searches & Candidates & Promotions & Per search & Inert \\", r"\midrule"]
    prev = None
    for r in rows:
        su = r["suite"]
        if prev and su[0] != prev[0]:
            L.append(r"\midrule")
        prev = su
        cells = [su, NICE_ARM.get(r["arm"], r["arm"]), r["searches"], r["candidates_generated"], r["promotions"],
                 f"{float(r['promotions_per_search']):.1f}", r["inert_searches"]]
        L.append(" & ".join(f"\\prov{{{c}}}" if i >= 2 else c for i, c in enumerate(cells)) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    (PAPER / "tables" / "promotions.tex").write_text("\n".join(L) + "\n")


def table_regress():
    """Real, search-time: tasks fixed and broken per candidate, and protect-set violations (analysis/out/attrib/regression_by_arm.csv)."""
    rows = read_csv(ATTR / "regression_by_arm.csv")
    def g(r, k):
        v = r.get(k, "")
        return "--" if v in ("", None) else f"{float(v):.1f}"
    L = [r"\begin{table}[t]", r"\centering\scriptsize", r"\setlength{\tabcolsep}{3pt}",
         r"\caption{Regressions at search time for CapEvolve and the one-shot control (in progress). Fixed and broke are tasks that flip from fail to pass and from pass to fail on the selection split, "
         r"per candidate. Protect-set violations count tasks passing in the incumbent that a promoted candidate failed. Selection-split counts include noise flips.}",
         r"\label{tab:regress_search}", r"\begin{tabular}{@{}llrrrrr@{}}", r"\toprule",
         r"Suite & Arm & Candidates & Promoted & Fixed & Broke & Protect violations per promotion \\", r"\midrule"]
    for r in rows:
        cells = [r["base_suite"], NICE_ARM.get(r["arm"], r["arm"]), r["candidates"], r["promoted"], g(r, "fixed_per_candidate"), g(r, "broke_per_candidate"), g(r, "protect_violation")]
        L.append(" & ".join(f"\\prov{{{c}}}" if i >= 2 else c for i, c in enumerate(cells)) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    (PAPER / "tables" / "regress_search.tex").write_text("\n".join(L) + "\n")


def table_surface_failure():
    """Real, search-time: tasks fixed by failure type and the surface a candidate edited most (analysis/out/attrib/surface_x_failure.csv)."""
    c = collections.defaultdict(int)
    for r in read_csv(ATTR / "surface_x_failure.csv"):
        if r["group"] in ("was_passing_or_unlabelled", "infra (unscorable)"):
            continue
        c[(r["group"], r["dominant_surface"])] += int(r["n_fixed"] or 0)
    groups = sorted({g for g, _ in c}, key=lambda g: -sum(v for (gg, _), v in c.items() if gg == g))
    cols = [("system_prompt", "Prompt"), ("tool_code", "Tool code"), ("unavailable", "Surface unknown")]
    L = [r"\begin{table}[t]", r"\centering\scriptsize",
         r"\caption{Tasks fixed by candidates, by failure type of the seed (rows) and by the surface the candidate edited most (columns), at search time on the selection split (in progress). "
         r"Counts sum over CapEvolve candidates and one-shot proposals on Suites A, B and C. Tasks fixed by noise flips are included, and no held-out claim rests on this table.}",
         r"\label{tab:surface_failure}", r"\begin{tabular}{@{}lrrrr@{}}", r"\toprule",
         r"Failure type & " + " & ".join(n for _, n in cols) + r" & Share by tool code \\", r"\midrule"]
    for g in groups:
        vals = [c.get((g, k), 0) for k, _ in cols]
        tot = sum(vals)
        L.append(" & ".join([g[0].upper() + g[1:]] + [f"\\prov{{{v}}}" for v in vals] + [f"\\prov{{{100 * vals[1] / tot:.0f}\\%}}"]) + r" \\")
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table}"]
    (PAPER / "tables" / "surface_failure.tex").write_text("\n".join(L) + "\n")


def fig_roles():
    rows = [r for r in read_csv(OUTM / "metrics_by_role.csv") if r["category"] == "main"]
    agg = collections.defaultdict(lambda: collections.defaultdict(float))
    lat = collections.defaultdict(lambda: [0.0, 0.0, 0.0])  # calls, p50*calls, p95*calls
    for r in rows:
        role = "optimizer" if r["role"] in OPT_ROLES else r["role"]
        k = (r["suite"], role)
        agg[k]["Uncached input"] += f(r["in_uncached"]); agg[k]["Cache read"] += f(r["cache_read"])
        agg[k]["Cache write"] += f(r["cache_write_5m"]) + f(r["cache_write_1h"]); agg[k]["Output"] += f(r["output"])
        c = f(r["calls"])
        if r["latency_p50"]:
            L = lat[role]; L[0] += c; L[1] += c * f(r["latency_p50"]); L[2] += c * f(r["latency_p95"])
    kinds = ["Uncached input", "Cache read", "Cache write", "Output"]
    kcol = ["#0072B2", "#56B4E9", "#E69F00", "#D55E00"]
    roles = ["target", "user", "judge", "optimizer"]
    fig, axes = plt.subplots(1, 3, figsize=(C.FULL_W, 2.5), gridspec_kw=dict(width_ratios=[1, 1, 1]))
    for ax, su in zip(axes[:2], "AB"):
        bottom = [0.0] * len(roles)
        for kd, kc in zip(kinds, kcol):
            vals = [agg[(su, r)][kd] / 1e6 for r in roles]
            ax.bar(roles, vals, bottom=bottom, color=kc, label=kd, width=0.7)
            bottom = [b + v for b, v in zip(bottom, vals)]
        ax.set_yscale("symlog", linthresh=1)
        ax.set_title(C.SUITE_NAME[su])
        ax.set_ylabel("Tokens so far (millions)" if su == "A" else "")
        ax.tick_params(axis="x", rotation=30)
        ax.grid(axis="x", alpha=0)
    h_, l_ = axes[0].get_legend_handles_labels()
    fig.legend(h_, l_, loc="lower center", ncol=4, frameon=False, bbox_to_anchor=(0.34, -0.1))
    ax = axes[2]
    xs = range(len(roles))
    p50 = [lat[r][1] / lat[r][0] if lat[r][0] else 0 for r in roles]
    p95 = [lat[r][2] / lat[r][0] if lat[r][0] else 0 for r in roles]
    ax.bar([i - 0.2 for i in xs], p50, 0.38, color="#999999", label="Median")
    ax.bar([i + 0.2 for i in xs], p95, 0.38, color="#333333", label="95th percentile")
    ax.set_xticks(list(xs)); ax.set_xticklabels(roles, rotation=30)
    ax.set_ylabel("Call latency (seconds)")
    ax.set_title("All suites")
    fig.legend(*ax.get_legend_handles_labels(), loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.84, -0.1))
    ax.grid(axis="x", alpha=0)
    fig.tight_layout()
    C.save(fig, "fig_roles", False)


def numbers(a):
    # Campaign totals (calls, tokens, USD) come from paper-core's derive_numbers.py (\\costCalls etc.), one source for the whole paper.
    m = {
        "realAuditGemmaReported": f"{a['gemma_rep']:.1f}", "realAuditGemmaRecalc": f"{a['gemma_recalc']:.1f}",
        "realAuditGptReported": f"{a['gpt_rep']:.1f}", "realAuditGptRecalc": f"{a['gpt_recalc']:.1f}",
        "realAuditClaims": str(a["n"]), "realAuditReproduced": str(a["verdict"]["yes"]),
        "realAuditContradicted": str(a["verdict"]["no"]), "realAuditNoArtifact": str(a["verdict"]["unverifiable"]),
    }
    # per-arm error counts for the zeros paragraph in appendix/protocol.tex, from error_label_parity.csv (suite A, main runs)
    pr = [r for r in read_csv(OUTM / "error_label_parity.csv") if r["category"] == "main" and r["suite"] == "A"]
    def tot(arm, fld):
        return sum(int(r[fld] or 0) for r in pr if r["arm"] == arm)
    def seedv(arm, seed, fld="errors"):
        return sum(int(r[fld] or 0) for r in pr if r["arm"] == arm and r["seed"] == seed)
    names = {0: "Zero", 1: "One", 2: "Two"}
    m.update({"errTraceTotal": str(tot("trace2skill", "errors")), "errTraceInfra": str(tot("trace2skill", "uniform_infra")),
              "errTraceCand": str(tot("trace2skill", "uniform_candidate_error")),
              "errWikiTotal": str(tot("wikiskill", "errors")), "errWikiInfra": str(tot("wikiskill", "uniform_infra")),
              "errMetaTotal": str(tot("metaharness", "errors")), "errMiproTotal": str(tot("mipro", "errors")),
              "errSkillInfra": str(tot("skillopt", "uniform_infra")), "errSkillCand": str(tot("skillopt", "uniform_candidate_error"))})
    for k, nm in names.items():
        m[f"errMetaSeed{nm}"] = str(seedv("metaharness", str(k)))
        m[f"errMiproSeed{nm}"] = str(seedv("mipro", str(k)))
    # search-time facts about inert searches (analysis/out/attrib/promotions_by_arm.csv), shown as in-progress values
    pb = {(r["base_suite"], r["arm"]): r for r in read_csv(ATTR / "promotions_by_arm.csv")}
    for arm, nm in (("hc", "Hc"), ("ao", "Ao"), ("hcstock", "Stock"), ("gepa", "Gepa")):
        for su in "ABC":
            r = pb.get((su, arm))
            if r:
                m[f"stInert{nm}{su}"] = r["inert_searches"]
                m[f"stSearches{nm}{su}"] = r["searches"]
                m[f"stPromo{nm}{su}"] = f"{float(r['promotions_per_search']):.1f}"
    L = ["% GENERATED by scripts/real_results.py from repo files. Audit values are final."]
    for k, v in m.items():
        L.append("\\newcommand{\\%s}{%s}" % (k, f"\\prov{{{v}}}" if k.startswith("st") else v))
    (PAPER / "numbers_real_results.tex").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    a = audit()
    table_zeros(); fig_audit(a); table_audit(a); fig_rulep(); cost(); fig_roles(); numbers(a)
    print("real results written")
