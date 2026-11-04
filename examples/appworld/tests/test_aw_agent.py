"""adapters/aw_agent.py: the episode worker (README: Harness).

Prompt injection, the gold-free record and error reports, the hardened import guard, secrets
handling and the constructor arguments passed to AppWorld's agent. AppWorld is not installed for
these tests: its guard module and the two agent signatures at 42b5bcf are stood in for."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

# The modules under test live in ../adapters (and ../scripts). `cap_evolve` normally comes
# from the installed package; core/ is a fallback so that
#     python3 examples/appworld/tests/test_aw_agent.py -v
# works from a clean shell, as in examples/parsec/tests. Appended, not prepended: a second copy of
# cap_evolve ahead of the installed one would be worse than an awkward invocation.
EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "adapters"))
sys.path.append(str(Path(__file__).resolve().parents[3] / "core"))

import aw_agent  # noqa: E402

KEY = aw_agent.KEY_ENV
GOLD = "expected 'GOLD-ANSWER-42'"


class TestInjection(unittest.TestCase):
    def test_block_goes_before_the_final_task_block(self):
        prompt = "USER:\ndemo My name is: A\nASSISTANT:\nx\nUSER:\nnow\n\nMy name is: B C.\nTask: do it"
        out = aw_agent.insert_before_final_block(prompt, "GUIDE")
        self.assertLess(out.index("GUIDE"), out.rindex("My name is: B"))
        self.assertGreater(out.index("GUIDE"), out.index("demo My name is"))

    def test_docstring_only_helpers_run_no_setup(self):
        self.assertFalse(aw_agent.has_code('"""nothing here"""\n'))
        self.assertEqual(aw_agent.setup_snippet('"""nothing here"""\n', {}), "")
        self.assertEqual(aw_agent.helper_notice('"""nothing here"""\n'), "")

    def test_notes_wrap_the_doc_lookups(self):
        snippet = aw_agent.setup_snippet("def f(apis, x):\n    return x\n", {"spotify.login": "N"})
        self.assertIn("def f(apis, x)", snippet)
        self.assertIn("apis.api_docs.show_api_doc = _cap_show_api_doc", snippet)
        self.assertIn("f(apis, x)", aw_agent.helper_notice("def f(apis, x):\n    return x\n"))

    def test_evaluation_record_is_gold_free(self):
        ev = {"success": False, "num_tests": 3,
              "passes": [{"requirement": "r1", "label": None}],
              "failures": [{"requirement": "r2", "trace": "expected 'GOLD-VALUE'", "label": "no_op_fail"},
                           {"requirement": "r3", "trace": "x", "label": "no_op_pass"}]}
        rec = aw_agent.evaluation_fields(ev)
        self.assertNotIn("GOLD-VALUE", json.dumps(rec))
        self.assertEqual(rec["failed_requirements"], ["r2", "r3"])
        self.assertTrue(rec["collateral_damage"])
        self.assertEqual((rec["pass_count"], rec["num_tests"]), (1, 3))


MODULES = frozenset({"uuid", "contextlib", "inspect", "json", "types", "re"})


BYPASSES = {
    "uuid.os": "import uuid\nprint(uuid.os.environ.get('RITS_API_KEY'))",
    "contextlib.os": "import contextlib\ncontextlib.os.listdir('.')",
    "getattr constant": "import uuid\ngetattr(uuid, 'os').environ",
    "getattr built name": "import uuid\ngetattr(uuid, 'o' + 's')",
    "subclasses walk": "().__class__.__base__.__subclasses__()",
    "globals of a function": "f = lambda: 0\nf.__globals__['__builtins__']",
    "frame walk": "import inspect\ninspect.currentframe().f_back.f_locals",
    "builtins import": "__import__('os')",
    "eval": "eval('1')",
    "vars": "vars()",
    "ipython shell escape": "!cat /etc/passwd",
    "ipython magic": "%env",
}


LEGIT = {
    "app api call": "token = apis.spotify.login(username='a', password='b')['access_token']",
    "dynamic app by name": "fn = getattr(getattr(apis, app_name), api_name)\nprint(fn(**kw))",
    "json": "import json\nprint(json.dumps({'a': 1}))",
    "type name": "print(type(x).__name__)",
    "class with init": "class A:\n    def __init__(self):\n        super().__init__()",
    "plain syntax error": "print(",
    "complete task": "apis.supervisor.complete_task(answer=None)",
}


class TestCodeGuard(unittest.TestCase):
    def test_bypasses_are_rejected(self):
        for name, code in BYPASSES.items():
            with self.subTest(name):
                self.assertTrue(aw_agent.code_guard_violations(code, MODULES), code)

    def test_legitimate_agent_code_passes(self):
        for name, code in LEGIT.items():
            with self.subTest(name):
                self.assertEqual(aw_agent.code_guard_violations(code, MODULES), [], code)

    def test_seed_prompt_examples_pass(self):
        prompt = (EX / "seed_capability" / "policy" / "instructions.txt").read_text()
        blocks = re.findall(r"```python\n(.*?)```", prompt, flags=re.DOTALL)
        self.assertGreater(len(blocks), 5)
        for code in blocks:
            self.assertEqual(aw_agent.code_guard_violations(code, MODULES), [], code)

    def test_setup_snippet_passes(self):
        snippet = aw_agent.setup_snippet("def f(apis, app_name):\n    return getattr(apis, app_name)\n",
                                         {"spotify.login": "N"})
        self.assertEqual(aw_agent.code_guard_violations(snippet, MODULES), [])


class TestHardenGuard(unittest.TestCase):
    """harden_guard() against a stand-in for appworld.common.safety_guard (AppWorld is not installed)."""

    def _fake_appworld(self):
        sg = types.ModuleType("appworld.common.safety_guard")
        sg.ALLOWED_MODULE_NAMES = {"os", "pathlib", "io", "uuid", "contextlib", "json", "collections.abc"}

        class SafetyGuard:
            def is_syntax_safe(self, code):
                if "import os" in code:
                    return False, "Usage of the following module is not allowed: os."
                return True, ""
        sg.SafetyGuard = SafetyGuard
        mods = {"appworld": types.ModuleType("appworld"), "appworld.common": types.ModuleType("appworld.common"),
                "appworld.common.safety_guard": sg}
        mods["appworld"].common = mods["appworld.common"]
        mods["appworld.common"].safety_guard = sg
        return sg, mods

    def test_wraps_appworlds_check(self):
        sg, mods = self._fake_appworld()
        with patch.dict(sys.modules, mods):
            aw_agent.harden_guard()
            aw_agent.harden_guard()  # idempotent
        self.assertNotIn("os", sg.ALLOWED_MODULE_NAMES)
        g = sg.SafetyGuard()
        ok, msg = g.is_syntax_safe("import uuid\nuuid.os.environ")
        self.assertFalse(ok)
        self.assertTrue(msg.startswith(aw_agent.GUARD_MESSAGE))
        self.assertEqual(g.is_syntax_safe("import os")[1], "Usage of the following module is not allowed: os.")
        self.assertEqual(g.is_syntax_safe("apis.spotify.login()"), (True, ""))
        self.assertFalse(g.is_syntax_safe("import uuid\ngetattr(uuid, name)")[0])


def _raise(exc: BaseException):
    try:
        raise exc
    except BaseException as e:  # noqa: BLE001
        return e


class TestRedactError(unittest.TestCase):
    def test_evaluate_phase_drops_the_message(self):
        out = aw_agent.redact_error(_raise(AssertionError(GOLD)), "evaluate")
        self.assertNotIn("GOLD-ANSWER", out)
        self.assertTrue(out.startswith("AssertionError during evaluate"))
        self.assertIn("in _raise", out)  # frames are kept

    def test_setup_phase_keeps_a_redacted_capped_message(self):
        e = _raise(FileNotFoundError("/aw/root_opt/data/tasks/x/specs.json key=sk-123 " + "y" * 900))
        out = aw_agent.redact_error(e, "setup", {"/aw/root_opt": "<root>", "sk-123": "<secret>"})
        self.assertIn("<root>/data/tasks", out)
        self.assertNotIn("/aw/root_opt", out)
        self.assertNotIn("sk-123", out)
        self.assertLess(len(out.split(" [")[0]), aw_agent.ERROR_MESSAGE_MAX + 60)

    def test_no_source_lines_in_frames(self):
        out = aw_agent.redact_error(_raise(ValueError("v")), "episode")
        self.assertNotIn("raise exc", out)

    def test_stderr_reduced_to_the_exception_type(self):
        stderr = f'Traceback (most recent call last):\n  File "x.py", line 1\nAssertionError: {GOLD}\n'
        self.assertEqual(aw_agent.redact_stderr(stderr), "AssertionError")
        self.assertEqual(aw_agent.redact_stderr("Killed\n"), "")


class TestMainRecord(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.spec = self.tmp / "spec.json"
        self.out = self.tmp / "out.json"
        self.spec.write_text(json.dumps({"task_id": "t", "appworld_root": "/aw/root_full", "experiment_name": "e"}))

    def _main_with(self, phase: str, exc: Exception) -> dict:
        def boom(spec):
            aw_agent.set_phase(phase)
            raise exc
        with patch.object(aw_agent, "run_episode", side_effect=boom):
            aw_agent.main(["aw_agent.py", str(self.spec), str(self.out)])
        return json.loads(self.out.read_text())

    def test_record_has_no_traceback_and_no_gold(self):
        rec = self._main_with("evaluate", AssertionError(GOLD))
        self.assertNotIn("traceback", rec)
        self.assertNotIn("GOLD-ANSWER", json.dumps(rec))
        self.assertIn("AssertionError during evaluate", rec["infra_error"])

    def test_root_path_is_replaced(self):
        rec = self._main_with("setup", OSError("cannot open /aw/root_full/data/x"))
        self.assertIn("<root>/data/x", rec["infra_error"])
        self.assertNotIn("/aw/root_full", json.dumps(rec))


class TestLoadSecrets(unittest.TestCase):
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


class TestWorkerEnv(unittest.TestCase):
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



class TestModelAuth(unittest.TestCase):
    """AW_KEY_HEADER picks how the key reaches the model: a named header (RITS) or a bearer key
    (a LiteLLM gateway, as the CI leg uses). Either way the config names an env var, never the key."""

    def _config(self, **env):
        import importlib
        with patch.dict(os.environ, env):
            return importlib.reload(aw_agent).MODEL_CONFIG

    def tearDown(self):
        import importlib
        importlib.reload(aw_agent)

    def test_default_is_the_rits_header(self):
        os.environ.pop("AW_KEY_HEADER", None)
        cfg = self._config(AW_KEY_ENV="RITS_API_KEY")
        self.assertEqual(cfg["extra_headers_env"], {"RITS_API_KEY": "RITS_API_KEY"})
        self.assertEqual(cfg["api_key"], "unused")
        self.assertNotIn("api_key_env_name", cfg)

    def test_bearer_reads_the_key_from_the_named_env_var(self):
        cfg = self._config(AW_KEY_HEADER="bearer", AW_KEY_ENV="AW_AGENT_KEY")
        self.assertEqual(cfg["api_key_env_name"], "AW_AGENT_KEY")
        self.assertNotIn("extra_headers_env", cfg)
        self.assertNotIn("api_key", cfg)
        self.assertEqual(aw_agent.SECRET_KEYS, ("AW_AGENT_KEY",))

class Agent:  # appworld_agents.code.simplified.agent.Agent @ 42b5bcf
    def __init__(self, model_config: dict[str, Any], appworld_config: dict[str, Any] | None = None,
                 logger_config: dict[str, Any] | None = None, usage_tracker_config: dict[str, Any] | None = None,
                 max_steps: int = 40, log_lm_calls: bool = False, skip_if_finished: bool = False):
        pass


class SimplifiedReActCodeAgent(Agent):  # ...react_code_agent @ 42b5bcf
    def __init__(self, prompt_file_path: str, ignore_multiple_calls: bool = True,
                 max_prompt_length: int | None = None, max_output_length: int | None = None, **kwargs: Any):
        super().__init__(**kwargs)


class CapLike(SimplifiedReActCodeAgent):  # same shape as aw_agent.build_agent_class()
    def __init__(self, candidate, **kwargs: Any):
        super().__init__(**kwargs)


class DriftedAgent(Agent):  # upstream renamed max_output_length
    def __init__(self, prompt_file_path: str, ignore_multiple_calls: bool = True,
                 max_prompt_length: int | None = None, max_observation_length: int | None = None, **kwargs: Any):
        super().__init__(**kwargs)


class CapOnDrifted(DriftedAgent):
    def __init__(self, candidate, **kwargs: Any):
        super().__init__(**kwargs)


SPEC = {"candidate_dir": str(EX / "seed_capability"), "random_seed": 100, "log_lm_calls": False}


class TestAgentSignature(unittest.TestCase):
    def test_every_kwarg_is_accepted_at_the_pin(self):
        kw = aw_agent.agent_kwargs(SPEC, dict(aw_agent.MODEL_CONFIG))
        self.assertEqual(len(kw), 10)
        self.assertEqual(aw_agent.unaccepted_kwargs(CapLike, kw), [])
        CapLike(candidate={}, **kw)  # and it really constructs

    def test_drift_is_named(self):
        kw = aw_agent.agent_kwargs(SPEC, dict(aw_agent.MODEL_CONFIG))
        self.assertEqual(aw_agent.unaccepted_kwargs(CapOnDrifted, kw), ["max_output_length"])

    def test_check_injection_runs_the_signature_check(self):
        src = (EX / "scripts" / "check_injection.py").read_text()
        self.assertIn("unaccepted_kwargs", src)
        self.assertIn("A4.0", src)


if __name__ == "__main__":
    unittest.main()
