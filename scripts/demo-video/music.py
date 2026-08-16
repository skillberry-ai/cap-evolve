#!/usr/bin/env python3
"""Generate the demo video's background music bed. Nothing is downloaded.

The bed is synthesised here, from the chord table below, with the standard
library's `wave` module and `math` — no numpy, no sample packs, no licensed
audio. That matters for two reasons: there is no third party to attribute or
clear, and the build stays reproducible (same table in, same wav out, bit for
bit).

Sound design, deliberately boring so it cannot fight the narration:

* soft additive pads — sine fundamental plus a quiet 2nd and 3rd harmonic, no
  noise, no percussion, nothing transient;
* one chord every `BAR` seconds, cross-faded, so the only movement is harmonic;
* a slow ~0.12 Hz tremolo, a few percent deep, to keep it from sounding frozen;
* everything below the voice's presence range, and mixed by build.sh at
  `script.MUSIC_DB` (-20 dB) under the voiceover.

    /tmp/vidvenv/bin/python scripts/demo-video/music.py [seconds] [out.wav]
"""
from __future__ import annotations

import math
import struct
import sys
import wave
from pathlib import Path

SR = 48_000
BAR = 8.0                  # seconds per chord
PEAK = 0.34                # pre-mix headroom; build.sh applies the -20 dB duck

# A slow i–VI–III–VII in A minor: unresolved, no strong cadence, so no bar
# lands like a "the end" while the narration is still going.
CHORDS: list[tuple[float, ...]] = [
    (110.00, 164.81, 220.00, 329.63),      # Am    A2 E3 A3 E4
    (87.31, 174.61, 220.00, 261.63),       # F     F2 F3 A3 C4
    (98.00, 146.83, 196.00, 293.66),       # G/C   G2 D3 G3 D4
    (82.41, 164.81, 246.94, 329.63),       # Em    E2 E3 B3 E4
]
# Relative levels of fundamental / 2nd / 3rd harmonic: a rounded, flute-ish pad.
HARMONICS = ((1.0, 1.0), (2.0, 0.16), (3.0, 0.06))


def _chord_at(t: float) -> tuple[tuple[float, ...], tuple[float, ...], float]:
    """The two chords straddling time `t` and the crossfade weight between them."""
    i = int(t // BAR)
    frac = (t - i * BAR) / BAR
    a = CHORDS[i % len(CHORDS)]
    b = CHORDS[(i + 1) % len(CHORDS)]
    # Cross-fade over the last 35% of the bar only: mostly one chord at a time.
    x = 0.0 if frac < 0.65 else (frac - 0.65) / 0.35
    return a, b, 0.5 - 0.5 * math.cos(math.pi * x)      # raised-cosine


def _voice(freq: float, t: float) -> float:
    """One pad voice: fundamental + two quiet harmonics, slightly detuned."""
    s = 0.0
    for mult, amp in HARMONICS:
        f = freq * mult * (1.0 + 0.0006 * mult)          # gentle inharmonicity
        s += amp * math.sin(2 * math.pi * f * t)
    return s / sum(a for _, a in HARMONICS)


def samples(dur: float):
    """Yield float samples in [-1, 1] for `dur` seconds."""
    n = int(dur * SR)
    for k in range(n):
        t = k / SR
        a, b, w = _chord_at(t)
        v = sum(_voice(f, t) for f in a) * (1 - w) + sum(_voice(f, t) for f in b) * w
        v /= len(a)
        trem = 1.0 - 0.05 + 0.05 * math.sin(2 * math.pi * 0.12 * t)
        yield PEAK * v * trem


def render(out: Path, dur: float) -> Path:
    """Write `dur` seconds of bed to `out` as 16-bit mono PCM.

    Cached on exact frame count: pure-python synthesis of the whole runtime takes
    ~30 s, and a rebuild that did not change the timeline does not need it again.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    want = int(dur * SR)
    if out.exists():
        try:
            with wave.open(str(out)) as w:
                if (w.getnframes(), w.getframerate()) == (want, SR):
                    print(f"   music: {dur:.2f}s bed cached → {out}")
                    return out
        except (wave.Error, EOFError):
            pass                        # truncated/garbage cache: just re-render
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(
            struct.pack("<h", max(-32768, min(32767, int(v * 32767))))
            for v in samples(want / SR)))
    print(f"   music: {dur:.2f}s pad bed → {out}")
    return out


def _selfcheck() -> None:
    """The one runnable check: the bed must be the right length, audible, and
    never clip. A silent or clipped bed is the only way this file can fail in a
    way the video would not obviously show."""
    vals = list(samples(BAR * len(CHORDS) + 1.0))
    assert len(vals) == int((BAR * len(CHORDS) + 1.0) * SR), "wrong sample count"
    assert max(abs(v) for v in vals) <= 1.0, "bed clips"
    assert max(abs(v) for v in vals) > 0.05, "bed is effectively silent"
    # Every chord change must actually change the signal, else the table is dead.
    a = sum(abs(v) for v in vals[:SR]) / SR
    b = sum(abs(v) for v in vals[int(BAR * SR):int((BAR + 1) * SR)]) / SR
    assert abs(a - b) > 1e-4, "chords 1 and 2 are indistinguishable"
    print("music selfcheck ok")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        _selfcheck()
    else:
        dur = float(sys.argv[1]) if len(sys.argv) > 1 else 90.0
        render(Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/video/music.wav"), dur)
