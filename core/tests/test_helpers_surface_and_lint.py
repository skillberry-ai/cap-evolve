"""v2: the helper config, the surface manifest, the lint, skills staging, the fault tag, the metric."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cap_evolve import helpers  # noqa: E402


@pytest.fixture(autouse=True)
def _no_env(monkeypatch):
    monkeypatch.delenv("CAPEVOLVE_HELPERS", raising=False)


def _cand(tmp_path, files: dict) -> Path:
    for rel, body in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    return tmp_path


# ---- config: v1 defaults ---------------------------------------------------------------------
def test_default_is_off_and_declares_nothing():
    cfg = helpers.resolve({})
    assert cfg["enabled"] is False and cfg["executable_dirs"] == []
    assert helpers.surface_problems(Path("/nonexistent"), cfg) == []


def test_enabled_by_spec_env_wins_and_typos_raise(monkeypatch):
    assert helpers.enabled({"helpers": {"enabled": True}})
    assert helpers.resolve({"helpers": {"enabled": True}})["executable_dirs"] == helpers.DEFAULT_EXECUTABLE_DIRS
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "0")
    assert not helpers.enabled({"helpers": {"enabled": True}})
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    assert helpers.enabled({})
    with pytest.raises(ValueError):
        helpers.resolve({"helpers": {"enabeld": True}})


def test_surface_manifest_dirs_come_from_the_spec():
    cfg = helpers.resolve({"helpers": {"enabled": True}, "surface": {"executable_dirs": ["skills/*/scripts"]}})
    assert cfg["executable_dirs"] == ["skills/*/scripts"]


# ---- surface manifest ------------------------------------------------------------------------
def test_executable_file_outside_declared_dirs_is_refused(tmp_path):
    cfg = helpers.resolve({"helpers": {"enabled": True}, "surface": {"executable_dirs": ["skills/*/scripts"]}})
    c = _cand(tmp_path, {"skills/a/scripts/f.py": "x=1\n", "skills/a/SKILL.md": "# a\n",
                         "prompt.md": "hi", "extra/evil.py": "x=2\n", "skills/a/run.sh": "echo\n"})
    probs = helpers.surface_problems(c, cfg)
    assert any("extra/evil.py" in p for p in probs) and any("skills/a/run.sh" in p for p in probs)
    assert not any("skills/a/scripts/f.py" in p for p in probs)
    assert [f.name for f in helpers.executable_files(c, cfg)] == ["f.py"]


def test_size_caps_and_symlinks(tmp_path):
    cfg = {**helpers.resolve({"helpers": {"enabled": True, "max_file_bytes": 10}}),
           "executable_dirs": ["skills/*/scripts"]}
    c = _cand(tmp_path, {"skills/a/scripts/big.py": "x = 1\n" * 10})
    os.symlink("/etc/passwd", c / "skills/a/scripts/link.py")
    probs = helpers.surface_problems(c, cfg)
    assert any("max_file_bytes" in p for p in probs) and any("symlink" in p for p in probs)


# ---- lint ------------------------------------------------------------------------------------
def _lint(src, **cfgkw):
    cfg = helpers.resolve({"helpers": {"enabled": True, **cfgkw}})
    return helpers.lint_source(src, "skills/a/scripts/f.py", cfg)


def test_a_parameterised_helper_passes():
    assert _lint("import re, json\n\ndef norm(cells, width=3):\n    return [re.sub(r'\\s+', ' ', c).strip() for c in cells][:width]\n") == []


@pytest.mark.parametrize("src,needle", [
    ("def f():\n    return '50768'\n", "task id literal"),
    ("def f(sid):\n    if sid == 'x1':\n        return 1\n", "task identity"),
    ("def f(task_id):\n    if task_id in ('a', 'b'):\n        return 1\n", "task identity"),
    ("def f(task):\n    return task['task_id'] != 'zz'\n", "task identity"),
    ("import socket\n", "network module"),
    ("import requests\n", "network module"),
    ("from urllib.request import urlopen\n", "network module"),
    ("import subprocess\n", "process"),
    ("import os\n\ndef f():\n    os.system('ls')\n", "os.system"),
    ("def f():\n    return open('/data/gold/1_answer.xlsx')\n", "evaluator/gold"),
    ("P = '/srv/splits/test.json'\n", "evaluator/gold"),
    ("def f():\n    return eval('1')\n", "eval()"),
])
def test_lint_blocks(src, needle):
    out = _lint(src, task_ids=["50768"])
    assert out and any(needle in x for x in out), out


def test_lint_blocks_copied_answer_literals_and_lookup_tables():
    assert any("copied from a trace" in x for x in _lint("X = 'Total: 1,234.50 USD'\n", forbidden_literals=["Total: 1,234.50 USD"]))
    table = "T = {" + ", ".join(f"'k{i}': 'v{i}'" for i in range(25)) + "}\n"
    assert any("lookup table" in x for x in _lint(table))
    assert _lint("T = {'a': 'b', 'c': 'd'}\n") == []


def test_lint_only_blames_new_findings_on_a_changed_file(tmp_path):
    cfg = helpers.resolve({"helpers": {"enabled": True}})
    parent = _cand(tmp_path / "p", {"tools/tools.py": "import socket\n\ndef a():\n    return 1\n"})
    cand = _cand(tmp_path / "c", {"tools/tools.py": "import socket\n\ndef a():\n    return 2\n"})
    assert helpers.lint_candidate(cand, cfg, parent)["ok"]
    cand2 = _cand(tmp_path / "c2", {"tools/tools.py": "import socket\nimport subprocess\n"})
    r = helpers.lint_candidate(cand2, cfg, parent)
    assert not r["ok"] and all("subprocess" in f for f in r["findings"])


def test_lint_ids_file(tmp_path):
    ids = tmp_path / "ids.txt"
    ids.write_text("abc-123\n", encoding="utf-8")
    assert _lint("X = 'abc-123'\n", ids_file=str(ids))


# ---- carrying skills into the kernel as text ---------------------------------------------------------
def _exec(src, ns=None):
    import contextlib, io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(compile(src, "<boot>", "exec"), ns if ns is not None else {})
    return buf.getvalue()


def test_bootstrap_defines_modules_under_skills_and_reports_ready(tmp_path):
    _cand(tmp_path, {"spreadsheet-helpers/scripts/norm.py": "def f(x):\n    return x + 1\n",
                     "spreadsheet-helpers/SKILL.md": "x"})
    src = helpers.kernel_bootstrap(tmp_path)
    saved = {k: sys.modules.pop(k) for k in list(sys.modules) if k == "skills" or k.startswith("skills.")}
    try:
        out = _exec(src)
        assert helpers.bootstrap_ok(out)
        from skills.spreadsheet_helpers import norm  # noqa: PLC0415
        assert norm.f(1) == 2
    finally:
        for k in [k for k in sys.modules if k == "skills" or k.startswith("skills.")]:
            sys.modules.pop(k)
        sys.modules.update(saved)


def test_bootstrap_carries_only_this_candidates_text_and_crashes_are_attributable(tmp_path):
    a = _cand(tmp_path / "a", {"s/scripts/one.py": "A = 1\n"})
    b = _cand(tmp_path / "b", {"s/scripts/two.py": "def boom():\n    raise ValueError('bad cell')\n"})
    sa, sb = helpers.kernel_bootstrap(a), helpers.kernel_bootstrap(b)
    assert "one.py" in sa and "two.py" not in sa and "one.py" not in sb
    assert str(tmp_path) not in sa            # no host paths reach the kernel
    import traceback
    ns = {}
    _exec(sb, ns)
    with pytest.raises(RuntimeError) as e:
        sys.modules["skills.s.two"].boom()
    tb = "".join(traceback.format_exception(e.type, e.value, e.tb))
    assert helpers.helper_crash_in([tb], helpers.KERNEL_ROOT) == \
        "CANDIDATE_HELPER_FAULT: skills.s.two.boom: ValueError: bad cell"
    for k in [k for k in sys.modules if k == "skills" or k.startswith("skills.")]:
        sys.modules.pop(k)


def test_bootstrap_failure_is_not_ready_and_oversize_is_refused(tmp_path):
    c = _cand(tmp_path, {"s/scripts/bad.py": "import not_a_real_module_xyz\n"})
    with pytest.raises(RuntimeError, match=helpers.HELPER_FAULT_MARKER):   # import-time crash carries the marker
        _exec(helpers.kernel_bootstrap(c))
    assert not helpers.bootstrap_ok("Traceback ...")
    for k in [k for k in sys.modules if k == "skills" or k.startswith("skills.")]:
        sys.modules.pop(k)
    with pytest.raises(ValueError, match="bytes"):
        helpers.kernel_bootstrap(c, max_bytes=5)


def test_skills_tree_problems_refuse_symlinks_gold_names_and_binaries(tmp_path):
    src = tmp_path / "skills"
    _cand(src, {"a/scripts/f.py": "x=1\n"})
    assert helpers.skills_tree_problems(src) == []
    os.symlink("/etc/hostname", src / "a/scripts/l.py")
    assert any("symlink" in p for p in helpers.skills_tree_problems(src))
    (src / "a/scripts/l.py").unlink()
    (src / "a/scripts/1_x_answer.py").write_text("y=1\n")
    assert any("gold-named" in p for p in helpers.skills_tree_problems(src))
    (src / "a/scripts/1_x_answer.py").unlink()
    (src / "a/blob.xlsx").write_bytes(b"PK")
    assert any("not allowed" in p for p in helpers.skills_tree_problems(src))


def test_the_gate_applies_the_targets_skills_tree_check(tmp_path):
    """The target refuses a whole skills tree (every rollout) on any ``skills_tree_problems`` finding, so the
    gate's surface check must refuse it first, for free (#895 GLM HC-2 smoke: a helper named answers.py
    passed the gate, then all 36 rung-1 rollouts were refused as "gold-named file")."""
    cfg = helpers.resolve({"helpers": {"enabled": True}, "surface": {"executable_dirs": ["skills/*/scripts"]}})
    assert cfg["skills_loader"] == "kernel"
    c = _cand(tmp_path, {"skills/a/scripts/answers.py": "def f():\n    return 1\n", "skills/a/SKILL.md": "# a\n",
                         "skills/a/notes.csv": "x\n"})
    probs = helpers.surface_problems(c, cfg)
    assert any("skills/a/scripts/answers.py: gold-named file" in p for p in probs), probs
    assert any("skills/a/notes.csv" in p and "not allowed" in p for p in probs), probs
    assert all("refuses the whole skills/ tree" in p for p in probs if p.startswith("skills/a/"))
    # a target that runs the scripts as files does not stage the tree: none of these apply
    assert not any("gold-named" in p or "not allowed" in p
                   for p in helpers.surface_problems(c, {**cfg, "skills_loader": "file"}))
    # a clean tree adds nothing
    ok = _cand(tmp_path / "ok", {"skills/a/scripts/fmt.py": "x = 1\n", "skills/a/SKILL.md": "# a\n"})
    assert helpers.surface_problems(ok, cfg) == []


def test_token_is_a_plain_replace_and_prompt_text_comes_from_skill_md(tmp_path):
    assert helpers.render_skills_root("see {skills_root}.a and {literal}", "skills") == "see skills.a and {literal}"
    _cand(tmp_path, {"my-skill/SKILL.md": "---\nname: my-skill\ndescription: does a thing\n---\nCall norm.f(x).\n"})
    t = helpers.skills_prompt(tmp_path)
    assert "my-skill" in t and "does a thing" in t and "Call norm.f(x)." in t and "---" not in t
    assert "skills.my_skill" in t


# ---- a helper's own crash is the candidate's fault ---------------------------------------------
def test_candidate_helper_types_every_failure():
    @helpers.candidate_helper
    def boom(x):
        raise KeyError(x)

    with pytest.raises(helpers.CandidateHelperError) as e:
        boom("k")
    assert helpers.fault_in_text(str(e.value)).startswith(helpers.HELPER_FAULT_MARKER)
    msgs = [{"role": "assistant", "content": "ok"}, {"role": "tool", "content": f"Error: {e.value}"}]
    assert "boom" in helpers.fault_in_messages(msgs)
    assert helpers.fault_in_messages([{"role": "tool", "content": "Error: no such reservation"}]) is None
    assert helpers.candidate_fault_metadata("x")["error_kind"] == "candidate"


def test_helper_crash_in_executor_output_needs_a_frame_under_the_skills_root():
    tb = ('Traceback (most recent call last):\n  File "<stdin>", line 3, in <module>\n'
          '  File "/mnt/skills/a/scripts/f.py", line 9, in norm\nZeroDivisionError: division by zero\n')
    assert helpers.helper_crash_in(["fine", tb], "/mnt/skills") == "ZeroDivisionError: division by zero"
    own = 'Traceback (most recent call last):\n  File "<stdin>", line 3, in <module>\nKeyError: 1\n'
    assert helpers.helper_crash_in([own], "/mnt/skills") is None


# ---- determinism metric ----------------------------------------------------------------------
def test_reward_variance():
    r = helpers.reward_variance({"t1": [1, 1, 1], "t2": [0, 1, 1], "t3": [1], "t4": [0, None, 0]})
    assert r["n_tasks"] == 3 and r["per_task"]["t1"] == 0 and r["per_task"]["t4"] == 0
    assert r["per_task"]["t2"] == pytest.approx(1 / 3)
    assert r["flaky_fraction"] == pytest.approx(1 / 3)
    seed = helpers.reward_variance({"t1": [0, 1, 1], "t2": [0, 1, 1]})
    d = helpers.variance_against(r, seed)
    assert d["n_shared"] == 2 and d["per_task_delta"]["t1"] < 0 and d["per_task_delta"]["t2"] == 0
    assert helpers.reward_variance({})["mean_variance"] is None


# ---- skill-package: risky code is an error under helpers, nested skills/ is validated ----------------------------
def _sp():
    import importlib.util
    p = Path(__file__).resolve().parents[2] / "skills/capabilities/skill-package/scripts/abstract.py"
    spec = importlib.util.spec_from_file_location("_sp_abstract", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_skill_package_makes_risky_imports_errors_only_when_helpers_are_on(tmp_path, monkeypatch):
    sp = _sp()
    _cand(tmp_path, {"skills/a/SKILL.md": "---\nname: a\ndescription: does a thing when asked to do it\n---\n# a\n",
                     "skills/a/scripts/f.py": "import socket\n\ndef f():\n    return socket.gethostname()\n"})
    off = sp.validate(tmp_path)                      # skills/ is a multi-skill root with helpers off too
    assert not off.get("empty") and off["ok"]        # ...but socket is only a warning there
    assert not any("socket" in p for p in off["problems"])
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    on = sp.validate(tmp_path)
    assert not on["ok"] and any("socket" in p for p in on["problems"])
    (tmp_path / "skills/a/scripts/f.py").write_text("def f():\n    return 1\n")
    assert not any("socket" in p for p in sp.validate(tmp_path)["problems"])


# ---- review round: the marker, the lint bypasses, per-message counts, name collisions, harvest ----
def _reset_skills_modules():
    for k in [k for k in sys.modules if k == "skills" or k.startswith("skills.")]:
        sys.modules.pop(k)


def test_wrapped_helpers_reraise_with_the_marker_and_nested_calls_are_not_double_wrapped(tmp_path):
    c = _cand(tmp_path, {"s/scripts/m.py": (
        "def inner(x):\n    return 1 / x\n\ndef outer(x):\n    return inner(x)\n\n"
        "class K:\n    def go(self, x):\n        return inner(x)\n")})
    try:
        _exec(helpers.kernel_bootstrap(c))
        m = sys.modules["skills.s.m"]
        assert m.outer(2) == 0.5
        for call in (lambda: m.outer(0), lambda: m.K().go(0)):
            with pytest.raises(RuntimeError) as e:
                call()
            msg = str(e.value)
            assert msg.startswith(helpers.HELPER_FAULT_MARKER) and msg.count(helpers.HELPER_FAULT_MARKER) == 1
            assert "ZeroDivisionError" in msg
    finally:
        _reset_skills_modules()


#: What the Jupyter server hands the vendored ``exec_code``: IPython's structured traceback joined by 4 newlines.
#: IPython >= 8.16 prints frames as ``File path:line, in fn(args)`` (no quotes), which no CPython-format regex sees.
_IPY_8_16 = [
    "\x1b[0;31m---------------------------------------------------------------------------\x1b[0m",
    "\x1b[0;31mHelperFault\x1b[0m                              Traceback (most recent call last)",
    "Cell \x1b[0;32mIn[3], line 1\x1b[0m\n\x1b[0;32m----> 1\x1b[0m skills\x1b[38;5;241m.\x1b[39ma\x1b[38;5;241m.\x1b[39mb\x1b[38;5;241m.\x1b[39mf(\x1b[38;5;241m0\x1b[39m)\n",
    "File \x1b[0;32mcapevolve_skills/a/b.py:2\x1b[0m, in \x1b[0;36mf\x1b[0;34m(x)\x1b[0m\n\x1b[1;32m      1\x1b[0m def f(x):\n----> 2\x1b[0m     return 1/x\n",
    "\x1b[0;31mHelperFault\x1b[0m: CANDIDATE_HELPER_FAULT: skills.a.b.f: ZeroDivisionError: division by zero",
]


def _vendored_exec_code(monkeypatch):
    """The vendored inference/code_exec.py (its HTTP client import is stubbed: not needed to format output)."""
    import importlib.util, types
    stub = types.ModuleType("jupyter_kernel_cli")
    stub.ClientJupyterKernel = object
    monkeypatch.setitem(sys.modules, "jupyter_kernel_cli", stub)
    path = Path(__file__).resolve().parents[2] / "benchmarks/spreadsheetbench/harness/inference/code_exec.py"
    spec = importlib.util.spec_from_file_location("_vendored_code_exec", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.exec_code


class _Client:
    def __init__(self, out):
        self.out = out

    def execute(self, code):
        return self.out


def test_ipython_structured_traceback_through_exec_code_is_still_attributed(monkeypatch):
    exec_code = _vendored_exec_code(monkeypatch)
    out = exec_code(_Client("\n\n\n\n".join(_IPY_8_16)), "skills.a.b.f(0)")
    assert "capevolve_skills/a/b.py" not in out                       # exec_code dropped the frame chunk
    assert helpers.helper_crash_in([out], helpers.KERNEL_ROOT) == \
        "CANDIDATE_HELPER_FAULT: skills.a.b.f: ZeroDivisionError: division by zero"
    foreign = "\n\n\n\n".join(_IPY_8_16[:3] + ["\x1b[0;31mKeyError\x1b[0m: 'x'"])
    assert helpers.helper_crash_in([exec_code(_Client(foreign), "x")], helpers.KERNEL_ROOT) is None


def test_real_ipython_shell_traceback_from_the_real_bootstrap_is_attributed(monkeypatch, tmp_path):
    ipy = pytest.importorskip("IPython.core.interactiveshell")
    exec_code = _vendored_exec_code(monkeypatch)
    c = _cand(tmp_path, {"a/scripts/b.py": "def f(x):\n    return 1 / x\n"})
    sh = ipy.InteractiveShell.instance()
    got = []
    sh.showtraceback = lambda *a, **k: got.append(sh.InteractiveTB.structured_traceback(*sys.exc_info()))
    try:
        sh.run_cell(helpers.kernel_bootstrap(c))
        sh.run_cell("from skills.a import b\nb.f(0)")
    finally:
        _reset_skills_modules()
        ipy.InteractiveShell.clear_instance()
    assert got, "the helper should have raised"
    out = exec_code(_Client("\n\n\n\n".join(got[0])), "skills.a.b.f(0)")
    assert helpers.helper_crash_in([out], helpers.KERNEL_ROOT).startswith(helpers.HELPER_FAULT_MARKER)


@pytest.mark.parametrize("src,needle", [
    ("import importlib\nm = importlib.import_module('soc' + 'ket')\n", "importlib"),
    ("from importlib import import_module\nimport_module('x')\n", "importlib"),
    ("def f(i):\n    return i.import_module('x')\n", "import_module"),
    ("m = __import__('soc' + 'ket')\n", "__import__"),
    ("m = __import__('json')\n", "__import__"),
    ("import builtins\nx = getattr(builtins, 'ev' + 'al')\n", "builtins"),
    ("g = getattr(__builtins__, 'open')\n", "__builtins__"),
    ("import os as o\no.system('x')\n", "os.system"),
    ("import os\np = os\np.popen('x')\n", "os.popen"),
    ("import posix\nposix.system('x')\n", "os.system"),
    ("import os\ngetattr(os, 'sys' + 'tem')('x')\n", "getattr(os"),
    ("from os import *\n", "import *"),
])
def test_lint_flags_the_dynamic_import_and_os_alias_bypasses(src, needle):
    findings = helpers.lint_source(src, "f.py", helpers.resolve({"helpers": {"enabled": True}}))
    assert any(needle in f for f in findings), findings


def test_lint_still_accepts_plain_helpers():
    ok = "import os, json\n\ndef f(p):\n    return os.path.join(p, 'x'), json.dumps({})\n"
    assert helpers.lint_source(ok, "f.py", helpers.resolve({"helpers": {"enabled": True}})) == []


def test_lint_counts_findings_per_message_not_by_set_membership(tmp_path):
    cfg = helpers.resolve({"helpers": {"enabled": True}})
    one = "import subprocess\n"
    parent = _cand(tmp_path / "p", {"skills/s/scripts/f.py": one})
    same = _cand(tmp_path / "c1", {"skills/s/scripts/f.py": one + "x = 1\n"})
    assert helpers.lint_candidate(same, cfg, parent)["ok"]
    twice = _cand(tmp_path / "c2", {"skills/s/scripts/f.py": one + "import subprocess\n"})
    r = helpers.lint_candidate(twice, cfg, parent)
    assert not r["ok"] and len(r["findings"]) == 1


def test_skill_and_script_names_that_import_alike_are_refused(tmp_path):
    src = tmp_path / "skills"
    _cand(src, {"a-b/scripts/f.py": "x=1\n", "a_b/scripts/f.py": "x=2\n"})
    assert any("imports as skills.a_b.f" in p for p in helpers.skills_tree_problems(src))
    with pytest.raises(ValueError, match="both import as"):
        helpers.kernel_bootstrap(src)
    src2 = tmp_path / "skills2"
    _cand(src2, {"s/scripts/x-y.py": "x=1\n", "s/scripts/x_y.py": "x=2\n"})
    assert any("imports as skills.s.x_y" in p for p in helpers.skills_tree_problems(src2))


def test_bootstrap_records_json_inputs_of_top_level_calls_that_returned(tmp_path):
    c = _cand(tmp_path, {"s/scripts/m.py": (
        "def inner(x):\n    return x\n\ndef outer(x, k=1):\n    return inner(x)\n\n"
        "def paths(p):\n    return p\n\ndef bad(x):\n    raise ValueError(x)\n")})
    try:
        _exec(helpers.kernel_bootstrap(c))
        m = sys.modules["skills.s.m"]
        m.outer([1, 2], k=3)
        m.paths("/mnt/data/in.xlsx")                   # a path is not a portable input: not recorded
        m.paths(object())                              # not JSON: not recorded
        with pytest.raises(RuntimeError):
            m.bad(1)                                   # raised: not recorded
        out = _exec(helpers.harvest_snippet())
    finally:
        _reset_skills_modules()
    calls = helpers.parse_harvest(out)
    assert calls == [{"helper": "skills/s/scripts/m.py", "call": "outer", "args": [[1, 2]], "kwargs": {"k": 3}}]
    assert helpers.parse_harvest("no tag here") == []


def test_parse_harvest_drops_protected_strings():
    import json as _j
    row = {"helper": "skills/s/scripts/m.py", "call": "f", "args_kwargs": _j.dumps([["golden_answer"], {}])}
    assert helpers.parse_harvest(f"{helpers.CALLS_TAG} {_j.dumps([row])}") == []


def test_fixture_splits_are_feedback_only():
    assert helpers.resolve({})["fixture_splits"] == ["feedback", "train"]
    for bad in ("confirm", "test", "val", "pool"):
        with pytest.raises(ValueError, match="held-out"):
            helpers.resolve({"helpers": {"fixture_splits": ["feedback", bad]}})


def _round_module(monkeypatch):
    import importlib.util
    scripts = Path(__file__).resolve().parents[2] / "skills/algorithms/agent-optimize/scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("_round_under_test", scripts / "round.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_a_helpers_config_error_propagates_out_of_the_round_pregate_not_fail_open(monkeypatch, tmp_path):
    import types
    rnd = _round_module(monkeypatch)
    rd = types.SimpleNamespace(candidate_dir=lambda t: tmp_path / t, rollouts=tmp_path / "rollouts", root=tmp_path,
                               log_event=lambda *a, **k: None)
    cand = tmp_path / "cand"
    cand.mkdir()
    (tmp_path / "seed").mkdir()     # a real run always has its seed snapshot; the helper gate requires it
    monkeypatch.setattr(rnd, "spec_for_run", lambda run_dir, project: {"helpers": {"enabled": True, "bogus": 1}})
    with pytest.raises(ValueError, match="unknown helpers key"):
        rnd.pregate_failure(rd, tmp_path, "parent", cand, None)
    # a genuine pre-gate crash is still fail-open (warning only)
    monkeypatch.setattr(rnd, "spec_for_run", lambda run_dir, project: {"helpers": {"enabled": True}})
    monkeypatch.setattr(rnd.pregate, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert rnd.pregate_failure(rd, tmp_path, "parent", cand, None) is None


def test_round_pregate_hands_the_smoke_only_feedback_rollouts_of_the_parent(monkeypatch, tmp_path):
    import types
    rnd = _round_module(monkeypatch)
    for sp in ("feedback", "confirm", "test"):
        (tmp_path / "rollouts" / sp).mkdir(parents=True)
        (tmp_path / "rollouts" / sp / "t__parent__t0.json").write_text("{}")
    rd = types.SimpleNamespace(candidate_dir=lambda t: tmp_path / t, rollouts=tmp_path / "rollouts", root=tmp_path,
                               log_event=lambda *a, **k: None)
    seen = {}
    (tmp_path / "seed").mkdir()     # a real run always has its seed snapshot; the helper gate requires it
    monkeypatch.setattr(rnd, "spec_for_run", lambda run_dir, project: {"helpers": {"enabled": True}})
    monkeypatch.setattr(rnd.pregate, "run", lambda *a, **k: (seen.update(k), {"ok": True, "warnings": []})[1])
    cand = tmp_path / "cand"
    cand.mkdir()
    assert rnd.pregate_failure(rd, tmp_path, "parent", cand, None) is None
    assert [p.parent.name for p in seen["traces"]] == ["feedback"]


def test_a_missing_seed_snapshot_stops_the_round_pregate_not_fail_open(monkeypatch, tmp_path):
    import types
    from cap_evolve import helper_gate
    rnd = _round_module(monkeypatch)
    rd = types.SimpleNamespace(candidate_dir=lambda t: tmp_path / t, rollouts=tmp_path / "rollouts", root=tmp_path,
                               log_event=lambda *a, **k: None)
    cand = tmp_path / "cand"
    cand.mkdir()
    monkeypatch.setattr(rnd, "spec_for_run", lambda run_dir, project: {"helpers": {"enabled": True}})
    with pytest.raises(helper_gate.GateConfigError, match="seed"):
        rnd.pregate_failure(rd, tmp_path, "parent", cand, None)


# ---- #912: ordinary spreadsheet code is not a task-id branch or a gold path ---------------------------
# Each case is a line the lint refused in exp895 (issue #895), shortened. None of them reads gold or
# branches on which task is running, so a helper that contains it must pass.
_EXCEL_NAMES = ", ".join(f"'F{i}'" for i in range(30))


@pytest.mark.parametrize("src", [
    # a parameter named after the task template's own field, in an error message (exp895: 13 candidates)
    "def check(answer_position):\n    if not answer_position:\n"
    "        raise ValueError('answer_position must be a non-empty string')\n",
    "def check(p):\n    raise ValueError(f'answer_position {p!r} is empty')\n",
    "def check(p):\n    raise ValueError('answer_position %r is empty' % (p,))\n",
    "def check(p):\n    raise ValueError('answer_position {} is empty'.format(p))\n",
    "def check(p):\n    raise ValueError('answer_position ' + str(p) + ' is empty')\n",
    "__all__ = ['parse_answer_position']\n\ndef parse_answer_position(s):\n    return s\n",
    "import logging\nlog = logging.getLogger(__name__)\n\ndef f(p):\n    log.warning('answer_position %r is empty', p)\n",
    # a docstring that mentions the words, with a slash (main's lint refused it as a path)
    '"""Fill the range named by task/answer_position; see the split/notes section."""\n',
    # a sheet name or row index compared with None (exp895: 7 candidates)
    "def ws_of(wb, sheet_name=None):\n    if sheet_name is None:\n        return wb.active\n    return wb[sheet_name]\n",
    "def ws_of(wb, sheet_name):\n    return wb[sheet_name] if sheet_name is not None else wb.active\n",
    "def r(row_idx=None):\n    if row_idx is None:\n        return 1\n    return row_idx\n",
    # a set of Excel function names: membership only, it stores no answers (exp895: 1 candidate)
    "_NEW = {" + _EXCEL_NAMES + "}\n\ndef needs_prefix(fn):\n    return fn.upper() in _NEW\n",
    # the helpers the shared #895 guidance itself suggests
    "def write_range(ws, answer_position, values):\n"
    "    if ':' not in answer_position:\n        raise ValueError('answer_position must be a range like A1:B2')\n",
    "def verify_output(path, answer_position):\n    import openpyxl\n"
    "    wb = openpyxl.load_workbook(path)\n    return wb, answer_position\n",
])
def test_ordinary_spreadsheet_code_passes_the_lint(src):
    assert _lint(src) == []


@pytest.mark.parametrize("src,needle", [
    # gold paths are still refused, however the path is built
    ("def f(root):\n    return open(root + '/gold/x.xlsx')\n", "evaluator/gold"),
    ("import os\n\ndef f(root, n):\n    return open(os.path.join(root, 'gold', n))\n", "evaluator/gold"),
    ("from pathlib import Path\n\ndef f(r):\n    return (Path(r) / 'answers' / 'a.xlsx').read_bytes()\n",
     "evaluator/gold"),
    ("def f():\n    return open('answer.json').read()\n", "evaluator/gold"),
    ("G = 'data/1_10452_golden.xlsx'\n", "evaluator/gold"),
    ("def f(p):\n    return open(f'{p}/splits/test.json')\n", "evaluator/gold"),
    # ... and when the protected word is held in a variable and joined later (review of #1008)
    ("D = 'gold'\n\ndef f(r, n):\n    return open(r + '/' + D + '/' + n)\n", "evaluator/gold"),
    ("D = 'golden'\n\ndef f(n):\n    return open(D + n)\n", "evaluator/gold"),
    ("G = ['ground_truth', 'x']\n\ndef f(r):\n    import os\n    return open(os.path.join(r, *G))\n",
     "evaluator/gold"),
    ("def f(r):\n    d = 'splits'\n    return open(r + '/' + d + '/x')\n", "evaluator/gold"),
    # prose exemptions do not cover a path: a file call inside a raise, a user function named like a logger
    # method, an __all__ entry the module does not define
    ("def f():\n    raise ValueError(open('/d/gold/x').read())\n", "evaluator/gold"),
    ("def error(p):\n    return open(p)\n\ndef f():\n    return error('/data/gold/x.xlsx')\n", "evaluator/gold"),
    ("__all__ = ['golden']\n", "evaluator/gold"),
    # ... nor a path handed to another call inside a message (review round 2 of #1008)
    ("def rd(p):\n    return open(p).read()\n\ndef f():\n    print(rd('/d/gold/x.json'))\n", "evaluator/gold"),
    ("def rd(p):\n    return open(p).read()\n\ndef f():\n    raise ValueError(rd('gold'))\n", "evaluator/gold"),
    ("import shutil\n\ndef f():\n    raise RuntimeError(shutil.move('splits', 'x'))\n", "evaluator/gold"),
    ("import os\n\ndef f(log):\n    log.info(os.path.abspath('gold'))\n", "evaluator/gold"),
    ("def f(r):\n    print(r, d := 'gold')\n    return open(r + '/' + d)\n", "evaluator/gold"),
    # task-identity branches are still refused when they compare with a real literal
    ("def f(task_id):\n    if task_id == '10452':\n        return 42\n", "task identity"),
    ("def f(sample_id):\n    return 1 if sample_id in ('a1', 'b2') else 0\n", "task identity"),
    # answer tables are still refused: a dict and a list store values
    ("T = {" + ", ".join(f"'k{i}': 'v{i}'" for i in range(25)) + "}\n", "lookup table"),
    ("T = [" + _EXCEL_NAMES + "]\n", "lookup table"),
])
def test_real_findings_are_still_refused(src, needle):
    out = _lint(src)
    assert out and any(needle in x for x in out), out
