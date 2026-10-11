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
    fig, axes = plt.subplots(1, 3, figsize=(C.FULL_W, 2.3), sharey=False)
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
            ax.plot(x, [y * 100 for y in cv["mean"]], color=col, label=lab, marker=mk, markevery=5, ms=3)
            ax.fill_between(x, [y * 100 for y in cv["lo"]], [y * 100 for y in cv["hi"]], color=col, alpha=0.10, lw=0)
        b = s["params"]["bstar"]
        ax.axvline(b, color="k", ls="--", lw=0.7)
        ax.text(b, 0.02, r"$B^\ast$ ", va="bottom", ha="right", fontsize=6.5, transform=ax.get_xaxis_transform())
        ax.set_title(C.SUITE_NAME[su])
        ax.set_xlabel("target rollouts")
    axes[0].set_ylabel("best-so-far score (%)")
    h, l = axes[0].get_legend_handles_labels()
    for ax in axes[1:]:
        hh, ll = ax.get_legend_handles_labels()
        for x, y in zip(hh, ll):
            if y not in l:
                h.append(x); l.append(y)
    fig.legend(h, l, loc="lower center", ncol=7, frameon=False, bbox_to_anchor=(0.5, -0.12), fontsize=6)
    fig.tight_layout()
    C.save(fig, "fig_anytime", MOCK)


def forest():
    fig, axes = plt.subplots(1, 3, figsize=(C.FULL_W, 2.6), gridspec_kw=dict(width_ratios=[12, 5, 5]))
    for ax, su in zip(axes, SUITES):
        s = data["suites"][su]
        arms = [a for a in C.SUITE_ARMS[su] if a != "seed"]
        for i, a in enumerate(arms):
            v = s["arms"][a]
            lab, col, mk = C.ARMS[a]
            sig = v["p_holm"] is not None and v["p_holm"] < 0.05
            y = len(arms) - 1 - i
            ax.plot([v["lo"] * 100, v["hi"] * 100], [y, y], color=col, lw=1.3)
            ax.plot(v["delta"] * 100, y, marker=mk, color=col, mfc=col if sig else "white", ms=4.5, mew=1.0)
        ax.axvline(0, color="k", lw=0.7)
        ax.set_yticks(range(len(arms)))
        ax.set_yticklabels([C.ARMS[a][0] for a in reversed(arms)] if su == "A" else [""] * len(arms))
        ax.set_title(C.SUITE_NAME[su])
        ax.set_xlabel(r"paired $\Delta$ vs seed (points)")
        ax.grid(axis="y", alpha=0)
    fig.text(0.99, 0.0, "filled: Holm p < 0.05", ha="right", va="bottom", fontsize=6)
    fig.tight_layout()
    C.save(fig, "fig_forest", MOCK)


def pareto():
    fig, axes = plt.subplots(1, 3, figsize=(C.FULL_W, 2.2))
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
                        color=col, marker=mk, ms=4, lw=0.6, capsize=0, label=lab, elinewidth=0.6, alpha=0.9)
            pts.append((x, v["delta"] * 100))
        pts.sort()
        front, best = [], -1e9
        for x, y in pts:
            if y > best:
                front.append((x, y)); best = y
        ax.step([p[0] for p in front], [p[1] for p in front], where="post", color="k", lw=0.7, ls="--")
        ax.set_xscale("log")
        ax.xaxis.set_major_formatter(ScalarFormatter())
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.axhline(0, color="k", lw=0.5)
        ax.set_title(C.SUITE_NAME[su])
        ax.set_xlabel("optimizer cost (USD, list-price proxy)")
    axes[0].set_ylabel(r"paired $\Delta$ (points)")
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=6, frameon=False, bbox_to_anchor=(0.5, -0.16), fontsize=6)
    fig.tight_layout()
    C.save(fig, "fig_pareto", MOCK)


def families():
    fams = data["suites"]["A"]["families"]
    names = list(fams)
    arms = [a for a in fams[names[0]]["arms"]]
    fig, ax = plt.subplots(figsize=(C.COL_W, 2.4))
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
    ax.set_ylabel(r"paired $\Delta$ (points)")
    ax.set_xlabel("task family, Suite A")
    ax.legend(ncol=3, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.25), fontsize=6)
    fig.tight_layout()
    C.save(fig, "fig_families", MOCK)


if __name__ == "__main__":
    anytime(); forest(); pareto(); families()
    print("mock plots written" if MOCK else "real plots written")
