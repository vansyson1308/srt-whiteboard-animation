#!/usr/bin/env python3
"""
Whiteboard scene renderer (region-mask choreography + streamed pen strokes).

Renders one line-art image + its ``annotation.json`` into a hand-drawn
whiteboard clip:

  * Choreography: elements are drawn one after another in ``reveal.startMs``
    order.  Each element may only paint inside its *allowed mask*
    (``region`` minus every later region minus ``protectedRegions``), so
    elements that have not started yet can never leak onto the board.
  * Drawing: inside the allowed mask the pen follows real strokes -
    explicit vector ``strokes`` (from SVG scenes), a skeleton trace of the
    line art, or a grid walk - revealing ink as it goes ("ink" phase), then
    the colours are washed in ("color" phase).
  * Video: exact output size (e.g. 1920x1080 / 1080x1920), frame-accurate
    duration (important for voice sync), smooth hand enter/exit, optional
    camera that eases towards the element being drawn, cross-fade to the
    full picture at the end.

The last stdout line is ``OUTPUT=<path>``.

Usage:
  python render_stream_whiteboard.py <image> <annotation.json> <out.mp4> [hand.png]
      [--size 1920x1080] [--fps 30] [--ink-path skeleton|grid]
      [--color-fill contour-wipe|brush|fade|none] [--camera none|follow] [--idle-hand exit|stretch]
      [--total-ms N] [--bare-tip] [--draft]
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import time
from dataclasses import dataclass, field, replace
from pathlib import Path

import cv2
import numpy as np

_SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
import stream_render as sr  # noqa: E402
from wb_video import VideoSink  # noqa: E402

ASSETS_DIR = _SCRIPT_DIR.parent / "assets"
DEFAULT_HAND = ASSETS_DIR / "drawing-hand-clean.png"
MAX_LAG_S = 0.8     # idle_hand="exit": how late an element may start so the one before isn't rushed
if not DEFAULT_HAND.exists():  # pragma: no cover - older checkouts
    DEFAULT_HAND = ASSETS_DIR / "drawing-hand.png"


# ──────────────────────────────────────────────────────────────
# Options
# ──────────────────────────────────────────────────────────────
@dataclass
class RenderOptions:
    width: int = 1920
    height: int = 1080
    fps: int = 30
    ink_path: str = "skeleton"          # skeleton | grid
    color_fill: str = "contour-wipe"    # contour-wipe | brush | fade | none
    ink_style: str = "original"         # original (real line colours, anti-aliased) | threshold (old b/w look)
    ink_weight: float = 2.0             # share of each element's duration spent on ink
    color_weight: float = 1.0           # share spent on colour
    paper_hex: str = "#F6F1E3"
    match_bg: bool = True               # repaint the image background with paper_hex
    match_bg_threshold: int = 28
    hand: str | None = str(DEFAULT_HAND)
    hand_height_ratio: float = 0.42     # hand height relative to the frame's short side
    tip_anchor: tuple[float, float] = (0.0, 0.0)
    hand_motion: bool = True            # hand slides in/out between elements
    camera: str = "none"                # none | follow
    camera_max_zoom: float = 1.35
    camera_tau_s: float = 0.5           # smoothing time constant
    final_fade_ms: int = 450
    grid_edge: int = 8
    skeleton_spacing: float = 2.5
    skeleton_min_points: int = 6
    travel_speed: float = 3.5           # pen-up travel speed relative to drawing speed
    human_motion: bool = True           # human pen timing: slow corners/stroke ends, dwell at pen-down/up
    pen_lift: float = 14.0              # px (at 1080p) the hand rises while travelling between strokes
    idle_hand: str = "exit"             # exit: draw at a natural pace, then the hand leaves until the next
                                        #   element (and data-filler doodles use long pauses) | stretch: old
                                        #   behaviour, every element is stretched over its whole time slot
    draw_speed: float = 1100.0          # natural pen speed, px/s at 1080p (idle_hand="exit")
    crf: int = 18
    preset: str = "veryfast"
    verbose: bool = True

    @property
    def scale_ref(self) -> float:
        """Resolution-independent size factor (1.0 at 1080 px short side)."""
        return min(self.width, self.height) / 1080.0


def parse_size(text: str) -> tuple[int, int]:
    w, h = text.lower().replace("*", "x").split("x")
    return int(w), int(h)


# ──────────────────────────────────────────────────────────────
# Geometry helpers
# ──────────────────────────────────────────────────────────────
def _ease(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return 0.5 - 0.5 * math.cos(math.pi * t)


def order_strokes_greedy(strokes: list[np.ndarray]) -> list[np.ndarray]:
    """Nearest-endpoint chaining (with reversal) to minimise pen travel.

    Starts from the stroke closest to the top-left corner, like a person
    drawing, then always continues with the closest unused stroke end.
    """
    n = len(strokes)
    if n <= 1:
        return strokes
    heads = np.array([s[0] for s in strokes], dtype=np.float32)
    tails = np.array([s[-1] for s in strokes], dtype=np.float32)
    lengths = np.array([len(s) for s in strokes], dtype=np.float32)
    used = np.zeros(n, dtype=bool)
    # first stroke: top-left-most head, prefer long strokes (outlines) slightly
    score = heads[:, 1] + heads[:, 0] * 0.5 - np.minimum(lengths, 200) * 0.5
    cur = int(np.argmin(score))
    out = [strokes[cur]]
    used[cur] = True
    pos = tails[cur]
    for _ in range(n - 1):
        dh = np.sum((heads - pos) ** 2, axis=1)
        dt = np.sum((tails - pos) ** 2, axis=1)
        dh[used] = np.inf
        dt[used] = np.inf
        ih, it = int(np.argmin(dh)), int(np.argmin(dt))
        if dh[ih] <= dt[it]:
            nxt, s = ih, strokes[ih]
        else:
            nxt, s = it, strokes[it][::-1]
        used[nxt] = True
        out.append(s)
        pos = s[-1].astype(np.float32)
    return out


def build_pen_plan(strokes: list[np.ndarray], spacing: float, travel_speed: float,
                   radii: list[int] | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Flatten ordered strokes into pen samples.

    Returns (points Nx2 int, draw N bool, radius N int) - ``draw[i]`` means the
    segment ``points[i-1] -> points[i]`` lays ink with ``radius[i]``.  Pen-up travel between strokes is
    inserted as fast, non-drawing samples so the hand glides instead of
    teleporting.
    """
    pts: list[np.ndarray] = []
    flags: list[np.ndarray] = []
    rads: list[np.ndarray] = []
    last = None
    for si, s in enumerate(strokes):
        r = radii[si] if radii else 0
        n0 = sum(len(x) for x in pts)
        s = np.asarray(s, dtype=np.float32)
        if last is not None:
            d = float(np.hypot(*(s[0] - last)))
            n_travel = int(d / max(1e-3, spacing * travel_speed))
            if n_travel > 0:
                t = np.linspace(0, 1, n_travel + 2, dtype=np.float32)[1:-1, None]
                pts.append(last + (s[0] - last) * t)
                flags.append(np.zeros(n_travel, dtype=bool))
            pts.append(s[:1])
            flags.append(np.zeros(1, dtype=bool))
            pts.append(s[1:])
            flags.append(np.ones(len(s) - 1, dtype=bool))
        else:
            pts.append(s)
            f = np.ones(len(s), dtype=bool)
            f[0] = False
            flags.append(f)
        rads.append(np.full(sum(len(x) for x in pts) - n0, r, dtype=np.int32))
        last = s[-1]
    if not pts:
        return np.zeros((0, 2), np.int32), np.zeros(0, bool), np.zeros(0, np.int32)
    return (np.round(np.concatenate(pts)).astype(np.int32), np.concatenate(flags),
            np.concatenate(rads))


def pen_timeline(pts: np.ndarray, draw: np.ndarray, frames: int, human: bool = True
                 ) -> tuple[np.ndarray, np.ndarray]:
    """Map ``frames`` output frames onto pen samples like a human hand moves.

    Every sample gets a time cost: drawing slows down in sharp turns and at both
    ends of a stroke (accelerate, cruise, brake); pen-up travel eases in and out;
    putting the pen down and lifting it cost a short dwell.  Frames are spread
    evenly over the accumulated time, so the frame count is unchanged.

    Returns (sample index per frame - non-decreasing, ends at the last sample;
    pen-up amount 0..1 per frame, smoothed, for the hand-lift animation).
    """
    n = len(pts)
    if n == 0 or frames <= 0:
        return np.zeros(max(frames, 0), int), np.zeros(max(frames, 0), np.float32)
    if not human or n < 3:
        idx = np.round(np.linspace(0, n - 1, frames)).astype(int) if frames > 1 else np.array([n - 1])
        return idx, (~draw[idx]).astype(np.float32)
    cost, _ = _pen_cost(pts, draw)
    cum = np.cumsum(cost)
    total = cum[-1]
    if total <= 0:
        idx = np.full(frames, n - 1, int)
    else:
        targets = total * (np.arange(1, frames + 1) / frames)
        idx = np.minimum(np.searchsorted(cum, targets - 1e-9), n - 1)
        idx[-1] = n - 1
    up = (~draw[idx]).astype(np.float32)
    k = 3
    smooth = np.convolve(np.pad(up, k, mode="edge"), np.ones(2 * k + 1) / (2 * k + 1), mode="valid")
    return idx.astype(int), smooth.astype(np.float32)


def _pen_cost(pts: np.ndarray, draw: np.ndarray) -> tuple[np.ndarray, float]:
    """Per-sample time cost (in units of one drawing step) of a human hand, and the step in px."""
    n = len(pts)
    p = pts.astype(np.float32)
    seg = np.diff(p, axis=0)
    seglen = np.maximum(np.hypot(seg[:, 0], seg[:, 1]), 1e-3)
    step = float(np.median(seglen[draw[1:]])) if draw[1:].any() else float(np.median(seglen))
    cost = np.zeros(n, np.float64)
    cost[1:] = seglen / max(step, 1e-3)                      # distance-proportional base
    # turning angle over a +-3 sample baseline (robust to pixel-jagged skeleton paths)
    # -> slow down in corners; a peak-preserving kernel spreads it over the approach
    bl = 3
    turn = np.zeros(n)
    if n > 2 * bl:
        vin = p[bl:n - bl] - p[:n - 2 * bl]
        vout = p[2 * bl:] - p[bl:n - bl]
        nin = np.maximum(np.hypot(vin[:, 0], vin[:, 1]), 1e-3)
        nout = np.maximum(np.hypot(vout[:, 0], vout[:, 1]), 1e-3)
        cosang = np.sum(vin * vout, axis=1) / (nin * nout)
        turn[bl:n - bl] = np.arccos(np.clip(cosang, -1, 1)) / math.pi
        turn = np.maximum.reduce([np.roll(turn, sh) * w for sh, w in
                                  ((-2, 0.5), (-1, 0.8), (0, 1.0), (1, 0.8), (2, 0.5))])
    runs, start = [], 0                                       # contiguous draw / travel runs
    for k in range(1, n + 1):
        if k == n or draw[k] != draw[start]:
            runs.append((start, k, bool(draw[start])))
            start = k
    for a, b, is_draw in runs:
        m = b - a
        t = (np.arange(m) + 0.5) / m
        if is_draw:
            edge = np.minimum(np.arange(m), np.arange(m)[::-1])            # samples from a stroke end
            ramp = 1.0 + 0.9 * np.exp(-edge / 3.0)                         # accelerate / brake
            cost[a:b] *= ramp * (1.0 + 2.5 * turn[a:b])
            cost[a] += 3.0                                                 # pen touches down
        else:
            cost[a:b] *= 1.0 + 1.2 * (1.0 - np.sin(math.pi * t))           # glide: ease in/out
            cost[a] += 2.0                                                 # pen lifts
    return cost, step


def natural_ink_seconds(pts: np.ndarray, draw: np.ndarray, speed_px_s: float,
                        travel_speed: float = 3.5) -> float:
    """How long a person takes to draw this pen plan: ink at ``speed_px_s`` on average,
    pen-up moves ``travel_speed`` times faster, plus a short touch-down per stroke.
    (:func:`pen_timeline` then decides where inside that time the pen slows down.)"""
    if len(pts) < 2:
        return 0.0
    d = np.hypot(*np.diff(pts.astype(np.float64), axis=0).T)
    ink, travel = float(d[draw[1:]].sum()), float(d[~draw[1:]].sum())
    strokes = int(np.count_nonzero(draw[1:] & ~draw[:-1])) + int(bool(draw[1]))
    return (ink + travel / max(1.0, travel_speed)) / max(1e-3, speed_px_s) + 0.05 * strokes


# ──────────────────────────────────────────────────────────────
# Hand
# ──────────────────────────────────────────────────────────────
class Hand:
    def __init__(self, path: str | None, height: int, anchor: tuple[float, float]):
        data = sr._load_hand(Path(path), height) if path else None
        ax, ay = anchor
        if data is None:
            data = sr._procedural_tip(height)
            ax, ay = 0.5, 0.70
        self.overlay = sr.TipOverlay(data[0], data[1], tip_anchor_x=ax, tip_anchor_y=ay)
        self.w, self.h = self.overlay.w, self.overlay.h

    def stamp(self, frame: np.ndarray, x: float, y: float) -> None:
        self.overlay.stamp(frame, int(round(x)), int(round(y)))


# ──────────────────────────────────────────────────────────────
# Scene renderer
# ──────────────────────────────────────────────────────────────
class SceneRenderer:
    def __init__(self, image_bgr: np.ndarray, annotation: dict, opts: RenderOptions,
                 bare_tip: bool = False, label_map: np.ndarray | None = None) -> None:
        self.opts = opts
        self.ann = annotation
        W, H = opts.width, opts.height
        e = opts.grid_edge
        # working canvas is padded up to a multiple of grid_edge; frames are cropped to W x H
        self.W, self.H = W, H
        self.CW, self.CH = -(-W // e) * e, -(-H // e) * e
        self.paper = sr._hex_to_bgr(opts.paper_hex)

        # fit ("contain") the image into the frame
        ih, iw = image_bgr.shape[:2]
        s = min(W / iw, H / ih)
        fw, fh = max(1, int(round(iw * s))), max(1, int(round(ih * s)))
        ox, oy = (W - fw) // 2, (H - fh) // 2
        cw_ann = annotation.get("canvas", {}).get("width") or iw
        ch_ann = annotation.get("canvas", {}).get("height") or ih
        self.ax, self.ay = fw / cw_ann, fh / ch_ann     # annotation -> frame scale
        self.ox, self.oy = ox, oy

        interp = cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC
        fitted = cv2.resize(image_bgr, (fw, fh), interpolation=interp)
        if opts.match_bg:
            fitted = self._match_background(fitted)
        color = np.empty((self.CH, self.CW, 3), np.uint8)
        color[...] = self.paper
        color[oy:oy + fh, ox:ox + fw] = fitted
        self.color = color
        # optional exact ownership map (SVG scenes): pixel value = element maskIndex
        self.labels = None
        if label_map is not None:
            lm = cv2.resize(label_map, (fw, fh), interpolation=cv2.INTER_NEAREST)
            self.labels = np.zeros((self.CH, self.CW), np.uint8)
            self.labels[oy:oy + fh, ox:ox + fw] = lm

        gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)
        block = max(15, int(15 * opts.scale_ref) | 1)
        self.thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                            cv2.THRESH_BINARY, block, 10)
        self.ink = self.thresh < 10                               # line pixels
        diff = np.abs(color.astype(np.int16) - self.paper.astype(np.int16)).sum(axis=2)
        self.content = diff > 40                                   # anything not paper
        self.solid = diff > 60                                     # clearly coloured (no AA fringe)
        if opts.ink_style == "threshold":
            self.ink_paint = np.repeat(self.thresh[:, :, None], 3, axis=2)
            self.ink_reveal = self.ink
        else:
            self.ink_paint = color
            self.ink_reveal = cv2.dilate(self.ink.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) \
                & (self.content | self.ink)

        self.drawn = np.empty_like(color)
        self.drawn[...] = self.paper
        self.reveal_r = max(2, int(round(4 * opts.scale_ref)))
        self.brush_r = max(8, int(round(40 * opts.scale_ref)))

        self.hand: Hand | None = None
        if not bare_tip and opts.hand is not None:
            self.hand = Hand(opts.hand, int(round(min(W, H) * opts.hand_height_ratio)), opts.tip_anchor)
        self.cam = np.array([W / 2, H / 2, 1.0], dtype=np.float64)  # cx, cy, zoom
        self._cam_plan = None   # explicit per-frame camera states (outro zoom-out)
        self.frames_written = 0
        self.activity: list[float] = []   # per frame: 1 = pen laying ink, 0.4 = colouring, 0 = idle
        self._act = 0.0

    # ── setup helpers ──
    def _match_background(self, img: np.ndarray) -> np.ndarray:
        img = img.copy()
        h, w = img.shape[:2]
        m = max(3, min(h, w) // 50)
        samples = [img[:m, :m], img[:m, -m:], img[-m:, :m], img[-m:, -m:]]
        bg = np.median(np.concatenate([x.reshape(-1, 3) for x in samples]), axis=0)
        d = np.abs(img.astype(np.int16) - bg.astype(np.int16)).sum(axis=2)
        img[d < self.opts.match_bg_threshold] = self.paper
        return img

    def _rect(self, r: dict) -> tuple[int, int, int, int]:
        x0 = int(round(self.ox + r["x"] * self.ax))
        y0 = int(round(self.oy + r["y"] * self.ay))
        x1 = int(round(self.ox + (r["x"] + r["width"]) * self.ax))
        y1 = int(round(self.oy + (r["y"] + r["height"]) * self.ay))
        return (max(0, min(self.CW, x0)), max(0, min(self.CH, y0)),
                max(0, min(self.CW, x1)), max(0, min(self.CH, y1)))

    def allowed_mask(self, el: dict, later: list[dict]) -> np.ndarray:
        m = np.zeros((self.CH, self.CW), dtype=bool)
        x0, y0, x1, y1 = self._rect(el["region"])
        m[y0:y1, x0:x1] = True
        if self.labels is not None and el.get("maskIndex"):
            # exact pixels of this element (still bounded by its editable region)
            m &= self.labels == int(el["maskIndex"])
            later = []
        for o in later:
            a, b, c, d = self._rect(o["region"])
            m[b:d, a:c] = False
        for p in el.get("reveal", {}).get("protectedRegions", []) or []:
            a, b, c, d = self._rect(p)
            m[b:d, a:c] = False
        return m

    # ── stroke planning ──
    def _explicit_strokes(self, el: dict) -> tuple[list[np.ndarray], list[int]]:
        """Vector strokes from the annotation (canvas coords) -> frame coords + reveal radii.

        A stroke is ``[[x, y], ...]`` or ``{"points": [...], "width": px}``;
        ``width`` (or the element's ``strokeWidth``) is the line width in canvas px.
        """
        out, radii = [], []
        k = max(self.ax, self.ay)
        default_w = el.get("strokeWidth")
        for s in el.get("strokes") or []:
            pts = s.get("points") if isinstance(s, dict) else s
            if not pts or len(pts) < 2:
                continue
            a = np.asarray(pts, dtype=np.float32)
            a[:, 0] = self.ox + a[:, 0] * self.ax
            a[:, 1] = self.oy + a[:, 1] * self.ay
            w = (s.get("width") if isinstance(s, dict) else None) or default_w
            r = int(math.ceil(float(w) * k / 2)) + 2 if w else self.reveal_r
            out.append(a)
            radii.append(max(self.reveal_r, r))
        return out, radii

    def _skeleton_strokes(self, allowed: np.ndarray) -> list[np.ndarray]:
        ink = self.ink & allowed
        ys, xs = np.nonzero(ink)
        if ys.size == 0:
            return []
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        crop = ink[y0:y1, x0:x1]
        skel = sr._zhang_suen_skeleton(crop, max_iterations=60)
        raw = sr.trace_8connected(skel, min_points=self.opts.skeleton_min_points)
        sp = self.opts.skeleton_spacing * max(1.0, self.opts.scale_ref)
        out = []
        for stroke in raw:
            pts = [(float(x + x0), float(y + y0)) for x, y in stroke]
            pts = sr._resample_stroke_points(pts, sp)
            pts = sr._chaikin_smooth(pts, iterations=1)
            pts = sr._resample_stroke_points(pts, sp)
            if len(pts) >= 2:
                out.append(np.asarray(pts, dtype=np.float32))
        return out

    def _grid_strokes(self, allowed: np.ndarray) -> list[np.ndarray]:
        e = self.opts.grid_edge
        active = sr._active_mask(np.where(self.ink, 0, 255).astype(np.uint8), e, 10)
        allowed_cells = sr._to_grid_blocks(allowed.astype(np.uint8), e).any(axis=(2, 3))
        active &= allowed_cells
        if not active.any():
            return []
        path = sr.flatten_streams(sr.cluster_ink_streams(active))
        strokes, cur = [], []
        for i, (r, c) in enumerate(path):
            p = (c * e + e / 2, r * e + e / 2)
            if cur and max(abs(r - path[i - 1][0]), abs(c - path[i - 1][1])) > 1:
                strokes.append(cur)
                cur = []
            cur.append(p)
        if cur:
            strokes.append(cur)
        sp = self.opts.skeleton_spacing * max(1.0, self.opts.scale_ref)
        out = []
        for s in strokes:
            if len(s) == 1:
                s = [s[0], (s[0][0] + 1, s[0][1])]
            out.append(np.asarray(sr._resample_stroke_points(s, sp), dtype=np.float32))
        return out

    def plan_element(self, el: dict, allowed: np.ndarray):
        strokes, radii = self._explicit_strokes(el)
        explicit = bool(strokes)
        if not strokes:
            if self.opts.ink_path == "skeleton":
                strokes = self._skeleton_strokes(allowed)
            if not strokes:
                strokes = self._grid_strokes(allowed)
            strokes = order_strokes_greedy(strokes)
            radii = [self.reveal_r] * len(strokes)
        sp = self.opts.skeleton_spacing * max(1.0, self.opts.scale_ref)
        pts, draw, rad = build_pen_plan(strokes, sp, self.opts.travel_speed, radii)
        reveal_mask = (self.content if explicit else self.ink_reveal) & allowed
        return pts, draw, rad, reveal_mask

    # ── painting primitives ──
    def _reveal_segment(self, a, b, radius: int, mask: np.ndarray) -> None:
        x0 = max(0, min(a[0], b[0]) - radius - 1)
        y0 = max(0, min(a[1], b[1]) - radius - 1)
        x1 = min(self.CW, max(a[0], b[0]) + radius + 2)
        y1 = min(self.CH, max(a[1], b[1]) + radius + 2)
        if x1 <= x0 or y1 <= y0:
            return
        seg = np.zeros((y1 - y0, x1 - x0), np.uint8)
        cv2.line(seg, (int(a[0]) - x0, int(a[1]) - y0), (int(b[0]) - x0, int(b[1]) - y0),
                 255, thickness=radius * 2 + 1, lineType=cv2.LINE_8)
        hit = (seg > 0) & mask[y0:y1, x0:x1]
        self.drawn[y0:y1, x0:x1][hit] = self.ink_paint[y0:y1, x0:x1][hit]

    # ── frame output ──
    def _emit(self, sink, hand_xy, cam_target=None, board: np.ndarray | None = None) -> None:
        frame = (self.drawn if board is None else board).copy()
        if self.hand is not None and hand_xy is not None:
            self.hand.stamp(frame, hand_xy[0], hand_xy[1])
        frame = frame[:self.H, :self.W]
        if self.opts.camera != "none":
            frame = self._apply_camera(frame, cam_target)
        sink.write(frame)
        self.frames_written += 1
        self.activity.append(self._act if hand_xy is not None else 0.0)

    def _camera_target_for(self, el: dict | None) -> np.ndarray:
        W, H = self.W, self.H
        if el is None:
            return np.array([W / 2, H / 2, 1.0])
        x0, y0, x1, y1 = self._rect(el["region"])
        rw, rh = max(1, x1 - x0) * 1.35, max(1, y1 - y0) * 1.35
        z = float(np.clip(min(W / rw, H / rh), 1.0, self.opts.camera_max_zoom))
        return np.array([(x0 + x1) / 2, (y0 + y1) / 2, z])

    def _apply_camera(self, frame: np.ndarray, target) -> np.ndarray:
        if self._cam_plan is not None and self._cam_plan:
            self.cam = self._cam_plan.pop(0)
        else:
            if target is None:
                target = np.array([self.W / 2, self.H / 2, 1.0])
            alpha = 1.0 - math.exp(-1.0 / (self.opts.fps * self.opts.camera_tau_s))
            self.cam += (target - self.cam) * alpha
        cx, cy, z = self.cam
        W, H = self.W, self.H
        half_w, half_h = W / (2 * z), H / (2 * z)
        cx = min(max(cx, half_w), W - half_w)
        cy = min(max(cy, half_h), H - half_h)
        if abs(z - 1.0) < 1e-3:
            return frame
        M = np.array([[z, 0, W / 2 - z * cx], [0, z, H / 2 - z * cy]], dtype=np.float32)
        return cv2.warpAffine(frame, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    # ── phases ──
    def _hand_rest(self) -> tuple[float, float]:
        """Off-screen parking spot for the hand (its tip is the top-left of the hand image)."""
        if self.H > self.W * 1.2:
            # tall frames: leave sideways so the hand never sweeps through the caption band
            return (self.W + 30, self.H * 0.42)
        return (self.W * 0.78, self.H * 1.08)   # tip below the frame -> hand fully off-screen

    def _gap(self, sink, n: int, start_xy, end_xy, cam_target=None) -> None:
        """Idle frames between elements, the way a person waits at a whiteboard.

        Long pause: the pen lifts, the hand leaves the board and comes back just in
        time for the next element.  Short pause: the pen lifts and holds still, then
        travels to the next start at a natural speed - never a slow drift across the
        board.  ``start_xy``/``end_xy`` None = the hand is (or ends) off-screen.
        """
        if n <= 0:
            return
        rest = self._hand_rest()
        if self.hand is None or not self.opts.hand_motion:
            for _ in range(n):
                self._emit(sink, None, cam_target)
            return
        fps = self.opts.fps
        move = max(1, int(0.4 * fps))                       # leave / come back
        lift = self.opts.pen_lift * self.opts.scale_ref
        lerp = lambda p, q, u: (p[0] + (q[0] - p[0]) * u, p[1] + (q[1] - p[1]) * u)  # noqa: E731

        def lifted(p, u):                                   # pen raised off the paper by u (0..1)
            return (p[0] + 0.35 * lift * u, p[1] - lift * u)

        def travel_frames(p, q) -> int:
            d = math.hypot(q[0] - p[0], q[1] - p[1])
            return int(np.clip(d / (2600.0 * self.opts.scale_ref) * fps, 0.22 * fps, 0.6 * fps))

        out = []
        leave = start_xy is None or end_xy is None or n >= 2 * move + int(0.5 * fps)
        if not leave:
            k = min(n, travel_frames(start_xy, end_xy))
            hold = n - k
            up = min(hold, max(1, int(0.15 * fps)))
            for i in range(hold):                           # lift, then keep still
                out.append(lifted(start_xy, _ease((i + 1) / up) if i < up else 1.0))
            a = lifted(start_xy, 1.0 if hold else 0.0)
            for i in range(k):                              # travel, pen comes down at the end
                u = _ease((i + 1) / k)
                xy = lerp(a, end_xy, u)
                out.append(lifted(xy, 1.0 - u) if hold else xy)
        else:
            go = min(move, n) if start_xy is not None else 0
            back = min(move, n - go) if end_xy is not None else 0
            for i in range(go):
                out.append(lerp(lifted(start_xy, 1.0), rest, _ease((i + 1) / go)))
            out += [None] * (n - go - back)
            for i in range(back):
                u = _ease((i + 1) / back)
                out.append(lifted(lerp(rest, end_xy, u), 1.0 - u))
        for xy in out:
            if xy is not None and (xy[0] >= self.W or xy[1] >= self.H):
                xy = None   # tip outside the frame: the whole hand is off-screen
            self._emit(sink, xy, cam_target)

    def _ink_phase(self, sink, frames: int, pts, draw, radius, mask, cam_target) -> tuple | None:
        n = len(pts)
        if frames <= 0:
            return tuple(pts[-1]) if n else None
        if n == 0:
            for _ in range(frames):
                self._emit(sink, None, cam_target)
            return None
        idx, up = pen_timeline(pts, draw, frames, self.opts.human_motion)
        lift = self.opts.pen_lift * self.opts.scale_ref
        last = 0
        for si, u in zip(idx, up):
            drew = False
            for k in range(last + 1, si + 1):
                if draw[k]:
                    self._reveal_segment(pts[k - 1], pts[k], int(radius[k]), mask)
                    drew = True
            last = max(last, si)
            self._act = 1.0 if drew else 0.0
            # while the pen is up the hand rises off the paper (and a touch to the right)
            hx, hy = float(pts[si][0]) + 0.35 * lift * u, float(pts[si][1]) - lift * u
            self._emit(sink, (hx, hy), cam_target)
        self._act = 0.0
        return tuple(pts[-1])

    def _color_phase(self, sink, frames: int, allowed: np.ndarray, pts, cam_target, mode: str | None = None):
        mode = mode or self.opts.color_fill
        if frames <= 0:
            self.drawn[allowed] = self.color[allowed]
            return None
        ys, xs = np.nonzero(allowed)
        if ys.size == 0:
            for _ in range(frames):
                self._emit(sink, None, cam_target)
            return None
        top, bottom, left, right = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        a_crop = allowed[top:bottom, left:right]
        c_crop = self.color[top:bottom, left:right]
        d_crop = self.drawn[top:bottom, left:right]
        rh, rw = bottom - top, right - left
        last_xy = None
        self._act = 0.4
        if mode == "fade":
            base = d_crop.copy().astype(np.float32)
            tgt = c_crop.astype(np.float32)
            for fi in range(frames):
                t = _ease((fi + 1) / frames)
                blend = (base * (1 - t) + tgt * t).astype(np.uint8)
                d_crop[a_crop] = blend[a_crop]
                self._emit(sink, None, cam_target)
        elif mode == "brush" and len(pts):
            centers = pts[:: max(1, len(pts) // max(1, frames * 3))]
            disk = sr._feathered_disk(self.brush_r)
            idx = np.round(np.linspace(0, len(centers) - 1, frames)).astype(int)
            last = -1
            for ci in idx:
                for k in range(last + 1, ci + 1):
                    self._brush(centers[k], disk, allowed)
                last = max(last, ci)
                last_xy = tuple(centers[ci])
                self._emit(sink, last_xy, cam_target)
        elif mode == "none":
            for _ in range(frames):
                self._emit(sink, None, cam_target)
        else:  # contour-wipe
            ink_u8 = (self.ink[top:bottom, left:right] & a_crop).astype(np.uint8) * 255
            spread = int(np.clip(min(rw, rh) // 32, 3, 17)) | 1
            dil = cv2.dilate(ink_u8, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (spread, spread)))
            br = max(1, int(round(min(rw, rh) / 220.0))) | 1
            res = cv2.GaussianBlur(dil, (br, br), 0).astype(np.float32)
            peak = float(res.max())
            res = res / peak if peak > 1e-6 else np.zeros_like(res)
            for row in range(1, rh):
                np.maximum(res[row], res[row - 1] * 0.86, out=res[row])
            wave = sr._build_wipe_wave(rw)
            delay = int(np.clip(rh * 0.04, 12, 52))
            ys_ = np.arange(rh, dtype=np.float32)[:, None]
            sweep = rh + 2 * delay
            # the hand only hatches across the columns that actually receive colour
            need = a_crop & (np.abs(d_crop.astype(np.int16) - c_crop.astype(np.int16)).sum(axis=2) > 24)
            cols = np.nonzero(need.any(axis=0))[0]
            c0, c1 = (int(cols[0]), int(cols[-1])) if cols.size else (0, rw - 1)
            lanes = max(2, int(round(frames / 9)))
            for fi in range(frames):
                p = 1.0 if frames == 1 else fi / (frames - 1)
                lead = _ease(p) * sweep - delay
                rev = (ys_ <= lead + wave[None, :] - res * delay) & a_crop
                d_crop[rev] = c_crop[rev]
                lane = _ease((fi * lanes / frames) % 1.0)
                fwd = int(fi * lanes / frames) % 2 == 0
                cx = c0 + int((lane if fwd else 1 - lane) * (c1 - c0))
                col = np.nonzero(rev[:, cx] & need[:, cx])[0]
                cy = int(col[-1]) if col.size else (last_xy[1] - top if last_xy else 0)
                last_xy = (left + cx, top + cy)
                self._emit(sink, last_xy, cam_target)
        d_crop[a_crop] = c_crop[a_crop]
        self._act = 0.0
        return last_xy

    def _brush(self, c, disk, allowed) -> None:
        r = self.brush_r
        px, py = int(c[0]), int(c[1])
        y0, y1 = max(0, py - r), min(self.CH, py + r + 1)
        x0, x1 = max(0, px - r), min(self.CW, px + r + 1)
        if y1 <= y0 or x1 <= x0:
            return
        m = disk[y0 - (py - r):y1 - (py - r), x0 - (px - r):x1 - (px - r)] * allowed[y0:y1, x0:x1]
        m = m[:, :, None]
        tgt = self.drawn[y0:y1, x0:x1].astype(np.float32)
        src = self.color[y0:y1, x0:x1].astype(np.float32)
        self.drawn[y0:y1, x0:x1] = (tgt * (1 - m) + src * m).astype(np.uint8)

    def colour_pixels(self, allowed: np.ndarray, pts, draw, radius, rmask) -> int:
        """Pixels of an element the pen strokes do not reveal (fills, shading): the
        area a colour pass would have to paint.  0 for pure line art and text."""
        cover = np.zeros(allowed.shape, np.uint8)
        k = 1
        while k < len(pts):
            if not draw[k]:
                k += 1
                continue
            j = k
            while j < len(pts) and draw[j]:
                j += 1
            seg = pts[k - 1:j].reshape(-1, 1, 2).astype(np.int32)
            cv2.polylines(cover, [seg], False, 255, thickness=int(radius[k]) * 2 + 1, lineType=cv2.LINE_8)
            k = j
        todo = allowed & ~(cover.astype(bool) & rmask)
        return int(np.count_nonzero(todo & self.solid))

    def element_timing(self, el: dict, allowed, pts, draw, radius, rmask) -> tuple[str, float, float]:
        """(colour mode, natural ink seconds, natural colour seconds) for one element."""
        o = self.opts
        s2 = o.scale_ref ** 2
        mode = el.get("colorFill") or o.color_fill
        px = self.colour_pixels(allowed, pts, draw, radius, rmask) if mode != "none" else 0
        if px < max(900 * s2, 0.03 * np.count_nonzero(allowed)):
            mode = "none"                                    # nothing worth a colour pass
        ink_s = natural_ink_seconds(pts, draw, o.draw_speed * o.scale_ref, o.travel_speed)
        col_s = 0.0 if mode == "none" else float(np.clip(0.45 + px / s2 / 120000.0, 0.6, 3.0))
        return mode, ink_s, col_s

    def _timeline(self, plans: list, total_f: int, to_f) -> list[list[int]]:
        """[start frame, frames used] per element.

        ``stretch``: every element fills its slot (start .. start + duration).
        ``exit``: an element takes its natural drawing time; a slot longer than that
        leaves a pause (the hand steps away), a slot too short may run on for up to
        ``MAX_LAG_S`` into the next element's start rather than rushing the pen.
        The scene length never changes."""
        end_f = total_f - to_f(self.opts.final_fade_ms) - int(0.3 * self.opts.fps)
        for lag in (MAX_LAG_S, MAX_LAG_S / 2, 0.0):      # less running-on if the scene would overflow
            out = self._timeline_pass(plans, end_f, to_f, lag)
            if not out or out[-1][0] + out[-1][1] <= max(end_f, to_f(plans[-1][0]["reveal"]["startMs"])
                                                          + to_f(plans[-1][0]["reveal"]["durationMs"])):
                break
        for tl in out:                                     # hard guarantee: the frame count is a contract
            tl[0] = min(tl[0], total_f - 2)
            tl[1] = max(1, min(tl[1], total_f - 1 - tl[0]))
        return out

    def _timeline_pass(self, plans: list, end_f: int, to_f, lag: float) -> list[list[int]]:
        fps = self.opts.fps
        out, f = [], 0
        for i, pl in enumerate(plans):
            el = pl[0]
            anchor = to_f(el["reveal"]["startMs"])
            slot = max(2, to_f(el["reveal"]["durationMs"]))
            start = max(f, anchor)
            if self.opts.idle_hand == "stretch":
                use = slot
            else:
                nat = max(int(0.45 * fps), int(round((pl[7] + pl[8]) * fps)))
                want = nat if slot < nat else slot if slot <= nat * 1.25 else int(round(nat * 1.1))
                nxt = to_f(plans[i + 1][0]["reveal"]["startMs"]) if i + 1 < len(plans) else end_f
                limit = (nxt + int(lag * fps) if i + 1 < len(plans) else end_f) - start - 2
                use = max(min(want, limit), min(slot, want), 2)
            out.append([start, use])
            f = start + use
        return out

    def _place_fillers(self, plans: list, timeline: list, fplans: list, total_f: int, to_f
                       ) -> tuple[list, list]:
        """Put data-filler doodles into the longest pauses of the scene (after an element
        is finished and before the next one starts); each filler is drawn at most once,
        in document order.  A filler that fits nowhere is left to the closing
        cross-fade, so the last frame still shows the complete picture."""
        fps = self.opts.fps
        spans = []                                          # [free from, free until, insert after]
        for i, (s, use) in enumerate(timeline):
            nxt = timeline[i + 1][0] if i + 1 < len(timeline) else \
                total_f - to_f(self.opts.final_fade_ms) - int(0.6 * fps)
            spans.append([s + use + int(0.3 * fps), nxt - int(0.5 * fps), i])
        placed: dict[int, list] = {}
        for fp in fplans:
            el = fp[0] = dict(fp[0])                        # the caller's annotation stays untouched
            need = max(int(0.6 * fps), int(round((fp[7] + fp[8]) * fps)))
            for sp in spans:
                if sp[1] - sp[0] >= need:
                    el["reveal"] = dict(el.get("reveal", {}), startMs=int(sp[0] * 1000 / fps),
                                        durationMs=int(need * 1000 / fps))
                    placed.setdefault(sp[2], []).append((fp, [sp[0], need]))
                    sp[0] += need + int(0.3 * fps)
                    break
            else:
                if self.opts.verbose:
                    print(f"  [filler] no pause long enough for '{el.get('label') or el.get('id')}'")
        out_p, out_t = [], []
        for i, (pl, tl) in enumerate(zip(plans, timeline)):
            out_p.append(pl)
            out_t.append(tl)
            for fp, ftl in placed.get(i, []):
                out_p.append(fp)
                out_t.append(ftl)
        return out_p, out_t

    # ── main loop ──
    def render(self, sink, total_ms: int | None = None) -> int:
        o = self.opts
        fps = o.fps
        els = sorted(self.ann.get("elements", []),
                     key=lambda e: (e["reveal"]["startMs"], e.get("sequence", 0)))
        to_f = lambda ms: int(round(ms * fps / 1000.0))  # noqa: E731
        if total_ms is None:
            total_ms = self.ann.get("sceneDurationMs") or (
                max((e["reveal"]["startMs"] + e["reveal"]["durationMs"] for e in els), default=0) + 1000)
        total_f = max(1, to_f(total_ms))
        # the frame count is a contract (voice sync): if the schedule does not fit, compress it
        last_end = max((e["reveal"]["startMs"] + e["reveal"]["durationMs"] for e in els
                        if not e.get("filler")), default=0)
        budget = max(200, total_ms - 300)
        if last_end > budget:
            k = budget / last_end
            if o.verbose:
                print(f"  [warn] schedule ends at {last_end}ms > {total_ms}ms: compressing x{k:.2f}")
            els = copy.deepcopy(els)
            for e in els:
                e["reveal"]["startMs"] = int(e["reveal"]["startMs"] * k)
                e["reveal"]["durationMs"] = max(200, int(e["reveal"]["durationMs"] * k))
        wsum = o.ink_weight + (0 if o.color_fill == "none" else o.color_weight)
        # data-filler doodles are not tied to the narration: they fill long pauses (below)
        fillers = [e for e in els if e.get("filler")]
        mains = [e for e in els if not e.get("filler")]

        def plan(seq, protect):
            out = []
            for i, el in enumerate(seq):
                allowed = self.allowed_mask(el, seq[i + 1:] + protect)
                pts, draw, radius, rmask = self.plan_element(el, allowed)
                mode, ink_s, col_s = self.element_timing(el, allowed, pts, draw, radius, rmask)
                out.append([el, allowed, pts, draw, radius, rmask, mode, ink_s, col_s])
            return out

        t0 = time.time()
        plans = plan(mains, fillers)
        timeline = self._timeline(plans, total_f, to_f)
        if fillers:
            plans, timeline = self._place_fillers(plans, timeline, plan(fillers, mains), total_f, to_f)
        if o.verbose:
            print(f"  planned {len(plans)} elements in {time.time() - t0:.1f}s")

        f = 0
        hand_xy = None
        for i, ((el, allowed, pts, draw, radius, rmask, mode, ink_s, col_s), (t_start, use_f)) in \
                enumerate(zip(plans, timeline)):
            start_f = max(f, t_start)
            if o.idle_hand == "stretch":
                ink_f = max(1, int(round(use_f * o.ink_weight / wsum))) if mode != "none" else use_f
            else:
                ink_f = max(1, use_f - int(round(use_f * col_s / (ink_s + col_s)))) if col_s > 0 else use_f
            color_f = use_f - ink_f if mode != "none" else 0
            first_xy = tuple(pts[0]) if len(pts) else None
            cam = self._camera_target_for(el)
            self._gap(sink, start_f - f, hand_xy, first_xy, cam)
            end_xy = self._ink_phase(sink, ink_f, pts, draw, radius, rmask, cam)
            # make sure every line pixel of the element is on the board before colouring
            left = self.ink_reveal & allowed
            self.drawn[left] = self.ink_paint[left]
            if mode == "none" or color_f <= 0:
                self.drawn[allowed] = self.color[allowed]
            else:
                cxy = self._color_phase(sink, color_f, allowed, pts, cam, mode)
                end_xy = cxy or end_xy
            hand_xy = end_xy
            f = start_f + ink_f + color_f
            if o.verbose:
                print(f"  [{i + 1}/{len(plans)}] {el.get('label') or el.get('id')}: "
                      f"ink {ink_s:.2f}s colour {mode} {col_s:.2f}s, "
                      f"{len(pts)} pen samples, frames {start_f}-{f} "
                      f"(slot {to_f(el['reveal']['startMs'])}+{to_f(el['reveal']['durationMs'])})")

        # outro: hand leaves, board cross-fades to the complete picture, camera returns
        remaining = total_f - f
        if o.camera != "none" and remaining > 0:
            # deterministic ease back to the full board: the last frame always shows everything
            m = max(1, min(remaining, int(0.9 * fps)))
            full_cam = np.array([self.W / 2, self.H / 2, 1.0])
            start_cam = self.cam.copy()
            self._cam_plan = [start_cam + (full_cam - start_cam) * _ease((i + 1) / m) for i in range(m)]
        fade_f = min(max(0, remaining), to_f(o.final_fade_ms))
        exit_f = max(0, min(remaining - fade_f, int(0.4 * fps)))
        self._gap(sink, exit_f, hand_xy, None, None)
        base = self.drawn.astype(np.float32)
        full = self.color.astype(np.float32)
        for k in range(fade_f):
            t = _ease((k + 1) / fade_f)
            self._emit(sink, None, None, board=(base * (1 - t) + full * t).astype(np.uint8))
        self.drawn[...] = self.color
        while self.frames_written < total_f:
            self._emit(sink, None, None)
        return self.frames_written


# ──────────────────────────────────────────────────────────────
# Public API / CLI
# ──────────────────────────────────────────────────────────────
def load_label_map(annotation: dict, base_dir: Path | None) -> np.ndarray | None:
    name = annotation.get("maskFile")
    if not name:
        return None
    p = Path(name)
    if not p.is_absolute() and base_dir is not None:
        p = base_dir / p
    lm = sr._imread_any(str(p), cv2.IMREAD_GRAYSCALE) if p.exists() else None
    if lm is None:
        print(f"  [warn] maskFile not found: {p} (falling back to region rectangles)")
    return lm


def render_scene(image: str | Path, annotation: dict | str | Path, output: str | Path,
                 opts: RenderOptions | None = None, total_ms: int | None = None,
                 bare_tip: bool = False, base_dir: str | Path | None = None,
                 activity_path: str | Path | None = None) -> Path:
    opts = opts or RenderOptions()
    img = sr._imread_any(str(image))
    if img is None:
        raise FileNotFoundError(f"cannot read image: {image}")
    if not isinstance(annotation, dict):
        base_dir = base_dir or Path(annotation).parent
        annotation = json.loads(Path(annotation).read_text(encoding="utf-8"))
    base_dir = Path(base_dir) if base_dir else Path(image).parent
    if not annotation.get("elements"):
        raise ValueError("annotation has no elements")
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    r = SceneRenderer(img, annotation, opts, bare_tip=bare_tip,
                      label_map=load_label_map(annotation, base_dir))
    t0 = time.time()
    with VideoSink(out, opts.width, opts.height, opts.fps, crf=opts.crf, preset=opts.preset) as sink:
        n = r.render(sink, total_ms)
    if activity_path:
        Path(activity_path).write_text(json.dumps({"fps": opts.fps, "activity": [round(a, 2) for a in r.activity]}),
                                       encoding="utf-8")
    if opts.verbose:
        print(f"  {n} frames ({n / opts.fps:.2f}s) in {time.time() - t0:.1f}s -> {out}")
    return out


def default_size_for(image_path: str, long_edge: int = 1920) -> tuple[int, int]:
    img = sr._imread_any(image_path)
    h, w = img.shape[:2]
    s = long_edge / max(w, h)
    return max(2, int(round(w * s / 2)) * 2), max(2, int(round(h * s / 2)) * 2)


def _parse_args(argv=None):
    p = argparse.ArgumentParser(description="Whiteboard scene renderer (mask choreography + stream strokes)")
    p.add_argument("image")
    p.add_argument("annotation")
    p.add_argument("output")
    p.add_argument("hand", nargs="?", default=str(DEFAULT_HAND), help="hand PNG (default: clean built-in hand)")
    p.add_argument("--size", default=None, help="output WxH, e.g. 1920x1080 (default: image aspect, long edge 1920)")
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--total-ms", type=int, default=None, help="scene length; default sceneDurationMs")
    p.add_argument("--bare-tip", action="store_true", help="no hand overlay")
    p.add_argument("--ink-path", default="skeleton", choices=["skeleton", "grid"])
    p.add_argument("--ink-style", default="original", choices=["original", "threshold"])
    p.add_argument("--color-fill", default="contour-wipe", choices=["contour-wipe", "brush", "fade", "none"])
    p.add_argument("--camera", default="none", choices=["none", "follow"])
    p.add_argument("--idle-hand", default="exit", choices=["exit", "stretch"],
                   help="exit: natural pace, the hand leaves during pauses; stretch: fill every time slot")
    p.add_argument("--paper", default="#F6F1E3", help="paper colour hex")
    p.add_argument("--crf", type=int, default=18)
    p.add_argument("--preset", default="veryfast")
    p.add_argument("--draft", action="store_true", help="fast low-res preview (640 px, 15 fps)")
    # legacy flags (accepted for backwards compatibility)
    p.add_argument("--pause", default=None, help=argparse.SUPPRESS)
    p.add_argument("--grid-edge", type=int, default=None)
    p.add_argument("--brush-radius", type=int, default=None, help=argparse.SUPPRESS)
    p.add_argument("--cap-long-edge", type=int, default=None, help="legacy: long edge in px when --size is omitted")
    return p.parse_args(argv)


def main(argv=None) -> int:
    a = _parse_args(argv)
    if a.size:
        w, h = parse_size(a.size)
    else:
        w, h = default_size_for(a.image, a.cap_long_edge or 1920)
    opts = RenderOptions(width=w, height=h, fps=a.fps, ink_path=a.ink_path, ink_style=a.ink_style,
                         color_fill=a.color_fill, camera=a.camera, paper_hex=a.paper, hand=a.hand,
                         idle_hand=a.idle_hand, crf=a.crf, preset=a.preset)
    if a.grid_edge:
        opts.grid_edge = a.grid_edge
    if a.draft:
        s = 640 / max(w, h)
        opts = replace(opts, width=int(w * s) // 2 * 2, height=int(h * s) // 2 * 2, fps=15, crf=26)
    print(f"render {a.image} -> {a.output} ({opts.width}x{opts.height}@{opts.fps})")
    try:
        out = render_scene(a.image, a.annotation, a.output, opts, a.total_ms, a.bare_tip)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as e:
        print(f"[err] {e}")
        return 1
    print(f"OUTPUT={out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
