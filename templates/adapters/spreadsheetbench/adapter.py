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
       sudo apt install libreoffice-calc   # Linux
       brew install --cask libreoffice     # macOS
     Scoring degrades gracefully (skips recalculation) if LibreOffice is absent.

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

WHAT THIS OPTIMIZES:
  - The spreadsheet agent's system prompt (prompt.md in the seed capability).
  - The prompt guides HOW the agent reads instructions, respects answer_position, and
    writes results — the task-specific scaffold (instruction/paths/preview/rounds
    protocol) is fixed, not optimizable.

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
"""

from __future__ import annotations

import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
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
LIBREOFFICE_BIN = os.environ.get("SPREADSHEETBENCH_LIBREOFFICE_BIN", "")

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
            "just_open_libreoffice": _open_spreadsheet.just_open_libreoffice,
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

        log_path = self.runtime_dir / "server.log"
        self._log = log_path.open("w", encoding="utf-8")
        self.proc = subprocess.Popen(
            [sys.executable, "api.py", "--port", str(self.port)],
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

    def client_for(self, conv_id: str):
        class _Client:
            def execute(_self, code: str) -> str:
                return self.execute(conv_id, code)

        return _Client()

    def shutdown(self) -> None:
        if self.proc.poll() is not None:
            return
        try:
            self.proc.send_signal(signal.SIGINT)
            self.proc.wait(timeout=60)
        except Exception:
            self.proc.kill()
        finally:
            self._log.close()


_sandbox: _Sandbox | None = None
_sandbox_lock = threading.Lock()
_libre_lock = threading.Lock()


def _get_sandbox() -> _Sandbox:
    global _sandbox
    with _sandbox_lock:
        if _sandbox is None:
            _sandbox = _Sandbox()
            import atexit

            atexit.register(_sandbox.shutdown)
        return _sandbox


def _sanitize_conv_id(s: str) -> str:
    """Docker container names need [A-Za-z0-9_.-], starting with an alnum."""
    out = re.sub(r"[^A-Za-z0-9_.-]", "_", s)
    return out if out and out[0].isalnum() else f"t{out}"


# ---------------------------------------------------------------------------
# Prompting
# ---------------------------------------------------------------------------


def _read_system_prompt(ctx) -> str:
    prompt_path = Path(ctx) / "prompt.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return _DEFAULT_SYSTEM_PROMPT


def _spreadsheet_preview(path: Path, rows: int) -> str:
    import pandas as pd

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

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        """Multi-round CodeAct loop for one task, then replay onto test cases 2 and 3."""
        try:
            entry = _entries_by_id().get(task.id)
            if entry is None:
                return Rollout(task_id=task.id, error=f"task id {task.id} not found in dataset")

            vendor = _Vendor.get()
            data_dir = _data_dir()
            sid = str(entry["id"])
            run_tag = f"{sid}_{seed}_{uuid.uuid4().hex[:8]}"
            conv_id = _sanitize_conv_id(f"capevolve-{run_tag}")

            local_dir = data_dir / "spreadsheet" / sid
            container_dir = f"/mnt/data/spreadsheet/{sid}"
            container_out_dir = f"/mnt/data/outputs/{run_tag}"
            host_out_dir = data_dir / "outputs" / run_tag
            host_out_dir.mkdir(parents=True, exist_ok=True)

            input_file = _resolve_case_file(local_dir, 1, sid, "input")
            preview = _spreadsheet_preview(input_file, PREVIEW_ROWS)
            user_msg = _TASK_TEMPLATE.format(
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
                return Rollout(task_id=task.id, error=f"sandbox startup failed: {e}")

            system_prompt = _read_system_prompt(ctx)
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ]

            cost = 0.0
            tokens = 0
            last_code = ""
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
                    return Rollout(task_id=task.id, error=f"LLM call failed: {e}", cost_usd=cost, tokens=tokens)

                cost += float(getattr(response, "_hidden_params", {}).get("response_cost", 0) or 0)
                usage = getattr(response, "usage", None)
                tokens += usage.total_tokens if usage else 0

                assistant_text = response.choices[0].message.content or ""
                messages.append({"role": "assistant", "content": assistant_text})
                last_code = vendor["extract_code"](assistant_text)

                try:
                    exec_result = vendor["exec_code"](client, last_code)
                except Exception as e:  # noqa: BLE001
                    # A raised exception here means the sandbox/network call itself failed,
                    # not that the model's code raised (kernel errors come back as TEXT via
                    # exec_code's own traceback handling) — infrastructure, not fixable by
                    # the prompt.
                    return Rollout(
                        task_id=task.id, error=f"sandbox exec failed: {e}", cost_usd=cost, tokens=tokens
                    )

                messages.append({"role": "user", "content": exec_result})
                if case1_path.exists():
                    break

            if case1_path.exists():
                for idx in (2, 3):
                    case_input = _resolve_case_file(local_dir, idx, sid, "input")
                    solution = last_code.replace(input_file.name, case_input.name)
                    solution = solution.replace(f"1_{sid}_output.xlsx", f"{idx}_{sid}_output.xlsx")
                    try:
                        vendor["exec_code"](client, solution)
                    except Exception:  # noqa: BLE001
                        pass  # that test case's output simply won't exist; scored as a miss

            return Rollout(
                task_id=task.id,
                output=last_code,
                trace=messages,
                cost_usd=cost,
                tokens=tokens,
                metadata={"run_tag": run_tag, "id": sid, "model": model_config.MODEL, "seed": seed},
            )
        except Exception as e:  # noqa: BLE001
            return Rollout(task_id=task.id, error=f"run_target failed: {e}")

    # ---- scoring -------------------------------------------------------------

    def score(self, task: Task, rollout: Rollout) -> Score:
        if rollout.error:
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
        for idx in (1, 2, 3):
            gt_path = _resolve_case_file(data_dir / "spreadsheet" / sid, idx, sid, "answer")
            proc_path = data_dir / "outputs" / run_tag / f"{idx}_{sid}_output.xlsx"
            if not proc_path.exists():
                missing.append(idx)
                test_results.append(0)
                continue

            if libre:
                # Recalculate cached formula values before comparing. Serialized: concurrent
                # headless LibreOffice invocations against the same profile conflict. Only the
                # rollout-owned proc file is mutated — the shared gt/answer file never is.
                with _libre_lock:
                    try:
                        vendor["just_open_libreoffice"](str(proc_path), libre)
                    except Exception:
                        pass  # best-effort; comparison below still runs on whatever is cached

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
        feedback = _build_feedback(entry, test_results, missing, mismatched, bool(libre))

        # Clean up the per-rollout output dir now that scoring has consumed all outputs.
        # Without this, a full run (912 tasks × iterations) would accumulate thousands of
        # per-task output dirs inside SPREADSHEETBENCH_DATA_DIR.
        out_dir = data_dir / "outputs" / run_tag
        shutil.rmtree(out_dir, ignore_errors=True)

        return Score(
            task_id=task.id,
            reward=soft,
            feedback=feedback,
            raw={"test_case_results": test_results},
            metrics=[
                {"name": "soft_restriction", "value": soft, "primary": True, "direction": "higher"},
                {"name": "hard_restriction", "value": hard, "primary": False, "direction": "higher"},
            ],
        )


def _build_feedback(
    entry: dict, test_results: list[int], missing: list[int], mismatched: list[int], had_libreoffice: bool
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
