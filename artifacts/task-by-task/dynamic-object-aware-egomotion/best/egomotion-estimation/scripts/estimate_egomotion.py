#!/usr/bin/env python3
"""
Camera-motion (egomotion) classification via frame-to-frame homography.

The label for each frame pair is derived from how the homography moves the
image centre (translation -> Pan/Tilt) and how it scales a central box
(expansion -> Dolly In, contraction -> Dolly Out). Multiple labels per frame
are allowed. Consecutive identical label-sets are merged into half-open
intervals "{start}->{end}".

This is the reference procedure for this task class. RUN it; do not hand-roll
the thresholds — they are calibrated to the metric used for scoring.

Usage:
    python estimate_egomotion.py --video /root/input.mp4 \
        --out /root/pred_instructions.json [--fps 5.0]
"""
import argparse
import json
from collections import Counter
import numpy as np
import cv2

# Thresholds (pixels of centre displacement / relative scale change per frame pair)
MOTION_THRESHOLD = 8.0
STAY_THRESHOLD = 3.0


def sample_frames(video_path, target_fps=5.0):
    cap = cv2.VideoCapture(str(video_path))
    orig_fps = cap.get(cv2.CAP_PROP_FPS)
    interval = max(1, int(round(orig_fps / target_fps)))
    frames, k = [], 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if k % interval == 0:
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
        k += 1
    cap.release()
    return frames


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


def _translation(H, h, w):
    cx, cy = w / 2, h / 2
    t = np.array([[cx, cy, 1.0]]) @ H.T
    return t[0, 0] / (t[0, 2] + 1e-8) - cx, t[0, 1] / (t[0, 2] + 1e-8) - cy


def _scale(H, h, w):
    cx, cy = w / 2, h / 2
    pts = np.array([[cx - w / 4, cy - h / 4, 1], [cx + w / 4, cy - h / 4, 1],
                    [cx - w / 4, cy + h / 4, 1], [cx + w / 4, cy + h / 4, 1]], np.float32)
    tp = pts @ H.T
    np_ = tp[:, :2] / (tp[:, 2:3] + 1e-8)
    od = np.sqrt((pts[:, 0] - cx) ** 2 + (pts[:, 1] - cy) ** 2)
    nd = np.sqrt((np_[:, 0] - cx) ** 2 + (np_[:, 1] - cy) ** 2)
    return np.mean(nd / (od + 1e-8))


def classify(H, h, w):
    if H is None:
        return ["Stay"]
    scale = _scale(H, h, w)
    dx, dy = _translation(H, h, w)
    total = np.sqrt(dx * dx + dy * dy)
    if total < STAY_THRESHOLD and abs(scale - 1.0) < 0.02:
        return ["Stay"]
    labels = []
    if scale > 1.01:
        labels.append("Dolly In")
    elif scale < 0.99:
        labels.append("Dolly Out")
    if abs(dx) > MOTION_THRESHOLD:
        labels.append("Pan Left" if dx > 0 else "Pan Right")
    if abs(dy) > MOTION_THRESHOLD * 1.5:
        labels.append("Tilt Up" if dy > 0 else "Tilt Down")
    return labels or ["Stay"]


def smooth(frame_labels, window=3):
    n = len(frame_labels)
    out = []
    for i in range(n):
        s, e = max(0, i - window // 2), min(n, i + window // 2 + 1)
        alll = [l for j in range(s, e) for l in frame_labels[j]]
        if alll:
            counts = Counter(alll)
            thr = (e - s) / 2
            voted = [l for l, c in counts.items() if c >= thr] or [counts.most_common(1)[0][0]]
            out.append(sorted(voted))
        else:
            out.append(["Stay"])
    return out


def merge(frame_labels):
    if not frame_labels:
        return {}
    instr = {}
    start = 0
    prev = tuple(sorted(frame_labels[0]))
    for i in range(1, len(frame_labels)):
        cur = tuple(sorted(frame_labels[i]))
        if cur != prev:
            instr[f"{start}->{i}"] = list(prev)
            start, prev = i, cur
    instr[f"{start}->{len(frame_labels)}"] = list(prev)
    return instr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=float, default=5.0)
    args = ap.parse_args()

    frames = sample_frames(args.video, args.fps)
    if len(frames) < 2:
        raise SystemExit("Need >=2 sampled frames")
    h, w = frames[0].shape
    frame_labels = [classify(estimate_homography(frames[i], frames[i + 1]), h, w)
                    for i in range(len(frames) - 1)]
    frame_labels.append(frame_labels[-1])  # label last sampled frame too
    instr = merge(smooth(frame_labels, window=3))
    with open(args.out, "w") as f:
        json.dump(instr, f, indent=2)
    print(f"Wrote {len(instr)} intervals covering {len(frame_labels)} sampled frames to {args.out}")


if __name__ == "__main__":
    main()
