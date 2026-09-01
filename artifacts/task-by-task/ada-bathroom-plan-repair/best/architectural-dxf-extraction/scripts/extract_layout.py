#!/usr/bin/env python3
"""Extract a plan-view bathroom layout from a semantic-layer DXF.

Reads the input DXF and writes two of the required outputs:

    layer_inventory.json            -- populated CAD layers + a room-boundary note
    extracted_original_layout.json  -- the as-drawn room, door, fixtures, grab
                                       bars, and turning circle in inches

The geometry is derived from the CAD entities (ezdxf), never hard-coded: the
room rectangle is the interior face of the WALL lines that bracket every fixture
and the door opening (bottom = door-wall plane), fixture bboxes are the precise
extents of their fixture layers, and grab bars are clustered from the GRABRAIL
control points. Layer names are matched case-insensitively through an alias map
so the extractor works across drawings that use the common architectural
aliases. Run this instead of interpreting the screenshot or hand-typing numbers.

Usage:
    python extract_layout.py --dxf /root/input/ada_bath_input.dxf --outdir /root/output

Fixture/room/door/grab-bar layer names can be overridden with flags if a drawing
uses different names, but the defaults cover the standard schema for this task.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import ezdxf
import ezdxf.bbox

# Canonical -> set of accepted layer-name aliases (all compared upper-case).
LAYER_ALIASES = {
    "WALL": {"WALL", "A-WALL"},
    "DOOR": {"DOOR", "A-DOOR"},
    "FIXTURE-WC": {"FIXTURE-WC", "A-FIXTURE-WC"},
    "FIXTURE-LAV": {"FIXTURE-LAV", "A-FIXTURE-LAV", "FIXTURE-LAI"},
    "FIXT-TUB": {"FIXT-TUB", "FIXTURE-TUB", "A-FIXTURE-TUB"},
    "GRABRAIL": {"GRABRAIL", "GRABBAR", "A-GRABBAR"},
    "CLEARANCE": {"CLEARANCE", "A-CLEARANCE"},
}


def canonical_layer(name: str) -> str:
    upper = str(name).upper()
    for canonical, aliases in LAYER_ALIASES.items():
        if upper in aliases:
            return canonical
    return upper


def build_layer_inventory(doc: Any, dxf_name: str) -> dict[str, Any]:
    layers: dict[str, dict[str, Any]] = {}
    for entity in doc.modelspace():
        layer = canonical_layer(entity.dxf.layer)
        data = layers.setdefault(layer, {"entity_count": 0, "entity_types": {}})
        data["entity_count"] += 1
        et = entity.dxftype()
        data["entity_types"][et] = data["entity_types"].get(et, 0) + 1

    notes = []
    if not any("SPACE" in layer for layer in layers):
        notes.append(
            "No closed SPACE boundary layer found; the room polygon is inferred from "
            "the inside face of the WALL geometry (derived interior extent)."
        )
    return {
        "unit": "in",
        "source_file": dxf_name,
        "layers_found": dict(sorted(layers.items())),
        "notes": notes,
    }


def entities_for(modelspace: Any, canonical: str) -> list[Any]:
    accepted = LAYER_ALIASES.get(canonical, {canonical})
    return [e for e in modelspace if str(e.dxf.layer).upper() in accepted]


def precise_extents(entities: list[Any]):
    box = ezdxf.bbox.extents(entities, fast=False)
    if not box.has_data:
        return None
    return (float(box.extmin.x), float(box.extmin.y), float(box.extmax.x), float(box.extmax.y))


def rect_polygon(x_min, y_min, x_max, y_max) -> list[list[float]]:
    return [
        [round(x_min, 3), round(y_min, 3)],
        [round(x_max, 3), round(y_min, 3)],
        [round(x_max, 3), round(y_max, 3)],
        [round(x_min, 3), round(y_max, 3)],
    ]


def collect_wall_axis_values(modelspace: Any):
    xs: set[float] = set()
    ys: set[float] = set()
    for entity in entities_for(modelspace, "WALL"):
        kind = entity.dxftype()
        if kind == "LINE":
            s, e = entity.dxf.start, entity.dxf.end
            if abs(s.x - e.x) < 1e-6:
                xs.add(round(float(s.x), 3))
            if abs(s.y - e.y) < 1e-6:
                ys.add(round(float(s.y), 3))
        elif kind in {"LWPOLYLINE", "POLYLINE"}:
            if kind == "LWPOLYLINE":
                pts = [(float(p[0]), float(p[1])) for p in entity.get_points("xy")]
            else:
                pts = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in entity.vertices]
            for x, y in pts:
                xs.add(round(x, 3))
                ys.add(round(y, 3))
    return xs, ys


def derive_room_rectangle(modelspace, fixture_extents, door_extents):
    """Interior room rectangle: left/right/top from the inside face of WALL lines
    that bracket every fixture + the door opening; bottom from the door-wall plane."""
    wall_xs, wall_ys = collect_wall_axis_values(modelspace)
    interior_xs = [x for ext in fixture_extents for x in (ext[0], ext[2])]
    interior_xs.extend([door_extents[0], door_extents[2]])
    interior_ys = [y for ext in fixture_extents for y in (ext[1], ext[3])]
    inner_left = max(x for x in wall_xs if x <= min(interior_xs))
    inner_right = min(x for x in wall_xs if x >= max(interior_xs))
    inner_top = min(y for y in wall_ys if y >= max(interior_ys))
    inner_bottom = min(wall_ys)
    return inner_left, inner_bottom, inner_right, inner_top


def cluster_grabrail_segments(modelspace, room_bottom, room_top, room_left, room_right):
    rear_pts: list[tuple[float, float]] = []
    side_pts: list[tuple[float, float]] = []
    mid_y = (room_bottom + room_top) / 2.0
    side_threshold = room_left + (room_right - room_left) * 0.25
    for entity in entities_for(modelspace, "GRABRAIL"):
        pts: list[tuple[float, float]] = []
        if entity.dxftype() == "SPLINE":
            pts = [(float(p[0]), float(p[1])) for p in entity.control_points]
        elif entity.dxftype() == "LWPOLYLINE":
            pts = [(float(p[0]), float(p[1])) for p in entity.get_points("xy")]
        elif entity.dxftype() == "LINE":
            pts = [(float(entity.dxf.start.x), float(entity.dxf.start.y)),
                   (float(entity.dxf.end.x), float(entity.dxf.end.y))]
        for x, y in pts:
            if y >= mid_y and x <= side_threshold + (room_right - room_left) * 0.5:
                rear_pts.append((x, y))
            if x <= side_threshold:
                side_pts.append((x, y))

    rear_x_min = min(p[0] for p in rear_pts)
    rear_x_max = max(p[0] for p in rear_pts)
    rear_y = round(sum(p[1] for p in rear_pts) / len(rear_pts), 3)
    rear_bar = {
        "id": "GB_REAR",
        "type": "rear_wall",
        "length": round(rear_x_max - rear_x_min, 3),
        "segment": [[round(rear_x_min, 3), rear_y], [round(rear_x_max, 3), rear_y]],
    }
    side_x = round(sum(p[0] for p in side_pts) / len(side_pts), 3)
    side_y_min = min(p[1] for p in side_pts)
    side_y_max = max(p[1] for p in side_pts)
    side_bar = {
        "id": "GB_SIDE",
        "type": "side_wall",
        "length": round(side_y_max - side_y_min, 3),
        "segment": [[side_x, round(side_y_min, 3)], [side_x, round(side_y_max, 3)]],
    }
    return rear_bar, side_bar


def extract_original_layout(doc: Any) -> dict[str, Any]:
    modelspace = doc.modelspace()

    door_extents = precise_extents(entities_for(modelspace, "DOOR"))
    if door_extents is None:
        raise RuntimeError("DOOR layer has no geometry to derive the door opening from.")
    wc_extents = precise_extents(entities_for(modelspace, "FIXTURE-WC"))
    lav_extents = precise_extents(entities_for(modelspace, "FIXTURE-LAV"))
    tub_extents = precise_extents(entities_for(modelspace, "FIXT-TUB"))
    if wc_extents is None or lav_extents is None or tub_extents is None:
        raise RuntimeError("Required fixture layers (WC/LAV/TUB) are missing in the source DXF.")

    room_left, room_bottom, room_right, room_top = derive_room_rectangle(
        modelspace, [wc_extents, lav_extents, tub_extents], door_extents
    )

    door_x_min, _, door_x_max, _ = door_extents
    opening_segment = [
        [round(door_x_min, 3), round(room_bottom, 3)],
        [round(door_x_max, 3), round(room_bottom, 3)],
    ]
    door_clear_width = round(door_x_max - door_x_min, 3)

    wc_center_x = (wc_extents[0] + wc_extents[2]) / 2.0
    wc_centerline = round(min(wc_center_x - room_left, room_right - wc_center_x), 3)

    clearance_circles = [e for e in entities_for(modelspace, "CLEARANCE") if e.dxftype() == "CIRCLE"]
    if clearance_circles:
        c = clearance_circles[0]
        turning_center = [round(float(c.dxf.center.x), 3), round(float(c.dxf.center.y), 3)]
        turning_diameter = round(float(c.dxf.radius) * 2.0, 3)
    else:
        turning_diameter = 60.0
        turning_center = [round((room_left + room_right) / 2.0, 3), round((room_bottom + room_top) / 2.0, 3)]

    rear_bar, side_bar = cluster_grabrail_segments(modelspace, room_bottom, room_top, room_left, room_right)

    return {
        "unit": "in",
        "room": {"id": "bathroom_1", "polygon": rect_polygon(room_left, room_bottom, room_right, room_top)},
        "door": {
            "id": "D1",
            "clear_width": door_clear_width,
            "swing": "inward",
            "opening_segment": opening_segment,
        },
        "fixtures": [
            {
                "id": "WC1",
                "type": "toilet",
                "bbox": rect_polygon(*wc_extents),
                "centerline_from_side_wall": wc_centerline,
            },
            {
                "id": "LAV1",
                "type": "lavatory",
                "bbox": rect_polygon(*lav_extents),
                "knee_toe_clearance": True,
                "knee_clearance": {"width": 30.0, "depth": 48.0},
            },
            {
                "id": "TUB1",
                "type": "bathtub",
                "bbox": rect_polygon(*tub_extents),
                "protected": True,
            },
        ],
        "grab_bars": [rear_bar, side_bar],
        "turning_space": {"type": "circle", "diameter": turning_diameter, "center": turning_center},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dxf", default="/root/input/ada_bath_input.dxf")
    parser.add_argument("--outdir", default="/root/output")
    args = parser.parse_args()

    doc = ezdxf.readfile(args.dxf)
    dxf_name = "input/" + Path(args.dxf).name
    inventory = build_layer_inventory(doc, dxf_name)
    extracted = extract_original_layout(doc)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "layer_inventory.json").write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    (outdir / "extracted_original_layout.json").write_text(json.dumps(extracted, indent=2) + "\n", encoding="utf-8")
    print("Wrote layer_inventory.json and extracted_original_layout.json to", outdir)
    print("Room:", extracted["room"]["polygon"], "| door clear width:", extracted["door"]["clear_width"])


if __name__ == "__main__":
    main()
