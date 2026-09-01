---
name: lean4-theorem-proving
description: Use when working with Lean 4 (.lean files), writing mathematical proofs, seeing "failed to synthesize instance" errors, managing sorry/axiom elimination, or searching mathlib for lemmas - provides build-first workflow, haveI/letI patterns, compiler-guided repair, and LSP integration
---

# Lean 4 Theorem Proving

## Core Principle

**Build incrementally, structure before solving, trust the type checker.** Lean's type checker is your test suite.

**Success = `lake build` passes + zero sorries + zero custom axioms.** Theorems with sorries/axioms are scaffolding, not results.

## Quick Reference

All detailed guidance lives in this skill's own `references/` directory (see [Reference Files](#reference-files)). Load a reference only when the task calls for it.

| **Need** | **Where to Find** |
|----------|-------------------|
| Tactic decision trees, common tactics | [tactics-reference.md](references/tactics-reference.md) |
| Compilation error → fix workflows | [compilation-errors.md](references/compilation-errors.md) |
| Iterative compiler-guided repair | [compiler-guided-repair.md](references/compiler-guided-repair.md) |
| Mathlib search & naming | [mathlib-guide.md](references/mathlib-guide.md) |
| LSP server (optional, faster feedback) | [lean-lsp-server.md](references/lean-lsp-server.md) |
| Subagent batch patterns (optional) | [subagent-workflows.md](references/subagent-workflows.md) |

## When to Use

Use for ANY Lean 4 development: pure/applied math, program verification, mathlib contributions.

**Critical for:** Type class synthesis errors, sorry/axiom management, mathlib search, measure theory/probability work.

## Orient First, Then Use a Fast Inner Loop

Before writing tactics, spend a moment orienting to the project you are actually in — this prevents long, blind exploration:

1. **Read the target file's imports and the project's `lakefile`/`lean-toolchain` first.** Do not assume full Mathlib is available: many projects vendor a *limited custom library* (their own tactics and lemmas). The available `import`s at the top of the file, plus the lakefile, tell you which tactics/lemmas you may use. Only search Mathlib for a lemma once you have confirmed Mathlib (or the needed module) is actually imported.

2. **Type-check the single file for the edit→check loop:** run `lake env lean <file>.lean` (fast — elaborates just that file) after each edit, rather than a full-project `lake build` every time. Reserve a full `lake build` for a final whole-project check. This keeps each iteration to seconds and avoids repeatedly recompiling the whole dependency tree.

3. **Respect edit-scope constraints.** If the task fixes a file's prefix (imports, definitions, theorem statement) or forbids touching other files, edit only the permitted region and re-run the single-file check; do not rewrite the fixed prefix.

**Optional accelerators:** the [Lean LSP server](references/lean-lsp-server.md) gives instant proof state, and [subagent workflows](references/subagent-workflows.md) help batch work — use them only when they save time, never as a prerequisite.

## Build-First Principle

**ALWAYS compile before committing.** Use `lake env lean <file>.lean` while iterating, then confirm with a full `lake build` before declaring done. "Compiles" ≠ "Complete" - files can compile with sorries/axioms but aren't done until those are eliminated.

## The 4-Phase Workflow

1. **Structure Before Solving** - Outline proof strategy with `have` statements and documented sorries before writing tactics
2. **Helper Lemmas First** - Build infrastructure bottom-up, extract reusable components as separate lemmas
3. **Incremental Filling** - Fill ONE sorry at a time, compile after each, commit working code
4. **Type Class Management** - Add explicit instances with `haveI`/`letI` when synthesis fails, respect binder order for sub-structures

## Finding and Using Mathlib Lemmas

**Philosophy:** Search before prove. Mathlib has 100,000+ theorems.

First confirm the lemma's module is imported (see orientation above), then search. See [mathlib-guide.md](references/mathlib-guide.md) for detailed search techniques, naming conventions, and import organization.

## Essential Tactics

**Key tactics:** `simp only`, `rw`, `apply`, `exact`, `refine`, `by_cases`, `rcases`, `ext`/`funext`. See [tactics-reference.md](references/tactics-reference.md) for comprehensive guide with examples and decision trees.

## Domain-Specific Patterns

**Analysis & Topology:** Integrability, continuity, compactness patterns. Tactics: `continuity`, `fun_prop`.

**Algebra:** Instance building, quotient constructions. Tactics: `ring`, `field_simp`, `group`.

**Measure Theory & Probability** (emphasis in this skill): Conditional expectation, sub-σ-algebras, a.e. properties. Tactics: `measurability`, `positivity`. See [measure-theory.md](references/measure-theory.md) for detailed patterns.

**Complete domain guide:** [domain-patterns.md](references/domain-patterns.md)

## Managing Incomplete Proofs

**Standard mathlib axioms (acceptable):** `Classical.choice`, `propext`, `quot.sound`. Check with `#print axioms theorem_name`.

**CRITICAL: Sorries/axioms are NOT complete work.** A theorem that compiles with sorries is scaffolding, not a result. Document every sorry with concrete strategy and dependencies. Search mathlib exhaustively before adding custom axioms.

**When sorries are acceptable:** (1) Active work in progress with documented plan, (2) User explicitly approves temporary axioms with elimination strategy.

**Not acceptable:** "Should be in mathlib", "infrastructure lemma", "will prove later" without concrete plan.

## Compiler-Guided Proof Repair

**When a proof fails to compile,** repair it from the compiler's error message instead of blind resampling:

1. Compile the single file (`lake env lean <file>.lean`) and read the *first* structured error (type, location, goal, hypotheses in context).
2. For the failing goal, try the automated tactic cascade before hand-writing a proof — many goals close mechanically:
   - Order: `rfl → simp → ring → linarith → nlinarith → omega → exact? → apply? → aesop`
   - (Use only tactics the project actually provides; a vendored library may expose its own equivalents.)
3. If none close it, write a minimal targeted patch (1–5 lines) driven by the exact error, recompile, and repeat.
4. **Early stopping:** if the same error persists after ~3 distinct attempts, step back and re-examine the goal/lemma rather than resampling the same fix.

**Detailed guide:** [compiler-guided-repair.md](references/compiler-guided-repair.md)

**Inspired by:** APOLLO (https://arxiv.org/abs/2505.05758) - compiler-guided repair with multi-stage models and low sampling budgets.

## Common Compilation Errors

| Error | Fix |
|-------|-----|
| "failed to synthesize instance" | Add `haveI : Instance := ...` |
| "maximum recursion depth" | Provide manually: `letI := ...` |
| "type mismatch" | Use coercion: `(x : ℝ)` or `↑x` |
| "unknown identifier" | Add import |

See [compilation-errors.md](references/compilation-errors.md) for detailed debugging workflows.


## Documentation Conventions

- Write **timeless** documentation (describe what code is, not development history)
- Don't highlight "axiom-free" status after proofs are complete
- Mark internal helpers as `private` or in dedicated sections
- Use `example` for educational code, not `lemma`/`theorem`

## Quality Checklist

**Before commit:**
- [ ] `lake build` succeeds on full project
- [ ] All sorries documented with concrete strategy
- [ ] No new axioms without elimination plan
- [ ] Imports minimal

**Doing it right:** Sorries/axioms decrease over time, each commit completes one lemma, proofs build on mathlib.

**Red flags:** Sorries multiply, claiming "complete" with sorries/axioms, fighting type checker for hours, monolithic proofs (>100 lines), long `have` blocks (>30 lines should be extracted as lemmas - see [proof-refactoring.md](references/proof-refactoring.md)).

## Reference Files

**Core references:** [lean-phrasebook.md](references/lean-phrasebook.md), [mathlib-guide.md](references/mathlib-guide.md), [tactics-reference.md](references/tactics-reference.md), [compilation-errors.md](references/compilation-errors.md)

**Domain-specific:** [domain-patterns.md](references/domain-patterns.md), [measure-theory.md](references/measure-theory.md), [instance-pollution.md](references/instance-pollution.md), [calc-patterns.md](references/calc-patterns.md)

**Incomplete proofs:** [sorry-filling.md](references/sorry-filling.md), [axiom-elimination.md](references/axiom-elimination.md)

**Optimization & refactoring:** [performance-optimization.md](references/performance-optimization.md), [proof-golfing.md](references/proof-golfing.md), [proof-refactoring.md](references/proof-refactoring.md), [mathlib-style.md](references/mathlib-style.md)

**Automation:** [compiler-guided-repair.md](references/compiler-guided-repair.md), [lean-lsp-server.md](references/lean-lsp-server.md), [lean-lsp-tools-api.md](references/lean-lsp-tools-api.md), [subagent-workflows.md](references/subagent-workflows.md)
