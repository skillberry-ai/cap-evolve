"""ALTK-Evolve setup shared by the altk scripts (README: ALTK-Evolve arm). Python 3.12 venv.

``setup()`` must run BEFORE anything from ``altk_evolve`` is imported: the library binds
``from litellm import completion`` at import time, so the wrapper has to be in place first. The
wrapper adds the optimizer gateway's base URL, token and custom headers to every call made in
this process (the library itself is not modified) and appends one usage line per call to
``runs/altk/optimizer_usage.jsonl``.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

EVAL = Path(os.environ.get("AW_EVAL", "/tmp/aw_eval"))
ALTK_DIR = Path(os.environ.get("AW_ALTK_DIR", str(EVAL / "runs" / "altk")))
USAGE_LOG = ALTK_DIR / "optimizer_usage.jsonl"
OPT_MODEL = os.environ.get("OPT_MODEL", "aws/claude-sonnet-5-5")
_lock = threading.Lock()


def _custom_headers() -> dict[str, str]:
    out = {}
    for line in os.environ.get("ANTHROPIC_CUSTOM_HEADERS", "").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def setup(data_dir: Path | None = None, namespace: str = "aw_train") -> None:
    os.environ.setdefault("HF_HOME", str(EVAL / "hf"))
    os.environ["EVOLVE_GUIDELINES_MODEL"] = f"anthropic/{OPT_MODEL}"
    os.environ["EVOLVE_MODEL_NAME"] = f"anthropic/{OPT_MODEL}"
    os.environ["EVOLVE_CUSTOM_LLM_PROVIDER"] = "anthropic"
    os.environ["EVOLVE_BACKEND"] = "filesystem"
    os.environ["EVOLVE_NAMESPACE_ID"] = namespace
    os.environ["EVOLVE_DATA_DIR"] = str(data_dir or (ALTK_DIR / "store"))
    os.environ.setdefault("EVOLVE_GUIDELINES_MODE", "standard")
    ALTK_DIR.mkdir(parents=True, exist_ok=True)

    import litellm

    if getattr(litellm.completion, "_aw_wrapped", False):
        return
    orig = litellm.completion
    base = os.environ["ANTHROPIC_BASE_URL"]
    token = os.environ["ANTHROPIC_AUTH_TOKEN"]
    headers = _custom_headers()

    def completion(*args, **kwargs):
        kwargs.setdefault("api_base", base)
        kwargs.setdefault("api_key", token)
        kwargs["extra_headers"] = {**headers, **(kwargs.get("extra_headers") or {})}
        t0 = time.time()
        err = None
        resp = None
        try:
            resp = orig(*args, **kwargs)
            return resp
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {str(e)[:300]}"
            raise
        finally:
            usage = getattr(resp, "usage", None)
            rec = {"t": round(t0, 2), "seconds": round(time.time() - t0, 2),
                   "model": kwargs.get("model") or (args[0] if args else None),
                   "prompt_tokens": getattr(usage, "prompt_tokens", None),
                   "completion_tokens": getattr(usage, "completion_tokens", None), "error": err}
            with _lock, open(USAGE_LOG, "a") as f:
                f.write(json.dumps(rec) + "\n")

    completion._aw_wrapped = True  # type: ignore[attr-defined]
    litellm.completion = completion

    # The gateway rejects the forced tool_choice that litellm uses to emulate response_format
    # on Anthropic models ("tool_choice: type tool and any are not supported for this model").
    # Report no schema support, so the library uses its own prompt-JSON path (as for groq).
    orig_srs = litellm.supports_response_schema

    def supports_response_schema(*args, **kwargs):
        model = kwargs.get("model") or (args[0] if args else "")
        if OPT_MODEL in str(model):
            return False
        return orig_srs(*args, **kwargs)

    litellm.supports_response_schema = supports_response_schema


def usage_totals(path: Path = USAGE_LOG) -> dict:
    calls = errors = pt = ct = 0
    if path.is_file():
        for line in path.read_text().splitlines():
            r = json.loads(line)
            calls += 1
            errors += bool(r.get("error"))
            pt += int(r.get("prompt_tokens") or 0)
            ct += int(r.get("completion_tokens") or 0)
    return {"calls": calls, "errors": errors, "prompt_tokens": pt, "completion_tokens": ct}


def log(detail: str, phase: str = "altk") -> None:
    p = EVAL / "progress" / "altk.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(p, "a") as f:
        f.write(f"{ts} | altk | {phase} | {detail}\n")
