#!/usr/bin/env python3
"""
SVG scene -> PNG + annotation.json with real vector pen strokes.

This is the agent-native way to make scenes: Claude Code / Codex write the
illustration as SVG (no image API needed), and this script turns it into the
same ``<name>.png`` + ``<name>.annotation.json`` pair the renderer uses - but
with exact regions and the true stroke order of every path, so the hand
traces the drawing like a real person.

SVG conventions (see docs/SVG_GUIDE.md):
  * every top-level ``<g id="...">`` is one drawing element, drawn in document order
  * optional attributes on that ``<g>``:
      data-label="Mặt trời"          human readable name
      data-say="mặt trời"            phrase in the narration that triggers drawing it
      data-role="nhân vật chính"     narrative role (free text)
      data-color="fade|contour-wipe|brush|none"  colour pass for this group
      data-filler="1"                decoration drawn in a pause (no data-say)
  * ``<text>`` inside a group is "hand-written" left to right
  * a full-canvas ``<rect>`` directly under ``<svg>`` is taken as the paper colour
  * top-level shapes outside groups are collected into one element drawn first

Usage:
  python svg_scene.py scene-01.svg [--out-dir DIR] [--width 1920] [--paper "#F6F1E3"]
"""
from __future__ import annotations

import argparse
import copy
import io
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stream_render as sr  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FONTS_DIR = ROOT / "assets" / "fonts"
SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

SHAPES = {"path", "line", "polyline", "polygon", "rect", "circle", "ellipse"}
NON_DRAWN = {"defs", "style", "title", "desc", "metadata", "clipPath", "mask", "linearGradient",
             "radialGradient", "pattern", "symbol", "marker", "filter"}


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _num(v: str | None, default: float | None = None) -> float | None:
    if v is None:
        return default
    m = re.match(r"\s*([-+]?[0-9]*\.?[0-9]+(?:e[-+]?\d+)?)", v)
    return float(m.group(1)) if m else default


def viewbox(root: ET.Element) -> tuple[float, float, float, float]:
    vb = root.get("viewBox")
    if vb:
        x, y, w, h = [float(t) for t in re.split(r"[\s,]+", vb.strip())]
        return x, y, w, h
    return 0.0, 0.0, _num(root.get("width"), 1920.0), _num(root.get("height"), 1080.0)


def render_svg(svg_text: str, width: int, height: int, background: str | None) -> np.ndarray:
    """Rasterise with resvg (no system libraries) -> BGRA uint8."""
    import resvg_py
    kw = dict(svg_string=svg_text, width=width, height=height,
              font_dirs=[str(FONTS_DIR)], font_family="Patrick Hand",
              sans_serif_family="Be Vietnam Pro", cursive_family="Patrick Hand")
    if background:
        kw["background"] = background
    png = resvg_py.svg_to_bytes(**kw)
    img = cv2.imdecode(np.frombuffer(bytes(png), np.uint8), cv2.IMREAD_UNCHANGED)
    if img.ndim == 3 and img.shape[2] == 3:
        img = np.dstack([img, np.full(img.shape[:2], 255, np.uint8)])
    return img


def _alpha_bbox(bgra: np.ndarray, thresh: int = 8):
    ys, xs = np.nonzero(bgra[:, :, 3] > thresh)
    if ys.size == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _is_hidden(el: ET.Element) -> bool:
    return el.get("display") == "none" or "display:none" in (el.get("style") or "").replace(" ", "")


def split_elements(root: ET.Element) -> tuple[list[ET.Element], str | None]:
    """Top-level drawing groups (+ a synthetic group for loose shapes) and the paper colour."""
    vx, vy, vw, vh = viewbox(root)
    paper = None
    groups: list[ET.Element] = []
    loose: list[ET.Element] = []
    for child in list(root):
        tag = _local(child.tag)
        if tag in NON_DRAWN or _is_hidden(child):
            continue
        if tag == "rect" and paper is None:
            w = child.get("width", "")
            h = child.get("height", "")
            full = w.strip() == "100%" or (_num(w, 0) >= vw * 0.98 and _num(h, 0) >= vh * 0.98)
            if full and child.get("fill") and child.get("fill") != "none":
                paper = child.get("fill")
                root.remove(child)
                continue
        if tag == "g":
            groups.append(child)
        else:
            loose.append(child)
    if loose:
        g = ET.Element(f"{{{SVG_NS}}}g", {"id": "base", "data-label": "base"})
        for el in loose:
            root.remove(el)
            g.append(el)
        root.insert(0, g)
        groups.insert(0, g)
    return groups, paper


def _only(root: ET.Element, keep: ET.Element) -> str:
    """SVG text with only the top-level group ``keep`` visible."""
    r = copy.deepcopy(root)
    for child in list(r):
        if _local(child.tag) not in NON_DRAWN and child.get("id") != keep.get("id"):
            r.remove(child)
    return ET.tostring(r, encoding="unicode")


def _has_text(el: ET.Element) -> bool:
    return any(_local(c.tag) == "text" for c in el.iter())


def text_lines(alpha: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Bounding boxes of text lines/blocks in a text-only render."""
    m = (alpha > 20).astype(np.uint8)
    if not m.any():
        return []
    h = max(3, int(m.shape[0] * 0.004))
    # connect letters of a word/line horizontally, keep lines apart
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (max(9, m.shape[1] // 60), h))
    blobs = cv2.morphologyEx(cv2.dilate(m, k), cv2.MORPH_CLOSE, k)
    n, lab, st, _ = cv2.connectedComponentsWithStats(blobs)
    boxes = []
    for i in range(1, n):
        x, y, w, hh, a = st[i]
        sub = m[y:y + hh, x:x + w]
        ys, xs = np.nonzero(sub)
        if ys.size:
            boxes.append((x + int(xs.min()), y + int(ys.min()), x + int(xs.max()) + 1, y + int(ys.max()) + 1))
    boxes.sort(key=lambda b: (b[1] // max(1, (b[3] - b[1])), b[0]))
    return boxes


def writing_stroke(box, sample: float) -> dict:
    """A left-to-right 'handwriting' pen path covering one text line."""
    x0, y0, x1, y1 = box
    h = max(4.0, y1 - y0)
    yc = (y0 + y1) / 2
    n = max(2, int((x1 - x0) / sample))
    xs = np.linspace(x0, x1, n)
    ys = yc + 0.28 * h * np.sin(2 * np.pi * (xs - x0) / max(6.0, 0.8 * h))
    return {"points": [[int(round(x)), int(round(y))] for x, y in zip(xs, ys)], "width": int(round(h * 1.25))}


def vector_strokes(svg_text: str, group_id: str, sample: float) -> list[list[dict]]:
    """Sample every shape of the group along its outline (document order).

    ``svg_text`` must carry width/height in output pixels: svgelements then
    applies the viewBox->viewport transform itself, so points, lengths and
    stroke widths all come out in pixels.
    """
    import svgelements as se
    doc = se.SVG.parse(io.StringIO(svg_text), reify=True)
    g = doc.get_element_by_id(group_id)
    if g is None:
        return []
    per_shape: list[list[dict]] = []
    items = list(g.select()) if hasattr(g, "select") else [g]
    for el in items:
        if not isinstance(el, se.Shape) or isinstance(el, se.Text):
            continue
        out: list[dict] = []
        per_shape.append(out)
        if getattr(el, "values", {}).get("visibility") == "hidden":
            continue
        stroke = el.stroke if el.stroke is not None and el.stroke.value is not None else None
        width = float(el.stroke_width or 0) if stroke is not None else 0.0
        try:
            path = se.Path(el)
        except Exception:
            continue
        for sub in path.as_subpaths():
            sp = se.Path(sub)
            try:
                length = sp.length(error=1e-2)
            except Exception:
                continue
            if not length or length < 1.5:
                continue
            n = max(2, int(math.ceil(length / sample)) + 1)
            pts = []
            for t in np.linspace(0, 1, n):
                p = sp.point(float(t))
                if p is None:
                    continue
                pts.append([int(round(p.x)), int(round(p.y))])
            if len(pts) >= 2:
                s = {"points": pts}
                if width > 0:
                    s["width"] = max(1, int(round(width)))
                out.append(s)
    return per_shape


def _only_text(root: ET.Element, text_el: ET.Element) -> str:
    """SVG with nothing visible except one <text> element."""
    text_el.set("data-wb-keep", "1")
    try:
        r = copy.deepcopy(root)
    finally:
        del text_el.attrib["data-wb-keep"]

    def prune(el: ET.Element) -> bool:  # returns True if el should stay
        if el.get("data-wb-keep") == "1":
            return True
        keep_any = False
        for c in list(el):
            t = _local(c.tag)
            if t in NON_DRAWN:
                continue
            if prune(c):
                keep_any = True
            else:
                el.remove(c)
        return keep_any
    prune(r)
    return ET.tostring(r, encoding="unicode")


def group_strokes(root: ET.Element, g: ET.Element, full_svg: str, W: int, H: int,
                  sample: float) -> list[dict]:
    """All pen strokes of a group in document order (shapes traced, text hand-written)."""
    per_shape = vector_strokes(full_svg, g.get("id"), sample)
    items = [c for c in g.iter() if _local(c.tag) in SHAPES or _local(c.tag) == "text"]
    n_shapes = sum(1 for c in items if _local(c.tag) in SHAPES)

    def text_strokes(t: ET.Element) -> list[dict]:
        alpha = render_svg(_only_text(root, t), W, H, None)[:, :, 3]
        return [writing_stroke(b, sample) for b in text_lines(alpha)]
    if n_shapes != len(per_shape):  # unusual markup (<use>, ...): shapes first, then text
        out = [s for shp in per_shape for s in shp]
        for c in items:
            if _local(c.tag) == "text":
                out += text_strokes(c)
        return out
    out, k = [], 0
    for c in items:
        if _local(c.tag) == "text":
            out += text_strokes(c)
        else:
            out += per_shape[k]
            k += 1
    return out


def _stroke_len(s: dict) -> float:
    a = np.asarray(s["points"], dtype=np.float32)
    return float(np.sum(np.hypot(*np.diff(a, axis=0).T))) if len(a) > 1 else 0.0


def build(svg_path: str | Path, out_dir: str | Path | None = None, width: int = 1920,
          paper: str = "#F6F1E3", sample_px: float = 3.0, px_per_sec: float = 1100.0) -> tuple[Path, Path]:
    svg_path = Path(svg_path)
    out_dir = Path(out_dir) if out_dir else svg_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    tree = ET.parse(svg_path)
    root = tree.getroot()
    vx, vy, vw, vh = viewbox(root)
    s = width / max(vw, vh)            # `width` = long edge in pixels (portrait-safe)
    W = int(round(vw * s))
    H = int(round(vh * s))
    groups, svg_paper = split_elements(root)
    paper = svg_paper or paper
    for g in groups:           # give every group an id
        if not g.get("id"):
            g.set("id", f"el_{groups.index(g) + 1}")
    root.set("width", str(W))
    root.set("height", str(H))
    full_svg = ET.tostring(root, encoding="unicode")

    full = render_svg(full_svg, W, H, paper)
    png_path = out_dir / (svg_path.stem + ".png")
    sr._imwrite_any(png_path, full[:, :, :3])

    pad = max(6, int(0.008 * W))
    elements = []
    t = 400
    # label map: which element owns each pixel (topmost group wins), 0 = paper
    labels = np.zeros((H, W), np.uint8)
    for i, g in enumerate(groups, 1):
        gid = g.get("id")
        alone = render_svg(_only(root, g), W, H, None)
        bb = _alpha_bbox(alone)
        if bb is not None and len(elements) < 254:
            own = cv2.dilate((alone[:, :, 3] > 8).astype(np.uint8), np.ones((3, 3), np.uint8)) > 0
            labels[own] = len(elements) + 1
        if bb is None:
            print(f"  [skip] group '{gid}' renders nothing")
            continue
        x0, y0, x1, y1 = bb
        x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
        x1, y1 = min(W, x1 + pad), min(H, y1 + pad)
        strokes = group_strokes(root, g, full_svg, W, H, sample_px)
        length = sum(_stroke_len(s) for s in strokes)
        dur = int(np.clip(length / px_per_sec * 1000, 900, 5000))
        label = g.get("data-label") or gid
        el = {
            "id": gid,
            "maskIndex": len(elements) + 1,
            "label": label,
            "sequence": len(elements) + 1,
            "narrativeRole": g.get("data-role", ""),
            "subtitle": "",
            "type": "text" if _has_text(g) and not any(_local(c.tag) in SHAPES for c in g.iter()) else "object",
            "region": {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0},
            "reveal": {"direction": "left_to_right", "startMs": t, "durationMs": dur,
                       "maskPaddingPx": pad, "protectedRegions": []},
            "handPath": {"start": [x0, (y0 + y1) // 2], "end": [x1, (y0 + y1) // 2], "easing": "easeInOut"},
            "strokes": strokes,
        }
        if g.get("data-say"):
            el["say"] = g.get("data-say")
        if g.get("data-color"):
            el["colorFill"] = g.get("data-color")
        if g.get("data-filler") not in (None, "", "false", "0"):
            el["filler"] = True
        elements.append(el)
        t += dur + 250
    mask_path = out_dir / (svg_path.stem + ".masks.png")
    sr._imwrite_any(mask_path, labels)
    ann = {
        "sceneId": svg_path.stem,
        "maskFile": mask_path.name,
        "canvas": {"width": W, "height": H},
        "paper": paper,
        "source": svg_path.name,
        "storyBasis": "",
        "sceneDurationMs": t + 800,
        "elements": elements,
    }
    ann_path = out_dir / (svg_path.stem + ".annotation.json")
    ann_path.write_text(json.dumps(ann, ensure_ascii=False, indent=1), encoding="utf-8")
    return png_path, ann_path


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="SVG scene -> PNG + annotation with vector strokes")
    p.add_argument("svg")
    p.add_argument("--out-dir", default=None)
    p.add_argument("--width", type=int, default=1920, help="long edge in pixels")
    p.add_argument("--paper", default="#F6F1E3")
    p.add_argument("--sample-px", type=float, default=3.0)
    a = p.parse_args(argv)
    png, ann = build(a.svg, a.out_dir, a.width, a.paper, a.sample_px)
    data = json.loads(ann.read_text(encoding="utf-8"))
    for e in data["elements"]:
        print(f"  #{e['sequence']} {e['label']}: region={e['region']} strokes={len(e['strokes'])}")
    print(f"PNG={png.resolve()}")
    print(f"OUTPUT={ann.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
