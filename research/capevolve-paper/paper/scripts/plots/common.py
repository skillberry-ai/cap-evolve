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
    "oneshot":     ("One-shot ctrl",  "#999999", "p"),
    "seed":        ("Seed",           "#555555", "+"),
}
SUITE_ARMS = {
    "A": ["hc", "ao", "gepa", "skillopt", "metaharness", "evoskill", "wikiskill", "trace2skill", "ace", "mipro", "oneshot", "seed"],
    "B": ["hc", "ao", "gepa", "harnesslens", "oneshot", "seed"],
    "C": ["hc", "ao", "gepa", "harnesslens", "oneshot", "seed"],
}
SUITE_NAME = {"A": "Suite A (SpreadsheetBench)", "B": r"Suite B ($\tau^2$ retail)", "C": r"Suite C ($\tau^2$ airline)"}
ROLE_COLOR = {"target": "#0072B2", "user": "#56B4E9", "judge": "#E69F00", "optimizer": "#D55E00", "other": "#999999"}


def style():
    import matplotlib as mpl
    mpl.use("Agg")
    mpl.rcParams.update({
        "font.size": 7, "axes.labelsize": 7, "axes.titlesize": 7.5, "legend.fontsize": 6,
        "xtick.labelsize": 6.5, "ytick.labelsize": 6.5, "axes.linewidth": 0.6,
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
