#!/usr/bin/env python3
"""
Recompute AC nodal power balance from a WRITTEN report.json exactly the way an
AC-OPF grader does, and report the max P / Q mismatch in MW / MVAr.

WHY THIS EXISTS (the #1 silent AC-OPF reporting failure):
The solver's *internal* mismatch is ~0, so an in-memory feasibility print always
looks fine. But graders re-solve nodal balance from the numbers you actually WROTE
to report.json (vm_pu, va_deg, pg_MW, qg_MVAr). If you rounded those values, the
recomputed balance no longer closes: rounding voltages/angles injects reactive
mismatch that easily exceeds a ~1 MVAr feasibility tolerance while P looks fine.

So: run this on your FINAL report.json (not on the solver arrays) before you finish.
If it prints FAIL, you rounded the report -> rewrite it with FULL float precision
(do not round vm_pu, va_deg, pg_MW, qg_MVAr).

Usage:
    python check_report_balance.py /root/report.json /root/network.json [tol]
    (tol defaults to 1.0 MW/MVAr)
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from branch_flows import build_bus_id_to_idx, compute_branch_flows_pu


def check_report_balance(report_path: str, network_path: str, tol: float = 1.0):
    with open(report_path) as f:
        report = json.load(f)
    with open(network_path) as f:
        net = json.load(f)

    baseMVA = float(net["baseMVA"])
    buses = np.array(net["bus"], dtype=float)
    branches = np.array(net["branch"], dtype=float)
    n_bus = buses.shape[0]

    bus_id_to_idx = build_bus_id_to_idx(buses)

    # --- Read the solution back from the report EXACTLY as it was written ---
    Vm = buses[:, 7].astype(float).copy()  # fallback to data VM
    Va = np.zeros(n_bus)
    for b in report["buses"]:
        i = bus_id_to_idx[int(b["id"])]
        Vm[i] = float(b["vm_pu"])
        Va[i] = np.deg2rad(float(b["va_deg"]))

    # Generator injections aggregated per bus (per unit), from the report
    Pg_bus = np.zeros(n_bus)
    Qg_bus = np.zeros(n_bus)
    for g in report["generators"]:
        i = bus_id_to_idx[int(g["bus"])]
        Pg_bus[i] += float(g["pg_MW"]) / baseMVA
        Qg_bus[i] += float(g["qg_MVAr"]) / baseMVA

    Pd = buses[:, 2] / baseMVA
    Qd = buses[:, 3] / baseMVA
    Gs = buses[:, 4] / baseMVA
    Bs = buses[:, 5] / baseMVA

    # Branch flows aggregated per bus (per unit), same pi-model as the grader
    P_out = np.zeros(n_bus)
    Q_out = np.zeros(n_bus)
    for k in range(branches.shape[0]):
        br = branches[k]
        i = bus_id_to_idx[int(br[0])]
        j = bus_id_to_idx[int(br[1])]
        P_ij, Q_ij, P_ji, Q_ji = compute_branch_flows_pu(Vm, Va, br, bus_id_to_idx)
        P_out[i] += P_ij
        Q_out[i] += Q_ij
        P_out[j] += P_ji
        Q_out[j] += Q_ji

    # (Ys)^*|V|^2 => real Gs|V|^2, imag -Bs|V|^2  =>  Qg - Qd + Bs|V|^2 = Q_out
    P_mis = (Pg_bus - Pd - Gs * Vm**2 - P_out) * baseMVA
    Q_mis = (Qg_bus - Qd + Bs * Vm**2 - Q_out) * baseMVA

    max_p = float(np.max(np.abs(P_mis)))
    max_q = float(np.max(np.abs(Q_mis)))
    ok = (max_p <= tol) and (max_q <= tol)
    return max_p, max_q, ok


def main() -> int:
    report_path = sys.argv[1] if len(sys.argv) > 1 else "/root/report.json"
    network_path = sys.argv[2] if len(sys.argv) > 2 else "/root/network.json"
    tol = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0

    max_p, max_q, ok = check_report_balance(report_path, network_path, tol)
    print(f"max_p_mismatch_MW   = {max_p:.6f}")
    print(f"max_q_mismatch_MVAr = {max_q:.6f}")
    if ok:
        print(f"POWER BALANCE: OK (both <= {tol} MW/MVAr)")
        return 0
    print(
        f"POWER BALANCE: FAIL (tol={tol} MW/MVAr). The report values are inconsistent "
        f"with the network -- most often because vm_pu/va_deg/pg_MW/qg_MVAr were ROUNDED. "
        f"Rewrite report.json with FULL float precision (no round())."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
