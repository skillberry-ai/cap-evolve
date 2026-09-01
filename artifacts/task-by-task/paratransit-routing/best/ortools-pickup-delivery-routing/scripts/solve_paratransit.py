#!/usr/bin/env python3
"""End-to-end solver for the full-day dial-a-ride / paratransit routing task.

This script implements the WHOLE pipeline in a single, time-bounded run so the
agent does not have to hand-roll the model, run several long solves, and risk a
wall-clock timeout with no output. It:

  1. Reads the standard task inputs (requests.json, t_matrix.csv,
     instance_config.json) using the exact node/window conventions from
     model-and-data.md.
  2. Builds an OR-Tools RoutingModel with cloned per-vehicle depots, a time
     dimension with service+travel transit, capacity, pickup->dropoff pairing,
     per-passenger all-or-none grouped disjunctions, hourly shift starts, an
     8-hour span limit, and a hard latest-return time.
  3. Solves with a hard internal time limit (well below the outer wall clock).
  4. Post-processes to enforce the all-or-none passenger rule (drops partial
     passenger sets to a fixpoint, re-auditing every rebuilt route from
     scratch), then ALWAYS writes report.json in the required schema.

The instance DATA changes across seeds, but the file format and the feasibility
rules are the fixed task contract, so this solver generalizes across instances.

Usage:
    python3 solve_paratransit.py \
        --requests /root/requests.json \
        --matrix /root/t_matrix.csv \
        --config /root/instance_config.json \
        --out /root/report.json \
        --time-limit 600

Leave a margin between --time-limit and the outer wall clock (build, extract,
audit and write all happen after the solve). ~600s of an ~900s wall clock is a
safe default. Run it unbuffered (python3 -u) so long solves are not mistaken for
an idle hang.
"""

import argparse
import json
import sys
import time

INVALID = -1  # matrix entries < 0 are invalid arcs (see model-and-data.md)
BIG = 10 ** 8  # sentinel cost/time for forbidden arcs (dominates any route)


def log(msg):
    print(f"[solve] {msg}", flush=True)


def load_instance(requests_path, matrix_path, config_path):
    with open(config_path) as f:
        config = json.load(f)
    with open(requests_path) as f:
        passengers = json.load(f)

    # Flatten trips: passenger order, then trip-list order (0-based trip index).
    trips = []  # each: dict with passenger idx, service times, count, windows
    passenger_trip_idx = []  # list per passenger of its flattened trip indices
    for p_idx, passenger in enumerate(passengers):
        my = []
        for trip in passenger["trips"]:
            i = len(trips)
            trips.append({
                "trip_index": i,
                "passenger_index": p_idx,
                "passenger_id": passenger.get("passenger_id"),
                "trip_id": trip.get("trip_id"),
                "expected_arrival_time": int(trip["expected_arrival_time"]),
                "pickup_service_time": int(trip["pickup_service_time"]),
                "dropoff_service_time": int(trip["dropoff_service_time"]),
                "passenger_count": int(trip["passenger_count"]),
            })
            my.append(i)
        passenger_trip_idx.append(my)

    n = len(trips)

    # Parse the square integer travel-time matrix (2n+2 x 2n+2).
    matrix = []
    with open(matrix_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = [int(float(x)) for x in line.replace(",", " ").split()]
            matrix.append(row)

    expected_dim = 2 * n + 2
    assert len(matrix) == expected_dim, (
        f"matrix has {len(matrix)} rows, expected {expected_dim} (2n+2, n={n})"
    )
    for r in matrix:
        assert len(r) == expected_dim, "matrix is not square"

    # External node layout: 0=start depot, 1..n pickups, n+1..2n dropoffs,
    # 2n+1=end depot. For trip i: pickup=1+i, dropoff=1+n+i.
    for t in trips:
        i = t["trip_index"]
        t["pickup_node"] = 1 + i
        t["dropoff_node"] = 1 + n + i
        direct = matrix[t["pickup_node"]][t["dropoff_node"]]
        t["direct_travel"] = direct

    return config, trips, passenger_trip_idx, matrix, n


def build_and_solve(config, trips, passenger_trip_idx, matrix, n, time_limit):
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2

    V = int(config["nb_vehicles"])
    capacity = int(config["vehicle_capacity"])
    tww = int(config["time_window_width"])

    START_MIN, START_MAX, LATEST_END, SHIFT = 300, 840, 1320, 480
    shift_starts = list(range(START_MIN, START_MAX + 1, 60))

    # Internal node layout (cloned depots):
    #   0 .. 2n-1   -> external job nodes 1..2n  (ext = internal + 1)
    #   2n .. 2n+V-1        -> start-depot copies (external 0)
    #   2n+V .. 2n+2V-1     -> end-depot copies   (external 2n+1)
    num_job = 2 * n
    num_internal = num_job + 2 * V
    start_int = list(range(num_job, num_job + V))
    end_int = list(range(num_job + V, num_job + 2 * V))

    ext_start_depot = 0
    ext_end_depot = 2 * n + 1

    def ext_of(internal):
        if internal < num_job:
            return internal + 1
        if internal in start_int:
            return ext_start_depot
        return ext_end_depot

    ext_index = [ext_of(a) for a in range(num_internal)]

    def arc(a, b):
        return matrix[ext_index[a]][ext_index[b]]

    # Service time at each internal node (departing-node service goes in transit).
    service = [0] * num_internal
    demand = [0] * num_internal
    for t in trips:
        i = t["trip_index"]
        service[i] = t["pickup_service_time"]           # pickup internal = i
        service[n + i] = t["dropoff_service_time"]       # dropoff internal = n+i
        demand[i] = t["passenger_count"]
        demand[n + i] = -t["passenger_count"]

    manager = pywrapcp.RoutingIndexManager(num_internal, V, start_int, end_int)
    routing = pywrapcp.RoutingModel(manager)

    # --- transit matrices (built over internal indices) ---
    time_matrix = [[0] * num_internal for _ in range(num_internal)]
    cost_matrix = [[0] * num_internal for _ in range(num_internal)]
    for a in range(num_internal):
        sa = service[a]
        for b in range(num_internal):
            tv = arc(a, b)
            if tv < 0:
                time_matrix[a][b] = BIG
                cost_matrix[a][b] = BIG
            else:
                time_matrix[a][b] = sa + tv
                cost_matrix[a][b] = tv
    # start-copy -> end-copy (empty route) costs nothing.
    for v in range(V):
        time_matrix[start_int[v]][end_int[v]] = 0
        cost_matrix[start_int[v]][end_int[v]] = 0

    time_cb = routing.RegisterTransitMatrix(time_matrix)
    cost_cb = routing.RegisterTransitMatrix(cost_matrix)
    routing.SetArcCostEvaluatorOfAllVehicles(cost_cb)

    # Time dimension: allow generous waiting (slack), horizon = latest end.
    routing.AddDimension(time_cb, LATEST_END, LATEST_END, False, "Time")
    time_dim = routing.GetDimensionOrDie("Time")

    # Capacity dimension.
    demand_cb = routing.RegisterUnaryTransitVector(demand)
    routing.AddDimensionWithVehicleCapacity(
        demand_cb, 0, [capacity] * V, True, "Capacity"
    )

    # Per-vehicle shift start (hourly) + latest end + 8h span.
    for v in range(V):
        s = routing.Start(v)
        e = routing.End(v)
        time_dim.CumulVar(s).SetRange(START_MIN, START_MAX)
        time_dim.CumulVar(s).SetValues(shift_starts)
        time_dim.CumulVar(e).SetRange(START_MIN, LATEST_END)
        time_dim.SetSpanUpperBoundForVehicle(SHIFT, v)
        routing.AddVariableMinimizedByFinalizer(time_dim.CumulVar(s))

    # Pickup/dropoff windows and pairing.
    solver = routing.solver()
    for t in trips:
        i = t["trip_index"]
        p = manager.NodeToIndex(i)
        d = manager.NodeToIndex(n + i)
        routing.AddPickupAndDelivery(p, d)
        solver.Add(routing.VehicleVar(p) == routing.VehicleVar(d))
        solver.Add(time_dim.CumulVar(p) <= time_dim.CumulVar(d))

        exp = t["expected_arrival_time"]
        direct = t["direct_travel"]
        # dropoff window: [exp - tww, exp]
        time_dim.CumulVar(d).SetRange(max(0, exp - tww), exp)
        # pickup window: [exp - tww - direct, exp - direct]
        if direct >= 0:
            time_dim.CumulVar(p).SetRange(
                max(0, exp - tww - direct), max(0, exp - direct)
            )

    # All-or-none per passenger: group each passenger's PICKUP nodes in one
    # disjunction (max_cardinality = #trips, big group penalty); dropoffs are
    # optional at zero penalty (the pairing ties served pairs together, and
    # postprocessing enforces the final all-or-none rule).
    PEN = 1_000_000
    for my in passenger_trip_idx:
        if not my:
            continue
        pickup_indices = [manager.NodeToIndex(i) for i in my]
        routing.AddDisjunction(pickup_indices, PEN * len(my), len(my))
        for i in my:
            routing.AddDisjunction([manager.NodeToIndex(n + i)], 0)

    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PARALLEL_CHEAPEST_INSERTION
    )
    params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GENERIC_TABU_SEARCH
    )
    params.time_limit.seconds = int(time_limit)
    params.log_search = True

    log(f"solving: n_trips={n} vehicles={V} nodes={num_internal} limit={time_limit}s")
    solution = routing.SolveWithParameters(params)
    if solution is None:
        log("no solution found")
        return None

    # Extract raw routes as external node sequences + start times.
    raw_routes = []
    for v in range(V):
        idx = routing.Start(v)
        seq = []
        while not routing.IsEnd(idx):
            seq.append(manager.IndexToNode(idx))
            idx = solution.Value(routing.NextVar(idx))
        seq.append(manager.IndexToNode(idx))
        # map internal -> external
        ext_seq = [ext_index[node] for node in seq]
        start_time = solution.Value(time_dim.CumulVar(routing.Start(v)))
        # skip empty routes (only depots)
        job_nodes = [node for node in seq if node < num_job]
        if job_nodes:
            raw_routes.append({"vehicle": v, "start_time": int(start_time),
                               "ext_seq": ext_seq})
    return raw_routes


def audit_route(ext_seq, start_time, trips_by_node, matrix, n, capacity):
    """Simulate a route from scratch; return (feasible, served_trip_indices)."""
    if not ext_seq or ext_seq[0] != 0 or ext_seq[-1] != (2 * n + 1):
        return False, set()
    if not (300 <= start_time <= 840) or (start_time - 300) % 60 != 0:
        return False, set()
    t = start_time
    load = 0
    served = set()
    prev = 0
    for node in ext_seq[1:]:
        travel = matrix[prev][node]
        if travel < 0:
            return False, set()
        arr = t + travel
        if node == 2 * n + 1:  # end depot
            if arr > 1320 or arr - start_time > 480:
                return False, set()
            prev = node
            t = arr
            continue
        info = trips_by_node.get(node)
        if info is None:
            return False, set()
        lo, hi, svc, dem, trip_i = info
        service_start = max(arr, lo)
        if service_start > hi:
            return False, set()
        load += dem
        if load < 0 or load > capacity:
            return False, set()
        t = service_start + svc
        prev = node
        served.add(trip_i)
    if load != 0:
        return False, set()
    return True, served


def postprocess(raw_routes, trips, passenger_trip_idx, matrix, n, capacity):
    """Enforce all-or-none per passenger by dropping partial sets to a fixpoint.

    Re-audits every rebuilt route from scratch; if a route is infeasible after
    dropping, removes the passengers on that route until it is feasible.
    """
    # node -> (win_lo, win_hi, service, demand, trip_index)
    trips_by_node = {}
    for t in trips:
        i = t["trip_index"]
        exp, tww_dir = t["expected_arrival_time"], t["direct_travel"]
        # windows recomputed from the fixed rules
        # (tww is per-instance; embed via closure caller passes matrix only, so
        #  windows are recomputed here from expected_arrival_time and direct)
        # NOTE: caller sets t["win_pickup"]/t["win_dropoff"].
        p_lo, p_hi = t["win_pickup"]
        d_lo, d_hi = t["win_dropoff"]
        trips_by_node[t["pickup_node"]] = (p_lo, p_hi, t["pickup_service_time"],
                                           t["passenger_count"], i)
        trips_by_node[t["dropoff_node"]] = (d_lo, d_hi, t["dropoff_service_time"],
                                            -t["passenger_count"], i)

    passenger_of_trip = {t["trip_index"]: t["passenger_index"] for t in trips}

    removed_passengers = set()
    routes_ext = [(r["ext_seq"], r["start_time"]) for r in raw_routes]

    for _ in range(200):  # fixpoint
        # rebuild each route keeping only nodes of non-removed passengers
        changed = False
        newly_bad = set()
        served_trips = set()
        rebuilt = []
        for ext_seq, st in routes_ext:
            kept = [0]
            for node in ext_seq[1:-1]:
                info = trips_by_node.get(node)
                if info is None:
                    continue  # depot copies already mapped to 0/2n+1; skip
                trip_i = info[4]
                if passenger_of_trip[trip_i] in removed_passengers:
                    continue
                kept.append(node)
            kept.append(2 * n + 1)
            feasible, served = audit_route(kept, st, trips_by_node, matrix, n,
                                           capacity)
            if not feasible:
                # remove all passengers currently on this route, retry next round
                for node in kept[1:-1]:
                    info = trips_by_node.get(node)
                    if info:
                        newly_bad.add(passenger_of_trip[info[4]])
                changed = True
                continue
            rebuilt.append((kept, st))
            served_trips |= served

        # enforce all-or-none: a passenger is served only if ALL its trips served
        incomplete = set()
        for p_idx, my in enumerate(passenger_trip_idx):
            if not my or p_idx in removed_passengers:
                continue
            if any(ti not in served_trips for ti in my):
                incomplete.add(p_idx)

        if newly_bad:
            removed_passengers |= newly_bad
            changed = True
        if incomplete:
            removed_passengers |= incomplete
            changed = True

        if not changed:
            # final rebuild is consistent; return it
            return rebuilt
    return rebuilt


def write_report(rebuilt, out_path):
    routes = []
    for v, (ext_seq, st) in enumerate(rebuilt):
        # only emit routes that actually serve at least one job node
        if len(ext_seq) > 2:
            routes.append({
                "vehicle_id": f"V{v}",
                "start_time": int(st),
                "node_sequence": [int(x) for x in ext_seq],
            })
    with open(out_path, "w") as f:
        json.dump({"routes": routes}, f)
    return routes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--requests", default="/root/requests.json")
    ap.add_argument("--matrix", default="/root/t_matrix.csv")
    ap.add_argument("--config", default="/root/instance_config.json")
    ap.add_argument("--out", default="/root/report.json")
    ap.add_argument("--time-limit", type=int, default=600)
    args = ap.parse_args()

    t0 = time.time()
    # Fallback: guarantee report.json exists even if the solve raises.
    try:
        config, trips, passenger_trip_idx, matrix, n = load_instance(
            args.requests, args.matrix, args.config)
    except Exception as exc:  # pragma: no cover
        log(f"load failed: {exc}")
        with open(args.out, "w") as f:
            json.dump({"routes": []}, f)
        raise

    tww = int(config["time_window_width"])
    for t in trips:
        exp, direct = t["expected_arrival_time"], t["direct_travel"]
        t["win_dropoff"] = (max(0, exp - tww), exp)
        t["win_pickup"] = (max(0, exp - tww - direct), max(0, exp - direct))

    try:
        raw_routes = build_and_solve(
            config, trips, passenger_trip_idx, matrix, n, args.time_limit)
    except Exception as exc:
        log(f"solve failed: {exc}")
        raw_routes = None

    if not raw_routes:
        with open(args.out, "w") as f:
            json.dump({"routes": []}, f)
        log("wrote empty report (no routes)")
        return

    capacity = int(config["vehicle_capacity"])
    rebuilt = postprocess(raw_routes, trips, passenger_trip_idx, matrix, n,
                          capacity)
    routes = write_report(rebuilt, args.out)

    # served-trip summary
    trips_by_node = {}
    for t in trips:
        trips_by_node[t["pickup_node"]] = t["trip_index"]
    served = set()
    for r in routes:
        for node in r["node_sequence"]:
            if node in trips_by_node:
                served.add(trips_by_node[node])
    log(f"routes={len(routes)} served_trips={len(served)}/{n} "
        f"elapsed={time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
