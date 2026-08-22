"""skill-package capability — optimize a WHOLE Agent Skill package.

A skill package is a directory: a required ``SKILL.md`` (YAML frontmatter
``name``/``description`` + a Markdown body) plus optional ``references/`` (docs
loaded on demand), ``scripts/`` (code the agent EXECUTES — its source never
enters context), and ``assets/`` (files used in output). Every one of those is an
editable component here: ``materialize`` exposes them, ``apply`` can create or
rewrite them (including a NEW bundled script), and ``validate`` checks them.

``validate`` encodes the skill-creator / Agent-Skills authoring rules so the
optimizer cannot drift into an invalid package (rules sourced to first-party
Anthropic docs — see references/concepts.md):
  - frontmatter has ``name`` (<=64 chars, [a-z0-9-], no "anthropic"/"claude",
    no XML tags) and a non-empty ``description`` (<=1024 chars, no XML tags) that
    says WHAT + WHEN ("use when").
  - the SKILL.md body stays within the Level-2 budget (<=500 lines): it is a
    recurring per-session token cost.
  - references are one level deep (no nested pointers), each is linked from
    SKILL.md, and a long one (>300 lines) opens with a table of contents.
  - files the body links to exist.
  - bundled scripts COMPILE (``ast.parse``), are not stub-only, and — when they
    declare a ``--self-check`` entry point — that self-check actually passes.
    Deterministic code the agent runs is only deterministic if it runs.

Soft authoring lints (warnings, not failures): first-person description (POV
drift hurts discovery), all-caps CRITICAL/ALWAYS/MUST/NEVER in the description
(over-triggers current models), a description long enough to risk the host's
listing truncation, a script with no declared self-check, and a script reaching
for network/subprocess/``eval`` (a bundled script is executable context — the
human must see that in the diff).

Edit ops (mirrored by the mock optimizer):
``{"file", "op": set|append|ensure_contains|remove, "text", "kind"?}``. ``kind``
defaults to the file's location (frontmatter/body/reference/script/asset) and is
checked against the action policy (``inputs/policy.json`` overrides
``DEFAULT_POLICY``), so a run can allow prose edits while forbidding new code.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9-]{1,64}$")
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.S)
XML_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")  # an actual tag, not a stray "<"
REL_LINK_RE = re.compile(r"\]\(([^)\s]+)\)")  # any Markdown link target
# A description states WHEN either conditionally ("Use when the user asks") or
# POSITIONALLY ("Use after intake", "Use as the last evaluation step") — both are real
# triggering signals, so demanding the literal "use when" bigram flags good prose.
SAYS_WHEN_RE = re.compile(
    r"\bwhen\b|\buse (after|before|as|at|to|between|right|during|only|this|the moment)\b",
    re.I)
MAX_BODY_LINES = 500              # skill-creator's Level-2 budget (hard here)
MAX_BODY_TOKENS = 5000            # cap-evolve heuristic (~chars/4), advisory only
CHARS_PER_TOKEN = 4
LONG_REF_LINES = 300
MIN_TOC_LINKS = 3                 # anchor links a long reference's TOC must show...
TOC_SCAN_CHARS = 1500             # ...within this leading window, so put the TOC FIRST
LISTING_CAP_CHARS = 1536          # Claude Code host default (maxSkillDescriptionChars)
LONG_DESC_CHARS = 1024            # hard cap; also the front-load advisory threshold
MAX_COMPONENT_CHARS = 40000       # per-component cap so one big file can't blow the prompt
SELF_CHECK_TIMEOUT = 30           # seconds per bundled-script self-check
TEXT_SUFFIXES = {".py", ".sh", ".md", ".txt", ".json", ".yaml", ".yml", ".toml",
                 ".js", ".ts", ".csv", ".cfg", ".ini", ""}
RISKY_IMPORTS = {"subprocess", "socket", "urllib", "http", "requests", "httpx", "ftplib",
                 "telnetlib", "smtplib", "ctypes"}
RISKY_BUILTINS = {"eval", "exec", "compile", "__import__"}

# The whole package is editable, so every kind is allowed by default. A run that
# must not gain new executable code drops "script" (and "add") in policy.json —
# the same knob shape the tool capabilities use (cap_evolve.tool_surface).
DEFAULT_POLICY = {"allow": ["frontmatter", "body", "reference", "script", "asset",
                            "add", "remove"]}


def load_policy(capability_dir: Path) -> dict:
    """``policy.json`` in the capability dir if present (it overrides), else the default."""
    f = Path(capability_dir) / "policy.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else dict(DEFAULT_POLICY)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse the YAML frontmatter enough for the authoring lints.

    Handles what a description realistically uses: a one-line value, a quoted
    value, a ``>``/``|`` block scalar, and an indented continuation. A block
    scalar is ordinary YAML for a long description — the highest-leverage field
    this capability edits — so a parser that returned the literal ``'>'`` would
    silently bypass every description lint.
    """
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm: dict[str, str] = {}
    key: str | None = None
    fold = ""                     # ">" (fold to spaces), "|" (keep newlines), or ""
    for line in m.group(1).splitlines():
        stripped = line.strip()
        indented = line[:1] in (" ", "\t")
        # A block scalar continues while lines are INDENTED; a blank line inside it
        # is not a terminator. An unindented `next-key:` ends it — treating that as
        # continuation swallowed every key after a `>`/`|` description (6 of them on
        # algorithms/evograph) and inflated the measured description past its cap.
        if key and (indented or (fold and not stripped)):
            if not stripped:
                continue
            sep = "\n" if fold == "|" else " "
            fm[key] = (fm[key] + sep + stripped).strip() if fm[key] else stripped
            continue
        if ":" in line and not indented:
            key, _, v = line.partition(":")
            key = key.strip()
            v = v.strip()
            if v in (">", "|", ">-", "|-", ">+", "|+"):
                fold, v = v[0], ""
            else:
                fold = ""
                v = v.strip('"').strip("'")
            fm[key] = v
        else:
            key, fold = None, ""
    return fm, text[m.end():]


def _relative_links(text: str) -> list[str]:
    """Local relative link targets in Markdown, anchors stripped.

    A Markdown link may carry an anchor (``references/x.md#a-heading``); the anchor is
    not part of the path, so existence-checking the raw target reads every deep link as
    broken. Absolute URLs, bare in-document anchors and mailto:/rooted paths are skipped
    — only targets that must resolve to a file next to the linking document come back,
    de-duplicated (the same file linked five times is one problem, not five findings).
    """
    out = []
    for raw in REL_LINK_RE.findall(text):
        if raw.startswith(("#", "/", "mailto:")) or "://" in raw:
            continue
        target = raw.split("#", 1)[0].strip()
        if target:
            out.append(target)
    return list(dict.fromkeys(out))


def _subpackages(capability_dir: Path) -> list[Path]:
    """Immediate sub-directories that are themselves skill packages (contain SKILL.md).

    A capability_path may hold ONE skill (SKILL.md at the top) or SEVERAL shared
    skills as immediate sub-packages (e.g. seed_capability/{docx,pptx,xlsx,pdf}/).
    Returns the sub-package dirs (sorted) when this is a MULTI-skill root, else []."""
    # A missing/typoed/non-dir path is NOT a multi-skill root — return [] so the caller
    # falls through to the single-skill path and reports a clean validation error
    # ("no SKILL.md") instead of raising FileNotFoundError on iterdir().
    if not capability_dir.is_dir() or (capability_dir / "SKILL.md").exists():
        return []
    return sorted(
        sub for sub in capability_dir.iterdir()
        if sub.is_dir() and (sub / "SKILL.md").exists()
    )


def _read_component(f: Path) -> str:
    """Component text for one bundled file; binaries become an inventory stub.

    An asset (icon/font/template) is part of the package the optimizer must SEE,
    but its bytes are worthless in a text prompt — so list it, don't inline it.
    """
    if f.suffix.lower() not in TEXT_SUFFIXES:
        return f"<binary asset, {f.stat().st_size} bytes>"
    try:
        text = f.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"<binary asset, {f.stat().st_size} bytes>"
    if len(text) > MAX_COMPONENT_CHARS:
        return text[:MAX_COMPONENT_CHARS] + f"\n<truncated at {MAX_COMPONENT_CHARS} chars>"
    return text


def _materialize_one(skill_dir: Path, prefix: str = "") -> dict:
    """Flatten ONE skill package — SKILL.md, references, scripts, assets — into components."""
    parts = {}
    skill_md = skill_dir / "SKILL.md"
    if skill_md.exists():
        parts[f"{prefix}SKILL.md"] = skill_md.read_text(encoding="utf-8")
    for sub in ("references", "scripts", "assets"):
        d = skill_dir / sub
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                rel = f.relative_to(skill_dir).as_posix()
                parts[f"{prefix}{rel}"] = _read_component(f)
    return parts


def materialize(capability_dir: Path) -> dict:
    """Flatten the whole package into named components (SKILL.md + refs + scripts + assets).

    ``scripts/<name>`` is code the downstream agent EXECUTES: its source costs the
    agent no context, only its output — which is why converting a skipped prose
    step into a script is the determinism lever.

    Supports BOTH a single-skill capability_path (SKILL.md at the top) and a
    MULTI-skill root holding several immediate sub-packages: components from each
    sub-package are namespaced by ``<skill>/`` (e.g. ``docx/SKILL.md``,
    ``pdf/references/forms.md``)."""
    capability_dir = Path(capability_dir)
    subs = _subpackages(capability_dir)
    if subs:
        parts: dict = {}
        for sub in subs:
            parts.update(_materialize_one(sub, prefix=f"{sub.name}/"))
        return parts
    return _materialize_one(capability_dir)


def _kind_of(rel: str) -> str:
    """The action kind implied by a component's location in the package."""
    head = rel.split("/", 1)[0]
    if head == "references":
        return "reference"
    if head == "scripts":
        return "script"
    if head == "assets":
        return "asset"
    return "body"          # SKILL.md — "frontmatter" is the same file, callers may say so


def apply(capability_dir: Path, edits: list[dict] | None = None) -> dict:
    """Apply edits to any part of the package. Returns {changed, refused}.

    Every write is contained to the capability dir (a ``../`` target is refused,
    not raised — the same {changed, refused} contract the tool capabilities use)
    and checked against the action policy, so a run can permit prose edits while
    forbidding new executable code.
    """
    capability_dir = Path(capability_dir)
    root = capability_dir.resolve()
    allow = set(load_policy(capability_dir).get("allow", []))
    report: dict = {"changed": [], "refused": []}

    def refuse(edit, reason):
        report["refused"].append({"edit": edit, "reason": reason})

    for e in edits or []:
        rel = str(e.get("file", ""))
        op = e.get("op", "set")
        text = e.get("text", "")
        target = capability_dir / rel
        try:
            resolved = target.resolve()
        except OSError as exc:                       # pragma: no cover — exotic paths
            refuse(e, f"unresolvable path: {exc}")
            continue
        if resolved != root and root not in resolved.parents:
            refuse(e, f"path '{rel}' escapes the capability dir")
            continue
        kind = e.get("kind") or _kind_of(rel)
        if kind == "frontmatter":
            kind = "frontmatter" if "frontmatter" in allow else "body"
        if kind not in allow:
            refuse(e, f"action '{kind}' not allowed by policy")
            continue
        exists = target.exists()
        if op == "remove":
            if "remove" not in allow:
                refuse(e, "action 'remove' not allowed by policy")
            elif exists:
                target.unlink()
                report["changed"].append(rel)
            continue
        if not exists and "add" not in allow:
            refuse(e, f"creating '{rel}' needs the 'add' action")
            continue
        cur = target.read_text(encoding="utf-8") if exists else ""
        if op == "set":
            new = text
        elif op == "append":
            new = cur + text
        elif op == "ensure_contains":
            new = cur if (text.strip() and text.strip() in cur) else cur + text
        else:
            refuse(e, f"unknown op {op!r}")
            continue
        if new != cur:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(new, encoding="utf-8")
            report["changed"].append(rel)
    return report


def is_empty(capability_dir: Path) -> bool:
    """Return True when the capability directory has no meaningful skill content yet.

    An empty directory (no SKILL.md, no sub-packages) is an accepted starting state
    so the optimizer can create the initial skill from failing trajectories."""
    capability_dir = Path(capability_dir)
    subs = _subpackages(capability_dir)
    if subs:
        return False
    return not (capability_dir / "SKILL.md").exists()


def validate(capability_dir: Path) -> dict:
    """Enforce the Agent-Skills authoring rules. Returns {ok, problems, warnings, scripts}.

    An empty capability (no SKILL.md, no sub-packages) is accepted as a valid
    starting state so the optimizer can create the initial skill from failing
    trajectories.

    For a MULTI-skill root (several immediate sub-packages), validate EACH
    sub-package and aggregate: problems/warnings are namespaced by ``<skill>:`` and
    ``ok`` is True only if every sub-package is valid."""
    capability_dir = Path(capability_dir)
    if is_empty(capability_dir):
        return {"ok": True, "empty": True, "name": "", "problems": [], "warnings": [],
                "scripts": []}
    subs = _subpackages(capability_dir)
    if subs:
        problems: list[str] = []
        warnings: list[str] = []
        names: list[str] = []
        scripts: list[dict] = []
        for sub in subs:
            v = _validate_one(sub)
            names.append(v.get("name", sub.name))
            problems += [f"{sub.name}: {p}" for p in v["problems"]]
            warnings += [f"{sub.name}: {w}" for w in v["warnings"]]
            scripts += [{**s, "skill": sub.name} for s in v.get("scripts", [])]
        return {"ok": not problems, "name": ",".join(names),
                "problems": problems, "warnings": warnings, "scripts": scripts}
    return _validate_one(capability_dir)


def _validate_frontmatter(fm: dict, problems: list, warnings: list) -> str:
    name = fm.get("name", "")
    if not name:
        problems.append("frontmatter missing 'name'")
    elif not NAME_RE.match(name):
        problems.append(f"name {name!r} must be <=64 chars, lowercase [a-z0-9-]")
    if "anthropic" in name.lower() or "claude" in name.lower():
        problems.append("name must not contain 'anthropic' or 'claude'")
    if XML_TAG_RE.search(name):
        problems.append("name must not contain XML tags")

    desc = fm.get("description", "")
    if not desc.strip():
        problems.append("frontmatter missing a non-empty 'description'")
        return name
    if len(desc) > LONG_DESC_CHARS:
        problems.append(f"description is {len(desc)} chars (>{LONG_DESC_CHARS})")
    if XML_TAG_RE.search(desc):
        problems.append("description must not contain XML tags")
    if not SAYS_WHEN_RE.search(desc):
        warnings.append("description should say WHEN to use the skill "
                        "('Use when …') — it is the primary triggering signal")
    # point-of-view drift: descriptions must be third person.
    if re.search(r"(?<![A-Za-z])I(?![A-Za-z])|I'?m\b|I can\b|you can help", desc):
        warnings.append("description should be third person (e.g. 'Processes X "
                        "…'), not first person ('I can …') — POV drift hurts discovery")
    # all-caps imperatives over-trigger current models.
    if re.search(r"\b(CRITICAL|ALWAYS|MUST|NEVER)\b", desc):
        warnings.append("avoid all-caps CRITICAL/ALWAYS/MUST/NEVER in the "
                        "description — it over-triggers; say plainly 'Use when …'")
    # host listing truncation (Claude Code default; configurable per host).
    if len(desc) > LISTING_CAP_CHARS - 256:
        warnings.append(f"description is {len(desc)} chars; the Claude Code host "
                        f"truncates description + when_to_use at {LISTING_CAP_CHARS} "
                        "by default (configurable) — front-load the key use case")
    return name


def _validate_references(pkg: Path, body: str, problems: list, warnings: list) -> None:
    # Relative links the body points at must resolve. Anchors are stripped first
    # (_relative_links), or every deep link like "references/x.md#heading" reads as broken.
    for rel in _relative_links(body):
        if rel.split("/", 1)[0] in ("references", "scripts", "assets") \
                and not (pkg / rel).exists():
            problems.append(f"SKILL.md links '{rel}' which does not exist")

    refs = pkg / "references"
    if not refs.is_dir():
        return
    # sorted(): filesystem iteration order differs between machines, and callers (the
    # repo's own blocking authoring lint, and the optimizer's warning list) need the
    # findings to come out in the same order everywhere.
    for sub in sorted(refs.iterdir()):
        if sub.is_dir():
            warnings.append(f"references/{sub.name}/ is nested >1 level deep; "
                            "keep references one level deep")
    for f in sorted(refs.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        head = text[:TOC_SCAN_CHARS]
        n = text.count("\n") + 1
        # A long reference needs a real table of contents, and the check is POSITIONAL:
        # the agent may read only the head, so a perfect TOC sitting behind a preamble
        # is a TOC the reader never sees. Anchor links preferred, section headings
        # accepted as the weaker form.
        if n > LONG_REF_LINES and not (head.count("](#") >= MIN_TOC_LINKS
                                       or head.count("\n## ") >= MIN_TOC_LINKS):
            warnings.append(f"references/{f.name} is {n} lines and shows no table of "
                            f"contents in its first {TOC_SCAN_CHARS} chars: put "
                            f"{MIN_TOC_LINKS}+ anchor links ('- [Section](#section)') "
                            "at the very TOP, above any orientation prose")
        # One level deep is about POINTERS, not directories: a reference that points at
        # another reference can be missed when the agent reads only part of it. Judged
        # on the RESOLVED target — a substring/`refs / link` test reads a legitimate
        # "../SKILL.md" back-link as a sibling reference (it resolves through refs/).
        for target in _relative_links(text):
            # A reference written as if it were SKILL.md ("references/b.md") still MEANS
            # the sibling, so resolve that form against references/ — otherwise the
            # commonest ref->ref shape reads as a mere broken link.
            rel = re.sub(r"^(\./)?references/", "", target)
            hop = ((refs if rel != target else f.parent) / rel).resolve()
            if hop.suffix == ".md" and hop.parent == refs.resolve() and hop != f.resolve():
                warnings.append(f"references/{f.name} points at another reference "
                                f"('{target}') — keep references one level deep, linked "
                                "directly from SKILL.md")
            elif not hop.exists():
                warnings.append(f"references/{f.name} links '{target}' "
                                "which does not exist")
        if f.name not in body and f"references/{f.name}" not in body:
            warnings.append(f"references/{f.name} is an orphan — SKILL.md never points "
                            "at it, so the agent will not know to load it")


def _script_self_check(f: Path, pkg: Path) -> dict:
    """Run a bundled script's declared ``--self-check`` and report the outcome.

    Only a script that DECLARES a self-check is executed — an entry point that
    needs real arguments would otherwise "fail" for the wrong reason. Runs with a
    timeout, in the package dir, with no inherited proxy/API env, so validation
    cannot quietly reach the network on the optimizer's behalf.
    """
    src = f.read_text(encoding="utf-8", errors="replace")
    rel = f.relative_to(pkg).as_posix()
    if "--self-check" not in src:
        return {"file": rel, "self_check": "absent"}
    if os.environ.get("CAPEVOLVE_NO_SCRIPT_EXEC"):
        return {"file": rel, "self_check": "skipped (CAPEVOLVE_NO_SCRIPT_EXEC)"}
    # PATH/HOME/PYTHONPATH pass through (a bundled script may import its own package);
    # nothing else does — no API keys — and the proxy vars are blanked so a self-check
    # cannot quietly reach the network on the optimizer's behalf.
    env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", ""),
           "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
           "PYTHONDONTWRITEBYTECODE": "1", "NO_NETWORK": "1",
           "http_proxy": "", "https_proxy": "", "HTTP_PROXY": "", "HTTPS_PROXY": ""}
    try:
        p = subprocess.run([sys.executable, str(f.resolve()), "--self-check"],
                           cwd=str(pkg.resolve()),
                           capture_output=True, text=True, timeout=SELF_CHECK_TIMEOUT,
                           env=env)
    except subprocess.TimeoutExpired:
        return {"file": rel, "self_check": "timeout", "ok": False,
                "exit_code": None, "stderr_tail": f"timed out after {SELF_CHECK_TIMEOUT}s"}
    except OSError as exc:                                # pragma: no cover
        return {"file": rel, "self_check": "error", "ok": False,
                "exit_code": None, "stderr_tail": str(exc)[-400:]}
    # A failing self-check often reports on stdout (an assertion printer, a FAIL
    # line), so carry both tails — the optimizer can only fix what it is shown.
    return {"file": rel, "self_check": "ran", "ok": p.returncode == 0,
            "exit_code": p.returncode, "stderr_tail": (p.stderr or "")[-400:],
            "stdout_tail": (p.stdout or "")[-400:]}


def _is_stub(tree: ast.Module) -> bool:
    """True when a module has no real body — only a docstring / pass / ``...``."""
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue                                      # docstring or bare ``...``
        if isinstance(node, ast.Pass):
            continue
        return False
    return True


def _risky(tree: ast.Module) -> list[str]:
    """Network / subprocess / dynamic-exec surface a human should see in the diff.

    Judged from the AST (imports and calls), not substrings, so a script that
    merely mentions the word is not flagged.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names} & RISKY_IMPORTS
        elif isinstance(node, ast.ImportFrom) and node.module:
            found |= {node.module.split(".")[0]} & RISKY_IMPORTS
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in RISKY_BUILTINS:
            found.add(node.func.id + "()")
    return sorted(found)


def _validate_scripts(pkg: Path, problems: list, warnings: list) -> list[dict]:
    """Check bundled code the way the downstream agent will meet it: as something run.

    Deterministic code is the point of ``scripts/`` — a script that does not
    compile, or whose declared self-check fails, is not determinism, it is a file.
    """
    d = pkg / "scripts"
    if not d.is_dir():
        return []
    reports: list[dict] = []
    for f in sorted(d.rglob("*.py")):
        if "__pycache__" in f.parts:
            continue
        rel = f.relative_to(pkg).as_posix()
        src = f.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(src, filename=str(f))
        except SyntaxError as exc:
            problems.append(f"{rel} does not compile: {exc.msg} (line {exc.lineno})")
            reports.append({"file": rel, "compiles": False, "error": exc.msg})
            continue
        rep: dict = {"file": rel, "compiles": True}
        if _is_stub(tree):
            warnings.append(f"{rel} has no real body (docstring/pass/... only) — a "
                            "bundled script must be working code, not a placeholder")
            rep["stub"] = True
        risky = _risky(tree)
        if risky:
            warnings.append(f"{rel} uses {', '.join(risky)} — a bundled script is "
                            "executable context; confirm this is intended in the diff")
            rep["risky"] = risky
        rep.update(_script_self_check(f, pkg))
        if rep.get("self_check") == "absent":
            warnings.append(f"{rel} has no declared '--self-check' entry point, so "
                            "nothing verifies it still runs after an edit — add one")
        elif rep.get("ok") is False:
            detail = (rep.get("stderr_tail") or "").strip() or (rep.get("stdout_tail") or "").strip()
            problems.append(f"{rel} --self-check failed (exit {rep.get('exit_code')}): "
                            f"{detail[-300:]}")
        reports.append(rep)
    return reports


def _validate_one(capability_dir: Path) -> dict:
    """Enforce the Agent-Skills authoring rules on ONE skill package."""
    capability_dir = Path(capability_dir)
    problems: list[str] = []
    warnings: list[str] = []

    skill_md = capability_dir / "SKILL.md"
    if not skill_md.exists():
        return {"ok": False, "name": "", "problems": ["no SKILL.md in the package"],
                "warnings": [], "scripts": []}

    text = skill_md.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    name = _validate_frontmatter(fm, problems, warnings)

    n_body = body.count("\n") + 1
    if n_body > MAX_BODY_LINES:
        problems.append(f"SKILL.md body is {n_body} lines (>{MAX_BODY_LINES}); the body "
                        "is a recurring per-session cost — split detail into references/")
    body_tokens = len(body) // CHARS_PER_TOKEN
    if body_tokens > MAX_BODY_TOKENS:
        warnings.append(f"SKILL.md body is ~{body_tokens} tokens (>{MAX_BODY_TOKENS}, this "
                        "repo's heuristic) — move detail into references/")

    _validate_references(capability_dir, body, problems, warnings)
    scripts = _validate_scripts(capability_dir, problems, warnings)

    return {"ok": not problems, "name": name, "problems": problems,
            "warnings": warnings, "scripts": scripts}
