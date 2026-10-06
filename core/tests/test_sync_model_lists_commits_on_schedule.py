"""The scheduled model-picker sync must actually commit what it computes.

`if: ${{ inputs.apply != false }}` skipped the Commit step on every scheduled run: a schedule has no
inputs, and GitHub coerces both an absent input and `false` to 0. Every sync reported the second
gateway's 30 models (including ibm-ete/azure/gpt-5.5) as "newly served" and then dropped them.
"""

from pathlib import Path

WF = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "sync-model-lists.yml"


def _commit_condition() -> str:
    lines = WF.read_text(encoding="utf-8").splitlines()
    i = next(n for n, l in enumerate(lines) if l.strip() == "- name: Commit")
    cond = next(l for l in lines[i + 1:i + 8] if l.strip().startswith("if:"))
    return cond.strip()


def test_the_commit_step_runs_on_schedule():
    cond = _commit_condition()
    assert "github.event_name == 'schedule'" in cond
    assert "inputs.apply != false" not in cond


def test_a_dispatch_still_commits_only_when_apply_is_checked():
    assert "inputs.apply" in _commit_condition()
