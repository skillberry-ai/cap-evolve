"""exp895 SkillOpt arm: the ONE packed text SkillOpt optimizes (issue #895 §7.3).

SkillOpt optimizes a single skill document. Our candidate is a directory (prompt.md, task_template.md,
skills/<name>/{SKILL.md, scripts/*.py}), so the document is the files concatenated, each introduced by a
marker line `=== FILE: <path> ===`. pack() builds it; unpack() turns SkillOpt's (possibly edited) text back
into a candidate directory, or reports why the document is damaged (it then scores 0 without a model call).

Order: task_template.md, then every skills/**/SKILL.md and script, then prompt.md LAST. SkillOpt's `append`
op and its slow-update / appendix blocks always land at the document tail, so they land in prompt.md (the
system prompt, which is what SkillOpt's own skill document is upstream). A protected block found anywhere
else is moved to the end of prompt.md.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

MARKER_RE = re.compile(r"^=== FILE: (?P<path>.+?) ===$")
_MARKERISH = re.compile(r"^\s*=+\s*FILE\b")
ALLOWED = (
    re.compile(r"^prompt\.md$"),
    re.compile(r"^task_template\.md$"),
    re.compile(r"^skills/[A-Za-z0-9_-]+/SKILL\.md$"),
    re.compile(r"^skills/[A-Za-z0-9_-]+/scripts/[A-Za-z_][A-Za-z0-9_]*\.py$"),
)
REQUIRED = ("prompt.md", "task_template.md")
# SkillOpt's protected regions (skillopt/optimizer/skill.py, slow_update.py, skill_aware.py).
PROTECTED = (("<!-- SLOW_UPDATE_START -->", "<!-- SLOW_UPDATE_END -->"),
             ("<!-- APPENDIX_START -->", "<!-- APPENDIX_END -->"))


def _order_key(rel: str):
    if rel == "task_template.md":
        return (0, rel)
    if rel == "prompt.md":
        return (2, rel)
    return (1, rel)


def candidate_files(cand: Path) -> list[str]:
    """Relative paths of the surface files in a candidate dir (the .gitkeep placeholder is not a surface)."""
    cand = Path(cand)
    out = []
    for p in sorted(cand.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and p.name != ".gitkeep":
            rel = p.relative_to(cand).as_posix()
            if any(a.match(rel) for a in ALLOWED):
                out.append(rel)
    return sorted(out, key=_order_key)


def pack(cand: Path) -> str:
    cand = Path(cand)
    parts = []
    for rel in candidate_files(cand):
        text = (cand / rel).read_text(encoding="utf-8")
        if text and not text.endswith("\n"):
            text += "\n"
        parts.append(f"=== FILE: {rel} ===\n{text}")
    return "".join(parts)


def _pull_protected(doc: str) -> tuple[str, list[str]]:
    """Remove every complete protected block from doc; return (rest, blocks)."""
    blocks = []
    for start, end in PROTECTED:
        while True:
            i = doc.find(start)
            if i == -1:
                break
            j = doc.find(end, i)
            if j == -1:
                break
            blocks.append(doc[i:j + len(end)])
            doc = doc[:i] + doc[j + len(end):]
    return doc, blocks


def unpack(doc: str) -> tuple[dict | None, str | None]:
    """Return ({rel_path: text}, None) or (None, reason the document is damaged)."""
    rest, blocks = _pull_protected(doc)
    for start, end in PROTECTED:
        if start in rest or end in rest:
            return None, f"unbalanced protected-region marker {start if start in rest else end}"
    files: dict[str, list[str]] = {}
    cur = None
    for ln in rest.splitlines(keepends=True):
        m = MARKER_RE.match(ln.rstrip("\n"))
        if m:
            rel = m.group("path").strip()
            if not any(a.match(rel) for a in ALLOWED):
                return None, f"marker names a path outside the editable surfaces: {rel[:120]!r}"
            if rel in files:
                return None, f"duplicate FILE marker for {rel}"
            files[rel] = []
            cur = rel
            continue
        if _MARKERISH.match(ln) or "=== FILE: " in ln:
            return None, f"malformed or mid-line FILE marker: {ln.strip()[:120]!r}"
        if cur is None:
            if ln.strip():
                return None, "text before the first FILE marker"
            continue
        files[cur].append(ln)
    missing = [r for r in REQUIRED if r not in files]
    if missing:
        return None, f"missing FILE block(s): {', '.join(missing)}"
    out = {rel: "".join(lines) for rel, lines in files.items()}
    if blocks:
        out["prompt.md"] = out["prompt.md"].rstrip("\n") + "\n\n" + "\n\n".join(b.strip() for b in blocks) + "\n"
    return out, None


def write_dir(files: dict, dst: Path) -> None:
    dst = Path(dst)
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for rel, text in files.items():
        p = dst / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    # The v2 seed keeps an empty scripts/ dir (with .gitkeep) under every skill; keep that layout.
    for skill in (dst / "skills").glob("*") if (dst / "skills").is_dir() else []:
        scripts = skill / "scripts"
        if not any(scripts.glob("*.py")):
            scripts.mkdir(exist_ok=True)
            (scripts / ".gitkeep").write_text("")


DAMAGED_TEMPLATE = ("PACK_DAMAGED: this candidate document could not be unpacked into files ({reason}). "
                    "It has no task placeholders, so the common rollout refuses it before any model call.\n")


def unpack_to_dir(doc: str, dst: Path) -> str | None:
    """Materialize doc into dst. On a damaged doc, write a stub whose task_template.md has no placeholders:
    the common adapter then scores every rollout 0 as a candidate error, before any LLM call, and the full
    evaluation is still debited from R (same path as any template-breaking candidate). Returns the reason."""
    files, err = unpack(doc)
    if err:
        write_dir({"prompt.md": "", "task_template.md": DAMAGED_TEMPLATE.format(reason=err.replace("{", "(")
                                                                               .replace("}", ")"))}, dst)
        return err
    write_dir(files, dst)
    return None


def tree_digest(d: Path) -> dict:
    import hashlib
    d = Path(d)
    return {p.relative_to(d).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(d.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def _self_check(seed: Path, tmp: Path) -> None:
    doc = pack(seed)
    assert doc.splitlines()[0] == "=== FILE: task_template.md ===", doc[:60]
    assert "=== FILE: prompt.md ===" in doc.splitlines()[-30:] or doc.rfind("=== FILE: prompt.md ===") > doc.rfind(
        "=== FILE: skills/"), "prompt.md must be last"
    assert unpack_to_dir(doc, tmp / "rt") is None
    assert tree_digest(tmp / "rt") == tree_digest(seed), "seed does not round-trip byte-identically"
    # SkillOpt's tail blocks land in prompt.md.
    from_slow = doc.rstrip() + "\n\n<!-- SLOW_UPDATE_START -->\nguidance\n<!-- SLOW_UPDATE_END -->\n"
    f, e = unpack(from_slow)
    assert e is None and f["prompt.md"].rstrip().endswith("<!-- SLOW_UPDATE_END -->")
    # A new script via the documented replace-the-prompt-marker edit.
    add = doc.replace("=== FILE: prompt.md ===", "=== FILE: skills/spreadsheet-helpers/scripts/util.py ===\n"
                      "def f(x):\n    return x\n=== FILE: prompt.md ===", 1)
    f, e = unpack(add)
    assert e is None and f["skills/spreadsheet-helpers/scripts/util.py"] == "def f(x):\n    return x\n"
    # Damaged documents.
    for bad, why in ((doc.replace("=== FILE: prompt.md ===\n", ""), "missing"),
                     ("junk\n" + doc, "before the first"),
                     (doc + "=== FILE: ../x.py ===\nx\n", "outside"),
                     (doc + "=== FILE: prompt.md ===\nx\n", "duplicate"),
                     (doc.replace("=== FILE: prompt.md ===", "== FILE: prompt.md ==", 1), "malformed"),
                     (doc.replace("\n=== FILE: prompt.md ===", " === FILE: prompt.md ===", 1), "mid-line")):
        f, e = unpack(bad)
        assert f is None and why in e, (why, e)
    assert unpack_to_dir("junk", tmp / "bad") and "{" not in (tmp / "bad" / "task_template.md").read_text()
    print("skillopt_pack self-check: OK", flush=True)


if __name__ == "__main__":
    import sys
    import tempfile
    seed = Path(sys.argv[1])
    with tempfile.TemporaryDirectory(dir=sys.argv[2] if len(sys.argv) > 2 else None) as t:
        _self_check(seed, Path(t))
