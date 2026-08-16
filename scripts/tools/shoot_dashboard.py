#!/usr/bin/env python3
"""Screenshot every tab of a cap-evolve dashboard, from the real running UI.

Serves the committed static export (or points at a live dashboard), enumerates the
tabs the UI actually renders — the tab set is the dashboard's business, not this
script's — and writes one PNG per tab at 1920x1080, deviceScaleFactor 2, dark.

    /tmp/vidvenv/bin/python scripts/tools/shoot_dashboard.py
    /tmp/vidvenv/bin/python scripts/tools/shoot_dashboard.py --live http://127.0.0.1:7878 --run run_x

Every tab is captured even when it is empty: an empty tab is a finding, and
silently skipping it is how an empty tab stays unnoticed. The page is measured
after each tab settles and the viewport grown to the content height, so nothing
is clipped; `--fixed-height` keeps a strict 1080 crop instead.
"""
from __future__ import annotations

import argparse
import contextlib
import functools
import http.server
import re
import socketserver
import subprocess
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STATIC = REPO / "examples/tau2_airline/run_full/ui"
OUT = REPO / "docs/assets/screenshots"
W, H = 1920, 1080
# Full-page captures grow to the content; this ceiling only exists so a runaway page
# cannot allocate an absurd bitmap. Hitting it is reported, never silent.
MAX_H = 8000
PREFIX = "dash_full_"


def serve(root: Path) -> tuple[int, socketserver.TCPServer]:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(root))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd.server_address[1], httpd


def slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_")


def shoot(url: str, run: str, fixed: bool, out: Path, prefix: str,
          only: set[str] | None) -> list[Path]:
    from playwright.sync_api import sync_playwright

    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--force-color-profile=srgb", "--hide-scrollbars"])
        ctx = b.new_context(viewport={"width": W, "height": H},
                            device_scale_factor=2, color_scheme="dark")
        pg = ctx.new_page()
        pg.goto(url, wait_until="load")
        pg.wait_for_timeout(1200)

        row = pg.get_by_text(run, exact=False).first
        if row.count():
            row.click()
            pg.wait_for_timeout(1500)

        tabs = [t.strip() for t in pg.get_by_role("tab").all_inner_texts() if t.strip()]
        print(f"tabs from the live UI ({len(tabs)}): {', '.join(tabs)}")

        for label in tabs:
            if only and slug(label) not in only:
                continue
            pg.get_by_role("tab", name=label, exact=True).first.click()
            pg.wait_for_timeout(1400)
            # No spinner, no in-flight fetch, no half-drawn chart.
            with contextlib.suppress(Exception):
                pg.wait_for_selector(".animate-pulse", state="detached", timeout=4000)
            pg.wait_for_timeout(400)
            if not fixed:
                # Grow the viewport to the content so nothing is cut off mid-row.
                h = pg.evaluate("Math.ceil(document.documentElement.scrollHeight)")
                if h > H:
                    if h + 24 > MAX_H:
                        # Say so rather than silently shipping a cropped "full page".
                        print(f"   !! {label} is {h}px — capped at {MAX_H}, BOTTOM IS CUT")
                    pg.set_viewport_size({"width": W, "height": min(h + 24, MAX_H)})
                    pg.wait_for_timeout(700)
            dst = out / f"{prefix}{slug(label)}.png"
            pg.screenshot(path=str(dst))
            print(f"  {label:<14} -> {dst.name}")
            written.append(dst)
            if not fixed:
                pg.set_viewport_size({"width": W, "height": H})
                pg.wait_for_timeout(200)
        ctx.close()
        b.close()
    return written


def optimize(paths: list[Path]) -> None:
    """Shrink losslessly if pngquant/oxipng are around; never fail the run over it."""
    for tool, args in (("oxipng", ["-o", "4", "--strip", "safe", "-q"]),
                       ("pngquant", ["--force", "--skip-if-larger", "--quality=70-96",
                                     "--speed", "1", "--ext", ".png"])):
        try:
            subprocess.run([tool, *args, *map(str, paths)], check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            print(f"  ({tool} not installed — skipping that pass)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", metavar="URL", help="a running dashboard instead of the static export")
    ap.add_argument("--run", default="run_full", help="visible name of the run row to open")
    ap.add_argument("--fixed-height", action="store_true", help="strict 1080 crop, no growing")
    ap.add_argument("--out", type=Path, default=OUT, help=f"output dir (default {OUT})")
    ap.add_argument("--prefix", default=PREFIX, help=f"filename prefix (default {PREFIX!r})")
    ap.add_argument("--only", help="comma-separated tab slugs to capture (default: all)")
    # Palettizing is right for docs and WRONG for video: pngquant's 256-colour table
    # dithers the dark gradients, and that noise reads as speckle once the frame is
    # scaled into a 1080p film. Video captures must stay 24-bit.
    ap.add_argument("--no-optimize", action="store_true",
                    help="skip pngquant/oxipng — keep true-colour PNGs (use for video)")
    a = ap.parse_args()

    httpd = None
    if a.live:
        url = a.live
    else:
        if not (STATIC / "index.html").is_file():
            print(f"!! {STATIC}/index.html not found", file=sys.stderr)
            return 1
        port, httpd = serve(STATIC)
        url = f"http://127.0.0.1:{port}/index.html"
    print(f"shooting {url}")
    try:
        only = {slug(x) for x in a.only.split(",")} if a.only else None
        written = shoot(url, a.run, a.fixed_height, a.out, a.prefix, only)
    finally:
        if httpd:
            with contextlib.suppress(Exception):
                httpd.shutdown()
    if not a.no_optimize:
        optimize(written)
    total = sum(p.stat().st_size for p in written)
    print(f"wrote {len(written)} PNGs, {total / 1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
