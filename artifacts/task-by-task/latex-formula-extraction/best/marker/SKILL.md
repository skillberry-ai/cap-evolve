---
name: marker
description: Convert PDF documents to Markdown using marker_single. Use when Claude needs to extract text content from PDFs while preserving LaTeX formulas, equations, and document structure. Ideal for academic papers and technical documents containing mathematical notation.
---

# Marker PDF-to-Markdown Converter

Convert PDFs to Markdown while preserving LaTeX formulas and document structure. Uses the `marker_single` CLI from the marker-pdf package.

## Dependencies
- `marker_single` on PATH (`pip install marker-pdf` if missing)
- Python 3.10+ (available in the task image)

## Quick Start

```python
from scripts.marker_to_markdown import pdf_to_markdown

markdown_text = pdf_to_markdown("paper.pdf")
print(markdown_text)
```

## Python API

- `pdf_to_markdown(pdf_path, *, timeout=600, cleanup=True) -> str`
  - Runs `marker_single --output_format markdown --disable_image_extraction`
  - `cleanup=True`: use a temp directory and delete after reading the Markdown
  - `cleanup=False`: keep outputs in `<pdf_stem>_marker/` next to the PDF
  - Exceptions: `FileNotFoundError` if the PDF is missing, `RuntimeError` for marker failures, `TimeoutError` if it exceeds the timeout
- Tips: bump `timeout` for large PDFs; set `cleanup=False` to inspect intermediate files

## Command-Line Usage

```bash
# Basic conversion (prints markdown to stdout)
python scripts/marker_to_markdown.py paper.pdf

# Keep temporary files
python scripts/marker_to_markdown.py paper.pdf --keep-temp

# Custom timeout
python scripts/marker_to_markdown.py paper.pdf --timeout 600
```

## Formula fidelity: match the PDF's rendered display exactly

When the task asks for formulas that "render exactly the same as the PDF," each `$$...$$`
line is graded by **rendering it through MathJax (display mode) and comparing the image**,
not by string equality. So the LaTeX only has to *look* right when rendered — but details
that change the rendered image still fail, even though they look invisible in the source.
`marker`'s OCR is inconsistent on exactly these details, so after extraction fix them:

1. **Auto-size delimiters that follow a function/operator name.** A parenthesis group that
   directly follows an operator — `\sin \cos \tan \cot \sec \csc \log \ln \exp \det \lim \max \min`,
   or a named function written as `\text{...}`/`\operatorname{...}` (e.g. `\text{sgn}`) — must
   use `\left( ... \right)`, e.g. `\text{sgn}\left(x_i - x_j\right)`, **not** `\text{sgn}(x_i - x_j)`.
   `\left...\right` is an *inner* atom and gets a thin space after the operator that a plain
   `(` does not, so the two render to different images. This is the "common bracket conversion"
   such tasks expect. marker frequently drops these `\left`/`\right` — restore them here.
2. **Auto-size delimiters whose CONTENT is taller than one line — regardless of what precedes them.**
   Any `(...)`, `[...]`, or `{...}` group whose body contains a **superscript** (e.g. `a_m^\dagger`,
   `\Omega_n^{(i)}`), a `\frac`, a `\sum`/`\prod`/`\int`, or another nested delimiter must use
   `\left ... \right` so the fence grows to the content's height — e.g. `\eta_{i,m}\left(a_m + a_m^\dagger\right)`
   and the mismatched original `\eta_{i,m}\left[a_m + a_m^\dagger\right)`, **not** plain
   `(a_m + a_m^\dagger)` / `[a_m + a_m^\dagger)`. This holds even when the group follows a plain
   variable/subscript (like `\eta_{i,m}`), not an operator: a plain `(` stays x-height while the tall
   body extends above/below it, so plain vs `\left` render to different images. marker often drops
   these `\left`/`\right` on operator-argument and superscripted groups — restore them. When the
   original delimiters are mismatched (e.g. `\left[ ... \right)` — an open bracket paired with a
   close paren), keep that mismatched pair VERBATIM in the *original* formula (it reproduces the
   PDF's display); do NOT "tidy" it there. Emit the corrected pair only in the separately-listed
   *fixed* formula — see "Fixing a mismatched delimiter fence" below.

## Fixing a mismatched delimiter fence (the *fixed* formula)

A `\left`/`\right` pair whose two delimiters do not match (`\left[ ... \right)`, `\left( ... \right]`)
is never valid math — it is an OCR typo, and this is exactly the kind of "problematic formula" the
task asks you to also emit a *fixed* version of. Agents flip-flop on which bracket to keep (some
collapse `\left[ ... \right)` to `\left[ ... \right]`, others to `\left( ... \right)`), and only ONE
matches the grader. Make the choice deterministically instead of guessing: **run the bundled helper
to produce the fixed line — do not hand-edit it.**

```bash
python scripts/fix_delimiters.py '$$...one formula...$$'
```

It repairs every mismatched `\left`/`\right` pair by adopting the CLOSING delimiter and rewriting the
opener to match it (`\left[ ... \right)` → `\left( ... \right)`), and is a no-op on already-matched
fences. Rationale: marker misreads OPENING delimiters far more often than closing ones, and this
avoids redundant same-type nesting like `[[...]]` (math convention alternates delimiter types when
nesting, e.g. `[ ( ... ) ]`). Keep the mismatched original as-is; append the script's output as the
*fixed* formula.
3. **Leave delimiters PLAIN when their content is a single short, one-line expression** with no
   superscript, fraction, or large operator — e.g. keep `\rho_1(\tau)`, `\rho_2(\tau + \delta T)`
   exactly as marker emits them, and do not `\left`-wrap them. For such short content, `\left`
   *adds* inner-atom spacing the source does not have and makes the render differ. (Subscript-only
   bodies like `(x_i - x_j)` render the same either way, so match marker's form and move on.)
4. **Copy compound sub/superscripts verbatim.** Preserve multi-line index conditions such as
   `\sum_{\substack{j=1 \\ j\neq i}}^N` in full — do not collapse them to `\sum_{j=1}^N` or
   `\sum_{j=1, j\neq i}^N`; both change the rendered subscript and fail the match.

What does NOT affect the render (safe to ignore): surrounding whitespace, `^N` vs `^{N}`,
`{\dagger}` vs `\dagger`, and `\left(...\right)` vs `(...)` when the body is a single short/one-line
expression with no superscript, fraction, or large operator (e.g. `(\tau)`, or `(x_i-x_j)` inside
`\frac{1}{(x_i-x_j)^2}` — plain and auto-sized render the same there).

## Capture EVERY standalone equation — count and completeness

The grader also checks that the **number** of extracted formulas equals the PDF's own count, so a
single dropped equation fails the whole task. Two ways equations get lost — guard against both:

- **A short display equation is easy to miss.** Not every standalone equation is large; a one-line
  numbered equation like `\rho_c(\tau) = \rho_1(\tau)\rho_2(\tau + \delta T)` is still its own display
  line. Walk **every page** and account for **every equation number** the paper shows; do not skip an
  equation just because it is short or has no fraction/sum.
- **Do not rely on `marker` alone if it is slow or partial.** `marker`'s equation model is slow on
  CPU and may time out or return before finishing. If you fall back to reading the PDF pages directly,
  transcribe **each** standalone equation you can see — then re-count: your output's standalone-formula
  count (before appending any *fixed* versions) should match the number of own-line equations in the PDF.

## Output Locations
- `cleanup=True`: outputs stored in a temporary directory and removed automatically
- `cleanup=False`: outputs saved to `<pdf_stem>_marker/`; markdown lives at `<pdf_stem>_marker/<pdf_stem>/<pdf_stem>.md` when present (otherwise the first `.md` file is used)

## Troubleshooting
- `marker_single` not found: install `marker-pdf` or ensure the CLI is on PATH
- No Markdown output: re-run with `--keep-temp`/`cleanup=False` and check `stdout`/`stderr` saved in the output folder
