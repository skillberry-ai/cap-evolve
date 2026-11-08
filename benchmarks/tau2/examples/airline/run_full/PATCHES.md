# Post-run patches to this artifact

This directory is the committed output of the tau2-airline run (53.6% -> 71.2%).
It is served as live UI (`README.md:173` tells users to `python3 -m http.server`
here), so presentation-only fixes are applied in place rather than left broken.
Every such edit is recorded below. **No result data has ever been modified** —
all JSON under `ui/data/`, `final.json`, and `demo.cast` are byte-identical to
what the run produced.

| Date | File | Change | Issue |
|---|---|---|---|
| 2026-07-30 | `ui/assets/index-vwBf6wRK.css` | Removed the Google Fonts CDN `@import` and replaced the `Fira Sans`/`Fira Code` font-family values with system stacks, so the snapshot renders offline/air-gapped. Presentation only. | #120 (PR #192) |
