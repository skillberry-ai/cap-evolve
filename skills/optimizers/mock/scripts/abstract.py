"""The mock optimizer is fully concrete — there are no abstract methods to fill.

It exists so the whole pipeline can be tested without a real agent. ``check.py``
smoke-tests the edit engine directly. Real optimizer skills (claude-code, codex,
gemini-cli, ...) put their proposer wiring in ``run.py`` and, if they need the
agent to implement anything, declare it here.
"""
