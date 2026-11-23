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
SEED = EX / "seed_capability"  # the committed blackbox seed: my_skill/SKILL.md + tools/
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
        """A rendered seed candidate, as setup_project.sh writes it: my_skill/SKILL.md (app list filled
        in) and the seed's tools/ files."""
        d = self.tmp / "cand"
        (d / "my_skill").mkdir(parents=True, exist_ok=True)
        (d / "my_skill" / "SKILL.md").write_text(make_seed_skill.build(STOCK, APPS), encoding="utf-8")
        make_seed_skill.write_tools(d)
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
            cand = Path(d)
            (cand / "my_skill").mkdir()
            (cand / "my_skill" / "SKILL.md").write_text("v1")
            self.assertTrue(tailoring.deploy(cand))
            self.assertFalse(tailoring.deploy(cand))  # same content: no restart
            (cand / "my_skill" / "SKILL.md").write_text("v2")
            self.assertTrue(tailoring.deploy(cand))
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
        text = (d / "my_skill" / "SKILL.md").read_text()
        self.assertIn(old, text)
        (d / "my_skill" / "SKILL.md").write_text(text.replace(old, new, 1))
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
        (d / "my_skill" / "scripts").mkdir()
        (d / "my_skill" / "scripts" / "x.py").write_text("def x():\n    return 1\n")
        self.assertTrue(any("found ['my_skill/scripts/x.py']" in x for x in bb_lints.lint_candidate(d)))

    def test_harness_files_are_ignored(self):
        d = self.seed_dir()
        for rel in ("INSTRUCTIONS.md", "JOURNAL.md", "guidance/sources/api_index.md"):
            (d / rel).parent.mkdir(parents=True, exist_ok=True)
            (d / rel).write_text("harness file")
        self.assertEqual(bb_lints.lint_candidate(d), [])

    def test_supervisor_contact_is_rejected(self):
        self.assertTrue(any("supervisor" in x for x in self.edited("**Key instructions**", "Timothy White **Key instructions**")))

    def test_missing_skill(self):
        self.assertEqual(bb_lints.lint_candidate(self.tmp), ["SKILL.md: missing (expected my_skill/SKILL.md)"])


class TestAdapterWiring(LintDataMixin, unittest.TestCase):
    def test_lint_reject_runs_no_episode_and_does_not_deploy(self):
        bb_adapter = load_bb_adapter()
        d = self.seed_dir()
        (d / "my_skill" / "scripts").mkdir()
        (d / "my_skill" / "scripts" / "x.py").write_text("def x():\n    return 1\n")
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
                patch.dict(os.environ, {"AW_REMOTE_REPL": "0"}), \
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
                patch.dict(os.environ, {"AW_INFRA_RETRIES": "0", "AW_REMOTE_REPL": "0"}), \
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


class TestRemoteRepl(unittest.TestCase):
    """Each trial gets its own AppWorld environment server; the adapter owns its port and lifetime."""

    def test_ports_are_unique_and_skip_ports_already_bound(self):
        import socket
        env = {"AW_ENV_PORTS": "9390-9399"}
        with socket.socket() as busy:
            busy.bind(("127.0.0.1", 9390))
            busy.listen(1)
            got = [tailoring.reserve_port(env) for _ in range(3)]
        try:
            self.assertNotIn(9390, got)
            self.assertEqual(len(set(got)), 3)
        finally:
            for p in got:
                tailoring.release_port(p)

    def test_port_range_runs_out(self):
        env = {"AW_ENV_PORTS": "9398-9398"}
        p = tailoring.reserve_port(env)
        try:
            with self.assertRaises(RuntimeError):
                tailoring.reserve_port(env)
        finally:
            tailoring.release_port(p)

    def test_off_switch(self):
        self.assertTrue(tailoring.remote_repl_enabled({}))
        self.assertFalse(tailoring.remote_repl_enabled({"AW_REMOTE_REPL": "0"}))

    def _episode(self, fake_run, start=lambda root, env: 9123):
        bb = load_bb_adapter()
        stopped, seen = [], {}
        run = Path(tempfile.mkdtemp())

        def run_and_capture(argv, **kw):
            seen.update(json.loads(Path(argv[2]).read_text()))
            return fake_run(argv, **kw)

        with patch.object(bb, "_supervisor", lambda tid, root: SUPERVISOR), \
                patch.object(bb, "_client_prompt", lambda: Path("instructions.txt")), \
                patch.object(bb.subprocess, "run", run_and_capture), \
                patch.dict(os.environ, {"AW_INFRA_RETRIES": "0", "AW_REMOTE_REPL": "1"}), \
                patch.object(bb.tailoring, "start_env_server", start), \
                patch.object(bb.tailoring, "stop_env_server", lambda port: stopped.append(port) or True), \
                patch.object(bb.tailoring, "disconnect", lambda *a, **k: True):
            r = bb.Adapter()._episode(bb.Task(id="a", input={}), 0, run, run)
        return r, seen, stopped

    def test_the_world_gets_the_trials_server_and_the_server_is_stopped(self):
        def fake_run(argv, **kw):
            Path(argv[3]).write_text(json.dumps({"task_id": "a", "termination": "completed", "steps": [],
                                                 "disconnected": True}))
            return type("P", (), {"returncode": 0, "stderr": ""})()
        r, seen, stopped = self._episode(fake_run)
        self.assertEqual(seen["remote_environment_url"], "http://127.0.0.1:9123")
        self.assertEqual(stopped, [9123])
        self.assertIsNone(r.error)

    def test_server_is_stopped_even_when_the_worker_is_killed(self):
        def fake_run(argv, **kw):
            raise __import__("subprocess").TimeoutExpired(argv, 1)
        r, _, stopped = self._episode(fake_run)
        self.assertTrue(r.error.startswith("infrastructure:"))
        self.assertEqual(stopped, [9123])

    def test_a_server_that_does_not_start_is_infra_and_runs_no_worker(self):
        def no_server(root, env):
            raise RuntimeError("did not come up")

        def fake_run(argv, **kw):
            raise AssertionError("the worker must not run without its server")
        r, seen, stopped = self._episode(fake_run, start=no_server)
        self.assertIn("remote REPL did not start", r.error)
        self.assertEqual((seen, stopped), ({}, []))


HELPERS = '''"""Helpers."""


def fetch_all_pages(apis, app_name, api_name, **kwargs):
    """Every page of a paginated API."""
    fn = getattr(getattr(apis, app_name), api_name)
    out, page = [], 0
    while True:
        batch = fn(page_index=page, **kwargs)
        if not batch:
            return out
        out += batch
        page += 1
'''
NOTES = {"spotify.show_song": "N1", "spotify": "APP"}


class ToolsMixin(LintDataMixin):
    def tools_dir(self, helpers=HELPERS, notes=None) -> Path:
        """A rendered candidate with tools/helpers.py and tools/api_notes.json
        (lint data: app spotify, api login)."""
        d = self.seed_dir()
        (d / "tools" / "helpers.py").write_text(helpers)
        (d / "tools" / "api_notes.json").write_text(json.dumps({"spotify": "Paginated."} if notes is None else notes))
        return d


class TestToolsLints(ToolsMixin, unittest.TestCase):
    def test_seed_passes_and_loads_nothing(self):
        d = self.seed_dir()
        self.assertEqual(bb_lints.lint_candidate(d), [])
        self.assertEqual(tailoring.repl_code(d), "")

    def test_helpers_and_notes_pass_without_skill_md_mentioning_them(self):
        d = self.tools_dir()
        self.assertNotIn("fetch_all_pages", (d / "my_skill" / "SKILL.md").read_text())
        self.assertEqual(bb_lints.lint_candidate(d), [])

    def test_direct_helper_rules_apply(self):
        d = self.tools_dir(helpers=HELPERS + "\nfetch_all_pages(None, 'a', 'b')\n")
        v = bb_lints.lint_candidate(d)
        self.assertTrue(any(x.startswith("tools/helpers.py:") and "top level" in x for x in v), v)

    def test_direct_note_rules_apply(self):
        d = self.tools_dir(notes={"nosuchapp": "x"})
        self.assertTrue(any(x.startswith("tools/api_notes.json:") for x in bb_lints.lint_candidate(d)))

    def test_other_files_in_tools_are_rejected(self):
        d = self.tools_dir()
        (d / "tools" / "extra.md").write_text("x")
        self.assertTrue(any("tools/extra.md" in x for x in bb_lints.lint_candidate(d)))

    def test_anything_but_skill_md_in_my_skill_is_rejected(self):
        d = self.seed_dir()
        (d / "my_skill" / "repl").mkdir()
        (d / "my_skill" / "repl" / "api_notes.json").write_text("{}")
        self.assertTrue(any("my_skill/repl/api_notes.json" in x for x in bb_lints.lint_candidate(d)))


class TestSystemPromptNotice(ToolsMixin, unittest.TestCase):
    """The deployed SKILL.md (the system prompt) ends with direct's generated helper sentence."""

    def test_the_direct_sentence_ends_the_deployed_skill_md(self):
        import aw_agent
        d = self.tools_dir()
        deployed = tailoring.deployed_skill_md(d)
        direct = aw_agent.helper_notice(HELPERS)
        self.assertTrue(direct.startswith("Pre-defined helper functions are available in the REPL "
                                          "(call them directly; see their docstrings with help(name)): "))
        self.assertTrue(deployed.endswith(f"\n\n{direct}\n"))
        self.assertNotIn("init_repl", deployed)  # no loader tool: the model is told about the helpers only
        self.assertTrue(deployed.startswith((d / "my_skill" / "SKILL.md").read_text().rstrip()))

    def test_no_helpers_no_sentence(self):
        d = self.tools_dir(helpers='"""doc only"""\n', notes={"spotify": "n"})
        self.assertEqual(tailoring.deployed_skill_md(d), (d / "my_skill" / "SKILL.md").read_text())

    def test_deployed_skill_md_still_passes_the_skill_lint(self):
        # The proxy renders it as a Jinja template: the sentence must add no placeholder.
        self.assertEqual(bb_lints.lint_skill_md(tailoring.deployed_skill_md(self.tools_dir())), [])


class TestReplCode(ToolsMixin, unittest.TestCase):
    """The REPL code the worker runs: exactly the direct approach's."""

    def test_is_the_direct_setup_snippet(self):
        import aw_agent
        d = self.tools_dir(notes=NOTES)
        self.assertEqual(tailoring.repl_code(d), aw_agent.setup_snippet(HELPERS, NOTES))

    def test_defines_the_helpers_and_wraps_the_doc_lookups(self):
        import types
        ns = {"apis": types.SimpleNamespace(api_docs=FakeDocs())}
        exec(tailoring.repl_code(self.tools_dir(notes=NOTES)), ns)  # noqa: S102  (what world.execute runs)
        self.assertTrue(callable(ns["fetch_all_pages"]))
        doc = ns["apis"].api_docs.show_api_doc(app_name="spotify", api_name="show_song")
        self.assertEqual(doc, {"app_name": "spotify", "api_name": "show_song", "note": "N1"})
        listed = ns["apis"].api_docs.show_api_descriptions(app_name="spotify")
        self.assertEqual(listed, [{"name": "show_song", "note": "N1"}, {"note": "APP"}])

    def test_the_seed_loads_nothing(self):
        self.assertEqual(tailoring.repl_code(self.seed_dir()), "")


class FakeDocs:
    """Stands in for apis.api_docs: the two lookups the notes wrap."""

    @staticmethod
    def show_api_doc(app_name=None, api_name=None):
        return {"app_name": app_name, "api_name": api_name}

    @staticmethod
    def show_api_descriptions(app_name=None):
        return [{"name": "show_song"}]


class FakeStoreBB:
    """blackbox_env stand-in: records what deploy stages for the skill."""

    def __init__(self):
        self.staged = []
        self.Protection = lambda: "protect"

    def start_store(self):
        pass

    def restart_spa(self, name, **env):
        pass

    def reset_store_to_skill(self, d, name, protect):
        self.staged.append((sorted(str(p.relative_to(d)) for p in Path(d).rglob("*") if p.is_file()),
                            (Path(d) / "SKILL.md").read_text()))


class TestDeploy(ToolsMixin, unittest.TestCase):
    def deploy(self, d):
        bb = FakeStoreBB()
        with patch.object(tailoring, "blackbox_env", lambda: bb), \
                patch.object(tailoring, "spa_upstream_env", lambda: {"SPA_MODEL_NAME": "m"}):
            tailoring._deployed.update(digest=None)
            tailoring.deploy(d)
        return bb

    def test_seed_deploys_its_skill_md_alone(self):
        d = self.seed_dir()
        self.assertEqual(self.deploy(d).staged, [(["SKILL.md"], (d / "my_skill" / "SKILL.md").read_text())])

    def test_the_store_gets_only_skill_md_with_the_helper_sentence(self):
        # No tool of any kind: the proxy offers the model none; tools/ is not sent to the store.
        d = self.tools_dir(notes=NOTES)
        self.assertEqual(self.deploy(d).staged, [(["SKILL.md"], tailoring.deployed_skill_md(d))])

    def test_digest_covers_skill_md_and_the_helpers(self):
        d = self.tools_dir()
        before = tailoring.skill_digest(d)
        (d / "tools" / "helpers.py").write_text(HELPERS + "\n\ndef g(x):\n    return x\n")
        self.assertNotEqual(tailoring.skill_digest(d), before)   # the helper sentence changes

    def test_no_port_header(self):
        h = tailoring.context_headers("e", "t", SUPERVISOR)
        self.assertFalse(any("repl_port" in k for k in h))


class TestEpisodeSpec(unittest.TestCase):
    """What the adapter tells each episode's worker: the candidate's tools as REPL code."""

    def spec_for(self, repl_code: str):
        bb = load_bb_adapter()
        seen = {}

        def fake_run(argv, **kw):
            seen.update(json.loads(Path(argv[2]).read_text()))
            Path(argv[3]).write_text(json.dumps({"task_id": "a", "termination": "completed", "steps": [],
                                                 "disconnected": True}))
            return type("P", (), {"returncode": 0, "stderr": ""})()

        run = Path(tempfile.mkdtemp())
        with patch.object(bb, "_supervisor", lambda tid, root: SUPERVISOR), \
                patch.object(bb, "_client_prompt", lambda: Path("instructions.txt")), \
                patch.object(bb.subprocess, "run", fake_run), \
                patch.dict(os.environ, {"AW_INFRA_RETRIES": "0", "AW_REMOTE_REPL": "1"}), \
                patch.object(bb.tailoring, "start_env_server", lambda root, env: 9123), \
                patch.object(bb.tailoring, "stop_env_server", lambda port: True), \
                patch.object(bb.tailoring, "disconnect", lambda *a, **k: True):
            bb.Adapter()._episode(bb.Task(id="a", input={}), 0, run, run, repl_code=repl_code)
        return seen

    def test_the_spec_carries_the_repl_code(self):
        spec = self.spec_for("def f():\n    return 1\n")
        self.assertEqual(spec["repl_code"], "def f():\n    return 1\n")
        self.assertEqual(spec["remote_environment_url"], "http://127.0.0.1:9123")

    def test_without_tools_there_is_nothing_to_run(self):
        self.assertEqual(self.spec_for("")["repl_code"], "")

    def test_run_trials_passes_the_candidates_code_to_every_episode(self):
        bb_adapter = load_bb_adapter()
        cand = Path(tempfile.mkdtemp())
        task = bb_adapter.Task(id="t1", input={})
        codes = []
        with patch.object(bb_adapter.Adapter, "_check_seal", lambda self, ids: None), \
                patch.object(bb_adapter, "_wait_readable", lambda p, timeout_s=60.0: None), \
                patch.object(bb_adapter.bb_lints, "lint_candidate", lambda d: []), \
                patch.object(bb_adapter.tailoring, "deploy", lambda d: True), \
                patch.object(bb_adapter.tailoring, "repl_code", lambda d: "CODE"), \
                patch.object(bb_adapter.Adapter, "_episode",
                             lambda self, t, s, r, w, native_path=None, repl_code="": codes.append(repl_code)
                             or bb_adapter.Rollout(task_id=t.id)):
            bb_adapter.Adapter().run_trials([task], cand, n_trials=2, base_seed=0)
        self.assertEqual(codes, ["CODE", "CODE"])


class TestWorkerRunsTheTools(unittest.TestCase):
    def test_world_execute_right_after_the_world_exists_as_direct_does(self):
        src = (EX / "adapters" / "aw_bb_agent.py").read_text()
        world = src.index("with AppWorld(task_id=task_id")
        run = src.index('world.execute(spec["repl_code"])')
        init = src.index("agent.initialize(world)")
        self.assertLess(world, run)
        self.assertLess(run, init)  # before the stock agent starts: before step 1
        self.assertIn('record["setup_output"]', src)
        # and direct runs the same snippet the same way
        direct = (DIRECT / "adapters" / "aw_agent.py").read_text()
        self.assertIn("self.setup_output = world.execute(snippet)", direct)


class TestBlackboxReferenceNotes(unittest.TestCase):
    def test_built_from_the_direct_notes_with_the_blackbox_delivery(self):
        sys.path.insert(0, str(DIRECT / "scripts"))
        import make_reference
        notes = make_reference.blackbox_notes()
        self.assertIn("tools/helpers.py", notes)
        self.assertIn("tools/api_notes.json", notes)
        self.assertIn("it is not a model tool", notes)
        self.assertIn("bb_lints.py", notes)
        shared = "The episode ends when the code calls `apis.supervisor.complete_task(...)`"
        self.assertIn(shared, notes)
        self.assertIn(shared, make_reference.NOTES)


class TestCommittedSeed(unittest.TestCase):
    """seed_capability/ is committed, with the app list as a placeholder."""

    def test_files(self):
        files = sorted(p.relative_to(SEED).as_posix() for p in SEED.rglob("*") if p.is_file()
                       and "__pycache__" not in p.parts)
        self.assertEqual(files, ["my_skill/SKILL.md", "tools/api_notes.json", "tools/helpers.py"])

    def test_tools_are_the_direct_seeds_own(self):
        for name in ("helpers.py", "api_notes.json"):
            self.assertEqual((SEED / "tools" / name).read_text(),
                             (DIRECT / "seed_capability" / "tools" / name).read_text(), name)

    def test_skill_md_is_built_from_the_stock_prompt_with_the_app_list_left_out(self):
        text = (SEED / "my_skill" / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(text, make_seed_skill.build(STOCK))  # drift check: rebuild with --build
        self.assertEqual(text.count("{{ app_descriptions }}"), 1)
        self.assertEqual(text.count("{{ main_user."), 6)

    def test_render_fills_only_the_app_list(self):
        text = (SEED / "my_skill" / "SKILL.md").read_text(encoding="utf-8")
        self.assertEqual(make_seed_skill.render(text, APPS), make_seed_skill.build(STOCK, APPS))

    def test_seed_tools_load_nothing(self):
        self.assertEqual(tailoring.repl_code(SEED), "")

    def test_main_renders_the_committed_seed_into_a_project(self):
        out = Path(tempfile.mkdtemp()) / "seed_capability"
        apps_json = out.parent / "apps.json"
        with patch.object(make_seed_skill, "render_app_descriptions", lambda: APPS):
            make_seed_skill.main(["x", str(SEED), str(out), str(apps_json)])
        self.assertEqual((out / "my_skill" / "SKILL.md").read_text(), make_seed_skill.build(STOCK, APPS))
        for name in ("helpers.py", "api_notes.json"):
            self.assertEqual((out / "tools" / name).read_bytes(), (SEED / "tools" / name).read_bytes())
        self.assertEqual(json.loads(apps_json.read_text()), {"text": APPS})

    def test_build_writes_the_same_seed(self):
        out = Path(tempfile.mkdtemp()) / "seed"
        stock = Path(tempfile.mkdtemp()) / "instructions.txt"
        stock.write_text(STOCK)
        make_seed_skill.main(["x", "--build", str(stock), str(out)])
        for rel in ("my_skill/SKILL.md", "tools/helpers.py", "tools/api_notes.json"):
            self.assertEqual((out / rel).read_bytes(), (SEED / rel).read_bytes(), rel)


class TestSpecs(unittest.TestCase):
    def test_seed_folder_is_the_candidate_and_nothing_extra_protected(self):
        for name in ("capevolve.yaml", "capevolve.smoke.yaml", "capevolve.fix10.yaml"):
            text = (EX / name).read_text()
            self.assertIn("capability_path: seed_capability ", text, name)
            self.assertIn("protected_paths: [default]", text, name)
            self.assertNotIn("init_repl", text, name)


class TestCandidateLayout(LintDataMixin, unittest.TestCase):
    """capability_path: seed_capability, so a candidate is the folder that HOLDS my_skill/ and tools/."""

    def test_harness_files_next_to_the_two_folders_are_fine(self):
        d = self.seed_dir()
        (d / "INSTRUCTIONS.md").write_text("the harness's own file")
        self.assertEqual(bb_lints.lint_candidate(d), [])

    def test_run_trials_deploys_the_candidate_and_writes_native_sims_for_it(self):
        bb_adapter = load_bb_adapter()
        run = Path(tempfile.mkdtemp())
        (run / "splits.json").write_text(json.dumps({"train": ["t1"], "val": ["t1"], "test": []}))
        cand = run / "work" / "cand_0001"
        import shutil
        shutil.copytree(self.seed_dir(), cand)
        deployed, natives = [], []
        task = bb_adapter.Task(id="t1", input={})
        with patch.object(bb_adapter.Adapter, "_check_seal", lambda self, ids: None), \
                patch.object(bb_adapter, "_wait_readable", lambda p, timeout_s=60.0: None), \
                patch.object(bb_adapter.tailoring, "deploy", lambda d: deployed.append(Path(d))), \
                patch.object(bb_adapter.Adapter, "_episode",
                             lambda self, t, s, r, w, native_path=None, repl_code="": natives.append(native_path)
                             or bb_adapter.Rollout(task_id=t.id)):
            bb_adapter.Adapter().run_trials([task], cand, n_trials=1, base_seed=0)
        self.assertEqual(deployed, [cand.resolve()])
        self.assertEqual(natives[0].parent, run.resolve() / "native_sims" / "cand_0001" / "val")


if __name__ == "__main__":
    unittest.main()
