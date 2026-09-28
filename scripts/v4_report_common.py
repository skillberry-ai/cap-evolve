"""Shared splice/diff machinery for the v4 arm report generators
(build_v4_t_task_reports.py, build_v4_g_task_reports.py).

These four pieces must stay identical between the arms: a divergence in the
marker splice logic would silently clobber hand-written narrative.
"""
import difflib
import re

AUTO_START = "<!-- BEGIN:auto -->"
AUTO_END = "<!-- END:auto -->"
AUTO_RE = re.compile(re.escape(AUTO_START) + r".*?" + re.escape(AUTO_END), re.DOTALL)

DIFF_START = "<!-- BEGIN:diff -->"
DIFF_END = "<!-- END:diff -->"
DIFF_RE = re.compile(re.escape(DIFF_START) + r".*?" + re.escape(DIFF_END), re.DOTALL)

PLACEHOLDER = "_Not yet analysed._"


def fmt(v):
    return "—" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v))


def file_diff(seed_path, best_path):
    """(diff_lines, added, removed) for one file, seed -> best."""
    seed_lines = seed_path.read_text().splitlines(keepends=True)
    best_lines = best_path.read_text().splitlines(keepends=True)
    diff_lines = list(difflib.unified_diff(
        seed_lines, best_lines,
        fromfile=f"seed/{seed_path.name}", tofile=f"{best_path.parent.parent.name}/best/{seed_path.name}",
    ))
    added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))
    return diff_lines, added, removed


def build_diff_block(seed_dir, best_dir, seed_link, best_link):
    """Auto-managed 'what changed' section: seed_dir/*.md vs best_dir/*.md.

    seed_link/best_link are (display_path, relative_url) pairs used to render
    the markdown links. None means no best_dir exists for this report -- the
    caller drops any stale block.
    """
    if not best_dir.is_dir():
        return None

    seed_files = sorted(seed_dir.glob("*.md"))
    changed = []
    for seed_file in seed_files:
        best_file = best_dir / seed_file.name
        if not best_file.is_file():
            continue
        diff_lines, added, removed = file_diff(seed_file, best_file)
        if diff_lines:
            changed.append((seed_file.name, added, removed, diff_lines))

    seed_display, seed_url = seed_link
    best_display, best_url = best_link

    lines = [DIFF_START, "", "## What changed (seed → best)", ""]
    if not changed:
        lines.append(
            f"Every skill file is byte-identical to [`{seed_display}`]({seed_url}) -- "
            "the champion made no edits."
        )
        lines += ["", DIFF_END]
        return "\n".join(lines)

    lines.append(
        f"{len(changed)} of {len(seed_files)} skill files changed. Full unified "
        f"diffs, [`{seed_display}`]({seed_url}) → [`{best_display}`]({best_url}):"
    )
    lines.append("")
    for name, added, removed, diff_lines in changed:
        lines.append("<details>")
        lines.append(f"<summary><code>{name}</code> (+{added}/−{removed})</summary>")
        lines.append("")
        lines.append("```diff")
        lines.extend(l.rstrip("\n") for l in diff_lines)
        lines.append("```")
        lines.append("")
        lines.append("</details>")
        lines.append("")
    lines.append(DIFF_END)
    return "\n".join(lines)


def build_report(title, auto_block, diff_block, existing_text, prefilled_hand=None):
    """Splice auto_block/diff_block into existing_text, preserving hand narrative."""
    if existing_text is None:
        hand = prefilled_hand if prefilled_hand is not None else PLACEHOLDER
        text = f"# {title}\n\n{auto_block}\n\n{hand}\n"
    elif AUTO_RE.search(existing_text):
        text = AUTO_RE.sub(auto_block, existing_text, count=1)
    else:
        text = existing_text.rstrip("\n") + "\n\n" + auto_block + "\n"

    if diff_block is None:
        return DIFF_RE.sub("", text) if DIFF_RE.search(text) else text
    if DIFF_RE.search(text):
        return DIFF_RE.sub(diff_block, text, count=1)
    return text.rstrip("\n") + "\n\n" + diff_block + "\n"
