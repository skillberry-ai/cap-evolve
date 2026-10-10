# Merging complementary branches

Digest `merge_opps` lists tip pairs whose wins are on different tasks. Merging is the cheap route to a big effect.

    python "$A/act.py" merge A B --tag M --run-dir "$R" --project "$P"
    python "$A/act.py" probe M --auto --run-dir "$R" --project "$P"
    python "$A/act.py" promote M --run-dir "$R" --project "$P"

`merge` folds files n-way (per function for code), reports interaction risk and the probe price, records a
merge node. A clean textual fold proves nothing: composition is empirical, so probe M on the union of the
parents' win-tasks plus their regressions. Only cells the ledger lacks run, so a merge of two probed
branches is cheap. Same function edited by both: keep the higher-posterior branch, say so in JOURNAL.md.
`smart_merge` off: `merge` refuses; use `merge_search.py --run-dir "$R" --project "$P" --base BEST --survivors a,b`.
