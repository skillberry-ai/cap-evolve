#!/usr/bin/env python3
"""Finalize a reconciliation/output report: force every reference-key field whose
value does NOT resolve to a row in its reference table to be JSON `null`.

This enforces the standard convention "an unresolved foreign key is missing -> null,
never the raw string" deterministically, regardless of how the report was built. Run
it as the LAST step on your output file so a botched inline null-check (or an echoed
placeholder like "PO-INVALID"/"N/A"/"") cannot leak the raw value into the result.

It is intentionally GENERAL: you tell it which field(s) hold a reference key and what
the valid keys are. It hardcodes nothing about any particular task.

Usage
-----
    # valid keys inline (comma-separated), one --set per key field:
    python nullify_unresolved_keys.py report.json \
        --set po_number=PO-1001,PO-1002,PO-1003

    # or read the valid keys from a file (one per line):
    python nullify_unresolved_keys.py report.json \
        --set po_number=@valid_pos.txt --set vendor_id=@valid_vids.txt

The report file must be a JSON array of objects (or a single object). Any object whose
`<field>` value, compared as a trimmed string, is not in the valid-key set for that
field is rewritten to null. Matching values are left untouched. The file is updated
in place (use --out to write elsewhere). Prints a summary of how many were nulled.
"""
import argparse
import json
import sys


def load_valid_keys(spec):
    """spec is either '@path' (one key per line) or 'a,b,c' (comma-separated)."""
    if spec.startswith("@"):
        with open(spec[1:], encoding="utf-8") as fh:
            items = [ln.strip() for ln in fh]
    else:
        items = [s.strip() for s in spec.split(",")]
    return {s for s in items if s}


def normalize(value):
    """Compare keys as trimmed strings so 'PO-1001' matches ' PO-1001 '."""
    if value is None:
        return None
    return str(value).strip()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report", help="path to the JSON report (array of objects)")
    ap.add_argument("--set", dest="sets", action="append", required=True,
                    metavar="FIELD=KEYS",
                    help="reference-key field and its valid keys; KEYS is either a "
                         "comma-separated list or @file (one key per line). Repeatable.")
    ap.add_argument("--out", help="output path (default: overwrite report in place)")
    args = ap.parse_args(argv)

    valid_by_field = {}
    for spec in args.sets:
        if "=" not in spec:
            ap.error(f"--set expects FIELD=KEYS, got {spec!r}")
        field, keyspec = spec.split("=", 1)
        valid_by_field[field.strip()] = load_valid_keys(keyspec)

    with open(args.report, encoding="utf-8") as fh:
        data = json.load(fh)

    records = data if isinstance(data, list) else [data]
    nulled = {f: 0 for f in valid_by_field}
    for rec in records:
        if not isinstance(rec, dict):
            continue
        for field, valid in valid_by_field.items():
            if field not in rec:
                continue
            if normalize(rec[field]) not in valid:
                if rec[field] is not None:
                    nulled[field] += 1
                rec[field] = None

    out_path = args.out or args.report
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")

    total = sum(nulled.values())
    print(f"nullify_unresolved_keys: wrote {out_path}; nulled {total} unresolved key(s): "
          + ", ".join(f"{f}={n}" for f, n in nulled.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
