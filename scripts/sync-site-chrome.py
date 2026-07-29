#!/usr/bin/env python3
"""Single source of truth for the cap-evolve site's shared chrome.

The site/ directory is shipped to GitHub Pages verbatim (no build step for
site/ itself), so this script does NOT generate HTML at request time or at
deploy time — it *rewrites the committed HTML in place*. Chrome lives here,
once; the 9 pages stay complete static documents that work with JS disabled
and are fully crawlable.

    scripts/sync-site-chrome.py            # rewrite site/*.html from PAGES below
    scripts/sync-site-chrome.py --check    # exit 1 if any page is out of sync (CI)

Editing the nav, the footer, the <head> block, or a page's meta description
means editing THIS file and re-running it. Never hand-edit the chrome in a
page; the next sync overwrites it.

The ?v= cache-buster is derived from the sha256 of the asset it points at, so
it can no longer be forgotten (it was, once — issue #87).
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent / "site"
BASE = "https://skillberry-ai.github.io/cap-evolve/"
OG_IMAGE = BASE + "assets/dashboard.png"

# ── per-page content (the ONLY per-page difference) ────────────────────────
# title:  <title> and og:title / twitter:title — one string, cannot drift
# desc:   meta description + og:description + twitter:description — likewise
# nav:    which nav link gets .active ("" = none, e.g. pages not in the nav)
# canon:  path under BASE ("" for the home page)
PAGES: dict[str, dict[str, str]] = {
    "index.html": {
        "title": "cap-evolve — Optimize agentic capabilities, with agents",
        "desc": "cap-evolve improves an AI agent's prompts, tools, and skills by learning "
        "from failed evaluation traces. Bring your agent and eval; cap-evolve runs the "
        "loop and reports one honest number.",
        "og_type": "website",
        "canon": "",
        "nav": "",
    },
    "getting-started.html": {
        "title": "Getting started — cap-evolve",
        "desc": "Your first successful cap-evolve run, in two minutes, with no API key. "
        "Clone, install the core, run the toy_calc example, open the dashboard.",
        "og_type": "article",
        "canon": "getting-started.html",
        "nav": "getting-started.html",
    },
    "run-end-to-end.html": {
        "title": "Run end-to-end — cap-evolve",
        "desc": "Take a real benchmark (τ²-bench airline) from a single prompt to an "
        "honest, sealed result — baseline 0.536 → 0.712 — with every claim backed by a "
        "committed artifact you can open offline.",
        "og_type": "article",
        "canon": "run-end-to-end.html",
        "nav": "run-end-to-end.html",
    },
    "results.html": {
        "title": "Results — cap-evolve",
        "desc": "Full benchmark results for cap-evolve — toy_calc, τ²-bench airline "
        "(fit-metric + held-out), SkillsBench. Every number cross-checked against "
        "committed run artifacts.",
        "og_type": "article",
        "canon": "results.html",
        "nav": "results.html",
    },
    "benchmarks.html": {
        "title": "Benchmark runs — cap-evolve",
        "desc": "Every ci/benchmarks execution (tau2 · swebench · skillsbench), on PRs "
        "and manual runs — a sortable, filterable log of reward, eval/optimizer cost, and "
        "models, each measured against that run's own freshly-computed baseline.",
        "og_type": "article",
        "canon": "benchmarks.html",
        "nav": "benchmarks.html",
    },
    "architecture.html": {
        "title": "Architecture — cap-evolve",
        "desc": "The cap-evolve pipeline (intake → check → baseline → algorithm → "
        "finalize → report), the optimizer context assembled each iteration, and the "
        "skill library.",
        "og_type": "article",
        "canon": "architecture.html",
        "nav": "architecture.html",
    },
    "optimize-your-own.html": {
        "title": "Optimize your own agent — cap-evolve",
        "desc": "Wire one small adapter — three methods — to optimize your own "
        "capability against your benchmark. Two ways: let your coding agent build it, or "
        "drive the cap-evolve CLI yourself.",
        "og_type": "article",
        "canon": "optimize-your-own.html",
        "nav": "",
    },
    "agent-orchestration.html": {
        "title": "Agent orchestration — cap-evolve",
        "desc": "Two orchestration modes (deterministic vs agent) and the agent-optimize "
        "algorithm: the conversational agent drives the whole optimization loop itself, "
        "honestly, sealing the test once.",
        "og_type": "article",
        "canon": "agent-orchestration.html",
        "nav": "agent-orchestration.html",
    },
    "adapter-templates.html": {
        "title": "Adapter templates — cap-evolve",
        "desc": "Copy-and-run cap-evolve adapter templates — JSONL, HuggingFace, "
        "tau2-bench, SWE-bench, SkillsBench — that work with any litellm provider. "
        "Onboarding a benchmark is config, not code.",
        "og_type": "article",
        "canon": "adapter-templates.html",
        "nav": "",
    },
}

NAV_LINKS = [
    ("getting-started.html", "Get started"),
    ("run-end-to-end.html", "Run end-to-end"),
    ("results.html", "Results"),
    ("benchmarks.html", "Benchmarks"),
    ("architecture.html", "Architecture"),
    ("agent-orchestration.html", "Agent mode"),
]

GITHUB = "https://github.com/skillberry-ai/cap-evolve"

MOON = (
    '<svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>'
)
SUN = (
    '<svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.9 4.9l1.4 '
    '1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"></path></svg>'
)
# Two whole icons swapped by CSS on [aria-expanded] — simpler and more robust
# than rotating the bars into an X (zero-height <path> bboxes make
# transform-origin unreliable across engines).
BURGER = (
    '<svg class="icon-burger" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" aria-hidden="true">'
    '<path d="M4 7h16M4 12h16M4 17h16"></path></svg>'
    '<svg class="icon-close" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" aria-hidden="true">'
    '<path d="M6 6l12 12M18 6L6 18"></path></svg>'
)


def cachebust(rel: str) -> str:
    """?v=<sha256[:8]> of the asset — so the buster cannot be forgotten."""
    digest = hashlib.sha256((SITE / rel).read_bytes()).hexdigest()[:8]
    return f"{rel}?v={digest}"


def head(page: str, meta: dict[str, str]) -> str:
    canonical = BASE + meta["canon"]
    return f"""  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{meta["title"]}</title>
  <meta name="description" content="{meta["desc"]}">
  <link rel="canonical" href="{canonical}">
  <meta property="og:type" content="{meta["og_type"]}">
  <meta property="og:site_name" content="cap-evolve">
  <meta property="og:title" content="{meta["title"]}">
  <meta property="og:description" content="{meta["desc"]}">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="{OG_IMAGE}">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{meta["title"]}">
  <meta name="twitter:description" content="{meta["desc"]}">
  <meta name="twitter:image" content="{OG_IMAGE}">
  <link rel="icon" href="assets/favicon.svg" type="image/svg+xml">
  <link rel="apple-touch-icon" href="assets/apple-touch-icon.png">
  <!-- dark-first: default dark, honor an explicit saved choice. Applied pre-paint (no FOUC) + enables JS-gated reveal -->
  <script>(function(){{try{{document.documentElement.setAttribute('data-theme',localStorage.getItem('capevolve-theme')||'dark');}}catch(e){{document.documentElement.setAttribute('data-theme','dark');}}document.documentElement.classList.add('js');}})();</script>
  <!-- ?v= is the asset's content hash, written by scripts/sync-site-chrome.py -->
  <link rel="stylesheet" href="{cachebust("style.css")}">"""


def nav(meta: dict[str, str]) -> str:
    def link(href: str, label: str) -> str:
        active = ' class="active" aria-current="page"' if href == meta["nav"] else ""
        return f'      <a href="{href}"{active}>{label}</a>'

    links = "\n".join(link(h, l) for h, l in NAV_LINKS)
    return f"""<nav class="nav">
  <div class="nav-inner">
    <a class="nav-brand" href="./"><img src="assets/logo-300.png" alt="" class="nav-brand-logo" aria-hidden="true"><span class="wordmark">cap<span class="wordmark-dot">·</span>evolve</span></a>
    <!-- shown only under the mobile breakpoint, and only when JS is available
         (html.js): without JS the full .nav-links strip stays visible instead. -->
    <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="nav-links" aria-label="Menu">{BURGER}</button>
    <div class="nav-links" id="nav-links">
{links}
      <a class="gh" href="{GITHUB}">GitHub</a>
      <button class="theme-toggle" type="button" aria-label="Switch theme">
        {MOON}
        {SUN}
      </button>
    </div>
  </div>
</nav>"""


FOOTER = f"""<footer class="footer">
  <div class="footer-inner">
    <div>
      <span class="wordmark" style="color:var(--ink);font-size:1.05rem;">cap<span class="wordmark-dot">·</span>evolve</span><br>
      Apache-2.0 · beta (0.x) · <em>Optimize agentic capabilities — with agents</em>
    </div>
    <div class="footer-affil">
      <span>Made at</span>
      <span class="footer-affil-logos">
        <img src="assets/ibm-logo.svg" alt="IBM" class="logo-ibm">
        <img src="assets/redhat-logo.svg" alt="Red Hat" class="logo-redhat">
      </span>
    </div>
    <div>
      <a href="{GITHUB}">github.com/skillberry-ai/cap-evolve</a>
    </div>
  </div>
</footer>"""

# Chrome regions, matched on their own stable boundaries — no marker comments to
# hand-maintain, and a page can't silently fall out of the sync (a miss raises).
HEAD_RE = re.compile(r"(?<=<head>\n).*?(?=\n</head>)", re.S)
NAV_RE = re.compile(r"<nav class=\"nav\">.*?</nav>", re.S)
FOOTER_RE = re.compile(r"<footer class=\"footer\">.*?</footer>", re.S)
SCRIPT_RE = re.compile(r'<script src="(js/site\.js|benchmarks\.js)\?v=[^"]*"')


def render(page: str, text: str) -> str:
    meta = PAGES[page]
    for name, pattern, repl in (
        ("head", HEAD_RE, head(page, meta)),
        ("nav", NAV_RE, nav(meta)),
        ("footer", FOOTER_RE, FOOTER),
    ):
        text, n = pattern.subn(lambda _m, r=repl: r, text, count=1)
        if n != 1:
            raise SystemExit(f"{page}: could not locate the {name} region")
    text = SCRIPT_RE.sub(lambda m: f'<script src="{cachebust(m.group(1))}"', text)
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="report drift, write nothing")
    args = ap.parse_args()

    stale = []
    for page in PAGES:
        path = SITE / page
        before = path.read_text(encoding="utf-8")
        after = render(page, before)
        if before == after:
            continue
        stale.append(page)
        if not args.check:
            path.write_text(after, encoding="utf-8")

    if args.check:
        if stale:
            print("site chrome out of sync: " + ", ".join(stale))
            print("run: scripts/sync-site-chrome.py")
            return 1
        print(f"site chrome in sync ({len(PAGES)} pages)")
        return 0
    print(f"synced {len(stale)}/{len(PAGES)} pages" + (f": {', '.join(stale)}" if stale else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
