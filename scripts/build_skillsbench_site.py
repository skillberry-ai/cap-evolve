#!/usr/bin/env python3
"""Render the skillsbench-history branch onto the Pages site.

Walks a checkout of the skillsbench-history branch (--src), converts every
markdown file to a chrome-wrapped HTML page, rewrites relative .md links to
.html, redirects anything under artifacts/ to GitHub (that 27MB tree is not
folded into the site), copies the branch's own pre-existing HTML pages
verbatim with the same link rewrite, copies every other file byte-for-byte,
and generates two level-2 heatmaps the source branch does not have yet
(transfer-eval-8fold, runnable-subset-43).

Usage:
    python3 scripts/build_skillsbench_site.py --src <skillsbench-history checkout> --out site/skillsbench
    python3 scripts/build_skillsbench_site.py --src <checkout> --out <dir> --check
"""
import argparse
import json
import posixpath
import re
import shutil
import sys
from pathlib import Path

import markdown as md_lib

REPO = "skillberry-ai/cap-evolve"
BRANCH = "skillsbench-history"
SKIP_TOP = {"artifacts", ".git"}
MD_EXTENSIONS = ["tables", "fenced_code", "toc", "attr_list", "sane_lists"]

NAV_ITEMS = [
    ("getting-started.html", "Get started"),
    ("run-end-to-end.html", "Run end-to-end"),
    ("results.html", "Results"),
    ("benchmarks.html", "Benchmarks"),
    ("architecture.html", "Architecture"),
    ("agent-orchestration.html", "Agent mode"),
    ("harbor.html", "Harbor"),
]

DEFERRED_ARTIFACTS_NOTE = (
    '<div class="callout callout-warn">'
    '<div class="callout-title">Level 3 material is partial here</div>'
    "<p>This page is rendered on-site from the <code>skillsbench-history</code> branch, "
    "but the underlying skill packages it discusses (<code>seed/</code>, <code>best/</code>, "
    "<code>PROCESS.md</code> under <code>artifacts/</code>) are not folded into the site yet "
    '— follow the <a class="ext-link" href="{artifacts_url}">GitHub ↗</a> links below to see them.</p>'
    "</div>"
)


def artifacts_tree_url(rel_path: str, is_dir: bool) -> str:
    kind = "tree" if is_dir else "blob"
    return f"https://github.com/{REPO}/{kind}/{BRANCH}/{rel_path}"


def rewrite_links(html: str, src_root: Path, cur_rel_dir: str) -> tuple[str, bool]:
    """Rewrite href="..." (including inside JS template-literal strings) in-place.

    Returns (new_html, touched_artifacts) — touched_artifacts is True if any
    link on this page was redirected to the artifacts/ tree on GitHub.
    """
    touched_artifacts = False

    href_re = re.compile(r'href=(["\'])([^"\']+?)\1')

    def repl(m: re.Match) -> str:
        nonlocal touched_artifacts
        quote, href = m.group(1), m.group(2)
        if re.match(r"^([a-z]+:)|^#", href):
            return m.group(0)
        path, _, fragment = href.partition("#")
        if not path:
            return m.group(0)
        resolved = posixpath.normpath(posixpath.join(cur_rel_dir, path))
        parts = resolved.split("/")
        if parts[0] == "artifacts":
            touched_artifacts = True
            is_dir = path.endswith("/") or (src_root / resolved).is_dir()
            new_href = artifacts_tree_url(resolved, is_dir)
            return f'href={quote}{new_href}{quote} class="ext-link"'
        if path.endswith(".md"):
            new_path = path[: -len(".md")] + ".html"
            new_href = new_path + ("#" + fragment if fragment else "")
            return f"href={quote}{new_href}{quote}"
        return m.group(0)

    return href_re.sub(repl, html), touched_artifacts


def rel_prefixes(rel_path: str) -> dict:
    """Compute the relative path prefixes a chrome-wrapped page needs."""
    cur_dir = posixpath.dirname(rel_path)
    to_hub_root = posixpath.relpath(".", cur_dir) if cur_dir else "."
    to_site_root = posixpath.normpath(posixpath.join(to_hub_root, ".."))
    return {
        "cur_dir": cur_dir,
        "hub": to_hub_root,
        "site_root": to_site_root,
    }


def render_chrome(title: str, description: str, body_html: str, rel_path: str, source_rel: str) -> str:
    p = rel_prefixes(rel_path)
    site_root = p["site_root"]
    hub = p["hub"]
    nav_links = "\n".join(
        f'      <a href="{site_root}/{href}">{label}</a>' for href, label in NAV_ITEMS
    )
    source_url = f"https://github.com/{REPO}/blob/{BRANCH}/{source_rel}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — cap-evolve</title>
  <meta name="description" content="{description}">
  <meta name="robots" content="noindex">
  <link rel="icon" href="{site_root}/assets/favicon.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Fira+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <script>(function(){{try{{document.documentElement.setAttribute('data-theme',localStorage.getItem('capevolve-theme')||'dark');}}catch(e){{document.documentElement.setAttribute('data-theme','dark');}}document.documentElement.classList.add('js');}})();</script>
  <link rel="stylesheet" href="{site_root}/style.css?v=20260908a">
</head>
<body>

<nav class="nav">
  <div class="nav-inner">
    <a class="nav-brand" href="{site_root}/"><img src="{site_root}/assets/logo-300.png" alt="" class="nav-brand-logo" aria-hidden="true"><span class="wordmark">cap<span class="wordmark-dot">·</span>evolve</span></a>
    <button class="nav-toggle" type="button" aria-label="Menu" aria-expanded="false" aria-controls="nav-links">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M3 6h18M3 12h18M3 18h18"></path></svg>
    </button>
    <div class="nav-links" id="nav-links">
{nav_links}
      <a href="{hub}/index.html">SkillsBench</a>
      <a class="gh" href="{source_url}">GitHub</a>
      <button class="theme-toggle" type="button" aria-label="Switch theme">
        <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
        <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"></path></svg>
      </button>
    </div>
  </div>
</nav>

<main class="page-narrow doc">
  <p class="lead" style="margin-bottom:0.6rem;font-size:0.95rem;">
    <a href="{hub}/index.html">SkillsBench research</a> ·
    <a class="ext-link" href="{source_url}">view source on GitHub ↗</a>
  </p>
{body_html}
</main>

<footer class="footer">
  <div class="footer-inner">
    <div>
      <span class="wordmark" style="color:var(--ink);font-size:1.05rem;">cap<span class="wordmark-dot">·</span>evolve</span><br>
      Apache-2.0 · beta (0.x) · <em>Optimize agentic capabilities — with agents</em>
    </div>
    <div>
      <a href="https://github.com/{REPO}">github.com/{REPO}</a>
    </div>
  </div>
</footer>

<script src="{site_root}/js/site.js?v=20260822" defer></script>
</body>
</html>
"""


def convert_markdown(src_file: Path, src_root: Path, out_root: Path) -> bool:
    rel = src_file.relative_to(src_root).as_posix()
    out_rel = rel[: -len(".md")] + ".html"
    text = src_file.read_text(encoding="utf-8")
    body = md_lib.markdown(text, extensions=MD_EXTENSIONS)
    cur_dir = posixpath.dirname(rel)
    body, touched_artifacts = rewrite_links(body, src_root, cur_dir)
    if rel.split("/")[0] == "reports" and "task-by-task" in rel:
        artifacts_url = artifacts_tree_url(
            f"artifacts/task-by-task/{Path(rel).stem}", is_dir=True
        )
        body = DEFERRED_ARTIFACTS_NOTE.format(artifacts_url=artifacts_url) + body
    title = rel.rsplit("/", 1)[-1][: -len(".html")]
    page = render_chrome(
        title=f"{title} — SkillsBench",
        description=f"Rendered from {rel} on the skillsbench-history branch.",
        body_html=body,
        rel_path=out_rel,
        source_rel=rel,
    )
    out_file = out_root / out_rel
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(page, encoding="utf-8")
    return touched_artifacts


def copy_html(src_file: Path, src_root: Path, out_root: Path) -> None:
    rel = src_file.relative_to(src_root).as_posix()
    text = src_file.read_text(encoding="utf-8")
    cur_dir = posixpath.dirname(rel)
    text, _ = rewrite_links(text, src_root, cur_dir)
    out_file = out_root / rel
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(text, encoding="utf-8")


def copy_verbatim(src_file: Path, src_root: Path, out_root: Path) -> None:
    rel = src_file.relative_to(src_root)
    out_file = out_root / rel
    out_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_file, out_file)


def walk_source(src_root: Path):
    for p in sorted(src_root.rglob("*")):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(src_root).parts
        if rel_parts and rel_parts[0] in SKIP_TOP:
            continue
        yield p


def fmt_delta(v: float) -> str:
    cls = "delta-pos" if v > 0 else ("delta-neg" if v < 0 else "delta-zero")
    sign = "+" if v > 0 else ""
    return f'<span class="{cls}">{sign}{v:.2f}</span>'


def build_transfer_heatmap(src_root: Path, out_root: Path) -> None:
    data = json.loads((src_root / "results/transfer-eval-8fold/transfer_eval_8fold.json").read_text())
    rows = []
    for f in data["folds"]:
        kind_marker = " ‡" if f["native_optimized_kind"] != "final_test" else ""
        rows.append(
            "<tr>"
            f"<td>{f['fold']}</td>"
            f"<td><code>{f['train_task']}</code></td>"
            f"<td><code>{f['test_task']}</code></td>"
            f"<td>{f['job_id']}</td>"
            f"<td>{f['status']}</td>"
            f"<td>{f['transfer_reward']:.2f}</td>"
            f"<td>{f['native_seed']:.2f}</td>"
            f"<td>{f['native_optimized']:.2f}{kind_marker}</td>"
            f"<td>{fmt_delta(f['transfer_minus_native_seed'])}</td>"
            "</tr>"
        )
    body = f"""
  <h1>transfer-eval-8fold — heatmap</h1>
  <p class="lead">Zero-shot skill transfer, {data['total_folds']} folds, generated {data['generated_at']}.</p>

  <div class="callout callout-warn">
    <div class="callout-title">Read this before the table</div>
    <ul>
      <li>{data['caveats']['test_delta_is_meaningless']}</li>
      <li>{data['caveats']['native_optimized_val_only']}</li>
      <li>{data['caveats']['sample_size']}</li>
    </ul>
  </div>

  <table>
    <thead><tr>
      <th>#</th><th>train task</th><th>test task</th><th>job</th><th>status</th>
      <th>transfer reward</th><th>native seed</th><th>native optimized</th><th>transfer − native seed</th>
    </tr></thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>
  <p><small>‡ in-loop val score, not a held-out test score (task is <code>KILLED_ceiling</code> in results.json).</small></p>

  <p><a href="summary.html">← back to the fold-by-fold writeup</a></p>
"""
    rel_out = "results/transfer-eval-8fold/heatmap.html"
    page = render_chrome(
        title="transfer-eval-8fold heatmap",
        description="Per-fold transfer reward vs native seed/optimized score, 8 folds.",
        body_html=body,
        rel_path=rel_out,
        source_rel="results/transfer-eval-8fold/transfer_eval_8fold.json",
    )
    out_file = out_root / rel_out
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(page, encoding="utf-8")


def build_runnable43_heatmap(src_root: Path, out_root: Path) -> None:
    baseline = json.loads((src_root / "results/runnable-43task-opt/baseline_all.json").read_text())
    per_task = {t["task_id"]: t for t in baseline["val"]["per_task"]}

    passing = {
        "3d-scan-calc", "edit-pdf", "protein-expression-analysis", "syzkaller-ppdev-syzlang",
    }
    partial = {
        "adaptive-cruise-control": "0.667 (2/3)",
        "court-form-filling": "0.667 (2/3)",
        "multilingual-video-dubbing": "0.667 (2/3)",
        "flood-risk-analysis": "0.333 (1/3)",
        "hvac-control": "0.333 (1/3)",
        "invoice-fraud-detection": "0.333 (1/3)",
        "r2r-mpc-control": "0.333 (1/3)",
    }

    rows = []
    for task_id in sorted(per_task):
        t = per_task[task_id]
        if task_id in passing:
            outcome = '<span class="delta-pos">pass (3/3)</span>'
        elif task_id in partial:
            outcome = f'<span class="delta-zero">partial ({partial[task_id]})</span>'
        else:
            outcome = "—"
        rows.append(
            "<tr>"
            f"<td><code>{task_id}</code></td>"
            f"<td>{t['reward']:.3f}</td>"
            f"<td>±{t['stderr']:.3f}</td>"
            f"<td>{t['n']}</td>"
            f"<td>{outcome}</td>"
            "</tr>"
        )

    body = f"""
  <h1>runnable-subset-43 — heatmap</h1>
  <p class="lead">Seed baseline, 43 runnable tasks, val split. Best candidate found: <code>{baseline['best_id']}</code>.</p>

  <div class="callout callout-warn">
    <div class="callout-title">Scope limit — no full candidate × task matrix</div>
    <p><code>iter1.log</code>–<code>iter4.log</code> are 14 lines each and contain no per-task
    granular data, so the per-candidate × per-task numbers were never captured for this run.
    This table shows the <strong>seed baseline</strong> per task, annotated with
    <code>cand_0002</code>'s (the accepted best) pass/partial outcome from
    <a href="summary.html">summary.md</a>'s own breakdown — not a full per-iteration trace.</p>
  </div>

  <table>
    <thead><tr>
      <th>task</th><th>seed reward</th><th>stderr</th><th>trials</th><th>cand_0002 outcome</th>
    </tr></thead>
    <tbody>
      {''.join(rows)}
    </tbody>
  </table>

  <p><a href="summary.html">← back to the run writeup</a></p>
"""
    rel_out = "results/runnable-43task-opt/heatmap.html"
    page = render_chrome(
        title="runnable-subset-43 heatmap",
        description="Seed-baseline per-task reward for the 43-task runnable subset, annotated with cand_0002 outcomes.",
        body_html=body,
        rel_path=rel_out,
        source_rel="results/runnable-43task-opt/baseline_all.json",
    )
    out_file = out_root / rel_out
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(page, encoding="utf-8")


def build(src: Path, out: Path) -> None:
    # site/skillsbench/index.html is a hand-authored hub page, committed on `main`
    # alongside this script — not part of the skillsbench-history branch content.
    # Preserve it across the rebuild instead of deleting it with everything else.
    hub_file = out / "index.html"
    hub_backup = hub_file.read_bytes() if hub_file.exists() else None

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    if hub_backup is not None:
        hub_file.write_bytes(hub_backup)

    n_md = n_html = n_other = 0
    for f in walk_source(src):
        if f.suffix == ".md":
            convert_markdown(f, src, out)
            n_md += 1
        elif f.suffix == ".html":
            copy_html(f, src, out)
            n_html += 1
        else:
            copy_verbatim(f, src, out)
            n_other += 1

    build_transfer_heatmap(src, out)
    build_runnable43_heatmap(src, out)

    print(f"converted {n_md} .md, rewrote {n_html} .html, copied {n_other} other files")
    print("generated results/transfer-eval-8fold/heatmap.html")
    print("generated results/runnable-43task-opt/heatmap.html")


def check(src: Path, out: Path) -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        fresh = Path(tmp) / "fresh"
        build(src, fresh)
        mismatches = []
        for f in sorted(fresh.rglob("*")):
            if not f.is_file():
                continue
            rel = f.relative_to(fresh)
            other = out / rel
            if not other.exists() or other.read_bytes() != f.read_bytes():
                mismatches.append(str(rel))
        for f in sorted(out.rglob("*")) if out.exists() else []:
            if not f.is_file():
                continue
            rel = f.relative_to(out)
            if str(rel) == "index.html":
                continue  # hand-authored hub page, not generated by this script
            if not (fresh / rel).exists():
                mismatches.append(str(rel) + " (stale, should be removed)")
        if mismatches:
            print(f"STALE: {len(mismatches)} file(s) differ from a fresh build:")
            for m in mismatches[:20]:
                print(f"  {m}")
            return 1
        print("up to date")
        return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", required=True, type=Path, help="skillsbench-history checkout")
    ap.add_argument("--out", required=True, type=Path, help="output dir (e.g. site/skillsbench)")
    ap.add_argument("--check", action="store_true", help="exit non-zero if --out is stale")
    args = ap.parse_args()

    if args.check:
        return check(args.src, args.out)
    build(args.src, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
