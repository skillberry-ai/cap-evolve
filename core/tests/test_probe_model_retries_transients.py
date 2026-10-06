"""The provider preflight probe must survive a transient stall, and only a transient one.

WHAT BROKE

`ci_setup.sh`'s `probe_model` fired a single `curl -sS -m 60`, so one upstream stall killed a
whole dispatch before any work started. It did, twice: runs 36259218074 and 36297602993 both
died at exactly 60s with `HTTP 000000` (curl's `-w '%{http_code}'` printed `000` and the
`|| echo 000` fallback appended another). The endpoint was healthy both times — `/health` and
`/v1/models` answered 200, and a real completion answered `200 in 1s` on one day and `200 in 6s`
on another. That latency spread is the argument: a single-shot probe against an endpoint whose
own good responses vary 6x is a coin flip, not a check.

WHAT MUST STILL BE FAST

A `429 budget_exceeded`, an entitlement refusal (`not allowed to access model`) and any other
`4xx` are DEFINITIVE answers from a live service. Retrying those would burn the backoff to
reach the same conclusion and, worse, would make a decision look like flakiness. They must
abort on the first response — which is what the "one attempt" assertions below pin.

HOW THIS IS TESTED

`probe_model` is a shell function, so it is lifted verbatim out of `ci_setup.sh` (same technique
as `test_run_suite_split_hook.py` / `test_entitlement_check_uses_wire_model_ids.py`) and run
against a local stub HTTP server that serves a scripted sequence of responses and counts the
requests it receives. Deliberately NOT written as `ci/benchmarks/lib/test_*.sh`: nothing in the
workflows runs those, so a regression there would be invisible.
"""

import http.server
import re
import socket
import subprocess
import textwrap
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "ci" / "benchmarks" / "lib"
CI_SETUP = LIB / "ci_setup.sh"
RESOLVE = LIB / "resolve_provider.sh"

# A RITS model: the RITS arm is the one that turns a non-200 into a hard abort, so it is what
# makes a final failure observable. It is also the arm both real-world failures happened on.
MODEL = "ibm-rits/google/gemma-4-31B-it"


# --- the stub provider ----------------------------------------------------------------------


class _Stub:
    """Serves a scripted list of (status, body) responses and counts requests.

    The last entry repeats forever, so `[(503, "...")]` is an endpoint that is always sick.
    """

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        outer = self

        class H(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def do_POST(self):  # noqa: N802
                length = int(self.headers.get("Content-Length") or 0)
                outer.requests.append(self.rfile.read(length).decode("utf-8", "replace"))
                i = min(len(outer.requests) - 1, len(outer.script) - 1)
                status, body = outer.script[i]
                raw = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *a):  # keep pytest output clean
                pass

        self._srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self._srv.server_port}"

    def __enter__(self):
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self._srv.shutdown()
        self._srv.server_close()


def _closed_port() -> int:
    """A port with nothing listening: curl fails to connect, i.e. the `000` case."""
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# --- lifting the real function --------------------------------------------------------------


def _probe_model_src() -> str:
    """Lift `probe_model` verbatim out of ci_setup.sh.

    The slice must end on the function's own closing brace: stopping earlier would leave a
    `case`/`while` unterminated, and running further would pull in the concurrent-dispatch
    block that calls it.
    """
    src = CI_SETUP.read_text(encoding="utf-8")
    start = src.index("  probe_model() {")
    end = src.index("\n  }\n", start) + len("\n  }\n")
    block = src[start:end]
    assert block.count("probe_model() {") == 1
    assert "chat/completions" in block, "the completion probe is not inside the lifted slice"
    return block


def _run(base: str, *, model: str = MODEL, env_extra: dict | None = None):
    script = textwrap.dedent(f"""
        set -uo pipefail
        . {RESOLVE}
        IBM_RITS_API_BASE="{base}"
        IBM_RITS_API_KEY="dummy-key"
        IBM_ETE_INT_API_BASE="{base}"; IBM_ETE_INT_API_KEY="dummy-key"
        IBM_ETE_API_BASE="{base}";     IBM_ETE_API_KEY="dummy-key"
    """) + _probe_model_src() + f'\nprobe_model agent "{model}"\n'
    started = time.monotonic()
    proc = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True,
        env={"PATH": "/usr/bin:/bin", **(env_extra or {})},
    )
    return proc, time.monotonic() - started


# Small, but not zero: the backoff still has to be exercised, just not at production length.
FAST = {"CAPEVOLVE_PROBE_BACKOFFS": "1 1", "CAPEVOLVE_PROBE_TIMEOUT": "10"}


def _attempt_lines(out: str) -> list[str]:
    """Only the per-attempt lines — not the final summary, which also names its attempt."""
    return [l for l in out.splitlines() if re.search(r"probe attempt \d+/\d+ ->", l)]


# --- 1. a transient stall must not kill the dispatch ----------------------------------------


def test_a_transient_failure_is_retried_and_the_probe_succeeds():
    """Two sick responses then a healthy one: today's single shot aborts the whole dispatch."""
    with _Stub([(503, '{"error":"upstream stalled"}'),
                (503, '{"error":"upstream stalled"}'),
                (200, '{"choices":[{"message":{"content":"pong"}}]}')]) as stub:
        proc, _ = _run(stub.base, env_extra=FAST)
    assert proc.returncode == 0, f"a recoverable stall still aborted preflight:\n{proc.stdout}\n{proc.stderr}"
    assert len(stub.requests) == 3, f"expected 3 attempts, got {len(stub.requests)}"
    assert "completion probe HTTP 200" in proc.stdout, proc.stdout


def test_every_attempt_is_logged_even_when_a_later_one_succeeds():
    """A transient that heals must stay visible in the log, not be hidden by the retry."""
    with _Stub([(503, "stalled"), (200, "{}")]) as stub:
        proc, _ = _run(stub.base, env_extra=FAST)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = _attempt_lines(proc.stdout)
    assert len(lines) == 2, f"each attempt must be logged; got {lines}\n---\n{proc.stdout}"
    assert any("503" in l for l in lines), lines


def test_a_connect_failure_is_retried_too():
    """`000` (connect failure / timeout) is the exact code both real dispatches died on."""
    proc, _ = _run(f"http://127.0.0.1:{_closed_port()}", env_extra=FAST)
    assert proc.returncode != 0
    assert len(_attempt_lines(proc.stdout)) == 3, proc.stdout


# --- 2. a genuinely dead endpoint still fails, and says how hard it tried -------------------


def test_a_persistent_failure_reports_the_attempt_count_and_last_code():
    with _Stub([(503, '{"error":"still down"}')]) as stub:
        proc, _ = _run(stub.base, env_extra=FAST)
    assert proc.returncode != 0, "an endpoint that never recovers must still abort"
    assert len(stub.requests) == 3, f"expected the full retry budget, got {len(stub.requests)}"
    out = proc.stdout
    assert "lite-rits may be down" in out, f"the existing diagnosis was dropped:\n{out}"
    assert re.search(r"3 attempt", out), f"the failure must name the attempt count:\n{out}"
    assert re.search(r"HTTP 503", out), f"the failure must name the last observed code:\n{out}"


def test_the_reported_code_is_not_doubled():
    """`HTTP 000000` in run 36259218074 was curl's `-w` output plus the `|| echo 000` fallback."""
    proc, _ = _run(f"http://127.0.0.1:{_closed_port()}", env_extra=FAST)
    assert "000000" not in proc.stdout, f"the http_code is still concatenated twice:\n{proc.stdout}"
    assert "HTTP 000" in proc.stdout, proc.stdout


# --- 3. definitive answers must still abort on the FIRST response ---------------------------


def test_over_budget_aborts_after_one_attempt():
    with _Stub([(429, '{"error":{"message":"budget_exceeded for team"}}')]) as stub:
        proc, elapsed = _run(stub.base, env_extra=FAST)
    assert proc.returncode != 0
    assert len(stub.requests) == 1, (
        f"a 429 budget_exceeded is definitive and must NOT be retried; got {len(stub.requests)} calls"
    )
    assert "OVER BUDGET" in proc.stdout, proc.stdout
    assert elapsed < 5, f"the over-budget abort must be immediate, took {elapsed:.1f}s"


def test_an_entitlement_refusal_aborts_after_one_attempt():
    with _Stub([(401, '{"error":"key not allowed to access model rits/google/gemma-4-31B-it"}')]) as stub:
        proc, _ = _run(stub.base, env_extra=FAST)
    assert proc.returncode != 0
    assert len(stub.requests) == 1, (
        f"an entitlement refusal is definitive and must NOT be retried; got {len(stub.requests)} calls"
    )
    assert "REFUSED" in proc.stdout, proc.stdout


def test_a_plain_4xx_is_not_retried():
    """A live service answering 400 has answered. Retrying only delays the same verdict."""
    with _Stub([(400, '{"error":"Invalid model name passed in model=rits/nope"}')]) as stub:
        proc, _ = _run(stub.base, env_extra=FAST)
    assert proc.returncode != 0
    assert len(stub.requests) == 1, (
        f"a 400 is a definitive answer and must NOT be retried; got {len(stub.requests)} calls"
    )
    assert "HTTP 400" in proc.stdout, proc.stdout


# --- 4. the retry must not make the worst case slower --------------------------------------


def test_the_retry_budget_stays_inside_the_old_single_attempt_budget():
    """Run with the REAL defaults (no FAST override): the whole retry sequence must still fit
    inside the 60s a single `curl -m 60` used to be allowed."""
    proc, elapsed = _run(f"http://127.0.0.1:{_closed_port()}")
    assert proc.returncode != 0
    assert len(_attempt_lines(proc.stdout)) >= 3, f"defaults must retry:\n{proc.stdout}"
    assert elapsed < 60, f"worst-case preflight got slower: {elapsed:.1f}s"


def test_a_hung_endpoint_cannot_exceed_the_preflight_budget():
    """Arithmetic guard on the shipped defaults: attempts x per-attempt timeout plus the
    backoffs is what a stalling endpoint (the failure in the issue) actually costs, and the
    loop must refuse an attempt that could not finish inside the budget."""
    src = _probe_model_src()
    m = re.search(r"probe_deadline=(?:\$\{[A-Z_]+:-)?(\d+)", src)
    assert m, "no total probe budget is defined"
    deadline = int(m.group(1))
    assert deadline <= 60, f"the total probe budget grew to {deadline}s"
    assert "probe_deadline" in src and re.search(r"elapsed.*probe_deadline|probe_deadline.*elapsed", src), (
        "nothing enforces the total budget, so three hung attempts would exceed it"
    )


# --- 5. what must not change ---------------------------------------------------------------


def test_both_roles_are_still_probed_concurrently():
    """Worst-case wall time stays ONE role's probes, not both. Each role's probes now run inside
    select_provider, which walks the provider order (RITS, ibm-ete-int, ibm-ete)."""
    src = CI_SETUP.read_text(encoding="utf-8")
    assert re.search(r'select_provider agent "\$PF_AGENT" &\s*pid_agent=\$!', src), src[-2000:]
    assert re.search(r'select_provider optimizer "\$PF_OPTIMIZER" &\s*pid_optimizer=\$!', src)
    assert 'wait "$pid_agent"' in src and 'wait "$pid_optimizer"' in src
    assert re.search(r'probe_model "\$role" "\$c"', src), "select_provider no longer probes each candidate"


def test_a_run_without_the_provider_secrets_still_skips_gracefully():
    """The early return for an unset provider base/key is unrelated to the retry and stays."""
    script = textwrap.dedent(f"""
        set -uo pipefail
        . {RESOLVE}
    """) + _probe_model_src() + '\nprobe_model agent "ibm-rits/google/gemma-4-31B-it"\n'
    proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                          env={"PATH": "/usr/bin:/bin"})
    assert proc.returncode == 0, f"a dispatch without RITS secrets must skip, not abort:\n{proc.stdout}{proc.stderr}"
    assert "skipping" in proc.stdout, proc.stdout


def test_the_shell_library_stays_valid():
    assert subprocess.run(["bash", "-n", str(CI_SETUP)]).returncode == 0
