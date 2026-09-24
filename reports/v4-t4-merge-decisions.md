# T4 (`tbt-merge`) — merge decisions and audit log

**What T4 is:** one merged 8-file prompt bundle for the v4 parsec benchmark, built by
combining every task's independently-T2-optimized edits (`artifacts/v4/<task>/best/*.md`)
against the shared seed (`artifacts/v4/seed/*.md`) into a single bundle
(`artifacts/v4/t4-merge/*.md`), so all 34 tasks can be scored zero-shot against one
candidate instead of 34 separate ones. T4 is "Approach A": a region-union merge of
disjoint donor edits, with hand-reconciled text for any region two or more donors both
touched. Approach B (whole-bundle re-optimization or similar) is deferred as **T5**
(merge-joint) in the spec's now-canonical arm scheme
(`docs/specs/2026-09-21-parsec-v4-experiment-plan-design.md` Sec.2).

**Where things live:**
- Merge script: [`scripts/build_v4_t4_merge.py`](../scripts/build_v4_t4_merge.py) (paths are
  script-relative, so `python3 scripts/build_v4_t4_merge.py` regenerates the bundle from any
  worktree that has this branch checked out).
- Merged output: `artifacts/v4/t4-merge/*.md` (8 files).
- Splice manifest: `/tmp/merge_splices.json` (a debug dump, regenerated on every run of the
  script; not committed — it's fully derived from the script + the committed donor bundles).

**Naming note — this report's arm ids are now canonical:** this session originally named
Approach A "T4" informally, before checking whether `results/v4/results.json`'s arm scaffold
already had a slot for it under a different id. At the time it did: **`G3`** (a
global-scope merge/merge-joint lineage that also had a `G4`). The spec has since dropped
that global-scope merge lineage entirely — **`T4`** (merge) and **`T5`** (merge-joint) are
the only ids for this experiment now (per
`docs/specs/2026-09-21-parsec-v4-experiment-plan-design.md` Sec.2, built into
[`scripts/build_v4_results_json.py`](../scripts/build_v4_results_json.py)'s arm scaffold);
the G-lineage stops at `G2`. Nothing below needs translating from "T4" to any other id —
this report's own informal naming turned out to be the one the spec adopted.

T4 has since actually run: `v4_t4_e1` (`parsec-intake_v4_t4_e1` worktree) evaluated this
merged bundle zero-shot against all 34 tasks (`n=5` trials), and its results are recorded in
`results/v4/results.json`'s `task_ledger[].t4_*` fields and `sections.task.t4_summary`, on
the `parsec-history` branch — see that branch's `results/v4/summary.md` ("T4" section) for
the write-up. Headline: a mixed result — 18/34 tasks improved, but 8 regressed, including 5
of the 13 tasks that were already perfect before the merge — exactly the failure mode this
audit's clean-merge gate exists to catch. Whether that means the gate needs to be stricter,
or it's simply a regression only a real eval surfaces, is open (see that same doc's "Next
moves").

## Method

For each of the 8 shared files, and independently for each of the 34 donors:

1. `difflib.SequenceMatcher(None, seed_lines, donor_lines, autojunk=False).get_opcodes()`
   gives every non-`equal` edit the donor made, anchored to seed line ranges `[i1:i2)`.
2. Union-find clusters opcodes (from any donors) whose seed ranges overlap
   (`a1 < b2 and b1 < a2`, strict inequality on both sides).
3. A cluster touched by exactly one donor is **standalone** — spliced in mechanically,
   verbatim, unless a **`STANDALONE_OVERRIDE`** entry rewrites part of its text or an
   **`ABSORBED_STANDALONE`** entry drops it (its content having been folded into a
   neighboring cluster's reconciled text instead).
4. A cluster touched by two or more donors is a **conflict cluster** — its merged text is
   hand-authored in `RECONCILED[(file, i1, i2)]`, replacing every donor's version.
5. All clusters splice left-to-right into the seed. `build_file()` asserts no two spliced
   ranges overlap.

## Ground-truth counts (current build)

| file | total splices | standalone | overridden | reconciled |
|---|--:|--:|--:|--:|
| aap2_agent.md | 68 | 43 | 11 | 14 |
| babylon_agent.md | 18 | 14 | 1 | 3 |
| cost_agent.md | 4 | 4 | 0 | 0 |
| icinga_agent.md | 21 | 21 | 0 | 0 |
| ocpv_agent.md | 0 | 0 | 0 | 0 |
| orchestrator.md | 25 | 24 | 0 | 1 |
| security_agent.md | 14 | 14 | 0 | 0 |
| shared_context.md | 25 | 19 | 3 | 3 |
| **total** | **175** | **139** | **15** | **21** |

("overridden" = standalone splices whose text was rewritten by a `STANDALONE_OVERRIDE`
entry before splicing; still counted once, not twice.)

### The 21 hand-reconciled conflict clusters

| file | seed range | donors |
|---|---|---|
| aap2_agent.md | 13–16 | platform-003, platform-008, platform-031 |
| aap2_agent.md | 17–22 | platform-005, platform-007, platform-031 |
| aap2_agent.md | 90–96 | platform-004, platform-022, platform-034 |
| aap2_agent.md | 203–205 | platform-001, platform-003 |
| aap2_agent.md | 234–238 | platform-001, platform-002, platform-004, platform-005, platform-031, platform-034 |
| aap2_agent.md | 247–248 | platform-003, platform-031 |
| aap2_agent.md | 268–269 | platform-003, platform-031 |
| aap2_agent.md | 280–281 | platform-008, platform-031 |
| aap2_agent.md | 343–348 | platform-001, platform-007 |
| aap2_agent.md | 414–417 | platform-001, platform-002, platform-003, platform-008, platform-031 |
| aap2_agent.md | 418–424 | platform-003, platform-007, platform-031 |
| aap2_agent.md | 454–457 | platform-001, platform-003 |
| aap2_agent.md | 504–512 | platform-031, platform-034 |
| aap2_agent.md | 517–521 | platform-031, platform-034 |
| babylon_agent.md | 12–17 | platform-005, platform-007, platform-033 |
| babylon_agent.md | 76–80 | platform-005, platform-032, platform-034 |
| babylon_agent.md | 229–231 | platform-032, platform-033 |
| orchestrator.md | 20–22 | platform-008, platform-023 |
| shared_context.md | 9–11 | platform-008, platform-023 |
| shared_context.md | 160–162 | platform-002, platform-005, platform-034 |
| shared_context.md | 181–184 | cost-029, icinga-011, platform-023 |

Each cluster's merged text is hand-authored directly in `RECONCILED[...]` in
`build_merge.py` — no separate log of the prose reasoning behind each one exists beyond
the script itself; that text *is* the decision record for these 21.

## Heading-disambiguation fixes (4)

Several donors independently extended the seed's own `Step N` numbering with a
self-chosen label, without seeing each other's edits, producing duplicate headings in
`aap2_agent.md`. Two pairs are true positional collisions (two donors' zero-width insert
opcodes at the *identical* seed point) that union-find cannot see, because two zero-width
ranges at the same point never satisfy the strict `a1 < b2` overlap test; the third pair
sits one seed line apart and isn't a positional collision at all, just two donors picking
the same label. Policy in all cases: keep whichever donor's section is physically first
unchanged (it keeps the canonical un-suffixed label); every later colliding donor's
heading, and its own self-references to that heading elsewhere in its text, get a
`-2`/`-3` suffix. No content is deleted; only headings and cross-references are rewritten,
via exact-substring replacement (never hand-retyped) so a large block can't suffer a
transcription error.

| seed point | first (kept) | renamed |
|---|---|---|
| (266,266) | platform-003 "Step 6b: Namespaced Roles Live in Their Own Collection Repo" | platform-031's "Step 6b" → **"Step 6b-2"** |
| (282,283)/(295,295) | platform-008 "Step 7a: Does the evidence actually establish a cause?" | platform-031's "Step 7a" → **"Step 7a-2"**; platform-034's "Step 7a" → **"Step 7a-3"** |
| (370,370)/(371,371) | platform-001 "Step 9: Assign Exactly One Root Cause Category" | platform-003's "Step 9" → **"Step 9-2: ...Naming the Mechanism Is Not Assigning a Category"** |

## Redundant/conflicting standalone splices dropped or folded (`ABSORBED_STANDALONE`, 9)

A handful of standalone splices sat at or adjacent to a conflict cluster's boundary, or
duplicated another standalone splice's point, in a way that (mechanically spliced as-is)
would have produced a dangling reference, a broken sentence, a re-opened numbered list,
or — in one case — a direct contradiction. Each was hand-verified and either dropped as
pure redundancy or folded into the neighboring cluster's reconciled text:

- **aap2_agent.md (418,418) platform-023** — a one-paragraph note folded into cluster
  (414,417)'s reconciled text.
- **babylon_agent.md (80,80) platform-005** — items continuing cluster (76,80)'s numbered
  list; folded in as that list's items 6/8.
- **babylon_agent.md (80,80) platform-034** — **directly contradicted** cluster
  (76,80)'s item 5 ("do NOT retry the lookup") by advising a retry for the same error
  case. The reconciled no-retry policy was kept; this donor's non-conflicting detail (an
  alternative owner/repo source) was folded into the reconciled text instead, and the
  contradictory retry advice dropped.
- **shared_context.md (11,11) platform-032** — redundant with platform-034's own
  "Investigation Budget" section at the same point; two distinct points folded in as new
  list items, the rest dropped.
- **shared_context.md (186,186) platform-005, platform-032** — folded into the
  neighboring reconciled cluster.
- **shared_context.md (214,214) platform-003** — a paragraph that only makes sense
  directly under "## Grounding", but splice ordering would have stranded it after three
  unrelated new sections; prepended to the (213,213) splice instead so it reads as
  Grounding's own coda.
- **shared_context.md (232,232) platform-003** — a sentence fragment written to continue
  directly off a seed bullet; sharing a splice point with platform-002's full paragraph on
  the same topic would have produced a broken sentence. Dropped — platform-002's paragraph
  already covers it.
- **shared_context.md (237,237) platform-001** — a third restatement of the same point
  made at (232,232), landing unheaded 128 lines past the section it's actually about. Its
  one non-redundant detail (a concrete `Confidence: high` field example) was folded into
  the (232,232) paragraph; the rest dropped.

Full line-level rationale for each is in `build_merge.py`'s comment block immediately
above `ABSORBED_STANDALONE`'s definition.

## Same-point collision audit

**Method:** group every `standalone`/`standalone-overridden` splice by exact `(i1,i2)`;
any group with 2+ entries is a same-point collision, hand-reviewed against this rule —
*benign* if no duplicate/confusing heading, no numbering collision, no dangling or
misleadingly-separated fragment, and no direct factual/procedural contradiction on the
same specific action (even if thematically similar or mildly redundant); *needs a fix*
only on a direct contradiction.

15 same-point collision points exist across the 8 files (0 in cost_agent.md,
icinga_agent.md, ocpv_agent.md, security_agent.md). All 15 have been reviewed:

| file | point | donors | verdict |
|---|---|---|---|
| aap2_agent.md | (125,125) | platform-031, platform-034 | benign — unrelated topics, sequential |
| aap2_agent.md | (206,206) | platform-001, platform-003 | benign — redundant but consistent (both warn against reusing the placeholder owner/repo) |
| aap2_agent.md | (266,266) | platform-003, platform-031 | **fixed** — duplicate "Step 6b" heading (see above) |
| aap2_agent.md | (275,275) | platform-008, platform-031 | benign — complementary (both: don't infer past the evidence) |
| aap2_agent.md | (295,295) | platform-031, platform-034 | **fixed** — duplicate "Step 7a" heading (see above) |
| babylon_agent.md | (6,6) | icinga-013, platform-032 | benign — unrelated topics, sequential |
| babylon_agent.md | (7,7) | platform-005, platform-033 | **fixed** — see below |
| babylon_agent.md | (40,40) | platform-023, platform-033 | benign — unrelated tools/topics |
| orchestrator.md | (12,12) | cloud-024, platform-034 | benign — unrelated, sequential |
| orchestrator.md | (26,26) | platform-022, platform-023 | benign — sequential, non-overlapping |
| orchestrator.md | (166,166) | platform-001, platform-002, platform-008, platform-034 (4-way) | benign — coherent progression, no clash |
| shared_context.md | (168,168) | platform-005, platform-034 | benign — topically out of place but no contradiction |
| shared_context.md | (213,213) | cost-029, icinga-010 | benign — complementary (absence-as-finding, both directions) |
| shared_context.md | (214,214) | icinga-013, platform-008, platform-022 | benign — distinct, no contradiction |
| shared_context.md | (237,237) | cost-029, icinga-013 | benign — distinct |

Re-run after every fix in this document; identical set of 15 points each time (no
regressions introduced).

## Defects found and fixed (4 total)

### 1. babylon_agent.md (7,7) — "6 tool calls" vs. "8 rounds" contradiction

Two same-point donors: platform-005's "## Critical Rules" section sets an **8-round**
budget; platform-033's own section imposed a hard **6-tool-calls** ceiling as a *different
unit* pointing at the *same* checkpoint number. Fixed by rewording platform-033's section
to speak in **rounds** (consistent with platform-005's unit) with the same "six is your
checkpoint, not your target" framing:
`STANDALONE_OVERRIDE[("babylon_agent.md", "platform-033-schema-change-not-the-oom", 7, 7)]`.

### 2. aap2_agent.md — Step 9 vs. Step 9-2 category-taxonomy swap

Not a same-point collision (seed 370 vs. 371 — one line apart, so the detector's exact
`(i1,i2)` match never fires). platform-003's "Step 9" table (renamed "Step 9-2" above)
had **swapped** two of platform-001's canonical "Step 9" definitions: it defined
`automation_failure` as "the automation platform itself broke — controller/EE/runner/
API fault" (word-for-word what Step 9 calls `platform_failure`), and narrowed
`platform_failure` to only the RHDP/Babylon provisioning layer. An agent following both
tables would classify the same AAP2 controller fault as `automation_failure` per one
table and `platform_failure` per the other. Fixed by rewording Step 9-2's two rows to
match Step 9's split (`automation_failure` = the invocation was wrong; `platform_failure`
= the platform itself erred), folding every distinct fact from platform-003's original
rows into the corrected `platform_failure` row so no information was lost:
`STANDALONE_OVERRIDE[("aap2_agent.md", "platform-003-tojson-dict-literal-rca", 371, 371)]`.

### 3. aap2_agent.md — a third, independent root-cause taxonomy table

Found by grepping the merged file for the recurring `` `automation_failure` ``/
`` `platform_failure` `` token pair (a content-pattern search, not a position-based one)
after fixing #2 — the grep returned a *third* pair of matching rows, from a section
neither Step 9 nor Step 9-2 reference: platform-002's own "Root Cause Category and
Confidence" table, a plain standalone insert at seed (424,424) — 54 seed lines past
Step 9-2, so not adjacent to either of the first two and invisible to both the same-point
detector and to visual proximity while reading the file top to bottom. Its
`automation_failure` row was "the automation harness never got as far as running the play
content — EE entrypoint, runner invocation, or inventory generation failed", which
contradicts the just-fixed consensus: Step 9-2's `platform_failure` row explicitly lists
"execution environment, runner" as symptoms of `platform_failure`, and Step 9 excludes
anything "outside the automation" from `automation_failure`. Fixed the same way as #2 —
reworded both rows to the same canonical split:
`STANDALONE_OVERRIDE[("aap2_agent.md", "platform-002-collection-not-found-rca", 424, 424)]`.

After this fix, all three sections agree on the identical 13-token taxonomy and on the
`automation_failure`/`platform_failure` split; confirmed by extracting the token set near
each of the three headings and by grepping the whole file for both tokens (4 rows total,
2 matching pairs of identical wording plus the just-reconciled third).

### 4. babylon_agent.md (76,80) / (80,80) — retry-vs-no-retry contradiction

Covered under "dropped or folded" above (platform-034's retry advice directly contradicted
the reconciled cluster's no-retry policy for the same error case); listed here again
because it is a content-level fix, not merely a redundancy drop.

## Methodology gap this audit surfaced, and how it was closed

The general same-point collision detector (group standalone splices by exact `(i1,i2)`)
is necessary but **not sufficient**. It structurally cannot catch:

- **Near-adjacent, non-identical collision points** — two donors' inserts a few seed
  lines apart (Step 9 at 370 vs. Step 9-2 at 371) can still conflict in content while
  never sharing an `(i1,i2)` key.
- **Cross-cluster topical conflicts** — content from one standalone splice can conflict
  with content from an entirely different, non-adjacent splice elsewhere in the same file
  on the same underlying topic (the third root-cause table at seed 424 vs. Step 9/9-2 at
  370/371).

Both were caught only by grepping the fully-merged file for a specific, recurring
content pattern (here, the `` `automation_failure` ``/`` `platform_failure` `` token
pair) rather than by any position-based check. Given this, the audit was broadened before
declaring the merge clean, checking every merged file for:

- **Exact duplicate `##`–`####` headings** — zero found (all prior duplicates already
  disambiguated per the heading-rename table above).
- **Duplicate `Step N` numbering** — checked across all 8 files; only aap2_agent.md had
  any duplicates, and all are now disambiguated (6b/6b-2, 7a/7a-2/7a-3, 9/9-2).
  icinga_agent.md and orchestrator.md have their own independent `Step N` sequences with
  no collisions.
- **Recurring numeric call/round budgets** (`N tool calls`, `N rounds`) — every file
  checked; the only multi-mention file is shared_context.md, where "18 calls" is a worked
  example under the file's own "20 tool calls" cap (consistent by construction, not a
  conflict).
- **Recurring closed-vocabulary token enumerations** (backtick-quoted tokens joined by
  `·`/commas, the shape a taxonomy table takes) — only aap2_agent.md's three root-cause
  sections match this pattern; all three now carry the identical 13-token set.

No further defects were found. This does not prove there is no fourth, subtler
conflict — only position- and pattern-based checks were run, not a full semantic review
of all 175 splices — but it closes every category of defect this merge has actually
produced so far, using the same technique that found defects #2 and #3.

## Status

- The clean-merge gate is now satisfied under this audit's criteria: every same-point
  collision reviewed, every duplicate heading disambiguated, every detected content
  contradiction fixed (4), and a broadened pattern-based sweep run with no further
  findings.
- The merge script (`scripts/build_v4_t4_merge.py`), the merged output
  (`artifacts/v4/t4-merge/*.md`), and this report are now committed on this worktree's
  branch. Confirmed the committed script reproduces byte-identical output before
  committing (reran it in place; splice counts per file matched this report's table).
- A dedicated worktree/branch, `parsec-intake_v4_t4_e1`, was forked from this commit to
  actually run the 34-task × n=5 zero-shot evaluation (170 trials) against the live
  parsec-live stack — see `handoff.md` there for the execution plan. That run has since
  completed and its scores are recorded in the **`T4`** arm in `results/v4/results.json`
  (see the naming note above; done on the `parsec-history` branch). T3 (`tbt-cross`,
  transfer) still needs its own row/decision — it isn't designed yet.
- The design doc (`docs/specs/2026-09-21-parsec-v4-experiment-plan-design.md`,
  branch `docs/parsec-v4-experiment-plan`) has since been updated: it now carries a T3 row
  (not yet designed) and adopted **`T5`** as the canonical id for Approach B, dropping both
  the tentative "T5"/"T6" naming above and the ledger's old `G4` slot.
