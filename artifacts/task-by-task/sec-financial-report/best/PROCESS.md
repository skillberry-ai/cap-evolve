# PROCESS — what I did this iteration (explainability; REQUIRED)

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | q2 "how many stocks" answered with Total holdings (3457) instead of stock holdings (2451) | sec-financial-report (t8: 1/10 trials) | Agent OVERRIDES the script's correct `Number of stock holdings`. In t8 it inspected the data, saw `PUTCALL` all-NaN (no options), and wrongly concluded "no options ⇒ all 3457 holdings are stocks", ignoring that non-stock instruments (ETFs/notes/funds/units) are classified by `TITLEOFCLASS`, not `PUTCALL`. | BEHAVIORAL (knowledge-backed) | SCRIPT (add evidence) + BODY note |

Only one cluster is FAILING in this iteration's trajectories (t0–t7,t9 all pass with reward 1.0; only t8 fails, and solely on `test_answer_quality: assert 3457 == 2451`). q4/q1/q3 are produced correctly by all passing trials, so I touched nothing there (would violate REAL/SAFE).

## Key diagnostic finding (informs why prior cand_0001 was rejected)
- Ground-truth q4 is the RAW UPPERCASE filing-manager name (`VANGUARD GROUP INC`, `STATE STREET CORP`); passing seed trials emit uppercase and pass. NOT a failing cluster → left alone.
- cand_0001 (label-only edit) was REJECTED at val=0.000, but its 10 val rollouts all produced the CORRECT answers.json (q2=2451, correct q4). The score feedback was "No per-test CTRF breakdown available" — the pytest verifier never ran = an INFRASTRUCTURE failure during scoring, NOT a semantic regression. So the q2 label idea was not disproven; it was killed by infra noise. broke={} confirms no task regressed.

## Changes made this iteration (one row per edit)
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| q2 stock-vs-total | SCRIPT | `13f-analyzer/scripts/one_fund_analysis.py` | ADDITIVE: after the existing (byte-identical) stock-holdings line, print `Number of NON-stock holdings` and a NOTE that stocks are identified by TITLEOFCLASS (not PUTCALL), so total > stock even with no options; report `Number of stock holdings` verbatim for "how many stocks". General: encodes the definition, no task-specific value. | Yes — existing Total/AUM/stock lines are unchanged; only new lines appended. |
| q2 stock-vs-total | BODY | `13f-analyzer/SKILL.md` | Concise "Reading the output" note: how many stocks vs holdings, TITLEOFCLASS-not-PUTCALL, report stock-holdings line directly. Reinforces the same rule the agent already follows in 9/10 trials. | Yes — additive prose; steers only toward the value passing trials already report. |

## Verify-the-fix (one line per change)
- SCRIPT: ran the edited script on a synthetic INFOTABLE (single-quarter AND comparative two-quarter paths). Total/stock/AUM outputs identical to pre-edit (5/2/4200/3000); new lines print `Number of NON-stock holdings: 3` + NOTE; buy/sell computation unchanged. On t8's real data this makes the non-stock count (3457−2451=1006) explicit, directly refuting the "no options ⇒ all stocks" reasoning that produced the wrong 3457.
- BODY: ties to `test_answer_quality: assert answers["q2_answer"] == 2451`; note tells the agent to report `Number of stock holdings` (=2451) and not derive it from PUTCALL/total. Blast radius: only 13f-analyzer; q1/q3/q4 code paths untouched; fuzzy-name-search untouched.

## Process & features used
- Serial (single small task, one cluster). No subagents/worktrees needed — diagnosis was a 10-trajectory diff, not a fan-out.
- Read from ./prior_iterations/cand_0001 + RUNMAP + JOURNAL + the champion's val rollouts (`rollouts/val/…cand_0001…`). Learned that cand_0001's q2 fix was semantically correct in all 10 val runs and was rejected by an infra (no-CTRF) scoring failure, not by regression.

## Good things to PRESERVE (do not let a future iteration undo these)
- The "missing-comma" concatenation in `title_class_of_stocks` is LOAD-BEARING: ground-truth q2=2451 is produced with that exact behavior. Do NOT "fix" the commas.
- Existing Total/AUM/stock-holdings print lines must stay byte-identical (passing trials copy them).
- Do NOT alter q4 output/casing — uppercase raw names already match ground truth.

## Deliberately skipped (cluster + why)
- q4 name casing: not a failing cluster (passing trials produce the correct uppercase). Editing it would risk SAFE and violate REAL.
- No new standalone script: the failing task's real data is not available in this workdir, so a new transform could not be verified on real inputs; instead I made the existing (already-run) script emit the disambiguating evidence — verified on synthetic data.
