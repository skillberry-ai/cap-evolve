#!/usr/bin/env python3
"""
solve_market.py — one-shot DC-OPF market clearing with reserve co-optimization,
LMP / reserve-MCP / binding-line extraction, and a base-vs-counterfactual
"relax one transmission line" impact analysis.

WHY THIS SCRIPT EXISTS
----------------------
Doing this by hand in the agent loop is fragile: the model must be re-derived
every run, the dual (LMP) extraction is numerically ill-conditioned in the
naive angle-based formulation, and the report is often never written because
the budget is spent debugging.  This script bakes in the *verified* method so
the whole analysis is a single deterministic command that ALWAYS writes the
report in the exact required schema.

NUMERICAL NOTE (the trap this avoids)
-------------------------------------
Branch susceptances b = 1/x can span several orders of magnitude.  If nodal
balance is written in per-unit and the LMP is recovered as dual*baseMVA, the
duals come out wildly ill-conditioned (thousands of $/MWh) even though the
primal cost is correct.  This script writes nodal power balance directly in MW
with explicit MW flow variables, so the balance-constraint dual IS the LMP in
$/MWh with no rescaling — well-conditioned and correct.

USAGE
-----
    python3 solve_market.py --network network.json \
        --relax-from 64 --relax-to 1501 --factor 1.2 --out report.json

    python3 solve_market.py --self-check      # runs a tiny built-in case, exit 0/1

--relax-from / --relax-to are the two endpoint bus NUMBERS (as they appear in
the data / task text, order-insensitive) of the line whose thermal limit
(RATE_A) is scaled by --factor in the counterfactual.  --factor 1.2 == "+20%".
"""

import argparse
import json
import sys

# numpy is imported lazily inside the solver so the pure-Python helpers and
# --self-check helper path work even if numpy is momentarily unavailable.

BINDING_THRESHOLD = 99.0  # percent loading at/above which a line is "binding"


# --------------------------------------------------------------------------- #
# Pure helpers (no solver dependency) — these are what --self-check always     #
# exercises even if cvxpy is unavailable.                                      #
# --------------------------------------------------------------------------- #
def load_network(path):
    with open(path) as f:
        data = json.load(f)
    return data


def _matches_line(a_from, a_to, want_from, want_to):
    """Order-insensitive branch endpoint match on bus NUMBERS."""
    return (a_from == want_from and a_to == want_to) or (
        a_from == want_to and a_to == want_from
    )


def apply_counterfactual(branches, relax_from, relax_to, factor):
    """Return a copy of `branches` with the target line's RATE_A (col 5) scaled.

    Raises ValueError if the line is not found (an actionable error rather than
    silently producing a base==cf report)."""
    cf = [list(br) for br in branches]
    found = False
    for k in range(len(cf)):
        if _matches_line(int(cf[k][0]), int(cf[k][1]), relax_from, relax_to):
            cf[k][5] = float(cf[k][5]) * float(factor)
            found = True
    if not found:
        raise ValueError(
            f"target line {relax_from}<->{relax_to} not found among branch "
            f"endpoints; check --relax-from/--relax-to against the network data"
        )
    return cf


def pick_top_lmp_drops(base_lmp_by_bus, cf_lmp_by_bus, k=3):
    """Return the k buses with the largest LMP *drop* (most negative delta)."""
    base_map = {d["bus"]: d["lmp_dollars_per_MWh"] for d in base_lmp_by_bus}
    cf_map = {d["bus"]: d["lmp_dollars_per_MWh"] for d in cf_lmp_by_bus}
    deltas = []
    for bus in base_map:
        b = base_map[bus]
        c = cf_map.get(bus, 0.0)
        deltas.append(
            {"bus": bus, "base_lmp": b, "cf_lmp": c, "delta": round(c - b, 2)}
        )
    deltas.sort(key=lambda d: d["delta"])  # most negative first
    return deltas[:k]


def build_report(base_result, cf_result, relax_from, relax_to):
    cost_reduction = round(
        base_result["total_cost_dollars_per_hour"]
        - cf_result["total_cost_dollars_per_hour"],
        2,
    )
    top = pick_top_lmp_drops(base_result["lmp_by_bus"], cf_result["lmp_by_bus"])
    # congestion_relieved: the adjusted line is binding in base but NOT in cf.
    congestion_relieved = bool(
        base_result["target_line_binding"] and not cf_result["target_line_binding"]
    )
    return {
        "base_case": {
            "total_cost_dollars_per_hour": base_result["total_cost_dollars_per_hour"],
            "lmp_by_bus": base_result["lmp_by_bus"],
            "reserve_mcp_dollars_per_MWh": base_result["reserve_mcp_dollars_per_MWh"],
            "binding_lines": base_result["binding_lines"],
        },
        "counterfactual": {
            "total_cost_dollars_per_hour": cf_result["total_cost_dollars_per_hour"],
            "lmp_by_bus": cf_result["lmp_by_bus"],
            "reserve_mcp_dollars_per_MWh": cf_result["reserve_mcp_dollars_per_MWh"],
            "binding_lines": cf_result["binding_lines"],
        },
        "impact_analysis": {
            "cost_reduction_dollars_per_hour": cost_reduction,
            "buses_with_largest_lmp_drop": top,
            "congestion_relieved": congestion_relieved,
        },
    }


# --------------------------------------------------------------------------- #
# Solver (cvxpy) — imported lazily so the helpers/self-check work without it.  #
# --------------------------------------------------------------------------- #
def solve_market(data, branches, relax_from, relax_to, label=""):
    import cvxpy as cp
    import numpy as np

    baseMVA = float(data["baseMVA"])
    buses = [list(b) for b in data["bus"]]
    gens = [list(g) for g in data["gen"]]
    gencost = [list(c) for c in data["gencost"]]
    reserve_capacity = np.asarray(data["reserve_capacity"], dtype=float)
    reserve_requirement = float(data["reserve_requirement"])

    n_bus = len(buses)
    n_gen = len(gens)
    n_branch = len(branches)

    bus_num_to_idx = {int(buses[i][0]): i for i in range(n_bus)}
    gen_bus = [bus_num_to_idx[int(g[0])] for g in gens]

    slack_idx = next((i for i in range(n_bus) if int(buses[i][1]) == 3), 0)

    # Branch parameters
    from_idx, to_idx, b_list, active = [], [], [], []
    for br in branches:
        f = bus_num_to_idx[int(br[0])]
        t = bus_num_to_idx[int(br[1])]
        x = float(br[3])
        status = int(br[10]) if len(br) > 10 else 1
        from_idx.append(f)
        to_idx.append(t)
        if x != 0 and status == 1:
            b_list.append(1.0 / x)
            active.append(True)
        else:
            b_list.append(0.0)
            active.append(False)

    Pg = cp.Variable(n_gen)      # per-unit
    Rg = cp.Variable(n_gen)      # MW
    theta = cp.Variable(n_bus)   # radians
    Flow = cp.Variable(n_branch) # MW

    constraints = [theta[slack_idx] == 0]

    # Generator energy limits (per-unit)
    for i in range(n_gen):
        constraints.append(Pg[i] >= float(gens[i][9]) / baseMVA)
        constraints.append(Pg[i] <= float(gens[i][8]) / baseMVA)

    # Reserve limits + standard capacity coupling (Pg_MW + Rg <= Pmax)
    constraints.append(Rg >= 0)
    for i in range(n_gen):
        constraints.append(Rg[i] <= reserve_capacity[i])
        constraints.append(Pg[i] * baseMVA + Rg[i] <= float(gens[i][8]))

    # System reserve requirement (its dual is the reserve MCP)
    reserve_con = cp.sum(Rg) >= reserve_requirement
    constraints.append(reserve_con)

    # Flow definition in MW
    for k in range(n_branch):
        if active[k]:
            constraints.append(
                Flow[k] == b_list[k] * (theta[from_idx[k]] - theta[to_idx[k]]) * baseMVA
            )
        else:
            constraints.append(Flow[k] == 0)

    # Nodal power balance in MW (dual == LMP in $/MWh directly)
    out_by_bus = [[] for _ in range(n_bus)]
    in_by_bus = [[] for _ in range(n_bus)]
    for k in range(n_branch):
        if active[k]:
            out_by_bus[from_idx[k]].append(k)
            in_by_bus[to_idx[k]].append(k)

    balance_constraints = []
    for i in range(n_bus):
        gens_here = [g for g in range(n_gen) if gen_bus[g] == i]
        pg_MW = cp.sum(Pg[gens_here]) * baseMVA if gens_here else 0
        pd = float(buses[i][2])
        out_ks, in_ks = out_by_bus[i], in_by_bus[i]
        net_export = (cp.sum(Flow[out_ks]) if out_ks else 0) - (
            cp.sum(Flow[in_ks]) if in_ks else 0
        )
        bal = pg_MW - pd == net_export
        balance_constraints.append(bal)
        constraints.append(bal)

    # Thermal limits
    for k, br in enumerate(branches):
        rate = float(br[5])
        if active[k] and rate > 0:
            constraints.append(Flow[k] <= rate)
            constraints.append(Flow[k] >= -rate)

    # Objective: total generation cost (handles variable NCOST)
    cost = 0
    for i in range(n_gen):
        ncost = int(gencost[i][3])
        Pg_MW = Pg[i] * baseMVA
        if ncost >= 3:
            c2, c1, c0 = gencost[i][4], gencost[i][5], gencost[i][6]
            cost += c2 * cp.square(Pg_MW) + c1 * Pg_MW + c0
        elif ncost == 2:
            c1, c0 = gencost[i][4], gencost[i][5]
            cost += c1 * Pg_MW + c0
        elif ncost >= 1:
            cost += gencost[i][4]

    prob = cp.Problem(cp.Minimize(cost), constraints)
    # CLARABEL is robust for DC-OPF-with-reserves; fall back to SCS if needed.
    for solver in (cp.CLARABEL, cp.SCS):
        try:
            prob.solve(solver=solver)
            if prob.status in ("optimal", "optimal_inaccurate"):
                break
        except Exception:
            continue
    if prob.value is None:
        raise RuntimeError(f"[{label}] solve failed, status={prob.status}")

    # LMPs = duals of MW balance, already $/MWh
    lmp_by_bus = []
    for i in range(n_bus):
        dv = balance_constraints[i].dual_value
        lmp = float(dv) if dv is not None else 0.0
        lmp_by_bus.append(
            {"bus": int(buses[i][0]), "lmp_dollars_per_MWh": round(lmp, 2)}
        )

    reserve_mcp = (
        float(reserve_con.dual_value) if reserve_con.dual_value is not None else 0.0
    )

    binding_lines = []
    target_line_binding = False
    flow_val = np.asarray(Flow.value).ravel()
    for k, br in enumerate(branches):
        rate = float(br[5])
        if active[k] and rate > 0:
            flow_MW = float(flow_val[k])
            if abs(flow_MW) / rate * 100 >= BINDING_THRESHOLD:
                binding_lines.append(
                    {
                        "from": int(br[0]),
                        "to": int(br[1]),
                        "flow_MW": round(flow_MW, 2),
                        "limit_MW": round(rate, 2),
                    }
                )
                if _matches_line(int(br[0]), int(br[1]), relax_from, relax_to):
                    target_line_binding = True

    return {
        "total_cost_dollars_per_hour": round(float(prob.value), 2),
        "lmp_by_bus": lmp_by_bus,
        "reserve_mcp_dollars_per_MWh": round(reserve_mcp, 2),
        "binding_lines": binding_lines,
        "target_line_binding": target_line_binding,
    }


def run(network_path, relax_from, relax_to, factor, out_path):
    data = load_network(network_path)
    branches = [list(br) for br in data["branch"]]
    base = solve_market(data, branches, relax_from, relax_to, "BASE")
    cf_branches = apply_counterfactual(branches, relax_from, relax_to, factor)
    cf = solve_market(data, cf_branches, relax_from, relax_to, "COUNTERFACTUAL")
    report = build_report(base, cf, relax_from, relax_to)
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"wrote {out_path}")
    print(f"  base cost      = {base['total_cost_dollars_per_hour']}")
    print(f"  cf   cost      = {cf['total_cost_dollars_per_hour']}")
    print(f"  cost_reduction = {report['impact_analysis']['cost_reduction_dollars_per_hour']}")
    print(f"  congestion_relieved = {report['impact_analysis']['congestion_relieved']}")
    return report


# --------------------------------------------------------------------------- #
# Self-check                                                                   #
# --------------------------------------------------------------------------- #
def _tiny_network():
    """A 3-bus toy system: cheap gen at bus 1, expensive gen at bus 3, load at
    bus 3, and a line 1-3 whose limit forces the expensive local gen on. It is
    designed so relaxing that line lets cheaper power flow in (cost drops)."""
    baseMVA = 100.0
    # bus: [num, type, Pd, Qd, Gs, Bs, area, Vm, Va, baseKV, zone, Vmax, Vmin]
    bus = [
        [1, 3, 0.0, 0, 0, 0, 1, 1, 0, 230, 1, 1.1, 0.9],
        [2, 1, 0.0, 0, 0, 0, 1, 1, 0, 230, 1, 1.1, 0.9],
        [3, 1, 100.0, 0, 0, 0, 1, 1, 0, 230, 1, 1.1, 0.9],
    ]
    # gen: [bus, Pg, Qg, Qmax, Qmin, Vg, mBase, status, Pmax, Pmin, ...]
    gen = [
        [1, 0, 0, 0, 0, 1, 100, 1, 200, 0],
        [3, 0, 0, 0, 0, 1, 100, 1, 200, 0],
    ]
    # gencost: [model, startup, shutdown, ncost, c1, c0]  (linear)
    gencost = [
        [2, 0, 0, 2, 10.0, 0.0],   # cheap
        [2, 0, 0, 2, 50.0, 0.0],   # expensive
    ]
    # branch: [from,to,r,x,b,rateA,rateB,rateC,ratio,angle,status,...]
    branch = [
        [1, 2, 0.0, 0.1, 0, 500, 0, 0, 0, 0, 1],
        [2, 3, 0.0, 0.1, 0, 500, 0, 0, 0, 0, 1],
        [1, 3, 0.0, 0.1, 0, 30, 0, 0, 0, 0, 1],   # tight line to relax
    ]
    return {
        "baseMVA": baseMVA,
        "bus": bus,
        "gen": gen,
        "gencost": gencost,
        "branch": branch,
        "reserve_capacity": [50.0, 50.0],
        "reserve_requirement": 20.0,
    }


def self_check():
    ok = True

    # --- helper checks (no solver needed) ---
    br = [[1, 2, 0, 0.1, 0, 100, 0, 0, 0, 0, 1]]
    cf = apply_counterfactual(br, 2, 1, 1.2)  # order-insensitive
    assert abs(cf[0][5] - 120.0) < 1e-9, "counterfactual scaling wrong"
    try:
        apply_counterfactual(br, 7, 9, 1.2)
        assert False, "missing line should raise"
    except ValueError:
        pass
    base_lmp = [{"bus": 1, "lmp_dollars_per_MWh": 40.0}, {"bus": 2, "lmp_dollars_per_MWh": 30.0}]
    cf_lmp = [{"bus": 1, "lmp_dollars_per_MWh": 20.0}, {"bus": 2, "lmp_dollars_per_MWh": 29.0}]
    top = pick_top_lmp_drops(base_lmp, cf_lmp, k=1)
    assert top[0]["bus"] == 1 and top[0]["delta"] == -20.0, "top-drop selection wrong"
    print("[self-check] helpers OK")

    # --- full solve check (needs cvxpy) ---
    try:
        import cvxpy  # noqa: F401
    except Exception as e:  # pragma: no cover
        print(f"[self-check] cvxpy unavailable ({e}); skipped solve, helpers passed")
        return 0

    data = _tiny_network()
    branches = [list(b) for b in data["branch"]]
    base = solve_market(data, branches, 1, 3, "BASE")
    cf_branches = apply_counterfactual(branches, 1, 3, 1.5)
    cfr = solve_market(data, cf_branches, 1, 3, "COUNTERFACTUAL")
    report = build_report(base, cfr, 1, 3)

    # Schema shape
    for sec in ("base_case", "counterfactual", "impact_analysis"):
        assert sec in report, f"missing {sec}"
    for sec in ("base_case", "counterfactual"):
        for key in ("total_cost_dollars_per_hour", "lmp_by_bus",
                    "reserve_mcp_dollars_per_MWh", "binding_lines"):
            assert key in report[sec], f"{sec} missing {key}"
    assert len(report["base_case"]["lmp_by_bus"]) == 3, "one LMP per bus"
    ia = report["impact_analysis"]
    assert set(ia) == {"cost_reduction_dollars_per_hour",
                       "buses_with_largest_lmp_drop", "congestion_relieved"}
    # Relaxing a binding constraint cannot increase cost.
    assert ia["cost_reduction_dollars_per_hour"] >= -1e-6, "cost went UP after relax"
    assert isinstance(ia["congestion_relieved"], bool)
    assert len(ia["buses_with_largest_lmp_drop"]) == 3
    print(f"[self-check] solve OK: base={base['total_cost_dollars_per_hour']} "
          f"cf={cfr['total_cost_dollars_per_hour']} "
          f"cost_reduction={ia['cost_reduction_dollars_per_hour']} "
          f"congestion_relieved={ia['congestion_relieved']}")
    return 0 if ok else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--network", help="path to MATPOWER-format network.json")
    ap.add_argument("--relax-from", type=int, help="one endpoint bus number of the line to relax")
    ap.add_argument("--relax-to", type=int, help="other endpoint bus number of the line to relax")
    ap.add_argument("--factor", type=float, default=1.2,
                    help="multiplier on the line RATE_A in the counterfactual (1.2 = +20%%)")
    ap.add_argument("--out", default="report.json", help="output report path")
    ap.add_argument("--self-check", action="store_true",
                    help="run built-in correctness check and exit")
    args = ap.parse_args(argv)

    if args.self_check:
        return self_check()

    missing = [n for n in ("network", "relax_from", "relax_to")
               if getattr(args, n) is None]
    if missing:
        ap.error("required unless --self-check: " + ", ".join("--" + m.replace("_", "-") for m in missing))
    run(args.network, args.relax_from, args.relax_to, args.factor, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
