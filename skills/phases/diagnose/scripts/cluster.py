"""Deterministic failure clustering — the mechanical half of diagnose.

A cluster is ONE root cause. Its identity is a **(site, expectation)** pair: where
the trajectory went wrong (the tool / field / step the trace names) and which
expectation was missed. Two failures belong to the same cluster when both halves
agree, however differently the scorer phrased it and whatever task-specific values
it quoted.

Deriving that key from a feedback string is deterministic, so it lives here instead
of being re-improvised in prose on every iteration:

1. strip the token prefix every failure's feedback shares (a scorer boilerplate
   preamble otherwise makes every failure look identical);
2. reduce to content words — drop quoted literals / numbers / punctuation
   (task-specific, not causal), drop stopwords and OUTCOME-GENERIC words which say
   *that* it failed and never *why*, and crudely stem the rest so
   confirm/confirmed/confirmation collapse;
3. the surviving token set is the key — identifiers are the site, verbs the
   expectation;
4. two keys are the same cluster when they OVERLAP: |A∩B| / min(|A|,|B|) >= 0.5,
   merged transitively. Overlap rather than equality is what keeps one root cause
   from splitting into three clusters under three phrasings.

Everything is sorted, so the same input always yields byte-identical output.
"""

from __future__ import annotations

import re

# Words that name THAT something failed, never WHY. Keeping them lets two unrelated
# causes look similar just because both were reported as a failure.
_GENERIC = frozenset("""
fail failed failure error errored wrong incorrect invalid missing miss expected
expect expects got produce produced output outputs task tasks agent step steps
required require unexpected instead actual result results response correct bad
should would did does done value values return returned reward score scored
scoring trajectory grading grade graded because only just also however issue
problem problems reason cause caused unable cannot able
""".split())

_STOP = frozenset("""
the a an and or but of to in on for with that this these those it its is are was
were be been being at by from as has have had do than then when which while will
can could all any into out no not none more most some such very over under after
before during about again there here their them they you your our his her one two
""".split())

# Longest first so "confirmation" -> "confirm", not "confirmatio".
_SUFFIXES = ("ations", "ation", "ements", "ement", "ingly", "ings", "ing", "edly",
             "ness", "ions", "ion", "ive", "ed", "es", "ly", "s")

_MIN_STEM = 4

OVERLAP_MIN = 0.5


def _stem(tok: str) -> str:
    for suf in _SUFFIXES:
        if tok.endswith(suf) and len(tok) - len(suf) >= _MIN_STEM:
            return tok[: -len(suf)]
    return tok


def _words(feedback: str) -> list[str]:
    s = (feedback or "").lower()
    s = re.sub(r"['\"`].*?['\"`]", " ", s)   # quoted literals: task-specific
    s = re.sub(r"[0-9]+", " ", s)            # numbers: task-specific
    s = re.sub(r"[^a-z_ ]+", " ", s)         # punctuation (keep _: identifiers)
    return [t for t in s.split() if len(t) > 2]


def common_prefix(feedbacks: list[str]) -> list[str]:
    """The longest leading token run shared by EVERY feedback (the boilerplate)."""
    seqs = [_words(f) for f in feedbacks if (f or "").strip()]
    if len(seqs) < 2:
        return []
    out: list[str] = []
    for i in range(min(len(s) for s in seqs)):
        tok = seqs[0][i]
        if all(s[i] == tok for s in seqs):
            out.append(tok)
        else:
            break
    # If the shared run covers a whole feedback, the failures are not distinguishable
    # by their prefix at all (identical wording) — stripping would delete the signal
    # rather than boilerplate. Leave it; the generic-word filter still discriminates.
    if out and any(len(s) == len(out) for s in seqs):
        return []
    return out


def key_tokens(feedback: str, prefix: list[str] | None = None) -> frozenset[str]:
    """The (site, expectation) key: content-word stems, boilerplate removed."""
    toks = _words(feedback)
    pre = prefix or []
    if pre and toks[: len(pre)] == pre:
        toks = toks[len(pre):]
    stems = [_stem(t) for t in toks]
    keep = [s for s in stems if s not in _STOP and s not in _GENERIC]
    if not keep:                       # all-generic feedback: fall back to what we have
        keep = [s for s in stems if s not in _STOP] or stems
    return frozenset(keep)


def overlap(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def cluster(items: list[tuple[str, str, float]]) -> list[dict]:
    """Group ``(task_id, feedback, score_lost)`` triples by root cause.

    Clusters are sorted by score lost, then task count, then signature — a total
    order, so the output is byte-identical on repeated runs over the same input.
    """
    prefix = common_prefix([f for _, f, _ in items])
    keys = [key_tokens(f, prefix) for _, f, _ in items]

    # Union-find over the overlap relation (transitive: A~B and B~C => one cluster).
    # ponytail: O(n^2) pair scan — fine for a val split; index by token if it grows.
    parent = list(range(len(items)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if overlap(keys[i], keys[j]) >= OVERLAP_MIN:
                ri, rj = find(i), find(j)
                if ri != rj:
                    parent[max(ri, rj)] = min(ri, rj)

    groups: dict[int, list[int]] = {}
    for i in range(len(items)):
        groups.setdefault(find(i), []).append(i)

    out = []
    for root in sorted(groups):
        idxs = groups[root]
        counts: dict[str, int] = {}
        for i in idxs:
            for t in keys[i]:
                counts[t] = counts.get(t, 0) + 1
        label = " ".join(t for t, _ in
                         sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:4])
        out.append({
            "signature": label or "unknown",
            "tasks": sorted(items[i][0] for i in idxs),
            "score_lost": round(sum(items[i][2] for i in idxs), 4),
            # Judgement, not derivable here — diagnose's reader fills these in.
            "tag": None,
            "blast_radius": None,
        })
    out.sort(key=lambda c: (-c["score_lost"], -len(c["tasks"]), c["signature"]))
    return out
