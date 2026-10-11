"""Build the main per-suite result tables from ../results_data.json.

The same code renders mock and real data. When source == "mock", every number is wrapped in \\pend{}
so check_paper.py fails if the table survives into a final build.

Run:  python3 -I make_tables.py
"""
import json
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
LABEL = {"hc": "CapEvolve HC", "ao": "CapEvolve AO", "gepa": "GEPA", "skillopt": "SkillOpt", "metaharness": "Meta-Harness",
         "evoskill": "EvoSkill", "wikiskill": "WikiSkill (community)", "trace2skill": "Trace2Skill", "ace": "ACE",
         "mipro": "MIPROv2", "harnesslens": "HarnessLens", "oneshot": "One-shot control", "seed": "Seed (no search)"}
SUITE_TITLE = {"A": "Suite A, SpreadsheetBench verified-400 (Gemma-4-31B-it)",
               "B": r"Suite B, $\tau^2$ retail, sealed test-40 (gpt-oss-120b)",
               "C": r"Suite C, $\tau^2$ airline, official test-20 (development-exposed)"}
HEAD = (r"Arm & Score & $\Delta$ vs seed [CI] & $p_{\mathrm{Holm}}$ & Rollouts & "
        r"Uncached & Cache rd & Cache wr & USD & Wall (h) & Missing \\")


def cell(x, mock):
    return rf"\pend{{{x}}}" if mock else x


def pct(x):
    return f"{100 * x:.1f}"


def sd(x):
    return f"{100 * x:+.1f}".replace("-", "$-$")


def pf(p):
    return "$<$0.001" if p < 0.001 else f"{p:.3f}"


def rows(suite, s, mock):
    out = []
    for a, v in s["arms"].items():
        c = lambda t: cell(t, mock)
        if a == "seed":
            ci, p = "reference", "--"
            d = "0"
        else:
            d = sd(v["delta"])
            ci = f"[{sd(v['lo'])}, {sd(v['hi'])}]"
            p = pf(v["p_holm"])
        tok = ("--", "--", "--", "--") if a == "seed" else (f"{v['tok_unc']:.1f}", f"{v['tok_cr']:.1f}", f"{v['tok_cw']:.1f}", f"{v['usd']:.0f}")
        wall = "--" if a == "seed" else f"{v['wall_h']:.1f}"
        roll = "--" if a == "seed" else str(v["rollouts"])
        dcell = c(d) if a == "seed" else c(f"{d} {ci}")
        out.append(" & ".join([LABEL[a], c(pct(v["score"])), dcell, c(p) if p != "--" else p, c(roll) if roll != "--" else roll,
                              *[c(t) if t != "--" else t for t in tok], c(wall) if wall != "--" else wall, c(f"{v['missing']}/{v['cells']}")]) + r" \\")
    return out


def block(suite, s, mock):
    return [rf"\multicolumn{{11}}{{l}}{{\textit{{{SUITE_TITLE[suite]}}}}} \\", r"\midrule"] + rows(suite, s, mock)


def table(suites, data, label, caption):
    mock = data["source"] == "mock"
    cap = caption + (" (placeholder)" if mock else "")
    L = [r"\begin{table*}[t]", r"\centering", r"\scriptsize", r"\setlength{\tabcolsep}{3.2pt}",
         rf"\caption{{{cap}}}", rf"\label{{{label}}}", r"\begin{tabular}{lcccrrrrrrr}", r"\toprule", HEAD, r"\midrule"]
    for i, su in enumerate(suites):
        if i:
            L.append(r"\midrule")
        L += block(su, data["suites"][su], mock)[0:1] + [r"\midrule"] + rows(su, data["suites"][su], mock)
    L += [r"\bottomrule", r"\end{tabular}", r"\end{table*}"]
    return "\n".join(L) + "\n"


def main():
    data = json.loads((PAPER / "results_data.json").read_text())
    cap_common = (r"Score is the mean final-set reward in percent. $\Delta$ is the paired difference to the seed in points with a "
                  r"family-cluster-robust 95\% interval, and $p_{\mathrm{Holm}}$ is Holm-adjusted within the suite. "
                  r"Rollouts are target rollouts spent at the matched checkpoint $B^\ast$. Token columns count optimizer "
                  r"tokens in millions (uncached input, cache read, cache write). USD uses Sonnet list prices as a proxy. "
                  r"Missing is missing cells over scheduled cells, bounded in the analysis rather than imputed.")
    (PAPER / "tables" / "main_A.tex").write_text(table(["A"], data, "tab:main_a", "Suite A final-set results. " + cap_common))
    (PAPER / "tables" / "main_BC.tex").write_text(table(["B", "C"], data, "tab:main_bc", r"Suites B and C final-set results. " + cap_common))
    print("tables written, source =", data["source"])


if __name__ == "__main__":
    main()
