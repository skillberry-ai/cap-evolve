"""The staged jupyter.py must wait for iopub status:idle after execute_reply.

The shell channel's execute_reply and the iopub stream messages travel on different sockets,
so the reply can arrive first. The vendored `wait_for_messages` returned at the reply and
silently dropped the late output ("[Code executed successfully with no output]"). The adapter
patches its staged copy of jupyter.py (third_party/ stays byte-identical to upstream).

These tests run the patched coroutine against a fake websocket; no docker or jupyter needed.
"""

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ADAPTER = REPO / "benchmarks" / "spreadsheetbench" / "template" / "adapter.py"
VENDOR_JUPYTER = REPO / "third_party" / "spreadsheetbench" / "code_exec_docker" / "jupyter.py"


def _patch_fn():
    """Pull _patch_jupyter_wait out of adapter.py without importing the adapter."""
    import ast

    tree = ast.parse(ADAPTER.read_text(encoding="utf-8"))
    keep = [n for n in tree.body if (isinstance(n, ast.Assign) and any(
        getattr(t, "id", "") == "_WAIT_FOR_MESSAGES_FIXED" for t in n.targets))
        or (isinstance(n, ast.FunctionDef) and n.name == "_patch_jupyter_wait")]
    assert len(keep) == 2
    ns: dict = {}
    exec(compile(ast.Module(keep, []), str(ADAPTER), "exec"), ns)
    return ns["_patch_jupyter_wait"]


def _load_patched_kernel_cls(tmp_path, monkeypatch):
    for name in ("docker", "tornado", "tornado.escape", "tornado.websocket", "tornado.ioloop",
                 "tornado.httpclient"):
        if name not in sys.modules:
            sys.modules[name] = types.ModuleType(name)
    esc = sys.modules["tornado.escape"]
    esc.json_encode, esc.json_decode, esc.url_escape = json.dumps, json.loads, str
    sys.modules["tornado.websocket"].websocket_connect = None
    sys.modules["tornado.websocket"].WebSocketHandler = object
    sys.modules["tornado.ioloop"].IOLoop = object
    sys.modules["tornado.ioloop"].PeriodicCallback = object
    sys.modules["tornado.httpclient"].AsyncHTTPClient = object
    sys.modules["tornado.httpclient"].HTTPRequest = object
    src = _patch_fn()(VENDOR_JUPYTER.read_text(encoding="utf-8"))
    path = tmp_path / "jupyter_patched.py"
    path.write_text(src, encoding="utf-8")
    (tmp_path / "config.json").write_text('{"volumes_path": "/tmp"}', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    spec = importlib.util.spec_from_file_location("jupyter_patched", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.JupyterKernel


class _FakeWS:
    def __init__(self, script):
        self.script = script  # callable(msg_id) -> list of (msg_type, content)
        self.queue: asyncio.Queue = asyncio.Queue()
        self.sent_id = None

    def write_message(self, raw):
        self.sent_id = json.loads(raw)["header"]["msg_id"]
        for mtype, content in self.script(self.sent_id):
            self.queue.put_nowait(json.dumps(
                {"msg_type": mtype, "parent_header": {"msg_id": self.sent_id}, "content": content}))

    async def read_message(self):
        return await self.queue.get()


def _run(kernel_cls, script):
    k = kernel_cls("x", "c")
    k.ws = _FakeWS(script)
    return asyncio.run(k.execute("print(1)", timeout=20))


def _stream(text):
    return ("stream", {"text": text})


IDLE = ("status", {"execution_state": "idle"})
REPLY = ("execute_reply", {"status": "ok"})


def test_late_stream_after_reply_is_kept(tmp_path, monkeypatch):
    cls = _load_patched_kernel_cls(tmp_path, monkeypatch)
    out = _run(cls, lambda _id: [REPLY, _stream("hello\n"), IDLE])
    assert out == "hello\n"


def test_normal_order_still_works(tmp_path, monkeypatch):
    cls = _load_patched_kernel_cls(tmp_path, monkeypatch)
    assert _run(cls, lambda _id: [_stream("a"), _stream("b"), IDLE, REPLY]) == "ab"


def test_no_output_is_still_reported(tmp_path, monkeypatch):
    cls = _load_patched_kernel_cls(tmp_path, monkeypatch)
    assert _run(cls, lambda _id: [REPLY, IDLE]) == "[Code executed successfully with no output]"


def test_error_traceback_collected_until_reply_and_idle(tmp_path, monkeypatch):
    cls = _load_patched_kernel_cls(tmp_path, monkeypatch)
    out = _run(cls, lambda _id: [("error", {"traceback": ["Boom"]}), REPLY, IDLE])
    assert "Boom" in out


def test_missing_idle_does_not_hang(tmp_path, monkeypatch):
    cls = _load_patched_kernel_cls(tmp_path, monkeypatch)
    import time
    t = time.time()
    out = _run(cls, lambda _id: [_stream("x"), REPLY])
    assert out == "x" and time.time() - t < 10


def test_vendored_file_is_untouched():
    src = VENDOR_JUPYTER.read_text(encoding="utf-8")
    assert "IDLE_GRACE_S" not in src and "execution_state" not in src


def test_patch_anchors_exist_in_vendored_file():
    src = VENDOR_JUPYTER.read_text(encoding="utf-8")
    assert src.count("        async def wait_for_messages():") == 1
    assert src.count("        async def interrupt_kernel():") == 1
