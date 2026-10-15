#!/usr/bin/env python3
"""rits_tps_probe.py — measure output speed (tokens/second) of RITS models.

lite-rits does not stream token by token: a streaming request gets one empty chunk after the
whole generation is done, plus the `usage` block (run 38698321564). So per-token timing is not
observable, and this script measures with non-streaming requests instead. Per trial it sends:
  * a SHORT request (max_tokens=SHORT_TOKENS)  — mostly fixed cost: network, queue, prefill
  * a LONG request  (max_tokens=MAX_TOKENS)
and reports:
  * e2e t/s    — LONG completion tokens / LONG wall time (what a caller sees)
  * decode t/s — (LONG tokens - SHORT tokens) / (LONG time - SHORT time); the fixed cost
                 cancels out, so this is the model's generation speed
  * overhead   — SHORT time minus SHORT tokens at the decode rate (approximate TTFT)
Token counts come from the server's `usage` block.

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
SHORT_TOKENS = int(os.environ.get("SHORT_TOKENS", "16"))
TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "300"))
PROMPT = (
    "Write a detailed, roughly 600-word technical explanation of how a hash table works, "
    "covering hashing, collisions, open addressing, chaining and resizing. Plain prose."
)


def url():
    return BASE + ("/chat/completions" if BASE.endswith("/v1") else "/v1/chat/completions")


def call(model, max_tokens):
    body = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }
    req = urllib.request.Request(
        url(),
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
    )
    t0 = time.monotonic()
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        out = json.load(resp)
    dt = time.monotonic() - t0
    usage = out.get("usage") or {}
    msg = ((out.get("choices") or [{}])[0]).get("message") or {}
    return {
        "s": dt,
        "tokens": int(usage.get("completion_tokens") or 0),
        "reasoning": int((usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0),
        "content_chars": len(msg.get("content") or ""),
    }


def one_trial(model):
    short = call(model, SHORT_TOKENS)
    long_ = call(model, MAX_TOKENS)
    if not long_["tokens"]:
        raise RuntimeError("no usage.completion_tokens in the response")
    dtok = long_["tokens"] - short["tokens"]
    dsec = long_["s"] - short["s"]
    decode = dtok / dsec if dtok > 0 and dsec > 0 else float("nan")
    overhead = short["s"] - short["tokens"] / decode if decode == decode else float("nan")
    return {
        "tokens": long_["tokens"],
        "reasoning": long_["reasoning"],
        "content_chars": long_["content_chars"],
        "long_s": long_["s"],
        "short_s": short["s"],
        "short_tokens": short["tokens"],
        "e2e_tps": long_["tokens"] / long_["s"],
        "decode_tps": decode,
        "overhead_s": overhead,
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
                f"  trial {i}: long {r['tokens']} tok ({r['reasoning']} reasoning, "
                f"{r['content_chars']} content chars) in {r['long_s']:.2f}s; "
                f"short {r['short_tokens']} tok in {r['short_s']:.2f}s -> "
                f"e2e {r['e2e_tps']:.1f} tok/s, decode {r['decode_tps']:.1f} tok/s, "
                f"overhead {r['overhead_s']:.2f}s",
                flush=True,
            )
        if rows:
            avg = lambda k: sum(r[k] for r in rows) / len(rows)  # noqa: E731
            summary.append((model, len(rows), avg("tokens"), avg("long_s"), avg("e2e_tps"),
                            avg("decode_tps"), avg("overhead_s")))
        else:
            summary.append((model, 0, 0, 0, 0, 0, 0))

    lines = [
        "| model | ok trials | avg tokens | avg time (s) | avg end-to-end tok/s "
        "| avg decode tok/s | avg overhead (s) |",
        "|---|---|---|---|---|---|---|",
    ]
    for m, n, tok, sec, e2e, dec, ovh in summary:
        lines.append(f"| `{m}` | {n}/{TRIALS} | {tok:.0f} | {sec:.2f} | {e2e:.1f} | {dec:.1f} | {ovh:.2f} |")
    table = "\n".join(lines)
    print("\n" + table)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a") as f:
            f.write(f"## RITS tokens/second (max_tokens={MAX_TOKENS} vs {SHORT_TOKENS}, non-streaming)\n\n{table}\n")
    return 0 if any(n for _, n, *_ in summary) else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
