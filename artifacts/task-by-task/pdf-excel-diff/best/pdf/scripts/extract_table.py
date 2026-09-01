#!/usr/bin/env python3
"""Robustly extract a single logical table that spans many pages of a PDF.

Large multi-page tables are the #1 cause of silent row loss. A header row is
often printed at the top of the FIRST page only (sometimes on every page, and
you cannot know which up front). Naively treating the first row of *every*
page's table as a header -- e.g. `pd.DataFrame(table[1:], columns=table[0])`
per page -- deletes one real data row on every page whose first row is NOT the
header. Over hundreds of pages that silently drops hundreds of records and the
downstream count / comparison is wrong.

This script is header-aware the safe way: it learns the header once, then keeps
every row EXCEPT rows that exactly match the header (so a repeated header is
dropped, but a genuine first-data-row is never lost).

Usage:
    python extract_table.py INPUT.pdf [--out OUT.csv] [--json OUT.json]

Writes a CSV (default: <input>.csv) and/or JSON list-of-dicts, and prints the
header plus the number of data rows so you can sanity-check the count.
"""
import argparse
import csv
import json
import sys

import pdfplumber


def _norm(cell):
    return "" if cell is None else str(cell).strip()


def extract_table(pdf_path):
    """Return (header, rows) for a table spanning one or more pages.

    header: list[str] column names (first non-empty row seen).
    rows:   list[list[str]] every data row, with repeated header rows removed.
    """
    header = None
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if not table:
                    continue
                for raw in table:
                    cells = [_norm(c) for c in raw]
                    if not any(cells):          # skip fully-empty rows
                        continue
                    if header is None:          # first non-empty row = header
                        header = cells
                        continue
                    if cells == header:         # drop a REPEATED header only
                        continue
                    rows.append(cells)
    return header, rows


def _fit(row, width):
    """Pad/truncate a ragged row to the header width."""
    if len(row) < width:
        return row + [""] * (width - len(row))
    return row[:width]


def main():
    ap = argparse.ArgumentParser(description="Robust multi-page PDF table extraction.")
    ap.add_argument("pdf")
    ap.add_argument("--out", help="CSV output path (default: <pdf>.csv)")
    ap.add_argument("--json", dest="json_out", help="optional JSON (list of dicts) output path")
    args = ap.parse_args()

    header, rows = extract_table(args.pdf)
    if header is None:
        print("No table found in PDF", file=sys.stderr)
        sys.exit(1)

    width = len(header)
    rows = [_fit(r, width) for r in rows]

    out_csv = args.out or (args.pdf.rsplit(".", 1)[0] + ".csv")
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump([dict(zip(header, r)) for r in rows], f)

    print(f"header: {header}")
    print(f"data rows: {len(rows)}")
    print(f"wrote: {out_csv}" + (f" and {args.json_out}" if args.json_out else ""))


if __name__ == "__main__":
    main()
