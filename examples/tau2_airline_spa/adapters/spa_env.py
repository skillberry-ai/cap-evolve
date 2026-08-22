"""SPA (Skillberry Proxy-Agent) environment wiring for tau2 airline.

Replaces the RITS module from the original tau2_airline example. Points tau2's
litellm calls at SPA (localhost:7000) for the agent, while the user simulator
calls the upstream LLM directly via OPENAI_BASE_URL.

Provides service lifecycle helpers: restart_spa() stops SPA, sets SKILL_NAME,
restarts, and waits for the health check — used by adapter.apply() before each
evaluation.

Store helpers: delete_skill() removes the single skill together with ALL of its
tools and snippets, so upload_skill() can re-import the optimizer's modified
version under the same name without orphaning anything. The frozen primitive
tools are never touched — they belong to no skill manifest, and a tag check
guards them regardless.

LAZY: no network at import time, so ``cap-evolve check`` stays offline.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Optional

# Default model strings (env-overridable).
_DEFAULT_AGENT_MODEL = "ibm/skillberry-local"
_DEFAULT_USER_MODEL = "openai/aws/gpt-oss-120b"

# Ports
SPA_PORT = "7000"
STORE_PORT = "8000"

# SPA records its service PID here. This is the
# authoritative handle on the process we started — always prefer it to guessing
# from whoever happens to own the port.
SPA_PID_FILE = "/tmp/skillberry-agent-service.pid"

# The one and only skill in the store. Never renamed — the optimizer modifies it
# in place, and apply() always deletes + re-imports it under this exact name.
SKILL_NAME = "airline_skill"

_SPA_DIR: Optional[str] = None
_STORE_DIR: Optional[str] = None


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


def _get_spa_dir() -> str:
    """Resolve the skillberry-agent directory."""
    global _SPA_DIR
    if _SPA_DIR is None:
        _load_env()
        _SPA_DIR = os.environ.get("SKILLBERRY_AGENT_DIR", "")
    return _SPA_DIR


def _get_store_dir() -> str:
    """Resolve the skillberry-store directory."""
    global _STORE_DIR
    if _STORE_DIR is None:
        _load_env()
        _STORE_DIR = os.environ.get("SKILLBERRY_STORE_DIR", "")
    return _STORE_DIR


# ---------------------------------------------------------------------------
# Model selection
# ---------------------------------------------------------------------------


def agent_model() -> str:
    """litellm model string for the agent under test (default: ibm/skillberry-local)."""
    _load_env()
    return os.environ.get("TAU2_AGENT_MODEL") or _DEFAULT_AGENT_MODEL


def user_model() -> str:
    """litellm model string for the user simulator (default: openai/aws/gpt-oss-120b)."""
    _load_env()
    return os.environ.get("TAU2_USER_MODEL") or _DEFAULT_USER_MODEL


def _is_spa_routed(model: str) -> bool:
    """True if this model routes through SPA (not directly to upstream)."""
    m = (model or "").lower()
    return "skillberry" in m or m == _DEFAULT_AGENT_MODEL.lower()


def llm_args_for(model: str) -> dict:
    """Per-model litellm args: SPA-routed models → localhost:7000; others → upstream."""
    _load_env()
    if _is_spa_routed(model):
        return _spa_llm_args()
    return _upstream_llm_args()


def _spa_llm_args() -> dict:
    """litellm args pointing at SPA on localhost.

    NOTE: Do NOT pass api_key here — tau2's llm_utils already sets api_key="EMPTY"
    for the skillberry model path and passing it in kwargs causes a duplicate error.
    """
    return {
        "temperature": 0.0,
    }


def _upstream_llm_args() -> dict:
    """litellm args for direct upstream access (user simulator)."""
    base_url = os.environ.get("OPENAI_BASE_URL")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not base_url:
        raise RuntimeError(
            "OPENAI_BASE_URL not set. Put it in the repo-root .env or export it."
        )
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Put it in the repo-root .env or export it."
        )
    return {
        "api_base": base_url,
        "api_key": api_key,
        "temperature": 0.0,
    }


# ---------------------------------------------------------------------------
# Service lifecycle
# ---------------------------------------------------------------------------


def _wait_for_health(port: str, timeout: int = 60) -> bool:
    """Poll localhost:<port>/health until responsive or timeout."""
    import urllib.request

    deadline = time.time() + timeout
    url = f"http://localhost:{port}/health"
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5):
                return True
        except Exception:
            time.sleep(2)
    return False


def _read_spa_pid() -> "int | None":
    """The PID SPA recorded in its sentinel, or None if absent/unreadable."""
    try:
        raw = Path(SPA_PID_FILE).read_text(encoding="utf-8").strip()
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return None
    except OSError as e:
        print(f"  warning: could not read {SPA_PID_FILE}: {e}")
        return None
    try:
        return int(raw.split()[0])
    except (ValueError, IndexError):
        print(f"  warning: {SPA_PID_FILE} does not contain a PID: {raw!r}")
        return None


def _process_args(pid: int) -> str:
    """The full command line of ``pid``, or "" if it cannot be read.

    ``ps`` rather than /proc so this also works on macOS.
    """
    try:
        r = subprocess.run(
            ["ps", "-p", str(pid), "-o", "args="],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def _is_spa_process(pid: int) -> bool:
    """Is ``pid`` really the SPA service, and not some unrelated port squatter?

    SPA is started by ``make run`` as ``python -m main`` from the agent checkout
    (``skillberry-agent/.mk/local.mk: SERVICE_ENTRY_MODULE := main``). Requiring
    both markers is what stops us SIGKILLing a stranger that merely holds 7000 —
    on macOS that is ``ControlCenter`` (AirPlay Receiver), a system process.
    """
    args = _process_args(pid)
    if not args:
        return False
    return "python" in args and "-m main" in args


def _pids_on_port(port: str) -> "list[int]":
    """PIDs LISTENING on ``port`` (empty if lsof is unavailable or finds nothing).

    ``-sTCP:LISTEN`` is essential, not cosmetic: a bare ``lsof -ti :7000`` also lists
    every process with an open CLIENT connection to that port. On a live run that
    includes cap-evolve's own hill-climb runner talking to SPA — so the unfiltered
    form both reports phantom port conflicts and, in the code this replaces, made
    ``kill -9`` a way to shoot our own optimizer.
    """
    try:
        r = subprocess.run(
            ["lsof", "-ti", f":{port}", "-sTCP:LISTEN"],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    out: list[int] = []
    for tok in r.stdout.split():
        try:
            out.append(int(tok))
        except ValueError:
            continue
    return out


def _terminate(pid: int, *, grace: float = 10.0) -> bool:
    """SIGTERM ``pid``, escalate to SIGKILL if it outlives ``grace`` seconds.

    SIGTERM first so SPA can shut down cleanly (this is what SPA's own
    ``stop-service.sh`` sends). Returns True once the process is gone.
    """
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


def port_owner_conflict(port: str) -> "str | None":
    """Describe a NON-SPA process holding ``port``, or None if the port is free/ours.

    Used as a preflight so an occupied port fails fast with the culprit named,
    instead of burning the whole health-check budget on a start that cannot work.
    """
    for pid in _pids_on_port(port):
        if not _is_spa_process(pid):
            return f"PID {pid} ({_process_args(pid) or 'unknown process'})"
    return None


def stop_spa() -> None:
    """Stop the SPA service, killing ONLY the process SPA itself recorded.

    Order matters:

      1. The sentinel PID is authoritative — SPA's own ``start-service.sh`` wrote it,
         so it identifies the process we started rather than whoever owns the port.
      2. Fall back to the port ONLY when there is no usable sentinel, and even then
         kill a PID only once ``_is_spa_process`` confirms it. A bare
         ``os.kill(pid, 9)`` on the port owner would SIGKILL macOS's ControlCenter,
         which holds 7000 for AirPlay Receiver by default.
      3. Always remove the sentinel. SPA's ``make stop`` does NOT remove it, and a
         stale sentinel makes the next ``make run`` print "service is already
         running" and exit 0 without starting anything — after which the health
         check can only time out.
    """
    pid = _read_spa_pid()
    if pid is not None:
        if _is_spa_process(pid):
            _terminate(pid)
        else:
            # Sentinel outlived its process (or the PID was recycled). Nothing to
            # kill; step 3 clears the file.
            pass
    else:
        for cand in _pids_on_port(SPA_PORT):
            if _is_spa_process(cand):
                _terminate(cand)
            else:
                print(
                    f"  warning: port {SPA_PORT} is held by PID {cand} "
                    f"({_process_args(cand) or 'unknown process'}), which is not SPA — "
                    "refusing to kill it. Free the port and retry."
                )

    Path(SPA_PID_FILE).unlink(missing_ok=True)


def start_spa(skill_name: str = SKILL_NAME, *, retries: int = 2) -> None:
    """Start SPA with the given SKILL_NAME.

    Runs inside the service's own venv (make run requires an active venv).
    Retries up to `retries` times on health-check timeout (transient failures).
    """
    spa_dir = _get_spa_dir()
    if not spa_dir or not Path(spa_dir).is_dir():
        raise RuntimeError(
            f"SKILLBERRY_AGENT_DIR not set or not a directory: {spa_dir!r}"
        )

    env = os.environ.copy()
    env["SKILL_NAME"] = skill_name
    env.setdefault("SPA_PROVIDER_NAME", "litellm")
    env.setdefault("SPA_MODEL_NAME", _DEFAULT_USER_MODEL)
    env.setdefault("USE_AGENT_TOOLS", "false")
    env.setdefault("USE_AGENT_PROMPTS", "true")
    env.setdefault("MCP_PROMPTS_POSITION", "postfix")

    conflict = port_owner_conflict(SPA_PORT)
    if conflict:
        raise RuntimeError(
            f"port {SPA_PORT} is already held by {conflict}, which is not SPA. "
            f"SPA's port is fixed at {SPA_PORT} (tau2 and SPA hardcode it), so free "
            "the port and retry."
        )

    port = SPA_PORT
    cmd = f"cd {spa_dir} && . .venv/bin/activate && make run"

    for attempt in range(1 + retries):
        subprocess.Popen(
            ["bash", "-c", cmd],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if _wait_for_health(port, timeout=60):
            return
        if attempt < retries:
            stop_spa()
            time.sleep(3)

    raise RuntimeError(
        f"SPA failed to start with SKILL_NAME={skill_name} on port {port} "
        f"after {1 + retries} attempts"
    )


def restart_spa(skill_name: str = SKILL_NAME) -> None:
    """Stop SPA, then restart it so it re-reads the skill from the store."""
    stop_spa()
    time.sleep(2)
    start_spa(skill_name)


# ---------------------------------------------------------------------------
# Store interaction
# ---------------------------------------------------------------------------


def _store_url(path: str) -> str:
    """Absolute store URL for a path like ``/skills/airline_skill``."""
    port = os.environ.get("SKILLBERRY_STORE_PORT", STORE_PORT)
    return f"http://localhost:{port}{path}"


PRIMITIVE_TAG = "primitive-tool"

# The frozen primitive tools. These are imported standalone from
# seed_capability/primitive_tools/functions.py and MUST NEVER be deleted or
# modified — every wrapper in airline_skill depends on them. Belt-and-braces:
# a tool is protected if it carries the tag, OR its name is in this set, OR it
# came from the primitive module. Any one match is enough to spare it.
PRIMITIVE_MODULE = "functions.py"
PRIMITIVE_TOOL_NAMES = frozenset({
    "book_reservation",
    "calculate",
    "cancel_reservation",
    "get_reservation_details",
    "get_user_details",
    "list_all_airports",
    "search_direct_flight",
    "search_onestop_flight",
    "send_certificate",
    "update_reservation_baggages",
    "update_reservation_flights",
    "update_reservation_passengers",
    "get_flight_status",
    "transfer_to_human_agents",
})


def _is_protected(tool: dict) -> bool:
    """True if this tool is a frozen primitive and must never be deleted."""
    if PRIMITIVE_TAG in (tool.get("tags") or []):
        return True
    if str(tool.get("name") or "") in PRIMITIVE_TOOL_NAMES:
        return True
    if str(tool.get("module_name") or "") == PRIMITIVE_MODULE:
        return True
    return False


def _curl(args: list[str], timeout: int = 60) -> "tuple[int, str]":
    """Run curl and return (http_status, body). Status -1 means curl itself failed."""
    try:
        result = subprocess.run(
            ["curl", "-s", "-w", "\n%{http_code}", *args],
            capture_output=True, text=True, timeout=timeout,
        )
    except Exception:
        return -1, ""
    if result.returncode != 0:
        return -1, result.stdout
    body, _, status = result.stdout.rpartition("\n")
    try:
        return int(status.strip()), body
    except ValueError:
        return -1, body


def _delete_object(kind: str, uuid: str) -> bool:
    """DELETE /<kind>s/<uuid>. A 404 counts as already gone."""
    status, _ = _curl(["-X", "DELETE", _store_url(f"/{kind}s/{uuid}")])
    return status in (200, 204, 404)


def _list(kind: str, tags: "str | None" = None) -> list:
    """GET /<kind>/ and return the rows as a list of dicts.

    The store returns a BARE LIST when neither ``limit`` nor ``offset`` is passed,
    and an ``{items, total, offset, limit}`` envelope otherwise; both are handled.
    Returns [] if the store cannot be reached.
    """
    import json

    q = f"?fields=wide" + (f"&tags={tags}" if tags else "")
    status, body = _curl(["-X", "GET", _store_url(f"/{kind}/{q}")])
    if status != 200:
        return []
    try:
        data = json.loads(body)
    except Exception:
        return []
    if isinstance(data, dict):
        data = data.get("items") or data.get(kind) or []
    return [r for r in data if isinstance(r, dict)] if isinstance(data, list) else []


def _primitive_names() -> set:
    """Names of every tool currently tagged ``primitive-tool`` in the store.

    Used as a before/after tripwire around destructive operations. Returns an
    empty set if the store cannot be reached, in which case the caller skips the
    comparison rather than reporting a false alarm.
    """
    return {str(r["name"]) for r in _list("tools", tags=PRIMITIVE_TAG) if r.get("name")}


def purge_non_primitive_content() -> bool:
    """Delete every tool that is not a frozen primitive, and every snippet.

    Call this only AFTER the skill has been deleted: at that point any surviving
    non-primitive tool is an orphan (a wrapper from an earlier run whose skill is
    gone), and orphans are harmful — they linger in the store, pollute listings,
    and make name-based dependency resolution ambiguous for the next import.

    Primitives are protected by ``_is_protected`` and are never touched. Tools whose
    metadata cannot be read are left alone (fail closed).
    """
    ok = True
    for row in _list("tools"):
        uuid = row.get("uuid")
        if not uuid or _is_protected(row):
            continue
        ok &= _delete_object("tool", uuid)
    for row in _list("snippets"):
        uuid = row.get("uuid")
        if uuid:
            ok &= _delete_object("snippet", uuid)
    return ok


def reset_store_to_skill(skill_dir: "str | Path", skill_name: str = SKILL_NAME) -> None:
    """Make ``skill_dir`` the ONLY skill in the store, from a clean slate.

    This is the single entry point used before every evaluation, so each run —
    starting with the baseline, which is handed the seed — begins against a store
    that holds exactly the frozen primitives plus this one skill:

      1. delete the current skill together with its own tools and snippets
      2. purge any leftover non-primitive tools/snippets (orphans from prior runs)
      3. import ``skill_dir`` fresh
      4. verify the frozen primitives are all still present

    Raises RuntimeError if any step fails, so a corrupt store stops the run instead
    of silently scoring a wrong tool set.
    """
    skill_dir = Path(skill_dir)
    before = _primitive_names()

    if not delete_skill(skill_name):
        raise RuntimeError(f"could not remove existing skill {skill_name} from the store")
    if not purge_non_primitive_content():
        raise RuntimeError("could not purge leftover non-primitive tools/snippets")
    if not upload_skill(skill_dir):
        raise RuntimeError(f"could not import skill from {skill_dir}")

    after = _primitive_names()
    if before and not before.issubset(after):
        raise RuntimeError(
            f"frozen primitive tools disappeared during reset: {sorted(before - after)}. "
            "Re-run setup.sh to re-import them."
        )


def delete_skill(skill_name: str = SKILL_NAME) -> bool:
    """Delete a skill together with ALL of its tools and snippets.

    Ordering matters, and the store's own cascade cannot be used:

    ``DELETE /skills/<name>?delete_tools=true`` runs its tool cascade while the
    skill is STILL registered as a dependent of its own tools, so every
    ``tools_service.delete`` raises ``ObjectInUseError``, which the cascade
    swallows as a warning. The skill goes away, the tools silently survive, and
    ``deleted_tools`` comes back empty. Re-importing then mints fresh UUIDs under
    the same names, orphaning the originals — ~14 stale tools per iteration.

    So we do it in the order that works:
      1. GET the manifest to collect ``tool_uuids`` / ``snippet_uuids``
      2. DELETE the skill (no cascade) — this frees the dependency
      3. DELETE each tool and snippet, now that nothing depends on them

    Primitives are NEVER deleted. They belong to no skill manifest so they should
    not appear here at all, but the checks are deliberately paranoid: a tool is
    spared if ``_is_protected`` matches, and — critically — it is also spared when
    its metadata cannot be read. Unknown means keep (fail closed): we would rather
    leak a stale wrapper than delete a primitive. The primitive set is re-verified
    after the deletions and the call fails if any went missing.

    A missing skill (404) is success — callers always delete-then-import.

    Returns True if the skill and all of its own tools/snippets are gone AND every
    primitive is still present.
    """
    import json

    before = _primitive_names()

    # 1. Read the manifest before removing it.
    status, body = _curl(["-X", "GET", _store_url(f"/skills/{skill_name}?fields=wide")])
    if status == 404:
        return True                        # nothing in the store yet
    if status != 200:
        return False
    try:
        manifest = json.loads(body)
    except Exception:
        return False
    tool_uuids = list(manifest.get("tool_uuids") or [])
    snippet_uuids = list(manifest.get("snippet_uuids") or [])

    # Decide what may be deleted BEFORE touching anything. Fail closed: a tool
    # whose metadata we cannot read is treated as protected.
    deletable: list[str] = []
    for tu in tool_uuids:
        t_status, t_body = _curl(["-X", "GET", _store_url(f"/tools/{tu}?fields=wide")])
        if t_status != 200:
            continue                       # unreadable -> keep
        try:
            tool = json.loads(t_body)
        except Exception:
            continue                       # unparseable -> keep
        if _is_protected(tool):
            continue                       # primitive -> keep
        deletable.append(tu)

    # 2. Delete the skill itself — releases its hold on the tools/snippets.
    status, _ = _curl(["-X", "DELETE", _store_url(f"/skills/{skill_name}")])
    if status not in (200, 204, 404):
        return False

    # 3. Now the tools and snippets can actually be removed.
    ok = True
    for tu in deletable:
        ok &= _delete_object("tool", tu)
    for su in snippet_uuids:
        ok &= _delete_object("snippet", su)

    # 4. Verify we did not disturb the frozen primitives.
    after = _primitive_names()
    if before and not before.issubset(after):
        missing = sorted(before - after)
        raise RuntimeError(
            f"delete_skill({skill_name}) removed frozen primitive tools: {missing}. "
            "The store is now inconsistent — re-run setup.sh to re-import them."
        )
    return ok


def upload_skill(skill_dir: str | Path) -> bool:
    """Import a skill directory into the store via POST /skills/import-anthropic.

    Each ``.py`` file under ``scripts/`` becomes one store tool; the store
    auto-detects each tool's dependency on the primitive it calls by bare name.
    The primitives must already be registered (setup.sh does this) so they are in
    the store's known-name set when the wrappers are imported.

    Returns True on success, False on failure.
    """
    skill_dir = str(Path(skill_dir).resolve())
    url = _store_url("/skills/import-anthropic")

    try:
        import json

        # Use subprocess + curl for multipart form upload (simpler than urllib multipart)
        result = subprocess.run(
            [
                "curl", "-s", "-X", "POST", url,
                "-F", "source_type=folder",
                "-F", f"folder_path={skill_dir}",
                "-F", "snippet_mode=file",
            ],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            try:
                resp = json.loads(result.stdout)
                return resp.get("success", False) is True
            except Exception:
                pass
    except Exception:
        pass
    return False
