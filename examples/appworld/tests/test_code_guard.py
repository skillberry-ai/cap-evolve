"""PR 874 review finding 2: blocked modules must not be reachable as attributes of allowed ones.

AppWorld's guard checks literal imports only, so ``import uuid; uuid.os.environ`` got through.
"""

from __future__ import annotations

import re
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aw_testlib import EX  # noqa: E402

import aw_agent  # noqa: E402

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


class CodeGuardTests(unittest.TestCase):
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


class HardenGuardTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
