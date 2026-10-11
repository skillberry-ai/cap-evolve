"""Rule-P operating point under a hard rollout budget (600 target rollouts/search, val-40, screen = 1 trial/task).

Budget accounting: seed eval 40; each candidate screen 40; each screen-passing candidate confirmation 2*40*n_conf
(candidate and incumbent, fresh seeds). A candidate whose screen passes but whose confirmation does not fit in the
remaining budget ends the search (agent-optimize refuses the spend). The REAL promotion.screen/decide and gate.decide
are used. Promotion rule P: screen k_se=1 on the unmasked vector; options vary (n_conf, z_conf, dmin).
One-stage rows accept on the screen alone (gate.decide paired, k_se) with no confirmation.

    python -I sim_budget.py [--reps N]
"""
import argparse, json, random, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sim_common import OUT, apply_edit, draw_base, md_table, mean, paired_decide, pool_map, seeds, task_means, draw_trials  # noqa: E402
from sim_gate import noisy_edit, _candidate  # noqa: E402
from cap_evolve import promotion  # noqa: E402

T, BUDGET = 40, 600
OPTIONS = {  # name: (kind, params)
    "a: P n_conf=3 z=2.0 dmin=.02": ("P", dict(n_conf=3, z_conf=2.0, dmin=0.02)),
    "b: P n_conf=3 z=1.645 dmin=0": ("P", dict(n_conf=3, z_conf=1.645, dmin=0.0)),
    "c: P n_conf=3 z=1.282 dmin=0": ("P", dict(n_conf=3, z_conf=1.282, dmin=0.0)),
    "d: P n_conf=5 z=1.645 dmin=0": ("P", dict(n_conf=5, z_conf=1.645, dmin=0.0)),
    "e: P n_conf=2 z=1.282 dmin=0 (fresh only)": ("P", dict(n_conf=2, z_conf=1.282, dmin=0.0)),
    "h: P n_conf=3 z=1.0 dmin=0": ("P", dict(n_conf=3, z_conf=1.0, dmin=0.0)),
    "i: P n_conf=3 z=0.842 dmin=0": ("P", dict(n_conf=3, z_conf=0.842, dmin=0.0)),
    "j: P n_conf=4 z=1.282 dmin=0": ("P", dict(n_conf=4, z_conf=1.282, dmin=0.0)),
    "f: one-stage k=1": ("one", dict(k=1.0)),
    "g: one-stage k=1.645": ("one", dict(k=1.645)),
}


def ev(rng, p, n):
    return task_means(draw_trials(rng, p, n))


def step(rng, opt, cur_meas, cand_true, cur_true, spent):
    """One candidate. Returns (status, new_meas or None, spent). status: promote|reject|stop."""
    kind, prm = OPTIONS[opt]
    if spent + T > BUDGET:
        return "stop", None, spent
    cand = ev(rng, cand_true, 1); spent += T
    deltas = [c - p for c, p in zip(cand, cur_meas)]
    if kind == "one":
        return ("promote" if paired_decide(cur_meas, cand, k_se=prm["k"]).accept else "reject"), cand, spent
    P = promotion.PromotionParams(k_se=1.0, n_conf=prm["n_conf"], dmin=prm["dmin"], z_conf=prm["z_conf"], min_coverage=0.6)
    if not promotion.screen(deltas, 1.0)["pass"]:
        return "reject", None, spent
    cost = 2 * T * prm["n_conf"]
    if spent + cost > BUDGET:
        return "stop", None, spent
    spent += cost
    held = {}

    def cf():
        held["c"] = ev(rng, cand_true, prm["n_conf"]); held["p"] = ev(rng, cur_true, prm["n_conf"])
        return [a - b for a, b in zip(held["c"], held["p"])]
    r = promotion.decide(deltas, cf, P)
    return ("promote" if r.promote else "reject"), held.get("c"), spent


def mixed(a):
    seed, cfg = a
    rng = random.Random(seed)
    out = []
    for _ in range(cfg["reps"]):
        p = draw_base(rng, T, 0.55, 1.5); pop = draw_base(rng, 300, 0.55, 1.5); pop0 = mean(pop)
        cur_true, cur_meas, spent = list(p), ev(rng, p, 1), T
        npro = nfalse = 0
        for _ in range(cfg["N"]):
            d, sp = _candidate(rng)
            qv, qp = noisy_edit(rng, cur_true, d, *sp), noisy_edit(rng, pop, d, *sp)
            st, meas, spent = step(rng, cfg["opt"], cur_meas, qv, cur_true, spent)
            if st == "stop":
                break
            if st == "promote":
                npro += 1; nfalse += d <= 0
                cur_true, cur_meas, pop = qv, meas, qp
        out.append((npro, nfalse, mean(pop) - pop0, mean(cur_true) - mean(p), spent))
    return out


def null(a):
    seed, cfg = a
    rng = random.Random(seed)
    out = []
    for _ in range(cfg["reps"]):
        p = draw_base(rng, T, 0.55, 1.5)
        cur_meas, spent, got = ev(rng, p, 1), T, 0
        for _ in range(cfg["N"]):
            st, meas, spent = step(rng, cfg["opt"], cur_meas, p, p, spent)
            if st == "stop":
                break
            if st == "promote":
                got += 1; cur_meas = meas
        out.append(got)
    return out


def power(a):
    seed, cfg = a
    rng = random.Random(seed)
    h = 0
    for _ in range(cfg["reps"]):
        p = draw_base(rng, T, 0.55, 1.5); q = apply_edit(rng, p, cfg["delta"], None)
        st, _, _ = step(rng, cfg["opt"], ev(rng, p, 1), q, p, T)
        h += st == "promote"
    return h, cfg["reps"]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--reps", type=int, default=5600); a = ap.parse_args()
    per = max(1, a.reps // 56); sd = iter(seeds(20261015, 10 ** 6)); res = {}
    def run(fn, mk):
        jobs, keys = [], []
        for k, cfg in mk():
            for _ in range(56):
                jobs.append((next(sd), {**cfg, "reps": per})); keys.append(k)
        ag = {}
        for k, o in zip(keys, pool_map(fn, jobs)):
            ag.setdefault(k, []).append(o)
        return ag
    N_list = (6, 12)
    nl = run(null, lambda: [((o, N), dict(opt=o, N=N)) for o in OPTIONS for N in N_list])
    mx = run(mixed, lambda: [((o, N), dict(opt=o, N=N)) for o in OPTIONS for N in N_list])
    pw = run(power, lambda: [((o, d), dict(opt=o, delta=d)) for o in OPTIONS for d in (0.04, 0.06, 0.08, 0.10)])
    rows = {}
    for o in OPTIONS:
        r = {}
        for N in N_list:
            g = [x for lst in nl[(o, N)] for x in lst]; m = [x for lst in mx[(o, N)] for x in lst]
            r[f"N={N}"] = {"p_any_false_null_search": sum(x > 0 for x in g) / len(g),
                           "p_any_false_mixed_search": sum(x[1] > 0 for x in m) / len(m),
                           "mean_promotions": mean([x[0] for x in m]),
                           "gain_new_tasks": mean([x[2] for x in m]), "gain_val_tasks": mean([x[3] for x in m]),
                           "rollouts_used": mean([x[4] for x in m])}
        r["power"] = {str(d): sum(h for h, _ in pw[(o, d)]) / sum(n for _, n in pw[(o, d)]) for d in (0.04, 0.06, 0.08, 0.10)}
        rows[o] = r
    (OUT / "sim_budget.json").write_text(json.dumps(rows, indent=1))
    md = [f"# sim_budget: rule P operating points, {BUDGET} rollouts/search, val-{T}, screen n=1 (~{per*56} searches/cell)\n"]
    for N in N_list:
        md += [f"## {N} candidates per search\n", md_table(
            ["option", "P(>=1 false promotion), all-null search", "P(>=1 false promotion), mixed search", "mean promotions",
             "E true gain new tasks", "E true gain val tasks", "E rollouts used"],
            [[o, f"{r[f'N={N}']['p_any_false_null_search']:.3f}", f"{r[f'N={N}']['p_any_false_mixed_search']:.3f}",
              f"{r[f'N={N}']['mean_promotions']:.2f}", f"{r[f'N={N}']['gain_new_tasks']:+.4f}",
              f"{r[f'N={N}']['gain_val_tasks']:+.4f}", f"{r[f'N={N}']['rollouts_used']:.0f}"] for o, r in rows.items()]) + "\n"]
    md += ["## Power (single candidate, diffuse true edit)\n", md_table(["option", "+0.04", "+0.06", "+0.08", "+0.10"],
           [[o] + [f"{r['power'][str(d)]:.2f}" for d in (0.04, 0.06, 0.08, 0.10)] for o, r in rows.items()])]
    (OUT / "sim_budget.md").write_text("\n".join(md)); print("\n".join(md))


if __name__ == "__main__":
    main()
