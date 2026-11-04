"""PR 874 review finding 5: only the named key leaves the secrets file, and it does not stay.

``load_secrets`` used to set every KEY=VALUE line, and only one key was removed afterwards. The
adapter also passed the whole ``cap-evolve run`` environment to the episode worker, minus that one key.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aw_testlib import EX  # noqa: E402

import aw_agent  # noqa: E402

KEY = aw_agent.KEY_ENV


class LoadSecretsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.secrets = self.tmp / ".env"
        self.secrets.write_text(f"{KEY}=agent-key\nRITS_URL=https://rits.example\n"
                                "ANTHROPIC_API_KEY=optimizer-key\nAWS_SECRET_ACCESS_KEY=cloud\n# c\n")
        self.env = patch.dict(os.environ, {}, clear=False)
        self.env.start()
        for k in (KEY, "RITS_URL", "ANTHROPIC_API_KEY", "AWS_SECRET_ACCESS_KEY"):
            os.environ.pop(k, None)

    def tearDown(self):
        self.env.stop()

    def test_only_the_named_keys_are_loaded(self):
        loaded = aw_agent.load_secrets(str(self.secrets))
        self.assertEqual(loaded, {KEY, "RITS_URL"})
        self.assertEqual(os.environ[KEY], "agent-key")
        self.assertNotIn("ANTHROPIC_API_KEY", os.environ)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", os.environ)

    def test_drop_secrets_leaves_no_key_but_keeps_the_url(self):
        aw_agent.load_secrets(str(self.secrets))
        aw_agent.drop_secrets()
        self.assertNotIn(KEY, os.environ)
        self.assertEqual(os.environ["RITS_URL"], "https://rits.example")

    def test_an_existing_value_is_not_overwritten(self):
        os.environ[KEY] = "from-env"
        self.assertEqual(aw_agent.load_secrets(str(self.secrets)), {"RITS_URL"})
        self.assertEqual(os.environ[KEY], "from-env")

    def test_missing_file_loads_nothing(self):
        self.assertEqual(aw_agent.load_secrets(str(self.tmp / "nope")), set())


class WorkerEnvTests(unittest.TestCase):
    PARENT = {"PATH": "/usr/bin", "HOME": "/h", "LC_ALL": "C", "APPWORLD_CACHE": "/c", "AW_MODEL_NAME": "m",
              KEY: "agent-key", "ANTHROPIC_API_KEY": "optimizer-key", "AWS_SECRET_ACCESS_KEY": "cloud",
              "GITHUB_TOKEN": "gh", "AW_SECRETS_FILE": "/repo/.env", "CAPEVOLVE_SKILLS_DIR": "/s"}

    def test_allowlist_drops_every_credential(self):
        env = aw_agent.worker_env(dict(self.PARENT), "/aw/root_opt")
        for k in (KEY, "ANTHROPIC_API_KEY", "AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN", "CAPEVOLVE_SKILLS_DIR"):
            self.assertNotIn(k, env)
        self.assertEqual(env["APPWORLD_ROOT"], "/aw/root_opt")
        for k in ("PATH", "HOME", "LC_ALL", "APPWORLD_CACHE", "AW_MODEL_NAME"):
            self.assertEqual(env[k], self.PARENT[k])

    def test_adapter_passes_the_allowlisted_env_to_the_worker(self):
        import subprocess

        import adapter as adapter_mod
        from cap_evolve import Task

        seen: dict = {}

        def fake_run(cmd, env, **kw):
            seen.update(env)
            Path(cmd[-1]).write_text(json.dumps({"infra_error": "stub"}))
            return subprocess.CompletedProcess(cmd, 0, "", "")

        work = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)
        with patch.dict(os.environ, self.PARENT), patch.object(adapter_mod.subprocess, "run", side_effect=fake_run), \
             patch.dict(os.environ, {"AW_INFRA_RETRIES": "0"}):
            adapter_mod.Adapter()._episode(Task(id="t", input={}), EX / "seed_capability", 0, work, work)
        self.assertNotIn("ANTHROPIC_API_KEY", seen)
        self.assertNotIn(KEY, seen)
        self.assertEqual(seen["APPWORLD_ROOT"], str(work))


if __name__ == "__main__":
    unittest.main()
