"""v2 helpers, SpreadsheetBench half: the candidate's skills/ reaches the executor as text in the rollout's own kernel
(nothing mounted, only the current candidate), and a crash in the candidate's own helper is tagged
error_kind=candidate. No docker, no model: the executor and litellm are faked."""
from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ADAPTER_DIR = REPO / "benchmarks" / "spreadsheetbench" / "template"


@pytest.fixture()
def mod(monkeypatch):
    monkeypatch.delenv("CAPEVOLVE_HELPERS", raising=False)
    for p in (REPO / "core", ADAPTER_DIR, REPO / "benchmarks" / "_shared"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("_sb_adapter_helpers", ADAPTER_DIR / "adapter.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _cand(root: Path, name: str, scripts: dict, prompt="solve with {skills_root}") -> Path:
    c = root / name
    (c / "skills/fmt/scripts").mkdir(parents=True)
    (c / "skills/fmt/SKILL.md").write_text("---\nname: fmt\ndescription: formats cells\n---\nCall norm.f.\n",
                                           encoding="utf-8")
    for k, v in scripts.items():
        (c / "skills/fmt/scripts" / k).write_text(v, encoding="utf-8")
    (c / "prompt.md").write_text(prompt, encoding="utf-8")
    return c


def test_no_mount_no_vendor_change_no_new_sandbox_machinery(mod):
    src = (REPO / "third_party/spreadsheetbench/code_exec_docker/jupyter.py").read_text()
    assert "/mnt/skills" not in src and "skills_path" not in src
    assert not hasattr(mod, "_get_skills_sandbox")


def test_skills_root_token_is_resolved_only_when_helpers_are_on(mod, monkeypatch, tmp_path):
    c = _cand(tmp_path, "c", {})
    (c / "task_template.md").write_text(
        "{instruction} {spreadsheet_path} {spreadsheet_content} {instruction_type} {answer_position} "
        "{output_path} see {skills_root}\n", encoding="utf-8")
    assert "unknown placeholder" in mod._task_template_error(c)       # v1 behaviour: not a known field
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    assert mod._task_template_error(c) is None
    assert "see skills" in mod._read_task_template(c)


class _Box:
    def client_for(self, conv):
        return object()

    def release(self, conv):
        pass


def _run(mod, monkeypatch, tmp_path, cand, exec_outputs, sent=None, turns=1):
    view = tmp_path / "view"
    (view / "spreadsheet/t1").mkdir(parents=True, exist_ok=True)
    (view / "spreadsheet/t1/1_t1_input.xlsx").write_bytes(b"PK")
    entry = {"id": "t1", "instruction": "i", "answer_position": "A1", "instruction_type": "Cell-Level Manipulation"}
    monkeypatch.setattr(mod, "_data_dir", lambda: view)
    monkeypatch.setattr(mod, "_entries_by_id", lambda: {"t1": entry})

    def fake_exec(client, code):
        if sent is not None:
            sent.append(code)
        return exec_outputs.pop(0)
    monkeypatch.setattr(mod._Vendor, "get", classmethod(lambda cls: {"extract_code": None, "exec_code": fake_exec}))
    monkeypatch.setattr(mod, "_extract_python", lambda vendor, text: "run()")
    monkeypatch.setattr(mod, "_workbook_context", lambda *a, **k: "preview")
    monkeypatch.setattr(mod, "_resolve_case_file", lambda d, i, sid, kind: d / "1_t1_input.xlsx")
    monkeypatch.setattr(mod, "_get_sandbox", lambda: _Box())
    monkeypatch.setattr(mod, "MAX_TURNS", turns)
    seen = {}
    resp = types.SimpleNamespace(
        choices=[types.SimpleNamespace(message=types.SimpleNamespace(content="```python\nrun()\n```"))],
        usage=None, _hidden_params={})
    fake = types.ModuleType("litellm")
    fake.completion = lambda **k: (seen.update(messages=k["messages"]), resp)[1]
    monkeypatch.setitem(sys.modules, "litellm", fake)
    monkeypatch.setattr(mod.model_config, "MODEL", "m", raising=False)
    monkeypatch.setattr(mod.model_config, "llm_kwargs", lambda: {}, raising=False)
    r = mod.Adapter().run_target(types.SimpleNamespace(id="t1"), cand)
    r.seen = seen
    return r


READY = "CAPEVOLVE_HELPERS_READY 1\n"
TB = ('Traceback (most recent call last):\n  File "<stdin>", line 2, in <module>\n'
      '  File "capevolve_skills/fmt/norm.py", line 4, in norm\nValueError: bad cell\n')


def test_only_the_current_candidates_text_is_sent_once_and_skill_md_reaches_the_prompt(mod, monkeypatch, tmp_path):
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    _cand(tmp_path, "other", {"secret_other.py": "OTHER = 1\n"})
    cur = _cand(tmp_path, "cur", {"norm.py": "CUR = 1\n"})
    sent = []
    r = _run(mod, monkeypatch, tmp_path, cur, [READY, "ok"], sent)
    assert "CUR = 1" in sent[0] and "OTHER" not in sent[0] and "CAPEVOLVE_HELPERS_READY" in sent[0]
    assert len(sent) == 2                                      # bootstrap once, then the model's code
    system = r.seen["messages"][0]["content"]
    assert "solve with skills" in system and "Call norm.f." in system and "formats cells" in system


def test_a_helper_crash_with_no_output_is_a_candidate_fault(mod, monkeypatch, tmp_path):
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    r = _run(mod, monkeypatch, tmp_path, _cand(tmp_path, "c", {"norm.py": "x=1\n"}), [READY, TB])
    assert "candidate helper crashed: ValueError: bad cell" in r.error
    assert r.metadata["error_kind"] == "candidate"


def test_a_bootstrap_failure_is_a_candidate_fault_before_any_llm_call(mod, monkeypatch, tmp_path):
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    r = _run(mod, monkeypatch, tmp_path, _cand(tmp_path, "c", {"norm.py": "x=1\n"}), [
        'Traceback (most recent call last):\n  File "capevolve_skills/fmt/norm.py", line 1\nSyntaxError: x\n'])
    assert "failed to load" in r.error and r.metadata["error_kind"] == "candidate"
    assert r.seen == {}


def test_an_infra_style_traceback_outside_the_helper_is_not_tagged(mod, monkeypatch, tmp_path):
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    own = 'Traceback (most recent call last):\n  File "<stdin>", line 2, in <module>\nKeyError: 1\n'
    r = _run(mod, monkeypatch, tmp_path, _cand(tmp_path, "c", {"norm.py": "x=1\n"}), [READY, own])
    assert (r.metadata or {}).get("error_kind") != "candidate"


def test_helpers_off_sends_nothing_and_never_tags(mod, monkeypatch, tmp_path):
    sent = []
    r = _run(mod, monkeypatch, tmp_path, _cand(tmp_path, "c", {"norm.py": "x=1\n"}), [TB], sent)
    assert len(sent) == 1 and "capevolve" not in sent[0].lower()
    assert (r.metadata or {}).get("error_kind") != "candidate"


def test_an_unloadable_skills_tree_is_refused_before_any_container(mod, monkeypatch, tmp_path):
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    c = _cand(tmp_path, "c", {"norm.py": "x=1\n"})
    os.symlink("/etc/hostname", c / "skills/fmt/scripts/l.py")
    r = _run(mod, monkeypatch, tmp_path, c, [])
    assert "skills/ tree refused" in r.error and r.metadata["error_kind"] == "candidate"


# ---- review round: attribution through the real exec_code, ordering, bootstrap infra vs candidate ----
MARKED = "CANDIDATE_HELPER_FAULT: skills.fmt.norm.f: ZeroDivisionError: division by zero"
IPY_CHUNKS = [
    "\x1b[0;31m---------------------------------------------------------------------------\x1b[0m",
    "\x1b[0;31mHelperFault\x1b[0m                              Traceback (most recent call last)",
    "Cell \x1b[0;32mIn[3], line 1\x1b[0m\n\x1b[0;32m----> 1\x1b[0m f(0)\n",
    "File \x1b[0;32mcapevolve_skills/fmt/norm.py:2\x1b[0m, in \x1b[0;36mf\x1b[0;34m(x)\x1b[0m\n",
    "\x1b[0;31mHelperFault\x1b[0m: " + MARKED,
]


def _through_exec_code(chunks):
    stub = types.ModuleType("jupyter_kernel_cli")
    stub.ClientJupyterKernel = object
    sys.modules.setdefault("jupyter_kernel_cli", stub)
    spec = importlib.util.spec_from_file_location(
        "_vendored_code_exec_sb", REPO / "third_party/spreadsheetbench/inference/code_exec.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.exec_code(types.SimpleNamespace(execute=lambda code: "\n\n\n\n".join(chunks)), "x")


def test_an_ipython_style_helper_crash_is_a_candidate_fault_after_exec_code(mod, monkeypatch, tmp_path):
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    out = _through_exec_code(IPY_CHUNKS)
    r = _run(mod, monkeypatch, tmp_path, _cand(tmp_path, "c", {"norm.py": "x=1\n"}), [READY, out])
    assert "candidate helper crashed: CANDIDATE_HELPER_FAULT" in r.error
    assert r.metadata["error_kind"] == "candidate"


def test_a_sandbox_denial_wins_over_a_crash_in_the_same_output(mod, monkeypatch, tmp_path):
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    denied = (f"{MARKED}\nPermissionError: [Errno 13] Permission denied: "
              f"'{mod._CONTAINER_DATA_ROOT}/spreadsheet/t1/1_t1_input.xlsx'")
    r = _run(mod, monkeypatch, tmp_path, _cand(tmp_path, "c", {"norm.py": "x=1\n"}), [READY, denied])
    assert r.metadata["error_kind"] == "infra"


def test_only_the_last_exec_result_decides_a_helper_crash(mod, monkeypatch, tmp_path):
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    r = _run(mod, monkeypatch, tmp_path, _cand(tmp_path, "c", {"norm.py": "x=1\n"}),
             [READY, f"Error: {MARKED}", "printed something, wrote nothing"], turns=2)
    assert (r.metadata or {}).get("error_kind") != "candidate"


def test_a_bootstrap_that_did_not_run_is_infra_unless_the_helper_is_named(mod, monkeypatch, tmp_path):
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    cand = _cand(tmp_path, "c", {"norm.py": "x=1\n"})
    for busy in ("Kernel is busy", "", "TimeoutError: kernel did not answer", "Traceback (most recent call last):\n"
                 '  File "<stdin>", line 1, in <module>\nConnectionError: kernel died'):
        r = _run(mod, monkeypatch, tmp_path, cand, [busy])
        assert r.metadata["error_kind"] == "infra" and r.seen == {}, busy
    r = _run(mod, monkeypatch, tmp_path, cand, [_through_exec_code(IPY_CHUNKS)])
    assert r.metadata["error_kind"] == "candidate" and "failed to load" in r.error


def test_a_skills_tree_with_colliding_module_names_is_refused_as_the_candidates_fault(mod, monkeypatch, tmp_path):
    monkeypatch.setenv("CAPEVOLVE_HELPERS", "1")
    cand = _cand(tmp_path, "c", {"x-y.py": "a=1\n", "x_y.py": "a=2\n"})
    r = _run(mod, monkeypatch, tmp_path, cand, [READY])
    assert "refused" in r.error and r.metadata["error_kind"] == "candidate"
