"""Acceptance A4 (no model call): seed prompt == stock prompt; memory block placement; helpers + notes setup.

Usage: APPWORLD_ROOT=/tmp/aw_eval/root_opt python check_injection.py SEED_CAPABILITY_DIR
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "adapters"))
os.environ.setdefault("OPENAI_API_KEY", "unused")
os.environ.setdefault("MODEL_SERVER_URL", "http://unused")
os.environ.setdefault(os.environ.get("AW_KEY_ENV", "RITS_API_KEY"), "unused")

import aw_agent  # noqa: E402
from appworld import AppWorld, load_task_ids  # noqa: E402
from appworld_agents.code.simplified.react_code_agent import SimplifiedReActCodeAgent  # noqa: E402

STOCK = Path(os.environ.get("AW_EVAL", "/tmp/aw_eval")) / "appworld/experiments/prompts/react_code_agent/instructions.txt"


def agent_kwargs(prompt_path: str) -> dict:
    return dict(prompt_file_path=prompt_path, model_config=dict(aw_agent.MODEL_CONFIG),
                appworld_config={"random_seed": 100}, logger_config={"color": False, "verbose": False},
                max_output_length=aw_agent.MAX_OUTPUT_LENGTH, max_steps=50)


def first_messages(agent, tid: str, exp: str):
    with AppWorld(task_id=tid, experiment_name=exp) as world:
        agent.initialize(world)
        msgs = [dict(m) for m in agent.messages]
        probe = None
        if getattr(agent, "setup_output", None) is not None:
            probe = world.execute(
                "print(apis.api_docs.show_api_doc(app_name='spotify', api_name='login'))\n"
                "print(cap_double(21))")
            raw = world.execute("print(_cap_orig_show_api_doc(app_name='spotify', api_name='login'))")
            probe = (probe, raw)
    return msgs, probe


def main(argv: list[str]) -> int:
    seed = Path(argv[1])
    tid = load_task_ids("dev")[0]
    Cap = aw_agent.build_agent_class()
    stock = SimplifiedReActCodeAgent(**agent_kwargs(str(STOCK)))
    m_stock, _ = first_messages(stock, tid, "probes/a4_stock")
    cap = Cap(candidate=aw_agent.read_candidate(seed), **agent_kwargs(str(seed / "policy/instructions.txt")))
    m_seed, _ = first_messages(cap, tid, "probes/a4_seed")
    ok = True
    same = json.dumps(m_stock) == json.dumps(m_seed)
    print(f"A4.1 seed first request byte-identical to stock: {same} ({len(m_seed)} messages)")
    ok &= same and cap.setup_output is None

    cap_m = Cap(candidate=aw_agent.read_candidate(seed), memory_block="- ALWAYS-TEST-GUIDELINE",
                **agent_kwargs(str(seed / "policy/instructions.txt")))
    m_mem, _ = first_messages(cap_m, tid, "probes/a4_mem")
    last = m_mem[-1]["content"]
    placed = (len(m_mem) == len(m_stock) and m_mem[:-1] == m_stock[:-1]
              and last.index(aw_agent.MEMORY_HEADING) < last.index("My name is:") < last.index("Task:"))
    print(f"A4.2 memory block in final USER message, before 'My name is:': {placed}")
    ok &= placed

    tmp = Path(tempfile.mkdtemp())
    shutil.copytree(seed, tmp / "cand")
    (tmp / "cand/tools/helpers.py").write_text('def cap_double(x):\n    """Double x."""\n    return 2 * x\n')
    (tmp / "cand/tools/api_notes.json").write_text(json.dumps({"spotify.login": "A4-NOTE"}))
    cap_t = Cap(candidate=aw_agent.read_candidate(tmp / "cand"), **agent_kwargs(str(tmp / "cand/policy/instructions.txt")))
    m_t, (probe, raw) = first_messages(cap_t, tid, "probes/a4_tools")
    doc_text, helper_out = probe.strip().rsplit("\n", 1)
    wrapped = json.loads(doc_text)
    original = json.loads(raw)
    tools_ok = (helper_out.strip() == "42" and wrapped.pop("note", None) == "A4-NOTE"
                and wrapped == original)
    notice = "cap_double(x)" in m_t[-1]["content"]
    print(f"A4.3 helpers defined + note appended, original doc text unchanged: {tools_ok}; notice in prompt: {notice}")
    ok &= tools_ok and notice
    print("A4", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
