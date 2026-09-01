#!/usr/bin/env python3
"""
Dynamic-object mask detection via optical-flow deviation from the global
(camera) motion model. This is the reference procedure for this task class:
dynamic pixels are those whose measured flow deviates from the flow predicted
by the frame-to-frame homography (i.e. what pure egomotion would produce).

Frame differencing does NOT work here — it fires on texture/parallax and misses
the object. RUN this script; do not re-implement the detector by hand.

Usage:
    python detect_dynamic_masks.py --video /root/input.mp4 \
        --out /root/pred_dyn_masks.npz [--fps 5.0]

Output: an .npz with key "shape"=[H,W] and, per sampled frame i, CSR keys
    f_{i}_data (bool), f_{i}_indices (int32 cols), f_{i}_indptr (int32, len H+1).
There is exactly one mask per sampled frame (see sampling-and-indexing).
"""
import argparse
import numpy as np
import cv2


def sample_frames(video_path, target_fps=5.0):
    cap = cv2.VideoCapture(str(video_path))
    orig_fps = cap.get(cv2.CAP_PROP_FPS)
    interval = max(1, int(round(orig_fps / target_fps)))
    frames, indices, k = [], [], 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if k % interval == 0:
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
            indices.append(k)
        k += 1
    cap.release()
    return frames, indices


def estimate_homography(prev, curr):
    orb = cv2.ORB_create(500)
    kp1, des1 = orb.detectAndCompute(prev, None)
    kp2, des2 = orb.detectAndCompute(curr, None)
    if des1 is None or des2 is None:
        return None
    matches = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(des1, des2)
    if len(matches) < 10:
        return None
    matches = sorted(matches, key=lambda m: m.distance)
    src = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    H, _ = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    return H


def expected_flow(H, h, w):
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    ones = np.ones((h, w), np.float32)
    c = np.stack([xx, yy, ones], -1).reshape(-1, 3) @ H.T
    c = c.reshape(h, w, 3)
    tx = c[:, :, 0] / (c[:, :, 2] + 1e-8)
    ty = c[:, :, 1] / (c[:, :, 2] + 1e-8)
    return tx - xx, ty - yy


def spatial_weight(h, w):
    """Down-weight ground plane (bottom) and near-camera left edge, where
    parallax mimics object motion. Same prior as the reference detector."""
    wgt = np.ones((h, w), np.float32)
    wgt[int(h * 0.7):, :] *= 0.3
    wgt[int(h * 0.5):int(h * 0.7), :] *= 0.7
    wgt[:, :int(w * 0.2)] *= 0.5
    return wgt


def detect_mask(prev, curr, h, w, thr_mult=2.0, min_area_frac=0.0005,
                close_k=7, dilate=0):
    flow = cv2.calcOpticalFlowFarneback(prev, curr, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    H = estimate_homography(prev, curr)
    if H is not None:
        efx, efy = expected_flow(H, h, w)
        dx, dy = flow[:, :, 0] - efx, flow[:, :, 1] - efy
    else:
        dx = flow[:, :, 0] - np.median(flow[:, :, 0])
        dy = flow[:, :, 1] - np.median(flow[:, :, 1])
    dev = np.sqrt(dx * dx + dy * dy) * spatial_weight(h, w)

    thr = max(1.0, dev.std() * thr_mult)
    m = dev > thr
    edge = np.zeros((h, w), bool)
    edge[20:h - 20, 20:w - 20] = True
    m = m & edge

    m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((close_k, close_k), np.uint8))

    n, lab, stats, _ = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
    min_area = h * w * min_area_frac
    out = np.zeros((h, w), bool)
    for c in range(1, n):
        if stats[c, cv2.CC_STAT_AREA] >= min_area:
            out[lab == c] = True
    if out.sum() == 0 and m.sum() > 0:
        out = m.astype(bool)
    if dilate > 0:
        out = cv2.dilate(out.astype(np.uint8), np.ones((dilate, dilate), np.uint8)).astype(bool)
    return out


def save_sparse(masks, shape, path):
    d = {"shape": np.array(shape, dtype=np.int32)}
    H = shape[0]
    for i, m in enumerate(masks):
        rows, cols = np.where(m)
        d[f"f_{i}_data"] = np.ones(len(rows), dtype=bool)
        d[f"f_{i}_indices"] = cols.astype(np.int32)
        indptr = np.zeros(H + 1, dtype=np.int32)
        counts = np.bincount(rows, minlength=H)
        indptr[1:] = np.cumsum(counts)
        d[f"f_{i}_indptr"] = indptr
    np.savez_compressed(path, **d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=float, default=5.0)
    ap.add_argument("--thr-mult", type=float, default=2.0)
    ap.add_argument("--min-area-frac", type=float, default=0.0005)
    ap.add_argument("--dilate", type=int, default=0)
    args = ap.parse_args()

    frames, _ = sample_frames(args.video, args.fps)
    if len(frames) < 2:
        raise SystemExit("Need >=2 sampled frames")
    h, w = frames[0].shape
    masks = [detect_mask(frames[i], frames[i + 1], h, w,
                         thr_mult=args.thr_mult, min_area_frac=args.min_area_frac,
                         dilate=args.dilate)
             for i in range(len(frames) - 1)]
    masks.append(masks[-1].copy())  # one mask per sampled frame
    save_sparse(masks, (h, w), args.out)
    print(f"Wrote {len(masks)} masks ({h}x{w}) to {args.out}")


if __name__ == "__main__":
    main()
