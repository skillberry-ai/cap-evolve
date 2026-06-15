---
name: docx-template-filler
description: >-
  Fill placeholder fields in a Microsoft Word (.docx) template from a data file
  and save the result. Use when a task provides a .docx template with
  {{PLACEHOLDER}} markers and a JSON/CSV of values to substitute.
---

# Filling a Word template

Use the `python-docx` library to open the template, replace each `{{FIELD}}`
placeholder with its value from the data file, and save the output document.

## Steps

1. Read the data file (e.g. `employee_data.json`) into a dict.
2. Open the template with `Document(template_path)`.
3. For every paragraph, replace each `{{FIELD}}` with `str(data[FIELD])`.
4. Save to the requested output path with `doc.save(output_path)`.

## Minimal example

```python
import json, re
from docx import Document

data = json.load(open("/root/employee_data.json"))
doc = Document("/root/offer_letter_template.docx")

for para in doc.paragraphs:
    for key, val in data.items():
        if f"{{{{{key}}}}}" in para.text:
            para.text = para.text.replace(f"{{{{{key}}}}}", str(val))

doc.save("/root/offer_letter_filled.docx")
```

Replace every placeholder so none remain in the final document.
