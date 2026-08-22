# Optimize the capability — MODIFY the single `airline_skill`

{{TARGET_READER}}

{{FOCUS_SUMMARY}}

{{EMPTY_SEED}}

## What you are editing (read this before anything else)

You are optimizing a **skill-package** capability. There is exactly **ONE** skill:
`./airline_skill/`. You modify it **IN PLACE**. Do not create sibling skills — a
second skill directory will not be deployed.

```
seed_capability/
├── airline_skill/            ← THE skill. Edit everything in here.
│   ├── SKILL.md              ← prompt enrichment SPA injects (editable)
│   └── scripts/              ← THE EXACT TOOL SET sent to the LLM (editable)
│       ├── book_reservation_wrapper.py
│       ├── cancel_reservation_wrapper.py
│       └── ... (14 baseline wrappers)
└── primitive_tools/          ← READ-ONLY reference. NEVER edit or import from.
    └── functions.py            The 14 frozen primitives, already in the store.
```

**You MAY:**
- Edit `airline_skill/SKILL.md` (prose / prompt enrichment)
- Edit any existing `*_wrapper.py` in `scripts/` (add guards, checks, logic)
- **Add** a new `.py` file to `scripts/` (a composite tool over 1+ primitives)
- **Remove** a `.py` file from `scripts/` (e.g. drop `list_all_airports_wrapper.py`
  if the agent never needs it and its presence causes misuse)

**You MUST NOT:**
- Edit anything under `./primitive_tools/` — it is frozen reference only
- Create a new skill directory next to `airline_skill/`
- Rename the skill (`airline_skill` is fixed; the `name:` in SKILL.md frontmatter
  must stay `airline_skill`)

**What gets evaluated:** `adapter.apply()` deletes `airline_skill` from the store,
re-imports your modified `airline_skill/`, and restarts SPA with
`SKILL_NAME=airline_skill`. The agent then sees your SKILL.md as system prompt
enrichment plus every public function in `scripts/` as a callable tool.

## SCRIPTS/ = THE EXACT TOOL SET SENT TO THE LLM

**CRITICAL:** `scripts/` defines the COMPLETE set of tools the Skillberry Agent
sends to the LLM. Each `.py` file's single top-level public function becomes one
callable tool. The LLM sees ONLY what is in `scripts/` — nothing more, nothing less.

So `scripts/` must always hold: **the baseline wrappers you keep** + **any new
composite tools you add**. If you delete a file, that tool disappears from the
agent's tool set. If you rename a function, the old tool name is gone.

### THE TWO HARD RULES for any tool you write

**Rule 1 — Call primitives BY NAME. Never call `_make_api_call`.**

Each baseline wrapper delegates to its equivalent primitive:

```python
def cancel_reservation_wrapper(reservation_id: str):
    """..."""
    return cancel_reservation(reservation_id=reservation_id)
```

The 14 primitives are already registered in the store. Call them by bare name —
`cancel_reservation(...)`, `get_user_details(...)`, `get_reservation_details(...)`
— and the store resolves the dependency automatically. You do not import
anything, declare anything, or pass a `tool_name`.

`_make_api_call` is **infrastructure used only inside the primitives themselves**.
Never call it from a tool in this skill; it will resolve the wrong tool name.

The 14 frozen primitives available to call:
`book_reservation`, `calculate`, `cancel_reservation`, `get_reservation_details`,
`get_user_details`, `list_all_airports`, `search_direct_flight`,
`search_onestop_flight`, `send_certificate`, `update_reservation_baggages`,
`update_reservation_flights`, `update_reservation_passengers`,
`get_flight_status`, `transfer_to_human_agents`.

**Rule 2 — Helpers are NESTED and `_`-prefixed.**

Any helper logic you add must be a function defined **inside** the tool's body,
with a name starting with `_`. A module-level helper would be picked up as its own
tool and shown to the LLM.

```python
def cancel_reservation_wrapper(reservation_id: str, user_id: str):
    """Cancel a reservation after verifying eligibility.

    Args:
        reservation_id (str): The reservation ID, such as 'ZFA04Y'.
        user_id (str): The user ID that must own the reservation.

    Returns:
        The cancellation result, or an error explaining why it was denied.
    """
    def _owns(res_id, uid):                       # nested + underscore = private
        user = get_user_details(user_id=uid)
        return res_id in (user.get("reservations") or [])

    if not _owns(reservation_id, user_id):
        return {"error": f"Reservation {reservation_id} does not belong to {user_id}"}
    return cancel_reservation(reservation_id=reservation_id)
```

### File and docstring requirements

Every file in `scripts/` must have **exactly one** top-level public function, and
its name must match the filename (`foo_tool.py` → `def foo_tool(...)`). Write a
Google-style docstring — the store parses it into the tool schema the LLM sees:

```python
def my_tool(reservation_id: str, count: int):
    """One-line summary of what the tool does.

    Args:
        reservation_id (str): What it is, with an example value.
        count (int): What it is.

    Returns:
        What the caller gets back.
    """
```

Annotate every parameter (`str`, `int`, `bool`, ...). A parameter missing from the
`Args:` block gets a useless auto-description, and a missing annotation degrades
its type in the schema.

### Pattern 1: GUARD an existing wrapper

Use when the agent misuses a tool (wrong args, skips a check, violates policy).
Edit the wrapper in place: add a nested `_`-helper that checks the failing
condition, return an error when it fires, and delegate normally otherwise.

The agent sees ONLY the wrapper — it cannot bypass the guard.

### Pattern 2: ADD an aggregation tool

Use when the agent needs a multi-step operation it does wrong or not at all.
Create a new file in `scripts/` whose function calls several primitives:

```python
# get_all_reservation_details.py
def get_all_reservation_details(user_id: str):
    """Get details for ALL reservations belonging to a user.

    Args:
        user_id (str): The user ID, such as 'sara_doe_496'.

    Returns:
        A list of reservation detail objects for every reservation the user holds.
    """
    user = get_user_details(user_id=user_id)
    return [
        get_reservation_details(reservation_id=rid)
        for rid in (user.get("reservations") or [])
    ]
```

### Pattern 3: REMOVE a tool

Use when a tool is unnecessary and its presence causes the agent to misfire (e.g.
it calls `list_all_airports_wrapper` on every turn and wastes steps, or it
escalates via `transfer_to_human_agents_wrapper` when it could have solved the
task). Delete the file. Be careful: this is UNBOUNDED — it changes the agent's
options on every task, including passing ones.

## GOAL

Raise the eval score as much as you can THIS iteration by modifying
`airline_skill`, then STOP (the harness re-scores you — don't run evaluation
yourself).

Diagnose EVERY failure cluster in `./trajectories/` and change the skill to fix as
many as possible. The more distinct failing clusters you address, the larger the gain.

The ONLY brake is regression: every change must pass the three tests below. A
single speculative change that breaks a passing task can sink the whole candidate.

## The THREE TESTS every change must pass
Before you keep any decision, confirm all three:
1. **REAL** — it targets a cluster that is FAILING in THIS iteration's
   `./trajectories/` (reward 0, partial-credit, or communication/omission). Never
   design for a hypothetical problem.
2. **SAFE (bounded blast radius)** — would this change what the agent DOES on ANY
   currently-passing task? A guard added to a wrapper is BOUNDED if it only fires
   on the failing condition and delegates normally otherwise. Deleting a tool or
   adding a broad prompt rule is UNBOUNDED — avoid unless the evidence is strong.
3. **VERIFIED** — you have shown it actually fixes its target (see VERIFY-THE-FIX).

## Read these first (everything is in this working directory)
- **`./guidance/<cap>/SKILL.md` for EACH selected capability — READ IT IN FULL.**
- `./guidance/diagnose/SKILL.md` — the failure-clustering method. Use it.
- `./trajectories/` — the FULL traces of the current best candidate. The
  `{{FAILURES}}` block below summarizes them — read the actual traces for clusters.
- `./airline_skill/` — the skill AS IT CURRENTLY STANDS (this is your starting
  point, and it already contains any changes accepted in prior iterations).
- `./primitive_tools/functions.py` — READ-ONLY reference for the exact primitive
  signatures, parameter names and return shapes you must call correctly.
- `./LEDGER.md` — FACTS (read-only): every prior iteration's outcome + exact tasks
  it broke/fixed. Never re-introduce a change that broke a task.
- `./JOURNAL.md` — the accumulating handover. Read all RESULT lines before
  proposing. APPEND your new entry below the marker; never edit earlier entries.
- `./RUNMAP.md` + `./prior_iterations/<id>/` — prior iteration PROCESS + diffs.
- `./PROCESS.md` — your REQUIRED explainability file for THIS iteration.
- `./guidance/optimizer/<name>.md` — your agent's subagent/parallelism features.
{{BENCH_REPO}}

## Process (do this, then STOP)
**Parallelism:** {{PARALLEL_NOTE}}
1. Read `./primitive_tools/functions.py` (signatures, behavior), the current
   `./airline_skill/`, capability SKILL(s), diagnose method, and cross-iteration
   files (LEDGER, JOURNAL, RUNMAP).
2. Diagnose THIS iteration's `./trajectories/` ONLY. Cluster ALL failures by shared
   root cause. RANK by LEVERAGE = (# failing tasks × trials × score recoverable).
3. Decide your changes to `airline_skill/`:
   - Rule violations / misuse → **Pattern 1**: guard the wrapper in code
   - Missing multi-step capability → **Pattern 2**: add an aggregation tool
   - Knowledge gaps (format, criterion, fact) → add it to SKILL.md prose
   - A tool that actively causes misfires → **Pattern 3**: remove it (cautiously)
4. Run each change through the THREE TESTS; drop any that fails.
5. Apply the changes to `./airline_skill/`.
6. Fill `PROCESS.md` and APPEND your entry to `JOURNAL.md`. STOP.

## VERIFY-THE-FIX
- **Guard added to a wrapper:** mentally trace the tool body on the EXACT args from
  the failing trace — confirm it fires and returns correctly. Then trace it on args
  from 1–2 PASSING tasks — confirm it does NOT fire (bounded).
- **New aggregation tool:** construct the inputs the agent SHOULD pass (from the
  trace's observed state) and confirm the body completes the action end-to-end.
- **Removed tool:** search the PASSING traces for calls to it. If any passing task
  used it, do not remove it.
- **SKILL.md prose:** confirm the missing fact is stated, general, and unambiguous.

Record one line per change in PROCESS.md.

## NON-OVERFITTING
Every change encodes a GENERAL rule — NEVER a literal that special-cases one task
(its id, target, name, or expected answer). A guard fires on the general condition,
NOT `if reservation_id == "SPECIFIC_ID"`. ALLOWED: constants the domain defines
(policy dates, fixed fees, domain enums).

## Handover (REQUIRED before you STOP)
- **PROCESS.md**: ranked clusters, every change + its pattern, VERIFY line per
  change, what you skipped and why.
- **JOURNAL.md** (append ONE entry): what you changed in the skill · expected effect
  + why safe · prior RESULTS you built on · refuted ideas you avoided · focus next iter.

{{FAILURES}}
{{PASSING}}
{{ALGO_BRIEF}}

## Self-check before STOP
- You did NOT edit anything under `./primitive_tools/`, and you did NOT create a
  sibling skill directory. All your work is inside `./airline_skill/`.
- `airline_skill/SKILL.md` still has valid frontmatter with `name: airline_skill`.
- Every file in `airline_skill/scripts/` has exactly ONE top-level public function,
  named identically to its filename, with a full Google-style docstring.
- Every helper you added is NESTED inside its tool and `_`-prefixed.
- Every tool calls primitives BY NAME. No tool calls `_make_api_call`.
- Every design choice passes the THREE TESTS (REAL, SAFE, VERIFIED) with a verify
  line in PROCESS.md.
- For rule-violation / behavioral clusters you changed tool CODE (enforcement), not
  just prose in SKILL.md.
- No change hardcodes a task-specific id/value/date/answer.
- PROCESS.md + JOURNAL.md are filled.
