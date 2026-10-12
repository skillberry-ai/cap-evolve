"""Suite D surface lock: files of a locked surface come from the pristine seed; violations are counted. No model calls."""
import importlib.util, json, os, shutil, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parents[1] / "core")); sys.path.insert(0, str(HERE / "adapters"))
spec = importlib.util.spec_from_file_location("ad_lock", HERE / "adapters/adapter.py"); ad = importlib.util.module_from_spec(spec); spec.loader.exec_module(ad)
SEED = HERE / "seed_capability"

def _cand(policy=None, tools_append=None):
    d = Path(tempfile.mkdtemp()) / "c"; shutil.copytree(SEED, d)
    if policy is not None: (d / "policy/policy.md").write_text(policy)
    if tools_append: (d / "tools/tools.py").write_text((d / "tools/tools.py").read_text() + tools_append)
    return d

def _run(surfaces, cand):
    vf = Path(tempfile.mkdtemp()) / "surface_violations.json"
    os.environ.update(TAU_SURFACES=surfaces, TAU_SEED_DIR=str(SEED), TAU_VIOLATION_FILE=str(vf))
    eff = ad._surface_lock(cand)
    return eff, (json.loads(vf.read_text()) if vf.exists() else None)

def test_policy_only_blocks_tools_edit():
    c = _cand(policy="Be careful.\n", tools_append="\n# edit\n")
    eff, v = _run("policy", c)
    assert (eff / "policy/policy.md").read_text() == "Be careful.\n"
    assert (eff / "tools/tools.py").read_bytes() == (SEED / "tools/tools.py").read_bytes()
    assert v and v["n_violating_candidates"] == 1 and list(v["violating_candidates"].values())[0]["surfaces"] == ["tools"]

def test_tools_only_blocks_policy_edit():
    c = _cand(policy="Sneaky rule.\n", tools_append="\n# ok\n")
    eff, v = _run("tools", c)
    assert (eff / "policy/policy.md").read_bytes() == (SEED / "policy/policy.md").read_bytes()
    assert b"# ok" in (eff / "tools/tools.py").read_bytes()
    assert v and list(v["violating_candidates"].values())[0]["surfaces"] == ["policy"]

def test_no_violation_when_untouched_and_full_surface_is_noop():
    c = _cand(policy="Only policy.\n")
    eff, v = _run("policy", c)
    assert v is None
    eff2, v2 = _run("policy,tools", c)
    assert eff2 == c and v2 is None
