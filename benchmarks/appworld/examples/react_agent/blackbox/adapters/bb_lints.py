"""Candidate lints for the blackbox approach: the candidate is one store skill, ``SKILL.md``.

    python bb_lints.py CANDIDATE_DIR    # prints {"ok": bool, "violations": [...]}; exit 1 on violation,
                                        # exit 2 when the lint data is unavailable

A violating candidate is rejected before any episode runs (scored 0 with the violations as
feedback), as in the direct approach. Reused from the direct approach's ``lints.py`` (copied into the
project by scripts/setup_project.sh): the lint cache, the 8-gram / supervisor-contact leak check
(AppWorld's rule against task-specific hints) and the token counter.

SKILL.md rules (README: Lints):
- No skill-package additions (``scripts/``, ``references/``, ``assets/``): a script would become a
  tool, and this approach optimizes the system prompt only. Other files in the candidate folder are
  the harness's own (INSTRUCTIONS.md, guidance/, JOURNAL.md, ...) and are never deployed: the
  tailoring stages SKILL.md alone for the store.
- Frontmatter ``name: my_skill``.
- The body is a Jinja template whose ONLY variable is ``main_user``, with only the fields
  first_name, last_name, email and phone_number. Every placeholder of the seed stays (each field
  at least once); no other ``{{ }}`` expression, no ``{% %}`` block, no filter. No
  ``{{ instruction }}``: the real task turn comes from AppWorld's client, after the proxy's marker.
- The app list rendered into the seed (``$AW_EVAL/app_descriptions.json``) stays verbatim: in the
  direct approach the optimizer only ever sees its ``{{ app_descriptions }}`` placeholder.
- The demo keeps its ``USER:`` / ``ASSISTANT:`` turns, and the body stays under the token limit.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lints as direct_lints  # noqa: E402

SKILL_NAME = "my_skill"
PACKAGE_DIRS = ("scripts", "references", "assets")  # skill-package parts the store would import
SKILL_MAX_TOKENS = 8500  # the direct prompt's 8,000 plus the rendered app list (~350 tokens)
MAIN_USER_FIELDS = {"first_name", "last_name", "email", "phone_number"}
PLACEHOLDER_RE = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)
MAIN_USER_RE = re.compile(r"^\s*main_user\.([a-z_]+)\s*$")
WHAT = "SKILL.md"


def app_descriptions_path() -> Path:
    return Path(os.environ.get("AW_APP_DESCRIPTIONS") or direct_lints._eval_dir() / "app_descriptions.json")


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """``(frontmatter key -> value, body)``; an empty dict when there is no frontmatter."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    fm = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fm[k.strip()] = v.strip()
    return fm, text[end + 5:]


def lint_skill_md(text: str) -> list[str]:
    out = []
    fm, body = split_frontmatter(text)
    if fm.get("name") != SKILL_NAME:
        out.append(f"{WHAT}: frontmatter must start the file and set name: {SKILL_NAME}")
    if "{%" in body or "{#" in body:
        out.append(f"{WHAT}: no Jinja {{% %}} blocks or {{# #}} comments; only the main_user placeholders")
    fields_used: set[str] = set()
    for expr in PLACEHOLDER_RE.findall(body):
        m = MAIN_USER_RE.match(expr)
        if not m:
            out.append(f"{WHAT}: placeholder {{{{{expr.strip()}}}}} is not allowed; only "
                       f"{{{{ main_user.<field> }}}} with field in {sorted(MAIN_USER_FIELDS)}")
        elif m.group(1) not in MAIN_USER_FIELDS:
            out.append(f"{WHAT}: main_user.{m.group(1)} does not exist; fields are {sorted(MAIN_USER_FIELDS)}")
        else:
            fields_used.add(m.group(1))
    missing = MAIN_USER_FIELDS - fields_used
    if missing:
        out.append(f"{WHAT}: the seed's placeholders must stay; missing main_user.{', main_user.'.join(sorted(missing))}")
    try:
        from jinja2 import Environment
        Environment().parse(body)
    except Exception as e:  # noqa: BLE001
        out.append(f"{WHAT}: Jinja template does not parse: {e}")
    if "USER:" not in body or "ASSISTANT:" not in body:
        out.append(f"{WHAT}: the few-shot demo must keep its USER: / ASSISTANT: turns")
    apps_file = app_descriptions_path()
    if apps_file.is_file():
        apps = json.loads(apps_file.read_text())["text"]
        if apps not in body:
            out.append(f"{WHAT}: the app list rendered into the seed must stay verbatim (it is AppWorld's "
                       "app list, not part of the capability)")
    else:
        out.append(f"{WHAT}: app list unavailable ({apps_file} missing; scripts/setup_project.sh writes it)")
    n = direct_lints._tokens(body)
    if n > SKILL_MAX_TOKENS:
        out.append(f"{WHAT}: {n} tokens > {SKILL_MAX_TOKENS}")
    if apps_file.is_file():
        body = body.replace(json.loads(apps_file.read_text())["text"], "")  # AppWorld's own text, not the candidate's
    return out + direct_lints._leaks(body, WHAT)


def lint_candidate(cdir: Path) -> list[str]:
    cdir = Path(cdir)
    skill = cdir / "SKILL.md"
    if not skill.is_file():
        return [f"{WHAT}: missing"]
    out = []
    others = sorted(str(p.relative_to(cdir)) for sub in PACKAGE_DIRS for p in (cdir / sub).rglob("*")
                    if p.is_file() and "__pycache__" not in p.parts)
    if others:
        out.append(f"the skill must be SKILL.md only (system-prompt capability); found {others}")
    return out + lint_skill_md(skill.read_text(encoding="utf-8"))


if __name__ == "__main__":
    try:
        v = lint_candidate(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
    except direct_lints.LintDataUnavailable as e:
        print(json.dumps({"ok": False, "violations": [str(e)]}, indent=1))
        raise SystemExit(2)
    print(json.dumps({"ok": not v, "violations": v}, indent=1))
    raise SystemExit(1 if v else 0)
