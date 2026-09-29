#!/usr/bin/env python3
"""
QA contact sheet: grab frames from a video at evenly spaced (or given) times and
tile them into one JPG with timestamps, so an agent/human can check a render
without scrubbing through it.  Also reports basic stats (size, fps, duration,
audio, loudness).

Usage:
  python qa_frames.py <video.mp4> <sheet.jpg> [--count 8] [--times 0.5,3,7.2] [--cols 4]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stream_render as sr  # noqa: E402
import wb_video  # noqa: E402


def contact_sheet(video: str, out: str, count: int = 8, times: list[float] | None = None,
                  cols: int = 4, tile_w: int = 480) -> dict:
    info = wb_video.probe_video(video)
    fps, n = info["fps"] or 30, info["frames"]
    dur = n / fps
    if times:
        idx = [min(n - 1, max(0, int(round(t * fps)))) for t in times]
    else:
        idx = [int(round(i * (n - 1) / max(1, count - 1))) for i in range(count)]
    want = {i: None for i in idx}
    for i, f in enumerate(wb_video.iter_frames(video)):
        if i in want:
            want[i] = f
        if i >= max(idx):
            break
    tiles = []
    for i in idx:
        f = want[i]
        if f is None:
            continue
        th = int(tile_w * f.shape[0] / f.shape[1])
        t = cv2.resize(f, (tile_w, th), interpolation=cv2.INTER_AREA)
        label = f"{i / fps:6.2f}s"
        cv2.rectangle(t, (0, 0), (110, 28), (0, 0, 0), -1)
        cv2.putText(t, label, (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(t)
    rows = []
    for r in range(0, len(tiles), cols):
        row = tiles[r:r + cols]
        while len(row) < cols:
            row.append(np.zeros_like(tiles[0]))
        rows.append(np.hstack(row))
    sheet = np.vstack(rows)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    sr._imwrite_any(out, sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
    report = {"video": str(video), "width": info["width"], "height": info["height"], "fps": fps,
              "frames": n, "durationSec": round(dur, 3), "hasAudio": info["has_audio"], "sheet": out}
    if info["has_audio"]:
        a = wb_video.load_audio(video)
        report["audioSec"] = round(len(a) / wb_video.SAMPLE_RATE, 3)
        report["loudnessLUFS"] = round(wb_video.loudness_lufs(a), 1)
        report["peakDb"] = round(20 * np.log10(max(1e-9, float(np.max(np.abs(a))))), 1) if len(a) else None
    return report


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Video QA contact sheet")
    p.add_argument("video")
    p.add_argument("sheet")
    p.add_argument("--count", type=int, default=8)
    p.add_argument("--times", default=None, help="comma separated seconds")
    p.add_argument("--cols", type=int, default=4)
    p.add_argument("--tile-w", type=int, default=480)
    a = p.parse_args(argv)
    times = [float(x) for x in a.times.split(",")] if a.times else None
    print(json.dumps(contact_sheet(a.video, a.sheet, a.count, times, a.cols, a.tile_w), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
