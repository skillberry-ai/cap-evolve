"""The demo video script — the SINGLE source of truth for every shot.

`assets.py` renders the cards and the voiceover from this table; `build.sh`
assembles them from the `shots.json` that `assets.py` writes. Nothing else
hard-codes a duration, a caption, or a narration line, so a card and its
voiceover can never drift apart.

Each shot:
  id        stable slug — names the PNG (`cards/<id>.png`) and the VO (`vo/<id>.m4a`)
  kind      "card"     — a still PNG, held for `dur`
            "footage"  — an external mp4 (`src`), trimmed to `dur`, captioned
  min_dur   floor in seconds; the real duration is max(min_dur, vo + PAD)
  vo        the narration, verbatim. "" = silent shot.
  caption   burned-in lower-third for footage shots (cards carry their own text)
  src       for footage: the key in `FOOTAGE` below
  draw      the renderer function name in assets.py
  data      renderer payload — this is the on-screen copy, final

EVERY NUMBER HERE IS ATTRIBUTED in the `src_note` field, which STORYBOARD.md
mirrors. `docs/RESULTS.md` and the live measurement are the only two sources.
"""
from __future__ import annotations

# ── canvas / palette / type ────────────────────────────────────────────────
W, H, FPS = 2560, 1440, 25
PAD_AFTER_VO = 0.7          # breath after the last syllable of a shot

BG      = (11, 13, 23)
PANEL   = (18, 22, 42)
LINE    = (35, 42, 69)
INK     = (230, 237, 243)
DIM     = (139, 147, 167)
MUTED   = (90, 99, 119)
PURPLE  = (124, 92, 255)
CYAN    = (34, 211, 238)
GREEN   = (74, 222, 128)
YELLOW  = (251, 191, 36)
RED     = (255, 107, 129)

SANS = "/System/Library/Fonts/SFNS.ttf"          # variable — see assets.font()
MONO = "/System/Library/Fonts/Menlo.ttc"         # matches the terminal footage

# ── footage sources ───────────────────────────────────────────────────────
# `blocked_on` is printed by build.sh and stamped on screen while the segment
# is still a stand-in, so a placeholder can never be mistaken for the final cut.
FOOTAGE = {
    "terminal": {
        "path": "/tmp/video/replay.mp4",
        "recipe": "vhs scripts/demo-video/replay.tape",
        "blocked_on": None,          # recorded against the rebuilt TUI
    },
    "dashboard": {
        "path": "/tmp/video/dashboard.mp4",
        # ONE-LINE SWAP when a better run lands: change --base (the dir of runs)
        # and --run (the run id) below, re-record, rebuild. Nothing else in the
        # build is coupled to which run is filmed — the shot has no burned-in
        # caption naming it, and every figure on screen is the dashboard's own.
        "recipe": ("cap-evolve dashboard --base examples/tau2_airline "
                   "--port 8791 --no-open   +   "
                   "dash.py --live http://127.0.0.1:8791 --run run_agentopt_v4"),
        "blocked_on": None,          # recorded against the rebuilt dashboard
    },
}

# ── background music ──────────────────────────────────────────────────────
# Generated, not licensed: `music.py` synthesises the bed from a chord table
# with the stdlib `wave` module, so there is nothing to attribute and the build
# stays reproducible. MUSIC_DB is how far UNDER the voiceover it sits.
MUSIC_WAV = "/tmp/video/music.wav"
MUSIC_DB = -20.0            # narration stays clearly on top
MUSIC_FADE_IN = 2.5
MUSIC_FADE_OUT = 3.5

# ── the real committed diff we put on screen (shot: diff) ─────────────────
# Source artifact, read directly:
#   examples/tau2_airline/run_full/ui/data/runs_run_full_diff_cand_0006.json
# Narrative + trajectory evidence: docs/OPTIMIZATION_EXAMPLES.md §1
DIFF_ARTIFACT = ("examples/tau2_airline/run_full/ui/data/"
                 "runs_run_full_diff_cand_0006.json")

DIFF_PROSE = [
    ("hunk", "@@ -118,7 +120,8 @@"),
    ("del",  "- Each reservation can use at most one travel"),
    ("del",  "  certificate, at most one credit card, and at"),
    ("del",  "  most three gift cards."),
    ("add",  "+ Each reservation can use at most one travel"),
    ("add",  "  certificate, at most one credit card, and at"),
    ("add",  "  most three gift cards. Even if the user has"),
    ("add",  "  multiple certificates, apply only ONE."),
]
DIFF_CODE = [
    ("hunk", "@@ -173,4 +173,22 @@"),
    ("add",  "+ # Guard: at most 1 travel certificate"),
    ("add",  "+ cert_count = sum("),
    ("add",  "+     1 for pm in payment_methods"),
    ("add",  "+     if user.payment_methods.get(pm.payment_id)"),
    ("add",  "+     and user.payment_methods["),
    ("add",  "+         pm.payment_id].source == \"certificate\")"),
    ("add",  "+ if cert_count > 1:"),
    ("add",  "+     raise ValueError("),
    ("add",  "+         f\"At most 1 travel certificate allowed\""),
    ("add",  "+         f\" ... Pick the single best certificate\""),
    ("add",  "+         f\" and use credit card or gift card for\""),
    ("add",  "+         f\" the remainder.\")"),
]

# ── the shot table ────────────────────────────────────────────────────────
SHOTS = [
    dict(
        id="logo", kind="card", draw="logo", min_dur=4.0,
        vo="cap-evolve. Watch capability evolve.",
        src_note="no numbers on screen",
        data=dict(
            wordmark="cap·evolve",
            tagline="watch capability evolve",
            sub="optimize an agent's prompts, tools and skills from its own failures",
        ),
    ),
    dict(
        id="problem", kind="card", draw="statement", min_dur=7.0,
        vo="A benchmark gives you one number. It won't tell you which policy rule was missing, or which tool let a bad call through. So you guess.",
        src_note="no numbers on screen",
        data=dict(
            eyebrow="THE PROBLEM",
            head="Your agent fails.\nYou don't know why.",
            lines=[
                ("A benchmark gives you one number.", DIM),
                ("Not which policy rule was missing.", DIM),
                ("Not which tool let a bad call through.", DIM),
            ],
            foot="So you guess — rewrite the prompt, run it again, hope.",
            accent=RED,
        ),
    ),
    dict(
        id="what", kind="card", draw="tiles", min_dur=7.0,
        vo="cap-evolve edits what your agent reads: prompts, tool code, "
           "MCP surfaces, skill packages.",
        src_note="capability list verbatim from README 'What can cap-evolve optimize?'",
        data=dict(
            eyebrow="WHAT IT DOES",
            head="It optimizes what your agent reads.",
            tiles=[
                ("system prompts", "rules, examples, output contracts", PURPLE),
                ("tool code", "executable guards inside the tool", CYAN),
                ("MCP surfaces", "tool docs + which tools are exposed", GREEN),
                ("skill packages", "SKILL.md, references, scripts", YELLOW),
            ],
            foot="Not its weights. Learned from its own failed trajectories.",
        ),
    ),
    dict(
        id="terminal", kind="footage", src="terminal", min_dur=16.0,
        vo="Each iteration scores a candidate on validation, reads the failures, "
           "and proposes one edit. Accepted, rejected, or indecisive — always "
           "with the reason. This session is illustrative: its numbers are "
           "hand-authored.",
        # No burned-in lower-third: the footage carries its own labelling. The
        # rebuilt CLI prints the demo banner ("illustrative sample … makes no
        # benchmark claim") as the last line of every replay frame, and the old
        # overlay used to COVER exactly that line. Removing the overlay makes the
        # disclaimer more visible muted, not less.
        src_note="every number visible is from the bundled demo_session and is "
                 "labelled on screen, by the CLI itself, as making no benchmark "
                 "claim",
    ),
    dict(
        id="diff", kind="card", draw="diff", min_dur=10.5,
        vo="One real iteration: a policy rule, and in the same edit, code inside "
           "the tool that rejects the illegal call. Task fourteen went from one "
           "pass in ten, to six.",
        src_note="diff rows read from " + DIFF_ARTIFACT + "; the 1/10 -> 6/10 "
                 "task-14 figure is docs/OPTIMIZATION_EXAMPLES.md §1",
        data=dict(
            eyebrow="ONE REAL ITERATION  ·  τ²-bench airline",
            head="cand_0005 → cand_0006",
            left=("policy/policy.md    +9  −2", DIFF_PROSE),
            right=("tools/tools.py    +37  −0", DIFF_CODE),
            result="prose for the knowledge gap  +  code for the rule the agent already knew",
            evidence="task 14:  1/10 → 6/10 the iteration the guard landed",
        ),
    ),
    dict(
        id="dashboard", kind="footage", src="dashboard", min_dur=8.0,
        vo="The dashboard holds the whole run — every candidate, every trial, "
           "every verdict. Five rejections, and nothing beat the seed.",
        # No burned-in lower-third. The null result is not lost with the caption
        # gone: the dashboard's OWN tiles say it in the frame we film —
        # "BASELINE VAL 56.7%", "BEST VAL 56.7% candidate seed", "Δ VAL VS
        # BASELINE 0.000 / 0% relative", "SEALED TEST 50.0% · seed 50.0% ·
        # Δ 0.000", "VERDICTS 5 candidates · 0 accept · 5 reject · 0
        # indecisive", and the Gate tab's five reject rows with their paired
        # arithmetic. Verified on the extracted frames, not assumed.
        src_note="live dashboard over examples/tau2_airline/run_agentopt_v4, "
                 "committed WITH its events.jsonl so the shot is reproducible "
                 "from the repo. It is the most rigorous τ²-bench run here — "
                 "num_trials 5, 26/12/12 split, five candidates, five gate "
                 "JSONs — and it is a NULL RESULT: best_id = seed, val 0.5667 "
                 "unchanged, train 0.5308, sealed test 0.5000 with every Δ = 0 "
                 "by construction (measure.json no_accepted_change = true). "
                 "Three of the five candidates were byte-identical seed copies "
                 "rejected as controls; the other two cleared the significance "
                 "bar (paired Δ̄=+0.0167 > 0.2·SE) and were still VETOED by the "
                 "regression check (gate_cA_partial.json, gate_cB_becabin.json) "
                 "— which is why the VO says 'five rejections', not 'the gate "
                 "rejected all five'. Spend is NOT claimed: this runner reports "
                 "no per-call cost, so cost.metered is false and the dashboard "
                 "prints 'SPEND not reported — $0 here would be a guess, not a "
                 "measurement'. That is also why dash.py no longer films the "
                 "Cost tab. The older run_full/ui static export is still NOT "
                 "filmed: its summary has no status field, so the rebuilt "
                 "dashboard stamps a red 'failed' badge on a run that finished, "
                 "and a false badge is worse than a true null result.",
    ),
    dict(
        id="honest", kind="card", draw="rows", min_dur=12.0,
        # The 'indecisive' beat is deliberately on-screen only — the card holds
        # long enough to read it, and the VO would overrun the shot.
        vo="Here's what most optimizers skip. Acceptance is a paired "
           "significance test, on validation only: clear k standard errors, or "
           "it's noise. The test split is scored once, then sealed.",
        src_note="semantics verified in core/cap_evolve/gate.py and "
                 "core/cap_evolve/harness.py (no_regression is opt-in — the "
                 "card says 'optional')",
        data=dict(
            eyebrow="WHY YOU CAN BELIEVE THE NUMBER",
            head="Honest by construction.",
            rows=[
                ("accept only if", "mean Δ  >  k · SE", "paired, per task", GREEN),
                ("gate split", "val only", "train can never gate", CYAN),
                ("test split", "sealed · scored exactly once", "a 2nd finalize raises", CYAN),
                ("repeated trials", "mean ± stderr · pass^k", "variance is reported", PURPLE),
                ("regression veto", "optional — reject if a passing task breaks", "dual gate", YELLOW),
                ("evidence too thin", "indecisive — NOT rejected", "says nothing about the edit", RED),
            ],
        ),
    ),
    dict(
        id="results", kind="card", draw="results", min_dur=10.0,
        # The card's TOP row is RH-SWE-bench, so the voice leads with it: the
        # narration used to describe rows 2 and 3 and skip the most persuasive
        # fact on screen. Scoped deliberately — "past an unoptimized Opus" is
        # this benchmark and this harness only, which is what the card's
        # sub-line and src_note below already say. The held-out clause reads
        # only the 47.5 endpoint; "30.0 → 47.5" stays on screen, and on-screen
        # text remains the primary channel.
        vo="RH-SWE-bench: fifty-five point seven to seventy-three point one, "
           "past an unoptimized Opus. τ²-bench airline: fifty-three point six "
           "to seventy-one point two, and forty-seven point five held out.",
        src_note="τ²-bench, SkillsBench and toy_calc rows verbatim from "
                 "docs/RESULTS.md. The RH-SWE-bench row is the CROSS-MODEL CHART "
                 "measurement, site/assets/rh_swe_bench.png: its 'Sonnet 4.6 "
                 "Claude Code' bar reads 55.7 and its 'Sonnet 4.6 Claude Code "
                 "optimized with cap-evolve' bar reads 73.1 — same model, same "
                 "harness. +17.4 pp, and 17.4/55.7 = +31.2% relative, computed "
                 "the same way as every other row on the card. That chart also "
                 "shows an unoptimized Opus 4.6 at 63.3, which is the sub-line's "
                 "claim, scoped to this benchmark/harness. This pair is a "
                 "DIFFERENT measurement from the 119-task fit-metric run "
                 "(58.0 → 76.5) documented in docs/RESULTS.md; both are real and "
                 "the repo already documents the distinction — nothing here "
                 "restates or replaces it.",
        data=dict(
            eyebrow="MEASURED",
            head="Baseline → optimized",
            rows=[
                ("RH-SWE-bench  ·  skill package + system prompt",
                 "Sonnet 4.6, Claude Code + Harbor — beats an unoptimized Opus 4.6 (63.3)",
                 "55.7", "73.1", "+31.2%", CYAN),
                ("τ²-bench airline  ·  policy + tool code",
                 "val — fit metric, 50 tasks × 10 trials", "53.6", "71.2", "+32.8%", CYAN),
                ("τ²-bench airline  ·  held-out 30/20",
                 "sealed test, 20 tasks, scored once", "30.0", "47.5", "+58.3%", GREEN),
                ("SkillsBench  ·  skill packages",
                 "sealed test, held-out", "55.6", "66.7", "+20.0%", GREEN),
                ("toy_calc  ·  zero-API, deterministic",
                 "sealed test", "0.0", "100.0", "proof", PURPLE),
            ],
        ),
    ),
    dict(
        id="start", kind="card", draw="start", min_dur=4.5,
        vo="Start in two minutes, with no API key.",
        src_note="commands verbatim from README 'Try it in two minutes'; "
                 "0.0 → 1.0 from docs/RESULTS.md toy_calc",
        data=dict(
            eyebrow="TRY IT",
            head="Two minutes. No API key.",
            cmds=[
                "git clone .../cap-evolve && cd cap-evolve",
                "pip install ./core",
                "bash examples/toy_calc/run.sh",
            ],
            out="baseline_val 0.0  →  test_reward 1.0   (gate-accepted, test sealed)",
            url="github.com/skillberry-ai/cap-evolve",
        ),
    ),
    dict(
        id="credits", kind="card", draw="credits", min_dur=4.0,
        vo="cap-evolve. Made at IBM and Red Hat.",
        src_note="'Made at' is the framing already used on the project site "
                 "(site/index.html hero + footer); the marks are the repo's own "
                 "site/assets/{ibm,redhat}-logo.svg, rendered in their brand "
                 "colours (#1f70c1 / #ee0000) taken from those same files",
        data=dict(
            wordmark="cap·evolve",
            affil="Made at",
            url="github.com/skillberry-ai/cap-evolve",
        ),
    ),
]

BY_ID = {s["id"]: s for s in SHOTS}
assert len(BY_ID) == len(SHOTS), "duplicate shot id"
