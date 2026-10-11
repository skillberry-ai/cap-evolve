#!/usr/bin/env python3
"""E05 tau2 faults, zero LLM (gateway points at a dead port). Prints JSON."""
import importlib.util, json, os, shutil, sys, tempfile, textwrap
from pathlib import Path
REPO = Path("/home/dev/projects2/cap-evolve-campaign")
os.environ.update(MODEL="litellm_proxy/aws/gpt-oss-120b", LITELLM_PROXY_API_BASE="http://127.0.0.1:9/v1", LITELLM_PROXY_API_KEY="dummy", TAU2_SIM_TIMEOUT="30", TAU2_MAX_CONCURRENCY="1", CAPEVOLVE_NATIVE_SIMS="0", TEMPERATURE="0.0")
sys.path[:0] = [str(REPO / "templates/adapters/tau2_bench"), str(REPO / "templates/adapters"), str(REPO / "core")]
spec = importlib.util.spec_from_file_location("t2", REPO / "templates/adapters/tau2_bench/adapter.py"); ad = importlib.util.module_from_spec(spec); spec.loader.exec_module(ad)
SEED = REPO / "examples/tau2_airline/seed_capability"
def cand(patch):
    d = Path(tempfile.mkdtemp()) / "c"; shutil.copytree(SEED, d); patch(d); return d
tools = lambda d: d / "tools" / "tools.py"
cases = {
 "healthy_control": lambda d: None,
 "tools_py_raises_at_import": lambda d: tools(d).write_text("raise RuntimeError('candidate import fault')\n"),
 "tools_py_syntax_error": lambda d: tools(d).write_text("def broken(:\n"),
 "tools_py_no_AirlineTools_class": lambda d: tools(d).write_text("X = 1\n"),
 "tools_py_get_tools_raises": lambda d: tools(d).write_text(tools(d).read_text() + textwrap.dedent('''
    _orig = AirlineTools.get_tools
    def _boom(self, include=None):
        raise ValueError("candidate get_tools fault")
    AirlineTools.get_tools = _boom
 ''')),
 "tools_py_removes_all_tools": lambda d: tools(d).write_text(tools(d).read_text() + "\nREMOVE_TOOLS = {n for n in dir(AirlineTools) if not n.startswith('_')}\n"),
}
out = {}
A = ad.Adapter(); task = [t for t in A.tasks("test") if t.id == "9"]
for name, patch in cases.items():
    d = cand(patch); rec = {}
    try:
        A.apply(d)
        r = A.run_batch(task, d, seed=0)["9"]
        s = A.score(task[0], r)
        rec = {"apply": "ok", "rollout_error": (r.error or "")[:120], "error_kind": (r.metadata or {}).get("error_kind"), "reward": s.reward, "feedback_head": (s.feedback or "")[:140]}
    except Exception as e:
        rec = {"apply_or_run_raised": f"{type(e).__name__}: {str(e)[:140]}"}
    out[name] = rec
# a tool that raises when CALLED: tau2's environment must hand the error back to the agent (no LLM needed to prove it)
try:
    d = cand(lambda d: tools(d).write_text(tools(d).read_text() + textwrap.dedent('''
        def _raise(self, *a, **k):
            raise ZeroDivisionError("candidate tool body fault")
        AirlineTools.get_user_details = _raise
    ''')))
    A.apply(d)
    from tau2.registry import registry
    env = registry.get_env_constructor("airline")()
    from tau2.data_model.message import ToolCall
    res = env.get_response(ToolCall(id="1", name="get_user_details", arguments={"user_id": "x"}, requestor="assistant"))
    out["tool_body_raises_when_called"] = {"env_returned_error_message": bool(res.error), "content_head": str(res.content)[:100]}
except Exception as e:
    out["tool_body_raises_when_called"] = {"raised": f"{type(e).__name__}: {str(e)[:140]}"}
print("E05JSON" + json.dumps(out))
