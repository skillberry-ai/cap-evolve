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
from .cache import EvalCache, hash_candidate_dir
from .gate import GateDecision, TrainGateError, decide
from .lr_schedule import build_schedule
from .memory import History, RejectedMemory
from .rundir import Budget, RunDir, Spent
from .selection import PICKERS, STRATEGIES, pick, validate_strategy
from .splits import Splits, TestSealError, make_splits
from .stats import aggregate, bootstrap_ci, combined_stderr, mean, pass_at_k, pass_k, stderr
from .trials import run_trials_pool
from .types import Candidate, Rollout, Score, Task

__version__ = "0.1.0"

__all__ = [
    "CapabilityAdapter",
    "stub_methods",
    "EvalCache",
    "hash_candidate_dir",
    "build_schedule",
    "PICKERS",
    "STRATEGIES",
    "pick",
    "validate_strategy",
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
    "run_trials_pool",
    "Candidate",
    "Rollout",
    "Score",
    "Task",
    "__version__",
]
