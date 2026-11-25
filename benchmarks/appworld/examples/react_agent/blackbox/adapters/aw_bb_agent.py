"""One AppWorld episode through the Skillberry Proxy-Agent (blackbox): the agent and its prompt are stock.

Run as a script, one episode per process (AppWorld allows one live world per process)::

    python aw_bb_agent.py SPEC_JSON OUT_JSON

SPEC_JSON (written by the adapter) holds the task_id, experiment_name, appworld_root and random_seed;
client_prompt (AppWorld's own stock react_code_agent/instructions.txt); spa_url and headers (the
skillberry-context-* headers, appworld_tailoring.context_headers); remote_environment_url (the
trial's own AppWorld environment server, or none for an in-process world); and repl_code.

The episode:
  1. builds AppWorld's stock SimplifiedReActCodeAgent, its model the proxy, its LLM calls carrying the
     headers. It sends AppWorld's stock prompt unchanged; the proxy drops it up to the real task turn
     (history_start_regex) and puts the candidate's rendered SKILL.md in its place;
  2. creates the world (on the trial's server when given) and, when repl_code is set, runs it with
     ``world.execute`` before the agent starts, as the direct approach does: the candidate's tools
     (its helpers and API-note wrappers, ``aw_agent.setup_snippet``). The agent's ``initialize`` does
     not touch the REPL;
  3. runs the stock step loop, evaluates the world, and disconnects the episode from the proxy.

OUT_JSON gets the same gold-free episode record the direct approach writes, so the adapter scores both
alike, plus ``setup_output`` (what the REPL printed for repl_code) and ``native`` (the agent's own
message list, which the adapter moves to native_sims/).

Reused from the direct approach's harness (``aw_agent.py``, copied into the project by
scripts/setup_project.sh): the hardened code guard, gold-free evaluation fields, error redaction and
the worker-environment allowlist. The worker needs no model key: the proxy holds it.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import aw_agent as core  # noqa: E402  (the direct approach's harness, stdlib-only at import)
import appworld_tailoring as tailoring  # noqa: E402


def model_config(spec: dict[str, Any]) -> dict[str, Any]:
    """AppWorld LanguageModel config: the proxy's sentinel, every header from an env var (the patch)."""
    extra_headers_env = {}
    for i, (name, value) in enumerate(spec["headers"].items()):
        var = f"AW_SB_CTX_HEADER_{i}"
        os.environ[var] = value
        extra_headers_env[name] = var
    return {
        "client_name": "litellm",
        "name": tailoring.SPA_MODEL_SENTINEL,  # the proxy calls its own SPA_MODEL_NAME
        "base_url": spec["spa_url"] + "/v1",
        "api_key": "EMPTY",
        "extra_headers_env": extra_headers_env,
        "temperature": 0,
        "max_completion_tokens": 6000,
        "drop_reasoning_content": True,
        "use_cache": False,
        "retry_after_n_seconds": 15,
        "max_retries": 20,
        "cost_per_token": {"input_cache_hit": 0, "input_cache_miss": 0, "input_cache_write": 0, "output": 0},
    }


def agent_kwargs(spec: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """The direct approach's constructor arguments, with AppWorld's stock prompt file."""
    kwargs = core.agent_kwargs(dict(spec, candidate_dir="/nonexistent"), config)
    kwargs["prompt_file_path"] = str(spec["client_prompt"])
    return kwargs


def disconnect(spec: dict[str, Any]) -> bool:
    """Release the proxy's per-env MCP server and trajectory for this episode's env_id (see
    appworld_tailoring.disconnect). The adapter retries it when this does not confirm."""
    return tailoring.disconnect(spec["headers"], spa_url=spec["spa_url"])


def run_episode(spec: dict[str, Any]) -> dict[str, Any]:
    t_start = time.time()
    core.set_phase("setup")
    os.environ["APPWORLD_ROOT"] = spec["appworld_root"]
    os.environ.setdefault("MODEL_SERVER_URL", spec["spa_url"])
    # AppWorld's LanguageModel builds an OpenAI() client object even for litellm; it only needs a value.
    os.environ.setdefault("OPENAI_API_KEY", "unused")

    from appworld import AppWorld
    core.harden_guard()
    from appworld_agents.code.simplified.react_code_agent import SimplifiedReActCodeAgent

    kwargs = agent_kwargs(spec, model_config(spec))
    unknown = core.unaccepted_kwargs(SimplifiedReActCodeAgent, kwargs)
    if unknown:
        raise core.AgentConstructionError(f"upstream agent does not accept {unknown} (AppWorld pin changed?)")
    agent = SimplifiedReActCodeAgent(**kwargs)

    task_id = spec["task_id"]
    steps: list[dict[str, Any]] = []
    termination = "max_steps"
    error_message = ""
    prompt_tokens = completion_tokens = 0
    max_prompt_tokens = 0
    trims = 0
    record: dict[str, Any] = {"task_id": task_id, "env_id": spec["headers"].get("skillberry-context-env_id")}
    try:
        with AppWorld.initializer(update_defaults=True, experiment_name=spec["experiment_name"],
                                  random_seed=int(spec["random_seed"]), raise_on_extra_parameters=True):
            # The remote REPL: with remote_environment_url (a constructor argument of the WORLD, not the
            # agent) the world, its databases and its REPL live in this trial's own environment server,
            # and world.execute / evaluate / task_completed go to it over HTTP. The agent stays stock.
            remote = {"remote_environment_url": spec["remote_environment_url"]} if spec.get("remote_environment_url") else {}
            with AppWorld(task_id=task_id, experiment_name=spec["experiment_name"], **remote) as world:
                if spec.get("repl_code"):
                    # The candidate's tools, as in the direct approach: its REPL code
                    # (aw_agent.setup_snippet), run once with world.execute before step 1. The stock agent
                    # is not involved; its initialize() below does not touch the REPL.
                    setup_output = world.execute(spec["repl_code"])
                    record["setup_output"] = (setup_output or "")[:500]   # as direct records it
                core.set_phase("episode")
                agent.usage_tracker.reset(task_id)
                agent.initialize(world)
                outputs: list = []
                from appworld_agents.code.simplified.agent import ExecutionIO
                for _ in range(agent.max_steps):
                    agent.step_number += 1
                    n_before = len(agent.messages)
                    trimmed = agent.trimmed_messages
                    if any("[NOT SHOWN FOR BREVITY]" in (m.get("content") or "") or
                           "[TRIMMED HISTORY]" in (m.get("content") or "") for m in trimmed):
                        trims += 1
                    inputs, usage, status = agent.next_execution_inputs_usage_and_status(outputs)
                    if status.failed:
                        error_message = status.message or ""
                        termination = "context_exceeded" if core.CONTEXT_RE.search(error_message) else "lm_error"
                        break
                    msg = agent.messages[-1] if len(agent.messages) > n_before else {}
                    pt = int(usage.tokens.input_cache_hit_or_miss)
                    ct = int(usage.tokens.output)
                    prompt_tokens += pt
                    completion_tokens += ct
                    max_prompt_tokens = max(max_prompt_tokens, pt)
                    code = inputs[0].content if inputs else ""
                    out = world.batch_execute([code])[0] if inputs else ""
                    outputs = [ExecutionIO(content=out)]
                    content = msg.get("content") or ""
                    thought = re.sub(r"```python\n.*?```", "", content, flags=re.DOTALL).strip()
                    steps.append({
                        "step": agent.step_number,
                        "thought": thought[:core.TRUNC_OUTPUT],
                        "reasoning": (msg.get("reasoning_content") or "")[:core.TRUNC_REASONING],
                        "code": code,
                        "output": out[:core.TRUNC_OUTPUT] + ("…[truncated]" if len(out) > core.TRUNC_OUTPUT else ""),
                        "prompt_tokens": pt, "completion_tokens": ct,
                    })
                    agent.usage_tracker.add(task_id, usage)
                    if world.task_completed():
                        termination = "completed"
                        break
                    if completion_tokens >= core.MAX_OUTPUT_TOKENS_PER_TASK or agent.usage_tracker.exceeded(task_id):
                        termination = "token_cap"
                        break
                completed = bool(world.task_completed())
                core.set_phase("evaluate")
                tracker = world.evaluate()
                ev = tracker.to_dict(stats_only=False)
    finally:
        record["disconnected"] = disconnect(spec)
    core.set_phase("setup")
    # The agent's own message list, as the stock agent holds it: AppWorld's prompt messages
    # (num_prompt_messages of them, which the proxy replaces with SKILL.md) then every turn.
    # The adapter writes it to native_sims/ and keeps it out of the rollout.
    record["native"] = {
        "task_id": task_id, "model": tailoring.SPA_MODEL_SENTINEL, "via": "skillberry-proxy",
        "num_prompt_messages": getattr(agent, "num_instruction_messages", None),
        "headers_sent": spec["headers"],
        "messages": [{k: m[k] for k in ("role", "content", "reasoning_content") if m.get(k)}
                     for m in agent.messages],
    }

    all_code = "\n".join(s["code"] for s in steps)
    record.update(core.evaluation_fields(ev))
    record.update({
        "complete_task_called": completed,
        "termination": termination,
        "error_message": error_message[:500],
        "n_steps": len(steps),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "max_prompt_tokens": max_prompt_tokens,
        "trimmed_steps": trims,
        "api_errors": sum(1 for s in steps if s["output"].startswith("Execution failed")),
        "fs_probe": bool(core.FS_PROBE_RE.search(all_code)),
        "guard_blocked": sum(1 for s in steps if core.GUARD_MESSAGE in s["output"]),
        "guard_probe": bool(core.GUARD_PROBE_RE.search(all_code))
        or any(core.GUARD_MESSAGE in s["output"] for s in steps),
        "steps": steps,
        "wall_seconds": round(time.time() - t_start, 1),
    })
    return record


def main(argv: list[str]) -> int:
    spec = json.loads(Path(argv[1]).read_text())
    out = Path(argv[2])
    replacements = {str(spec.get("appworld_root") or ""): "<root>"}
    try:
        rec = run_episode(spec)
    except Exception as e:  # noqa: BLE001 — reported to the adapter as infrastructure
        rec = {"task_id": spec.get("task_id"), "infra_error": core.redact_error(e, core._phase["name"], replacements)}
        if os.environ.get("AW_KEEP_OUTPUTS") == "1":
            d = Path(spec["appworld_root"]) / "experiments" / "outputs" / str(spec.get("experiment_name", ""))
            try:
                d.mkdir(parents=True, exist_ok=True)
                (d / "infra_traceback.txt").write_text(traceback.format_exc())
            except OSError:
                pass
    out.write_text(json.dumps(rec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
