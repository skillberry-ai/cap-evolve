"""AppWorld blackbox tailoring: route AppWorld's stock ReAct agent through the Skillberry Proxy-Agent.

Nothing in AppWorld is modified. The agent under test is AppWorld's own SimplifiedReActCodeAgent with
its own stock prompt file. What this module adds, from outside the benchmark:

- The client's model is the proxy's sentinel (``openai/ibm/skillberry-local`` at the proxy's
  ``/v1``), so every LLM call goes to the Skillberry Proxy-Agent (SPA).
- Every call carries ``skillberry-context-*`` headers (README: How a call flows):
  ``env_id`` / ``task_id`` / ``plugin``, ``history_start_regex`` (the proxy drops the client's
  22 stock prompt messages up to the real task turn) and ``template-main_user-*`` (the proxy
  renders the candidate SKILL.md with the task's supervisor).
- The candidate (a skill folder with one SKILL.md) is deployed to the Skillberry Store, and SPA
  is restarted bound to it (``deploy``).
- SPA's upstream model comes from the same ``AW_*`` variables the direct approach uses
  (``spa_upstream_env``).
"""

from __future__ import annotations

import hashlib
import os
import sys
import shutil
import tempfile
import threading
import urllib.request
from pathlib import Path

_HERE = Path(__file__).resolve().parent

SKILL_NAME = "my_skill"
PLUGIN = "appworld"
SPA_MODEL_SENTINEL = "openai/ibm/skillberry-local"
# The client's real task turn: the last message of AppWorld's stock prompt. It is the only message
# that starts with this phrase (the demo's look-alike reads "Using these APIs, you can now ...").
HISTORY_START_REGEX = r"^\s*Using these APIs, now generate code to solve the actual task:"
SUPERVISOR_FIELDS = ("first_name", "last_name", "email", "phone_number")

# What the direct approach uses for its model (adapters/aw_agent.py MODEL_CONFIG).
DEFAULT_MODEL_NAME = "hosted_vllm/openai/gpt-oss-120b-a100"
DEFAULT_MODEL_URL = "{{MODEL_SERVER_URL}}/gpt-oss-120b-a100/v1"
URL_KEYS = ("RITS_URL", "MODEL_SERVER_URL")
# litellm provider prefixes the direct approach may use that are OpenAI-compatible endpoints;
# SPA reaches them through litellm's openai provider (OPENAI_API_BASE / OPENAI_API_KEY).
OPENAI_COMPATIBLE_PREFIXES = ("hosted_vllm/", "litellm_proxy/", "openai/")


class BlackboxConfigError(RuntimeError):
    """The AW_* model settings cannot be served through the proxy."""


def _blackbox_scripts() -> Path:
    skills = os.environ.get("CAPEVOLVE_SKILLS_DIR")
    if skills:
        return Path(skills) / "interventions" / "llm-proxies" / "blackbox" / "scripts"
    for p in _HERE.parents:
        cand = p / "skills" / "interventions" / "llm-proxies" / "blackbox" / "scripts"
        if cand.is_dir():
            return cand
    raise RuntimeError("cannot locate skills/interventions/llm-proxies/blackbox/scripts "
                       "(set CAPEVOLVE_SKILLS_DIR)")


def blackbox_env():
    scripts = str(_blackbox_scripts())
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    import blackbox_env as bb  # noqa: PLC0415
    return bb


# ---- per-call headers --------------------------------------------------------------------------
def context_headers(env_id: str, task_id: str, supervisor: dict) -> dict[str, str]:
    """The skillberry-context-* headers for one episode. Values must be single-line ASCII."""
    headers = {
        "skillberry-context-plugin": PLUGIN,
        "skillberry-context-env_id": str(env_id),
        "skillberry-context-task_id": str(task_id),
        "skillberry-context-history_start_regex": HISTORY_START_REGEX,
    }
    for field in SUPERVISOR_FIELDS:
        value = str(supervisor.get(field, ""))
        if "\n" in value or "\r" in value or not value.isascii():
            raise ValueError(f"supervisor {field!r} is not a single-line ASCII header value")
        headers[f"skillberry-context-template-main_user-{field}"] = value
    return headers


# ---- SPA's upstream model, from the AW_* variables --------------------------------------------
def _read_kv(path: str | None, keys: tuple[str, ...]) -> dict[str, str]:
    """Only ``keys`` from a KEY=VALUE file (the secrets file); every other line is ignored."""
    out: dict[str, str] = {}
    if not path or not Path(path).is_file():
        return out
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if k.strip() in keys:
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def spa_model_name(aw_model_name: str) -> str:
    """The litellm model SPA should call for the direct approach's ``AW_MODEL_NAME``.

    ``AW_SPA_MODEL`` overrides. Otherwise an OpenAI-compatible provider prefix is replaced by
    ``openai/`` so SPA's litellm uses OPENAI_API_BASE / OPENAI_API_KEY, keeping the served model id
    (``hosted_vllm/openai/gpt-oss-120b-a100`` -> ``openai/openai/gpt-oss-120b-a100``).
    """
    override = os.environ.get("AW_SPA_MODEL")
    if override:
        return override
    for prefix in OPENAI_COMPATIBLE_PREFIXES:
        if aw_model_name.startswith(prefix):
            return "openai/" + aw_model_name[len(prefix):]
    return "openai/" + aw_model_name


def spa_upstream_env(environ: dict[str, str] | None = None) -> dict[str, str]:
    """SPA env overrides (model, endpoint, key) derived from the direct approach's AW_* variables.

    The proxy sends a standard ``Authorization: Bearer`` key, so the AW endpoint must accept one:
    ``AW_KEY_HEADER=bearer`` (a LiteLLM gateway, as CI uses). A custom-header endpoint such as RITS
    with ``RITS_API_KEY: <key>`` cannot be served through the proxy.
    """
    env = dict(os.environ if environ is None else environ)
    key_header = env.get("AW_KEY_HEADER", "RITS_API_KEY")
    if key_header.lower() != "bearer":
        raise BlackboxConfigError(
            f"AW_KEY_HEADER={key_header!r}: the proxy authenticates with a standard bearer key, so the "
            "blackbox approach needs AW_KEY_HEADER=bearer and a gateway that accepts it (README: Models)")
    key_env = env.get("AW_KEY_ENV", "RITS_API_KEY")
    secrets = _read_kv(env.get("AW_SECRETS_FILE"), (key_env,) + URL_KEYS)
    key = env.get(key_env) or secrets.get(key_env)
    if not key:
        raise BlackboxConfigError(f"no value for {key_env} (AW_KEY_ENV) in the environment or AW_SECRETS_FILE")
    url = env.get("AW_MODEL_URL", DEFAULT_MODEL_URL)
    if "{{MODEL_SERVER_URL}}" in url:
        server = (env.get("MODEL_SERVER_URL") or env.get("RITS_URL")
                  or secrets.get("MODEL_SERVER_URL") or secrets.get("RITS_URL"))
        if not server:
            raise BlackboxConfigError("AW_MODEL_URL uses {{MODEL_SERVER_URL}} but neither MODEL_SERVER_URL "
                                      "nor RITS_URL is set")
        url = url.replace("{{MODEL_SERVER_URL}}", server.rstrip("/"))
    return {
        "SPA_MODEL_NAME": spa_model_name(env.get("AW_MODEL_NAME", DEFAULT_MODEL_NAME)),
        "OPENAI_API_BASE": url,
        "OPENAI_BASE_URL": url,
        "OPENAI_API_KEY": key,
    }


# ---- deploying a candidate ---------------------------------------------------------------------
def skill_digest(skill_dir: Path) -> str:
    """A content hash of the candidate's SKILL.md (the only file deployed): which candidate SPA serves."""
    return hashlib.sha256((Path(skill_dir) / "SKILL.md").read_bytes()).hexdigest()


_deploy_lock = threading.Lock()
_deployed = {"digest": None}


def deploy(skill_dir: Path) -> bool:
    """Make ``skill_dir`` the store's only skill and restart SPA bound to it.

    Idempotent per candidate content: a second call with the same SKILL.md does nothing (SPA serves
    one skill for its whole lifetime, so only a new candidate needs a restart). Returns True when it
    (re)deployed. Raises on any store or SPA failure.
    """
    digest = skill_digest(skill_dir)
    with _deploy_lock:
        if _deployed["digest"] == digest:
            return False
        bb = blackbox_env()
        upstream = spa_upstream_env()
        bb.start_store()
        # The store imports EVERY file of the folder (each .md becomes an injected snippet), and the
        # candidate folder also holds the harness's own files - so import a copy with SKILL.md alone.
        stage = Path(tempfile.mkdtemp(prefix="aw_bb_skill_")) / SKILL_NAME
        stage.mkdir()
        shutil.copy2(Path(skill_dir) / "SKILL.md", stage / "SKILL.md")
        try:
            bb.reset_store_to_skill(stage, SKILL_NAME, bb.Protection())
        finally:
            shutil.rmtree(stage.parent, ignore_errors=True)
        bb.restart_spa(SKILL_NAME, **upstream)
        _deployed["digest"] = digest
        return True


def spa_base_url() -> str:
    return os.environ.get("SPA_BASE_URL", "http://127.0.0.1:7000").rstrip("/")


def disconnect(headers: dict, spa_url: str | None = None, timeout: float = 60) -> bool:
    """Release the proxy's per-episode state (its vMCP server and trajectory) for headers' env_id.

    A session is one episode (one trial). The worker calls this when its episode ends, and the adapter calls it again for any episode that did
    not confirm it (killed at the wall cap, crashed): without that, the proxy keeps that env_id's
    server for the rest of its life. Idempotent: the proxy answers 200 for an env_id it no longer holds.
    Returns whether the proxy confirmed it. AppWorld needs no trajectory tailoring: its agent writes
    code instead of calling proxy tools, so the proxy's trajectory has nothing to merge.
    """
    req = urllib.request.Request((spa_url or spa_base_url()) + "/disconnect", data=b"{}", method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001 — cleanup only: report it, never raise
        return False
