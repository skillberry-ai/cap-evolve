#!/usr/bin/env python3
"""Deterministic pre-submit validation for one strategy's epic decomposition.

Checks the mechanically decidable contract rules that the downstream judges
and submit.py enforce — the ones an LLM step can silently get wrong while the
decomposition still looks good:

  1. Epic body sections: every epic file must carry headings covering
     Description, Scope, Acceptance Criteria, and HLR Traceability (matched on
     heading text at any level, exactly like the artifact contract).
  2. Component vocabulary: every epic's `component` frontmatter value must be
     verbatim in .context/rhai-components.txt (submit.py silently strips
     unknown names, leaving the Jira epic component-less).
  3. Rule 11 (docs-last): every docs-authoring epic must be blocked, directly
     or transitively, by every main-plan Implementation epic that is not
     itself docs-authoring.
  4. Priority inheritance: an epic that directly or transitively enables a P0
     epic must itself be P0 (docs-authoring epics are exempt; branch epics
     are conditional alternatives and out of scope).
  5. Implementation-type parallelism (Rules 7/8/10): no `dependencies` edge,
     in either direction, between a license-validation and a repo-onboarding
     epic (Rule 7), a license-validation and a konflux-onboarding epic
     (Rule 8), or a konflux-onboarding and a general implementation epic
     (Rule 10) — these pairs must run in parallel; any real coupling is an
     acceptance-criterion gate, never a DAG edge. Edges into a docs-authoring
     epic are exempt (Rule 11 requires them).
  6. Epic-size overage triggers (summary-side): a decomposition summary that
     acknowledges an epic kept above the ~2-week guideline must record a
     concrete re-split trigger somewhere in the summary — a bare
     "flagged for planning awareness only" note is an unresolved defect.
  7. On-matrix bundling record (summary-side): when the summary acknowledges a
     lower-priority HLR bundled into a higher-priority epic, the HLR
     Traceability Matrix row itself must carry the `bundled` flag with its
     rationale — a rationale that lives only in prose outside the matrix reads
     as an unanalyzed priority collapse.

Exit 0 with "OK" when clean; exit 1 with one line per violation otherwise.

Usage:
    python3 skills/epic-decompose/scripts/validate_decomposition.py <STRAT_ID> \
        [--artifacts-dir artifacts] [--components .context/rhai-components.txt]
    python3 skills/epic-decompose/scripts/validate_decomposition.py --self-check
"""

import argparse
import os
import re
import sys

import yaml

SECTIONS = [("Description", ("description",)),
            ("Scope", ("scope",)),
            ("Acceptance Criteria", ("acceptance criteria",)),
            ("HLR Traceability", ("hlr traceability", "traceability"))]

PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2}

IT_ENUM = ("docs-authoring", "konflux-onboarding", "license-validation",
           "repo-onboarding")

# Pairs of implementation kinds that must run in parallel (no DAG edge either
# way) — parity with the implementation_type_rules judge.
PARALLEL_PAIRS = {
    frozenset(("license-validation", "repo-onboarding")): "Rule 7",
    frozenset(("license-validation", "konflux-onboarding")): "Rule 8",
    frozenset(("konflux-onboarding", "general")): "Rule 10",
}

FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?\n)---\s*\n', re.DOTALL)

# ─── check 6: epic-size overage triggers (summary-side) ───────────────────────
# A segment "acknowledges a kept overage" when it says the work sits above the
# size guideline. Negations ("stays within the guideline") never acknowledge.
OVERAGE_ACK = re.compile(
    r'\b(?:above|exceeds?|exceeded|over|beyond|larger than|'
    r'at (?:or )?(?:slightly )?above|at the upper (?:end|bound) of)\s*'
    r'[^.\n]{0,80}?\b(?:guideline|2-week|two-week|one[- ]sprint|'
    r'epic[- ]size|size guideline)\b', re.I)
OVERAGE_NEG = re.compile(
    r'\b(?:within|stays? within|does not exceed|no epic (?:exceeds|is above)|'
    r'under)\s*[^.\n]{0,60}?\b(?:guideline|2-week|size)\b', re.I)
# A re-split trigger is a conditional planning statement naming when to split.
RESPLIT_TRIG = re.compile(
    r'\bre-?split\b|'
    r'\bsplit\b[^.\n]{0,120}\bif\b|'
    r'\bif\b[^.\n]{0,120}\b(?:outgrows|exceeds the|finds (?:materially )?more|'
    r'grows beyond|expands beyond)\b', re.I)

# ─── check 7: on-matrix bundling record (summary-side) ────────────────────────
# Fires only when the summary itself acknowledges a bundling DECISION (the
# word "bundled" near an HLR id or a P0/P1/P2 label) in prose outside the
# matrix, while no matrix row carries the flag.
BUNDLE_ACK = re.compile(
    r'\bbundl\w*\b[^.\n]{0,100}\b(?:P[012]\b|HLR|priority)|'
    r'\b(?:HLR|P[12]\b|priority)[^.\n]{0,100}\bbundl\w*\b', re.I)
# An off-matrix bundling note that itself carries the why-not-splittable
# rationale is a compliant record; only a bare pointer is a violation.
# ("same component/team" is deliberately NOT a rationale marker — it restates
# the default boundary rule, not why the HLR is not separately schedulable.)
BUNDLE_RATIONALE = re.compile(
    r'\b(?:because|since|shares?|shared|extends? the same|thin layer|'
    r'same (?:call|report|data|surface|file|ui|endpoint|code|site)|'
    r'not (?:independently|separately) (?:deferrable|schedulable)|'
    r'double-touch|two (?:epics|passes|audits)|'
    r'duplicat\w+ the (?:audit|work|pass)|fragment\w+)\b', re.I)
MATRIX_ROW_BUNDLED = re.compile(r'^\s*\|.*\bbundl', re.I | re.M)
MATRIX_RE = re.compile(r'#+\s*HLR Traceability Matrix.*?(?=\n#|\Z)', re.S)


def read_frontmatter(path):
    """Return (frontmatter dict, body string) for a markdown file."""
    with open(path, encoding="utf-8") as f:
        content = f.read()
    m = FRONTMATTER_RE.match(content)
    if not m:
        return {}, content
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError:
        return {}, content
    if not isinstance(data, dict):
        return {}, content
    return data, content[m.end():]


def body_headings(body):
    heads = []
    for hm in re.finditer(r'^#{1,6}\s+(.+?)\s*$', body, re.M):
        heads.append(re.sub(r'[^a-z ]', '', hm.group(1).lower()).strip())
    return heads


def load_epics(artifacts_dir, strat_id):
    """Return {epic_key: (path, frontmatter, body)} for one strategy's epics.

    epic_key is the filename stem; branch files carry their BRANCH- prefix.
    """
    task_dir = os.path.join(artifacts_dir, "epic-tasks")
    if not os.path.isdir(task_dir):
        return {}
    pat = re.compile(re.escape(strat_id) + r"-(BRANCH-[A-Z]-)?(E\d{3})\.md$")
    epics = {}
    for name in sorted(os.listdir(task_dir)):
        m = pat.match(name)
        if not m:
            continue
        path = os.path.join(task_dir, name)
        fm, body = read_frontmatter(path)
        epics[name[:-3]] = (path, fm, body)
    return epics


def dependency_closure(start_key, deps):
    """All epics reachable from start_key by following dependencies."""
    seen, stack = set(), list(deps.get(start_key, []))
    while stack:
        n = stack.pop()
        if n in seen or n not in deps:
            continue
        seen.add(n)
        stack.extend(deps[n])
    return seen


def check(strat_id, artifacts_dir, components_path):
    """Run all checks; return a list of violation strings."""
    probs = []
    epics = load_epics(artifacts_dir, strat_id)
    if not epics:
        return ["no epic files found for %s under %s/epic-tasks/"
                % (strat_id, artifacts_dir)]

    valid_components = set()
    if os.path.isfile(components_path):
        with open(components_path, encoding="utf-8") as f:
            valid_components = {ln.strip() for ln in f if ln.strip()}
    if not valid_components:
        probs.append("cannot read canonical component list %s — verify the "
                     "path before trusting component names" % components_path)

    deps, is_branch, is_docs, is_impl, itype, prio = {}, {}, {}, {}, {}, {}
    for key, (path, fm, body) in epics.items():
        name = key + ".md"
        # 1. body sections (contract parity with the artifact judge)
        heads = body_headings(body)
        for want, aliases in SECTIONS:
            if not any(a in h for h in heads for a in aliases):
                probs.append("%s: body missing '%s' section (required "
                             "sections: Description, Scope, Acceptance "
                             "Criteria, HLR Traceability)" % (name, want))
        # 2. component vocabulary
        comp = fm.get("component")
        if valid_components and isinstance(comp, str) and comp.strip() \
                and comp.strip() not in valid_components:
            probs.append("%s: component '%s' is not in %s — pick the closest "
                         "canonical name (submit.py strips unknown names)"
                         % (name, comp.strip(), components_path))
        # collect graph facts
        dl = fm.get("dependencies")
        deps[key] = [x for x in dl if isinstance(x, str)] \
            if isinstance(dl, list) else []
        is_branch[key] = "BRANCH-" in key
        is_docs[key] = fm.get("implementation_type") == "docs-authoring"
        is_impl[key] = fm.get("type") == "Implementation"
        it = fm.get("implementation_type")
        itype[key] = it if it in IT_ENUM else None
        prio[key] = fm.get("priority")

    def kind(key):
        """Implementation kind of an epic — parity with the judge: an epic
        that is not type Implementation is never a parallel-rule party; an
        Implementation epic's kind is its implementation_type when that is a
        known label, else 'general'."""
        if not is_impl[key]:
            return "non-implementation"
        return itype[key] or "general"

    # 3. Rule 11 — docs-authoring blocked by every main-plan Implementation
    universe = [k for k in epics
                if is_impl[k] and not is_docs[k] and not is_branch[k]]
    for k in sorted(epics):
        if not is_docs[k]:
            continue
        cl = dependency_closure(k, deps)
        missing = sorted(e for e in universe if e != k and e not in cl)
        if missing:
            probs.append("Rule 11: docs-authoring %s is not blocked by every "
                         "Implementation epic — add %s to its dependency chain"
                         % (k, ", ".join(missing)))

    # 4. Priority inheritance — enablers of P0 work must be P0
    for k in sorted(epics):
        if is_branch[k] or is_docs[k]:
            continue
        if prio.get(k) != "P0":
            continue
        # every main-plan, non-docs epic in k's closure enables P0 work
        cl = dependency_closure(k, deps)
        for t in sorted(cl):
            if is_branch[t] or is_docs[t]:
                continue
            if PRIORITY_ORDER.get(prio.get(t), 9) > 0:
                probs.append("priority inheritance: %s (%s) blocks P0 epic %s "
                             "but is %s — raise it to P0 or restructure"
                             % (t, prio.get(t), k, prio.get(t)))

    # 5. Rules 7/8/10 — implementation-type parallelism: the mandated-parallel
    #    pairs carry no dependencies edge in either direction (direct edges
    #    only; edges into a docs-authoring epic are exempt — Rule 11 requires
    #    them; dependencies naming epics with no file cannot be judged).
    for k in sorted(epics):
        if kind(k) == "docs-authoring":
            continue
        for t in deps[k]:
            if t not in epics:
                continue
            pair = frozenset((kind(t), kind(k)))
            rule = PARALLEL_PAIRS.get(pair)
            if rule:
                probs.append("%s: %s (%s) blocks %s (%s) — these must run in "
                             "parallel; remove the dependencies edge and "
                             "express any coupling as an AC gate on the "
                             "dependent epic"
                             % (rule, t, kind(t), k, kind(k)))

    # 6. Epic-size overage triggers — a summary that acknowledges an epic kept
    #    above the ~2-week guideline must record a concrete re-split trigger.
    #    (Summary-side: overage text in epic bodies or reviews is out of scope;
    #    negated acknowledgments ("stays within the guideline") are clean.)
    summary_path = os.path.join(artifacts_dir, "epic-tasks",
                                strat_id + "-decomposition.md")
    if os.path.isfile(summary_path):
        with open(summary_path, encoding="utf-8") as f:
            summary = f.read()
        acked = any(OVERAGE_ACK.search(seg) and not OVERAGE_NEG.search(seg)
                    for line in summary.splitlines()
                    for seg in re.split(r'(?<=\.)\s+', line))
        if acked and not RESPLIT_TRIG.search(summary):
            probs.append(
                "summary acknowledges an epic kept above the size guideline "
                "with no re-split trigger — a bare overage note is an "
                "unresolved defect every later review will re-dock. FIX: "
                "append to that Health Warning a concrete planning condition, "
                "e.g. \"Re-split trigger: re-split <epic> if <the measurable "
                "condition that would make it more than one logical change, "
                "e.g. the audit/count estimate is exceeded>.\"")

        # 7. On-matrix bundling record — a bare-pointer bundling
        #    acknowledgment (no inline rationale, no matrix row flag) reads as
        #    an unanalyzed priority collapse; a self-contained note or a
        #    flagged row is a compliant record.
        mm = MATRIX_RE.search(summary)
        if mm:
            outside = summary[:mm.start()] + summary[mm.end():]
            lines = outside.splitlines()
            bare_pointer = False
            for i, line in enumerate(lines):
                if BUNDLE_ACK.search(line):
                    window = line + " " + (lines[i + 1] if i + 1 < len(lines)
                                           else "")
                    if not BUNDLE_RATIONALE.search(window):
                        bare_pointer = True
                        break
            if bare_pointer \
                    and not MATRIX_ROW_BUNDLED.search(mm.group(0)):
                probs.append(
                    "summary acknowledges a lower-priority HLR bundled into a "
                    "higher-priority epic, but the HLR Traceability Matrix row "
                    "carries no `bundled` flag — the rationale must be on the "
                    "record where the mapping is read. FIX: change that row's "
                    "Epic cell to \"<epic> (bundled)\" and append the rationale "
                    "to the row: \"Bundled with the P0 work: <why the HLR is "
                    "not separately schedulable — it edits the same call sites/"
                    "surface>; a split would double-touch the same files.\"")
    return probs


# ─── self-check ───────────────────────────────────────────────────────────────

def _self_check():
    """Verify each check fires on a minimal bad fixture and passes a good one."""
    import shutil
    import tempfile

    tmp = tempfile.mkdtemp(prefix="validate-decomp-selfcheck-")
    try:
        art = os.path.join(tmp, "artifacts", "epic-tasks")
        os.makedirs(art)
        comp = os.path.join(tmp, "components.txt")
        with open(comp, "w") as f:
            f.write("Dashboard\nServing Runtimes\n")

        def write(name, fm, body):
            with open(os.path.join(art, name), "w") as f:
                f.write("---\n%s\n---\n%s" % (fm, body))

        good_body = ("# T\n## Description\nd\n## Scope\ns\n"
                     "## Acceptance Criteria\na\n## HLR Traceability\nh\n")
        write("RHAISTRAT-9001-E001.md",
              "component: Dashboard\ntype: Implementation\npriority: P0\n"
              "dependencies: []\n", good_body)
        write("RHAISTRAT-9001-E002.md",
              "component: Serving Runtimes\ntype: Implementation\n"
              "implementation_type: docs-authoring\npriority: P2\n"
              "dependencies: [RHAISTRAT-9001-E001, RHAISTRAT-9001-E003]\n",
              good_body)
        # a konflux-onboarding epic parallel to the general epic (no edge
        # either way) is the Rule 10-compliant shape — must not be flagged
        write("RHAISTRAT-9001-E003.md",
              "component: Dashboard\ntype: Implementation\n"
              "implementation_type: konflux-onboarding\npriority: P1\n"
              "dependencies: []\n", good_body)
        assert check("RHAISTRAT-9001", os.path.join(tmp, "artifacts"),
                     comp) == [], "good fixture must pass cleanly"

        # bad fixture: missing Scope, bad component, Rule 11 gap, P0->P1 edge,
        # Rule 10 konflux-onboarding -> general edge
        write("RHAISTRAT-9002-E001.md",
              "component: Model Serving Stack\ntype: Implementation\n"
              "priority: P0\ndependencies: [RHAISTRAT-9002-E002]\n",
              "# T\n## Description\nd\n## Acceptance Criteria\na\n"
              "## HLR Traceability\nh\n")
        write("RHAISTRAT-9002-E002.md",
              "component: Dashboard\ntype: Implementation\npriority: P1\n"
              "dependencies: []\n", good_body)
        write("RHAISTRAT-9002-E003.md",
              "component: Dashboard\ntype: Implementation\n"
              "implementation_type: docs-authoring\npriority: P2\n"
              "dependencies: [RHAISTRAT-9002-E001]\n", good_body)
        # E004 is a main-plan Implementation the docs epic never depends on
        write("RHAISTRAT-9002-E004.md",
              "component: Dashboard\ntype: Implementation\npriority: P1\n"
              "dependencies: [RHAISTRAT-9002-E005]\n", good_body)
        write("RHAISTRAT-9002-E005.md",
              "component: Dashboard\ntype: Implementation\n"
              "implementation_type: konflux-onboarding\npriority: P1\n"
              "dependencies: []\n", good_body)
        probs = check("RHAISTRAT-9002", os.path.join(tmp, "artifacts"), comp)
        joined = "\n".join(probs)
        assert "missing 'Scope'" in joined, probs
        assert "Model Serving Stack" in joined, probs
        assert "Rule 11" in joined and "E004" in joined, probs
        assert "priority inheritance" in joined and "E002" in joined, probs
        r10 = [p for p in probs if p.startswith("Rule 10:")]
        assert len(r10) == 1 and "E005" in r10[0] and "E004" in r10[0], probs

        # checks 6/7 need a decomposition summary next to the epic files
        def write_summary(sid, body):
            with open(os.path.join(art, sid + "-decomposition.md"), "w") as f:
                f.write("---\nparent_strat: %s\n---\n%s" % (sid, body))

        matrix = ("## HLR Traceability Matrix\n\n"
                  "| HLR | Priority | Requirement | Epic |\n"
                  "|-----|----------|-------------|------|\n"
                  "| HLR-1 | P0 | core work | RHAISTRAT-9003-E001 |\n"
                  "| HLR-2 | P1 | enhancement | RHAISTRAT-9003-E001 |\n")

        # bare-note overage, off-matrix bundling note -> both checks fire
        write_summary("RHAISTRAT-9003",
                      "## Health Warnings\n\n"
                      "- **Planning note (epic size)**: E001 is ~1.5 sprints "
                      "by the strategy's own effort estimate — slightly above "
                      "the ~2-week epic guideline; the boundary is kept, "
                      "flagged for planning awareness only.\n\n"
                      "Post-matrix note: HLR-2 (P1) is bundled with P0 work "
                      "per the tight-coupling rule above.\n\n" + matrix)
        write("RHAISTRAT-9003-E001.md",
              "component: Dashboard\ntype: Implementation\npriority: P0\n"
              "dependencies: []\n", good_body)
        probs = check("RHAISTRAT-9003", os.path.join(tmp, "artifacts"), comp)
        joined = "\n".join(probs)
        assert "re-split trigger" in joined, probs
        assert "bundled" in joined and "Matrix row" in joined, probs

        # triggered overage + on-matrix bundled flag -> clean
        write_summary("RHAISTRAT-9004",
                      "## Health Warnings\n\n"
                      "- **Planning note (epic size)**: E001 is ~1.5 sprints "
                      "by the strategy's own effort estimate — slightly above "
                      "the ~2-week epic guideline; kept as one logical change. "
                      "Re-split trigger: re-split E001 if the audit finds "
                      "materially more sites than the estimate.\n\n"
                      "## HLR Traceability Matrix\n\n"
                      "| HLR | Priority | Requirement | Epic |\n"
                      "|-----|----------|-------------|------|\n"
                      "| HLR-1 | P0 | core work | RHAISTRAT-9004-E001 |\n"
                      "| HLR-2 | P1 | enhancement | E001 (bundled) | "
                      "Bundled with the P0 work: same call sites; a split "
                      "would double-touch the same files. |\n")
        write("RHAISTRAT-9004-E001.md",
              "component: Dashboard\ntype: Implementation\npriority: P0\n"
              "dependencies: []\n", good_body)
        assert check("RHAISTRAT-9004", os.path.join(tmp, "artifacts"),
                     comp) == [], "triggered overage + flagged row must pass"

        # negated overage ("stays within the guideline") -> clean
        write_summary("RHAISTRAT-9005",
                      "## Health Warnings\n\n"
                      "- Per the strategy's S-size effort estimate this stays "
                      "within the epic-size guideline.\n\n" + matrix)
        write("RHAISTRAT-9005-E001.md",
              "component: Dashboard\ntype: Implementation\npriority: P0\n"
              "dependencies: []\n", good_body)
        assert check("RHAISTRAT-9005", os.path.join(tmp, "artifacts"),
                     comp) == [], "negated overage must not fire"

        # off-matrix bundling note that carries its own rationale -> clean
        write_summary("RHAISTRAT-9006",
                      "## Notes\n\n"
                      "HLR-2 (P1) is kept bundled with the P0 work because "
                      "it extends the same report surface; a split would "
                      "double-touch the same files.\n\n" + matrix)
        write("RHAISTRAT-9006-E001.md",
              "component: Dashboard\ntype: Implementation\npriority: P0\n"
              "dependencies: []\n", good_body)
        assert check("RHAISTRAT-9006", os.path.join(tmp, "artifacts"),
                     comp) == [], "self-contained bundling note must not fire"

        print("self-check OK: 7 checks fire on bad fixture, clean on good")
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("strat_id", nargs="?", help="e.g. RHAISTRAT-9013")
    ap.add_argument("--artifacts-dir", default="artifacts")
    ap.add_argument("--components",
                    default=".context/rhai-components.txt")
    ap.add_argument("--self-check", action="store_true")
    args = ap.parse_args(argv)

    if args.self_check:
        return _self_check()
    if not args.strat_id:
        ap.error("strat_id is required (unless --self-check)")

    probs = check(args.strat_id, args.artifacts_dir, args.components)
    if probs:
        for p in probs:
            print("VIOLATION: %s" % p)
        print("%d violation(s) — fix these before marking the decomposition "
              "complete" % len(probs))
        return 1
    print("OK: contract checks passed for %s" % args.strat_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
