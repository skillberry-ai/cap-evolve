"""Tiny redacted provider probes. Prints status, returned model id, latency, usage only.

python3.12 -I probe_providers.py <provider> <model> [<model> ...]
provider in {rits, azure, litellm, litellm-models, rits-models}
Appends one JSON line per probe to ../logs/provider_probes.jsonl (no secrets).
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from provider_env import load_all  # noqa: E402

LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "provider_probes.jsonl")
PROMPT = [{"role": "user", "content": "Reply with exactly the word: pong"}]


def _req(url, headers, body=None, timeout=120):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={**headers, "Content-Type": "application/json"},
                                 method="POST" if body is not None else "GET")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode()), time.time() - t0
    except urllib.error.HTTPError as e:
        txt = e.read().decode(errors="replace")[:300]
        return e.code, {"error": txt}, time.time() - t0
    except Exception as e:  # network
        return None, {"error": f"{type(e).__name__}: {str(e)[:200]}"}, time.time() - t0


def probe(provider, model, cfg):
    if provider == "rits":
        c = cfg["rits"]
        url = f"{c['base'].rstrip('/')}/{model.strip('/')}/v1/chat/completions"
        hdr = {"RITS_API_KEY": c["key"]}
        body = {"model": None, "messages": PROMPT, "max_tokens": 256, "temperature": 0}
        # RITS needs the served model name; try listing first.
        st, js, _ = _req(f"{c['base'].rstrip('/')}/{model.strip('/')}/v1/models", hdr)
        served = (js.get("data") or [{}])[0].get("id") if st == 200 else None
        body["model"] = served or model.strip("/")
    elif provider == "azure":
        c = cfg["azure"]
        url = f"{c['base'].rstrip('/')}/openai/deployments/{model}/chat/completions?api-version={c['version']}"
        hdr = {"api-key": c["key"]}
        body = {"messages": PROMPT, "max_completion_tokens": 64}
        served = None
    elif provider == "litellm":
        c = cfg["litellm"]
        url = f"{c['base'].rstrip('/')}/v1/chat/completions"
        hdr = {"Authorization": f"Bearer {c['key']}"}
        body = {"model": model, "messages": PROMPT, "max_tokens": 64}
        served = None
    else:
        raise SystemExit(provider)
    st, js, dt = _req(url, hdr, body)
    rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "provider": provider, "alias": model,
           "served_listing": served, "status": st, "latency_s": round(dt, 2),
           "response_model": js.get("model"), "usage": js.get("usage"),
           "content": (((js.get("choices") or [{}])[0].get("message") or {}).get("content") or "")[:40] if st == 200 else None,
           "error": js.get("error") if st != 200 else None}
    with open(LOG, "a") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def list_models(provider, cfg):
    c = cfg[provider]
    if provider == "litellm":
        st, js, _ = _req(f"{c['base'].rstrip('/')}/v1/models", {"Authorization": f"Bearer {c['key']}"})
        return st, sorted(m["id"] for m in js.get("data", [])) if st == 200 else js
    if provider == "azure":
        st, js, _ = _req(f"{c['base'].rstrip('/')}/openai/deployments?api-version=2022-12-01", {"api-key": c["key"]})
        return st, js


if __name__ == "__main__":
    cfg = load_all()
    prov = sys.argv[1]
    if prov.endswith("-models"):
        print(json.dumps(list_models(prov[:-7], cfg), indent=0)[:20000])
    else:
        for m in sys.argv[2:]:
            print(json.dumps(probe(prov, m, cfg)))
