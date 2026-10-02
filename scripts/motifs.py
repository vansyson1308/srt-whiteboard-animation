"""Hand-drawn SVG motifs for whiteboard scenes (viewBox 1600x900).

Build a scene as top-level groups - ``g(id, label, say, *parts)`` - from these motifs, so
every video of a series shares one drawing style.  Coordinates are viewBox pixels; most
figures take ``(x, y)`` = the point they stand on (feet, base) and a scale ``s``.

    from motifs import *
    els = [g("chap", "Phần 1", "điều quan trọng nhất", chapter(1, "Hiểu chính mình")),
           g("kid", "Đứa trẻ", "đứa trẻ", teen(400, 800, 1.1, "sad"), speech(480, 220, 380, 100, "ghét!", 48))]

Drawing notes (see docs/SVG_GUIDE.md): keep 3-5 light elements per scene, labels short,
text only in glyphs Patrick Hand has (draw arrows with ``arrow``, never "→").
"""
from __future__ import annotations

import math
from xml.sax.saxutils import escape

INK, OR, RED, BLUE, YEL, GRN, BROWN = "#2b2b2b", "#e8743b", "#e04b3a", "#3b7dd8", "#f6c453", "#5aa469", "#8a5a2b"
WHITE, LIGHT, SKY, ROBE, GRAY = "#ffffff", "#eef5fb", "#dfeefe", "#f0a24a", "#9a9a9a"
FONT = "Patrick Hand"


def svg(body: str, note: str = "") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900">\n'
            f'  <!-- {escape(note)} -->\n{body}\n</svg>\n')


def g(gid: str, label: str, say: str, *parts: str) -> str:
    inner = "\n".join("    " + p for p in parts if p)
    return f'  <g id="{gid}" data-label="{escape(label)}" data-say="{escape(say)}">\n{inner}\n  </g>'


def text(x, y, s, size=56, fill=INK, anchor="middle") -> str:
    return (f'<text x="{x:.0f}" y="{y:.0f}" text-anchor="{anchor}" font-family="{FONT}" '
            f'font-size="{size}" fill="{fill}">{escape(s)}</text>')


def line(x1, y1, x2, y2, color=INK, w=6) -> str:
    return (f'<path d="M{x1:.0f} {y1:.0f} L {x2:.0f} {y2:.0f}" fill="none" stroke="{color}" '
            f'stroke-width="{w}" stroke-linecap="round"/>')


def path(d, fill="none", color=INK, w=6) -> str:
    return (f'<path d="{d}" fill="{fill}" stroke="{color}" stroke-width="{w}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>')


def circle(cx, cy, r, fill="none", color=INK, w=6) -> str:
    return f'<circle cx="{cx:.0f}" cy="{cy:.0f}" r="{r:.0f}" fill="{fill}" stroke="{color}" stroke-width="{w}"/>'


def rect(x, y, w, h, fill=WHITE, color=INK, sw=6, rx=18) -> str:
    return (f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="{rx}" fill="{fill}" '
            f'stroke="{color}" stroke-width="{sw}"/>')


def title(s, y=110, size=80, color=INK, under=OR) -> str:
    half = min(700, len(s) * size * 0.22)
    return "\n    ".join([text(800, y, s, size, color),
                         path(f"M{800 - half:.0f} {y + 30} C {800 - half / 3:.0f} {y + 44}, "
                              f"{800 + half / 3:.0f} {y + 44}, {800 + half:.0f} {y + 28}", color=under, w=7)])


def arrow(x1, y1, x2, y2, color=BLUE, w=7, head=22) -> str:
    a = math.atan2(y2 - y1, x2 - x1)
    hx1, hy1 = x2 - head * math.cos(a - 0.45), y2 - head * math.sin(a - 0.45)
    hx2, hy2 = x2 - head * math.cos(a + 0.45), y2 - head * math.sin(a + 0.45)
    return path(f"M{x1:.0f} {y1:.0f} L {x2:.0f} {y2:.0f} M{hx1:.0f} {hy1:.0f} L {x2:.0f} {y2:.0f} "
                f"L {hx2:.0f} {hy2:.0f}", color=color, w=w)


def box(x, y, w, h, label, size=48, fill=WHITE, color=INK, tcolor=INK) -> str:
    return "\n    ".join([rect(x, y, w, h, fill, color), text(x + w / 2, y + h / 2 + size * 0.34, label, size, tcolor)])


# ── people ──────────────────────────────────────────────────────
def person(x, y, s=1.0, face="smile", arms="down", color=INK) -> str:
    """Stick figure standing on (x, y) = feet; height ~ 230*s."""
    hy = y - 190 * s
    r = 28 * s
    mouth = {"smile": f"M{x - 10 * s:.0f} {hy + 8 * s:.0f} q {10 * s:.0f} {9 * s:.0f} {20 * s:.0f} 0",
             "sad": f"M{x - 10 * s:.0f} {hy + 14 * s:.0f} q {10 * s:.0f} {-9 * s:.0f} {20 * s:.0f} 0",
             "flat": f"M{x - 9 * s:.0f} {hy + 11 * s:.0f} l {18 * s:.0f} 0"}[face]
    eyes = f"M{x - 10 * s:.0f} {hy - 6 * s:.0f} l 0 3 M{x + 10 * s:.0f} {hy - 6 * s:.0f} l 0 3"
    sh = y - 150 * s
    hip = y - 70 * s
    arm = {"down": f"M{x - 38 * s:.0f} {sh + 60 * s:.0f} L {x:.0f} {sh + 8 * s:.0f} L {x + 38 * s:.0f} {sh + 60 * s:.0f}",
           "up": f"M{x - 45 * s:.0f} {sh - 45 * s:.0f} L {x:.0f} {sh + 8 * s:.0f} L {x + 45 * s:.0f} {sh - 45 * s:.0f}",
           "reach": f"M{x - 38 * s:.0f} {sh + 60 * s:.0f} L {x:.0f} {sh + 8 * s:.0f} L {x + 60 * s:.0f} {sh - 30 * s:.0f}",
           "point": f"M{x - 38 * s:.0f} {sh + 60 * s:.0f} L {x:.0f} {sh + 8 * s:.0f} L {x + 62 * s:.0f} {sh + 10 * s:.0f}"}[arms]
    return "\n    ".join([
        circle(x, hy, r, WHITE, color, 5),
        path(eyes + " " + mouth, color=color, w=4),
        path(f"M{x:.0f} {hy + r:.0f} L {x:.0f} {hip:.0f} M{x - 30 * s:.0f} {y:.0f} L {x:.0f} {hip:.0f} "
             f"L {x + 30 * s:.0f} {y:.0f}", color=color, w=6),
        path(arm, color=color, w=6)])


def monk(x, y, s=1.0, robe=ROBE) -> str:
    """Standing monk in a robe; feet at y."""
    hy = y - 185 * s
    return "\n    ".join([
        path(f"M{x - 20 * s:.0f} {y - 150 * s:.0f} Q {x - 70 * s:.0f} {y - 40 * s:.0f} {x - 55 * s:.0f} {y:.0f} "
             f"L {x + 55 * s:.0f} {y:.0f} Q {x + 70 * s:.0f} {y - 40 * s:.0f} {x + 20 * s:.0f} {y - 150 * s:.0f} Z",
             fill=robe, w=5),
        path(f"M{x + 18 * s:.0f} {y - 148 * s:.0f} L {x - 40 * s:.0f} {y - 20 * s:.0f}", color=INK, w=4),
        circle(x, hy, 30 * s, "#fbe3c8", INK, 5),
        path(f"M{x - 10 * s:.0f} {hy - 4 * s:.0f} l 0 3 M{x + 10 * s:.0f} {hy - 4 * s:.0f} l 0 3 "
             f"M{x - 9 * s:.0f} {hy + 10 * s:.0f} q {9 * s:.0f} {7 * s:.0f} {18 * s:.0f} 0", w=4)])


def buddha(x, y, s=1.0, halo=True) -> str:
    """Seated meditating figure; (x, y) = bottom centre of the lap."""
    hy = y - 175 * s
    parts = []
    if halo:
        parts.append(circle(x, hy, 62 * s, "#fff4cc", YEL, 5))
    parts += [
        path(f"M{x - 115 * s:.0f} {y:.0f} Q {x - 120 * s:.0f} {y - 40 * s:.0f} {x - 60 * s:.0f} {y - 55 * s:.0f} "
             f"Q {x - 70 * s:.0f} {y - 120 * s:.0f} {x - 28 * s:.0f} {y - 138 * s:.0f} L {x + 28 * s:.0f} {y - 138 * s:.0f} "
             f"Q {x + 70 * s:.0f} {y - 120 * s:.0f} {x + 60 * s:.0f} {y - 55 * s:.0f} "
             f"Q {x + 120 * s:.0f} {y - 40 * s:.0f} {x + 115 * s:.0f} {y:.0f} Z", fill=ROBE, w=5),
        path(f"M{x - 45 * s:.0f} {y - 50 * s:.0f} Q {x:.0f} {y - 30 * s:.0f} {x + 45 * s:.0f} {y - 50 * s:.0f}", w=4),
        circle(x, hy, 36 * s, "#fbe3c8", INK, 5),
        circle(x, hy - 42 * s, 10 * s, INK, INK, 3),
        path(f"M{x - 16 * s:.0f} {hy - 2 * s:.0f} q 8 5 14 0 M{x + 2 * s:.0f} {hy - 2 * s:.0f} q 8 5 14 0 "
             f"M{x - 9 * s:.0f} {hy + 16 * s:.0f} q {9 * s:.0f} {6 * s:.0f} {18 * s:.0f} 0", w=4)]
    return "\n    ".join(parts)


# ── nature & symbols ────────────────────────────────────────────
def tree(x, y, s=1.0) -> str:
    """Bodhi tree; (x, y) = base of the trunk."""
    return "\n    ".join([
        path(f"M{x - 18 * s:.0f} {y:.0f} Q {x - 10 * s:.0f} {y - 110 * s:.0f} {x - 5 * s:.0f} {y - 200 * s:.0f} "
             f"L {x + 12 * s:.0f} {y - 200 * s:.0f} Q {x + 14 * s:.0f} {y - 110 * s:.0f} {x + 24 * s:.0f} {y:.0f} Z",
             fill=BROWN, w=5),
        path(f"M{x:.0f} {y - 190 * s:.0f} C {x - 190 * s:.0f} {y - 170 * s:.0f}, {x - 200 * s:.0f} {y - 380 * s:.0f}, "
             f"{x - 60 * s:.0f} {y - 400 * s:.0f} C {x - 20 * s:.0f} {y - 470 * s:.0f}, {x + 90 * s:.0f} {y - 460 * s:.0f}, "
             f"{x + 110 * s:.0f} {y - 390 * s:.0f} C {x + 230 * s:.0f} {y - 360 * s:.0f}, {x + 190 * s:.0f} {y - 170 * s:.0f}, "
             f"{x:.0f} {y - 190 * s:.0f} Z", fill="#9fd49a", w=5)])


def wheel(cx, cy, r, color=YEL, spokes=8, hub=None) -> str:
    parts = [circle(cx, cy, r, color, INK, 7), circle(cx, cy, r * 0.8, WHITE, INK, 5)]
    for k in range(spokes):
        a = 2 * math.pi * k / spokes - math.pi / 2
        parts.append(line(cx + r * 0.2 * math.cos(a), cy + r * 0.2 * math.sin(a),
                          cx + r * 0.8 * math.cos(a), cy + r * 0.8 * math.sin(a), INK, 6))
        parts.append(circle(cx + r * 1.08 * math.cos(a), cy + r * 1.08 * math.sin(a), r * 0.07, color, INK, 4))
    parts.append(circle(cx, cy, r * 0.2, hub or OR, INK, 5))
    return "\n    ".join(parts)


def lotus(x, y, s=1.0) -> str:
    """Lotus flower sitting on water at (x, y)."""
    petals = []
    for dx, h, w in ((0, 120, 38), (-55, 95, 34), (55, 95, 34), (-95, 60, 30), (95, 60, 30)):
        px = x + dx * s
        petals.append(path(f"M{px:.0f} {y:.0f} Q {px - w * s:.0f} {y - h * 0.55 * s:.0f} {px:.0f} {y - h * s:.0f} "
                           f"Q {px + w * s:.0f} {y - h * 0.55 * s:.0f} {px:.0f} {y:.0f} Z", fill="#f7b6c8", w=4))
    return "\n    ".join(petals + [path(f"M{x - 150 * s:.0f} {y + 6 * s:.0f} Q {x:.0f} {y + 40 * s:.0f} "
                                      f"{x + 150 * s:.0f} {y + 6 * s:.0f}", fill="#9fd49a", w=5)])


def deer(x, y, s=1.0) -> str:
    """Small deer standing, (x, y) = front feet."""
    return "\n    ".join([
        path(f"M{x - 110 * s:.0f} {y - 80 * s:.0f} Q {x - 60 * s:.0f} {y - 110 * s:.0f} {x:.0f} {y - 85 * s:.0f} "
             f"L {x + 15 * s:.0f} {y - 140 * s:.0f} L {x + 45 * s:.0f} {y - 130 * s:.0f} L {x + 20 * s:.0f} {y - 75 * s:.0f} "
             f"Q {x - 10 * s:.0f} {y - 50 * s:.0f} {x - 110 * s:.0f} {y - 55 * s:.0f} Z", fill="#e5b77f", w=5),
        path(f"M{x - 95 * s:.0f} {y - 55 * s:.0f} L {x - 100 * s:.0f} {y:.0f} M{x - 70 * s:.0f} {y - 55 * s:.0f} "
             f"L {x - 65 * s:.0f} {y:.0f} M{x - 10 * s:.0f} {y - 60 * s:.0f} L {x - 15 * s:.0f} {y:.0f} "
             f"M{x + 8 * s:.0f} {y - 66 * s:.0f} L {x + 12 * s:.0f} {y:.0f}", w=5),
        path(f"M{x + 22 * s:.0f} {y - 140 * s:.0f} l -8 -30 m 8 30 l 18 -34 m -8 16 l 14 -6", w=4),
        circle(x + 28 * s, y - 118 * s, 3, INK, INK, 2)])


def water(x1, x2, y, color=BLUE) -> str:
    n = max(2, int((x2 - x1) / 80))
    step = (x2 - x1) / n
    d = f"M{x1:.0f} {y:.0f} " + " ".join(f"q {step / 4:.0f} -14 {step / 2:.0f} 0 q {step / 4:.0f} 14 {step / 2:.0f} 0"
                                          for _ in range(n))
    return path(d, color=color, w=5)


def heart(x, y, s=1.0, fill=RED, broken=False) -> str:
    d = (f"M{x:.0f} {y + 40 * s:.0f} C {x - 70 * s:.0f} {y - 10 * s:.0f}, {x - 50 * s:.0f} {y - 70 * s:.0f}, {x:.0f} {y - 35 * s:.0f} "
         f"C {x + 50 * s:.0f} {y - 70 * s:.0f}, {x + 70 * s:.0f} {y - 10 * s:.0f}, {x:.0f} {y + 40 * s:.0f} Z")
    parts = [path(d, fill=fill, w=5)]
    if broken:
        parts.append(path(f"M{x:.0f} {y - 35 * s:.0f} l -10 20 l 16 12 l -12 18 l 6 25", color=WHITE, w=6))
    return "\n    ".join(parts)


def speech(x, y, w, h, label, size=40, fill=WHITE, color=INK, tail="left") -> str:
    tx = x + 40 if tail == "left" else x + w - 40
    return "\n    ".join([
        path(f"M{x + 24:.0f} {y:.0f} L {x + w - 24:.0f} {y:.0f} Q {x + w:.0f} {y:.0f} {x + w:.0f} {y + 24:.0f} "
             f"L {x + w:.0f} {y + h - 24:.0f} Q {x + w:.0f} {y + h:.0f} {x + w - 24:.0f} {y + h:.0f} "
             f"L {tx + 20:.0f} {y + h:.0f} L {tx - 10:.0f} {y + h + 34:.0f} L {tx:.0f} {y + h:.0f} "
             f"L {x + 24:.0f} {y + h:.0f} Q {x:.0f} {y + h:.0f} {x:.0f} {y + h - 24:.0f} L {x:.0f} {y + 24:.0f} "
             f"Q {x:.0f} {y:.0f} {x + 24:.0f} {y:.0f} Z", fill=fill, color=color, w=5),
        text(x + w / 2, y + h / 2 + size * 0.34, label, size)])


def hand(x, y, fingers=1, s=1.0) -> str:
    """Raised hand (palm) with 1 or 2 fingers up; (x, y) = wrist bottom."""
    parts = [path(f"M{x - 34 * s:.0f} {y:.0f} L {x - 38 * s:.0f} {y - 70 * s:.0f} Q {x - 40 * s:.0f} {y - 100 * s:.0f} "
                  f"{x - 10 * s:.0f} {y - 100 * s:.0f} L {x + 30 * s:.0f} {y - 100 * s:.0f} Q {x + 44 * s:.0f} {y - 90 * s:.0f} "
                  f"{x + 38 * s:.0f} {y - 60 * s:.0f} L {x + 34 * s:.0f} {y:.0f} Z", fill="#fbe3c8", w=5)]
    xs = [x - 14 * s] if fingers == 1 else [x - 22 * s, x + 4 * s]
    for fx in xs:
        parts.append(path(f"M{fx - 10 * s:.0f} {y - 98 * s:.0f} L {fx - 10 * s:.0f} {y - 170 * s:.0f} "
                          f"Q {fx:.0f} {y - 185 * s:.0f} {fx + 10 * s:.0f} {y - 170 * s:.0f} L {fx + 10 * s:.0f} {y - 98 * s:.0f}",
                          fill="#fbe3c8", w=5))
    return "\n    ".join(parts)


def pill(x, y, s=1.0) -> str:
    """Capsule: sweet coating outside, bitter core inside."""
    return "\n    ".join([
        path(f"M{x - 110 * s:.0f} {y - 55 * s:.0f} L {x + 110 * s:.0f} {y - 55 * s:.0f} A {55 * s:.0f} {55 * s:.0f} 0 0 1 "
             f"{x + 110 * s:.0f} {y + 55 * s:.0f} L {x - 110 * s:.0f} {y + 55 * s:.0f} A {55 * s:.0f} {55 * s:.0f} 0 0 1 "
             f"{x - 110 * s:.0f} {y - 55 * s:.0f} Z", fill="#fde3ef", w=6),
        path(f"M{x - 90 * s:.0f} {y - 25 * s:.0f} L {x + 90 * s:.0f} {y - 25 * s:.0f} A {25 * s:.0f} {25 * s:.0f} 0 0 1 "
             f"{x + 90 * s:.0f} {y + 25 * s:.0f} L {x - 90 * s:.0f} {y + 25 * s:.0f} A {25 * s:.0f} {25 * s:.0f} 0 0 1 "
             f"{x - 90 * s:.0f} {y - 25 * s:.0f} Z", fill="#7a5c3e", w=4)])


def weed(x, y, s=1.0, roots=True) -> str:
    parts = [path(f"M{x:.0f} {y:.0f} Q {x - 30 * s:.0f} {y - 70 * s:.0f} {x - 70 * s:.0f} {y - 110 * s:.0f} "
                  f"M{x:.0f} {y:.0f} Q {x + 10 * s:.0f} {y - 90 * s:.0f} {x + 5 * s:.0f} {y - 150 * s:.0f} "
                  f"M{x:.0f} {y:.0f} Q {x + 40 * s:.0f} {y - 60 * s:.0f} {x + 80 * s:.0f} {y - 95 * s:.0f}", color=GRN, w=8)]
    if roots:
        parts.append(path(f"M{x:.0f} {y:.0f} Q {x - 20 * s:.0f} {y + 50 * s:.0f} {x - 60 * s:.0f} {y + 90 * s:.0f} "
                          f"M{x:.0f} {y:.0f} Q {x + 5 * s:.0f} {y + 60 * s:.0f} {x - 5 * s:.0f} {y + 120 * s:.0f} "
                          f"M{x:.0f} {y:.0f} Q {x + 30 * s:.0f} {y + 45 * s:.0f} {x + 70 * s:.0f} {y + 85 * s:.0f}",
                          color=BROWN, w=6))
    return "\n    ".join(parts)


def ground(x1, x2, y, color=INK) -> str:
    return path(f"M{x1:.0f} {y:.0f} Q {(x1 + x2) / 2:.0f} {y + 8:.0f} {x2:.0f} {y:.0f}", color=color, w=5)


def crown(x, y, s=1.0) -> str:
    return path(f"M{x - 60 * s:.0f} {y:.0f} L {x - 70 * s:.0f} {y - 70 * s:.0f} L {x - 30 * s:.0f} {y - 35 * s:.0f} "
                f"L {x:.0f} {y - 85 * s:.0f} L {x + 30 * s:.0f} {y - 35 * s:.0f} L {x + 70 * s:.0f} {y - 70 * s:.0f} "
                f"L {x + 60 * s:.0f} {y:.0f} Z", fill=YEL, w=6)


def cup(x, y, s=1.0, steam=True, fill=WHITE) -> str:
    parts = [path(f"M{x - 60 * s:.0f} {y - 110 * s:.0f} L {x + 60 * s:.0f} {y - 110 * s:.0f} L {x + 50 * s:.0f} {y:.0f} "
                  f"L {x - 50 * s:.0f} {y:.0f} Z", fill=fill, w=6),
             path(f"M{x + 58 * s:.0f} {y - 90 * s:.0f} q {45 * s:.0f} 5 {35 * s:.0f} {40 * s:.0f} q -8 {25 * s:.0f} "
                  f"{-42 * s:.0f} {25 * s:.0f}", w=6)]
    if steam:
        parts.append(path(f"M{x - 25 * s:.0f} {y - 130 * s:.0f} q -15 -25 0 -50 M{x + 15 * s:.0f} {y - 130 * s:.0f} "
                          f"q -15 -25 0 -50", color=GRAY, w=5))
    return "\n    ".join(parts)


# ══ additions for the "Luật hấp dẫn" video ══════════════════════
PAPER, EMERALD, PURPLE, SKIN, DARK = "#fff7e0", "#3fa37a", "#8e6cc9", "#fbe3c8", "#4a4a4a"


def gf(gid: str, label: str, *parts: str) -> str:
    """Decoration with no data-say: the renderer doodles it into a pause."""
    inner = "\n".join("    " + p for p in parts if p)
    return f'  <g id="{gid}" data-label="{escape(label)}" data-filler="1">\n{inner}\n  </g>'


def dashed(d, color=GRAY, w=5, dash="4 16") -> str:
    return path(d, color=color, w=w).replace("/>", f' stroke-dasharray="{dash}"/>')


def sparkle(x, y, s=1.0, color=YEL) -> str:
    return path(f"M{x:.0f} {y - 30 * s:.0f} Q {x + 4 * s:.0f} {y - 4 * s:.0f} {x + 30 * s:.0f} {y:.0f} "
                f"Q {x + 4 * s:.0f} {y + 4 * s:.0f} {x:.0f} {y + 30 * s:.0f} Q {x - 4 * s:.0f} {y + 4 * s:.0f} "
                f"{x - 30 * s:.0f} {y:.0f} Q {x - 4 * s:.0f} {y - 4 * s:.0f} {x:.0f} {y - 30 * s:.0f} Z", fill=color, w=4)


def star(cx, cy, r, fill=YEL, w=5) -> str:
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.45
        pts.append(f"{cx + rr * math.cos(a):.0f} {cy + rr * math.sin(a):.0f}")
    return path("M" + " L ".join(pts) + " Z", fill=fill, w=w)


def check(x, y, s=1.0, color=GRN) -> str:
    return path(f"M{x - 30 * s:.0f} {y:.0f} L {x - 8 * s:.0f} {y + 24 * s:.0f} L {x + 34 * s:.0f} {y - 28 * s:.0f}",
                color=color, w=9)


def cross(x, y, s=1.0, color=RED, w=9) -> str:
    return path(f"M{x - 28 * s:.0f} {y - 28 * s:.0f} L {x + 28 * s:.0f} {y + 28 * s:.0f} "
                f"M{x + 28 * s:.0f} {y - 28 * s:.0f} L {x - 28 * s:.0f} {y + 28 * s:.0f}", color=color, w=w)


def qmark(x, y, s=1.0, color=OR) -> str:
    return "\n    ".join([path(f"M{x - 22 * s:.0f} {y - 40 * s:.0f} Q {x - 20 * s:.0f} {y - 72 * s:.0f} {x + 6 * s:.0f} {y - 72 * s:.0f} "
                                f"Q {x + 34 * s:.0f} {y - 70 * s:.0f} {x + 30 * s:.0f} {y - 42 * s:.0f} Q {x + 26 * s:.0f} {y - 22 * s:.0f} "
                                f"{x + 2 * s:.0f} {y - 10 * s:.0f} L {x + 2 * s:.0f} {y + 10 * s:.0f}", color=color, w=8),
                           circle(x + 2 * s, y + 34 * s, 5 * s, color, color, 4)])


def planet(cx, cy, r, fill="#f2c27b", ring=False) -> str:
    parts = [circle(cx, cy, r, fill, INK, 6)]
    if ring:
        parts.append(path(f"M{cx - r * 1.7:.0f} {cy + r * 0.25:.0f} Q {cx:.0f} {cy - r * 0.55:.0f} {cx + r * 1.7:.0f} "
                          f"{cy - r * 0.25:.0f} Q {cx:.0f} {cy + r * 0.75:.0f} {cx - r * 1.7:.0f} {cy + r * 0.25:.0f} Z", w=5))
    return "\n    ".join(parts)


def earth(cx, cy, r, core=False) -> str:
    parts = [circle(cx, cy, r, "#8ec5f0", INK, 6),
             path(f"M{cx - r * 0.6:.0f} {cy - r * 0.45:.0f} q {r * 0.3:.0f} {-r * 0.25:.0f} {r * 0.55:.0f} 0 "
                  f"q {r * 0.1:.0f} {r * 0.3:.0f} {-r * 0.2:.0f} {r * 0.45:.0f} q {-r * 0.3:.0f} {r * 0.05:.0f} "
                  f"{-r * 0.35:.0f} {-r * 0.45:.0f} Z", fill="#9fd49a", w=4),
             path(f"M{cx + r * 0.15:.0f} {cy + r * 0.2:.0f} q {r * 0.35:.0f} {-r * 0.15:.0f} {r * 0.5:.0f} {r * 0.15:.0f} "
                  f"q {-r * 0.05:.0f} {r * 0.35:.0f} {-r * 0.35:.0f} {r * 0.35:.0f} q {-r * 0.25:.0f} {-r * 0.2:.0f} "
                  f"{-r * 0.15:.0f} {-r * 0.5:.0f} Z", fill="#9fd49a", w=4)]
    if core:
        parts.append(circle(cx, cy, r * 0.32, OR, INK, 5))
    return "\n    ".join(parts)


def moon(cx, cy, r) -> str:
    return "\n    ".join([circle(cx, cy, r, "#e6e6e6", INK, 6), circle(cx - r * 0.3, cy - r * 0.2, r * 0.18, WHITE, GRAY, 4),
                           circle(cx + r * 0.35, cy + r * 0.25, r * 0.13, WHITE, GRAY, 4),
                           circle(cx + r * 0.1, cy - r * 0.45, r * 0.09, WHITE, GRAY, 3)])


def apple(x, y, s=1.0) -> str:
    return "\n    ".join([
        path(f"M{x:.0f} {y - 28 * s:.0f} C {x - 50 * s:.0f} {y - 60 * s:.0f}, {x - 60 * s:.0f} {y + 30 * s:.0f}, "
             f"{x:.0f} {y + 40 * s:.0f} C {x + 60 * s:.0f} {y + 30 * s:.0f}, {x + 50 * s:.0f} {y - 60 * s:.0f}, "
             f"{x:.0f} {y - 28 * s:.0f} Z", fill=RED, w=5),
        path(f"M{x:.0f} {y - 28 * s:.0f} q 2 -22 14 -30", color=BROWN, w=5),
        path(f"M{x + 6 * s:.0f} {y - 46 * s:.0f} q 22 -14 34 4 q -20 10 -34 -4 Z", fill=GRN, w=4)])


def magnet(x, y, s=1.0, angle=0) -> str:
    """U magnet, opening upwards, (x, y) = bottom of the bend."""
    d = (f"M{x - 70 * s:.0f} {y - 150 * s:.0f} L {x - 70 * s:.0f} {y - 60 * s:.0f} A {70 * s:.0f} {70 * s:.0f} 0 0 0 "
         f"{x + 70 * s:.0f} {y - 60 * s:.0f} L {x + 70 * s:.0f} {y - 150 * s:.0f} L {x + 30 * s:.0f} {y - 150 * s:.0f} "
         f"L {x + 30 * s:.0f} {y - 60 * s:.0f} A {30 * s:.0f} {30 * s:.0f} 0 0 1 {x - 30 * s:.0f} {y - 60 * s:.0f} "
         f"L {x - 30 * s:.0f} {y - 150 * s:.0f} Z")
    tips = (rect(x - 70 * s, y - 175 * s, 40 * s, 30 * s, "#d9d9d9", INK, 5, 4) + "\n    "
            + rect(x + 30 * s, y - 175 * s, 40 * s, 30 * s, "#d9d9d9", INK, 5, 4))
    out = "\n    ".join([path(d, fill=RED, w=6), tips])
    if angle:
        out = f'<g transform="rotate({angle} {x:.0f} {y:.0f})">' + out + "</g>"
    return out


def pull(x1, y1, x2, y2, n=3, color=BLUE) -> str:
    """Attraction lines between two points."""
    out = []
    for k in range(n):
        off = (k - (n - 1) / 2) * 22
        out.append(dashed(f"M{x1:.0f} {y1 + off:.0f} Q {(x1 + x2) / 2:.0f} {(y1 + y2) / 2 + off * 1.6:.0f} "
                          f"{x2:.0f} {y2 + off:.0f}", color, 5, "3 14"))
    return "\n    ".join(out)


def book(x, y, w, h, label="", fill="#f7d58b", size=34, tcolor=INK) -> str:
    parts = [rect(x, y, w, h, fill, INK, 6, 8), line(x + 18, y + 6, x + 18, y + h - 6, INK, 4)]
    if label:
        parts.append(text(x + w / 2 + 9, y + h / 2 + size * 0.34, label, size, tcolor))
    return "\n    ".join(parts)


def scroll(x, y, w, h, label="", size=40, tcolor=INK) -> str:
    return "\n    ".join([
        rect(x, y, w, h, PAPER, INK, 5, 6),
        path(f"M{x - 14:.0f} {y:.0f} q -14 {h / 2:.0f} 0 {h:.0f} q 14 0 14 -14 L {x:.0f} {y + 14:.0f} q 0 -14 -14 -14 Z",
             fill="#f1dcae", w=5),
        path(f"M{x + w + 14:.0f} {y:.0f} q 14 {h / 2:.0f} 0 {h:.0f} q -14 0 -14 -14 L {x + w:.0f} {y + 14:.0f} "
             f"q 0 -14 14 -14 Z", fill="#f1dcae", w=5),
        text(x + w / 2, y + h / 2 + size * 0.34, label, size, tcolor) if label else ""])


def tablet(x, y, w=220, h=300) -> str:
    """Emerald tablet: rounded-top green slab with engraved lines; (x, y) = top-left."""
    r = w / 2
    parts = [path(f"M{x:.0f} {y + r:.0f} A {r:.0f} {r:.0f} 0 0 1 {x + w:.0f} {y + r:.0f} L {x + w:.0f} {y + h:.0f} "
                  f"L {x:.0f} {y + h:.0f} Z", fill=EMERALD, w=6)]
    for k in range(5):
        yy = y + r * 0.7 + k * (h - r * 0.7) / 5.5
        parts.append(line(x + 30, yy, x + w - 30 - (k % 2) * 30, yy, "#1f6b4c", 5))
    return "\n    ".join(parts)


def cloud(cx, cy, s=1.0, fill=WHITE, rain=False, color=INK) -> str:
    """Puffy cloud centred near (cx, cy); optional rain below."""
    def P(dx, dy):
        return f"{cx + dx * s:.0f} {cy + dy * s:.0f}"
    d = (f"M{P(-90, 30)} Q {P(-135, 30)} {P(-130, -5)} Q {P(-125, -40)} {P(-85, -35)} "
         f"Q {P(-70, -85)} {P(-20, -75)} Q {P(15, -115)} {P(60, -80)} Q {P(115, -85)} {P(115, -30)} "
         f"Q {P(150, -20)} {P(145, 10)} Q {P(140, 32)} {P(105, 30)} Z")
    parts = [path(d, fill=fill, color=color, w=5)]
    if rain:
        for k in range(5):
            x = cx - 80 * s + k * 40 * s
            parts.append(line(x, cy + 50 * s, x - 12 * s, cy + 90 * s, BLUE, 6))
    return "\n    ".join(parts)


def drum(x, y, s=1.0) -> str:
    return "\n    ".join([
        path(f"M{x - 70 * s:.0f} {y - 80 * s:.0f} L {x - 70 * s:.0f} {y:.0f} Q {x:.0f} {y + 30 * s:.0f} {x + 70 * s:.0f} {y:.0f} "
             f"L {x + 70 * s:.0f} {y - 80 * s:.0f}", fill="#c98b4f", w=6),
        path(f"M{x - 70 * s:.0f} {y - 80 * s:.0f} Q {x:.0f} {y - 110 * s:.0f} {x + 70 * s:.0f} {y - 80 * s:.0f} "
             f"Q {x:.0f} {y - 50 * s:.0f} {x - 70 * s:.0f} {y - 80 * s:.0f} Z", fill=PAPER, w=6),
        line(x + 40 * s, y - 150 * s, x + 10 * s, y - 92 * s, BROWN, 7)])


def bison(x, y, s=1.0, color="#a0522d") -> str:
    """Cave-painting bison facing left; (x, y) = feet line centre."""
    return "\n    ".join([
        path(f"M{x - 130 * s:.0f} {y - 70 * s:.0f} Q {x - 120 * s:.0f} {y - 150 * s:.0f} {x - 40 * s:.0f} {y - 155 * s:.0f} "
             f"Q {x + 60 * s:.0f} {y - 170 * s:.0f} {x + 120 * s:.0f} {y - 110 * s:.0f} Q {x + 140 * s:.0f} {y - 70 * s:.0f} "
             f"{x + 110 * s:.0f} {y - 50 * s:.0f} L {x - 100 * s:.0f} {y - 45 * s:.0f} Q {x - 135 * s:.0f} {y - 50 * s:.0f} "
             f"{x - 130 * s:.0f} {y - 70 * s:.0f} Z", fill=color, color=color, w=5),
        path(f"M{x - 85 * s:.0f} {y - 48 * s:.0f} L {x - 90 * s:.0f} {y:.0f} M{x - 50 * s:.0f} {y - 46 * s:.0f} L {x - 45 * s:.0f} {y:.0f} "
             f"M{x + 60 * s:.0f} {y - 50 * s:.0f} L {x + 55 * s:.0f} {y:.0f} M{x + 95 * s:.0f} {y - 52 * s:.0f} L {x + 100 * s:.0f} {y:.0f} "
             f"M{x - 120 * s:.0f} {y - 120 * s:.0f} q -20 -20 -10 -40", color=color, w=8)])


def cave(x1, x2, y_top, y_bot) -> str:
    return path(f"M{x1:.0f} {y_bot:.0f} L {x1:.0f} {y_top + 80:.0f} Q {(x1 + x2) / 2:.0f} {y_top - 60:.0f} {x2:.0f} "
                f"{y_top + 80:.0f} L {x2:.0f} {y_bot:.0f}", fill="#efe1c6", color=BROWN, w=8)


def brain(cx, cy, s=1.0, fill="#f7c6d0") -> str:
    return "\n    ".join([
        path(f"M{cx - 110 * s:.0f} {cy + 10 * s:.0f} Q {cx - 130 * s:.0f} {cy - 70 * s:.0f} {cx - 60 * s:.0f} {cy - 85 * s:.0f} "
             f"Q {cx - 20 * s:.0f} {cy - 120 * s:.0f} {cx + 30 * s:.0f} {cy - 95 * s:.0f} Q {cx + 100 * s:.0f} {cy - 110 * s:.0f} "
             f"{cx + 115 * s:.0f} {cy - 40 * s:.0f} Q {cx + 140 * s:.0f} {cy + 20 * s:.0f} {cx + 80 * s:.0f} {cy + 55 * s:.0f} "
             f"Q {cx + 20 * s:.0f} {cy + 80 * s:.0f} {cx - 40 * s:.0f} {cy + 60 * s:.0f} Q {cx - 100 * s:.0f} {cy + 60 * s:.0f} "
             f"{cx - 110 * s:.0f} {cy + 10 * s:.0f} Z", fill=fill, w=6),
        path(f"M{cx:.0f} {cy - 90 * s:.0f} Q {cx - 20 * s:.0f} {cy - 40 * s:.0f} {cx + 10 * s:.0f} {cy:.0f} "
             f"Q {cx + 30 * s:.0f} {cy + 30 * s:.0f} {cx:.0f} {cy + 60 * s:.0f} M{cx - 70 * s:.0f} {cy - 40 * s:.0f} "
             f"q 30 10 30 40 M{cx + 50 * s:.0f} {cy - 60 * s:.0f} q -10 30 30 40", w=4)])


def thought(x, y, w, h, label="", size=40, fill=WHITE, tail=(0, 0)) -> str:
    """Thought cloud with small circles leading to (tail) point."""
    parts = [path(f"M{x + 30:.0f} {y + h:.0f} Q {x - 10:.0f} {y + h:.0f} {x + 6:.0f} {y + h / 2:.0f} Q {x - 10:.0f} {y:.0f} "
                  f"{x + w * 0.3:.0f} {y + 8:.0f} Q {x + w * 0.5:.0f} {y - 22:.0f} {x + w * 0.72:.0f} {y + 6:.0f} "
                  f"Q {x + w + 14:.0f} {y + 4:.0f} {x + w - 6:.0f} {y + h / 2:.0f} Q {x + w + 10:.0f} {y + h:.0f} "
                  f"{x + w - 34:.0f} {y + h:.0f} Z", fill=fill, w=5)]
    if tail != (0, 0):
        tx, ty = tail
        mx, my = x + w * 0.3, y + h
        parts += [circle(mx + (tx - mx) * 0.35, my + (ty - my) * 0.35, 12, fill, INK, 4),
                  circle(mx + (tx - mx) * 0.7, my + (ty - my) * 0.7, 7, fill, INK, 4)]
    if label:
        parts.append(text(x + w / 2, y + h / 2 + size * 0.34, label, size))
    return "\n    ".join(parts)


def funnel(x, y, s=1.0) -> str:
    """Filter funnel, (x, y) = top centre."""
    return path(f"M{x - 110 * s:.0f} {y:.0f} L {x + 110 * s:.0f} {y:.0f} L {x + 22 * s:.0f} {y + 110 * s:.0f} "
                f"L {x + 22 * s:.0f} {y + 170 * s:.0f} L {x - 22 * s:.0f} {y + 170 * s:.0f} L {x - 22 * s:.0f} {y + 110 * s:.0f} Z",
                fill="#e6f2ff", w=6)


def car(x, y, s=1.0, fill=RED) -> str:
    """Side view car, (x, y) = ground under the middle."""
    return "\n    ".join([
        path(f"M{x - 110 * s:.0f} {y - 25 * s:.0f} L {x - 110 * s:.0f} {y - 60 * s:.0f} L {x - 60 * s:.0f} {y - 65 * s:.0f} "
             f"L {x - 30 * s:.0f} {y - 105 * s:.0f} L {x + 50 * s:.0f} {y - 105 * s:.0f} L {x + 80 * s:.0f} {y - 65 * s:.0f} "
             f"L {x + 110 * s:.0f} {y - 58 * s:.0f} L {x + 112 * s:.0f} {y - 25 * s:.0f} Z", fill=fill, w=5),
        path(f"M{x - 22 * s:.0f} {y - 95 * s:.0f} L {x + 6 * s:.0f} {y - 95 * s:.0f} L {x + 6 * s:.0f} {y - 66 * s:.0f} "
             f"L {x - 42 * s:.0f} {y - 66 * s:.0f} Z M{x + 18 * s:.0f} {y - 95 * s:.0f} L {x + 44 * s:.0f} {y - 95 * s:.0f} "
             f"L {x + 64 * s:.0f} {y - 66 * s:.0f} L {x + 18 * s:.0f} {y - 66 * s:.0f} Z", fill=SKY, w=4),
        circle(x - 60 * s, y - 22 * s, 22 * s, DARK, INK, 5), circle(x + 62 * s, y - 22 * s, 22 * s, DARK, INK, 5)])


def lens(x, y, s=1.0) -> str:
    """Magnifying glass, lens centre (x, y)."""
    return "\n    ".join([circle(x, y, 80 * s, "#eef8ff", INK, 7),
                           line(x + 58 * s, y + 58 * s, x + 140 * s, y + 140 * s, BROWN, 18)])


def money_bag(x, y, s=1.0) -> str:
    """Sack of money, (x, y) = bottom centre."""
    return "\n    ".join([
        path(f"M{x - 30 * s:.0f} {y - 130 * s:.0f} Q {x - 110 * s:.0f} {y - 70 * s:.0f} {x - 80 * s:.0f} {y - 10 * s:.0f} "
             f"Q {x:.0f} {y + 10 * s:.0f} {x + 80 * s:.0f} {y - 10 * s:.0f} Q {x + 110 * s:.0f} {y - 70 * s:.0f} "
             f"{x + 30 * s:.0f} {y - 130 * s:.0f} Z", fill="#d9b779", w=6),
        path(f"M{x - 30 * s:.0f} {y - 130 * s:.0f} L {x - 45 * s:.0f} {y - 165 * s:.0f} L {x + 45 * s:.0f} {y - 165 * s:.0f} "
             f"L {x + 30 * s:.0f} {y - 130 * s:.0f}", fill="#d9b779", w=6),
        text(x, y - 40 * s, "$", int(70 * s), GRN)])


def coin(x, y, r=26) -> str:
    return "\n    ".join([circle(x, y, r, YEL, INK, 5), text(x, y + r * 0.4, "$", int(r * 1.2), BROWN)])


def seed(x, y, s=1.0) -> str:
    return path(f"M{x:.0f} {y - 22 * s:.0f} Q {x + 20 * s:.0f} {y:.0f} {x:.0f} {y + 22 * s:.0f} "
                f"Q {x - 20 * s:.0f} {y:.0f} {x:.0f} {y - 22 * s:.0f} Z", fill=BROWN, w=5)


def sprout(x, y, s=1.0) -> str:
    return "\n    ".join([path(f"M{x:.0f} {y:.0f} L {x:.0f} {y - 80 * s:.0f}", color=GRN, w=7),
                           path(f"M{x:.0f} {y - 60 * s:.0f} q -50 -10 -55 -50 q 45 0 55 50 Z", fill="#9fd49a", w=4),
                           path(f"M{x:.0f} {y - 70 * s:.0f} q 50 -10 55 -50 q -45 0 -55 50 Z", fill="#9fd49a", w=4)])


def sun(cx, cy, r=50) -> str:
    rays = []
    for k in range(8):
        a = k * math.pi / 4
        rays.append(line(cx + r * 1.25 * math.cos(a), cy + r * 1.25 * math.sin(a),
                         cx + r * 1.6 * math.cos(a), cy + r * 1.6 * math.sin(a), OR, 6))
    return "\n    ".join([circle(cx, cy, r, YEL, INK, 6)] + rays)


def monkey_paw(x, y, s=1.0) -> str:
    """Dried monkey paw, fingers up; (x, y) = wrist bottom."""
    parts = [path(f"M{x - 30 * s:.0f} {y:.0f} Q {x - 45 * s:.0f} {y - 60 * s:.0f} {x - 40 * s:.0f} {y - 110 * s:.0f} "
                  f"L {x + 40 * s:.0f} {y - 110 * s:.0f} Q {x + 45 * s:.0f} {y - 60 * s:.0f} {x + 30 * s:.0f} {y:.0f} Z",
                  fill="#8b6b4a", w=5)]
    for k, (dx, h) in enumerate(((-32, 70), (-12, 90), (10, 88), (30, 66))):
        fx = x + dx * s
        parts.append(path(f"M{fx - 8 * s:.0f} {y - 108 * s:.0f} Q {fx - 14 * s:.0f} {y - (108 + h) * s:.0f} "
                          f"{fx + 2 * s:.0f} {y - (110 + h) * s:.0f} Q {fx + 12 * s:.0f} {y - (104 + h) * s:.0f} "
                          f"{fx + 8 * s:.0f} {y - 108 * s:.0f}", fill="#8b6b4a", w=5))
    parts.append(path(f"M{x - 40 * s:.0f} {y - 100 * s:.0f} q -40 -10 -50 -45 q 20 -5 50 25", fill="#8b6b4a", w=5))
    return "\n    ".join(parts)


def scale(cx, cy, s=1.0, left="+", right="-", tilt=0.0) -> str:
    """Balance; (cx, cy) = pivot top. ``tilt`` > 0 lowers the left pan."""
    dy = 40 * tilt * s
    lx, rx = cx - 220 * s, cx + 220 * s
    ly, ry = cy + dy, cy - dy
    return "\n    ".join([
        path(f"M{cx:.0f} {cy:.0f} L {cx:.0f} {cy + 300 * s:.0f} M{cx - 90 * s:.0f} {cy + 300 * s:.0f} L {cx + 90 * s:.0f} "
             f"{cy + 300 * s:.0f}", color=BROWN, w=10),
        line(lx, ly, rx, ry, BROWN, 9),
        path(f"M{lx:.0f} {ly:.0f} L {lx - 70 * s:.0f} {ly + 120 * s:.0f} M{lx:.0f} {ly:.0f} L {lx + 70 * s:.0f} {ly + 120 * s:.0f} "
             f"M{rx:.0f} {ry:.0f} L {rx - 70 * s:.0f} {ry + 120 * s:.0f} M{rx:.0f} {ry:.0f} L {rx + 70 * s:.0f} {ry + 120 * s:.0f}",
             color=GRAY, w=4),
        path(f"M{lx - 90 * s:.0f} {ly + 120 * s:.0f} Q {lx:.0f} {ly + 175 * s:.0f} {lx + 90 * s:.0f} {ly + 120 * s:.0f} Z",
             fill=YEL, w=5),
        path(f"M{rx - 90 * s:.0f} {ry + 120 * s:.0f} Q {rx:.0f} {ry + 175 * s:.0f} {rx + 90 * s:.0f} {ry + 120 * s:.0f} Z",
             fill=YEL, w=5),
        text(lx, ly + 100 * s, left, int(70 * s), GRN), text(rx, ry + 100 * s, right, int(80 * s), RED),
        circle(cx, cy, 14 * s, OR, INK, 5)])


def chain(x1, x2, y, color=GRAY) -> str:
    n = max(2, int((x2 - x1) / 60))
    step = (x2 - x1) / n
    return "\n    ".join(rect(x1 + k * step, y - 18, step * 1.15, 36, "none", color, 7, 18) for k in range(n))


def gear(cx, cy, r, fill="#cfd8e3") -> str:
    pts = []
    for k in range(32):
        a = 2 * math.pi * k / 32
        rr = r if (k // 2) % 2 == 0 else r * 0.8
        pts.append(f"{cx + rr * math.cos(a):.0f} {cy + rr * math.sin(a):.0f}")
    return "\n    ".join([path("M" + " L ".join(pts) + " Z", fill=fill, w=5), circle(cx, cy, r * 0.3, WHITE, INK, 5)])


def tower(x, y, s=1.0) -> str:
    """Radio tower with waves; (x, y) = base centre."""
    return "\n    ".join([
        path(f"M{x - 50 * s:.0f} {y:.0f} L {x:.0f} {y - 220 * s:.0f} L {x + 50 * s:.0f} {y:.0f} M{x - 32 * s:.0f} {y - 80 * s:.0f} "
             f"L {x + 32 * s:.0f} {y - 80 * s:.0f} M{x - 18 * s:.0f} {y - 150 * s:.0f} L {x + 18 * s:.0f} {y - 150 * s:.0f}", w=6),
        circle(x, y - 228 * s, 10 * s, RED, INK, 4),
        path(f"M{x - 40 * s:.0f} {y - 258 * s:.0f} q -20 30 0 60 M{x + 40 * s:.0f} {y - 258 * s:.0f} q 20 30 0 60 "
             f"M{x - 70 * s:.0f} {y - 275 * s:.0f} q -32 47 0 94 M{x + 70 * s:.0f} {y - 275 * s:.0f} q 32 47 0 94",
             color=BLUE, w=5)])


def ticket(x, y, w=260, h=130, label="", fill="#ffe9a8") -> str:
    return "\n    ".join([rect(x, y, w, h, fill, INK, 5, 10), dashed(f"M{x + 60:.0f} {y + 8:.0f} L {x + 60:.0f} {y + h - 8:.0f}", INK, 4, "6 10"),
                           text(x + 60 + (w - 60) / 2, y + h / 2 + 14, label, 40) if label else ""])


def bowl(x, y, s=1.0, fill=WHITE) -> str:
    """Instant-noodle cup, (x, y) = bottom centre."""
    return "\n    ".join([
        path(f"M{x - 90 * s:.0f} {y - 170 * s:.0f} L {x + 90 * s:.0f} {y - 170 * s:.0f} L {x + 65 * s:.0f} {y:.0f} "
             f"L {x - 65 * s:.0f} {y:.0f} Z", fill=fill, w=6),
        path(f"M{x - 80 * s:.0f} {y - 170 * s:.0f} q 20 -40 40 0 q 20 -40 40 0 q 20 -40 40 0 q 20 -40 40 0",
             color="#d9a441", w=6),
        path(f"M{x - 30 * s:.0f} {y - 225 * s:.0f} q -15 -25 0 -50 M{x + 20 * s:.0f} {y - 225 * s:.0f} q -15 -25 0 -50",
             color=GRAY, w=5)])


def scissors(x, y, s=1.0) -> str:
    return "\n    ".join([circle(x - 40 * s, y + 40 * s, 22 * s, "none", RED, 6), circle(x - 40 * s, y - 40 * s, 22 * s, "none", RED, 6),
                           path(f"M{x - 22 * s:.0f} {y + 28 * s:.0f} L {x + 80 * s:.0f} {y - 30 * s:.0f} "
                                f"M{x - 22 * s:.0f} {y - 28 * s:.0f} L {x + 80 * s:.0f} {y + 30 * s:.0f}", color=GRAY, w=7)])


def bed(x, y, s=1.0) -> str:
    """Hospital bed with a lying sad person, (x, y) = floor under the bed middle."""
    return "\n    ".join([
        path(f"M{x - 150 * s:.0f} {y:.0f} L {x - 150 * s:.0f} {y - 110 * s:.0f} M{x + 150 * s:.0f} {y:.0f} L {x + 150 * s:.0f} "
             f"{y - 80 * s:.0f} M{x - 150 * s:.0f} {y - 50 * s:.0f} L {x + 150 * s:.0f} {y - 50 * s:.0f}", w=7),
        rect(x - 140 * s, y - 80 * s, 280 * s, 30 * s, WHITE, INK, 5, 8),
        circle(x - 105 * s, y - 100 * s, 24 * s, WHITE, INK, 5),
        path(f"M{x - 112 * s:.0f} {y - 92 * s:.0f} q 8 -6 14 0", w=4),
        path(f"M{x - 80 * s:.0f} {y - 82 * s:.0f} Q {x:.0f} {y - 110 * s:.0f} {x + 130 * s:.0f} {y - 82 * s:.0f}", fill="#cfe6ff", w=5),
        path(f"M{x + 190 * s:.0f} {y:.0f} L {x + 190 * s:.0f} {y - 220 * s:.0f} L {x + 160 * s:.0f} {y - 220 * s:.0f}", color=GRAY, w=5),
        rect(x + 140 * s, y - 215 * s, 40 * s, 55 * s, "#e6f2ff", INK, 4, 6)])


def domino(x, y, label, w=210, h=110, fill=WHITE, size=38) -> str:
    return box(x, y, w, h, label, size, fill)


# ══ additions for the "Chính trị 101" video ═════════════════════
def hourglass(x, y, s=1.0) -> str:
    """Sand timer, (x, y) = bottom centre."""
    return "\n    ".join([
        line(x - 60 * s, y, x + 60 * s, y, BROWN, 9), line(x - 60 * s, y - 200 * s, x + 60 * s, y - 200 * s, BROWN, 9),
        path(f"M{x - 45 * s:.0f} {y - 190 * s:.0f} L {x + 45 * s:.0f} {y - 190 * s:.0f} Q {x + 45 * s:.0f} {y - 130 * s:.0f} "
             f"{x + 8 * s:.0f} {y - 100 * s:.0f} Q {x + 45 * s:.0f} {y - 70 * s:.0f} {x + 45 * s:.0f} {y - 10 * s:.0f} "
             f"L {x - 45 * s:.0f} {y - 10 * s:.0f} Q {x - 45 * s:.0f} {y - 70 * s:.0f} {x - 8 * s:.0f} {y - 100 * s:.0f} "
             f"Q {x - 45 * s:.0f} {y - 130 * s:.0f} {x - 45 * s:.0f} {y - 190 * s:.0f} Z", fill="#eef8ff", w=5),
        path(f"M{x - 30 * s:.0f} {y - 160 * s:.0f} L {x + 30 * s:.0f} {y - 160 * s:.0f} L {x:.0f} {y - 110 * s:.0f} Z", fill=YEL, w=3),
        path(f"M{x - 38 * s:.0f} {y - 12 * s:.0f} Q {x:.0f} {y - 60 * s:.0f} {x + 38 * s:.0f} {y - 12 * s:.0f} Z", fill=YEL, w=3)])


def bandage(x, y, s=1.0, angle=-20) -> str:
    body = "\n    ".join([rect(x - 80 * s, y - 25 * s, 160 * s, 50 * s, "#f6d2a8", INK, 5, int(25 * s)),
                        rect(x - 28 * s, y - 25 * s, 56 * s, 50 * s, "#fbe7cf", INK, 4, 6),
                        circle(x - 12 * s, y - 8 * s, 3, BROWN, BROWN, 1), circle(x + 12 * s, y + 8 * s, 3, BROWN, BROWN, 1)])
    return f'<g transform="rotate({angle} {x:.0f} {y:.0f})">' + body + "</g>"


def traffic_light(x, y, s=1.0, on="red", cross_out=False) -> str:
    """(x, y) = top centre of the box."""
    cols = {"red": RED, "yellow": YEL, "green": GRN}
    parts = [rect(x - 45 * s, y, 90 * s, 240 * s, DARK, INK, 5, 16), line(x, y + 240 * s, x, y + 380 * s, INK, 8)]
    for k, c in enumerate(("red", "yellow", "green")):
        parts.append(circle(x, y + (45 + 75 * k) * s, 26 * s, cols[c] if c == on else "#7a7a7a", INK, 4))
    if cross_out:
        parts.append(cross(x, y + 120 * s, 2.2 * s))
    return "\n    ".join(parts)


def teddy(x, y, s=1.0) -> str:
    """Plush bear sitting, (x, y) = bottom centre."""
    b = "#c99b6d"
    return "\n    ".join([
        circle(x - 38 * s, y - 175 * s, 18 * s, b, INK, 4), circle(x + 38 * s, y - 175 * s, 18 * s, b, INK, 4),
        path(f"M{x - 70 * s:.0f} {y:.0f} Q {x - 80 * s:.0f} {y - 100 * s:.0f} {x:.0f} {y - 105 * s:.0f} "
             f"Q {x + 80 * s:.0f} {y - 100 * s:.0f} {x + 70 * s:.0f} {y:.0f} Z", fill=b, w=5),
        circle(x, y - 140 * s, 48 * s, b, INK, 5), circle(x, y - 125 * s, 16 * s, "#e8c9a6", INK, 3),
        circle(x - 16 * s, y - 150 * s, 4, INK, INK, 2), circle(x + 16 * s, y - 150 * s, 4, INK, INK, 2),
        circle(x, y - 128 * s, 4, INK, INK, 2)])


def stick(x1, y1, x2, y2) -> str:
    """Talking stick with bands."""
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    return "\n    ".join([line(x1, y1, x2, y2, BROWN, 16), circle(x2, y2, 14, OR, INK, 4),
                           line(mx - 10, my - 6, mx + 10, my + 6, RED, 6), line(mx + 30, my - 26, mx + 50, my - 14, BLUE, 6)])


def ballot_box(x, y, s=1.0, paper=True) -> str:
    """(x, y) = bottom centre."""
    parts = [path(f"M{x - 110 * s:.0f} {y:.0f} L {x - 110 * s:.0f} {y - 150 * s:.0f} L {x + 110 * s:.0f} {y - 150 * s:.0f} "
                  f"L {x + 110 * s:.0f} {y:.0f} Z", fill="#cfe6ff", w=6),
             line(x - 50 * s, y - 150 * s, x + 50 * s, y - 150 * s, INK, 10),
             text(x, y - 55 * s, "BẦU", int(48 * s), BLUE)]
    if paper:
        parts.append(path(f"M{x - 35 * s:.0f} {y - 150 * s:.0f} L {x - 40 * s:.0f} {y - 240 * s:.0f} L {x + 30 * s:.0f} "
                          f"{y - 245 * s:.0f} L {x + 35 * s:.0f} {y - 150 * s:.0f}", fill=WHITE, w=5))
        parts.append(check(x, y - 200 * s, 0.6 * s))
    return "\n    ".join(parts)


def gavel(x, y, s=1.0) -> str:
    """Judge's gavel and block; (x, y) = block bottom centre."""
    return "\n    ".join([
        rect(x - 70 * s, y - 30 * s, 140 * s, 30 * s, BROWN, INK, 5, 6),
        f'<g transform="rotate(-30 {x:.0f} {y - 100 * s:.0f})">'
        + rect(x - 60 * s, y - 135 * s, 120 * s, 55 * s, "#a0522d", INK, 5, 12)
        + line(x, y - 105 * s, x + 150 * s, y - 105 * s, BROWN, 12) + "</g>"])


def pillar_building(x, y, w=420, h=260, label="", fill="#f4ecd8") -> str:
    """Classical building, (x, y) = bottom-left."""
    parts = [path(f"M{x:.0f} {y - h + 60:.0f} L {x + w / 2:.0f} {y - h:.0f} L {x + w:.0f} {y - h + 60:.0f} Z", fill=fill, w=6)]
    n = 5
    for k in range(n):
        cx = x + 30 + k * (w - 60) / (n - 1)
        parts.append(rect(cx - 16, y - h + 70, 32, h - 110, fill, INK, 5, 4))
    parts.append(rect(x, y - 40, w, 40, fill, INK, 5, 4))
    if label:
        parts.append(text(x + w / 2, y - h + 48, label, 36))
    return "\n    ".join(parts)


def campfire(x, y, s=1.0) -> str:
    return "\n    ".join([
        line(x - 60 * s, y, x + 50 * s, y - 25 * s, BROWN, 12), line(x - 50 * s, y - 25 * s, x + 60 * s, y, BROWN, 12),
        path(f"M{x:.0f} {y - 20 * s:.0f} Q {x - 50 * s:.0f} {y - 70 * s:.0f} {x - 5 * s:.0f} {y - 140 * s:.0f} "
             f"Q {x + 5 * s:.0f} {y - 95 * s:.0f} {x + 25 * s:.0f} {y - 110 * s:.0f} Q {x + 50 * s:.0f} {y - 60 * s:.0f} "
             f"{x:.0f} {y - 20 * s:.0f} Z", fill=OR, w=5),
        path(f"M{x:.0f} {y - 25 * s:.0f} Q {x - 18 * s:.0f} {y - 55 * s:.0f} {x:.0f} {y - 85 * s:.0f} "
             f"Q {x + 18 * s:.0f} {y - 55 * s:.0f} {x:.0f} {y - 25 * s:.0f} Z", fill=YEL, w=3)])


def wheat(x, y, s=1.0) -> str:
    parts = [path(f"M{x:.0f} {y:.0f} Q {x + 6 * s:.0f} {y - 90 * s:.0f} {x:.0f} {y - 180 * s:.0f}", color=GRN, w=6)]
    for k in range(5):
        yy = y - 110 * s - k * 18 * s
        parts.append(path(f"M{x:.0f} {yy:.0f} q {-18 * s:.0f} -6 {-22 * s:.0f} -22 q {16 * s:.0f} 2 {22 * s:.0f} 22 Z",
                          fill=YEL, w=3))
        parts.append(path(f"M{x:.0f} {yy:.0f} q {18 * s:.0f} -6 {22 * s:.0f} -22 q {-16 * s:.0f} 2 {-22 * s:.0f} 22 Z",
                          fill=YEL, w=3))
    return "\n    ".join(parts)


def hut(x, y, s=1.0, fill=PAPER) -> str:
    """(x, y) = bottom centre."""
    return "\n    ".join([
        rect(x - 70 * s, y - 90 * s, 140 * s, 90 * s, fill, INK, 5, 4),
        path(f"M{x - 95 * s:.0f} {y - 85 * s:.0f} L {x:.0f} {y - 170 * s:.0f} L {x + 95 * s:.0f} {y - 85 * s:.0f} Z",
             fill="#d9b779", w=5),
        rect(x - 18 * s, y - 55 * s, 36 * s, 55 * s, BROWN, INK, 4, 4)])


def newspaper(x, y, w=300, h=200, head="TIN TỨC") -> str:
    parts = [rect(x, y, w, h, WHITE, INK, 5, 6), text(x + w / 2, y + 42, head, 34), line(x + 20, y + 58, x + w - 20, y + 58, INK, 4)]
    for k in range(4):
        parts.append(line(x + 20, y + 85 + k * 28, x + w - 20 - (k % 2) * 50, y + 85 + k * 28, GRAY, 4))
    return "\n    ".join(parts)


def mask(x, y, s=1.0, fill=WHITE) -> str:
    """Theatre mask (persona), centre (x, y)."""
    return "\n    ".join([
        path(f"M{x - 80 * s:.0f} {y - 70 * s:.0f} Q {x:.0f} {y - 100 * s:.0f} {x + 80 * s:.0f} {y - 70 * s:.0f} "
             f"Q {x + 90 * s:.0f} {y + 40 * s:.0f} {x:.0f} {y + 95 * s:.0f} Q {x - 90 * s:.0f} {y + 40 * s:.0f} "
             f"{x - 80 * s:.0f} {y - 70 * s:.0f} Z", fill=fill, w=6),
        path(f"M{x - 50 * s:.0f} {y - 20 * s:.0f} q 18 -16 36 0 q -18 10 -36 0 Z M{x + 14 * s:.0f} {y - 20 * s:.0f} "
             f"q 18 -16 36 0 q -18 10 -36 0 Z", fill=INK, w=3),
        path(f"M{x - 35 * s:.0f} {y + 35 * s:.0f} Q {x:.0f} {y + 60 * s:.0f} {x + 35 * s:.0f} {y + 35 * s:.0f}", w=5)])


def shield(x, y, s=1.0, fill=SKY) -> str:
    return path(f"M{x:.0f} {y - 90 * s:.0f} L {x + 75 * s:.0f} {y - 60 * s:.0f} Q {x + 75 * s:.0f} {y + 40 * s:.0f} "
                f"{x:.0f} {y + 95 * s:.0f} Q {x - 75 * s:.0f} {y + 40 * s:.0f} {x - 75 * s:.0f} {y - 60 * s:.0f} Z", fill=fill, w=6)


def fingerprint(x, y, s=1.0, color=BLUE) -> str:
    return "\n    ".join(path(f"M{x - r * s:.0f} {y + 10 * s:.0f} Q {x - r * s:.0f} {y - r * 1.3 * s:.0f} {x:.0f} "
                              f"{y - r * 1.3 * s:.0f} Q {x + r * s:.0f} {y - r * 1.3 * s:.0f} {x + r * s:.0f} {y + 10 * s:.0f}",
                              color=color, w=4) for r in (8, 16, 24, 32))


def board(x, y, w, h, title_text="", lines=4, fill="#2f5d50") -> str:
    """Classroom board with optional title and chalk lines."""
    parts = [rect(x, y, w, h, fill, BROWN, 8, 6)]
    if title_text:
        parts.append(text(x + w / 2, y + 52, title_text, 40, WHITE))
    for k in range(lines):
        parts.append(line(x + 30, y + 90 + k * 34, x + w - 30 - (k % 3) * 40, y + 90 + k * 34, "#d8e6df", 4))
    return "\n    ".join(parts)


def kid(x, y, s=0.7, face="smile", arms="down", color=INK) -> str:
    return person(x, y, s, face, arms, color)


# ══ additions for the "Bản chất con người" video ════════════════
def well(x, y, s=1.0) -> str:
    """Stone well with a roof; (x, y) = bottom centre."""
    parts = [path(f"M{x - 110 * s:.0f} {y - 110 * s:.0f} L {x - 110 * s:.0f} {y:.0f} L {x + 110 * s:.0f} {y:.0f} "
                  f"L {x + 110 * s:.0f} {y - 110 * s:.0f}", fill="#cfc6b8", w=6),
             path(f"M{x - 120 * s:.0f} {y - 110 * s:.0f} Q {x:.0f} {y - 135 * s:.0f} {x + 120 * s:.0f} {y - 110 * s:.0f} "
                  f"Q {x:.0f} {y - 90 * s:.0f} {x - 120 * s:.0f} {y - 110 * s:.0f} Z", fill="#3a4b5c", w=6)]
    for k in range(3):
        yy = y - 30 * s - k * 30 * s
        parts.append(line(x - 110 * s, yy, x + 110 * s, yy, GRAY, 3))
    parts += [line(x - 95 * s, y - 115 * s, x - 95 * s, y - 260 * s, BROWN, 9),
              line(x + 95 * s, y - 115 * s, x + 95 * s, y - 260 * s, BROWN, 9),
              path(f"M{x - 140 * s:.0f} {y - 240 * s:.0f} L {x:.0f} {y - 320 * s:.0f} L {x + 140 * s:.0f} {y - 240 * s:.0f} Z",
                   fill="#c0623a", w=6),
              line(x, y - 250 * s, x, y - 160 * s, INK, 3)]
    return "\n    ".join(parts)


def knife(x, y, s=1.0, angle=0) -> str:
    """Kitchen knife lying horizontally, (x, y) = handle end; blade to the right."""
    body = "\n    ".join([
        rect(x, y - 16 * s, 110 * s, 32 * s, BROWN, INK, 5, 10),
        path(f"M{x + 110 * s:.0f} {y - 22 * s:.0f} L {x + 300 * s:.0f} {y - 22 * s:.0f} Q {x + 350 * s:.0f} {y - 10 * s:.0f} "
             f"{x + 340 * s:.0f} {y + 22 * s:.0f} L {x + 110 * s:.0f} {y + 22 * s:.0f} Z", fill="#dfe6ee", w=5)])
    return f'<g transform="rotate({angle} {x:.0f} {y:.0f})">' + body + "</g>" if angle else body


def boulder(x, y, s=1.0) -> str:
    return path(f"M{x - 70 * s:.0f} {y + 40 * s:.0f} Q {x - 90 * s:.0f} {y - 30 * s:.0f} {x - 30 * s:.0f} {y - 60 * s:.0f} "
                f"Q {x + 40 * s:.0f} {y - 80 * s:.0f} {x + 75 * s:.0f} {y - 20 * s:.0f} Q {x + 90 * s:.0f} {y + 35 * s:.0f} "
                f"{x + 30 * s:.0f} {y + 50 * s:.0f} Z", fill="#b9b2a6", w=6)


def elephant(x, y, s=1.0, fill="#b8c2cc") -> str:
    """Elephant facing right; (x, y) = feet line centre."""
    return "\n    ".join([
        path(f"M{x - 120 * s:.0f} {y - 60 * s:.0f} Q {x - 130 * s:.0f} {y - 190 * s:.0f} {x - 10 * s:.0f} {y - 200 * s:.0f} "
             f"Q {x + 90 * s:.0f} {y - 205 * s:.0f} {x + 100 * s:.0f} {y - 120 * s:.0f} L {x + 100 * s:.0f} {y - 60 * s:.0f} Z",
             fill=fill, w=6),
        *[rect(x + dx * s, y - 70 * s, 34 * s, 70 * s, fill, INK, 5, 6) for dx in (-110, -60, 20, 66)],
        circle(x + 120 * s, y - 160 * s, 55 * s, fill, INK, 6),
        path(f"M{x + 150 * s:.0f} {y - 150 * s:.0f} Q {x + 215 * s:.0f} {y - 90 * s:.0f} {x + 195 * s:.0f} {y - 25 * s:.0f} "
             f"L {x + 172 * s:.0f} {y - 28 * s:.0f} Q {x + 185 * s:.0f} {y - 85 * s:.0f} {x + 130 * s:.0f} {y - 125 * s:.0f} Z",
             fill=fill, w=5),
        path(f"M{x + 95 * s:.0f} {y - 200 * s:.0f} Q {x + 40 * s:.0f} {y - 170 * s:.0f} {x + 80 * s:.0f} {y - 110 * s:.0f}",
             fill="#d6dde4", w=5),
        circle(x + 135 * s, y - 175 * s, 5 * s, INK, INK, 2),
        path(f"M{x + 150 * s:.0f} {y - 120 * s:.0f} q 25 5 35 -10", color=WHITE, w=7)])


def rails(x1, x2, y, color=BROWN) -> str:
    """Railway track seen from the side-top: two rails with sleepers."""
    n = max(2, int((x2 - x1) / 140))
    parts = [line(x1 + k * (x2 - x1) / n, y - 16, x1 + k * (x2 - x1) / n + 8, y + 16, color, 7) for k in range(n + 1)]
    parts += [line(x1, y - 10, x2, y - 10, GRAY, 6), line(x1, y + 10, x2, y + 10, GRAY, 6)]
    return "\n    ".join(parts)


def trolley(x, y, s=1.0, fill="#e04b3a") -> str:
    """Tram car on rails, facing right; (x, y) = wheel line centre."""
    return "\n    ".join([
        rect(x - 130 * s, y - 150 * s, 260 * s, 130 * s, fill, INK, 6, 16),
        *[rect(x + dx * s, y - 130 * s, 55 * s, 50 * s, "#dff1ff", INK, 4, 6) for dx in (-105, -30, 45)],
        circle(x - 70 * s, y - 10 * s, 22 * s, DARK, INK, 5), circle(x + 70 * s, y - 10 * s, 22 * s, DARK, INK, 5),
        path(f"M{x + 140 * s:.0f} {y - 110 * s:.0f} l 40 -12 M{x + 140 * s:.0f} {y - 80 * s:.0f} l 50 0 "
             f"M{x + 140 * s:.0f} {y - 50 * s:.0f} l 40 12", color=GRAY, w=5)])


def lever(x, y, s=1.0, pulled=False) -> str:
    """Track switch lever, (x, y) = base centre."""
    tx, ty = (x + 70 * s, y - 120 * s) if pulled else (x - 70 * s, y - 120 * s)
    return "\n    ".join([rect(x - 50 * s, y - 25 * s, 100 * s, 25 * s, DARK, INK, 5, 6),
                           line(x, y - 20 * s, tx, ty, GRAY, 10), circle(tx, ty, 18 * s, RED, INK, 4)])


def ship(x, y, s=1.0) -> str:
    """Sailing ship, (x, y) = waterline centre."""
    return "\n    ".join([
        path(f"M{x - 220 * s:.0f} {y - 60 * s:.0f} L {x + 230 * s:.0f} {y - 60 * s:.0f} L {x + 170 * s:.0f} {y + 20 * s:.0f} "
             f"L {x - 170 * s:.0f} {y + 20 * s:.0f} Z", fill=BROWN, w=6),
        line(x - 20 * s, y - 60 * s, x - 20 * s, y - 330 * s, INK, 8),
        path(f"M{x - 10 * s:.0f} {y - 320 * s:.0f} Q {x + 140 * s:.0f} {y - 220 * s:.0f} {x - 10 * s:.0f} {y - 90 * s:.0f} Z",
             fill=WHITE, w=5),
        path(f"M{x - 30 * s:.0f} {y - 300 * s:.0f} Q {x - 160 * s:.0f} {y - 210 * s:.0f} {x - 30 * s:.0f} {y - 110 * s:.0f} Z",
             fill="#f4ecd8", w=5),
        path(f"M{x - 20 * s:.0f} {y - 330 * s:.0f} l 60 15 l -60 15", fill=RED, w=4),
        water(x - 280 * s, x + 280 * s, y + 30 * s)])


def pirate(x, y, s=1.0) -> str:
    """Stick figure with bandana, eye patch and a curved sword."""
    hy = y - 190 * s
    return "\n    ".join([
        person(x, y, s, "flat", "reach"),
        path(f"M{x - 30 * s:.0f} {hy - 8 * s:.0f} Q {x:.0f} {hy - 45 * s:.0f} {x + 30 * s:.0f} {hy - 8 * s:.0f} Z",
             fill=RED, w=4),
        circle(x + 10 * s, hy - 4 * s, 8 * s, INK, INK, 2),
        line(x - 30 * s, hy - 8 * s, x + 30 * s, hy - 12 * s, INK, 3),
        path(f"M{x + 60 * s:.0f} {y - 180 * s:.0f} Q {x + 120 * s:.0f} {y - 250 * s:.0f} {x + 110 * s:.0f} {y - 320 * s:.0f}",
             color=GRAY, w=9)])


def captain(x, y, s=1.0) -> str:
    """Stick figure in a captain's hat."""
    hy = y - 190 * s
    return "\n    ".join([
        person(x, y, s, "flat", "down"),
        path(f"M{x - 40 * s:.0f} {hy - 18 * s:.0f} L {x + 40 * s:.0f} {hy - 18 * s:.0f} L {x + 30 * s:.0f} {hy - 50 * s:.0f} "
             f"L {x - 30 * s:.0f} {hy - 50 * s:.0f} Z", fill=BLUE, w=4),
        circle(x, hy - 34 * s, 7 * s, YEL, INK, 2)])


def cell(cx, cy, r, fill="#e8f6e9", nucleus=True) -> str:
    parts = [path(f"M{cx - r:.0f} {cy:.0f} Q {cx - r:.0f} {cy - r * 1.05:.0f} {cx:.0f} {cy - r:.0f} "
                  f"Q {cx + r * 1.05:.0f} {cy - r * 0.95:.0f} {cx + r:.0f} {cy:.0f} Q {cx + r * 0.95:.0f} {cy + r:.0f} "
                  f"{cx:.0f} {cy + r:.0f} Q {cx - r * 1.05:.0f} {cy + r * 1.02:.0f} {cx - r:.0f} {cy:.0f} Z", fill=fill, w=6)]
    if nucleus:
        parts.append(circle(cx - r * 0.25, cy - r * 0.2, r * 0.28, "#c9b6e8", INK, 5))
    return "\n    ".join(parts)


def bacterium(cx, cy, s=1.0, fill="#f6c453", angle=0) -> str:
    body = "\n    ".join([
        rect(cx - 55 * s, cy - 24 * s, 110 * s, 48 * s, fill, INK, 5, int(24 * s)),
        path(f"M{cx + 55 * s:.0f} {cy:.0f} q 20 -14 40 0 q 20 14 40 0", color=INK, w=4)])
    return f'<g transform="rotate({angle} {cx:.0f} {cy:.0f})">' + body + "</g>" if angle else body


def mitochondrion(cx, cy, s=1.0) -> str:
    return "\n    ".join([
        rect(cx - 70 * s, cy - 32 * s, 140 * s, 64 * s, "#f7a76c", INK, 5, int(32 * s)),
        path(f"M{cx - 50 * s:.0f} {cy:.0f} q 10 -22 20 0 q 10 22 20 0 q 10 -22 20 0 q 10 22 20 0 q 10 -22 20 0",
             color=INK, w=4)])


def chloroplast(cx, cy, s=1.0) -> str:
    parts = [rect(cx - 65 * s, cy - 32 * s, 130 * s, 64 * s, "#7cc47f", INK, 5, int(32 * s))]
    for k in range(3):
        parts.append(rect(cx - 45 * s + k * 32 * s, cy - 16 * s, 24 * s, 32 * s, "#3f8f4a", INK, 3, 4))
    return "\n    ".join(parts)


def asteroid(cx, cy, r, fill="#b9a68f") -> str:
    pts = []
    for k in range(9):
        a = k * 2 * math.pi / 9
        rr = r * (1.0 if k % 2 == 0 else 0.8) * (1.05 if k % 3 == 0 else 1.0)
        pts.append(f"{cx + rr * math.cos(a):.0f} {cy + rr * math.sin(a):.0f}")
    return "\n    ".join([path("M" + " L ".join(pts) + " Z", fill=fill, w=5),
                           circle(cx - r * 0.3, cy - r * 0.2, r * 0.18, "none", INK, 3),
                           circle(cx + r * 0.3, cy + r * 0.25, r * 0.12, "none", INK, 3)])


def burst(cx, cy, r, color=OR) -> str:
    """Impact star / collision flash."""
    pts = []
    for k in range(16):
        a = k * math.pi / 8
        rr = r if k % 2 == 0 else r * 0.5
        pts.append(f"{cx + rr * math.cos(a):.0f} {cy + rr * math.sin(a):.0f}")
    return path("M" + " L ".join(pts) + " Z", fill=YEL, color=color, w=5)


def mushroom(x, y, s=1.0, fill=RED) -> str:
    """(x, y) = stem base."""
    return "\n    ".join([
        path(f"M{x - 22 * s:.0f} {y:.0f} Q {x - 28 * s:.0f} {y - 60 * s:.0f} {x - 18 * s:.0f} {y - 100 * s:.0f} "
             f"L {x + 18 * s:.0f} {y - 100 * s:.0f} Q {x + 28 * s:.0f} {y - 60 * s:.0f} {x + 22 * s:.0f} {y:.0f} Z",
             fill="#fff4e0", w=5),
        path(f"M{x - 100 * s:.0f} {y - 95 * s:.0f} Q {x - 95 * s:.0f} {y - 200 * s:.0f} {x:.0f} {y - 205 * s:.0f} "
             f"Q {x + 95 * s:.0f} {y - 200 * s:.0f} {x + 100 * s:.0f} {y - 95 * s:.0f} Z", fill=fill, w=6),
        circle(x - 45 * s, y - 145 * s, 14 * s, WHITE, INK, 3), circle(x + 30 * s, y - 165 * s, 12 * s, WHITE, INK, 3),
        circle(x + 55 * s, y - 120 * s, 10 * s, WHITE, INK, 3), circle(x - 5 * s, y - 120 * s, 9 * s, WHITE, INK, 3)])


def fence(x1, x2, y, h=120, color=BROWN) -> str:
    n = max(2, int((x2 - x1) / 85))
    parts = [path(f"M{x1 + k * (x2 - x1) / n - 12:.0f} {y:.0f} L {x1 + k * (x2 - x1) / n - 12:.0f} {y - h:.0f} "
                  f"L {x1 + k * (x2 - x1) / n:.0f} {y - h - 18:.0f} L {x1 + k * (x2 - x1) / n + 12:.0f} {y - h:.0f} "
                  f"L {x1 + k * (x2 - x1) / n + 12:.0f} {y:.0f} Z", fill="#e3c08f", color=color, w=4) for k in range(n + 1)]
    parts += [line(x1 - 20, y - h * 0.3, x2 + 20, y - h * 0.3, color, 7), line(x1 - 20, y - h * 0.75, x2 + 20, y - h * 0.75, color, 7)]
    return "\n    ".join(parts)


def tiger(x, y, s=1.0) -> str:
    """Prowling tiger facing left; (x, y) = feet line centre."""
    parts = [path(f"M{x - 110 * s:.0f} {y - 70 * s:.0f} Q {x - 100 * s:.0f} {y - 130 * s:.0f} {x:.0f} {y - 125 * s:.0f} "
                  f"Q {x + 110 * s:.0f} {y - 125 * s:.0f} {x + 120 * s:.0f} {y - 70 * s:.0f} Q {x + 110 * s:.0f} {y - 45 * s:.0f} "
                  f"{x:.0f} {y - 45 * s:.0f} Q {x - 100 * s:.0f} {y - 45 * s:.0f} {x - 110 * s:.0f} {y - 70 * s:.0f} Z",
                  fill=OR, w=6)]
    parts += [rect(x + dx * s, y - 55 * s, 26 * s, 55 * s, OR, INK, 5, 8) for dx in (-95, -55, 50, 85)]
    parts += [path(f"M{x + dx * s:.0f} {y - 122 * s:.0f} q 8 25 0 50", color=INK, w=6) for dx in (-40, -5, 30, 65)]
    parts += [circle(x - 140 * s, y - 120 * s, 45 * s, OR, INK, 6),
              path(f"M{x - 172 * s:.0f} {y - 155 * s:.0f} l 8 -28 l 18 18 M{x - 125 * s:.0f} {y - 162 * s:.0f} l 10 -26 l 14 22",
                   fill=OR, w=5),
              circle(x - 155 * s, y - 128 * s, 5 * s, INK, INK, 2), circle(x - 130 * s, y - 128 * s, 5 * s, INK, INK, 2),
              path(f"M{x - 160 * s:.0f} {y - 100 * s:.0f} l 12 8 l 12 -8 l 12 8", color=INK, w=4),
              path(f"M{x + 120 * s:.0f} {y - 80 * s:.0f} Q {x + 190 * s:.0f} {y - 110 * s:.0f} {x + 180 * s:.0f} {y - 170 * s:.0f}",
                   color=INK, w=8)]
    return "\n    ".join(parts)


def mammoth(x, y, s=1.0, fill="#8b5a3c") -> str:
    """Woolly mammoth facing left; (x, y) = feet line centre."""
    return "\n    ".join([
        path(f"M{x + 120 * s:.0f} {y - 60 * s:.0f} Q {x + 140 * s:.0f} {y - 210 * s:.0f} {x - 10 * s:.0f} {y - 230 * s:.0f} "
             f"Q {x - 110 * s:.0f} {y - 230 * s:.0f} {x - 130 * s:.0f} {y - 130 * s:.0f} L {x - 120 * s:.0f} {y - 60 * s:.0f} Z",
             fill=fill, w=6),
        *[rect(x + dx * s, y - 75 * s, 40 * s, 75 * s, fill, INK, 5, 6) for dx in (-120, -70, 40, 85)],
        path(f"M{x - 130 * s:.0f} {y - 150 * s:.0f} Q {x - 190 * s:.0f} {y - 100 * s:.0f} {x - 165 * s:.0f} {y - 30 * s:.0f}",
             color=INK, w=16),
        path(f"M{x - 130 * s:.0f} {y - 150 * s:.0f} Q {x - 190 * s:.0f} {y - 100 * s:.0f} {x - 165 * s:.0f} {y - 30 * s:.0f}",
             color=fill, w=8),
        path(f"M{x - 115 * s:.0f} {y - 115 * s:.0f} Q {x - 200 * s:.0f} {y - 110 * s:.0f} {x - 220 * s:.0f} {y - 180 * s:.0f}",
             color="#fff4e0", w=12),
        circle(x - 95 * s, y - 175 * s, 5 * s, INK, INK, 2)])


def spear(x1, y1, x2, y2) -> str:
    a = math.atan2(y2 - y1, x2 - x1)
    hx, hy = x2 + 40 * math.cos(a), y2 + 40 * math.sin(a)
    lx, ly = x2 + 14 * math.cos(a + 1.57), y2 + 14 * math.sin(a + 1.57)
    rx, ry = x2 + 14 * math.cos(a - 1.57), y2 + 14 * math.sin(a - 1.57)
    return "\n    ".join([line(x1, y1, x2, y2, BROWN, 8),
                           path(f"M{lx:.0f} {ly:.0f} L {hx:.0f} {hy:.0f} L {rx:.0f} {ry:.0f} Z", fill=GRAY, w=4)])


def bolt(x, y, s=1.0, fill=YEL) -> str:
    """Lightning bolt, (x, y) = top."""
    return path(f"M{x:.0f} {y:.0f} L {x - 45 * s:.0f} {y + 110 * s:.0f} L {x - 5 * s:.0f} {y + 105 * s:.0f} "
                f"L {x - 35 * s:.0f} {y + 210 * s:.0f} L {x + 50 * s:.0f} {y + 80 * s:.0f} L {x + 8 * s:.0f} {y + 85 * s:.0f} "
                f"L {x + 35 * s:.0f} {y:.0f} Z", fill=fill, w=5)


def mirror(x, y, s=1.0) -> str:
    """Hand mirror, (x, y) = glass centre."""
    return "\n    ".join([
        line(x, y + 85 * s, x, y + 200 * s, BROWN, 18),
        circle(x, y, 90 * s, "#e9f4fb", INK, 8),
        path(f"M{x - 45 * s:.0f} {y - 30 * s:.0f} Q {x - 30 * s:.0f} {y - 60 * s:.0f} {x:.0f} {y - 65 * s:.0f}", color=WHITE, w=8)])


def candy(x, y, s=1.0, fill="#f27bb0") -> str:
    return "\n    ".join([
        path(f"M{x - 40 * s:.0f} {y:.0f} L {x - 80 * s:.0f} {y - 28 * s:.0f} L {x - 80 * s:.0f} {y + 28 * s:.0f} Z", fill=fill, w=4),
        path(f"M{x + 40 * s:.0f} {y:.0f} L {x + 80 * s:.0f} {y - 28 * s:.0f} L {x + 80 * s:.0f} {y + 28 * s:.0f} Z", fill=fill, w=4),
        circle(x, y, 40 * s, fill, INK, 5),
        path(f"M{x - 25 * s:.0f} {y - 20 * s:.0f} Q {x:.0f} {y + 10 * s:.0f} {x + 25 * s:.0f} {y - 20 * s:.0f}", color=WHITE, w=5)])


def phone(x, y, s=1.0, screen="#dff1ff") -> str:
    """Smartphone, (x, y) = top-left."""
    return "\n    ".join([rect(x, y, 120 * s, 220 * s, DARK, INK, 5, 18),
                           rect(x + 10 * s, y + 22 * s, 100 * s, 168 * s, screen, INK, 3, 6),
                           circle(x + 60 * s, y + 205 * s, 7 * s, WHITE, INK, 2)])


def watering_can(x, y, s=1.0) -> str:
    """(x, y) = bottom centre; spout to the left."""
    return "\n    ".join([
        rect(x - 60 * s, y - 120 * s, 120 * s, 120 * s, "#7fb8e6", INK, 6, 14),
        path(f"M{x - 60 * s:.0f} {y - 40 * s:.0f} L {x - 150 * s:.0f} {y - 130 * s:.0f}", color=INK, w=12),
        path(f"M{x - 60 * s:.0f} {y - 40 * s:.0f} L {x - 150 * s:.0f} {y - 130 * s:.0f}", color="#7fb8e6", w=5),
        path(f"M{x + 60 * s:.0f} {y - 100 * s:.0f} Q {x + 110 * s:.0f} {y - 80 * s:.0f} {x + 60 * s:.0f} {y - 30 * s:.0f}", w=7),
        *[line(x - 160 * s - k * 12 * s, y - 120 * s + k * 30 * s, x - 175 * s - k * 12 * s, y - 95 * s + k * 30 * s, BLUE, 4)
          for k in range(3)]])


def chest(x, y, w=260, h=170, fill="#c98a4a") -> str:
    """Storehouse / treasure chest, (x, y) = top-left."""
    return "\n    ".join([rect(x, y + h * 0.3, w, h * 0.7, fill, INK, 6, 8),
                           path(f"M{x:.0f} {y + h * 0.3:.0f} Q {x + w / 2:.0f} {y - h * 0.15:.0f} {x + w:.0f} {y + h * 0.3:.0f} Z",
                                fill=fill, w=6),
                           rect(x + w / 2 - 20, y + h * 0.3 - 10, 40, 45, YEL, INK, 4, 4)])


def tribe(x, y, n=5, s=0.55, gap=70, face="smile", arms="down") -> str:
    return "\n    ".join(person(x + (k - (n - 1) / 2) * gap, y, s, face, arms) for k in range(n))


def slope_water(x, y, s=1.0) -> str:
    """Hill with water running down to a pool; (x, y) = bottom-left of the hill."""
    return "\n    ".join([
        path(f"M{x:.0f} {y:.0f} L {x:.0f} {y - 260 * s:.0f} Q {x + 120 * s:.0f} {y - 250 * s:.0f} {x + 250 * s:.0f} {y - 120 * s:.0f} "
             f"Q {x + 330 * s:.0f} {y - 30 * s:.0f} {x + 420 * s:.0f} {y:.0f} Z", fill="#cfe3b5", w=6),
        path(f"M{x + 30 * s:.0f} {y - 250 * s:.0f} Q {x + 150 * s:.0f} {y - 225 * s:.0f} {x + 250 * s:.0f} {y - 110 * s:.0f} "
             f"Q {x + 320 * s:.0f} {y - 40 * s:.0f} {x + 410 * s:.0f} {y - 10 * s:.0f}", color=BLUE, w=12),
        path(f"M{x + 380 * s:.0f} {y:.0f} Q {x + 470 * s:.0f} {y - 30 * s:.0f} {x + 560 * s:.0f} {y:.0f} Z", fill="#9cc9f0", w=5),
        arrow(x + 200 * s, y - 210 * s, x + 300 * s, y - 120 * s, BLUE, 5, 16)])


# ══ additions for the "LGBT: tự nhiên hay trái tự nhiên" video ══
RAINBOW = ["#e04b3a", "#f08a3c", "#f6c453", "#5aa469", "#3b7dd8", "#8e6cc9"]


def rainbow(cx, cy, r, w=16, n=6) -> str:
    """Arc rainbow; (cx, cy) = centre of the arcs' baseline."""
    parts = []
    for k, c in enumerate(RAINBOW[:n]):
        rr = r - k * w
        parts.append(path(f"M{cx - rr:.0f} {cy:.0f} A {rr:.0f} {rr:.0f} 0 0 1 {cx + rr:.0f} {cy:.0f}", color=c, w=w))
    return "\n    ".join(parts)


def woman(x, y, s=1.0, face="smile", arms="down", hair=BROWN) -> str:
    hy = y - 190 * s
    return "\n    ".join([
        path(f"M{x - 34 * s:.0f} {hy + 30 * s:.0f} Q {x - 42 * s:.0f} {hy - 40 * s:.0f} {x:.0f} {hy - 36 * s:.0f} "
             f"Q {x + 42 * s:.0f} {hy - 40 * s:.0f} {x + 34 * s:.0f} {hy + 30 * s:.0f}", color=hair, w=9),
        person(x, y, s, face, arms),
        path(f"M{x - 30 * s:.0f} {y - 60 * s:.0f} L {x:.0f} {y - 135 * s:.0f} L {x + 30 * s:.0f} {y - 60 * s:.0f} Z",
             fill="#f7c6d0", w=4)])


def penguin(x, y, s=1.0) -> str:
    """(x, y) = feet."""
    return "\n    ".join([
        path(f"M{x - 50 * s:.0f} {y - 20 * s:.0f} Q {x - 70 * s:.0f} {y - 150 * s:.0f} {x:.0f} {y - 200 * s:.0f} "
             f"Q {x + 70 * s:.0f} {y - 150 * s:.0f} {x + 50 * s:.0f} {y - 20 * s:.0f} Z", fill=DARK, w=5),
        path(f"M{x - 30 * s:.0f} {y - 25 * s:.0f} Q {x - 42 * s:.0f} {y - 120 * s:.0f} {x:.0f} {y - 150 * s:.0f} "
             f"Q {x + 42 * s:.0f} {y - 120 * s:.0f} {x + 30 * s:.0f} {y - 25 * s:.0f} Z", fill=WHITE, w=4),
        circle(x - 14 * s, y - 168 * s, 5 * s, WHITE, WHITE, 2), circle(x + 14 * s, y - 168 * s, 5 * s, WHITE, WHITE, 2),
        path(f"M{x - 10 * s:.0f} {y - 152 * s:.0f} L {x:.0f} {y - 138 * s:.0f} L {x + 10 * s:.0f} {y - 152 * s:.0f} Z", fill=OR, w=3),
        path(f"M{x - 30 * s:.0f} {y:.0f} l 20 -14 M{x + 30 * s:.0f} {y:.0f} l -20 -14", color=OR, w=7)])


def swan(x, y, s=1.0, fill=DARK, face_left=False) -> str:
    """Swimming swan; (x, y) = waterline centre."""
    k = -1 if face_left else 1
    return "\n    ".join([
        path(f"M{x - 90 * s * k:.0f} {y:.0f} Q {x - 100 * s * k:.0f} {y - 70 * s:.0f} {x - 20 * s * k:.0f} {y - 60 * s:.0f} "
             f"Q {x + 40 * s * k:.0f} {y - 55 * s:.0f} {x + 70 * s * k:.0f} {y:.0f} Z", fill=fill, w=5),
        path(f"M{x + 40 * s * k:.0f} {y - 40 * s:.0f} Q {x + 70 * s * k:.0f} {y - 110 * s:.0f} {x + 45 * s * k:.0f} {y - 150 * s:.0f} "
             f"Q {x + 30 * s * k:.0f} {y - 170 * s:.0f} {x + 60 * s * k:.0f} {y - 175 * s:.0f}", color=INK, w=int(20 * s) or 12),
        path(f"M{x + 40 * s * k:.0f} {y - 40 * s:.0f} Q {x + 70 * s * k:.0f} {y - 110 * s:.0f} {x + 45 * s * k:.0f} {y - 150 * s:.0f} "
             f"Q {x + 30 * s * k:.0f} {y - 170 * s:.0f} {x + 60 * s * k:.0f} {y - 175 * s:.0f}", color=fill, w=int(12 * s) or 7),
        path(f"M{x + 58 * s * k:.0f} {y - 180 * s:.0f} l {28 * s * k:.0f} 8 l {-26 * s * k:.0f} 6 Z", fill=RED, w=3)])


def ape(x, y, s=1.0, fill="#5b4636") -> str:
    """Sitting bonobo; (x, y) = bottom centre."""
    hy = y - 170 * s
    return "\n    ".join([
        path(f"M{x - 70 * s:.0f} {y:.0f} Q {x - 85 * s:.0f} {y - 110 * s:.0f} {x:.0f} {y - 125 * s:.0f} "
             f"Q {x + 85 * s:.0f} {y - 110 * s:.0f} {x + 70 * s:.0f} {y:.0f} Z", fill=fill, w=5),
        circle(x - 48 * s, hy, 14 * s, "#d9b48f", INK, 4), circle(x + 48 * s, hy, 14 * s, "#d9b48f", INK, 4),
        circle(x, hy, 45 * s, fill, INK, 5),
        path(f"M{x - 28 * s:.0f} {hy + 2 * s:.0f} Q {x:.0f} {hy - 18 * s:.0f} {x + 28 * s:.0f} {hy + 2 * s:.0f} "
             f"Q {x + 30 * s:.0f} {hy + 38 * s:.0f} {x:.0f} {hy + 38 * s:.0f} Q {x - 30 * s:.0f} {hy + 38 * s:.0f} "
             f"{x - 28 * s:.0f} {hy + 2 * s:.0f} Z", fill="#d9b48f", w=4),
        circle(x - 12 * s, hy + 4 * s, 4 * s, INK, INK, 2), circle(x + 12 * s, hy + 4 * s, 4 * s, INK, INK, 2),
        path(f"M{x - 10 * s:.0f} {hy + 24 * s:.0f} q {10 * s:.0f} {8 * s:.0f} {20 * s:.0f} 0", w=3)])


def flower_parts(x, y, s=1.0) -> str:
    """Open flower showing stamens (male) and pistil (female); (x, y) = stem base."""
    cy = y - 230 * s
    parts = [path(f"M{x:.0f} {y:.0f} Q {x + 10 * s:.0f} {y - 120 * s:.0f} {x:.0f} {cy + 30 * s:.0f}", color=GRN, w=8)]
    for a in (-60, -25, 25, 60):
        rad = math.radians(a - 90)
        px, py = x + 85 * s * math.cos(rad), cy + 85 * s * math.sin(rad)
        parts.append(f'<ellipse cx="{px:.0f}" cy="{py:.0f}" rx="{38 * s:.0f}" ry="{62 * s:.0f}" fill="#f7c6d0" stroke="{INK}" '
                     f'stroke-width="5" transform="rotate({a} {px:.0f} {py:.0f})"/>')
    parts.append(path(f"M{x - 60 * s:.0f} {cy + 10 * s:.0f} Q {x:.0f} {cy + 60 * s:.0f} {x + 60 * s:.0f} {cy + 10 * s:.0f}",
                      fill="#9fd49a", w=5))
    for dx in (-36, -18, 18, 36):          # stamens
        parts.append(line(x + dx * s, cy + 10 * s, x + dx * 1.5 * s, cy - 70 * s, BROWN, 4))
        parts.append(circle(x + dx * 1.5 * s, cy - 76 * s, 9 * s, YEL, INK, 3))
    parts.append(line(x, cy + 10 * s, x, cy - 95 * s, GRN, 9))          # pistil
    parts.append(circle(x, cy - 100 * s, 13 * s, "#5aa469", INK, 4))
    return "\n    ".join(parts)


def dna(x, y, h=300, s=1.0) -> str:
    """Vertical double helix; (x, y) = top."""
    n = 6
    a = [f"{x + 40 * s * math.sin(k * math.pi / 3):.0f} {y + k * h / (2 * n):.0f}" for k in range(2 * n + 1)]
    b = [f"{x - 40 * s * math.sin(k * math.pi / 3):.0f} {y + k * h / (2 * n):.0f}" for k in range(2 * n + 1)]
    parts = [path("M" + " L ".join(a), color=BLUE, w=7), path("M" + " L ".join(b), color=RED, w=7)]
    for k in range(1, 2 * n, 2):
        yy = y + k * h / (2 * n)
        parts.append(line(x - 40 * s * math.sin(k * math.pi / 3), yy, x + 40 * s * math.sin(k * math.pi / 3), yy, GRAY, 4))
    return "\n    ".join(parts)


def egg(x, y, s=1.0, fill="#fff8ec") -> str:
    return f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="{32 * s:.0f}" ry="{42 * s:.0f}" fill="{fill}" stroke="{INK}" stroke-width="5"/>'


def nest(x, y, s=1.0) -> str:
    return "\n    ".join([path(f"M{x - 110 * s:.0f} {y - 30 * s:.0f} Q {x:.0f} {y + 40 * s:.0f} {x + 110 * s:.0f} {y - 30 * s:.0f} "
                                f"Q {x:.0f} {y - 5 * s:.0f} {x - 110 * s:.0f} {y - 30 * s:.0f} Z", fill="#c9a77a", w=5),
                           path(f"M{x - 90 * s:.0f} {y - 18 * s:.0f} l 40 10 M{x - 20 * s:.0f} {y - 4 * s:.0f} l 50 -4 "
                                f"M{x + 40 * s:.0f} {y - 14 * s:.0f} l 40 -8", color=BROWN, w=4)])


def calendar(x, y, w=220, h=230, top="THÁNG 5", big="17") -> str:
    """(x, y) = top-left."""
    return "\n    ".join([rect(x, y, w, h, WHITE, INK, 6, 14), rect(x, y, w, 64, RED, INK, 6, 14),
                           text(x + w / 2, y + 46, top, 36, WHITE), text(x + w / 2, y + h - 40, big, 110, INK)])


def yinyang(cx, cy, r) -> str:
    return "\n    ".join([
        circle(cx, cy, r, WHITE, INK, 6),
        path(f"M{cx:.0f} {cy - r:.0f} A {r / 2:.0f} {r / 2:.0f} 0 0 1 {cx:.0f} {cy:.0f} A {r / 2:.0f} {r / 2:.0f} 0 0 0 "
             f"{cx:.0f} {cy + r:.0f} A {r:.0f} {r:.0f} 0 0 1 {cx:.0f} {cy - r:.0f} Z", fill=DARK, w=4),
        circle(cx, cy - r / 2, r / 7, WHITE, INK, 3), circle(cx, cy + r / 2, r / 7, DARK, INK, 3)])


def lgbt_flag(x, y, w=260, h=170) -> str:
    """Six-stripe flag on a pole; (x, y) = top-left of the cloth."""
    sh = h / 6
    parts = [line(x, y - 10, x, y + h + 160, BROWN, 10)]
    for k, c in enumerate(RAINBOW):
        parts.append(f'<rect x="{x:.0f}" y="{y + k * sh:.0f}" width="{w:.0f}" height="{sh:.0f}" fill="{c}"/>')
    parts.append(rect(x, y, w, h, "none", INK, 5, 4))
    return "\n    ".join(parts)


def half_person(x, y, s=1.0) -> str:
    """Ardhanarishvara-like figure: left half blue (masculine), right half pink (feminine)."""
    hy = y - 190 * s
    return "\n    ".join([
        path(f"M{x:.0f} {y - 155 * s:.0f} L {x - 60 * s:.0f} {y - 140 * s:.0f} L {x - 50 * s:.0f} {y:.0f} L {x:.0f} {y:.0f} Z",
             fill="#9cc3f0", w=5),
        path(f"M{x:.0f} {y - 155 * s:.0f} L {x + 55 * s:.0f} {y - 140 * s:.0f} Q {x + 80 * s:.0f} {y - 40 * s:.0f} "
             f"{x + 60 * s:.0f} {y:.0f} L {x:.0f} {y:.0f} Z", fill="#f7c6d0", w=5),
        path(f"M{x:.0f} {hy - 36 * s:.0f} A {36 * s:.0f} {36 * s:.0f} 0 0 0 {x:.0f} {hy + 36 * s:.0f} Z", fill="#9cc3f0", w=5),
        path(f"M{x:.0f} {hy - 36 * s:.0f} A {36 * s:.0f} {36 * s:.0f} 0 0 1 {x:.0f} {hy + 36 * s:.0f} Z", fill="#f7c6d0", w=5),
        path(f"M{x + 10 * s:.0f} {hy - 34 * s:.0f} Q {x + 60 * s:.0f} {hy - 20 * s:.0f} {x + 50 * s:.0f} {hy + 50 * s:.0f}",
             color=DARK, w=8),
        circle(x - 14 * s, hy - 4 * s, 4 * s, INK, INK, 2), circle(x + 14 * s, hy - 4 * s, 4 * s, INK, INK, 2),
        path(f"M{x - 12 * s:.0f} {hy + 14 * s:.0f} q {12 * s:.0f} {9 * s:.0f} {24 * s:.0f} 0", w=4)])


def rice_bowl(x, y, s=1.0, rice=True) -> str:
    """Bowl seen from the side; (x, y) = bottom centre."""
    parts = []
    if rice:
        parts.append(path(f"M{x - 85 * s:.0f} {y - 80 * s:.0f} Q {x:.0f} {y - 150 * s:.0f} {x + 85 * s:.0f} {y - 80 * s:.0f} Z",
                          fill=WHITE, w=5))
    parts += [path(f"M{x - 100 * s:.0f} {y - 80 * s:.0f} L {x + 100 * s:.0f} {y - 80 * s:.0f} Q {x + 90 * s:.0f} {y - 10 * s:.0f} "
                   f"{x:.0f} {y - 5 * s:.0f} Q {x - 90 * s:.0f} {y - 10 * s:.0f} {x - 100 * s:.0f} {y - 80 * s:.0f} Z",
                   fill="#cfe6ff", w=6),
              rect(x - 35 * s, y - 12 * s, 70 * s, 14 * s, "#cfe6ff", INK, 5, 4),
              path(f"M{x - 60 * s:.0f} {y - 50 * s:.0f} q 20 -12 40 0 q 20 12 40 0 q 20 -12 40 0", color=BLUE, w=4)]
    return "\n    ".join(parts)


# ══ additions for the "Những khó khăn của Đức Phật" video ═══════
def monkey(x, y, s=1.0, fill="#a0764a") -> str:
    """Sitting monkey holding a honeycomb-ish offering; (x, y) = bottom centre."""
    hy = y - 120 * s
    return "\n    ".join([
        path(f"M{x + 40 * s:.0f} {y - 10 * s:.0f} Q {x + 110 * s:.0f} {y - 20 * s:.0f} {x + 100 * s:.0f} {y - 90 * s:.0f}",
             color=fill, w=8),
        path(f"M{x - 45 * s:.0f} {y:.0f} Q {x - 55 * s:.0f} {y - 80 * s:.0f} {x:.0f} {y - 90 * s:.0f} "
             f"Q {x + 55 * s:.0f} {y - 80 * s:.0f} {x + 45 * s:.0f} {y:.0f} Z", fill=fill, w=5),
        circle(x - 34 * s, hy, 12 * s, "#e8c9a6", INK, 4), circle(x + 34 * s, hy, 12 * s, "#e8c9a6", INK, 4),
        circle(x, hy, 32 * s, fill, INK, 5),
        path(f"M{x - 20 * s:.0f} {hy:.0f} Q {x:.0f} {hy - 14 * s:.0f} {x + 20 * s:.0f} {hy:.0f} Q {x + 22 * s:.0f} {hy + 26 * s:.0f} "
             f"{x:.0f} {hy + 26 * s:.0f} Q {x - 22 * s:.0f} {hy + 26 * s:.0f} {x - 20 * s:.0f} {hy:.0f} Z", fill="#e8c9a6", w=3),
        circle(x - 8 * s, hy + 4 * s, 3 * s, INK, INK, 2), circle(x + 8 * s, hy + 4 * s, 3 * s, INK, INK, 2)])


def cow(x, y, s=1.0, fill=WHITE) -> str:
    """Cow facing right; (x, y) = feet line centre."""
    return "\n    ".join([
        rect(x - 110 * s, y - 150 * s, 200 * s, 90 * s, fill, INK, 6, int(40 * s)),
        *[rect(x + dx * s, y - 70 * s, 22 * s, 70 * s, fill, INK, 5, 6) for dx in (-95, -60, 40, 70)],
        circle(x - 40 * s, y - 115 * s, 18 * s, DARK, DARK, 2), circle(x + 30 * s, y - 130 * s, 12 * s, DARK, DARK, 2),
        rect(x + 85 * s, y - 175 * s, 60 * s, 70 * s, fill, INK, 5, int(22 * s)),
        rect(x + 110 * s, y - 130 * s, 45 * s, 30 * s, "#f7c6d0", INK, 4, 12),
        path(f"M{x + 90 * s:.0f} {y - 172 * s:.0f} l -12 -18 M{x + 140 * s:.0f} {y - 172 * s:.0f} l 12 -18", color=BROWN, w=5),
        circle(x + 115 * s, y - 155 * s, 4 * s, INK, INK, 2),
        path(f"M{x - 110 * s:.0f} {y - 130 * s:.0f} q -30 20 -20 60", w=4)])


def raft(x, y, w=320, s=1.0) -> str:
    """Bamboo raft; (x, y) = centre of the deck."""
    parts = [rect(x - w / 2 + k * w / 6, y - 18 * s, w / 6, 36 * s, "#d9b779", BROWN, 4, 14) for k in range(6)]
    parts += [line(x - w / 2 + 10, y - 8 * s, x + w / 2 - 10, y - 8 * s, BROWN, 4),
              line(x - w / 2 + 10, y + 8 * s, x + w / 2 - 10, y + 8 * s, BROWN, 4)]
    return "\n    ".join(parts)


def bare_tree(x, y, s=1.0) -> str:
    """Dead tree without leaves; (x, y) = base."""
    return "\n    ".join([
        path(f"M{x - 16 * s:.0f} {y:.0f} Q {x - 8 * s:.0f} {y - 120 * s:.0f} {x:.0f} {y - 220 * s:.0f} "
             f"L {x + 12 * s:.0f} {y - 220 * s:.0f} Q {x + 14 * s:.0f} {y - 120 * s:.0f} {x + 22 * s:.0f} {y:.0f} Z", fill=BROWN, w=5),
        path(f"M{x:.0f} {y - 150 * s:.0f} L {x - 70 * s:.0f} {y - 230 * s:.0f} M{x - 40 * s:.0f} {y - 195 * s:.0f} L {x - 50 * s:.0f} {y - 260 * s:.0f} "
             f"M{x + 6 * s:.0f} {y - 200 * s:.0f} L {x + 70 * s:.0f} {y - 270 * s:.0f} M{x + 40 * s:.0f} {y - 235 * s:.0f} L {x + 90 * s:.0f} {y - 240 * s:.0f} "
             f"M{x + 4 * s:.0f} {y - 215 * s:.0f} L {x - 10 * s:.0f} {y - 290 * s:.0f}", color=BROWN, w=7)])


def cart(x, y, s=1.0) -> str:
    """Old cart tied together with rope; (x, y) = ground centre."""
    return "\n    ".join([
        path(f"M{x - 150 * s:.0f} {y - 140 * s:.0f} L {x + 130 * s:.0f} {y - 150 * s:.0f} L {x + 120 * s:.0f} {y - 70 * s:.0f} "
             f"L {x - 140 * s:.0f} {y - 60 * s:.0f} Z", fill="#c9a77a", w=6),
        path(f"M{x - 60 * s:.0f} {y - 145 * s:.0f} l 10 80 M{x + 30 * s:.0f} {y - 148 * s:.0f} l -6 82", color=BROWN, w=4),
        circle(x - 90 * s, y - 45 * s, 45 * s, "none", BROWN, 9), circle(x + 80 * s, y - 50 * s, 45 * s, "none", BROWN, 9),
        path(f"M{x - 90 * s:.0f} {y - 90 * s:.0f} L {x - 90 * s:.0f} {y:.0f} M{x - 135 * s:.0f} {y - 45 * s:.0f} L {x - 45 * s:.0f} {y - 45 * s:.0f}",
             color=BROWN, w=4),
        path(f"M{x - 115 * s:.0f} {y - 150 * s:.0f} q 20 50 -5 90 M{x + 100 * s:.0f} {y - 155 * s:.0f} q -25 50 5 95 "
             f"M{x - 20 * s:.0f} {y - 150 * s:.0f} q 15 45 -5 85", color="#d9a441", w=6),
        line(x + 130 * s, y - 100 * s, x + 230 * s, y - 120 * s, BROWN, 8)])


def brahma(x, y, s=1.0) -> str:
    """Kneeling deity with a crown and folded hands; (x, y) = knee line centre."""
    hy = y - 170 * s
    return "\n    ".join([
        path(f"M{x - 60 * s:.0f} {y:.0f} Q {x - 70 * s:.0f} {y - 90 * s:.0f} {x - 20 * s:.0f} {y - 130 * s:.0f} "
             f"L {x + 20 * s:.0f} {y - 130 * s:.0f} Q {x + 70 * s:.0f} {y - 90 * s:.0f} {x + 60 * s:.0f} {y:.0f} Z", fill="#f6d77a", w=5),
        path(f"M{x - 20 * s:.0f} {y - 125 * s:.0f} L {x + 50 * s:.0f} {y - 20 * s:.0f}", color=RED, w=6),
        circle(x, hy, 32 * s, SKIN, INK, 5),
        path(f"M{x - 30 * s:.0f} {hy - 26 * s:.0f} L {x - 30 * s:.0f} {hy - 62 * s:.0f} L {x - 15 * s:.0f} {hy - 44 * s:.0f} "
             f"L {x:.0f} {hy - 70 * s:.0f} L {x + 15 * s:.0f} {hy - 44 * s:.0f} L {x + 30 * s:.0f} {hy - 62 * s:.0f} L {x + 30 * s:.0f} {hy - 26 * s:.0f} Z",
             fill=YEL, w=4),
        path(f"M{x - 10 * s:.0f} {hy - 4 * s:.0f} l 0 3 M{x + 10 * s:.0f} {hy - 4 * s:.0f} l 0 3 "
             f"M{x - 8 * s:.0f} {hy + 12 * s:.0f} q 8 6 16 0", w=4),
        path(f"M{x - 4 * s:.0f} {y - 115 * s:.0f} L {x + 4 * s:.0f} {y - 75 * s:.0f} L {x + 12 * s:.0f} {y - 115 * s:.0f}", fill=SKIN, w=4)])


def lotus_pond(x1, x2, y) -> str:
    """Cross-section of a pond: mud, water line, lotuses at three depths; (y) = water line."""
    w = x2 - x1
    parts = [rect(x1, y, w, 260, "#d9ecfa", BLUE, 5, 10), path(f"M{x1:.0f} {y + 260:.0f} Q {x1 + w / 2:.0f} {y + 220:.0f} {x2:.0f} {y + 260:.0f} "
                                                              f"L {x2:.0f} {y + 300:.0f} L {x1:.0f} {y + 300:.0f} Z", fill="#8a6a4a", w=5),
             water(x1, x2, y, BLUE)]
    for k, top in enumerate((y + 150, y + 5, y - 120)):
        cx = x1 + w * (0.2 + 0.3 * k)
        parts.append(path(f"M{cx:.0f} {y + 255:.0f} Q {cx + 10:.0f} {(y + 255 + top) / 2:.0f} {cx:.0f} {top + 30:.0f}", color=GRN, w=6))
        parts.append(path(f"M{cx:.0f} {top + 30:.0f} Q {cx - 30:.0f} {top:.0f} {cx:.0f} {top - 40:.0f} Q {cx + 30:.0f} {top:.0f} {cx:.0f} {top + 30:.0f} Z",
                          fill="#f7c6d0", w=5))
    return "\n    ".join(parts)


def skinny_buddha(x, y, s=1.0) -> str:
    """Emaciated seated ascetic; (x, y) = lap bottom centre."""
    hy = y - 175 * s
    return "\n    ".join([
        path(f"M{x - 100 * s:.0f} {y:.0f} Q {x - 100 * s:.0f} {y - 35 * s:.0f} {x - 45 * s:.0f} {y - 45 * s:.0f} "
             f"L {x + 45 * s:.0f} {y - 45 * s:.0f} Q {x + 100 * s:.0f} {y - 35 * s:.0f} {x + 100 * s:.0f} {y:.0f} Z", fill="#d9b48f", w=5),
        path(f"M{x - 32 * s:.0f} {y - 45 * s:.0f} L {x - 26 * s:.0f} {y - 140 * s:.0f} L {x + 26 * s:.0f} {y - 140 * s:.0f} "
             f"L {x + 32 * s:.0f} {y - 45 * s:.0f} Z", fill="#e7c9a6", w=5),
        *[path(f"M{x - 22 * s:.0f} {y - (125 - 18 * k) * s:.0f} q {22 * s:.0f} 8 {44 * s:.0f} 0", color=BROWN, w=3) for k in range(4)],
        path(f"M{x - 28 * s:.0f} {y - 130 * s:.0f} L {x - 60 * s:.0f} {y - 60 * s:.0f} L {x - 10 * s:.0f} {y - 50 * s:.0f} "
             f"M{x + 28 * s:.0f} {y - 130 * s:.0f} L {x + 60 * s:.0f} {y - 60 * s:.0f} L {x + 10 * s:.0f} {y - 50 * s:.0f}", w=5),
        f'<ellipse cx="{x:.0f}" cy="{hy:.0f}" rx="{26 * s:.0f}" ry="{34 * s:.0f}" fill="#e7c9a6" stroke="{INK}" stroke-width="5"/>',
        path(f"M{x - 14 * s:.0f} {hy - 4 * s:.0f} q 6 4 10 0 M{x + 4 * s:.0f} {hy - 4 * s:.0f} q 6 4 10 0 "
             f"M{x - 8 * s:.0f} {hy + 16 * s:.0f} l 16 0", w=3),
        path(f"M{x - 18 * s:.0f} {hy + 2 * s:.0f} q -4 12 4 18 M{x + 18 * s:.0f} {hy + 2 * s:.0f} q 4 12 -4 18", color=GRAY, w=3)])


def archer(x, y, s=1.0) -> str:
    """Stick figure drawing a bow, facing right."""
    sh = y - 150 * s
    return "\n    ".join([
        person(x, y, s, "flat", "point"),
        path(f"M{x + 60 * s:.0f} {sh - 50 * s:.0f} Q {x + 110 * s:.0f} {sh + 10 * s:.0f} {x + 60 * s:.0f} {sh + 70 * s:.0f}", color=BROWN, w=6),
        line(x + 60 * s, sh - 50 * s, x + 60 * s, sh + 70 * s, GRAY, 2),
        arrow(x + 20 * s, sh + 10 * s, x + 140 * s, sh + 10 * s, INK, 4, 14)])


def golden_bowl(x, y, s=1.0) -> str:
    return path(f"M{x - 70 * s:.0f} {y - 40 * s:.0f} L {x + 70 * s:.0f} {y - 40 * s:.0f} Q {x + 65 * s:.0f} {y + 30 * s:.0f} {x:.0f} {y + 32 * s:.0f} "
                f"Q {x - 65 * s:.0f} {y + 30 * s:.0f} {x - 70 * s:.0f} {y - 40 * s:.0f} Z", fill=YEL, color=OR, w=6)


def moon_eclipse(cx, cy, r) -> str:
    return "\n    ".join([circle(cx, cy, r, "#fff4cc", INK, 5),
                           path(f"M{cx + r * 0.2:.0f} {cy - r:.0f} A {r:.0f} {r:.0f} 0 0 1 {cx + r * 0.2:.0f} {cy + r:.0f} "
                                f"A {r * 0.8:.0f} {r:.0f} 0 0 0 {cx + r * 0.2:.0f} {cy - r:.0f} Z", fill=DARK, w=4)])


def nun(x, y, s=1.0) -> str:
    """Nun: monk figure in a darker robe with a slimmer silhouette."""
    return monk(x, y, s, "#b9774a")


def votive(x, y, s=1.0) -> str:
    """Incense sticks in a pot with smoke."""
    return "\n    ".join([
        rect(x - 45 * s, y - 60 * s, 90 * s, 60 * s, "#c0623a", INK, 5, 10),
        *[line(x + dx * s, y - 60 * s, x + dx * 1.4 * s, y - 170 * s, BROWN, 4) for dx in (-15, 0, 15)],
        path(f"M{x:.0f} {y - 175 * s:.0f} q -20 -25 0 -50 q 20 -25 0 -50", color=GRAY, w=4)])


# ══ additions for the "Người học thông thái" video ═══════════════
def lectern(x, y, s=1.0) -> str:
    """Speaker's podium, (x, y) = bottom centre."""
    return "\n    ".join([
        path(f"M{x - 70 * s:.0f} {y:.0f} L {x - 55 * s:.0f} {y - 170 * s:.0f} L {x + 55 * s:.0f} {y - 170 * s:.0f} L {x + 70 * s:.0f} {y:.0f} Z",
             fill="#a0764a", w=6),
        rect(x - 90 * s, y - 200 * s, 180 * s, 34 * s, "#c9a77a", INK, 6, 6),
        line(x + 30 * s, y - 200 * s, x + 50 * s, y - 260 * s, DARK, 5), circle(x + 52 * s, y - 266 * s, 9 * s, DARK, DARK, 2)])


def throne(x, y, s=1.0) -> str:
    """(x, y) = floor centre."""
    return "\n    ".join([
        rect(x - 70 * s, y - 300 * s, 140 * s, 210 * s, "#c0392b", OR, 7, int(30 * s)),
        rect(x - 90 * s, y - 120 * s, 180 * s, 50 * s, "#e8b23b", INK, 6, 10),
        line(x - 75 * s, y - 70 * s, x - 75 * s, y, BROWN, 9), line(x + 75 * s, y - 70 * s, x + 75 * s, y, BROWN, 9),
        crown(x, y - 330 * s, 0.6 * s)])


def megaphone(x, y, s=1.0) -> str:
    """Pointing right; (x, y) = handle grip."""
    return "\n    ".join([
        path(f"M{x - 40 * s:.0f} {y - 40 * s:.0f} L {x + 80 * s:.0f} {y - 90 * s:.0f} L {x + 80 * s:.0f} {y + 50 * s:.0f} "
             f"L {x - 40 * s:.0f} {y + 10 * s:.0f} Z", fill=RED, w=6),
        rect(x - 70 * s, y - 40 * s, 32 * s, 50 * s, DARK, INK, 5, 6), line(x - 20 * s, y + 10 * s, x - 10 * s, y + 60 * s, DARK, 8),
        path(f"M{x + 105 * s:.0f} {y - 60 * s:.0f} q 25 40 0 80 M{x + 130 * s:.0f} {y - 85 * s:.0f} q 40 65 0 130", color=OR, w=6)])


def barrel(x, y, s=1.0) -> str:
    """Empty barrel; (x, y) = bottom centre."""
    return "\n    ".join([
        path(f"M{x - 70 * s:.0f} {y - 200 * s:.0f} Q {x - 100 * s:.0f} {y - 100 * s:.0f} {x - 70 * s:.0f} {y:.0f} L {x + 70 * s:.0f} {y:.0f} "
             f"Q {x + 100 * s:.0f} {y - 100 * s:.0f} {x + 70 * s:.0f} {y - 200 * s:.0f} Z", fill="#c98a4a", w=6),
        f'<ellipse cx="{x:.0f}" cy="{y - 200 * s:.0f}" rx="{70 * s:.0f}" ry="{18 * s:.0f}" fill="{DARK}" stroke="{INK}" stroke-width="5"/>',
        path(f"M{x - 88 * s:.0f} {y - 60 * s:.0f} Q {x:.0f} {y - 45 * s:.0f} {x + 88 * s:.0f} {y - 60 * s:.0f} "
             f"M{x - 88 * s:.0f} {y - 140 * s:.0f} Q {x:.0f} {y - 125 * s:.0f} {x + 88 * s:.0f} {y - 140 * s:.0f}", color=DARK, w=5)])


def skewer(x, y, s=1.0) -> str:
    """Street-food skewer, (x, y) = stick bottom; leaning right."""
    return "\n    ".join([
        line(x, y, x + 60 * s, y - 260 * s, "#d9b779", 6),
        *[circle(x + (14 + 14 * k) * s, y - (60 + 60 * k) * s, 26 * s, c, INK, 4)
          for k, c in enumerate(["#c0623a", "#e8b23b", "#c0623a"])]])


def boxed(x, y, s=1.0, label="") -> str:
    """Stick figure squeezed inside a box; (x, y) = box bottom centre."""
    parts = [rect(x - 90 * s, y - 270 * s, 180 * s, 270 * s, "#f6ecd8", BROWN, 7, 6), person(x, y - 10 * s, 1.0 * s, "sad", "up")]
    if label:
        parts.append(text(x, y + 50 * s, label, int(40 * s), BROWN))
    return "\n    ".join(parts)


def shadow_person(x, y, s=1.0) -> str:
    """Dark silhouette (the Shadow); (x, y) = feet."""
    hy = y - 190 * s
    return "\n    ".join([
        circle(x, hy, 30 * s, "#4a4a55", "#4a4a55", 3),
        path(f"M{x - 40 * s:.0f} {y:.0f} L {x - 30 * s:.0f} {y - 150 * s:.0f} Q {x:.0f} {y - 165 * s:.0f} {x + 30 * s:.0f} {y - 150 * s:.0f} "
             f"L {x + 40 * s:.0f} {y:.0f} Z", fill="#4a4a55", color="#4a4a55", w=3)])


def laptop(x, y, s=1.0, screen="#dff1ff") -> str:
    """(x, y) = base front centre."""
    return "\n    ".join([
        rect(x - 130 * s, y - 210 * s, 260 * s, 170 * s, DARK, INK, 6, 12),
        rect(x - 112 * s, y - 194 * s, 224 * s, 138 * s, screen, INK, 3, 4),
        path(f"M{x - 170 * s:.0f} {y:.0f} L {x - 130 * s:.0f} {y - 40 * s:.0f} L {x + 130 * s:.0f} {y - 40 * s:.0f} L {x + 170 * s:.0f} {y:.0f} Z",
             fill="#9aa3ad", w=5)])


def number_card(x, y, n="4", s=1.0, fill="#efe3f7") -> str:
    return "\n    ".join([rect(x - 60 * s, y - 80 * s, 120 * s, 160 * s, fill, INK, 6, 14), text(x, y + 30 * s, n, int(90 * s), PURPLE)])


def cake(x, y, s=1.0) -> str:
    """Birthday cake; (x, y) = plate centre."""
    return "\n    ".join([
        line(x - 110 * s, y, x + 110 * s, y, GRAY, 6),
        rect(x - 90 * s, y - 90 * s, 180 * s, 90 * s, "#f7c6d0", INK, 6, 10),
        path(f"M{x - 90 * s:.0f} {y - 70 * s:.0f} q 22 20 45 0 q 22 20 45 0 q 22 20 45 0 q 22 20 45 0", color=WHITE, w=6),
        *[line(x + dx * s, y - 90 * s, x + dx * s, y - 140 * s, BLUE, 6) for dx in (-40, 0, 40)],
        *[path(f"M{x + dx * s:.0f} {y - 142 * s:.0f} q -8 -12 0 -24 q 8 12 0 24 Z", fill=YEL, w=3) for dx in (-40, 0, 40)]])


# ══ additions for the "Con ghét bố mẹ" video ═══════════════════
def teen(x, y, s=1.0, face="flat", arms="down", hair=INK):
    """Teenager: stick figure with a fringe and a backpack strap; (x, y) = feet."""
    hy = y - 190 * s
    return "\n    ".join([
        person(x, y, s, face, arms),
        path(f"M{x - 30 * s:.0f} {hy - 4 * s:.0f} Q {x - 20 * s:.0f} {hy - 44 * s:.0f} {x + 6 * s:.0f} {hy - 30 * s:.0f} "
             f"Q {x + 30 * s:.0f} {hy - 44 * s:.0f} {x + 30 * s:.0f} {hy - 6 * s:.0f}", color=hair, w=8),
        rect(x - 62 * s, y - 145 * s, 30 * s, 60 * s, "#f6c453", INK, 4, 8)])


def parent(x, y, s=1.0, face="flat", arms="down", mom=False):
    """Adult; mum has long hair, dad glasses."""
    if mom:
        return woman(x, y, s, face, arms)
    hy = y - 190 * s
    return "\n    ".join([person(x, y, s, face, arms),
                         circle(x - 10 * s, hy - 4 * s, 9 * s, "none", INK, 3), circle(x + 10 * s, hy - 4 * s, 9 * s, "none", INK, 3)])


def blanket_kid(x, y, s=1.0):
    """Child curled under a blanket, face lit by a phone; (x, y) = floor centre."""
    return "\n    ".join([
        path(f"M{x - 150 * s:.0f} {y:.0f} Q {x - 160 * s:.0f} {y - 150 * s:.0f} {x - 20 * s:.0f} {y - 170 * s:.0f} "
             f"Q {x + 140 * s:.0f} {y - 180 * s:.0f} {x + 150 * s:.0f} {y:.0f} Z", fill="#cfd8e3", w=6),
        path(f"M{x - 60 * s:.0f} {y - 150 * s:.0f} q 40 30 80 0 M{x - 110 * s:.0f} {y - 70 * s:.0f} q 60 25 120 0", color=GRAY, w=4),
        circle(x - 30 * s, y - 95 * s, 30 * s, SKIN, INK, 5),
        path(f"M{x - 42 * s:.0f} {y - 100 * s:.0f} l 0 3 M{x - 22 * s:.0f} {y - 100 * s:.0f} l 0 3 M{x - 40 * s:.0f} {y - 82 * s:.0f} l 18 0", w=4),
        rect(x + 20 * s, y - 120 * s, 40 * s, 66 * s, DARK, INK, 4, 8),
        path(f"M{x + 20 * s:.0f} {y - 100 * s:.0f} L {x - 10 * s:.0f} {y - 110 * s:.0f} L {x - 10 * s:.0f} {y - 75 * s:.0f} Z",
             fill="#fff4cc", color="#fff4cc", w=2)])


def door(x, y, s=1.0, locked=True):
    """Closed door; (x, y) = bottom centre."""
    parts = [rect(x - 80 * s, y - 300 * s, 160 * s, 300 * s, "#c98a4a", INK, 6, 6),
             rect(x - 60 * s, y - 280 * s, 120 * s, 110 * s, "none", BROWN, 4, 4),
             rect(x - 60 * s, y - 150 * s, 120 * s, 130 * s, "none", BROWN, 4, 4),
             circle(x + 55 * s, y - 150 * s, 9 * s, YEL, INK, 3)]
    if locked:
        parts += [path(f"M{x + 40 * s:.0f} {y - 115 * s:.0f} q 0 -28 18 -28 q 18 0 18 28", color=GRAY, w=6),
                  rect(x + 30 * s, y - 118 * s, 56 * s, 46 * s, YEL, INK, 4, 6)]
    return "\n    ".join(parts)


def ledger(x, y, w=360, h=260, left="cho", right="nợ"):
    """Account book with two columns; (x, y) = top-left."""
    parts = [rect(x, y, w, h, "#fbf3dc", INK, 6, 10), line(x + w / 2, y + 20, x + w / 2, y + h - 20, BROWN, 4),
             text(x + w / 4, y + 60, left, 44, GRN), text(x + 3 * w / 4, y + 60, right, 44, RED),
             line(x + 20, y + 80, x + w - 20, y + 80, BROWN, 4)]
    for k in range(3):
        yy = y + 120 + k * 45
        if yy < y + h - 20:
            parts += [line(x + 30, yy, x + w / 2 - 30, yy, GRAY, 4), line(x + w / 2 + 30, yy, x + w - 30, yy, GRAY, 4)]
    return "\n    ".join(parts)


def sage(x, y, s=1.0, hat=True, robe="#e8dcc4"):
    """Old philosopher with a beard (Confucius with a hat, Aristotle without); (x, y) = feet."""
    hy = y - 190 * s
    parts = [path(f"M{x - 25 * s:.0f} {y - 150 * s:.0f} Q {x - 75 * s:.0f} {y - 40 * s:.0f} {x - 60 * s:.0f} {y:.0f} L {x + 60 * s:.0f} {y:.0f} "
                  f"Q {x + 75 * s:.0f} {y - 40 * s:.0f} {x + 25 * s:.0f} {y - 150 * s:.0f} Z", fill=robe, w=5),
             circle(x, hy, 30 * s, SKIN, INK, 5),
             path(f"M{x - 24 * s:.0f} {hy + 12 * s:.0f} Q {x:.0f} {hy + 80 * s:.0f} {x + 24 * s:.0f} {hy + 12 * s:.0f} Z", fill=WHITE, w=4),
             path(f"M{x - 10 * s:.0f} {hy - 6 * s:.0f} l 0 3 M{x + 10 * s:.0f} {hy - 6 * s:.0f} l 0 3", w=4)]
    if hat:
        parts += [rect(x - 40 * s, hy - 46 * s, 80 * s, 14 * s, DARK, INK, 3, 4), rect(x - 16 * s, hy - 66 * s, 32 * s, 22 * s, DARK, INK, 3, 4)]
    else:
        parts.append(path(f"M{x - 30 * s:.0f} {hy - 10 * s:.0f} Q {x:.0f} {hy - 50 * s:.0f} {x + 30 * s:.0f} {hy - 10 * s:.0f}", color=GRAY, w=7))
    return "\n    ".join(parts)


def dog(x, y, s=1.0):
    """(x, y) = feet line centre, facing right."""
    return "\n    ".join([
        rect(x - 70 * s, y - 90 * s, 130 * s, 55 * s, "#d9b779", INK, 5, int(22 * s)),
        *[line(x + dx * s, y - 40 * s, x + dx * s, y, INK, 6) for dx in (-55, -30, 30, 50)],
        circle(x + 75 * s, y - 105 * s, 30 * s, "#d9b779", INK, 5),
        path(f"M{x + 58 * s:.0f} {y - 128 * s:.0f} q -10 25 5 35", fill="#a0764a", w=4),
        circle(x + 85 * s, y - 110 * s, 4 * s, INK, INK, 2), circle(x + 104 * s, y - 100 * s, 5 * s, INK, INK, 2),
        path(f"M{x - 70 * s:.0f} {y - 80 * s:.0f} q -30 -20 -25 -50", w=5)])


def horse(x, y, s=1.0):
    """(x, y) = feet line centre, facing right."""
    return "\n    ".join([
        rect(x - 90 * s, y - 150 * s, 170 * s, 70 * s, "#a0764a", INK, 5, int(30 * s)),
        *[line(x + dx * s, y - 85 * s, x + dx * s, y, INK, 7) for dx in (-70, -45, 45, 65)],
        path(f"M{x + 60 * s:.0f} {y - 140 * s:.0f} L {x + 100 * s:.0f} {y - 220 * s:.0f} L {x + 140 * s:.0f} {y - 195 * s:.0f} "
             f"L {x + 95 * s:.0f} {y - 125 * s:.0f} Z", fill="#a0764a", w=5),
        path(f"M{x + 92 * s:.0f} {y - 215 * s:.0f} q -25 30 -20 70", color=DARK, w=7),
        path(f"M{x - 90 * s:.0f} {y - 140 * s:.0f} q -35 20 -30 70", color=DARK, w=7),
        circle(x + 118 * s, y - 200 * s, 4 * s, INK, INK, 2)])


def house(x, y, s=1.0, fill="#fbf3dc"):
    """(x, y) = bottom centre."""
    return "\n    ".join([
        rect(x - 110 * s, y - 150 * s, 220 * s, 150 * s, fill, INK, 6, 4),
        path(f"M{x - 140 * s:.0f} {y - 145 * s:.0f} L {x:.0f} {y - 260 * s:.0f} L {x + 140 * s:.0f} {y - 145 * s:.0f} Z", fill="#e07b5f", w=6),
        rect(x - 30 * s, y - 85 * s, 60 * s, 85 * s, "#c98a4a", INK, 5, 4),
        rect(x + 45 * s, y - 120 * s, 45 * s, 40 * s, SKY, INK, 4, 4)])


def sticky(x, y, label, fill="#fff4a8", angle=0, w=230, size=38):
    """Sticky note centred on (x, y)."""
    return "\n    ".join([rect(x - w / 2, y - 70, w, 140, fill, INK, 4, 4), path(f"M{x + w / 2 - 36:.0f} {y + 70:.0f} l 36 -36", color=GRAY, w=4),
                           text(x, y + 13, label, size)])


def bridge(x1, x2, y, color=BROWN):
    mid = (x1 + x2) / 2
    parts = [path(f"M{x1:.0f} {y:.0f} Q {mid:.0f} {y - 120:.0f} {x2:.0f} {y:.0f}", color=color, w=10),
             path(f"M{x1:.0f} {y + 40:.0f} Q {mid:.0f} {y - 80:.0f} {x2:.0f} {y + 40:.0f}", color=color, w=7)]
    n = 9
    for k in range(1, n):
        t = k / n
        xx = x1 + (x2 - x1) * t
        yy = y - 120 * 2 * t * (1 - t) * 1.0
        parts.append(line(xx, yy, xx, yy + 40, color, 5))
    return "\n    ".join(parts)


def cooker(x, y, s=1.0):
    """Pressure cooker on a flame; (x, y) = burner bottom centre."""
    return "\n    ".join([
        *[path(f"M{x + dx * s:.0f} {y:.0f} q {-18 * s:.0f} {-30 * s:.0f} 0 {-60 * s:.0f} q {18 * s:.0f} {30 * s:.0f} 0 {60 * s:.0f} Z",
               fill=OR, color=RED, w=3) for dx in (-50, 0, 50)],
        rect(x - 120 * s, y - 220 * s, 240 * s, 150 * s, "#cfd8e3", INK, 6, 18),
        rect(x - 135 * s, y - 240 * s, 270 * s, 30 * s, "#9aa3ad", INK, 6, 10),
        rect(x - 15 * s, y - 275 * s, 30 * s, 36 * s, DARK, INK, 4, 4),
        path(f"M{x - 30 * s:.0f} {y - 290 * s:.0f} q -20 -30 0 -60 M{x + 30 * s:.0f} {y - 290 * s:.0f} q 20 -30 0 -60", color=GRAY, w=5)])


def gift(x, y, s=1.0, fill="#e8f4ff"):
    """Gift box; (x, y) = bottom centre."""
    return "\n    ".join([
        rect(x - 80 * s, y - 120 * s, 160 * s, 120 * s, fill, INK, 6, 6),
        rect(x - 90 * s, y - 150 * s, 180 * s, 34 * s, fill, INK, 6, 6),
        rect(x - 12 * s, y - 150 * s, 24 * s, 150 * s, RED, INK, 3, 2),
        path(f"M{x:.0f} {y - 150 * s:.0f} q -50 -50 -60 -10 q 10 20 60 10 q 50 10 60 -10 q -10 -40 -60 10", fill=RED, w=4)])


def letter(x, y, s=1.0):
    """Envelope centred on (x, y)."""
    return "\n    ".join([
        rect(x - 110 * s, y - 70 * s, 220 * s, 140 * s, WHITE, INK, 6, 8),
        path(f"M{x - 110 * s:.0f} {y - 66 * s:.0f} L {x:.0f} {y + 10 * s:.0f} L {x + 110 * s:.0f} {y - 66 * s:.0f}", w=5),
        heart(x, y + 30 * s, 0.3 * s)])


def brick_wall(x, y, w=200, h=320):
    """(x, y) = top-left."""
    parts = [rect(x, y, w, h, "#e8b49a", INK, 5, 4)]
    rows = int(h / 40)
    for r in range(1, rows):
        parts.append(line(x, y + r * 40, x + w, y + r * 40, BROWN, 3))
    for r in range(rows):
        off = 0 if r % 2 else w / 4
        for k in range(2):
            xx = x + off + k * w / 2
            if x < xx < x + w:
                parts.append(line(xx, y + r * 40, xx, y + r * 40 + 40, BROWN, 3))
    return "\n    ".join(parts)


def blind(x, y, s=1.0):
    """Blindfolded figure touching forward; (x, y) = feet."""
    hy = y - 190 * s
    return "\n    ".join([person(x, y, s, "flat", "reach"), rect(x - 30 * s, hy - 14 * s, 60 * s, 16 * s, DARK, INK, 3, 4)])


def carry(x, y, s=1.0):
    """Child carrying a parent on each shoulder (AN 2.33 image); (x, y) = feet."""
    return "\n    ".join([
        person(x, y, s, "flat", "up"),
        person(x - 70 * s, y - 210 * s, 0.55 * s, "smile"), person(x + 70 * s, y - 210 * s, 0.55 * s, "smile")])


def amygdala_brain(cx, cy, s=1.0, calm=False):
    parts = [brain(cx, cy, s), circle(cx + 20 * s, cy + 20 * s, 22 * s, GRN if calm else RED, INK, 4)]
    if not calm:
        parts.append(path(f"M{cx + 50 * s:.0f} {cy - 10 * s:.0f} l 25 -20 M{cx + 55 * s:.0f} {cy + 25 * s:.0f} l 30 0", color=RED, w=5))
    return "\n    ".join(parts)


# ══ composites used across videos ═══════════════════════════════


def chapter(n, name, y=110):
    return "\n    ".join([text(800, y - 50, f"PHẦN {n}", 40, OR), title(name, y + 20, 70)])


def tag(x, y, label, fill="#fff4cc", size=40, w=None):
    """Rounded label centred on (x, y)."""
    w = w or max(150, len(label) * size * 0.5 + 50)
    return box(x - w / 2, y - 40, w, 80, label, size, fill)


def big_number(x, y, value, label, color=RED, size=120):
    return "\n    ".join([text(x, y, value, size, color), text(x, y + 70, label, 38, GRAY)])


def army(x, y, n=4, s=0.55):
    out = []
    for k in range(n):
        px = x + k * 80 * s / 0.55
        out += [person(px, y, s, "flat", "down"), spear(px + 30 * s, y - 60 * s, px + 30 * s, y - 260 * s)]
    return "\n    ".join(out)


def atom(cx, cy, r=110):
    orbit = " ".join(f'<ellipse cx="{cx}" cy="{cy}" rx="{r}" ry="{r * 0.38:.0f}" fill="none" stroke="{BLUE}" stroke-width="5" '
                     f'transform="rotate({a} {cx} {cy})"/>' for a in (0, 60, 120))
    return "\n    ".join([orbit, circle(cx, cy, r * 0.18, RED, INK, 4)])


def baby(x, y, s=1.0):
    return "\n    ".join([path(f"M{x - 70 * s:.0f} {y:.0f} Q {x - 80 * s:.0f} {y - 60 * s:.0f} {x:.0f} {y - 60 * s:.0f} "
                                f"Q {x + 80 * s:.0f} {y - 60 * s:.0f} {x + 70 * s:.0f} {y:.0f} Z", fill="#fff4cc", w=5),
                           circle(x - 55 * s, y - 55 * s, 30 * s, SKIN, INK, 4),
                           path(f"M{x - 64 * s:.0f} {y - 58 * s:.0f} l 0 3 M{x - 46 * s:.0f} {y - 58 * s:.0f} l 0 3 "
                                f"M{x - 62 * s:.0f} {y - 44 * s:.0f} q 7 5 14 0", w=3)])


def big_person(x, y, s=1.0):
    hy = y - 190 * s
    return "\n    ".join([circle(x, hy, 30 * s, WHITE, INK, 5),
                           path(f"M{x - 10 * s:.0f} {hy - 6 * s:.0f} l 0 3 M{x + 10 * s:.0f} {hy - 6 * s:.0f} l 0 3 "
                                f"M{x - 9 * s:.0f} {hy + 12 * s:.0f} l 18 0", w=4),
                           path(f"M{x - 60 * s:.0f} {y - 60 * s:.0f} Q {x - 70 * s:.0f} {y - 160 * s:.0f} {x:.0f} {y - 160 * s:.0f} "
                                f"Q {x + 70 * s:.0f} {y - 160 * s:.0f} {x + 60 * s:.0f} {y - 60 * s:.0f} Z", fill="#f2d5b0", w=6),
                           path(f"M{x - 30 * s:.0f} {y:.0f} L {x - 25 * s:.0f} {y - 60 * s:.0f} M{x + 30 * s:.0f} {y:.0f} "
                                f"L {x + 25 * s:.0f} {y - 60 * s:.0f}", w=7)])


def bodhi(x, y, s=1.0):
    """Buddha seated under a bodhi tree."""
    return "\n    ".join([tree(x, y - 10 * s, 1.05 * s), buddha(x, y, s)])


def bucket(x, y, s=1.0):
    """Water bucket; (x, y) = bottom centre."""
    return "\n    ".join([
        path(f"M{x - 55 * s:.0f} {y - 110 * s:.0f} L {x - 42 * s:.0f} {y:.0f} L {x + 42 * s:.0f} {y:.0f} L {x + 55 * s:.0f} {y - 110 * s:.0f} Z",
             fill="#cfd8e3", w=6),
        path(f"M{x - 55 * s:.0f} {y - 110 * s:.0f} Q {x:.0f} {y - 190 * s:.0f} {x + 55 * s:.0f} {y - 110 * s:.0f}", color=GRAY, w=5),
        path(f"M{x - 45 * s:.0f} {y - 95 * s:.0f} q 22 -12 45 0 q 22 12 45 0", color=BLUE, w=5)])


def chain_links(x1, x2, y, color=GRAY):
    return "\n    ".join(f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="26" ry="15" fill="none" stroke="{color}" stroke-width="7"/>'
                           for x in range(int(x1), int(x2), 40))


def city(x, y, s=1.0, n=5):
    return "\n    ".join(rect(x + k * 80 * s, y - (120 + (k % 3) * 40) * s, 70 * s, (120 + (k % 3) * 40) * s, "#e8dcc4", INK, 5, 4)
                           for k in range(n))


def computer(x, y, label=""):
    """Monitor, (x, y) = top-left, 220x170."""
    return "\n    ".join([rect(x, y, 220, 150, DARK, INK, 6, 10), rect(x + 14, y + 14, 192, 118, "#dff1ff", INK, 3, 4),
                           line(x + 110, y + 150, x + 110, y + 190, INK, 8), line(x + 70, y + 192, x + 150, y + 192, INK, 8),
                           text(x + 110, y + 92, label, 40, BLUE) if label else ""])


def counter_phone(x, y, s, big, small=""):
    """Phone showing a member counter; (x, y) = top-left."""
    parts = [phone(x, y, s), text(x + 60 * s, y + 95 * s, big, int(34 * s), BLUE)]
    if small:
        parts.append(text(x + 60 * s, y + 130 * s, small, int(16 * s), GRAY))
    return "\n    ".join(parts)


def couple(x, y, s=0.8, kinds=("m", "w"), heart_y=None):
    """Two figures side by side with a small heart above; kinds: m = man, w = woman."""
    out = []
    for k, dx in zip(kinds, (-55, 55)):
        out.append(woman(x + dx * s, y, s) if k == "w" else person(x + dx * s, y, s))
    out.append(heart(x, heart_y if heart_y is not None else y - 260 * s, 0.45 * s / 0.8))
    return "\n    ".join(out)


def doc(x, y, w=260, h=320, head="", stamp=True):
    parts = [rect(x, y, w, h, WHITE, INK, 6, 8)]
    if head:
        parts.append(text(x + w / 2, y + 50, head, 36))
    for k in range(4):
        parts.append(line(x + 30, y + 90 + k * 40, x + w - 30 - (k % 2) * 50, y + 90 + k * 40, GRAY, 4))
    if stamp:
        parts.append(circle(x + w - 60, y + h - 60, 38, "none", RED, 6))
    return "\n    ".join(parts)


def drops(x, y, s=1.0):
    return "\n    ".join(path(f"M{x + dx * s:.0f} {y + dy * s:.0f} q -10 18 0 26 q 10 -8 0 -26 Z", fill=SKY, color=BLUE, w=3)
                         for dx, dy in ((0, 0), (-30, 40), (28, 50), (0, 90)))


def family(x, y, s=1.0):
    """Dad, mum and a teen side by side; (x, y) = feet of the middle figure."""
    return "\n    ".join([parent(x - 150 * s, y, s, "smile"), parent(x + 150 * s, y, s, "smile", mom=True), teen(x, y, 0.8 * s, "smile")])


def fish(x, y, s=1.0, fill=BLUE, face_left=True):
    k = -1 if face_left else 1
    return "\n    ".join([
        path(f"M{x - 70 * s * k:.0f} {y:.0f} Q {x:.0f} {y - 50 * s:.0f} {x + 70 * s * k:.0f} {y:.0f} "
             f"Q {x:.0f} {y + 50 * s:.0f} {x - 70 * s * k:.0f} {y:.0f} Z", fill=fill, w=5),
        path(f"M{x - 70 * s * k:.0f} {y:.0f} L {x - 110 * s * k:.0f} {y - 30 * s:.0f} L {x - 110 * s * k:.0f} {y + 30 * s:.0f} Z",
             fill=fill, w=5),
        circle(x + 40 * s * k, y - 10 * s, 6 * s, INK, INK, 2)])


def flame(x, y, s=1.0):
    return "\n    ".join([path(f"M{x:.0f} {y:.0f} Q {x - 50 * s:.0f} {y - 50 * s:.0f} {x - 5 * s:.0f} {y - 130 * s:.0f} "
                                f"Q {x + 5 * s:.0f} {y - 85 * s:.0f} {x + 25 * s:.0f} {y - 100 * s:.0f} Q {x + 50 * s:.0f} {y - 50 * s:.0f} "
                                f"{x:.0f} {y:.0f} Z", fill=OR, w=5),
                           path(f"M{x:.0f} {y - 5 * s:.0f} Q {x - 18 * s:.0f} {y - 35 * s:.0f} {x:.0f} {y - 65 * s:.0f} "
                                f"Q {x + 18 * s:.0f} {y - 35 * s:.0f} {x:.0f} {y - 5 * s:.0f} Z", fill=YEL, w=3)])


def flower(x, y, s=1.0, petal="#f7a8c4"):
    """Flower with scent waves; (x, y) = stem base."""
    return "\n    ".join([
        path(f"M{x:.0f} {y:.0f} Q {x + 10 * s:.0f} {y - 90 * s:.0f} {x:.0f} {y - 180 * s:.0f}", color=GRN, w=7),
        *[circle(x + 34 * s * math.cos(a), y - 200 * s + 34 * s * math.sin(a), 26 * s, petal, INK, 4)
          for a in [k * math.pi / 3 for k in range(6)]],
        circle(x, y - 200 * s, 20 * s, YEL, INK, 4),
        path(f"M{x - 70 * s:.0f} {y - 280 * s:.0f} q 15 -20 0 -40 q -15 -20 0 -40 M{x + 70 * s:.0f} {y - 280 * s:.0f} q 15 -20 0 -40 "
             f"q -15 -20 0 -40", color=PURPLE, w=4)])


def footsteps(x, y, n=4, dx=70, dy=-30):
    return "\n    ".join(f'<ellipse cx="{x + k * dx:.0f}" cy="{y + k * dy:.0f}" rx="12" ry="20" fill="{GRAY}" stroke="none"/>'
                           for k in range(n))


def gold_bar(x, y, s=1.0):
    return path(f"M{x - 70 * s:.0f} {y:.0f} L {x - 45 * s:.0f} {y - 40 * s:.0f} L {x + 45 * s:.0f} {y - 40 * s:.0f} L {x + 70 * s:.0f} {y:.0f} Z",
                fill=YEL, color=OR, w=5)


def guru(x, y, s=1.0):
    """Self-styled master behind a podium; (x, y) = podium bottom."""
    return "\n    ".join([person(x, y - 120 * s, s, "smile", "up"), lectern(x, y, s)])


def iceberg(x, y, s=1.0):
    """(x, y) = waterline centre."""
    return "\n    ".join([
        path(f"M{x - 300 * s:.0f} {y + 10:.0f} Q {x - 250 * s:.0f} {y + 260 * s:.0f} {x:.0f} {y + 330 * s:.0f} "
             f"Q {x + 260 * s:.0f} {y + 260 * s:.0f} {x + 320 * s:.0f} {y + 10:.0f} Z", fill="#cfe6ff", w=6),
        path(f"M{x - 110 * s:.0f} {y:.0f} L {x - 30 * s:.0f} {y - 150 * s:.0f} L {x + 20 * s:.0f} {y - 100 * s:.0f} "
             f"L {x + 60 * s:.0f} {y - 170 * s:.0f} L {x + 130 * s:.0f} {y:.0f} Z", fill=WHITE, w=6),
        water(x - 420 * s, x + 420 * s, y, BLUE)])


def lama(x, y, s=1.0):
    """Monk with a yellow pandit hat."""
    hy = y - 185 * s
    return "\n    ".join([monk(x, y, s, "#a33b2c"),
                           path(f"M{x - 40 * s:.0f} {hy - 18 * s:.0f} Q {x:.0f} {hy - 90 * s:.0f} {x + 40 * s:.0f} {hy - 18 * s:.0f} Z",
                                fill=YEL, w=4)])


def milk(x, y, s=1.0):
    """Milk carton with an expiry stamp; (x, y) = bottom centre."""
    return "\n    ".join([
        rect(x - 70 * s, y - 220 * s, 140 * s, 220 * s, WHITE, INK, 6, 6),
        path(f"M{x - 70 * s:.0f} {y - 220 * s:.0f} L {x:.0f} {y - 290 * s:.0f} L {x + 70 * s:.0f} {y - 220 * s:.0f}", fill="#dfeefe", w=6),
        text(x, y - 130 * s, "SỮA", int(46 * s), BLUE),
        rect(x - 55 * s, y - 90 * s, 110 * s, 50 * s, "#fde2df", RED, 4, 6), text(x, y - 53 * s, "HSD", int(34 * s), RED)])


def molecule(cx, cy, s=1.0):
    pts = [(cx + 50 * s * math.cos(k * math.pi / 3), cy + 50 * s * math.sin(k * math.pi / 3)) for k in range(6)]
    d = "M" + " L ".join(f"{x:.0f} {y:.0f}" for x, y in pts) + " Z"
    return "\n    ".join([path(d, fill="#f7e3f0", color=PURPLE, w=6),
                           line(pts[0][0], pts[0][1], pts[0][0] + 50 * s, pts[0][1], PURPLE, 6),
                           circle(pts[0][0] + 60 * s, pts[0][1], 10 * s, PURPLE, PURPLE, 3)])


def prince(x, y, s=1.0, face="flat", arms="down"):
    return "\n    ".join([person(x, y, s, face, arms), crown(x, y - 225 * s, 0.45 * s)])


def pyramid(x, y, w=420, h=360, labels=("tu sĩ", "vua, chiến binh", "thương nhân", "người làm thuê", "bị khinh rẻ")):
    """Caste pyramid; (x, y) = bottom-left."""
    parts = [path(f"M{x:.0f} {y:.0f} L {x + w / 2:.0f} {y - h:.0f} L {x + w:.0f} {y:.0f} Z", fill="#f4ecd8", w=6)]
    n = len(labels)
    for k, lab in enumerate(labels):
        yy = y - h + (k + 1) * h / n
        if k < n - 1:
            half = (w / 2) * (k + 1) / n
            parts.append(line(x + w / 2 - half, yy, x + w / 2 + half, yy, BROWN, 4))
        parts.append(text(x + w / 2, yy - h / n * 0.3, lab, (24, 26, 32, 32, 32)[k], RED if k == n - 1 else INK))
    return "\n    ".join(parts)


def reclining(x, y, s=1.0):
    """Buddha lying on the right side (lion posture); (x, y) = ground centre."""
    return "\n    ".join([
        rect(x - 170 * s, y - 20 * s, 340 * s, 20 * s, "#c9a77a", INK, 4, 6),
        path(f"M{x - 130 * s:.0f} {y - 20 * s:.0f} Q {x - 140 * s:.0f} {y - 85 * s:.0f} {x - 40 * s:.0f} {y - 80 * s:.0f} "
             f"L {x + 150 * s:.0f} {y - 60 * s:.0f} Q {x + 170 * s:.0f} {y - 40 * s:.0f} {x + 150 * s:.0f} {y - 20 * s:.0f} Z", fill=ROBE, w=5),
        circle(x - 150 * s, y - 70 * s, 32 * s, "#fbe3c8", INK, 5),
        circle(x - 150 * s, y - 110 * s, 9 * s, INK, INK, 3),
        path(f"M{x - 165 * s:.0f} {y - 74 * s:.0f} q 7 4 12 0 M{x - 148 * s:.0f} {y - 74 * s:.0f} q 7 4 12 0", w=3)])


def river(x1, x2, y, h=160):
    return "\n    ".join([rect(x1, y, x2 - x1, h, "#d9ecfa", BLUE, 5, 10), water(x1 + 20, x2 - 20, y + h / 3, BLUE),
                           water(x1 + 20, x2 - 20, y + 2 * h / 3, BLUE)])


def roots(x, y, s=1.0, color=BROWN):
    return path(f"M{x:.0f} {y:.0f} q {-30 * s:.0f} {50 * s:.0f} {-90 * s:.0f} {80 * s:.0f} M{x:.0f} {y:.0f} q {5 * s:.0f} {60 * s:.0f} "
                f"{-10 * s:.0f} {120 * s:.0f} M{x:.0f} {y:.0f} q {35 * s:.0f} {45 * s:.0f} {95 * s:.0f} {70 * s:.0f}", color=color, w=7)


def shaman(x, y, s=1.0):
    hy = y - 190 * s
    return "\n    ".join([
        person(x, y, s, "flat", "up"),
        path(f"M{x - 34 * s:.0f} {hy - 20 * s:.0f} L {x - 20 * s:.0f} {hy - 75 * s:.0f} L {x - 4 * s:.0f} {hy - 30 * s:.0f} "
             f"L {x + 10 * s:.0f} {hy - 85 * s:.0f} L {x + 22 * s:.0f} {hy - 30 * s:.0f} L {x + 36 * s:.0f} {hy - 70 * s:.0f} "
             f"L {x + 34 * s:.0f} {hy - 20 * s:.0f} Z", fill=OR, w=4)])


def shirt(x, y, s=1.0, fill=SKY):
    return path(f"M{x - 70 * s:.0f} {y - 100 * s:.0f} L {x - 25 * s:.0f} {y - 120 * s:.0f} Q {x:.0f} {y - 95 * s:.0f} "
                f"{x + 25 * s:.0f} {y - 120 * s:.0f} L {x + 70 * s:.0f} {y - 100 * s:.0f} L {x + 100 * s:.0f} {y - 50 * s:.0f} "
                f"L {x + 60 * s:.0f} {y - 35 * s:.0f} L {x + 55 * s:.0f} {y + 40 * s:.0f} L {x - 55 * s:.0f} {y + 40 * s:.0f} "
                f"L {x - 60 * s:.0f} {y - 35 * s:.0f} L {x - 100 * s:.0f} {y - 50 * s:.0f} Z", fill=fill, w=5)


def thinker(x, y, s=1.0, glasses=False, bald=False, hair=None):
    hy = y - 190 * s
    parts = [person(x, y, s, "flat", "point")]
    if glasses:
        parts += [circle(x - 11 * s, hy - 4 * s, 9 * s, "none", INK, 3), circle(x + 11 * s, hy - 4 * s, 9 * s, "none", INK, 3)]
    if hair:
        parts.insert(0, path(f"M{x - 34 * s:.0f} {hy + 10 * s:.0f} Q {x - 40 * s:.0f} {hy - 44 * s:.0f} {x:.0f} {hy - 40 * s:.0f} "
                             f"Q {x + 40 * s:.0f} {hy - 44 * s:.0f} {x + 34 * s:.0f} {hy + 10 * s:.0f}", color=hair, w=10))
    if bald:
        parts.append(path(f"M{x - 20 * s:.0f} {hy - 22 * s:.0f} q 6 -6 12 -2", color=WHITE, w=4))
    return "\n    ".join(parts)


def track_fork(y_main=560):
    """Main track to the right with five people, a branch going down-right with one person."""
    return "\n    ".join([rails(120, 1480, y_main),
                           path(f"M700 {y_main + 10} Q 900 {y_main + 60} 1050 {y_main + 200} L 1500 {y_main + 210}",
                                color=GRAY, w=7),
                           path(f"M700 {y_main + 30} Q 890 {y_main + 80} 1040 {y_main + 222} L 1500 {y_main + 232}",
                                color=GRAY, w=7)])


def tree_wilted(x, y, s=1.0, leaf="#b7a68a"):
    return "\n    ".join([
        path(f"M{x - 16 * s:.0f} {y:.0f} L {x - 8 * s:.0f} {y - 190 * s:.0f} L {x + 10 * s:.0f} {y - 190 * s:.0f} L {x + 18 * s:.0f} {y:.0f} Z",
             fill=BROWN, w=5),
        circle(x, y - 270 * s, 120 * s, leaf, INK, 5)])


def walking_buddha(x, y, s=1.0):
    """Standing Buddha (monk with a halo); (x, y) = feet."""
    return "\n    ".join([circle(x, y - 185 * s, 52 * s, "#fff4cc", YEL, 5), monk(x, y, s)])
