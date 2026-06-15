# Pitfalls — editing a tool surface

Failure modes that make a tool edit a regression rather than an improvement, and
how to detect each from traces or from `validate`.

## Over-describing into contradiction
Piling on "use when" clauses until two of them conflict makes selection *worse*,
not better. A model resolves contradictory instructions unpredictably.
- **Detect:** description has multiple, overlapping trigger conditions; selection
  is now inconsistent across near-identical inputs.
- **Fix:** one crisp paragraph — what / when / when-not — and state the boundary
  only against the *nearest sibling* tool, not against every other tool.

## Schema and code drift apart
You own the callers, so a `schema` change is "safe" — but only if the handler
`code` matches it. A renamed/retyped parameter in the schema with an unchanged
handler yields runtime errors the model can't recover from.
- **Detect:** the tool starts erroring on well-formed calls after a schema edit.
- **Fix:** change `schema` and `code` in the *same* edit batch, then run
  `validate`. In a frozen-API setting, lock both off via policy.

## Composite-tool sprawl
A `compose` tool is only worth its slot in the choice set if the chain it
replaces is frequent and error-prone. Adding composites for paths the agent
already handles enlarges the toolset and *degrades* selection (more tools → worse
relevance detection; see concepts.md §3).
- **Detect:** new composite tools are rarely chosen, or selection accuracy on
  *other* tools dropped after you added them.
- **Fix:** remove composites that don't earn their place; keep the surface small.

## Removing a rarely-but-critically-needed tool
Low call-count is not the same as low value. A tool used in 2% of traces may be
the only correct action in those traces.
- **Detect:** removed a low-frequency tool; a previously-passing task class now
  fails with "no applicable tool."
- **Fix:** remove for *overlap/confusion*, not for low frequency. Re-add and
  instead disambiguate via descriptions.

## Example dumps that hurt reasoning models
A few examples sharpen formatting, but long blocks of examples can degrade
reasoning-tuned models and crowd the context.
- **Detect:** adding many `examples` lowered accuracy on a model that reasons.
- **Fix:** encode the constraint in the *schema* (types, `enum`, formats) and keep
  one or two examples, not ten.

## Vague names defeat good descriptions
`lookup`, `query`, `do_it` select poorly no matter how good the description is —
the name is read first and weighs heavily.
- **Detect:** mis-selection persists after a description rewrite.
- **Fix:** rename to a verb-noun that states the action and object
  (`get_order`, `search_orders`); namespace when domains overlap.

## Silent policy mismatch (avoided by design)
`apply()` never silently drops a disallowed edit — it records it under
`refused`. An optimizer that "did nothing" is usually hitting a too-tight policy.
- **Detect:** `apply()` returns `changed: []` and a non-empty `refused`.
- **Fix:** widen `inputs/policy.json` deliberately, or re-express the change as an
  allowed edit kind.
