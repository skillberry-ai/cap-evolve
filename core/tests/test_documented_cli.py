"""Every CLI invocation shown in the docs actually parses.

Docs are the agent-facing API: `orchestrate` and the algorithm skills tell an agent
to run these exact command lines. A flag that was renamed, or a `--mode` value the
script's `choices` never had, turns a documented instruction into an exit-2 crash —
or worse, silently does something else. Nothing else in CI covers the phase
`scripts/run.py` surface, so this scans the docs and checks each flag (and each
enumerated value) against the real argparse.

Catches the class in #203 (docs instructing `cap-evolve finalize`, which does not
exist) and the `--mode paired` breakage fixed in #198.
"""

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# `$S` / `$SKILLS_DIR` etc. all stand in for the skills dir; a bare `scripts/run.py`
# in a SKILL.md means that skill's own script.
_SCRIPT = re.compile(r'(?:"?\$\{?\w+\}?"?/|\.\.\./)?([\w./-]*scripts/run\.py)')
_FLAG = re.compile(r"(--[a-z][a-z0-9-]*)")
# Placeholders (`<best_mean>`, `{workdir}`) and shell vars are not values to validate.
_PLACEHOLDER = re.compile(r"^[<{$]|^'")


def _spec(script: Path) -> tuple[set[str], dict[str, set[str]]]:
    """(known flags, {flag: allowed choices}) from the script's own --help."""
    out = subprocess.run([sys.executable, str(script), "--help"],
                         capture_output=True, text=True, cwd=script.parent)
    help_text = out.stdout + out.stderr
    choices = {f"--{f}": set(v.split(","))
               for f, v in re.findall(r"--([a-z][a-z0-9-]*) \{([^}]+)\}", help_text)}
    return set(_FLAG.findall(help_text)), choices


def _resolve(raw: str, doc: Path) -> Path | None:
    for cand in (REPO / "skills" / raw, REPO / raw,
                 doc.parent / raw):  # bare `scripts/run.py` inside a SKILL.md
        if cand.is_file():
            return cand
    return None


def test_documented_run_py_invocations_parse():
    docs = [p for p in REPO.glob("**/*.md")
            if "node_modules" not in p.parts and ".git" not in p.parts
            # design specs/plans describe past or proposed states, not runnable commands
            and "specs" not in p.parts and "plans" not in p.parts]
    scanned, findings = 0, []
    for doc in docs:
        for line in doc.read_text(errors="replace").splitlines():
            if "scripts/run.py" not in line or not line.lstrip().startswith(("python", "$")):
                continue
            m = _SCRIPT.search(line)
            script = _resolve(m.group(1), doc) if m else None
            if script is None:
                continue
            scanned += 1
            known, choices = _spec(script)
            # only the command itself runs; a trailing `# ...` comment is prose
            tokens = line.split(" #")[0].split()
            for i, tok in enumerate(tokens):
                if not tok.startswith("--"):
                    continue
                flag, _, inline = tok.partition("=")
                if flag not in known:
                    findings.append(f"{doc.relative_to(REPO)}: {script.name} has no {flag}")
                    continue
                if flag in choices:
                    val = inline or (tokens[i + 1] if i + 1 < len(tokens) else "")
                    if val and not _PLACEHOLDER.match(val) and val not in choices[flag]:
                        findings.append(
                            f"{doc.relative_to(REPO)}: {flag} {val!r} not in "
                            f"{sorted(choices[flag])}")
    assert scanned > 20, f"scanner found only {scanned} invocations — regex likely broke"
    assert not findings, "documented CLI invocations that do not parse:\n" + "\n".join(findings)


def test_gate_check_py_passes():
    """CI runs only `pytest core/tests`, so no skill `check.py` was ever exercised.

    The gate's check.py is what covers the `--paired-deltas` parsing and the paired
    k_se=1.0 rule, so run it here rather than leaving that coverage CI-invisible.
    (A general runner for all 20 skills' check.py belongs in its own change; several
    need network/optimizer setup. ponytail: one skill now, widen when CI can afford it.)
    """
    check = REPO / "skills" / "phases" / "gate" / "scripts" / "check.py"
    out = subprocess.run([sys.executable, str(check)], capture_output=True, text=True,
                         cwd=check.parent)
    assert out.returncode == 0, f"gate check.py failed:\n{out.stdout}\n{out.stderr}"
