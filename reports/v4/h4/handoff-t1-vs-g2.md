# Handoff: T1 vs G2 on the h4 held-out tasks, run in parallel on CCC

Written 2026-10-08 for whoever runs this next. It distils a three-arm debugging
session (e1, e2, e3) on the h4 suite, 2026-10-04 → 10-08. **Read sections 1-3
before launching anything** — they are the ones that otherwise cost you a run.

(The older `HANDOFF.md` in this worktree is the 2026-09-23 T4-merge handoff and
is still valid for that experiment. This file does not supersede it.)

**The goal**: compare the original PARSEC instructions ("T1") against the
optimizer's best candidate `cand_0004` ("G2") on an identical set of tasks.
Everything here exists to make that comparison mean something.

---

## 1. Three ways a bad trial looks like a real score

The single most important section. We lost and re-ran whole task sets before
finding all three, and two are invisible to the harness's own error accounting.

### 1a. Harness error — already handled

Reward comes back `null`, `errored_trials` increments, the harness drops it.
Nothing to do.

### 1b. The agent did not finish — scored 0.0, `errored_trials` stays 0

When the agent is cancelled or hits an API error, the trial **still writes
`reward.json`**. Every h4 task's verifier has a completion gate:

```python
# tests/verify.py
ok = event.get("subtype") == "success" and not event.get("is_error", False)
gate = 0.0 if (completion.get("status","ok") == "ok" and not ok) else 1.0
reward = gate * (w_tool * tool_score + w_answer * answer_score)
```

The gate zeroes the reward, so it appears as a legitimate **0.0**,
indistinguishable from a wrong answer — and the harness books the trial as
completed, so **`errored_trials` reads 0**.

Detect it from the agent's own final event:

```python
def final_event(trial_dir):          # last {"type":"result"} in agent/*.jsonl
    out = None
    for p in glob.glob(f"{trial_dir}/*/*/agent/*.jsonl"):
        for line in open(p, errors="replace"):
            ev = json.loads(line)
            if ev.get("type") == "result":
                out = ev
    return out

ev = final_event(td)
dead = ev is None or ev.get("subtype") != "success" or ev.get("is_error")
```

A dead trial has `subtype == "error_during_execution"` and a `result` like
`"CancelledError: agent timed out"` or `"RuntimeError: Claude API error: Request
timed out or interrupted"`.

**Do NOT grep transcripts for error strings.** A structured
`error_during_execution` contains no matching text, so a regex returns nothing
and the silence reads as proof the trial was sound. That exact mistake produced
a confidently wrong "capability regression" claim here.

Rates seen: e1 1/150, e2 1/150, e3 3/20 early, then **34/60** overnight on a
degraded gateway. Correcting e1/e2's single dead trial moved `platform-043`
from 0.800 to **1.000**, which then matched George exactly.

### 1c. The simulator errored or invented data — plausible partial credit

The nastiest. The trial completes, the agent behaves correctly, tool calls score
**1.0**, and the reward is a believable partial score. Two variants:

**Fabrication.** Same call, byte-identical seed, different arms:

```
e1  query_azure_pools(get_subscription, 'pool-01-999')
    -> {"error": "Subscription 'pool-01-999' not found"}            reward 1.00
e3  same call
    -> {"subscription_name":"pool-01-999","subscription_id":"sub-pool-01-999",
        "tenant_id":"72f988bf-...","status":"Succeeded"}            reward 0.65
```

The task is `cloud-055-azure-subscription-not-found`. The simulator invented a
full subscription for an entity absent from its own seed; the agent faithfully
reported it and lost the `subscription-not-found` assertion.

**Operation failure.** `lookup_catalog_item(search=...)` returning
`{"error": "Operation schema unavailable"}` on `platform-039` and
`platform-044`, while working on other tasks.

These failures hit **absence traps** — the tasks testing whether the agent
honestly reports something is missing. They are the most valuable tasks in the
suite, and this failure makes an honest agent look worse than a credulous one.

Detect by flagging trials that missed an absence assertion while scoring 1.0 on
tool calls:

```python
ABSENCE = re.compile(r"not[-_]?found|miss\b|missing|absent|no[-_]|unavailable|"
                     r"not[-_]?enriched|not[-_]?requested|empty", re.I)
# from verifier/reward-detail.json
missed = [m["id"] for m in (detail["answer"].get("required_missed") or [])]
suspect = any(ABSENCE.search(m) for m in missed) and reward["tool_calls"] == 1.0
```

Counts rose monotonically on **identical seed data** — e1: 2, e2: 8, e3: 11 —
which is a simulator change, not an agent change. Also scan for
`"Operation schema unavailable"` and `"is not defined in parsec-"`.

Working implementations live on the **main** branch at
`scripts/parsec/h4_t1_e3/`: `audit_trials.py`, `audit_absence_traps.py`, and
the filter inside `compare_arms.py`. They are not on this branch, because
anything that imports cap-evolve has to live where cap-evolve lives (see §3).

---

## 2. Parallel execution on CCC — read before distributing

You plan one task per dedicated machine. Two things make that non-trivial.

### 2a. Each parallel worker needs its OWN simulator stack

The five harness services are **shared mutable state**. Seeding is
`PUT /api/v1/simulation/database`, which "replaces db.json and resets the
simulation" — the whole dataset, per trial. Two tasks running against the same
stack will overwrite each other's fixtures mid-flight and both sets of results
will be silently wrong.

That is why the serial driver holds a lock:

```python
LOCK_NAME = "v4_t2_e1.lock"   # protects the shared live stack, not the arm
```

So: **per machine, bring up its own 5 harness services + its own parsec-live**,
with its own ports and its own `_run` tree. Do not point N machines at one
stack. If machines must share a stack, they must share the lock too, and you
lose the parallelism.

Per-trial seeding is still required even when isolated — the `PUT` reset is what
makes a task's five trials independent samples rather than a chain inheriting
each other's mutations.

Conversely, the **simulator-quiescence gate** (§4) matters less when isolated:
the 409-on-seed race came from one task's abandoned tool call outliving it and
colliding with the *next* task's seeding on a shared stack. With one task per
machine that cross-task collision disappears, though trial-to-trial collisions
within a task remain, so keep the gate.

### 2b. Parallelism may self-inflict the gateway failure we spent days diagnosing

All simulators across all machines hit **one** shared gateway:
`ete-litellm.ai-models.vpc-int.res.ibm.com`. We measured it going bimodal —
either sub-2s or hanging past 60s — with a ~50% hang rate at worst, which
produced 34 dead trials out of 60 overnight. Each trial makes ~8-10 simulator
calls and each simulator call is itself ~2-3 LLM calls, so **30 parallel tasks
is on the order of 30× the request rate we were already seeing fail.**

Recommendation:

1. **Ramp, don't jump.** Start with 4-6 parallel tasks. Measure per-call latency
   and the §1b dead-trial rate. Scale only while both stay flat.
2. **Probe the gateway from a machine before and during the run.** One minimal
   request (`max_tokens: 5`, no data) is enough; see §4.
3. **Treat a rising dead-trial rate as a saturation signal**, not as a result.
   If it climbs as you add workers, you are the cause.
4. Budget: a 429 `"Budget has been exceeded!"` already killed one v4 trial.
   Parallelism multiplies spend rate as well as request rate.

If the gateway cannot take the concurrency, the fallback that still helps is
modest parallelism (say 4-8) rather than 30 — the serial run took roughly a day,
so even 6× is a large win.

---

## 3. Which harness and which task drop

### The simulators have always used the v4 harness

`_run/harness-cfg/<service>.yaml` sets:

```yaml
skills:
  folder: /Users/boazc/workarea/Python/rhdp-parsec/v4_2026-09-16/_run/skills
```

Services load that at **process start** and never reload (ours had been up since
2026-09-16). So **e1, e2 and e3 all ran on the v4 harness skills** — George's
`h4_*/harness-skills` was never used by our simulators. The plan to "run h4
tasks on the v4 harness" is therefore already what we did; e1/e2/e3 *are* that
experiment.

Measured with `diff -rq`:

| comparison | result |
|---|---|
| `v4_2026-09-16/_run/skills` vs `h4_2026_10_04/harness-skills` | only `parsec-platform/db.json` differs |
| `v4_2026-09-16/_run/skills` vs `h4_2026_10_06/harness-skills` | only `parsec-platform/db.json` differs |
| all five `SKILL.md` | **byte-identical** |

So the `SKILL.md` difference remembered between "v4" and "h4" is **not** between
these paths. If a different pair was meant — JB's original v4 bundle, or an
older checkout — re-run that diff and record which paths were compared before
building on it. George's runner uses
`--skills-dir ../bench-v4-challenge/harness-skills`, so his runs and ours differ
in `parsec-platform/db.json` and nothing else in the skills.

### Oct-04 vs Oct-06 differ in more than seeds

Beyond seed coverage (2.9 KB / 4 records per task → 56.3 KB / 137.6), the
task.toml changed **which MCP servers the agent can reach**:

```
platform-039, Oct-04:  services = ["github"]                        # one server
platform-039, Oct-06:  services = ["platform","github","icinga","cost","cloud"]
                       scenario_services = ["github"]
```

Observed consequence on that task:

```
e1 (Oct-04)  lookup_catalog_item -> {"error":"No catalog item found for 'turbo-widget'"}
e2 (Oct-04)  lookup_catalog_item -> {"error":"Operation lookup_catalog_item is not
                                     defined in parsec-github 2.0.0"}
e3 (Oct-06)  lookup_catalog_item -> {"error":"Operation schema unavailable"}
```

In e1/e2 the agent had **only the github server**, so a platform operation could
not resolve. In e1 the github simulator *improvised* a plausible "not found",
accidentally satisfying the `catalog-miss` assertion → **0.650**. In e2 it
correctly reported the operation undefined → **0.475**. So **e1's higher score
there was the artifact**, not e2's lower one.

**Recommendation — a judgement call, stated with reasons:**

- **Prefer the Oct-06 drop.** It declares all five servers, so an off-path tool
  call reaches a service that implements the operation rather than one that
  improvises. Oct-04 lets the agent call operations no available server
  implements, and what comes back is an LLM's invention — which demonstrably
  inflated at least one task's score.
- Oct-06's cost is the `lookup_catalog_item(search=...)` schema failure on
  `platform-039` and `platform-044`. Exclude those two from aggregates, or fix
  the failure first.
- **Whichever you choose, run BOTH arms on the same drop.** This matters far
  more than the choice itself: e1-vs-e3 showed task-level swings of ±0.5 from
  the drop alone. Mixing drops across arms makes the comparison meaningless.

---

## 4. Operational setup

### Both branches are needed to run

Code and artifacts are split by whether they import cap-evolve:

| what | branch | why |
|---|---|---|
| cap-evolve core, adapter, arm driver, detectors | **main** | imports `cap_evolve` / `capevolve_harbor`, and runs `skills/phases/baseline/scripts/run.py` |
| prompt bundles, results, report builders | **parsec-history** | pure data and JSON-reading scripts; this branch is an orphan with no cap-evolve packages at all |

The two bundles are the **existing v4 artifacts**, not h4-specific copies —
verified byte-identical, all 8 files each:

| arm | bundle |
|---|---|
| T1 (original instructions) | `artifacts/v4/seed/` |
| G2 (`cand_0004`) | `artifacts/v4/v4_g_e1/best/` |

Pointing at them directly rather than duplicating is deliberate: a second copy
would let the h4 arms silently drift from their v4 provenance, and "the same
bundle as v4" is the whole basis for comparing the two experiments.

So check out both (`git worktree add` twice from the same repo — no rebase, and
never rebase this orphan branch onto main or you merge cap-evolve's whole tree
into it), and point the driver at the arm you want:

```bash
export PARSEC_H4_BUNDLE=.../parsec-history/artifacts/v4/seed          # T1
# or:  .../parsec-history/artifacts/v4/v4_g_e1/best                     # G2
export PARSEC_V4N=.../rhdp-parsec/v4_2026-09-16              # task fixtures
```

`PARSEC_H4_BUNDLE` has **no default on purpose**: which arm's prompts get
installed is the independent variable of the whole experiment, so an unset
value stops the run rather than picking one. **This is the T1-vs-G2 switch** —
set it wrong and both arms measure the same bundle.

### Models — verify, don't assume

| role | model | where |
|---|---|---|
| optimizer | `claude-opus-5` | `capevolve.yaml` → `optimizer_model` |
| agent under test | `claude-sonnet-4-6` | `capevolve.yaml` → `target_model` |
| simulators (×5) | `azure/gpt-5.4`, `temperature: 0` | `_run/harness-cfg/<svc>.yaml` |

Every simulator process **must** launch with its own `HARNESS_CONFIG_PATH`.
Without it the harness silently falls back to its packaged default (`gpt-4.1`)
with a healthy `/health` and no error. Check per machine:

```bash
ps eww -p <pid> | tr ' ' '\n' | grep HARNESS_CONFIG_PATH
```

As of 2026-10-07 `azure/gpt-4.1` returns **HTTP 403** on this gateway, so a
misconfigured simulator now fails loudly — but verify anyway. This is doubly
important when bringing up N stacks: one machine misconfigured means one arm's
subset silently used a different simulator model.

**The agent's temperature is not set** anywhere in PARSEC — no `temperature` key
in its config or source, so the API default applies. Setting it to 0 would mean
patching four `messages.create` sites in `src/agent/orchestrator.py` and
`src/agent/agents.py`. We deliberately did **not**: T1 and G2 were both measured
without it, and patching breaks comparability with George. Leave it unless you
re-baseline both arms.

### The gateway is the dominant risk

Minimal-request latency (one short message, `max_tokens: 5`, no data):

| when | result |
|---|---|
| Oct-04 (inferred from full sim calls) | ~1.8s |
| Oct-06 | 6.2 / 17.6 / 8.9s — mean 10.9s |
| Oct-07 am | **3 of 6 never returned**; the rest 0.7-2.0s |
| Oct-07 pm | 1.8 / 0.7s — normal |

**Bimodal and unstable, not uniformly slow** — the fast floor never moved.

- **Probe before launching.** One request costs nothing and tells you whether
  you are about to waste hours.
- **Never compare wall-clock, per-call latency or cost across days.** Only
  rewards are comparable.
- A long investigation here wrongly blamed a 2.3× slowdown on the Oct-06 seed
  payload. It was the gateway. One direct probe settled what hours of
  correlation could not — **probe first**.

Model comparison on the same gateway, if you are tempted to switch:

| model | mean | note |
|---|--:|---|
| `azure/gpt-5.4` | 6.36s | **fastest available** |
| `azure/gpt-4.1` | — | HTTP 403 |
| `claude-sonnet-4-6` | 16.27s | |
| `claude-opus-4-6` | 16.13s | 2.5× slower than gpt-5.4 |

Switching the simulator model would also break comparability with e1/e2 and
with George. Keep `gpt-5.4`.

### Timeouts

Tasks declare `[agent] timeout_sec = 600.0`. At degraded gateway latency a 10-18
call task exceeds it and the agent is cancelled → a false 0.0 (§1b). We raised:

```python
AGENT_TIMEOUT_MULTIPLIER = 2.5     # harbor's --agent-timeout-multiplier
TRIAL_TIMEOUT_SEC = 40 * 60        # the adapter's own subprocess cap
```

Both were needed: the multiplier raises Harbor's ceiling; the adapter cap must
stay well above it or it preempts the thing it is meant to contain. **Watch for
nested timeouts** — a 120s drain budget inside `install_seeds.py` once equalled
the adapter's 120s cap on that same subprocess, so the retry could never
finish. Revert to `20 * 60` / `1.0` if the gateway is healthy: a raised timeout
makes a *failing* trial cost 2.5× more, and it did not rescue `062`, which
thrashes on an unmodelled tool (~2.2-2.6 rejected `query_provisions_db` calls
per trial in **every** arm).

### Seeding and the 409 race

A `PUT` is refused with **409** while a service has a tool call in flight. A
trial ends when the *agent* stops, which does not wait for the simulators, so an
abandoned call outlives its trial. Wait for quiescence before seeding, and put
the wait **outside** any subprocess timeout:

```python
# poll all five /api/v1/simulation for session_state.queue_depth == 0
# budget ~300s; treat an unreadable service as busy, never as idle
```

e1/e2 never hit this because they seeded only each task's declared services
(1-3 of 5), and the service the current agent used is quiet by construction.
Seeding all five exposes it.

Also: point `install_seeds.py`'s `SKILLS_DIR` at the **active** drop. It was
found still defaulting to a superseded one.

---

## 5. How to read the results

### Report per-trial vectors, never bare means

Three shapes occur, and the mean is meaningful for only one:

| shape | example | reading |
|---|---|---|
| stable | `icinga-049` `[0.62 0.62 0.62]` | the mean **is** the result |
| stable + outlier | `icinga-046` `[0.70 ×4, 0.12]` | mean understates; mode is right |
| bimodal | `platform-036` `[0.15 ×4, 1.00]` | **the mean describes nothing real** |

Differencing means across arms on a bimodal task manufactures findings. `062`'s
"0.790 → 0.720 → 0.607" is two high draws, then one, then none, on a task whose
modal value is 0.65 in every arm and matches George exactly. `platform-036`
succeeds about 1 in 5 — report it as a success rate.

Of the differences initially attributed to the Oct-06 drop, **one was real, two
were measurement artifacts, and the rest was sampling noise.** Per-trial vectors
are what made that separable.

**`n=5` is not enough** for any task whose vector spans more than two values.
`cloud-059` spans 0.35-1.00; nothing can be concluded about it at that sample
size. Give a headline task 20+ trials. Parallel capacity is best spent here.

### Stability is not validity

`platform-039` returned `[0.47 ×5]` — zero variance — and was called "the most
informative kind of result" before all five trials turned out to be the same
broken catalog operation. **Five identical trials can be five identical
infrastructure failures.** Run the §1 detectors before interpreting a stable
value.

### The noise floor

e1 and e2 are the **same bundle on the same tasks** — a deliberate repeat.
Aggregate difference +0.007; mean |Δ| **0.056 per task**; 20/30 tasks moved. Any
claimed T1-vs-G2 effect must clear 0.056 per task.

Caveat: e2 looks slightly noisier than e1 or e3 (it is the odd arm on
`icinga-047`, `cloud-058`, `cloud-060`, `platform-039`), so 0.056 may be
somewhat inflated. Recomputing the floor from e1↔e3 is reasonable.

### Match the statistic when comparing to George

Our mean-of-5 vs his best-of-1 is not a like comparison. A ~0.09 "gap" dissolved
once matched: our mean-of-max 0.756 vs his 0.727. **State the statistic
explicitly** in any table placing the two side by side.

### Known T1 baseline — use it as a sanity check

Full per-trial table for all three arms: `all-arms-per-trial.md`, beside this file.

| arm | 30-task mean |
|---|--:|
| George | 0.8150 |
| e1 (T1, Oct-04) | 0.6799 |
| e2 (T1, Oct-04, repeat) | 0.6870 |
| e3 (T1, Oct-06) | 0.6735 |

**Control group — perfect in all arms and matching George**: `platform-035`,
`platform-038`, `platform-041`, `platform-043`, `cloud-056`. If a new run breaks
one of these, you have a setup problem, not a result.

**Where T1's gap to George actually is** — not a uniform deficit; T1 matches or
beats him on 12 of 30:

| task | T1 (e1/e3) | George | note |
|---|--:|--:|---|
| `platform-036` | 0.15 modal | 1.000 | bimodal ~1-in-5; largest gap |
| `icinga-048` | 0.500 stable | 1.000 | **cause known**: fails to discriminate two comments by `service_name` |
| `icinga-047` | 0.550 (e1≡e3) | 1.000 | e2's `[0.81 ×5]` is a value absent from both neighbours |
| `icinga-049` | 0.617 stable | 0.850 | stable |
| `cost-053` | 0.825 | 1.000 | |

**The stable tasks are the best optimization targets** — a deterministic 0.500
gives a clean signal; a bimodal task's gains vanish into variance. If G2 is
expected to help anywhere, it is here.

The one thing e3 established: **`icinga-045` `[0.47 ×5]` → `[1.00 ×5]`**,
matching George, because Oct-06 seeds the icinga service for every task and
Oct-04 did not. This also explains an earlier unexplained icinga mystery — the
agent had been searching a database that did not contain the host.

---

## 6. Pre-launch checklist

1. Probe the gateway. Abort if requests are hanging.
2. Per machine: all five simulators have `HARNESS_CONFIG_PATH`, yaml says
   `azure/gpt-5.4`, `temperature: 0`.
3. Per machine: its **own** stack, own ports, own `_run` tree. Never two tasks
   against one stack (§2a).
4. `diff -rq` the task directory the adapter reads against the drop you intend.
   Ours was silently overwritten from Oct-04 to Oct-06 between arms — do not
   trust the path name.
5. `install_seeds.py` `SKILLS_DIR` → the active drop.
6. **Both arms on the same drop and same harness.**
7. Ramp parallelism 4-6 → measure → scale (§2b).
8. Run the §1 detectors after **every task**, not at the end. Gate on §1b/§1c
   counts, never on `errored_trials`.
9. Top up rather than restart: an infra-killed trial yields no reward, so
   survivors stay valid and only the shortfall needs re-running. **Union clean
   trials across a task's run dirs** — reading only the newest run dir silently
   discards the trials you were topping up (this bug nearly cost us
   `icinga-045`'s result).
10. If any window was unattended, audit it before trusting the scores. Two
    overnight episodes cost full task sets.

---

## 7. Open questions

- **`lookup_catalog_item(search=...)` → `Operation schema unavailable`.**
  Deterministic per task (`platform-039` 5/5, `platform-044` 4/4), works
  elsewhere, identical argument shape. Mechanism unknown. Blocks two tasks on
  Oct-06.
- **Simulator fabrication.** Why a service invents a record for an absent key in
  some arms and correctly reports absence in others, on identical seeds. Highest
  value to fix: it inverts the absence-trap tasks.
- **`icinga-047` in e2**: `[0.81 ×5]`, a value appearing nowhere in e1 or e3
  (both 0.550). Unexplained.
- **G2 has never been audited** for any §1 failure mode, and `v4_g_e1` /
  `v4_g2_e1` raw rollouts are **not on the local machine** — `results.json`
  points at `/dccstor/...`. On CCC you may have access: **audit them before
  quoting G2 numbers.** The published G2 figures predate every detector in §1.
- **`h4_g2_e1` is incomplete** — 25 non-icinga tasks only. Since `icinga-045`
  turned out to be the single clearest effect in the whole suite, G2 needs the
  icinga tasks too.
- **The v4 arms are contaminated.** 12 dead trials reached published v4 numbers
  (11 in `v4_t2_e1`, 1 in `v4_t4_e1`); `v4_t4_e2` is clean across 179 trials.
  `icinga-013`'s `cand_0002` has **no valid measurement at all** (5/5 dead) yet
  is published as 0.0000, and `platform-004`'s `cand_0001` is published as
  0.4000 when both its surviving trials scored **1.000** — a candidate discarded
  on a gateway outage. Detail:
  `reports/v4-cap-evolve-question-answers.md`, on this branch.
