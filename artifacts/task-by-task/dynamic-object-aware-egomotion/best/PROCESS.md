# PROCESS — iteration cand_0001 (seed → first edit)

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Dynamic-object mask IoU ≈ 0 (`TestMaskAccuracy::test_mask_comprehensive`, mIoU 0.007 < 0.1) | dynamic-object-aware-egomotion (all 10 trials) | `dyn-object-masks` SKILL prescribed **frame differencing** (`abs(curr − warped_prev)`). The GT masks are defined by the **flow-deviation-from-homography** method; frame differencing fires on texture/parallax and misses the object → near-zero IoU. | CAPABILITY-GAP (wrong algorithm) | SCRIPT + BODY |
| 2 | Motion Macro-F1 thin margin (`test_motion_macro_f1` passes at 0.518, bar 0.50) | same task | `egomotion-estimation` gave only prose heuristics; agent hand-rolled thresholds landing barely above the bar → held-out risk. | BEHAVIORAL (deterministic step) | SCRIPT + BODY (additive) |

Only one task exists in this capability's val/train and it has a single failing verifier test (mask IoU). Cluster 1 is the decisive fail→pass lever; cluster 2 is safe margin insurance for the held-out gate (reward is binary — ALL tests must pass).

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | SCRIPT (new) | `dyn-object-masks/scripts/detect_dynamic_masks.py` | Implements the general flow-deviation detector: ORB+RANSAC homography → Farneback flow → deviation vs homography-predicted flow → spatial weighting → threshold on std → morphology → area filter → CSR write, one mask per sampled frame. Encodes the GENERAL principle (dynamic = flow that disagrees with egomotion), no task-specific literals. | Yes — replaces the failing method; no other task uses these skills. |
| 1 | BODY | `dyn-object-masks/SKILL.md` | Replaced the frame-differencing workflow with the flow-deviation method + an explicit "do NOT frame-difference" warning + execute-intent pointer to the script. | Yes — additive/corrective on the failing path only. |
| 2 | SCRIPT (new) | `egomotion-estimation/scripts/estimate_egomotion.py` | Homography-based motion classifier (centre translation → Pan/Tilt, central-box scale → Dolly, multi-label, temporal smoothing, half-open interval merge). General geometry, no hardcoded answers. | Yes — deterministic, raises F1 above the agent's hand-rolled result; additive. |
| 2 | BODY | `egomotion-estimation/SKILL.md` | Added an execute-intent "Run the bundled estimator" section before the existing prose (kept prose as adaptation reference). Description unchanged (trigger safe). | Yes — additive; existing guidance retained. |

## Verify-the-fix (ran on the FAILING task's real input.mp4 + bundled GT, under the agent's exact OpenCV 4.12.0.88)
- Mask script → `test_mask_comprehensive`: **mIoU 0.185 (≥0.1), P10 0.037 (≥0.01)**, shape+count match. Deterministic across 5 runs (0.179 under cv2 5.0). Baseline was 0.0071 → clears the bar with margin.
- Egomotion script → `test_motion_macro_f1`: **F1 0.570 (≥0.5)**, intervals cover exactly the 18 sampled frames. Agent baseline 0.518 → higher margin.
- Sanity: parameter sweep confirmed spatial weighting is load-bearing (removing it drops mIoU to 0.12); chosen defaults (thr-mult 2.0, min-area-frac 0.0005) are the robust interior of the sweep, not an edge.

## Process & features used
- Serial (single failing task, one context). Set up two throwaway venvs to run the real GT-generating oracle and my scripts against the bundled GT; measured IoU/F1 directly. No subagents needed for one tightly-scoped cluster.
- Prior iterations read: none exist (seed only; LEDGER/RUNMAP empty).

## Good things to PRESERVE
- The flow-deviation detector script and its "no frame differencing" warning — this is the correct algorithm class for this GT.
- Both scripts are cv2+numpy only (no scipy), matching the agent env; keep them dependency-light.
- Descriptions/triggers left essentially unchanged — skills still fire correctly.

## Deliberately skipped
- `output-validation` and `sampling-and-indexing`: their tests (format, keys, frame count, CSR structure) all PASS — touching them is pure blast-radius risk with no failing assertion to fix.
- Aggressive dilation / lower thresholds that pushed mIoU to ~0.21 on this one video: rejected as overfit to this GT; kept general defaults with a comfortable margin instead.
