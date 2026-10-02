#!/usr/bin/env python3
"""
Contact sheets of a project's SVG scenes: every scene drawn complete, 12 to a page with its
number, so the whole storyboard can be checked at a glance (overlaps, text running off the
frame, empty corners) before any audio or video is made.

Usage:
  python scene_sheet.py <project dir> [--out-dir DIR] [--scenes 3,7,12] [--per-page 12] [--safe]

``--safe`` outlines the 90 % title-safe area (broadcast).  Prints ``OUTPUT=<sheet>`` per page.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from svg_scene import render_svg  # noqa: E402

W, H, COLS = 800, 450, 3


def sheets(project: Path, out_dir: Path, scenes: list[int] | None = None, per_page: int = 12,
           safe: bool = False) -> list[Path]:
    files = sorted((project / "scenes").glob("scene-*.svg"))
    if scenes:
        files = [f for f in files if int(f.stem.split("-")[-1]) in scenes]
    out_dir.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default(size=36)
    pages = []
    for p0 in range(0, len(files), per_page):
        batch = files[p0:p0 + per_page]
        rows = (len(batch) + COLS - 1) // COLS
        sheet = Image.new("RGB", (COLS * W, rows * H), "white")
        d = ImageDraw.Draw(sheet)
        for k, f in enumerate(batch):
            im = render_svg(f.read_text(encoding="utf-8"), W, H, "#ffffff")
            im = im if isinstance(im, Image.Image) else Image.fromarray(np.asarray(im))
            x, y = (k % COLS) * W, (k // COLS) * H
            sheet.paste(im.convert("RGB"), (x, y))
            d.rectangle([x, y, x + W - 1, y + H - 1], outline="#cccccc")
            if safe:
                d.rectangle([x + W // 20, y + H // 20, x + W - W // 20, y + H - H // 20], outline="#ffb0b0")
            d.text((x + 8, y + 6), f.stem.split("-")[-1], fill="red", font=font)
        out = out_dir / f"sheet-{p0 // per_page + 1}.png"
        sheet.save(out)
        pages.append(out)
    return pages


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="contact sheets of a project's SVG scenes")
    p.add_argument("project")
    p.add_argument("--out-dir", default=None, help="default: <project>/build/sheets")
    p.add_argument("--scenes", default=None, help="comma-separated scene numbers")
    p.add_argument("--per-page", type=int, default=12)
    p.add_argument("--safe", action="store_true", help="outline the 90%% title-safe area")
    a = p.parse_args(argv)
    project = Path(a.project)
    nums = [int(x) for x in a.scenes.split(",")] if a.scenes else None
    pages = sheets(project, Path(a.out_dir) if a.out_dir else project / "build" / "sheets", nums, a.per_page, a.safe)
    for page in pages:
        print(f"OUTPUT={page.resolve()}")
    return 0 if pages else 1


if __name__ == "__main__":
    sys.exit(main())
