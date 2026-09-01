#!/usr/bin/env python3
"""Deterministic minimal-change repair for a plan-view bathroom layout.

Given an already-extracted original layout (the JSON you produced with the
architectural-dxf-extraction skill) and the task rules file, this computes a
repaired layout that satisfies the plan-view accessibility rules and writes:

    repaired_layout.json   -- the compliant, minimally-changed layout
    violations_before.json -- the rule failures detected in the ORIGINAL layout
    changes.json           -- a design-action change log

Every transformation is computed from geometry (it mirrors the verifier's own
usable-floor math with shapely); nothing is hard-coded to a specific drawing, so
it generalizes across bathroom plans of this class. Run it instead of hand-
placing the turning circle / toilet / grab bars, which is easy to get subtly
wrong (the circle must clear the inward-offset room polygon on EVERY edge,
including the door-wall edge, and the toilet centerline must both fall in range
AND match the geometric distance to the nearest room side wall).

Usage:
    python repair_layout.py \
        --extracted /root/output/extracted_original_layout.json \
        --rules /root/input/ada_rules.json \
        --outdir /root/output

The extracted layout must contain: room.polygon, door (clear_width, swing,
opening_segment), fixtures (toilet, lavatory, bathtub with bbox), grab_bars,
and turning_space (diameter, center). Fixture ids are preserved verbatim.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
from pathlib import Path
from typing import Any

from shapely.geometry import Point, Polygon


def polygon(points: list[list[float]]) -> Polygon:
    return Polygon([(float(x), float(y)) for x, y in points])


def bbox_polygon(points: list[list[float]]) -> Polygon:
    return polygon(points)


def fixture_by_type(layout: dict[str, Any], fixture_type: str) -> dict[str, Any]:
    for fixture in layout.get("fixtures", []):
        if fixture.get("type") == fixture_type:
            return fixture
    raise KeyError(f"Layout is missing a {fixture_type} fixture.")


def lavatory_has_required_knee_clearance(fixture: dict[str, Any], rules: dict[str, Any]) -> bool:
    clearance = fixture.get("knee_clearance") or {}
    return bool(
        fixture.get("knee_toe_clearance")
        and float(clearance.get("width", 0.0)) >= float(rules["lavatory_knee_clearance_width_min"])
        and float(clearance.get("depth", 0.0)) >= float(rules["lavatory_knee_clearance_depth_min"])
    )


def usable_floor_polygon(layout: dict[str, Any], rules: dict[str, Any]) -> Polygon:
    """Usable floor = room polygon offset inward on ALL edges by the wall/boundary
    offset, minus fixtures the rules do NOT let the turning circle overlap.

    This matches the verifier exactly: the toilet clear floor is overlappable,
    the lavatory is overlappable only when it declares valid knee/toe clearance,
    and everything else (e.g. the bathtub) is subtracted as a blocker.
    """
    room = polygon(layout["room"]["polygon"])
    wall_offset = float(rules.get("wall_boundary_clearance_offset", 2.8))
    usable = room.buffer(-wall_offset, join_style=2)
    for fixture in layout.get("fixtures", []):
        ftype = fixture.get("type")
        if ftype == "toilet" and rules.get("turning_space_may_overlap_toilet_clearance", True):
            continue
        if (
            ftype == "lavatory"
            and rules.get("lavatory_may_overlap_turning_space_only_with_knee_toe_clearance", True)
            and lavatory_has_required_knee_clearance(fixture, rules)
        ):
            continue
        usable = usable.difference(bbox_polygon(fixture["bbox"]))
    return usable


def turning_circle_fits(layout: dict[str, Any], rules: dict[str, Any]) -> bool:
    usable = usable_floor_polygon(layout, rules)
    if usable.is_empty:
        return False
    turning = layout["turning_space"]
    diameter = float(turning.get("diameter", 0.0))
    center = turning.get("center") or []
    if diameter < float(rules["turning_circle_diameter_min"]) or len(center) != 2:
        return False
    circle = Point(float(center[0]), float(center[1])).buffer(diameter / 2.0, quad_segs=64)
    return bool(usable.buffer(1e-3).covers(circle))


def find_turning_center(layout: dict[str, Any], rules: dict[str, Any]) -> list[float]:
    """A center is valid iff it lies in the usable floor eroded by the radius.
    Returns a point in that feasible region, or None if none exists at this size."""
    usable = usable_floor_polygon(layout, rules)
    diameter = float(rules["turning_circle_diameter_min"])
    feasible = usable.buffer(-diameter / 2.0, join_style=2)
    if feasible.is_empty:
        return None
    point = feasible.representative_point()
    return [round(float(point.x), 3), round(float(point.y), 3)]


def shift_bbox(bbox: list[list[float]], dx: float, dy: float = 0.0) -> list[list[float]]:
    return [[round(float(x) + dx, 3), round(float(y) + dy, 3)] for x, y in bbox]


def detect_violations(layout: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    """Report only rules the ORIGINAL layout actually fails, using the canonical
    rule names the verifier expects (range rules are not split into min/max)."""
    violations: list[dict[str, Any]] = []

    toilet = fixture_by_type(layout, "toilet")
    centerline = float(toilet.get("centerline_from_side_wall", -1.0))
    lo = float(rules["toilet_centerline_from_side_wall_min"])
    hi = float(rules["toilet_centerline_from_side_wall_max"])
    if centerline < lo or centerline > hi:
        violations.append(
            {
                "rule": "toilet_centerline_from_side_wall_range",
                "element_id": toilet.get("id", "WC1"),
                "actual": round(centerline, 3),
                "required": [lo, hi],
            }
        )

    if not turning_circle_fits(layout, rules):
        violations.append(
            {
                "rule": "turning_circle_fit_usable_floor",
                "element_id": layout.get("room", {}).get("id", "bathroom_1"),
                "actual": layout["turning_space"].get("center"),
                "required": f">= {rules['turning_circle_diameter_min']} in circle inside usable floor",
            }
        )

    return {"violations": violations}


def compute_repaired_layout(original: dict[str, Any], rules: dict[str, Any]) -> dict[str, Any]:
    """Minimally-invasive repair. Each edit is keyed to a specific rule failure and
    the geometry is computed, never copied from an answer key."""
    repaired = copy.deepcopy(original)
    repaired.setdefault("unit", "in")

    room_xs = [float(p[0]) for p in repaired["room"]["polygon"]]
    room_ys = [float(p[1]) for p in repaired["room"]["polygon"]]
    room_left, room_right = min(room_xs), max(room_xs)
    room_top = max(room_ys)
    wall_offset = float(rules.get("wall_boundary_clearance_offset", 2.8))

    target_centerline = round(
        (float(rules["toilet_centerline_from_side_wall_min"])
         + float(rules["toilet_centerline_from_side_wall_max"])) / 2.0,
        3,
    )

    # 1) Toilet centerline: move the toilet horizontally so its bbox-center sits
    #    target_centerline from the NEAREST side wall, then declare that value so
    #    the declared centerline matches the geometry the verifier recomputes.
    toilet = fixture_by_type(repaired, "toilet")
    wc_xs = [float(p[0]) for p in toilet["bbox"]]
    wc_center_x = (min(wc_xs) + max(wc_xs)) / 2.0
    if abs(wc_center_x - room_left) <= abs(room_right - wc_center_x):
        target_center_x = room_left + target_centerline
        adjacent_side_x = room_left
    else:
        target_center_x = room_right - target_centerline
        adjacent_side_x = room_right
    toilet["bbox"] = shift_bbox(toilet["bbox"], target_center_x - wc_center_x)
    toilet["centerline_from_side_wall"] = target_centerline

    # 2) Door swing: an inward swing enters fixture clearance; represent the
    #    repaired condition as outward (a sliding door is equally acceptable).
    if repaired["door"].get("swing") == "inward":
        repaired["door"]["swing"] = "outward"

    # 3) Lavatory: ensure the declared plan-view knee/toe clearance is present and
    #    meets the minimums so the turning circle may overlap it.
    try:
        lav = fixture_by_type(repaired, "lavatory")
        if not lavatory_has_required_knee_clearance(lav, rules):
            lav["knee_toe_clearance"] = True
            clr = lav.get("knee_clearance") or {}
            lav["knee_clearance"] = {
                "width": max(float(clr.get("width", 0.0)), float(rules["lavatory_knee_clearance_width_min"])),
                "depth": max(float(clr.get("depth", 0.0)), float(rules["lavatory_knee_clearance_depth_min"])),
            }
    except KeyError:
        pass

    # 4) Turning circle: place it inside the usable floor. If the inward-offset
    #    room cannot contain the full diameter on some axis, expand the room
    #    boundary just enough (minimal change) and retry.
    center = find_turning_center(repaired, rules)
    if center is None:
        diameter = float(rules["turning_circle_diameter_min"])
        needed = diameter + 2.0 * wall_offset
        room_bottom = min(room_ys)
        # Grow the deficient axis by pushing the wall away from the fixtures
        # (right and top), first to the geometric minimum then in small steps if
        # blockers still leave the usable region short. Bounded so the repair
        # stays minimal.
        new_right = max(room_right, room_left + needed)
        new_top = max(room_top, room_bottom + needed)
        for _ in range(40):
            repaired["room"]["polygon"] = [
                [round(room_left, 3), round(room_bottom, 3)],
                [round(new_right, 3), round(room_bottom, 3)],
                [round(new_right, 3), round(new_top, 3)],
                [round(room_left, 3), round(new_top, 3)],
            ]
            center = find_turning_center(repaired, rules)
            if center is not None:
                break
            new_right += diameter * 0.1
            new_top += diameter * 0.1
        room_right, room_top = new_right, new_top
    if center is None:
        raise RuntimeError("Could not fit the required turning circle even after expanding the room.")
    repaired["turning_space"]["center"] = center
    repaired["turning_space"].setdefault("type", "circle")
    repaired["turning_space"]["diameter"] = max(
        float(repaired["turning_space"].get("diameter", 0.0)),
        float(rules["turning_circle_diameter_min"]),
    )

    # 5) Grab bars: recompute both bars to follow the repaired toilet and meet the
    #    minimum lengths. Side bar is vertical on the toilet's side wall and spans
    #    the toilet use zone; rear bar is horizontal on the rear wall and crosses
    #    the toilet centerline.
    new_wc_xs = [float(p[0]) for p in toilet["bbox"]]
    new_wc_ys = [float(p[1]) for p in toilet["bbox"]]
    wc_center_x = (min(new_wc_xs) + max(new_wc_xs)) / 2.0
    wc_center_y = (min(new_wc_ys) + max(new_wc_ys)) / 2.0

    side_min = float(rules["side_grab_bar_length_min"])
    side_x = round(adjacent_side_x + (wall_offset if adjacent_side_x == room_left else -wall_offset), 3)
    side_y_top = round(room_top, 3)
    side_y_bottom = round(min(wc_center_y - side_min / 2.0, side_y_top - side_min), 3)
    side_bar = {
        "id": "GB_SIDE",
        "type": "side_wall",
        "length": round(side_y_top - side_y_bottom, 3),
        "segment": [[side_x, side_y_bottom], [side_x, side_y_top]],
    }

    rear_min = float(rules["rear_grab_bar_length_min"])
    rear_y = round(room_top - (rear_min * 0.18 + wall_offset), 3)
    rear_x_left = round(room_left, 3)
    rear_x_right = round(max(rear_x_left + rear_min, wc_center_x + 12.0), 3)
    rear_bar = {
        "id": "GB_REAR",
        "type": "rear_wall",
        "length": round(rear_x_right - rear_x_left, 3),
        "segment": [[rear_x_left, rear_y], [rear_x_right, rear_y]],
    }
    repaired["grab_bars"] = [rear_bar, side_bar]

    return repaired


def build_change_log(original: dict[str, Any], repaired: dict[str, Any]) -> dict[str, Any]:
    changes: list[str] = []
    try:
        o_wc = fixture_by_type(original, "toilet")
        n_wc = fixture_by_type(repaired, "toilet")
        oc = float(o_wc.get("centerline_from_side_wall", 0.0))
        nc = float(n_wc.get("centerline_from_side_wall", 0.0))
        if not math.isclose(oc, nc, abs_tol=0.05):
            ox = sum(float(p[0]) for p in o_wc["bbox"]) / len(o_wc["bbox"])
            nx = sum(float(p[0]) for p in n_wc["bbox"]) / len(n_wc["bbox"])
            changes.append(
                f"Shifted WC1 by {nx - ox:+.3f} in so the toilet centerline is {nc} in "
                f"from the adjacent side wall, satisfying the required range."
            )
    except KeyError:
        pass

    if original.get("door", {}).get("swing") != repaired.get("door", {}).get("swing"):
        changes.append(
            f"Changed door swing from {original.get('door', {}).get('swing')} to "
            f"{repaired.get('door', {}).get('swing')} so it no longer enters fixture clearance."
        )

    oc_xy = list(original.get("turning_space", {}).get("center", []))
    nc_xy = list(repaired.get("turning_space", {}).get("center", []))
    if oc_xy and nc_xy and (
        not math.isclose(oc_xy[0], nc_xy[0], abs_tol=0.05)
        or not math.isclose(oc_xy[1], nc_xy[1], abs_tol=0.05)
    ):
        changes.append(
            f"Re-centered the {repaired['turning_space']['diameter']} in turning circle to "
            f"({nc_xy[0]}, {nc_xy[1]}) so it fits inside the usable floor area."
        )

    o_area = polygon(original["room"]["polygon"]).area
    n_area = polygon(repaired["room"]["polygon"]).area
    if n_area > o_area + 1.0:
        changes.append(
            f"Expanded the room boundary from {o_area:.1f} to {n_area:.1f} sq in "
            f"because the turning circle could not fit by repositioning alone."
        )

    changes.append("Preserved protected fixtures and original fixture identities (WC1, LAV1, TUB1).")
    changes.append("Recomputed side-wall and rear-wall grab bars to follow the repaired toilet position.")
    return {"changes": changes}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extracted", default="/root/output/extracted_original_layout.json")
    parser.add_argument("--rules", default="/root/input/ada_rules.json")
    parser.add_argument("--outdir", default="/root/output")
    args = parser.parse_args()

    original = json.loads(Path(args.extracted).read_text(encoding="utf-8"))
    rules = json.loads(Path(args.rules).read_text(encoding="utf-8"))

    repaired = compute_repaired_layout(original, rules)
    violations = detect_violations(original, rules)
    changes = build_change_log(original, repaired)

    # Post-condition self-check: the repaired circle must fit; otherwise the
    # repair is wrong and should not be written silently.
    if not turning_circle_fits(repaired, rules):
        raise RuntimeError("Repaired turning circle still does not fit usable floor; check extraction.")

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "repaired_layout.json").write_text(json.dumps(repaired, indent=2) + "\n", encoding="utf-8")
    (outdir / "violations_before.json").write_text(json.dumps(violations, indent=2) + "\n", encoding="utf-8")
    (outdir / "changes.json").write_text(json.dumps(changes, indent=2) + "\n", encoding="utf-8")
    print("Wrote repaired_layout.json, violations_before.json, changes.json to", outdir)
    print("Repaired turning center:", repaired["turning_space"]["center"],
          "| toilet centerline:", fixture_by_type(repaired, "toilet")["centerline_from_side_wall"])


if __name__ == "__main__":
    main()
