"""Every command in agent-optimize SKILL.md / references must exist with the flags it uses."""

import re
import subprocess
import sys
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2] / "skills"
AO = SKILLS / "algorithms/agent-optimize"
CMD = re.compile(r'python3? "\$(A|S)/([\w/.-]+\.py)"(?: (propose|probe|promote|prune|merge|finalize))?')
FLAG = re.compile(r"(?<![\w-])(--[a-z][\w-]*)")


def _commands():
    for f in [AO / "SKILL.md", *sorted((AO / "references").glob("*.md"))]:
        for line in f.read_text(encoding="utf-8").replace("\\\n", " ").splitlines():
            m = CMD.search(line)
            if m:
                base = AO / "scripts" if m.group(1) == "A" else SKILLS
                yield f.name, base / m.group(2), m.group(3), set(FLAG.findall(line[m.end():]))


def _help(script, verb):
    argv = [sys.executable, str(script)] + ([verb] if verb else []) + ["--help"]
    return subprocess.run(argv, capture_output=True, text=True).stdout


def test_skill_md_has_commands_and_every_flag_exists():
    cmds = list(_commands())
    assert any(s.name == "act.py" for _, s, _, _ in cmds) and any(s.name == "digest.py" for _, s, _, _ in cmds)
    for doc, script, verb, flags in cmds:
        assert script.is_file(), f"{doc}: {script} does not exist"
        text = _help(script, verb)
        assert "usage" in text.lower(), f"{doc}: {script.name} {verb or ''} --help failed"
        for fl in flags:
            assert fl in text, f"{doc}: {script.name} {verb or ''} has no {fl}"


def test_all_six_verbs_are_documented():
    body = (AO / "SKILL.md").read_text(encoding="utf-8")
    for v in ("propose", "probe", "promote", "prune", "merge", "finalize"):
        assert f"act.py\" {v}" in body, v


def test_host_briefing_follows_the_engine_switch():
    sys.path.insert(0, str(AO / "scripts"))
    import host
    base = "x\n## Default to 3+ candidates per round\nold\n## Your stop condition\nstop measure.py\n"
    assert "3+ candidates" in host._new_engine_briefing(base, {})
    new = host._new_engine_briefing(
        base, {"optimizer": {"ablation": {"active_eval": True, "dag_parallel": True}}})
    assert "digest.py" in new and "3+ candidates" not in new and "act.py finalize" in new


def test_references_are_small():
    for f in (AO / "references").glob("*.md"):
        assert f.stat().st_size <= 2400, f"{f.name} is {f.stat().st_size} bytes"
