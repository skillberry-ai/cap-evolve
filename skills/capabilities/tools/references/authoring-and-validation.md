# Building tools & scripts an agent can find, fill, and run

> Load this when the edit *builds or specifies* a tool or a bundled script (not just
> rewording an existing one). Two things must be true of a good tool: (a) the agent
> can FIND it and FILL its arguments correctly, and (b) it FUNCTIONALLY WORKS and
> returns the desired output. This file covers both, plus the validation that proves
> it. The mental model behind (a) is in [`concepts.md`](concepts.md) (SELECT-then-FILL);
> failure modes are in [`pitfalls.md`](pitfalls.md).

## Contents
- 1. Write for the agent reader, not the human
- 2. Specify a tool completely before building it
- 3. Docstring rules that make slot-filling reliable
- 4. Validate that the tool functionally works
- 5. Tool granularity, composition, and observability
- 6. Bundled scripts: the agent-facing interface

## 1. Write for the agent reader, not the human
An LLM never sees your implementation — only `{name, description, parameters, examples}`
and the return value. Text written to impress a human (marketing tone, internal
mechanics, long rationale, first person) wastes the surface the agent actually reads.
Write third-person and imperative; state what the tool does, when to use it, when NOT
to, and the exact argument semantics. (Same principle across every capability.)

## 2. Specify a tool completely before building it
A tool the agent can use well starts from a complete spec. Capture every field —
gaps here become slot-filling and correctness failures later:
- **name** — a `verb_noun` that states the action and object (`get_order`, not `lookup`).
- **summary / intent** — one line of what it does; one line of why it exists.
- **inputs** — per parameter: `name`, `type`, `description`, `required`, `default`,
  and **`enum_values`** for any closed set (turns "guess a string" into "pick one").
- **outputs** — per field: `name`, `type`, `description`, `nullable`.
- **examples** — split into **happy_path**, **edge_cases**, and **error_cases**.
- **dependencies** — the other tools this one calls, with their compact signatures so
  the body calls them correctly.
- **error_model** — the failure conditions and what each returns/raises.
- **security_notes** — anything the code must refuse or sanitize.

**Error-case discipline.** An `error_case` whose expected result is an error *code*
(`NOT_FOUND`, `UNAUTHORIZED` — all-caps, no spaces) is a true negative the tool should
raise/return-as-error. An `error_case` whose expected result is a full-sentence
message, OR any tool that always returns a dict, should instead be a *positive* example
returning `{"success": false, "message": "..."}`. Don't model a recoverable,
message-bearing outcome as a thrown exception.

## 3. Docstring rules that make slot-filling reliable
The docstring is the contract the agent reads to fill arguments. Make it exact:
- **Derive the docstring from the CODE, not from a supplied description.** This
  prevents description/implementation drift — the doc always matches what runs.
- **Enumerate ALL allowed values for every constrained parameter.** If the code uses
  an enum, a `Literal`, a default, or validation logic, list every accepted value
  explicitly (do not generalize or summarize). Explain each hardcoded value the code
  depends on.
- **Pin units, format, and default per parameter** — "amount in whole US cents",
  "ISO-8601 date `YYYY-MM-DD`", "default: 10".
- **Keep it parseable:** a standalone `Parameters:` section with one indented
  `<name> (<type>): <description>` line per argument, and a standalone `Returns:`
  section with the return type and description. Retain a `Raises:` / errors section —
  documented failure modes are guidance the model uses to avoid a bad call, not clutter.

## 4. Validate that the tool functionally works
Building is not done until the tool is proven to work. A robust build/validate loop:
- **Retry generation on validation failure** (a few attempts) rather than shipping a
  broken tool.
- **Generate unit tests from the provided examples** — assert happy_path and
  edge_cases return the expected output, and that error_cases raise/return the expected
  error. Prefer testing against the *provided* examples (including negatives) over
  free-invented tests.
- **Execute the tests**, don't just generate them — execution validation catches what
  static checks miss.
- **Syntax + signature checks** — the code parses (AST), defines the named function,
  and matches the declared signature (strict signature from name + inputs).
- **Evaluation-score threshold** — hold the candidate to a minimum quality score;
  reject below it.
- **Security / unwanted-content checks** — refuse code that does something the spec
  forbids or embeds disallowed content.
- **Recovery** — on a codegen failure, prefer reusing an already-validated tool over
  emitting a stub.

## 5. Tool granularity, composition, and observability
- **Granularity** — avoid tools that are too small (one trivial call the agent could
  inline) or too large (`office_tool()` that does everything). Aim for one clear
  capability per tool: `extract_text()`, `extract_xml()`, `validate_file()`,
  `repair_document()`.
- **Composition** — design tools that compose naturally
  (`extract_xml() → modify_notes() → repackage()`) instead of one monolithic
  executable. A composite tool is worth its slot only when the chain it replaces is
  frequent and error-prone.
- **Observability (Layer 4, invisible to the LLM)** — the implementation should be
  robust (retries, validation, graceful failures, informative errors) and, where it
  matters, collect execution time / failures / retries so the tool can be optimized
  over time. Algorithmic and memory improvements (streaming, caching, parallelism)
  live here and never change the tool's contract.

## 6. Bundled scripts: the agent-facing interface
A script an agent runs must be designed for a non-interactive reader:
- **Never prompt interactively.** Agents run in non-interactive shells; a TTY prompt
  hangs forever. Take all input via flags / env / stdin, and fail with a clear message
  naming the missing flag.
- **Document the interface in `--help`** — a brief description, the flags, and usage
  examples. This is how the agent learns to call the script; keep it concise.
- **Structured output** — prefer JSON/CSV/TSV on stdout; send progress/warnings to
  stderr so the agent can parse clean data while still seeing diagnostics.
- **Meaningful, documented exit codes** — distinct codes for distinct failures
  (not-found, bad-args, auth), listed in `--help`.
- **Idempotency & `--dry-run`** — agents retry; "create if not exists" beats "fail on
  duplicate", and a `--dry-run` lets the agent preview stateful/destructive actions.
- **Truncation-safe output** — many harnesses truncate large tool output; default to a
  summary and support `--offset`/`--output` (or write to a file) for more.
- **Self-contained dependencies** — declare deps inline (PEP-723 `# /// script` for
  Python `uv run`; `npm:`/`bun` pins for JS) and pin versions so runs are reproducible.
