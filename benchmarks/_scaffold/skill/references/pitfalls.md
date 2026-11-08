# Pitfalls & important points — <skill-name>

> Related problems, failure modes, and the things that go wrong in practice.
> This is where hard-won, cited knowledge lives.

## Failure modes
- **<failure>**: <how it shows up> → <how to avoid/detect it>.

## Easy to get wrong
- <subtle point>.

## Honesty guardrails
- Never score or peek at the test split outside `finalize`.
- Gate acceptance on val, never on the data the optimizer edited against.
