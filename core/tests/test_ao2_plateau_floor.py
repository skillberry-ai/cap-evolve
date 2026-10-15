"""There is no derived plateau stop: a search that has not changed champion runs to its budget
(campaign v2.0: every unaccepted AO-2 search stopped at 41% of the rollout budget)."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"))

import policy  # noqa: E402


def _stop(frac, n_proposals=13, since=None, **caps):
    mc = 600
    c = policy.Caps(max_metric_calls=mc, **caps)
    return policy.stop_reason(caps=c, committed=int(frac * mc), reserved=0, tokens=0, tokens_reserved=0, now=0.0,
                              best_reward=None, n_proposals=n_proposals,
                              since_improve=n_proposals if since is None else since, alive_p=[])


def test_no_plateau_stop_without_an_explicit_count():
    for frac in (0.41, 0.6, 0.85, 0.9):
        for n in (6, 13, 40):
            assert _stop(frac, n_proposals=n) is None


def test_an_explicit_count_and_floor_are_honoured():
    assert _stop(0.5, plateau_n=3, plateau_floor=0.6) is None
    assert (_stop(0.7, plateau_n=3, plateau_floor=0.6) or "").startswith("plateau")
    assert _stop(0.7, n_proposals=13, since=2, plateau_n=3, plateau_floor=0.6) is None


def test_the_budget_still_stops_the_run():
    assert (_stop(0.99) or "").startswith("budget")
