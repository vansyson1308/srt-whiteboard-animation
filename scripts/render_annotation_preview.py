#!/usr/bin/env python3
"""
Annotation check image: numbered region boxes, labels, timing and `say`
phrases drawn over the source image - quick visual QA for humans and agents.

Usage:
  python render_annotation_preview.py <image> <annotation.json> <preview.jpg>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONT_CANDIDATES = [
    ROOT / "assets" / "fonts" / "BeVietnamPro-ExtraBold.ttf",
    Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/msyh.ttc"),
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]
COLORS = [(38, 103, 255), (230, 80, 60), (30, 150, 90), (160, 80, 230), (230, 140, 20), (20, 150, 170)]


def load_font(size: int) -> ImageFont.ImageFont:
    for f in FONT_CANDIDATES:
        if f.exists():
            try:
                return ImageFont.truetype(str(f), size)
            except OSError:
                continue
    return ImageFont.load_default()


def main(image_path: str, annotation_path: str, output_path: str) -> None:
    image = Image.open(image_path).convert("RGBA")
    data = json.loads(Path(annotation_path).read_text(encoding="utf-8"))
    cw = data.get("canvas", {}).get("width") or image.width
    sx = image.width / cw
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    fs = max(14, int(image.width / 70))
    font, small = load_font(fs), load_font(int(fs * 0.75))
    els = sorted(data["elements"], key=lambda e: (e["reveal"]["startMs"], e.get("sequence", 0)))
    for index, el in enumerate(els, start=1):
        r = el["region"]
        x, y = r["x"] * sx, r["y"] * sx
        right, bottom = x + r["width"] * sx, y + r["height"] * sx
        c = COLORS[(index - 1) % len(COLORS)]
        draw.rounded_rectangle((x, y, right, bottom), radius=10, outline=(*c, 230), width=max(2, fs // 6),
                               fill=(*c, 22))
        for p in el.get("reveal", {}).get("protectedRegions", []) or []:
            px, py = p["x"] * sx, p["y"] * sx
            draw.rectangle((px, py, px + p["width"] * sx, py + p["height"] * sx), outline=(0, 0, 0, 200), width=2)
        rv = el["reveal"]
        label = f"{index}. {el.get('label', el.get('id', ''))}  {rv['startMs'] / 1000:.1f}s+{rv['durationMs'] / 1000:.1f}s"
        tb = draw.textbbox((0, 0), label, font=font)
        draw.rounded_rectangle((x + 6, y + 6, x + 18 + tb[2], y + 14 + tb[3]), radius=6, fill=(255, 255, 255, 230))
        draw.text((x + 12, y + 8), label, font=font, fill=(*c, 255))
        say = el.get("say")
        if say:
            draw.text((x + 12, y + 18 + tb[3]), f"say: {say}", font=small, fill=(*c, 255))
    result = Image.alpha_composite(image, overlay).convert("RGB")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    result.save(output_path, quality=92)
    print(f"OUTPUT={Path(output_path).resolve()}")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    main(*sys.argv[1:4])
