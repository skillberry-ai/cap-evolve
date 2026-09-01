#!/usr/bin/env python3
"""Vehicle rebalancing / pickup-dropoff routing solver.

Solves the general "rebalance items among stations with a fleet of
capacitated vehicles based at one depot" problem and writes a report.

Use this when the task matches this problem family:
  * one depot, `vehicle_count` identical vehicles of `vehicle_capacity`;
  * a list of `stations`, each with lat/lon, `net_rebalancing_target`
    (positive = pick up from station, negative = drop off at station),
    `initial_bikes`, and `station_capacity`;
  * distances are great-circle miles (Earth radius 3960.0);
  * objective = total travel distance + `penalty_weight` * total unmet target.

It reads every parameter from the data file (nothing is hardcoded), builds a
correct MILP with PySCIPOpt, solves with a bounded time limit that leaves
plenty of wall-clock time to extract and write the answer, reconstructs the
routes, INDEPENDENTLY re-validates the solution, and writes `report.json` in
the required schema.

Usage:
    python scripts/rebalance_solver.py [DATA_PATH] [OUT_PATH]

Defaults: DATA_PATH=/root/data.json  OUT_PATH=/root/report.json
Env overrides: DATA_PATH, OUT_PATH, SOLVE_TIME (seconds, default 240).

Do NOT reimplement this by hand. Run it, then read the printed summary and the
written report.json. If the incumbent is not yet good enough you may re-run
with a larger SOLVE_TIME, but a valid report is written after the first solve.
"""
import json
import math
import os
import sys
from pathlib import Path

from pyscipopt import Model, quicksum

DATA_PATH = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("DATA_PATH", "/root/data.json")
OUT_PATH = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("OUT_PATH", "/root/report.json")
SOLVE_TIME = float(os.environ.get("SOLVE_TIME", "240"))
EARTH_RADIUS = 3960.0

data = json.loads(Path(DATA_PATH).read_text())

vehicle_count = int(data["vehicle_count"])
vehicle_capacity = float(data["vehicle_capacity"])
penalty_weight = float(data["penalty_weight"])
depot = data["depot"]
stations_data = data["stations"]

station_ids = [int(s["id"]) for s in stations_data]
assert len(station_ids) == len(set(station_ids)), "duplicate station ids"

n = len(stations_data)
stations = list(range(n))
idx_to_id = {idx: sid for idx, sid in enumerate(station_ids)}

target = {i: float(stations_data[i]["net_rebalancing_target"]) for i in stations}
initial_bikes = {i: float(stations_data[i]["initial_bikes"]) for i in stations}
station_capacity = {i: float(stations_data[i]["station_capacity"]) for i in stations}


def parse_location(record):
    return {"latitude": float(record["latitude"]), "longitude": float(record["longitude"])}


depot_loc = parse_location(depot)
station_locs = {i: parse_location(stations_data[i]) for i in stations}


def great_circle_miles(a, b, radius=EARTH_RADIUS):
    deg = math.pi / 180.0
    phi1 = (90.0 - a["latitude"]) * deg
    phi2 = (90.0 - b["latitude"]) * deg
    theta1 = a["longitude"] * deg
    theta2 = b["longitude"] * deg
    cos_arc = (
        math.sin(phi1) * math.sin(phi2) * math.cos(theta1 - theta2)
        + math.cos(phi1) * math.cos(phi2)
    )
    cos_arc = max(-1.0, min(1.0, cos_arc))
    return math.acos(cos_arc) * radius


START, END = "depot_start", "depot_end"


def node_loc(node):
    return depot_loc if node in (START, END) else station_locs[node]


from_nodes = [START, *stations]
to_nodes = [*stations, END]
arcs = [
    (i, j)
    for i in from_nodes
    for j in to_nodes
    if i != j and not (i == START and j == END)
]
distance = {(i, j): great_circle_miles(node_loc(i), node_loc(j)) for i, j in arcs}

vehicles = list(range(vehicle_count))

model = Model("bike_rebalancing")
model.hideOutput()


def set_if_available(name, value):
    try:
        model.setParam(name, value)
    except Exception:
        pass


# Determinism: fix randomization and force a single thread so repeated runs
# reproduce the same incumbent.
for name in [
    "randomization/randomseedshift",
    "randomization/permutationseed",
    "randomization/lpseed",
]:
    set_if_available(name, 0)
for name in ["randomization/permutevars", "randomization/permuteconss"]:
    set_if_available(name, False)
set_if_available("parallel/maxnthreads", 1)

x = {
    (v, i, j): model.addVar(vtype="B", name=f"x_{v}_{i}_{j}")
    for v in vehicles
    for i, j in arcs
}
order = {
    (v, i): model.addVar(vtype="C", lb=1, ub=max(1, n), name=f"order_{v}_{i}")
    for v in vehicles
    for i in stations
}
service = {
    (v, i): model.addVar(vtype="I", lb=-vehicle_capacity, ub=vehicle_capacity, name=f"service_{v}_{i}")
    for v in vehicles
    for i in stations
}
start_load = {v: model.addVar(vtype="I", lb=0, ub=vehicle_capacity, name=f"start_load_{v}") for v in vehicles}
end_load = {v: model.addVar(vtype="I", lb=0, ub=vehicle_capacity, name=f"end_load_{v}") for v in vehicles}
load = {
    (v, i): model.addVar(vtype="I", lb=0, ub=vehicle_capacity, name=f"load_{v}_{i}")
    for v in vehicles
    for i in stations
}
dev = {i: model.addVar(vtype="I", lb=0, name=f"dev_{i}") for i in stations}


def load_var(v, node):
    if node == START:
        return start_load[v]
    if node == END:
        return end_load[v]
    return load[v, node]


def outgoing_expr(v, i):
    return quicksum(x[v, i, j] for j in to_nodes if j != i and (i, j) in arcs)


def incoming_expr(v, i):
    return quicksum(x[v, j, i] for j in from_nodes if j != i and (j, i) in arcs)


# Each vehicle leaves the depot once and returns once; a vehicle must be used
# (it cannot just stay at the depot).
for v in vehicles:
    model.addCons(quicksum(x[v, START, j] for j in stations) == 1)
    model.addCons(quicksum(x[v, i, END] for i in stations) == 1)
    for i in stations:
        inc = incoming_expr(v, i)
        out = outgoing_expr(v, i)
        model.addCons(inc == out)
        model.addCons(out <= 1)

# MTZ subtour elimination (station-to-station arcs only).
for v in vehicles:
    for i in stations:
        for j in stations:
            if i != j and (i, j) in arcs:
                model.addCons(order[v, i] - order[v, j] + n * x[v, i, j] <= n - 1)

# A vehicle can only pick up/drop off at a station it visits.
for v in vehicles:
    for i in stations:
        visit_i = outgoing_expr(v, i)
        model.addCons(service[v, i] <= vehicle_capacity * visit_i)
        model.addCons(service[v, i] >= -vehicle_capacity * visit_i)

# Load transitions along the chosen arcs: load_after(j) = load(i) + service(j).
M = 2 * vehicle_capacity
for v in vehicles:
    for i, j in arcs:
        lhs = load_var(v, j) - load_var(v, i)
        if j != END:
            lhs = lhs - service[v, j]
        model.addCons(lhs <= M * (1 - x[v, i, j]))
        model.addCons(lhs >= -M * (1 - x[v, i, j]))

# Station inventory feasibility (hard) and target deviation (soft, penalized).
for i in stations:
    net_change = quicksum(service[v, i] for v in vehicles)
    model.addCons(initial_bikes[i] - net_change >= 0)
    model.addCons(initial_bikes[i] - net_change <= station_capacity[i])
    model.addCons(net_change - target[i] <= dev[i])
    model.addCons(target[i] - net_change <= dev[i])

travel_cost = quicksum(distance[i, j] * x[v, i, j] for v in vehicles for i, j in arcs)
penalty_cost = penalty_weight * quicksum(dev[i] for i in stations)
model.setObjective(travel_cost + penalty_cost, "minimize")

# Bounded solve. Keep the limit well under the agent wall clock so there is
# always time to extract and write the answer. Accept the best incumbent; do
# NOT require proven optimality (gap 0). A near-optimal incumbent is enough.
model.setParam("limits/time", SOLVE_TIME)
model.optimize()

status = str(model.getStatus()).lower()
if model.getNSols() == 0:
    raise RuntimeError(f"SCIP found no feasible solution; status={status}")

print("status:", status)
print("solver objective:", model.getObjVal())
print("gap:", model.getGap())


def is_selected(var):
    return model.getVal(var) > 0.5


vehicle_reports = []
for v in vehicles:
    selected = [(i, j) for (i, j) in arcs if is_selected(x[v, i, j])]
    outgoing = {i: j for (i, j) in selected}
    route_nodes = [START]
    cur = START
    seen = {START}
    while cur != END:
        if cur not in outgoing:
            raise RuntimeError(f"vehicle {v} route disconnected at {cur!r}")
        nxt = outgoing[cur]
        if nxt in seen and nxt != END:
            raise RuntimeError(f"vehicle {v} cycle detected at {nxt!r}")
        route_nodes.append(nxt)
        seen.add(nxt)
        cur = nxt

    stops = []
    for node in route_nodes[1:-1]:
        svc = round(model.getVal(service[v, node]))
        picked = float(max(svc, 0))
        dropped = float(max(-svc, 0))
        load_after = round(model.getVal(load[v, node]))
        stops.append({
            "station_id": idx_to_id[node],
            "bikes_picked_up": picked,
            "bikes_dropped_off": dropped,
            "load_after_stop": float(load_after),
        })

    report_route = [node if node in (START, END) else idx_to_id[node] for node in route_nodes]
    vehicle_reports.append({
        "vehicle_id": v + 1,
        "start_load": float(round(model.getVal(start_load[v]))),
        "route": report_route,
        "stops": stops,
        "end_load": float(round(model.getVal(end_load[v]))),
    })

station_reports = []
total_unmet = 0.0
for i in stations:
    total_picked = 0.0
    total_dropped = 0.0
    for vr in vehicle_reports:
        for stop in vr["stops"]:
            if stop["station_id"] == idx_to_id[i]:
                total_picked += stop["bikes_picked_up"]
                total_dropped += stop["bikes_dropped_off"]
    net_change = total_picked - total_dropped
    unmet = abs(target[i] - net_change)
    total_unmet += unmet
    station_reports.append({
        "station_id": idx_to_id[i],
        "net_rebalancing_target": target[i],
        "total_bikes_picked_up": total_picked,
        "total_bikes_dropped_off": total_dropped,
        "net_bike_change": net_change,
        "unmet_rebalancing_amount": unmet,
    })


# Recompute travel distance independently from the reconstructed routes.
def route_distance(route):
    id_to_idx = {idx_to_id[i]: i for i in stations}
    total = 0.0
    for a, b in zip(route, route[1:]):
        ai = a if a in (START, END) else id_to_idx[a]
        bi = b if b in (START, END) else id_to_idx[b]
        total += distance[ai, bi]
    return total


travel_distance = sum(route_distance(vr["route"]) for vr in vehicle_reports)
unmet_penalty = penalty_weight * total_unmet
objective = travel_distance + unmet_penalty

# Independent feasibility re-validation before writing.
for vr in vehicle_reports:
    ld = vr["start_load"]
    assert 0 - 1e-6 <= ld <= vehicle_capacity + 1e-6, "start_load out of range"
    for stop in vr["stops"]:
        assert not (stop["bikes_picked_up"] > 0 and stop["bikes_dropped_off"] > 0), "both pickup and dropoff at a stop"
        ld = ld + stop["bikes_picked_up"] - stop["bikes_dropped_off"]
        assert abs(ld - stop["load_after_stop"]) < 1e-6, "load transition mismatch"
        assert 0 - 1e-6 <= ld <= vehicle_capacity + 1e-6, "load out of range"
    assert abs(ld - vr["end_load"]) < 1e-6, "end_load mismatch"
for sr in station_reports:
    i = next(k for k in stations if idx_to_id[k] == sr["station_id"])
    final_inv = initial_bikes[i] - sr["total_bikes_picked_up"] + sr["total_bikes_dropped_off"]
    assert 0 - 1e-6 <= final_inv <= station_capacity[i] + 1e-6, "station inventory out of range"

report = {
    "summary": {
        "objective": round(objective, 6),
        "travel_distance_miles": round(travel_distance, 6),
        "unmet_rebalancing_penalty": round(unmet_penalty, 6),
        "total_unmet_rebalancing_amount": round(total_unmet, 6),
    },
    "vehicles": vehicle_reports,
    "stations": station_reports,
}

Path(OUT_PATH).write_text(json.dumps(report, indent=2))
print("wrote", OUT_PATH)
print(json.dumps(report["summary"], indent=2))
