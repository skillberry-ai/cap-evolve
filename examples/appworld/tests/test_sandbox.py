"""sandbox/claude, sandbox/ns_exec.sh, the settings templates and scripts/isolation_gate.py (README: Isolation).

The namespace-mode tests run the shim for real (unprivileged user and mount namespaces) with a
stand-in for the claude CLI, and skip where namespaces are unavailable."""

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

# The modules under test live in ../adapters (and ../scripts, ../altk). `cap_evolve` normally comes
# from the installed package; core/ is a fallback so that
#     python3 examples/appworld/tests/test_sandbox.py -v
# works from a clean shell, as in examples/parsec/tests. Appended, not prepended: a second copy of
# cap_evolve ahead of the installed one would be worse than an awkward invocation.
EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "scripts"))
sys.path.append(str(Path(__file__).resolve().parents[3] / "core"))

import isolation_gate  # noqa: E402

SHIM = EX / "sandbox" / "claude"


class TestShimDispatch(unittest.TestCase):
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


def _namespaces_work() -> bool:
    if not shutil.which("unshare"):
        return False
    r = subprocess.run(["unshare", "-rm", "--propagation", "private", "bash", "-c",
                        "mount -t tmpfs tmpfs /mnt && unshare -U --map-user=%d true" % os.getuid()],
                       capture_output=True)
    return r.returncode == 0


@unittest.skipUnless(sys.platform.startswith("linux") and _namespaces_work(), "needs unprivileged namespaces")
class TestNamespaceMode(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.aw = self.tmp / "aw_eval"
        (self.aw / "root_opt" / "data").mkdir(parents=True)
        (self.aw / "root_opt" / "data" / "gold.txt").write_text("GOLD")
        (self.aw / "reference").mkdir()
        (self.aw / "reference" / "doc.md").write_text("DOC")
        self.work = self.aw / "runs" / "r1" / "work"
        self.work.mkdir(parents=True)
        # stand-in for the claude CLI: report what it sees from inside the namespace
        self.fake = self.tmp / "fake_claude"
        self.fake.write_text("#!/bin/bash\n"
                             'echo "cwd=$(pwd -P)"\n'
                             'ls "$AW_EVAL_CHECK/root_opt" >/dev/null 2>&1 && echo root_opt=visible || echo root_opt=hidden\n'
                             'cat "$AW_EVAL_CHECK/reference/doc.md" 2>/dev/null; echo\n'
                             'echo hello > ./written.txt && echo write=ok\n')
        self.fake.chmod(0o755)
        self.settings = self.tmp / "optimizer-permissions.json"
        self.settings.write_text('{"permissions": {"deny": []}}')

    def _run(self, cwd: Path, aw_eval: Path) -> subprocess.CompletedProcess:
        env = {"PATH": os.environ["PATH"], "HOME": str(self.tmp / "home"), "AW_EVAL": str(aw_eval),
               "AW_EVAL_CHECK": str(aw_eval), "AW_REAL_CLAUDE": str(self.fake),
               "AW_ISOLATION": "namespace", "AW_CLAUDE_SETTINGS": str(self.settings),
               "AW_NS_HIDE_FILES": "", "AW_NS_LOG": str(self.tmp / "guard.log"),
               "AW_NS_TRANSCRIPTS": str(self.tmp / "transcripts")}
        return subprocess.run(["bash", str(SHIM)], cwd=cwd, env=env, capture_output=True, text=True, timeout=60)

    def test_workdir_is_bound_and_answers_hidden(self):
        r = self._run(self.work, self.aw)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"cwd={self.work}", r.stdout)
        self.assertIn("root_opt=hidden", r.stdout)
        self.assertIn("DOC", r.stdout)
        self.assertIn("write=ok", r.stdout)
        self.assertEqual((self.work / "written.txt").read_text().strip(), "hello")

    def test_cwd_equal_to_aw_eval_is_refused(self):
        r = self._run(self.aw, self.aw)
        self.assertEqual(r.returncode, 97)
        self.assertIn("itself", r.stderr)
        self.assertFalse((self.aw / "written.txt").exists())

    def test_cwd_outside_aw_eval_is_refused(self):
        r = self._run(self.tmp, self.aw)
        self.assertEqual(r.returncode, 97)
        self.assertIn("outside", r.stderr)

    def test_symlinked_aw_eval_works(self):
        link = self.tmp / "aw_link"
        link.symlink_to(self.aw)
        r = self._run(link / "runs" / "r1" / "work", link)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("root_opt=hidden", r.stdout)
        self.assertIn("write=ok", r.stdout)


class TestSettingsTemplates(unittest.TestCase):
    def test_both_modes_deny_the_same_answer_paths(self):
        sb = json.loads((EX / "sandbox" / "optimizer-sandbox.template.json").read_text())
        perm = json.loads((EX / "sandbox" / "optimizer-permissions.template.json").read_text())
        self.assertEqual(sb["permissions"]["deny"], perm["permissions"]["deny"])
        deny_read = " ".join(sb["sandbox"]["filesystem"]["denyRead"])
        for p in ("root_opt", "root_full", "runs/final", "runs/altk", "appworld/generate", "@AW_SECRETS_FILE@"):
            self.assertIn(p, deny_read)
        self.assertFalse(sb["sandbox"]["allowUnsandboxedCommands"])
        self.assertTrue(sb["sandbox"]["failIfUnavailable"])


class TestLaunchGate(unittest.TestCase):
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
