# scripts/v4_t2_e1/tests/test_preflight_check.py
from __future__ import annotations

import subprocess
import sys
import unittest
import unittest.mock
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


class TestStackIsHealthy(unittest.TestCase):
    """A task's budget (max_usd 50, up to 3 iterations x 5 trials) is committed
    the moment `cap-evolve run` starts. If one of the 5 MCP services or
    parsec-live itself is down, every trial in that budget burns against a
    broken stack and scores 0.0 — indistinguishable, in the run record, from a
    genuine capability failure. Cheaper to check five TCP connects first.
    """

    def test_all_five_mcp_ports_plus_parsec_live_are_checked(self):
        self.assertEqual(preflight_check.STACK_PORTS["parsec-live"], 8000)
        self.assertEqual(
            sorted(p for n, p in preflight_check.STACK_PORTS.items() if n != "parsec-live"),
            [8086, 8087, 8088, 8089, 8090],
        )

    def test_healthy_when_every_port_accepts(self):
        with patch.object(preflight_check.socket, "create_connection") as conn:
            healthy, unreachable = preflight_check.stack_is_healthy()
        self.assertTrue(healthy)
        self.assertEqual(unreachable, [])
        self.assertEqual(conn.call_count, len(preflight_check.STACK_PORTS))

    def test_unhealthy_and_names_everything_when_all_down(self):
        with patch.object(preflight_check.socket, "create_connection",
                           side_effect=OSError("connection refused")):
            healthy, unreachable = preflight_check.stack_is_healthy()
        self.assertFalse(healthy)
        self.assertEqual(sorted(unreachable), sorted(preflight_check.STACK_PORTS))

    def test_names_only_the_down_service_on_a_partial_outage(self):
        def fake_conn(addr, timeout=None):
            if addr[1] == 8088:  # ICINGA_MCP
                raise OSError("connection refused")
            return unittest.mock.MagicMock()

        with patch.object(preflight_check.socket, "create_connection", side_effect=fake_conn):
            healthy, unreachable = preflight_check.stack_is_healthy()
        self.assertFalse(healthy)
        self.assertEqual(unreachable, ["ICINGA_MCP"])

    def test_closes_every_socket_it_opens(self):
        """Leaking 5 sockets per invocation into a long external loop is the
        kind of thing that only shows up 200 iterations in."""
        opened = []

        def fake_conn(addr, timeout=None):
            sock = unittest.mock.MagicMock()
            opened.append(sock)
            return sock

        with patch.object(preflight_check.socket, "create_connection", side_effect=fake_conn):
            preflight_check.stack_is_healthy()
        self.assertEqual(len(opened), len(preflight_check.STACK_PORTS))
        for sock in opened:
            sock.close.assert_called_once()


if __name__ == "__main__":
    unittest.main()
