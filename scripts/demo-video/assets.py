#!/usr/bin/env python3
"""Render every card, lower-third, logo frame and voiceover line for the demo video.

Reads `script.py` (the single source of truth) and writes into /tmp/video:

    cards/<id>.png        one still per card shot
    logo/%04d.jpg         the animated opener, a real frame sequence
    lower/<id>.png        transparent caption bands for the footage shots
    vo/<id>.m4a           narration per shot (macOS `say`, then ffmpeg)
    logos/{ibm,redhat}.png  the two SVGs rasterised once, from site/assets/
    shots.json            id, kind, final duration, vo path — what build.sh reads
    captions.srt          sidecar transcript, timed to the final durations

Run with the throwaway venv's python — NEVER the repo's .venv:

    python3 -m venv /tmp/vidvenv && /tmp/vidvenv/bin/pip install Pillow playwright
    /tmp/vidvenv/bin/python scripts/demo-video/assets.py
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import script as S  # noqa: E402

OUT = Path("/tmp/video")
REPO = Path(__file__).resolve().parents[2]
W, H = S.W, S.H
MARGIN = 170
VOICE, RATE = "Samantha", 168      # calmest / clearest of the stock macOS voices

for sub in ("cards", "logo", "lower", "vo", "logos"):
    (OUT / sub).mkdir(parents=True, exist_ok=True)


# ── type ───────────────────────────────────────────────────────────────────
_fc: dict = {}


def sans(size: int, weight: str = "Regular") -> ImageFont.FreeTypeFont:
    """SF Pro. It is a variable font, so weights come from named instances."""
    key = ("s", size, weight)
    if key not in _fc:
        f = ImageFont.truetype(S.SANS, size)
        try:
            f.set_variation_by_name(weight)
        except Exception:                     # non-variable fallback build
            pass
        _fc[key] = f
    return _fc[key]


def mono(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    key = ("m", size, bold)
    if key not in _fc:
        _fc[key] = ImageFont.truetype(S.MONO, size, index=1 if bold else 0)
    return _fc[key]


# ── chrome ─────────────────────────────────────────────────────────────────
def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """Flat background on purpose. A dot grid or gradient here looks like depth
    to the eye and like high-frequency noise to x264 — it cost ~2 MB per card
    shot for detail nobody can see at YouTube/README scale."""
    img = Image.new("RGB", (W, H), S.BG)
    return img, ImageDraw.Draw(img)


def eyebrow(d, text: str, accent=S.PURPLE) -> None:
    """Small tracked-out label + accent tick, top-left. Present on every card."""
    d.rectangle([MARGIN, 158, MARGIN + 6, 200], fill=accent)
    d.text((MARGIN + 30, 158), " ".join(text), font=sans(30, "Semibold"), fill=accent)


def head(d, text: str, y: int = 232, size: int = 108, fill=S.INK) -> int:
    f = sans(size, "Bold")
    for i, ln in enumerate(text.split("\n")):
        d.text((MARGIN, y + i * int(size * 1.14)), ln, font=f, fill=fill)
    return y + len(text.split("\n")) * int(size * 1.14)


# NOTE: there is deliberately no footer() helper any more. Every card from the
# third shot on used to carry a dimmed grey provenance line pinned to the bottom
# edge; it is gone by request. Attribution did not go with it — it lives in each
# shot's `src_note` in script.py, which STORYBOARD.md mirrors.


def panel(d, box, fill=S.PANEL, outline=S.LINE, r: int = 22) -> None:
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=2)


def ctr(d, y, text, f, fill) -> None:
    d.text(((W - d.textlength(text, font=f)) / 2, y), text, font=f, fill=fill)


# ── the capybara logo, masked out of its white background ─────────────────
def logo_disc(size: int) -> Image.Image:
    """Crop the logo to its circular artwork and return it as RGBA."""
    src = Image.open(REPO / "docs/assets/cap-evolve-logo.png").convert("RGB")
    # The art is a dark disc on white; the non-white bbox is the disc.
    bg = Image.new("RGB", src.size, (255, 255, 255))
    from PIL import ImageChops
    box = ImageChops.difference(src, bg).convert("L").point(lambda v: 255 if v > 18 else 0).getbbox()
    side = max(box[2] - box[0], box[3] - box[1])
    cx, cy = (box[0] + box[2]) // 2, (box[1] + box[3]) // 2
    disc = src.crop((cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2))
    disc = disc.resize((size, size), Image.LANCZOS).convert("RGBA")
    mask = Image.new("L", (size * 4, size * 4), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size * 4 - 1, size * 4 - 1], fill=255)
    disc.putalpha(mask.resize((size, size), Image.LANCZOS))
    return disc


#: Brand colours, read out of the repo's own SVGs (site/assets/*-logo.svg).
LOGO_FILL = {"ibm": "#1f70c1", "redhat": "#ee0000"}


def _viewbox(svg: str) -> tuple[float, float]:
    """The SVG's intrinsic w/h from its viewBox, so the page can match its shape."""
    import re
    m = re.search(r'viewBox\s*=\s*["\']\s*[\d.eE+-]+[ ,]+[\d.eE+-]+[ ,]+'
                  r'([\d.eE+-]+)[ ,]+([\d.eE+-]+)', svg)
    if m:
        return float(m.group(1)), float(m.group(2))
    return 1.0, 1.0                     # square fallback; still never clips


def rasterize_logos() -> None:
    """IBM + Red Hat SVGs → transparent PNGs, in their own brand colours.

    Two things were wrong before and both are fixed here:

    * the marks were force-filled ``#e6edf3``, i.e. monochrome white;
    * the page was a fixed 1200x400 flex box while the ``<svg>`` was sized
      ``width:900px;height:auto``. The Red Hat mark is a 24x24 viewBox, so it
      laid out 900px tall inside a 400px viewport, overflowed centred, and the
      element screenshot lost the top of the hat. Now the viewport is DERIVED
      from the viewBox (plus a small pad), so the box always contains the art.
    """
    want = {"ibm": "ibm-logo.svg", "redhat": "redhat-logo.svg"}
    if all((OUT / "logos" / f"{k}.png").exists() for k in want):
        return
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("!! playwright missing — credits card will omit the IBM/Red Hat logos")
        return
    with sync_playwright() as p:
        b = p.chromium.launch()
        for key, name in want.items():
            svg = (REPO / "site/assets" / name).read_text()
            vw, vh = _viewbox(svg)
            box_w = 900
            box_h = max(1, round(box_w * vh / vw))
            pad = 12                     # headroom, so no stroke sits on the edge
            col = LOGO_FILL[key]
            pg = b.new_page(viewport={"width": box_w + 2 * pad,
                                      "height": box_h + 2 * pad},
                            device_scale_factor=3)
            pg.set_content(
                f"<body style='margin:0;padding:{pad}px;background:transparent'>"
                f"<div id=w style='width:{box_w}px;height:{box_h}px'>{svg}</div>"
                "<style>#w svg{display:block;width:100%;height:100%}"
                f"#w svg *{{fill:{col}!important;stroke:none!important}}</style></body>")
            pg.locator("#w").screenshot(path=str(OUT / "logos" / f"{key}.png"),
                                        omit_background=True)
            pg.close()
        b.close()
    print("   rasterised IBM + Red Hat marks from site/assets/*.svg, in brand colour")


def _trim_alpha(im: Image.Image) -> Image.Image:
    """Crop to the mark's own ink. Both viewBoxes carry slack (the Red Hat 24x24
    box is ~25% empty vertically); trimming first is what lets the two marks be
    normalised on a real cap height instead of on their padding."""
    box = im.getchannel("A").getbbox()
    return im.crop(box) if box else im


# ── card renderers ─────────────────────────────────────────────────────────
def draw_logo(d, img, c) -> None:
    disc = logo_disc(430)
    img.paste(disc, ((W - 430) // 2, 300), disc)
    ctr(d, 790, c["wordmark"], sans(150, "Bold"), S.INK)
    ctr(d, 985, c["tagline"], sans(56, "Medium"), S.PURPLE)
    d.rectangle([(W - 460) / 2, 1075, (W + 460) / 2, 1080], fill=S.PURPLE)
    ctr(d, 1120, c["sub"], sans(40), S.DIM)


def draw_statement(d, img, c) -> None:
    eyebrow(d, c["eyebrow"], c["accent"])
    y = head(d, c["head"], 300, 132)
    y += 110
    for txt, col in c["lines"]:
        d.rectangle([MARGIN, y + 30, MARGIN + 26, y + 35], fill=S.LINE)
        d.text((MARGIN + 62, y), txt, font=sans(58), fill=col)
        y += 104
    d.text((MARGIN, y + 90), c["foot"], font=sans(54, "Medium"), fill=c["accent"])


def draw_tiles(d, img, c) -> None:
    eyebrow(d, c["eyebrow"], S.CYAN)
    head(d, c["head"], 250, 108)
    gap, n = 34, len(c["tiles"])
    tw = (W - 2 * MARGIN - gap * (n - 1)) // n
    # +40 on the tile block and +80 on the closing line: with the grey footer gone
    # the freed ~170px at the bottom is redistributed instead of left as a hole.
    for i, (name, sub, col) in enumerate(c["tiles"]):
        x = MARGIN + i * (tw + gap)
        panel(d, [x, 550, x + tw, 1050])
        d.rectangle([x, 550, x + tw, 559], fill=col)
        d.text((x + 42, 630), name, font=sans(54, "Bold"), fill=col)
        # wrap the sub-label to the tile
        words, ln, yy = sub.split(), "", 740
        for wd in words:
            t = (ln + " " + wd).strip()
            if d.textlength(t, font=sans(38)) > tw - 84:
                d.text((x + 42, yy), ln, font=sans(38), fill=S.DIM)
                ln, yy = wd, yy + 54
            else:
                ln = t
        d.text((x + 42, yy), ln, font=sans(38), fill=S.DIM)
    d.text((MARGIN, 1190), c["foot"], font=sans(56, "Medium"), fill=S.INK)


DIFF_COL = {"add": S.GREEN, "del": S.RED, "hunk": S.MUTED, "ctx": S.DIM}


def draw_diff(d, img, c) -> None:
    eyebrow(d, c["eyebrow"], S.PURPLE)
    head(d, c["head"], 226, 88)
    f = mono(29)
    for side, (label, rows) in (("l", c["left"]), ("r", c["right"])):
        x = MARGIN if side == "l" else W // 2 + 26
        wid = W // 2 - MARGIN - 26
        panel(d, [x, 420, x + wid, 1130])
        d.text((x + 34, 450), label, font=mono(34, True), fill=S.INK)
        d.line([x + 34, 505, x + wid - 34, 505], fill=S.LINE, width=2)
        y = 534
        for kind, ln in rows:
            col = DIFF_COL[kind]
            if kind == "add":
                d.rectangle([x + 20, y - 4, x + wid - 20, y + 38], fill=(17, 40, 30))
            elif kind == "del":
                d.rectangle([x + 20, y - 4, x + wid - 20, y + 38], fill=(46, 20, 27))
            d.text((x + 34, y), ln[:78], font=f, fill=col)
            y += 44
    d.text((MARGIN, 1180), c["result"], font=sans(42, "Medium"), fill=S.INK)
    d.text((MARGIN, 1250), c["evidence"], font=mono(38, True), fill=S.GREEN)


def draw_rows(d, img, c) -> None:
    eyebrow(d, c["eyebrow"], S.GREEN)
    head(d, c["head"], 232, 104)
    # 510/118 rather than 470/108: the six rows now use the room the grey footer
    # used to occupy, so the block stays optically centred.
    y = 524
    kw = max(d.textlength(k, font=sans(44)) for k, _, _, _ in c["rows"])
    for k, v, note, col in c["rows"]:
        d.rectangle([MARGIN, y + 16, MARGIN + 10, y + 52], fill=col)
        d.text((MARGIN + 36, y), k, font=sans(44), fill=S.DIM)
        d.text((MARGIN + 36 + kw + 60, y), v, font=mono(46, True), fill=col)
        d.text((W - MARGIN - d.textlength(note, font=sans(34)), y + 10), note,
               font=sans(34), fill=S.MUTED)
        y += 124


def draw_results(d, img, c) -> None:
    eyebrow(d, c["eyebrow"], S.GREEN)
    head(d, c["head"], 226, 104)
    x0, span = 1310, 540
    d.text((x0 + span - d.textlength("reward × 100", font=sans(30)), 424),
           "reward × 100", font=sans(30), fill=S.MUTED)
    y = 500
    for name, split, a, b, gain, col in c["rows"]:
        d.text((MARGIN, y), name, font=sans(48, "Medium"), fill=S.INK)
        d.text((MARGIN, y + 62), split, font=sans(33), fill=S.MUTED)
        # the bar: hollow baseline dot → filled optimized dot, shared 0..100 scale.
        # Baseline label sits BELOW the axis and optimized ABOVE, so the two never
        # collide when a gain is small (SkillsBench 55.6 → 66.7).
        av, bv = float(a), float(b)
        ax, bx = x0 + span * av / 100, x0 + span * bv / 100
        d.line([x0, y + 44, x0 + span, y + 44], fill=S.LINE, width=3)
        d.line([ax, y + 44, bx, y + 44], fill=col, width=9)
        d.ellipse([ax - 12, y + 32, ax + 12, y + 56], fill=S.BG, outline=S.DIM, width=4)
        d.ellipse([bx - 13, y + 31, bx + 13, y + 57], fill=col)
        d.text((ax - d.textlength(a, font=mono(33)) / 2, y + 68), a,
               font=mono(33), fill=S.DIM)
        d.text((bx - d.textlength(b, font=mono(38, True)) / 2, y - 8), b,
               font=mono(38, True), fill=col)
        d.text((x0 + span + 96, y + 24), gain, font=mono(40, True), fill=col)
        y += 155


def draw_start(d, img, c) -> None:
    eyebrow(d, c["eyebrow"], S.PURPLE)
    head(d, c["head"], 236, 116)
    panel(d, [MARGIN, 540, W - MARGIN, 990], fill=(9, 11, 19))
    y = 586
    for cmd in c["cmds"]:
        d.text((MARGIN + 46, y), "$", font=mono(46, True), fill=S.PURPLE)
        d.text((MARGIN + 110, y), cmd, font=mono(46), fill=S.INK)
        y += 82
    d.text((MARGIN + 46, y + 24), c["out"], font=mono(40, True), fill=S.GREEN)
    ctr(d, 1090, c["url"], mono(48, True), S.CYAN)


def draw_credits(d, img, c) -> None:
    disc = logo_disc(240)
    img.paste(disc, ((W - 240) // 2, 250), disc)
    ctr(d, 546, c["wordmark"], sans(104, "Bold"), S.INK)
    ctr(d, 720, c["affil"], sans(40, "Medium"), S.DIM)
    marks = [OUT / "logos" / "ibm.png", OUT / "logos" / "redhat.png"]
    if all(m.exists() for m in marks):
        # Normalise on the marks' own INK height, not on the raster's height: the
        # IBM mark is a wide 8-bar wordmark and the Red Hat mark is a near-square
        # glyph inside a loose 24x24 viewBox, so matching raster heights makes the
        # hat look small and matching widths makes it tower. Trim, then match ink.
        cap, row_y = 132, 880
        imgs = [_trim_alpha(Image.open(m).convert("RGBA")) for m in marks]
        imgs = [im.resize((max(1, round(im.width * cap / im.height)), cap),
                          Image.LANCZOS) for im in imgs]
        gap = 170
        x = (W - (sum(i.width for i in imgs) + gap)) // 2
        for im in imgs:
            img.paste(im, (x, row_y - im.height // 2), im)
            x += im.width + gap
    d.rectangle([(W - 360) / 2, 1046, (W + 360) / 2, 1051], fill=S.PURPLE)
    ctr(d, 1120, c["url"], mono(46, True), S.CYAN)


DRAW = {k[5:]: v for k, v in list(globals().items()) if k.startswith("draw_")}


# ── logo opener: a real frame sequence ────────────────────────────────────
def render_logo_frames(dur: float) -> None:
    """Disc scales up + fades in, then the wordmark rises. 25 fps, JPEG."""
    n = int(dur * S.FPS)
    disc_full = logo_disc(430)
    c = S.BY_ID["logo"]["data"]
    for i in range(n):
        t = i / S.FPS
        img, d = canvas()
        # disc: 0.0-1.3s ease-out scale 0.80→1.0 with alpha ramp
        p = min(1.0, t / 1.3)
        e = 1 - (1 - p) ** 3
        sz = int(430 * (0.80 + 0.20 * e))
        dsc = disc_full.resize((sz, sz), Image.LANCZOS)
        a = dsc.getchannel("A").point(lambda v, e=e: int(v * e))
        dsc.putalpha(a)
        img.paste(dsc, ((W - sz) // 2, 300 + (430 - sz) // 2), dsc)
        # wordmark from 0.9s, rising 26px
        q = max(0.0, min(1.0, (t - 0.9) / 0.9))
        if q > 0:
            eq = 1 - (1 - q) ** 3
            lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ld = ImageDraw.Draw(lay)
            off = int(26 * (1 - eq))
            f = sans(150, "Bold")
            ld.text(((W - ld.textlength(c["wordmark"], font=f)) / 2, 790 + off),
                    c["wordmark"], font=f, fill=S.INK + (int(255 * eq),))
            if t > 1.5:
                r = min(1.0, (t - 1.5) / 0.8)
                f2 = sans(56, "Medium")
                ld.text(((W - ld.textlength(c["tagline"], font=f2)) / 2, 985),
                        c["tagline"], font=f2, fill=S.PURPLE + (int(255 * r),))
                bw = int(460 * r)
                ld.rectangle([(W - bw) / 2, 1075, (W + bw) / 2, 1080],
                             fill=S.PURPLE + (255,))
                if t > 2.1:
                    s = min(1.0, (t - 2.1) / 0.8)
                    f3 = sans(40)
                    ld.text(((W - ld.textlength(c["sub"], font=f3)) / 2, 1120),
                            c["sub"], font=f3, fill=S.DIM + (int(255 * s),))
            img = Image.alpha_composite(img.convert("RGBA"), lay).convert("RGB")
        img.save(OUT / "logo" / f"{i:04d}.jpg", quality=94)
    print(f"   logo: {n} frames")


# ── footage stand-in warning ──────────────────────────────────────────────
# There are no burned-in lower-thirds any more: both footage shots are shown
# clean, and each one's own on-screen output carries its labelling (the CLI's
# "makes no benchmark claim" banner; the dashboard's own verdict tiles). The
# ANIMATIC stand-in stamp survives as a small corner badge, because a
# placeholder segment still must not be mistakable for the final cut.
def render_lower(shot: dict) -> None:
    blocked = S.FOOTAGE[shot["src"]]["blocked_on"]
    dst = OUT / "lower" / f"{shot['id']}.png"
    if not (bool(os.environ.get("ANIMATIC")) and blocked):
        dst.unlink(missing_ok=True)
        return
    txt = f"STAND-IN FOOTAGE — NOT FINAL  ·  blocked on {blocked}"
    f = mono(33, True)
    img = Image.new("RGBA", (W, 96), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = d.textlength(txt, font=f) + 80
    d.rounded_rectangle([MARGIN - 40, 16, MARGIN - 40 + w, 80], radius=14,
                        fill=(11, 13, 23, 235), outline=S.RED + (255,), width=3)
    d.text((MARGIN, 30), txt, font=f, fill=S.RED + (255,))
    img.save(dst)


# ── voiceover ─────────────────────────────────────────────────────────────
def dur_of(p: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration", "-of", "csv=p=0", str(p)],
                         capture_output=True, text=True).stdout.strip()
    return float(out) if out else 0.0


def render_vo(shot: dict) -> tuple[str | None, float]:
    if not shot["vo"]:
        return None, 0.0
    aiff, m4a = OUT / "vo" / f"{shot['id']}.aiff", OUT / "vo" / f"{shot['id']}.m4a"
    subprocess.run(["say", "-v", VOICE, "-r", str(RATE), "-o", str(aiff),
                    shot["vo"]], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(aiff), "-ac", "1",
                    "-ar", "48000", "-c:a", "aac", "-b:a", "96k",
                    str(m4a), "-y"], check=True)
    aiff.unlink()
    return str(m4a), dur_of(m4a)


def srt_ts(t: float) -> str:
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}".replace(".", ",")


#: Max characters per cue — two lines of ~42, the usual subtitle ceiling. One cue
#: per SHOT is far too coarse: the terminal shot's narration is 213 characters
#: held for 13 s, which nobody can read. Cues are what a muted viewer relies on,
#: so they get split even though the voiceover itself is one file per shot.
SRT_MAX_CHARS = 84


def _split_text(text: str, limit: int = SRT_MAX_CHARS) -> list[str]:
    """Break narration into cue-sized chunks, preferring sentence boundaries.

    Falls back to clause boundaries, then to words, so a chunk is only ever
    over-long if a single word is.
    """
    def pack(units: list[str]) -> list[str]:
        out: list[str] = []
        for u in units:
            if out and len(out[-1]) + 1 + len(u) <= limit:
                out[-1] = f"{out[-1]} {u}"
            else:
                out.append(u)
        return out

    # sentences first (keep the terminator with its sentence)
    sentences = re.findall(r"[^.!?]+[.!?]*\s*", text.strip()) or [text.strip()]
    chunks = pack([s.strip() for s in sentences if s.strip()])

    # any chunk still too long: re-split it on clause marks, then on words
    out: list[str] = []
    for c in chunks:
        if len(c) <= limit:
            out.append(c)
            continue
        clauses = re.findall(r"[^,:;—]+[,:;—]*\s*", c) or [c]
        for piece in pack([x.strip() for x in clauses if x.strip()]):
            if len(piece) <= limit:
                out.append(piece)
            else:
                out.extend(textwrap.wrap(piece, limit, break_long_words=False,
                                         break_on_hyphens=False) or [piece])
    return out


def cues(text: str, start: float, vo_dur: float) -> list[tuple[float, float, str]]:
    """Time each chunk proportionally to its length — speech rate is ~constant.

    Never emits a cue shorter than 0.9 s, and never runs past the narration.
    """
    parts = _split_text(text)
    total = sum(len(p) for p in parts) or 1
    span = max(1.2, vo_dur)
    out, t = [], start
    for i, p in enumerate(parts):
        d = span * len(p) / total
        end = start + span if i == len(parts) - 1 else t + d
        out.append((t, max(t + 0.9, end) if len(parts) == 1 else end, p))
        t = end
    return out


# ── main ──────────────────────────────────────────────────────────────────
def main() -> int:
    if shutil.which("say") is None:
        print("!! `say` not found — voiceover cannot be built on this platform")
        return 1
    rasterize_logos()

    print("1/3  voiceover")
    shots, t = [], 0.0
    for sh in S.SHOTS:
        vo, vd = render_vo(sh)
        dur = round(max(sh["min_dur"], vd + S.PAD_AFTER_VO), 2)
        shots.append(dict(id=sh["id"], kind=sh["kind"], dur=dur, vo=vo,
                          vo_dur=round(vd, 2), start=round(t, 2),
                          src=sh.get("src"), text=sh["vo"]))
        t += dur
        print(f"   {sh['id']:<10} vo {vd:5.2f}s  →  shot {dur:5.2f}s")

    print("2/3  cards")
    dur_by_id = {s["id"]: s["dur"] for s in shots}
    for stale in (OUT / "cards").glob("*.png"):
        stale.unlink()          # never let a renamed shot leave a card behind
    for sh in S.SHOTS:
        if sh["kind"] == "footage":
            render_lower(sh)
            continue
        if sh["id"] == "logo":
            render_logo_frames(dur_by_id["logo"])
        img, d = canvas()
        DRAW[sh["draw"]](d, img, sh["data"])
        img.save(OUT / "cards" / f"{sh['id']}.png")
    print("   cards:", *sorted(p.name for p in (OUT / "cards").glob("*.png")))

    print("3/3  manifest + captions")
    (OUT / "shots.json").write_text(json.dumps(
        dict(w=W, h=H, fps=S.FPS, total=round(t, 2), shots=shots,
             footage=S.FOOTAGE), indent=1))
    srt, n = [], 0
    for s in shots:
        if not s["text"]:
            continue
        for a, b, txt in cues(s["text"], s["start"] + 0.15, s["vo_dur"]):
            n += 1
            srt.append(f"{n}\n{srt_ts(a)} --> {srt_ts(b)}\n{txt}\n")
    (OUT / "captions.srt").write_text("\n".join(srt))
    longest = max((len(c.splitlines()[2]) for c in srt), default=0)
    print(f"   captions: {n} cues, longest {longest} chars")
    assert longest <= SRT_MAX_CHARS + 20, f"cue of {longest} chars is unreadable"

    # The music bed is generated to the exact runtime, so build.sh never has to
    # loop or hard-trim it and the closing fade always lands on the last frame.
    import music
    music.render(Path(S.MUSIC_WAV), t)

    print(f"   total runtime {t:.2f}s over {len(shots)} shots")
    if t > 90:
        print(f"!! {t:.1f}s exceeds the 90s budget — tighten a vo line in script.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
