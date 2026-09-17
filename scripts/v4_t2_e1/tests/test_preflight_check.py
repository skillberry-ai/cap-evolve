# scripts/v4_t2_e1/tests/test_preflight_check.py
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import preflight_check  # noqa: E402


class TestPreflightCheck(unittest.TestCase):
    def test_supports_flag_when_help_mentions_it(self):
        completed = subprocess.CompletedProcess(
            args=["cap-evolve", "run", "--help"], returncode=0,
            stdout="usage: cap-evolve run [-h] ... --stop-at-reward STOP_AT_REWARD ...",
            stderr="",
        )
        with patch("subprocess.run", return_value=completed):
            self.assertTrue(preflight_check.installed_cli_supports_stop_at_reward())

    def test_does_not_support_flag_when_help_omits_it(self):
        completed = subprocess.CompletedProcess(
            args=["cap-evolve", "run", "--help"], returncode=0,
            stdout="usage: cap-evolve run [-h] --project PROJECT --spec SPEC",
            stderr="",
        )
        with patch("subprocess.run", return_value=completed):
            self.assertFalse(preflight_check.installed_cli_supports_stop_at_reward())

    def test_remedy_cmd_points_at_this_worktrees_core(self):
        self.assertIn("uv tool install", preflight_check.REMEDY_CMD)
        self.assertIn("--force", preflight_check.REMEDY_CMD)
        self.assertTrue(preflight_check.REMEDY_CMD.rstrip().endswith("core"))

    def test_main_returns_0_when_supported(self):
        with patch.object(preflight_check, "installed_cli_supports_stop_at_reward",
                           return_value=True):
            self.assertEqual(preflight_check.main(), 0)

    def test_main_returns_1_when_not_supported(self):
        with patch.object(preflight_check, "installed_cli_supports_stop_at_reward",
                           return_value=False):
            self.assertEqual(preflight_check.main(), 1)


if __name__ == "__main__":
    unittest.main()
