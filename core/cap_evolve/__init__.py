"""cap_evolve — the tiny, stdlib-only honest-evaluation substrate.

This is the *only* shipped code in cap-evolve. Everything user-facing is an
Agent Skill; those skills' ``run.py`` scripts call into here for the things that
must be consistent and honest across every run: task/score types, seeded splits
with a sealed test set, variance-aware statistics, the acceptance gate,
optimizer memory, the run directory, and the adapter contract.

Import it directly when Python is available, or invoke ``python -m
cap_evolve <command>`` and parse the JSON it prints.
"""

from __future__ import annotations

from .adapter import CapabilityAdapter, stub_methods
from .gate import GateDecision, TrainGateError, decide
from .memory import History, RejectedMemory
from .rundir import Budget, RunDir, Spent
from .splits import Splits, TestSealError, make_splits
from .stats import aggregate, bootstrap_ci, combined_stderr, mean, pass_at_k, pass_k, stderr
from .types import Candidate, Rollout, Score, Task

__version__ = "0.1.0"

__all__ = [
    "CapabilityAdapter",
    "stub_methods",
    "GateDecision",
    "TrainGateError",
    "decide",
    "History",
    "RejectedMemory",
    "Budget",
    "RunDir",
    "Spent",
    "Splits",
    "TestSealError",
    "make_splits",
    "aggregate",
    "bootstrap_ci",
    "combined_stderr",
    "mean",
    "pass_at_k",
    "pass_k",
    "stderr",
    "Candidate",
    "Rollout",
    "Score",
    "Task",
    "__version__",
]
