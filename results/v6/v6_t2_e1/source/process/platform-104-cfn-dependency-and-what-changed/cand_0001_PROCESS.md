# PROCESS — what I did this iteration (explainability; REQUIRED)

## Method note (how I got a per-item signal instead of guessing)

The `trajectories/*.json` files carry no trace (`"trace": null`), only a reward
scalar. But each one's `metadata.trial_dir` points at the live Harbor trial, which
still holds `agent/agent.jsonl` (the full stream-json transcript) and the verifier
output. I re-ran the task's own verifier offline over all 10 seed transcripts:

```
python3 tests/verify.py --expected tests/expected.json --agent-logs <trial>/agent --out /tmp/...
```

This reproduced all 10 published rewards exactly (0.8 0.8 0.8 0.8 0.9 0.7 0.8 0.8
0.7 0.6), which means the offline harness is faithful — so `reward-detail.json`'s
`required_missed` / `citations_missed` / `unmatched_expected` are a **measured**
per-item miss matrix, not an inference. Every claim below comes from that matrix.

### The measured miss matrix (10/10 seeds)

| seed | answer items missed | expected tool call missed |
|---|---|---|
| 0 | guard-gap, assoc-line | — |
| 1 | assoc-line | fetch_github_file(template) |
| 2 | guard-gap, assoc-line | — |
| 3 | guard-gap, assoc-line | — |
| 4 | guard-gap | — |
| 5 | guard-gap, assoc-line | fetch_github_file(template) |
| 6 | guard-gap, assoc-line | — |
| 7 | assoc-line | fetch_github_file(template) |
| 8 | guard-gap, assoc-line | fetch_github_file(template) |
| 9 | key-pair, bucket, assoc-line | query_aap2(changed_only=true) |

Nothing else ever missed: `cfn-error` 10/10, `changed-tasks` (count=3) 10/10,
`forbidden` never tripped 0/10. So the entire 0.23 of lost reward lives in exactly
four mechanisms, ranked below.

## Ranked issue list (clusters by # failing tasks × trials, biggest first)

| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | **`assoc-line` — line citation never credited (9/10 trials)** | platform-104 | Two separate defects, both measured. (a) The agent cites the **wrong line**: it names the `{% endif %}` (36), the definition (30/31), a property line (41), or the *rendered* offset (33/34/35) instead of line 38 where the referencing block starts. (b) When it is right it is often **unusable**: a range ("lines 33–38"), two candidates ("34 or 39"), or the number parked in a later sentence — `_citation_present` only accepts a single number within 24 chars after the path. 4 seeds cited no line at all. | BEHAVIORAL | decision rule + explicit counting/format contract |
| 2 | **`guard-gap` — correct diagnosis, unscoreable prose (7/10 trials)** | platform-104 | The agent *understood* the bug in all 7 misses; it wrote the key phrase with markdown **inside** it: ``sits **outside** the `{% if %}` block``. This contract does **not** set `fold_markup`, so the verifier matches raw text and "outside the guard"/"outside the conditional" is split by the `**`/backticks and never matches. Stripping ``[`*_]`` from the same answers newly HITs 4 of them — proof the loss is formatting, not reasoning. | BEHAVIORAL | output-contract rule (keep literals/phrases contiguous) |
| 3 | **template fetch missed via owner-guessing + path-searching (4/10 trials)** | platform-104 | `get_job_log` hands the agent `git_url: .../<owner>/<repo>.git` **and** the exact template path in the task's `src:`. The agent ignored both: `aap2_agent.md` Step 6 carried a **static owner table** mapping agnosticd-v2 → `rhpds`, so the agent swept `rhpds`, `redhat-cop`, `agnosticd` with 9–12 `search_github_repo` calls (seed 5: 42 total calls; seed 7: 38) and in 4 seeds never landed the one correct `fetch_github_file`. | KNOWLEDGE (bad fact in prompt) | correct the table → parse from `git_url`; forbid the sweep |
| 4 | **`changed_only` not called → named resources lost (1/10, worst trial)** | platform-104 | Nothing in any of the 8 files mentioned `changed_only` (verified: `grep -rn changed_only *.md` was empty). Step 5 named only `failed_only=true`. Seed 9 called `failed_only` only, so the key pair and bucket — which exist **solely** in the changed events, because the log is trimmed to a 1,251-byte tail of 2,214,660 — were unrecoverable. It still got count=3 from the PLAY RECAP, which is why the loss shows up as two name items, not the count. | KNOWLEDGE | add the `changed_only` trigger + a section on reading it |
| 5 | wasted parallel security dispatch (10/10, costs tokens not reward) | platform-104 | Orchestrator fans out `investigate_security` alongside the AAP2 agent for the "what was created" half. CloudTrail/account-pool have no data and no account id is derivable from a job id, so it returns 0 rows every time and appends a "Blocked / unable to retrieve" report after an otherwise good answer. Never tripped `forbidden`, so it is a cost + answer-dilution issue. | BEHAVIORAL (routing) | routing discriminator |

## Changes made this iteration (one row per edit)

| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | DECISION RULE + CONTRACT | `aap2_agent.md` new **Step 7d**; `shared_context.md` new **"Citing a specific line"** | New Step 7d names the general mechanism — *a cloud API rejects a **rendered** template because a name it references is undefined; the definition is inside a conditional/loop and a reference sits outside it* — and prescribes: find **both** sites, compare guards, and cite the line where the **referencing block begins** (not the definition, not the `{% endif %}`, not an inner property). `shared_context.md` adds the format contract: one line, number immediately after the path, counted from line 1 of the **fetched** content including blanks/`---`/`{% %}` lines. The "count from what you fetched, not the rendered view" rule is what kills the 33/34/35 class of answer. | Yes — adds a rule for a case nothing handled; the `owner/repo:path:line` form is only *more* specific about a format already requested. |
| 2 | OUTPUT CONTRACT | `shared_context.md` new **"Literal values must be plain text"**; reinforced in Step 7d | "Keep each literal contiguous; never put `**` or a backtick *inside* a value or key phrase." Given with the three shapes that actually break: an identifier split mid-name, a count separated from its noun, and a cause phrase broken by emphasis — each with a wrong/right pair. Generalizes to every task graded on literal names or counts, which is most of this suite. | Yes — it constrains *formatting* of the same content, never what is reported. Emphasis around a whole phrase is still explicitly allowed. |
| 3 | KNOWLEDGE (fact correction) | `aap2_agent.md` Step 6 | Replaced the static owner table with **"always take owner/repo from the job's own `git_url`"** + a worked parse example, and added an explicit **stop rule**: do not try other owners when a fetch is empty; retry once with `ref` omitted, then write the report. The old table was actively wrong for the fork this job used — exactly the "wrong owner" mistake the verifier's own comment calls the most common real error. | Yes — strictly more accurate. Any job whose `git_url` matches the old table still resolves identically, because it is parsed from the same URL. |
| 3 | DECISION RULE | `aap2_agent.md` Step 6 | **"When the log already names a file, fetch THAT path — do not search for it."** Ansible prints real repo-relative paths in `src:`/`dest:`/`task path:`; strip the `/runner/project/` prefix and it *is* the `path` argument. Worked example included. `search_github_repo` is reserved for when no path is known. | Yes — it removes speculative search, which existing Critical Rule 3 ("do NOT speculatively browse") already asks for; this makes it actionable. |
| 4 | KNOWLEDGE + TRIGGER | `aap2_agent.md` Step 5b + new **Step 7e** | Step 5b: if the user asks what was created/changed/needs cleanup, **or the log is trimmed**, you MUST also call `get_job_events(changed_only=true)` — and both `failed_only` and `changed_only` when both halves are asked. Step 7e explains *why* (trimmed tail cannot carry earlier changed tasks; compare `log_trimmed_size` vs `log_original_size`), and requires naming each resource by its **concrete identifier from the event payload** plus the changed-task count next to its noun. | Yes — an added tool call on a question that asks for it; `unordered-subset` scoring cannot be hurt by an extra call, and no passing behavior is removed. |
| 4 | OVERCONFIDENCE GUARD | `aap2_agent.md` Step 7e | **"Only report as created what the events show as changed."** If the failure was a validation/API rejection of a *submitted* request, nothing it described exists — do not infer resources from the template's contents, and say the stack was never created. This is the trap the contract's `forbidden` block encodes ("the VPC was created", "delete the stack resources"). Currently 0/10 trip it, so this is **insurance** for the new, more detailed cleanup section: I am asking for more inventory detail, which is exactly what could start tripping it. | Yes — it *protects* the one component that is already perfect. |
| 5 | ROUTING | `orchestrator.md` Multi-domain | Added the discriminator: **"Two questions about the SAME job are one domain, not two"** — why-it-failed + what-it-changed both come from that job's log and events, so it is one `investigate_aap2_job`. `investigate_security` is for activity **beyond one known job** (who touched an account, IAM keys, drift with no job), because CloudTrail needs an account id a job id does not yield. Conditional, not a blanket ban. | Yes — narrows by a stated condition; genuine cross-domain and account-scoped questions route exactly as before. |

## Verify-the-fix (the trace it targets → what the new text does on those exact inputs)

- **Cluster 1, seeds 0/2/3/5/6/8/9 (cited 31/34/35/36/39 or a range):** Step 7d now says to cite where the **referencing** block begins, and `shared_context.md` says to count from line 1 of the fetched content including `{% %}` and blank lines. On the seeded file that is unambiguously **38** (`PublicSubnetBRouteTableAssociation:`) — the definition is 30, the `{% endif %}` 36, the `!Ref` property 41. The "cite ONE line" rule also kills seed 3's "36, 39" and seed 4's "33, 38", which `_citation_present` rejects even when 38 is present but not adjacent to the path.
- **Cluster 2, seeds 0/2/3/4/5/6/8 (diagnosis right, phrase broken):** all 7 wrote the cause with emphasis inside it. The new contract's worked pair — "the reference sits outside the guard", *not* "sits **outside** the `{% if %}` guard" — is the literal transformation that turns each of those sentences into a match. Measured: markdown-stripping those same answers newly HITs 4; the rule targets the cause of all 7.
- **Cluster 3, seeds 1/5/7/8 (never fetched the template):** the log hands them `git_url: https://github.com/agnosticd/agnosticd-v2.git` and `src: /runner/project/ansible/configs/.../ec2_cloud_template.j2`. Step 6's parse rule yields owner `agnosticd` (the old table said `rhpds` — seeds 1/5/8 all tried `rhpds` and failed), and the fetch-the-printed-path rule yields the exact `path`. Together they produce the one expected `fetch_github_file` call on the first try instead of 9–12 searches.
- **Cluster 4, seed 9 (lost key-pair + bucket):** seed 9 called `get_job_events(failed_only=true)` and never `changed_only`. Step 5b makes `changed_only` mandatory for the "what was created / what to clean up" half that this request explicitly asks ("what the run had already created... so I know what to clean up first"). Those two names exist **only** in the changed events.
- **End-to-end check (the real test):** I wrote the answer the edited prompts now prescribe and ran it through the task's own matchers (`_count_present`, `_citation_present`, the any_of/none_of logic): **all 4 required + the count + the citation HIT, forbidden MISS** → answer component 1.0, vs the 0.571–0.857 observed. So the prescribed output is reachable and sufficient, not merely plausible.

## Process & features used
- **Subagents / worktrees:** serial, deliberately. The brief suggests fanning out one subagent per trajectory-group, but all 10 trajectories are trials of **one** task and the offline verifier replay gave me the complete per-item miss matrix in a single pass — cheaper and more exact than 10 diagnostic subagents reading the same transcript shapes. Fan-out would have cost budget for information I already had; I spent the budget on the verifier replay + the end-to-end scoring check instead.
- **Prior iterations read:** none exist — `RUNMAP.md` is empty, `LEDGER.md` has only the baseline row, `rejected.jsonl`/`history.jsonl` are absent (iteration 1/5). Nothing to build on or avoid yet.
- **Non-overfitting check:** `grep -niE "retail|k9fhs|693027|PublicSubnetB|subnet_count|2d6f0a9"` over the three edited files returns **nothing** outside pre-existing generic repo names. Every rule is stated over a mechanism (conditional definition vs unguarded reference; log-printed path; trimmed-log vs changed events; same-job two-part question) and all worked examples use `EXAMPLE-ORG`/`some-repo`/`some-resource-name-abc123` placeholders. Restated without task-specific nouns: each rule survives.

## Good things to PRESERVE (do not let a future iteration undo these)
- **`forbidden` is clean 0/10 and `cfn-error` + `changed-tasks` are 10/10.** Do not loosen the Step 7e overconfidence guard or encourage listing template contents as created resources — that is precisely what the `forbidden` block punishes, and it is currently free reward.
- **Parse `owner`/`repo` from `git_url`.** Do not reintroduce a static owner→repo table; it was measurably wrong here.
- **No `fold_markup` in this contract.** Literal names, counts, and cause phrases must stay contiguous in the output. Any future edit that encourages decorating identifiers with emphasis will silently cost answer points.
- The offline verifier-replay recipe at the top of this file — it converts a null-trace trajectory set into an exact per-item miss matrix. Reuse it.

## Deliberately skipped (cluster + why)
- **`cfn-error` and `changed-tasks`** — already 10/10; the error literal comes free from the log tail and the count from PLAY RECAP. No edit needed, and touching them risks the regression above.
- **`completion`** — 1.0 on every trial. Not a lever.
- **A tools/code fix for line numbers.** The honest observation is that `fetch_github_file` returns raw `content` with no line numbers, so the agent must count lines itself — a real capability gap (see escalation). I did not fake a code fix; I wrote the counting rule as explicitly as prose allows (count from line 1, include blanks/`---`/`{% %}`, count the fetched text not the rendered view).

## Escalation (needs code, not prose — out of scope this phase)
`fetch_github_file` returns `{path, content, type}` with no line numbering, so every
line citation depends on the model counting newlines in a blob by eye. That is the
single largest residual risk here: `assoc-line` missed in **9/10** trials, and in
several the agent had the right block but the wrong number. A tools-layer change —
returning line-numbered content, or accepting a `grep`/anchor argument that reports
the matching line number — would make this item deterministic rather than a
counting exercise. Recommend it for the phase that can edit tools.

---

# DIAGNOSIS.json

See `DIAGNOSIS.json` in this directory.
