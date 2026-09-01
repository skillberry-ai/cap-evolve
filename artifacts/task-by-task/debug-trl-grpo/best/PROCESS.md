# PROCESS — what I did this iteration (explainability; REQUIRED)

Val split is a SINGLE task, `debug-trl-grpo` (fix 3 injected bugs in `/app/trl` so a
countdown-math GRPO run improves). Parent is **cand_0003** (val 0.925). Its 10 rollouts here:
**8× reward 1.0**, **t2 = 0.60**, **t7 = 0.65**. Mean 0.925.

Bug weights (verifier `test_outputs.py`): Bug1 `selective_log_softmax` sign flip = 0.35,
Bug2 advantage epsilon = 0.25, Bug3 `decode_and_strip_padding` = 0.40.
- **t2 = 0.60 = Bug1+Bug2** → lost Bug3 (0.40).
- **t7 = 0.65 = Bug2+Bug3** → lost Bug1 (0.35).

## The decisive NEW diagnosis (which skill each trial actually loaded)
I parsed "Launching skill: X" from every rollout. The discriminator is not *what the skill says*
but *which skill loaded*:

| trial | reward | skills loaded | ran probe | miss |
|-------|--------|---------------|-----------|------|
| t0,t1,t3,t6,t9 | 1.0 | include `rl-post-training` | some | — |
| t4,t5,t8 | 1.0 | include `rl-post-training` | no | — (body discipline sufficed) |
| **t2** | **0.60** | **`grpo` ONLY** | no | reverted decode to upstream → Bug3 |
| **t7** | **0.65** | **`grpo`+`trl` only** | no | never opened `selective_log_softmax`, stopped after 2 fixes → Bug1 |

**Every passing trial loaded `rl-post-training`; both failing trials never did.** All prior
iterations (cand_0001/0002/0003) put their fixes — the verify_pipeline.py probe, the
"check all stages / don't stop early" gate, the "upstream ≠ oracle / don't revert custom
decode" knowledge — into `rl-post-training` and `trl`. The failing trials never load those
skills, so the guidance never reaches them. **`grpo` is loaded in EVERY trial (pass and fail)
yet carried ZERO debugging discipline and no pointer to the probe.** That is the gap.

## Ranked issue list (leverage = #trials × recoverable weight)
| rank | cluster | tasks | root cause | tag | change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Diagnostic discipline unreachable in the entry skill | debug-trl-grpo (t2, t7) | Failing trials load only `grpo` (+`trl`), never `rl-post-training`; `grpo` has no "check all stages / don't revert custom logic / run the probe" guidance. t7 → early stop misses Bug1; t2 → upstream-revert deletes Bug3. | BEHAVIORAL (t7) + KNOWLEDGE (t2) | BODY |
| 2 | Bug1 / Bug2 / Bug3 mechanics | debug-trl-grpo | mechanics already documented in trl/rl-post-training; not the gap | — | not touched |

## Change made this iteration (ONE focused, additive edit)
| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | BODY | `grpo/SKILL.md` — new section "Debugging a GRPO pipeline that shows no improvement" | Surfaces the diagnostic discipline in the skill BOTH failing trials load: (a) no-improvement = usually MULTIPLE independent bugs, verify EVERY stage, stopping after 1–2 fixes is the common failure (→ t7); (b) a per-stage invariant checklist incl. log-prob `<=0` / operand order (`selected_logit - logsumexp`) → t7's exact miss, tiny advantage epsilon, decode branch-correctness; (c) "a version diff LOCATES anomalies, is not the ORACLE — do not restore upstream / delete intentional custom decode extraction" → t2's exact miss; (d) explicit instruction to also load `rl-post-training` and run its `scripts/verify_pipeline.py` before declaring done. All stated as GENERAL GRPO invariants — no filename/value/marker hardcoded. | The 7 passing trials that load `grpo` already do exactly these things (load rl-post-training, check all stages, keep the extraction, fix all 3). Additive reinforcement of correct behavior cannot push them onto a worse path. |

## Verify-the-fix (traced to the exact failing behavior)
- **t7 (lost Bug1):** trace msg [10] says it will "check log-probs" but it never opens
  `selective_log_softmax`; msg [33] declares done after 2 fixes. The new checklist row makes the
  log-prob sign/operand-order check and "verify every stage before concluding" unmissable in the
  one skill t7 loaded (`grpo`).
- **t2 (lost Bug3):** msg [42]/[51] — diffed `/app/trl` vs upstream 0.17.0, decided the `<think>`
  extraction was "injected corruption", reverted decode + call-site to plain `batch_decode`. The
  new "diff locates, is not the oracle; do not restore upstream / delete intentional custom decode"
  paragraph lives in the one skill t2 loaded (`grpo`), directly countering that reasoning.
- **Probe pointer accurate:** confirmed `verify_pipeline.py` round-trips each stage and prints
  `!!` + "Unambiguous invariant violations in: …" on the broken stage (lines 118, 272–296, 324).
- **Package validity:** `grpo/SKILL.md` frontmatter intact, body 114 lines (≪ ~500 budget), both
  `references/*.md` still resolve, `verify_pipeline.py` path exists. `py_compile` clean.
- **Blast radius:** only `debug-trl-grpo` uses these skills on this split. Edit is additive prose
  in `grpo` only; Bug1/Bug2/Bug3 mechanics in `trl`/`rl-post-training` untouched; the probe code
  unchanged; no description/trigger touched (so no skill-selection is disturbed).

## Process & features used
- Serial. Diagnosis = extracting per-trial "Launching skill: X" from all 10 rollouts to find the
  load-order discriminator, then reading t2/t7 agent messages against the verifier weights. No
  subagents needed at this scale (single task, single cluster).

## Why NOT breadth this iteration
There is exactly ONE recoverable cluster (grpo lacks discipline) with two sub-modes, both fixed
by this one section. Adding the same prose to `trl` would be redundant (t7 already loads `grpo`;
t2 loads neither `trl` nor `rl-post-training`). Editing descriptions to force `rl-post-training`
to load is the riskier lever (disturbs skill selection on passing trials) with no clean
failing-assertion tie — deliberately skipped per the SAFE test.

## Good things to PRESERVE
- The network-free stub-tokenizer decode probe + three-branch contract (hard-checked) in
  `rl-post-training`/`trl` — kept as the authoritative home; `grpo` now points to it.
- The self-locating `trl` import in `verify_pipeline.py`.
- The "upstream ≠ oracle / fix the branch in place" knowledge in `trl` + `rl-post-training`
  (now mirrored into `grpo`, the entry skill).

## Deliberately skipped
- Bug1/Bug2/Bug3 mechanics and the probe code: unchanged (correct where loaded).
- Description/trigger edits: not touched — riskier blast radius, no failing-assertion tie.
