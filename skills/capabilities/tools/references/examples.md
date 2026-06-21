# Examples — worked tool edits

Each example is an edit you would emit to `apply()`. Edit shape:
`{"tool": <name>, "kind": <action>, "value": <...>}`. For `add`/`compose` the
value is a full tool def; for `remove` the value is ignored.

**Ordered by leverage.** The DEFAULT, most common edit is §0 — editing the BODY of
an EXISTING tool to convert a violated prose rule into an in-body check. The other
PRIMARY edits are the code-bearing tools in §3b (workflow/loop) and §3c
(validation/rule-enforcement) — a deterministic body beats a prompt sentence. Reach
for the description/schema edits (§1, §2) *after* asking "can this rule be code in
the existing body instead?" A passthrough / reasoning-only tool (§7) is the
SECONDARY, last-resort form — prose in a tool's costume.

**First-class failure→fix patterns** (diagnose for these first): a wrong ARGUMENT the
tool could validate → resolve/validate against state, return `available=[...]`
(§3c-ter); a required eligible action abandoned via bail-out / transfer-to-human →
encapsulate the batch as a COMPOSITE WRITE (§3c-quater, §3e); a recoverable error that
strands the agent → an enriched RETURN that names what's wrong + the valid options +
the next action (§3f). Always VERIFY the fix fires on the exact failing-trace
arguments before shipping it.

## 0. Turning N prose rules into N in-body checks (the DEFAULT edit)

The most common high-leverage edit is NOT adding a tool — it is editing the BODIES
of EXISTING tools so a rule the agent keeps violating becomes code it cannot skip.
Most violated textual rules govern a tool that already exists, so expect to emit
SEVERAL `code` edits per iteration, one per violated rule. Each example below
edits an existing handler in place (no new tool, no `remove`).

**0a. Precondition guard — refuse when the rule is not met.** Prose rule: "only
cancel a record that is still cancellable." Edit the existing `cancel_record` body
to enforce it:

```json
{ "tool": "cancel_record", "kind": "code",
  "value": "def cancel_record(record_id):\n    rec = get_record(record_id)\n    if not rec.get('cancellable'):\n        raise ValueError(\"not cancellable; reason=\" + rec.get('status','unknown') + \"; offer a change_record instead\")\n    return _backend.cancel(record_id)" }
```

**0b. Unit / format normalization — coerce the field, then validate.** Prose rule:
"amounts are in whole US cents." Edit the existing `charge` body to normalize the
field so a dollars-vs-cents mistake can't corrupt the write:

```json
{ "tool": "charge", "kind": "code",
  "value": "def charge(record_id, amount):\n    amount = int(round(amount))\n    if amount <= 0:\n        raise ValueError(f\"amount must be a positive integer in whole US cents, got {amount!r}\")\n    return _backend.charge(record_id, amount)" }
```

**0c. Actionable error — name the valid options on refusal.** Prose rule: "the
payment method must already be on the record." Edit the existing `book` body to
check it and raise an error the model can recover from on the next turn:

```json
{ "tool": "book", "kind": "code",
  "value": "def book(record_id, payment_id):\n    methods = {m['id'] for m in get_record(record_id)['payment_methods']}\n    if payment_id not in methods:\n        raise ValueError(f\"payment method {payment_id!r} not on file; available={sorted(methods)} — pass one of these\")\n    return _backend.book(record_id, payment_id)" }
```

**0d. Required-order guard — enforce read-before-write in the body.** Prose rule:
"never update a record you have not fetched this turn." Edit the existing
`update_record` body so the read is part of the write and the staleness check is
guaranteed:

```json
{ "tool": "update_record", "kind": "code",
  "value": "def update_record(record_id, field, value):\n    rec = get_record(record_id)\n    if rec.get('locked'):\n        raise ValueError(f\"record {record_id} is locked (status={rec.get('status')}); unlock or escalate before updating\")\n    return _backend.update(record_id, field, value)" }
```

These four counterbalance the new-tool-heavy examples below: each takes ONE prose
rule and lands it as an in-body check on the tool that already owns it. A
docstring-only or new-tool-only iteration that leaves these rules as prose is
under-used.

## 1. Selection fix — sharpen a vague description

Trace symptom: agent calls a generic `query` tool for everything and fails on
order lookups.

```json
{ "tool": "query", "kind": "description",
  "value": "Look up a single order by its ID and return status, line items, and shipping. Use when the user references a specific order (an ID, 'my last order', or an order already in this thread). Do NOT use for free-text search across orders — use search_orders for that." }
```

Why it works: the description now states *what*, *when*, and *when not*, and
names the sibling tool to disambiguate (§1, §3 of concepts.md).

## 2. Argument-filling fix — close the value set with an enum

Trace symptom: agent sends `status="done"`, backend expects `"fulfilled"`.

```json
{ "tool": "search_orders", "kind": "schema",
  "value": { "type": "object",
    "properties": {
      "status": { "type": "string", "enum": ["pending","fulfilled","cancelled"],
                  "description": "Order status to filter by." },
      "since":  { "type": "string", "description": "ISO-8601 date, e.g. 2025-06-14." }
    },
    "required": ["status"] } }
```

Why it works: `enum` turns a guess into a pick; the `since` description pins the
exact format. (Requires `schema` to be allowed by policy.)

## 3. Collapse a fumbled chain — compose

Trace symptom: agent must `search_orders` then `get_order` on the first hit, and
often forgets the second call.

```json
{ "kind": "compose",
  "value": {
    "name": "find_order",
    "description": "Search orders by free text and return the FULL record of the best match. Use this instead of search_orders+get_order when you want exactly one order.",
    "parameters": { "type": "object", "properties": { "q": { "type": "string" } }, "required": ["q"] },
    "code": "def find_order(q):\n    hit = search_orders(q)[0]\n    return get_order(hit['id'])" } }
```

## 3b. Collapse repeated primitive calls — a loop-in-one-call tool

Trace symptom: the agent calls `get_record(id)` once per id (e.g. fetching every
record a user owns, one at a time), or calls `search(origin, dest, date)` once
per route/date combination — many calls, results sometimes dropped or
mis-threaded.

```json
{ "kind": "compose",
  "value": {
    "name": "get_records",
    "description": "Fetch the FULL details of EVERY record in `ids` in ONE call. Use this instead of calling get_record once per id when you have several ids (e.g. all of a user's records). Returns a list aligned with `ids`; an entry is {\"id\":..., \"error\":...} if that id is not found.",
    "parameters": { "type": "object", "properties": { "ids": { "type": "array", "items": { "type": "string" } } }, "required": ["ids"] },
    "code": "def get_records(ids):\n    out = []\n    for i in ids:\n        try:\n            out.append(get_record(i))\n        except Exception as e:\n            out.append({'id': i, 'error': str(e)})\n    return out" } }
```

Why it works: N fragile turns become 1 deterministic call; the loop and the
error handling live in code the model cannot get wrong.

## 3c. Validation / rule-enforcement tool — wrap, then delegate (then remove the primitive)

Trace symptom: a write that must be preceded by a read, or whose precondition the
backend does not itself enforce, keeps producing wrong-state failures (the agent
skips the check or mis-reads it). The rule is GENERAL (it always applies), so it
belongs in code, not in a prompt sentence the model can forget.

Emit two edits together: `compose` the safe wrapper, then `remove` the raw
primitive so the only reachable path is the validated one.

```json
[
  { "kind": "compose",
    "value": {
      "name": "cancel_record_safely",
      "description": "Cancel a record after verifying it is cancellable. Reads the record first and REFUSES (returns an error) if the cancellation preconditions are not met — so you never need to read the record yourself before cancelling. Use this for every cancellation.",
      "parameters": { "type": "object", "properties": { "record_id": { "type": "string" } }, "required": ["record_id"] },
      "code": "def cancel_record_safely(record_id):\n    rec = get_record(record_id)\n    if not rec.get('cancellable'):\n        return {'error': 'not cancellable', 'record': rec}\n    return cancel_record(record_id)" } },
  { "tool": "cancel_record", "kind": "remove" }
]
```

Why it works: the read-before-write order and the precondition are guaranteed in
code; a violation is a clean refusal, not a corrupted write. Removing the raw
`cancel_record` keeps the surface lean and makes the unsafe path unreachable —
the model cannot route around the check.

## 3c-bis. Validate-and-normalize inputs before a primitive

Trace symptom: the agent calls `charge_payment` with the amount in the wrong
unit, or against a method that isn't on file, and the raw primitive happily
errors mid-task. A wrapper normalizes the input, checks the precondition, then
delegates.

```json
{ "kind": "compose",
  "value": {
    "name": "charge_payment_safely",
    "description": "Charge `amount` (whole US cents) to `payment_id` after confirming the method is on the user's profile. Normalizes the amount and refuses (returns an error) if the method is not on file, so the charge never errors mid-task.",
    "parameters": { "type": "object", "properties": { "payment_id": { "type": "string" }, "amount": { "type": "integer" } }, "required": ["payment_id", "amount"] },
    "code": "def charge_payment_safely(payment_id, amount):\n    amount = int(round(amount))\n    methods = {m['id'] for m in get_user_details()['payment_methods']}\n    if payment_id not in methods:\n        return {'error': 'payment method not on file', 'available': sorted(methods)}\n    return charge_payment(payment_id=payment_id, amount=amount)" } }
```

Why it works: validate → normalize → enforce → delegate, all in code; the model
hands over an id and an amount and cannot mis-route the call.

## 3c-ter. Wrong ARGUMENT the tool could validate — resolve/validate against state, return `available=[...]`

Trace symptom (FIRST-CLASS): the agent calls a write with an id / reference / count
that is NOT consistent with the agent-visible state — an item id not in the record, a
quantity exceeding what's available, a reference to a resource that doesn't exist for
this entity. The right tool, the wrong argument. Never let the write proceed on an
unvalidated reference: wrap it in a body that RESOLVES/VALIDATES the argument against
the current state and, on mismatch, returns the valid options (`available=[...]`) or
raises an actionable error.

```json
{ "kind": "compose",
  "value": {
    "name": "remove_item_safely",
    "description": "Remove `item_id` from `record_id` after confirming the item is actually on the record. Validates the id against the record's current items and refuses (returning the valid options) if it is not present, so the write never corrupts state on a stale or wrong id.",
    "parameters": { "type": "object", "properties": { "record_id": { "type": "string" }, "item_id": { "type": "string" } }, "required": ["record_id", "item_id"] },
    "code": "def remove_item_safely(record_id, item_id):\n    items = {it['id'] for it in get_record(record_id)['items']}\n    if item_id not in items:\n        return {'error': f'item {item_id!r} not on record {record_id!r}', 'available': sorted(items), 'next': 'pass one of available'}\n    return remove_item(record_id, item_id)" } }
```

Why it works: the argument is resolved against the live state in code; a wrong/stale
reference becomes a clean refusal that NAMES the valid options, so the model corrects
on the next turn instead of corrupting the record. (Verify the fix: run this body on
the exact id from the failing trace and confirm it returns `available` rather than
calling through.)

## 3c-quater. A required, eligible action abandoned via bail-out / transfer-to-human — encapsulate the batch as a COMPOSITE WRITE

Trace symptom (FIRST-CLASS, behavioral): the agent calls `transfer_to_human` /
escalates / bails out instead of performing a REQUIRED action it was eligible to do
itself — often a batch of similar writes (cancel each eligible line, refund each
qualifying charge). This is a behavioral STALL, not a missing capability; a "don't
bail out" prose rule does not fix it. Encapsulate the eligible-action batch in ONE
composite WRITE tool whose body executes the steps in code, skipping ineligible items
with a recorded reason — then `remove` the raw primitives so the batch is the path.

```json
[
  { "kind": "compose",
    "value": {
      "name": "process_eligible_items",
      "description": "Process EVERY eligible item on `record_id` in one call: applies the action to each item that meets the precondition and SKIPS the rest with a reason, returning a per-item result. Use this instead of escalating or handing off when the items are processable — there is no separate per-item write tool.",
      "parameters": { "type": "object", "properties": { "record_id": { "type": "string" } }, "required": ["record_id"] },
      "code": "def process_eligible_items(record_id):\n    rec = get_record(record_id)\n    results = []\n    for it in rec['items']:\n        if not it.get('eligible'):\n            results.append({'id': it['id'], 'skipped': it.get('reason', 'ineligible')})\n            continue\n        results.append({'id': it['id'], 'result': process_item(record_id, it['id'])})\n    return {'record_id': record_id, 'processed': results}" } },
  { "tool": "process_item", "kind": "remove" }
]
```

Why it works: the whole eligible-action batch runs the moment the tool is called, so
the agent can no longer hand off a task it was equipped to finish; ineligible items
are skipped with a reason rather than blocking the batch. (Verify: run the body on the
record from the bail-out trace and confirm it processes the eligible items.)

## 3e. Make a STALLED action un-skippable — a composite WRITE tool (then remove the primitives)

Trace symptom (the most common behavioral failure): the agent analyzes a
multi-step change, explains the plan, sometimes even gets the user's
confirmation — and then **never issues the write calls and stops**, leaving the
task half-done. No prose rule ("be sure to apply the change", "always act after
confirming") reliably fixes this; it is behavioral, not a knowledge gap. The fix
is to encapsulate the WHOLE action as one tool whose body performs every step in
code, so the moment the agent calls it the action is complete and cannot be
skipped mid-conversation. Then `remove` the raw write primitives so the composite
is the only path.

```json
[
  { "kind": "compose",
    "value": {
      "name": "apply_change_plan",
      "description": "Apply an ENTIRE multi-step change to one record in a single call: validates every step, then performs them in order via the underlying writes, and returns the final record. Use this for any change of one or more steps instead of issuing the writes yourself — there is no separate per-step write tool.",
      "parameters": { "type": "object", "properties": {
          "record_id": { "type": "string" },
          "steps": { "type": "array", "items": { "type": "object",
              "properties": { "op": { "type": "string", "enum": ["add","remove","update"] },
                              "field": { "type": "string" }, "value": {} },
              "required": ["op","field"] } } },
        "required": ["record_id","steps"] },
      "code": "def apply_change_plan(record_id, steps):\n    rec = get_record(record_id)\n    for s in steps:\n        if s['op'] not in ('add','remove','update'):\n            return {'error': 'bad op', 'step': s}\n    for s in steps:\n        rec = update_record(record_id, s['op'], s['field'], s.get('value'))\n    return {'record_id': record_id, 'applied': len(steps), 'record': rec}" } },
  { "tool": "update_record", "kind": "remove" }
]
```

Why it works: the analyze→apply sequence lives entirely in the tool body, so a
single call performs all of it — the agent can no longer narrate a plan and then
fail to execute it. Removing the raw `update_record` makes the composite the only
reachable write path, so the stall cannot recur by routing around it.

## 3d. Keep failure modes — improve, do not delete, `Raises:`

Anti-symptom: an optimizer "cleaned up" a description by deleting its `Raises:`
section. Do the opposite — keep the error conditions and pair each with the
recovery action.

```json
{ "tool": "charge_payment", "kind": "description",
  "value": "Charge `amount` (whole US cents) to the payment method `payment_id` from the user's profile. Use after the user confirms the total. Fails if the payment method is not on file (pick another from get_user_details) or if a gift-card balance is below `amount` (split across methods or choose a card). Example: charge_payment(payment_id='gift_card_42', amount=1299)." }
```

Why it works: the model now knows the units (cents), the precondition (method on
file), and exactly what to do on each failure — instead of retrying the same bad
call.

## 3f. Shape the result — high-signal fields, readable ids, actionable errors

Trace symptom: a tool returns the raw row (uuids, mime, audit columns); the model
hallucinates ids and the response floods context. And when a call is invalid, the
handler raises an opaque traceback the model can't recover from.

```json
{ "tool": "get_order", "kind": "code",
  "value": "def get_order(order_id):\n    row = db.orders.find(order_id)\n    if row is None:\n        return {'error': f\"no order {order_id!r}; search with search_orders(query=...) to find the id\"}\n    return {\n        'order_id': row['public_ref'],   # stable, human-readable, not the uuid\n        'status': row['status'],\n        'items': [{'sku': i['sku'], 'qty': i['qty']} for i in row['items']],\n        'total_cents': row['total_cents'],\n    }" }
```

Why it works: the projection drops noise, returns a readable `order_id`, and the
not-found path is an **actionable** message that names the recovery tool — the
model self-corrects instead of retrying the same bad call. Add a
`verbosity`/`response_format` param when callers sometimes need the full row.

## 3g. A comprehensively documented tool (the doc contract)

Every tool — primitive or wrapper — should carry: a crisp what/when/when-not, an
"important points" note, a Raises/errors section, per-parameter docs with
units/format/default, and one generic example.

```json
{ "tool": "charge_payment", "kind": "description",
  "value": "Charge `amount` to a payment method on the user's profile and return the receipt.\nUse after the user confirms the total; do NOT use to quote a price (use get_quote).\nImportant: amounts are in WHOLE US CENTS (1299 = $12.99); the method must already be on file.\nRaises: 'method not on file' — pick another id from get_user_details; 'gift-card balance below amount' — split across methods or choose a card.\nExample: charge_payment(payment_id='card_1', amount=1299)" }
```

Pair it with a schema whose `amount` param description says "Whole US cents
(integer), e.g. 1299 for $12.99" and a `payment_id` with an `input_examples` entry.

## 4. Shrink an overlapping toolset — remove + consolidate

Trace symptom: `create_pr`, `review_pr`, `merge_pr` all present; agent keeps
choosing the wrong one. Consolidate into one tool with an `action` parameter,
then remove the three originals.

```json
[
  { "kind": "add", "value": {
      "name": "pull_request",
      "description": "Create, review, or merge a pull request. Set action to choose the operation.",
      "parameters": { "type": "object", "properties": {
          "action": { "type": "string", "enum": ["create","review","merge"] },
          "id": { "type": "string" } }, "required": ["action"] } } },
  { "tool": "create_pr", "kind": "remove" },
  { "tool": "review_pr", "kind": "remove" },
  { "tool": "merge_pr",  "kind": "remove" }
]
```

## 5. Behavior bug — code edit

Trace symptom: `get_order` returns the raw DB row including internal fields the
model then leaks. Fix the handler to return a clean projection.

```json
{ "tool": "get_order", "kind": "code",
  "value": "def get_order(order_id):\n    row = db.orders.find(order_id)\n    return {k: row[k] for k in ('id','status','items','shipping')}" }
```

## 6. A policy refusal (what tightening looks like)

With `inputs/policy.json = {"allow": ["description","params","examples"]}`, the
schema edit in example 2 is refused:

```json
{ "edit": {"tool":"search_orders","kind":"schema", ...},
  "reason": "action 'schema' not allowed by policy" }
```

The fix is either to widen the policy deliberately or to express the change as an
allowed edit (e.g. add the enum guidance via a `params` description instead).

## 7. SECONDARY (last resort) — a passthrough / reasoning-only tool

Trace symptom: the agent keeps skipping a rule. The WEAK fix is a tool whose body
does no real work — it returns its argument and parks the rule in the docstring:

```json
{ "kind": "compose",
  "value": {
    "name": "check_cancellable",
    "description": "Before cancelling, state here whether the record is cancellable and why.",
    "parameters": { "type": "object", "properties": { "reasoning": { "type": "string" } }, "required": ["reasoning"] },
    "code": "def check_cancellable(reasoning):\n    return {'noted': reasoning}" } }
```

Why it under-performs: the body enforces nothing — the model can write any
`reasoning` and still proceed, exactly like ignoring a prompt sentence. **Prefer
the §3c code-bearing wrapper** (`cancel_record_safely` reads the record and refuses
in code, then `remove` the raw primitive) so the rule is guaranteed, not merely
requested. Only keep a reasoning-only tool when the step genuinely cannot be made
deterministic.
