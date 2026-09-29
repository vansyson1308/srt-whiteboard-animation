#!/usr/bin/env python3
"""
Print your channel name on the marker barrel of the drawing hand.

  python brand_hand.py "Tên Kênh" assets/my-hand.png [--color "#1f1f1f"]

Then set  "render": {"hand": "path/to/my-hand.png"}  in video.json.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stream_render as sr  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CLEAN_HAND = ROOT / "assets" / "drawing-hand-clean.png"
FONT = ROOT / "assets" / "fonts" / "BeVietnamPro-ExtraBold.ttf"


def barrel_mask(rgba: np.ndarray) -> np.ndarray:
    """The white visible part of the marker barrel (largest near-white blob)."""
    bgr = rgba[:, :, :3]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    white = ((hsv[:, :, 2] > 215) & (hsv[:, :, 1] < 40) & (rgba[:, :, 3] > 200)).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(white)
    if n < 2:
        raise RuntimeError("could not find the marker barrel")
    big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    return (lab == big).astype(np.uint8)


def brand(text: str, out: str | Path, color: str = "#1f1f1f", hand: Path = CLEAN_HAND) -> Path:
    rgba = sr._imread_any(hand, cv2.IMREAD_UNCHANGED)
    mask = barrel_mask(rgba)
    pts = np.argwhere(mask > 0)[:, ::-1].astype(np.float32)
    (cx, cy), (w, h), ang = cv2.minAreaRect(pts)
    length, thick = max(w, h), min(w, h)
    # direction of the long axis in degrees (image coordinates, y down)
    axis = ang if w >= h else ang + 90
    size = int(thick * 0.62)
    font = ImageFont.truetype(str(FONT), size)
    d = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    tw = d.textlength(text, font=font)
    while tw > length * 0.8 and size > 10:
        size -= 2
        font = ImageFont.truetype(str(FONT), size)
        tw = d.textlength(text, font=font)
    rgb = tuple(int(color.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    pad = size
    layer = Image.new("RGBA", (int(tw) + 2 * pad, size * 2 + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((pad, pad + size * 0.35), text, font=font, fill=(*rgb, 255))
    layer = layer.rotate(-axis, expand=True, resample=Image.BICUBIC)
    canvas = Image.new("RGBA", (rgba.shape[1], rgba.shape[0]), (0, 0, 0, 0))
    canvas.paste(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)), layer)
    txt = np.asarray(canvas).astype(np.float32)
    inner = cv2.erode(mask, np.ones((7, 7), np.uint8)).astype(np.float32)
    a = txt[:, :, 3:4] / 255.0 * inner[:, :, None]
    out_img = rgba.copy().astype(np.float32)
    out_img[:, :, :3] = out_img[:, :, :3] * (1 - a) + txt[:, :, 2::-1] * a
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sr._imwrite_any(out, out_img.astype(np.uint8))
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Put a channel name on the drawing hand's marker")
    p.add_argument("text")
    p.add_argument("out")
    p.add_argument("--color", default="#1f1f1f")
    a = p.parse_args(argv)
    out = brand(a.text, a.out, a.color)
    print(f"OUTPUT={out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
