#!/usr/bin/env python3
"""
Burned-in captions: short "pages" of words with the spoken word highlighted
(karaoke style used on TikTok / Shorts), rendered with Pillow using a
Vietnamese-capable font and composited onto frames.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tts import Word  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CAPTION_FONT = ROOT / "assets" / "fonts" / "BeVietnamPro-ExtraBold.ttf"


@dataclass
class CaptionStyle:
    font: str = str(CAPTION_FONT)
    size: int = 64
    color: tuple = (255, 255, 255)
    highlight: tuple = (255, 214, 10)       # active word
    stroke: tuple = (20, 20, 20)
    stroke_ratio: float = 0.12
    max_width: int = 900
    max_lines: int = 2
    max_words: int = 6
    box: bool = False                        # rounded translucent box behind the text
    box_color: tuple = (0, 0, 0, 150)
    uppercase: bool = False
    karaoke: bool = True
    center: tuple = (540, 1250)              # caption block centre in frame pixels
    line_gap: float = 0.18


@dataclass
class Page:
    words: list[Word]
    start: int
    end: int


def build_pages(words: list[Word], style: CaptionStyle) -> list[Page]:
    """Group words into short pages; break at sentence punctuation."""
    pages: list[Page] = []
    cur: list[Word] = []
    for w in words:
        cur.append(w)
        if len(cur) >= style.max_words or w.text[-1:] in ".!?…" or \
                (w.text[-1:] in ",;:" and len(cur) >= max(2, style.max_words // 2)):
            pages.append(Page(cur, cur[0].startMs, cur[-1].endMs))
            cur = []
    if cur:
        pages.append(Page(cur, cur[0].startMs, cur[-1].endMs))
    # a page stays until the next one starts (no flicker), but not forever
    for i, p in enumerate(pages):
        nxt = pages[i + 1].start if i + 1 < len(pages) else p.end + 900
        p.end = max(p.end, min(nxt, p.end + 1200))
    return pages


class CaptionRenderer:
    def __init__(self, style: CaptionStyle) -> None:
        self.s = style
        self.font = ImageFont.truetype(style.font, style.size)
        self.cache: dict[tuple[int, int], tuple[np.ndarray, int, int]] = {}

    def _space(self, d: ImageDraw.ImageDraw) -> float:
        # the outline eats into the gap between words: widen it accordingly
        return d.textlength(" ", font=self.font) + 1.6 * self.s.size * self.s.stroke_ratio

    def _layout(self, words: list[str]) -> list[list[int]]:
        """Greedy line breaking -> list of lines (word indices)."""
        d = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
        space = self._space(d)
        lines, cur, width = [], [], 0.0
        for i, w in enumerate(words):
            wl = d.textlength(w, font=self.font)
            if cur and width + space + wl > self.s.max_width:
                lines.append(cur)
                cur, width = [], 0.0
            width = width + (space if cur else 0) + wl
            cur.append(i)
        if cur:
            lines.append(cur)
        return lines

    def render(self, page: Page, page_id: int, active: int) -> tuple[np.ndarray, int, int]:
        """RGBA image of the page (numpy) and its top-left position in the frame."""
        key = (page_id, active if self.s.karaoke else -1)
        if key in self.cache:
            return self.cache[key]
        s = self.s
        texts = [w.text.upper() if s.uppercase else w.text for w in page.words]
        lines = self._layout(texts)
        stroke = max(1, int(s.size * s.stroke_ratio))
        asc, desc = self.font.getmetrics()
        lh = asc + desc
        gap = int(lh * s.line_gap)
        d0 = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
        space = self._space(d0)
        widths = [sum(d0.textlength(texts[i], font=self.font) for i in ln) + space * (len(ln) - 1) for ln in lines]
        pad = stroke * 2 + (int(s.size * 0.35) if s.box else 0)
        W = int(max(widths) + 2 * pad) + 2
        H = int(len(lines) * lh + (len(lines) - 1) * gap + 2 * pad) + 2
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        if s.box:
            d.rounded_rectangle((0, 0, W - 1, H - 1), radius=int(s.size * 0.4), fill=s.box_color)
        y = pad
        for ln, lw in zip(lines, widths):
            x = (W - lw) / 2
            for i in ln:
                col = s.highlight if (s.karaoke and i == active) else s.color
                d.text((x, y), texts[i], font=self.font, fill=col, stroke_width=stroke, stroke_fill=s.stroke)
                x += d.textlength(texts[i], font=self.font) + space
            y += lh + gap
        arr = np.asarray(img)
        x0 = int(s.center[0] - W / 2)
        y0 = int(s.center[1] - H / 2)
        out = (arr, x0, y0)
        self.cache[key] = out
        return out


def overlay_rgba(frame_bgr: np.ndarray, rgba: np.ndarray, x0: int, y0: int) -> None:
    """Alpha-blend an RGBA image onto a BGR frame in place (clipped)."""
    h, w = rgba.shape[:2]
    H, W = frame_bgr.shape[:2]
    fx0, fy0 = max(0, x0), max(0, y0)
    fx1, fy1 = min(W, x0 + w), min(H, y0 + h)
    if fx1 <= fx0 or fy1 <= fy0:
        return
    src = rgba[fy0 - y0:fy1 - y0, fx0 - x0:fx1 - x0]
    a = src[:, :, 3:4].astype(np.float32) / 255.0
    dst = frame_bgr[fy0:fy1, fx0:fx1].astype(np.float32)
    rgb = src[:, :, 2::-1].astype(np.float32)  # RGBA -> BGR
    frame_bgr[fy0:fy1, fx0:fx1] = (dst * (1 - a) + rgb * a).astype(np.uint8)


class CaptionTrack:
    """Time-indexed captions for a whole video."""

    def __init__(self, words: list[Word], style: CaptionStyle) -> None:
        self.pages = build_pages(words, style)
        self.r = CaptionRenderer(style)
        self._i = 0

    def draw(self, frame: np.ndarray, t_ms: float) -> None:
        pages = self.pages
        if not pages:
            return
        # pages are sorted: advance a cursor (frames are drawn in time order)
        while self._i < len(pages) - 1 and t_ms >= pages[self._i + 1].start:
            self._i += 1
        while self._i > 0 and t_ms < pages[self._i].start:
            self._i -= 1
        p = pages[self._i]
        if not (p.start <= t_ms < p.end):
            return
        active = -1
        for k, w in enumerate(p.words):
            if w.startMs <= t_ms:
                active = k
        img, x0, y0 = self.r.render(p, self._i, active)
        overlay_rgba(frame, img, x0, y0)


def draw_text_block(frame: np.ndarray, text: str, center: tuple[int, int], max_width: int,
                    size: int, color=(43, 43, 43), font: str = str(CAPTION_FONT),
                    underline=(232, 116, 59)) -> None:
    """Static title/header text (wrapped, centred) - used for the portrait header."""
    st = CaptionStyle(font=font, size=size, color=color, stroke=color, stroke_ratio=0.0,
                      max_width=max_width, karaoke=False, center=center, line_gap=0.12)
    words = [Word(t, 0, 0) for t in text.split()]
    img, x0, y0 = CaptionRenderer(st).render(Page(words, 0, 1), 0, -1)
    if underline:
        pil = Image.fromarray(img)
        d = ImageDraw.Draw(pil)
        h = pil.height
        d.line((pil.width * 0.2, h - 4, pil.width * 0.8, h - 4), fill=(*underline, 255), width=max(3, size // 12))
        img = np.asarray(pil)
    overlay_rgba(frame, img, x0, y0)
