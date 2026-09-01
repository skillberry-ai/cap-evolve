#!/usr/bin/env python3
"""Generate high-naturalness TTS speech with Kokoro (neural, offline).

Use this whenever the output speech is judged for naturalness / quality
(e.g. a UTMOS or MOS gate) and the task runs offline. Kokoro is a local
neural model and consistently scores far higher on naturalness meters than
formant engines (espeak-ng, pyttsx3) or unreachable cloud engines
(edge-tts, gTTS, OpenAI) — do NOT hand-roll those when quality is graded.

Generates at the model's native rate (24000 Hz) at natural speed
(speed=1); resample / master / time-fit afterward with ffmpeg. Generating
at natural speed and avoiding heavy time-stretch preserves naturalness.

Usage:
    python kokoro_tts.py --text "こんにちは" --lang ja --out /tmp/tts_raw.wav
    python kokoro_tts.py --text-file target.txt --lang ja --out /tmp/tts_raw.wav

--lang takes an ISO code (ja, en, zh, fr, es, hi, it, pt); it is mapped to
Kokoro's single-letter lang_code and a default voice below. Override the
voice with --voice. Prints the output path and native sample rate as JSON.
"""
import argparse
import json
import sys

import numpy as np
import soundfile as sf
from kokoro import KPipeline

# ISO language code -> Kokoro lang_code (single letter)
LANG_CODE = {
    "ja": "j", "en": "a", "en-gb": "b", "zh": "z",
    "fr": "f", "es": "e", "hi": "h", "it": "i", "pt": "p",
}
# ISO language code -> a good default Kokoro voice for that language
VOICE = {
    "ja": "jm_kumo", "en": "am_michael", "en-gb": "bm_george",
    "zh": "zm_yunjian", "fr": "ff_siwis", "es": "em_alex",
    "hi": "hm_omega", "it": "im_nicola", "pt": "pm_alex",
}
NATIVE_SR = 24000  # Kokoro native sample rate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default=None)
    ap.add_argument("--text-file", default=None)
    ap.add_argument("--lang", required=True, help="ISO code, e.g. ja / en / zh")
    ap.add_argument("--voice", default=None, help="override default Kokoro voice")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if args.text_file:
        with open(args.text_file, "r", encoding="utf-8") as f:
            text = f.read().strip()
    elif args.text is not None:
        text = args.text.strip()
    else:
        sys.exit("provide --text or --text-file")
    if not text:
        sys.exit("empty text")

    lang = args.lang.strip().lower()
    lang_code = LANG_CODE.get(lang, "a")
    voice = args.voice or VOICE.get(lang, "af_bella")

    pipeline = KPipeline(lang_code=lang_code)
    generator = pipeline(text, voice=voice, speed=args.speed)
    audio = np.concatenate([chunk for _, _, chunk in generator])
    sf.write(args.out, audio, NATIVE_SR)

    print(json.dumps({
        "out": args.out,
        "sample_rate_hz": NATIVE_SR,
        "voice": voice,
        "lang_code": lang_code,
        "num_samples": int(audio.shape[0]),
        "duration_sec": round(float(audio.shape[0]) / NATIVE_SR, 3),
    }))


if __name__ == "__main__":
    main()
