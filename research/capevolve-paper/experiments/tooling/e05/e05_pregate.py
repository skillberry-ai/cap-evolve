import importlib.util, json, os, shutil, sys, tempfile, textwrap
from pathlib import Path
REPO = Path("/home/dev/projects2/cap-evolve-campaign")
os.environ.update(MODEL="litellm_proxy/aws/gpt-oss-120b", LITELLM_PROXY_API_BASE="http://127.0.0.1:9/v1", LITELLM_PROXY_API_KEY="dummy")
sys.path[:0] = [str(REPO / "core"), str(REPO / "skills/algorithms/agent-optimize/scripts"), str(REPO / "templates/adapters/tau2_bench"), str(REPO / "templates/adapters")]
import pregate
SEED = REPO / "examples/tau2_airline/seed_capability"; TK = str(REPO / "templates/adapters/tau2_bench/adapter.py") + ":pregate_toolkit"
tools = lambda d: d / "tools" / "tools.py"
cases = {"healthy_control": lambda d: None,
 "tools_py_raises_at_import": lambda d: tools(d).write_text("raise RuntimeError('candidate import fault')\n"),
 "tools_py_syntax_error": lambda d: tools(d).write_text("def broken(:\n"),
 "tools_py_no_AirlineTools_class": lambda d: tools(d).write_text("X = 1\n"),
 "tools_py_get_tools_raises": lambda d: tools(d).write_text(tools(d).read_text() + "\ndef _b(self, include=None):\n    raise ValueError('x')\nAirlineTools.get_tools = _b\n"),
 "tools_py_removes_all_tools": lambda d: tools(d).write_text(tools(d).read_text() + "\nREMOVE_TOOLS = {n for n in dir(AirlineTools) if not n.startswith('_')}\n")}
out = {}
FX = Path(tempfile.mkdtemp()) / "tool_fixtures.jsonl"
FX.write_text(json.dumps({"tool": "get_user_details", "args": {"user_id": "mia_li_3668"}, "result": "{}"}) + "\n")
for n, p in cases.items():
    d = Path(tempfile.mkdtemp()) / "c"; shutil.copytree(SEED, d); p(d)
    try:
        r = pregate.run(d, SEED, fixtures=FX, toolkit=TK, traces=[], max_growth=None, strict=False, write_tools=None, tool_dirs=("tools",))
        out[n] = {"ok": r["ok"], "failure": (r.get("failure") or "")[:150], "warnings": [w[:100] for w in r.get("warnings", [])][:2]}
    except Exception as e:
        out[n] = {"raised": f"{type(e).__name__}: {str(e)[:120]}"}
print("E05JSON" + json.dumps(out))
