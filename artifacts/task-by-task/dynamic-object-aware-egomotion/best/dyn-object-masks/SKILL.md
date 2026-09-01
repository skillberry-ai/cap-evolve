---
name: dyn-object-masks
description: "Generate dynamic-object binary masks from video with camera motion, output per-frame CSR sparse masks."
---

# When to use
- Detect moving objects in scenes with camera motion; produce one sparse mask per sampled frame.

# Method (read this — the detection principle matters)
A pixel is *dynamic* when its measured optical flow deviates from the flow that the
**global camera motion** (egomotion) alone would produce. So:
1. Estimate the frame-to-frame **homography** (ORB features + RANSAC).
2. Compute **dense optical flow** (Farneback) between the two frames.
3. `deviation = measured_flow − homography_predicted_flow`; large deviation = dynamic pixel.
4. Down-weight the ground plane / near edges (parallax there mimics motion), threshold on
   the deviation's std, clean with morphology, keep components above a small area.

**Do NOT use plain frame differencing** (`abs(curr − warped_prev)`): with real camera
motion it fires on static texture and parallax and misses the object — it scores near-zero
IoU against the ground truth, which is defined by the flow-deviation method above.

# Run the bundled detector (do this — do not reimplement)
The detector is provided and calibrated to the scoring metric. Execute it:

```bash
python scripts/detect_dynamic_masks.py --video /root/input.mp4 --out /root/pred_dyn_masks.npz --fps 5.0
```

It samples at the requested fps, produces **exactly one mask per sampled frame** (the last
frame reuses the previous mask so mask count == sampled-frame count), and writes the CSR
`.npz`. Optional flags: `--thr-mult` (default 2.0; lower = more sensitive), `--min-area-frac`
(default 0.0005), `--dilate` (default 0). Only tune these if masks are clearly too sparse or
too noisy against a sanity check.

# CSR encoding (what the script writes; verifier expects this exactly)
- `shape` = `[H, W]` int32.
- Per frame `i`: `f_{i}_data` (bool ones), `f_{i}_indices` (int32 True-column indices),
  `f_{i}_indptr` (int32, `len == H+1`, `indptr[-1] == indices.size`).

# Self-check
- [ ] One mask per sampled frame; count matches the sampled-frame count.
- [ ] `shape` stored as `[H, W]`; `len(indptr)==H+1`; `indptr[-1]==indices.size`; indices in `[0,W)`.
- [ ] Masks come from flow-deviation vs the homography, NOT frame differencing.
- [ ] Border fill not treated as foreground.
