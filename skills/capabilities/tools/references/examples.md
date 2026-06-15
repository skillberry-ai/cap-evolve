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
