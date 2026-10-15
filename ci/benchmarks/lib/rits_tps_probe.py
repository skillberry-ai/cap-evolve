#!/usr/bin/env python3
"""rits_tps_probe.py — measure output speed (tokens/second) of RITS and ETE gateway models.

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

Usage: rits_tps_probe.py <ci-model-id> [<ci-model-id> ...]
CI ids carry a provider prefix (ibm-rits/, ibm-ete/, ibm-ete-int/), mapped to the wire id
and credentials the same way resolve_provider.sh does.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

TRIALS = int(os.environ.get("TRIALS", "3"))
MAX_TOKENS = int(os.environ.get("MAX_TOKENS", "512"))
SHORT_TOKENS = int(os.environ.get("SHORT_TOKENS", "16"))
TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "300"))
RETRY_WAITS_429 = (20, 40, 60, 60)
LITELLM_HEADERS = {
    "x-litellm-attempted-retries",
    "x-litellm-cache-key",
    "x-litellm-response-duration-ms",
    "x-litellm-model-region",
}
PROMPT = (
    "Write a detailed, roughly 600-word technical explanation of how a hash table works, "
    "covering hashing, collisions, open addressing, chaining and resizing. Plain prose."
)


def resolve(ci_id):
    """CI id -> (wire model, api base, api key). Mirrors resolve_provider.sh."""
    for prefix, env, wire_prefix in (
        ("ibm-ete-int/", "IBM_ETE_INT", ""),
        ("ibm-ete/", "IBM_ETE", ""),
        # lite-rits only routes ids that keep the "rits/" wire prefix.
        ("ibm-rits/", "IBM_RITS", "rits/"),
    ):
        if ci_id.startswith(prefix):
            base = os.environ[f"{env}_API_BASE"].rstrip("/")
            return wire_prefix + ci_id[len(prefix):], base, os.environ[f"{env}_API_KEY"]
    raise SystemExit(f"{ci_id}: no provider prefix (ibm-rits/, ibm-ete/, ibm-ete-int/)")


def url(base):
    return base + ("/chat/completions" if base.endswith("/v1") else "/v1/chat/completions")


def call(ci_id, max_tokens):
    model, base, key = resolve(ci_id)
    body = {
        "model": model,
        # A unique id per request: the ETE LiteLLM gateway otherwise serves a cached answer
        # in ~0.2s (run 38699969277, trials 2-3), which is not a generation.
        "messages": [{"role": "user", "content": f"[request {uuid.uuid4()}] {PROMPT}"}],
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }
    req = urllib.request.Request(
        url(base),
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    # A 429 (e.g. Azure's tokens-per-minute limit behind ETE) is a wait, not a result: retry it
    # and time only the attempt that succeeds.
    for wait in (*RETRY_WAITS_429, None):
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                out = json.load(resp)
                # LiteLLM's own view: internal retries (hidden 429 waits), cache, server time.
                hdr = {k[len("x-litellm-"):]: v for k, v in resp.headers.items()
                       if k.lower() in LITELLM_HEADERS}
            break
        except urllib.error.HTTPError as e:
            if e.code != 429 or wait is None:
                raise
            print(f"    HTTP 429 (max_tokens={max_tokens}); retrying in {wait}s", flush=True)
            time.sleep(wait)
    dt = time.monotonic() - t0
    usage = out.get("usage") or {}
    msg = ((out.get("choices") or [{}])[0]).get("message") or {}
    return {
        "s": dt,
        "tokens": int(usage.get("completion_tokens") or 0),
        "reasoning": int((usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0),
        "content_chars": len(msg.get("content") or ""),
        # Where the text actually is: GLM can put it in reasoning_content instead of content.
        "fields": {k: len(v) if isinstance(v, str) else type(v).__name__ for k, v in msg.items()},
        "finish": ((out.get("choices") or [{}])[0]).get("finish_reason"),
        "litellm": hdr,
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
        "fields": long_["fields"],
        "finish": long_["finish"],
        "litellm": {"short": short["litellm"], "long": long_["litellm"]},
        # A gateway-side retry hides a rate-limit wait inside the timing: not a clean trial.
        "retried": any(str(c["litellm"].get("attempted-retries", "0")) not in ("0", "")
                       for c in (short, long_)),
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
            if r["retried"]:
                print(f"  trial {i}: gateway retried internally; excluded from the averages", flush=True)
            else:
                rows.append(r)
            print(
                f"  trial {i}: long {r['tokens']} tok ({r['reasoning']} reasoning, "
                f"{r['content_chars']} content chars) in {r['long_s']:.2f}s; "
                f"short {r['short_tokens']} tok in {r['short_s']:.2f}s -> "
                f"e2e {r['e2e_tps']:.1f} tok/s, decode {r['decode_tps']:.1f} tok/s, "
                f"overhead {r['overhead_s']:.2f}s; finish={r['finish']} message fields={r['fields']} litellm={r['litellm']}",
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
            f.write(f"## Tokens/second (max_tokens={MAX_TOKENS} vs {SHORT_TOKENS}, non-streaming)\n\n{table}\n")
    return 0 if any(n for _, n, *_ in summary) else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1:]))
