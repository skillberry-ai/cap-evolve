"""all-at-once has no per-skill abstract methods beyond the project adapter.

It composes the contract methods (tasks/run_target/score/apply) via the shared
harness; the optimizer skill supplies the proposer. Nothing here needs filling,
so ``check.py`` verifies wiring rather than implementations.
"""
