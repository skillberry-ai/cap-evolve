# Merge Log — 34 task edits into one prompt set

Inputs: `merge_inputs/seed/` and `merge_inputs/tasks/*/edit.diff`, plus each task's `instruction.md`
and `PROCESS.md`. `ocpv_agent.md` was touched by no task and is byte-identical to the seed.

Categories: **intact** = all of the task's text kept, only relocated or given a cross-reference;
**merged** = combined with other tasks' text into one rule; **partly dropped** = some content
removed or overridden, with the reason given.

## Per-task summary

| Task | Files | Handling |
|---|---|---|
| cloud-057-cloudtrail-select-only-refusal | orch, shared, security | **Partly dropped.** The orchestrator "mixed request" block is kept intact. The shared "Mixed Requests" section is merged with platform-116's read-only/mixed-request text into one section. In security, `userIdentity.username` is kept as the who-column, along with the NULL-attribution re-query rule, but the advice to fall back to `userIdentity.arn` is dropped: cloud-317 lists that column as unsupported, and its notes say re-adding it brings back the failure. |
| cloud-058-malformed-account-id | orch, shared, security | **Merged.** The orchestrator "Suspect Identifiers" and "Reporting a Request You Could Not Fulfil" sections are kept, with item 3 reconciled with platform-158 (ask the user only after your own retries are exhausted). The shared "error ≠ empty" bullet is merged with cost-408/051/402/155/201 into "Error, Empty, Zero, and No-Field Are Different Findings". The neighbouring-entity and three-part rules are kept in Grounding. The security hunks are kept, with a pointer to the shared rule. |
| cloud-317-namesake-user-other-account | shared, security | **Merged.** The shared multi-part-answer rules are merged with platform-004 and cost-402 into "Answering Every Part of the Request". The security hunks are kept as-is; they win the column-list conflict with 057 and are reconciled with 158 on `awsRegion`. |
| cost-051-gcp-net-of-credits | shared, cost | **Intact.** The shared "no field for it ≠ zero" text is kept verbatim as a bullet in the Error/Empty/Zero section. The cost subsection is kept, with a pointer added. |
| cost-402-unused-cost-preset-has-no-utilisation | shared, cost | **Merged.** The shared "unfilled slot" text goes into the Error/Empty/Zero section. "Answer every quantity" and "say where each figure came from" go into "Answering Every Part". In cost, the preset roll-up paragraph is merged with cost-418's into one subsection; the table and worked example are kept. |
| cost-407-aws-historical-query-came-back-org-wide | shared, cost | **Merged.** The shared "what the data does not cover is a finding" exception is kept, attached to the no-narration rule it qualifies. Its confidence-marker paragraph is merged with cost-418's. The cost scope-verification section is kept as-is. |
| cost-408-three-cloud-total-gcp-query-failed | orch, shared, cost | **Merged.** The orchestrator chart rule is kept as-is. The shared error/empty/zero text is merged into the combined section. The cached-view rule is kept in Tool Result Handling. In cost, one sentence that repeated "How to close" verbatim was trimmed, and the seed's "use cost_monitor for speed" intro was reconciled. |
| cost-418-capacity-window-starts-mid-review | shared, cost | **Merged.** The shared retry exception is merged into the single repeat-call rule. "Result metadata is data" is kept in Grounding. The marker-is-no-licence and decline-silently paragraphs are merged with cost-407's. In cost, the roll-up paragraph is merged with cost-402's; the window sections are kept. |
| icinga-045-hosts-search-filter | shared, icinga | **Intact.** "Keep each entity adjacent to its status" is kept verbatim in shared, and the icinga state-word and multi-host rules are kept. |
| icinga-201-soft-critical-not-yet-hard | shared, icinga | **Merged.** In shared, the empty-result "could not retrieve" sentence goes into the Error/Empty section, and the live-state retry becomes exception 2 of the unified repeat-call rule. In icinga, SOFT vs HARD is kept. The empty-live-state section is shortened to a pointer plus the icinga detail. "Answer the question first" is merged with 204 and 212. The word "silently" (do the reasoning silently) is dropped to fit 204/206/216's "show the arithmetic". |
| icinga-204-downtime-window-expired | icinga | **Merged.** Its epoch procedure is merged with 206/212/215/216 into one Timestamps section (Method A); its 1760000000 example is cut to a one-line reference value. Downtime-coverage rules are kept under "Reading Downtimes", reconciled with 216's flexible downtimes. Its output-format rules are merged with 201 and 212. |
| icinga-206-stale-ok-check | shared, icinga | **Merged.** The shared as-of, age-is-not-a-date and don't-ratify-the-premise rules are kept verbatim in Grounding. In icinga, Step 0.05 and the stale-result wording are kept; its day-number epoch method became Method B of the unified Timestamps section. |
| icinga-212-fix-on-main-not-on-pinned-ref | icinga | **Merged.** Pinned-ref fetch, fetch-twice-and-diff, Step 2.5 and the plain-sentence verdict are kept. Its epoch section is merged into Timestamps. Its retry paragraph is shortened to a pointer plus the ref-comparison specifics, and two generic phrases are dropped. |
| icinga-215-ack-comment-author-and-expiry | icinga | **Merged.** "Reading Comments and Acknowledgements" is kept. Its epoch content is merged into Timestamps. "Epochs a few hours apart land on the same date" is reconciled with 216's midnight-crossing windows. |
| icinga-216-flexible-downtime-duration | shared, icinga | **Merged.** The shared epoch conversion/multiply-back bullet is kept verbatim. In icinga, the downtime field table and fixed-vs-flexible rules are merged with 204 into "Reading Downtimes". Staged subtraction and the multiply-back diagnosis go into Timestamps. The midnight worked example is kept, condensed. |
| icinga-222-lag-check-runs-on-satellite | shared, icinga | **Merged.** The shared transient-vs-deterministic classification is merged with platform-158's refusal-vs-no-answer into one "Failed Tool Calls" section. Its no-proxy-substitution bullet is kept, reconciled with 158's pivot. Its repeat-call text is merged into the unified rule. The icinga Step 0.2 is kept as-is. |
| platform-004-events-then-config | shared, aap2 | **Merged.** In shared, the Sources example URL is changed to placeholders and the placeholder note is kept. Its retry exception goes into the unified repeat-call rule, the "different action is not a re-fetch" bullet replaces the seed bullet, and "Answer Every Field" is merged into "Answering Every Part". In aap2, its rules 3/4 are merged with 148 and 158, the log-vs-events table is kept, Step 1 requires the events call, and the v2 owner is reconciled with 005 and 104. |
| platform-005-wrong-owner-trap | orch, shared, aap2, babylon | **Partly dropped.** The orchestrator "ask only about genuine ambiguity" paragraph is kept. The shared "A missing path is not a wrong container" section is kept, minus the words "/ directory listing" in step 2 (they conflict with 007). Its Sources-URL fix (`agnosticd/…`) is superseded by 004's placeholders: the wrong owner is gone either way, and placeholders are more general. In aap2, "named routes, not guesses" and "no fixed call quota" are kept, and the owner text is softened to "commonly `agnosticd`" to fit 104's "parse it from the URL". The babylon step 5 is kept, with a pointer. |
| platform-007-directory-path-fetch | orch, shared, aap2, babylon | **Merged.** The orchestrator "Reading source-repo files" routing is kept. The shared "GitHub Path Discovery" section is kept and grouped with 005 and 153 under "Reading Files from GitHub", with a pointer to the pinned-ref rule. In aap2 and babylon, the tool descriptions and response formats are merged with 032/137/152. The "zero matches is authoritative" claim is qualified, since 137/152 say an empty result does not disprove a given path or prove a symbol is unused. |
| platform-032-shared-secret-not-a-registry-outage | aap2, babylon | **Merged.** In aap2, "two dead calls" became rule 5 ("dead" means not-found; timeouts are retried first, per 152/158), "the source said unavailable" became rule 6, and the shared-cause and auth-vs-outage text is kept. In babylon, the tool entry is folded into 007's; the paths-only, declared-unreadable and round-budget sections are kept. |
| platform-101-vcpu-quota-from-catalog-sizing | shared, aap2 | **Merged.** Its line-citation section is merged with 104/136/153 into one "Citing a Specific Line" section; its YAML worked example is kept as example 1. "Stating a Derived Comparison in Plain Prose" is kept verbatim. The aap2 search-by-identifier rule and the two-`found:false` rule are kept. |
| platform-104-cfn-dependency-and-what-changed | orch, shared, aap2 | **Partly dropped.** The orchestrator "same job = one domain" rule is kept, with a sentence distinguishing it from 158's region case. In shared, the citation form, Routes A/B, agreement gate and worked example are kept in the merged line-citation section. Its "keep Routes A/B out of the final answer" is relaxed: 101/136/153 require a numbered block in the answer, so the cited span is shown and the full transcription is working notes. "Literal values must be plain text" is kept and moved to the style block. In aap2, Steps 7d/7e, `changed_only` and git_url owner parsing are kept, and the line-number pointer is reworded. |
| platform-112-exec-pool-disk-not-the-bastion | aap2 | **Merged.** Kept: the which-host rule (merged with 004), resource exhaustion relabelled Step 7f and proposed-fix assessment as Step 7g (the 7a label collided with 148), and the Splunk matching rules (merged with 155). The seed's FQDN controller instruction is dropped, because both 112 and 155 contradict it. |
| platform-116-timeout-headroom-from-history | shared, aap2 | **Merged.** In shared, "Quote numbers in the unit the tool returned" (with the zero-count exception) and "Name the cause you found" are kept; the two duplicated carve-out bullets inside the latter are merged into one. The read-only/mixed-request text is merged with 057's, and "every tool only reads" is scoped to exclude write actions an agent's own prompt lists (Icinga ack/downtime). In aap2, get_job-first, history comparison and the "Erroring task" rename are kept, reconciled with 004 on read order. |
| platform-121-near-miss-pick-partner-repo | shared, babylon | **Partly dropped.** In shared, "broaden only while you have no candidate" is folded into the existing "broaden immediately" bullet as its exception; "wrong target vs wrong filename" is kept. In babylon, Critical Rules and similar_items handling are kept, but "fetch the directory listing with a trailing /" is replaced with one `search_github_repo` call, since 007 established that directory fetches return an error. |
| platform-124-event-accounts-not-returned | aap2 | **Intact.** "No Job Exists for a GUID" and the verbatim-identifier report rules are kept as-is. |
| platform-126-stop-job-from-tower-jobs | babylon | **Intact.** The get_job vs get_job_log table, decision rule, example and formats are kept as-is. |
| platform-136-provision-key-mode-too-open | shared, aap2 | **Merged.** In shared, its rules (count every line, cite the value not the comment, a log line number is not your citation, no fetch means no line) and its worked example are kept in the merged line-citation section. In aap2, the general procedure is shortened to a pointer; both AAP2 traps (`task path:` and comment-above-setting) are kept. |
| platform-137-generated-password-forbidden-chars | aap2 | **Merged.** "One fix, not a menu", "Recommending the Fix" and Root Cause item 4 are kept verbatim. "When the log names the file, fetch it" and path-from-log are merged with 104, and the ref-retry is merged with 104's. |
| platform-148-precheck-caches-nxdomain | aap2 | **Merged.** "Budget rounds" and "every asserted value from a result" are merged into rules 3/4. Step 7a (the cache deep dive) and the route-by-shape list are kept. The theory-verdict text, duplicated in two places, is merged into one section with 155 and 112. Role-file enumeration is reframed so it does not search for a path the log gave. |
| platform-152-path-search-cannot-find-variable-uses | aap2 | **Partly dropped.** Its rule 5 (retry once) is merged into Critical Rule 7. Its line-counting procedure and YAML worked example are replaced by a pointer to the shared line-citation section, which carries the same procedure and three worked examples. "State it as a digit" and "read the comments around the target" are kept, and "Reading an empty search_github_repo result" is kept in full. |
| platform-153-override-uses-removed-variable-name | shared | **Merged.** "Fetching a File at the Revision That Is Actually Deployed" and "Reporting a Setting That Is Not In Effect" are kept verbatim. Its line-citation section is merged with 101/104/136; its de-numbered excerpt block, "never carry a number over" and "state one number consistently" are kept. |
| platform-155-order-time-was-queue-wait | shared, aap2 | **Merged.** The shared "check your own arguments before reporting empty" and "lacks this field ≠ doesn't exist" bullets go into the Error/Empty section. In aap2, the scheduling/queue-wait section, short-name Splunk matching (merged with 112) and response-format fields are kept. |
| platform-158-lab-instances-outside-default-region | orch, shared, aap2, security | **Merged.** All orchestrator text is kept: outsourcing questions, successful-job delegation, the region rule, provisioning jobs as facts, "blocked step" and After-Delegation gating. Its triple-stated re-delegate-once instruction is reduced to one statement plus pointers. In shared, the Babylon-timeout and 429 tips, "Use Every Identifier" and "Scoped Lookups" are kept. "Refusal vs No-Answer" is merged with 222 as "Failed Tool Calls: No-Answer vs Deterministic Failure", and the confidence-marker clause is kept. In aap2 and security, the text is kept and reconciled with 317 on `awsRegion`. |

**Totals:** 4 intact (icinga-045, cost-051, platform-124, platform-126); 25 merged; 5 partly dropped
(cloud-057, platform-005, platform-104, platform-121, platform-152). No task was dropped entirely.

---

## Conflicts resolved, per file

### shared_context.md

1. **The "never call the same tool with the same parameters twice" bullet was rewritten five
   ways** (201, 222, 418, 004, 158). It is now one rule allowing exactly two single
   identical re-issues:
   - a call that never answered (timeout, unavailable, 5xx);
   - a live-state query that came back empty for something the user says exists (201).

   Both cases share one stop condition: after two identical failures, no third try. Then
   change the query, switch source, or name the missing figure, without substituting a
   roll-up (418).
2. **Two failure taxonomies.** 222 (transient vs deterministic) and 158 (refusal vs
   no-answer) became one section. A no-answer gets one retry. Deterministic failures are a bad
   argument (fix it) or a refusal (never retry; get the fact elsewhere). 158's tie-breaker on
   the word "unavailable" is kept. The heading was renamed, and every in-file reference
   updated.
3. **222's "never substitute a proxy" vs 158/155's "get the fact from another service".**
   Reconciled: moving to a source that actually carries the same fact is allowed. Treating an
   easier call that does not carry it, such as a broad keyword search, as covering the
   ground is not.
4. **Five tasks on error/empty/zero** (058, 408, 051, 402, 155, 201). These became one
   subsection with four distinct findings: error, empty (with the argument-check, scope-check
   and user-says-it-exists rules), real zero vs unfilled slot, and no-field. 155's "lacks
   this field ≠ does not exist" closes it.
5. **Four line-citation sections** (101, 104, 136, 153) became one. They clashed on what goes
   in the final answer:
   - 101 and 136 want the numbered listing written in the reply, and 153 wants a numbered
     excerpt block.
   - 104 wants Routes A/B kept out of the answer, with only the citation shown.

   Resolved: the answer shows a numbered block of the relevant span, and the full
   line-1-to-target transcription and the `\n` tally are working notes. 104's "cite the block
   start" applies only when narrowed to a block; 136/153's "cite the value line, not the
   comment" governs otherwise. All three worked examples are kept.
6. **Sources example URL.** 004 replaced the wrong-owner agnosticd URL with
   `{owner}/{repo}/{ref}/{config}` placeholders; 005 replaced it with the `agnosticd`
   owner. I kept 004's placeholders because they are more general. Both tasks' intent, to
   remove the wrong owner, is met, and 005's "never from a remembered default" is kept in
   the placeholder note.
7. **Two "mixed request" sections** (057 and 116) became one. 116's numbered steps
   (one-sentence refusal, name the owner and setting) are folded into 057's three steps, and
   057's worked example and no-inner-emphasis rule are kept. 116's "every tool you have only
   reads" contradicts the Icinga agent's explicit acknowledge/downtime write actions, so it
   is scoped: "except for any write operations your own agent prompt explicitly lists".
8. **Two "a confidence marker is not…" paragraphs** (407 and 418) became one. Its
   "interpretation vs coverage" and "decline silently about the value" parts are kept.
9. **Three "answer every part" texts** (004's checklist, 317's yes/no and negated
   absences, 402's one-sentence-per-missing-figure) became one section. 317's "do not hedge a
   verified absence" now cross-references Scoped Lookups, because an unconfirmed-scope empty
   is not a verified absence.
10. **"Broaden immediately" vs 121's "broaden only while you have no candidate".** The
    exception is folded into the existing bullet.
11. **005 step 2's "search / directory listing" vs 007's "never fetch a directory".** I
    dropped "directory listing".
12. **007 "omit `ref` to get the default branch" vs 153 "always pass the pinned ref".** 007's
    sentence now adds "or a config you read pins one" with a pointer to 153's section.
13. **116's "Name the cause you found" contained two near-identical carve-out bullets.** I
    merged them into one, and it now covers "or whether something happened" (317's yes/no
    questions).
14. **Placement.** The style rules (407 exception, 045 status adjacency, 104 literal values,
    116 raw numbers) are grouped at the top under the opening style paragraphs. 104's literal
    values section moved there from Source Citations. 007, 005 and 153's GitHub sections are
    grouped under a new `## Reading Files from GitHub` heading. The seed's Investigation Tips
    and Catalog Item Search Strategy stay under Security, as in the seed.

### orchestrator.md

1. **158 "don't ask the user which source to retry" vs 058 "ask the user for the corrected
   value".** 058's item 3 now says to ask only once your own retries and alternative routes
   are exhausted. A malformed user-supplied identifier is still asked about, since no tool
   can repair it. 158's "blocked step" paragraph points to 058's three-part report form.
2. **104 "a single job's what-changed question goes only to `investigate_aap2_job`, no
   security dispatch" vs 158 "a named job goes to aap2 first, then security, for an
   inventory".** These don't conflict: 104 covers changes made by the job, and 158 covers a
   parameter (the region) feeding a security inventory. I added one clarifying sentence.
3. **158 stated "re-delegate once on timeout" three times** (region rule, blocked-step
   paragraph, After Delegation). The region bullet now points to the blocked-step paragraph
   instead of repeating it.
4. **Pointers on the `investigate_aap2_job` description** now cover both 158 (successful
   jobs) and 007 (source-file reading). 005's "never ask to continue" and 057's "don't
   confirm a read-only lookup" agree, so both are kept.

### aap2_agent.md

1. **Which job read comes first.** The seed, 004 and 158 say the log; 116 says `get_job`
   first. Resolved: `get_job` goes in the first batch alongside the log/events reads,
   never after them. 004's required `failed_only` events call stays in Step 1.
2. **Search before fetch (007/148) vs never search a path the log gave you (104/137).**
   Resolved: search only when you lack the path, and fetch directly when it was given. 148's
   role enumeration covers only files not given.
3. **What a zero-match search means** (007: the path does not exist; 137: not proof; 152:
   paths only). Resolved: no path contains the substring, so don't descend directories. It is
   not proof that a given path is missing, and never evidence that a symbol is unused.
4. **032's "two dead calls" vs the one-retry rule (152/158/004).** "Dead" means not-found;
   timeouts get one retry first. 032's single exception is extended to verbatim given paths
   (005).
5. **Budget vs completeness** (032/seed vs 004/005). The budget applies to speculative
   browsing only; asked-for fields must be answered, and the report is written the moment
   every part can be answered.
6. **v2 owner.** The seed says `rhpds`; 004/005 say `agnosticd`; 104 says parse it from
   `git_url`. Resolved: parse it from the tool result, or take the user's verbatim
   owner/repo, with "commonly `agnosticd/agnosticd-v2`" as the default.
7. **Splunk.** It is optional in general but required for capacity causes (112) and queue-wait
   questions (155). Time windows are set per purpose. The controller value is the short name
   (112/155 override the seed's FQDN instruction).
8. **Duplicated theory-verdict text** (148 ×2, 155, 112) and **"answer every part" text**
   (032, 148, 004) were each merged into one section. The colliding Step 7a labels were
   resolved by relabelling 112's steps to 7f/7g.

### icinga_agent.md

1. **Five separate epoch-conversion sections** (204, 206, 212, 215, 216) became one
   Timestamps section. Method A anchors on the year (204/212/215). Method B is the
   day-number difference from a reference date (206 + 216). Both share one verification
   step (212's two checks plus 216's diagnosis of the difference) and use unified variable
   names. All the worked epochs were checked arithmetically by the sub-merger.
2. **Show the working vs report results only.** 201 says reason silently, never put scratch
   above the answer; 204/206/216 say show the arithmetic. Resolved: answer first, then a
   brief working block after it.
3. **215 "epochs hours apart land on the same date" vs 216's midnight-crossing windows.** It
   now reads "same date, or adjacent dates when they straddle midnight".
4. **204 "`is_in_effect` is authoritative, open window = in effect" vs 216 "a flexible
   downtime does not mute at start_time".** Resolved: a flexible window that is open but not
   triggered is the one case where `is_in_effect` is legitimately false.
5. **The seed's "if already in downtime, report this first"** was narrowed to "actually in
   effect" (204).
6. **Output Format.** 201's and 204's preambles and 212's sub-question bullets became one
   section.
7. **Step 1 ordering** (201 and 206 edited the same lines): Determine State, then Date the
   State, then Determine Confirmation.

### cost_agent.md

1. **402 vs 418.** Both added a "roll-ups are placeholder zeros" rule at the same place. They
   became one subsection, using 402's table with 418's "headline figure from the preset that
   computes it" and "sum the per-dimension rows" folded in.
2. **408 vs the seed intro "use cost_monitor for speed".** The intro is now conditioned on
   "the figure is not itself the deliverable", pointing to 408's cached-vs-source section.
3. **Ordering.** The date sections now run: windows (418), per-provider semantics (seed),
   scope verification (407).

### babylon_agent.md

1. **007 and 032 both rewrote the tool list and the `search_github_repo`/`fetch_github_file`
   formats.** They became one entry each, and "zero matches is authoritative" is qualified as
   holding for a path query against the correct carried owner/repo.
2. **121 "fetch the directory listing with a trailing /" vs 007 "directory fetches error".**
   Replaced with: try `common.yaml`, then the stage file, then one `search_github_repo`.
3. **121's "limited calls" vs 032's explicit round budget.** The two sections are placed
   together, with a pointer between them. 005's one-search step and 032's "accept zero
   results" agree, since both allow exactly one search.

### security_agent.md

1. **057 vs 317 on identity columns.** 057 allowed falling back to `userIdentity.arn`; 317
   lists it as unsupported. 317's exhaustive column list is kept. 057's NULL-attribution rule
   now says to re-query with `userIdentity.username`, or to drop the aggregate. The seed's
   Marketplace sample SQL was changed from `arn` to `username`, and the seed's
   `requestParameters` note gained one sentence; both changes remove direct contradictions
   with 317.
2. **158 "read `awsRegion` from CloudTrail" vs 317 "`awsRegion` unsupported".** Region
   discovery through `query_cloudtrail` is kept, but run alone. Zero rows or NULLs mean
   "region not established", and the agent then moves on to the next source. `lookup_events`
   is still allowed.
3. **317 replaced the seed's "empty results → widen immediately".** The ±5–10 minute
   widening is kept only in the IAM-key playbook. The seed's `lookup_events` preference is
   narrowed to recent activity, to match 317 and 158.
4. 057's reference to the "never call the same tool twice" rule now refers to it by topic,
   matching the reworded shared rule.

### ocpv_agent.md

No task edits it, so it is unchanged and byte-identical to the seed.
