"""Offline tests for the AppWorld blackbox approach: tailoring, the seed skill, the SKILL.md lints and
the adapter's deploy/lint wiring. No AppWorld install, no store, no proxy and no model needed.

    python3 benchmarks/appworld/examples/react_agent/blackbox/tests/test_blackbox.py -v
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

EX = Path(__file__).resolve().parents[1]
DIRECT = EX.parent  # the direct example is the parent folder
sys.path.insert(0, str(EX / "adapters"))
sys.path.insert(0, str(EX / "scripts"))
sys.path.insert(1, str(DIRECT / "adapters"))  # the direct harness the blackbox adapter reuses
sys.path.append(str(Path(__file__).resolve().parents[6] / "core"))

import appworld_tailoring as tailoring  # noqa: E402
import bb_lints  # noqa: E402
import lints as direct_lints  # noqa: E402
import make_seed_skill  # noqa: E402


def load_bb_adapter():
    """The blackbox adapter by file path: the direct tests also import a module named `adapter`."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("aw_blackbox_adapter", EX / "adapters" / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

STOCK = (DIRECT / "seed_capability" / "policy" / "instructions.txt").read_text(encoding="utf-8")
APPS = json.dumps([{"name": "spotify", "description": "A music app."}], indent=1)
SUPERVISOR = {"first_name": "Joseph", "last_name": "Weber", "email": "joseph.webe@gmail.com",
              "phone_number": "2233697879"}


class LintDataMixin:
    """A fake lint cache (no 8-grams, no contacts) and app-list file, so lints run offline."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        cache = self.tmp / "lint_cache.json"
        cache.write_text(json.dumps({"grams": [], "contacts": ["timothy white"], "apps": ["spotify"],
                                     "api_names": ["login"]}))
        apps = self.tmp / "app_descriptions.json"
        apps.write_text(json.dumps({"text": APPS}))
        self.env = patch.dict(os.environ, {"AW_LINT_CACHE": str(cache), "AW_APP_DESCRIPTIONS": str(apps)})
        self.env.start()
        direct_lints.lint_data.cache_clear()

    def tearDown(self):
        self.env.stop()
        direct_lints.lint_data.cache_clear()

    def seed_dir(self) -> Path:
        d = self.tmp / "my_skill"
        d.mkdir(exist_ok=True)
        (d / "SKILL.md").write_text(make_seed_skill.build(STOCK, APPS), encoding="utf-8")
        return d


class TestTailoring(unittest.TestCase):
    def test_marker_matches_only_the_real_task_turn(self):
        rx = re.compile(tailoring.HISTORY_START_REGEX)
        turns = re.split(r"^(?:USER|ASSISTANT):\n", STOCK, flags=re.M)
        hits = [t for t in turns if rx.search(t)]
        self.assertEqual(len(hits), 1)
        self.assertIn("Task: {{ instruction }}", hits[0])
        self.assertIsNone(rx.search("Using these APIs, you can now generate code, that I will execute"))

    def test_context_headers(self):
        h = tailoring.context_headers("aw-ep1", "07b42fd_2", SUPERVISOR)
        self.assertEqual(h["skillberry-context-env_id"], "aw-ep1")
        self.assertEqual(h["skillberry-context-task_id"], "07b42fd_2")
        self.assertEqual(h["skillberry-context-plugin"], "appworld")
        self.assertEqual(h["skillberry-context-history_start_regex"], tailoring.HISTORY_START_REGEX)
        for f in tailoring.SUPERVISOR_FIELDS:
            self.assertEqual(h[f"skillberry-context-template-main_user-{f}"], SUPERVISOR[f])

    def test_header_values_must_be_single_line_ascii(self):
        with self.assertRaises(ValueError):
            tailoring.context_headers("e", "t", dict(SUPERVISOR, last_name="Line\nbreak"))
        with self.assertRaises(ValueError):
            tailoring.context_headers("e", "t", dict(SUPERVISOR, first_name="José"))

    def test_spa_model_name_mapping(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AW_SPA_MODEL", None)
            self.assertEqual(tailoring.spa_model_name("hosted_vllm/openai/gpt-oss-120b-a100"),
                             "openai/openai/gpt-oss-120b-a100")
            self.assertEqual(tailoring.spa_model_name("litellm_proxy/aws/claude-haiku-4-5"), "openai/aws/claude-haiku-4-5")
            self.assertEqual(tailoring.spa_model_name("openai/aws/gpt-oss-120b"), "openai/aws/gpt-oss-120b")
        with patch.dict(os.environ, {"AW_SPA_MODEL": "openai/custom"}):
            self.assertEqual(tailoring.spa_model_name("anything"), "openai/custom")

    def test_spa_upstream_env_requires_bearer(self):
        with self.assertRaises(tailoring.BlackboxConfigError):
            tailoring.spa_upstream_env({"AW_KEY_HEADER": "RITS_API_KEY"})

    def test_spa_upstream_env_reads_only_the_key_and_url_from_the_secrets_file(self):
        with tempfile.TemporaryDirectory() as d:
            secrets = Path(d) / ".env"
            secrets.write_text("GW_KEY=sk-test\nMODEL_SERVER_URL=http://gw.example\nOTHER=nope\n")
            env = tailoring.spa_upstream_env({
                "AW_KEY_HEADER": "bearer", "AW_KEY_ENV": "GW_KEY", "AW_SECRETS_FILE": str(secrets),
                "AW_MODEL_NAME": "litellm_proxy/aws/gpt-oss-120b", "AW_MODEL_URL": "{{MODEL_SERVER_URL}}/v1"})
        self.assertEqual(env, {"SPA_MODEL_NAME": "openai/aws/gpt-oss-120b", "OPENAI_API_BASE": "http://gw.example/v1",
                               "OPENAI_BASE_URL": "http://gw.example/v1", "OPENAI_API_KEY": "sk-test"})

    def test_deploy_is_once_per_candidate_content(self):
        calls = []

        class FakeBB:
            Protection = staticmethod(lambda: "protect")

            @staticmethod
            def start_store():
                calls.append("start_store")

            @staticmethod
            def reset_store_to_skill(d, name, protect):
                calls.append(("reset", name))

            @staticmethod
            def restart_spa(name, **env):
                calls.append(("restart", name, env["SPA_MODEL_NAME"]))

        with tempfile.TemporaryDirectory() as d, \
                patch.object(tailoring, "blackbox_env", lambda: FakeBB), \
                patch.object(tailoring, "spa_upstream_env", lambda: {"SPA_MODEL_NAME": "m"}):
            tailoring._deployed["digest"] = None
            skill = Path(d)
            (skill / "SKILL.md").write_text("v1")
            self.assertTrue(tailoring.deploy(skill))
            self.assertFalse(tailoring.deploy(skill))  # same content: no restart
            (skill / "SKILL.md").write_text("v2")
            self.assertTrue(tailoring.deploy(skill))
        self.assertEqual([c for c in calls if c[0] == "restart"], [("restart", "my_skill", "m")] * 2)


class TestSeedSkill(unittest.TestCase):
    def test_body_is_the_stock_prompt_up_to_the_real_task_turn(self):
        text = make_seed_skill.build(STOCK, APPS)
        fm, body = bb_lints.split_frontmatter(text)
        self.assertEqual(fm["name"], "my_skill")
        self.assertTrue(body.startswith(make_seed_skill.HEADER))
        cut = STOCK.rfind(make_seed_skill.FINAL_TURN)
        expected = STOCK[:cut].rstrip("\n").replace("{{ app_descriptions }}", APPS) + "\n"
        self.assertEqual(body[len(make_seed_skill.HEADER):], expected)  # byte for byte
        self.assertNotIn("now generate code to solve the actual task", body)
        self.assertNotIn("{{ instruction }}", body)
        self.assertEqual(body.count("{{ main_user."), 6)


class TestSkillLints(LintDataMixin, unittest.TestCase):
    def test_seed_passes(self):
        self.assertEqual(bb_lints.lint_candidate(self.seed_dir()), [])

    def edited(self, old: str, new: str) -> list[str]:
        d = self.seed_dir()
        text = (d / "SKILL.md").read_text()
        self.assertIn(old, text)
        (d / "SKILL.md").write_text(text.replace(old, new, 1))
        return bb_lints.lint_candidate(d)

    def test_removed_placeholder_is_rejected(self):
        v = self.edited("{{ main_user.phone_number }}", "the phone number")
        self.assertTrue(any("main_user.phone_number" in x for x in v), v)

    def test_invented_field_is_rejected(self):
        self.assertTrue(any("main_user.address does not exist" in x
                            for x in self.edited("{{ main_user.email }}", "{{ main_user.address }}")))

    def test_instruction_placeholder_is_rejected(self):
        self.assertTrue(self.edited("**Key instructions**", "{{ instruction }} **Key instructions**"))

    def test_jinja_block_is_rejected(self):
        self.assertTrue(any("blocks" in x for x in self.edited("**Key instructions**", "{% if x %}y{% endif %}**Key instructions**")))

    def test_app_list_must_stay_verbatim(self):
        self.assertTrue(any("app list" in x for x in self.edited("A music app.", "A great music app.")))

    def test_frontmatter_name(self):
        self.assertTrue(any("name: my_skill" in x for x in self.edited("name: my_skill", "name: other")))

    def test_skill_package_addition_is_rejected(self):
        d = self.seed_dir()
        (d / "scripts").mkdir()
        (d / "scripts" / "x.py").write_text("def x():\n    return 1\n")
        self.assertTrue(any("SKILL.md only" in x for x in bb_lints.lint_candidate(d)))

    def test_harness_files_are_ignored(self):
        d = self.seed_dir()
        for rel in ("INSTRUCTIONS.md", "JOURNAL.md", "guidance/sources/api_index.md"):
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            (d / rel).write_text("harness file")
        self.assertEqual(bb_lints.lint_candidate(d), [])

    def test_supervisor_contact_is_rejected(self):
        self.assertTrue(any("supervisor" in x for x in self.edited("**Key instructions**", "Timothy White **Key instructions**")))

    def test_missing_skill(self):
        self.assertEqual(bb_lints.lint_candidate(self.tmp), ["SKILL.md: missing"])


class TestAdapterWiring(LintDataMixin, unittest.TestCase):
    def test_lint_reject_runs_no_episode_and_does_not_deploy(self):
        bb_adapter = load_bb_adapter()
        d = self.seed_dir()
        (d / "scripts").mkdir()
        (d / "scripts" / "x.py").write_text("def x():\n    return 1\n")
        task = bb_adapter.Task(id="t1", input={})
        with patch.object(bb_adapter.Adapter, "_check_seal", lambda self, ids: None), \
                patch.object(bb_adapter, "_wait_readable", lambda p, timeout_s=60.0: None), \
                patch.object(bb_adapter.tailoring, "deploy", side_effect=AssertionError("deployed")):
            out = bb_adapter.Adapter().run_trials([task], d, n_trials=2, base_seed=0)
        self.assertEqual([r.output for r in out["t1"]], ["lint_reject", "lint_reject"])

    def test_deploy_failure_is_infra_not_candidate(self):
        bb_adapter = load_bb_adapter()
        task = bb_adapter.Task(id="t1", input={})
        with patch.object(bb_adapter.Adapter, "_check_seal", lambda self, ids: None), \
                patch.object(bb_adapter, "_wait_readable", lambda p, timeout_s=60.0: None), \
                patch.object(bb_adapter.tailoring, "deploy", side_effect=RuntimeError("store down")):
            out = bb_adapter.Adapter().run_trials([task], self.seed_dir(), n_trials=1, base_seed=0)
        self.assertTrue(out["t1"][0].error.startswith("infrastructure:"))


class TestNativeSims(unittest.TestCase):
    """Each episode's own ReAct message list lands in <run_dir>/native_sims/<tag>/<split>/, and never
    in the rollout."""

    def setUp(self):
        self.bb = load_bb_adapter()
        self.run = Path(tempfile.mkdtemp())
        (self.run / "splits.json").write_text(json.dumps({"train": ["a", "b"], "val": ["a", "b"], "test": ["c"]}))
        for d in ("work/cand_0001", "candidates/seed"):
            (self.run / d).mkdir(parents=True)

    def test_path_is_run_dir_native_sims_tag_split(self):
        self.assertEqual(self.bb._native_dir(self.run / "work" / "cand_0001", ["a", "b"]),
                         self.run / "native_sims" / "cand_0001" / "val")
        self.assertEqual(self.bb._native_dir(self.run / "candidates" / "seed", ["c"]),
                         self.run / "native_sims" / "seed" / "test")

    def test_off_and_unknown_layout_write_nothing(self):
        with patch.dict(os.environ, {"CAPEVOLVE_NATIVE_SIMS": "0"}):
            self.assertIsNone(self.bb._native_dir(self.run / "work" / "cand_0001", ["a"]))
        self.assertIsNone(self.bb._native_dir(self.run / "elsewhere", ["a"]))

    def test_a_second_record_never_replaces_the_first(self):
        dest = self.run / "native_sims" / "seed" / "val" / "a__t0.json"
        first = self.bb._write_native(dest, {"phase": "baseline"})
        second = self.bb._write_native(dest, {"phase": "final"})
        self.assertEqual((first, second), (dest, dest.with_name("a__t0__2.json")))
        self.assertEqual(json.loads(dest.read_text())["phase"], "baseline")
        self.assertEqual(json.loads(second.read_text())["phase"], "final")

    def test_episode_writes_messages_to_native_sims_not_the_rollout(self):
        native_msgs = [{"role": "user", "content": "stock prompt"}, {"role": "assistant", "content": "code"}]

        def fake_run(argv, **kw):
            Path(argv[3]).write_text(json.dumps({
                "task_id": "a", "termination": "completed", "steps": [{"step": 1}],
                "native": {"task_id": "a", "num_prompt_messages": 1, "messages": native_msgs}}))
            return type("P", (), {"returncode": 0, "stderr": ""})()

        dest = self.run / "native_sims" / "cand_0001" / "val" / "a__t0.json"
        with patch.object(self.bb, "_supervisor", lambda tid, root: SUPERVISOR), \
                patch.object(self.bb, "_client_prompt", lambda: Path("instructions.txt")), \
                patch.object(self.bb.subprocess, "run", fake_run), \
                patch.object(self.bb.tailoring, "disconnect", lambda *a, **k: True):
            r = self.bb.Adapter()._episode(self.bb.Task(id="a", input={}), 0, self.run, self.run, dest)
        self.assertNotIn("native", r.metadata)
        self.assertEqual(r.trace, [{"step": 1}])
        saved = json.loads(dest.read_text())
        self.assertEqual(saved["messages"], native_msgs)
        self.assertEqual((saved["seed"], saved["termination"]), (0, "completed"))


class TestDisconnectOnTrialEnd(unittest.TestCase):
    """The proxy's per-episode state is released when the trial ends, however it ended."""

    def run_episode(self, fake_run):
        bb = load_bb_adapter()
        calls = []
        run = Path(tempfile.mkdtemp())
        with patch.object(bb, "_supervisor", lambda tid, root: SUPERVISOR), \
                patch.object(bb, "_client_prompt", lambda: Path("instructions.txt")), \
                patch.object(bb.subprocess, "run", fake_run), \
                patch.dict(os.environ, {"AW_INFRA_RETRIES": "0"}), \
                patch.object(bb.tailoring, "disconnect", lambda headers, **k: calls.append(headers) or True):
            r = bb.Adapter()._episode(bb.Task(id="a", input={}), 0, run, run)
        return r, calls

    def test_worker_killed_at_the_wall_cap_is_disconnected_by_the_adapter(self):
        def fake_run(argv, **kw):
            raise __import__("subprocess").TimeoutExpired(argv, 1)
        r, calls = self.run_episode(fake_run)
        self.assertTrue(r.error.startswith("infrastructure:"))
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0]["skillberry-context-env_id"].startswith("aw-a__s0__"))

    def test_worker_that_disconnected_itself_is_not_disconnected_again(self):
        def fake_run(argv, **kw):
            Path(argv[3]).write_text(json.dumps({"task_id": "a", "termination": "completed", "steps": [],
                                                 "disconnected": True}))
            return type("P", (), {"returncode": 0, "stderr": ""})()
        r, calls = self.run_episode(fake_run)
        self.assertIsNone(r.error)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
