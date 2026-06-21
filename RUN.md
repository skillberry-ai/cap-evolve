# RUN — drive the full cap-evolve pipeline (point any agent here)

You are an AI agent asked to optimize an agent capability with **cap-evolve**.
Follow these steps exactly. The skills you load do the real work; this file just
sequences them and enforces the non-negotiable rules.

## 0. Install (once)

**Claude Code (plugin — recommended):** load the bundled plugin so every phase /
algorithm / optimizer skill becomes a `/cap-evolve:<skill>` command, the honesty
hooks arm, and the `using-cap-evolve` router auto-triggers on "optimize X":
```
claude --plugin-dir ./plugins/cap-evolve        # dev: load the plugin in place
pip install ./core                              # the honest-eval substrate (or export CAPEVOLVE_CORE)
```
The plugin's hooks (PreToolUse / Stop / SubagentStop / SessionStart) enforce the
sealed-test and green-check rules automatically; they no-op outside a run dir.

**Any host (host-agnostic — Codex / Gemini / opencode / openclaw / IBM Bob / bare):**
```
./install.sh                     # copy skills into this host's skills dir
pip install ./core               # or: export CAPEVOLVE_CORE="$PWD/core"
```
This path needs none of the Claude-only features. The optimizer step (`run-optimizer`)
runs the chosen CLI prose-fed and sequential, so the full pipeline still completes;
the offline `mock` optimizer keeps zero-API CI working.

> Under the plugin, prefix the skill names below with `/cap-evolve:` (e.g.
> `/cap-evolve:intake`); on a bare host, "load the **`intake`** skill" means open
> its `SKILL.md`. Either way the steps and rules are identical.

## 1. Intake — collect inputs
Load the **`intake`** skill (or start with **`using-cap-evolve`**, the router that
sends "optimize X" here). It interviews the user, scaffolds `.capevolve/project/`
(adapters + inputs + `capevolve.yaml` + `PROJECT.md`), and gathers inputs.
> For every input the skill marks **NEEDED** that is missing, ASK THE USER —
> quote the expected path, the command/options to obtain it, and alternatives.
> Never fabricate a NEEDED input.

## 2. Implement & check — make the contract real
Load **`implement-and-check`**. Implement the 4 adapter methods in
`.capevolve/project/adapters/adapter.py` (and any selected skill's `abstract.py`),
then run each skill's `check.py` and:
```
cap-evolve check .capevolve/project       # HARD GATE — must print {"ok": true}
```
**Do not proceed past this gate until it is green.** A half-wired project cannot
produce an honest number.

## 3. Baseline
Load **`baseline`**: score the unmodified capability on VAL to confirm there is
headroom. Records the starting point in the run dir.

## 4. Optimize
Load the algorithm skill named in `capevolve.yaml` (e.g. **`hill-climb`** with
`algorithm_focus: all`). It runs
the loop: select parent → propose edit (via your chosen **optimizer** skill) →
evaluate on VAL → **gate** (accept only if Δ exceeds the significance bar) →
snapshot or record-as-rejected → repeat until budget is spent. Diagnosis of
traces is provided by the **`diagnose`** skill, which the algorithm calls to turn
failures into an actionable learning signal.

## 5. Finalize & report
Load **`finalize`**: score the best candidate on TEST **exactly once** (the run
dir seals it), then **`report`** for a human-readable summary and the best
artifact.

## The rules (enforced by cap_evolve, restated here for bare hosts)
- Train/val/test are split once with a seed; **test is scored only at finalize**.
- Acceptance is gated on **val**, never on the data the optimizer edited against.
- Multi-trial scoring reports mean + stderr; pass^k is reported when trials > 1.
- Rejected approaches are remembered and never re-proposed.

## One-command alternative
If you'd rather not drive it turn-by-turn:
```
./install.sh && pip install ./core && cap-evolve run --spec .capevolve/project/capevolve.yaml
```
(Run intake first to create `capevolve.yaml`.)
