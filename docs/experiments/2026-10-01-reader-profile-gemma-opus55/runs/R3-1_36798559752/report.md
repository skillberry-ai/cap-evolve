## Full_verified_probe suite — spreadsheetbench  (held-out test split)

Agent `ibm-rits/google/gemma-4-31B-it` · optimizer Claude Code `ibm-ete-int/aws/claude-opus-5-5` · 3 iteration(s) · base→opt is the seed vs the best candidate on the **same 100 SEALED test tasks**, which the optimizer never saw (selection happened on a disjoint val split). This is a held-out generalization number.

| bench | task | reward (base→opt) | Δ | note |
|---|---|---|---|:--:|
| spreadsheetbench | `24-23` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `41-47` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `297-42` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `333-29` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `341-40` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `384-4` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `408-5` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `455-35` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `547-18` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `61-4` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `82-38` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `91-34` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `109-21` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `130-9` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `142-19` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `156-14` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `157-4` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `178-22` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `208-20` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `120-24` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `334-11` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `359-21` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `367-23` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `374-18` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `416-27` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `448-11` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `493-5` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `510-3` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `567-21` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `599-9` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `31202` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `38537` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `40478` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `42198` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `42526` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `44389` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `45300` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `47933` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `48608` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `48643` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `48969` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `49036` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `49196` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `49300` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `50324` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `52807` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `52917` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `53167` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `3002` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `3911` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `4714` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `9448` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `13284` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `14240` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `15387` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `16511` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `17111` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `18645` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `31746` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `32562` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `32789` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `33157` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `36191` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `36764` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `37229` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `37554` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `36277` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `39190` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `42930` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `44266` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `44296` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `49857` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `49945` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `50631` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `51556` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `52220` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `52233` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `52305` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `52964` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `53161` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `54474` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `54513` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `54717` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `55085` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `57033` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `42902` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `43213` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `43657` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `44017` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `45937` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `55260` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `55468` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `55708` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `55977` | 1.000 → 0.000 | -1.000 | ↓ |
| spreadsheetbench | `57262` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `57989` | 0.000 → 1.000 | +1.000 |  |
| spreadsheetbench | `58942` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `59639` | 1.000 → 1.000 | +0.000 |  |
| spreadsheetbench | `59734` | 0.000 → 0.000 | +0.000 |  |
| spreadsheetbench | `59794` | 1.000 → 1.000 | +0.000 |  |

**Suite (held-out):** mean reward 0.430 → 0.810 (Δ +0.380 (+88% rel)) · best = `cand_0003` · optimizer $23.02 over 3 iter(s)

### Metrics by candidate and split

| candidate | split | n | `soft_restriction` | `hard_restriction` | `soft_no_recalc` | `hard_no_recalc` |
|---|---|--:|--:|--:|--:|--:|
| seed | val | 40 | 0.6250 | 0.6250 | 0.4500 | 0.4500 |
| seed | test | 100 | 0.5400 | 0.5400 | 0.4300 | 0.4300 |
| best | val | 40 | 0.9500 | 0.9500 | 0.9500 | 0.9500 |
| best | test | 100 | 0.8200 | 0.8200 | 0.8100 | 0.8100 |

### Iterations

| phase | iter | candidate | accepted | reward | traded | optimizer $ | optimizer time | eval $ | eval time |
|---|:--:|---|:--:|---|---|---|---|---|---|
| iterate | 1 | `cand_0001` | ✅ | 0.800 | +16 fixed / -2 broke | $5.8801 | 19m22s | $0.0000 | 8m52s |
| iterate | 2 | `cand_0002` | ✅ | 0.825 | +5 fixed / -4 broke | $9.1407 | 39m55s | $0.0000 | 13m44s |
| iterate | 3 | `cand_0003` | ✅ | 0.950 | +5 fixed / -0 broke | $7.9954 | 31m27s | $0.0000 | 7m19s |
| finalize | — | `cand_0003` | — | 0.810 | — | $0.0000 | 0s | $0.0000 | 25m42s |

> **Accepted candidates that broke a previously-solved val task:** `cand_0001` +16 fixed / -2 broke; `cand_0002` +5 fixed / -4 broke. The gate decides on the MEAN paired Δ, so a net-positive trade is accepted by design — these are the trades it made, not gate failures. Set `gate_max_broke` to veto them instead.

**Totals:** optimizer $23.0163 over 90m44s · eval $0.0000 over 55m36s
