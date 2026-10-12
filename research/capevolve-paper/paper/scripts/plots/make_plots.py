"""Figures that depend on final-evaluation data: anytime curves, forest, cost-quality Pareto, Suite A families.

Reads ../../results_data.json. If source == "mock" every figure carries the PLACEHOLDER watermark and the
LaTeX caption (results.tex) ends with "(placeholder)". Figures built from real data (audit, rule P, role
breakdown) live in real_plots.py and never carry the watermark.

Run:  python3 -I make_plots.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

C.style()
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import NullFormatter, ScalarFormatter  # noqa: E402

data = C.load()
MOCK = data["source"] == "mock"
SUITES = ["A", "B", "C"]


def anytime():
    fig, axes = plt.subplots(1, 3, figsize=(C.FULL_W, 2.6), sharey=False)
    for ax, su in zip(axes, SUITES):
        s = data["suites"][su]
        for a in C.SUITE_ARMS[su]:
            v = s["arms"][a]
            if a == "seed":
                ax.axhline(v["score"] * 100, color=C.ARMS["seed"][1], ls=":", lw=0.9, label=C.ARMS["seed"][0])
                continue
            if not v.get("curve"):
                continue
            lab, col, mk = C.ARMS[a]
            cv = v["curve"]
            x = cv["rollouts"]
            ax.plot(x, [y * 100 for y in cv["mean"]], color=col, label=lab, marker=mk, markevery=5, ms=3.5, lw=C.lw(a), alpha=C.alpha(a), zorder=3 if a in C.CAP else 2)
            ax.fill_between(x, [y * 100 for y in cv["lo"]], [y * 100 for y in cv["hi"]], color=col, alpha=0.10 if a in C.CAP else 0.0, lw=0)
        b = s["params"]["bstar"]
        ax.axvline(b, color="k", ls="--", lw=0.7)
        ax.text(b, 0.02, C.CKPT + " ", va="bottom", ha="right", fontsize=6.5, transform=ax.get_xaxis_transform())
        ax.set_title(C.SUITE_NAME[su])
        ax.set_xlabel("Target rollouts")
    axes[0].set_ylabel("Best selection-set score so far (%)")
    h, l = axes[0].get_legend_handles_labels()
    for ax in axes[1:]:
        hh, ll = ax.get_legend_handles_labels()
        for x, y in zip(hh, ll):
            if y not in l:
                h.append(x); l.append(y)
    fig.legend(h, l, loc="lower center", ncol=5, frameon=False, bbox_to_anchor=(0.5, -0.2))
    fig.tight_layout()
    C.save(fig, "fig_anytime", MOCK)


def forest():
    # Panels share the row order of their arm list. B and C share the same arms, so they also share the y axis and align row for row.
    fig, axes = plt.subplots(1, 3, figsize=(C.FULL_W, 3.1), gridspec_kw=dict(width_ratios=[10, 7, 7]), constrained_layout=True)
    for ax, su, tag in zip(axes, SUITES, "abc"):
        s = data["suites"][su]
        arms = C.table_order(s)
        for i, a in enumerate(arms):
            v = s["arms"][a]
            lab, col, mk = C.ARMS[a]
            sig = v["p_holm"] is not None and v["p_holm"] < 0.05
            y = len(arms) - 1 - i
            ax.plot([v["lo"] * 100, v["hi"] * 100], [y, y], color=col, lw=C.lw(a) + 0.4, alpha=C.alpha(a))
            ax.plot(v["delta"] * 100, y, marker=mk, color=col, mfc=col if sig else "white", ms=6 if a in C.CAP else 4.5, mew=1.0)
        ax.axvline(0, color="k", lw=0.7)
        ax.set_yticks(range(len(arms)))
        ax.set_yticklabels([C.ARMS[a][0] for a in reversed(arms)])
        ax.set_title(f"({tag}) {C.SUITE_NAME[su]}")
        ax.grid(axis="y", alpha=0)
    fig.supxlabel("Paired difference to seed (points). Filled markers: Holm-adjusted p < 0.05", fontsize=8.5, y=0.0)
    C.save(fig, "fig_forest", MOCK)


def contrast():
    fig, axes = plt.subplots(1, 3, figsize=(C.FULL_W, 3.1), gridspec_kw=dict(width_ratios=[10, 7, 7]), constrained_layout=True)
    for ax, su, tag in zip(axes, SUITES, "abc"):
        s = data["suites"][su]
        others = [a for a in C.SUITE_ARMS[su] if a not in ("hc", "ao", "seed", "hcstock")]
        for i, a in enumerate(others):
            y = len(others) - 1 - i
            for off, cap in ((0.17, "hc"), (-0.17, "ao")):
                c = s["contrasts"][f"{cap}-{a}"]
                col, mk = C.ARMS[cap][1], C.ARMS[cap][2]
                ax.plot([c["lo"] * 100, c["hi"] * 100], [y + off, y + off], color=col, lw=1.8)
                ax.plot(c["delta"] * 100, y + off, marker=mk, color=col, ms=5, mfc="white" if c["lo"] < 0 < c["hi"] else col)
        ax.axvline(0, color="k", lw=0.7)
        ax.set_yticks(range(len(others)))
        ax.set_yticklabels([C.ARMS[a][0] for a in reversed(others)])
        ax.set_title(f"({tag}) {C.SUITE_NAME[su]}")
        ax.grid(axis="y", alpha=0)
    axes[0].plot([], [], color=C.ARMS["hc"][1], marker="o", label="CapEvolve HC minus arm")
    axes[0].plot([], [], color=C.ARMS["ao"][1], marker="s", label="CapEvolve AO minus arm")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 1.07))
    fig.supxlabel("Difference in paired delta (points). Filled markers: interval excludes zero", fontsize=8.5, y=0.0)
    C.save(fig, "fig_contrast", MOCK)


CELL_COL = {"ctl": "#999999", "p": "#56B4E9", "t": "#009E73", "pt": "#003F73", "rulep": "#0072B2", "onestage": "#D55E00",
            "nohist": "#CC79A7", "gepa": "#E69F00", "td": "#8A7B00", "pts": "#882255"}
CELL_MK = {"ctl": "p", "p": "s", "t": "^", "pt": "H", "rulep": "o", "onestage": "D", "nohist": "P", "gepa": "v", "td": "X", "pts": "*"}


def ablate():
    """Fig. 3: ablation small multiples. Every panel shows the difference to the seed in points with 95% intervals."""
    D = data["suites"]["D"]
    cells = D["cells"]
    fig = plt.figure(figsize=(C.FULL_W, 4.4), constrained_layout=True)
    gs = fig.add_gridspec(2, 3)
    axes = {"a": fig.add_subplot(gs[0, 0]), "b": fig.add_subplot(gs[0, 1]), "c": fig.add_subplot(gs[0, 2]),
            "d": fig.add_subplot(gs[1, 0:2]), "e": fig.add_subplot(gs[1, 2])}

    def rows(ax, keys, title, names):
        for i, k in enumerate(keys):
            c = cells[k]
            y = len(keys) - 1 - i
            col, mk = CELL_COL.get(k, "#555555"), CELL_MK.get(k, "o")
            ax.plot([c["lo"] * 100, c["hi"] * 100], [y, y], color=col, lw=2.0 if k == "pt" else 1.3)
            ax.plot(c["delta"] * 100, y, marker=mk, color=col, ms=6 if k == "pt" else 5)
        ax.axvline(0, color="k", lw=0.7)
        ax.set_yticks(range(len(keys)))
        ax.set_yticklabels([names[k] for k in reversed(keys)])
        ax.set_title(title, loc="left")
        ax.set_xlabel("Difference to seed (points)")
        ax.grid(axis="y", alpha=0)

    names = {"ctl": "One-shot control", "p": "Prompt only", "t": "Tools only", "pt": "Prompt and tools", "rulep": "Rule P",
             "onestage": "One-stage gate", "nohist": "Without fixed/broke history", "gepa": "GEPA, prompt only"}
    rows(axes["a"], ["ctl", "p", "t", "pt"], "(a) Surface width", names)
    ax = axes["b"]
    ys, labs = [], []
    for i, su in enumerate("ABC"):
        for j, a in enumerate(("hc", "ao")):
            v = data["suites"][su]["arms"][a]
            y = 5 - (2 * i + j)
            ax.plot([v["lo"] * 100, v["hi"] * 100], [y, y], color=C.ARMS[a][1], lw=1.6)
            ax.plot(v["delta"] * 100, y, marker=C.ARMS[a][2], color=C.ARMS[a][1], ms=5)
            ys.append(y); labs.append(f"{su}, {'hill-climb' if a == 'hc' else 'agent-optimize'}")
    ax.axvline(0, color="k", lw=0.7)
    ax.set_yticks(ys); ax.set_yticklabels(labs)
    ax.set_title("(b) Orchestration", loc="left"); ax.set_xlabel("Difference to seed (points)"); ax.grid(axis="y", alpha=0)
    rows(axes["c"], ["pt", "rulep", "onestage"], "(c) Acceptance gate", dict(names, pt="Stock gate"))
    rows(axes["d"], ["pt", "nohist", "p", "gepa"], "(d) Context and loop, same target", dict(names, p="CapEvolve, prompt only"))
    ax = axes["e"]
    it = D["interaction"]
    ax.plot([it["lo"] * 100, it["hi"] * 100], [0, 0], color=CELL_COL["pt"], lw=2.0)
    ax.plot(it["delta"] * 100, 0, marker="H", color=CELL_COL["pt"], ms=6)
    ax.axvline(0, color="k", lw=0.7)
    ax.set_yticks([0]); ax.set_yticklabels(["Prompt and tools minus each alone"])
    ax.set_title("(e) Interaction", loc="left"); ax.set_xlabel("Difference (points)"); ax.grid(axis="y", alpha=0)
    C.save(fig, "fig_ablate", MOCK)


def nullpool():
    """E22 null pool, mock: false-accept rate per ten-candidate search for each gate, with the simulated value."""
    npool = data["null_pool"]
    fig, ax = plt.subplots(figsize=(C.COL_W, 1.9))
    ks = [("rulep", "Rule P"), ("onestage", "One-stage gate"), ("stock", "Stock gate")]
    for i, (k, lab) in enumerate(ks):
        y = len(ks) - 1 - i
        v = npool[k]
        ax.barh(y, v["rate"] * 100, color={"rulep": CELL_COL["rulep"], "onestage": CELL_COL["onestage"], "stock": CELL_COL["pt"]}[k], height=0.55)
        ax.plot([v["lo"] * 100, v["hi"] * 100], [y, y], color="k", lw=0.9)
        ax.plot(v["sim"] * 100, y, marker="|", color="#cc0000", ms=11, mew=1.8)
    ax.set_yticks(range(len(ks))); ax.set_yticklabels([l for _, l in reversed(ks)])
    ax.set_xlim(0, 100)
    ax.set_xlabel("Null searches with a false promotion (%)")
    ax.plot([], [], marker="|", color="#cc0000", ms=9, mew=1.6, ls="", label="Simulation")
    ax.legend(frameon=False, loc="upper right", fontsize=7)
    ax.grid(axis="y", alpha=0)
    fig.tight_layout()
    C.save(fig, "fig_nullpool", MOCK)


def pareto():
    fig, axes = plt.subplots(1, 3, figsize=(C.FULL_W, 2.5))
    for ax, su in zip(axes, SUITES):
        s = data["suites"][su]
        pts = []
        for a in C.SUITE_ARMS[su]:
            if a in ("seed",):
                continue
            v = s["arms"][a]
            lab, col, mk = C.ARMS[a]
            x = max(v["usd"], 0.5)
            ax.errorbar(x, v["delta"] * 100, yerr=[[(v["delta"] - v["lo"]) * 100], [(v["hi"] - v["delta"]) * 100]],
                        color=col, marker=mk, lw=0.6, capsize=0, label=lab, elinewidth=C.lw(a) * 0.7, alpha=C.alpha(a), ms=6 if a in C.CAP else 4)
            pts.append((x, v["delta"] * 100))
        pts.sort()
        front, best = [], -1e9
        for x, y in pts:
            if y > best:
                front.append((x, y)); best = y
        ax.step([p[0] for p in front], [p[1] for p in front], where="post", color="k", lw=0.7, ls="--")
        ax.set_xscale("log")
        lo_, hi_ = ax.get_xlim()
        ticks = [t for t in (2, 3, 5, 10, 20, 30, 50, 100, 200, 300, 500, 1000) if lo_ * 0.8 <= t <= hi_ * 1.25]
        ax.set_xticks(ticks)
        ax.xaxis.set_major_formatter(ScalarFormatter())
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.set_xlim(lo_ * 0.85, hi_ * 1.2)
        ax.axhline(0, color="k", lw=0.5)
        ax.set_title(C.SUITE_NAME[su])
        ax.set_xlabel("Optimizer cost (USD, log scale)")
    axes[0].set_ylabel("Paired difference to seed (points)")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=5, frameon=False, bbox_to_anchor=(0.5, -0.22))
    fig.tight_layout()
    C.save(fig, "fig_pareto", MOCK)


def families():
    fams = data["suites"]["A"]["families"]
    names = list(fams)
    arms = [a for a in fams[names[0]]["arms"]]
    fig, ax = plt.subplots(figsize=(C.COL_W, 2.6))
    w = 0.8 / len(arms)
    for j, a in enumerate(arms):
        lab, col, mk = C.ARMS[a]
        xs = [i + (j - (len(arms) - 1) / 2) * w for i in range(len(names))]
        d = [fams[n]["arms"][a]["delta"] * 100 for n in names]
        lo = [(fams[n]["arms"][a]["delta"] - fams[n]["arms"][a]["lo"]) * 100 for n in names]
        hi = [(fams[n]["arms"][a]["hi"] - fams[n]["arms"][a]["delta"]) * 100 for n in names]
        ax.errorbar(xs, d, yerr=[lo, hi], fmt=mk, color=col, ms=3, lw=0.6, label=lab)
    ax.axhline(0, color="k", lw=0.6)
    ax.set_xticks(range(len(names)))
    ax.set_xticklabels([f"{n}\n(n={fams[n]['n_tasks']})" for n in names])
    ax.set_ylabel("Paired difference to seed (points)")
    ax.set_xlabel("Task family, Suite A")
    h_, l_ = ax.get_legend_handles_labels()
    fig.legend(h_, l_, loc="lower center", ncol=3, frameon=False, bbox_to_anchor=(0.5, -0.12))
    fig.tight_layout()
    C.save(fig, "fig_families", MOCK)


if __name__ == "__main__":
    anytime(); forest(); contrast(); ablate(); nullpool(); pareto(); families()
    print("mock plots written" if MOCK else "real plots written")
