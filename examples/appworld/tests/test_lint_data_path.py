"""PR 874 review finding 1: the lint gate must work in the real launch path.

The optimizer runs ``python lints.py .`` inside a namespace where root_opt is not visible. The lint
must then read its data from the cache written by ``make_roots.py``. When neither the cache nor
root_opt can be read, it must fail closed with a clear message, not a traceback.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aw_testlib import EX, make_root  # noqa: E402

import lints  # noqa: E402

LINTS = EX / "adapters" / "lints.py"


class LintDataPathTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.eval = self.tmp / "aw_eval"
        make_root(self.eval / "root_opt")
        self.env = patch.dict(os.environ, {"AW_EVAL": str(self.eval)})
        self.env.start()
        for k in ("AW_LINT_ROOT", "AW_LINT_CACHE", "APPWORLD_ROOT", "AW_APPWORLD_ROOT"):
            os.environ.pop(k, None)
        lints.lint_data.cache_clear()

    def tearDown(self):
        self.env.stop()
        lints.lint_data.cache_clear()

    def _run_cli(self, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-I", str(LINTS), *args], capture_output=True, text=True,
                              env={**os.environ, **(env or {})})

    def test_defaults_follow_aw_eval(self):
        self.assertEqual(lints._root(), self.eval / "root_opt")
        self.assertEqual(lints.cache_path(), self.eval / "lint_cache.json")

    def test_lint_root_ignores_the_episode_root(self):
        # In the final window AW_APPWORLD_ROOT/APPWORLD_ROOT point at root_full; lint data must not.
        with patch.dict(os.environ, {"APPWORLD_ROOT": "/elsewhere/root_full", "AW_APPWORLD_ROOT": "/elsewhere/root_full"}):
            self.assertEqual(lints._root(), self.eval / "root_opt")

    def test_cached_lint_never_touches_root_opt(self):
        lints.write_cache()
        shutil.rmtree(self.eval / "root_opt")  # what the optimizer's namespace looks like
        lints.lint_data.cache_clear()
        self.assertEqual(lints.lint_candidate(EX / "seed_capability"), [])

    def test_cli_with_cache_and_no_root_prints_ok(self):
        lints.write_cache()
        shutil.rmtree(self.eval / "root_opt")
        r = self._run_cli(str(EX / "seed_capability"))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(json.loads(r.stdout)["ok"])

    def test_cli_without_cache_or_root_fails_closed(self):
        shutil.rmtree(self.eval / "root_opt")
        r = self._run_cli(str(EX / "seed_capability"))
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)
        out = json.loads(r.stdout)
        self.assertFalse(out["ok"])
        self.assertIn("lint data unavailable", out["violations"][0])
        self.assertIn("make_roots.py", out["violations"][0])

    def test_lint_candidate_raises_when_data_unavailable(self):
        shutil.rmtree(self.eval / "root_opt")
        with self.assertRaises(lints.LintDataUnavailable):
            lints.lint_candidate(EX / "seed_capability")

    def test_make_roots_builds_the_cache_from_root_opt(self):
        import make_roots
        cache = make_roots.build_lint_cache(self.eval / "root_opt", self.eval / "lint_cache.json")
        self.assertEqual(oct(cache.stat().st_mode & 0o777), oct(0o644))
        self.assertIn("move all songs from my workout playlist to", json.loads(cache.read_text())["grams"])

    def test_launch_scripts_require_the_cache(self):
        for script in ("scripts/launch_cape_hc.sh", "scripts/setup_project.sh", "scripts/check_optimizer_isolation.sh"):
            self.assertIn("lint_cache.json", (EX / script).read_text(), script)
        instr = (EX / "optimizer" / "INSTRUCTIONS.template.md").read_text()
        self.assertNotIn("root_opt", instr.split("LINT BEFORE YOU STOP")[1].split("\n\n")[0])
        self.assertIn("{AW_LINT_CACHE}", instr)
        self.assertIn("{AW_LINT_CACHE}", (EX / "scripts" / "setup_project.sh").read_text())


if __name__ == "__main__":
    unittest.main()
