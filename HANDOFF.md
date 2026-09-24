# HANDOFF — parsec v4 intake

Written 2026-09-09, handing off to a fresh Claude Code session in a new window/terminal.
v1 and v2 are finished, written up, and pushed. This worktree is an empty shell for v4 —
nothing has been run here yet. Read this end-to-end before doing anything; v1 and v2 each
burned real time on mistakes that are cheap to avoid if you know about them going in.

---

## Where things are

| what | where |
|---|---|
| **This worktree** — branch `parsec-intake_v4`, forked from `origin/main` @ `8efb1e88` | `/Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v4/` |
| Main cap-evolve tree | `/Users/boazc/workarea/Python/skillberry_ai/cap-evolve/` |
| **v4 source materials** (external, not a git repo) | `/Users/boazc/workarea/Python/rhdp-parsec/v4/` |
| v1 source materials (for reference/comparison) | `/Users/boazc/workarea/Python/rhdp-parsec/v1/`, worked in `cap-evolve-worktrees/parsec-intake_v1/` |
| v2 source materials (for reference/comparison) | `/Users/boazc/workarea/Python/rhdp-parsec/v2/`, worked in `cap-evolve-worktrees/parsec-intake_v2/` |
| Written-up results, both experiments, pushed | orphan branch `parsec-history` — checked out at `cap-evolve-worktrees/parsec-history/` |
| Open PRs from the v1/v2 cycle (unmerged as of this writing) | #464 (`HARBOR_LOCAL_ASIS` guard), #465 (parsec benchmark integration, local-only), #466 (`benchmark-history` records for v1+v2) — all green in CI |

Open this worktree with either:

```bash
code "/Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v4"
```

or

```bash
cd "/Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-intake_v4" && claude
```

There is no `.env`, no venv, and no cap-evolve project scaffold here yet — this worktree is
just a clean checkout of `main` on its own branch, waiting for v4 to be built out.

---

## What v4 actually is — read its own README first

**`/Users/boazc/workarea/Python/rhdp-parsec/v4/README.md` is thorough, self-contained, and
already answers most setup questions.** Read it in full before asking the user anything about
how to run v4 — the setup procedure, port assignments, gotchas, and honesty caveats are all
there. Summary so you know what you're looking at:

- **30 hand-authored Harbor tasks** against **5 simulated backends** (platform, github,
  icinga, cost, cloud — 20 tools total), not the kaegis-simulator setup v1/v2 used.
- Runs against a **patched parsec checkout** at commit `28e2c40`
  (`parsec-simulation-redirect.patch`, applied to a throwaway clone — never patch your
  reference checkout) plus a dedicated Harbor agent, `parsec_harbor_agent.py`, invoked as
  `harbor run -a parsec_harbor_agent:ParsecAgent`.
- New reward schema (`bench/v4`): `completion` gate × (`w_tool·tool_calls + w_answer·answer`),
  with `tool_calls` **zeroed outright** if the agent makes any forbidden call.
- **Every simulated tool response is model-synthesized** — one call takes 30–60s, and the full
  30-task suite takes about **3 hours**. This makes v4 the slowest and most expensive of the
  three parsec experiments to run per-trial.
- **No real production trace data at all** — a deliberate departure from v1. Every literal in
  every task is either attested in parsec's own source at `28e2c40` or explicitly declared
  invented in that task's `provenance.md`. Read `provenance.md` before trusting any one task's
  number; several record a stated limitation.
- **This is a raw Harbor + simulation-harness setup. It does not currently integrate with
  cap-evolve's `capevolve.yaml`/adapter flow the way v1 and v2 did.** How (or whether) v4 wires
  into cap-evolve's optimization loop — as a Harbor adapter project like v1/v2, or left as a
  standalone benchmark — is an **open design question**, not something already decided. Don't
  assume the v1/v2 pattern (`.capevolve/project/`, `capevolve.<version>.yaml`, the Harbor
  adapter template) just because that's what the last two experiments did; confirm the intent
  with the user before building the scaffold.

---

## What you need to know from v1 — 30 traced tasks, optimizer never won

Full writeup: [`parsec-history/results/v1/summary.md`](../parsec-history/results/v1/summary.md)
(worth reading in full if you're building v4's contract/scoring design — its "what the 30
contracts actually measure" section is the most important part).

- Task set: 30 `traces_parsec-aap2-*` tasks, **mechanically extracted from real scraped
  sessions** — not hand-authored. Reward = `gate · (0.5·trajectory + 0.5·assertions)`, where
  `trajectory` is a `subset` match on the scraped tool-call sequence and `assertions` is the
  fraction of `answer_contains` substrings present.
- **The optimizer never beat the seed in any run that reached FINAL.** Champion == seed,
  byte-identical SKILL.md, `test_delta = +0.0`, across 4 runs and 9 candidates.
- **The headline finding is about the benchmark, not the skill.** Only 2 of the 4 backend sims
  were running when the 30-task baseline was swept (aap2 + github, not babylon or
  provisions_db). 25 of 30 tasks demanded a tool call that no running sim could serve, capping
  their trajectory term at 0 by construction — reachability, not skill quality, predicted the
  outcome almost perfectly (5/5 matched where every demanded tool was servable; 0/25 matched
  where it wasn't). **If you stand up simulated backends for v4 or reuse anything from v1,
  confirm every backend a task's contract needs is actually running before trusting a
  baseline sweep** — this exact mistake cost the entire v1 baseline its validity for 25 of 30
  tasks.
- **No genuine holdout.** `train == val == test == {0047, 0048}` on every optimizer run — the
  two tasks chosen because they scored `gate == 0.0` at baseline. `test_delta = +0.0` is
  arithmetic on the optimizer tuning against the tasks it's later "tested" on, not a
  generalization result. **Pin a real disjoint split in the recipe if v4 does anything
  optimizer-driven** (`split_ids_file` was empty in v1's committed yaml, so a verbatim rerun
  draws a random split rather than the intended pinned one).
- **The seed measurement is not stable.** Two `n=10` measurements of the byte-identical seed
  skill, one day apart, differed by 0.203 (0.017 vs 0.220). Any delta smaller than ~0.2 in v1's
  setup is inside the noise — this is the same instability pattern v4's own README already
  flags for its own rewards (0.420 four times, 0.520 once, no change to the task).
- **Infra errors were written as `reward: 0.0` and silently mixed with genuine zeros**, only
  distinguishable via a `rollout.error` field. 16 of 60 trials in the headline baseline cell
  never ran (one `NetworkConnectionError` outage window) and were undercounted by the run's own
  journal at the time. Whatever harness/reporting v4 uses, keep infra-errored trials
  distinguishable from genuine zero scores and exclude them from means rather than counting
  them as zero.
- One task (`0052`) had **zero assertions**, which trivially scores 1.000 on that half and
  drags the aggregate up — a task that checks nothing should not ship.
- **v1 is not comparable to v2's numbers** (different task counts, different reward formulas,
  different tool coverage) — the same caution will apply to v4, which uses yet another reward
  schema (`bench/v4`) and yet another tool surface. Don't put v1/v2/v4 numbers in the same
  sentence without saying what's different.

## What you need to know from v2 — 10 authored tasks, champion accepted but overstated

Full writeup: [`parsec-history/results/v2/summary.md`](../parsec-history/results/v2/summary.md).

- Task set: 10 hand-authored `bench-aap2-*` tasks, one isolated simulator per task. Reward =
  `w_tc·(calls matched) + w_ans·(answer items)`, per-task weights, forbidden facts satisfied by
  absence.
- A champion **was** accepted (`cand_0001`, val 0.962 vs seed's reported 0.876, "+0.086"), but
  **the headline comparison mixed trial counts**: the run used `--reuse-baseline`, so the seed's
  figure was a stale `n=3` measurement while the champion was measured at `n=9`. Re-derived at
  equal `n=9` with errored trials dropped, the honest delta is **+0.139**, not +0.086 — same
  direction, 1.6x the reported magnitude. **Never gate or report a delta across two different
  trial counts; if a baseline must be reused, re-derive the comparison from the in-run
  re-measurement (`seed_train`), not from `report.md`.**
- **Three of the run's five per-task "fixed"/"broke" verdicts were wrong** once re-derived at
  equal `n` — including missing the one genuine regression (`007`, −0.051) entirely, which
  `report.md` had listed as a +0.130 gain. All three errors trace to the same
  `--reuse-baseline`-across-a-trial-count-change cause above.
- **No held-out test either** (`test: []`, `test_used: false` despite `report.md` claiming
  otherwise) — a `report.md` boilerplate sentence about held-out tasks was flatly false for this
  run. **Don't trust cap-evolve's own narrative text about what was held out; check
  `splits.json` directly.**
- **The win itself is real but narrow**: nearly the entire gain was a documentation fix (which
  tool to call for metadata vs. logs), not a reasoning improvement — and it's an open risk
  whether the seed's original guidance was actually wrong, or only wrong for the *simulator*.
  That was never resolved because the pre-optimization trajectories weren't captured. If v4's
  simulators diverge from real backend behavior in some similar way, the same risk applies:
  **a champion that's "correct" for a simulator can be wrong for production**, and there's no
  way to catch that after the fact without captured pre/post trajectories.
- Errored trials again landed disproportionately on one side of a comparison (8 of 90 baseline
  re-measurement trials errored, 0 of 90 champion trials) — same lesson as v1, independently
  confirmed: infra failures are not randomly distributed across what you're comparing, don't
  assume they wash out.
- Optimizer cost telemetry was wrong in the run's own summary (`$0.00` reported,
  `$3.23` actually spent per the error payload) — don't trust `state.json`'s cost figures at
  face value if you're tracking v4's cost.
- No journal/handover was written for either accepted candidate across the whole v2 run — if
  v4 ends up optimizer-driven, insist on the journal actually being populated; otherwise every
  later attribution of *why* an edit worked is inference, not a reading of the record.

## Cross-cutting lessons — apply regardless of which version you're extending

- **Ask before pushing anything.** Never push to `origin/main`, a PR branch, or `parsec-history`
  without explicit confirmation first.
- **Never push `benchmark-history` directly under any instruction** — only ever via a side
  branch + PR, and only when explicitly asked to prepare (not push) a record.
- **DCO**: every commit needs a matching `Signed-off-by` trailer (name+email must exactly match
  the commit author identity) or CI fails. Fix with `--amend --signoff --no-edit` or
  `rebase --signoff`.
- **Fork vs. origin**: the v1/v2 PRs (#464/#465) live on the `bcarmeli` fork remote, not
  `origin`. Pushing an amended PR branch to the wrong remote silently creates a stray branch
  with a deceptive `[new branch]` message rather than erroring — verify the push target before
  force-pushing.
- **`git status` before any destructive git command.** Run it, and stash/commit anything found,
  before `checkout`/`restore`/`reset`/`clean` or removing a worktree.
- **`parsec-history`'s core discipline: generate every number once, never hand-type it twice.**
  Every table in a `summary.md`, `reports/` block, or `ui/heatmap.html` is produced by a script
  in `scripts/` from `results/results.json`. `skillsbench-history` caught a real bug this way —
  hand-transcribed numbers had drifted from source — twice.
- **Raw simulator rollouts are deliberately not committed to `parsec-history`** (~96 MB across
  v1+v2 already). Only derived per-task score vectors and recipes get committed; rollout logs
  stay in the source intake worktree.
- **`HARBOR_LOCAL_ASIS`** (added in PR #464, `templates/adapters/harbor/adapter.py`): if v4 ends
  up using the shared Harbor adapter template, know that the ASIS path delivers instruction
  *text only* — a skill package's bundled `scripts/`/`references/` are silently dropped unless
  the candidate is reduced to `capabilities: [system-prompt]`. There's now a guard
  (`_assert_asis_can_deliver`) that raises instead of silently under-delivering; don't work
  around it, fix the capability declaration instead.
- **No hardcoded personal paths in anything meant to ship** (recipes, scripts, READMEs) — v1/v2
  both had to fix defaults that pointed at `/Users/boazc/...` before those files could be
  reviewed as shared code.
- **Equal-n, paired comparisons only.** Every real mistake found in v1 and v2's numbers traces
  back to either an unequal trial count on the two sides of a delta, or infra-errored trials
  counted asymmetrically. Whatever v4's harness looks like, keep those two invariants explicit
  from the start rather than re-deriving them after the fact.

---

## Suggested first moves

1. Read `/Users/boazc/workarea/Python/rhdp-parsec/v4/README.md` in full — it's the authoritative
   setup doc, not this file.
2. Skim `parsec-history/results/v1/summary.md` and `results/v2/summary.md` in full if you'll be
   designing v4's contracts/scoring — both are short, dense, and full of "we got this wrong the
   first time" detail that's cheap to avoid repeating.
3. Confirm with the user, before scaffolding anything, whether v4 is meant to plug into
   cap-evolve's optimizer loop (à la v1/v2's `.capevolve/project/` + Harbor adapter) or stay a
   standalone Harbor+simulation benchmark run by hand. The v4 README's own setup procedure is
   written for the latter (`harbor run -a parsec_harbor_agent:ParsecAgent -t <task>`, one task
   at a time) — nothing in it assumes cap-evolve.
4. Stand up the five simulations per the README (ports 8086–8090), confirm each with
   `curl localhost:<port>/healthz` before trusting it's serving traffic (podman reports
   `(unhealthy)` even when a container is fine — a known quirk, not a real failure).
5. Run one task by hand end-to-end before anything larger, and read `reward-detail.json`, not
   just `reward.json` — a `tool_calls: 0.0` can mean either "no expected call matched" or "a
   forbidden call fired," and those are very different findings.
