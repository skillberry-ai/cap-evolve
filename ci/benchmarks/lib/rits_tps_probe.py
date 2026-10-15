#!/usr/bin/env python3
"""rits_tps_probe.py — measure streaming output speed (tokens/second) of RITS models.

Sends a streaming chat completion through the lite-rits proxy (IBM_RITS_API_BASE /
IBM_RITS_API_KEY) and reports, per trial:
  * TTFT       — time to the first streamed token (content or reasoning)
  * decode t/s — completion tokens after the first one / time from first to last token
  * e2e t/s    — completion tokens / whole request time
Completion tokens come from the server's `usage` block when it sends one; otherwise the
script falls back to the number of streamed chunks (marked "est").

Stdlib only, so it runs on the self-hosted runner without a venv.

Usage: rits_tps_probe.py <wire-model> [<wire-model> ...]   (wire ids start with "rits/")
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.environ["IBM_RITS_API_BASE"].rstrip("/")
KEY = os.environ["IBM_RITS_API_KEY"]
TRIALS = int(os.environ.get("TRIALS", "3"))
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "512"))
TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "300"))
PROMPT = (
    "Write a detailed, roughly 600-word technical explanation of how a hash table works, "
    "covering hashing, collisions, open addressing, chaining and resizing. Plain prose."
)


def url():
    return BASE + ("/chat/completions" if BASE.endswith("/v1") else "/v1/chat/completions")


def one_trial(model):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": MAX_TOKENS,
        "temperature": 0.7,
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    req = urllib.request.Request(
        url(),
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    t0 = time.monotonic()
    t_first = t_last = None
    chunks = 0
    usage = None
    reasoning_chunks = 0
    raw_head = []  # first raw lines, printed when no token is parsed
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if line and len(raw_head) < 8:
                raw_head.append(line[:300])
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                ev = json.loads(data)
            except json.JSONDecodeError:
                continue
            if ev.get("usage"):
                usage = ev["usage"]
            for ch in ev.get("choices") or []:
                d = ch.get("delta") or {}
                text = d.get("content") or ""
                rtext = d.get("reasoning_content") or d.get("reasoning") or ""
                if text or rtext:
                    now = time.monotonic()
                    t_first = t_first or now
                    t_last = now
                    chunks += 1
                    if rtext:
                        reasoning_chunks += 1
    t_end = time.monotonic()
    if t_first is None:
        raise RuntimeError("stream returned no tokens; first lines: " + " || ".join(raw_head))
    if usage and usage.get("completion_tokens"):
        ntok, src = int(usage["completion_tokens"]), "usage"
    else:
        ntok, src = chunks, "est"
    decode_s = max(t_last - t_first, 1e-6)
    return {
        "tokens": ntok,
        "src": src,
        "ttft_s": t_first - t0,
        "decode_tps": (ntok - 1) / decode_s if ntok > 1 else 0.0,
        "e2e_tps": ntok / (t_end - t0),
        "total_s": t_end - t0,
        "chunks": chunks,
        "reasoning_chunks": reasoning_chunks,
        "prompt_tokens": (usage or {}).get("prompt_tokens"),
    }


def main(models):
    summary = []
    for model in models:
        print(f"\n=== {model} ===", flush=True)
        rows = []
        for i in range(1, TRIALS + 1):
            try:
                r = one_trial(model)
            except urllib.error.HTTPError as e:
                print(f"  trial {i}: HTTP {e.code}: {e.read()[:400]!r}", flush=True)
                break
            except Exception as e:  # noqa: BLE001 — report and move to the next model
                print(f"  trial {i}: ERROR {type(e).__name__}: {e}", flush=True)
                break
            rows.append(r)
            print(
                f"  trial {i}: {r['tokens']} tok ({r['src']}), TTFT {r['ttft_s']:.2f}s, "
                f"decode {r['decode_tps']:.1f} tok/s, e2e {r['e2e_tps']:.1f} tok/s, "
                f"total {r['total_s']:.1f}s, chunks {r['chunks']} "
                f"(reasoning {r['reasoning_chunks']})",
                flush=True,
            )
        if rows:
            avg = lambda k: sum(r[k] for r in rows) / len(rows)  # noqa: E731
            summary.append((model, len(rows), avg("tokens"), avg("ttft_s"), avg("decode_tps"), avg("e2e_tps")))
        else:
            summary.append((model, 0, 0, 0, 0, 0))

    lines = [
        "| model | ok trials | avg tokens | avg TTFT (s) | avg decode tok/s | avg end-to-end tok/s |",
        "|---|---|---|---|---|---|",
    ]
    for m, n, tok, ttft, dec, e2e in summary:
        lines.append(f"| `{m}` | {n}/{TRIALS} | {tok:.0f} | {ttft:.2f} | {dec:.1f} | {e2e:.1f} |")
    table = "\n".join(lines)
    print("\n" + table)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a") as f:
            f.write(f"## RITS tokens/second (max_tokens={MAX_TOKENS}, streaming)\n\n{table}\n")
    return 0 if any(n for _, n, *_ in summary) else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
