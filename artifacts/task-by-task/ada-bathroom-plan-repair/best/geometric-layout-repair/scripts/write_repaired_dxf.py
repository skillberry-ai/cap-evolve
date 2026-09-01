#!/usr/bin/env python3
"""Write the repaired CAD deliverable (repaired_plan.dxf) from repaired_layout.json.

Preserves the original drawing context (reads the input DXF) and overlays the
final repaired geometry on the machine-checkable semantic layers the verifier
looks for: REPAIR-ROOM, REPAIR-DOOR, REPAIR-WC, REPAIR-LAV, REPAIR-TUB,
REPAIR-GRABBAR, REPAIR-CLEARANCE. Because it draws straight from
repaired_layout.json, the DXF and JSON always describe the same design (the
verifier checks IoU of the repair polygons and matches the circle + grab-bar
lengths). Run this instead of hand-adding entities so the two stay in sync.

Usage:
    python write_repaired_dxf.py \
        --input-dxf /root/input/ada_bath_input.dxf \
        --layout /root/output/repaired_layout.json \
        --out /root/output/repaired_plan.dxf
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import ezdxf

REPAIR_LAYERS = {
    "REPAIR-ROOM": 3,
    "REPAIR-DOOR": 4,
    "REPAIR-WC": 1,
    "REPAIR-LAV": 2,
    "REPAIR-TUB": 6,
    "REPAIR-GRABBAR": 5,
    "REPAIR-CLEARANCE": 30,
    "REPAIR-NOTES": 7,
}
FIXTURE_LAYER = {"toilet": "REPAIR-WC", "lavatory": "REPAIR-LAV", "bathtub": "REPAIR-TUB"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dxf", default="/root/input/ada_bath_input.dxf")
    parser.add_argument("--layout", default="/root/output/repaired_layout.json")
    parser.add_argument("--out", default="/root/output/repaired_plan.dxf")
    args = parser.parse_args()

    layout = json.loads(Path(args.layout).read_text(encoding="utf-8"))
    doc = ezdxf.readfile(args.input_dxf)
    msp = doc.modelspace()
    for name, color in REPAIR_LAYERS.items():
        if name not in doc.layers:
            doc.layers.add(name, color=color)

    def closed_poly(layer, pts):
        msp.add_lwpolyline([(float(x), float(y)) for x, y in pts], close=True, dxfattribs={"layer": layer})

    closed_poly("REPAIR-ROOM", layout["room"]["polygon"])

    door = layout["door"]
    seg = door["opening_segment"]
    msp.add_line(tuple(seg[0]), tuple(seg[1]), dxfattribs={"layer": "REPAIR-DOOR"})

    for fixture in layout.get("fixtures", []):
        closed_poly(FIXTURE_LAYER.get(fixture.get("type"), "REPAIR-NOTES"), fixture["bbox"])

    for grab_bar in layout.get("grab_bars", []):
        s = grab_bar["segment"]
        msp.add_line(tuple(s[0]), tuple(s[1]), dxfattribs={"layer": "REPAIR-GRABBAR"})

    turning = layout["turning_space"]
    msp.add_circle(tuple(turning["center"]), float(turning["diameter"]) / 2.0, dxfattribs={"layer": "REPAIR-CLEARANCE"})
    msp.add_text("REPAIRED ADA PLAN-VIEW LAYOUT", dxfattribs={"layer": "REPAIR-NOTES", "height": 4.0})

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(args.out)
    print("Wrote repaired CAD to", args.out)


if __name__ == "__main__":
    main()
