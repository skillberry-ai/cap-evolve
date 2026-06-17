"""tau2 airline runtime helpers for the cap-evolve example.

Routes both the agent and the user simulator to RITS ``openai/gpt-oss-120b``,
injects the candidate policy into tau2's airline domain, and runs tasks through
tau2's concurrent batch runner. Adapted from prior agent-optimization work's tau2 wiring (rits_connect +
inject + runner) and trimmed to the policy-optimization case.
"""

from __future__ import annotations

import os
from pathlib import Path

import requests

INFO_URL = os.environ.get("RITS_INFO_URL", "https://rits.fmaas.res.ibm.com/ritsapi/inferenceinfo")
API_URL = os.environ.get(
    "RITS_API_URL",
    "https://inference-3scale-apicast-production.apps.rits.fmaas.res.ibm.com")
AGENT_MODEL = os.environ.get("RITS_MODEL", "openai/gpt-oss-120b")
MAX_CONCURRENCY = int(os.environ.get("TAU2_MAX_CONCURRENCY", "20"))


def load_env() -> None:
    """Load the repo .env (RITS/watsonx keys) without requiring python-dotenv."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        env = parent / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    # strip surrounding quotes — a quoted value (KEY="abc") must not
                    # send the quotes downstream (RITS rejects a quoted API key).
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            return


def rits_kwargs(model_name: str = AGENT_MODEL) -> dict:
    load_env()
    key = os.environ.get("RITS_API_KEY")
    if not key:
        raise RuntimeError("RITS_API_KEY not set (add it to the repo .env)")
    resp = requests.get(INFO_URL, headers={"RITS_API_KEY": key}, timeout=30)
    resp.raise_for_status()
    models = {m["model_name"]: m["endpoint"].split("/")[-1] for m in resp.json()}
    url = models.get(model_name)
    if not url:
        raise RuntimeError(f"model {model_name} not in RITS list: {sorted(models)[:8]}...")
    return {"model": f"hosted_vllm/{model_name}",
            "api_base": f"{API_URL.rstrip('/')}/{url}/v1",
            "api_key": key,
            "extra_headers": {"RITS_API_KEY": key}}


def _patch_empty_turn_retry(max_retries: int = 4) -> None:
    """Reasoning models (gpt-oss) sometimes return an empty turn (spent in
    reasoning_content); tau2 treats that as an infra error. Re-request the single
    call (sampling is stochastic). No content is fabricated. Idempotent."""
    import tau2.agent.llm_agent as _agent
    import tau2.user.user_simulator as _user
    import tau2.utils.llm_utils as _llm
    if getattr(_llm, "_forge_retry_patch", False):
        return
    orig = _llm.generate

    def _empty(msg) -> bool:
        return not (getattr(msg, "content", None) and str(msg.content).strip()) \
            and not getattr(msg, "tool_calls", None)

    def wrapped(*a, **k):
        msg = orig(*a, **k)
        tries = 0
        while _empty(msg) and tries < max_retries:
            tries += 1
            msg = orig(*a, **k)
        return msg

    for mod in (_llm, _agent, _user):
        mod.generate = wrapped
    _llm._forge_retry_patch = True


def _find(candidate_dir: Path, *names: str) -> Path | None:
    """Find a file by name in candidate_dir or any one-level subdir (composite layout)."""
    cdir = Path(candidate_dir)
    for n in names:
        if (cdir / n).exists():
            return cdir / n
    if cdir.is_dir():
        for sub in cdir.iterdir():
            if sub.is_dir():
                for n in names:
                    if (sub / n).exists():
                        return sub / n
    return None


def inject_policy(candidate_dir: Path) -> None:
    """Override tau2's airline domain policy with the candidate's policy.md
    (found at candidate_dir/policy.md or candidate_dir/policy/policy.md)."""
    pf = _find(candidate_dir, "policy.md")
    if pf:
        policy = pf.read_text(encoding="utf-8")
        from tau2.environment.environment import Environment
        Environment.get_policy = lambda self: policy  # type: ignore


def _body_is_trivial(fn) -> bool:
    """True if the function body is only a docstring + `...`/`pass` (docstring-only override)."""
    import ast
    import inspect
    import textwrap
    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn))).body[0]
        stmts = list(tree.body)
        if stmts and isinstance(stmts[0], ast.Expr) and isinstance(getattr(stmts[0], "value", None), ast.Constant):
            stmts = stmts[1:]
        return all(isinstance(s, ast.Pass) or
                   (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and s.value.value is Ellipsis)
                   for s in stmts) if stmts else True
    except Exception:
        # If we can't introspect the source, be conservative: treat as docstring-only
        # (override the description, don't swap in an impl we couldn't verify).
        return True


def inject_tools(candidate_dir: Path) -> dict:
    """Apply the candidate's tools.py to tau2's AirlineTools.

    For each function whose name matches an existing airline tool: override its
    DOCSTRING (the tool description the agent reads); if the body is non-trivial,
    also replace the implementation. New functions are added as tools (composite
    tools that may call existing ones via ``self``). Best-effort and guarded — a
    malformed tools.py yields no change (so the gate rejects it) rather than crashing.
    """
    import inspect
    import tau2.domains.airline.tools as air
    from tau2.environment.toolkit import ToolKitBase, is_tool
    AT = air.AirlineTools
    existing = [n for n in dir(AT) if getattr(getattr(AT, n, None), "__tool__", False)]

    # Snapshot the PRISTINE airline tools once (docstrings, methods, get_tools), so
    # each candidate is evaluated against pristine + its own edits — no leakage of
    # one candidate's overrides/added-tools into the next (which would make scores
    # depend on evaluation order).
    if not hasattr(AT, "_forge_pristine"):
        AT._forge_pristine = {
            "docs": {n: getattr(AT, n).__doc__ for n in existing},
            "methods": {n: getattr(AT, n) for n in existing},
            "get_tools": ToolKitBase.get_tools,
        }
    pristine = AT._forge_pristine
    # reset to pristine before applying this candidate
    for n, m in pristine["methods"].items():
        setattr(AT, n, m)
        getattr(AT, n).__doc__ = pristine["docs"][n]
    ToolKitBase.get_tools = pristine["get_tools"]

    f = _find(candidate_dir, "tools.py")
    if not f:
        return {"applied": 0}
    ns: dict = {}
    try:
        exec(compile(f.read_text(encoding="utf-8"), "<tools.py>", "exec"), air.__dict__, ns)
    except Exception as e:  # noqa: BLE001
        return {"applied": 0, "error": f"tools.py exec failed: {e}"}
    funcs = {k: v for k, v in ns.items() if inspect.isfunction(v) and not k.startswith("_")}
    added, applied = {}, 0
    for name, fn in funcs.items():
        if name in pristine["methods"]:
            tgt = getattr(AT, name)
            if fn.__doc__:
                try:
                    tgt.__doc__ = fn.__doc__  # description override
                except Exception:  # noqa: BLE001
                    pass
            if not _body_is_trivial(fn):  # behavior change → replace impl
                try:
                    fn.__doc__ = fn.__doc__ or tgt.__doc__
                    setattr(AT, name, is_tool()(fn) if not getattr(fn, "__tool__", False) else fn)
                except Exception:  # noqa: BLE001
                    pass
            applied += 1
        else:
            added[name] = fn
    if added:
        base_get = pristine["get_tools"]

        def patched_get_tools(self, include=None):
            tools = base_get(self, include)
            from tau2.environment.tool import as_tool
            import types as _t
            for n, fn in added.items():
                try:
                    tools[n] = as_tool(_t.MethodType(fn, self))
                except Exception:  # noqa: BLE001
                    pass
            return tools
        ToolKitBase.get_tools = patched_get_tools  # type: ignore
    return {"applied": applied, "added": sorted(added)}


def inject(candidate_dir: Path) -> dict:
    """Inject BOTH the policy and the tools from a (composite) candidate dir."""
    _patch_empty_turn_retry()
    inject_policy(candidate_dir)
    return inject_tools(candidate_dir)


def transcript(sim, max_turns: int = 60, max_chars: int = 8000) -> str:
    lines = []
    for m in (getattr(sim, "messages", None) or [])[-max_turns:]:
        role = getattr(getattr(m, "role", None), "value", getattr(m, "role", "?"))
        content, tcs = getattr(m, "content", None), getattr(m, "tool_calls", None)
        if tcs:
            for tc in tcs:
                lines.append(f"{role} -> {getattr(tc,'name','?')}({str(getattr(tc,'arguments',''))[:200]})")
        elif content:
            lines.append(f"{role}: {str(content)[:300]}")
    return "\n".join(lines)[-max_chars:]


def run_airline_batch(candidate_dir: Path, task_ids: list[str], *, seed: int = 42) -> dict:
    """Run the given airline task ids through tau2 with the candidate policy.

    ``seed`` (W1 per-trial seed): threaded into tau2's ``TextRunConfig.seed`` so
    distinct trials (the harness calls this once per trial with ``base_seed + k``)
    are genuinely independent draws. Previously this hardcoded ``seed=42`` for every
    trial, which made multi-trial evaluation produce identical runs ⇒ stderr 0 ⇒ the
    significance gate degenerated to "any Δ>0". Returns
    {task_id: {reward, reward_info, trace, termination, output}}."""
    from tau2.data_model.simulation import TextRunConfig
    from tau2.runner import get_tasks, run_tasks
    import contextlib
    import signal
    import sys as _sys

    inject_policy(candidate_dir)
    kw = rits_kwargs(AGENT_MODEL)
    model = kw["model"]
    # `timeout`/`num_retries`: a stalled RITS request must abort (and let tau2's
    # max_errors retry) rather than hang the whole batch forever.
    llm_args = {"max_tokens": 8000, "api_base": kw["api_base"], "api_key": kw["api_key"],
                "extra_headers": kw["extra_headers"],
                "timeout": float(os.environ.get("TAU2_LLM_TIMEOUT", "300")),
                "num_retries": int(os.environ.get("TAU2_LLM_RETRIES", "2"))}
    config = TextRunConfig(
        domain="airline", agent="llm_agent", llm_agent=model, llm_args_agent=dict(llm_args),
        user="user_simulator", llm_user=model, llm_args_user=dict(llm_args),
        num_trials=1, max_steps=100, max_errors=10, max_concurrency=MAX_CONCURRENCY, seed=int(seed),
    )
    # Hard wall-clock watchdog: the per-call `timeout` does NOT catch a tau2
    # concurrent-runner stall (a wedged conversation can hang the batch forever).
    # SIGALRM fires in the main thread (the harness is synchronous) and aborts the run.
    batch_timeout = int(os.environ.get("TAU2_BATCH_TIMEOUT", "1200"))

    class _BatchTimeout(Exception):
        pass

    def _on_alarm(signum, frame):
        raise _BatchTimeout()

    def _run_ids(ids: list[str]) -> dict:
        """Run one batch over `ids`; return {tid: result}. {} on watchdog timeout."""
        t2 = get_tasks("airline", task_ids=[str(t) for t in ids])
        old = signal.signal(signal.SIGALRM, _on_alarm)
        signal.alarm(batch_timeout)
        try:
            with contextlib.redirect_stdout(_sys.stderr):
                results = run_tasks(config, t2, save_path=None, console_display=False)
        except _BatchTimeout:
            _sys.stderr.write(f"[tau2_runtime] batch timed out after {batch_timeout}s "
                              f"({len(ids)} tasks)\n")
            return {}
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
        res = {}
        for sim in results.simulations:
            tid = str(sim.task_id)
            ri = getattr(sim, "reward_info", None)
            tokens = 0
            for m in (getattr(sim, "messages", None) or []):
                u = getattr(m, "usage", None)
                if isinstance(u, dict):
                    tokens += int(u.get("total_tokens")
                                  or (u.get("prompt_tokens", 0) + u.get("completion_tokens", 0)) or 0)
            cost = float((getattr(sim, "agent_cost", 0) or 0) + (getattr(sim, "user_cost", 0) or 0))
            res[tid] = {
                "reward": float(ri.reward) if ri else 0.0,
                "reward_info": ri,
                "trace": transcript(sim),
                "termination": str(getattr(sim, "termination_reason", None)),
                "tokens": tokens, "cost": cost,
                "output": str(getattr(sim, "messages", [])[-1].content
                              if getattr(sim, "messages", None) else ""),
            }
        return res

    out = _run_ids([str(t) for t in task_ids])
    # Retry tasks that died with an INFRASTRUCTURE error (gpt-oss empty turns / RITS
    # flakiness). These are uncontrollable 0s that no policy/tools edit can fix — they
    # depress the baseline and inject pure noise into the gate. Re-running usually
    # recovers them (sampling is stochastic), so the optimizer sees the real signal.
    for _ in range(int(os.environ.get("TAU2_INFRA_RETRIES", "2"))):
        infra = [str(t) for t in task_ids
                 if "INFRASTRUCTURE" in str(out.get(str(t), {}).get("termination", "")) or str(t) not in out]
        if not infra:
            break
        _sys.stderr.write(f"[tau2_runtime] retrying {len(infra)} infra-errored task(s): {infra}\n")
        for tid, r in _run_ids(infra).items():
            if "INFRASTRUCTURE" not in str(r.get("termination", "")):  # keep only recovered runs
                out[tid] = r
    return out
