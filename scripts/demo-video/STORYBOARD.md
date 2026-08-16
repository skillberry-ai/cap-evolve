# cap-evolve demo video — storyboard

**Format:** 2560×1440, 25 fps, 88.8 s, h264 + one mono AAC voiceover track, 5.4 MB.
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
| `RH-SWE-bench` | **Now on the results card, at the lead's instruction, using the chart pair `55.7 → 73.1`.** The repo holds two real measurements of this same work: the 119-task **fit-metric** run in `docs/RESULTS.md` (`58.0 → 76.5`, no committed artifact) and the cross-model chart `site/assets/rh_swe_bench.png`, whose *same-model* bars read `Sonnet 4.6 Claude Code 55.7` and `Sonnet 4.6 Claude Code optimized with cap-evolve 73.1`. The video quotes the **chart** pair, because it is a clean same-model baseline → optimized comparison with a published figure behind it. `docs/RESULTS.md` keeps documenting the other pair and the unresolved relationship between them; the video does not restate or replace it. |

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
below are the built values. **10 shots, 88.78 s total** (was 10 shots / 84.73 s — the
`dashboard` and `results` voiceovers grew, see shots 6 and 8).

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

### 4 · `terminal` — 16.0 s — footage · **reshot, Arbor-style opening**
- **Recipe:** `vhs scripts/demo-video/replay.tape`, window from `TERM_SEEK=0.6` s — the tape
  is built to be played from the top, in two beats.
- **Geometry:** the tape records **2010×1440**, **FontSize 28**, Padding 40 →
  **112 cols × 40 rows** (measured with `tput cols` / `tput lines` inside the tape, not
  computed). `build.sh`'s `NORM` then pillarboxes that 1.40-aspect recording symmetrically
  inside 2560×1440. It was 2560 wide (144 cols) until this cut, and that was the single
  worst framing defect in the video: the home screen's content is only ~87 columns, so it
  sat hard left with **1005 px (39 %) of the frame dead on the right** and read as a broken
  render. Measured on the published 0:21 frame, before → after:

  | | content | dead left | dead right |
  |---|---|---|---|
  | 144 cols (old) | 1515 px | 40 px | **1005 px** |
  | 112 cols (this cut) | 1477 px | 314 px | 769 px |

  The replay beat, which fills whatever width it is given, goes from `40 / 178` to a
  symmetric `314 / 318`.
  - **Why 40 rows is the ceiling, and why the text is not bigger.** Text height in the
    finished frame is `FontSize × (1440 / tape Height)`, so it is set by the row count, not
    by `FontSize`: 40 rows at Height 1440 is 34 px per row ⇒ FontSize 28. Raise it to 34
    and only 33 rows fit, `home()` scrolls the capybara off the top, and the *effective*
    glyph size is unchanged. Nothing is gained by trading rows for a bigger font.
  - **Why 112 and not the 105–110 that pure symmetry wants.** `tui.DEMO_BANNER` (the
    demo disclaimer) is 119 characters and the terminal hard-wraps it **mid-word** at every
    width from 104 to 111 — at 107 it reads *"…make no benc / hmark claim."* 112 is the
    narrowest width ≥ 105 that breaks it on a space. Splitting a compliance line mid-word
    costs more than 40 px of asymmetry.
  - **The residual 769 px is a geometry ceiling, not a bug.** The home screen's content
    box is 1477 × 1331 ≈ **1.11 aspect**; 16:9 is 1.78. With the 40 rows `home()` needs,
    the width *cannot* be filled without cropping rows. Nothing is stretched or distorted:
    the recording keeps its aspect and is centred.
  - The home screen is adaptive — `home()` condenses its command table to 3 rows below
    ~23 rows. **The full table is what is filmed**, because 40 rows is also what makes the
    text as large as it can be, and the condensed form would show less of the CLI for no
    legibility gain.
- **Beat 1 (~0.6 → 5.4 s) — opening the CLI.** The user types `cap-evolve` and the branded
  home screen appears: the truecolor **capybara mark**, `cap-evolve / watch capability
  evolve`, the one-paragraph what-it-is, the **Golden path** (`init` → `doctor` →
  `run --tui`), and the three command groups (set up / optimize / inspect) with
  `cap-evolve 0.1.0` at the foot. `COLORTERM=truecolor` is exported off camera because that
  is what unlocks the mark in `core/cap_evolve/branding.py`.
- **Beat 2 (~7.6 → 16.6 s) — the phases of a run.** `cap-evolve replay --demo --speed 40
  --max-gap 0.7`, i.e. the *same* live view a real run renders, driven by the bundled
  `demo_session`. On camera, in order: the run identity card (run · algorithm · spec ·
  split · gate `paired k_se 0.20 trials 2` · target), the **phase breadcrumb**
  `intake › check › baseline › optimize › finalize › report` with the current phase lit,
  the `run_config` + `splits frozen train=8 val=6 test=6 (test sealed)` intake lines, the
  seed **baseline** `0.333±0.193`, then one candidate per iteration with the gate's own
  arithmetic — **`✓` ACCEPT**, **`✗` reject**, and **`~ indecisive: Δ̄=0 within noise
  (SE=0.105, n=6) — not a reject`** — the `iter 7 ✓4 ✗2 ~1` counter, `test (sealed) 0.833
  Δ vs base +0.500`, and finally `FINALIZE test=0.8333 (baseline 0.5000, Δ+0.3333)
  best=cand_0007`.
- **Real output, not a mockup:** the tape defines `cap-evolve() { python -m cap_evolve.cli
  "$@"; }` with `PYTHONPATH=core`, so it runs **this checkout's** rebuilt CLI rather than
  whatever `cap-evolve` is on `PATH` (on the author's machine that resolves to a different
  clone). `--speed` / `--max-gap` compress the recorded inter-event *gaps* only.
- **No lower-third.** The overlay is gone (see the removal note at the end of this file).
  Nothing was lost: the renderer prints `illustrative sample — replays the cap-evolve UI
  with no API key. The numbers are synthetic and make no benchmark claim.` itself, and the
  old band used to sit *on top of* that line. It is now visible for the whole shot.
- **VO:** "Each iteration scores a candidate on validation, reads the failures, and
  proposes one edit. Accepted, rejected, or indecisive — always with the reason. This
  session is illustrative: its numbers are hand-authored."
- **In / out:** fade · fade.
- **Numbers:** all from `core/cap_evolve/demo_session/events.jsonl`. **Hand-authored, no
  benchmark claim** — on screen from the renderer itself, and said aloud.

### 5 · `diff` — 10.6 s — card
- **On screen:** eyebrow `ONE REAL ITERATION · τ²-bench airline`; head
  **"cand_0005 → cand_0006"**; two panels side by side —
  left `policy/policy.md +9 −2` with the real removed/added rule, right
  `tools/tools.py +37 −0` with the real `cert_count` guard and its recovery message;
  under them *prose for the knowledge gap + code for the rule the agent already knew*;
  then in green **`task 14:  1/10 → 6/10 the iteration the guard landed`**. No footer line
  — the artifact path lives in the shot's `src_note`, not on screen.
- **VO:** "One real iteration: a policy rule, and in the same edit, code inside the tool
  that rejects the illegal call. Task fourteen went from one pass in ten, to six."
- **In / out:** fade · fade.
- **Source:** diff rows from `runs_run_full_diff_cand_0006.json`; the 1/10 → 6/10 figure
  from `docs/OPTIMIZATION_EXAMPLES.md` §1.

### 6 · `dashboard` — 8.3 s — footage · **re-filmed against `run_agentopt_v4`**
- **Recipe:** `cap-evolve dashboard --base examples/tau2_airline --port 8791 --no-open`,
  then `dash.py --live http://127.0.0.1:8791 --run run_agentopt_v4`, window from
  `DASH_SEEK=1.6` s. Kill stray dashboards first (`pkill -f "cap-evolve dashboard"`) —
  leftovers on the fixed port have caused false failures.
- **On screen:** Chromium driving the *running* dashboard over
  `examples/tau2_airline/run_agentopt_v4`. Opens the run — `run_agentopt_v4 · ⊘ completed ·
  agent-optimize · 🔒 test sealed`, the split-discipline line (`splits · train 26 · val 12 ·
  test 12 · seed 0 | val decides selection; test is scored exactly once and never optimized
  against.`), then the tile grid — `BASELINE VAL 56.7% ±0.118 n=12` · `BEST VAL 56.7%
  candidate seed` · `Δ VAL VS BASELINE 0.000 / 0% relative` · `SEALED TEST 50.0% · seed
  50.0% · Δ 0.000` · `VERDICTS 5 candidates, 0 accept · 5 reject · 0 indecisive` ·
  `SPEND not reported` · `TOKENS not recorded` · `VAL TASKS 12` · `EVENTS 17` — then
  **Candidates**, **Gate** (five rows, every one `reject`, each with its paired arithmetic
  note underneath) and **Tasks** (per-task val, 12 tasks × 5 trials).
- **Still a null result, and it cannot read as a win.** `best_id = seed`, train 0.5308,
  val 0.5667, sealed test 0.5000, **every Δ = 0 by construction**
  (`measure.json` `no_accepted_change: true`).
- **No lower-third.** The null result is not lost with the band gone — the four headline
  tiles above are the dashboard's own, and the Gate tab's five `reject` rows are too.
  Verified on extracted frames at **0:48** and **0:52**, not assumed.
- **VO:** "The dashboard holds the whole run — every candidate, every trial, every verdict.
  Five rejections, and nothing beat the seed."
- **In / out:** fade · fade.
- **Numbers:** every figure is that run's own, read back from the run dir and the
  dashboard's `/api/runs/run_agentopt_v4`. Five candidates, all rejected: `c0_null5`,
  `c0_null5b` and `c0_null5c` are **byte-identical copies of the seed**, entered as
  controls to measure the harness rather than an edit, and rejected by the significance
  gate. `cA_partial` and `cB_becabin` are real policy edits that **cleared** the bar
  (`paired Δ̄=+0.0167 > 0.2·SE`) and were then **VETOED by the regression check**
  (`gate_cA_partial.json`, `gate_cB_becabin.json`). Which is why the VO says *"five
  rejections"* and not *"the gate rejected all five"* — the second is false for two of them.
  This is also the `regression veto` row of shot 7 firing for real.
- **Spend is not claimed.** This run's runner reports no per-call cost, so
  `cost.metered` is `false` and the dashboard prints **`SPEND not reported — this runner
  reports no per-call cost — $0 here would be a guess, not a measurement`**. The VO
  therefore says "every trial", not "every dollar", and `dash.py` no longer films the
  **Cost** tab: it is honest but empty, and 3.4 s of zeros says nothing. Its dwell went to
  **Gate** (3.4 s) and **Tasks** (2.4 s).

**Why this run.** `run_agentopt_v4` is the most rigorous τ²-bench run in the repo —
`num_trials: 5`, a 26/12/12 split, five candidates with five committed gate JSONs, `pass^k`
defined — and it ships **with its `events.jsonl`**, so the shot is reproducible from a
clean checkout. It replaces the older `run_agentopt` (also a null result, but 1 trial and
four candidates). It is *not* `run_full`: that 50-task win only exists as a static export
at `examples/tau2_airline/run_full/ui`, whose `summary` carries no `status` and no
`algorithm`, so the rebuilt dashboard stamps a red **`⊗ failed`** badge and
`algorithm not recorded` on a run that finished, and its Cost tab reads "No spend recorded"
because the export ships no `events.jsonl`. A false "failed" badge is a worse integrity
problem than a true null result, and the export cannot be regenerated (its source run dir
was a `/tmp` path). **Flagged for the lead:** that badge and empty ledger are `ws-dash`
bugs; if they are fixed, `--run run_full` against a regenerated export is the nicer shot
and only `--run` plus the VO in `script.py` need changing.
- **Correction to the earlier note:** `run_agentopt_v4` has **no Screens tab** —
  its `capabilities.screens` is `false` (as are `trajectories` and `diffs`). The tabs it
  actually exposes are Overview, Candidates, Gate, Tasks, Cost, Logs, Agent rounds, Memory,
  Files.

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

  No footer line. Row spacing widened to 124 px (from 108) so the six rows use the space
  the footer used to occupy.
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

### 8 · `results` — 13.7 s — card
- **On screen:** eyebrow `MEASURED`; head **"Baseline → optimized"**; **five** rows, each
  with its split discipline spelled out under the name and a dot-to-dot bar on a shared
  `reward × 100` axis:

  | row | split label on screen | bar | gain |
  |---|---|---|---|
  | RH-SWE-bench · skill package + system prompt | Sonnet 4.6, Claude Code + Harbor — beats an unoptimized Opus 4.6 (63.3) | 55.7 → 73.1 | +31.2% |
  | τ²-bench airline · policy + tool code | val — fit metric, 50 tasks × 10 trials | 53.6 → 71.2 | +32.8% |
  | τ²-bench airline · held-out 30/20 | sealed test, 20 tasks, scored once | 30.0 → 47.5 | +58.3% |
  | SkillsBench · skill packages | sealed test, held-out | 55.6 → 66.7 | +20.0% |
  | toy_calc · zero-API, deterministic | sealed test | 0.0 → 100.0 | proof |

  **No amber cost line** (the `~$32 (cap $400)` spend line is removed) and **no footer**.
  Row pitch is 155 px from y=500, so five rows fill the card without the removed lines.
- **VO:** "RH-SWE-bench: fifty-five point seven to seventy-three point one, past an
  unoptimized Opus. τ²-bench airline: fifty-three point six to seventy-one point two, and
  forty-seven point five held out."
  - The narration used to open on row 2 and **skip its own top row** — the single most
    persuasive fact on the card. It now leads with RH-SWE-bench, scoped exactly as the
    card's sub-line and `src_note` scope it: this benchmark, this harness, one unoptimized
    Opus 4.6 bar at 63.3. No "beats Opus" in the abstract.
  - The held-out clause reads only the `47.5` endpoint; `30.0 → 47.5` stays on screen.
    On-screen text is still the primary channel — the video is fully comprehensible muted —
    and the shot grew 10.0 s → 13.7 s to fit the line without clipping it.
- **In / out:** fade · fade.
- **Source:** the τ²-bench, SkillsBench and toy_calc rows are verbatim from
  `docs/RESULTS.md`. The **RH-SWE-bench** row is the cross-model chart measurement,
  `site/assets/rh_swe_bench.png`: `Sonnet 4.6 Claude Code` = 55.7 and `Sonnet 4.6 Claude
  Code optimized with cap-evolve` = 73.1 — the same model and harness on both bars.
  Arithmetic, computed the way every other row's is: 73.1 − 55.7 = **+17.4 pp**, and
  17.4 / 55.7 = **+31.2 %** relative. The sub-line's "beats an unoptimized Opus 4.6 (63.3)"
  is the same chart's `Opus 4.6 Claude Code` bar, and is scoped on screen to this
  benchmark/harness. This pair is a **different measurement** from the 119-task fit-metric
  run (`58.0 → 76.5`) that `docs/RESULTS.md` documents; both are real, the repo already
  explains the distinction, and the video neither restates nor supersedes it.

### 9 · `start` — 4.5 s — card
- **On screen:** eyebrow `TRY IT`; head **"Two minutes. No API key."**; a terminal panel —
  `$ pip install ./core` / `$ bash examples/toy_calc/run.sh`; then in green
  `baseline_val 0.0  →  test_reward 1.0   (gate-accepted, test sealed)`; then
  `github.com/skillberry-ai/cap-evolve` in cyan. No footer line.
- **VO:** "Start in two minutes, with no API key."
- **In / out:** fade · fade.
- **Source:** commands verbatim from the README quickstart; `0.0 → 1.0` from
  `docs/RESULTS.md` toy_calc.

### 10 · `credits` — 4.0 s — card
- **On screen:** the mark, `cap·evolve`, **`Made at`**, then the IBM and Red Hat marks **in
  their own brand colours** (IBM `#1f70c1`, Red Hat `#ee0000`, both read out of
  `site/assets/*-logo.svg`), a short purple rule, and the repo URL. Nothing else.
- **Removed:** the two infrastructure sub-lines (*runner models served via IBM RITS and an
  IBM litellm proxy*, *self-hosted evaluation on Red Hat OpenShift (vLLM)*) and the
  *Apache-2.0 · zero runtime dependencies · beta (0.x)* licence line.
- **Red Hat clipping, fixed.** The rasteriser used to force both marks to monochrome
  `#e6edf3` and lay a `width:900px; height:auto` SVG inside a fixed 1200×400 flex page. The
  Red Hat mark has a `0 0 24 24` viewBox, so it laid out 900 px tall in a 400 px viewport,
  overflowed centred, and the element screenshot **lost the top of the hat**. The viewport
  is now derived from each SVG's own viewBox plus 12 px of pad, the marks are exported with
  transparency, and they are normalised on their **trimmed ink height** (132 px) rather than
  on raster height — so the wide IBM wordmark and the near-square hat read at the same
  weight. Verified by looking at the rendered card and at a frame at 1:23.
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
2. **The demo session labels itself.** With the burned-in lower-thirds removed, the
   renderer's *own* banner — *illustrative sample … The numbers are synthetic and make no
   benchmark claim* — carries it, on screen for the whole shot (the old band covered that
   very line), and the voiceover says it aloud.
3. **No card restates a figure its footage contradicts.** The dashboard shot's null result
   is legible from the dashboard's own verdict tiles, and the measured gains on the results
   card are labelled with their own splits and are a different run. The VO says *"nothing
   beat the seed"* over footage whose tiles read `Δ 0.000` — the two agree, and neither
   claims a win.
8. **Framing is never faked to fill the frame.** The terminal recording is pillarboxed at
   its true aspect and centred; it is never stretched, and rows are never cropped to widen
   it. The dead space that remains is the home screen's own 1.11 aspect against 16:9.
4. **No mockups.** The terminal shot is `vhs` driving the real renderer; the dashboard shot
   is Chromium loading a real committed run artifact. Neither is a drawing.
5. **Split discipline is on screen**, per row, on the results card — `fit metric` vs
   `sealed test, held-out` — never averaged into one flattering number.
6. **RH-SWE-bench is on screen as the chart pair `55.7 → 73.1`** — a same-model
   baseline → optimized comparison off `site/assets/rh_swe_bench.png`, with the arithmetic
   done the same way as every other row (+17.4 pp, +31.2 % relative). It is *not* the
   119-task fit-metric pair, and nothing in the repo was rewritten to agree with it.
7. **Bottom text is gone from shot 3 onward, and no claim went with it.** Every removed
   grey footer was provenance, which now lives only in `script.py`'s `src_note` — never a
   number or a caveat that the card body did not already carry.

## Known issues to watch

- **`ws-dash`:** `examples/tau2_airline/run_full/ui` renders a red `⊗ failed` badge and
  `algorithm not recorded`, and its Cost tab says "No spend recorded". See shot 6 above.
  Fixed: the `pass^k NaN%` the previous cut flagged is now correctly *omitted*.
- The `parallel` footage shot and the `speedup` card are **removed from the cut** (they
  were 1:12.44 → 1:20.94), along with `build.sh`'s `par_results.json` freshness check and
  `parallel.tape`. `par_demo.py` itself is kept as a standalone parallelism check, but
  nothing in the build reads it any more and the README no longer documents it.
- **Music bed, generated not licensed.** `scripts/demo-video/music.py` synthesises a slow
  four-chord pad (Am–F–G/C–Em, one chord per 8 s, cross-faded, plus a ~0.12 Hz tremolo)
  with the stdlib `wave` module — no download, nothing to attribute, byte-identical on a
  rebuild. `build.sh` mixes it under the narration at `script.MUSIC_DB = -20 dB` with a
  2.5 s fade in and a 3.5 s fade out, and refuses to ship if the bed is shorter than the
  cut. Measured on the built file: **-40.5 dB** mean in a narration gap vs **-17.0 dB**
  mean under narration.
- **Not verifiable here:** the voiceover is macOS `say` and cannot be auditioned in this
  environment — nobody has *listened* to this cut, and no claim is made about how the mix
  sounds. Only durations were checked (video 88.84 s, audio 88.83 s, music bed 88.78 s, and
  every shot is `max(min_dur, vo + 0.7 s)`, so no line clips its shot or the end of the
  cut). The music measurement quoted above (-40.5 dB in a gap vs -17.0 dB under narration)
  is from the previous cut; the mix parameters are unchanged, but it has not been re-taken.
- **Captions:** 26 cues, longest 80 chars, under the `SRT_MAX_CHARS = 84` cap that
  `assets.py` asserts. Cues split on sentence → clause → word boundaries.
