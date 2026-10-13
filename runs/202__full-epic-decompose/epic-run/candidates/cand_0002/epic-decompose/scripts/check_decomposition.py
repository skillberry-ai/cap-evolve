#!/usr/bin/env python3
"""Boundary self-check for epic decompositions.

Usage:
    python3 check_decomposition.py <STRATEGY_ID> [--epic-dir artifacts/epic-tasks]
    python3 check_decomposition.py --self-check

Two checks, each finding naming the file, the epic, the defect, and the fix:

  spec-content  A format/schema/standard-defining epic whose Scope or Acceptance
                Criteria promise authoring a real content instance (a "reference
                example/tutorial/notebook/sample/guide/walkthrough") while a
                sibling epic authors that same content type. Two teams then
                author the same deliverable — a boundary overlap.
                Fix: restate the claim as a format-validation stub (minimal
                synthetic fixture) or subsume the reference instance into the
                content epic. Never merge the two epics.

  gating-ac     An epic whose Scope names a rollout gate (feature flag, config
                gate, toggle, "behind a flag") but whose Acceptance Criteria do
                not verify the gated behavior. A gate named in scope with no
                verifying AC is an untestable claim.
                Fix: add an AC (gate disabled -> feature hidden/inert;
                gate enabled -> feature renders and functions).

Excluded by design (verified non-defect classes):
  - docs-authoring epics (documenting a format is a sanctioned work product);
  - human-approval gates, review boards, sign-offs, and CI gating checks
    (work items, not rollout gates of the feature being built).

Exit codes: 0 = no findings, 1 = findings, 2 = usage error.
The check is advisory and fail-open: fix findings when printed, but never block
decomposition completion on a script error.
"""

import glob
import os
import re
import sys
import tempfile

# A real-instance authoring claim inside a format/spec epic ("reference ...").
REF_CLAIM = re.compile(
    r"reference\s+(example|tutorial|notebook|sample|guide|walkthrough|"
    r"implementation|instance)",
    re.IGNORECASE,
)
# A content-authoring claim in a sibling epic (verb + content noun, one line).
AUTHOR_CLAIM = re.compile(
    r"(author|curat|writ|creat|produc|publish)\w*[^.\n]{0,80}"
    r"(tutorial|notebook|sample notebook|curated example|walkthrough|guide)",
    re.IGNORECASE,
)
# Rollout-gate vocabulary in a Scope section.
GATE_SCOPE = re.compile(
    r"feature[ -]?flag|config\s+gat|dashboard\s+config|toggle|behind a flag|"
    r"flag-gated|gating for",
    re.IGNORECASE,
)
# Gate-verification vocabulary anywhere in the Acceptance Criteria section.
GATE_AC = re.compile(r"flag|gat(e|ing)|toggl|enabl|disabl", re.IGNORECASE)

CONTENT_NOUNS = (
    "tutorial", "notebook", "example", "sample", "guide", "walkthrough",
    "instance", "implementation",
)


def singular(noun):
    noun = noun.lower()
    return noun[:-1] if noun.endswith("s") else noun


def claim_noun(text, pos):
    """Return the content noun nearest after position pos in text, if any."""
    tail = text[pos:pos + 200].lower()
    for noun in CONTENT_NOUNS:
        idx = tail.find(noun)
        if idx != -1:
            return singular(noun)
    return None


class Epic:
    def __init__(self, path):
        self.path = path
        text = open(path, encoding="utf-8").read()
        parts = text.split("---")
        self.frontmatter = parts[1] if len(parts) >= 3 else ""
        self.body = "---".join(parts[2:]) if len(parts) >= 3 else text
        self.epic_id = self._fm("epic_id") or os.path.basename(path)
        self.title = self._fm("title") or ""
        self.implementation_type = self._fm("implementation_type")
        self.scope = self._section("Scope")
        self.acs = self._section("Acceptance Criteria")

    def _fm(self, key):
        m = re.search(r"^%s:\s*(.+?)\s*$" % re.escape(key), self.frontmatter,
                      re.MULTILINE)
        return m.group(1) if m else None

    def _section(self, name):
        m = re.search(r"## %s\n(.*?)(?=\n## |\Z)" % re.escape(name), self.body,
                      re.DOTALL)
        return m.group(1) if m else ""

    @property
    def is_docs(self):
        return self.implementation_type == "docs-authoring"

    @property
    def scan_text(self):
        return self.scope + "\n" + self.acs


def load_epics(strategy_id, epic_dir):
    paths = []
    for pattern in ("%s-E*.md" % strategy_id,):
        paths.extend(glob.glob(os.path.join(epic_dir, pattern)))
    paths = [p for p in sorted(set(paths))
             if not p.endswith("-ai-signals.md")]
    return [Epic(p) for p in paths]


def check_spec_content(epics):
    """Flag non-docs epics that claim to author a real content instance which
    a sibling non-docs epic also authors (format/content boundary overlap)."""
    findings = []
    candidates = [e for e in epics if not e.is_docs]
    for a in candidates:
        claim = REF_CLAIM.search(a.scan_text)
        if not claim:
            continue
        noun_a = claim_noun(a.scan_text, claim.end()) or singular(
            claim.group(1))
        # Prefer a sibling whose title carries the authoring claim.
        partner = None
        for prefer_title in (True, False):
            for b in candidates:
                if b.epic_id == a.epic_id:
                    continue
                hay = b.title if prefer_title else (b.title + "\n" + b.scope)
                m = AUTHOR_CLAIM.search(hay)
                if m:
                    noun_b = singular(m.group(2).split()[-1])
                    if noun_a == noun_b or noun_a.startswith(noun_b) or \
                            noun_b.startswith(noun_a):
                        partner = (b, m.group(0))
                        break
            if partner:
                break
        if partner:
            b, phrase = partner
            findings.append(
                "FINDING [spec-content] %s (%s): authors a real content "
                "instance (\"%s\") that %s also authors (\"%s\"). Fix: "
                "restate as a format-validation stub (minimal synthetic "
                "fixture exercising the schema) or subsume the reference "
                "instance into the content epic — do NOT merge the epics."
                % (a.epic_id, os.path.basename(a.path), claim.group(0),
                   b.epic_id, phrase))
    return findings


def check_gating_ac(epics):
    """Flag non-docs epics naming a rollout gate in Scope with no gate
    verification in their Acceptance Criteria."""
    findings = []
    for e in epics:
        if e.is_docs:
            continue
        m = GATE_SCOPE.search(e.scope)
        if m and not GATE_AC.search(e.acs):
            findings.append(
                "FINDING [gating-ac] %s (%s): rollout gate named in scope "
                "(\"%s\") but no acceptance criterion verifies the gated "
                "behavior. Fix: add an AC — gate disabled -> feature hidden/"
                "inert; gate enabled -> feature renders and functions."
                % (e.epic_id, os.path.basename(e.path), m.group(0)))
    return findings


def run_checks(epics):
    return check_spec_content(epics) + check_gating_ac(epics)


def _write(dirpath, name, text):
    path = os.path.join(dirpath, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


EPIC_TMPL = """---
epic_id: %s
title: %s
parent_strat: T1
component: C
team: T
type: Implementation
priority: P0
dependencies: []
implementation_type: %s
---

# %s

## Description

%s

## Scope

%s

## Acceptance Criteria

%s

## HLR Traceability

- HLR-1 (P0): x
"""


def _fixture(dirpath, name, eid, title, impl_type, desc, scope, acs):
    return _write(dirpath, name, EPIC_TMPL % (eid, title, impl_type, title,
                                              desc, scope, acs))


def self_check():
    """Run both checks against synthetic fixtures with known outcomes."""
    failures = []

    def expect(label, got, want):
        ok = got == want
        print("%s %s (findings=%d)" % ("PASS" if ok else "FAIL", label,
                                       len(got)))
        if not ok:
            failures.append(label)
            print("  expected %d findings, got: %s" % (len(want), got))

    with tempfile.TemporaryDirectory() as tmp:
        # 1. Clean decomposition: format epic validates with a stub, content
        #    epic authors instances, gate in scope has a gate AC.
        _fixture(tmp, "T1-E001.md", "T1-E001", "Define widget packaging format",
                 "null", "Defines the format.",
                 "- Define the metadata schema.\n- Validate the format with a "
                 "minimal stub widget fixture (synthetic metadata).\n- Follow "
                 "the feature flag gating for the new section.",
                 "- A written specification exists.\n- The stub fixture passes "
                 "validation.\n- With the feature flag disabled the section is "
                 "hidden; enabled it renders.")
        _fixture(tmp, "T1-E002.md", "T1-E002", "Author the curated widget guides",
                 "null", "Authors the guides.",
                 "- Author six curated guides, one per journey.",
                 "- Six guides exist and pass the format validation.")
        expect("clean decomposition", run_checks(load_epics("T1", tmp)), [])

        # 2. Spec/content overlap: format epic promises a real reference
        #    instance; sibling authors the same content type.
        _fixture(tmp, "T2-E001.md", "T2-E001", "Define guide packaging format",
                 "null", "Defines the format.",
                 "- Define the metadata schema.\n- Produce a reference example "
                 "of a correctly packaged guide and a specification document.",
                 "- At least one reference guide is packaged per the spec.")
        _fixture(tmp, "T2-E002.md", "T2-E002", "Author six curated guides",
                 "null", "Authors the guides.",
                 "- Author six curated guides, one per journey.",
                 "- Six guides exist.")
        got = run_checks(load_epics("T2", tmp))
        expect("spec-content overlap", [f.startswith(
            "FINDING [spec-content] T2-E001") for f in got], [True])

        # 3. Gating gap: gate named in scope, no verifying AC.
        _fixture(tmp, "T3-E001.md", "T3-E001", "Build the gallery surface",
                 "null", "Builds the surface.",
                 "- Implement the section behind a feature flag per the "
                 "dashboard config.",
                 "- The section renders curated items.")
        got = run_checks(load_epics("T3", tmp))
        expect("gating-ac gap", [f.startswith(
            "FINDING [gating-ac] T3-E001") for f in got], [True])

        # 4. Exclusions: docs-authoring epic with both patterns is not flagged.
        _fixture(tmp, "T4-E001.md", "T4-E001", "Document the format",
                 "docs-authoring", "Documents it.",
                 "- Publish a reference example of a packaged guide; describe "
                 "the feature flag gating.",
                 "- Docs cover the format.")
        expect("docs-authoring excluded", run_checks(load_epics("T4", tmp)), [])

        # 5. Gate AC present elsewhere in ACs (e.g. "enabled by default")
        #    does not fire.
        _fixture(tmp, "T5-E001.md", "T5-E001", "Enable the management UI",
                 "null", "Ships it.",
                 "- Ship the management UI enabled by default behind the "
                 "dashboard config toggle.",
                 "- The management UI is enabled by default and functional.")
        expect("gate AC present", run_checks(load_epics("T5", tmp)), [])

    if failures:
        print("SELF-CHECK FAILED: %s" % ", ".join(failures))
        return 1
    print("SELF-CHECK PASSED (5 fixtures)")
    return 0


def main(argv):
    if "--self-check" in argv:
        return self_check()
    args = [a for a in argv[1:] if not a.startswith("--")]
    epic_dir = "artifacts/epic-tasks"
    for a in argv[1:]:
        if a.startswith("--epic-dir="):
            epic_dir = a.split("=", 1)[1]
    if not args:
        print("usage: check_decomposition.py <STRATEGY_ID> "
              "[--epic-dir=DIR] | --self-check", file=sys.stderr)
        return 2
    strategy_id = args[0]
    if not os.path.isdir(epic_dir):
        print("OK: epic dir %s not found — nothing to check" % epic_dir)
        return 0
    epics = load_epics(strategy_id, epic_dir)
    if not epics:
        print("OK: no epic files found for %s" % strategy_id)
        return 0
    findings = run_checks(epics)
    for f in findings:
        print(f)
    if findings:
        print("%d boundary finding(s) — apply the fix each finding states, "
              "then re-run." % len(findings))
        return 1
    print("OK: no boundary findings (%d epics checked)" % len(epics))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
