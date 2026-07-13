"""Shared vocabulary for the whole pipeline.

Every skill speaks in these types so that evaluation, diagnosis, gating, and
optimization compose without bespoke glue. Pure stdlib: a dataclass file with
``to_dict`` / ``from_dict`` so any host can round-trip the JSON that skill
``run.py`` scripts print to stdout.

Design note (vs. prior agent-optimization work): we keep prior agent-optimization work's ``Sample``/``Rollout``/``EvalResult``
shapes but rename to ``Task``/``Rollout``/``Score`` and add ``Candidate`` (the
named-component view gepa uses) so a single object serves both the file-tree
optimizers and the text-component optimizers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


def _clamp01(x: float) -> float:
    """Rewards live in [0, 1]; clamp defensively so a buggy scorer can't poison stats."""
    if x != x:  # NaN
        return 0.0
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else float(x)


@dataclass
class Task:
    """One unit of evaluation work (prior agent-optimization work's ``Sample``)."""

    id: str
    input: Any = None
    target: Any = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return cls(
            id=str(d["id"]),
            input=d.get("input"),
            target=d.get("target"),
            metadata=dict(d.get("metadata") or {}),
        )


@dataclass
class Rollout:
    """The result of running the target agent on one task with a candidate applied."""

    task_id: str
    output: Any = None
    trace: Any = None
    tool_calls: list = field(default_factory=list)
    cost_usd: float = 0.0
    tokens: int = 0
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Rollout":
        return cls(
            task_id=str(d["task_id"]),
            output=d.get("output"),
            trace=d.get("trace"),
            tool_calls=list(d.get("tool_calls") or []),
            cost_usd=float(d.get("cost_usd") or 0.0),
            tokens=int(d.get("tokens") or 0),
            error=d.get("error"),
            metadata=dict(d.get("metadata") or {}),
        )


@dataclass
class Score:
    """A scored task (prior agent-optimization work's ``EvalResult``).

    ``reward`` is the mean over ``trial_rewards``; ``feedback`` is the natural
    language learning signal (gepa's "Actionable Side Information") consumed by
    the diagnosis + optimization skills.
    """

    task_id: str
    reward: float = 0.0
    feedback: str = ""
    n: int = 1
    stderr: float = 0.0
    trial_rewards: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)
    metrics: list = field(default_factory=list)  # shown-only catalog; see _validate_metrics

    def __post_init__(self) -> None:
        self.reward = _clamp01(self.reward)
        self.trial_rewards = [_clamp01(r) for r in self.trial_rewards]
        self._validate_metrics()

    def _validate_metrics(self) -> None:
        if not self.metrics:
            return
        primaries = [m for m in self.metrics if m.get("primary") is True]
        if len(primaries) != 1:
            raise ValueError(f"exactly one metric must be primary, got {len(primaries)}")
        for m in self.metrics:
            if m.get("direction") not in ("higher", "lower"):
                raise ValueError(f"metric {m.get('name')!r} needs direction higher|lower")
        pv = float(primaries[0]["value"])
        if abs(pv - self.reward) > 1e-9:
            raise ValueError(f"primary metric value {pv} must equal reward {self.reward}")

    def primary_metric(self):
        for m in self.metrics:
            if m.get("primary") is True:
                return m
        return None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Score":
        return cls(
            task_id=str(d["task_id"]),
            reward=float(d.get("reward") or 0.0),
            feedback=str(d.get("feedback") or ""),
            n=int(d.get("n") or 1),
            stderr=float(d.get("stderr") or 0.0),
            trial_rewards=list(d.get("trial_rewards") or []),
            raw=dict(d.get("raw") or {}),
            metrics=list(d.get("metrics") or []),
        )


@dataclass
class Candidate:
    """A version of the capability being optimized.

    ``text_parts`` is the named-component view (gepa: ``dict[str, str]``) used by
    text optimizers; ``dir`` is the file-tree view used by directory capabilities
    (SKILL.md packages, tool code). A capability skill provides whichever it
    naturally has; both may be populated.
    """

    id: str
    component: str = ""
    text_parts: dict = field(default_factory=dict)
    dir: Optional[str] = None  # path as str for JSON-friendliness

    @property
    def path(self) -> Optional[Path]:
        return Path(self.dir) if self.dir else None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Candidate":
        return cls(
            id=str(d["id"]),
            component=str(d.get("component") or ""),
            text_parts=dict(d.get("text_parts") or {}),
            dir=d.get("dir"),
        )
