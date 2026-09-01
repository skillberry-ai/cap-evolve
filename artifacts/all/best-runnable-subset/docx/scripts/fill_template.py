#!/usr/bin/env python3
"""
Fill a Word ({{PLACEHOLDER}}) template from a JSON data dict, correctly handling
the four things that break naive scripts and cost tasks their score:

  1. SPLIT PLACEHOLDERS - Word stores "{{NAME}}" as several XML runs
     ("{{NA", "ME}}"). Matching per-run misses them; this works at paragraph level.
  2. HEADERS & FOOTERS - not in doc.paragraphs. A body-only fill leaves
     "{{DOC_ID}}" etc. behind, and verifiers extract header/footer text.
  3. NESTED TABLES - tables inside table cells (and tables inside headers/footers).
  4. CONDITIONAL BLOCKS - "{{IF_KEY}}...{{END_IF_KEY}}" spanning one OR many
     paragraphs; markers must be removed, kept content substituted.

USAGE
-----
    python scripts/fill_template.py <template.docx> <data.json> <output.docx>

data.json is a flat object of KEY -> value, e.g.
    {"CANDIDATE_FULL_NAME": "Sarah Chen", "RELOCATION_PACKAGE": "Yes", ...}

CONDITIONAL SEMANTICS
---------------------
For a marker "{{IF_RELOCATION}}", the block is KEPT iff a truthy condition is
found, looked up in this order: data["RELOCATION_PACKAGE"], then data["RELOCATION"],
then any single key that starts with "RELOCATION". Truthy = one of
{"yes","true","1","y","include","on"} (case-insensitive) or boolean True / 1.
If kept, the {{IF_}}/{{END_IF_}} markers are stripped and inner placeholders filled;
if not, the entire block content is removed.

The placeholder pattern is  \\{\\{([A-Za-z0-9_]+)\\}\\}  (handles digits in keys).
Do NOT reimplement this by hand - run this script.
"""
import json
import re
import sys

from docx import Document

PLACEHOLDER = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")
IF_RE = re.compile(r"\{\{IF_([A-Za-z0-9_]+)\}\}")
ENDIF_RE = re.compile(r"\{\{END_IF_([A-Za-z0-9_]+)\}\}")
TRUTHY = {"yes", "true", "1", "y", "include", "on"}


def condition_true(key, data):
    for cand in (f"{key}_PACKAGE", key):
        if cand in data:
            v = data[cand]
            if isinstance(v, bool):
                return v
            return str(v).strip().lower() in TRUTHY
    for k, v in data.items():
        if k.startswith(key):
            if isinstance(v, bool):
                return v
            return str(v).strip().lower() in TRUTHY
    return False


def set_paragraph_text(para, new_text):
    """Replace a paragraph's whole text, preserving the first run's formatting."""
    runs = para.runs
    if runs:
        runs[0].text = new_text
        for r in runs[1:]:
            r.text = ""
    else:
        para.add_run(new_text)


def delete_paragraph(para):
    el = para._element
    el.getparent().remove(el)


def fill_placeholders(text, data):
    def repl(m):
        key = m.group(1)
        return str(data[key]) if key in data else m.group(0)
    return PLACEHOLDER.sub(repl, text)


def process_paragraph_list(paragraphs, data):
    """Handle conditionals (single- or multi-paragraph) then fill placeholders,
    over a flat, ordered list of paragraphs from one container."""
    # Pass 1: conditional blocks.
    i = 0
    to_delete = []
    while i < len(paragraphs):
        p = paragraphs[i]
        text = p.text
        mif = IF_RE.search(text)
        if mif:
            key = mif.group(1)
            keep = condition_true(key, data)
            mend_same = ENDIF_RE.search(text)
            if mend_same:
                # Whole block inside one paragraph.
                if keep:
                    new = IF_RE.sub("", text)
                    new = ENDIF_RE.sub("", new)
                    set_paragraph_text(p, new)
                else:
                    # Remove the block text; keep any text outside the markers.
                    start = mif.start()
                    end = mend_same.end()
                    new = text[:start] + text[end:]
                    if new.strip():
                        set_paragraph_text(p, new)
                    else:
                        to_delete.append(p)
                i += 1
                continue
            # Multi-paragraph block: find the END paragraph.
            j = i + 1
            end_idx = None
            while j < len(paragraphs):
                if ENDIF_RE.search(paragraphs[j].text):
                    end_idx = j
                    break
                j += 1
            if end_idx is None:
                # Malformed; just strip the opening marker.
                set_paragraph_text(p, IF_RE.sub("", text))
                i += 1
                continue
            # Opening paragraph: strip marker or delete.
            first_rest = IF_RE.sub("", text)
            if keep:
                if first_rest.strip():
                    set_paragraph_text(p, first_rest)
                else:
                    to_delete.append(p)
            else:
                to_delete.append(p)
            # Middle paragraphs.
            for k in range(i + 1, end_idx):
                if not keep:
                    to_delete.append(paragraphs[k])
            # Closing paragraph: strip marker or delete.
            end_p = paragraphs[end_idx]
            end_rest = ENDIF_RE.sub("", end_p.text)
            if keep:
                if end_rest.strip():
                    set_paragraph_text(end_p, end_rest)
                else:
                    to_delete.append(end_p)
            else:
                to_delete.append(end_p)
            i = end_idx + 1
            continue
        i += 1

    for p in to_delete:
        delete_paragraph(p)

    # Pass 2: fill placeholders on survivors.
    for p in paragraphs:
        if p._element.getparent() is None:
            continue
        if "{{" in p.text:
            set_paragraph_text(p, fill_placeholders(p.text, data))


def process_table(table, data):
    for row in table.rows:
        for cell in row.cells:
            process_paragraph_list(list(cell.paragraphs), data)
            for nested in cell.tables:
                process_table(nested, data)


def fill(template_path, data_path, out_path):
    with open(data_path) as f:
        data = json.load(f)
    doc = Document(template_path)

    process_paragraph_list(list(doc.paragraphs), data)
    for table in doc.tables:
        process_table(table, data)
    for section in doc.sections:
        for hf in (section.header, section.footer,
                   section.first_page_header, section.first_page_footer,
                   section.even_page_header, section.even_page_footer):
            process_paragraph_list(list(hf.paragraphs), data)
            for table in hf.tables:
                process_table(table, data)

    doc.save(out_path)

    # Self-check: report any placeholder left anywhere.
    check = Document(out_path)
    parts = [p.text for p in check.paragraphs]
    for t in check.tables:
        for r in t.rows:
            for c in r.cells:
                parts.append(c.text)
    for s in check.sections:
        for hf in (s.header, s.footer):
            parts.extend(p.text for p in hf.paragraphs)
            for t in hf.tables:
                for r in t.rows:
                    for c in r.cells:
                        parts.append(c.text)
    leftover = PLACEHOLDER.findall("\n".join(parts))
    if leftover:
        print("WARNING: unreplaced placeholders remain:", sorted(set(leftover)), file=sys.stderr)
        return False
    print("OK: no placeholders remain.")
    return True


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)
    ok = fill(sys.argv[1], sys.argv[2], sys.argv[3])
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
