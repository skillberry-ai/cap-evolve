"""PR 874 review finding 7: the final-window CI uses cap_evolve.stats.bootstrap_ci.

``analyze.py`` had its own percentile bootstrap. With equal-size scenarios, the scenario-clustered
paired bootstrap of ΔTGC/ΔSGC is a bootstrap of the mean of per-scenario differences.
"""

from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import aw_testlib  # noqa: E402, F401

import analyze  # noqa: E402
from cap_evolve import stats  # noqa: E402


def synthetic(n_scen=6, per=3, seed=1):
    rng = random.Random(seed)
    scen = {f"s{i}": [f"s{i}_{j}" for j in range(per)] for i in range(n_scen)}
    cells = {}
    for arm, p in (("seed", 0.4), ("cape-hc", 0.6)):
        for ts in scen.values():
            for t in ts:
                for k in range(analyze.TRIALS):
                    cells[(arm, t, k)] = {"success": rng.random() < p}
    cells.pop(("seed", "s0_0", 1))  # a missing cell counts as 0 in the primary analysis
    return cells, scen


class AnalyzeBootstrapTests(unittest.TestCase):
    def test_scenario_diffs_average_to_the_headline_differences(self):
        cells, scen = synthetic()
        ids = [t for ts in scen.values() for t in ts]
        d_t, d_s = analyze.scenario_diffs(cells, "cape-hc", "seed", scen)
        self.assertAlmostEqual(sum(d_t) / len(d_t), analyze.tgc(cells, "cape-hc", ids) - analyze.tgc(cells, "seed", ids))
        self.assertAlmostEqual(sum(d_s) / len(d_s), analyze.sgc(cells, "cape-hc", scen) - analyze.sgc(cells, "seed", scen))

    def test_ci_is_bootstrap_ci_of_the_scenario_diffs(self):
        cells, scen = synthetic()
        d_t, d_s = analyze.scenario_diffs(cells, "cape-hc", "seed", scen)
        ci_t, ci_s = analyze.paired_cis(cells, "cape-hc", "seed", scen)
        self.assertEqual(ci_t, list(stats.bootstrap_ci(d_t, resamples=analyze.B, seed=0)))
        self.assertEqual(ci_s, list(stats.bootstrap_ci(d_s, resamples=analyze.B, seed=0)))
        self.assertLessEqual(ci_t[0], ci_t[1])

    def test_uses_the_shared_helper(self):
        cells, scen = synthetic()
        with patch.object(analyze, "bootstrap_ci", wraps=stats.bootstrap_ci) as spy:
            analyze.paired_cis(cells, "cape-hc", "seed", scen)
        self.assertEqual(spy.call_count, 2)
        self.assertFalse(hasattr(analyze, "bootstrap"))

    def test_unequal_scenarios_are_refused(self):
        cells, scen = synthetic()
        scen["s0"] = scen["s0"][:2]
        with self.assertRaises(ValueError):
            analyze.paired_cis(cells, "cape-hc", "seed", scen)


if __name__ == "__main__":
    unittest.main()
