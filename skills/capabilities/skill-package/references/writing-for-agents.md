# Writing for the agent reader, not the human

> Load this before editing any user-facing text of a skill (the `description`, the
> body, a reference). Most skills are authored by humans (or human+AI), so the prose
> drifts toward a *human* reader — it markets, narrates, and explains at length. The
> only reader that matters at runtime is an **agent** deciding whether to trigger the
> skill and how to follow it. Optimize for that reader.

## The principle
A human reader skims, infers intent, and forgives vague prose. An agent reader does
three concrete things with your text and nothing else:
1. **Selects** — reads the `description` to decide whether this skill fires.
2. **Follows** — reads the body to decide what to do, step by step.
3. **Pays** — every body token is re-read on every trigger for the whole session.

So write text that makes those three cheap and unambiguous, and cut everything that
only serves a human.

## Human-reader smells → agent-reader fix
- **Marketing / value-prop tone** ("a powerful, flexible toolkit for…") → state the
  concrete task and the trigger: "Exports a table to CSV. Use when the user asks to
  export or download tabular data."
- **Describing internal mechanics** ("uses a three-pass XML transform") → describe
  the *user intent* the skill serves; the agent matches against what the user asked,
  not how you built it.
- **Narrating the why at length** (paragraphs of rationale) → state what to do; give
  a rule's reason in one clause ("…because the output is read aloud by TTS").
- **First / mixed person** ("I can help you…", "we then…") → third person,
  imperative: "Processes…", "Run the validation script first."
- **Prose where a list/table/decision-tree is clearer** → the agent parses structure
  faster and follows it more reliably than paragraphs.

## Checklist (run before keeping an edit)
- [ ] `description` says WHAT it does AND WHEN to use it, third person, front-loaded.
- [ ] The literal keywords a user would actually type appear in the `description`.
- [ ] The body instructs (imperative) rather than narrates; each rule's reason is one
      clause, not a paragraph.
- [ ] No first person, no marketing adjectives, no ALL-CAPS unless a measured
      over/under-trigger problem demands it.
- [ ] Nothing in the text serves only a human reader (history, credits, prose that
      restates the obvious).

See also: [`description-optimization.md`](description-optimization.md) (the trigger
lever) and [`anti-patterns.md`](anti-patterns.md) (smells to review against).
