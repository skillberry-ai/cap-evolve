"""One AppWorld episode with a cap-evolve candidate live: the injection layer (README: Harness).

``CapReActAgent`` subclasses AppWorld's official simplified ReAct code agent and overrides only
``initialize``: the prompt template comes from the candidate's ``policy/instructions.txt``, an
optional memory block is inserted before the final ``My name is: … Task: …`` block, and a setup
snippet defines ``tools/helpers.py`` in the REPL and appends ``tools/api_notes.json`` notes to the
API-doc lookups. With an empty memory, helpers and notes the prompt is byte-identical to stock.

Run as a script, one episode per process (AppWorld allows one live world per process)::

    python aw_agent.py SPEC_JSON OUT_JSON

SPEC_JSON holds task_id, experiment_name, candidate_dir, appworld_root, random_seed, and
optionally memory_block. OUT_JSON gets the gold-free episode record (``episode_record``).
Ground-truth evaluation details are reduced to requirement texts: AppWorld's failure ``trace``
holds gold values and is dropped here, before anything is written.
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

HERE = Path(__file__).resolve().parent

MEMORY_HEADING = "Guidelines learned from past task attempts:"
TRUNC_OUTPUT = 2000
TRUNC_REASONING = 1500
# Paths that only matter to someone looking for gold data. Agent code that names one is flagged.
FS_PROBE_RE = re.compile(r"ground_truth|answer\.json|/data/tasks|APPWORLD_ROOT|root_full|root_opt|test_normal")
CONTEXT_RE = re.compile(r"context length|context_length|ContextWindowExceeded|maximum context|max_model_len|too many tokens|input tokens", re.I)
# Removed from AppWorld's import allowlist for every arm (README: Harness): with them the
# agent's REPL code can list and read files (pathlib.Path.read_text goes through the read-only open).
EXTRA_BLOCKED_MODULES = {"os", "pathlib", "io", "shutil", "glob"}

# The agent under test. Defaults: gpt-oss-120b on IBM RITS (vLLM, OpenAI-compatible), authenticated by
# a `RITS_API_KEY: <key>` header. Override the model, URL, header and the env var that holds the key:
#   AW_MODEL_NAME, AW_MODEL_URL (may use {{MODEL_SERVER_URL}}), AW_KEY_HEADER, AW_KEY_ENV.
KEY_ENV = os.environ.get("AW_KEY_ENV", "RITS_API_KEY")
MODEL_CONFIG: dict[str, Any] = {
    "client_name": "litellm",
    "name": os.environ.get("AW_MODEL_NAME", "hosted_vllm/openai/gpt-oss-120b-a100"),
    "base_url": os.environ.get("AW_MODEL_URL", "{{MODEL_SERVER_URL}}/gpt-oss-120b-a100/v1"),
    "api_key": "unused",
    "extra_headers_env": {os.environ.get("AW_KEY_HEADER", "RITS_API_KEY"): KEY_ENV},
    "reasoning_effort": "medium",
    "temperature": 0,
    "max_completion_tokens": 6000,
    "drop_reasoning_content": True,
    "use_cache": False,
    "retry_after_n_seconds": 15,
    "max_retries": 20,
    "cost_per_token": {"input_cache_hit": 0, "input_cache_miss": 0, "input_cache_write": 0, "output": 0},
}
MAX_STEPS = 50
MAX_OUTPUT_LENGTH = 60000
MAX_OUTPUT_TOKENS_PER_TASK = 100000


def load_secrets(path: str | None) -> None:
    """Read KEY=VALUE lines into os.environ (the RITS key). Nothing is exported by the caller."""
    if not path or not Path(path).is_file():
        return
    for line in Path(path).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def read_candidate(candidate_dir: Path) -> dict[str, Any]:
    cdir = Path(candidate_dir)
    helpers = (cdir / "tools" / "helpers.py")
    notes = (cdir / "tools" / "api_notes.json")
    return {
        "template": (cdir / "policy" / "instructions.txt").read_text(encoding="utf-8").lstrip(),
        "helpers": helpers.read_text(encoding="utf-8") if helpers.is_file() else "",
        "notes": json.loads(notes.read_text(encoding="utf-8") or "{}") if notes.is_file() else {},
    }


def helper_names(helpers_src: str) -> list[str]:
    import ast
    try:
        tree = ast.parse(helpers_src or "")
    except SyntaxError:
        return []
    return [n.name for n in tree.body if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")]


def has_code(src: str) -> bool:
    """True when ``src`` has a statement other than a module docstring (the seed's helpers.py has none)."""
    import ast
    try:
        body = ast.parse(src or "").body
    except SyntaxError:
        return bool((src or "").strip())  # let the REPL report the syntax error
    return any(not (isinstance(n, ast.Expr) and isinstance(getattr(n, "value", None), ast.Constant))
               for n in body)


def helper_notice(helpers_src: str) -> str:
    """One line naming the helpers, appended only when helpers exist."""
    import ast
    names = []
    try:
        tree = ast.parse(helpers_src or "")
    except SyntaxError:
        return ""
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and not n.name.startswith("_"):
            names.append(f"{n.name}({', '.join(a.arg for a in n.args.args)})")
    if not names:
        return ""
    return ("Pre-defined helper functions are available in the REPL (call them directly; "
            "see their docstrings with help(name)): " + ", ".join(names) + ".")


def insert_before_final_block(prompt: str, block: str) -> str:
    """Insert ``block`` right before the last ``My name is:`` line (the final task block)."""
    i = prompt.rfind("My name is:")
    if i < 0:
        raise ValueError("prompt has no final 'My name is:' block")
    return prompt[:i] + block.rstrip() + "\n\n" + prompt[i:]


def setup_snippet(helpers_src: str, notes: dict[str, str]) -> str:
    """REPL code run once before step 1: define helpers, wrap the two API-doc lookups.

    The wrappers return the original result unchanged plus a ``note`` field when one exists for
    that app/api (``api_notes.json`` keys are ``app`` or ``app.api``).
    """
    parts = []
    if has_code(helpers_src):
        parts.append(helpers_src)
    if notes:
        parts.append(f"""
_cap_api_notes = {json.dumps(notes)}
_cap_orig_show_api_doc = apis.api_docs.show_api_doc
_cap_orig_show_api_descriptions = apis.api_docs.show_api_descriptions
def _cap_show_api_doc(*args, **kwargs):
    result = _cap_orig_show_api_doc(*args, **kwargs)
    app = kwargs.get("app_name", args[0] if args else None)
    api = kwargs.get("api_name", args[1] if len(args) > 1 else None)
    note = _cap_api_notes.get(f"{{app}}.{{api}}")
    if note and isinstance(result, dict):
        result = dict(result)
        result["note"] = note
    return result
def _cap_show_api_descriptions(*args, **kwargs):
    result = _cap_orig_show_api_descriptions(*args, **kwargs)
    app = kwargs.get("app_name", args[0] if args else None)
    if not isinstance(result, list):
        return result
    out = []
    for item in result:
        note = _cap_api_notes.get(f"{{app}}.{{item.get('name')}}") if isinstance(item, dict) else None
        out.append(dict(item, note=note) if note else item)
    app_note = _cap_api_notes.get(str(app))
    if app_note:
        out.append({{"note": app_note}})
    return out
apis.api_docs.show_api_doc = _cap_show_api_doc
apis.api_docs.show_api_descriptions = _cap_show_api_descriptions
""")
    return "\n".join(parts).strip()


def build_agent_class():
    from appworld_agents.code.simplified.react_code_agent import SimplifiedReActCodeAgent

    class CapReActAgent(SimplifiedReActCodeAgent):  # type: ignore[misc, valid-type]
        def __init__(self, candidate: dict[str, Any], memory_block: str = "", **kwargs: Any):
            self.candidate = candidate
            self.memory_block = memory_block or ""
            self.setup_output: str | None = None
            super().__init__(**kwargs)
            self.prompt_template = candidate["template"]

        def initialize(self, world) -> None:  # noqa: ANN001
            super().initialize(world)
            extra = []
            block = self.memory_block.strip()
            if block:
                # ALTK's format_selection already starts with this heading; add it only when missing.
                extra.append(block if block.startswith(MEMORY_HEADING.rstrip(":")) else MEMORY_HEADING + "\n" + block)
            notice = helper_notice(self.candidate["helpers"])
            if notice:
                extra.append(notice)
            if extra:
                # Re-render with the block in the final USER message, then re-split exactly as stock does.
                from jinja2 import Template
                app_descriptions = json.dumps(
                    [{"name": k, "description": v} for (k, v) in world.task.app_descriptions.items()], indent=1)
                rendered = Template(self.prompt_template).render({
                    "instruction": world.task.instruction, "main_user": world.task.supervisor,
                    "app_descriptions": app_descriptions})
                rendered = insert_before_final_block(rendered, "\n\n".join(extra))
                rendered = self.truncate_input(rendered) + "\n\n"
                self.messages = self.text_to_messages(rendered)
                self.num_instruction_messages = len(self.messages)
            snippet = setup_snippet(self.candidate["helpers"], self.candidate["notes"])
            if snippet:
                self.setup_output = world.execute(snippet)

    return CapReActAgent


def harden_guard() -> None:
    import appworld.common.safety_guard as sg
    sg.ALLOWED_MODULE_NAMES.difference_update(EXTRA_BLOCKED_MODULES)


def _code_of(text: str) -> str:
    m = re.search(r"```python\n(.*?)```", text or "", flags=re.DOTALL)
    return m.group(1).strip() if m else ""


def evaluation_fields(ev: dict[str, Any]) -> dict[str, Any]:
    """The gold-free part of ``TestTracker.to_dict()``: the failure ``trace`` holds gold values and is dropped."""
    failures = ev.get("failures") or []
    return {
        "success": bool(ev.get("success")),
        "num_tests": int(ev.get("num_tests") or 0),
        "pass_count": len(ev.get("passes") or []),
        "failed_requirements": [f.get("requirement", "") for f in failures],
        # no_op_pass checks pass when nothing changes; failing one means unrequested state changes
        "collateral_damage": any(f.get("label") == "no_op_pass" for f in failures),
    }


def run_episode(spec: dict[str, Any]) -> dict[str, Any]:
    t_start = time.time()
    os.environ["APPWORLD_ROOT"] = spec["appworld_root"]
    load_secrets(spec.get("secrets_file"))
    os.environ.setdefault("MODEL_SERVER_URL", os.environ.get("RITS_URL", ""))
    os.environ.setdefault("OPENAI_API_KEY", "unused")

    from appworld import AppWorld
    harden_guard()

    candidate = read_candidate(Path(spec["candidate_dir"]))
    model_config = dict(MODEL_CONFIG)
    model_config["extra_headers_env"] = dict(MODEL_CONFIG["extra_headers_env"])
    CapReActAgent = build_agent_class()
    agent = CapReActAgent(
        candidate=candidate,
        memory_block=spec.get("memory_block", ""),
        prompt_file_path=str(Path(spec["candidate_dir"]) / "policy" / "instructions.txt"),
        model_config=model_config,
        appworld_config={"random_seed": int(spec["random_seed"]), "raise_on_extra_parameters": True},
        logger_config={"color": False, "verbose": False},
        usage_tracker_config={"max_cost_per_task": 10, "max_output_tokens_per_task": MAX_OUTPUT_TOKENS_PER_TASK},
        ignore_multiple_calls=True,
        max_prompt_length=None,
        max_output_length=MAX_OUTPUT_LENGTH,
        max_steps=MAX_STEPS,
        log_lm_calls=bool(spec.get("log_lm_calls", False)),
    )
    # The header value was read at init; drop the secret so agent code (os.environ) cannot see it.
    os.environ.pop(KEY_ENV, None)

    task_id = spec["task_id"]
    steps: list[dict[str, Any]] = []
    termination = "max_steps"
    error_message = ""
    prompt_tokens = completion_tokens = 0
    max_prompt_tokens = 0
    trims = 0
    first_messages: list[dict[str, Any]] | None = None
    record: dict[str, Any] = {"task_id": task_id}
    with AppWorld.initializer(update_defaults=True, experiment_name=spec["experiment_name"],
                              random_seed=int(spec["random_seed"]), raise_on_extra_parameters=True):
        with AppWorld(task_id=task_id, experiment_name=spec["experiment_name"]) as world:
            agent.usage_tracker.reset(task_id)
            agent.initialize(world)
            first_messages = [dict(m) for m in agent.messages]
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
                    termination = ("context_exceeded" if CONTEXT_RE.search(error_message)
                                   else "lm_error")
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
                    "thought": thought[:TRUNC_OUTPUT],
                    "reasoning": (msg.get("reasoning_content") or "")[:TRUNC_REASONING],
                    "code": code,
                    "output": out[:TRUNC_OUTPUT] + ("…[truncated]" if len(out) > TRUNC_OUTPUT else ""),
                    "prompt_tokens": pt, "completion_tokens": ct,
                })
                agent.usage_tracker.add(task_id, usage)
                if world.task_completed():
                    termination = "completed"
                    break
                if completion_tokens >= MAX_OUTPUT_TOKENS_PER_TASK or agent.usage_tracker.exceeded(task_id):
                    termination = "token_cap"
                    break
            completed = bool(world.task_completed())
            tracker = world.evaluate()
            ev = tracker.to_dict(stats_only=False)

    all_code = "\n".join(s["code"] for s in steps)
    record.update(evaluation_fields(ev))
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
        "fs_probe": bool(FS_PROBE_RE.search(all_code)),
        "setup_output": (agent.setup_output or "")[:500] if agent.setup_output is not None else None,
        "steps": steps,
        "wall_seconds": round(time.time() - t_start, 1),
    })
    if spec.get("dump_first_messages"):
        record["first_messages"] = first_messages
    return record


def main(argv: list[str]) -> int:
    spec = json.loads(Path(argv[1]).read_text())
    out = Path(argv[2])
    try:
        rec = run_episode(spec)
    except Exception as e:  # noqa: BLE001 — reported to the adapter as infrastructure
        rec = {"task_id": spec.get("task_id"), "infra_error": f"{type(e).__name__}: {e}",
               "traceback": traceback.format_exc()[-4000:]}
    out.write_text(json.dumps(rec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
