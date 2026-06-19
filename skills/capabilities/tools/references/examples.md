# Examples — worked tool edits

Each example is an edit you would emit to `apply()`. Edit shape:
`{"tool": <name>, "kind": <action>, "value": <...>}`. For `add`/`compose` the
value is a full tool def; for `remove` the value is ignored.

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
