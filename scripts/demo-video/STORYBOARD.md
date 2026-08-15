# cap-evolve demo video — storyboard

**Format:** 2560×1440, 25 fps, 89.5 s, h264 + one mono AAC voiceover track, 5.2 MB.
**Comprehensible muted.** Every claim is on screen as text; the voiceover adds emphasis,
never information. A `.srt` transcript ships alongside.

The machine-readable version of this document is
[`script.py`](script.py) — durations, on-screen copy, voiceover lines and the
attribution of every number live there, and `assets.py` + `build.sh` render from it. If
this file and `script.py` disagree, `script.py` is what got built.

---

## The spine: τ²-bench airline

Chosen over the alternatives, and it is the thread the whole video follows.

| Candidate | Why not the spine |
|---|---|
| `toy_calc` | Deterministic and provable, but a toy — it proves the *loop* runs, not that cap-evolve is worth anything. Demoted to the closing "start here" shot, which is exactly what it is good at. |
| **`tau2_airline`** | **The spine.** A real benchmark, a real model, a committed run artifact, *and* it optimizes the airline **policy and the tool code jointly** — which is the differentiator against every prompt-only optimizer. It is also the only example with a committed, readable **diff** plus per-task trajectory evidence that the diff is what moved the number. |
| `skillsbench` | Real and held-out, so it appears as a results row. But its artifact is a report, not a legible diff, and "office-document skills" needs more setup than 90 s allows. |
| `RH-SWE-bench` | The biggest number (58.0 → 76.5) — **deliberately absent from the video, and confirmed absent by the lead.** It is now in `docs/RESULTS.md`, but documented there as the one result with **no committed run artifact**, and its own hero chart shows *different* numbers (55.7 → 73.1). Two candidate figures and no artifact is not quotable in a video. |

## The persuasive shot: a real diff, from a committed artifact

Shot `diff` renders rows read out of

```
examples/tau2_airline/run_full/ui/data/runs_run_full_diff_cand_0006.json
```

which is the actual git diff the run produced for `cand_0005 → cand_0006`:
`policy/policy.md +9 −2` **and** `tools/tools.py +37 −0` in the same iteration. The
narrative and the trajectory evidence are `docs/OPTIMIZATION_EXAMPLES.md` §1: under
`cand_0005` the agent rebooks with three travel certificates and the seed tool accepts
it (reward 0); under `cand_0006` the new in-code guard rejects the call, the agent reads
the error, says *"Only one travel certificate can be applied,"* and rebooks correctly —
**task 14 went 1/10 → 6/10 the iteration the guard landed.**

That pairing is the argument in one frame: prose for the genuine knowledge gap, executable
code for the rule the agent already knew and skipped.

---

## Shot list

Durations are `max(min_dur, voiceover + 0.7 s)`, computed at build time from the actual
synthesized audio — so no line is ever clipped and no shot ends in dead air. The numbers
below are the built values.

### 1 · `logo` — 4.0 s — card (animated frame sequence)
- **On screen:** the capybara mark scales and fades up, then `cap·evolve` rises,
  then `watch capability evolve`, then `optimize an agent's prompts, tools and skills
  from its own failures`.
- **VO:** "cap-evolve. Watch capability evolve."
- **In / out:** cold open on black · fade to black.
- **Numbers:** none.

### 2 · `problem` — 8.1 s — card
- **On screen:** eyebrow `THE PROBLEM`; head **"Your agent fails. / You don't know why."**;
  three lines — *A benchmark gives you one number.* / *Not which policy rule was missing.* /
  *Not which tool let a bad call through.*; kicker in red:
  *So you guess — rewrite the prompt, run it again, hope.*
- **VO:** "A benchmark gives you one number. It won't tell you which policy rule was
  missing, or which tool let a bad call through. So you guess."
- **In / out:** fade · fade.
- **Numbers:** none.

### 3 · `what` — 7.3 s — card
- **On screen:** eyebrow `WHAT IT DOES`; head **"It optimizes what your agent reads."**;
  four accented tiles — `system prompts` (rules, examples, output contracts) ·
  `tool code` (executable guards inside the tool) · `MCP surfaces` (tool docs + which
  tools are exposed) · `skill packages` (SKILL.md, references, scripts); kicker
  *Not its weights. Learned from its own failed trajectories.*
- **VO:** "cap-evolve edits what your agent reads: prompts, tool code, MCP surfaces,
  skill packages."
- **In / out:** fade · fade.
- **Source:** capability list is the README's *What can cap-evolve optimize?* table.

### 4 · `terminal` — 13.7 s — footage · **recorded against the rebuilt TUI**
- **On screen:** a real recording of `cap-evolve replay --demo`, from the *rebuilt*
  renderer: capybara masthead, identity card (run · algorithm · spec · split · gate
  `paired k_se 0.20 trials 2` · target), the filled cumulative-best chart with its glyph
  legend, lineage, the per-task heatmap, and spend split runner/optimizer. Window is
  `TERM_SEEK=7.7` s into a ~21.6 s recording, so the shot *builds*: it opens on iteration
  2 and lands on iteration 7, by which point the lineage shows an accept, a reject, and an
  **`indecisive: Δ̄=0 within noise (SE=0.105, n=6) — not a reject`** row, in full, not
  truncated. The gate-warning banner and the budget line are also visible, unstaged.
- **Fills the frame:** at this geometry the renderer emits 41 of 41 rows with no blank
  rows — the earlier cut's empty bottom third is gone.
- **Lower-third, line 1:** `real recording of  cap-evolve replay --demo  ·  the renderer you get, not a mockup`
- **Lower-third, line 2 (amber):** `illustrative session — hand-authored numbers, NO benchmark claim  ·  measured results: docs/RESULTS.md`
- **VO:** "Each iteration scores a candidate on validation, reads the failures, and
  proposes one edit. Accepted, rejected, or indecisive — always with the reason. This
  session is illustrative: its numbers are hand-authored."
- **In / out:** fade · fade.
- **Numbers:** all from `core/cap_evolve/demo_session/events.jsonl`. **Hand-authored, no
  benchmark claim** — the renderer prints that banner itself and it is on screen at the
  *top* of the frame for the whole shot; the amber lower-third line restates it; the
  voiceover says it aloud. Triply present. (The lower-third band covers the *bottom* copy
  of the banner and the run path — that is why the band's own amber line carries the same
  claim verbatim in substance.)

### 5 · `diff` — 10.6 s — card
- **On screen:** eyebrow `ONE REAL ITERATION · τ²-bench airline`; head
  **"cand_0005 → cand_0006"**; two panels side by side —
  left `policy/policy.md +9 −2` with the real removed/added rule, right
  `tools/tools.py +37 −0` with the real `cert_count` guard and its recovery message;
  under them *prose for the knowledge gap + code for the rule the agent already knew*;
  then in green **`task 14:  1/10 → 6/10 the iteration the guard landed`**; footer is the
  artifact path.
- **VO:** "One real iteration: a policy rule, and in the same edit, code inside the tool
  that rejects the illegal call. Task fourteen went from one pass in ten, to six."
- **In / out:** fade · fade.
- **Source:** diff rows from `runs_run_full_diff_cand_0006.json`; the 1/10 → 6/10 figure
  from `docs/OPTIMIZATION_EXAMPLES.md` §1.

### 6 · `dashboard` — 8.0 s — footage · **recorded against the rebuilt dashboard**
- **On screen:** Chromium driving the *running* dashboard over
  `examples/tau2_airline/run_agentopt`. Opens the run — split-discipline line
  (`splits · train 26 · val 12 · test 12 · seed 0 | val decides selection; test is scored
  exactly once and never optimized against.`), then the tile grid
  (`BASELINE VAL 83.3%` · `BEST VAL 83.3%` · `Δ 0.000` · `SEALED TEST 41.7% pass^1` ·
  `VERDICTS 4 candidates, 0 accept · 4 reject` · `SPEND $12.98` ·
  `UNATTRIBUTED SPEND $2.40`) — then **Candidates** (the accept/reject/seed lineage graph
  with the best path lit), **Gate** (four rows, each `reject`, with val and the k·SE bar),
  and **Cost** (the reconciled ledger: total, attributed, unattributed, and the warning
  that the $2.40 gap "is real" rather than hidden).
- **Lower-third 1:** `the live dashboard on a real τ²-bench run  ·  baseline / best / sealed test / spend, the candidate lineage, and a reconciled cost ledger`
- **Lower-third 2 (amber):** `this run is a NULL RESULT — 4 candidates, 0 accepted, best = seed  ·  measured gains: docs/RESULTS.md`
- **VO:** "The dashboard holds the whole run — every candidate, every dollar, and the
  gate's verdict. On this run the gate rejected all four."
- **In / out:** fade · fade.
- **Numbers:** every figure is that run's own, and every one is in `docs/RESULTS.md`
  §"τ²-Bench airline — `agent-optimize` with subset screening" — `$12.98` ($10.58 runner
  + $2.40 optimizer), val `0.8333 ± 0.1124`, sealed test `0.4167 ± 0.1486`, `best_id ==
  seed`, four candidates all rejected.

**Why this run and not `run_full`.** The obvious choice was the documented 50-task
`run_full` win, whose committed static export lives at `examples/tau2_airline/run_full/ui`.
The rebuilt dashboard renders that export with a red **`⊗ failed`** badge and
`algorithm not recorded` beside the run name, because the export's `summary` object carries
no `status` and no `algorithm` field, and its **Cost tab reads "No spend recorded"** because
the export ships no `events.jsonl` for the ledger to reconcile. There is no Diffs tab
either. A false "failed" badge over a run that finished is a worse integrity problem than a
true null result, and the export cannot be regenerated (its source run dir is gone — the
path in `runs.json` is a `/tmp` dir). So the shot films the live dashboard over the one
τ²-bench run whose full event stream *is* committed, and says out loud and on screen that
it is a null result. **Flagged for the lead:** the badge and the empty ledger on that
export are `ws-dash` bugs; if they are fixed, `--run run_full` against a regenerated export
is the nicer shot and only the caption/VO in `script.py` need changing.

### 7 · `honest` — 12.2 s — card — **the payoff**
- **On screen:** eyebrow `WHY YOU CAN BELIEVE THE NUMBER`; head **"Honest by construction."**;
  six rows, each with a right-hand aside:

  | | | |
  |---|---|---|
  | accept only if | `mean Δ  >  k · SE` | paired, per task |
  | gate split | `val only` | train can never gate |
  | test split | `sealed · scored exactly once` | a 2nd finalize raises |
  | repeated trials | `mean ± stderr · pass^k` | variance is reported |
  | regression veto | `optional — reject if a passing task breaks` | dual gate |
  | evidence too thin | `indecisive — NOT rejected` | says nothing about the edit |

  Footer: *the gate, the split and the seal live in the core — not in editable docs.*
- **VO:** "Here's what most optimizers skip. Acceptance is a paired significance test, on
  validation only: clear k standard errors, or it's noise. The test split is scored once,
  then sealed."
- **In / out:** fade · fade.
- **Source:** verified in `core/cap_evolve/gate.py` (val-only, `TrainGateError`,
  `GateDecision.indecisive`) and `core/cap_evolve/harness.py` (`no_regression` dual gate).
  `no_regression` **defaults to False**, so the card says **optional** — it would be false
  to imply it is always on.
- **Note:** the `indecisive` row is on screen but deliberately *not* narrated — the VO
  would overrun, and shot 4's footage already shows a live `indecisive` verdict. The card
  holds long enough to read it.

### 8 · `results` — 8.5 s — card
- **On screen:** eyebrow `MEASURED`; head **"Baseline → optimized"**; four rows, each with
  its split discipline spelled out under the name and a dot-to-dot bar on a shared
  `reward × 100` axis:

  | row | split label on screen | bar | gain |
  |---|---|---|---|
  | τ²-bench airline · policy + tool code | val — fit metric, 50 tasks × 10 trials | 53.6 → 71.2 | +32.8% |
  | τ²-bench airline · held-out 30/20 | sealed test, 20 tasks, scored once | 30.0 → 47.5 | +58.3% |
  | SkillsBench · skill packages | sealed test, held-out | 55.6 → 66.7 | +20.0% |
  | toy_calc · zero-API, deterministic | sealed test | 0.0 → 100.0 | proof |

  Then in amber: *optimizer spend, 87-task SkillsBench run: ~$32 (cap $400)*.
  Footer: *docs/RESULTS.md — every number cross-checked against a committed run artifact.*
- **VO:** "On τ²-bench airline: fifty-three point six to seventy-one point two. Thirty to
  forty-seven point five, held out."
- **In / out:** fade · fade.
- **Source:** all four rows and the cost line verbatim from `docs/RESULTS.md`. Every row
  carries **fit metric** vs **held-out** on screen, because the difference is the whole
  point. The cost figure is labelled as the SkillsBench run, and is a *different* run from
  the `$12.98` the dashboard shot shows — both are labelled with their run, so
  neither restates the other.

### 9 · `parallel` — 5.0 s — footage
- **On screen:** `par_demo.py` measured live, window at `PAR_SEEK=13.5` s so the
  `workers=8` row lands on camera and `identical SplitResult (workers=1 vs 8): True` and
  `32 rollouts x 0.2s = 6.4s of sleep; per_task order: True` are both on screen.
- **Geometry:** the tape records at **2560×760, FontSize 56**, not 2560×1440/28 — the
  script only ever prints 8 lines, so at full height the shot was ~90% empty frame.
  `build.sh`'s scale-to-fit then centres that band and the lower-third sits in the pad.
- **Lower-third:** `measured live on this machine  ·  16 tasks × 2 trials  ·  scripts/demo-video/par_demo.py`
- **VO:** "The tasks-by-trials grid is parallel. Measured live, right here."
- **In / out:** fade · fade.
- **Numbers:** measured on camera.

### 10 · `speedup` — 3.5 s — card
- **On screen:** eyebrow `MEASURED, SAME MACHINE`; head **"Faster. Not different."**;
  `workers = 1  6.57 s` / `workers = 4  1.67 s  3.9x` / `workers = 8  0.83 s  7.9x` /
  `SplitResult  identical`; footer *parallelism may change the wallclock and nothing else —
  par_demo.py exits non-zero if any statistic diverges.*
- **VO:** "Eight workers, identical result."
- **In / out:** fade · fade.
- **Source:** **generated at build time from `/tmp/video/par_results.json`, written by the
  same `par_demo.py` run the previous shot filmed.** The card cannot quote a number the
  footage did not show. `build.sh` additionally refuses to build if that json is *newer*
  than `parallel.mp4`, which would mean it came from a different run. This is a fix for a
  real defect in the previous video, whose card said `6.61 s` while the README table said
  `6.60 s`.

### 11 · `start` — 4.5 s — card
- **On screen:** eyebrow `TRY IT`; head **"Two minutes. No API key."**; a terminal panel —
  `$ pip install ./core` / `$ bash examples/toy_calc/run.sh`; then in green
  `baseline_val 0.0  →  test_reward 1.0   (gate-accepted, test sealed)`; then
  `github.com/skillberry-ai/cap-evolve`.
- **VO:** "Start in two minutes, with no API key."
- **In / out:** fade · fade.
- **Source:** commands verbatim from the README quickstart; `0.0 → 1.0` from
  `docs/RESULTS.md` toy_calc.

### 12 · `credits` — 4.0 s — card
- **On screen:** the mark, `cap·evolve`, then **`Made at`** over the IBM and Red Hat marks,
  then two factual sub-lines — *runner models served via IBM RITS and an IBM litellm proxy*
  and *self-hosted evaluation on Red Hat OpenShift (vLLM)* — then
  *Apache-2.0 · zero runtime dependencies · beta (0.x)* and the repo URL.
- **VO:** "cap-evolve. Made at IBM and Red Hat."
- **In / out:** fade · fade to black.
- **See the framing note below.**

---

## IBM / Red Hat framing

**What the repo actually supports.** `site/index.html` already puts both marks under the
label **"Made at"**, in the hero and again in the footer, using `site/assets/ibm-logo.svg`
and `site/assets/redhat-logo.svg` — both already committed. No logo was fetched from
anywhere. Beyond that label, `docs/RESULTS.md` states as fact that the runner and user
simulator were served **via IBM RITS** and **via an IBM ete litellm proxy**, and that other
runs used **Qwen 2.5 14B via vLLM on Red Hat OpenShift**. `presentation/README.md` refers to
"Working with Red Hat (Parsec PoC + head-to-head)". The git identity on this work is an
`@ibm.com` address.

**What the video therefore says.** The same words the site already uses — `Made at` — plus
two sub-lines that are pure statements of infrastructure fact. No "sponsored by", no
"endorsed by", no "in partnership with", no claim about either company's view of the
project. The marks appear once, in the credits, at modest size.

**Flag for the lead:** "Made at" is an *affiliation* claim, not an infrastructure one. It
is already published on the project site, so the video is not making a new claim — but if
that framing has never been cleared with IBM/Red Hat brand or legal, it is worth asking the
user before shipping, because a video is louder than a page footer. The defensible
fallback, needing no approval, is to drop the "Made at" line and keep only the two
infrastructure sub-lines with the marks — that is supported entirely by `docs/RESULTS.md`.

---

## Integrity rules this cut obeys

1. **Every on-screen number is either measured on camera or verbatim from
   `docs/RESULTS.md`.** `script.py` carries a `src_note` for each shot recording which.
2. **The demo session is labelled at both ends** — the lower-third says
   *hand-authored numbers, NO benchmark claim*, the renderer's own header says the same,
   and the voiceover says it aloud.
3. **No card restates a figure its footage contradicts.** The speedup card is *generated
   from* the filmed run, and `build.sh` fails if the two could have come from different
   runs.
4. **No mockups.** The terminal shot is `vhs` driving the real renderer; the dashboard shot
   is Chromium loading a real committed run artifact. Neither is a drawing.
5. **Split discipline is on screen**, per row, on the results card — `fit metric` vs
   `sealed test, held-out` — never averaged into one flattering number.
6. **RH-SWE-bench is omitted** because it has no committed run artifact and two
   different published figures.

## Known issues to watch

- **`ws-dash`:** `examples/tau2_airline/run_full/ui` renders a red `⊗ failed` badge and
  `algorithm not recorded`, and its Cost tab says "No spend recorded". See shot 6 above.
  Fixed: the `pass^k NaN%` the previous cut flagged is now correctly *omitted*.
- The `stderr=0.10442675862376782` in the parallel footage is `par_demo.py`'s own
  unrounded print. True, just ugly; rounding it is `par_demo.py`'s call, not the video's.
- No music bed. See `README.md` for why.
- **Not verifiable here:** the voiceover is macOS `say` and cannot be auditioned in this
  environment. Only its *duration* was checked (audio 89.51 s vs video 89.52 s, and every
  shot is `max(min_dur, vo + 0.7 s)` so no line clips).
