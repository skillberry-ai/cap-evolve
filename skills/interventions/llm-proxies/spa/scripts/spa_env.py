"""The Skillberry proxy stack as a library — provision, run, deploy, stop, clean.

SPA mode ("proxy runtime") delivers an optimized capability to the model under test
by putting it in the **Skillberry Store** and letting the **Skillberry Proxy-Agent
(SPA)** inject it into every LLM call the agent makes. The benchmark sees no skill
files; it just talks to what it believes is an LLM.

This module owns everything about that stack that is NOT benchmark-specific:

  * provisioning  -- clone + install store and SPA at pinned refs (``provision``)
  * lifecycle     -- start/stop/status, health-checked, PID-sentinel safe
  * deployment    -- make one skill dir THE skill the store serves
                     (``reset_store_to_skill``) and restart SPA onto it
  * routing       -- where a caller (on the host, or inside a container) reaches SPA

A benchmark example supplies only what is specific to it: its task list, its scorer,
its own environment service, and which skill name SPA should serve.

Two properties are deliberate and load-bearing:

* **No network at import time.** ``cap-evolve check`` must stay offline, so every
  call that touches a service is lazy and every directory is resolved on demand.
* **Nothing is killed that we did not start.** Stops go through the PID sentinel the
  service itself wrote, and fall back to the port owner only after confirming its
  argv. On macOS port 7000 belongs to ControlCenter (AirPlay Receiver); SIGKILLing a
  system process because it squats our port is not acceptable.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Pins and ports
#
# Pins live here, in code, so they are a single source of truth that `check.py`
# can assert on offline. Every one is env-overridable for a bisect or a spike.
# ---------------------------------------------------------------------------

STORE_REPO = "https://github.com/skillberry-ai/skillberry-store.git"
STORE_REF = "0.2.1"                       # a tag: cloned with --branch
AGENT_REPO = "https://github.com/skillberry-ai/skillberry-agent.git"
AGENT_REF = "e359494f18267e339f9561acbd7a930e3b51189e"   # a commit: clone + checkout

# SPA's port is FIXED at 7000 (+7001 for its config UI): `uvicorn.run(..., port=7000)`
# in SPA's main.py, and consumers hardcode it too. A knob here would move the health
# check without moving the routing, so there deliberately isn't one — we preflight the
# port instead and name whoever holds it.
SPA_PORT = "7000"
SPA_CONFIG_PORT = "7001"
STORE_PORT_DEFAULT = "8000"

# Sentinels written by skillberry-common's start-service.sh. They hold the PID of the
# process the service itself started, which is a far safer handle than "whoever owns
# the port".
SPA_PID_FILE = "/tmp/skillberry-agent-service.pid"
STORE_PID_FILE = "/tmp/skillberry-store-service.pid"

# argv markers that identify each service, used before signalling anything.
SPA_PROC_MARKERS = ("python", "-m main")
STORE_PROC_MARKERS = ("skillberry_store.main",)

# SPA runtime configuration defaults. An example overrides only what it means to.
SPA_ENV_DEFAULTS = {
    "SPA_PROVIDER_NAME": "litellm",
    "USE_AGENT_TOOLS": "false",
    "USE_AGENT_PROMPTS": "true",
    "MCP_PROMPTS_POSITION": "postfix",
}

_ENV_LOADED = False


# ---------------------------------------------------------------------------
# Environment + paths
# ---------------------------------------------------------------------------


def load_env() -> None:
    """Load the nearest ancestor ``.env`` into os.environ, without overwriting.

    Idempotent, and never raises: a malformed .env must not take the run with it.
    """
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        env = parent / ".env"
        if not env.exists():
            continue
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
        except OSError:
            pass
        break


#: Marker that identifies a cap-evolve checkout, as opposed to a skills INSTALL dir.
_REPO_MARKERS = ("core/cap_evolve", "skills/_registry")


def repo_root() -> Path:
    """The cap-evolve checkout this skill lives in, or the cwd when it is not in one.

    Found by walking UP for a marker rather than counting parents. A fixed
    ``parents[4]`` is only correct in the repo layout
    (``<root>/skills/interventions/llm-proxies/spa/scripts``): ``install.sh`` copies each skill to
    ``$DEST/<name>``, so an installed tree puts this file at
    ``$DEST/spa/scripts/spa_env.py`` and ``parents[4]`` resolves to ``$HOME`` — which
    would silently point ``vendor/`` at the home directory and clone gigabytes there.
    Falling back to the cwd keeps that blast radius inside the project being run;
    ``SPA_VENDOR_DIR`` remains the explicit override for any layout.
    """
    here = Path(__file__).resolve()
    for cand in here.parents:
        if all((cand / m).is_dir() for m in _REPO_MARKERS):
            return cand
    return Path.cwd()


def vendor_dir() -> Path:
    """Where the stack's clones live. Shared across examples on purpose: cloning and
    installing both services costs minutes, and `clean` is scoped to remove only the
    subdirectories it created."""
    load_env()
    return Path(os.environ.get("SPA_VENDOR_DIR") or (repo_root() / "vendor"))


def store_dir() -> Path:
    load_env()
    return Path(os.environ.get("SKILLBERRY_STORE_DIR") or (vendor_dir() / "skillberry-store"))


def agent_dir() -> Path:
    load_env()
    return Path(os.environ.get("SKILLBERRY_AGENT_DIR") or (vendor_dir() / "skillberry-agent"))


def store_port() -> str:
    load_env()
    return os.environ.get("SKILLBERRY_STORE_PORT") or STORE_PORT_DEFAULT


def remote_env_url() -> str:
    """The benchmark's own environment service, if it has one.

    In this phase the benchmark owns that service (some runners ship an environment manager);
    core only health-checks it when a URL is configured.
    """
    load_env()
    return os.environ.get("SPA_REMOTE_ENV_URL", "")


# ---------------------------------------------------------------------------
# Process + port primitives
# ---------------------------------------------------------------------------


def _http_ok(url: str, timeout: float = 5.0) -> bool:
    """True if ``url`` answers at all (any 2xx/3xx). Never raises."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=timeout):
            return True
    except Exception:
        return False


def health_ok(port: str) -> bool:
    """Is a Skillberry service answering on ``port``?

    Tries /health, then /docs, then /: the three services in this stack do not agree
    on which of those exists, and requiring one specific path has historically been
    reported as "service failed to start" when it was merely different.
    """
    base = f"http://localhost:{port}"
    return any(_http_ok(f"{base}{p}") for p in ("/health", "/docs", "/"))


def wait_for_health(port: str, timeout: int = 60, *, interval: float = 2.0) -> bool:
    """Poll ``port`` until it answers or ``timeout`` expires."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if health_ok(port):
            return True
        time.sleep(interval)
    return False


# Liveness paths, in probe order. Services in and around this stack do not agree on
# which they expose: the store and SPA answer /health, a benchmark's environment manager
# answers /status and 404s on both /health and / — which made a perfectly healthy
# service look like a failed start. Probing a list, rather than assuming one path, is
# the difference between "not up" and "up, different surface".
LIVENESS_PATHS = ("/health", "/status", "/docs", "")


def url_reachable(url: str, *, paths: tuple[str, ...] = LIVENESS_PATHS) -> bool:
    """Does ``url`` answer on any of ``paths``? Never raises."""
    base = url.rstrip("/")
    return any(_http_ok(f"{base}{p}") for p in paths)


def wait_for_health_url(url: str, timeout: int = 45, *, interval: float = 2.0,
                        paths: tuple[str, ...] = LIVENESS_PATHS) -> bool:
    """Poll a service this runtime does not own until it answers — e.g. a benchmark's
    own environment service, whose liveness path is its own business."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if url_reachable(url, paths=paths):
            return True
        time.sleep(interval)
    return False


def _process_args(pid: int) -> str:
    """The full command line of ``pid``, or "" if unreadable. ``ps`` (not /proc) so
    this works on macOS too."""
    try:
        r = subprocess.run(["ps", "-p", str(pid), "-o", "args="],
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def _is_service_process(pid: int, markers: tuple[str, ...]) -> bool:
    """Does ``pid``'s argv contain EVERY marker? Requiring all of them is what stops
    us signalling a stranger that merely holds our port."""
    args = _process_args(pid)
    return bool(args) and all(m in args for m in markers)


def _pids_on_port(port: str) -> list[int]:
    """PIDs LISTENING on ``port``.

    ``-sTCP:LISTEN`` is essential, not cosmetic: a bare ``lsof -ti :7000`` also lists
    every process holding a CLIENT connection to that port — on a live run that
    includes cap-evolve's own runner talking to SPA, so the unfiltered form both
    reports phantom conflicts and makes a kill a way to shoot our own optimizer.
    """
    try:
        r = subprocess.run(["lsof", "-ti", f":{port}", "-sTCP:LISTEN"],
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return []
    out: list[int] = []
    for tok in r.stdout.split():
        try:
            out.append(int(tok))
        except ValueError:
            continue
    return out


def _read_pid(pid_file: str) -> Optional[int]:
    """The PID a service recorded in its sentinel, or None if absent/unreadable."""
    try:
        raw = Path(pid_file).read_text(encoding="utf-8").strip()
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return None
    except OSError as e:
        print(f"  warning: could not read {pid_file}: {e}")
        return None
    try:
        return int(raw.split()[0])
    except (ValueError, IndexError):
        print(f"  warning: {pid_file} does not contain a PID: {raw!r}")
        return None


def _terminate(pid: int, *, grace: float = 10.0) -> bool:
    """SIGTERM ``pid``, escalating to SIGKILL only if it outlives ``grace``."""
    for sig in (15, 9):
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            return True
        except PermissionError:
            print(f"  warning: not permitted to signal PID {pid}; leaving it alone")
            return False
        deadline = time.time() + (grace if sig == 15 else 5.0)
        while time.time() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
            time.sleep(0.25)
    return False


def port_owner_conflict(port: str, markers: tuple[str, ...] = SPA_PROC_MARKERS) -> Optional[str]:
    """Describe a process holding ``port`` that is NOT the expected service.

    A preflight: an occupied port then fails fast with the culprit named, instead of
    burning the whole health-check budget on a start that cannot work.
    """
    for pid in _pids_on_port(port):
        if not _is_service_process(pid, markers):
            return f"PID {pid} ({_process_args(pid) or 'unknown process'})"
    return None


def _stop_service(name: str, port: str, pid_file: str, markers: tuple[str, ...]) -> None:
    """Stop a service via its own PID sentinel; fall back to the port ONLY for a
    process whose argv confirms it.

    The sentinel is always removed, even when nothing was killed: the services'
    ``make stop`` does not remove it, and a stale sentinel makes the next ``make run``
    print "service is already running" and exit 0 without starting anything — after
    which the health check can only time out.
    """
    stopped = False
    pid = _read_pid(pid_file)
    if pid is not None and _is_service_process(pid, markers):
        stopped = _terminate(pid)
    if not stopped:
        for cand in _pids_on_port(port):
            if _is_service_process(cand, markers):
                stopped = _terminate(cand) or stopped
            else:
                print(f"  ! port {port} held by PID {cand} "
                      f"({_process_args(cand) or 'unknown process'}) — not {name}, "
                      "leaving it alone")
    Path(pid_file).unlink(missing_ok=True)
    print(f"  {'stopped' if stopped else 'not running:'} {name}")


# ---------------------------------------------------------------------------
# Provisioning
# ---------------------------------------------------------------------------


def _run(cmd: list[str] | str, *, cwd: Optional[Path] = None, env: Optional[dict] = None,
         timeout: int = 1800) -> tuple[int, str]:
    """Run a command, returning (rc, combined output tail). Shell only for strings."""
    shell = isinstance(cmd, str)
    try:
        r = subprocess.run(cmd if shell else list(cmd), shell=shell, cwd=str(cwd) if cwd else None,
                           env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return -1, f"timed out after {timeout}s"
    except (OSError, subprocess.SubprocessError) as e:
        return -1, str(e)
    return r.returncode, ((r.stdout or "") + (r.stderr or ""))[-2000:]


def _clone_at(repo: str, ref: str, dest: Path, *, ref_is_tag: bool) -> None:
    """Clone ``repo`` at ``ref`` into ``dest``, idempotently.

    A tag can be cloned shallow with --branch; a commit needs a full clone then a
    checkout. An existing checkout is left alone — remove it to change refs, which is
    what ``clean`` is for.
    """
    if (dest / ".git").is_dir():
        print(f"  ✓ {dest.name} already cloned")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    if ref_is_tag:
        rc, out = _run(["git", "clone", "--branch", ref, "--depth", "1", repo, str(dest)])
    else:
        rc, out = _run(["git", "clone", repo, str(dest)])
        if rc == 0:
            rc, out = _run(["git", "checkout", ref], cwd=dest)
    if rc != 0:
        raise RuntimeError(f"could not clone {repo} @ {ref}: {out}")
    print(f"  ✓ cloned {dest.name} @ {ref}")


def _install_service(d: Path) -> None:
    """Create the service's own py3.11 venv and install it.

    Both services ship a Makefile whose `run` target requires an ACTIVE venv, so the
    venv must live at ``<service>/.venv`` and be activated by the same shell that runs
    make — not merely referenced by interpreter path.
    """
    if not shutil.which("uv"):
        raise RuntimeError("uv is required to create the service venvs "
                           "(https://docs.astral.sh/uv/)")
    if not (d / ".venv").is_dir():
        rc, out = _run(["uv", "venv", "-p", "3.11", ".venv"], cwd=d)
        if rc != 0:
            raise RuntimeError(f"could not create py3.11 venv in {d}: {out}")
        _run(["uv", "pip", "install", "pip", "--python", ".venv/bin/python"], cwd=d)
    rc, out = _run(". .venv/bin/activate && (make install-requirements || pip install -e .)",
                   cwd=d)
    if rc != 0:
        raise RuntimeError(f"install failed in {d}: {out}")
    print(f"  ✓ installed {d.name}")


def provision(*, store_ref: Optional[str] = None, agent_ref: Optional[str] = None) -> dict:
    """Clone + install both services at their pinned refs. Idempotent.

    Returns the resolved paths so a caller can report or verify them.
    """
    load_env()
    sd, ad = store_dir(), agent_dir()
    _clone_at(STORE_REPO, store_ref or os.environ.get("SKILLBERRY_STORE_REF") or STORE_REF,
              sd, ref_is_tag=True)
    _install_service(sd)
    _clone_at(AGENT_REPO, agent_ref or os.environ.get("SKILLBERRY_AGENT_REF") or AGENT_REF,
              ad, ref_is_tag=False)
    _install_service(ad)
    return {"store_dir": str(sd), "agent_dir": str(ad)}


# ---------------------------------------------------------------------------
# Service lifecycle
# ---------------------------------------------------------------------------


def _start_detached(d: Path, env: dict, log: Path, *, extra: str = "") -> None:
    """Launch ``make run`` inside the service's venv, detached, logging to ``log``."""
    log.parent.mkdir(parents=True, exist_ok=True)
    cmd = f"cd {d} && . .venv/bin/activate && {extra}make run"
    with log.open("ab") as fh:
        subprocess.Popen(["bash", "-c", cmd], env=env, stdout=fh, stderr=fh,
                         start_new_session=True)


def start_store(*, timeout: int = 90) -> None:
    """Start the store (idempotent; a healthy store is left alone).

    ``EXECUTE_PYTHON_LOCALLY=True`` is what lets the store execute a skill's tools in
    its own process — the mechanism that makes store-hosted tools work at all.
    """
    load_env()
    port = store_port()
    if health_ok(port):
        print(f"  ✓ store already healthy on {port}")
        return
    d = store_dir()
    if not (d / ".git").is_dir():
        raise RuntimeError(f"store not provisioned at {d} — run provision() first")
    conflict = port_owner_conflict(port, STORE_PROC_MARKERS)
    if conflict:
        raise RuntimeError(f"port {port} is held by {conflict}, which is not the store")
    # A stale sentinel makes `make run` exit 0 without starting anything.
    Path(STORE_PID_FILE).unlink(missing_ok=True)
    env = os.environ.copy()
    env["EXECUTE_PYTHON_LOCALLY"] = "True"
    _start_detached(d, env, d / "store.log")
    if not wait_for_health(port, timeout):
        raise RuntimeError(f"store did not become healthy on {port} in {timeout}s "
                           f"(see {d / 'store.log'})")
    print(f"  ✓ store healthy on {port}")


def stop_store() -> None:
    _stop_service("skillberry-store", store_port(), STORE_PID_FILE, STORE_PROC_MARKERS)


def start_spa(skill_name: str, *, retries: int = 2, timeout: int = 60, **env_overrides) -> None:
    """Start SPA serving exactly ``skill_name``.

    SPA resolves ONE skill, in priority order SKILL_UUID > SKILL_NAME > a search of the
    chat history. That last fallback is silent and looks like success even against an
    EMPTY store, so ``skill_name`` is required here rather than defaulted.

    Retries on health-check timeout: a cold start occasionally loses the race.
    """
    load_env()
    if not skill_name:
        raise RuntimeError("start_spa() requires a skill_name — SPA's nameless fallback "
                           "silently searches the store and cannot be verified")
    d = agent_dir()
    if not (d / ".git").is_dir():
        raise RuntimeError(f"SPA not provisioned at {d} — run provision() first")
    if not health_ok(store_port()):
        raise RuntimeError(f"the store is not healthy on {store_port()}; SPA resolves its "
                           "skill through the store, so start the store first")

    conflict = port_owner_conflict(SPA_PORT)
    if conflict:
        raise RuntimeError(
            f"port {SPA_PORT} is held by {conflict}, which is not SPA. SPA's port is fixed "
            f"at {SPA_PORT}, so free it and retry. (On macOS, ControlCenter holds 7000 for "
            "AirPlay Receiver by default: System Settings > General > AirDrop & Handoff.)")

    env = os.environ.copy()
    env["SKILL_NAME"] = skill_name
    env.pop("SKILL_UUID", None)          # else it silently outranks SKILL_NAME
    for k, v in SPA_ENV_DEFAULTS.items():
        env.setdefault(k, v)
    for k, v in env_overrides.items():
        env[str(k)] = str(v)

    for attempt in range(1 + retries):
        Path(SPA_PID_FILE).unlink(missing_ok=True)
        _start_detached(d, env, d / "proxy-agent.log")
        if wait_for_health(SPA_PORT, timeout):
            print(f"  ✓ SPA healthy on {SPA_PORT} (SKILL_NAME={skill_name})")
            return
        if attempt < retries:
            stop_spa()
            time.sleep(3)
    raise RuntimeError(f"SPA did not become healthy on {SPA_PORT} with SKILL_NAME="
                       f"{skill_name} after {1 + retries} attempts "
                       f"(see {d / 'proxy-agent.log'})")


def stop_spa() -> None:
    """Stop SPA. Stopping its PID releases 7001 too — one process binds both."""
    _stop_service("skillberry-proxy-agent", SPA_PORT, SPA_PID_FILE, SPA_PROC_MARKERS)


def restart_spa(skill_name: str, **env_overrides) -> None:
    """Stop SPA and start it again so it re-reads its skill from the store."""
    stop_spa()
    time.sleep(2)
    start_spa(skill_name, **env_overrides)


def status() -> dict:
    """A snapshot of the stack: per service, whether it is up and who owns its port."""
    load_env()
    rows = {
        "store": {"port": store_port(), "pid_file": STORE_PID_FILE, "markers": STORE_PROC_MARKERS,
                  "dir": str(store_dir())},
        "spa": {"port": SPA_PORT, "pid_file": SPA_PID_FILE, "markers": SPA_PROC_MARKERS,
                "dir": str(agent_dir())},
    }
    out: dict = {}
    for name, r in rows.items():
        pids = _pids_on_port(r["port"])
        out[name] = {
            "port": r["port"],
            "healthy": health_ok(r["port"]),
            "pids": pids,
            "ours": [p for p in pids if _is_service_process(p, r["markers"])],
            "provisioned": (Path(r["dir"]) / ".git").is_dir(),
            "dir": r["dir"],
        }
    url = remote_env_url()
    out["remote_env"] = {"url": url, "healthy": bool(url) and url_reachable(url)}
    return out


# ---------------------------------------------------------------------------
# Routing — where a caller reaches SPA
# ---------------------------------------------------------------------------


def docker_bridge_ip() -> str:
    """The Docker bridge gateway, i.e. the host as seen from inside a container.

    Linux/WSL2 only; macOS/Windows use host.docker.internal. Falls back to the usual
    172.17.0.1 when docker cannot be queried.
    """
    rc, out = _run(["docker", "network", "inspect", "bridge", "--format",
                    "{{range .IPAM.Config}}{{.Gateway}}{{end}}"], timeout=15)
    # _run merges stdout and stderr, so the last line can be a docker WARNING rather
    # than the gateway. Taking it verbatim produced URLs like
    # "http://WARNING: ...:7000", which fail from inside a container in a way that
    # looks like a networking problem. Accept only a line that IS an IPv4 address.
    ip = ""
    if rc == 0:
        for line in reversed(out.splitlines()):
            cand = line.strip()
            if re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", cand):
                ip = cand
                break
    return ip or "172.17.0.1"


def spa_base_url(*, from_container: bool = False) -> str:
    """SPA's OpenAI-compatible endpoint, addressed for the caller's vantage point.

    A container cannot reach the host on localhost, and SPA must bind 0.0.0.0 for the
    container-facing form to work at all.
    """
    load_env()
    explicit = os.environ.get("SPA_BASE_URL")
    if explicit:
        return explicit
    if not from_container:
        return f"http://localhost:{SPA_PORT}"
    host = os.environ.get("SPA_CONTAINER_HOST") or docker_bridge_ip()
    return f"http://{host}:{SPA_PORT}"


def upstream_llm_args(*, include_api_key: bool = False) -> dict:
    """litellm args for talking DIRECTLY to the provider — the call paths that must
    never be proxied (a user simulator, an LLM judge, a verifier).

    Routing those through SPA would inject the capability into the simulated user or
    let it influence its own score, so this is a correctness boundary, not a detail.

    **The API KEY IS NOT IN THE RETURNED DICT BY DEFAULT — deliberately.** These args get
    handed to a benchmark runner, and a runner is entitled to record the config it was
    given: a runner may write ``llm_args`` verbatim into its results file, e.g. under
    ``info.agent_info.llm_args`` / ``info.user_info.llm_args``. That file is exactly what
    the runtime asks adapters to persist and expose through ``trajectories()``, and
    cap-evolve then copies it VERBATIM into the optimizer's working dir every iteration
    while ``store: git`` commits it. A key placed in this dict therefore becomes a
    committed secret that was also shipped to the optimizer. This was observed for real on
    a benchmark baseline, not theorised.

    Omitting it costs nothing on the normal path: litellm resolves the credential from
    ``OPENAI_API_KEY`` in the environment for the ``openai/`` route, and ``load_env()``
    has already put it there. The key is still VALIDATED here, so a missing credential
    fails loudly at config time rather than as a wall of 401s mid-run.

    Pass ``include_api_key=True`` only for a client that cannot read the environment
    (a raw HTTP call, a non-litellm SDK) AND whose args are never persisted. If you do,
    you own redacting whatever they end up inside.
    """
    load_env()
    base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not base_url:
        raise RuntimeError("OPENAI_BASE_URL (or OPENAI_API_BASE) not set — put it in .env")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set — put it in .env")
    # Make the env-var path litellm actually reads explicit, so a caller that relies on
    # the key NOT being in the dict still authenticates when .env was the only source.
    os.environ.setdefault("OPENAI_API_KEY", api_key)
    args = {"api_base": base_url}
    if include_api_key:
        args["api_key"] = api_key
    return args


# ---------------------------------------------------------------------------
# Store: deploying a capability
# ---------------------------------------------------------------------------


def _store_url(path: str) -> str:
    return f"http://localhost:{store_port()}{path}"


def _curl(args: list[str], timeout: int = 60) -> tuple[int, str]:
    """Run curl and return (http_status, body). Status -1 means curl itself failed."""
    try:
        r = subprocess.run(["curl", "-s", "-w", "\n%{http_code}", *args],
                           capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return -1, ""
    if r.returncode != 0:
        return -1, r.stdout
    body, _, status = r.stdout.rpartition("\n")
    try:
        return int(status.strip()), body
    except ValueError:
        return -1, body


def _list(kind: str, tags: Optional[str] = None) -> list:
    """GET /<kind>/ as a list of rows.

    The store returns a BARE LIST when neither limit nor offset is passed and an
    ``{items, total, ...}`` envelope otherwise; both shapes are handled. [] if the
    store cannot be reached.
    """
    q = "?fields=wide" + (f"&tags={tags}" if tags else "")
    status, body = _curl(["-X", "GET", _store_url(f"/{kind}/{q}")])
    if status != 200:
        return []
    try:
        data = json.loads(body)
    except ValueError:
        return []
    if isinstance(data, dict):
        data = data.get("items") or data.get(kind) or []
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


def _delete_object(kind: str, uuid: str) -> bool:
    """DELETE /<kind>s/<uuid>. A 404 counts as already gone."""
    status, _ = _curl(["-X", "DELETE", _store_url(f"/{kind}s/{uuid}")])
    return status in (200, 204, 404)


class Protection:
    """Which store tools must survive a redeploy — the benchmark's frozen substrate.

    A benchmark may keep standalone tools in the store that its skill's tools call by
    name (the benchmark's frozen primitives). Those belong to no skill manifest and must never be
    deleted when the skill is replaced. Protection is declared by the caller, by any
    of three independent markers; ANY match spares a tool.
    """

    def __init__(self, tags: tuple[str, ...] = (), names: tuple[str, ...] = (),
                 modules: tuple[str, ...] = ()):
        self.tags = tuple(tags)
        self.names = frozenset(names)
        self.modules = frozenset(modules)

    def __bool__(self) -> bool:
        return bool(self.tags or self.names or self.modules)

    def covers(self, tool: dict) -> bool:
        if any(t in (tool.get("tags") or []) for t in self.tags):
            return True
        if str(tool.get("name") or "") in self.names:
            return True
        return str(tool.get("module_name") or "") in self.modules

    def present_names(self) -> set:
        """Names of protected tools currently in the store, by tag.

        A before/after tripwire around destructive operations. Empty when the store is
        unreachable, in which case the caller skips the comparison rather than raising
        a false alarm.
        """
        found: set = set()
        for tag in self.tags:
            found |= {str(r["name"]) for r in _list("tools", tags=tag) if r.get("name")}
        return found


def delete_skill(skill_name: str, protect: Optional[Protection] = None) -> bool:
    """Delete a skill together with ALL of its own tools and snippets.

    The store's own cascade cannot be used. ``DELETE /skills/<name>?delete_tools=true``
    runs the tool cascade while the skill is STILL registered as a dependent of its own
    tools, so every ``tools_service.delete`` raises ObjectInUseError, which the cascade
    swallows as a warning: the skill goes away, the tools silently survive, and the next
    import mints fresh UUIDs under the same names — orphaning one full tool set per
    iteration. So the order that actually works:

      1. GET the manifest to collect tool_uuids / snippet_uuids
      2. DELETE the skill (no cascade) — this releases the dependency
      3. DELETE each tool and snippet, now that nothing depends on them

    FAIL CLOSED: a tool whose metadata cannot be read is KEPT, not deleted. Leaking a
    stale wrapper is cheap; deleting a protected primitive corrupts the run.

    A missing skill (404) is success — callers always delete-then-import.
    """
    protect = protect or Protection()
    before = protect.present_names()

    status, body = _curl(["-X", "GET", _store_url(f"/skills/{skill_name}?fields=wide")])
    if status == 404:
        return True
    if status != 200:
        return False
    try:
        manifest = json.loads(body)
    except ValueError:
        return False

    deletable: list[str] = []
    for tu in list(manifest.get("tool_uuids") or []):
        t_status, t_body = _curl(["-X", "GET", _store_url(f"/tools/{tu}?fields=wide")])
        if t_status != 200:
            continue                      # unreadable -> keep
        try:
            tool = json.loads(t_body)
        except ValueError:
            continue                      # unparseable -> keep
        if protect.covers(tool):
            continue                      # protected -> keep
        deletable.append(tu)

    status, _ = _curl(["-X", "DELETE", _store_url(f"/skills/{skill_name}")])
    if status not in (200, 204, 404):
        return False

    ok = True
    for tu in deletable:
        ok &= _delete_object("tool", tu)
    for su in list(manifest.get("snippet_uuids") or []):
        ok &= _delete_object("snippet", su)

    after = protect.present_names()
    if before and not before.issubset(after):
        raise RuntimeError(
            f"delete_skill({skill_name}) removed protected tools: {sorted(before - after)}. "
            "The store is now inconsistent — re-run the example's setup to re-import them.")
    return ok


def purge_orphans(protect: Optional[Protection] = None) -> bool:
    """Delete every unprotected tool and every snippet.

    Call only AFTER the skill is gone: at that point any surviving unprotected tool is
    an orphan from an earlier run, and orphans are harmful — they pollute listings and
    make the store's name-based dependency resolution ambiguous for the next import.
    """
    protect = protect or Protection()
    ok = True
    for row in _list("tools"):
        uuid = row.get("uuid")
        if not uuid or protect.covers(row):
            continue
        ok &= _delete_object("tool", uuid)
    for row in _list("snippets"):
        uuid = row.get("uuid")
        if uuid:
            ok &= _delete_object("snippet", uuid)
    return ok


def upload_skill(skill_dir: str | Path) -> bool:
    """Import a skill directory into the store (POST /skills/import-anthropic).

    Every public top-level function in each ``scripts/*.py`` becomes one store tool, and
    the store auto-detects a tool's dependency on any protected tool it calls by bare
    name — so the protected substrate must already be registered when this runs.
    """
    d = Path(skill_dir).resolve()
    if not (d / "SKILL.md").exists():
        print(f"  ! {d} has no SKILL.md")
        return False
    status, body = _curl(["-X", "POST", _store_url("/skills/import-anthropic"),
                          "-F", "source_type=folder", "-F", f"folder_path={d}",
                          "-F", "snippet_mode=file"], timeout=180)
    if status != 200:
        print(f"  ! import of {d.name} returned HTTP {status}: {body[:300]}")
        return False
    try:
        resp = json.loads(body)
    except ValueError:
        return False
    return resp.get("success") is True or bool(resp.get("skill_name"))


def reset_store_to_skill(skill_dir: str | Path, skill_name: str,
                         protect: Optional[Protection] = None) -> None:
    """Make ``skill_dir`` the ONLY skill in the store, from a clean slate.

    The single entry point an adapter's ``apply()`` needs. Because cap-evolve calls
    ``live()`` -> ``apply()`` before EVERY evaluation and hands the baseline the seed,
    this is also what guarantees each run starts against a store refreshed from the
    seed rather than from whatever the previous run left behind.

    Raises RuntimeError on any failure, so a corrupt store stops the candidate instead
    of silently scoring the wrong tool set. Callers must translate that into a
    per-candidate infra error rather than letting it escape ``live()``.
    """
    protect = protect or Protection()
    d = Path(skill_dir)
    if not delete_skill(skill_name, protect):
        raise RuntimeError(f"could not remove existing skill {skill_name} from the store")
    if not purge_orphans(protect):
        raise RuntimeError("could not purge leftover unprotected tools/snippets")
    if not upload_skill(d):
        raise RuntimeError(f"could not import skill from {d}")


def public_functions(module_path: str | Path) -> list[str]:
    """Top-level public function names in a .py file, by AST (no import, no execution).

    The leading-underscore filter is the convention the store's own importer uses: an
    ``_``-prefixed helper stays internal, while every public top-level function becomes
    a tool the model can see.
    """
    import ast

    src = Path(module_path).read_text(encoding="utf-8")
    tree = ast.parse(src)
    return [n.name for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not n.name.startswith("_")]


def import_standalone_tools(module_path: str | Path, *, tags: tuple[str, ...] = ()) -> list[str]:
    """Register every public function of ``module_path`` as a STANDALONE store tool.

    Standalone means: belonging to no skill manifest, so a skill redeploy cannot cascade
    into them. This is how a benchmark installs the frozen substrate its skill's tools
    call by name. Tagging them is what lets ``Protection`` recognise them later.

    Returns the names imported; raises if any failed, since a partial substrate produces
    a silently wrong tool set rather than an error.
    """
    p = Path(module_path).resolve()
    names = public_functions(p)
    if not names:
        raise RuntimeError(f"no public functions found in {p}")
    failed: list[str] = []
    for name in names:
        status, body = _curl(["-X", "POST",
                              _store_url(f"/tools/add?selected_func={name}&update=true"),
                              "-F", f"tool=@{p}"], timeout=120)
        if status != 200 or '"uuid"' not in body:
            failed.append(name)
            continue
        if tags:
            t_status, t_body = _curl(["-X", "GET", _store_url(f"/tools/{name}")])
            if t_status == 200:
                try:
                    tool = json.loads(t_body)
                except ValueError:
                    tool = None
                if tool is not None:
                    tool["tags"] = list(tags)
                    _curl(["-X", "PUT", _store_url(f"/tools/{name}"),
                           "-H", "Content-Type: application/json",
                           "-d", json.dumps(tool)])
    if failed:
        raise RuntimeError(f"could not import standalone tools: {failed}")
    return names


def purge_store() -> bool:
    """Wipe the store completely (DELETE /admin/purge-all). Used by a cold setup."""
    status, _ = _curl(["-X", "DELETE", _store_url("/admin/purge-all")])
    return status in (200, 204)


# ---------------------------------------------------------------------------
# Teardown
#
# Deleting clones is the most destructive thing in this module, so the guards live
# here (importable, unit-testable offline) rather than in a caller's shell script.
# ---------------------------------------------------------------------------


def safe_rm(target: str | Path, label: str) -> bool:
    """Recursively remove ``target`` only if it is a path we are allowed to destroy.

    ``set -u``-style discipline does not help here: the paths are always *set*, just
    potentially wrong, so a mis-resolved root would aim a recursive delete at something
    real. Refusals raise rather than warn — a teardown that silently skipped its target
    is indistinguishable from one that removed the wrong thing.

    Never removed: ``/``, ``$HOME``, the repo root, anything at or under ``.capevolve``
    (run artifacts — those are *measurements*) or ``.venv`` (shared with other examples),
    and anything outside the repo.
    """
    repo = repo_root()
    if not (repo / "core" / "cap_evolve").is_dir():
        raise RuntimeError(f"{repo} does not look like the cap-evolve checkout — "
                           "refusing to delete anything")
    t = Path(target)
    resolved = t.resolve() if t.exists() else Path(os.path.abspath(str(t)))
    if resolved in (Path("/"), Path.home(), repo):
        raise RuntimeError(f"refusing to remove {resolved} ({label})")
    for keep in (repo / ".capevolve", repo / ".venv"):
        if resolved == keep or keep in resolved.parents:
            raise RuntimeError(f"refusing to touch {keep.name} ({label})")
    if repo not in resolved.parents:
        raise RuntimeError(f"refusing to remove {resolved} — outside {repo} ({label})")
    if not resolved.exists():
        print(f"  - {label} not present")
        return False
    shutil.rmtree(resolved, ignore_errors=True)
    print(f"  ✓ removed {label}")
    return True


def stop_all() -> None:
    """Stop the stack in reverse startup order (SPA resolves its skill via the store)."""
    stop_spa()
    stop_store()


def clean(*, keep_clones: bool = False) -> None:
    """Stop everything, clear the PID sentinels, and (unless asked not to) drop the clones.

    ``vendor/`` itself is removed only when it ends up empty — other examples keep their
    own checkouts there.
    """
    stop_all()
    for pf in (SPA_PID_FILE, STORE_PID_FILE):
        Path(pf).unlink(missing_ok=True)
    print("  ✓ PID sentinels cleared")
    if keep_clones:
        print("  - clones kept")
        return
    safe_rm(store_dir(), "vendor/skillberry-store")
    safe_rm(agent_dir(), "vendor/skillberry-agent")
    vd = vendor_dir()
    if vd.is_dir():
        rest = sorted(p.name for p in vd.iterdir())
        if rest:
            print(f"  - vendor/ kept (still holds: {' '.join(rest)})")
        else:
            vd.rmdir()
            print("  ✓ removed empty vendor/")
    print("  NOT touched: .capevolve/ (run artifacts) and .venv/ (shared)")
