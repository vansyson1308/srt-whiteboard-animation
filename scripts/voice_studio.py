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
    "tiktok": [
        {"id": "BV074_streaming", "gender": "female", "note": "Chị Vi - giọng TikTok quen thuộc"},
        {"id": "BV075_streaming", "gender": "male", "note": "Anh Vi - giọng TikTok quen thuộc"},
    ],
    "makevoice": [
        {"id": "pNInz6obpgDQGcFmaJgB", "gender": "male", "note": "Adam (ElevenLabs) - dứt khoát"},
        {"id": "21m00Tcm4TlvDq8ikWAM", "gender": "female", "note": "Rachel (ElevenLabs) - điềm tĩnh"},
    ],
    "elevenlabs": [
        {"id": "pNInz6obpgDQGcFmaJgB", "gender": "male", "note": "Adam"},
        {"id": "21m00Tcm4TlvDq8ikWAM", "gender": "female", "note": "Rachel"},
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
    """The text a viewer should see: pause tags removed, whitespace collapsed."""
    return re.sub(r"\s+", " ", PAUSE_TAG.sub(" ", text)).strip()


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
            chunk = str(val).strip()
            if not chunk:
                continue
            for si, sentence in enumerate(split_sentences(chunk)):
                parts = split_long_sentence(sentence)
                for pi, part in enumerate(parts):
                    u = Unit("speech", part,
                             "heading" if heading else _classify(sentence if pi == len(parts) - 1 else part),
                             "clause" if pi > 0 else ("sentence" if si > 0 or line_units else pending),
                             paragraph)
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


def plan_script(text: str, style: str = "natural", rate: str | float = 0, pitch: str | float = 0,
                pause_scale: float = 1.0, phrasing: bool = True, lexicon: dict | list | None = None,
                lang: str | None = None, builtin_lexicon: bool = True) -> Plan:
    preset = STYLE_PRESETS.get(style) or STYLE_PRESETS["natural"]
    style = style if style in STYLE_PRESETS else "natural"
    lang = lang or detect_lang(text)
    pause_scale = max(0.3, min(3.0, float(pause_scale)))
    user_rate, user_pitch = parse_offset(rate), parse_offset(pitch)
    lex = lexicon_entries(lexicon, lang, builtin_lexicon)
    plan = Plan(style, lang)
    manual, saw_tag, prev_type = 0, False, None
    for u in segment_script(text):
        if u.kind == "pause":
            manual += u.ms
            saw_tag = True
            continue
        spoken = prepare_spoken(u.text, lang, lex, phrasing)
        if not any(c.isalnum() for c in spoken):
            continue
        auto = 0.0
        if u.boundary != "start" and plan.segments:
            auto = preset["pauses"][u.boundary]
            if prev_type == "heading":
                auto = max(auto, preset["pauses"]["afterHeading"])
            elif prev_type == "question" and u.boundary != "clause":
                auto = max(auto, preset["pauses"]["afterQuestion"])
            auto *= pause_scale
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
        has_prev = bool(plan.segments)
        plan.segments.append(Segment(
            len(plan.segments), u.text, spoken, u.type, u.paragraph, u.boundary, saw_tag and has_prev,
            int(max(-50, min(100, round(r)))), int(max(-50, min(50, round(p)))),
            int(round((manual if saw_tag else auto) if has_prev else manual))))
        manual, saw_tag, prev_type = 0, False, u.type
    plan.trailing_pause_ms = manual
    return plan


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Show how a narration will be read (Voice Studio plan)")
    p.add_argument("text", help="text, or @file.txt")
    p.add_argument("--style", default="natural", choices=STYLES)
    p.add_argument("--rate", default="+0%")
    p.add_argument("--pitch", default="+0Hz")
    p.add_argument("--pause-scale", type=float, default=1.0)
    p.add_argument("--catalogue", action="store_true", help="print the voice catalogue instead")
    a = p.parse_args(argv)
    if a.catalogue:
        print(json.dumps(CATALOGUE, ensure_ascii=False, indent=2))
        return 0
    text = open(a.text[1:], encoding="utf-8").read() if a.text.startswith("@") else a.text
    plan = plan_script(text, a.style, a.rate, a.pitch, a.pause_scale)
    for s in plan.segments:
        print(f"[{s.pause_before_ms:>5} ms] {format_rate(s.rate):>5} {format_pitch(s.pitch):>6} "
              f"{s.type:<11} {s.spoken}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
