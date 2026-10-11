"""A candidate tools.py that raises (import error / get_tools raising / missing class) must come back as
error_kind="candidate" rollouts WITHOUT any model call; a clean seed has no fault. Run with the tau2 venv python."""
import importlib.util, shutil, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parents[1] / "core")); sys.path.insert(0, str(HERE / "adapters"))
spec = importlib.util.spec_from_file_location("ad", HERE / "adapters/adapter.py"); ad = importlib.util.module_from_spec(spec); spec.loader.exec_module(ad)

def _cap(tools_src):
    d = Path(tempfile.mkdtemp()) / "c"; shutil.copytree(HERE / "seed_capability", d)
    if tools_src is not None: (d / "tools/tools.py").write_text(tools_src)
    return d

def _check(src, expect_fault):
    A = ad.Adapter(); cap = _cap(src); A.apply(cap)
    assert bool(ad.Adapter._candidate_fault) == expect_fault, ad.Adapter._candidate_fault
    if expect_fault:
        t = ad.Task(id="0", input="0")
        r = A.run_trials([t], cap, n_trials=2, base_seed=0)["0"]
        assert len(r) == 2 and all(x.metadata["error_kind"] == "candidate" and x.error for x in r)
        assert A.run_batch([t], cap)["0"].metadata["error_kind"] == "candidate"

def test_import_error(): _check("raise ImportError('boom')\n", True)
def test_syntax_error(): _check("def (:\n", True)
def test_missing_class(): _check("X = 1\n", False)  # falls back to the pristine class: not a fault
def test_get_tools_raises():
    seed = (HERE / "seed_capability/tools/tools.py").read_text()
    _check(seed + "\n\ndef _boom(self, include=None):\n    raise RuntimeError('x')\nAirlineTools.get_tools = _boom\n", True)
def test_seed_clean(): _check(None, False)
