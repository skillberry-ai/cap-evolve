"""Build the result tables from ../results_data.json.

Main tables (body): score, delta vs seed [CI], delta vs one-shot [CI], Holm p, USD, missing cells.
Appendix tables: tokens and wall clock (tab:cost_tokens), per-seed deltas with missingness bounds (tab:perseed).
Rows: seed, one-shot control, then baselines by ascending delta, CapEvolve arms last.
The same code renders mock and real data. When source == "mock", every number is wrapped in \\pend{}.

Run:  python3 -I make_tables.py
"""
import json
from pathlib import Path

pathlib_path = Path

PAPER = Path(__file__).resolve().parents[1]
LABEL = {"hc": "CapEvolve HC, rule P", "ao": "CapEvolve AO, rule P", "gepa": "GEPA", "skillopt": "SkillOpt", "metaharness": "Meta-Harness",
         "evoskill": "EvoSkill", "wikiskill": "WikiSkill (community)", "trace2skill": "Trace2Skill", "ace": "ACE",
         "mipro": "MIPROv2", "harnesslens": "HarnessLens", "oneshot": "One-shot control", "seed": "Seed (no search)",
         "hcstock": r"CapEvolve as shipped, stock gate$^{\S}$", "bestofk": r"One-shot best of $k$"}
SUITE_TITLE = {"A": "Suite A, SpreadsheetBench, 70-task final set from the 912 residual pool (Gemma-4-31B-it)",
               "B": r"Suite B, $\tau^2$ retail, sealed test-40 (gpt-oss-120b)",
               "C": r"Suite C, $\tau^2$ airline, official test-20 (development-exposed)"}


GROUP = {"seed": "ref", "oneshot": "ref", "hc": "primary", "ao": "primary", "hcstock": "primary", "bestofk": "explor"}
GROUP_TITLE = {"ref": "Reference arms", "secondary": "Competitors, secondary family", "primary": "CapEvolve (primary family; the stock-gate row is post-search-time)",
               "explor": "Exploratory, outside the Holm family"}


def order(s):
    arms = s["arms"]
    base = sorted((a for a in arms if a not in ("seed", "oneshot", "hc", "ao", "hcstock", "bestofk")), key=lambda a: arms[a]["delta"])
    return ["seed"] + (["oneshot"] if "oneshot" in arms else []) + base + [a for a in ("hcstock", "hc", "ao") if a in arms] + [a for a in ("bestofk",) if a in arms]


def pct(x):
    return f"{100 * x:.1f}"


def sd(x):
    return f"{100 * x:+.1f}".replace("-", "$-$")


def ci(d):
    return f"{sd(d['delta'])} [{sd(d['lo'])}, {sd(d['hi'])}]"


def pf(p):
    return "$<$0.001" if p < 0.001 else f"{p:.3f}"


def wrap(mock):
    return (lambda x: rf"\pend{{{x}}}" if x not in ("--", "ref.") else x) if mock else (lambda x: x)


def tabular(spec, head, body, cap, label, mock, star=True):
    env = "table*" if star else "table"
    cap = cap + (" (placeholder)" if mock else "")
    L = [rf"\begin{{{env}}}[t]", r"\centering", r"\scriptsize", r"\setlength{\tabcolsep}{3.5pt}",
         rf"\caption{{{cap}}}", rf"\label{{{label}}}", rf"\begin{{tabular}}{{{spec}}}", r"\toprule", head, r"\midrule"]
    L += body + [r"\bottomrule", r"\end{tabular}", rf"\end{{{env}}}"]
    return "\n".join(L) + "\n"


def main_table(suites, data, label, cap):
    mock = data["source"] == "mock"
    w = wrap(mock)
    has_os = all("oneshot" in data["suites"][su]["arms"] for su in suites)
    ncol = 7 if has_os else 6
    body = []
    for i, su in enumerate(suites):
        s = data["suites"][su]
        if i:
            body.append(r"\midrule")
        body += [rf"\multicolumn{{{ncol}}}{{l}}{{\textit{{{SUITE_TITLE[su]}}}}} \\", r"\midrule"]
        group = None
        for a in order(s):
            v = s["arms"][a]
            g = GROUP[a] if a in GROUP else "secondary"
            if g != group:
                group = g
                body.append(rf"\multicolumn{{{ncol}}}{{l}}{{\textit{{{GROUP_TITLE[g]}}}}} \\")
            miss = w(f"{v['missing']}/{v['cells']}")
            if a == "seed":
                cells = [w(pct(v["score"])), "ref."] + ([w(sd(-s["arms"]["oneshot"]["delta"]))] if has_os else []) + ["--", "--", miss]
            elif a == "oneshot":
                cells = [w(pct(v["score"])), w(ci(v)), "ref.", w(pf(v["p_holm"])), w(f"{v['usd']:.0f}"), miss]
            else:
                p = w(pf(v["p_holm"])) if v["p_holm"] is not None else "--"
                cells = [w(pct(v["score"])), w(ci(v))] + ([w(ci(v["vs_oneshot"]))] if has_os else []) + [p, w(f"{v['usd']:.0f}"), miss]
            body.append(" & ".join([LABEL[a]] + cells) + r" \\")
        if s.get("s_stock"):
            body.append(rf"\multicolumn{{{ncol}}}{{l}}{{\textit{{Secondary family S-stock, post-search-time: as shipped minus}}}} \\")
            for r_ in s["s_stock"]:
                nm = "the seed" if r_["vs"] == "seed" else LABEL[r_["vs"]]
                cells = ["", w(ci(r_))] + ([""] if has_os else []) + [w(pf(r_["p_holm"])), "", ""]
                body.append(" & ".join([nm] + cells) + r" \\")
    head = (r"Arm & Score (\%) & $\Delta$ vs seed [CI] & " + (r"$\Delta$ vs one-shot [CI] & " if has_os else "") + r"$p_{\mathrm{Holm}}$ in family & USD & Missing \\")
    return tabular("lcc" + ("c" if has_os else "") + "rrr", head, body, cap, label, mock)


def promotions_table(data):
    mock = data["source"] == "mock"
    w = wrap(mock)
    body = []
    for i, su in enumerate("ABC"):
        s = data["suites"][su]
        if i:
            body.append(r"\midrule")
        body += [rf"\multicolumn{{6}}{{l}}{{\textit{{{SUITE_TITLE[su]}}}}} \\", r"\midrule"]
        for a in order(s):
            if a in ("seed", "oneshot", "bestofk"):
                continue
            v = s["arms"][a]
            pr, ca = v["promotions"], v["candidates"]
            ret = sum(1 for x in pr if x == 0)
            body.append(" & ".join([LABEL[a], w(f"{sum(ca) / len(ca):.1f}"), w("/".join(str(x) for x in ca)), w(f"{sum(pr) / len(pr):.1f}"),
                                    w("/".join(str(x) for x in pr)), w(f"{ret} of {len(pr)}")]) + r" \\")
    head = r"Arm & Screened, mean & Screened per seed & Promoted, mean & Promoted per seed & Returned artifact equals seed \\"
    cap = ("Promotions per search for every arm at the matched checkpoint: candidates screened, candidates promoted under the arm's own rule, "
           "and the number of seeds whose returned artifact is byte-identical to the seed artifact. "
           "CapEvolve with rule P is a deliberately conservative configuration, and the stock-gate rows show the other side of that trade.")
    return tabular("lccccc", head, body, cap, "tab:promotions", mock)


def _bestofk_pause():
    """Proposals completed and counted rollouts per seed, read from the pause record of the best-of-k run."""
    import json as _j
    f = pathlib_path("/home/dev/projects2/campaign-scratch/runs/E12C/bestofk/PAUSED.json")
    try:
        rec = _j.loads(f.read_text())
        d = rec["final"]  # the final block supersedes the snapshot taken at the first pause
        ks = [str(d[s]["proposals_completed"]) for s in ("s0", "s1", "s2")]
        rs = [str(d[s]["counted_incl_baseline"]) for s in ("s0", "s1", "s2")]
        return "/".join(ks), "/".join(rs)
    except Exception:
        return "6/6/8", "140/140/180"


def e12_table(data):
    BOK_K, BOK_ROLL = _bestofk_pause()
    mock = data["source"] == "mock"
    w = wrap(mock)
    body = []
    for su in "AC":
        s = data["suites"][su]
        body += [rf"\multicolumn{{7}}{{l}}{{\textit{{{SUITE_TITLE[su].split(',')[0]}}}}} \\"]
        for a, nm in (("hc", "Rule P"), ("hcstock", "Stock gate")) + ((("bestofk", r"Best of $k$"),) if su == "C" else ()):
            v = s["arms"][a]
            sdl = v["seed_deltas"]
            if a == "bestofk":
                cells = [w(sd(x)) for x in sdl] + ["--", "--", "--"]
            else:
                pr, ca = v["promotions"], v["candidates"]
                cells = [w(sd(x)) for x in sdl] + [w(f"{sum(ca) / len(ca):.1f}"), w(f"{sum(pr) / len(pr):.1f}"), w(f"{sum(1 for x in pr if x == 0)} of {len(pr)}")]
            body.append(" & ".join([nm] + cells) + r" \\")
        if su == "A":
            body.append(r"\midrule")
    head = r"Arm & Seed 0 & Seed 1 & Seed 2 & Screened & Promoted & Returned = seed \\"
    cap = (r"Stock-gate and rule-P hill-climb at the same rollout count, with per-seed paired deltas to the seed in points and promotion counts (means per search). "
           r"Descriptive and exploratory: no tests. The best-of-$k$ row draws $k$ independent one-shot proposals per seed on Suite C and keeps the best on the optimization set. It is truncated at $k=" + BOK_K + "$ proposals (" + BOK_ROLL + " counted rollouts) for seeds 0/1/2, paused to fund the Suite B stock-gate arm, and is exploratory and descriptive only.")
    return tabular("lcccccc", head, body, cap, "tab:e12", mock, star=False)


def cost_table(data):
    mock = data["source"] == "mock"
    w = wrap(mock)
    body = []
    for i, su in enumerate("ABC"):
        s = data["suites"][su]
        if i:
            body.append(r"\midrule")
        body += [rf"\multicolumn{{9}}{{l}}{{\textit{{{SUITE_TITLE[su]}}}}} \\", r"\midrule"]
        for a in order(s):
            if a == "seed":
                continue
            v = s["arms"][a]
            out = v.get("tok_out", 0.0)
            nc = v["tok_unc"] + v["tok_cw"] + out
            body.append(" & ".join([LABEL[a], w(str(v["rollouts"])), w(f"{v['tok_unc']:.1f}"), w(f"{out:.1f}"), w(f"{v['tok_cw']:.1f}"),
                                    w(f"{nc:.1f}"), w(f"{v['tok_cr']:.1f}"), w(f"{v['cap_used']:.0f}"), w(f"{v['wall_h']:.1f}")]) + r" \\")
    head = (r"Arm & Rollouts at \ckpt{} & Uncached input & Output & Cache write & Non-cache-read & Cache read & Cap used (\%) & Wall clock (h) \\")
    cap = ("Optimizer tokens in millions and wall clock per arm, summed over seeds. Non-cache-read is uncached input plus output plus cache write, "
           "the quantity the optimizer cap of 4M per search counts. Cache read is priced apart and not counted by the cap. "
           "Cap used is the largest seed as a share of the cap.")
    return tabular("lrrrrrrrr", head, body, cap, "tab:cost_tokens", mock)


def perseed_table(data):
    mock = data["source"] == "mock"
    w = wrap(mock)
    body = []
    for i, su in enumerate("ABC"):
        s = data["suites"][su]
        if i:
            body.append(r"\midrule")
        body += [rf"\multicolumn{{7}}{{l}}{{\textit{{{SUITE_TITLE[su]}}}}} \\", r"\midrule"]
        for a in order(s):
            if a == "seed":
                continue
            v = s["arms"][a]
            sdl = v["seed_deltas"] if "seed_deltas" in v else [v["delta"]] * 3
            body.append(" & ".join([LABEL[a]] + [w(sd(x)) for x in sdl] + [w(sd(v["delta"])), w(f"[{sd(v['bound_pess'])}, {sd(v['bound_opt'])}]"),
                                    w(f"{v['missing']}/{v['cells']}")]) + r" \\")
    head = r"Arm & Seed 0 & Seed 1 & Seed 2 & Mean $\Delta$ & Missingness bounds & Missing \\"
    cap = ("Paired delta to the seed for each search seed, in points, with the pessimistic and optimistic bounds on the mean. "
           "The pessimistic bound scores every missing cell of the arm as a loss and of the comparator as a win, and the optimistic bound does the reverse. "
           "Missing is missing over scheduled cells.")
    return tabular("lcccccr", head, body, cap, "tab:perseed", mock)


def ablation_table(data):
    mock = data["source"] == "mock"
    w = wrap(mock)
    D = data["suites"]["D"]
    body = []
    for k, c in D["cells"].items():
        v = D["vs_pt"].get(k)
        vs_pt = "ref." if k == "pt" else w(ci(v))
        p = "--" if k == "pt" else w(pf(v["p_holm"]))
        ps = w(pf(c["p_holm_seed"])) if "p_holm_seed" in c else "--"
        body.append(" & ".join([c["label"], str(c["seeds"]), w(ci(c)), ps, vs_pt, p,
                                w(f"{sum(c['promotions']) / len(c['promotions']):.1f}"), w(f"{c['returned_seed']} of {len(c['promotions'])}")]) + r" \\")
    it = D["interaction"]
    body.append(r"\midrule")
    body.append(rf"\multicolumn{{8}}{{l}}{{Interaction PT $-$ P $-$ T (descriptive): {w(ci(it))}. P versus T: {w(sd(D['p_vs_t']['delta']))} points, $p_{{\mathrm{{Holm}}}}$ {w(pf(D['p_vs_t']['p_holm']))}.}} \\")
    head = r"Cell & Seeds & $\Delta$ vs seed [CI] & $p_{\mathrm{Holm}}$ vs seed & $\Delta$ vs PT [CI] & $p_{\mathrm{Holm}}$ vs PT & Promoted per search & Returned = seed \\"
    cap = ("Suite D ablation cells on the 40 test tasks scored five times each; the 65 held-out tasks (selection and test) are descriptive. All cells are hill-climb with the stock gate except where the gate or the history is the factor. "
           f"Each cell changes one factor against the PT reference. The Holm family has {D['p_vs_t']['m']} contrasts. Differences below the pre-registered equivalence margin of 10 points are written inconclusive, not equal.")
    return tabular("lcccccrr", head, body, cap, "tab:ablation", mock, star=True)


def decomposition_table(data):
    mock = data["source"] == "mock"
    w = wrap(mock)
    body = []
    for r in data["decomposition"]:
        body.append(" & ".join([f"{r['cell']} seed {r['seed']}", w(sd(r["whole"])), w(sd(r["p_part"])), w(sd(r["t_part"])), w(sd(r["gap"]))]) + r" \\")
    head = r"Champion & Whole artifact & Prompt part & Tool part & Whole minus parts \\"
    cap = ("Decomposition of Suite D champions that edit both surfaces: paired delta of the whole artifact, of its prompt edits on the seed tools, "
           "and of its tool edits on the seed prompt, in points. A gap near zero means the parts add up.")
    return tabular("lrrrr", head, body, cap, "tab:decomp", mock, star=False)


def rq4_table(data):
    mock = data["source"] == "mock"
    w = wrap(mock)
    body = []
    for i, su in enumerate("ABC"):
        s = data["suites"][su]
        if i:
            body.append(r"\midrule")
        body += [rf"\multicolumn{{7}}{{l}}{{\textit{{{SUITE_TITLE[su]}}}}} \\", r"\midrule"]
        for a in order(s):
            if a in ("seed", "oneshot", "bestofk"):
                continue
            v = s["arms"][a]
            r_, sh = v["regress"], v["shrink"]
            body.append(" & ".join([LABEL[a], (w(f"{v['usd_per_point']['est']:.1f} [{v['usd_per_point']['lo']:.1f}, " + (f"{v['usd_per_point']['hi']:.1f}" if v['usd_per_point']['hi'] else "$\\infty$") + "]") if v['usd_per_point'] else "--"), w(f"{r_['pass_to_fail']:.1f}"), w(f"{r_['protect_viol']:.1f}"),
                                    w(sd(sh["sel_gain"])), w(sd(sh["final_gain"])), w(sd(sh["shrinkage"]))]) + r" \\")
    head = r"Arm & USD per point [interval] & Pass to fail & Protect-set violations & Selection gain & Final gain & Shrinkage \\"
    cap = ("Cost, regressions and selection-to-final shrinkage per arm. USD per point is the total optimizer cost over all seeds divided by the total final-set gain in points, with a bootstrap interval over seeds, and is undefined when the total gain is not positive. "
           "Pass to fail counts tasks the seed solved and the champion fails, per seed. Shrinkage is selection gain minus final gain, in points, and is zero for a seed that returned the seed artifact.")
    return tabular("lrrrrrr", head, body, cap, "tab:rq4", mock)


def suite_e_table(data):
    mock = data["source"] == "mock"
    w = wrap(mock)
    E = data["suites"]["E"]
    body = [r"\multicolumn{5}{l}{\textit{Family E, Holm m = 11: contrasts mirrored from Suite D}} \\", r"\midrule"]
    for c in E["family"]:
        rep = "replicated" if c["replicated"] else "not replicated"
        body.append(" & ".join([c["name"], w(ci(c)), w(pf(c["p_holm"])), w(sd(c["d_delta"])), w(rep)]) + r" \\")
    body += [r"\midrule", r"\multicolumn{5}{l}{\textit{Secondary family E-sec, Holm m = 4}} \\"]
    for c in E["secondary"]:
        body.append(" & ".join([c["name"], w(ci(c)), w(pf(c["p_holm"])), "--", "--"]) + r" \\")
    body += [r"\midrule", r"\multicolumn{5}{l}{\textit{Competitor family E-comp: PT minus competitor (replication domain, exploratory for generality)}} \\"]
    for c in E["competitors"]:
        if c["key"] == "hl":
            body.append(" & ".join([c["label"] + r" (exploratory, one seed, descriptive)", w(ci(c)), "--", "--", "--"]) + r" \\")
        else:
            nm = c["label"] + (r"$^{\dagger}$" if c["key"] == "ao" else "")
            body.append(" & ".join([nm, w(ci(c)), w(pf(c["p_holm"])), "--", "--"]) + r" \\")
    ao = next(c for c in E["competitors"] if c["key"] == "ao")
    others = [c for c in E["competitors"] if c["key"] not in ("ao", "hl")]
    body.append(r"\multicolumn{5}{l}{\textit{Sensitivity excluding agent-optimize$^{\dagger}$: " + ", ".join(f"{c['label']} {w(pf(c['p_holm_sens']))}" for c in others) + r"}} \\")
    head = r"Contrast & $\Delta$ [CI] & $p_{\mathrm{Holm}}$ & Suite D $\Delta$ & Replication \\"
    cap = ("Suite E, the airline replication of Suite D, on the 20 official test tasks scored five times each (the seed ten times); 3 seeds per cell. "
           "A Suite D contrast is replicated when the Suite E contrast has the same sign and a 95\\% interval that excludes zero, and is not replicated otherwise, which includes inconclusive. "
           "The minimum detectable difference at 20 tasks is \\mdeESeed{} points against the seed and \\mdeECellHolm{} between cells at the Holm level, so most contrasts read inconclusive, and no equivalence claim is made. "
           "Suite E is a replication on the development-exposed airline test set (T = 20, five trials per champion) and carries no sealed-set claim; D and E are never pooled. "
           r"$^{\dagger}$ Agent-optimize can read the gold actions of its own training tasks.")
    return tabular("lcccc", head, body, cap, "tab:suitee", mock, star=True)


def main():
    data = json.loads((PAPER / "results_data.json").read_text())
    cap_a = (r"Score is the final-set reward. $\Delta$ is the paired difference in points with a family-cluster-robust 95\% interval, "
             r"$p_{\mathrm{Holm}}$ is Holm-adjusted within the suite, and USD is optimizer cost at Sonnet list prices. "
             r"Missing is missing over scheduled cells. Tokens and wall clock are in Table~\ref{tab:cost_tokens}, per-seed values in Table~\ref{tab:perseed}. Suite A has no one-shot control. The stock-gate arm (E12A on Suite A, E12C on Suite C) is tested in its own secondary family S-stock, and its difference to rule-P hill-climb is descriptive.")
    T = PAPER / "tables"
    (T / "main_A.tex").write_text(main_table(["A"], data, "tab:main_a", "Suite A results, baselines by ascending delta and the CapEvolve arms last. The row marked $\\S$ is CapEvolve as shipped (stock gate), added after search-time results were seen, so it is post-search-time. " + cap_a))
    (T / "main_BC.tex").write_text(main_table(["B", "C"], data, "tab:main_bc", r"Suites B and C results. Columns as in Table~\ref{tab:main_a}."))
    (T / "cost_tokens.tex").write_text(cost_table(data))
    (T / "e12.tex").write_text(e12_table(data))
    (T / "ablation.tex").write_text(ablation_table(data))
    (T / "suite_e.tex").write_text(suite_e_table(data))
    (T / "decomp.tex").write_text(decomposition_table(data))
    (T / "rq4.tex").write_text(rq4_table(data))
    (T / "perseed.tex").write_text(perseed_table(data))
    print("tables written, source =", data["source"])


if __name__ == "__main__":
    main()
