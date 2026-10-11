"""Build the result tables from ../results_data.json.

Main tables (body): score, delta vs seed [CI], delta vs one-shot [CI], Holm p, USD, missing cells.
Appendix tables: tokens and wall clock (tab:cost_tokens), per-seed deltas with missingness bounds (tab:perseed).
Rows: seed, one-shot control, then baselines by ascending delta, CapEvolve arms last.
The same code renders mock and real data. When source == "mock", every number is wrapped in \\pend{}.

Run:  python3 -I make_tables.py
"""
import json
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
LABEL = {"hc": "CapEvolve HC", "ao": "CapEvolve AO", "gepa": "GEPA", "skillopt": "SkillOpt", "metaharness": "Meta-Harness",
         "evoskill": "EvoSkill", "wikiskill": "WikiSkill (community)", "trace2skill": "Trace2Skill", "ace": "ACE",
         "mipro": "MIPROv2", "harnesslens": "HarnessLens", "oneshot": "One-shot control", "seed": "Seed (no search)",
         "hcstock": r"CapEvolve HC, stock gate \textit{(exploratory)}"}
SUITE_TITLE = {"A": "Suite A, SpreadsheetBench verified-400 (Gemma-4-31B-it)",
               "B": r"Suite B, $\tau^2$ retail, sealed test-40 (gpt-oss-120b)",
               "C": r"Suite C, $\tau^2$ airline, official test-20 (development-exposed)"}


def order(s):
    arms = s["arms"]
    base = sorted((a for a in arms if a not in ("seed", "oneshot", "hc", "ao", "hcstock")), key=lambda a: arms[a]["delta"])
    return ["seed"] + (["oneshot"] if "oneshot" in arms else []) + base + [a for a in ("hc", "ao") if a in arms] + (["hcstock"] if "hcstock" in arms else [])


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
        for a in order(s):
            v = s["arms"][a]
            miss = w(f"{v['missing']}/{v['cells']}")
            if a == "seed":
                cells = [w(pct(v["score"])), "ref."] + ([w(sd(-s["arms"]["oneshot"]["delta"]))] if has_os else []) + ["--", "--", miss]
            elif a == "oneshot":
                cells = [w(pct(v["score"])), w(ci(v)), "ref.", w(pf(v["p_holm"])), w(f"{v['usd']:.0f}"), miss]
            else:
                p = w(pf(v["p_holm"])) if v["p_holm"] is not None else "--"
                cells = [w(pct(v["score"])), w(ci(v))] + ([w(ci(v["vs_oneshot"]))] if has_os else []) + [p, w(f"{v['usd']:.0f}"), miss]
            body.append(" & ".join([LABEL[a]] + cells) + r" \\")
    head = (r"Arm & Score (\%) & $\Delta$ vs seed [CI] & " + (r"$\Delta$ vs one-shot [CI] & " if has_os else "") + r"$p_{\mathrm{Holm}}$ & USD & Missing \\")
    return tabular("lccc" + ("c" if has_os else "") + "rrr", head, body, cap, label, mock)


def promotions_table(data):
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
            pr, ca = v["promotions"], v["candidates"]
            body.append(" & ".join([LABEL[a]] + [w(str(x)) for x in pr] + [w(f"{sum(pr) / len(pr):.1f}"), w(f"{sum(ca) / len(ca):.1f}"),
                                    w(f"{100 * sum(pr) / max(sum(ca), 1):.0f}")]) + r" \\")
    head = r"Arm & Seed 0 & Seed 1 & Seed 2 & Mean per search & Candidates evaluated & Promoted (\%) \\"
    cap = ("Promotions per search for every arm, from the candidate logs, with the mean number of candidates evaluated. "
           "A promotion is a candidate that the arm's own acceptance rule put on its lineage. "
           "CapEvolve with rule P is a deliberately conservative configuration and is expected to promote rarely, "
           "and the stock-gate rows (E12) show the other side of that trade.")
    return tabular("lcccccr", head, body, cap, "tab:promotions", mock)


def cost_table(data):
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
            nc = v["tok_unc"] + v["tok_cw"] + v.get("tok_out", 0.0)
            body.append(" & ".join([LABEL[a], w(str(v["rollouts"])), w(f"{nc:.1f}"), w(f"{v['tok_cr']:.1f}"), w(f"{nc + v['tok_cr']:.1f}"),
                                    w(f"{v['cap_used']:.0f}"), w(f"{v['wall_h']:.1f}")]) + r" \\")
    head = r"Arm & Rollouts at $B^\ast$ & Non-cache-read & Cache read & Incl.\ cache read & Cap used (\%) & Wall clock (h) \\"
    cap = ("Optimizer tokens in millions and wall clock per arm, summed over seeds. Non-cache-read tokens are uncached input, output and cache writes, "
           "the quantity the optimizer cap of 4M per search counts. The last token column adds cache reads, which the cap ignores. "
           "Cap used is the largest seed as a share of the cap.")
    return tabular("lrrrrrr", head, body, cap, "tab:cost_tokens", mock)


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


def main():
    data = json.loads((PAPER / "results_data.json").read_text())
    cap_a = (r"Score is the final-set reward. $\Delta$ is the paired difference in points with a family-cluster-robust 95\% interval, "
             r"$p_{\mathrm{Holm}}$ is Holm-adjusted within the suite, and USD is optimizer cost at Sonnet list prices. "
             r"Missing is missing over scheduled cells. Tokens and wall clock are in Table~\ref{tab:cost_tokens}, per-seed values in Table~\ref{tab:perseed}, promotions per search in Table~\ref{tab:promotions}. Suite A has no one-shot control. The stock-gate arm (E12A on Suite A, E12C on Suite C) is exploratory and outside the Holm family.")
    T = PAPER / "tables"
    (T / "main_A.tex").write_text(main_table(["A"], data, "tab:main_a", "Suite A results, baselines by ascending delta and CapEvolve last, with the exploratory stock-gate arm below. " + cap_a))
    (T / "main_BC.tex").write_text(main_table(["B", "C"], data, "tab:main_bc", r"Suites B and C results. Columns as in Table~\ref{tab:main_a}."))
    (T / "cost_tokens.tex").write_text(cost_table(data))
    (T / "promotions.tex").write_text(promotions_table(data))
    (T / "perseed.tex").write_text(perseed_table(data))
    print("tables written, source =", data["source"])


if __name__ == "__main__":
    main()
