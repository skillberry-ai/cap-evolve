"""Runs ONE helper invocation inside the helper_smoke subprocess (see ``helper_smoke.py``).

Copied alone into a fresh directory before it runs, so its sys.path[0] holds nothing else. It
installs an audit hook BEFORE importing the helper: sockets, process spawning and reads of
gold/evaluator paths are refused, and any write outside the declared outputs is refused. Every
refusal is also recorded, so a helper that swallows the PermissionError still fails the smoke.
The single result line goes to the real stdout as JSON; the helper's own stdout is captured.
"""
import hashlib
import importlib.util
import io
import json
import os
import re
import runpy
import sys
import traceback

spec = json.load(open(sys.argv[1], encoding="utf-8"))
WS = os.path.realpath(spec["workspace"])
SCRATCH = os.path.join(WS, ".scratch")
OUTS = {os.path.realpath(os.path.join(WS, o.rstrip("/"))): o.endswith("/") for o in spec.get("outputs") or []}
DENY_RE = [re.compile(p) for p in spec.get("deny_patterns") or []]
DENY_ROOTS = [os.path.realpath(r) for r in spec.get("deny_roots") or []]
SYSTEM = tuple(os.path.realpath(p) for p in {sys.prefix, sys.base_prefix, sys.exec_prefix, sys.base_exec_prefix})
HELPER_DIR = os.path.realpath(spec["script_dir"])
violations = []
_real_stdout = sys.__stdout__


def _under(p, root):
    return p == root or p.startswith(root + os.sep)


def _write_ok(p):
    p = os.path.realpath(p)
    if p == os.devnull or _under(p, SCRATCH):
        return True
    return any(p == o or (isdir and _under(p, o)) for o, isdir in OUTS.items())


def _bad(msg):
    violations.append(msg)
    raise PermissionError(f"helper_smoke: {msg}")


_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC


# event -> indexes of the path arguments that get modified (a copy's source is only read)
_MUTATING = {"os.remove": (0,), "os.rmdir": (0,), "os.mkdir": (0,), "os.truncate": (0,), "os.chmod": (0,),
             "os.rename": (0, 1), "os.replace": (0, 1), "shutil.move": (0, 1), "os.link": (1,),
             "os.symlink": (1,), "shutil.copyfile": (1,), "shutil.copymode": (1,), "shutil.rmtree": (0,),
             "os.utime": (0,), "os.chown": (0,), "os.mkfifo": (0,), "os.mknod": (0,),
             "os.setxattr": (0,), "os.removexattr": (0,)}


def hook(event, args):
    # a socket is never created: sendmsg/sendto on an unconnected one would send without connect or bind
    if event in ("socket.__new__", "socket.connect", "socket.bind", "socket.sendto", "socket.getaddrinfo",
                 "socket.gethostbyname", "socket.gethostbyaddr", "socket.getnameinfo"):
        _bad(f"network access ({event})")
    elif event == "ctypes.dlopen" and args and args[0] is None:
        return          # `import ctypes` itself opens the interpreter's own handle (PyDLL(None)); numpy,
                        # pandas and openpyxl import it. Naming a library, or looking a symbol up, is still refused.
    elif event in ("subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.fork",
                   "os.forkpty", "ctypes.dlopen", "ctypes.dlsym"):
        _bad(f"process/foreign-code use ({event})")
    elif event == "open":
        path, mode, flags = args
        if isinstance(path, int):
            return
        p = os.path.realpath(os.fsdecode(path))
        if any(_under(p, r) for r in DENY_ROOTS):
            _bad(f"read of protected path {p}")
        if not (any(_under(p, s) for s in SYSTEM) or _under(p, WS) or _under(p, HELPER_DIR)):
            if any(r.search(p) for r in DENY_RE):
                _bad(f"read of evaluator/gold path {p}")
        writing = (mode and any(c in str(mode) for c in "wax+")) or (flags and flags & _WRITE_FLAGS)
        if writing and not _write_ok(p):
            _bad(f"write outside the declared outputs: {p}")
    elif event in _MUTATING:
        for i in _MUTATING[event]:
            if i < len(args) and isinstance(args[i], (str, bytes, os.PathLike)):
                p = os.path.realpath(os.fsdecode(args[i]))
                if event == "os.mkdir" and _under(p, WS):
                    continue
                if not _write_ok(p):
                    _bad(f"{event} outside the declared outputs: {p}")


def _guard_special_file_creation():
    """``os.mkfifo`` / ``os.mknod`` raise no audit event, so they are wrapped (os and posix) instead."""
    import posix

    def guarded(name, real):
        def inner(path, *a, **k):
            p = os.path.realpath(os.fsdecode(path))
            if not _write_ok(p):
                _bad(f"os.{name} outside the declared outputs: {p}")
            return real(path, *a, **k)
        return inner
    for name in ("mkfifo", "mknod"):
        g = guarded(name, getattr(os, name))
        setattr(os, name, g)
        setattr(posix, name, g)


def digest(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def collect():
    out = {}
    for dp, dn, fn in os.walk(WS):
        dn[:] = [d for d in dn if d != ".scratch"]
        for f in fn:
            full = os.path.join(dp, f)
            out[os.path.relpath(full, WS)] = digest(full)
    return out


before = collect()
res = {"ok": True, "exception": None, "stdout": "", "value": None, "violations": violations}
sys.addaudithook(hook)
_guard_special_file_creation()
captured = io.StringIO()
sys.stdout = captured
try:
    script = spec["script"]
    if spec["mode"] == "import":
        s = importlib.util.spec_from_file_location("helper_under_smoke", script)
        mod = importlib.util.module_from_spec(s)
        s.loader.exec_module(mod)
    elif spec["mode"] == "cli":
        sys.argv = [script] + [str(a) for a in spec.get("argv") or []]
        if spec.get("stdin") is not None:
            sys.stdin = io.StringIO(spec["stdin"])
        try:
            runpy.run_path(script, run_name="__main__")
        except SystemExit as e:
            if e.code not in (None, 0):
                raise RuntimeError(f"exit status {e.code}")
    else:  # call
        s = importlib.util.spec_from_file_location("helper_under_smoke", script)
        mod = importlib.util.module_from_spec(s)
        s.loader.exec_module(mod)
        fn = mod
        for part in spec["call"].split("."):
            fn = getattr(fn, part)
        res["value"] = json.dumps(fn(*spec.get("args") or [], **spec.get("kwargs") or {}),
                                  sort_keys=True, default=str)
except BaseException as e:  # noqa: BLE001 — the smoke reports it, whatever it is
    res["ok"] = False
    res["exception"] = f"{type(e).__name__}: {e}"
    res["traceback"] = traceback.format_exc()[-600:]
finally:
    sys.stdout = _real_stdout
res["stdout"] = captured.getvalue()
after = collect()
res["outputs"] = {k: v for k, v in sorted(after.items()) if before.get(k) != v}
if violations:
    res["ok"] = False
_real_stdout.write("\n@@HELPER_SMOKE_RESULT@@" + json.dumps(res) + "\n")
_real_stdout.flush()
