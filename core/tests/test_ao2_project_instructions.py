"""AO-2 proposer jobs get the project's own optimizer INSTRUCTIONS.md (benchmark facts and constraints),
as the hill-climb path and the agent host already do."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))
import ao2_fakes as F  # noqa: E402,F401  (puts core/ and the agent-optimize scripts on sys.path)

import conductor_backend  # noqa: E402
import proposer  # noqa: E402

FACT = "Tool outputs must stay identical to the benchmark's: never change a return value's shape."


def _project(tmp_path, spec_extra=None, text=None):
    proj = tmp_path / "proj"
    (proj / "optimizer").mkdir(parents=True)
    (proj / "optimizer" / "INSTRUCTIONS.md").write_text(
        text if text is not None else f"# Benchmark facts\n- {FACT}\n\n{{{{FAILURES}}}}\n{{{{CAP_BRIEF}}}}\nclosing line\n")
    return SimpleNamespace(project=proj, spec=dict(spec_extra or {}))


def test_the_project_sentence_reaches_the_job_prompt(tmp_path):
    be = _project(tmp_path)
    text = conductor_backend.RealBackend._project_instructions(be)
    body = proposer.build_prompt(workdir=tmp_path / "w", parent="seed", cluster=None, project_instructions=text)
    assert FACT in body
    assert "Project instructions from the user" in body and "end of project instructions" in body
    assert "{{FAILURES}}" not in body and "{{CAP_BRIEF}}" not in body        # template placeholders are dropped
    assert body.index("Rules:") < body.index(FACT)                           # the conductor's rules come first


def test_it_can_be_disabled_and_an_absent_file_is_silent(tmp_path):
    be = _project(tmp_path, {"ao_project_instructions": False})
    assert conductor_backend.RealBackend._project_instructions(be) == ""
    body = proposer.build_prompt(workdir=tmp_path / "w", parent="seed", cluster=None, project_instructions="")
    assert "Project instructions" not in body
    be2 = SimpleNamespace(project=tmp_path / "nowhere", spec={})
    assert conductor_backend.RealBackend._project_instructions(be2) == ""
    named = _project(tmp_path / "n", {"optimizer_instructions_file": "optimizer/OTHER.md"})
    (named.project / "optimizer" / "OTHER.md").write_text("Only this file counts.\n")
    assert "Only this file counts." in conductor_backend.RealBackend._project_instructions(named)


def test_a_long_file_is_cut_but_the_rules_and_the_digest_budget_are_untouched(tmp_path):
    big = FACT + "\n" + "\n".join(f"filler line {i} " * 5 for i in range(2000))
    text = proposer.project_instructions_section(big)
    assert FACT in text and len(text.encode()) < proposer.PROJECT_MAX_BYTES + 700 and "cut" in text
    plain = proposer.build_prompt(workdir=tmp_path / "w", parent="seed", cluster=None, digest_text="D" * 20000)
    withp = proposer.build_prompt(workdir=tmp_path / "w", parent="seed", cluster=None, digest_text="D" * 20000,
                                  project_instructions=big)
    assert withp.startswith(plain) and len(plain.encode()) <= proposer.MAX_PROMPT_BYTES


def test_the_launched_job_prompt_and_workdir_instructions_carry_the_project_sentence(tmp_path):
    import unittest.mock as m
    be = _project(tmp_path)
    work = tmp_path / "work" / "cand_9"
    calls = []

    def sh(argv):
        calls.append(argv)
        work.mkdir(parents=True)
        return 0, "", ""
    fake = SimpleNamespace(
        ctx=SimpleNamespace(work=lambda t: work), run_dir=tmp_path, root=tmp_path, project=be.project, spec={},
        cfg=SimpleNamespace(cost_eps=None), optimizer="mock",
        _paths=lambda j: (tmp_path / "j.log", tmp_path / "j.rc", tmp_path / "j.prompt.md"),
        _spawn=lambda j, cmd, env=None: {"pid": 1}, transcript=lambda j: tmp_path / "t.jsonl", job_usd_cap=lambda: 0,
        _inject_context=lambda w, p: None)
    fake._project_instructions = lambda: conductor_backend.RealBackend._project_instructions(fake)
    fake._valid_clusters = lambda: []
    job = {"id": "j1", "kind": "merge", "tag": "cand_9", "parent": "cand_1", "parents": ["cand_1", "cand_2"],
           "conflicts": [{"where": "policy/policy.md::Rules", "trunk": ["cand_2"], "donor": ["cand_1"]}]}
    with m.patch.object(conductor_backend.act, "sh", sh), \
            m.patch.object(conductor_backend, "conductor_jobs", lambda root: []), \
            m.patch.object(conductor_backend.digest, "build", lambda *a: {}), \
            m.patch.object(conductor_backend.digest, "fit", lambda d: ({}, "")), \
            m.patch.object(conductor_backend.digest, "cand_dir", lambda rd, t: tmp_path / "candidates" / t):
        conductor_backend.RealBackend._start_llm(fake, job)
    assert FACT in (tmp_path / "j.prompt.md").read_text()
    assert FACT in (work / "INSTRUCTIONS.md").read_text()
