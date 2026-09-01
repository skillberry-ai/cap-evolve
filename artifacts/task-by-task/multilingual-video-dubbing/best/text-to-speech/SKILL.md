---
name: text-to-speech
description: "Generate and master TTS speech for video dubbing: pick a high-naturalness engine, then clean up, loudness-normalize, and time-align each segment. Use when synthesizing speech (especially when output quality/naturalness is graded) or preparing dubbed audio to delivery specs."
---

# SKILL: TTS Audio Mastering

This skill focuses on producing clean, consistent, and delivery-ready TTS audio for video tasks. It covers engine selection, speech cleanup, loudness normalization, segment boundaries, and export specs.

## 1. TTS Engine Selection — default to a neural offline engine

Engine choice is the single biggest driver of speech **naturalness**. Many dubbing tasks grade the synthesized speech with an automatic naturalness meter (e.g. UTMOS / MOS, typically requiring a score >= 3.5). Formant and low-fidelity engines routinely fall below that bar, and cloud engines may be unreachable in an offline/sandboxed run.

**Default: neural offline (Kokoro).** It is local (no network), stable, and scores high on naturalness meters. Prefer it whenever quality/naturalness is graded or the environment may lack network. A ready generator is bundled — run it, do not reimplement:

```
python scripts/kokoro_tts.py --text-file <target_text.txt> --lang <iso_code> --out /tmp/tts_raw.wav
```

It maps the ISO language code to Kokoro's `lang_code` and a good default voice, generates at natural speed (`speed=1`) at the native **24000 Hz**, and prints the output path + sample rate. Resample/master afterward (Sections 2–4).

**Avoid these when naturalness is graded:**
* **Formant TTS** (espeak-ng, pyttsx3): robotic; typically scores well below the naturalness bar. Prototyping only.
* **Cloud TTS** (edge-tts, gTTS, OpenAI): network-dependent — fails or degrades in offline/sandboxed runs. Do not rely on network being available; if you already have a neural offline engine, use it.

**Key rule:** Always confirm the **native sample rate** of the generated audio (Kokoro = 24000 Hz) before resampling for video delivery.

---

## 2. Speech Cleanup (Per Segment)

Apply lightweight processing to avoid common artifacts:

* **Rumble/DC removal:** high-pass filter around **20 Hz**
* **Harshness control:** optional low-pass around **16 kHz** (helps remove digital fizz)
* **Click/pop prevention:** short fades at boundaries (e.g., **50 ms** fade-in and fade-out)

Recommended FFmpeg pattern (example):

* Add filters in a single chain, and keep them consistent across segments.

---

## 3. Loudness Normalization — hit **-23 LUFS**, the graded delivery target

For video-dubbing / professional-mastering delivery the integrated-loudness target is the
**EBU R128 / ITU-R BS.1770 broadcast standard**, and it is **graded**: verifiers measure the
delivered file with FFmpeg `ebur128` and require integrated loudness within a tight band.

* **Integrated loudness:** **-23 LUFS** — pass band is typically **-23 ± 1.5 LUFS** (i.e. **-24.5 .. -21.5**).
* **True peak:** around **-1.5 dBTP**
* **LRA:** around **11** (optional)

**Use -23 LUFS. Do NOT substitute a streaming/"comfort" loudness.** The most common way this
gate fails is targeting the wrong level: -14/-16 LUFS (Spotify/YouTube streaming), or a
"broadcast-comfort" level like -16/-18 LUFS. Those are louder than -23 and land the delivered
track OUTSIDE the band (e.g. a track measured at -18 LUFS fails a -23 ± 1.5 gate). Neural TTS
often already sits near -23 LUFS; do not push it up.

Workflow (normalize the **final assembled track**, as the **last audio step**, then mux):

1. **Measure** integrated loudness with `ebur128`, e.g. `ffmpeg -i in.wav -af ebur128=peak=true -f null -` (read the last `I: <x> LUFS`).
2. **Normalize to -23 LUFS.** Either `loudnorm=I=-23:TP=-1.5:LRA=11`, or — to land exactly on
   target — apply a single **linear gain** of `(-23 - measured)` dB via the `volume` filter
   (a linear gain shifts gated integrated loudness by exactly that many dB).
3. **VERIFY the delivered file the way the grader will:** re-measure with `ebur128` and confirm
   the last `I:` is inside **-24.5 .. -21.5**. If it is outside, apply a correcting linear gain
   of `(-23 - measured)` dB and re-measure. Report this delivered-file value in `measured_lufs`.
4. If you adjust tempo/duration after normalizing, re-normalize and re-verify.

---

## 4. Timing & Segment Boundary Handling

When stitching segment-level TTS into a full track:

* Match each segment to its target window as closely as possible.
* If a segment is shorter than its window, pad with silence.
* If a segment is longer, use gentle duration control (small speed change) or truncate carefully.
* Always apply boundary fades after padding/trimming to avoid clicks.

**Naturalness caution:** large time-stretching (`atempo` far from 1.0) audibly degrades speech and lowers naturalness-meter scores. Keep the tempo factor as close to 1.0 as the window allows; when the synthesized speech already fits inside the window, prefer `pad_silence` over speeding it up, and reserve aggressive `rate_adjust` for cases where the speech genuinely overruns the window.

**Sync guideline:** keep end-to-end drift small (e.g., **<= 0.2s**) unless the task states otherwise.
