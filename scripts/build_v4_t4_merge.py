#!/usr/bin/env python3
"""Build the T4 (tbt-merge) bundle: splice each donor's standalone edits plus
21 hand-reconciled conflict-cluster texts into the shared seed files.

Merge strategy ("Approach A"):
  1. Diff every T2 donor's best/ file against the seed (difflib opcodes).
  2. Union-find cluster opcodes across donors: two different donors' opcodes
     join a cluster iff their seed-line ranges (i1:i2) overlap.
  3. A cluster touched by exactly one donor is a "standalone range" -- splice
     that donor's replacement text in mechanically, no decision needed.
  4. A cluster touched by 2+ donors is a "conflict cluster" -- hand-authored
     reconciled text (see RECONCILED below) is spliced in instead.
  5. Splice all clusters left-to-right into the seed; everywhere else, seed
     content is kept verbatim.

See reports/v4-t4-merge-decisions.md for the rationale behind every
conflict-cluster resolution below.
"""
import difflib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = ROOT / 'artifacts/v4/seed'
ARTIFACTS = ROOT / 'artifacts/v4'
OUT_DIR = ROOT / 'artifacts/v4/t4-merge'

DONORS = sorted([
    "cloud-024-guid-to-account", "cloud-026-gpu-abuse-triage",
    "cost-029-no-cost-rows-for-guid",
    "icinga-010-stuck-anarchysubjects", "icinga-011-aap2-job-status-alert",
    "icinga-013-acknowledged-not-an-issue", "icinga-014-check-script-path-moved",
    "platform-001-ee-entrypoint-rca", "platform-002-collection-not-found-rca",
    "platform-003-tojson-dict-literal-rca", "platform-004-events-then-config",
    "platform-005-wrong-owner-trap", "platform-007-directory-path-fetch",
    "platform-008-log-does-not-say", "platform-022-job-on-no-controller",
    "platform-023-splunk-guid-no-events", "platform-031-helm-url-not-a-timeout",
    "platform-032-shared-secret-not-a-registry-outage",
    "platform-033-schema-change-not-the-oom", "platform-034-rate-limit-not-an-outage",
])

FILES = ["aap2_agent.md", "babylon_agent.md", "cost_agent.md", "icinga_agent.md",
         "ocpv_agent.md", "orchestrator.md", "security_agent.md", "shared_context.md"]


def donor_opcodes(seed_lines, donor_lines):
    sm = difflib.SequenceMatcher(None, seed_lines, donor_lines, autojunk=False)
    return [{"tag": tag, "i1": i1, "i2": i2, "j1": j1, "j2": j2}
            for tag, i1, i2, j1, j2 in sm.get_opcodes() if tag != 'equal']


def ranges_overlap(a1, a2, b1, b2):
    return a1 < b2 and b1 < a2


def cluster_opcodes(per_donor_ops):
    items = []
    for donor, ops in per_donor_ops.items():
        for op in ops:
            items.append((donor, op))
    n = len(items)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for i in range(n):
        for j in range(i + 1, n):
            d1, op1 = items[i]
            d2, op2 = items[j]
            if d1 == d2:
                continue
            if ranges_overlap(op1["i1"], op1["i2"], op2["i1"], op2["i2"]):
                union(i, j)

    groups = {}
    for i in range(n):
        r = find(i)
        groups.setdefault(r, []).append(items[i])
    return list(groups.values())


# ============================================================================
# Hand-reconciled text for the 21 conflict clusters. Keyed by (file, i1, i2)
# where i1/i2 are the union (min/max) of the seed-line range across every
# donor opcode in that cluster -- matching /tmp/merge_analysis.json exactly.
# ============================================================================
RECONCILED = {}

# A handful of standalone (single-donor) splices sit exactly at a conflict
# cluster's boundary (a zero-width insert opcode never "overlaps" anything
# under the strict i1<i2/j1<j2 inequality used for clustering, so union-find
# leaves them as their own cluster even when they are clearly part of the
# same hotspot). Rather than loosen the overlap test -- which risks pulling
# unrelated adjacent edits into a cluster elsewhere -- each such case is
# hand-verified and its content folded directly into the neighboring
# conflict cluster's RECONCILED text; the entry here says "this standalone
# splice's content has already been absorbed, do not also splice it in raw."
#
# aap2_agent.md (418,418) platform-023: a one-paragraph note ("fill fields
# 1-3 from tool results only, write 'not established' rather than guessing")
# inserted immediately after the seed's item-4/Fix-suggestions line and
# immediately before cluster 8's "Relevant Files to Review" heading. Folded
# into cluster (414,417)'s reconciled text above, renumbered to match its
# item list, right before the Root-cause-category table.
#
# babylon_agent.md (80,80) platform-005: a same-point standalone insert
# landing immediately after conflict cluster (76,80)'s reconciled numbered
# list -- but platform-005's own items 5-6 ("read owner/repo out of the
# result", "fetch the path the user asked for, not the lookup's own path")
# duplicate/continue that same numbered list, which the reconciled text
# already renumbered through item 7. Left as its own standalone splice it
# reopened "5."/"6." *after* the reconciled block's "### Deriving an
# AgnosticV Path Without the Index" subsection, splitting one logical list
# across an unrelated heading with two different items 5 and 6. Its owner-
# guessing detail was folded into the reconciled item 6 above; its distinct
# "fetch the requested path, not the lookup's path" point became new item 8.
#
# shared_context.md (11,11) platform-032: redundant with platform-034's
# "Investigation Budget and the Final Answer Contract" section at the same
# seed point -- see the STANDALONE_OVERRIDE comment above. Its two distinct
# points ("front-load the answer", "answer every sub-question in prose") were
# folded into platform-034's list as new items 7-8; the rest of its content
# restates platform-034's items 2/6 and is dropped, not retyped elsewhere.
#
# shared_context.md (214,214) platform-003: a short, headingless paragraph
# ("This rule governs facts, not judgments...") that in platform-003's own
# bundle sits directly under the seed's "## Grounding" heading, clarifying
# that same grounding rule. Its splice point (214,214) sits one line after
# the neighboring (213,213) cluster (cost-029 + icinga-010), and splice
# ordering put three brand-new sections -- icinga-013's "## Answering the
# Question That Was Asked" plus two more -- between the Grounding bullets and
# this paragraph, so "This rule" ends up dangling after unrelated content
# instead of the Grounding rule it actually refers to. Folded into cost-029's
# (213,213) splice, prepended immediately before its "### An absence is not a
# measurement" heading, so it reads as the Grounding bullets' own coda again.
#
# shared_context.md (232,232) platform-003: a fragment ("— this exempts you
# from tagging individual claims...") written in its own bundle to continue
# directly off the seed bullet "...(high confidence is the default)". Sharing
# the splice point with platform-002's full paragraph making the identical
# point (the marker exemption doesn't cover a root-cause verdict's own stated
# confidence) left platform-003's dangling em-dash attached to the END of
# platform-002's already-complete sentence instead of the seed bullet,
# producing a broken sentence. Dropped entirely -- platform-002's paragraph
# already covers everything platform-003's fragment adds.
#
# babylon_agent.md (80,80) platform-034: a paragraph ("retry once, and if it
# errors again, construct the path...") that landed dangling after an
# unrelated root-cause-analysis paragraph and right before "## Babylon
# Platform Overview" -- but worse than misplacement, it directly contradicts
# reconciled cluster (76,80)'s item 5 ("Do NOT retry the lookup") for the
# exact same `{"error": ...}` case. Item 5's no-retry policy is kept (it is
# the already-reconciled decision and the more efficient one -- a schema/
# validation error will not resolve itself on a bare retry). This donor's
# non-conflicting, additive detail -- an alternative owner/repo source
# (a resource's own `scm_url`, or the AAP2 agent's owner/repo table) plus the
# "never probe a guessed org" warning -- was folded into the RECONCILED
# "Deriving an AgnosticV Path Without the Index" text above instead; the
# contradictory retry advice is dropped.
#
# shared_context.md (237,237) platform-001: a third restatement of the same
# "confidence-marker exemption doesn't cover a root-cause verdict" point (see
# the STANDALONE_OVERRIDE comment above) landing, unheaded, at the tail of
# icinga-013's unrelated "When You Have No Tool for the System Being Asked
# About" section, 128 lines past the Confidence Markers section it is
# actually about. Its one distinct detail (the `Confidence: high` field
# example) was folded into platform-002's (232,232) paragraph; the rest is
# dropped as redundant.
ABSORBED_STANDALONE = {
    ("aap2_agent.md", "platform-023-splunk-guid-no-events", 418, 418),
    ("babylon_agent.md", "platform-005-wrong-owner-trap", 80, 80),
    ("shared_context.md", "platform-005-wrong-owner-trap", 186, 186),
    ("shared_context.md", "platform-032-shared-secret-not-a-registry-outage", 186, 186),
    ("shared_context.md", "platform-032-shared-secret-not-a-registry-outage", 11, 11),
    ("shared_context.md", "platform-003-tojson-dict-literal-rca", 214, 214),
    ("shared_context.md", "platform-003-tojson-dict-literal-rca", 232, 232),
    ("shared_context.md", "platform-001-ee-entrypoint-rca", 237, 237),
    ("babylon_agent.md", "platform-034-rate-limit-not-an-outage", 80, 80),
}

# Heading-disambiguation overrides for standalone (single-donor) splices.
#
# Several donors independently extended the seed's own Step-N numbering with
# a self-chosen label ("Step 6b", "Step 7a", "Step 9") without seeing each
# other's edits. Two pairs land at the *identical* zero-width seed insertion
# point (aap2_agent.md (266,266): platform-003 + platform-031's "Step 6b";
# (295,295): platform-031 + platform-034's "Step 7a") -- a true positional
# collision that the strict i1<i2 overlap test cannot see (two zero-width
# ranges at the same point never satisfy `a1 < b2`), so union-find keeps
# them as separate standalone clusters and the splicer's own `a[1] <= b[0]`
# assertion never fires either (266 <= 266 is true). A third pair (Step 9 at
# (370,370)/(371,371)) is not a positional collision at all -- just two
# donors choosing the same label a few lines apart -- but still renders as a
# confusing duplicate-titled pair.
#
# Policy: keep whichever donor's section is physically first unchanged
# (it keeps the canonical, un-suffixed label); every later colliding donor's
# heading -- and every self-reference to that heading elsewhere in the same
# donor's own text -- gets a "-2"/"-3" suffix. No donor's content is deleted
# or merged; only headings and self-references are disambiguated, via exact
# string substitutions applied to the donor's own raw text (never hand-
# retyped) so large blocks can't suffer a transcription error. Coverage:
#   - platform-003's "Step 6b: Namespaced Roles..." stays "Step 6b" (first).
#   - platform-031's "Step 6b: Compose the Failing Value..." -> "Step 6b-2"
#     (also renames its own "see Step 7a question 3" cross-ref).
#   - platform-008's "Step 7a: Does the evidence..." stays "Step 7a" (first;
#     not a positional collision -- it's a `replace` at seed (282,283) --
#     but shares the label, so it anchors the canonical name).
#   - platform-031's "Step 7a: Timeouts, Retries..." -> "Step 7a-2" (also
#     renames its own "(Step 6b)" self-reference to "(Step 6b-2)").
#   - platform-034's "Step 7a: Many Jobs Failing..." -> "Step 7a-3".
#   - platform-001's "Step 9: Assign Exactly One Root Cause Category" stays
#     "Step 9" (first, at seed (370,370)).
#   - platform-003's "Step 9: Assign Exactly One Root Cause Category" ->
#     "Step 9-2" (at seed (371,371); distinguished with a subtitle since the
#     title is otherwise identical to platform-001's).
#
# Each entry is a list of (old, new) exact-substring replacements applied,
# in order, to that donor's raw standalone-splice text (the same text
# build_file would otherwise splice in verbatim). Every `old` is asserted
# to occur exactly once so a typo can't silently no-op.
STANDALONE_OVERRIDE = {}

STANDALONE_OVERRIDE[("aap2_agent.md", "platform-031-helm-url-not-a-timeout", 266, 266)] = [
    ("#### Step 6b: Compose the Failing Value from Its Variables",
     "#### Step 6b-2: Compose the Failing Value from Its Variables"),
    ("unpinned version variable) — see Step 7a question 3.",
     "unpinned version variable) — see Step 7a-2 question 3."),
]

STANDALONE_OVERRIDE[("aap2_agent.md", "platform-031-helm-url-not-a-timeout", 292, 293)] = [
    ("whole host/service is (Step 7a) |", "whole host/service is (Step 7a-2) |"),
]

STANDALONE_OVERRIDE[("aap2_agent.md", "platform-031-helm-url-not-a-timeout", 295, 295)] = [
    ("#### Step 7a: Timeouts, Retries and Dead Dependencies",
     "#### Step 7a-2: Timeouts, Retries and Dead Dependencies"),
    ("resolve it from the role's own variables\n   (Step 6b) — not by copying",
     "resolve it from the role's own variables\n   (Step 6b-2) — not by copying"),
]

STANDALONE_OVERRIDE[("aap2_agent.md", "platform-034-rate-limit-not-an-outage", 295, 295)] = [
    ("#### Step 7a: Many Jobs Failing at Once — Throttling vs. Outage",
     "#### Step 7a-3: Many Jobs Failing at Once — Throttling vs. Outage"),
]

STANDALONE_OVERRIDE[("aap2_agent.md", "platform-034-rate-limit-not-an-outage", 125, 125)] = [
    ("arithmetic in Step 7a runs on.", "arithmetic in Step 7a-3 runs on."),
]

STANDALONE_OVERRIDE[("aap2_agent.md", "platform-031-helm-url-not-a-timeout", 367, 368)] = [
    ("talking to a host or endpoint; that is `query_splunk` (Step 7a).",
     "talking to a host or endpoint; that is `query_splunk` (Step 7a-2)."),
]

STANDALONE_OVERRIDE[("aap2_agent.md", "platform-003-tojson-dict-literal-rca", 371, 371)] = [
    ("#### Step 9: Assign Exactly One Root Cause Category",
     "#### Step 9-2: Assign Exactly One Root Cause Category — Naming the Mechanism Is Not Assigning a Category"),
    # The heading rename above only fixed the duplicate-title surface issue.
    # Step 9-2's own table swaps two of Step 9's category definitions: it
    # defines automation_failure as "the automation platform itself broke"
    # (controller/EE/runner/AAP-side API fault) -- which is word-for-word
    # what Step 9 defines as platform_failure ("AAP2 ... itself returned an
    # error") -- and narrows platform_failure to only the RHDP/Babylon
    # provisioning layer. An agent following both tables would classify the
    # same AAP2 controller fault as automation_failure per Step 9-2 and as
    # platform_failure per Step 9. Reword both rows to match Step 9's
    # canonical split (automation_failure = the invocation was wrong;
    # platform_failure = the platform itself erred) while keeping every
    # distinct fact from platform-003's original rows -- the AAP2
    # controller/EE/runner/API detail and the RHDP/Babylon/AnarchySubject
    # detail -- folded together under platform_failure, where both belong.
    ("| The automation platform itself broke — controller error, execution "
     "environment, runner, or an AAP-side API fault. | `automation_failure` |",
     "| The automation *invoked* something incorrectly — a playbook, role, "
     "wrapper, or entrypoint passed bad arguments, took a wrong code path, "
     "or skipped a mode check. The call is wrong, not the data it computes. "
     "| `automation_failure` |"),
    ("| RHDP's own provisioning plane misbehaved — Babylon/AnarchySubject "
     "stuck or erroring, the catalog or lifecycle machinery itself faulting "
     "— with the job's own code and config correct. | `platform_failure` |",
     "| AAP2, OpenShift, or a cloud control plane itself returned an error "
     "or refused the operation — the controller, execution environment, "
     "runner, or an AAP-side API itself faulting; or RHDP's own "
     "provisioning plane misbehaving: Babylon/AnarchySubject stuck or "
     "erroring, or the catalog/lifecycle machinery itself faulting — with "
     "the job's own code and config correct. | `platform_failure` |"),
]

STANDALONE_OVERRIDE[("aap2_agent.md", "platform-002-collection-not-found-rca", 424, 424)] = [
    # This standalone insert adds a THIRD independent root-cause-category table
    # ("Root Cause Category and Confidence") at a seed point (424) distant from
    # both Step 9 (370) and Step 9-2 (371), so the general same-point collision
    # detector never flagged it -- only a grep across the whole merged file for
    # the automation_failure/platform_failure token pair surfaced it. Its
    # automation_failure row classifies "EE entrypoint, runner invocation, or
    # inventory generation failed" as automation_failure, which directly
    # contradicts the Step 9 / Step 9-2 consensus (see the 371,371 override
    # above): those two sections classify "execution environment, runner" as
    # symptoms of platform_failure, and Step 9 explicitly excludes anything
    # "outside the automation" from automation_failure. Reword both rows to
    # match the same canonical split already applied to Step 9-2, so all three
    # sections now agree.
    ("| The automation harness never got as far as running the play content "
     "— EE entrypoint, runner invocation, or inventory generation failed "
     "| `automation_failure` |",
     "| The automation *invoked* something incorrectly — a playbook, role, "
     "wrapper, or entrypoint passed bad arguments, took a wrong code path, "
     "or skipped a mode check. The call is wrong, not the data it computes "
     "| `automation_failure` |"),
    ("| The AAP2 controller or the underlying platform itself errored "
     "| `platform_failure` |",
     "| AAP2, OpenShift, or a cloud control plane itself returned an error "
     "or refused the operation — the controller, execution environment, "
     "runner, or an AAP-side API itself faulting | `platform_failure` |"),
]

STANDALONE_OVERRIDE[("aap2_agent.md", "platform-031-helm-url-not-a-timeout", 412, 412)] = [
    ("them (Step 6b)", "them (Step 6b-2)"),
]

STANDALONE_OVERRIDE[("aap2_agent.md", "platform-031-helm-url-not-a-timeout", 436, 436)] = [
    ("still reporting the hypothesis the log was built to suggest. Go back to Step 7a\n   question 4 and write the measured duration instead.",
     "still reporting the hypothesis the log was built to suggest. Go back to Step 7a-2\n   question 4 and write the measured duration instead."),
]

STANDALONE_OVERRIDE[("aap2_agent.md", "platform-031-helm-url-not-a-timeout", 443, 444)] = [
    ("First establish WHAT the wait was on (Step 7a).",
     "First establish WHAT the wait was on (Step 7a-2)."),
    ("Trace the URL back to the role variables that build it (Step 6b);",
     "Trace the URL back to the role variables that build it (Step 6b-2);"),
]

# babylon_agent.md: platform-005 and platform-033 each independently insert a
# brand-new "## Critical Rules" section at the exact same seed point (7,7) —
# the same silent same-point zero-width collision subclass as aap2's Step
# 6b/7a/9 headings. Unlike those, the two sections' CONTENT genuinely
# overlaps (both are round/tool-call budget + report-before-you-run-out
# rules), so this is a true Approach-A "hotspot region for overlapping
# edits," not just a naming coincidence. Rather than hand-merging the prose
# (risking transcription drift on ~120 lines), keep platform-005's section
# (physically first) as the canonical "## Critical Rules" and retitle
# platform-033's (physically second) to name what it actually adds beyond
# 005's rules — its own distinct tool-call-count discipline and search
# behavior — so a reader sees two complementary rule sets, not a duplicate
# heading. No cross-reference anywhere cites "Critical Rules" by name, so no
# other text needs updating.
#
# The heading rename alone left a deeper defect: platform-033's body states
# a hard "six tool calls" ceiling, a different unit from platform-005's
# canonical "8 rounds" budget (005's own rule 1 defines a round as one
# assistant turn, not one tool call — several parallel calls in one turn
# cost only one round). A reader hitting both sections gets two
# incompatible numeric caps for the same resource. Reconcile platform-033's
# two budget-asserting sentences to "rounds," aligned with 005's 8-round
# budget and its "by round 6" checkpoint; leave platform-033's other "tool
# call" mentions alone since they describe unrelated concepts (calls being
# invisible to the requester) or an actual step count in a worked example,
# not a competing cap.
STANDALONE_OVERRIDE[("babylon_agent.md", "platform-033-schema-change-not-the-oom", 7, 7)] = [
    ("## Critical Rules",
     "## Critical Rules — Tool-Call Budget and Report Discipline"),
    ("**Count your tool calls as you go. Six is your ceiling: your seventh response\n"
     "   contains no tool calls and is the report.** The chains in this file reach every\n"
     "   answer in five calls or fewer, so six is not a squeeze — it is slack. If six calls\n"
     "   have not settled a detail, a seventh will not either; that detail is a\n"
     "   \"Not confirmed\" line, not a reason to keep going.",
     "**Count your rounds as you go — the same rounds Critical Rules above caps at 8. Six\n"
     "   is your checkpoint: your seventh round contains no tool calls and is the report.**\n"
     "   The chains in this file reach every answer in five rounds or fewer, so six is not a\n"
     "   squeeze — it is slack. If six rounds have not settled a detail, a seventh will not\n"
     "   either; that detail is a \"Not confirmed\" line, not a reason to keep going."),
    ("   - You have made six tool calls.\n",
     "   - You have used six rounds.\n"),
]

# shared_context.md: platform-032 and platform-034 each independently insert a
# brand-new section at the exact same seed point (11,11), both re-explaining
# the same core idea (the tool-call budget runs out without warning, so write
# findings before that happens) with genuinely overlapping guidance -- the
# same "hotspot region for overlapping edits" pattern as babylon's (7,7), but
# here the two donors' content is redundant rather than complementary: three
# of platform-032's five bullets restate platform-034's items 2 and 6 in
# different words. Policy: rather than run both full sections back-to-back
# (a reader hits the same "you'll be cut off, write now" point twice under
# two different headings), fold platform-032's two genuinely distinct points
# -- "front-load the answer" and "answer every sub-question in prose, not a
# table" -- into platform-034's more detailed numbered list as new items 7-8,
# and drop platform-032's standalone splice entirely since none of its
# content is lost.
STANDALONE_OVERRIDE[("shared_context.md", "platform-034-rate-limit-not-an-outage", 11, 11)] = [
    ("6. **Your last output MUST be your findings, not a tool call.** This applies to\n"
     "   every investigation, in every domain — not just the ones with a named report\n"
     "   format. If you have gathered data and have not yet written your findings,\n"
     "   stop calling tools and write them now.\n"
     "\n"
     "**Worked example of the stop decision.**",
     "6. **Your last output MUST be your findings, not a tool call.** This applies to\n"
     "   every investigation, in every domain — not just the ones with a named report\n"
     "   format. If you have gathered data and have not yet written your findings,\n"
     "   stop calling tools and write them now.\n"
     "\n"
     "7. **Front-load the answer, not the investigation.** Spend rounds on what you\n"
     "   cannot answer without, and stop as soon as you can explain the finding.\n"
     "\n"
     "8. **Answer every sub-question the user actually asked, in prose.** When a\n"
     "   request enumerates items (\"say how many…\", \"name X and where it comes\n"
     "   from\", \"say what Y was doing\"), each needs its own explicit answer. Do not\n"
     "   leave one implied by a table.\n"
     "\n"
     "**Worked example of the stop decision.**"),
]

# shared_context.md: platform-003's (214,214) paragraph belongs right after
# the Grounding bullets it clarifies (see the ABSORBED_STANDALONE comment
# above) -- prepend it to cost-029's (213,213) splice, which sits in the same
# gap one seed line earlier, so it lands immediately before any of the
# donors' brand-new sections rather than after them.
# shared_context.md: platform-001's (237,237) paragraph makes, for the third
# time in this file, the same point platform-002 and platform-003 already
# made at (232,232) (see the ABSORBED_STANDALONE comment below) -- but its
# splice point sits 128 lines further down, past icinga-013's entire "When
# You Have No Tool for the System Being Asked About" section, so it lands as
# an unheaded non-sequitur at that section's tail. Its one non-redundant
# detail -- the concrete "state it as a field, e.g. `Confidence: high`"
# suggestion -- is folded into platform-002's (232,232) paragraph, which
# already sits directly under the Confidence Markers section this point is
# actually about; the rest of platform-001's text is dropped as redundant.
STANDALONE_OVERRIDE[("shared_context.md", "platform-002-collection-not-found-rca", 232, 232)] = [
    ("verdict, even when the confidence is high and no marker is needed.\n",
     "verdict, even when the confidence is high and no marker is needed. State it as a\n"
     "  field, e.g. `Confidence: high`.\n"),
]

STANDALONE_OVERRIDE[("shared_context.md", "cost-029-no-cost-rows-for-guid", 213, 213)] = [
    ("\n### An absence is not a measurement\n\n",
     "\n"
     "**This rule governs facts, not judgments.** A diagnosis, a classification, or a root\n"
     "cause is a conclusion you draw *from* the evidence — it is never \"confirmed by a tool\n"
     "result\" in the way a timestamp or a job status is, and it is not hallucination to state\n"
     "one. So when your report format requires a verdict — a root cause, a category, a\n"
     "confidence — produce it from the evidence you have. Grounding means your verdict must\n"
     "follow from the tool results and must not contradict them; it does not mean withholding\n"
     "the verdict until some tool states it outright, and \"not confirmed by available data\" is\n"
     "never a substitute for a conclusion the format asks you to reach. If the evidence is\n"
     "thin, commit to the best-supported verdict, lower the confidence, and name in one clause\n"
     "what you could not verify.\n"
     "\n"
     "### An absence is not a measurement\n\n"),
]

# ---------------------------------------------------------------------------
# aap2_agent.md
# ---------------------------------------------------------------------------

RECONCILED[("aap2_agent.md", 203, 205)] = """\
    scm_url: https://github.com/{owner}/{repo}
    scm_ref: {branch}
"""

RECONCILED[("aap2_agent.md", 234, 238)] = """\
| Project Pattern | Version | GitHub Owner | GitHub Repo |
|----------------|---------|--------------|-------------|
| `https://github.com/redhat-cop/agnosticd.git` | v1 | `redhat-cop` | `agnosticd` |
| `https://github.com/agnosticd/agnosticd-v2.git` | v2 | `agnosticd` | `agnosticd-v2` |

**The owner of a repo is NOT always `rhpds`.** `rhpds` owns the *agnosticv* repos
(`rhpds/agnosticv`, `rhpds/zt-*-agnosticv`); the *agnosticd* content repos are owned by
`agnosticd` (v2) and `redhat-cop` (v1). Guessing `rhpds` for an agnosticd repo is the
single most common wasted-call mistake — the search returns "No search results found",
which looks like "the file doesn't exist" when it actually means "wrong owner".

**Never guess or recall the `owner` of a content repository — always parse it out of
a value a tool actually returned.** The same repo name is published under different
owners in different environments, and these repos have been re-homed between orgs over
time (`redhat-cop`, `rhpds`, `agnosticd`), so an owner you supply from memory is wrong
often enough that it is never worth a call. Take it from whichever of these the
investigation has actually put in front of you, in priority order:

1. An `owner/repo` the **request itself names**, or a fully-qualified collection name
   in the failing task line. A log task header of the form
   `TASK [<namespace>.<collection> : ...]` names the repository directly: the
   namespace is the owner and the collection is the repo. Use it as written — this is
   reading a tool result, not recalling an owner.
2. The `__meta__.deployer.scm_url` of the agnosticv config (or from `get_component`),
   or the job's Project URL / `git_url` from `get_job_log` **when the response actually
   carries one** — split `https://github.com/{owner}/{repo}.git` and use both halves
   exactly as written. Check the field is present before relying on it: many
   `get_job_log` responses have no Project URL or `git_url` at all.
3. The `owner`/`repo` fields of a `lookup_catalog_item` result. **Use them as written
   for your next fetch.** If the file you are after is agnosticd *content* and a
   `__meta__.deployer.scm_url` you have **actually fetched** names a different repo,
   prefer that URL — that is a tool result disagreeing with a tool result, which is the
   only thing that outranks the lookup. Otherwise do not second-guess the lookup, and
   never replace its owner with a remembered one.
4. The table above, only when none of the above is available.

Parse the version from the repo half of that same URL (`agnosticd` = v1,
`agnosticd-v2` = v2). Read the owner from the URL's owner half — do NOT infer the
owner from the version, and do NOT assume the owner used by another repo in this
investigation. The `agd-v2` / `agd` account prefix in a job template name tells you the
deployment is agnosticd v2; it does NOT tell you the GitHub owner — confirm via one of
the sources above.

**Get an owner out of a tool before your first GitHub call** (Critical Rule 5) — a
single `lookup_catalog_item` call is the cheapest source. The *only* thing that
excuses that call is source 1 having already written **both halves** out: a literal
`owner/repo`, or an FQCN header you can split into namespace and collection. A path,
a bare repo name, or a description of the repository ("the content repo", "that
repository") excuses nothing — those are precisely the cases where a remembered owner
feels certain and is wrong. A `lookup_catalog_item` that returns `found: false` is an
answer, not a reason to start guessing — fall back to the remaining sources, and if
the repository is still unknown, fetch with the best tool-derived owner you have and
name that source in the report rather than probing for more.

**Verify the file you fetched belongs to the job that ran.** Cross-check one concrete
value from the file against the log — the failing URL, the image reference, the
namespace, the version. If the file does not contain the value the log shows failing,
you have the wrong owner, repo, ref, or path: fix the coordinates from a tool result
rather than reasoning from the mismatched file. If a `search_github_repo` or
`fetch_github_file` call fails on an agnosticd path, retry the SAME path under the
other agnosticd owner before concluding the file is missing, and cite the owner that
actually returned the content, not the one you tried first — but do NOT re-fetch the
same path from a second and third org hoping one looks right beyond that one retry:
each copy will look entirely plausible, you have no way to tell which one ran, and you
will burn your whole budget comparing forgeries.

Guessing an owner and probing GitHub costs many calls, and each miss is
indistinguishable from the file genuinely not existing — which is how an
investigation talks itself into the wrong conclusion. So do NOT sweep candidate
owner/repo pairs. When you need to locate a file whose directory you know but whose
exact path you do not, that is what `search_github_repo` is for — one search, not a
walk: never call `fetch_github_file` on a directory prefix to see what is inside it,
because a directory is not a file.
"""

RECONCILED[("aap2_agent.md", 343, 348)] = """\
   - `search_github_repo(owner, repo, "setup-automation")` — one call, returns every
     path under that tree, so you learn the real file names instead of guessing them
   - `fetch_github_file(owner, repo, "<path from matches>")` — the `main.yml` the setup
     container runs, plus any scripts `main.yml` references (e.g. `setup-builder.sh`,
     `setup.sh`), each fetched by its path from `matches`
"""

RECONCILED[("aap2_agent.md", 414, 417)] = """\
2. **Root cause:** underlying reason (expired token, missing image, bad config, etc.) —
   this is where the mechanism goes: the type mismatch, the double-encoding, the misused
   filter, whatever you actually found. Describe it as precisely as you can here.
3. **Category:** exactly one label from the table below — REQUIRED whenever you
   determined a cause, and *not* a restatement of the mechanism you just described in
   item 2. Never a phrase of your own invention, and never a second token. If a summary
   table repeats it, that cell holds the same token. If the evidence did not establish a
   cause, write "the log does not establish the cause" here instead of a token, per the
   exception in Step 9.
4. **Confidence:** `high`, `medium`, or `low`, with the reason — REQUIRED, always written
   out, on every report. This is a structured field of the verdict, not the optional
   inline `[confidence: ...]` inference marker; a report whose category carries no
   confidence word is incomplete even when the evidence is conclusive.
5. **What the evidence settles:** one line per piece of evidence, each in the shape
   `<observation, with its timestamp or count> — so <what that establishes about the
   system>`. Every line names a fact from a tool result and says what that fact pins down.
   No line names the explanation it defeats, and this section carries no list of
   alternatives — see "Name the evidence, never the hypothesis" below for the exact shape.
6. **How you determined it:** the method, not the findings — which tools you called, which
   files you fetched, and what you compared against what (timing analysis, log line, script
   trace). Quote the tool result it rests on — the `fatal:` / `error_msg` line, or the
   specific script line, container, or file the trace lands on, plus the timing that pins
   it (Steps 7b/7c). Item 5 is the facts; this is how you got them.
7. **The change that fixes it:** the file to edit and the **specific change** — not a
   direction to go investigate. When you have read the source, quote the current value
   and give the corrected one:

Fill items 1, 2, 5 and 6 from tool results only. If your searches came back empty and no
result identifies a cause, write "not established — <what you searched> returned no
events" in the Root cause and Category fields (see the exception in Step 9) and put the
check that would establish it under item 7, The change that fixes it. That is the correct
report, not a failed one — do not fill a field with an inference about whether the job ran.

**Root cause category — pick exactly one:**

| Category | Use when | Do NOT use when |
|---|---|---|
| `dependency` | An external artifact, image, package, tag, or URL the automation needs is gone, moved, withdrawn, or never existed at the requested coordinates — including a floating ref (`latest`, `stable`) whose target upstream restructured. The host serving it is reachable. | Nothing reached the host at all |
| `connectivity` | The host, endpoint, or network path itself is unreachable or unresponsive for ALL traffic in the window — DNS failure, refused connection, route or firewall block — confirmed by other traffic to the same target also failing | Other operations reached the same host successfully — that makes it `dependency` |
| `configuration` | A value in agnosticv, `default_vars`, or `extra_vars` is wrong, missing, or overridden to something invalid | The config is unchanged and was correct for what upstream used to serve — then the config did not break, the dependency did |
| `permissions` | Credentials, tokens, vault secrets, IAM, or RBAC denied the operation | |
| `capacity` | Quota, limit, pool exhaustion, insufficient nodes, storage, or address space | |
| `code_defect` | The playbook, role, or script is itself broken — bad syntax, wrong logic, a regression in a recent commit | |
| `platform` | The controller, cluster, or Babylon/Anarchy machinery malfunctioned | |

**The `dependency` vs `connectivity` split is decided by evidence, not by the error
text.** A read timeout, a connection error, and a hang produce near-identical log lines
in both cases, so the wording of the error cannot settle it. The discriminator is Step 7a-2
question 2: did anything else reach the same host in that window? Something succeeded →
`dependency`. Nothing did → `connectivity`. No data → say so and lower confidence.

#### Name the evidence, never the hypothesis

**Every sentence in your report states an observation from a tool result, a consequence you
derived from one, or a fix. A hypothesis you rejected appears *only* as the observation
that rejects it — you do not name it, and you do not negate it.** This is a hard rule, not
a style preference, and it has three reasons behind it:

- A negated label is not checkable. "This was not a host outage" gives the reader nothing
  to verify; the timestamps of the traffic that *did* get through give them everything.
- A negation does not survive being quoted. Your line lands in a ticket, a summary, or a
  triage tool that keyword-matches it, and the label is what gets kept while the "not"
  gets dropped. You will have put the wrong diagnosis into the record yourself.
- If a sentence's only job is to say what the problem is **not**, the evidence line above
  it has already done that work, so the sentence is pure risk. Delete it.

**Do not create a "ruled out" section, list, or heading.** A list of alternatives is a list
of labels, and it is the single most common way this rule gets broken: the heading names the
hypothesis, and then the line under it negates the heading.

**Every fact moves; nothing is dropped.** Removing that section is a relocation, not a
deletion — the observations that were under it are the most valuable lines in the report and
they must still appear. Each one goes in **What the evidence settles** as a plain
observation, and the contrast evidence from Step 7a-2 question 2 — what else reached the same
host in the window, named, with timestamps — also has its own required field under
**Failure Analysis**. If you delete the heading and lose the facts with it, you have made the
report worse, not better. Check that each one survived the move.

Three families cover nearly every violation. The right column is not a hint — each entry is
a complete sentence shaped the way yours should be:

| Do not write this — in either polarity | Write this |
|---|---|
| That the failure was short-lived, one-off, self-correcting, a blip, or a flap — *or any dismissal of the same idea*, such as "not a brief blip" or a heading like "Ruled out: impermanence" | "All 6 attempts failed the same way across the 9 minutes from the first to the last, so the fault was present for the whole window and the next run meets it again." |
| That the host, server, endpoint, or mirror had gone away — unreachable, unavailable, in an outage, not up — *or any dismissal of the same idea*, such as "this was not a host outage" | Whichever way the contrast check came out, report the check: "Two other downloads, `<artifact-a>` and `<artifact-b>`, came down from the same host at 01:04:12 and 01:07:48, so the host was answering requests throughout the failure window and only the path this task asked for did not." Or, when the search held nothing: "No other downloads or requests to that host are logged in the window, so this check is inconclusive; what does discriminate is that the failure is confined to the one resolved path." |
| That the remedy is another attempt at the job, or waiting to see whether it clears | "Point `<variable>` at a version upstream still publishes; until that value changes, every run fails at the same task." |

The vocabulary of impermanence is covered in **both** polarities — words for a fault that
comes and goes on its own make a causal claim you have not observed, so they are wrong as a
conclusion, and writing them in order to reject them puts that same claim in front of the
reader behind a "not" that does not survive the quote. Report the duration you measured
instead; it says more, and it is true.

**This rule covers every word you emit, not just the report body.** Any sentence you write
alongside a tool call, any aside about your own tooling, and every note in your Sources list
reach the reader as part of your answer. So: a tool of yours that returned an error is
reported as "`<tool>` returned an error" and nothing more — you never watched it recover, so
you are not in a position to say *why* it failed, and guessing at a cause for your own
tooling is the same unchecked claim this whole rule is about.
"""

RECONCILED[("aap2_agent.md", 454, 457)] = """\
**AgnosticD repositories:**
- **agnosticd-v2** (current): `https://github.com/agnosticd/agnosticd-v2`
- **agnosticd** (legacy): `https://github.com/redhat-cop/agnosticd`

**AgnosticD monorepos** — for roles under `ansible/roles/`. Take `owner` and `repo` from
the job's own Project URL (or the component's `scm_url`) and use the Step 6 version table
to read them off — do not hardcode an owner from memory. The current v2 monorepo is owned
by `agnosticd`, the legacy v1 monorepo by `redhat-cop`; any other owner for these repo names
is a guess, and a guessed owner produces a citation to a repository that does not exist.

**Collection repositories** — for a failing task namespaced `namespace.collection`, the
role does NOT live in either monorepo. Derive the repo from the FQCN itself
(`owner` = namespace, `repo` = collection, `path` = `roles/{role}/tasks/main.yml`) and
read Step 6b. Take the owner from the FQCN, not from this list: reaching for a familiar
monorepo here is what produces a wrong-repo citation.
"""

RECONCILED[("aap2_agent.md", 13, 16)] = """\
   full structured analysis (config trace table, failure analysis, root cause — or,
   when the evidence does not establish one, the explicit statement that it does not,
   see Step 7a — the root cause **category** line with its confidence, and
   recommendations). If you have been calling tools, your next text block should be
   the report — not more narration. A report that ends without the category line is
   incomplete no matter how good the analysis above it is (see Step 9). **A run that
   ends while still calling tools delivers nothing and is scored as a total failure,
   however much you learned.**
"""

RECONCILED[("aap2_agent.md", 247, 248)] = """\
- the failing role's `tasks/main.yml` — what the role *does*. If the failing task is
  namespaced (`namespace.collection : …`), this path is wrong; use Step 6b instead.
- **the failing role's `defaults/main.yml` — the variables it does it WITH.** Fetch this
  whenever the failure involves a URL, image reference, version, path, or endpoint. The
  variables that compose that value — and usually a comment spelling out the exact
  composition — live in `defaults/`, not in `tasks/`, and appear nowhere in the job log.
  This is the file that answers "how was the failing value built?"

**Do NOT type role paths from memory — get them from `search_github_repo`.** Role
directory layout differs by repo and generation: v1 roles sit under `ansible/roles/`,
while v2 OCP workload roles (the `ocp4_workload_*` family) sit under
`ansible/roles_ocp_workloads/`. A single
`search_github_repo(owner="{owner}", repo="{repo}", search="{role_name}")` returns the
real paths for that role; every guessed path costs a wasted fetch.
"""

RECONCILED[("aap2_agent.md", 268, 269)] = """\
**CHECKPOINT:** Verify you have completed Steps 3-6, and Step 6b if the failing task was
namespaced, or Step 6b-2 if the failing operation targeted anything outside the job (a
download, pull, clone, mount, or API call), before analyzing. In particular: have you read
the source of the role that actually failed, from the repo that actually ships it, and —
for anything outside the job — run the unfiltered GUID-scoped Splunk search before naming
a root cause?
"""

RECONCILED[("aap2_agent.md", 418, 424)] = """\
   ```
   # in {owner}/{repo}:{path}
   # before (broken):
   {the line as committed}
   # after (fixed):
   {the line as it should read}
   ```

   **When the bug is that a value has the wrong type or shape, say what the corrected
   value's type is, in the vocabulary of the file's own format, in the same sentence as
   the diff.** A diff shows what to type; it does not say what the value *becomes*, and
   the reader needs both. Write it as a fact about the file:

   Name **both sides** — what the value wrongly is today, and what it becomes:

   - "the committed value is a single-quoted Python dict literal, i.e. a string; the
     corrected value is a real YAML mapping — proper YAML, not a quoted string"
   - "…is a comma-separated string; the corrected value is a native YAML list"
   - "…is a quoted numeral; the corrected value is a YAML integer"

   Both halves matter and neither substitutes for the other. The *current* type explains
   why it failed — name the wrong value in the vocabulary of whatever produced it (a
   Python dict literal, a single-quoted string, a stringified list) rather than calling it
   merely "wrong" or "malformed". The *corrected* type is the recommendation.

   This applies whenever the failure is one of type or structure — a string where an
   object was expected, a scalar where a list was, a template that stringified something
   before it was consumed, a filter handed the wrong kind of input. These are statements
   about the source file, not narration of your analysis, so the "state facts, don't
   narrate" rules do not excuse leaving them out.

   "Check the extra vars", "verify the value is valid", and "review the role" are not
   fixes — they are what you do *before* you know the fix. If you have the source in
   hand, name the new value. Only when a needed file was genuinely unreachable do you
   state which file must be read, and then say so explicitly rather than dressing an
   investigation step up as a recommendation. Give each recommendation a priority
   (high / medium / low).

**Relevant Files to Review:** cite each as a single `owner/repo:path` token — these are
locations to name for the reader, not paths to fetch. The ones ending in `/` are
directories: to read a file inside one, resolve it with `search_github_repo` first, as
in "Finding a File in a GitHub Repo" above.
- AgnosticV config: `{owner}/{repo}:{path_to_common.yaml}`
- Component config (if used): `{owner}/{repo}:{component_item}/common.yaml`
- AgnosticD env_type: `{owner}/{repo}:ansible/configs/{env_type}/default_vars.yml`
- Failed role: `{owner}/{repo}:ansible/roles/{role_name}/tasks/main.yml` and
  `defaults/main.yml`, or for a namespaced collection
  `{namespace}/{collection}:roles/{role_name}/tasks/main.yml` — use the path
  `search_github_repo` returned (`ansible/roles/…` or `ansible/roles_ocp_workloads/…`),
  not a guessed one
- Content repo scripts (if showroom): `{owner}/{repo}:setup-automation/`
"""

RECONCILED[("aap2_agent.md", 90, 96)] = """\
- **Pick `get_job` vs `get_job_log` by purpose** — `get_job` to establish that a job
  exists or to read its status/template/timing; `get_job_log` once the job is known
  to exist and you need the log text. See "Choosing `get_job` vs `get_job_log`".
- **Job ID typos are common.** Once a job ID has come back not-found on *every*
  controller in scope, report that and offer a typo as the likely explanation — ask
  the user to double-check the number before widening the sweep to controllers they
  did not name. If you do widen, check all remaining controllers in a single batch —
  don't try them one at a time.
- **When the user provides a specific job ID**, query that ID directly — don't use
  `find_jobs` to *locate* it. Use `get_job` when you are establishing whether it exists
  or what its status is, and `get_job_log` when you need the log content. This shortcut
  skips the GUID/Babylon *discovery* steps only; if the job failed, still make the
  `get_job_events` call from Critical Rule 5. It also does **not** reorder the request:
  if the request *also* asks how many jobs failed, that is a separate population-level
  question and its `find_jobs` call comes **first** — see Step 0 below.
"""

RECONCILED[("aap2_agent.md", 17, 22)] = """\
3. **Budget your rounds — running out silently destroys your answer.** You get a
   limited number of rounds, and a "round" is ONE assistant turn, not one tool call:
   a turn with four parallel tool calls costs the same single round as a turn with one.
   When the rounds run out before you have written your findings, the user receives no
   answer at all — your entire investigation is discarded and replaced with a prompt
   asking whether to keep going. A partial answer always beats being cut off.

   **Spend rounds like this:**
   - **Batch every independent lookup into one round.** If two calls do not depend on
     each other's output, issue them as parallel tool calls in the SAME turn. Probing
     one search term per turn is the main way investigations run out of rounds.
   - **Never spend a round re-asking a question a previous result already answered.**
     Re-read the results already in your context first.
   - **Do NOT speculatively browse directories** — use `search_github_repo` or
     `lookup_catalog_item` to find paths in one call. **Never pass a directory path to
     `fetch_github_file`, and never guess a file path from naming convention.** Both are
     covered in "Finding a File in a GitHub Repo" below; it is the rule most often
     broken in this agent's traces.
   - **By your 12th tool call, stop investigating and write the report.** Treat call 12
     as a hard checkpoint, not a target. If you reach it still missing something, write
     the report anyway, name the gap, and add a confidence marker.
   - **Never spend more than 4 calls locating one file.** After four, write the report
     and state which file you could not locate and what you needed from it.
   - **Never re-fetch the same logical path from a different owner, repo, or ref hoping
     for a better answer.** Every org's copy of a role looks plausible and none of them
     is labelled "this is the one that ran". Fix the coordinates from a tool result
     instead (Step 6).
   - **Stop and write as soon as you can answer.** The moment a tool result contains
     the values the user asked for, your NEXT output MUST be the final answer — not
     one more confirming call. Confirming a value you already have costs a round and
     buys nothing.
   - **Once you are two thirds through your rounds, write the answer.** State what you
     found and mark what you could not resolve as unresolved. Do not open a new line of
     investigation late in the budget.

   **Worked example — the failure mode to avoid:**
   > A round fetches `defaults/main.yml` and the result contains
   > `workload_gitea_version: 1.22.3`, the exact value the user asked for.
   > ❌ The next round calls `search_github_repo` to "double-check the role name" →
   >    rounds run out, the user gets nothing, the whole investigation is wasted.
   > ✅ The next round is text: the version, the other values read from that file, and
   >    the `owner/repo:path` they came from.
"""

RECONCILED[("aap2_agent.md", 280, 281)] = """\
5. **Timing** — how long did the failing operation take? Short (< 10s) = auth failure,
   missing resource, or bad config. Long = the operation spent that time *waiting on
   something*. That tells you WHERE to look; it does not tell you the root cause is "a
   timeout". A timeout is the clock running out. The root cause is whatever it was
   waiting for, and why that thing never answered. Timing narrows the *candidates* — on
   its own it is never the cause. See Step 7a.
"""

RECONCILED[("aap2_agent.md", 504, 512)] = """\
- **OCP pod logs**: `search_by_guid` with the provision GUID returns all pod logs for
  that provision from the Babylon cluster — Anarchy runner pods, showroom pods, and
  workload pods. Filter with `errors_only=true` for failure investigation.

- **AAP2 controller logs**: Use `search_aap2_logs` with the **controller short
  name** (`east`, `west`, `event0`, `partner0`) — the same value you passed to
  `query_aap2`. Do NOT pass a fully-qualified hostname such as
  `aap2-prod-us-east-2-01.aap.infra.demo.redhat.com`; `search_aap2_logs` keys on
  the short name and an FQDN returns an empty result that looks like "no logs
  exist". If a `search_aap2_logs` call comes back empty and you passed a
  hostname, retry once with the short name before concluding there are no logs.

  **Start broad on AAP2 controller logs, then narrow. Your first call passes the
  controller and nothing else:**

      search_aap2_logs(controller="<short-name>")

  no `search_terms`, no `earliest`, no `latest`, no `errors_only`. The controller
  log set for one incident is small, and the decisive rows (rate limits and quota
  ceilings, capacity or storage warnings, isolated diagnostic probes) are often
  logged by a *different* component than the one that failed — and at INFO, not
  ERROR — so they contain neither the words you would think to search for nor the
  severity you would think to filter on. Read what comes back, *then* narrow.

  **Every filter you add to a Splunk search can silently empty it.** These three
  are the usual culprits, and all three fail the same way — a clean, empty result
  that reads like "those logs do not exist":
  - **`search_terms` is one literal substring, not a set of keywords.** Stacking
    three words you hope to find — `"<api-call> <resource> <error-class>"` — is
    matched as that whole phrase and hits nothing, even when all three words
    appear in the logs on separate lines. Pass **one** token (a single error
    class, or a single API name) or omit it entirely.
  - **`earliest` / `latest` narrow to nothing far more often than they help.**
    Omit them on controller-log searches. An incident weeks or months old sits
    outside any window you would reach for by default, and a tight window around
    a timestamp you *do* have still tends to come back empty.
  - **`errors_only=true` hides INFO rows**, which is exactly where isolated
    diagnostic probes and quota-limit notices live. Use it to triage a large
    result, never to find one specific row.

  If a search comes back empty, **remove a filter — never add one.** Removing
  the last filter and getting rows back is the normal outcome; it means the data
  was always there.

"""

RECONCILED[("aap2_agent.md", 517, 521)] = """\
1. Get the GUID and controller from `query_aap2`, `query_babylon_catalog`, or by parsing
   the job template name / bastion hostname
2. Search AAP2 controller logs **unfiltered**: `search_aap2_logs` with the
   controller short name and no other arguments. Read every row — the one that
   explains the incident is often not an ERROR and often names a different
   component.
3. Search OCP pod logs for container-level failures: `search_by_guid` with the GUID,
   unfiltered first — establish what else ran and what succeeded — then narrow with
   `errors_only=true` or `search_terms` if you still have not located the error itself.
4. If a search came back empty, broaden **once** by *removing* an argument
   (`search_terms` first, then `errors_only`, then the time bounds) — not by
   adding a different filter.

**Cap your Splunk usage at about four calls total.** Pod-log and Kubernetes-side
sources are frequently not forwarded for a given environment: if OCP pod logs or
Anarchy pod logs come back empty twice, that data does not exist here — record
"no pod logs available" and move on. Do not keep re-querying with new
namespaces, clusters, time windows, or SPL variations. Hand-written `search_raw`
SPL is a last resort, not a substitute for the structured actions.
"""

# ---------------------------------------------------------------------------
# babylon_agent.md
# ---------------------------------------------------------------------------

RECONCILED[("babylon_agent.md", 12, 17)] = """\
4. **fetch_github_file** — Fetch **one file's contents** by its complete file path. It is
   a read tool, not a discovery tool: resolve the path with `lookup_catalog_item` first and
   pass the path it returns, rather than a directory or a path guessed from convention.
5. **search_github_repo** — Search a repo's *pre-indexed* path list for paths matching a
   substring. Use ONLY when you do not know the path — it can never prove a file is
   absent, and it is not how you read a file whose path you already know (use
   `fetch_github_file`); skip it when the path is already known or was given to you.
6. **search_agnosticv_prs** — Search open agnosticv pull requests. `search` matches PR
   **titles and changed file paths** only — not the description, not the branch name.
   `state` defaults to `open`, so pass `state="all"` to see merged or closed PRs. Use this
   when a catalog item is referenced by a running job but absent from the index (it may
   exist only on an unmerged PR branch).
7. **query_provisions_db** — Run read-only SQL against the provision database
8. **Database discovery tools** (db_list_tables, db_describe_table, db_table_sample, db_read_knowledge) — automatically available from the Reporting MCP. Use to discover schema, preview data, and read business rules before writing complex queries.
9. **query_aws_account_db** — Query the sandbox account pool (DynamoDB) for account metadata
10. **query_splunk** — Search Splunk for Kubernetes pod logs from Babylon clusters **and**
    for AAP2 controller-side logs (CI check results, merge/approval events, scheduling and
    quota errors) via `action="search_aap2_logs"`
"""

RECONCILED[("babylon_agent.md", 76, 80)] = """\
   Call it **once** for the item you need. Do not call it again with the same search, and
   do not call it once per item when you already hold the account and stage (see
   "Deriving an AgnosticV Path Without the Index").
2. **Search the item segment, not the full dotted name.** The index is keyed on agnosticv
   *directory* names, not on `account.item.stage` CatalogItem names. Given
   `account.some-long-item-name.prod`, search `some-long-item-name` — drop the account
   prefix and the stage suffix. Passing the whole dotted name returns `not found` even
   when the item exists.
3. **A `not found` means your search term was too specific — shorten it once before
   giving up.** Retry with a distinctive substring of the item name (e.g.
   `some-long-item` → `long-item`). Only after a shortened substring also returns
   nothing, with no similar items, may you conclude the item does not exist.
4. If it returns `found: false` with no similar items after that retry, the item **does
   not exist** — and that holds only when the tool actually answered. Do NOT fall back to
   other methods to prove otherwise.
5. **A tool that did not answer is not a `found: false`.** Treat the lookup as having
   failed to answer when it returns `{"error": ...}`, or a result with no `owner`/`repo`
   fields, or a path under `ansible/configs/` or `ansible/roles/` (those are *agnosticd*
   source locations, not agnosticv config). In that case derive the path yourself from the
   naming convention below. Do NOT retry the lookup and do NOT substitute a
   `search_github_repo` keyword sweep — a sweep costs rounds and answers a different
   question than the one you have.
6. If it returns `found: true`, call `fetch_github_file` with the `owner`, `repo`,
   `path` **and** `default_branch` (as `ref`) from that same result. All four come
   from the tool — do not retype any of them from memory and do not mix one
   result's `path` with another's `owner`. Do NOT assume the owner is `rhpds`:
   `rhpds` owns the *agnosticv* repos, while AgnosticD *content* repos are owned by
   `agnosticd` (`agnosticd/agnosticd-v2`, current) and `redhat-cop`
   (`redhat-cop/agnosticd`, legacy). Guessing the owner produces "No search results
   found" or "File not found", which reads like "the file is missing" when it
   actually means "wrong owner".
7. If it returns similar items, present them and ask which one was meant.
8. **Fetch the path the user asked for, not the lookup's own `path`.** The result's
   `path` points at the agnosticv config directory for the catalog item. When the
   request names a different file — for example a workload role's
   `ansible/roles_ocp_workloads/<role>/defaults/main.yml` — fetch **that** path from
   the repo this result named. Substituting the lookup's `path` fetches the wrong
   file and wastes rounds on "File not found".

### Deriving an AgnosticV Path Without the Index

An AAP2 provision job template name encodes the location of its own config, and so does
the CatalogItem name. Both use the same three dot-separated parts:

    RHDP <account>.<catalog-item>.<stage>-provision
          |          |              |
          |          |              +-- file      -> <stage>.yaml
          |          +----------------- directory
          +----------------------------- account directory

    agnosticv path  =  <account>/<catalog-item>/<stage>.yaml
    shared defaults =  <account>/<catalog-item>/common.yaml

Worked examples (the account, item and stage all vary — read them off the name you have,
never assume a particular one):

    clusterplatform.ocp4-aws.prod   ->  clusterplatform/ocp4-aws/prod.yaml
    someaccount.some-lab.dev        ->  someaccount/some-lab/dev.yaml

For `owner` and `repo`, use the agnosticv/agnosticd repositories named in the
`fetch_github_file` tool description; a `v2` account directory lives in the v2 repo.
When a specific AnarchySubject or AgnosticVComponent is in evidence, its own `scm_url`
(`https://github.com/{owner}/{repo}.git`) is authoritative for that resource — or take
the pairing from the owner/repo table in the AAP2 agent's prompt. **Never probe a
guessed org**: listing directories or retrying `ref` after `ref` against the wrong
organization burns the whole budget and finds nothing.

**This derivation is a fallback, not a shortcut.** Still call `lookup_catalog_item` once
first — it is instant, it is the only thing that can tell you the item does not exist, and
its `default_branch` is what makes your source links correct. Derive the path only when
that one call did not answer (rule 5 above).

**When you can derive the path, you DO know the exact path** — so fetch it directly with
`fetch_github_file`. The general advice to "search first if you don't know the path" does
not apply to a path you just derived. Fetch `<stage>.yaml` first, since it carries the
stage-specific values and any credential includes; add `common.yaml` in the *same* round
if you also need the shared defaults. If a fetch 404s, try the other file in that same
directory — not a repo-wide search.
"""

RECONCILED[("babylon_agent.md", 229, 231)] = """\
Deep job failure analysis (log tracing, config-chain resolution, root-cause analysis) is
the AAP2 Investigation agent's specialty — name that agent when you are *recommending
follow-up work the investigator has not asked for yet*. But when the question in front of
you already requires that analysis, do it here: `get_job_log`, `fetch_github_file`,
`search_agnosticv_prs` and `query_splunk` are everything the chains above need. Never
answer a question by redirecting it.

### Tracing a Provision Failure to Its Config

Four rounds of work, in this order:

1. **Read the named job's log** with `get_job_log`. Take the failing task name and the
   error text **verbatim** — for a failed provision the error string is usually the whole
   diagnosis, and it is in your hands on round one. The `PLAY [...]` header names the
   catalog item being provisioned.

2. **Scope the blast radius** with `find_jobs` on the same controller with
   `status: failed` and **no date filter**. *Never guess a date window.* You do not know
   when the failure happened until the results tell you, today's date is not evidence, and
   a guessed window that returns `[]` costs a round and teaches you nothing. Get the
   unfiltered list, then read the `started` timestamps in it to see which failures cluster
   together. If a filtered call has already come back `[]`, do not narrow or shift the
   window — drop the filter.

3. **Read the job-template names in that list.** They hand you, at no extra tool cost, the
   account, the stage, and **every** affected catalog item. Count the distinct catalog
   items and state the count in that same turn, as a sentence that puts the number next to
   what is being counted — "<N> catalog items are failing", not a bare number in a table.

4. **Read the config that sets the value the failure complains about.** Call
   `lookup_catalog_item` once for the affected item; use the path it returns, or, if it did
   not answer, the path you derive per "Deriving an AgnosticV Path Without the Index". Then
   `fetch_github_file` that `<stage>.yaml`. Fetch it even if the log already gave you a
   theory: it is the only artifact that names the variable *and* the file the variable is
   pulled in from, and no amount of reading source code substitutes for it.

### When Several Jobs Fail the Same Way

An identical failing task plus identical error text across different catalog items on one
account means they depend on **one shared input** — not that each item is separately
broken. Say that explicitly: name the input, and say it is **shared**, the same one every
affected item uses. A per-item theory ("each lab has a bad reference of its own") is wrong
when the failing task and the message are the same in every job.

### Authentication and Credential Failures

When the error text is an authentication rejection — `unauthorized`, `invalid
username/password`, `401`/`403`, "please login", a refused or rejected token:

- **Do not go hunting through the Ansible role that emitted the message.** A role
  *consumes* a variable; it never holds the value. The value is set in the agnosticv config
  for the catalog item — `<stage>.yaml`, or a file that `<stage>.yaml` includes. Searching
  the role tree for the variable name, the task name, or the endpoint is the single most
  reliable way to run out of rounds on this kind of failure, because the answer is not
  there to be found.
- **Report two things about the credential**: the **variable or secret name**, and the
  **path of the file it is pulled in from**. An `includes:`/`include` entry in
  `<stage>.yaml` *is* that path — quote it exactly as written in the file.
- **Look for a change or rotation note.** Config files that hold a shared value often carry
  a comment recording when it was last changed outside this repo. If that change predates
  the failures, say the stored value is **stale** — it was **rotated** elsewhere and the
  copy in the config is **no longer valid**.
- **Say what the remote service did, in its own terms.** An authentication rejection is a
  *reply*: the service was reachable, it answered, and it refused the credential presented
  to it. Write that as an observation about the service — for a container registry, "the
  registry responded and rejected the credentials it was sent" — and then say what that
  establishes: the stored credential is wrong, and the service is doing its job.

  | what the log shows | what actually happened |
  |---|---|
  | connection refused, timeout, no route, DNS failure, 5xx | the service never answered |
  | an auth rejection, a refused token, a login prompt | the service answered and refused the credential |

  **Report only the row you landed on, and describe only what your evidence shows.** Do not
  write a sentence whose job is to deny the other row, do not name the explanation you are
  setting aside, and do not add a "ruled out" list, section, or heading. Naming a cause in
  order to dismiss it reads to anyone scanning your answer as though you had asserted it.

  | weaker (names a hypothesis) | stronger (names the evidence) |
  |---|---|
  | "this was not an infrastructure problem" | "the endpoint answered and refused the credential we sent" |
  | "no sign the service had stopped serving" | "the service returned an authentication error, so it was serving requests" |

- **Name only the credential the log actually names.** Do not speculate about other kinds
  of credential that the log says nothing about — a guess at a different mechanism is
  wrong more often than it is right, and it displaces the one you can evidence.
"""

# ---------------------------------------------------------------------------
# orchestrator.md
# ---------------------------------------------------------------------------

RECONCILED[("orchestrator.md", 20, 22)] = """\
short. If the user asks "why did this fail?" and a tool result shows the cause,
answer with the cause — not a walkthrough of how you figured it out. If no tool
result shows it, say the cause is not established by the data you have and name the
check that would establish it. "Not established yet, here is the check" is a
complete answer; a plausible-sounding cause you did not read in a result is not.
"""

# ---------------------------------------------------------------------------
# shared_context.md
# ---------------------------------------------------------------------------

RECONCILED[("shared_context.md", 186, 187)] = """\
- **Distinguish a backend error from a bad search term — they need opposite responses.**
  Read what the error is *about*:
  - **The tool or its backend is unavailable** — e.g. `Validation error in store ...`,
    `Unknown store ...`, `No simulation skill available for operation ...`,
    `Operation specification unavailable`, `Failed to generate valid JSON response`.
    These say nothing about your arguments, so rewording your search and calling the
    same tool again will fail identically and burn your remaining rounds. Treat that
    tool as unavailable for this investigation and switch to a **different tool** that
    can reach the same fact (e.g. `lookup_catalog_item` failing → go straight to
    `search_github_repo` / `fetch_github_file` on the repo).
  - **The tool worked but found nothing** — e.g. `not found`, `No search results
    found`, `{"results": []}`. Here your *arguments* are the problem: broaden the term
    (shorter substring, different naming convention) or try a different owner/repo.
  - **Hard limit: at most 2 attempts per tool per fact.** After the second failure on
    the same fact, change tool or change repo — never make a third variation of the
    same call.
- **A failed lookup/index tool is not a reason to start searching broadly.** When a
  convenience tool that resolves a name to a location fails, returns an error, or returns
  a result missing the fields you needed, do NOT retry it and do NOT substitute a broad
  keyword search. Derive the identifier or path yourself from data you already hold (a job
  template name, a URL, a resource name) and query the target directly. Broad searches
  spend several rounds and usually answer a different question than the one you have.
- **Never repeat an identical call — same tool, same parameters — in a conversation.**
  If a prior result already holds the value you need, read it from that result instead
  of calling again. This bans repeating a *call*, not touching a *resource* twice: a
  different tool, or the same tool with different parameters (a different `action`, a
  different filter), returns data the first call did not, so it is not a re-fetch and
  is not redundant.
"""

RECONCILED[("shared_context.md", 181, 184)] = """\
- **Empty results**: Say so clearly, and say so in the answer — not just in a table
  cell. "Clearly" means the negative carries the noun it applies to and names *what* it
  is that has no data: write "no provisions were found for this user" or "no failed jobs
  in the window", not a bare `None` or `0` in a cell whose meaning depends on its column
  header. An empty result is a finding about the data, not a value for the thing you
  asked about — see **"An absence is not a measurement"** under Grounding below, and
  report it in the shape given under "When a Search Comes Back Empty": the absence
  stated bare, what it does and does not tell us, and the next check. A verified absence
  is a real finding; a lone `None` is indistinguishable from "not checked". If the empty
  result blocks the task, suggest alternatives; but when you called a tool specifically
  to check whether something exists, the empty result IS the answer to that question —
  report it and move on rather than hunting for a non-empty one. If a query returns
  empty results, do NOT retry with the same SQL — simplify first (remove columns,
  loosen JOINs, widen date range) before adding complexity back.
"""

RECONCILED[("shared_context.md", 160, 162)] = """\
> [agnosticv config](https://github.com/{owner}/{repo}/blob/{ref}/{account}/{catalog-item}/prod.yaml),
> [agnosticd env_type defaults](https://github.com/{owner}/{repo}/blob/{ref}/ansible/configs/{env_type}/default_vars.yml),
"""

RECONCILED[("shared_context.md", 9, 11)] = """\
short. If the user asks "why did this fail?" and a tool result shows the cause,
answer with the cause — not a walkthrough of how you figured it out. If no tool
result shows it, say the cause is not established by the data you have and name the
check that would establish it. "Not established yet, here is the check" is a
complete answer; a plausible-sounding cause you did not read in a result is not.

## When a Search Comes Back Empty

A search that returns zero rows is a real finding — report it. But it is evidence
about the *search*, not about the system: it bounds what was indexed or stored, in
the window you asked for, at the severity or filter you applied, and nothing more.
An absence does not license any statement about what the system did or did not do.

Report it in this shape:

> **Searched:** `<tool/action>` for `<identifier>`, `<window>`, `<filters applied>`.
>
> **Result: no events — 0 results.**
>
> **What that establishes:** nothing matching `<identifier>` was indexed in
> `<index/source>` at that severity inside that window.
>
> **What it does not tell us:** whether the operation ran, whether it succeeded, or
> why it failed. An empty result is not evidence for any of those, so no cause is
> established here.
>
> **Next checks** — each named by the change to make and the data it would return:
> - drop the error/severity filter and re-run → whether any lines at all exist for `<identifier>`
> - widen the time window → lines outside the window first searched
> - `<the authoritative record for the object itself>` → its recorded status and message

Three rules the shape does not enforce on its own:

1. **State the absence bare, then qualify it.** Write "the search returned no
   events" (or "no results" / "0 results") as its own statement, then add the scope
   separately. Fusing them — "no error-level entries for this identifier in this
   index" — reads as a narrow technical caveat, and a reader skimming it misses that
   the search came back with nothing at all.
2. **List checks, not explanations.** Do not enumerate what might have happened: not
   as a list of possible causes, not as a "does NOT establish" list, not in scare
   quotes, and not as the thing a check would distinguish between. Name each check by
   the parameter you would change and the data it would return. A reader keeps the
   hypothesis and drops the hedge, so a hedged hypothesis is still a claim.
3. **Vocabulary.** In an empty-result answer do not use the word *never*, and do not
   use *confirms*, *proves* or *shows* about what the result means — each of them
   asserts more than an absence can carry. Phrase every open question as `whether …`.

Re-read the answer once before sending: is the bare absence in it, is the limit
stated in words ("does not tell us" / "does not mean"), is a named next check in it,
and is every sentence about the data rather than about what happened?

This applies to every empty result, not only logs: no CloudTrail events, no cost
rows, no monitoring history, no database rows.
"""


def build_file(fname):
    seed_lines = (SEED_DIR / fname).read_text().splitlines(keepends=True)
    per_donor_ops = {}
    for donor in DONORS:
        p = ARTIFACTS / donor / 'best' / fname
        if not p.is_file():
            continue
        donor_lines = p.read_text().splitlines(keepends=True)
        if donor_lines == seed_lines:
            continue
        ops = donor_opcodes(seed_lines, donor_lines)
        if ops:
            per_donor_ops[donor] = ops

    clusters = cluster_opcodes(per_donor_ops) if per_donor_ops else []

    splices = []
    for cluster in clusters:
        donors_in_cluster = sorted(set(d for d, op in cluster))
        i1 = min(op['i1'] for d, op in cluster)
        i2 = max(op['i2'] for d, op in cluster)
        if len(donors_in_cluster) == 1:
            if len(cluster) != 1:
                raise AssertionError(f"{fname}: standalone cluster has >1 op: {cluster}")
            d, op = cluster[0]
            if (fname, d, i1, i2) in ABSORBED_STANDALONE:
                continue
            donor_lines = (ARTIFACTS / d / 'best' / fname).read_text().splitlines(keepends=True)
            text = ''.join(donor_lines[op['j1']:op['j2']])
            overrides = STANDALONE_OVERRIDE.get((fname, d, i1, i2))
            if overrides:
                for old, new in overrides:
                    count = text.count(old)
                    if count != 1:
                        raise AssertionError(
                            f"{fname}: override old-string occurs {count} times "
                            f"(expected 1) in standalone splice ({d}, {i1}, {i2}): {old!r}"
                        )
                    text = text.replace(old, new)
                tag = f"standalone-overridden:{d}"
            else:
                tag = f"standalone:{d}"
            splices.append((i1, i2, text, tag))
        else:
            key = (fname, i1, i2)
            if key not in RECONCILED:
                raise KeyError(f"Missing reconciled text for conflict cluster {key} donors={donors_in_cluster}")
            splices.append((i1, i2, RECONCILED[key], f"reconciled:{'+'.join(donors_in_cluster)}"))

    splices.sort(key=lambda s: s[0])
    for a, b in zip(splices, splices[1:]):
        if a[1] > b[0]:
            raise AssertionError(f"{fname}: overlapping splices {a} vs {b}")

    out = []
    pos = 0
    for i1, i2, text, tag in splices:
        out.append(''.join(seed_lines[pos:i1]))
        out.append(text)
        pos = i2
    out.append(''.join(seed_lines[pos:]))
    return ''.join(out), splices


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_splices = {}
    for fname in FILES:
        merged, splices = build_file(fname)
        (OUT_DIR / fname).write_text(merged)
        all_splices[fname] = splices
        n_standalone = sum(1 for s in splices if s[3].startswith('standalone'))
        n_reconciled = sum(1 for s in splices if s[3].startswith('reconciled'))
        print(f"{fname}: {len(splices)} splices ({n_standalone} standalone, {n_reconciled} reconciled)")

    Path('/tmp/merge_splices.json').write_text(json.dumps(
        {f: [[i1, i2, tag] for i1, i2, text, tag in splices] for f, splices in all_splices.items()},
        indent=2))
    print("\nWrote merged files to", OUT_DIR)
    print("Wrote splice manifest to /tmp/merge_splices.json")


if __name__ == '__main__':
    main()
