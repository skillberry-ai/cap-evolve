"""PR 874 review finding 6: the namespace mode binds exactly the optimizer's working directory.

With cwd == $AW_EVAL the prefix strip did not match and the bind landed under $AW/$AW. With a
symlinked AW_EVAL every working dir failed the guard. The shim is run for real (unprivileged user
and mount namespaces) with a stand-in for the claude CLI. Skipped where namespaces are unavailable.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from aw_testlib import EX  # noqa: E402

SHIM = EX / "sandbox" / "claude"


def _namespaces_work() -> bool:
    if not shutil.which("unshare"):
        return False
    r = subprocess.run(["unshare", "-rm", "--propagation", "private", "bash", "-c",
                        "mount -t tmpfs tmpfs /mnt && unshare -U --map-user=%d true" % os.getuid()],
                       capture_output=True)
    return r.returncode == 0


@unittest.skipUnless(sys.platform.startswith("linux") and _namespaces_work(), "needs unprivileged namespaces")
class SandboxShimTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
