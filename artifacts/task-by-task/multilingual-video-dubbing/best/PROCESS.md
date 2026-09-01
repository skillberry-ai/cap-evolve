# PROCESS — iteration cand_0004 (explainability; REQUIRED)

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag | change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Loudness target wrong (`test_metric_04_loudness_standard`) | multilingual-video-dubbing (1/10 trials fail → mean 0.90) | Agent sometimes normalizes to a **streaming/comfort loudness (~-16/-18 LUFS)** instead of the graded **-23 LUFS** broadcast target. §3 hedged ("target depends on the spec; a common target is -23"), so an opinionated agent overrides to -18. | KNOWLEDGE | BODY (text-to-speech §3) |

Only ONE failing cluster exists. All 7 other metrics (files, 48k SR, mono, alignment, drift,
naturalness metric_08, report schema) PASS in all 10 trials of the champion cand_0001. No other
cluster to fix; adding edits elsewhere would be speculative (fails REAL/SAFE) — deliberately skipped.

## Root-cause evidence (why prior loudness iterations were misdiagnosed)
- **t0 (FAIL):** Kokoro output measured **-23.65 LUFS (already in band!)**; agent then normalized
  UP to **-18.08**, wrote `measured_lufs: -18.08`, and described it as "human-comfortable,
  high-quality range." Verifier: `Loudness -18.1 LUFS is non-compliant (should be -23 ± 1.5)`.
- **t1 (PASS):** used `loudnorm` at the -23/default target: Input -23.6 → Output -23.1 LUFS. PASS.
- Discriminator between pass and fail is **the target value chosen**, NOT loudnorm accuracy.
  t1 proves single-pass `loudnorm` hits -23 fine. This REFUTES cand_0002/cand_0003's hypothesis
  ("single-pass loudnorm is inaccurate on short clips") — both were rejected Δ=0.

## Changes made this iteration
| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | BODY | `text-to-speech/SKILL.md` §3 | Pin delivery target to **-23 LUFS (EBU R128)**, state it is graded within -24.5..-21.5, and explicitly forbid streaming/comfort targets (-14/-16/-18) with the exact failure mode ("a track at -18 fails a -23 ± 1.5 gate"). Keep `loudnorm=I=-23` as valid (passing trials use it) and add a linear-gain option + a MANDATORY final in-band re-measure of the delivered file. General EBU R128 fact; no task-specific filename/value/marker. | Yes — t1..t9 already land ~-23.1..-23.65 via loudnorm; they already use -23 and verify, so behavior is unchanged. Only the wrong-target (-18) path is removed. |

## Verify-the-fix
- Ties to `test_metric_04_loudness_standard` assertion `Loudness -18.1 LUFS is non-compliant
  (should be -23 ± 1.5)` in t0. The edit removes exactly the reasoning that produced -18 (agent
  chose a comfort target) and adds a self-check that would catch/repair an out-of-band delivered
  file. Contrast t0(-18, comfort target) vs t1(-23.1, correct target) confirms target-choice is
  the discriminator.
- Blast radius: single-task val; the ffmpeg-* skills untouched (cand_0002 proved t0 never loads
  `ffmpeg-audio-processing`). Passing trials already target -23 → not pushed onto a worse path.
- Skill still VALID: frontmatter intact (desc 274 chars), body 84 lines / ~1.3k tokens, script
  ref `scripts/kokoro_tts.py` resolves, no `references/` links (none broken).
- No new script: ffmpeg/ffprobe are absent on this build node, so any new ffmpeg-based script
  could not be RUN-verified here; per the rules an unverified script is dropped. The miss is a
  KNOWLEDGE gap (the target value), for which prose is the correct class; the verify step uses
  tools (`ebur128`, `volume`) the agent already runs in the traces.

## Process & features used
- Diagnosed inline from the 10 champion trajectories (single task / single cluster) — no subagent
  fan-out needed for one cluster.
- Read LEDGER + JOURNAL + both prior loudness diffs (cand_0002, cand_0003) to avoid re-testing
  their refuted "loudnorm-accuracy" approach.

## Good things to PRESERVE
- Kokoro-as-default + `kokoro_tts.py` (cand_0001, ACCEPTED) — metric_08 naturalness solid. Untouched.
- `loudnorm` remains a valid tool at the -23 target (do NOT forbid it — passing trials rely on it).

## Deliberately skipped
- A bundled loudness/master script: cannot RUN-verify ffmpeg here; and cand_0002/cand_0003 showed
  a measure→linear-gain script did not move the gate (they misattributed the cause anyway).
- ffmpeg-* skills: all their metrics pass; editing risks regression with no upside.
- Any other cluster: none failing.
