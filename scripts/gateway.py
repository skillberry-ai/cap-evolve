#!/usr/bin/env python3
"""Local metering gateway for exp895 (issue skillberry-ai/cap-evolve#895, section 8).

One process per upstream: `--upstream gemma` (RITS google/gemma-4-31B-it, port 4113) or `--upstream glm`
(Curve Bender GLM, port 4115). Callers use a NON-secret tag in the path: http://127.0.0.1:<port>/t/<tag>/v1/...
with tag = `<exp>-<arm>-s<seed>:<role>`. The gateway injects the real credential (read from ~/secrets into
memory only; never logged, never written to the ledger).

Behaviour (from the issue):
  * retries 429/500/502/503/504/529, connection errors, read timeouts, empty/truncated replies; exponential backoff
    with jitter (cap 60 s), up to 8 attempts; nothing reaches the client before an attempt succeeds
  * streams are buffered until complete, then replayed
  * a per-model concurrency semaphore, hot-reloaded from caps.json
  * a key answering 401/403 is marked dead for 10 minutes
  * GLM: /v1/messages gets thinking={"type":"disabled"} and output_config dropped; chat/completions gets
    reasoning_effort="low" unless the caller set one; image blocks replaced by a text placeholder
  * ledger: one JSON line per call, one per retry, in calls.jsonl (token counts only; $ is recomputed offline
    from pricing.json)
"""
import argparse
import asyncio
import json
import os
import random
import time
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request, Response

SECRETS = Path(os.path.expanduser("~/secrets"))
RETRY_STATUS = {429, 500, 502, 503, 504, 529}
# 401/403 cool-off before the call is retried (it waits; it does not fail). 60 s x up to 8 attempts covers a transient
# upstream auth blip; a really revoked key still ends with the final 401 status after all attempts.
AUTH_COOLOFF_S = float(os.environ.get("GW_AUTH_COOLOFF", "60"))
MAX_ATTEMPTS = 8


def load_env(name):
    d = {}
    for line in (SECRETS / name).read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip().strip("'\"")
    return d


def upstream_cfg(kind):
    if kind == "gemma":  # route B: RITS instruction-tuned Gemma (decisions.md)
        e = load_env("rits.env")
        base = e["RITS_BASE_URL"].rsplit("/", 1)[0] + "/google-gemma-4-31b-it-a100"
        # GW_RITS_KEY_SLOT picks one extra key (RITS_API_KEY_<n> in ~/secrets/rits_keys.env) for this gateway, so
        # jobs spread over several keys (2026-10-25). Unset = the original rits.env key, unchanged for running arms.
        slot = os.environ.get("GW_RITS_KEY_SLOT", "").strip()
        key = load_env("rits_keys.env")[f"RITS_API_KEY_{slot}"] if slot else e["RITS_API_KEY"]
        return dict(base=base, headers={"RITS_API_KEY": key}, model="google/gemma-4-31B-it", key_slot=slot or "rits.env",
                    read_timeout=float(os.environ.get("GW_GEMMA_TIMEOUT", "300")), apis={"chat"})   # 90 until 2026-10-26; Boaz: 300 for gateways started from now on
    e = load_env("curve_bender.env")  # glm
    tok = e["CB_LITELLM_TOKEN"]
    return dict(base=e["CB_LITELLM_BASE_URL"].rstrip("/"),
                headers={"Authorization": "Bearer " + tok, "x-api-key": tok, "anthropic-version": "2023-06-01"},
                model=e["CB_MODEL"], read_timeout=float(os.environ.get("GW_GLM_TIMEOUT", "900")),   # non-streamed 16k replies need >180 s (decisions.md)
                apis={"chat", "messages"})


def scrub_images(obj):
    """GLM is text-only: replace image blocks by a placeholder."""
    if isinstance(obj, list):
        return [({"type": "text", "text": "[image omitted]"} if isinstance(x, dict) and x.get("type") in
                 ("image", "image_url") else scrub_images(x)) for x in obj]
    if isinstance(obj, dict):
        return {k: scrub_images(v) for k, v in obj.items()}
    return obj


def stream_usage(data: bytes) -> dict:
    """The usage of a buffered SSE stream, merged into one dict.

    Anthropic /v1/messages: `message_start` carries message.usage (input_tokens, cache_*), and each
    `message_delta` carries usage.output_tokens (cumulative). OpenAI chat/completions: the final chunk carries
    `usage` when stream_options.include_usage was set. Later values win, so cumulative counters end correct.
    """
    merged = {}
    for line in data.decode("utf-8", "replace").splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            ev = json.loads(payload)
        except ValueError:
            continue
        for u in ((ev.get("message") or {}).get("usage"), ev.get("usage")):
            if isinstance(u, dict):
                merged.update({k: v for k, v in u.items() if v is not None})
    return merged


def usage_record(u: dict) -> dict:
    """Normalise either usage shape. NB: Anthropic input_tokens EXCLUDE cache reads/creations (issue §2.3);
    OpenAI prompt_tokens INCLUDE cached tokens. prompt_total is the shape-independent total."""
    det = u.get("prompt_tokens_details") or {}
    anthropic = "input_tokens" in u
    cached = u.get("cache_read_input_tokens") if anthropic else det.get("cached_tokens")
    created = u.get("cache_creation_input_tokens")
    prompt = u.get("input_tokens") if anthropic else u.get("prompt_tokens")
    total = (prompt or 0) + ((cached or 0) + (created or 0) if anthropic else 0)
    return {"prompt_tokens": prompt, "completion_tokens": u.get("output_tokens", u.get("completion_tokens")),
            "cached_tokens": cached, "cache_creation_tokens": created, "prompt_total": total if u else None,
            "reasoning_tokens": (u.get("completion_tokens_details") or {}).get("reasoning_tokens"),
            "usage_shape": ("anthropic" if anthropic else "openai") if u else None}


def make_app(kind, run_dir):
    cfg = upstream_cfg(kind)
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    ledger = open(run_dir / f"calls_{kind}.jsonl", "a", buffering=1)
    caps_file = run_dir / "caps.json"
    state = {"sem": None, "cap": 0, "dead_until": 0.0}
    # §5 runaway guard: 20M non-cache-read optimizer tokens per search (per tag). LOG-ONLY for every arm, because the
    # CapEvolve searches were launched without an enforcing guard; enforcing it on competitors alone would be unequal.
    OPT_TOKEN_GUARD = int(os.environ.get("GW_OPT_TOKEN_GUARD", "20000000"))
    opt_tokens: dict = {}

    def cap():
        try:
            return int(json.loads(caps_file.read_text()).get(kind, 16))
        except Exception:
            return 16

    def sem():  # hot reload: a changed cap swaps the semaphore for new callers
        c = cap()
        if state["sem"] is None or c != state["cap"]:
            state["sem"], state["cap"] = asyncio.Semaphore(c), c
        return state["sem"]

    app = FastAPI()
    client = httpx.AsyncClient(timeout=httpx.Timeout(cfg["read_timeout"], connect=20.0),
                               limits=httpx.Limits(max_connections=512))

    def log(rec):
        ledger.write(json.dumps(rec, separators=(",", ":")) + "\n")

    @app.get("/healthz")
    async def healthz():
        return {"ok": True, "upstream": kind, "cap": cap(), "dead_until": state["dead_until"],
                "key_slot": cfg.get("key_slot")}

    @app.api_route("/t/{tag:path}", methods=["POST"])
    async def proxy(tag: str, request: Request):
        tagname, _, rest = tag.partition("/v1/")
        rest = "v1/" + rest
        api = "messages" if rest.startswith("v1/messages") else "chat"
        if api not in cfg["apis"]:
            return Response(json.dumps({"error": f"{kind} gateway has no {api} api"}), 404)
        body = json.loads(await request.body())
        stream = bool(body.get("stream"))
        body["model"] = cfg["model"]
        if kind == "glm":
            body = scrub_images(body)
            if api == "messages":
                body["thinking"] = {"type": "disabled"}
                body.pop("output_config", None)
            else:
                body.setdefault("reasoning_effort", "low")
        url = f"{cfg['base']}/{rest}"
        t0, retries, queue_s = time.time(), 0, 0.0
        async with sem():
            queue_s = time.time() - t0
            for attempt in range(1, MAX_ATTEMPTS + 1):
                err, status, data = None, None, b""
                # A 401/403 marks the key dead for a short cool-off, and the call WAITS it out instead of failing.
                # On 2026-10-22 14:03Z Curve Bender returned a transient 401 and the old 600 s "fail every call" window
                # (§8's literal reading) ended 4 searches with no optimizer step. An auth error is infra, never a result.
                wait = state["dead_until"] - time.time()
                if wait > 0:
                    await asyncio.sleep(wait + random.uniform(0, 5))
                try:
                    r = await client.post(url, json=body, headers={**cfg["headers"], "content-type": "application/json"})
                    status, data = r.status_code, r.content  # httpx reads the whole stream: buffered
                    if status in (401, 403):
                        state["dead_until"] = max(state["dead_until"], time.time() + AUTH_COOLOFF_S)
                        err = f"auth_{status}"
                    elif status in RETRY_STATUS:
                        err = f"http_{status}"
                    elif status == 200 and not data.strip():
                        err = "empty_reply"
                    elif status == 200 and stream and b"[DONE]" not in data and b"message_stop" not in data:
                        err = "truncated_stream"
                except (httpx.TimeoutException, httpx.TransportError) as e:
                    err = type(e).__name__
                # auth errors are now RETRIED (after the cool-off above); only success or the last attempt ends the loop
                if err is None or attempt == MAX_ATTEMPTS:
                    break
                retries += 1
                log({"event": "retry", "ts": time.time(), "tag": tagname, "upstream": kind, "attempt": attempt,
                     "error_class": err})
                await asyncio.sleep(min(60.0, 2.0 ** attempt) * random.uniform(0.5, 1.0))
        usage = {}
        if status == 200:
            try:
                usage = usage_record(stream_usage(data) if stream else (json.loads(data).get("usage") or {}))
            except Exception:
                pass
        if usage and tagname.endswith(":optimizer"):
            used = (usage.get("prompt_total") or 0) - (usage.get("cached_tokens") or 0) + (usage.get("completion_tokens") or 0)
            before = opt_tokens.get(tagname, 0)
            opt_tokens[tagname] = before + used
            if before < OPT_TOKEN_GUARD <= opt_tokens[tagname]:
                log({"event": "opt_token_guard_crossed", "ts": time.time(), "tag": tagname,
                     "non_cache_read_tokens": opt_tokens[tagname], "guard": OPT_TOKEN_GUARD})
        log({"t": t0, "ts": time.time(), "tag": tagname, "model": cfg["model"], "upstream": kind, "api": api,
             "stream": stream, "status": status, "attempts": retries + 1, "retries": retries,
             "queue_s": round(queue_s, 3), "latency_s": round(time.time() - t0, 3),
             "req_max_tokens": body.get("max_tokens"), "error_class": err, **usage})
        if status is None:
            return Response(json.dumps({"error": {"message": f"gateway: {err}"}}), 502, media_type="application/json")
        ct = "text/event-stream" if stream else "application/json"
        return Response(data, status, media_type=ct)

    return app


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", choices=["gemma", "glm"], required=True)
    ap.add_argument("--port", type=int)
    ap.add_argument("--run-dir", required=True)
    a = ap.parse_args()
    port = a.port or {"gemma": 4113, "glm": 4115}[a.upstream]
    uvicorn.run(make_app(a.upstream, a.run_dir), host="127.0.0.1", port=port, log_level="warning")
