# What the optimizer actually changed — verified in the trajectories

These are **real edits** from the committed tau2-bench airline run
([`examples/tau2_airline/run_full/`](../examples/tau2_airline/run_full/)), each
paired with the **trajectory evidence** that it helped: the agent's behavior on a
*failing* rollout (the seed or the parent candidate) versus the *passing* rollout
under the champion `cand_0007`. Rollouts live at
`<run_dir>/rollouts/val/<task_id>__<tag>__t<k>.json` (full message transcript +
`reward_info`); every example below was read directly from those files.

The throughline: **argument-level feedback from failing rollouts is converted into
executable guards inside the existing tools** — code where the agent already "knew"
the rule but skipped it, prose only for genuine knowledge gaps. Across the run
`tools.py` grew **593 → 832 lines** and `policy.md` **166 → 233 lines**; most of the
lift is real code, and the edits span several distinct *types* (the optimizer is told
to read each capability skill's menu of change types and apply several per iteration).

---

## 1. In-body code guard — reject bookings with >1 travel certificate
**Edit type:** in-body code guard with a recoverable, actionable error
**File:** `tools/tools.py` → `book_reservation` (added in `cand_0006`)

The airline policy allows at most **one** travel certificate per reservation, but the
seed tool accepted any number silently.

```python
cert_count = sum(1 for pm in payment_methods
    if user.payment_methods.get(pm.payment_id)
    and user.payment_methods[pm.payment_id].source == "certificate")
if cert_count > 1:
    raise ValueError(
        f"At most 1 travel certificate allowed per reservation, but {cert_count} "
        f"were provided: {cert_ids}. Pick the single best certificate and use "
        f"credit card or gift card for the remainder.")
```

**Trajectory evidence (task 14):** in `14__cand_0005__t0.json` the agent rebooks with
**three** certificates (`certificate_3765853`, `_9984806`, `_2765295`); the seed tool
accepts it and the final DB state is wrong (reward 0 — *"Database state does NOT
match… Action-level defects… book_reservation"*). In `14__cand_0006__t0.json` the
identical 3-cert call is **rejected by the guard**, the agent reads the error, replies
*"Only one travel certificate can be applied,"* and rebooks with one certificate + a
card (reward 1). Task went 1/10 → 6/10 the iteration the guard landed.

Why it generalizes: the guard fires on the **count of certificate-sourced payment
methods**, never on a specific id — and its error message tells the agent exactly how
to recover, so the model self-corrects instead of stalling.

---

## 2. New validation parameter + guard — never exceed a stated spending cap
**Edit type:** validation (new optional parameter + in-body guard), paired with a policy rule
**File:** `tools/tools.py` → `update_reservation_flights` (added in `cand_0007`)

```python
max_charge: Optional[int] = None,          # new parameter
...
if max_charge is not None and total_price > max_charge:
    raise ValueError(
        f"Update rejected: total charge would be ${total_price} which exceeds "
        f"the authorized maximum of ${max_charge}…")
```
> policy.md: "Always pass `max_charge` to `update_reservation_flights` when the user
> stated a spending cap… the tool will reject the update if the actual charge exceeds
> it — this is your safety net."

**Trajectory evidence (task 10):** in `10__cand_0006__t2.json` the user says the extra
cost "needs to be under $1,000"; the agent fabricates a "$495" flight combination and
calls `update_reservation_flights` anyway, writing a state that doesn't match gold
(reward 0). In the `cand_0007` traces the agent's reasoning explicitly carries
`max_charge = 1000`, so the over-budget write is either rejected by the guard or
declined — task went 3/10 → 9/10. The cap is enforced **in code**, not left to the
model's arithmetic.

---

## 3. New loop/read tool — enumerate ALL reservations before deciding
**Edit type:** new read tool (collapses an error-prone N-call sequence)
**File:** `tools/tools.py` → `get_all_reservation_details` (added in `cand_0003`)

```python
@is_tool(ToolType.READ)
def get_all_reservation_details(self, user_id: str) -> list:
    """Get the details of ALL reservations for a user in one call. Use this instead
    of calling get_reservation_details multiple times when you need to find the right
    reservation by route, date, or other criteria…"""
    user = self._get_user(user_id)
    return [self._get_reservation(r) for r in user.reservations]
```

**Trajectory evidence (tasks 1, 2):** under the seed, the agent fetched reservations
one at a time and frequently **stopped after the first**, matching the wrong one. All
ten `1__cand_0003__t*.json` traces call `get_all_reservation_details(user_id)` to
enumerate every reservation before acting, and all ten pass (10/10; task 2 went 8/10 →
10/10). Giving the agent a single correct action removed the "incomplete enumeration"
failure mode entirely.

---

## 4. Prompt knowledge-rule — don't ask the user for data you can look up
**Edit type:** prompt knowledge-rule (+ a matching tool docstring)
**File:** `policy/policy.md` + `tools/tools.py` docstring for `update_reservation_passengers` (from `cand_0001`, sharpened in `cand_0003`)

> policy.md: "Do NOT demand information from the user that you can look up (e.g. DOB
> for passenger name changes — get it from `get_reservation_details`)."

**Trajectory evidence (task 40):** in `40__seed__t0.json` the agent insists *"I'll need
Mei's date of birth,"* the user refuses, and the agent calls `transfer_to_human_agents`
and gives up (seed scored this task 0/10). In `40__cand_0007__t0.json` the agent instead
calls `get_reservation_details(3RK2T9)`, reads the existing DOB (`1989-12-13`) from the
returned passenger list, and completes `update_reservation_passengers` without ever
asking the user (reward 1). Task went 0/10 → 5/10 → 10/10. This is a true **knowledge
gap** — the agent didn't know the data was already available — so prose is the right
lever (not code).

---

## 5. Prompt output-contract rule — state the EXACT figure from the tool return
**Edit type:** prompt knowledge-rule (output contract)
**File:** `policy/policy.md` after-write reporting section (sharpened in `cand_0007`)

> "Look at the LAST entry in the returned `payment_history` array — its `amount` field
> is the authoritative charge (positive) or refund (negative). State that EXACT
> number… your arithmetic WILL be wrong when multiple segments and passengers are
> involved… Example: if `payment_history` last entry shows `amount: -5244`, tell the
> user 'Your refund is $5,244.'"

**Trajectory evidence (task 11):** in `11__cand_0006__t0.json` the agent performs the
cabin downgrade correctly but reports a **self-computed** "$1,244" refund; the scorer
flags *"1 required piece(s) of information were not clearly communicated"* and the agent
transfers to a human over the mismatch (reward 0). In `11__cand_0007__t0.json` the same
downgrade is done and the agent states *"a refund of $5,244 (the last entry in the
payment history)"* — the exact gold figure — and the user accepts (reward 1). Task went
2/10 → 10/10. The agent was *capable* but reported the wrong shape; the output-contract
rule fixes that class.

---

## How these compounded (and how rejects became signal)

The run climbed **0.536 → 0.712** (best candidate `cand_0007`, +0.176 ≈ +33%
relative), 5 of 10 iterations accepted, then a sealed-test finalize scored `cand_0007`
**once** at **0.694 pass@1** (pass^2 0.584). Crucially, the *rejected* iterations were
not wasted: each one's outcome is stamped objectively into `JOURNAL.md` (a framework
**RESULT** line with the exact tasks it broke/fixed), and the next iteration reads it.
After `cand_0002` was rejected, `cand_0003` recorded:

> "cand_0002 REJECTED (broke={13,34,43}): I re-introduced [the safe edits]… I did NOT
> re-introduce: cancel_reservation in-body guard or the 'ENFORCES' docstring change
> (caused regression on 13/34/43)."

— it kept the safe edits, dropped the one regressing edit, and logged it as refuted so
no later iteration repeated it. That is how the cross-iteration state turns even a
failed attempt into a lesson the run builds on.

> Open the full interactive dashboard for all of this offline — accepted/rejected
> lineage, per-task heatmap, and the **git diff** of every iteration:
> `cd examples/tau2_airline/run_full/ui && python3 -m http.server 8000`.
