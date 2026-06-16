"""Abstract methods for <skill-name> — IMPLEMENT THESE.

The optimizer agent implements every method below. Each stub raises
NotImplementedError with the "IMPLEMENT ME" marker so `check.py` can detect and
report exactly what is unfilled. Replace the body, keep the signature.

Many skills delegate to the project-level adapter in
``.capevolve/project/adapters/adapter.py`` (the 4-method CapabilityAdapter). If this
skill's work is fully covered there, import and call it rather than duplicating.
"""

from __future__ import annotations

IMPLEMENT_MARKER = "IMPLEMENT ME"


def example_abstract_method(*args, **kwargs):
    """Replace with the real method(s) this skill needs.

    Document inputs/outputs precisely; downstream skills depend on the shape.
    """
    raise NotImplementedError(f"{IMPLEMENT_MARKER}: example_abstract_method")
