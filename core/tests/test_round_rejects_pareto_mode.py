"""PR #671 review: round.py's own --mode choices must exclude "pareto".

gate_check.GATE_MODES gained "pareto" for issue #665 ws3, and round.py's --mode choices were
`gate_check.GATE_MODES` verbatim, so `round.py --mode pareto` was CLI-acceptable. But round.py's
`_gate()` never forwards --objectives/--metrics-* to gate_check.py, so that always crashed at
runtime (gate_check.py exits 2 on `ParetoObjectiveError`, round.py raises GateCheckFailed) --
after a wasted gate_check.py subprocess call, and in the full round, after an eval round too.
round.py's own choices now exclude "pareto" so this is rejected at argument-parsing time instead.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"


def test_round_mode_pareto_rejected_at_argparse_time():
    env = dict(os.environ, CAPEVOLVE_CORE=str(REPO / "core"))
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "round.py"),
         "--run-dir", "/nonexistent", "--project", "/nonexistent",
         "--candidates", "cand_1", "--n-trials", "1", "--mode", "pareto"],
        capture_output=True, text=True, env=env)

    # argparse's own usage-error exit code, raised before any run-dir/project/gate_check work.
    assert result.returncode == 2
    assert "invalid choice: 'pareto'" in result.stderr
    # Rejected modes still name the ones that ARE accepted, "pareto" absent from the list.
    # argparse's exact quoting of the choices list varies by Python version (3.11 vs 3.12+),
    # so check each name individually rather than one literal substring.
    for mode in ("paired", "significant", "strict", "threshold"):
        assert mode in result.stderr
    assert result.stderr.count("pareto") == 1  # only the rejected value itself, not in the choices list
