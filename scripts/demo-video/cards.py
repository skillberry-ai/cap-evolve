"""Render title / chapter / outro cards for the cap-evolve demo video.

Same palette and typeface as the recorded terminal segments, so the composited
video reads as one piece rather than a screencast with slides bolted on.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 2560, 1340
BG = (11, 13, 23)
FG = (230, 237, 243)
DIM = (107, 114, 128)
PURPLE = (124, 92, 255)
CYAN = (34, 211, 238)
GREEN = (74, 222, 128)
YELLOW = (251, 191, 36)

MONO = "/System/Library/Fonts/Menlo.ttc"
OUT = Path("/tmp/video/cards")
OUT.mkdir(parents=True, exist_ok=True)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    # Menlo.ttc: index 0 Regular, 1 Bold.
    return ImageFont.truetype(MONO, size, index=1 if bold else 0)


def base() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # Dot grid, very low contrast — gives the flat background some depth.
    for y in range(60, H, 64):
        for x in range(60, W, 64):
            d.point((x, y), fill=(26, 30, 48))
    return img, d


def centered(d, y, text, f, fill):
    w = d.textlength(text, font=f)
    d.text(((W - w) / 2, y), text, font=f, fill=fill)
    return w


def title_card(path: str) -> None:
    img, d = base()
    centered(d, 470, "cap-evolve", font(190, True), FG)
    centered(d, 700, "watch capability evolve", font(58), PURPLE)
    centered(d, 830, "optimize an agent's prompts, tools and skills from its own failures",
             font(40), DIM)
    bw = 520
    d.rectangle([(W - bw) / 2, 950, (W + bw) / 2, 956], fill=PURPLE)
    centered(d, 1010, "zero runtime dependencies  ·  stdlib only", font(34), DIM)
    img.save(path)


def chapter_card(path: str, num: str, name: str, sub: str, accent) -> None:
    img, d = base()
    f_num, f_name = font(64, True), font(132, True)
    label = f"Step {num}"
    nw = d.textlength(label, font=f_num)
    tw = d.textlength(name, font=f_name)
    total = nw + 46 + tw
    x = (W - total) / 2
    d.text((x, 585), label, font=f_num, fill=DIM)
    d.text((x + nw + 46, 530), name, font=f_name, fill=accent)
    centered(d, 730, sub, font(46), FG)
    img.save(path)


def stat_card(path: str, heading: str, rows: list[tuple[str, str, tuple]], foot: str) -> None:
    img, d = base()
    centered(d, 210, heading, font(96, True), FG)
    d.rectangle([(W - 420) / 2, 350, (W + 420) / 2, 355], fill=PURPLE)
    f_k, f_v = font(52), font(52, True)
    # One shared column boundary so the values line up as a table.
    kw = max(d.textlength(k, font=f_k) for k, _, _ in rows)
    x0 = (W - (kw + 80 + 620)) / 2
    y = 470
    for k, v, col in rows:
        d.text((x0, y), k, font=f_k, fill=DIM)
        d.text((x0 + kw + 80, y), v, font=f_v, fill=col)
        y += 104
    centered(d, y + 60, foot, font(36), DIM)
    img.save(path)


title_card(f"{OUT}/00_title.png")
chapter_card(f"{OUT}/01_replay.png", "1", "OPTIMIZE",
             "evaluate → diagnose → propose an edit → gate it → commit", CYAN)
chapter_card(f"{OUT}/02_parallel.png", "2", "PARALLEL",
             "the tasks x trials grid is embarrassingly parallel — now the framework uses it",
             YELLOW)
stat_card(
    f"{OUT}/03_speedup.png", "measured, same machine",
    [("workers = 1", "6.61 s", FG),
     ("workers = 4", "1.66 s   4.0x", GREEN),
     ("workers = 8", "0.84 s   7.9x", GREEN),
     ("SplitResult", "identical", CYAN)],
    "16 tasks x 2 trials — parallelism changes the wallclock, never the number",
)
stat_card(
    f"{OUT}/04_honest.png", "honest by construction",
    [("accept only if", "delta > k · SE", GREEN),
     ("gate split", "val only", CYAN),
     ("test split", "sealed, scored once", CYAN),
     ("infra error", "missing data, never 0.0", YELLOW),
     ("tampered candidate", "discarded, not scored", YELLOW)],
    "the gate, the split and the seal live in the core — not in editable docs",
)
print("wrote:", *sorted(p.name for p in OUT.glob("*.png")))
