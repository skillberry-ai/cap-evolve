"""Self-test: round-trip the WHOLE package through materialize -> apply -> validate.

One case per rule, each with a deliberately broken fixture, so every authoring
rule is a checked property instead of a claim. The end-to-end case is the point
of the capability: apply() CREATES a new bundled script, materialize() shows it as
a component, and validate() runs its self-check.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

import abstract
import token_report
import trigger_eval

GOOD = ("---\nname: demo-skill\n"
        "description: Do a thing. Use when the user wants the thing done.\n---\n"
        "# Demo\nBody.\n")


def _pkg(d: Path, skill_md: str = GOOD) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(skill_md, encoding="utf-8")
    return d


def main() -> int:
    report = {"skill": "skill-package", "ok": False, "problems": [], "notes": []}
    fail = report["problems"].append
    note = report["notes"].append

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # --- the whole package is materialized (SKILL.md + refs + scripts + assets)
        cap = _pkg(root / "full")
        (cap / "references").mkdir()
        (cap / "references" / "deep.md").write_text("# Deep\n", encoding="utf-8")
        (cap / "scripts").mkdir()
        (cap / "scripts" / "helper.py").write_text("print(1)\n", encoding="utf-8")
        (cap / "assets").mkdir()
        (cap / "assets" / "tpl.html").write_text("<p>x</p>\n", encoding="utf-8")
        (cap / "assets" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 40)
        parts = abstract.materialize(cap)
        missing = [k for k in ("SKILL.md", "references/deep.md", "scripts/helper.py",
                               "assets/tpl.html", "assets/logo.png") if k not in parts]
        if missing:
            fail(f"materialize missed package components: {missing}")
        if "binary asset" not in parts.get("assets/logo.png", ""):
            fail("a binary asset must be inventoried as a stub, not inlined")
        note("materialize exposes SKILL.md + references + scripts + assets")

        # --- a valid package passes
        v = abstract.validate(_pkg(root / "ok"))
        if not v["ok"]:
            fail(f"valid skill rejected: {v['problems']}")

        # --- frontmatter: bad name / XML tag in name
        if abstract.validate(_pkg(root / "n1", "---\nname: Bad_Name\ndescription: x\n---\n#x\n"))["ok"]:
            fail("invalid name not rejected")
        if abstract.validate(_pkg(root / "n2", "---\nname: bad-<tag>\n"
                                  "description: Do it. Use when needed.\n---\n#x\n"))["ok"]:
            fail("XML tag in name not rejected")

        # --- soft lints fire on a ONE-LINE description
        w = " ".join(abstract.validate(_pkg(
            root / "l1", "---\nname: lint-demo\n"
            "description: I can help. ALWAYS use when the user wants it.\n---\n#x\n"))["warnings"])
        if "third person" not in w or "over-triggers" not in w:
            fail(f"POV/all-caps lints did not fire: {w!r}")

        # --- ... and on a FOLDED (block scalar) description, which used to bypass them
        folded = abstract.validate(_pkg(
            root / "l2", "---\nname: lint-folded\ndescription: >\n"
            "  I can help with things.\n  ALWAYS use when the user wants it.\n---\n#x\n"))
        wf = " ".join(folded["warnings"])
        if "third person" not in wf or "over-triggers" not in wf:
            fail(f"block-scalar description bypassed the lints: {folded}")
        note("block-scalar (`description: >`) frontmatter is parsed and linted")

        # --- body budget is enforced, not merely advised
        big = abstract.validate(_pkg(root / "big", GOOD + "line\n" * 600))
        if big["ok"] or not any("lines" in p for p in big["problems"]):
            fail(f"a 600-line body must be a hard problem: {big}")

        # --- references: nested pointer, orphan, fake TOC
        cap = _pkg(root / "refs", GOOD + "See [a](references/a.md).\n")
        (cap / "references").mkdir()
        (cap / "references" / "a.md").write_text("# A\nSee [b](references/b.md)\n", encoding="utf-8")
        (cap / "references" / "b.md").write_text("# B\n", encoding="utf-8")
        (cap / "references" / "long.md").write_text(
            "# L\n" + "orientation prose that pushes the TOC out of the window\n" * 30 +
            "## Contents\n- [A](#a)\n- [B](#b)\n- [C](#c)\n" + "x\n" * 400,
            encoding="utf-8")   # a real TOC, but behind a preamble -> still warns
        w = " ".join(abstract.validate(cap)["warnings"])
        for want, label in (("one level deep", "nested reference pointer"),
                            ("orphan", "orphan reference"),
                            ("table of contents", "missing TOC in a long reference")):
            if want not in w:
                fail(f"{label} not warned: {w!r}")
        note("reference structure: nested pointers, orphans, missing TOC all warn")

        # --- broken link the body points at
        if abstract.validate(_pkg(root / "bl", GOOD + "See [x](references/gone.md).\n"))["ok"]:
            fail("a broken reference link must be a hard problem")

        # --- scripts: a syntax error is a hard problem
        cap = _pkg(root / "badpy")
        (cap / "scripts").mkdir()
        (cap / "scripts" / "x.py").write_text("def broken(:\n", encoding="utf-8")
        v = abstract.validate(cap)
        if v["ok"] or not any("does not compile" in p for p in v["problems"]):
            fail(f"a bundled script that does not compile must fail validation: {v}")

        # --- scripts: stub body + missing self-check warn
        cap = _pkg(root / "stub")
        (cap / "scripts").mkdir()
        (cap / "scripts" / "s.py").write_text('"""todo."""\n...\n', encoding="utf-8")
        w = " ".join(abstract.validate(cap)["warnings"])
        if "no real body" not in w or "--self-check" not in w:
            fail(f"stub/self-check warnings did not fire: {w!r}")

        # --- scripts: a FAILING declared self-check is a hard problem
        cap = _pkg(root / "failing")
        (cap / "scripts").mkdir()
        (cap / "scripts" / "f.py").write_text(
            "import sys\nif '--self-check' in sys.argv:\n"
            "    print('boom', file=sys.stderr); sys.exit(1)\n", encoding="utf-8")
        v = abstract.validate(cap)
        if v["ok"] or not any("--self-check failed" in p for p in v["problems"]):
            fail(f"a failing script self-check must fail validation: {v}")

        # --- apply(): path traversal is refused, not written
        cap = _pkg(root / "esc")
        r = abstract.apply(cap, [{"file": "../escaped.txt", "op": "set", "text": "pwned"}])
        if r["changed"] or not r["refused"] or (root / "escaped.txt").exists():
            fail(f"apply must refuse an edit escaping the capability dir: {r}")

        # --- apply(): the action policy gates a script edit
        cap = _pkg(root / "policy")
        (cap / "policy.json").write_text(json.dumps({"allow": ["body", "reference", "add"]}),
                                        encoding="utf-8")
        r = abstract.apply(cap, [{"file": "scripts/no.py", "op": "set", "text": "x=1\n"}])
        if r["changed"] or "not allowed by policy" not in json.dumps(r["refused"]):
            fail(f"a script edit must be refusable by policy: {r}")
        note("apply() contains writes to the package and honors the action policy")

        # --- END TO END: apply() CREATES a bundled script, it materializes as a
        #     component, and validate() runs its self-check.
        cap = _pkg(root / "e2e", GOOD + "Run [the helper](scripts/helper.py).\n")
        script = ("import sys\n\n"
                  "def normalize(s):\n    return ' '.join(str(s).split()).lower()\n\n"
                  'if __name__ == "__main__":\n'
                  "    if '--self-check' in sys.argv:\n"
                  "        assert normalize('  A  B ') == 'a b'\n"
                  "        print('ok')\n")
        r = abstract.apply(cap, [{"file": "scripts/helper.py", "op": "set", "text": script}])
        if "scripts/helper.py" not in r["changed"]:
            fail(f"apply did not create the new bundled script: {r}")
        if "scripts/helper.py" not in abstract.materialize(cap):
            fail("a newly created script must appear as a component")
        v = abstract.validate(cap)
        checked = [s for s in v["scripts"] if s["file"] == "scripts/helper.py"]
        if not v["ok"]:
            fail(f"the created script package must validate: {v['problems']}")
        if not checked or checked[0].get("self_check") != "ran" or not checked[0].get("ok"):
            fail(f"the created script's self-check did not run and pass: {v['scripts']}")
        note("end-to-end: optimizer-created script -> component -> self-check ran and passed")

        # --- reporters
        tr = token_report.report(cap)
        if "body_tokens" not in tr or "over_budget" not in tr:
            fail(f"token_report missing budget fields: {tr}")
        if not tr.get("scripts") or tr.get("scripts_context_cost") != 0:
            fail(f"token_report must inventory scripts with context_cost 0: {tr}")
        if trigger_eval.main(["--self-check"]) != 0:
            fail("trigger_eval --self-check failed")
        note("token_report inventories scripts; trigger_eval self-check passes")

    report["ok"] = not report["problems"]
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
