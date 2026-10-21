"""A sandbox container that fails to START must be retried, not reported as a failed rollout.

The vendored `JupyterGatewayDocker.__enter__` (third_party/spreadsheetbench/code_exec_docker/jupyter.py)
picks a free port, RELEASES it, and only then asks the engine to publish it, so a concurrent container can
take the port in between. Under rootless podman this surfaces as `rootlessport listen tcp 0.0.0.0:<p>:
bind: address already in use`, and pasta's network-namespace setup fails intermittently on its own
(`netlink: Unexpected sequence number`). On CCC compute nodes that was 2 failed starts in 8 at concurrency 2.

Both happen before the agent's first turn: no LLM call has been made, so a retry costs nothing and the
rollout's outcome is unchanged. The staged copy of jupyter.py is patched to retry the start with a fresh
port; `third_party/` stays byte-identical to upstream.
"""

import ast
import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ADAPTER_DIR = REPO / "templates" / "adapters" / "spreadsheetbench"
VENDOR_JUPYTER = REPO / "third_party" / "spreadsheetbench" / "code_exec_docker" / "jupyter.py"


def _load_adapter_module():
    for p in (REPO / "core", ADAPTER_DIR, ADAPTER_DIR.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("_sb_adapter_start_retry", ADAPTER_DIR / "adapter.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _patched_source(mod):
    return mod._patch_container_start(mod._patch_jupyter_wait(VENDOR_JUPYTER.read_text(encoding="utf-8")))


def test_vendored_file_still_has_the_block_the_patch_replaces():
    """If upstream changes this block the patch must fail loudly, not silently stop applying."""
    mod = _load_adapter_module()
    assert mod._CONTAINER_RUN_VENDORED in VENDOR_JUPYTER.read_text(encoding="utf-8")


def test_patch_refuses_a_changed_vendored_file():
    mod = _load_adapter_module()
    with pytest.raises(RuntimeError, match="no longer applies"):
        mod._patch_container_start("class JupyterGatewayDocker:\n    pass\n")


def test_patched_jupyter_is_valid_python_and_keeps_the_call():
    mod = _load_adapter_module()
    src = _patched_source(mod)
    ast.parse(src)
    assert mod._CONTAINER_RUN_VENDORED not in src
    assert "CAPEVOLVE_CONTAINER_START_RETRY" in src
    assert src.count("self.client.containers.run(") == 1


def test_sandbox_stages_the_patched_copy():
    """The patch only helps if _Sandbox writes the patched text, not the vendored file."""
    src = (ADAPTER_DIR / "adapter.py").read_text(encoding="utf-8")
    assert "_patch_container_start(_patch_jupyter_wait(text))" in src


class _APIError(Exception):
    pass


def _exec_patched_class(mod, attempts):
    """Compile the patched JupyterGatewayDocker against a fake docker module."""
    src = _patched_source(mod)
    tree = ast.parse(src)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "JupyterGatewayDocker")
    fake_docker = types.SimpleNamespace(errors=types.SimpleNamespace(APIError=_APIError, ImageNotFound=KeyError),
                                        from_env=lambda: None)
    ns = {"docker": fake_docker, "os": __import__("os"), "time": types.SimpleNamespace(sleep=lambda s: None),
          "logging": types.SimpleNamespace(warning=attempts.append, info=lambda *a, **k: None),
          "docker_config": {"volumes_path": "/data"}}
    exec(compile(ast.Module(body=[cls], type_ignores=[]), "jupyter_patched", "exec"), ns)
    return ns["JupyterGatewayDocker"]


class _FakeContainers:
    def __init__(self, failures):
        self.failures, self.runs, self.removed = failures, [], []

    def run(self, image, **kw):
        self.runs.append(kw["ports"]["8888/tcp"])
        if len(self.runs) <= self.failures:
            raise _APIError("rootlessport listen tcp 0.0.0.0:1234: bind: address already in use")
        return types.SimpleNamespace(id="c", logs=lambda: b"Jupyter Kernel Gateway is available at")

    def get(self, name):
        return types.SimpleNamespace(remove=lambda force: self.removed.append(name))


def _gateway(cls, failures):
    gw = cls.__new__(cls)
    gw.name, gw.container, gw.url = "conv-x", None, None
    containers = _FakeContainers(failures)
    gw.client = types.SimpleNamespace(containers=containers, images=types.SimpleNamespace(get=lambda i: None))
    ports = iter(range(50000, 50100))
    gw._get_free_port = lambda: next(ports)
    gw._wait_for_container = lambda c: None
    return gw, containers


def test_transient_start_failure_is_retried_with_a_fresh_port():
    mod = _load_adapter_module()
    logged = []
    gw, containers = _gateway(_exec_patched_class(mod, logged), failures=2)
    url = gw.__enter__()
    assert len(containers.runs) == 3
    assert len(set(containers.runs)) == 3, "each attempt must ask for a new port"
    assert url == f"localhost:{containers.runs[-1]}"
    assert containers.removed == ["conv-x", "conv-x"], "a failed start's leftover container must be removed"
    assert len(logged) == 2 and all("CAPEVOLVE_CONTAINER_START_RETRY" in m for m in logged)


def test_persistent_start_failure_still_raises():
    """After the last attempt the error must surface as before (an infra error), not be swallowed."""
    mod = _load_adapter_module()
    gw, containers = _gateway(_exec_patched_class(mod, []), failures=10**6)
    with pytest.raises(_APIError):
        gw.__enter__()
    assert len(containers.runs) == mod.CONTAINER_START_ATTEMPTS
