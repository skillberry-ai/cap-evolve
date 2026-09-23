# scripts/v4_t2_e1/tests/test_parsec_paths.py
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import parsec_paths  # noqa: E402


class TestResolveV4N(unittest.TestCase):
    def test_or_none_returns_none_when_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(parsec_paths.resolve_v4n_or_none())

    def test_or_none_returns_path_when_set(self):
        with patch.dict(os.environ, {"PARSEC_V4N": "/tmp/fake-v4n"}, clear=True):
            self.assertEqual(parsec_paths.resolve_v4n_or_none(), Path("/tmp/fake-v4n"))

    def test_or_none_treats_blank_string_as_unset(self):
        with patch.dict(os.environ, {"PARSEC_V4N": "   "}, clear=True):
            self.assertIsNone(parsec_paths.resolve_v4n_or_none())

    def test_resolve_raises_clearly_when_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                parsec_paths.resolve_v4n()
            self.assertIn("PARSEC_V4N", str(ctx.exception))

    def test_resolve_returns_path_when_set(self):
        with patch.dict(os.environ, {"PARSEC_V4N": "/tmp/fake-v4n"}, clear=True):
            self.assertEqual(parsec_paths.resolve_v4n(), Path("/tmp/fake-v4n"))


class TestMcpPorts(unittest.TestCase):
    def test_has_the_five_expected_entries(self):
        self.assertEqual(
            parsec_paths.MCP_PORTS,
            {
                "PLATFORM_MCP_URL": 8086,
                "GITHUB_MCP_URL": 8087,
                "ICINGA_MCP_URL": 8088,
                "COST_MCP_URL": 8089,
                "CLOUD_MCP_URL": 8090,
            },
        )


if __name__ == "__main__":
    unittest.main()
