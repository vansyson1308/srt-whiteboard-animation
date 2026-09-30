#!/usr/bin/env python3
"""
Voice-sync scheduling: decide when each element is drawn from word timings.

Rules (all times are relative to the scene start):
  * an element with ``say`` (a phrase from the narration) starts drawing a
    little before that phrase is spoken - "draw it when you say it";
  * elements without ``say`` are spread over the narration between the
    anchored ones, snapping to sentence starts when possible;
  * each element draws until shortly before the next one starts, clamped to
    [minDrawMs, maxDrawMs] so the pen never crawls or rushes;
  * the scene lasts until the voice ends + a short hold;
  * ``filler`` elements (SVG ``data-filler``) are left out: the renderer draws
    them in the pauses where the hand would otherwise wait.
"""
from __future__ import annotations

import difflib
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from tts import Word, norm  # noqa: E402


@dataclass
class SyncOptions:
    lead_ms: int = 250          # start drawing this much before the phrase is spoken
    gap_ms: int = 150           # idle time between consecutive elements
    min_draw_ms: int = 900
    max_draw_ms: int = 4500
    first_start_ms: int | None = 150  # first element starts almost immediately (hook); None = follow `say`
    tail_ms: int = 700          # hold after the voice ends


def find_phrase(words: list[Word], phrase: str, from_idx: int = 0) -> int | None:
    """Index of the first word where ``phrase`` starts (exact token match, then fuzzy)."""
    target = [norm(t) for t in phrase.split() if norm(t)]
    if not target:
        return None
    toks = [norm(w.text) for w in words]
    n = len(target)
    for i in range(from_idx, len(toks) - n + 1):
        if toks[i:i + n] == target:
            return i
    best, best_i = 0.0, None
    tgt = " ".join(target)
    for i in range(from_idx, len(toks)):
        cand = " ".join(toks[i:i + n])
        r = difflib.SequenceMatcher(None, tgt, cand).ratio()
        if r > best:
            best, best_i = r, i
    return best_i if best >= 0.75 else None


def sentence_starts(words: list[Word]) -> list[int]:
    idx = [0] if words else []
    for i, w in enumerate(words[:-1]):
        if w.text[-1:] in ".!?…:;":
            idx.append(i + 1)
    return idx


def schedule(elements: list[dict], words: list[Word], speech_end_ms: int | None = None,
             opts: SyncOptions | None = None) -> int:
    """Set ``reveal.startMs`` / ``durationMs`` of every element in place.

    Elements are drawn in their list order (``sequence``).  Returns the scene
    duration in ms.
    """
    o = opts or SyncOptions()
    end_ms = speech_end_ms if speech_end_ms is not None else (words[-1].endMs if words else 0)
    # data-filler doodles follow no phrase: the renderer puts them into the pauses
    for e in elements:
        if e.get("filler"):
            rv = e.setdefault("reveal", {})
            rv.update(startMs=int(end_ms), durationMs=o.min_draw_ms)
            rv.setdefault("direction", "left_to_right")
            rv.setdefault("protectedRegions", [])
    els = sorted((e for e in elements if not e.get("filler")), key=lambda e: e.get("sequence", 0))
    n = len(els)
    if n == 0:
        return (end_ms or 0) + o.tail_ms

    # 1) anchors from `say`
    anchors: list[int | None] = [None] * n
    cursor = 0
    for i, e in enumerate(els):
        phrase = e.get("say")
        if phrase and words:
            k = find_phrase(words, phrase, cursor)
            if k is None:
                k = find_phrase(words, phrase, 0)
            if k is not None:
                anchors[i] = max(0, words[k].startMs - o.lead_ms)
                cursor = k
                if not e.get("subtitle"):
                    e["subtitle"] = _sentence_around(words, k)
    if o.first_start_ms is not None:     # hook: the board is never empty for long
        anchors[0] = min(anchors[0], o.first_start_ms) if anchors[0] is not None else o.first_start_ms
    elif anchors[0] is None:
        anchors[0] = 0

    # 2) fill the gaps between anchors
    known = [i for i, a in enumerate(anchors) if a is not None]
    sent = [words[k].startMs for k in sentence_starts(words)] if words else []
    for ki, i in enumerate(known):
        j = known[ki + 1] if ki + 1 < len(known) else n
        if j - i <= 1:
            continue
        a0 = anchors[i]
        a1 = anchors[j] if j < n else max(a0 + (j - i) * o.min_draw_ms, end_ms - o.min_draw_ms)
        for m in range(i + 1, j):
            t = a0 + (a1 - a0) * (m - i) / (j - i)
            # snap to a nearby sentence start (feels intentional)
            near = [s for s in sent if abs(s - t) < 900 and a0 < s < a1]
            anchors[m] = int(min(near, key=lambda s: abs(s - t)) - o.lead_ms if near else t)
    # keep monotonic
    for i in range(1, n):
        anchors[i] = max(anchors[i], anchors[i - 1] + o.min_draw_ms // 2)

    # 3) durations
    for i, e in enumerate(els):
        start = int(anchors[i])
        nxt = anchors[i + 1] if i + 1 < n else max(end_ms, start + o.min_draw_ms)
        dur = int(max(o.min_draw_ms, min(o.max_draw_ms, nxt - start - o.gap_ms)))
        rv = e.setdefault("reveal", {})
        rv["startMs"] = start
        rv["durationMs"] = dur
        rv.setdefault("direction", "left_to_right")
        rv.setdefault("protectedRegions", [])
    last_end = max(e["reveal"]["startMs"] + e["reveal"]["durationMs"] for e in els)
    return int(max(end_ms, last_end) + o.tail_ms)


def _sentence_around(words: list[Word], k: int) -> str:
    starts = sentence_starts(words)
    s = max([x for x in starts if x <= k], default=0)
    e = min([x for x in starts if x > k], default=len(words))
    return " ".join(w.text for w in words[s:e])


def schedule_without_voice(elements: list[dict], opts: SyncOptions | None = None) -> int:
    """Silent scenes: keep the annotation's own timing (only repair overlaps)."""
    o = opts or SyncOptions()
    els = sorted(elements, key=lambda e: e.get("sequence", 0))
    t = o.first_start_ms
    for e in els:
        rv = e.setdefault("reveal", {})
        rv["startMs"] = max(int(rv.get("startMs", t)), t)
        rv["durationMs"] = int(rv.get("durationMs", 2000))
        t = rv["startMs"] + rv["durationMs"] + o.gap_ms
    return t + o.tail_ms
