#!/usr/bin/env python3
"""Mechanical consistency checks for a single strategy's epic decomposition.

Usage:
    python3 check_decomposition.py <STRAT_ID> [--root DIR]
    python3 check_decomposition.py --self-check

Run from the pipeline workspace root (or pass --root). Reads:
    artifacts/strat-tasks/<ID>.md            (strategy frontmatter)
    artifacts/epic-tasks/<ID>-decomposition.md
    artifacts/epic-tasks/<ID>-E*.md          (main-plan and -BRANCH-<letter>- epics)

Prints one FINDING block per defect and exits 1; exits 0 when clean.
Every finding names the file, the defect class, and the concrete fix, so the
fix is always actionable: edit the named file as described and re-run.

Checked defect classes (all derived from the review rubric):
    docs-priority   docs-authoring epic priority must derive from the strategy
                    Jira priority (Critical->P0, Major->P1, else P2)
    gating-ac       a rollout gate named in an epic's Scope (feature flag,
                    config gate, toggle) must have a matching AC
    spec-content    a spec/format epic must not produce real instances of a
                    sibling content epic's deliverable (validation stub only)
    structure       dependencies resolving to nonexistent epics, branch files
                    missing branch/gated_by, main-plan epics depending on
                    branch epics, epic_count not matching the files on disk,
                    missing per-epic ai-signals rationale files, epic bodies
                    referencing sibling epics by draft ID
"""

import argparse
import glob
import os
import re
import sys
import tempfile

# ---------------------------------------------------------------------------
# Frontmatter / body parsing (dependency-free; handles the subset of YAML the
# pipeline writes: flat keys, dotted keys, one nested dict, dash lists, and
# comma-separated or bracketed lists).
# ---------------------------------------------------------------------------

def parse_frontmatter(text):
    """Return (fm, body) where fm maps top-level keys to str or [str]."""
    fm = {}
    body = text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return fm, body
    fm_text, body = m.group(1), m.group(2)
    current_key = None
    for line in fm_text.split("\n"):
        if not line.strip() or line.strip().startswith("#"):
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and current_key:
            # list item under the current key (e.g. dependencies:)
            if not isinstance(fm.get(current_key), list):
                fm[current_key] = []
            item = stripped[2:].strip().strip("\"'")
            if item:
                fm[current_key].append(item)
            continue
        km = re.match(r"^([A-Za-z_][\w]*):\s*(.*)$", line)
        if km and not line.startswith((" ", "\t")):
            key, val = km.group(1), km.group(2).strip()
            current_key = key
            if val == "":
                fm[key] = ""
            elif val.startswith("[") and val.endswith("]"):
                items = [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
                fm[key] = items if items else []
                current_key = None
            else:
                fm[key] = val.strip("\"'")
                current_key = None
    return fm, body


def split_sections(body):
    """Return {section_title: text} for '## Title' sections."""
    sections = {}
    parts = re.split(r"^## +(.+?)\s*$", body, flags=re.M)
    for i in range(1, len(parts) - 1, 2):
        sections[parts[i].strip()] = parts[i + 1]
    return sections


def as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [v for v in value if v]
    if isinstance(value, str):
        if value.strip().startswith("["):
            return [v.strip().strip("\"'") for v in value.strip()[1:-1].split(",") if v.strip()]
        return [v.strip().strip("\"'") for v in value.split(",") if v.strip()]
    return []


# ---------------------------------------------------------------------------
# Defect-class lexicons
# ---------------------------------------------------------------------------

DOCS_PRIORITY_DERIVATION = {"Critical": "P0", "Major": "P1"}
DOCS_PRIORITY_DEFAULT = "P2"

GATING_TERMS = ("feature flag", "feature-flag", "config gate", "dashboard config",
                "toggle", "gating")

SPEC_WORDS = re.compile(r"\b(defin\w*|specif\w+|schema|format|standard)\b", re.I)
PROD_VERBS = re.compile(
    r"\b(produce|produces|produced|author|authors|create|creates|created|"
    r"write|writes|build|builds|develop|develops|deliver|delivers|publish|"
    r"publishes)\b([^.\n]{0,90})", re.I)
# A produced-noun window ends at a preposition that introduces purpose/means
# ("create a workbench WITH the tutorial's image" produces a workbench, not a
# tutorial) — the noun after the preposition is not the thing being produced.
STOP_PREPS = re.compile(r"\b(with|for|from|in|into|using|via|against|onto|to)\b", re.I)
CONTENT_NOUNS = re.compile(r"\b(tutorial|notebook|guide|walkthrough|example|sample|demo)s?\b", re.I)
AUTHOR_VERBS = re.compile(r"\b(author|authors|authored|authoring|write|writes|writing|curate|curates|curated|curating)\b", re.I)


def noun_stems(text):
    return {m.group(1).lower().rstrip("s") for m in CONTENT_NOUNS.finditer(text)}


def produced_content_nouns(text):
    """Content nouns that some production verb in `text` actually produces."""
    produced = set()
    for m in PROD_VERBS.finditer(text):
        window = m.group(0)
        stop = STOP_PREPS.search(window[len(m.group(1)):])
        if stop:
            window = window[:len(m.group(1)) + stop.start()]
        produced |= noun_stems(window)
    return produced


# ---------------------------------------------------------------------------
# Workspace model
# ---------------------------------------------------------------------------

class Workspace(object):
    def __init__(self, root, strat_id):
        self.root = root
        self.strat_id = strat_id
        self.findings = []
        self.strategy_fm = {}
        self.epics = {}        # epic_id -> dict (main-plan and branch epics)
        self.main_ids = []
        self.branch_ids = []
        self.decomp_fm = {}

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def finding(self, cls, file_ref, message):
        self.findings.append((cls, file_ref, message))

    def load(self):
        strat_path = self.path("artifacts", "strat-tasks", "%s.md" % self.strat_id)
        if not os.path.isfile(strat_path):
            self.finding("missing-input", strat_path,
                         "strategy file not found — cannot run consistency checks")
            return False
        with open(strat_path) as fh:
            self.strategy_fm, _ = parse_frontmatter(fh.read())

        decomp_path = self.path("artifacts", "epic-tasks", "%s-decomposition.md" % self.strat_id)
        if os.path.isfile(decomp_path):
            with open(decomp_path) as fh:
                self.decomp_fm, _ = parse_frontmatter(fh.read())

        pattern = self.path("artifacts", "epic-tasks", "%s-E*.md" % self.strat_id)
        for epic_path in sorted(glob.glob(pattern)):
            base = os.path.basename(epic_path)
            if base.endswith("-ai-signals.md") or base.endswith("-decomposition.md"):
                continue
            with open(epic_path) as fh:
                fm, body = parse_frontmatter(fh.read())
            epic_id = fm.get("epic_id") or base[:-3]
            sections = split_sections(body)
            epic = {
                "path": epic_path,
                "base": base,
                "fm": fm,
                "body": body,
                "scope": sections.get("Scope", ""),
                "acs": sections.get("Acceptance Criteria", ""),
                "title": fm.get("title", ""),
                "priority": fm.get("priority", ""),
                "type": fm.get("type", ""),
                "implementation_type": fm.get("implementation_type") or "",
                "dependencies": as_list(fm.get("dependencies")),
                "is_branch": "-BRANCH-" in base,
                "branch": fm.get("branch") or "",
                "gated_by": fm.get("gated_by") or "",
            }
            self.epics[epic_id] = epic
            (self.branch_ids if epic["is_branch"] else self.main_ids).append(epic_id)
        return True

    # -- checks --------------------------------------------------------------

    def check_docs_priority(self):
        strat_priority = (self.strategy_fm.get("priority") or "").strip()
        expected = DOCS_PRIORITY_DERIVATION.get(strat_priority, DOCS_PRIORITY_DEFAULT)
        for eid, epic in sorted(self.epics.items()):
            if epic["implementation_type"] != "docs-authoring":
                continue
            if epic["priority"] != expected:
                self.finding(
                    "docs-priority", epic["base"],
                    "%s is a docs-authoring epic with priority=%s, but the strategy's "
                    "Jira priority is %r — the docs-authoring priority exception derives "
                    "Critical->P0, Major->P1, Normal/Minor/missing->P2. Set priority=%s "
                    "(do not copy the HLR's own priority label)." %
                    (eid, epic["priority"] or "(unset)", strat_priority or "(missing)",
                     expected))

    def check_gating_ac(self):
        for eid, epic in sorted(self.epics.items()):
            scope_l = epic["scope"].lower()
            ac_l = epic["acs"].lower()
            named = [t for t in GATING_TERMS if t in scope_l]
            if named and not any(t in ac_l for t in GATING_TERMS):
                self.finding(
                    "gating-ac", epic["base"],
                    "%s's Scope names a rollout gate (%s) but no acceptance criterion "
                    "verifies the gated behavior. Add an AC that tests the gate (e.g. "
                    "\"Given the feature flag is disabled, the surface is not visible; "
                    "given it is enabled, <behavior> holds\")." % (eid, ", ".join(named)))

    def check_spec_content_overlap(self):
        # Content epics: the TITLE states their work is authoring content
        # deliverables (docs-authoring epics are their own work-product class
        # and are excluded).
        content_nouns_by_epic = {}
        for eid, epic in sorted(self.epics.items()):
            if epic["implementation_type"] == "docs-authoring":
                continue
            title = epic["title"] or ""
            if AUTHOR_VERBS.search(title):
                stems = noun_stems(title)
                if stems:
                    content_nouns_by_epic[eid] = stems
        # Spec epics must not produce real instances of those deliverables.
        for eid, epic in sorted(self.epics.items()):
            if not SPEC_WORDS.search(epic["scope"]):
                continue
            produced = produced_content_nouns(epic["scope"]) | produced_content_nouns(epic["acs"])
            if not produced:
                continue
            overlaps = {}
            for other, stems in sorted(content_nouns_by_epic.items()):
                if other == eid:
                    continue
                hit = produced & stems
                if hit:
                    overlaps[other] = hit
            if overlaps:
                detail = "; ".join("%s authors %s" % (o, sorted(s))
                                   for o, s in sorted(overlaps.items()))
                self.finding(
                    "spec-content", epic["base"],
                    "%s defines a format/spec but its Scope/ACs produce real content "
                    "deliverable(s) that a sibling epic authors (%s) — a boundary "
                    "overlap. Restate the example as a minimal format-validation stub "
                    "(a fixture that exercises the format, not a usable deliverable), "
                    "or explicitly subsume the example into the authoring epic's scope." %
                    (eid, detail))

    def check_structure(self):
        all_ids = set(self.epics)
        # 1. every dependency resolves to an existing epic file
        for eid, epic in sorted(self.epics.items()):
            for dep in epic["dependencies"]:
                if dep not in all_ids:
                    self.finding(
                        "structure", epic["base"],
                        "%s depends on %r, which has no epic file — the pipeline drops "
                        "unresolvable dependencies. Fix the dependency (or create the "
                        "missing epic file)." % (eid, dep))
        # 2. branch metadata
        for eid, epic in sorted(self.epics.items()):
            if not epic["is_branch"]:
                continue
            if not epic["branch"] or not epic["gated_by"]:
                self.finding(
                    "structure", epic["base"],
                    "branch file %s must set both `branch` (the outcome letter, matching "
                    "the filename) and `gated_by` (the main-plan Investigation epic_id) "
                    "— the pipeline silently drops branch files missing either." % eid)
            elif epic["gated_by"] not in epic["dependencies"]:
                self.finding(
                    "structure", epic["base"],
                    "branch file %s sets gated_by=%s but that epic is not in its "
                    "`dependencies` — gated_by must always be a member of dependencies." %
                    (eid, epic["gated_by"]))
        # 3. main-plan epics must not depend on branch epics
        for eid in sorted(self.main_ids):
            epic = self.epics[eid]
            for dep in epic["dependencies"]:
                if dep in self.epics and self.epics[dep]["is_branch"]:
                    self.finding(
                        "structure", epic["base"],
                        "main-plan epic %s depends on branch epic %s — branch epics are "
                        "never created as issues. Depend on (and gated_by) the gating "
                        "Investigation epic instead, or move this work into the branch." %
                        (eid, dep))
        # 4. epic_count matches the files on disk (main-plan, or main+branches)
        declared = self.decomp_fm.get("epic_count")
        if declared is not None:
            try:
                declared = int(str(declared).strip())
            except ValueError:
                declared = None
        if declared is not None:
            n_main = len(self.main_ids)
            n_all = n_main + len(self.branch_ids)
            if declared not in (n_main, n_all):
                self.finding(
                    "structure", "%s-decomposition.md" % self.strat_id,
                    "epic_count=%d but %d main-plan epic file(s) (%d including branch "
                    "files) exist — set epic_count to the number of main-plan epics "
                    "(or all epics including branches), consistently." %
                    (declared, n_main, n_all))
        # 5. per-epic ai-signals rationale files exist
        for eid, epic in sorted(self.epics.items()):
            rationale = epic["path"][:-3] + "-ai-signals.md"
            if not os.path.isfile(rationale):
                self.finding(
                    "structure", epic["base"],
                    "%s has no %s-ai-signals.md rationale file — every epic (main-plan "
                    "and branch) needs one; the artifact contract fails without it." %
                    (eid, eid))
        # 6. epic bodies must not reference sibling epics by draft ID
        for eid, epic in sorted(self.epics.items()):
            own_refs = {eid, eid.split("-")[-1] if "-E" in eid else eid}
            refs = set()
            for m in re.finditer(r"\b(RHAISTRAT-\d+-E\d{3}|E\d{3})\b", epic["body"]):
                token = m.group(0)
                if token not in own_refs:
                    refs.add(token)
            if refs:
                self.finding(
                    "structure", epic["base"],
                    "%s's body references sibling epic draft ID(s) %s — draft IDs are "
                    "meaningless in Jira. Describe the dependency in plain terms "
                    "(artifact/capability names) instead." % (eid, sorted(refs)))

    def run_all(self):
        if not self.load():
            return self.findings
        self.check_docs_priority()
        self.check_gating_ac()
        self.check_spec_content_overlap()
        self.check_structure()
        return self.findings


# ---------------------------------------------------------------------------
# Self-check: build synthetic workspaces exercising every defect class.
# ---------------------------------------------------------------------------

STRATEGY_TMPL = """---
strat_id: {sid}
title: Self-check strategy
status: Refinement Done
priority: {priority}
labels: []
---

## Problem Statement

Self-check fixture.
"""

EPIC_TMPL = """---
epic_id: {eid}
title: "{title}"
parent_strat: {sid}
component: Dashboard
team: RHOAI Dashboard
type: Implementation
priority: {priority}
dependencies: {deps}
implementation_type: {impl_type}
branch: {branch}
gated_by: {gated_by}
---

# {title}

## Description

Fixture epic.

## Scope

{scope}

## Acceptance Criteria

{acs}

## HLR Traceability

- HLR-1: fixture.
"""

DECOMP_TMPL = """---
parent_strat: {sid}
epic_count: {count}
critical_path_length: 2
decompose_complete: true
---

# Decomposition Summary

## Epic List

| ID | Title |
"""


def write_fixture(root, sid, priority, epics, epic_count=None):
    os.makedirs(os.path.join(root, "artifacts", "strat-tasks"))
    os.makedirs(os.path.join(root, "artifacts", "epic-tasks"))
    with open(os.path.join(root, "artifacts", "strat-tasks", "%s.md" % sid), "w") as fh:
        fh.write(STRATEGY_TMPL.format(sid=sid, priority=priority))
    if epic_count is not None:
        with open(os.path.join(root, "artifacts", "epic-tasks", "%s-decomposition.md" % sid), "w") as fh:
            fh.write(DECOMP_TMPL.format(sid=sid, count=epic_count))
    for spec in epics:
        eid = spec["eid"]
        content = EPIC_TMPL.format(
            eid=eid, sid=sid,
            title=spec.get("title", "Fixture epic"),
            priority=spec.get("priority", "P1"),
            deps=spec.get("deps", ""),
            impl_type=spec.get("impl_type", "null"),
            branch=spec.get("branch", "null"),
            gated_by=spec.get("gated_by", "null"),
            scope=spec.get("scope", "- Fixture scope line."),
            acs=spec.get("acs", "- Fixture AC line."))
        fname = spec.get("file") or ("%s.md" % eid)
        with open(os.path.join(root, "artifacts", "epic-tasks", fname), "w") as fh:
            fh.write(content)
        if spec.get("signals", True):
            with open(os.path.join(root, "artifacts", "epic-tasks",
                                   "%s-ai-signals.md" % eid), "w") as fh:
                fh.write("# Signals\n\n| Signal | Value | Rationale |\n|---|---|---|\n")


def run_fixture(name, expect_classes, **kwargs):
    root = tempfile.mkdtemp(prefix="chk-self-")
    sid = "RHAISTRAT-9999"
    write_fixture(root, sid, **kwargs)
    ws = Workspace(root, sid)
    findings = ws.run_all()
    got = sorted({cls for cls, _, _ in findings})
    want = sorted(expect_classes)
    ok = got == want
    print("  %-28s expect=%s got=%s %s" % (name, want, got, "OK" if ok else "FAIL"))
    return ok


def self_check():
    print("self-check: check_decomposition.py")
    results = []

    # Clean decomposition: no findings.
    results.append(run_fixture(
        "clean", [],
        priority="Major",
        epics=[
            {"eid": "RHAISTRAT-9999-E001", "title": "Define widget format",
             "scope": "- Define the widget metadata schema.\n- Validate with a minimal "
                      "format-validation stub fixture.",
             "acs": "- A stub fixture passes validation.", "priority": "P1"},
            {"eid": "RHAISTRAT-9999-E002", "title": "Widget gallery UI",
             "scope": "- Implement the gallery surface behind a feature flag.\n"
                      "- Gate the section per release plan.",
             "acs": "- Given the feature flag is disabled, the gallery is not visible.\n"
                    "- Given the feature flag is enabled, the gallery renders widgets.",
             "priority": "P0"},
        ],
        epic_count=2))

    # docs-priority: Major strategy, docs-authoring epic at P2.
    results.append(run_fixture(
        "docs-priority", ["docs-priority"],
        priority="Major",
        epics=[
            {"eid": "RHAISTRAT-9999-E001", "title": "Widget docs",
             "impl_type": "docs-authoring", "priority": "P2",
             "scope": "- Author widget documentation.",
             "acs": "- Docs technically reviewed."},
        ],
        epic_count=1))

    # gating-ac: gate named in scope, no verifying AC.
    results.append(run_fixture(
        "gating-ac", ["gating-ac"],
        priority="Normal",
        epics=[
            {"eid": "RHAISTRAT-9999-E001", "title": "Widget gallery UI",
             "scope": "- Implement the gallery surface with dashboard config gating.",
             "acs": "- The gallery renders widgets.", "priority": "P0"},
        ],
        epic_count=1))

    # spec-content: spec epic produces tutorials a sibling content epic authors.
    results.append(run_fixture(
        "spec-content", ["spec-content"],
        priority="Major",
        epics=[
            {"eid": "RHAISTRAT-9999-E001", "title": "Define widget packaging format",
             "scope": "- Define the packaging schema.\n- Produce a reference example of "
                      "a correctly packaged tutorial.",
             "acs": "- The format is specified.", "priority": "P1"},
            {"eid": "RHAISTRAT-9999-E002", "title": "Author six widget tutorials",
             "scope": "- Author six tutorials covering core journeys.",
             "acs": "- Six tutorials exist.", "priority": "P0"},
        ],
        epic_count=2))

    # structure: unresolvable dependency, branch metadata gaps, bad epic_count,
    # missing signals file, and a sibling draft-ID reference in a body.
    results.append(run_fixture(
        "structure", ["structure"],
        priority="Normal",
        epics=[
            {"eid": "RHAISTRAT-9999-E001", "title": "Widget investigation",
             "type": "Investigation",
             "scope": "- Investigate widget options per E003 guidance.",
             "acs": "- Decision recorded.", "priority": "P1"},
            {"eid": "RHAISTRAT-9999-BRANCH-A-E002",
             "file": "RHAISTRAT-9999-BRANCH-A-E002.md",
             "title": "Branch A widget work", "priority": "P1",
             "deps": "", "signals": True,
             "scope": "- Branch A scope.", "acs": "- Branch A AC."},
            {"eid": "RHAISTRAT-9999-E003", "title": "Widget build",
             "deps": "RHAISTRAT-9999-E009", "signals": False,
             "scope": "- Build widgets.", "acs": "- Widgets built.", "priority": "P1"},
        ],
        epic_count=5))

    if all(results):
        print("self-check: ALL PASS")
        return 0
    print("self-check: FAILURES")
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("strat_id", nargs="?", help="strategy ID, e.g. RHAISTRAT-1234")
    ap.add_argument("--root", default=".", help="workspace root (default: cwd)")
    ap.add_argument("--self-check", action="store_true", help="run built-in self-test")
    args = ap.parse_args(argv)

    if args.self_check:
        return self_check()
    if not args.strat_id:
        ap.error("strat_id is required (or use --self-check)")

    ws = Workspace(args.root, args.strat_id)
    findings = ws.run_all()
    if not findings:
        print("OK: no consistency findings for %s" % args.strat_id)
        return 0
    for cls, file_ref, message in findings:
        print("FINDING [%s] %s\n  %s\n" % (cls, file_ref, message))
    print("%d finding(s) for %s — fix each as described, then re-run until clean."
          % (len(findings), args.strat_id))
    return 1


if __name__ == "__main__":
    sys.exit(main())
