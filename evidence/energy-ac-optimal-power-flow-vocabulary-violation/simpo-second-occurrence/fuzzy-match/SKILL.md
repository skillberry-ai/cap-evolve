---
name: fuzzy-match
description: A toolkit for fuzzy string matching and data reconciliation. Useful for matching entity names (companies, people) across different datasets where spelling variations, typos, or formatting differences exist.
license: MIT
---

# Fuzzy Matching Guide

## Overview

This skill provides methods to compare strings and find the best matches using Levenshtein distance and other similarity metrics. It is essential when joining datasets on string keys that are not identical.

When reconciling records against a reference/master table, a lookup key that is **not present in the reference** counts as *missing* — report it as `null`, even if the source row literally carried a value. Do not echo the raw source token. See [Reporting reconciled keys](#reporting-reconciled-keys-missing-vs-present) below.

## Quick Start

```python
from difflib import SequenceMatcher

def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

print(similarity("Apple Inc.", "Apple Incorporated"))
# Output: 0.7...
```

## Python Libraries

### difflib (Standard Library)

The `difflib` module provides classes and functions for comparing sequences.

#### Basic Similarity

```python
from difflib import SequenceMatcher

def get_similarity(str1, str2):
    """Returns a ratio between 0 and 1."""
    return SequenceMatcher(None, str1, str2).ratio()

# Example
s1 = "Acme Corp"
s2 = "Acme Corporation"
print(f"Similarity: {get_similarity(s1, s2)}")
```

#### Finding Best Match in a List

```python
from difflib import get_close_matches

word = "appel"
possibilities = ["ape", "apple", "peach", "puppy"]
matches = get_close_matches(word, possibilities, n=1, cutoff=0.6)
print(matches)
# Output: ['apple']
```

### rapidfuzz (Recommended for Performance)

If `rapidfuzz` is available (pip install rapidfuzz), it is much faster and offers more metrics.

```python
from rapidfuzz import fuzz, process

# Simple Ratio
score = fuzz.ratio("this is a test", "this is a test!")
print(score)

# Partial Ratio (good for substrings)
score = fuzz.partial_ratio("this is a test", "this is a test!")
print(score)

# Extraction
choices = ["Atlanta Falcons", "New York Jets", "New York Giants", "Dallas Cowboys"]
best_match = process.extractOne("new york jets", choices)
print(best_match)
# Output: ('New York Jets', 100.0, 1)
```

## Common Patterns

### Normalization before Matching

Always normalize strings before comparing to improve accuracy.

```python
import re

def normalize(text):
    # Convert to lowercase
    text = text.lower()
    # Remove special characters
    text = re.sub(r'[^\w\s]', '', text)
    # Normalize whitespace
    text = " ".join(text.split())
    # Common abbreviations
    text = text.replace("limited", "ltd").replace("corporation", "corp")
    return text

s1 = "Acme  Corporation, Inc."
s2 = "acme corp inc"
print(normalize(s1) == normalize(s2))
```

### Entity Resolution

When matching a list of dirty names to a clean database:

```python
clean_names = ["Google LLC", "Microsoft Corp", "Apple Inc"]
dirty_names = ["google", "Microsft", "Apple"]

results = {}
for dirty in dirty_names:
    # simple containment check first
    match = None
    for clean in clean_names:
        if dirty.lower() in clean.lower():
            match = clean
            break

    # fallback to fuzzy
    if not match:
        matches = get_close_matches(dirty, clean_names, n=1, cutoff=0.6)
        if matches:
            match = matches[0]

    results[dirty] = match
```

### Reporting reconciled keys (missing vs. present)

A key you looked up carries two *independent* facts: (1) whether it exists in the
authoritative reference table, and (2) what value you report for it. These must not
be conflated. If a key read from a source row is **absent from the reference table**,
it is *missing* for reporting purposes — emit `None`/`null`, **not** the raw source
token — even when the source literally carried a value such as `"INVALID"`, `"N/A"`,
`"NONE"`, `"-"`, `"UNKNOWN"`, or any other placeholder. A value being *present in the
source* does NOT make the key "found"; only presence in the reference table does.

```python
# reference_keys: the set (or dict keys) of keys that exist in the authoritative table.
def report_key(source_key, reference_keys):
    # Present in the source but absent from the reference => missing => null.
    return source_key if source_key in reference_keys else None
```

Determine any *flag/reason* ("key not found" is itself a finding) from the same
lookup, and then report the key's output value with `report_key(...)`. So a record
flagged because its key is not in the reference table should report that key as
`null`, regardless of what string the source contained.
