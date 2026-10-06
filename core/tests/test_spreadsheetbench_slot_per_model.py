"""The kept-run slot is keyed by tier and agent model, so one model's run never overwrites another's seed.

With a single slot, a GPT-5.5 no-skill baseline would have replaced the Gemma-4-31B-It seed that
the #606 experiment reuses. The slot path now includes `<tier>__<model>`.
"""

import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUN_SUITE = REPO / "ci" / "benchmarks" / "lib" / "run_suite.sh"


def _slot(tier: str, model: str, home: str = "/h") -> str:
    src = RUN_SUITE.read_text(encoding="utf-8")
    lines = [l.strip() for l in src.splitlines()
             if re.match(r"\s*SB_(SLOT_KEY|LATEST_DIR)=", l)]
    script = f'TIER={tier!r}; AGENT_MODEL={model!r}; HOME={home!r}\n' + "\n".join(lines) + '\necho "$SB_LATEST_DIR"'
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True).stdout.strip()


def test_the_slot_is_keyed_by_tier_and_model():
    gemma = _slot("full_verified", "ibm-rits/google/gemma-4-31B-it")
    assert gemma == "/h/.cache/capevolve-latest/spreadsheetbench-slots/full_verified__ibm-rits_google_gemma-4-31B-it"
    assert _slot("full_verified", "ibm-ete-int/azure/gpt-5.5") != gemma
    assert _slot("smoke", "ibm-rits/google/gemma-4-31B-it") != gemma


def test_an_explicit_slot_dir_still_wins():
    src = RUN_SUITE.read_text(encoding="utf-8")
    assert 'SB_LATEST_DIR="${SB_LATEST_DIR:-' in src
