"""Campaign gateway: one local endpoint for every model call in the campaign.

Responsibilities
  * routing: `rits/<vendor>/<model>` -> RITS per-deployment URL (RITS_API_KEY header);
             everything else -> the LiteLLM gateway (Bearer key). Anthropic `/v1/messages`
             is passed through verbatim (streaming supported) for the Claude Code optimizer.
  * admission control: one semaphore per upstream key shared by every worker in the campaign.
  * metering: one JSON line per call to logs/gateway_calls.jsonl with the caller's tag, model,
             status, latency, queue wait and token usage. Credentials are injected here and
             never logged; the caller's bearer token is used ONLY as a non-secret run tag.
  * budget guard: refuses new calls (HTTP 429, body names the cap) once the token ledger
             exceeds campaign caps in caps.json (re-read every 30 s).

Run:  python3.12 -I campaign_gateway.py --port 4111
Client config:  OPENAI_API_BASE / LITELLM_PROXY_API_BASE = http://127.0.0.1:4111/v1
                API key = "tag:<experiment_id>:<arm>:<role>"   (not a secret)
"""
import argparse
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from provider_env import load_all  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "..", "logs", "gateway_calls.jsonl")
CAPS = os.path.join(HERE, "..", "logs", "caps.json")

# served-model-name -> RITS deployment path (verified by /v1/models listing on 2026-10-11)
RITS_ROUTES = {
    "google/gemma-4-31B-it": "google-gemma-4-31b-it-a100",
    "Qwen/Qwen3.6-35B-A3B": "qwen3-6-35b-a3b-a100",
    "openai/gpt-oss-120b-a100": "gpt-oss-120b-a100",
}
DEFAULT_LIMITS = {"rits:google/gemma-4-31B-it": 4, "rits:Qwen/Qwen3.6-35B-A3B": 4,
                  "rits:openai/gpt-oss-120b-a100": 4, "litellm": 8}

CFG = load_all()
_lock = threading.Lock()
_sems = {}
_limits = dict(DEFAULT_LIMITS)
_reserve = {}
_low_tags = []
_ledger = {"total_tokens": 0, "capped_tokens": 0, "rits_tokens": 0, "azure_tokens": 0, "calls": 0, "blocked": False, "reason": ""}


def _bucket(upstream):
    """Ledger bucket: RITS and Azure-direct are uncapped (user decisions 2026-10-11); everything else is capped."""
    u = str(upstream)
    return "rits_tokens" if u.startswith("rits:") else ("azure_tokens" if u.startswith("azoai:") else "capped_tokens")


class _LiveSem:
    """Counting semaphore whose limit is re-read from _limits on every acquire (caps.json is live)."""

    def __init__(self, key):
        self.key, self.n, self.cv = key, 0, threading.Condition()

    def acquire(self, low=False):
        """Low-priority callers (tags matching caps.json `low_priority_tags`) may only use slots
        beyond `reserve_high[key]`; high-priority callers may use all slots."""
        with self.cv:
            while True:
                lim = int(_limits.get(self.key, _limits["litellm"]))
                res = int(_reserve.get(self.key, 0)) if low else 0
                if self.n < max(1, lim - res):
                    break
                self.cv.wait(timeout=5)
            self.n += 1

    def release(self):
        with self.cv:
            self.n -= 1
            self.cv.notify_all()


def _sem(key):
    with _lock:
        if key not in _sems:
            _sems[key] = _LiveSem(key)
        return _sems[key]


def _log(rec):
    line = json.dumps(rec)
    with _lock:
        with open(LOG, "a") as fh:
            fh.write(line + "\n")


def _usage_tokens(u):
    if not u:
        return 0
    if "total_tokens" in u:
        return int(u.get("total_tokens") or 0)
    # anthropic shape
    return int(u.get("input_tokens", 0) or 0) + int(u.get("output_tokens", 0) or 0) + \
        int(u.get("cache_creation_input_tokens", 0) or 0)


def _caps_watch():
    while True:
        try:
            caps = json.load(open(CAPS))
            lim = caps.get("concurrency")
            if lim:
                _limits.update(lim)
            _reserve.clear(); _reserve.update(caps.get("reserve_high", {}))
            _low_tags[:] = caps.get("low_priority_tags", [])
            cap = caps.get("max_nonrits_tokens_ex_cache_read")
            if cap and _ledger["capped_tokens"] >= cap:
                _ledger["blocked"], _ledger["reason"] = True, f"token cap {cap} reached"
        except FileNotFoundError:
            pass
        except Exception as e:  # never die on a bad caps file
            print("caps.json error", e, file=sys.stderr)
        time.sleep(30)


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # silence default access log (it would print headers/paths only, but keep clean)
        pass

    def _tag(self):
        a = self.headers.get("Authorization", "") or self.headers.get("x-api-key", "")
        a = a.replace("Bearer ", "").strip()
        return a if a.startswith("tag:") else "untagged"

    def _send(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            ids = [f"rits/{k}" for k in RITS_ROUTES] + ["azoai/<dated Azure deployment>", "<any litellm gateway id>"]
            return self._send(200, {"object": "list", "data": [{"id": i, "object": "model"} for i in ids]})
        if self.path.startswith("/health"):
            return self._send(200, {"ok": True, **_ledger})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)
        try:
            body = json.loads(raw or b"{}")
        except Exception:
            return self._send(400, {"error": "bad json"})
        tag = self._tag()
        if _ledger["blocked"]:
            return self._send(429, {"error": {"message": f"campaign budget guard: {_ledger['reason']}"}})
        model = body.get("model", "")
        path = self.path
        is_anthropic = path.startswith("/v1/messages")
        if model.startswith("azoai/"):
            # Azure OpenAI direct (user decision 2026-10-11 21:05): deployment = dated name, e.g. azoai/gpt-4.1-2025-04-14.
            # Metered like everything else; tokens are counted in their own uncapped bucket (azure_tokens).
            dep = model[len("azoai/"):]
            c = CFG["azure"]
            url = f"{c['base'].rstrip('/')}/openai/deployments/{dep}/chat/completions?api-version={c['version']}"
            hdr = {"api-key": c["key"], "Content-Type": "application/json"}
            body.pop("model", None)
            if "max_tokens" in body and "max_completion_tokens" not in body:
                body["max_completion_tokens"] = body.pop("max_tokens")
            key = f"azoai:{dep}"
        elif model.startswith("rits/"):
            served = model[len("rits/"):]
            route = RITS_ROUTES.get(served)
            if not route:
                return self._send(404, {"error": {"message": f"unknown rits model {served}"}})
            c = CFG["rits"]
            url = f"{c['base'].rstrip('/')}/{route}/v1/chat/completions"
            hdr = {"RITS_API_KEY": c["key"], "Content-Type": "application/json"}
            body["model"] = served
            key = f"rits:{served}"
        else:
            c = CFG["litellm"]
            p = path if path.startswith("/v1/") else "/v1" + path
            url = c["base"].rstrip("/") + p
            hdr = {"Content-Type": "application/json"}
            if is_anthropic:
                hdr["x-api-key"] = c["key"]
                hdr["Authorization"] = f"Bearer {c['key']}"
                for h in ("anthropic-version", "anthropic-beta"):
                    if self.headers.get(h):
                        hdr[h] = self.headers[h]
            else:
                hdr["Authorization"] = f"Bearer {c['key']}"
            key = "litellm"
        stream = bool(body.get("stream"))
        data = json.dumps(body).encode()
        t_q = time.time()
        sem = _sem(key)
        low = any(pat in tag for pat in _low_tags)
        sem.acquire(low=low)
        t0 = time.time()
        status, usage, err, attempts = None, None, None, 0
        try:
            # Transparent upstream retry for exogenous transport failures (connection reset, read
            # timeout, 502/503/504) BEFORE any byte is sent to the client: chat/messages requests are
            # idempotent from the caller's view, so every arm gets identical, invisible retries.
            while True:
                attempts += 1
                req = urllib.request.Request(url, data=data, headers=hdr, method="POST")
                try:
                    resp = urllib.request.urlopen(req, timeout=1800)
                    status = resp.status
                    if status in (502, 503, 504) and attempts < 4:
                        resp.read(); time.sleep(2 ** attempts); continue
                    break
                except urllib.error.HTTPError as e:
                    if e.code in (502, 503, 504) and attempts < 4:
                        e.read(); time.sleep(2 ** attempts); continue
                    resp, status = e, e.code
                    break
                except (ConnectionError, TimeoutError, urllib.error.URLError) as e:
                    if attempts < 4:
                        time.sleep(2 ** attempts); continue
                    raise
            self.send_response(status)
            ctype = resp.headers.get("Content-Type", "application/json")
            self.send_header("Content-Type", ctype)
            if stream and status == 200:
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                buf = b""
                while True:
                    chunk = resp.read1(65536) if hasattr(resp, "read1") else resp.read(65536)
                    if not chunk:
                        break
                    buf += chunk
                    self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
                usage = _parse_stream_usage(buf)
            else:
                payload = resp.read()
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                try:
                    js = json.loads(payload)
                    usage = js.get("usage")
                    ch = (js.get("choices") or [{}])[0] if isinstance(js.get("choices"), list) else {}
                    finish = ch.get("finish_reason") or js.get("stop_reason")
                    msg = ch.get("message") or {}
                    empty = (not (msg.get("content") or msg.get("tool_calls"))) if ch else (not js.get("content"))
                    if finish in ("content_filter", "refusal") or (status == 200 and empty):
                        err = f"finish={finish} empty={empty}"
                    if status != 200:
                        err = str(js.get("error"))[:300]
                except Exception:
                    err = None if status == 200 else payload[:300].decode(errors="replace")
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:200]}"
            try:
                self._send(502, {"error": {"message": f"campaign gateway upstream error: {err}"}})
            except Exception:
                pass
            status = status or 502
        finally:
            sem.release()
            tok = _usage_tokens(usage)
            with _lock:
                _ledger["total_tokens"] += tok
                # user decision 2026-10-11: RITS-served tokens are uncapped (still metered); the cap covers the rest
                _ledger[_bucket(key)] += tok
                _ledger["calls"] += 1
            _log({"t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tag": tag, "model": model,
                  "upstream": key, "api": "anthropic" if is_anthropic else "openai", "stream": stream,
                  "status": status, "attempts": attempts, "queue_s": round(t0 - t_q, 3), "latency_s": round(time.time() - t0, 3),
                  "usage": usage, "error": err})


def _parse_stream_usage(buf):
    """Pull token usage out of an SSE stream (OpenAI final chunk or Anthropic message_start/delta)."""
    usage = {}
    for line in buf.decode(errors="replace").splitlines():
        if not line.startswith("data:"):
            continue
        s = line[5:].strip()
        if s in ("", "[DONE]"):
            continue
        try:
            ev = json.loads(s)
        except Exception:
            continue
        if ev.get("usage"):
            usage.update({k: v for k, v in ev["usage"].items() if v is not None})
        msg = ev.get("message") or {}
        if msg.get("usage"):
            usage.update({k: v for k, v in msg["usage"].items() if v is not None})
    return usage or None


def _replay_ledger():
    """Rebuild the ledger from the call log so a gateway restart never resets the budget."""
    if not os.path.exists(LOG):
        return
    for line in open(LOG):
        try:
            r = json.loads(line)
        except Exception:
            continue
        tok = _usage_tokens(r.get("usage"))
        _ledger["total_tokens"] += tok
        _ledger[_bucket(r.get("upstream", ""))] += tok
        _ledger["calls"] += 1


if __name__ == "__main__":
    _replay_ledger()
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=4111)
    a = ap.parse_args()
    threading.Thread(target=_caps_watch, daemon=True).start()
    class _Srv(ThreadingHTTPServer):
        allow_reuse_address = True

        def server_bind(self):
            import socket
            # SO_REUSEPORT lets a new gateway bind beside an old one, so a restart can drain the old
            # process (stop accepting, finish in-flight calls) instead of dropping them.
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            super().server_bind()

    srv = _Srv(("127.0.0.1", a.port), H)
    srv.daemon_threads = True
    print(f"campaign gateway on 127.0.0.1:{a.port}", flush=True)
    srv.serve_forever()
