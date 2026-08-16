#!/usr/bin/env python3
"""Record the cap-evolve dashboard as video, with Playwright driving a real browser.

Not a screenshot slideshow and not a mockup: Chromium loads the dashboard, a
scripted pointer moves through it, and Playwright's own recorder captures the
frames — so scroll and hover are genuinely animated.

Two targets:

  --live URL  (what the shipped cut uses) the running dashboard:
             cap-evolve dashboard --base examples/tau2_airline --port 8791 --no-open
             /tmp/vidvenv/bin/python dash.py --live http://127.0.0.1:8791 \
                 --run run_agentopt_v4

  --static   (default) the committed static export under
             examples/tau2_airline/run_full/ui, served on a throwaway port.
             KNOWN DEFECT, do not ship: that export's summary carries no
             `status` or `algorithm`, so the rebuilt dashboard renders a red
             "failed" badge over a run that finished, and its Cost tab reads
             "No spend recorded" because the export has no events.jsonl. A
             false badge on screen is a worse integrity problem than any
             framing question about which run to film, hence --live above.

Output: /tmp/video/dashboard.mp4  (2560x1440, silent).
"""
from __future__ import annotations

import argparse
import contextlib
import functools
import http.server
import shutil
import socketserver
import subprocess
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STATIC = REPO / "examples/tau2_airline/run_full/ui"
OUT = Path("/tmp/video")
W, H, SECONDS = 2560, 1440, 14
ZOOM = 1.9          # page zoom, so a 1440p viewport is not a wall of tiny UI
RUN_LABEL = "run_agentopt_v4"   # the run row to open; override with --run
# (tab label, dwell ms). Gate dwells longest: on run_agentopt_v4 it is the
# credibility-bearing tab — five reject verdicts with their paired arithmetic,
# two of which cleared the significance bar and were still vetoed by the
# regression check. Cost is NOT filmed any more: that run's ledger reports
# cost.metered = false (a local runner, $0.00 across every row), so the tab is
# honest but empty, and 3.6s of zeros on camera says nothing. Tasks (per-task
# val, 12 tasks x 5 trials) carries more. Missing tabs are skipped, not fatal.
TABS = (("Candidates", 2600), ("Gate", 3400), ("Tasks", 2400))


def serve(root: Path) -> tuple[int, socketserver.TCPServer]:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(root))
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd.server_address[1], httpd


def record(url: str) -> Path:
    from playwright.sync_api import sync_playwright

    raw = OUT / "dash_raw"
    shutil.rmtree(raw, ignore_errors=True)
    raw.mkdir(parents=True)
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--force-color-profile=srgb",
                                    "--hide-scrollbars"])
        # Playwright records the page at its VIEWPORT size in CSS px and ignores
        # device_scale_factor, so a small viewport with a large record size just
        # pins the page into the top-left corner of a grey canvas. Take the full
        # 1440p viewport instead and zoom the page up, which is both crisp and
        # correctly framed.
        ctx = b.new_context(viewport={"width": W, "height": H},
                            device_scale_factor=1, color_scheme="dark",
                            record_video_dir=str(raw),
                            record_video_size={"width": W, "height": H})
        pg = ctx.new_page()
        pg.goto(url, wait_until="load")
        pg.add_style_tag(content=f":root{{zoom:{ZOOM}}}")
        pg.wait_for_timeout(1300)

        def step(label: str, ms: int) -> None:
            """Click a control by visible text; skip it if this build lacks it.

            Deliberately tolerant: the tab set is the dashboard's business, not
            the video's, so a renamed tab must degrade to a shorter shot rather
            than crash the build.
            """
            # role=tab FIRST and exact: get_by_text("Candidates") also matches the
            # "4 candidates" summary tile, which silently clicked nothing and cost
            # the shot two of its three beats.
            tab = pg.get_by_role("tab", name=label, exact=True)
            loc = tab if tab.count() else pg.get_by_text(label, exact=False).first
            try:
                loc.click(timeout=2500)
            except Exception:
                print(f"   (no '{label}' here — skipping)")
                return
            pg.wait_for_timeout(ms)

        # Into the run, then across the tabs that carry the story. The tab set is
        # now generic across algorithms — Overview, Candidates, Gate, Tasks,
        # Cost, Logs, Diffs, Trajectories, Memory, Files — so the old "Lineage" /
        # "Git diffs" labels are gone. step() skips a missing label rather than
        # failing, but keep TABS in sync or the shot silently gets shorter.
        step(RUN_LABEL, 1700)
        for tab, ms in TABS:
            step(tab, ms)
        pg.wait_for_timeout(600)
        ctx.close()
        b.close()
    vids = sorted(raw.glob("*.webm"))
    if not vids:
        raise SystemExit("!! playwright produced no video")
    return vids[0]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", metavar="URL",
                    help="record a running dashboard instead of the committed artifact")
    ap.add_argument("--run", default=RUN_LABEL,
                    help=f"visible name of the run row to open (default {RUN_LABEL})")
    a = ap.parse_args()
    globals()["RUN_LABEL"] = a.run
    OUT.mkdir(parents=True, exist_ok=True)

    httpd = None
    if a.live:
        url, label = a.live, f"live dashboard at {a.live}"
    else:
        if not (STATIC / "index.html").is_file():
            print(f"!! {STATIC}/index.html not found", file=sys.stderr)
            return 1
        port, httpd = serve(STATIC)
        url = f"http://127.0.0.1:{port}/index.html"
        label = f"committed static artifact ({STATIC.relative_to(REPO)})"
    print(f"recording: {label}")
    try:
        webm = record(url)
    finally:
        if httpd:
            with contextlib.suppress(Exception):
                httpd.shutdown()

    dst = OUT / "dashboard.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(webm),
                    "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
                           f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x0b0d17,fps=25",
                    "-c:v", "libx264", "-preset", "slow", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-an", str(dst), "-y"], check=True)
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
