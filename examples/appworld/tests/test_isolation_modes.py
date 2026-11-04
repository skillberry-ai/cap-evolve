"""PR 874 review finding 8: Claude Code's built-in sandbox is the default, the namespace a fallback.

``sandbox/claude`` dispatches on AW_ISOLATION and fails closed. A launch needs a passing isolation
check for its mode that is newer than the settings it will use.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aw_testlib import EX  # noqa: E402

import isolation_gate  # noqa: E402

SHIM = EX / "sandbox" / "claude"


class ShimDispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.fake = self.tmp / "bin" / "claude"
        self.fake.parent.mkdir()
        self.argv = self.tmp / "argv"
        self.fake.write_text(f'#!/bin/bash\nprintf "%s\\0" "$@" > {self.argv}\necho ran\n')
        self.fake.chmod(0o755)
        self.sandbox_settings = self.tmp / "optimizer-sandbox.json"
        rendered = (EX / "sandbox" / "optimizer-sandbox.template.json").read_text().replace("@AW_EVAL@", "/aw")
        self.sandbox_settings.write_text(rendered.replace("@AW_SECRETS_FILE@", "/repo/.env"))

    def _run(self, **env) -> subprocess.CompletedProcess:
        # the shim's own dir comes first on PATH, as in launch_cape_hc.sh; the fake claude after it
        full = {"PATH": f"{SHIM.parent}:{self.fake.parent}:/usr/bin:/bin", "HOME": str(self.tmp), **env}
        return subprocess.run(["claude", "-p", "hi"], env=full, capture_output=True, text=True, timeout=30)

    def test_default_is_the_builtin_sandbox_with_settings_inline(self):
        r = self._run(AW_CLAUDE_SETTINGS=str(self.sandbox_settings))
        self.assertEqual(r.returncode, 0, r.stderr)
        args = self.argv.read_text().split("\0")[:-1]
        self.assertEqual(args[0], "--settings")
        self.assertTrue(json.loads(args[1])["sandbox"]["failIfUnavailable"])
        self.assertEqual(args[2:], ["-p", "hi"])

    def test_finds_the_real_claude_past_itself(self):
        r = self._run(AW_CLAUDE_SETTINGS=str(self.sandbox_settings))
        self.assertNotIn("no claude CLI", r.stderr)

    def test_no_settings_refuses(self):
        r = self._run()
        self.assertEqual(r.returncode, 97)
        self.assertFalse(self.argv.exists())

    def test_sandbox_mode_requires_fail_if_unavailable(self):
        weak = self.tmp / "weak.json"
        weak.write_text('{"sandbox": {"enabled": true}}')
        r = self._run(AW_CLAUDE_SETTINGS=str(weak))
        self.assertEqual(r.returncode, 97)
        self.assertIn("failIfUnavailable", r.stderr)

    def test_unknown_mode_refuses(self):
        r = self._run(AW_CLAUDE_SETTINGS=str(self.sandbox_settings), AW_ISOLATION="none")
        self.assertEqual(r.returncode, 97)


class SettingsTemplateTests(unittest.TestCase):
    def test_both_modes_deny_the_same_answer_paths(self):
        sb = json.loads((EX / "sandbox" / "optimizer-sandbox.template.json").read_text())
        perm = json.loads((EX / "sandbox" / "optimizer-permissions.template.json").read_text())
        self.assertEqual(sb["permissions"]["deny"], perm["permissions"]["deny"])
        deny_read = " ".join(sb["sandbox"]["filesystem"]["denyRead"])
        for p in ("root_opt", "root_full", "runs/final", "runs/altk", "appworld/generate", "@AW_SECRETS_FILE@"):
            self.assertIn(p, deny_read)
        self.assertFalse(sb["sandbox"]["allowUnsandboxedCommands"])
        self.assertTrue(sb["sandbox"]["failIfUnavailable"])


class LaunchGateTests(unittest.TestCase):
    def setUp(self):
        self.aw = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.aw, ignore_errors=True)
        self.settings = self.aw / "optimizer-sandbox.json"
        self.settings.write_text("{}")

    def _report(self, mode: str, ok: bool, name: str = "20261104T000000") -> None:
        d = self.aw / "runs" / "isolation_check" / f"{mode}-{name}"
        d.mkdir(parents=True)
        time.sleep(0.01)
        (d / "report.json").write_text(json.dumps({"pass": ok}))

    def test_no_report_blocks(self):
        self.assertFalse(isolation_gate.gate(self.aw, "sandbox", self.settings)[0])

    def test_passing_report_for_the_mode_opens(self):
        self._report("sandbox", True)
        self.assertTrue(isolation_gate.gate(self.aw, "sandbox", self.settings)[0])

    def test_report_for_the_other_mode_does_not_count(self):
        self._report("namespace", True)
        self.assertFalse(isolation_gate.gate(self.aw, "sandbox", self.settings)[0])

    def test_latest_failed_report_blocks(self):
        self._report("sandbox", True, "20261101T000000")
        self._report("sandbox", False, "20261102T000000")
        self.assertFalse(isolation_gate.gate(self.aw, "sandbox", self.settings)[0])

    def test_settings_changed_after_the_check_blocks(self):
        self._report("sandbox", True)
        time.sleep(0.01)
        self.settings.write_text('{"changed": true}')
        ok, why = isolation_gate.gate(self.aw, "sandbox", self.settings)
        self.assertFalse(ok)
        self.assertIn("predates", why)

    def test_launch_script_runs_the_gate(self):
        launch = (EX / "scripts" / "launch_cape_hc.sh").read_text()
        self.assertIn("isolation_gate.py", launch)
        self.assertIn('AW_ISOLATION="${AW_ISOLATION:-sandbox}"', launch)


if __name__ == "__main__":
    unittest.main()
