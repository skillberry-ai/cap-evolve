# What the numbers can resolve

- One full-val mean (30 tasks x 3 trials): sd ~0.05 (digest `noise.sd_est`, from identical-bytes repeat
  cells). Resolvable: gains >= ~0.10, or many-task gains with paired evidence. +0.02 is not a result.
- A single-task edit has ceiling 1/n_tasks (~0.03): below noise by construction.
- Never re-test a within-noise delta hoping it grows; that is regression to the mean.
- Per-task rates from 3 trials are a search signal, not proof of a fix.
- Paired comparisons (same task x trial cells) beat unpaired means.
- Sign test: count tasks up vs down between two candidates; a mean gain carried by one big mover is that
  one task, not the edit. Few net movers with an even split is noise.
- Small effects count only when two independently seeded blocks agree in sign; otherwise say "not resolvable".
- Val is development-exposed by repeated gating. Test is sealed, scored ONCE at finalize, never viewed before
  and development-exposed after. No second finalize (TestSealError).
- Timeouts and infra errors are missing data, not 0.0: low coverage is indecisive, not a score.
