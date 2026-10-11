"""Shared plot style, arm registry and data loading for the results figures.

One arm keeps one colour and one marker in every figure. Palette: Okabe-Ito plus greys,
chosen to stay distinguishable under the common colour-vision deficiencies.
Sizes follow the MLSys two-column layout: 3.3 in column, 6.9 in full width.
"""
import json
import os
from pathlib import Path

PAPER = Path(__file__).resolve().parents[2]
REPO = PAPER.parent
DATA_JSON = PAPER / "results_data.json"   # written by mock_numbers.py or real_numbers.py

COL_W, FULL_W = 3.3, 6.9

# key: (label, colour, marker)
ARMS = {
    "hc":          ("CapEvolve HC",   "#0072B2", "o"),
    "ao":          ("CapEvolve AO",   "#56B4E9", "s"),
    "gepa":        ("GEPA",           "#E69F00", "^"),
    "skillopt":    ("SkillOpt",       "#009E73", "v"),
    "metaharness": ("Meta-Harness",   "#D55E00", "D"),
    "evoskill":    ("EvoSkill",       "#CC79A7", "P"),
    "wikiskill":   ("WikiSkill-comm.", "#8A7B00", "X"),
    "trace2skill": ("Trace2Skill",    "#000000", "*"),
    "ace":         ("ACE",            "#882255", "h"),
    "mipro":       ("MIPROv2",        "#44AA99", "<"),
    "harnesslens": ("HarnessLens",    "#332288", ">"),
    "hcstock":     ("CapEvolve HC, stock gate", "#6C9BC4", "H"),
    "oneshot":     ("One-shot control",  "#999999", "p"),
    "seed":        ("Seed",           "#555555", "+"),
}
SUITE_ARMS = {
    "A": ["hc", "ao", "gepa", "skillopt", "metaharness", "evoskill", "wikiskill", "trace2skill", "ace", "mipro", "hcstock", "seed"],
    "B": ["hc", "ao", "gepa", "harnesslens", "oneshot", "seed"],
    "C": ["hc", "ao", "gepa", "harnesslens", "oneshot", "hcstock", "seed"],
}
SUITE_NAME = {"A": "Suite A (SpreadsheetBench)", "B": "Suite B (\u03c4\u00b2 retail)", "C": "Suite C (\u03c4\u00b2 airline)"}  # plain Unicode: mathtext tau extracts as a wrong glyph from the PDF
CKPT = "B*"  # label of the matched checkpoint; set to the symbol paper-core adopts
ROLE_COLOR = {"target": "#0072B2", "user": "#56B4E9", "judge": "#E69F00", "optimizer": "#D55E00", "other": "#999999"}


CAP = ("hc", "ao")  # CapEvolve arms are drawn thick and opaque, all others thinner, so the key comparison stands out


def lw(a):
    return 2.0 if a in CAP else 0.9


def alpha(a):
    return 1.0 if a in CAP else 0.75


def style():
    import matplotlib as mpl
    mpl.use("Agg")
    mpl.rcParams.update({
        "font.size": 8.5, "axes.labelsize": 8.5, "axes.titlesize": 8.5, "legend.fontsize": 7.5,
        "xtick.labelsize": 8, "ytick.labelsize": 8, "axes.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 1.1,
        "pdf.fonttype": 42, "ps.fonttype": 42, "figure.dpi": 150, "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02, "axes.grid": True, "grid.linewidth": 0.3, "grid.alpha": 0.5,
        "font.family": "serif", "mathtext.fontset": "cm",
    })


def watermark(fig):
    fig.text(0.5, 0.5, "PLACEHOLDER: mock data", ha="center", va="center", rotation=28,
             fontsize=17 * min(1.0, fig.get_figwidth() / 6.0), color="#cc0000", alpha=0.22, weight="bold", zorder=1000)


def load():
    return json.loads(DATA_JSON.read_text())


def save(fig, name, mock):
    if mock:
        watermark(fig)
    out = PAPER / "figures" / f"{name}.pdf"
    fig.savefig(out)
    return out


def table_order(suite_data):
    """Row order shared by the tables and the forest plot: one-shot control, baselines by ascending delta, CapEvolve last, exploratory arm after."""
    arms = suite_data["arms"]
    base = sorted((a for a in arms if a not in ("seed", "oneshot", "hc", "ao", "hcstock")), key=lambda a: arms[a]["delta"])
    return (["oneshot"] if "oneshot" in arms else []) + base + [a for a in ("hc", "ao") if a in arms] + (["hcstock"] if "hcstock" in arms else [])
