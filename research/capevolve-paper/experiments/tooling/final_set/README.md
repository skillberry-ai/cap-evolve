Scripts that produced `protocol/final_set/*` (zero LLM; host-specific paths at the top of each script).
`build_912_pool.py` builds the SpreadsheetBench-912 residual pool manifest. `pop_check.py` is the gold-as-output ceiling check.
`sb2_check.py` runs the official SpreadsheetBench-2 scorer on gold/stripped-gold/input outputs; `sb2_adapter_probe.py` tests whether the
CapEvolve adapter can load SB2 and measures first-prompt size.
