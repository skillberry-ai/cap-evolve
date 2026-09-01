#!/usr/bin/env python3
"""End-to-end Civ6 adjacency optimizer: search + write the solution file.

WHY THIS EXISTS
===============
The task asks you to (1) choose a city center, (2) choose which districts to
build and where, to MAXIMIZE total adjacency, then (3) write a correctly
formatted solution file. Doing the search by hand -- writing a bespoke
brute-force script every run -- is slow and the #1 way to run out of turns and
never write ``/output/scenario_N.json`` at all (an automatic ZERO).

This script does the WHOLE job in one command:

  * parses the ``.Civ6Map`` with the SAME converter the grader uses,
  * SEARCHES over city centers and district placements to maximize adjacency,
    scoring every candidate with the SAME engine the grader uses,
  * writes a ready-to-submit solution whose ``total_adjacency`` is guaranteed to
    match the grader and whose format is exactly what the grader accepts
    (repeated districts as a LIST of ``[x,y]`` under ONE canonical key -- never
    suffixed keys like ``NEIGHBORHOOD_1``).

USAGE
=====
    # Point it straight at the scenario file; it writes the output file.
    python scripts/optimize.py /data/scenario_3/scenario.json -o /output/scenario_3.json

It prints the best total it found and where it wrote the file. Run it FIRST so a
valid file always exists; you can inspect the result and, if you think you can do
better, hand a refined plan to build_solution.py -- but never finish a run
without a written file.

The search is deterministic-ish (fixed restarts) and time-bounded (``--time``,
default 90s). ``--topk`` controls how many city-center candidates get the full
local search (default 60). Larger values search harder but take longer.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from placement_rules import (  # noqa: E402
    Tile,
    DistrictType,
    DISTRICT_NAME_MAP,
    get_placement_rules,
    calculate_max_specialty_districts,
)
from adjacency_rules import get_adjacency_calculator  # noqa: E402
from hex_utils import hex_distance, get_neighbors  # noqa: E402
from civ6map_to_scenario import convert_civ6map  # noqa: E402


# Specialty districts that actually earn adjacency (worth a limited slot).
SPECIALTY_PALETTE = [
    DistrictType.INDUSTRIAL_ZONE,
    DistrictType.CAMPUS,
    DistrictType.COMMERCIAL_HUB,
    DistrictType.HOLY_SITE,
    DistrictType.THEATER_SQUARE,
    DistrictType.HARBOR,
]
# Non-specialty support districts (no population limit). They earn 0 adjacency
# themselves but count as a "district" for neighbors' +1-per-2 bonus, and
# Aqueduct/Dam/Canal each give an adjacent Industrial Zone +2.
SUPPORT_PALETTE = [
    DistrictType.AQUEDUCT,
    DistrictType.DAM,
    DistrictType.CANAL,
    DistrictType.NEIGHBORHOOD,
]
PALETTE = SPECIALTY_PALETTE + SUPPORT_PALETTE
SPECIALTY_SET = set(SPECIALTY_PALETTE)


def build_tiles(map_file):
    parsed = convert_civ6map(str(map_file))
    tiles = {}
    for td in parsed["tiles"]:
        t = Tile(
            x=td["x"], y=td["y"], terrain=td.get("terrain", "GRASS"),
            feature=td.get("feature"), is_hills=td.get("is_hills", False),
            is_floodplains=td.get("is_floodplains", False),
            river_edges=td.get("river_edges", []), river_names=td.get("river_names", []),
            resource=td.get("resource"), resource_type=td.get("resource_type"),
            improvement=td.get("improvement"),
        )
        tiles[(t.x, t.y)] = t
    return tiles


def valid_city_center(tile):
    if tile is None:
        return False
    return not (tile.is_water or tile.is_mountain or tile.is_natural_wonder)


def cc_proxy_score(cc, tiles):
    """Cheap heuristic to rank city centers before the expensive search:
    reward buildable land in range plus nearby adjacency features."""
    x, y = cc
    buildable = 0
    feature_pts = 0
    for (tx, ty), t in tiles.items():
        d = hex_distance(x, y, tx, ty)
        if d == 0 or d > 3:
            continue
        if not (t.is_water or t.is_mountain or t.is_natural_wonder
                or t.resource_type in ("STRATEGIC", "LUXURY")
                or t.feature == "FEATURE_GEOTHERMAL_FISSURE"):
            buildable += 1
        if d <= 2:
            if t.is_mountain:
                feature_pts += 2
            if t.has_river:
                feature_pts += 1
            if t.feature in ("FEATURE_GEOTHERMAL_FISSURE", "FEATURE_REEF"):
                feature_pts += 2
            if t.is_floodplains:
                feature_pts += 1
            if t.is_water:
                feature_pts += 1
    return buildable + feature_pts


def legal_types_for_tile(rules, cc, pos, population):
    """District types (from PALETTE) that are individually legal at pos,
    ignoring occupancy/count (handled by the search)."""
    x, y = pos
    base_existing = {cc: DistrictType.CITY_CENTER}
    out = []
    for d in PALETTE:
        res = rules.validate_placement(d, x, y, base_existing)
        if res.valid:
            out.append(d)
    return out


def score_assignment(calc, cc, assignment):
    """Total adjacency for {pos: DistrictType} plus the city center."""
    placements = dict(assignment)
    placements[cc] = DistrictType.CITY_CENTER
    total, per = calc.calculate_total_adjacency(placements)
    return total, per


def _count_specialty(assignment):
    return sum(1 for d in assignment.values() if d in SPECIALTY_SET)


def optimize_city(tiles, cc, population, calc):
    """Greedy construction + local search for one city center. Returns
    (total, assignment{pos:DistrictType}, per_district)."""
    rules = get_placement_rules(tiles, cc, population)
    max_spec = calculate_max_specialty_districts(population)

    cand = [p for p in tiles
            if p != cc and hex_distance(cc[0], cc[1], p[0], p[1]) <= 3]
    legal = {p: legal_types_for_tile(rules, cc, p, population) for p in cand}
    legal = {p: v for p, v in legal.items() if v}
    if not legal:
        return 0, {}, {}

    def used_specialties(a):
        return {d for d in a.values() if d in SPECIALTY_SET}

    def can_place(a, pos, d):
        if d in SPECIALTY_SET:
            if d in used_specialties(a) and a.get(pos) != d:
                return False
            spec = _count_specialty(a) - (1 if a.get(pos) in SPECIALTY_SET else 0)
            if spec + 1 > max_spec:
                return False
        return True

    def greedy_add(assignment):
        """Repeatedly add the placement with max marginal gain (from any start)."""
        best_total, _ = score_assignment(calc, cc, assignment)
        improved = True
        while improved:
            improved = False
            best_gain, best_move = 0, None
            for pos, types in legal.items():
                if pos in assignment:
                    continue
                for d in types:
                    if not can_place(assignment, pos, d):
                        continue
                    assignment[pos] = d
                    total, _ = score_assignment(calc, cc, assignment)
                    del assignment[pos]
                    gain = total - best_total
                    if gain > best_gain:
                        best_gain, best_move = gain, (pos, d)
            if best_move and best_gain > 0:
                assignment[best_move[0]] = best_move[1]
                best_total += best_gain
                improved = True
        return best_total

    def fill_nonneg(assignment, best_total):
        """Fill empty legal tiles with any district giving non-negative gain
        (a neighborhood feeds neighbors' district-count bonus at 0 self-bonus)."""
        changed = True
        while changed:
            changed = False
            for pos, types in legal.items():
                if pos in assignment:
                    continue
                best_gain, best_d = -1, None
                for d in types:
                    if not can_place(assignment, pos, d):
                        continue
                    assignment[pos] = d
                    total, _ = score_assignment(calc, cc, assignment)
                    del assignment[pos]
                    gain = total - best_total
                    if gain > best_gain:
                        best_gain, best_d = gain, d
                if best_d is not None and best_gain >= 0:
                    assignment[pos] = best_d
                    best_total += best_gain
                    changed = True
        return best_total

    def local_search(assignment, best_total):
        """Single-tile reassignment / removal until no strict improvement."""
        changed = True
        while changed:
            changed = False
            for pos in list(legal.keys()):
                cur = assignment.get(pos)
                local_best_gain, local_best = 0, cur
                for d in [None] + list(legal[pos]):
                    if d == cur:
                        continue
                    if d is not None and not can_place(assignment_without(assignment, pos), pos, d):
                        continue
                    trial = dict(assignment)
                    if d is None:
                        trial.pop(pos, None)
                    else:
                        trial[pos] = d
                    total, _ = score_assignment(calc, cc, trial)
                    gain = total - best_total
                    if gain > local_best_gain:
                        local_best_gain, local_best = gain, d
                if local_best != cur and local_best_gain > 0:
                    if local_best is None:
                        assignment.pop(pos, None)
                    else:
                        assignment[pos] = local_best
                    best_total += local_best_gain
                    changed = True
        return best_total

    def swap_search(assignment, best_total):
        """2-opt: swap the district types of two occupied tiles, or move an
        occupied district to an empty legal tile. Escapes local optima that
        single-tile moves (which require each step to strictly improve) miss."""
        changed = True
        while changed:
            changed = False
            occ = list(assignment.keys())
            # type swaps between two occupied tiles
            for i in range(len(occ)):
                for j in range(i + 1, len(occ)):
                    p, q = occ[i], occ[j]
                    dp, dq = assignment.get(p), assignment.get(q)
                    if dp is None or dq is None or dp == dq:
                        continue
                    if dq not in legal[p] or dp not in legal[q]:
                        continue
                    trial = dict(assignment)
                    trial[p], trial[q] = dq, dp
                    total, _ = score_assignment(calc, cc, trial)
                    if total > best_total:
                        assignment[p], assignment[q] = dq, dp
                        best_total = total
                        changed = True
            # move an occupied district to an empty legal tile
            for p in list(assignment.keys()):
                d = assignment.get(p)
                if d is None:
                    continue
                for q in legal:
                    if q in assignment or d not in legal[q]:
                        continue
                    trial = dict(assignment)
                    del trial[p]
                    trial[q] = d
                    total, _ = score_assignment(calc, cc, trial)
                    if total > best_total:
                        del assignment[p]
                        assignment[q] = d
                        best_total = total
                        changed = True
                        break
        return best_total

    def run_from(assignment):
        bt = greedy_add(assignment)
        bt = fill_nonneg(assignment, bt)
        bt = local_search(assignment, bt)
        bt = swap_search(assignment, bt)
        bt = local_search(assignment, bt)
        bt = fill_nonneg(assignment, bt)
        return bt

    # Multi-start: (a) empty greedy, (b) dense all-neighborhood seed. The dense
    # seed gives every specialty its full district-count neighbors up front, so
    # local search discovers support<->Industrial-Zone synergy the pure greedy
    # order can miss. Keep the best assignment across starts.
    best_assignment, best_total = None, -1

    a1 = {}
    t1 = run_from(a1)
    if t1 > best_total:
        best_assignment, best_total = dict(a1), t1

    a2 = {}
    for pos, types in legal.items():
        if DistrictType.NEIGHBORHOOD in types:
            a2[pos] = DistrictType.NEIGHBORHOOD
    t2 = run_from(a2)
    if t2 > best_total:
        best_assignment, best_total = dict(a2), t2

    assignment = best_assignment if best_assignment is not None else {}
    total, per = score_assignment(calc, cc, assignment)
    return total, assignment, per


def assignment_without(a, pos):
    if pos not in a:
        return a
    b = dict(a)
    b.pop(pos, None)
    return b


def format_solution(cc, assignment, calc, num_cities):
    total, per = score_assignment(calc, cc, assignment)
    # Group positions by district name.
    by_name = {}
    for pos, d in assignment.items():
        by_name.setdefault(d.name, []).append([pos[0], pos[1]])
    out_placements = {}
    for name, coords in by_name.items():
        out_placements[name] = coords[0] if len(coords) == 1 else coords
    # Per-district-NAME bonuses (sum to total).
    bonuses = {}
    for key, res in per.items():
        name = key.split("@")[0]
        bonuses[name] = bonuses.get(name, 0) + res.total_bonus
    for name in by_name:
        bonuses.setdefault(name, 0)
    solution = {}
    if num_cities == 1:
        solution["city_center"] = [cc[0], cc[1]]
    else:
        solution["cities"] = [{"center": [cc[0], cc[1]]}]
    solution["placements"] = out_placements
    solution["adjacency_bonuses"] = bonuses
    solution["total_adjacency"] = total
    return solution, total


def main():
    ap = argparse.ArgumentParser(description="Search + write a Civ6 adjacency solution.")
    ap.add_argument("scenario", help="Path to scenario.json (map_file, population, num_cities).")
    ap.add_argument("-o", "--output", help="Where to write the solution JSON.")
    ap.add_argument("--topk", type=int, default=60,
                    help="City-center candidates to fully search (default 60).")
    ap.add_argument("--time", type=float, default=90.0,
                    help="Soft wall-clock budget in seconds (default 90).")
    args = ap.parse_args()

    scen_path = Path(args.scenario)
    scenario = json.loads(scen_path.read_text())
    data_dir = scen_path.parent.parent
    map_rel = scenario["map_file"]
    map_path = Path(map_rel)
    if not map_path.is_absolute():
        cand = data_dir / map_rel
        map_path = cand if cand.exists() else (scen_path.parent / map_rel)
    population = scenario.get("population", 7)
    num_cities = scenario.get("num_cities", 1)

    tiles = build_tiles(map_path)
    calc = get_adjacency_calculator(tiles)

    centers = [p for p, t in tiles.items() if valid_city_center(t)]
    centers.sort(key=lambda p: cc_proxy_score(p, tiles), reverse=True)
    centers = centers[: max(1, args.topk)]

    start = time.time()
    best = (-1, None, None)  # (total, cc, assignment)
    tried = 0
    for cc in centers:
        if time.time() - start > args.time and best[0] >= 0:
            break
        total, assignment, _ = optimize_city(tiles, cc, population, calc)
        tried += 1
        if total > best[0]:
            best = (total, cc, assignment)
            print(f"  new best: center={cc} total={total}", file=sys.stderr)

    if best[1] is None:
        print("ERROR: no valid city center found", file=sys.stderr)
        sys.exit(2)

    total, cc, assignment = best
    solution, total = format_solution(cc, assignment, calc, num_cities)

    text = json.dumps(solution, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text)
        print(f"WROTE {args.output}", file=sys.stderr)
    else:
        print(text)
    print(f"BEST total_adjacency={total} at city_center={list(cc)} "
          f"(searched {tried} centers, {time.time()-start:.1f}s)", file=sys.stderr)


if __name__ == "__main__":
    main()
