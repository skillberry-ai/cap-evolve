"""A finished rollout's sandbox container must be released, not left to a 10-minute timeout.

The vendored server (third_party/spreadsheetbench/code_exec_docker/api.py) only reclaims a
container when `cleanup_kernels` sees it idle past a hardcoded `KERNEL_TIMEOUT = 10 * 60`,
or on a force-cleanup at SIGINT. Every rollout gets a fresh conv_id and nothing releases it
when the rollout ends, so at 8-way concurrency ~50 containers are alive at any moment — and
the ones still alive when the server is asked to stop are stopped SERIALLY inside our
shutdown budget. Anything that budget does not reach is orphaned and then runs forever,
because the only process that knew about it is gone.

Run 30691123806 left **176** `conv-capevolve-*` containers running on the runner (all
"unhealthy", load average 14), with `ConnectionRefusedError: Failed to reconnect to kernel
websocket` throughout its sandbox log. At three full seeds (2,279 rollouts each) that
accumulation is a runner-health problem, not a cosmetic one.

Fixed without touching `third_party/`: that directory is a filtered subtree which must stay
byte-identical to upstream for `git subtree pull` to work (NOTICE.md), so the adapter serves
a small wrapper that IMPORTS the vendored handler and adds a `/release` route.
"""

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ADAPTER_DIR = REPO / "templates" / "adapters" / "spreadsheetbench"
VENDOR_API = REPO / "third_party" / "spreadsheetbench" / "code_exec_docker" / "api.py"


def _load_adapter_module():
    for p in (REPO / "core", ADAPTER_DIR, ADAPTER_DIR.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("_sb_adapter_release", ADAPTER_DIR / "adapter.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- the generated wrapper server ---------------------------------------------------------


def test_wrapper_server_is_valid_python():
    mod = _load_adapter_module()
    compile(mod._RELEASE_SERVER, "capevolve_server.py", "exec")


def test_wrapper_adds_release_and_health_without_redefining_execute():
    """It must REUSE the vendored ExecuteHandler — a divergent copy would silently drift."""
    mod = _load_adapter_module()
    src = mod._RELEASE_SERVER
    tree = ast.parse(src)
    classes = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    assert "ReleaseHandler" in classes and "HealthHandler" in classes
    assert "ExecuteHandler" not in classes, "must import the vendored handler, not reimplement it"
    imported = {
        alias.name
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and n.module == "api"
        for alias in n.names
    }
    assert {"ExecuteHandler", "cleanup_kernels"} <= imported
    assert '(r"/release", ReleaseHandler)' in src
    assert '(r"/execute", ExecuteHandler)' in src, "the exec route must still be served"


def test_release_pops_the_entry_before_stopping_it():
    """The vendored `__exit__` is unguarded. If a raising entry stayed in the dict, every
    later `cleanup_kernels` tick would abort on it and reclaim nothing at all — so the pop
    must happen first, and the stop must not propagate."""
    mod = _load_adapter_module()
    tree = ast.parse(mod._RELEASE_SERVER)
    handler = next(n for n in ast.walk(tree)
                   if isinstance(n, ast.ClassDef) and n.name == "ReleaseHandler")
    post = next(n for n in handler.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "post")
    body = ast.dump(post)
    assert "'pop'" in body or '"pop"' in body, "entry must be popped from conv_id_to_kernel"
    pop_at = body.index("pop")
    exit_at = body.index("__exit__")
    assert pop_at < exit_at, "pop BEFORE stopping, so a failing stop cannot poison the dict"
    tries = [n for n in ast.walk(post) if isinstance(n, ast.Try)]
    assert any(
        any(isinstance(h.type, ast.Name) and h.type.id == "Exception" for h in t.handlers)
        and "__exit__" in ast.dump(t)
        for t in tries
    ), "the stop must be wrapped in except Exception"


def test_vendored_api_still_builds_its_app_under_main_guard():
    """The wrapper can only import api.py because upstream builds its Application inside
    `if __name__ == "__main__"`. If an upstream pull changes that, importing would start a
    second server — fail here rather than in a benchmark run."""
    tree = ast.parse(VENDOR_API.read_text(encoding="utf-8"))
    main_guards = [
        n for n in tree.body
        if isinstance(n, ast.If) and "__main__" in ast.dump(n.test)
    ]
    assert main_guards, "api.py must keep its __main__ guard"
    guarded = ast.dump(main_guards[0])
    assert "Application" in guarded and "listen" in guarded, "app/listen must stay guarded"
    top_level = ast.dump(ast.Module(body=[n for n in tree.body if n not in main_guards],
                                    type_ignores=[]))
    assert "listen" not in top_level, "importing api.py must not start a server"


def test_vendored_timeout_is_still_hardcoded_and_long():
    """The whole reason a release route exists. If upstream ever makes KERNEL_TIMEOUT
    configurable, this fix can be simplified — this test is the tripwire."""
    src = VENDOR_API.read_text(encoding="utf-8")
    assert "KERNEL_TIMEOUT = 10 * 60" in src


# --- the adapter side ---------------------------------------------------------------------


def test_sandbox_serves_the_wrapper_not_the_vendored_api():
    src = (ADAPTER_DIR / "adapter.py").read_text(encoding="utf-8")
    assert '"capevolve_server.py", "--port"' in src
    assert '"api.py", "--port"' not in src, "the wrapper is the entrypoint now"
    # api.py must still be COPIED next to it — the wrapper imports it.
    assert 'for name in ("api.py", "jupyter.py")' in src


def test_run_target_releases_on_every_exit_path():
    """The early returns (missing output, denied mount, LLM failure) leak just as easily as
    the happy path, so the call belongs in a `finally` with pre-bound names."""
    src = (ADAPTER_DIR / "adapter.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "run_target")
    tries = [n for n in fn.body if isinstance(n, ast.Try)]
    assert tries and tries[0].finalbody, "run_target's outer try needs a finally"
    final = ast.dump(ast.Module(body=tries[0].finalbody, type_ignores=[]))
    assert "release" in final and "conv_id" in final
    # Pre-bound before the try, or the finally itself raises NameError on an early failure.
    pre = ast.dump(ast.Module(body=[n for n in fn.body if not isinstance(n, ast.Try)],
                              type_ignores=[]))
    assert "sandbox" in pre and "conv_id" in pre


def test_shutdown_budget_scales_with_live_containers():
    """Force-cleanup stops containers serially; a flat 60s budget orphans whatever it does
    not reach. With per-rollout release this is normally ~0 and returns at once."""
    mod = _load_adapter_module()
    sb = object.__new__(mod._Sandbox)

    class _Proc:
        def __init__(self):
            self.waited = None
            self.killed = False
            self.signalled = None

        def poll(self):
            return None

        def send_signal(self, s):
            self.signalled = s

        def wait(self, timeout=None):
            self.waited = timeout

        def kill(self):
            self.killed = True

    class _Log:
        def close(self):
            pass

    for live, expected in ((0, 60.0), (50, 310.0), (10_000, 600.0)):
        sb.proc = _Proc()
        sb._log = _Log()
        sb.live_kernels = lambda live=live: live
        sb.shutdown()
        assert sb.proc.waited == expected, f"live={live} -> budget {sb.proc.waited} != {expected}"
        assert not sb.proc.killed


def test_shutdown_survives_a_server_that_cannot_be_asked():
    """live_kernels() returns None when the server is already wedged — fall back, don't crash."""
    mod = _load_adapter_module()
    sb = object.__new__(mod._Sandbox)

    class _Proc:
        killed = False

        def poll(self):
            return None

        def send_signal(self, s):
            pass

        def wait(self, timeout=None):
            raise subprocess.TimeoutExpired("x", timeout or 0)

        def kill(self):
            type(self).killed = True

    class _Log:
        def close(self):
            pass

    sb.proc = _Proc()
    sb._log = _Log()
    sb.live_kernels = lambda: None
    sb.shutdown()
    assert _Proc.killed, "a server that will not stop must still be killed"


def test_release_never_raises_into_the_rollout():
    """A rollout that produced its output must not be failed by a cleanup hiccup."""
    mod = _load_adapter_module()
    sb = object.__new__(mod._Sandbox)
    sb.port = 1  # nothing is listening: requests will fail
    sb.release("capevolve-1-1_0_deadbeef")  # must be a no-op, not an exception
    assert sb.live_kernels() is None
