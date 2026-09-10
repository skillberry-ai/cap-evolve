---
name: fuzzy-match
description: "Reconcile transactional records (invoices, transactions, line items) against authoritative reference tables — approved-vendor lists, purchase-order/order registers, customer masters — including fuzzy entity-name matching and foreign-key (PO/vendor/order id) validation. Use when detecting invoice or payment fraud, validating that a record's reference id exists in a lookup table, or matching vendor/company names that have spelling variations or suffix differences (Ltd vs Limited)."
---

# Reconciling Records Against Reference Tables

Use this when cross-checking transactional records (invoices, transactions, line items)
against authoritative lookup tables (an approved-vendor list, a purchase-order/order
register, a customer master) — e.g. invoice-fraud detection.

## Output convention for unresolved reference keys (read this first)

A record often carries a **foreign key** — a PO number, order id, vendor id, reference
number — that is supposed to resolve to a row in a reference table. Handle a key that does
NOT resolve as follows, because downstream checks define it this way:

- **An unresolved reference key is "missing" — output it as `null`, never the raw string.**
  If the key is malformed, fails the expected format, or is simply absent from the reference
  table, do **not** echo the raw unmatched value (e.g. `"PO-INVALID"`, `"N/A"`, an empty
  string) into your output. Report that key field as `null`.
- Only emit the literal key value when it **actually matches a row** in the reference table.
- Instructions like *"if the PO is missing, set it to null"* mean *not found in the reference
  table*, not merely blank on the record. An id that is present on the record but absent from
  (or malformed for) the lookup counts as missing → `null`.

```python
import re
# po_raw is the value parsed off the record; po_db is the set/dict of valid PO keys.
# Validate the expected key shape, then require membership in the reference table.
po_key = po_raw if (po_raw and re.fullmatch(r"PO-\d+", po_raw) and po_raw in po_db) else None
# po_key is None  ->  the reference is invalid/missing; report null (do NOT write po_raw).
```

(The `PO-\d+` pattern above is illustrative — use the key shape your reference table
actually uses.)

**Naming the reason after an invalid key does NOT mean you keep the key value.** A record
whose PO is present on the document but absent from the register is still reported with a
`null` key — the reason merely *names* the failure. Concretely, for a required output like
`{... "po_number": ..., "reason": ...}`:

```json
{ "po_number": null, "reason": "Invalid PO" }          // reason names the bad key; field is null
{ "po_number": "PO-INVALID", "reason": "Invalid PO" }  // WRONG: raw placeholder leaked into the key
```

### Finalize the output — enforce this convention with the bundled script

Do NOT rely on an inline `if`/ternary to null the key while you build each row — that check is
easy to botch (e.g. `po if po != "PO-INVALID" or True else po` silently keeps the raw value).
Build your report, then **run the bundled finalizer as the LAST step** to guarantee every
unresolved key field is `null`. Do not reimplement it:

```bash
# valid_pos: the keys that DO resolve in the reference table (comma-list, or @file one per line)
python scripts/nullify_unresolved_keys.py /root/fraud_report.json \
    --set po_number=@valid_pos.txt
```

It rewrites the report in place, setting any `po_number` (or any `--set` field) whose value is
not in the valid-key set to `null`, and leaves matching values untouched. Pass one `--set`
per key field. This makes the "unresolved key → null" rule deterministic regardless of how
your row-building code handled it.

## Normalize entity names before fuzzy matching

Raw fuzzy scores without normalization misclassify legitimate spelling variants as unknown.
Before comparing names, on BOTH sides: lower-case, strip punctuation, collapse whitespace,
and canonicalize common entity suffixes (`Ltd`↔`Limited`, `Inc`↔`Incorporated`,
`Corp`↔`Corporation`, `Co`↔`Company`).

## Apply classification criteria strictly in priority order

When a record can match several criteria, stop at the FIRST that fires in the stated order.
Checks that need the reference row to exist (amount/value comparison, cross-link/ownership
checks) can only run AFTER the key resolves. If the key is unresolved, the record's reason is
the invalid-reference case and its key field is `null` — do not attempt the later checks.

## Fuzzy string matching (how to compute similarity)

### difflib (standard library, always available)

```python
from difflib import SequenceMatcher, get_close_matches

def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()   # 0..1

# best match within a candidate list
matches = get_close_matches("Acme Corp", ["Acme Corporation", "Beta LLC"], n=1, cutoff=0.85)
```

### rapidfuzz (faster, more metrics — use if installed: `pip install rapidfuzz`)

```python
from rapidfuzz import fuzz, process
fuzz.ratio("Acme Corp", "Acme Corporation")            # 0..100
process.extractOne("Acme Corp", ["Acme Corporation"])  # (match, score, index)
```

Pick a cutoff (e.g. ratio > 85 / 0.85) that accepts suffix/typo variants but rejects genuinely
different entities; when in doubt, normalize first (above) so the threshold is meaningful.
