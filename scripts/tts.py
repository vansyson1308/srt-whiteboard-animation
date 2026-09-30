#!/usr/bin/env python3
"""
Text-to-speech with word-level timings (for voice sync + karaoke captions).

Engines
  edge        free Microsoft Edge neural voices (default).  Vietnamese:
              vi-VN-HoaiMyNeural (female), vi-VN-NamMinhNeural (male).
              Real per-word timings (WordBoundary events).
  elevenlabs  ELEVENLABS_API_KEY; /with-timestamps -> real character timings.
  openai      OPENAI_API_KEY; gpt-4o-mini-tts; timings estimated from text.
  silent      no audio (silence of the estimated speaking length) - for drafts/tests.

Every engine returns the same thing: an audio file + a list of words
``{"text", "startMs", "endMs"}`` whose text keeps the original punctuation.

Usage:
  python tts.py "Xin chào các bạn." out.mp3 [--engine edge] [--voice vi-VN-NamMinhNeural]
                [--rate +5%] [--srt out.srt] [--words out.words.json]
  python tts.py --list-voices vi
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

DEFAULT_VOICES = {
    "edge": "vi-VN-HoaiMyNeural",
    "openai": "alloy",
    "elevenlabs": "21m00Tcm4TlvDq8ikWAM",
    "silent": "",
}
OPENAI_TTS_MODEL = os.environ.get("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_flash_v2_5")


@dataclass
class Word:
    text: str
    startMs: int
    endMs: int


@dataclass
class TTSResult:
    audio: str
    durationMs: int
    words: list[Word]
    engine: str
    voice: str

    def to_json(self) -> dict:
        d = asdict(self)
        d["words"] = [asdict(w) for w in self.words]
        return d

    @staticmethod
    def from_json(d: dict) -> "TTSResult":
        return TTSResult(d["audio"], d["durationMs"], [Word(**w) for w in d["words"]], d["engine"], d["voice"])


# ──────────────────────────────────────────────────────────────
# Text helpers
# ──────────────────────────────────────────────────────────────
def tokens(text: str) -> list[str]:
    return [t for t in re.split(r"\s+", text.strip()) if t]


def norm(t: str) -> str:
    t = unicodedata.normalize("NFC", t.lower())
    return "".join(ch for ch in t if ch.isalnum())


def _weight(tok: str) -> float:
    w = len(norm(tok)) + 2.0
    if tok[-1:] in ",;:":
        w += 4
    elif tok[-1:] in ".!?…":
        w += 8
    return w


def estimate_words(text: str, start_ms: float, end_ms: float) -> list[Word]:
    """Spread the text's tokens over [start, end] proportionally to their length."""
    toks = tokens(text)
    if not toks:
        return []
    ws = [_weight(t) for t in toks]
    total = sum(ws)
    out, t = [], float(start_ms)
    span = max(1.0, end_ms - start_ms)
    for tok, w in zip(toks, ws):
        d = span * w / total
        # the pause after punctuation is not part of the word itself
        speak = d * (len(norm(tok)) + 2.0) / w
        out.append(Word(tok, int(round(t)), int(round(t + speak))))
        t += d
    return out


def estimate_speech_ms(text: str, syllables_per_sec: float = 3.6) -> int:
    toks = tokens(text)
    ms = len(toks) / syllables_per_sec * 1000
    ms += sum(250 for t in toks if t[-1:] in ",;:") + sum(450 for t in toks if t[-1:] in ".!?…")
    return int(ms)


def align_to_text(text: str, spoken: list[Word]) -> list[Word]:
    """Map engine word timings back onto the original tokens (keeps punctuation).

    Engines split and merge tokens freely ("năm 2024" may come back as one
    word, "365,25" as several), so we align at character level: each
    normalised character of the spoken words gets a time (linear inside its
    word), the original tokens' characters are matched to them with difflib,
    and a token spans from its first to its last matched character.  If too
    little matches we fall back to a proportional estimate.
    """
    import difflib
    toks = tokens(text)
    if not toks or not spoken:
        return spoken
    sp_chars, sp_t0, sp_t1 = [], [], []
    for w in spoken:
        c = norm(w.text)
        n = len(c)
        for i, ch in enumerate(c):
            sp_chars.append(ch)
            sp_t0.append(w.startMs + (w.endMs - w.startMs) * i / n)
            sp_t1.append(w.startMs + (w.endMs - w.startMs) * (i + 1) / n)
    tk_chars, owner = [], []
    for ti, t in enumerate(toks):
        for ch in norm(t):
            tk_chars.append(ch)
            owner.append(ti)
    if not sp_chars or not tk_chars:
        return estimate_words(text, spoken[0].startMs, spoken[-1].endMs)
    sm = difflib.SequenceMatcher(None, tk_chars, sp_chars, autojunk=False)
    mapped: dict[int, int] = {}
    for a, b, size in sm.get_matching_blocks():
        for k in range(size):
            mapped[a + k] = b + k
    if len(mapped) < 0.6 * len(tk_chars):
        return estimate_words(text, spoken[0].startMs, spoken[-1].endMs)
    spans: list[list[float]] = [[None, None] for _ in toks]  # type: ignore[list-item]
    for ci, ti in enumerate(owner):
        if ci in mapped:
            j = mapped[ci]
            if spans[ti][0] is None:
                spans[ti][0] = sp_t0[j]
            spans[ti][1] = sp_t1[j]
    out: list[Word] = []
    prev_end = float(spoken[0].startMs)
    for ti, tok in enumerate(toks):
        s0, s1 = spans[ti]
        if s0 is None:  # unmatched token: squeeze it in after the previous one
            nxt = next((spans[k][0] for k in range(ti + 1, len(toks)) if spans[k][0] is not None),
                       float(spoken[-1].endMs))
            s0 = prev_end
            s1 = max(prev_end, min(nxt, prev_end + 250))
        s0 = max(s0, prev_end if out else s0)
        s1 = max(s1, s0)
        out.append(Word(tok, int(round(s0)), int(round(s1))))
        prev_end = s1
    return out


def words_to_srt(words: list[Word], max_chars: int = 42, max_words: int = 10) -> str:
    cues, cur = [], []
    for w in words:
        cur.append(w)
        text = " ".join(x.text for x in cur)
        if len(text) >= max_chars or len(cur) >= max_words or w.text[-1:] in ".!?…":
            cues.append(cur)
            cur = []
    if cur:
        cues.append(cur)

    def ts(ms: int) -> str:
        h, ms = divmod(int(ms), 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    lines = []
    for i, c in enumerate(cues, 1):
        lines += [str(i), f"{ts(c[0].startMs)} --> {ts(c[-1].endMs)}", " ".join(x.text for x in c), ""]
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# Engines
# ──────────────────────────────────────────────────────────────
def _edge_ssl_fix() -> None:
    """edge-tts pins certifi; honour SSL_CERT_FILE (corporate proxies / custom CAs)."""
    ca = os.environ.get("SSL_CERT_FILE")
    if not ca or not Path(ca).exists():
        return
    try:
        import ssl
        import edge_tts.communicate as ec
        ec._SSL_CTX = ssl.create_default_context(cafile=ca)
    except Exception:  # pragma: no cover
        pass


def _edge(text: str, out: Path, voice: str, rate: str, pitch: str, volume: str) -> list[Word]:
    import edge_tts
    _edge_ssl_fix()

    async def run() -> list[Word]:
        kw = dict(rate=rate, pitch=pitch, volume=volume)
        try:
            com = edge_tts.Communicate(text, voice, boundary="WordBoundary", **kw)
        except TypeError:  # edge-tts < 7.2 always emits WordBoundary
            com = edge_tts.Communicate(text, voice, **kw)
        words = []
        with open(out, "wb") as f:
            async for ch in com.stream():
                if ch["type"] == "audio":
                    f.write(ch["data"])
                elif ch["type"] == "WordBoundary":
                    s = ch["offset"] / 10000.0
                    words.append(Word(ch["text"], int(round(s)), int(round(s + ch["duration"] / 10000.0))))
        return words

    last = None
    for attempt in range(4):
        try:
            return asyncio.run(run())
        except Exception as e:  # network hiccups are common: retry with backoff
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"edge-tts failed: {last}")


def _post_json(url: str, payload: dict, headers: dict) -> bytes:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={
        "Content-Type": "application/json", **headers}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def _openai(text: str, out: Path, voice: str, instructions: str | None) -> None:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    payload = {"model": OPENAI_TTS_MODEL, "voice": voice, "input": text, "response_format": "mp3"}
    if instructions:
        payload["instructions"] = instructions
    out.write_bytes(_post_json("https://api.openai.com/v1/audio/speech", payload,
                               {"Authorization": f"Bearer {key}"}))


def _elevenlabs(text: str, out: Path, voice: str, language: str | None) -> list[Word]:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")
    payload = {"text": text, "model_id": ELEVENLABS_MODEL}
    if language:
        payload["language_code"] = language
    data = json.loads(_post_json(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_128",
        payload, {"xi-api-key": key}))
    out.write_bytes(base64.b64decode(data["audio_base64"]))
    al = data.get("alignment") or data.get("normalized_alignment") or {}
    chars = al.get("characters", [])
    st = al.get("character_start_times_seconds", [])
    en = al.get("character_end_times_seconds", [])
    words, cur, cs, ce = [], "", None, None
    for c, s, e in zip(chars, st, en):
        if c.isspace():
            if cur:
                words.append(Word(cur, int(cs * 1000), int(ce * 1000)))
            cur, cs = "", None
            continue
        if cs is None:
            cs = s
        cur += c
        ce = e
    if cur:
        words.append(Word(cur, int(cs * 1000), int(ce * 1000)))
    return words


def _speech_span(audio_path: Path) -> tuple[int, int, int]:
    """(first_voice_ms, last_voice_ms, total_ms) using an energy gate."""
    import numpy as np
    import wb_video
    a = wb_video.load_audio(audio_path, stereo=False)
    total = int(len(a) * 1000 / wb_video.SAMPLE_RATE)
    if not len(a):
        return 0, 0, 0
    env = wb_video.rms_envelope(a, 20)
    on = np.nonzero(env > max(0.005, float(env.max()) * 0.05))[0]
    if on.size == 0:
        return 0, total, total
    return int(on[0] * 1000 / wb_video.SAMPLE_RATE), int(on[-1] * 1000 / wb_video.SAMPLE_RATE), total


def synthesize(text: str, out: str | Path, engine: str = "edge", voice: str | None = None,
               rate: str = "+0%", pitch: str = "+0Hz", volume: str = "+0%",
               instructions: str | None = None, language: str | None = "vi") -> TTSResult:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    voice = voice or DEFAULT_VOICES.get(engine, "")
    text = unicodedata.normalize("NFC", text.strip())
    if engine == "silent":
        import wb_video
        ms = estimate_speech_ms(text)
        out = out.with_suffix(".wav")
        wb_video.save_wav(out, wb_video.silence(ms + 200))
        return TTSResult(str(out), ms + 200, estimate_words(text, 100, 100 + ms), engine, voice)
    if engine == "edge":
        spoken = _edge(text, out, voice, rate, pitch, volume)
        words = align_to_text(text, spoken) if spoken else None
    elif engine == "elevenlabs":
        spoken = _elevenlabs(text, out, voice, language)
        words = align_to_text(text, spoken) if spoken else None
    elif engine == "openai":
        _openai(text, out, voice, instructions)
        words = None
    else:
        raise ValueError(f"unknown TTS engine: {engine}")
    first, last, total = _speech_span(out)
    if not words:
        words = estimate_words(text, first, last)
    return TTSResult(str(out), total, words, engine, voice)


def list_voices(prefix: str = "vi") -> list[dict]:
    import edge_tts
    _edge_ssl_fix()
    voices = asyncio.run(edge_tts.list_voices())
    return [{"name": v["ShortName"], "gender": v["Gender"]} for v in voices
            if v["Locale"].lower().startswith(prefix.lower())]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="TTS with word timings")
    p.add_argument("text", nargs="?", help="text, or @file.txt")
    p.add_argument("out", nargs="?")
    p.add_argument("--engine", default="edge", choices=["edge", "openai", "elevenlabs", "silent"])
    p.add_argument("--voice", default=None)
    p.add_argument("--rate", default="+0%")
    p.add_argument("--pitch", default="+0Hz")
    p.add_argument("--instructions", default=None, help="openai: speaking style")
    p.add_argument("--srt", default=None)
    p.add_argument("--words", default=None)
    p.add_argument("--list-voices", default=None, metavar="LOCALE_PREFIX")
    a = p.parse_args(argv)
    if a.list_voices is not None:
        print(json.dumps(list_voices(a.list_voices), ensure_ascii=False, indent=2))
        return 0
    if not a.text or not a.out:
        p.error("text and out are required")
    text = Path(a.text[1:]).read_text(encoding="utf-8") if a.text.startswith("@") else a.text
    r = synthesize(text, a.out, a.engine, a.voice, a.rate, a.pitch, instructions=a.instructions)
    if a.srt:
        Path(a.srt).write_text(words_to_srt(r.words), encoding="utf-8")
    if a.words:
        Path(a.words).write_text(json.dumps(r.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(r.words)} words, {r.durationMs} ms")
    print(f"OUTPUT={Path(r.audio).resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
