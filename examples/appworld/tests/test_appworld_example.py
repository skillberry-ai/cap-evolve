"""Offline tests for the AppWorld example: no AppWorld install, no model call.

They cover the parts whose mistakes would silently corrupt a run: the candidate lints, the prompt
injection helpers, the gold-free evaluation record, the scoring feedback and the ALTK conversion.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "adapters"))
sys.path.insert(0, str(EX / "altk"))

import aw_agent  # noqa: E402
import lints  # noqa: E402

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


class LintTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        root = make_root(self.tmp)
        self.env = patch.dict(os.environ, {"APPWORLD_ROOT": str(root), "AW_LINT_CACHE": str(self.tmp / "none.json")})
        self.env.start()
        lints.CACHE = Path(os.environ["AW_LINT_CACHE"])
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
        lints.CACHE = self.tmp / "cache.json"
        lints.write_cache()
        lints.lint_data.cache_clear()
        self.assertIn(("move", "all", "songs", "from", "my", "workout", "playlist", "to"), lints.lint_data()["grams"])


class InjectionTests(unittest.TestCase):
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


class ScoreTests(unittest.TestCase):
    def setUp(self):
        from adapter import Adapter
        from cap_evolve import Rollout, Task
        self.ad, self.Rollout = Adapter(), Rollout
        self.task = Task(id="t", input={"instruction": "x"})

    def test_success_and_failure_feedback(self):
        ok = self.Rollout(task_id="t", metadata={"success": True, "num_tests": 2, "pass_count": 2, "n_steps": 4})
        bad = self.Rollout(task_id="t", metadata={"success": False, "num_tests": 2, "pass_count": 1, "n_steps": 9,
                                                   "failed_requirements": ["assert the playlist exists"],
                                                   "collateral_damage": True})
        s_ok, s_bad = self.ad.score(self.task, ok), self.ad.score(self.task, bad)
        self.assertEqual((s_ok.reward, s_bad.reward), (1.0, 0.0))
        self.assertIn("assert the playlist exists", s_bad.feedback)
        self.assertIn("Collateral damage", s_bad.feedback)
        self.assertEqual(s_bad.to_dict(), self.ad.score(self.task, bad).to_dict())  # deterministic

    def test_lint_reject_and_infra_error(self):
        lr = self.ad.score(self.task, self.Rollout(task_id="t", metadata={"lint_reject": ["bad helper"]}))
        self.assertEqual(lr.reward, 0.0)
        self.assertIn("LINT_REJECT", lr.feedback)
        err = self.ad.score(self.task, self.Rollout(task_id="t", error="infrastructure: timeout"))
        self.assertTrue(err.raw.get("errored"))


class AltkConversionTests(unittest.TestCase):
    def test_instruction_first_and_no_outcome_label(self):
        from to_messages import rollout_to_messages
        msgs = rollout_to_messages({"input": {"instruction": "Do X", "supervisor": "A B"},
                                    "rollout": {"trace": [{"thought": "t", "code": "print(1)", "output": "1"}]},
                                    "score": {"reward": 1.0}})
        self.assertEqual(msgs[0], {"role": "user", "content": "Do X\nSupervisor: A B"})
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant", "user"])
        self.assertNotIn("reward", json.dumps(msgs))


if __name__ == "__main__":
    unittest.main()
