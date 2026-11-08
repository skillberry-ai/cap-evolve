"""adapters/lints.py: the candidate lints, and where their data comes from (README: Lints).

The optimizer lints inside a namespace where root_opt is hidden, so the lint must read the cache
written by scripts/make_roots.py, and fail closed with a clear message when it has no data."""

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

# The modules under test live in ../adapters (and ../scripts). `cap_evolve` normally comes
# from the installed package; core/ is a fallback so that
#     python3 benchmarks/appworld/examples/react_agent/tests/test_lints.py -v
# works from a clean shell, as in benchmarks/parsec/examples/rca_prompts/tests. Appended, not prepended: a second copy of
# cap_evolve ahead of the installed one would be worse than an awkward invocation.
EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "adapters"))
sys.path.insert(0, str(EX / "scripts"))
sys.path.append(str(Path(__file__).resolve().parents[5] / "core"))

import lints  # noqa: E402

LINTS = EX / "adapters" / "lints.py"


TRAIN_INSTRUCTION = "Move all songs from my workout playlist to a new playlist called cardio mix please"


def make_root(tmp: Path) -> Path:
    """A tiny fake APPWORLD_ROOT: one train and one dev task, two apps of API docs."""
    data = tmp / "data"
    (data / "datasets").mkdir(parents=True)
    (data / "datasets" / "train.txt").write_text("aaa1111_1\n")
    (data / "datasets" / "dev.txt").write_text("bbb2222_1\n")
    for tid, instr, email in (("aaa1111_1", TRAIN_INSTRUCTION, "jane.roe@example.com"),
                              ("bbb2222_1", "How many alarms do I have set on my phone today", "joe@example.com")):
        (data / "tasks" / tid).mkdir(parents=True)
        (data / "tasks" / tid / "specs.json").write_text(json.dumps({
            "instruction": instr,
            "supervisor": {"first_name": "Jane", "last_name": "Roe", "email": email, "phone_number": "5550001111"}}))
    (data / "api_docs" / "standard").mkdir(parents=True)
    (data / "api_docs" / "standard" / "spotify.json").write_text(json.dumps({"login": {}, "show_playlist": {}}))
    (data / "api_docs" / "standard" / "phone.json").write_text(json.dumps({"show_alarms": {}}))
    return tmp


class TestLintRules(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        root = make_root(self.tmp)
        self.env = patch.dict(os.environ, {"AW_LINT_ROOT": str(root), "AW_LINT_CACHE": str(self.tmp / "none.json")})
        self.env.start()
        lints.lint_data.cache_clear()

    def tearDown(self):
        self.env.stop()
        lints.lint_data.cache_clear()

    def test_seed_capability_passes(self):
        self.assertEqual(lints.lint_candidate(EX / "seed_capability"), [])

    def test_prompt_must_keep_template_variables_and_final_block(self):
        v = lints.lint_prompt("USER:\nhello {{ unknown_var }}\nASSISTANT:\nok\n")
        self.assertTrue(any("unknown template variables" in x for x in v))
        self.assertTrue(any("My name is" in x for x in v))

    def test_prompt_leaking_a_train_instruction_is_rejected(self):
        seed = (EX / "seed_capability/policy/instructions.txt").read_text()
        v = lints.lint_prompt(seed.replace("D. Task-completion", f"Example: {TRAIN_INSTRUCTION}\n\nD. Task-completion"))
        self.assertTrue(any("8-gram" in x for x in v))

    def test_supervisor_contact_is_rejected(self):
        self.assertTrue(lints._leaks("write to jane.roe@example.com", "x"))

    def test_hardcoded_helper_is_rejected(self):
        src = ("import os\n"
               "def songs(apis, token):\n    return apis.spotify.show_playlist(access_token=token)\n"
               "x = songs(None, 'login')\n")
        v = " | ".join(lints.lint_helpers(src))
        for needle in ("import of ['os']", "apis.spotify", "'login'", "top level"):
            self.assertIn(needle, v)

    def test_generic_helper_passes(self):
        src = ('"""Helpers."""\nimport json\n\n'
               "def call(apis, app_name, api_name, **kw):\n"
               '    """Call any API by name."""\n'
               "    return getattr(getattr(apis, app_name), api_name)(**kw)\n")
        self.assertEqual(lints.lint_helpers(src), [])

    def test_notes_keys_and_length(self):
        v = lints.lint_notes(json.dumps({"spotify.login": "ok", "nope.api": "x", "phone": "y" * 500}))
        self.assertTrue(any("'nope.api'" in x for x in v))
        self.assertTrue(any("chars >" in x for x in v))

    def test_cache_round_trip(self):
        os.environ["AW_LINT_CACHE"] = str(self.tmp / "cache.json")
        lints.write_cache()
        lints.lint_data.cache_clear()
        self.assertIn(("move", "all", "songs", "from", "my", "workout", "playlist", "to"), lints.lint_data()["grams"])


class TestLintDataPath(unittest.TestCase):
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
