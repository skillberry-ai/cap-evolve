# Pitfalls — editing a tool surface

Failure modes that make a tool edit a regression rather than an improvement, and
how to detect each from traces or from `validate`.

## Stripping error info / `Raises:` to "clean up" the description
The error conditions a tool can raise are *guidance for the model*, not clutter.
Knowing a call raises "balance too low" or "record not found" is
what lets the model pick a different argument or a different tool instead of
failing. Deleting that text removes a guard rail and typically does not improve
selection at all.
- **Detect:** an edit's only change is removing `Raises:`/error lines or other
  failure-mode text; the metric is flat or the model now makes the same bad call
  the error described.
- **Fix:** keep failure modes in the description. If anything, make them more
  precise and pair each with what the model should do instead.

## Trying to fix a BEHAVIORAL stall with prose
The agent analyzes, confirms, then fails to call the write tool and stops. This
is the single most common — and most expensive — failure, and it is *behavioral*:
the model already "knows" what to do and skips it. Rewording a docstring or
adding "always act after confirming" does not fix a behavior the model already
declined; the traces show those edits failing.
- **Detect:** failing tasks where the trace contains the analysis/confirmation
  but no write call; "be sure to act"-style edits that don't move the metric.
- **Fix:** move the whole action into a composite WRITE tool whose body performs
  every step (examples §3e), then `remove` the raw write primitives so completing
  the action is the only path.

## Wrapping a primitive but leaving it exposed
A validation wrapper or composite achieves nothing if the raw primitive it wraps
is still in the toolset — the model can call the primitive directly and reproduce
the exact failure the wrapper was meant to prevent. Observed: optimizers add safe
wrappers but never `remove` the primitives, so the unsafe path survives.
- **Detect:** a wrapper/composite was added but the primitive it delegates to is
  still exposed; traces still show direct calls to the primitive.
- **Fix:** pair every wrapper/composite with a `remove` of the primitive, unless
  the primitive is still independently needed for a different, safe purpose.

## Wrong arguments to a write (partial-credit failures)
A task can fail partway — the right write tool called with the wrong unit, a
missing field, or an unresolved id — scoring partial credit, not zero. These are
easy to overlook if you only look at fully-failing tasks.
- **Detect:** partial-credit tasks whose feedback names a malformed write
  argument (wrong unit, id not on file, missing required field).
- **Fix:** a normalize-then-call wrapper that coerces units, resolves ids, and
  checks the field/method is on file *before* calling the primitive, turning a
  corrupted write into a clean refusal (examples §3c-bis).

## Cosmetic rewording that adds no always-true information
Reflowing sentences, adding commas, or restating the obvious changes the text
without changing what the model knows. It will not move behavior.
- **Detect:** the diff has no new trigger, unit, allowed-value, default, or
  failure mode — just reworded prose.
- **Fix:** add genuinely new, always-true content (when/when-not, argument
  semantics, an always-valid example), or reach for a loop/rule/composite tool.

## Overfitting a description to one task
Putting a specific id, date, or city from a single task into a description
overfits and can mislead on the next input.
- **Detect:** the description names literal values that came from one trace.
- **Fix:** describe the *shape* and *rules* that hold for every input; if you
  show an example, make it a generic well-formed one.

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

## Opaque errors and UUID-heavy / bloated responses
A handler that raises a raw traceback (or returns a low-signal blob full of uuids,
mime types, and audit columns) leaves the model blind: it hallucinates ids,
re-fetches, and retries the same invalid call because the error told it nothing.
- **Detect:** failing tasks where the trace shows the model copying a wrong id, or
  re-issuing the identical bad call after an error with an opaque message.
- **Fix:** project to high-signal fields, surface a stable human-readable id (not
  the raw UUID), and return an **actionable** error that names the correct format
  or the recovery tool ("payment method not on file; available: [...]"). Errors are
  a steering surface (examples §3f).

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

## Tool granularity that fights the agent
A tool that is too small (a one-liner the agent could inline) clutters the choice set;
a tool that is too large (`office_tool()` doing everything) hides its real behavior and
can't be selected precisely.
- **Detect:** a rarely-chosen trivial tool, or one mega-tool whose description needs
  five "use when" clauses.
- **Fix:** one clear capability per tool; split the mega-tool into composable pieces
  (`extract_text`, `extract_xml`, `validate_file`, `repair_document`).

## Human-oriented tool text (the meta-smell)
Descriptions and docstrings written to read well for a person — marketing adjectives,
internal-mechanics narration, long rationale, first person — waste the surface the
agent selects and fills from.
- **Detect:** the description carries no always-true matchable info (triggers, units,
  allowed values, failure modes) — just polished prose.
- **Fix:** third-person imperative; what/when/when-not; per-argument units, allowed
  values, defaults; retained failure modes. See
  [`authoring-and-validation.md`](authoring-and-validation.md) §1.
