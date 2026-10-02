#!/usr/bin/env python3
"""
Voice Studio - the "voice director" ported from ttspromax (src/lib/speech/*).

Turns a narration into an ordered list of synthesis segments, each with
  display  what the viewer reads (captions / karaoke / data-say sync)
  spoken   what the voice says (pronunciation lexicon + breath commas)
  rate     Edge prosody rate (%) for this sentence (style + sentence type)
  pitch    Edge prosody pitch (Hz)
  pause    silence (ms) between the previous sentence's speech and this one

so every sentence can be synthesised on its own and stitched with exact,
style-aware pauses - the difference between a flat reading and a narrator.

Styles:  natural | news | story | podcast | ads   (see STYLE_PRESETS)
Manual pauses in the text:  [pause 1s]  [ngắt 500ms]  [nghỉ 2 giây]  <break time="800ms"/>
Moods (content-aware delivery, see MOODS): read automatically from each sentence, or set
with a tag at the start of a sentence:  [nhanh] [chậm] [cao trào] [xúc động] [hồi hộp] [vui]
[bình thường]  (English: [fast] [slow] [climax] [emotional] [suspense] [happy] [neutral]).

Pure and deterministic; no network.  ``python voice_studio.py "text" --style story``
prints the plan.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import asdict, dataclass, field

# ──────────────────────────────────────────────────────────────
# Style presets (planner.ts STYLE_PRESETS)
# ──────────────────────────────────────────────────────────────
STYLE_PRESETS: dict[str, dict] = {
    "natural": {
        "label": "Tự nhiên", "rate": 0, "pitch": 0,
        "pauses": {"clause": 180, "sentence": 400, "line": 520, "paragraph": 820,
                   "afterHeading": 700, "afterQuestion": 480},
        "heading": (-3, 2), "question": (0, 2), "exclamation": (2, 2),
        "paragraphStart": (0, 1), "paragraphEnd": (-2, 0),
    },
    "news": {
        "label": "Bản tin thời sự", "rate": 3, "pitch": -1,
        "pauses": {"clause": 150, "sentence": 340, "line": 480, "paragraph": 760,
                   "afterHeading": 900, "afterQuestion": 420},
        "heading": (-5, 3), "question": (0, 2), "exclamation": (1, 1),
        "paragraphStart": (0, 1), "paragraphEnd": (-2, 0),
    },
    "story": {
        "label": "Kể chuyện / Sách nói", "rate": -8, "pitch": 0,
        "pauses": {"clause": 240, "sentence": 600, "line": 720, "paragraph": 1150,
                   "afterHeading": 1200, "afterQuestion": 700},
        "heading": (-6, 1), "question": (-1, 3), "exclamation": (2, 3),
        "paragraphStart": (0, 1), "paragraphEnd": (-4, -1),
    },
    "podcast": {
        "label": "Podcast / Trò chuyện", "rate": 2, "pitch": 0,
        "pauses": {"clause": 150, "sentence": 320, "line": 440, "paragraph": 650,
                   "afterHeading": 650, "afterQuestion": 380},
        "heading": (-2, 2), "question": (0, 3), "exclamation": (3, 3),
        "paragraphStart": (0, 1), "paragraphEnd": (-1, 0),
    },
    "ads": {
        "label": "Quảng cáo / TVC", "rate": 9, "pitch": 2,
        "pauses": {"clause": 110, "sentence": 250, "line": 330, "paragraph": 480,
                   "afterHeading": 450, "afterQuestion": 300},
        "heading": (0, 4), "question": (2, 4), "exclamation": (4, 4),
        "paragraphStart": (0, 1), "paragraphEnd": (-1, 0),
    },
}
STYLES = list(STYLE_PRESETS)

# Natural-language directions for LLM voices (render-gemini.ts STYLE_DIRECTIONS)
STYLE_DIRECTIONS = {
    "natural": "Natural, warm, human delivery. Conversational but clear, with natural breathing pauses "
               "at punctuation.",
    "news": "Professional television news anchor. Clear, confident and credible; measured broadcast pace; "
            "precise phrasing with crisp pauses at commas and full stops; subtle emphasis on key figures, "
            "names and places; no exaggerated emotion.",
    "story": "Audiobook narrator. Warm, expressive and immersive; unhurried pace; deeper pauses between "
             "sentences; let emotion follow the story.",
    "podcast": "Friendly podcast host talking to one listener. Relaxed, engaging, smiling voice; lively rhythm.",
    "ads": "Energetic commercial voice-over. Upbeat, persuasive, punchy rhythm; highlight the key offer.",
}


def direction(style: str, lang: str = "vi", extra: str | None = None) -> str:
    hint = (" Speak Vietnamese with native, standard pronunciation and correct tones." if lang == "vi"
            else " Speak English with a natural, neutral accent.")
    return STYLE_DIRECTIONS.get(style, STYLE_DIRECTIONS["natural"]) + hint + (f" {extra}" if extra else "")


# ──────────────────────────────────────────────────────────────
# Moods: content-aware delivery per sentence
# ──────────────────────────────────────────────────────────────
# rate %, pitch in semitones, gain dB, extra pause before/after (ms), multiplier on the
# automatic pause before the sentence, and a dB ramp across the sentence (crescendo > 0)
MOODS: dict[str, dict] = {
    "neutral":   {"label": "Bình thường", "rate": 0, "st": 0.0, "gain": 0.0, "before": 0, "after": 0,
                  "pace": 1.0, "ramp": 0.0, "direction": ""},
    "fast":      {"label": "Nhanh, lướt", "rate": 11, "st": 0.3, "gain": 0.0, "before": 0, "after": 0,
                  "pace": 0.7, "ramp": 0.0,
                  "direction": "Read this part briskly, with light forward momentum."},
    "slow":      {"label": "Chậm, nhấn mạnh", "rate": -10, "st": -0.4, "gain": 1.0, "before": 180, "after": 420,
                  "pace": 1.15, "ramp": 0.0,
                  "direction": "Slow down and stress the key idea: deliberate, weighty, every word clear."},
    "climax":    {"label": "Cao trào", "rate": 6, "st": 1.8, "gain": 3.0, "before": 320, "after": 520,
                  "pace": 1.0, "ramp": 2.0,
                  "direction": "This is the climax: build intensity, raise the energy and pitch, land it hard."},
    "emotional": {"label": "Xúc động, trầm lắng", "rate": -14, "st": -1.3, "gain": -2.5, "before": 280,
                  "after": 480, "pace": 1.25, "ramp": -1.5,
                  "direction": "Emotional and tender: slower, softer and lower, with feeling in the voice."},
    "suspense":  {"label": "Hồi hộp", "rate": -8, "st": -0.8, "gain": -1.5, "before": 200, "after": 650,
                  "pace": 1.15, "ramp": 0.0,
                  "direction": "Suspenseful: hushed and restrained, holding the listener before the reveal."},
    "happy":     {"label": "Vui, hào hứng", "rate": 7, "st": 1.1, "gain": 1.2, "before": 0, "after": 0,
                  "pace": 0.9, "ramp": 0.0,
                  "direction": "Bright and upbeat, smiling voice."},
}
MOOD_ALIASES = {
    "nhanh": "fast", "lướt": "fast", "fast": "fast",
    "chậm": "slow", "nhấn": "slow", "nhấn mạnh": "slow", "slow": "slow", "emphasis": "slow",
    "cao trào": "climax", "kịch tính": "climax", "mạnh": "climax", "climax": "climax", "dramatic": "climax",
    "xúc động": "emotional", "trầm": "emotional", "buồn": "emotional", "trầm lắng": "emotional",
    "emotional": "emotional", "sad": "emotional",
    "hồi hộp": "suspense", "bí ẩn": "suspense", "suspense": "suspense",
    "vui": "happy", "hào hứng": "happy", "happy": "happy", "excited": "happy",
    "bình thường": "neutral", "thường": "neutral", "neutral": "neutral", "normal": "neutral",
}
MOOD_TAG = re.compile(r"\[\s*(" + "|".join(sorted((re.escape(k) for k in MOOD_ALIASES), key=len, reverse=True))
                      + r")\s*\]", re.IGNORECASE)


def mood_name(value: str | None) -> str | None:
    """'cao trào' / 'Climax' / 'climax' -> 'climax'; None or unknown -> None."""
    if not value:
        return None
    v = unicodedata.normalize("NFC", str(value)).strip().lower()
    return v if v in MOODS else MOOD_ALIASES.get(v)


def _cues(words: str) -> re.Pattern:
    return re.compile(r"(?<!\w)(?:" + words + r")(?!\w)", re.IGNORECASE)


# Cue words for the automatic mood reading (Vietnamese first; a few English ones).
MOOD_CUES: dict[str, list[tuple[re.Pattern, float]]] = {
    "emotional": [
        (_cues("đau khổ|khổ đau|nỗi khổ|khổ sở|đau đớn|nỗi đau|đau lòng|xót xa|day dứt|tuyệt vọng|nước mắt|"
               "khóc|cô đơn|bi kịch|thương tâm|mất mát|chia ly|chia lìa|qua đời|cái chết|chết chóc|ra đi mãi mãi|"
               "hy sinh|bệnh tật|già yếu|sinh lão bệnh tử|tang thương|nghèo khổ|khốn khổ|bất hạnh|đáng thương|"
               "thương xót|yêu thương|mẹ già|người thân|lìa đời|vô thường|trống rỗng|khắc khoải|nghẹn ngào|"
               "grief|tears|lonely|died|death|suffering|heartbroken"), 1.0),
        (_cues("buồn|khổ|đau|mất|thương|chết|nỗi"), 0.35),
    ],
    "climax": [
        (_cues("bùng nổ|đỉnh điểm|sụp đổ|kinh hoàng|khủng khiếp|chấn động|choáng váng|khổng lồ|hàng nghìn tỷ|"
               "hàng tỷ|hàng triệu|nghìn tỷ|siêu lạm phát|phá sản|tan hoang|không thể tin|không tưởng|"
               "vĩ đại nhất|lớn nhất|cao nhất|mạnh nhất|kỷ lục|mất kiểm soát|chưa từng có|thay đổi mãi mãi|"
               "cuối cùng thì|bước ngoặt|explode|collapse|record|incredible"), 1.0),
        (_cues("nhất|tăng vọt|lao dốc|vỡ òa|mãnh liệt|gấp đôi|gấp ba|gấp mười|gấp \d+"), 0.45),
    ],
    "suspense": [
        (_cues("nhưng rồi|thế nhưng|bỗng nhiên|bỗng|đột nhiên|bất ngờ|bí ẩn|bí mật|chuyện gì|điều gì|"
               "liệu có|liệu rằng|không ai ngờ|không ai biết|lặng lẽ|âm thầm|ngay lúc đó|suddenly|mystery|"
               "secret|what happened"), 0.9),
        (_cues("nhưng|liệu"), 0.3),
    ],
    "slow": [
        (_cues("quan trọng nhất|quan trọng|cốt lõi|bản chất|chìa khóa|chìa khoá|mấu chốt|tóm lại|nói cách khác|"
               "nghĩa là|hãy nhớ|điều cần nhớ|bài học|chân lý|thực chất|chính là|nguyên nhân sâu xa|"
               "the key|in short|remember|the point is"), 0.9),
    ],
    "happy": [
        (_cues("tuyệt vời|hạnh phúc|niềm vui|vui mừng|hân hoan|thú vị|may mắn|thành công|chiến thắng|"
               "rạng rỡ|tươi sáng|wonderful|happy|joy|amazing"), 0.8),
    ],
    "fast": [
        (_cues("ví dụ như|chẳng hạn|nào là|rồi thì|vân vân|v\.v\.|for example|such as"), 0.7),
    ],
}


def detect_mood(sentence: str) -> tuple[str, float]:
    """Best guess of how a sentence should be read, from its words and punctuation.
    Returns (mood, strength 0..1); ("neutral", 0) when nothing stands out."""
    s = unicodedata.normalize("NFC", sentence)
    score = {m: sum(w * len(rx.findall(s)) for rx, w in cues) for m, cues in MOOD_CUES.items()}
    core = re.sub(r"[\"'”’)\]»\s]+$", "", s)
    if core.endswith(("!", "！")):
        score["climax"] += 0.6
    if core.endswith(("…", "...")):
        score["suspense"] += 0.6
    if core.endswith(("?", "？")):
        score["suspense"] += 0.15
    if s.count(",") >= 3 and len(s.split()) / (s.count(",") + 1) <= 5:     # a quick list of short items
        score["fast"] += 0.8
    mood = max(score, key=lambda m: score[m])
    val = score[mood]
    if val < 0.6:
        return "neutral", 0.0
    return mood, float(min(1.0, 0.55 + 0.25 * val))


# ──────────────────────────────────────────────────────────────
# Voice catalogue (what an agent can pick from)
# ──────────────────────────────────────────────────────────────
CATALOGUE: dict[str, list[dict]] = {
    "edge": [
        {"id": "vi-VN-HoaiMyNeural", "gender": "female", "note": "Tiếng Việt chuẩn, rõ"},
        {"id": "vi-VN-NamMinhNeural", "gender": "male", "note": "Tiếng Việt chuẩn, trầm"},
        # Multilingual voices speak Vietnamese with a livelier (slightly foreign) delivery
        {"id": "en-US-AndrewMultilingualNeural", "gender": "male", "note": "đa ngôn ngữ, ấm, tự nhiên"},
        {"id": "en-US-BrianMultilingualNeural", "gender": "male", "note": "đa ngôn ngữ, trẻ trung"},
        {"id": "en-US-AvaMultilingualNeural", "gender": "female", "note": "đa ngôn ngữ, biểu cảm"},
        {"id": "en-US-EmmaMultilingualNeural", "gender": "female", "note": "đa ngôn ngữ, vui tươi"},
        {"id": "fr-FR-VivienneMultilingualNeural", "gender": "female", "note": "đa ngôn ngữ"},
        {"id": "de-DE-FlorianMultilingualNeural", "gender": "male", "note": "đa ngôn ngữ"},
    ],
    "gemini": [
        {"id": n, "gender": g, "note": t} for n, g, t in [
            ("Kore", "female", "Firm"), ("Aoede", "female", "Breezy"), ("Leda", "female", "Youthful"),
            ("Despina", "female", "Smooth"), ("Erinome", "female", "Clear"), ("Sulafat", "female", "Warm"),
            ("Vindemiatrix", "female", "Gentle"), ("Charon", "male", "Informative"), ("Orus", "male", "Firm"),
            ("Iapetus", "male", "Clear"), ("Rasalgethi", "male", "Informative"),
            ("Sadaltager", "male", "Knowledgeable"), ("Algieba", "male", "Smooth"), ("Gacrux", "male", "Mature"),
        ]
    ],
    "vieneu": [   # VieNeu-TTS v3 Turbo presets (offline, Apache-2.0); region · style
        {"id": v, "gender": g, "note": n} for v, g, n in [
            ("Hải Đăng", "male", "Bắc · tự nhiên"), ("Thiện Minh", "male", "Bắc · kể chuyện"),
            ("Minh Đức", "male", "Bắc · tin tức"), ("Thanh Bình", "male", "Bắc · kể chuyện"),
            ("Quốc Tuấn", "male", "Bắc · tự nhiên"), ("Minh Triết", "male", "Nam · tin tức"),
            ("Thái Sơn", "male", "Nam · kể chuyện"), ("Quang Sơn", "male", "Trung · tự nhiên"),
            ("Mai Anh", "female", "Bắc · tin tức"), ("Trúc Ly", "female", "Bắc · tự nhiên"),
            ("Ngọc Linh", "female", "Bắc · kể chuyện"), ("Đoan Trang", "female", "Bắc · tự nhiên"),
            ("Thùy Dung", "female", "Nam · tin tức"), ("Thục Đoan", "female", "Nam · kể chuyện"),
            ("Ngọc Trân", "female", "Trung · tự nhiên"),
        ]
    ],
    "tiktok": [
        {"id": "BV074_streaming", "gender": "female", "note": "Chị Vi - giọng TikTok quen thuộc"},
        {"id": "BV075_streaming", "gender": "male", "note": "Anh Vi - giọng TikTok quen thuộc"},
    ],
    "makevoice": [
        {"id": "pNInz6obpgDQGcFmaJgB", "gender": "male", "note": "Adam (ElevenLabs) - dứt khoát"},
        {"id": "21m00Tcm4TlvDq8ikWAM", "gender": "female", "note": "Rachel (ElevenLabs) - điềm tĩnh"},
    ],
    "elevenlabs": [
        {"id": "FTYCiQT21H9XQvhRu0ch", "gender": "male", "note": "MinhTrung - giọng Việt (mặc định)"},
        {"id": "<voice_id>", "gender": "", "note": "giọng Việt khác trong Voice Library (Gentle Linh, "
                                                  "Soft Spoken Huong, Tram...) hoặc giọng bạn tự clone"},
    ],
    "openai": [{"id": v, "gender": "", "note": ""} for v in
               ("alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer")],
    "fish": [{"id": "<reference_id>", "gender": "", "note": "model ID từ fish.audio, hoặc clone từ "
                                                          "voice.reference (cần sự đồng ý của người nói)"}],
}

# ──────────────────────────────────────────────────────────────
# Segmenter (segmenter.ts)
# ──────────────────────────────────────────────────────────────
MAX_MANUAL_PAUSE_MS = 10_000
DEFAULT_MANUAL_PAUSE_MS = 700
MAX_UNIT_CHARS = 450

PAUSE_TAG = re.compile(
    r"\[\s*(?:pause|break|ngắt|ngat|nghỉ|nghi|dừng|dung)\s*:?\s*(?:(\d+(?:[.,]\d+)?)\s*(ms|s|giây|giay|sec)?)?\s*\]"
    r"|<break\s+time\s*=\s*[\"']?(\d+(?:\.\d+)?)\s*(ms|s)?[\"']?\s*/?>",
    re.IGNORECASE,
)


def _pause_ms(num: str | None, unit: str | None) -> int:
    if not num:
        return DEFAULT_MANUAL_PAUSE_MS
    try:
        n = float(num.replace(",", "."))
    except ValueError:
        return DEFAULT_MANUAL_PAUSE_MS
    u = (unit or "").lower()
    ms = n if u == "ms" else n * 1000 if u else (n * 1000 if n <= 10 else n)
    return max(0, min(MAX_MANUAL_PAUSE_MS, round(ms)))


def _tag_ms(m: re.Match) -> int:
    return _pause_ms(m.group(1) or m.group(3), m.group(2) or m.group(4))


def strip_pause_tags(text: str) -> str:
    """The text a viewer should see: pause / mood tags and delivery marks removed."""
    return markup(re.sub(r"\s+", " ", MOOD_TAG.sub(" ", PAUSE_TAG.sub(" ", text))).strip())[0]


def _take_moods(text: str) -> tuple[str, list[tuple[int, str]]]:
    """Remove mood tags; return the clean text and (position in it, mood) marks."""
    out, marks, last = "", [], 0
    for m in MOOD_TAG.finditer(text):
        out += text[last:m.start()]
        marks.append((len(out), mood_name(m.group(1))))
        last = m.end()
        if (not out or out[-1].isspace()) and text[last:last + 1].isspace():
            last += 1                                        # "a [tag] b" -> "a b"
    return out + text[last:], marks


ABBREVIATIONS = {
    "tp", "gs", "pgs", "ts", "ths", "bs", "ks", "nxb", "tx", "gs.ts", "pgs.ts", "cty", "tnhh", "sđt",
    "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "vs", "e.g", "i.e", "vol", "fig", "jan", "feb", "mar", "apr",
    "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "u.s", "u.k", "approx", "dept", "gen", "gov",
    "sen", "rep",
}
CAPITALIZED_ONLY = {"gen", "sen", "rep", "gov", "mar", "dec"}
TERMINATORS = set(".!?…。！？")
CLOSERS = set("\"'”’)]»")


def _is_abbrev_before(text: str, dot: int) -> bool:
    i = dot - 1
    while i >= 0 and (text[i].isalpha() or text[i] == "."):
        i -= 1
    raw = text[i + 1:dot]
    token = raw.lower()
    if not token:
        return False
    if token in ABBREVIATIONS:
        return token not in CAPITALIZED_ONLY or raw[:1].isupper()
    if len(raw) == 1 and raw.isupper():          # initials: "J. Smith", but not "vitamin C."
        prev = (text[:i + 1].rstrip().split() or [""])[-1]
        return prev == "" or prev[:1].isupper()
    return False


def split_sentences(line: str) -> list[str]:
    out, start, i, n = [], 0, 0, len(line)
    while i < n:
        ch = line[i]
        if ch in TERMINATORS:
            j = i + 1
            while j < n and (line[j] in TERMINATORS or line[j] in CLOSERS):
                j += 1
            nxt = line[j:]
            if not nxt.strip():
                break
            if nxt[:1].isspace():
                c = nxt.lstrip()[:1]
                ellipsis = ch == "…" or line[i:i + 3] == "..."
                starts = bool(c) and (c.isupper() or c.isdigit() or c in "\"“'‘([«-")
                abbrev = ch == "." and not ellipsis and _is_abbrev_before(line, i)
                if starts and not abbrev:
                    out.append(line[start:j].strip())
                    start = j
            i = j
            continue
        i += 1
    rest = line[start:].strip()
    if rest:
        out.append(rest)
    return [s for s in out if s]


def split_long_sentence(sentence: str, max_chars: int = MAX_UNIT_CHARS) -> list[str]:
    if len(sentence) <= max_chars:
        return [sentence]
    mid = len(sentence) / 2
    best, best_score = -1, float("inf")
    for m in re.finditer(r"[;:,]\s", sentence):
        pos = m.start() + 1
        score = abs(pos - mid) * (1 if m.group()[0] == "," else 0.6)
        if score < best_score:
            best, best_score = pos, score
    if best <= 0:
        left = sentence.rfind(" ", 0, int(mid))
        best = left if left > 0 else int(mid)
    a, b = sentence[:best].strip(), sentence[best:].strip()
    return split_long_sentence(a, max_chars) + split_long_sentence(b, max_chars)


def _classify(sentence: str) -> str:
    s = re.sub(r"[\"'”’)\]»\s]+$", "", sentence)
    if s.endswith(("?", "？")):
        return "question"
    if s.endswith(("!", "！")):
        return "exclamation"
    return "statement"


def _is_all_caps(line: str) -> bool:
    letters = [c for c in line if c.isalpha()]
    if len(letters) < 6:
        return False
    upper = sum(1 for c in letters if c.isupper())
    return upper / len(letters) > 0.85 and bool(re.search(r"\s", line.strip()))


def _looks_like_heading(line: str, is_last: bool) -> bool:
    t = line.strip()
    if _is_all_caps(t):
        return True
    if is_last or len(t) > 110 or re.search(r"[.!?…:;,][\"'”’)\]»]?$", t):
        return False
    return 2 <= len(t.split()) <= 18


@dataclass
class Unit:
    kind: str                      # "speech" | "pause"
    text: str = ""
    type: str = "statement"        # statement | question | exclamation | heading
    boundary: str = "start"        # start | clause | sentence | line | paragraph
    paragraph: int = 0
    first: bool = False
    last: bool = False
    ms: int = 0
    mood: str | None = None        # from a [mood] tag in the script


def segment_script(text: str) -> list[Unit]:
    """Parse a script into one speech unit per sentence (+ explicit pause units)."""
    units: list[Unit] = []
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    lines = text.split("\n")
    non_empty = [i for i, l in enumerate(lines) if PAUSE_TAG.sub("", l).strip()]
    last_line = non_empty[-1] if non_empty else -1
    paragraph, pending, blank = -1, "start", True
    for li, raw in enumerate(lines):
        if not raw.strip():
            blank = True
            continue
        if not PAUSE_TAG.sub("", raw).strip():        # a line of pause tags only
            units += [Unit("pause", ms=_tag_ms(m)) for m in PAUSE_TAG.finditer(raw)]
            continue
        new_par = blank or paragraph < 0
        if new_par:
            paragraph += 1
        if units:
            pending = "paragraph" if new_par else "line"
        blank = False
        pieces: list[tuple[str, object]] = []
        last = 0
        for m in PAUSE_TAG.finditer(raw):
            pieces += [("text", raw[last:m.start()]), ("pause", _tag_ms(m))]
            last = m.end()
        pieces.append(("text", raw[last:]))
        line_text = PAUSE_TAG.sub(" ", raw).strip()
        heading = _looks_like_heading(line_text, li == last_line) and len(split_sentences(line_text)) == 1
        line_units: list[Unit] = []
        for kind, val in pieces:
            if kind == "pause":
                units.append(Unit("pause", ms=int(val)))  # type: ignore[arg-type]
                continue
            chunk, marks = _take_moods(str(val))
            lead = len(chunk) - len(chunk.lstrip())
            chunk = chunk.strip()
            marks = [(max(0, pos - lead), m) for pos, m in marks]
            if not chunk:
                continue
            cursor = 0
            for si, sentence in enumerate(split_sentences(chunk)):
                prev = cursor
                a = chunk.find(sentence, cursor)
                cursor = (cursor if a < 0 else a) + len(sentence)
                # a tag belongs to the sentence it opens or sits in
                tagged = [m for pos, m in marks if prev <= pos < cursor]
                parts = split_long_sentence(sentence)
                for pi, part in enumerate(parts):
                    u = Unit("speech", part,
                             "heading" if heading else _classify(sentence if pi == len(parts) - 1 else part),
                             "clause" if pi > 0 else ("sentence" if si > 0 or line_units else pending),
                             paragraph, mood=tagged[-1] if tagged else None)
                    if not units or (all(x.kind == "pause" for x in units) and u.boundary != "clause"):
                        u.boundary = "start"
                    units.append(u)
                    line_units.append(u)
    speech = [u for u in units if u.kind == "speech"]
    for i, u in enumerate(speech):
        u.first = i == 0 or speech[i - 1].paragraph != u.paragraph
        u.last = i == len(speech) - 1 or speech[i + 1].paragraph != u.paragraph
    return units


# ──────────────────────────────────────────────────────────────
# Breath commas (phrasing.ts)
# ──────────────────────────────────────────────────────────────
VI_CONNECTIVES = [
    "tuy nhiên", "trong khi đó", "trong khi", "thế nhưng", "nhưng", "song song với", "bởi vì", "vì vậy",
    "vì thế", "do đó", "do vậy", "cho nên", "mặc dù", "dù vậy", "đồng thời", "ngoài ra", "bên cạnh đó",
    "theo đó", "qua đó", "từ đó", "nhằm", "trong đó", "cũng như", "kể cả", "tức là", "nghĩa là",
    "khiến cho", "dẫn đến", "sau khi", "trước khi", "để từ đó",
]
EN_CONNECTIVES = ["however", "but", "although", "though", "whereas", "because", "therefore", "meanwhile",
                  "while", "which means", "so that", "even though", "unless"]
MIN_LEFT_WORDS, MIN_RIGHT_WORDS = 9, 4
_PHRASE_RE: dict[str, re.Pattern] = {}


def _phrase_re(lang: str) -> re.Pattern:
    if lang not in _PHRASE_RE:
        cs = sorted(VI_CONNECTIVES if lang == "vi" else EN_CONNECTIVES, key=len, reverse=True)
        alt = "|".join(re.escape(c).replace(r"\ ", r"\s+") for c in cs)
        _PHRASE_RE[lang] = re.compile(rf"(?<=\w)\s+({alt})(?!\w)", re.IGNORECASE)
    return _PHRASE_RE[lang]


def insert_phrase_breaks(sentence: str, lang: str = "vi") -> str:
    """Add a breath comma before connectives in long, comma-less clauses."""
    def since_break(before: str) -> int:
        k = max(before.rfind(c) for c in ",;:(-–")
        return len(before[k + 1:].split())

    def until_break(after: str) -> int:
        m = re.search(r"[,;:.!?]", after)
        return len((after if m is None else after[:m.start()]).split())

    out, last = "", 0
    for m in _phrase_re(lang).finditer(sentence):
        before = out + sentence[last:m.start()]
        after = sentence[m.end():]
        if since_break(before) >= MIN_LEFT_WORDS and until_break(after) + len(m.group(1).split()) >= MIN_RIGHT_WORDS:
            out = before + "," + m.group(0)
        else:
            out = before + m.group(0)
        last = m.end()
    return out + sentence[last:]


# ──────────────────────────────────────────────────────────────
# Delivery: where a presenter takes a beat
# ──────────────────────────────────────────────────────────────
# Punctuation says where a sentence may break; a presenter also decides where it *should*:
# a beat before the word that is being revealed ("Tên nhóm chỉ có bốn chữ: | con ghét bố
# mẹ"), a breath between two mirrored halves so the contrast is heard ("Người lớn đọc...
# | Người trẻ đọc..."), points of an argument laid out one by one ("Thứ nhất: ..."), items
# of a list read deliberately, the short line that closes a thought given room.  These are
# read from the structure of the text (``discourse_breaks`` / ``lead_pause_ms``) and can be
# written into the script by its author:
#   |        a beat (~320 ms)            ||       a long beat (~600 ms)
#   *words*  stressed: spoken a little slower; a beat before it only after a word that
#            announces it ("... là *X*", "... rằng *X*") - elsewhere a stop would split the
#            phrase ("nhốt trong | một nhà giam") and sound like the reader stumbled
# Both are removed from captions.  Break lengths are base values, scaled like every pause.
BEAT_MS = {"|": 320, "||": 600}
REVEAL_MS = 420            # colon or lead-in before a short phrase that lands as the point
HEAD_COLON_MS = 380        # "Thứ nhất:", "Kết quả:" - a short head announcing what follows
LIST_INTRO_MS = 450        # "...ba cái bẫy:", "...như sau:" - the listener braces for a list
LIST_COMMA_MS = 240        # between short items of a list
CONTRAST_MS = 280          # ", còn ...", ", nhưng ...", ", mà là ..."
CONTRAST_NO_COMMA_MS = 220
PARALLEL_MS = 220          # extra rest before the mirrored second half of a parallel pair
PARALLEL_INNER_MS = 260    # the same, inside one sentence ("..., điều thứ hai ...")
ORDINAL_MS = 250           # extra rest before "Thứ hai: ...", "Dấu hiệu thứ ba: ..."
CONTRAST_OPEN_MS = 150     # extra rest before a sentence opening with "Còn", "Nhưng" ...
PUNCHLINE_MS = 150         # extra rest before a short line closing a long one
MAX_LEAD_MS = 350
EMPH_RATE = -7             # stressed words are spoken this much slower (%)

_NUM_WORDS = {"một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín", "mười", "mấy", "vài", "nhiều"}
_REVEAL_LEADS = [("chỉ", "có"), ("tên", "là"), ("gọi", "là"), ("gọi", "đó", "là"), ("chính", "là"),
                 ("câu", "trả", "lời", "là"), ("đáp", "án", "là"), ("đó", "là"), ("ấy", "là"), ("chỉ", "là")]
# "nghĩa là", "tức là" gloss a word - the gloss flows on, it is not a reveal.  After a
# negation ("không chỉ là", "không phải là") the phrase is not the point either.
_NEGATIONS = {"không", "chẳng", "chả", "chưa"}
# words after which a stressed phrase may be set apart by a beat: they announce it
_STRESS_LEADS = {"là", "rằng"}
_CONTRAST_NEXT = {"còn", "nhưng", "mà", "chứ", "song", "ngược", "trái", "thế"}
_CONTRAST_OPENERS = {"còn", "nhưng", "ngược", "song", "tuy", "thế"}
_LIST_INTRO_TAIL = [("như", "sau"), ("sau", "đây"), ("gồm",), ("bao", "gồm")]
_ORDINAL = re.compile(r"^(thứ (nhất|hai|ba|tư|năm|sáu|bảy)|(một|hai|ba|bốn|năm) là|điều thứ|dấu hiệu thứ|bẫy thứ"
                      r"|bước (một|hai|ba|bốn|năm|đầu|cuối)|đầu tiên|cuối cùng|trước hết|sau cùng)\b")
_BREAK_PUNCT = ",;:.!?…—–"


def _word(tok: str) -> str:
    return unicodedata.normalize("NFC", tok).lower().strip("\"'“”‘’()[]«»*").rstrip(_BREAK_PUNCT + "\"'”’)")


def _punct(tok: str) -> str:
    c = tok.rstrip("\"'”’)]»")[-1:]
    return c if c in _BREAK_PUNCT else ""


def markup(text: str) -> tuple[str, dict[int, int], list[tuple[int, int]]]:
    """Read the author's delivery marks: ``|`` / ``||`` beats and ``*stressed words*``.
    Returns the clean text, ``{token index: beat ms}`` (a beat *after* that token) and the
    stressed token spans ``(first, last)``."""
    t = re.sub(r"\s*(\|\|?)\s*", r" \1 ", text)
    out: list[str] = []
    breaks: dict[int, int] = {}
    emph: list[tuple[int, int]] = []
    open_at = None
    for tok in t.split():
        if tok in BEAT_MS:
            if out:
                breaks[len(out) - 1] = max(breaks.get(len(out) - 1, 0), BEAT_MS[tok])
            continue
        if tok.startswith("*") and len(tok) > 1:
            open_at = len(out)
            tok = tok[1:]
            # a stressed phrase is set apart - unless the voice has just paused (a comma one or
            # two words back): two stops in a row sound like stumbling, not emphasis
            near = any(_punct(out[k]) for k in range(max(0, open_at - 2), open_at))
            if open_at and (open_at - 1) not in breaks and not near and _word(out[-1]) in _STRESS_LEADS:
                breaks[open_at - 1] = BEAT_MS["|"]
        close = tok.rstrip("\"'”’)]».,;:!?…").endswith("*")
        if close:
            i = tok.rfind("*")
            tok = tok[:i] + tok[i + 1:]
        if tok:
            out.append(tok)
        if close and open_at is not None and out:
            emph.append((open_at, len(out) - 1))
            open_at = None
    return " ".join(out), breaks, emph


def discourse_breaks(toks: list[str]) -> tuple[dict[int, int], list[tuple[int, int]]]:
    """Beats a presenter takes inside one sentence, read from its structure.

    Returns ``{token index: ms}`` (rest after that token) and stressed spans."""
    n = len(toks)
    w = [_word(t) for t in toks]
    p = [_punct(t) for t in toks]
    breaks: dict[int, int] = {}
    emph: list[tuple[int, int]] = []
    if n < 3:
        return breaks, emph

    def clean_run(a: int, b: int) -> bool:          # no inner break punctuation in toks[a:b]
        return all(not p[k] for k in range(a, b))

    # colons: a head ("Thứ nhất:"), a list intro ("ba cái bẫy:"), or the lead-in to a short point
    for i in range(n - 1):
        if p[i] != ":":
            continue
        rest = n - 1 - i
        head = i + 1 - max((k + 1 for k in range(i) if p[k]), default=0)
        listy = "," in p[i + 1:]                     # what follows is itself a list
        intro = any(tuple(w[i - len(t) + 1:i + 1]) == t for t in _LIST_INTRO_TAIL) or \
            (listy and any(x in _NUM_WORDS or x.isdigit() for x in w[max(0, i - 3):i + 1]))
        if intro and rest >= 3:
            breaks[i] = LIST_INTRO_MS
        elif rest <= 7 and clean_run(i + 1, n - 1):
            breaks[i] = REVEAL_MS
            if rest <= 5:
                emph.append((i + 1, n - 1))
        elif head <= 4:
            breaks[i] = HEAD_COLON_MS
    # lead-ins without a colon: "chỉ có bốn chữ | con ghét bố mẹ", "đó là | ..."
    for lead in _REVEAL_LEADS:
        L = len(lead)
        for j in range(n - L):
            if tuple(w[j:j + L]) != lead or not clean_run(j, j + L) or (j and w[j - 1] in _NEGATIONS):
                continue
            if any(p[x] for x in range(max(0, j - 2), j)):   # the voice has just paused: no second stop
                continue
            k = j + L - 1
            if lead == ("chỉ", "có"):                    # "chỉ có [số] chữ/từ/câu/điều ..."
                m = k + 1
                if m < n and (w[m] in _NUM_WORDS or w[m].isdigit()):
                    m += 1
                if m >= n or w[m] not in ("chữ", "từ", "câu", "điều", "cách", "việc") or not clean_run(k, m):
                    continue
                k = m
            rest = n - 1 - k
            if 1 <= rest <= 6 and clean_run(k, n - 1) and k not in breaks and k + 1 < n:
                breaks[k] = REVEAL_MS - 40
                if rest <= 5:
                    emph.append((k + 1, n - 1))
    # contrast: ", còn ...", ", nhưng ...", "không phải A mà là B"
    for i in range(n - 1):
        if p[i] == "," and w[i + 1] in _CONTRAST_NEXT:
            breaks[i] = max(breaks.get(i, 0), CONTRAST_MS)
        elif not p[i] and i >= 3 and (w[i + 1:i + 3] == ["mà", "là"] or w[i + 1:i + 3] == ["chứ", "không"]):
            breaks[i] = max(breaks.get(i, 0), CONTRAST_NO_COMMA_MS)
    # mirrored clauses inside one sentence: "điều thứ nhất là học, điều thứ hai là hành"
    starts = [0] + [k + 1 for k in range(n - 1) if p[k]]
    for a, b in zip(starts, starts[1:]):
        if b + 1 < n and w[a:a + 2] == w[b:b + 2] and b - a >= 3:
            breaks[b - 1] = max(breaks.get(b - 1, 0), PARALLEL_INNER_MS)
    # lists: three or more short items in a row ("khóc, gào, đòi hỏi")
    cuts = [-1] + [k for k in range(n - 1) if p[k] and p[k] in ",:;"] + [n - 1]
    items = [(cuts[k] + 1, cuts[k + 1]) for k in range(len(cuts) - 1)]
    run: list[int] = []
    for idx, (a, b) in enumerate(items + [(0, 10 ** 6)]):
        short = idx < len(items) and b - a + 1 <= 5 and p[b] != ":"     # a list intro is not an item
        if short:
            run.append(idx)
            continue
        if len(run) >= 3:
            for r in run[:-1]:
                c = items[r][1]
                if p[c] == ",":
                    breaks[c] = max(breaks.get(c, 0), LIST_COMMA_MS)
        run = []
    return breaks, emph


def lead_pause_ms(prev: str, cur: str) -> int:
    """Extra rest before sentence ``cur`` (after ``prev``) for the shape of the argument:
    the mirrored half of a parallel pair, the next point of a list, a contrast, a punchline."""
    a = [_word(t) for t in prev.split()]
    b = [_word(t) for t in cur.split()]
    if not a or not b:
        return 0
    extra = 0
    head = " ".join(b[:4])
    if _ORDINAL.match(head):
        extra = max(extra, ORDINAL_MS)
    if (a[:2] == b[:2] and len(b) > 2) or (a[0] == b[0] and len(set(a[1:7]) & set(b[1:7])) >= 2):
        extra = max(extra, PARALLEL_MS)
    if b[0] in _CONTRAST_OPENERS:
        extra = max(extra, CONTRAST_OPEN_MS)
    if any(tuple(a[-len(t):]) == t for t in _LIST_INTRO_TAIL):
        extra = max(extra, LIST_INTRO_MS - 250)
    if len(b) <= 7 and len(a) >= 14 and _classify(cur) == "statement":
        extra = max(extra, PUNCHLINE_MS)
    return min(extra, MAX_LEAD_MS)


def _with_break_commas(display: str, breaks: dict[int, int]) -> str:
    """The text to speak: a comma at every beat that has no punctuation, so the voice
    closes the phrase there (the pause length itself is set after synthesis)."""
    toks = display.split()
    for i in breaks:
        if 0 <= i < len(toks) - 1 and not _punct(toks[i]):
            toks[i] += ","
    return " ".join(toks)


# ──────────────────────────────────────────────────────────────
# Pronunciation lexicon (lexicon.ts, conservative subset)
# ──────────────────────────────────────────────────────────────
VI_LEXICON: list[tuple[str, str]] = [
    ("TP.HCM", "Thành phố Hồ Chí Minh"), ("TP. HCM", "Thành phố Hồ Chí Minh"), ("TPHCM", "Thành phố Hồ Chí Minh"),
    ("TP HCM", "Thành phố Hồ Chí Minh"), ("HCM", "Hồ Chí Minh"), ("TP.", "thành phố"), ("VN", "Việt Nam"),
    ("ĐBSCL", "Đồng bằng sông Cửu Long"), ("UBND", "Ủy ban nhân dân"), ("HĐND", "Hội đồng nhân dân"),
    ("CSGT", "cảnh sát giao thông"), ("BHXH", "bảo hiểm xã hội"), ("BHYT", "bảo hiểm y tế"),
    ("NHNN", "Ngân hàng Nhà nước"), ("CNTT", "công nghệ thông tin"), ("THPT", "trung học phổ thông"),
    ("THCS", "trung học cơ sở"), ("ĐHQG", "Đại học Quốc gia"), ("ĐH", "đại học"),
    ("GS.TS.", "giáo sư tiến sĩ"), ("PGS.TS.", "phó giáo sư tiến sĩ"), ("GS.", "giáo sư"),
    ("PGS.", "phó giáo sư"), ("TS.", "tiến sĩ"), ("ThS.", "thạc sĩ"), ("BS.", "bác sĩ"),
    ("TGĐ", "tổng giám đốc"), ("v.v.", "vân vân"), ("v.v", "vân vân"),
    ("GDP", "gi đi pi"), ("CPI", "xi pi ai"), ("FDI", "ép đê i"), ("AI", "ây ai"),
    ("COVID-19", "Cô vít mười chín"), ("Covid-19", "Cô vít mười chín"), ("WTO", "vê kép tê ô"),
    ("ASEAN", "A-xê-an"),
]


def _is_word_char(ch: str) -> bool:
    return bool(ch) and ch.isalnum()


def _is_acronym(s: str) -> bool:
    return any(c.isupper() for c in s) and s == s.upper()


def apply_lexicon(text: str, entries: list[tuple[str, str]]) -> str:
    """Whole-token replacement in one left-to-right pass; earlier entries win ties."""
    cands, seen = [], set()
    for order, (frm, to) in enumerate(entries):
        frm, to = unicodedata.normalize("NFC", frm).strip(), unicodedata.normalize("NFC", to).strip()
        if not frm or not to:
            continue
        cs = _is_acronym(frm)
        key = (cs, frm if cs else frm.lower())
        if key in seen:
            continue
        seen.add(key)
        cands.append((frm, to, cs, order))
    if not cands:
        return text
    cands.sort(key=lambda c: (-len(c[0]), c[3]))
    out, last, i = "", 0, 0
    while i < len(text):
        hit = None
        mid = i > 0 and _is_word_char(text[i - 1])
        for frm, to, cs, _ in cands:
            if mid and _is_word_char(frm[0]):
                continue
            sl = text[i:i + len(frm)]
            if len(sl) != len(frm) or (sl != frm if cs else sl.lower() != frm.lower()):
                continue
            if _is_word_char(frm[-1]) and _is_word_char(text[i + len(frm):i + len(frm) + 1]):
                continue
            hit = (frm, to)
            break
        if not hit:
            i += 1
            continue
        frm, to = hit
        end = i + len(frm)
        glue = " " if not _is_word_char(frm[-1]) and _is_word_char(text[end:end + 1]) else ""
        pending = out + text[last:i]
        lead = " " if not _is_word_char(frm[0]) and pending and _is_word_char(pending[-1]) else ""
        out = pending + lead + to + glue
        last = i = end
    return out + text[last:]


def lexicon_entries(user: dict | list | None, lang: str = "vi", builtin: bool = True) -> list[tuple[str, str]]:
    """User entries ({"GPT": "gi pi ti"} or [{"from","to"}]) first, then built-ins."""
    out: list[tuple[str, str]] = []
    if isinstance(user, dict):
        out += [(str(k), str(v)) for k, v in user.items()]
    elif isinstance(user, list):
        out += [(str(e["from"]), str(e["to"])) for e in user if isinstance(e, dict) and "from" in e and "to" in e]
    if builtin and lang == "vi":
        out += VI_LEXICON
    return out


# ──────────────────────────────────────────────────────────────
# Planner (planner.ts planScript)
# ──────────────────────────────────────────────────────────────
@dataclass
class Segment:
    index: int
    display: str
    spoken: str
    type: str
    paragraph: int
    boundary: str
    manual_pause: bool
    rate: int
    pitch: int
    pause_before_ms: int
    mood: str = "neutral"
    intensity: float = 0.0          # 0..1 (x expressiveness) - how strongly the mood is played
    mood_rate: float = 0.0          # the mood's own share of rate (%), pitch (semitones), gain (dB)
    mood_st: float = 0.0
    gain_db: float = 0.0
    ramp_db: float = 0.0            # loudness change across the sentence (crescendo > 0)
    breaks: dict = field(default_factory=dict)   # display token index -> beat (ms, unscaled) after it
    emph: list = field(default_factory=list)     # stressed display token spans [first, last]


@dataclass
class Plan:
    style: str
    lang: str
    segments: list[Segment] = field(default_factory=list)
    trailing_pause_ms: int = 0

    def to_json(self) -> dict:
        return asdict(self)


def parse_offset(v: str | int | float | None) -> float:
    """'+6%' / '-2Hz' / 4 -> 6 / -2 / 4."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    m = re.match(r"\s*([+-]?\d+(?:\.\d+)?)", str(v))
    return float(m.group(1)) if m else 0.0


def format_rate(r: float) -> str:
    r = round(max(-50, min(100, r)))
    return f"{'+' if r >= 0 else ''}{r}%"


def format_pitch(p: float) -> str:
    p = round(max(-50, min(50, p)))
    return f"{'+' if p >= 0 else ''}{p}Hz"


def detect_lang(text: str) -> str:
    vi = set("ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ")
    return "vi" if any(c in vi for c in text.lower()) else "en"


def prepare_spoken(display: str, lang: str, lexicon: list[tuple[str, str]], phrasing: bool) -> str:
    t = apply_lexicon(unicodedata.normalize("NFC", display), lexicon)
    t = re.sub(r"\s+", " ", t).strip()
    return insert_phrase_breaks(t, lang) if phrasing else t


HZ_PER_SEMITONE = 8.0      # Edge prosody pitch is in Hz; ~8 Hz = one semitone for a narrator
SAME_MOOD_PAUSE = 0.3      # share of a mood's extra pause kept between two sentences of the same mood
MAX_AUTO_PAUSE_MS = 1000   # longest automatic pause between two sentences of one narration


def plan_script(text: str, style: str = "natural", rate: str | float = 0, pitch: str | float = 0,
                pause_scale: float = 1.0, phrasing: bool = True, lexicon: dict | list | None = None,
                lang: str | None = None, builtin_lexicon: bool = True, mood: str | None = None,
                expressiveness: float = 1.0, auto_mood: bool = True) -> Plan:
    """``mood`` is the default delivery of the whole text (a scene's "mood"); ``[mood]``
    tags in the text win for their sentence; otherwise, with ``auto_mood``, each sentence's
    mood is read from its words.  ``expressiveness`` scales every mood effect (0 = flat)."""
    preset = STYLE_PRESETS.get(style) or STYLE_PRESETS["natural"]
    expressiveness = max(0.0, min(2.0, float(expressiveness)))
    default_mood = mood_name(mood)
    style = style if style in STYLE_PRESETS else "natural"
    lang = lang or detect_lang(text)
    pause_scale = max(0.3, min(3.0, float(pause_scale)))
    user_rate, user_pitch = parse_offset(rate), parse_offset(pitch)
    lex = lexicon_entries(lexicon, lang, builtin_lexicon)
    plan = Plan(style, lang)
    manual, saw_tag, prev_type = 0, False, None
    prev_after, prev_mood = 0.0, ("neutral", 0.0)
    units = segment_script(text)
    speech = [x for x in units if x.kind == "speech"]
    prev_display = None
    for u in units:
        if u.kind == "pause":
            manual += u.ms
            saw_tag = True
            continue
        display, marked, marked_emph = markup(u.text)
        breaks, emph = discourse_breaks(display.split()) if phrasing else ({}, [])
        breaks.update(marked)                                      # the author's marks win
        emph = marked_emph or emph
        listed = sum(1 for v in breaks.values() if v == LIST_COMMA_MS) >= 2
        spoken = prepare_spoken(_with_break_commas(display, breaks), lang, lex, phrasing)
        if not any(c.isalnum() for c in spoken):
            continue
        auto = 0.0
        if u.boundary != "start" and plan.segments:
            auto = preset["pauses"][u.boundary]
            if prev_type == "heading":
                auto = max(auto, preset["pauses"]["afterHeading"])
            elif prev_type == "question" and u.boundary != "clause":
                auto = max(auto, preset["pauses"]["afterQuestion"])
            if phrasing and prev_display and u.boundary == "sentence":
                auto += lead_pause_ms(prev_display, display)          # the shape of the argument
            auto *= pause_scale
        # how this sentence should feel: tag > scene mood > automatic reading
        if u.mood:
            md, inten = u.mood, 1.0
        elif default_mood:
            md, inten = default_mood, 1.0
        elif auto_mood and u.type != "heading":
            md, inten = detect_mood(display)
            if md == "fast" and listed:
                md, inten = "neutral", 0.0          # a list is laid out item by item, not rushed
            if md == "neutral" and prev_mood[0] in ("emotional", "suspense"):
                md, inten = prev_mood[0], 0.5 * prev_mood[1]       # a feeling lingers a little
            elif (md == "neutral" and len(speech) >= 2 and u is speech[-1] and u.type == "statement"
                  and len(u.text.split()) <= 9):
                md, inten = "slow", 0.6                             # a short closing line lands slowly
        else:
            md, inten = "neutral", 0.0
        k = inten * expressiveness
        mp = MOODS[md]
        if auto > 0:
            auto *= 1.0 + (mp["pace"] - 1.0) * k
        if plan.segments:
            extra = max(mp["before"] * k, prev_after)               # one breath, not two
            if md == prev_mood[0] and md != "neutral":
                extra *= SAME_MOOD_PAUSE       # inside a run of one mood the dramatic beat is not repeated
            auto += extra * pause_scale
            if u.boundary in ("sentence", "clause"):              # paragraphs keep their longer rest
                auto = min(auto, MAX_AUTO_PAUSE_MS * pause_scale)
        r, p = preset["rate"] + user_rate, preset["pitch"] + user_pitch
        tweaks = []
        if u.type in ("heading", "question", "exclamation"):
            tweaks.append(preset[u.type])
        if u.first and u.type != "heading":
            tweaks.append(preset["paragraphStart"])
        if u.last and not u.first and u.type != "heading":
            tweaks.append(preset["paragraphEnd"])
        for dr, dp in tweaks:
            r += dr
            p += dp
        r += mp["rate"] * k
        p += mp["st"] * k * HZ_PER_SEMITONE
        has_prev = bool(plan.segments)
        plan.segments.append(Segment(
            len(plan.segments), display, spoken, u.type, u.paragraph, u.boundary, saw_tag and has_prev,
            int(max(-50, min(100, round(r)))), int(max(-50, min(50, round(p)))),
            int(round((manual if saw_tag else auto) if has_prev else manual)),
            md, round(inten, 3), round(mp["rate"] * k, 2), round(mp["st"] * k, 3),
            round(mp["gain"] * k, 2), round(mp["ramp"] * k, 2),
            {int(i): int(v) for i, v in sorted(breaks.items())}, [list(e) for e in emph]))
        manual, saw_tag, prev_type, prev_display = 0, False, u.type, display
        prev_after, prev_mood = mp["after"] * k, (md, inten)
    plan.trailing_pause_ms = manual
    return plan


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Show how a narration will be read (Voice Studio plan)")
    p.add_argument("text", help="text, or @file.txt")
    p.add_argument("--style", default="natural", choices=STYLES)
    p.add_argument("--rate", default="+0%")
    p.add_argument("--pitch", default="+0Hz")
    p.add_argument("--pause-scale", type=float, default=1.0)
    p.add_argument("--mood", default=None, help="default mood: " + ", ".join(MOODS))
    p.add_argument("--expressiveness", type=float, default=1.0, help="0 = flat ... 1 = default ... 2 = strong")
    p.add_argument("--catalogue", action="store_true", help="print the voice catalogue instead")
    a = p.parse_args(argv)
    if a.catalogue:
        print(json.dumps(CATALOGUE, ensure_ascii=False, indent=2))
        return 0
    text = open(a.text[1:], encoding="utf-8").read() if a.text.startswith("@") else a.text
    plan = plan_script(text, a.style, a.rate, a.pitch, a.pause_scale, mood=a.mood,
                       expressiveness=a.expressiveness)
    for s in plan.segments:
        feel = f"{s.mood}" + (f"·{s.intensity:.1f}" if s.mood != "neutral" else "")
        toks = s.display.split()
        stressed = {k for a_, b_ in s.emph for k in range(a_, b_ + 1)}
        shown = " ".join((f"*{t}*" if k in stressed else t) + (f" ⟨{s.breaks[k]}⟩" if k in s.breaks else "")
                         for k, t in enumerate(toks))
        print(f"[{s.pause_before_ms:>5} ms] {format_rate(s.rate):>5} {format_pitch(s.pitch):>6} "
              f"{s.type:<11} {feel:<14} {shown}")
    print("⟨ms⟩ = nhịp ngừng sau từ đó (trước khi nhân pauseScale), *từ* = được nhấn")
    return 0


if __name__ == "__main__":
    sys.exit(main())
