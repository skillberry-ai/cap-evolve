"""SPA (Skillberry Proxy-Agent) environment wiring for the in-sandbox OpenHands agent.

The agent under test (OpenHands) runs in a Docker container and must reach
Skillberry Proxy-Agent (SPA) on the host. SPA exposes an OpenAI-compatible
endpoint at port 7000. Since Docker containers cannot use localhost to reach
the host, we resolve the Docker bridge gateway IP (Linux/WSL2: typically
172.17.0.1; macOS/Windows: host.docker.internal).

Credentials (LLM_API_KEY) are read from the repo-root .env (walk parents,
setdefault, no python-dotenv dep) and propagated into the sandbox with
BenchFlow's --agent-env KEY=VALUE flags.

This does NO network at import time, so cap-evolve check stays offline.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

LLM_BASE_URL_VAR = "LLM_BASE_URL"
LLM_API_KEY_VAR = "LLM_API_KEY"
LLM_MODEL_VAR = "LLM_MODEL"

DEFAULT_SPA_PORT = "7000"


def _load_env() -> None:
    """Load the repo-root .env into os.environ (walk parents), without overwrite."""
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        env = parent / ".env"
        if env.exists():
            try:
                for raw in env.read_text(encoding="utf-8").splitlines():
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, val = line.partition("=")
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key:
                        os.environ.setdefault(key, val)
            except Exception:
                pass
            break


def _docker_bridge_ip() -> str:
    """Detect the Docker bridge gateway IP for host access from containers."""
    try:
        result = subprocess.run(
            ["docker", "network", "inspect", "bridge",
             "--format", "{{range .IPAM.Config}}{{.Gateway}}{{end}}"],
            capture_output=True, text=True, timeout=10,
        )
        ip = result.stdout.strip()
        if ip:
            return ip
    except Exception:
        pass
    return "172.17.0.1"


def spa_env() -> dict[str, str]:
    """Return {LLM_BASE_URL, LLM_API_KEY, LLM_MODEL} for the sandboxed agent.

    LLM_BASE_URL points to SPA on the host via the Docker bridge IP.
    Raises only when actually needed for a real rollout.
    """
    _load_env()

    api_key = os.environ.get(LLM_API_KEY_VAR)
    if not api_key:
        raise RuntimeError(
            f"{LLM_API_KEY_VAR} not set. Put it in the repo-root .env "
            "or export it in your shell."
        )

    base_url = os.environ.get(LLM_BASE_URL_VAR)
    if not base_url:
        bridge_ip = _docker_bridge_ip()
        port = os.environ.get("SKILLBERRY_AGENT_PORT", DEFAULT_SPA_PORT)
        base_url = f"http://{bridge_ip}:{port}/"

    model = os.environ.get(LLM_MODEL_VAR, "gpt-4o")

    return {
        LLM_BASE_URL_VAR: base_url,
        LLM_API_KEY_VAR: api_key,
        LLM_MODEL_VAR: model,
    }
