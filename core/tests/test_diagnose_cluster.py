"""Corpus-relative stopword filtering in diagnose's failure clustering.

The live-run bug: 22 of 30 failing tasks merged into one mega-cluster with no
discriminating signal, because the benchmark's own recurring domain vocabulary
("action check state write") isn't in any fixed English stopword list, so it
survived into every key and made unrelated failures look identical. The fix adds
a SECOND, corpus-relative filter (a stem common to most of the batch's feedbacks
is dropped too) on top of — never instead of — the fixed generic-English list.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

CLUSTER_PY = (Path(__file__).resolve().parents[2] / "skills" / "phases" / "diagnose"
             / "scripts" / "cluster.py")


@pytest.fixture(scope="module")
def cluster_mod():
    spec = importlib.util.spec_from_file_location("diagnose_cluster", CLUSTER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_mega_cluster_without_the_fix(cluster_mod):
    """Reproduce the bug directly against the OLD single-tier filter (_STOP/_GENERIC
    only, no corpus-relative pass): the benchmark's boilerplate ("action check state
    write") is generic-English-clean, so two genuinely different root causes still
    overlap >= 0.5 and merge into one cluster."""
    a = "action check state write balance field is negative for account"
    b = "action check state write balance field is negative for currency"
    key_a = cluster_mod.key_tokens(a)
    key_b = cluster_mod.key_tokens(b)
    assert cluster_mod.overlap(key_a, key_b) >= cluster_mod.OVERLAP_MIN


def test_corpus_relative_filter_separates_the_mega_cluster(cluster_mod):
    """With the SAME boilerplate recurring across a whole batch of otherwise-different
    failures, the fix separates them into discriminated clusters instead of one mega-
    cluster covering every task."""
    items = []
    # 8 failures share "action check state write" boilerplate but differ in root cause.
    causes = [
        "negative account balance field",
        "negative account balance field",
        "negative account balance field",
        "duplicate transaction id conflict",
        "duplicate transaction id conflict",
        "duplicate transaction id conflict",
        "missing currency code parameter",
        "missing currency code parameter",
    ]
    for i, cause in enumerate(causes):
        fb = f"action check state write {cause} for task"
        items.append((f"t{i}", fb, 1.0))

    clusters = cluster_mod.cluster(items)
    # Old behavior (no corpus filter) would merge all 8 into one mega-cluster because
    # "action check state write" dominates every key. The fix must produce at least the
    # 3 real root-cause groups (balance / duplicate / missing-currency).
    assert len(clusters) >= 3, clusters
    all_tasks = sorted(t for c in clusters for t in c["tasks"])
    assert all_tasks == sorted(f"t{i}" for i in range(len(causes)))


def test_corpus_stopwords_needs_real_recurrence():
    """A stem used by only a MINORITY of the batch is not corpus boilerplate — it must
    stay, or a real shared root cause could be filtered away by the corpus pass."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("diagnose_cluster", CLUSTER_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    stemmed = [["negative", "balance"], ["negative", "balance"], ["duplicate", "id"]]
    stop = mod.corpus_stopwords(stemmed, threshold=0.65)
    assert "duplicate" not in stop and "id" not in stop


def test_corpus_stopwords_is_additive_not_a_replacement(cluster_mod):
    """The fixed generic-English list still fires even when nothing is corpus-common —
    the new filter is IN ADDITION to it, not instead of it."""
    key = cluster_mod.key_tokens(
        "the task failed because the expected balance was negative")
    assert "task" not in key and "fail" not in key and "expect" not in key
    assert "negat" in key and "balance" in key
