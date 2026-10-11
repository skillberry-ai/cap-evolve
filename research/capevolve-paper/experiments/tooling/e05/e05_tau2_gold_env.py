import importlib.util, json, os, shutil, sys, tempfile
from pathlib import Path
REPO = Path("/home/dev/projects2/wt-e05")
os.environ.update(MODEL="litellm_proxy/x", LITELLM_PROXY_API_BASE="http://127.0.0.1:9/v1", LITELLM_PROXY_API_KEY="d")
sys.path[:0] = [str(REPO / "templates/adapters/tau2_bench"), str(REPO / "templates/adapters"), str(REPO / "core")]
spec = importlib.util.spec_from_file_location("t2", REPO / "templates/adapters/tau2_bench/adapter.py"); ad = importlib.util.module_from_spec(spec); spec.loader.exec_module(ad)
d = Path(tempfile.mkdtemp()) / "c"; shutil.copytree(REPO / "examples/tau2_airline/seed_capability", d)
t = d / "tools/tools.py"; t.write_text(t.read_text() + "\nAirlineTools.cancel_reservation = lambda self, reservation_id: 'cancelled (no-op)'\n")
ad.Adapter().apply(d)
from tau2.registry import registry
from tau2.evaluator import evaluator
import inspect
src = inspect.getsource(evaluator)
env = registry.get_env_constructor("airline")()
print("E05JSON" + json.dumps({"constructor_used_by_evaluator_is_registry": "registry.get_env_constructor(domain)" in src,
  "env_tools_class_module": type(env.tools).__module__, "cancel_reservation_is_noop": env.tools.cancel_reservation("X") == "cancelled (no-op)"}))
