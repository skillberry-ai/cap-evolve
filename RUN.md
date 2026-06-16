# RUN — drive the full AgentCapTune pipeline (point any agent here)

You are an AI agent asked to optimize an agent capability with **AgentCapTune**.
Follow these steps exactly. The skills you load do the real work; this file just
sequences them and enforces the non-negotiable rules.

## 0. Install (once)
```
./install.sh                     # copy skills into this host's skills dir
pip install ./core               # or: export AGENT_CAPO_CORE="$PWD/core"
```

## 1. Intake — collect inputs
Load the **`intake`** skill. It interviews the user, scaffolds `.agentcapo/project/`
(adapters + inputs + `acapo.yaml` + `PROJECT.md`), and gathers inputs.
> For every input the skill marks **NEEDED** that is missing, ASK THE USER —
> quote the expected path, the command/options to obtain it, and alternatives.
> Never fabricate a NEEDED input.

## 2. Implement & check — make the contract real
Load **`implement-and-check`**. Implement the 4 adapter methods in
`.agentcapo/project/adapters/adapter.py` (and any selected skill's `abstract.py`),
then run each skill's `check.py` and:
```
acapo check .agentcapo/project       # HARD GATE — must print {"ok": true}
```
**Do not proceed past this gate until it is green.** A half-wired project cannot
produce an honest number.

## 3. Baseline
Load **`baseline`**: score the unmodified capability on VAL to confirm there is
headroom. Records the starting point in the run dir.

## 4. Optimize
Load the algorithm skill named in `acapo.yaml` (e.g. **`all-at-once`**). It runs
the loop: select parent → propose edit (via your chosen **optimizer** skill) →
evaluate on VAL → **gate** (accept only if Δ exceeds the significance bar) →
snapshot or record-as-rejected → repeat until budget is spent. Diagnosis of
traces is provided by the **`diagnose`** skill, which the algorithm calls to turn
failures into an actionable learning signal.

## 5. Finalize & report
Load **`finalize`**: score the best candidate on TEST **exactly once** (the run
dir seals it), then **`report`** for a human-readable summary and the best
artifact.

## The rules (enforced by agent_capo, restated here for bare hosts)
- Train/val/test are split once with a seed; **test is scored only at finalize**.
- Acceptance is gated on **val**, never on the data the optimizer edited against.
- Multi-trial scoring reports mean + stderr; pass^k is reported when trials > 1.
- Rejected approaches are remembered and never re-proposed.

## One-command alternative
If you'd rather not drive it turn-by-turn:
```
./install.sh && pip install ./core && acapo run --spec .agentcapo/project/acapo.yaml
```
(Run intake first to create `acapo.yaml`.)
