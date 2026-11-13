# Backup profile: `rh-swebench` (retired) — Harbor on SWE-bench Verified

Shared values from core: [`_core.md`](_core.md). Format and how to create or correct a profile: `docs/BACKUP_BOX.md` Appendix B. Status: see [`INDEX.md`](INDEX.md).

Values as [`swebench-verified-harbor.md`](swebench-verified-harbor.md) (`swebench-verified-harbor`), except:

| Key | Value |
|---|---|
| Bench names | `rh-swebench`; runs `manual__full-rh-swebench-v4` and `manual__full-rh-swebench-v4__full-rh-swebench` (`<setting>` = `v4`). |
| Reward | resolved, on 119 SWE-bench Verified tasks. The published result is val, **a fit metric** (`results/rh-swe-bench-image-and-reorder` README: 0.580 → 0.765). |
| Capability | skill package + system prompt |
| Models | agent `claude-sonnet-4-6`, optimizer `claude-opus-4-6` (record). |
| Cost | `eval_usd` 0 in the record: unknown, not $0 (`zero_means: unknown`). |
| Sources | `benchmark-history` `runs/manual__full-rh-swebench-v4*/ui` (UI exports, `compare_ids_*`), `records/manual__full-rh-swebench-v4.json`; branch `results/rh-swe-bench-image-and-reorder` (`site/results.html`, `site/assets/rh_swe_bench.png`). Owner: `avalappi`. The full run dir is on the owner's machine (`may_exist_at`). |

Runs `200`, `201`, `202__full-swebench-verified` (bench name `swebench-verified`; `ui/` only; made in
`/private/tmp/ce-runs/s<k>/run_suite` by `avalappi`) are profiled as `swebench-verified-harbor`
([`swebench-verified-harbor.md`](swebench-verified-harbor.md)), with `<replicate>` = `s<k>`. Their adapter at the run's commit is confirmed at the first
backup.
