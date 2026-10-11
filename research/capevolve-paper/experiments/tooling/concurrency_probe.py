"""Concurrency/latency probe: N parallel requests of a ~1.5k-token agent-like prompt.

python3.12 -I concurrency_probe.py <provider> <model> <concurrency> <n_requests> [max_tokens]
Writes one JSON summary line to ../logs/concurrency_probes.jsonl. No secrets logged.
"""
import json
import os
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from provider_env import load_all  # noqa: E402
from probe_providers import _req  # noqa: E402

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "concurrency_probes.jsonl")
CTX = ("You are a spreadsheet agent. The workbook has sheets Sales(A:F) and Summary. " * 60)
MSG = [{"role": "system", "content": CTX},
       {"role": "user", "content": "Write a short python openpyxl snippet that sums column C of sheet Sales into Summary!B2. Code only."}]
TOOLS = [{"type": "function", "function": {"name": "run_python", "description": "Run python code",
          "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}}}]


def one(provider, model, cfg, max_tokens, tools):
    if provider == "rits":
        c = cfg["rits"]
        base = f"{c['base'].rstrip('/')}/{model.split('|')[0].strip('/')}/v1"
        served = model.split("|")[1]
        url, hdr = base + "/chat/completions", {"RITS_API_KEY": c["key"]}
        body = {"model": served, "messages": MSG, "max_tokens": max_tokens, "temperature": 0}
    else:
        c = cfg["litellm"]
        url, hdr = c["base"].rstrip("/") + "/v1/chat/completions", {"Authorization": f"Bearer {c['key']}"}
        body = {"model": model, "messages": MSG, "max_tokens": max_tokens}
    if tools:
        body["tools"] = TOOLS
    st, js, dt = _req(url, hdr, body, timeout=300)
    ch = (js.get("choices") or [{}])[0].get("message") or {}
    return {"status": st, "lat": dt, "usage": js.get("usage") or {},
            "tool_call": bool(ch.get("tool_calls")), "err": None if st == 200 else str(js.get("error"))[:120]}


if __name__ == "__main__":
    prov, model, conc, n = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    mt = int(sys.argv[5]) if len(sys.argv) > 5 else 400
    tools = os.environ.get("PROBE_TOOLS") == "1"
    cfg = load_all()
    t0 = time.time()
    with ThreadPoolExecutor(conc) as ex:
        res = list(ex.map(lambda _: one(prov, model, cfg, mt, tools), range(n)))
    wall = time.time() - t0
    ok = [r for r in res if r["status"] == 200]
    lats = sorted(r["lat"] for r in ok)
    out = {"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "provider": prov, "model": model,
           "concurrency": conc, "n": n, "ok": len(ok), "errors": [r["err"] for r in res if r["status"] != 200][:5],
           "status_counts": {str(s): sum(1 for r in res if r["status"] == s) for s in {r["status"] for r in res}},
           "p50": round(statistics.median(lats), 2) if lats else None,
           "p95": round(lats[int(0.95 * (len(lats) - 1))], 2) if lats else None,
           "wall_s": round(wall, 1), "req_per_min": round(60 * len(ok) / wall, 1),
           "mean_completion_tokens": round(statistics.mean(r["usage"].get("completion_tokens", 0) for r in ok), 1) if ok else None,
           "mean_prompt_tokens": round(statistics.mean(r["usage"].get("prompt_tokens", 0) for r in ok), 1) if ok else None,
           "tool_call_rate": round(sum(r["tool_call"] for r in ok) / len(ok), 2) if ok and tools else None}
    with open(LOG, "a") as fh:
        fh.write(json.dumps(out) + "\n")
    print(json.dumps(out))
