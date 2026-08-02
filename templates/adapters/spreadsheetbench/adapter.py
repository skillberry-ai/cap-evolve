"""SpreadsheetBench adapter template — optimize a spreadsheet agent's system prompt.

Ready-to-use cap-evolve adapter for SpreadsheetBench
(https://github.com/RUCKBReasoning/SpreadsheetBench). Supports ANY litellm-compatible
provider — configure via env vars (see model_config.py).

SETUP:
  1. Get the harness code (Docker/Jupyter sandbox + prompt/scoring helpers). cap-evolve
     vendors it as a filtered git subtree at third_party/spreadsheetbench — point at that,
     or clone+filter upstream yourself (see third_party/spreadsheetbench/NOTICE.md):
       SPREADSHEETBENCH_HARNESS_DIR=/path/to/cap-evolve/third_party/spreadsheetbench

  2. Fetch the dataset (NOT vendored — ~19MB of xlsx files, fetched at run time):
       ci/benchmarks/spreadsheetbench/fetch_data.sh /some/cache/dir
     then point at the extracted folder (contains dataset.json + spreadsheet/):
       SPREADSHEETBENCH_DATA_DIR=/some/cache/dir/sample_data_200

  3. Install Docker (required — each task runs in its own sandboxed container) and,
     for accurate scoring of formula-bearing outputs, LibreOffice:
       sudo apt install libreoffice-calc   # Debian/Ubuntu
       sudo dnf install libreoffice-calc   # RHEL/Fedora
       brew install --cask libreoffice     # macOS
     Scoring degrades gracefully (skips recalculation) if LibreOffice is absent — but
     silently: a formula-only cell then reads as empty and never matches, so a task the
     agent actually solved scores 0. Treat the "LibreOffice not found" warning as a
     setup error, not a nicety. Upstream's docstring asks for 7.5+; RHEL 9's 7.1.8.1
     recalculates correctly through `--convert-to xlsx` and is verified in use.

  4. Install adapter deps: pip install pandas openpyxl docker tornado requests

  5. Copy this directory to .capevolve/project/adapters/, copy model_config.py alongside.

  6. Set env vars (in .env or shell) — any litellm provider, see model_config.py:
       MODEL=gpt-4.1-mini  OPENAI_API_KEY=sk-…       # OpenAI
       MODEL=anthropic/claude-sonnet-4-6  ANTHROPIC_API_KEY=…  # Anthropic
       MODEL=litellm_proxy/my-model  LITELLM_PROXY_API_BASE=http://proxy:4000  LITELLM_PROXY_API_KEY=…

  7. Optional env vars:
       SPREADSHEETBENCH_TASK_IDS=59196,58568         # comma-separated subset (default: all 200)
       SPREADSHEETBENCH_MAX_TURNS=5                  # rounds of code-exec interaction per task
       SPREADSHEETBENCH_ROWS=5                       # preview rows shown per sheet in the prompt
       SPREADSHEETBENCH_CONCURRENCY=4                # parallel tasks (each = one Docker container)
       SPREADSHEETBENCH_EXEC_TIMEOUT=180             # per code-exec call timeout (s)
       SPREADSHEETBENCH_LIBREOFFICE_BIN=/path/to/soffice

  8. Run: cap-evolve check && cap-evolve run

WHAT THIS OPTIMIZES — ALL the text the agent reads, in two files:
  - prompt.md         the system prompt: who the agent is, how it should work.
  - task_template.md  the per-task user message: how the job is framed, what the fields
                      mean, and the interaction contract. Optional — no file falls back to
                      the built-in _TASK_TEMPLATE, so older capabilities are unaffected.
  Keeping the job description frozen in this file used to leave ~60% of the agent's
  instruction surface un-optimizable, including the line "once that file exists, you are
  done" — which encourages exactly the dominant failure (a wrong-but-present output file).
  Per-task VALUES (instruction, paths, preview, answer_position) are still supplied by the
  adapter through placeholders that live() validates; see _task_template_error.

HOW IT WORKS:
  - tasks()       → loads all SpreadsheetBench instances from the fetched dataset.json.
  - run_target()  → a multi-round CodeAct loop: the model writes Python, code runs in a
                     per-task Docker/Jupyter sandbox (SpreadsheetBench's own harness),
                     the result/traceback feeds back, up to MAX_TURNS rounds. Once the
                     first test case's output file exists, the SAME generated code is
                     replayed (no new LLM calls) against test cases 2 and 3.
  - score()       → compares each test case's output workbook against its answer
                     workbook cell-by-cell over answer_position (SpreadsheetBench's own
                     comparison logic). Reward = Soft Restriction = matches / 3.

NOTE ON SCORING:
  Each task spins up its own Docker container (the upstream harness's design — one
  Jupyter Kernel Gateway container per task, all bind-mounting the same dataset dir at
  /mnt/data). Ensure Docker is running and has enough headroom for
  SPREADSHEETBENCH_CONCURRENCY containers (8GB RAM / 2 CPU each) at once.

  That container is released as soon as its rollout ends (see _Sandbox.release and
  _RELEASE_SERVER). Upstream only reclaims one on a 10-minute idle timeout, which at 8-way
  concurrency means ~50 live at all times and, worse, orphans whatever is still alive when
  the server stops — so the live count tracks concurrency now, not run length.

  The executor image runs as uid 1000, so unless SPREADSHEETBENCH_DATA_DIR happens to be
  owned by uid 1000 the container can read the inputs but not create the output file.
  The adapter widens the mode of the outputs dirs it creates to compensate (see
  _make_container_writable); if a write is still denied, the rollout is reported as an
  infrastructure error rather than as a zero-reward miss, so the optimizer is not sent
  chasing a mount problem it cannot fix from the prompt.

  The SAME uid mismatch also applies to the dataset root itself, which is what gets
  bind-mounted AT /mnt/data — and there it is worse, because a root the container cannot
  TRAVERSE makes every path under the mount unreachable, reads included. The upstream
  912-task archive ships its top-level dir as 0700 (the 200-task sample ships 0755), and
  `tar` preserves stored modes, so extracting it yields a mount no container can enter.
  _preflight_mount widens the root and then VERIFIES the mount before any LLM call, so
  this fails in seconds with a precise message instead of burning a full eval (it cost
  $77 and ~3h of wall time once — run 30691123806).
"""

from __future__ import annotations

import json
import os
import re
import string
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

import model_config

# --- configuration -----------------------------------------------------------
HARNESS_DIR = os.environ.get("SPREADSHEETBENCH_HARNESS_DIR", "")
DATA_DIR = os.environ.get("SPREADSHEETBENCH_DATA_DIR", "")
TASK_IDS = [s.strip() for s in os.environ.get("SPREADSHEETBENCH_TASK_IDS", "").split(",") if s.strip()]
MAX_TURNS = int(os.environ.get("SPREADSHEETBENCH_MAX_TURNS", "5"))
PREVIEW_ROWS = int(os.environ.get("SPREADSHEETBENCH_ROWS", "5"))
CONCURRENCY = int(os.environ.get("SPREADSHEETBENCH_CONCURRENCY", "4"))
EXEC_TIMEOUT = int(os.environ.get("SPREADSHEETBENCH_EXEC_TIMEOUT", "180"))
# Container teardown is bookkeeping, not work: keep it short so a hung server delays a
# finished rollout by seconds, never by the exec timeout.
RELEASE_TIMEOUT = int(os.environ.get("SPREADSHEETBENCH_RELEASE_TIMEOUT", "30"))
# How many further rounds the agent gets AFTER it has first written a graded output file, to
# re-open it, check the values and correct them. Was effectively 0: the loop broke the instant
# the file appeared, so "verify your work" was unreachable no matter what the skill said, and
# agents used ~2 of 30 available turns. Bounded rather than unbounded because each round is a
# real LLM call: at MAX_TURNS=30 an unbounded loop is ~15x the token cost of the old behaviour.
VERIFY_TURNS = int(os.environ.get("SPREADSHEETBENCH_VERIFY_TURNS", "3"))
LIBREOFFICE_BIN = os.environ.get("SPREADSHEETBENCH_LIBREOFFICE_BIN", "")

# Which of SpreadsheetBench's two OJ-style metrics becomes the optimization target.
#   soft (default) — matches / 3, i.e. partial credit per test case.
#   hard           — 1.0 only when ALL THREE test cases match, 0.0 otherwise.
# Both are computed on every rollout regardless (see score()); this only decides which one
# is `reward`, and therefore what the gate and the headline are measured on. `hard` exists
# for comparisons against work that reports the benchmark's "native hard score" — mixing the
# two silently flatters us, because soft >= hard by construction.
SCORING = os.environ.get("SPREADSHEETBENCH_SCORING", "soft").strip().lower()
if SCORING not in ("soft", "hard"):
    raise RuntimeError(
        f"SPREADSHEETBENCH_SCORING={SCORING!r} is not recognized (want 'soft' or 'hard')."
    )

# Where the vendored sandbox bind-mounts SPREADSHEETBENCH_DATA_DIR inside every container
# (code_exec_docker/jupyter.py hardcodes this bind target).
_CONTAINER_DATA_ROOT = "/mnt/data"
LIBRE_TIMEOUT = int(os.environ.get("SPREADSHEETBENCH_LIBREOFFICE_TIMEOUT", "120"))

_TASK_TEMPLATE = """You need to solve the following spreadsheet manipulation question. It contains six pieces of information:
- instruction: the question about spreadsheet manipulation.
- spreadsheet_path: the path of the spreadsheet file you need to manipulate.
- spreadsheet_content: the first few rows of the content of the spreadsheet file.
- instruction_type: Cell-Level Manipulation (answer_position is exact cell(s)) or Sheet-Level Manipulation (answer_position is the maximum range you may modify).
- answer_position: the cell(s)/range you must modify or fill in.
- output_path: write the modified spreadsheet file to this exact path.

### instruction
{instruction}

### spreadsheet_path
{spreadsheet_path}

### spreadsheet_content
{spreadsheet_content}

### instruction_type
{instruction_type}

### answer_position
{answer_position}

### output_path
{output_path}

You have up to {max_turns} rounds of interaction. In each round, reply with exactly ONE python code block:
1. Information-gathering code (e.g. inspecting the file) — the execution result is returned to you.
2. Final solution code that writes the modified file to output_path — once that file exists, you are done.
If your code raises an error, the traceback will be returned to you; fix the code and try again.
"""

_DEFAULT_SYSTEM_PROMPT = (Path(__file__).resolve().parent / "seed_capability" / "prompt.md").read_text(
    encoding="utf-8"
) if (Path(__file__).resolve().parent / "seed_capability" / "prompt.md").exists() else (
    "You are a spreadsheet expert who can manipulate spreadsheets through Python code."
)


# ---------------------------------------------------------------------------
# Vendored-harness loading (lazy — no filesystem/import work at module import time)
# ---------------------------------------------------------------------------


class _Vendor:
    """Lazily-imported callables from third_party/spreadsheetbench (see SETUP)."""

    _mod: dict = {}

    @classmethod
    def get(cls):
        if cls._mod:
            return cls._mod

        if not HARNESS_DIR:
            raise RuntimeError(
                "SPREADSHEETBENCH_HARNESS_DIR is not set. Point it at a checkout of "
                "the SpreadsheetBench harness code — cap-evolve vendors one at "
                "third_party/spreadsheetbench. See this file's SETUP docstring."
            )
        base = Path(HARNESS_DIR).expanduser()
        code_dir, eval_dir, inf_dir = base / "code_exec_docker", base / "evaluation", base / "inference"
        for d in (code_dir, eval_dir, inf_dir):
            if not d.is_dir():
                raise RuntimeError(
                    f"SPREADSHEETBENCH_HARNESS_DIR={base} is missing expected subdir {d.name}/ "
                    "— is this a SpreadsheetBench checkout?"
                )

        for d in (eval_dir, inf_dir):
            if str(d) not in sys.path:
                sys.path.insert(0, str(d))

        import code_exec as _code_exec
        import evaluation as _sb_evaluation
        import open_spreadsheet as _open_spreadsheet

        cls._mod = {
            "code_dir": code_dir,
            "extract_code": _code_exec.extract_code,
            "exec_code": _code_exec.exec_code,
            "compare_workbooks": _sb_evaluation.compare_workbooks,
            "find_libreoffice": _open_spreadsheet.find_libreoffice,
            # NB: the vendored `just_open_libreoffice` is deliberately NOT used — see
            # _recalc_workbook. It shares one implicit LibreOffice user profile across calls,
            # so it can only run serialized, and it prints to stdout on every failure path.
        }
        return cls._mod


def _data_dir() -> Path:
    if not DATA_DIR:
        raise RuntimeError(
            "SPREADSHEETBENCH_DATA_DIR is not set. Run "
            "ci/benchmarks/spreadsheetbench/fetch_data.sh and point at the extracted "
            "sample_data_200/ folder. See this file's SETUP docstring."
        )
    d = Path(DATA_DIR).expanduser()
    if not (d / "dataset.json").exists():
        raise RuntimeError(f"SPREADSHEETBENCH_DATA_DIR={d} has no dataset.json.")
    return d


_dataset_cache: list[dict] | None = None


def _load_dataset() -> list[dict]:
    global _dataset_cache
    if _dataset_cache is not None:
        return _dataset_cache

    d = _data_dir()
    entries = json.loads((d / "dataset.json").read_text(encoding="utf-8"))
    if TASK_IDS:
        want = set(TASK_IDS)
        entries = [e for e in entries if str(e["id"]) in want]
        if not entries:
            raise RuntimeError(f"None of SPREADSHEETBENCH_TASK_IDS={TASK_IDS} are in the dataset.")

    _dataset_cache = entries
    return _dataset_cache


def _entries_by_id() -> dict[str, dict]:
    return {str(e["id"]): e for e in _load_dataset()}


def _libreoffice_bin() -> str | None:
    if LIBREOFFICE_BIN:
        return LIBREOFFICE_BIN
    return _Vendor.get()["find_libreoffice"]()


# ---------------------------------------------------------------------------
# Sandbox: one Tornado/Jupyter-gateway server per adapter process, one Docker
# container per task (minted by the server itself, keyed by conv_id).
# ---------------------------------------------------------------------------

# The vendored server only reclaims a container on a 10-MINUTE IDLE TIMEOUT
# (api.py's hardcoded KERNEL_TIMEOUT) or on a force-cleanup at SIGINT. Nothing releases a
# kernel when its rollout ENDS, and every rollout gets a fresh conv_id — so containers pile
# up until the timeout, and the ones still live when the server is asked to stop get stopped
# SERIALLY inside our shutdown budget. Whatever the budget does not cover is orphaned and
# then runs FOREVER, because the only process that knew about it is gone. Run 30691123806
# left 176 `conv-capevolve-*` containers running (all "unhealthy", load average 14), and its
# sandbox log is full of `ConnectionRefusedError: Failed to reconnect to kernel websocket`.
#
# This wrapper adds the missing lifecycle call: a `/release` route that shuts one conv_id's
# container down NOW. It imports the vendored handler rather than editing it, because
# `third_party/` is a filtered subtree that must stay byte-identical to upstream for
# `git subtree pull` to keep working (see third_party/spreadsheetbench/NOTICE.md) — and
# api.py builds its Application under `if __name__ == "__main__"`, so importing it yields
# ExecuteHandler + cleanup_kernels with no side effect beyond module import.
_RELEASE_SERVER = '''\
"""cap-evolve wrapper around the vendored api.py — adds POST /release.

Generated by templates/adapters/spreadsheetbench/adapter.py; not upstream code. The
vendored ExecuteHandler and cleanup_kernels are imported unchanged; the only addition is
an explicit per-conversation teardown, so a finished rollout's container goes away at once
instead of idling for KERNEL_TIMEOUT and risking an orphan at shutdown.
"""
import argparse
import json
import logging
import os
import signal

import tornado.httpserver
import tornado.ioloop
import tornado.web

from api import ExecuteHandler, cleanup_kernels

logging.basicConfig(level=logging.INFO)


class ReleaseHandler(tornado.web.RequestHandler):
    async def post(self):
        try:
            convid = json.loads(self.request.body or b"{}").get("convid")
        except ValueError:
            convid = None
        entry = self.application.conv_id_to_kernel.pop(convid, None)
        released = False
        if entry is not None:
            # Pop FIRST: even if the stop below fails, the periodic cleanup must never see
            # this entry again — its own __exit__ is unguarded, and one raising entry would
            # abort every later tick and stop reclaiming anything at all.
            try:
                entry.kernel_wrapper.__exit__(None, None, None)
                released = True
            except Exception as e:  # noqa: BLE001
                logging.info("release: stopping %s failed: %s", convid, e)
        self.write(json.dumps({"released": released}))


class HealthHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(json.dumps({"live_kernels": len(self.application.conv_id_to_kernel)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    app = tornado.web.Application([
        (r"/execute", ExecuteHandler),
        (r"/release", ReleaseHandler),
        (r"/health", HealthHandler),
    ])
    app.conv_id_to_kernel = {}

    periodic_cleanup = tornado.ioloop.PeriodicCallback(
        lambda: cleanup_kernels(app),
        int(os.environ.get("CLEANUP_TIMEOUT_MS", 60000)),
    )
    periodic_cleanup.start()

    def signal_handler(signum, frame, app):
        logging.info("Received SIGINT, cleaning up...")
        cleanup_kernels(app, force=True)
        tornado.ioloop.IOLoop.current().stop()
        logging.info("Cleanup complete, shutting down.")

    signal.signal(signal.SIGINT, lambda signum, frame: signal_handler(signum, frame, app))
    server = tornado.httpserver.HTTPServer(app)
    server.listen(args.port)
    tornado.ioloop.IOLoop.current().start()
'''


class _Sandbox:
    def __init__(self) -> None:
        vendor = _Vendor.get()
        data_dir = _data_dir()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        self.port = sock.getsockname()[1]
        sock.close()

        self.runtime_dir = Path(tempfile.mkdtemp(prefix="capevolve_sb_sandbox_"))
        for name in ("api.py", "jupyter.py"):
            (self.runtime_dir / name).write_text(
                (vendor["code_dir"] / name).read_text(encoding="utf-8"), encoding="utf-8"
            )
        (self.runtime_dir / "config.json").write_text(
            json.dumps({"volumes_path": str(data_dir.resolve())}), encoding="utf-8"
        )
        # Serve the wrapper, not api.py itself: same handlers plus /release (see above).
        (self.runtime_dir / "capevolve_server.py").write_text(_RELEASE_SERVER, encoding="utf-8")

        log_path = self.runtime_dir / "server.log"
        self._log = log_path.open("w", encoding="utf-8")
        self.proc = subprocess.Popen(
            [sys.executable, "capevolve_server.py", "--port", str(self.port)],
            cwd=str(self.runtime_dir),
            stdout=self._log,
            stderr=subprocess.STDOUT,
        )
        self._wait_ready()

    def _wait_ready(self, timeout: float = 30.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(
                    f"SpreadsheetBench sandbox server exited early (code {self.proc.returncode}); "
                    f"see {self.runtime_dir / 'server.log'}"
                )
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=1):
                    return
            except OSError:
                time.sleep(0.3)
        raise RuntimeError(f"SpreadsheetBench sandbox server did not start within {timeout}s")

    def execute(self, conv_id: str, code: str) -> str:
        import requests

        resp = requests.post(
            f"http://127.0.0.1:{self.port}/execute",
            data=json.dumps({"convid": conv_id, "code": code}),
            timeout=EXEC_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["result"]

    def release(self, conv_id: str) -> None:
        """Tear down one rollout's container now that its rollout is over.

        Best-effort and never fatal: a rollout that produced its output must not be failed
        because cleanup hiccuped. Skipping it only costs what the vendored server would have
        done anyway on its 10-minute idle timeout — the point is to not let 8 concurrent
        rollouts/minute accumulate for ten minutes and then be orphaned at shutdown.
        """
        try:
            import requests  # inside the try: this runs in a finally, where NOTHING may raise

            requests.post(
                f"http://127.0.0.1:{self.port}/release",
                data=json.dumps({"convid": conv_id}),
                timeout=RELEASE_TIMEOUT,
            )
        except Exception:  # noqa: BLE001
            pass

    def live_kernels(self) -> int | None:
        """How many containers the server currently holds; None if it cannot be asked."""
        try:
            import requests

            resp = requests.get(f"http://127.0.0.1:{self.port}/health", timeout=RELEASE_TIMEOUT)
            return int(resp.json()["live_kernels"])
        except Exception:  # noqa: BLE001
            return None

    def client_for(self, conv_id: str):
        class _Client:
            def execute(_self, code: str) -> str:
                return self.execute(conv_id, code)

        return _Client()

    def shutdown(self) -> None:
        if self.proc.poll() is not None:
            return
        # SIGINT force-cleanup stops every remaining container SERIALLY, so the budget has
        # to scale with how many are left rather than being a flat 60s: whatever we kill the
        # server before it reaches is orphaned and runs forever. With per-rollout release()
        # this is normally ~0 containers and returns immediately.
        live = self.live_kernels() or 0
        budget = min(600.0, 60.0 + 5.0 * live)
        try:
            self.proc.send_signal(signal.SIGINT)
            self.proc.wait(timeout=budget)
        except Exception:  # noqa: BLE001
            self.proc.kill()
        finally:
            self._log.close()


_sandbox: _Sandbox | None = None
_sandbox_lock = threading.Lock()
# NOTE: there is deliberately NO global LibreOffice lock. _recalc_workbook gives every
# invocation its own user-profile dir, which is what previously forced serialization.


def _get_sandbox() -> _Sandbox:
    global _sandbox
    with _sandbox_lock:
        if _sandbox is None:
            # Check the mount BEFORE the first container exists. run_target calls us
            # before its first LLM call, so an unusable mount costs ~$0 per rollout and
            # every rollout carries the same precise reason — which the report renders as
            # an infra error and assert_run.py's >50% gate turns into a failed job.
            _preflight_mount(_data_dir())
            _sandbox = _Sandbox()
            import atexit

            atexit.register(_sandbox.shutdown)
        return _sandbox


def _sanitize_conv_id(s: str) -> str:
    """Docker container names need [A-Za-z0-9_.-], starting with an alnum."""
    out = re.sub(r"[^A-Za-z0-9_.-]", "_", s)
    return out if out and out[0].isalnum() else f"t{out}"


def _make_container_writable(p: Path, *, sticky: bool = False) -> None:
    """Widen a bind-mounted dir so the sandbox container can create files in it.

    The executor image (docker.io/xingyaoww/codeact-executor) runs as a FIXED uid
    (1000), which is generally NOT the uid running this adapter. A dir we create here
    is owned by our uid at mode 0755, so the container gets r-x: it can READ the input
    workbooks but cannot create the output file, and every rollout dies with
    `PermissionError: [Errno 13] ... <n>_<id>_output.xlsx` and scores 0. Widening the
    mode is the least invasive fix — running the container as our uid instead breaks
    the image's own jupyter HOME.

    `sticky` (0o1777, as on /tmp) is for the shared outputs root, where many
    concurrent rollouts write side by side: it lets each create its own subdir while
    preventing one from deleting another's. Best-effort — if we do not own a
    pre-existing dir the chmod fails, and the write itself then surfaces the real
    error instead of this being silently papered over.
    """
    try:
        os.chmod(p, 0o1777 if sticky else 0o777)
    except OSError:
        pass


# a+rX, minus the owner bits already present: enough for the container to enter a dir and
# read what is inside, and deliberately NOT a+w — the dataset tree is INPUT, nothing in the
# sandbox may rewrite it.
#
# BOTH the group and other classes must be granted, not just other. POSIX checks the
# classes in order and the FIRST match decides: the executor image runs as uid 1000 gid
# 100(users) and the dataset is typically owned by <runner>:users, so the container matches
# the GROUP class and never falls through to other. A file at 0o604 (`-rw----r--`) is
# therefore still EACCES for it — verified against the real image, which is why this is
# 0o055/0o044 rather than 0o005/0o004.
_TRAVERSE_BITS = 0o055   # dirs: g+rx, o+rx
_READ_BITS = 0o044       # files: g+r, o+r


def _make_container_readable(p: Path) -> int:
    """OR o+rX onto `p` so the container's uid can traverse/read it. Returns the mode.

    Unlike _make_container_writable this widens as LITTLE as possible, because it is
    applied to the dataset tree rather than to a scratch dir we own. Best-effort: a
    foreign-owned dir cannot be chmod'ed, and _preflight_mount then reports the real
    mode instead of this failing silently.
    """
    try:
        mode = os.stat(p).st_mode & 0o7777
    except OSError:
        return 0
    if mode & _TRAVERSE_BITS != _TRAVERSE_BITS:
        try:
            os.chmod(p, mode | _TRAVERSE_BITS)
            mode = os.stat(p).st_mode & 0o7777
        except OSError:
            pass
    return mode


def _widen_tree_for_container(root: Path) -> None:
    """OR o+rX across the dataset tree, the `chmod -R a+rX` fetch_data.sh applies on extract.

    Needed for a tree extracted by an older revision of the fetcher, or fetched by hand: the
    modes `tar` writes come from the archive AND the extracting shell's umask, so the input
    workbooks themselves can land 0640. Best-effort per entry (a foreign-owned file simply
    stays as it is and the caller then reports it), and O(files) with no stat churn beyond
    the walk — a few thousand entries, well under a second, once per process.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        for name in (*dirnames, *filenames):
            p = Path(dirpath) / name
            try:
                mode = os.stat(p).st_mode & 0o7777
                want = mode | (_TRAVERSE_BITS if p.is_dir() else _READ_BITS)
                if want != mode:
                    os.chmod(p, want)
            except OSError:
                continue


def _preflight_mount(data_dir: Path) -> None:
    """Verify the container can actually USE the bind mount, before any LLM call.

    The dataset root is bind-mounted at /mnt/data, so if the container's uid cannot
    traverse it then EVERY path under the mount is unreachable — `open()` on an input
    workbook and even `Path.exists()` raise EACCES (a missing search bit, not a missing
    file). The upstream 912-task archive ships its top-level dir as 0700, and `tar`
    preserves that, so the extracted tree looks perfect on inspection (`spreadsheet/` and
    the workbooks are 0755/0644) while the ONE dir at the top locks everyone out.

    We widen what we can and then check, rather than assuming the chmod worked: the data
    dir may be owned by another uid (a shared cache), in which case the run must stop
    here. Raising is the whole point — a silent mount fault reads as a capability score
    of 0.000, and the optimizer then "fixes" it by editing infrastructure. Run
    30691123806 spent $77.49 and ~3h before this became visible.

    Host-side and O(1): no container is started, so it is safe to call per process.
    """
    mode = _make_container_readable(data_dir)
    if mode & _TRAVERSE_BITS != _TRAVERSE_BITS:
        raise RuntimeError(
            f"spreadsheetbench mount is unusable: SPREADSHEETBENCH_DATA_DIR={data_dir} is "
            f"mode 0o{mode & 0o777:03o}, so the sandbox container's uid cannot traverse it "
            f"— every read AND write under /mnt/data would fail with EACCES. The upstream "
            f"912-task archive ships this dir as 0700; fix with "
            f"`chmod -R a+rX {data_dir}` (fetch_data.sh does this on extract)."
        )

    # The inputs themselves must be readable through the mount, not just the root. Which
    # modes `tar` leaves depends on the extracting shell's umask (the runner's 077 yields a
    # 0700 root, an interactive 027 yields 0750 dirs and 0640 workbooks), so check a real
    # file rather than trusting the root's mode alone.
    probe = next((data_dir / "spreadsheet").glob("*/*_input.xls*"), None)

    def _readable(p: Path) -> bool:
        # Both classes, for the group-precedence reason documented at _READ_BITS.
        return os.stat(p).st_mode & _READ_BITS == _READ_BITS

    if probe is not None and not _readable(probe):
        _widen_tree_for_container(data_dir)  # we own it → heal it, same as fetch_data.sh
    if probe is not None and not _readable(probe):
        raise RuntimeError(
            f"spreadsheetbench mount is unusable: input workbook {probe} is mode "
            f"0o{os.stat(probe).st_mode & 0o777:03o} — not readable by the container's uid, "
            f"and we do not own it so it cannot be widened here. "
            f"Fix with `chmod -R a+rX {data_dir}`."
        )

    # And the outputs root must be writable by the container, or nothing can be scored.
    outputs_root = data_dir / "outputs"
    outputs_root.mkdir(parents=True, exist_ok=True)
    _make_container_writable(outputs_root, sticky=True)
    if os.stat(outputs_root).st_mode & 0o022 != 0o022:  # both classes, as above
        raise RuntimeError(
            f"spreadsheetbench mount is unusable: {outputs_root} is mode "
            f"0o{os.stat(outputs_root).st_mode & 0o777:03o} — the container's uid cannot "
            f"create its output file there. It must be world-writable (see "
            f"_make_container_writable); a foreign-owned outputs dir cannot be widened by us."
        )


def _reclaim_container_file(p: Path) -> bool:
    """Make a container-created output file writable by US. Returns True if it now is.

    ``_make_container_writable`` widens the DIRS we create so the uid-1000 container can
    create its output file — but that file is then owned by uid 1000 at its umask (~0644),
    so WE cannot write it. Scoring needs to: ``just_open_libreoffice`` recalculates cached
    formula values by converting into a ``/tmp`` tempdir and moving the result back over the
    original. ``/tmp`` and the data dir are different filesystems, so that move falls back
    to ``copy2``, which opens the existing container-owned file for WRITING and dies with
    ``[Errno 13] Permission denied: <n>_<id>_output.xlsx``.

    ``chmod`` cannot fix this — you may not chmod a file you do not own. Replacing the file
    with a byte-identical copy we DO own can: the file stays readable (0644), and both the
    create and the rename need write+execute on the *directory*, which is already 0o777 and
    deliberately NOT sticky for these per-rollout dirs. ``os.replace`` is atomic, so a
    concurrent reader never observes a partial file.

    Best-effort: on failure the caller reports the recalc as failed rather than silently
    comparing stale cached values, which is how this hid for so long.
    """
    if os.access(p, os.W_OK):
        return True
    try:
        data = p.read_bytes()
    except OSError:
        return False
    tmp = p.with_name(p.name + ".hostcopy")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, p)
        return True
    except OSError:
        try:
            tmp.unlink()
        except OSError:
            pass
        return False


def _recalc_workbook(path: Path, soffice: str, *, timeout: float = LIBRE_TIMEOUT) -> bool:
    """Recalculate a workbook's cached formula values in place. True on success.

    openpyxl reads cached values with ``data_only=True``; a formula cell the agent wrote has
    no cached value until something recalculates it, so it reads as ``None`` and can never
    match. Round-tripping through headless LibreOffice fills the cache.

    This replaces the vendored ``just_open_libreoffice``, for two reasons:

    1. CONCURRENCY. The vendored helper lets soffice use its default user profile, and two
       headless instances sharing one profile conflict — so it had to run behind a global
       lock. That lock is the full tier's scoring bottleneck: 912 tasks x 3 test cases is
       2,736 serialized soffice startups per evaluation, and no amount of
       SPREADSHEETBENCH_CONCURRENCY helps, because the lock is process-wide. Giving each
       invocation its own ``-env:UserInstallation`` profile removes the conflict, so recalc
       parallelizes with the rest of scoring.
    2. STDOUT. It prints on every failure path, and phase stdout is a pure-JSON contract.
       ``capture_output`` keeps that here regardless of the harness-level guard.

    Failure is reported, never raised: the caller records it so a run cannot silently score
    un-recalculated cells (which reads as a prompt defect and burns optimizer budget).
    """
    path = Path(path)
    with tempfile.TemporaryDirectory(prefix="capevolve_sb_libre_") as td:
        outdir = Path(td) / "out"
        outdir.mkdir()
        profile = Path(td) / "profile"          # unique per call -> safe to run concurrently
        cmd = [
            soffice, "--headless", "--calc",
            f"-env:UserInstallation=file://{profile}",
            "--convert-to", "xlsx:Calc MS Excel 2007 XML",
            "--outdir", str(outdir), str(path),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except (subprocess.TimeoutExpired, OSError):
            return False
        if proc.returncode != 0:
            return False
        produced = outdir / f"{path.stem}.xlsx"
        if not produced.is_file():
            return False
        try:
            # Cross-filesystem (/tmp -> data dir), so this is copy2+unlink under the hood;
            # it needs `path` to be writable by us, which _reclaim_container_file ensures.
            shutil.move(str(produced), str(path))
        except OSError:
            return False
        return True


_FENCE_RE = re.compile(r"```[a-zA-Z0-9_+-]*[ \t]*\r?\n(.*?)```", re.DOTALL)

_NO_CODE_REMINDER = (
    "No python code block was found in your reply, so NOTHING was executed and the "
    "round was wasted. Reply with exactly ONE ```python fenced code block containing "
    "runnable code, with no prose or XML outside the block."
)


def _extract_python(vendor, response: str) -> str | None:
    """Extract the fenced python block, or None when the reply contains no code fence.

    The vendored `extract_code` falls back to the RAW response when there is no
    ```python fence, so a reply that is prose — or a literal `<function_calls>` block,
    which some models emit — gets sent to the Jupyter kernel verbatim and burns a
    round on `SyntaxError: invalid syntax`. Returning None lets the caller re-state the
    contract instead of spending the round.
    """
    if "```python" in response:
        # Delegate so fenced replies stay byte-identical to upstream's behaviour.
        return vendor["extract_code"](response)
    m = _FENCE_RE.search(response)
    return m.group(1).rstrip("\n") if m else None


def _cleanup_output_dir(rollout) -> None:
    """Drop a rollout's per-rollout output dir once nothing more will read it.

    Without this a full run (912 tasks × trials × iterations) accumulates thousands of
    per-rollout dirs inside SPREADSHEETBENCH_DATA_DIR. Safe on every path: the dir is
    owned by us (we created it), so rmtree succeeds even though the files inside were
    written by the container's uid.
    """
    run_tag = (getattr(rollout, "metadata", None) or {}).get("run_tag")
    if not run_tag:
        return
    try:
        shutil.rmtree(_data_dir() / "outputs" / run_tag, ignore_errors=True)
    except RuntimeError:
        pass  # _data_dir() unset — nothing was created, nothing to clean


def _sandbox_access_denied(exec_results: list[str], container_out_dir: str) -> str | None:
    """Return the offending line if the sandbox was denied access through the bind mount.

    A PermissionError/OSError on a path under the mount is an INFRASTRUCTURE fault, not a
    defect in the prompt under optimization. Reporting it as a plain zero-reward miss sends
    the optimizer chasing an unfixable wall; surfacing it as a rollout error routes it
    through score()'s "do not optimize against it" path instead.

    Two distinct faults land here, and telling them apart is what makes the report
    actionable — the earlier write-only version of this function reported BOTH as "the
    output dir is not writable", which cost hours of hunting the wrong thing:
      - a denial under `container_out_dir` → the OUTPUT dir is not writable (the classic
        uid mismatch on a dir we created; see _make_container_writable).
      - a denial anywhere else under _CONTAINER_DATA_ROOT — typically on an INPUT workbook
        — → the mount ROOT is not traversable, so nothing under it is reachable at all
        (see _preflight_mount). Another rollout's output dir is NOT ours: ignore it.
    """
    other_out_dirs = f"{_CONTAINER_DATA_ROOT}/outputs/"
    for res in reversed(exec_results):
        if "PermissionError" not in res and "OSError" not in res:
            continue
        for line in res.splitlines():
            if "PermissionError" not in line and "OSError" not in line:
                continue
            if container_out_dir in line:
                return line.strip()
            if _CONTAINER_DATA_ROOT in line and other_out_dirs not in line:
                return line.strip()
    return None


# ---------------------------------------------------------------------------
# Prompting
# ---------------------------------------------------------------------------


_TEMPLATE_COMMENT_RE = re.compile(r"<!--.*?-->\s*", re.DOTALL)
# Filled in per task, so they must survive any edit the optimizer makes. {max_turns} is
# cosmetic (it only tells the agent its round budget) and may be dropped.
_TEMPLATE_REQUIRED = frozenset({
    "instruction", "spreadsheet_path", "spreadsheet_content",
    "instruction_type", "answer_position", "output_path",
})
_TEMPLATE_OPTIONAL = frozenset({"max_turns"})


def _artifact_stamp(path: Path):
    """A change-detecting stamp for the graded output file, or None when it does not exist.

    Used to tell "the code that WROTE the answer" apart from "the code that merely inspected
    it". That distinction only started to matter once the agent was allowed to keep working
    after its first write: cases 2 and 3 are scored by REPLAYING the agent's code, so replaying
    a verification snippet (which writes nothing) would produce no output for them and score 0
    on two of three test cases — turning a fix into a large regression.
    """
    try:
        st = path.stat()
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def _read_task_template(ctx) -> str:
    """The agent's first user message, as editable capability text.

    Previously this lived only in _TASK_TEMPLATE, i.e. frozen in the adapter — so ~60% of the
    text the agent reads (the field semantics, the interaction contract, and the line "once
    that file exists, you are done") could not be optimized, while the thing it most needs to
    fix — writing a wrong-but-present output file — is exactly what that line encourages.
    Comparable published work optimizes a single skill document that covers this same ground,
    so keeping it frozen made our editable surface strictly smaller than theirs.

    A capability that ships `task_template.md` overrides the built-in; the leading HTML
    comment (which documents the placeholder contract for the optimizer) is stripped so the
    agent never sees it. No file ⇒ the built-in, so older capabilities are unaffected.
    """
    path = Path(ctx) / "task_template.md"
    if not path.exists():
        return _TASK_TEMPLATE
    return _TEMPLATE_COMMENT_RE.sub("", path.read_text(encoding="utf-8"), count=1).strip() + "\n"


def _task_template_error(ctx) -> str | None:
    """Why this candidate's template is unusable, or None if it is fine.

    Returns a message rather than raising, because the CALLER decides the consequence and the
    consequence must never be "abort the run". harness.run_step wraps the optimizer call in
    try/except precisely so a bad proposal costs one iteration rather than the whole run — but
    the evaluate_candidate call right below it is NOT wrapped, so anything this raised from
    live() would propagate and kill a multi-hour run, destroying the sealed evaluation over one
    bad text edit. Instead every rollout returns this as its error: the candidate scores 0, the
    gate rejects it, the run continues, and the optimizer READS the reason in its next
    trajectories and learns not to break the contract.

    Both directions are unusable: a MISSING required placeholder means the agent is never told
    (say) where to write its answer, and an UNKNOWN one raises KeyError inside str.format on
    every single task.
    """
    path = Path(ctx) / "task_template.md"
    if not path.exists():
        return None
    text = _read_task_template(ctx)
    try:
        found = {f for _, f, _, _ in string.Formatter().parse(text) if f}
    except ValueError as e:  # unbalanced braces — a literal brace must be doubled
        return (f"task_template.md is not a valid format string ({e}). A literal brace must "
                f"be written as {{{{ or }}}}.")
    missing = sorted(_TEMPLATE_REQUIRED - found)
    unknown = sorted(found - _TEMPLATE_REQUIRED - _TEMPLATE_OPTIONAL)
    if missing or unknown:
        problems = []
        if missing:
            problems.append(f"missing required placeholder(s): {', '.join('{%s}' % m for m in missing)}")
        if unknown:
            problems.append(f"unknown placeholder(s): {', '.join('{%s}' % u for u in unknown)}")
        return (
            "task_template.md broke the placeholder contract — " + "; ".join(problems)
            + f". Required: {', '.join('{%s}' % r for r in sorted(_TEMPLATE_REQUIRED))}"
            + f" · optional: {', '.join('{%s}' % o for o in sorted(_TEMPLATE_OPTIONAL))}."
            + " Restore the placeholder and this candidate can be scored; as it stands every"
            + " task scores 0 because the agent is not told where to write its answer."
        )
    return None


def _read_system_prompt(ctx) -> str:
    """The capability text. An EMPTY prompt.md means deliberately NO skill text.

    The distinction matters for a no-skill control: a file that EXISTS but is empty is the
    capability saying "there is nothing here", and must not silently fall back to
    _DEFAULT_SYSTEM_PROMPT — that would measure the built-in prompt while claiming to measure
    an unskilled agent. A MISSING file still falls back, since that means the capability was
    never materialized rather than deliberately blank. Callers must treat "" as "send no
    system message at all" (an empty system message is not the same thing, and some
    providers reject it).
    """
    prompt_path = Path(ctx) / "prompt.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return _DEFAULT_SYSTEM_PROMPT


_pandas_configured = False


def _pandas():
    """Import pandas with the PyArrow-backed string dtype turned OFF, once per process.

    pandas 3.x makes `str` columns `ArrowStringArray` by default, so `read_excel` constructs
    them through pyarrow's C++ layer. Called concurrently from the rollout thread pool that
    is exactly where a run died:

        Current thread (most recent call first):
          File ".../pandas/core/arrays/string_arrow.py", line 241 in _from_sequence
          File ".../pandas/core/construction.py", line 616 in sanitize_array
          ...
          File ".../pandas/io/excel/_base.py", line 1780 in parse
          File ".../adapter.py", line ... in _spreadsheet_preview
          File ".../cap_evolve/trials.py", line 49 in _one      <- ThreadPoolExecutor worker

    SIGSEGV, so nothing catches it: one bad preview takes down the whole algorithm process
    and every completed iteration with it (run 30634898569 lost 68 minutes and ~$6 that way).

    `mode.string_storage = "python"` keeps the `str` dtype but backs it with Python objects,
    so `ArrowStringArray._from_sequence` — the frame that crashed — is never called. Verified
    locally on pandas 3.0.5 / pyarrow 25.0.0 that the resulting preview text is BYTE-IDENTICAL
    to the default, so the agent's prompt does not change and results stay comparable.

    Set once at import rather than per call via `pd.option_context`: that context manager
    mutates a process-global option and restores it on exit, which in a thread pool lets one
    thread restore the Arrow backend while another is still reading — the same class of race
    `run_trials_pool` documents for `redirect_stdout`.
    """
    global _pandas_configured
    import pandas as pd

    if not _pandas_configured:
        try:
            pd.options.mode.string_storage = "python"
        except Exception:  # noqa: BLE001 — older pandas without the option; nothing to disable
            pass
        _pandas_configured = True
    return pd


def _spreadsheet_preview(path: Path, rows: int) -> str:
    pd = _pandas()

    excel_file = pd.ExcelFile(path)
    chunks = []
    for sheet_name in excel_file.sheet_names:
        df = excel_file.parse(sheet_name)
        n = rows if df.shape[0] > rows else df.shape[0]
        chunks.append(f"Sheet Name: {sheet_name}\n{df.head(n).to_string()}\n" + "-" * 50)
    return "\n".join(chunks)


def _resolve_case_file(dir_path: Path, idx: int, sid: str, kind: str) -> Path:
    """Resolve a test case's real on-disk filename, tolerating upstream data quirks
    in the 912-task set (a few ids use .xlsm; a few have a stray space before the
    extension). Falls back to the canonical name if nothing matches, so a
    genuinely-missing file still surfaces as a normal missing-file miss."""
    canonical = dir_path / f"{idx}_{sid}_{kind}.xlsx"
    if canonical.exists():
        return canonical
    matches = sorted(dir_path.glob(f"{idx}_{sid}_{kind}*.xls*"))
    return matches[0] if matches else canonical


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class Adapter(CapabilityAdapter):

    # ---- tasks -------------------------------------------------------------

    def tasks(self, split: str) -> list[Task]:
        """Return ALL SpreadsheetBench instances (stable, no network after first fetch)."""
        return [
            Task(
                id=str(e["id"]),
                input={
                    "instruction": e["instruction"],
                    "spreadsheet_path": e["spreadsheet_path"],
                    "instruction_type": e["instruction_type"],
                    "answer_position": e["answer_position"],
                },
                metadata={"benchmark": "spreadsheetbench", "instruction_type": e["instruction_type"]},
            )
            for e in _load_dataset()
        ]

    # ---- running -------------------------------------------------------------

    def run_trials(self, tasks: list[Task], ctx, *, n_trials: int, base_seed: int) -> dict:
        """Run the task×trial grid concurrently (bounded by SPREADSHEETBENCH_CONCURRENCY).

        Each (task, trial) gets its own Docker sandbox container (minted by conv_id),
        so — unlike a shared-RNG batch runner — plain external-thread-pool concurrency
        is safe here; there is no unsynchronized global state to race on.
        """
        from cap_evolve import run_trials_pool

        return run_trials_pool(
            lambda task, seed: self.run_target(task, ctx, seed=seed),
            tasks, n_trials=n_trials, base_seed=base_seed, max_workers=CONCURRENCY,
        )

    @contextmanager
    def live(self, candidate_dir):
        """Report a broken job description ONCE per evaluation, loudly — but do not raise.

        Raising here would propagate through harness.evaluate_candidate, which run_step does
        NOT wrap in try/except, and abort the whole run. So this only logs; run_target turns
        the same message into a per-rollout error, which costs the candidate its score and
        nothing else.
        """
        err = _task_template_error(candidate_dir)
        if err:
            print(f"spreadsheetbench: candidate rejected — {err}", file=sys.stderr)
        yield candidate_dir

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        """Multi-round CodeAct loop for one task, then replay onto test cases 2 and 3."""
        # Bound before the try so the finally can release the container on EVERY exit path —
        # the early returns (no output, denied mount, LLM failure) as much as the happy one.
        sandbox: _Sandbox | None = None
        conv_id = ""
        try:
            # Before ANY work: a candidate whose job description lost a required placeholder
            # cannot be scored, and must fail cheaply rather than either aborting the run or
            # burning 30 turns per task on a prompt with no output path in it.
            tmpl_error = _task_template_error(ctx)
            if tmpl_error:
                return Rollout(task_id=task.id, error=tmpl_error)

            entry = _entries_by_id().get(task.id)
            if entry is None:
                return Rollout(task_id=task.id, error=f"task id {task.id} not found in dataset")

            vendor = _Vendor.get()
            data_dir = _data_dir()
            sid = str(entry["id"])
            run_tag = f"{sid}_{seed}_{uuid.uuid4().hex[:8]}"
            conv_id = _sanitize_conv_id(f"capevolve-{run_tag}")

            local_dir = data_dir / "spreadsheet" / sid
            container_dir = f"{_CONTAINER_DATA_ROOT}/spreadsheet/{sid}"
            container_out_dir = f"{_CONTAINER_DATA_ROOT}/outputs/{run_tag}"
            outputs_root = data_dir / "outputs"
            host_out_dir = outputs_root / run_tag
            # Both levels must be writable by the container's uid, not just the leaf:
            # the generated code typically re-mkdir's the leaf, which needs write on the
            # parent too.
            outputs_root.mkdir(parents=True, exist_ok=True)
            _make_container_writable(outputs_root, sticky=True)
            host_out_dir.mkdir(parents=True, exist_ok=True)
            _make_container_writable(host_out_dir)

            input_file = _resolve_case_file(local_dir, 1, sid, "input")
            preview = _spreadsheet_preview(input_file, PREVIEW_ROWS)
            user_msg = _read_task_template(ctx).format(
                instruction=entry["instruction"],
                spreadsheet_path=f"{container_dir}/{input_file.name}",
                spreadsheet_content=preview,
                instruction_type=entry["instruction_type"],
                answer_position=entry["answer_position"],
                output_path=f"{container_out_dir}/1_{sid}_output.xlsx",
                max_turns=MAX_TURNS,
            )

            try:
                sandbox = _get_sandbox()
                client = sandbox.client_for(conv_id)
            except Exception as e:  # noqa: BLE001
                return Rollout(
                    task_id=task.id, error=f"sandbox startup failed: {e}",
                    metadata={"run_tag": run_tag},
                )

            system_prompt = _read_system_prompt(ctx)
            # A blank capability means NO system message — that is the no-skill control, and
            # it must not degrade into an empty-string system turn (providers differ on
            # whether they accept one, and a run that half-sends it measures neither thing).
            messages = [{"role": "system", "content": system_prompt}] if system_prompt.strip() else []
            messages.append({"role": "user", "content": user_msg})

            cost = 0.0
            tokens = 0
            last_code = ""      # last code executed at all (diagnostics)
            solution_code = ""  # last code that actually WROTE case 1's output — what 2/3 replay
            artifact = None     # stamp of case 1's output, to detect which code wrote it
            verify_left = VERIFY_TURNS
            no_code_replies = 0
            exec_results: list[str] = []
            case1_path = host_out_dir / f"1_{sid}_output.xlsx"

            import litellm

            for _round in range(MAX_TURNS):
                try:
                    response = litellm.completion(
                        model=model_config.MODEL,
                        messages=messages,
                        seed=seed,
                        **model_config.llm_kwargs(),
                    )
                except Exception as e:  # noqa: BLE001
                    return Rollout(
                        task_id=task.id, error=f"LLM call failed: {e}", cost_usd=cost,
                        tokens=tokens, metadata={"run_tag": run_tag},
                    )

                cost += float(getattr(response, "_hidden_params", {}).get("response_cost", 0) or 0)
                usage = getattr(response, "usage", None)
                tokens += usage.total_tokens if usage else 0

                assistant_text = response.choices[0].message.content or ""
                messages.append({"role": "assistant", "content": assistant_text})

                code = _extract_python(vendor, assistant_text)
                if code is None or not code.strip():
                    # Nothing runnable in the reply. Once an answer exists this is the agent
                    # saying it is FINISHED — honour that instead of nagging it into burning a
                    # round. Before that, re-state the contract rather than feeding prose to
                    # the kernel for a guaranteed SyntaxError.
                    if solution_code:
                        break
                    no_code_replies += 1
                    if no_code_replies >= 3:
                        break  # it is not going to produce code; stop paying for rounds
                    messages.append({"role": "user", "content": _NO_CODE_REMINDER})
                    continue
                last_code = code

                try:
                    exec_result = vendor["exec_code"](client, last_code)
                except Exception as e:  # noqa: BLE001
                    # A raised exception here means the sandbox/network call itself failed,
                    # not that the model's code raised (kernel errors come back as TEXT via
                    # exec_code's own traceback handling) — infrastructure, not fixable by
                    # the prompt.
                    return Rollout(
                        task_id=task.id, error=f"sandbox exec failed: {e}", cost_usd=cost,
                        tokens=tokens, metadata={"run_tag": run_tag},
                    )

                exec_results.append(exec_result)
                messages.append({"role": "user", "content": exec_result})

                stamp = _artifact_stamp(case1_path)
                if stamp is not None and stamp != artifact:
                    # This round produced or changed the graded file, so THIS is the solution
                    # to replay onto cases 2 and 3 — and a later correction supersedes it.
                    artifact, solution_code = stamp, code
                elif solution_code:
                    # A round that did not touch the answer is inspection/verification. Give a
                    # bounded number of them, then stop: the benchmark grades the file, not the
                    # commentary, and every extra round is another LLM call.
                    verify_left -= 1
                    if verify_left <= 0:
                        break

            if not case1_path.exists():
                blocked = _sandbox_access_denied(exec_results, container_out_dir)
                if blocked:
                    # Name the fault precisely: a denial on the OUTPUT dir is the uid
                    # mismatch on a dir we created, while a denial anywhere else under the
                    # mount means the container cannot traverse the dataset root at all —
                    # a different fix, and _preflight_mount should have caught it.
                    if container_out_dir in blocked:
                        why = (
                            f"sandbox denied writes to the bind-mounted output dir "
                            f"{container_out_dir} ({blocked}) — the host dir is not "
                            f"writable by the container's uid; see _make_container_writable"
                        )
                    else:
                        why = (
                            f"sandbox denied access through the bind mount "
                            f"{_CONTAINER_DATA_ROOT} ({blocked}) — the container's uid cannot "
                            f"traverse/read SPREADSHEETBENCH_DATA_DIR, so no path under the "
                            f"mount is reachable; run `chmod -R a+rX` on it (see "
                            f"_preflight_mount)"
                        )
                    return Rollout(
                        task_id=task.id,
                        output=last_code,
                        trace=messages,
                        cost_usd=cost,
                        tokens=tokens,
                        error=why,
                        metadata={"run_tag": run_tag, "id": sid, "model": model_config.MODEL, "seed": seed},
                    )
            else:
                # Case 1 solved — replay the SAME code onto cases 2 and 3 (no new LLM calls).
                for idx in (2, 3):
                    case_input = _resolve_case_file(local_dir, idx, sid, "input")
                    solution = solution_code.replace(input_file.name, case_input.name)
                    solution = solution.replace(f"1_{sid}_output.xlsx", f"{idx}_{sid}_output.xlsx")
                    try:
                        vendor["exec_code"](client, solution)
                    except Exception:  # noqa: BLE001
                        pass  # that test case's output simply won't exist; scored as a miss

            return Rollout(
                task_id=task.id,
                output=solution_code or last_code,
                trace=messages,
                cost_usd=cost,
                tokens=tokens,
                metadata={"run_tag": run_tag, "id": sid, "model": model_config.MODEL, "seed": seed},
            )
        except Exception as e:  # noqa: BLE001
            return Rollout(task_id=task.id, error=f"run_target failed: {e}")
        finally:
            # This rollout's conv_id is never reused, so its container is dead weight the
            # moment we leave: release it here rather than leaving it to the server's
            # 10-minute idle timeout (which is what let 176 of them accumulate and be
            # orphaned). Scoring reads the output from the HOST dir, so nothing downstream
            # needs the container alive.
            if sandbox is not None and conv_id:
                sandbox.release(conv_id)

    # ---- scoring -------------------------------------------------------------

    def score(self, task: Task, rollout: Rollout) -> Score:
        if rollout.error:
            # Errored rollouts leave their output dir behind too — clean it up on this
            # path as well, or a long run accumulates one stale dir per failed rollout
            # inside SPREADSHEETBENCH_DATA_DIR.
            _cleanup_output_dir(rollout)
            return Score(
                task_id=task.id,
                reward=0.0,
                feedback=(
                    f"Rollout failed: {rollout.error}. Infrastructure error, not a "
                    "prompt defect; do not optimize against it."
                ),
            )

        entry = _entries_by_id().get(task.id)
        if entry is None:
            _cleanup_output_dir(rollout)
            return Score(task_id=task.id, reward=0.0, feedback="Unknown task id.")

        meta = rollout.metadata or {}
        run_tag = meta.get("run_tag")
        sid = meta.get("id", task.id)
        if not run_tag:
            return Score(task_id=task.id, reward=0.0, feedback="Rollout has no run_tag; cannot locate outputs.")

        vendor = _Vendor.get()
        data_dir = _data_dir()
        libre = _libreoffice_bin()

        test_results: list[int] = []
        missing: list[int] = []
        mismatched: list[int] = []
        recalc_failed: list[int] = []   # cases whose formula recalc could not run
        for idx in (1, 2, 3):
            gt_path = _resolve_case_file(data_dir / "spreadsheet" / sid, idx, sid, "answer")
            proc_path = data_dir / "outputs" / run_tag / f"{idx}_{sid}_output.xlsx"
            if not proc_path.exists():
                missing.append(idx)
                test_results.append(0)
                continue

            if libre:
                # Recalculate cached formula values before comparing. NOT serialized: each
                # _recalc_workbook call gets its own LibreOffice profile dir, so concurrent
                # invocations no longer conflict. Only the rollout-owned proc file is mutated —
                # the shared gt/answer file never is.
                #
                # Take ownership first: the file was created by the uid-1000 container and is
                # not writable by us, which makes the move-back fail with EACCES (see
                # _reclaim_container_file). Still best-effort — the comparison below runs on
                # whatever is cached either way — but a failure is RECORDED rather than
                # swallowed, because silently comparing un-recalculated formula cells
                # understates every score and looks like a prompt defect.
                if not _reclaim_container_file(proc_path):
                    recalc_failed.append(idx)
                elif not _recalc_workbook(proc_path, libre):
                    recalc_failed.append(idx)

            try:
                ok, _ = vendor["compare_workbooks"](
                    str(gt_path), str(proc_path), entry["instruction_type"], entry["answer_position"]
                )
            except Exception:
                ok = False

            test_results.append(1 if ok else 0)
            if not ok:
                mismatched.append(idx)

        soft = sum(test_results) / len(test_results)
        hard = 1.0 if all(test_results) else 0.0
        feedback = _build_feedback(entry, test_results, missing, mismatched, bool(libre),
                                   recalc_failed)

        # Scoring has consumed every output; drop the per-rollout dir.
        _cleanup_output_dir(rollout)

        return Score(
            task_id=task.id,
            reward=hard if SCORING == "hard" else soft,
            feedback=feedback,
            raw={"test_case_results": test_results},
            # Both are always recorded, whichever is the target — so the other metric can be
            # recovered from any past run's rollouts without re-running it.
            metrics=[
                {"name": "soft_restriction", "value": soft,
                 "primary": SCORING == "soft", "direction": "higher"},
                {"name": "hard_restriction", "value": hard,
                 "primary": SCORING == "hard", "direction": "higher"},
            ],
        )


def _build_feedback(
    entry: dict, test_results: list[int], missing: list[int], mismatched: list[int],
    had_libreoffice: bool, recalc_failed: list[int] | None = None,
) -> str:
    """Gold-SAFE feedback: which test cases passed/failed and why, never gold cell values."""
    n_pass = sum(test_results)
    lines = [
        f"{n_pass}/{len(test_results)} test cases passed "
        f"({entry['instruction_type']}, checked range: {entry['answer_position']})."
    ]
    if missing:
        lines.append(f"Test case(s) {missing} produced NO output file — the code never wrote output_path.")
    if mismatched:
        lines.append(
            f"Test case(s) {mismatched} produced an output file but its values in "
            f"{entry['answer_position']} did not match the expected result."
        )
    if not had_libreoffice and (missing or mismatched):
        lines.append(
            "Note: LibreOffice was unavailable, so formula-only cells (never assigned a "
            "literal value) could not be recalculated before comparison."
        )
    if recalc_failed:
        # An INFRASTRUCTURE fault, not a prompt defect: the comparison ran on stale cached
        # values, so this score is a floor. Say so, or the optimizer spends budget rewriting
        # a prompt against a broken mount (exactly what happened in run 30520700500).
        lines.append(
            f"INFRASTRUCTURE: formula recalculation FAILED for test case(s) {recalc_failed}, "
            "so comparison used stale cached values and this score may understate the real "
            "result. Not a prompt defect — do not optimize against it."
        )
    if n_pass == len(test_results):
        lines.append("All checks passed.")
    return " ".join(lines)


if __name__ == "__main__":
    # Offline self-check: pure helpers only (no Docker/LLM/network).
    assert _sanitize_conv_id("275-49") == "275-49"
    assert _sanitize_conv_id("CF_6540") == "CF_6540"
    assert _sanitize_conv_id("59196") == "59196"
    assert _sanitize_conv_id("-leading-dash") == "t-leading-dash"
    print("spreadsheetbench conv-id self-check: OK")

    fake_entry = {"instruction_type": "Cell-Level Manipulation", "answer_position": "H3:H5"}
    fb = _build_feedback(fake_entry, [1, 0, 0], [3], [2], True)
    assert "1/3" in fb and "[3]" in fb and "[2]" in fb and "H3:H5" in fb
    assert "59196" not in fb  # no leakage of anything beyond ids we passed in ourselves
    fb_full = _build_feedback(fake_entry, [1, 1, 1], [], [], True)
    assert "All checks passed" in fb_full
    print("spreadsheetbench feedback self-check: OK")

    import tempfile as _tempfile

    with _tempfile.TemporaryDirectory() as _td:
        _d = Path(_td)
        (_d / "1_1000_input.xlsx").write_bytes(b"")
        assert _resolve_case_file(_d, 1, "1000", "input") == _d / "1_1000_input.xlsx"

        (_d / "2_1000_input .xlsx").write_bytes(b"")  # upstream's stray-space typo
        assert _resolve_case_file(_d, 2, "1000", "input") == _d / "2_1000_input .xlsx"

        (_d / "3_1000_input.xlsm").write_bytes(b"")  # upstream's .xlsm variant
        assert _resolve_case_file(_d, 3, "1000", "input") == _d / "3_1000_input.xlsm"

        assert _resolve_case_file(_d, 4, "1000", "input") == _d / "4_1000_input.xlsx"  # missing → canonical fallback
    print("spreadsheetbench case-file resolver self-check: OK")

    # Code extraction: a fenced block runs; prose / tool-call XML must NOT be executed.
    _vendor_stub = {"extract_code": lambda r: r[r.find("```python") + 9:].split("```")[0].strip("\n")}
    assert _extract_python(_vendor_stub, "sure!\n```python\nwb.save(p)\n```\ndone") == "wb.save(p)"
    assert _extract_python(_vendor_stub, "```\nwb.save(p)\n```") == "wb.save(p)"
    assert _extract_python(_vendor_stub, "```py\nwb.save(p)\n```") == "wb.save(p)"
    assert _extract_python(_vendor_stub, "I'll start by examining the spreadsheet.") is None
    assert _extract_python(_vendor_stub, "<function_calls>\n<invoke>x</invoke>") is None
    assert _extract_python(_vendor_stub, "") is None
    print("spreadsheetbench code-extraction self-check: OK")

    # Denied output-dir writes are infra, and must be told apart from other errors.
    _out = "/mnt/data/outputs/160-6_0_dead"
    _perm = (
        "PermissionError                        Traceback (most recent call last)\n"
        "Cell In[1], line 76\n"
        "---> 76 wb.save(output_path)\n"
        f"PermissionError: [Errno 13] Permission denied: '{_out}/1_160-6_output.xlsx'"
    )
    assert _sandbox_access_denied([_perm], _out) is not None
    assert _sandbox_access_denied(["ok", _perm], _out) is not None
    assert _sandbox_access_denied([_perm], "/mnt/data/outputs/other_tag") is None  # different rollout's dir
    assert _sandbox_access_denied(["NameError: name 'wb' is not defined"], _out) is None
    assert _sandbox_access_denied([], _out) is None

    # A non-traversable mount ROOT denies the INPUT read — the 912-archive fault. It must
    # classify as infra too, or 50 rollouts get reported as plain zero-reward misses.
    _read_denied = (
        "PermissionError                        Traceback (most recent call last)\n"
        "Cell In[1], line 3\n"
        "----> 3 wb = openpyxl.load_workbook(path)\n"
        "PermissionError: [Errno 13] Permission denied: "
        "'/mnt/data/spreadsheet/110-2/1_110-2_input.xlsx'"
    )
    _hit = _sandbox_access_denied([_read_denied], _out)
    assert _hit is not None and "1_110-2_input.xlsx" in _hit
    print("spreadsheetbench sandbox-access-denied self-check: OK")

    # The mount preflight: heal a 0700 dataset root, and refuse to run when we cannot.
    with _tempfile.TemporaryDirectory() as _td:
        _root = Path(_td) / "all_data_912_v0.1"
        (_root / "spreadsheet" / "110-2").mkdir(parents=True)
        (_root / "spreadsheet" / "110-2" / "1_110-2_input.xlsx").write_bytes(b"PK\x03\x04")
        os.chmod(_root, 0o700)                      # exactly what the 912 tarball ships
        _preflight_mount(_root)                     # must widen, not raise
        assert (_root.stat().st_mode & 0o055) == 0o055
        assert (_root / "outputs").is_dir() and (_root / "outputs").stat().st_mode & 0o002
        _preflight_mount(_root)                     # idempotent on a healthy tree

        # tar ANDs stored modes with the extracting umask, so the workbooks can land 0640
        # too — a root-only fix would still deny the read. We own this tree, so heal it.
        _wb = _root / "spreadsheet" / "110-2" / "1_110-2_input.xlsx"
        os.chmod(_wb, 0o600)
        _preflight_mount(_root)
        # BOTH classes — the container's gid matches the tree's group and POSIX stops at
        # the first matching class, so 0o604 (`-rw----r--`) is still EACCES for it.
        assert _wb.stat().st_mode & 0o044 == 0o044, "workbook must be container-readable"
        assert not _wb.stat().st_mode & 0o022, "read-only input stays read-only"
    print("spreadsheetbench mount-preflight self-check: OK")

    with _tempfile.TemporaryDirectory() as _td:
        _p = Path(_td) / "outputs"
        _p.mkdir()
        _make_container_writable(_p, sticky=True)
        assert (_p.stat().st_mode & 0o1777) == 0o1777
        _leaf = _p / "tag"
        _leaf.mkdir()
        _make_container_writable(_leaf)
        assert (_leaf.stat().st_mode & 0o777) == 0o777
        _make_container_writable(Path(_td) / "does-not-exist")  # best-effort, must not raise
    print("spreadsheetbench container-writable self-check: OK")

    with _tempfile.TemporaryDirectory() as _td:
        # A container-created output is readable but not writable by us; scoring's recalc
        # rewrite needs it writable, and chmod cannot deliver that on a foreign-owned file.
        _f = Path(_td) / "1_42_output.xlsx"
        _f.write_bytes(b"workbook")
        os.chmod(_f, 0o444)
        assert not os.access(_f, os.W_OK)
        assert _reclaim_container_file(_f) is True
        assert os.access(_f, os.W_OK)
        assert _f.read_bytes() == b"workbook"      # bytes preserved
        assert not list(Path(_td).glob("*.hostcopy"))
        assert _reclaim_container_file(_f) is True  # idempotent once ours
    print("spreadsheetbench reclaim-container-file self-check: OK")

    class _FakeRollout:
        def __init__(self, metadata):
            self.metadata = metadata

    with _tempfile.TemporaryDirectory() as _td:
        _saved = DATA_DIR
        try:
            DATA_DIR = _td  # module global — this is what _data_dir() reads
            (Path(_td) / "dataset.json").write_text("[]", encoding="utf-8")
            _tag_dir = Path(_td) / "outputs" / "160-6_0_dead"
            _tag_dir.mkdir(parents=True)
            (_tag_dir / "1_160-6_output.xlsx").write_bytes(b"")
            _cleanup_output_dir(_FakeRollout({"run_tag": "160-6_0_dead"}))
            assert not _tag_dir.exists(), "output dir should be removed after scoring"
            _cleanup_output_dir(_FakeRollout({}))            # no run_tag → no-op
            _cleanup_output_dir(_FakeRollout(None))          # no metadata at all → no-op
            _cleanup_output_dir(_FakeRollout({"run_tag": "never-created"}))  # already gone
        finally:
            DATA_DIR = _saved
    print("spreadsheetbench output-cleanup self-check: OK")
