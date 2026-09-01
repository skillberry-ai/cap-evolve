#!/usr/bin/env python3
"""Build and self-verify a Civ6 adjacency solution file.

WHY THIS EXISTS
===============
The grader RE-COMPUTES total adjacency from your placements with the exact
modules bundled here (placement_rules.py, adjacency_rules.py) after parsing the
.Civ6Map with civ6map_to_scenario.py. If the ``total_adjacency`` you submit does
not match its recomputation, the solution scores ZERO (hard gate) -- even if the
placement is optimal. Hand-computing the total, or parsing the map yourself, is
the #1 cause of a 0. This script removes that risk:

  * It parses the map with the SAME converter the grader uses.
  * It computes adjacency with the SAME engine the grader uses.
  * So the ``total_adjacency`` it writes is guaranteed to match the grader.

It also emits the ONE correct output format, including the format for placing
several districts of the same type (a LIST of ``[x, y]`` pairs under a single
district key -- NEVER suffixed keys like ``NEIGHBORHOOD_1``/``DAM_2``, which the
grader rejects as "Unknown district type").

USAGE
=====
Write a plan JSON (you choose the placements), then run this script::

    # plan.json
    {
      "map_file": "/data/maps/e2e_test_case_0.Civ6Map",
      "population": 9,
      "num_cities": 1,
      "city_center": [22, 15],
      "placements": {
        "CAMPUS": [21, 14],
        "COMMERCIAL_HUB": [23, 14],
        "NEIGHBORHOOD": [[22, 17], [23, 17], [22, 13]]
      }
    }

    python scripts/build_solution.py plan.json -o /output/scenario_3.json

Multi-city: use ``"cities": [[x1,y1],[x2,y2]]`` instead of ``city_center``.

It prints a validation report. If it reports errors, FIX the placement and rerun
-- do not submit an invalid plan. On success it writes a ready-to-submit file
whose ``total_adjacency`` matches the grader exactly.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from placement_rules import (  # noqa: E402
    Tile,
    DistrictType,
    DISTRICT_NAME_MAP,
    get_placement_rules,
    validate_city_distances,
    validate_district_count,
    validate_district_uniqueness,
)
from adjacency_rules import get_adjacency_calculator  # noqa: E402
from civ6map_to_scenario import convert_civ6map  # noqa: E402


def _normalize_coords(coords):
    """[x,y] -> [(x,y)];  [[x1,y1],[x2,y2]] -> [(x1,y1),(x2,y2)]."""
    if not coords:
        return []
    if isinstance(coords[0], (list, tuple)):
        return [(int(c[0]), int(c[1])) for c in coords]
    return [(int(coords[0]), int(coords[1]))]


def build_tiles(map_file):
    parsed = convert_civ6map(str(map_file))
    tiles = {}
    for td in parsed["tiles"]:
        tile = Tile(
            x=td["x"],
            y=td["y"],
            terrain=td.get("terrain", "GRASS"),
            feature=td.get("feature"),
            is_hills=td.get("is_hills", False),
            is_floodplains=td.get("is_floodplains", False),
            river_edges=td.get("river_edges", []),
            river_names=td.get("river_names", []),
            resource=td.get("resource"),
            resource_type=td.get("resource_type"),
            improvement=td.get("improvement"),
        )
        tiles[(tile.x, tile.y)] = tile
    return tiles


def main():
    ap = argparse.ArgumentParser(description="Build + verify a Civ6 solution.")
    ap.add_argument("plan", help="Path to plan JSON (map_file, city_center/cities, placements).")
    ap.add_argument("-o", "--output", help="Where to write the final solution JSON.")
    args = ap.parse_args()

    plan = json.loads(Path(args.plan).read_text())

    map_file = plan["map_file"]
    population = plan.get("population", 7)
    raw_placements = plan.get("placements", {})

    if "cities" in plan:
        city_centers = [tuple(c) for c in plan["cities"]]
    elif "city_center" in plan:
        city_centers = [tuple(plan["city_center"])]
    else:
        print("ERROR: plan needs 'city_center' or 'cities'", file=sys.stderr)
        sys.exit(2)

    num_cities = plan.get("num_cities", len(city_centers))

    tiles = build_tiles(map_file)
    errors = []
    warnings = []

    if len(city_centers) != num_cities:
        errors.append(f"Expected {num_cities} cities, got {len(city_centers)}")

    # City center legality
    for i, cc in enumerate(city_centers):
        tile = tiles.get(cc)
        if tile is None:
            errors.append(f"City {i+1} at {cc}: No tile data")
            continue
        if tile.is_water:
            errors.append(f"City {i+1} at {cc}: Cannot settle on water")
        if tile.is_mountain:
            errors.append(f"City {i+1} at {cc}: Cannot settle on mountain")
        if tile.is_natural_wonder:
            errors.append(f"City {i+1} at {cc}: Cannot settle on natural wonder")

    if len(city_centers) > 1 and not errors:
        ok, derr = validate_city_distances(city_centers, tiles)
        if not ok:
            errors.extend(f"City distance violation: {e}" for e in derr)

    # Ensure city tiles exist (grader does the same)
    for cc in city_centers:
        if cc not in tiles:
            tiles[cc] = Tile(x=cc[0], y=cc[1], terrain="GRASS")

    # Unknown district types
    for name in raw_placements:
        if name not in DISTRICT_NAME_MAP:
            errors.append(
                f"Unknown district type: {name} "
                f"(use canonical names; for several of the same type put a LIST of "
                f"[x,y] pairs under ONE key, not '{name}')"
            )

    if not errors:
        ok, cerr = validate_district_count(raw_placements, population)
        if not ok:
            errors.extend(cerr)
        ok, uerr = validate_district_uniqueness(raw_placements, city_id="city")
        if not ok:
            errors.extend(uerr)

    # Duplicate positions
    pos_counts = {}
    for name, coords in raw_placements.items():
        if name not in DISTRICT_NAME_MAP:
            continue
        for pos in _normalize_coords(coords):
            pos_counts.setdefault(pos, []).append(name)
    for pos, ds in pos_counts.items():
        if len(ds) > 1:
            errors.append(f"Multiple districts at {pos}: {ds}")

    # Per-placement rule validation
    city_center = city_centers[0]
    if not errors:
        rules = get_placement_rules(tiles, city_center, population)
        existing = {cc: DistrictType.CITY_CENTER for cc in city_centers}
        for name, coords in raw_placements.items():
            dtype = DISTRICT_NAME_MAP[name]
            for (x, y) in _normalize_coords(coords):
                v = rules.validate_placement(dtype, x, y, existing)
                if not v.valid:
                    errors.extend(f"{name}@({x},{y}): {e}" for e in v.errors)
                warnings.extend(f"{name}@({x},{y}): {w}" for w in v.warnings)
                existing[(x, y)] = dtype

    if errors:
        print("INVALID PLAN -- fix these and rerun:", file=sys.stderr)
        for e in errors:
            print("  ERROR:", e, file=sys.stderr)
        for w in warnings:
            print("  warn :", w, file=sys.stderr)
        sys.exit(1)

    # Build placements dict for adjacency (identical to grader)
    placements = {}
    for name, coords in raw_placements.items():
        dtype = DISTRICT_NAME_MAP[name]
        for pos in _normalize_coords(coords):
            placements[pos] = dtype
    for cc in city_centers:
        placements[cc] = DistrictType.CITY_CENTER

    calculator = get_adjacency_calculator(tiles)
    total, per_district = calculator.calculate_total_adjacency(placements)

    # Aggregate per-district-NAME bonuses so they sum to total exactly.
    bonuses = {}
    for key, res in per_district.items():
        name = key.split("@")[0]
        bonuses[name] = bonuses.get(name, 0) + res.total_bonus
    # Ensure every placed district name appears (even if 0 bonus).
    for name in raw_placements:
        if name in DISTRICT_NAME_MAP:
            bonuses.setdefault(name, 0)

    # Output format: repeated -> list of [x,y]; single -> [x,y].
    out_placements = {}
    for name, coords in raw_placements.items():
        norm = _normalize_coords(coords)
        if len(norm) == 1:
            out_placements[name] = [norm[0][0], norm[0][1]]
        else:
            out_placements[name] = [[x, y] for (x, y) in norm]

    solution = {}
    if len(city_centers) == 1:
        solution["city_center"] = [city_centers[0][0], city_centers[0][1]]
    else:
        solution["cities"] = [{"center": [c[0], c[1]]} for c in city_centers]
    solution["placements"] = out_placements
    solution["adjacency_bonuses"] = bonuses
    solution["total_adjacency"] = total

    text = json.dumps(solution, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text)
        print(f"WROTE {args.output}", file=sys.stderr)
    else:
        print(text)

    print(f"VALID. total_adjacency={total} (matches grader). "
          f"per-district={bonuses}", file=sys.stderr)
    for w in warnings:
        print("  warn :", w, file=sys.stderr)


if __name__ == "__main__":
    main()
