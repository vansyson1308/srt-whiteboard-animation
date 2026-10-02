#!/usr/bin/env python3
"""
Text-to-speech with word-level timings (for voice sync + karaoke captions).

Engines (Vietnamese-capable; voice catalogue: ``python voice_studio.py x --catalogue``)
  edge        free Microsoft Edge neural voices (default).  vi-VN-HoaiMyNeural (female),
              vi-VN-NamMinhNeural (male), or a *MultilingualNeural voice.  Real word timings.
              With a ``style`` it runs in *expressive* mode (Voice Studio, from ttspromax):
              one request per sentence with its own rate/pitch, breath commas, and exact,
              style-aware pauses stitched in between.
  gemini      GEMINI_API_KEY (free tier).  LLM voices (Sulafat, Kore, Charon, ...) that follow
              the style direction ("audiobook narrator"); one request per sentence.
  vieneu      VieNeu-TTS v3 Turbo - free, offline, Apache-2.0 Vietnamese model on CPU
              (``pip install vieneu``).  25 preset voices (Hải Đăng, Thiện Minh, Mai Anh, ...),
              or cloning from a consented reference clip.
  tiktok      the TikTok voices (BV074_streaming "Chị Vi", BV075_streaming "Anh Vi") via a
              public proxy (TIKTOK_TTS_PROXY to override).  No key.
  makevoice   ElevenLabs voices through makevoice.io (unofficial, no key, may change).
  elevenlabs  ELEVENLABS_API_KEY; /with-timestamps -> real character timings.  Newest model
              first (eleven_v4 -> eleven_v3 -> eleven_flash_v2_5), Vietnamese voice by default.
  openai      OPENAI_API_KEY; gpt-4o-mini-tts; the style becomes its ``instructions``.
              OPENAI_BASE_URL points it at any OpenAI-compatible server (e.g. ``vieneu serve``).
  fish        FISH_API_KEY + ``pip install fish-audio-sdk``.  A fish.audio voice model id,
              or cloning from ``reference`` audio - only with the speaker's consent
              (``consent=True`` / "confirmAuthorizedVoice": true).
  silent      no audio (silence of the estimated speaking length) - for drafts/tests.

Every engine returns the same thing: an audio file + a list of words
``{"text", "startMs", "endMs"}`` whose text keeps the original punctuation.  Engines
without timestamps (gemini/tiktok/makevoice/openai/fish) get *pause-anchored* timings:
silences found in the audio are matched to the punctuation of the text, and words are
spread over the voiced time between those anchors.

Usage:
  python tts.py "Xin chào các bạn." out.mp3 [--engine edge] [--voice vi-VN-NamMinhNeural]
                [--style story] [--rate +5%] [--srt out.srt] [--words out.words.json]
  python tts.py --list-voices vi
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import voice_studio as vs  # noqa: E402

ENGINES = ["edge", "gemini", "vieneu", "elevenlabs", "openai", "fish", "tiktok", "makevoice", "silent"]
DEFAULT_VOICES = {
    "edge": "vi-VN-HoaiMyNeural",
    "gemini": "Sulafat",
    "vieneu": "Hải Đăng",
    "tiktok": "BV074_streaming",
    "makevoice": "pNInz6obpgDQGcFmaJgB",
    "openai": "alloy",
    "elevenlabs": "FTYCiQT21H9XQvhRu0ch",     # "MinhTrung", Vietnamese male
    "fish": "",
    "silent": "",
}
OPENAI_TTS_MODEL = os.environ.get("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
# newest first; a model the account/API doesn't know falls through to the next one
ELEVENLABS_MODELS = ([os.environ["ELEVENLABS_MODEL"]] if os.environ.get("ELEVENLABS_MODEL")
                     else ["eleven_v4", "eleven_v3", "eleven_flash_v2_5"])
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
VIENEU_MODE = os.environ.get("VIENEU_MODE", "v3turbo")      # or v3nano for weak CPUs
GEMINI_TTS_MODEL = os.environ.get("GEMINI_TTS_MODEL", "gemini-3.8-flash-tts")
TIKTOK_TTS_PROXY = os.environ.get("TIKTOK_TTS_PROXY", "https://tiktok-tts.weilnet.workers.dev/api/generation")
FISH_TTS_MODEL = os.environ.get("FISH_TTS_MODEL", "s2-pro")


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


def _speech_weight(tok: str) -> float:
    """Relative speaking time of a token.  Digits are read out ("1969" -> "một nghìn chín
    trăm sáu mươi chín", ~2 syllables per digit), so they weigh far more than 4 letters."""
    n = norm(tok)
    if not n:
        return 0.5
    digits = sum(ch.isdigit() for ch in n)
    if digits:
        return (2 * digits - 1) * 5.5 + (len(n) - digits) + 2.0
    return len(n) + 2.0


def _weight(tok: str) -> float:
    w = _speech_weight(tok)
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
        speak = d * _speech_weight(tok) / w
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
        if s0 is None:
            # unmatched run (a lexicon expansion, a dropped word): the run shares the
            # time up to the next matched token, at most ~600 ms per token
            k = ti
            while k < len(toks) and spans[k][0] is None:
                k += 1
            nxt = spans[k][0] if k < len(toks) else float(spoken[-1].endMs)
            gap = max(0.0, min(nxt - prev_end, 600.0 * (k - ti)))
            s0 = prev_end
            s1 = prev_end + gap / (k - ti)
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


def _request(url: str, data: bytes, headers: dict, what: str, attempts: int = 4) -> tuple[bytes, str]:
    """POST with retries/backoff; follows 307/308 keeping the body. -> (body, content-type)."""
    import urllib.error
    last: Exception | None = None
    for attempt in range(attempts):
        target = url
        try:
            for _ in range(4):
                req = urllib.request.Request(target, data=data, headers=headers, method="POST")
                try:
                    with urllib.request.urlopen(req, timeout=180) as r:
                        return r.read(), r.headers.get("Content-Type", "")
                except urllib.error.HTTPError as e:
                    if e.code in (307, 308) and e.headers.get("Location"):
                        target = urllib.parse.urljoin(target, e.headers["Location"])
                        continue
                    raise
            raise RuntimeError("too many redirects")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            if 400 <= e.code < 500 and e.code not in (408, 429):   # our request is wrong: don't retry
                raise RuntimeError(f"{what}: HTTP {e.code} {detail}") from e
            last = RuntimeError(f"HTTP {e.code} {detail}")
        except Exception as e:  # network hiccups are common
            last = e
        time.sleep(2 ** attempt)
    raise RuntimeError(f"{what} failed: {last}")


def _post_json(url: str, payload: dict, headers: dict, what: str = "TTS request") -> bytes:
    body, _ = _request(url, json.dumps(payload).encode(), {"Content-Type": "application/json", **headers}, what)
    return body


def _openai(text: str, out: Path, voice: str, instructions: str | None) -> None:
    key = os.environ.get("OPENAI_API_KEY") or ("local" if "api.openai.com" not in OPENAI_BASE_URL else None)
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    payload = {"model": OPENAI_TTS_MODEL, "voice": voice, "input": text, "response_format": "mp3"}
    if instructions:
        payload["instructions"] = instructions
    out.write_bytes(_post_json(f"{OPENAI_BASE_URL}/audio/speech", payload,
                               {"Authorization": f"Bearer {key}"}))


def _elevenlabs(text: str, out: Path, voice: str, language: str | None) -> list[Word]:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set")
    data, last = None, None
    for model in ELEVENLABS_MODELS:
        payload = {"text": text, "model_id": model}
        if language:
            payload["language_code"] = language
        try:
            data = json.loads(_post_json(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps?output_format=mp3_44100_128",
                payload, {"xi-api-key": key}, "ElevenLabs TTS"))
            break
        except RuntimeError as e:     # unknown model / no timestamps for it: try the next one
            last = e
            if any(f"HTTP {c}" in str(e) for c in (401, 402, 403, 429)):
                raise
    if data is None:
        raise RuntimeError(f"ElevenLabs TTS failed for {ELEVENLABS_MODELS}: {last}")
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


def _gemini(text: str, voice: str, direction: str) -> bytes:
    """One Gemini TTS request (Interactions API, as in ttspromax) -> WAV bytes."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set (free key: https://aistudio.google.com/apikey)")
    payload = {
        "model": GEMINI_TTS_MODEL,
        "input": [{"type": "user_input", "content": [
            {"type": "text", "text": text, "annotations": [{"type": "speech_metadata", "style": direction}]}]}],
        "response_format": {"type": "audio"},
        "generation_config": {"speech_config": [{"voice": voice}]},
    }
    data = json.loads(_post_json("https://generativelanguage.googleapis.com/v1beta/interactions", payload,
                                 {"x-goog-api-key": key}, "Gemini TTS"))
    b64, mime = _find_audio_b64(data)
    if not b64:
        raise RuntimeError("Gemini TTS returned no audio")
    raw = base64.b64decode(b64)
    if raw[:4] == b"RIFF":
        return raw
    m = re.search(r"rate=(\d+)", mime or "")           # raw 16-bit PCM (audio/L16;rate=24000)
    return _pcm16_wav(raw, int(m.group(1)) if m else 24000)


def _find_audio_b64(node) -> tuple[str | None, str]:
    """The longest base64 ``data`` field with an audio mime type (response shapes vary)."""
    best: list = [None, ""]

    def visit(n) -> None:
        if isinstance(n, list):
            for x in n:
                visit(x)
        elif isinstance(n, dict):
            mime = str(n.get("mime_type") or n.get("mimeType") or n.get("type") or "")
            d = n.get("data")
            if isinstance(d, str) and ("audio" in mime.lower() or len(d) > 1000):
                if best[0] is None or len(d) > len(best[0]):
                    best[0], best[1] = d, mime
            for v in n.values():
                visit(v)
    visit(node)
    return best[0], best[1]


def _pcm16_wav(raw: bytes, rate: int) -> bytes:
    import io
    import wave
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(raw[:len(raw) // 2 * 2])
    return buf.getvalue()


def _tiktok(text: str, voice: str) -> bytes:
    """TikTok voices through the public proxy used by ttspromax -> MP3 bytes (<= 300 chars)."""
    body, _ = _request(TIKTOK_TTS_PROXY, json.dumps({"text": text, "voice": voice}).encode(),
                       {"Content-Type": "application/json"}, "TikTok TTS")
    data = json.loads(body)
    if not data.get("success") or not data.get("data"):
        raise RuntimeError(f"TikTok TTS: {data.get('error') or 'no audio'}")
    return base64.b64decode(data["data"])


def _makevoice(text: str, voice: str, language: str | None) -> bytes:
    """ElevenLabs voices through makevoice.io (unofficial endpoint used by ttspromax) -> MP3."""
    model = "eleven_turbo_v2_5" if (language or "vi") == "vi" else "eleven_multilingual_v2"
    body, ctype = _request("https://makevoice.io/api/text-to-speech",
                           json.dumps({"voice_id": voice, "text": text, "model": model}).encode(),
                           {"Content-Type": "application/json",
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                           "MakeVoice TTS")
    if "json" in ctype or body[:1] in (b"{", b"<"):
        raise RuntimeError(f"MakeVoice TTS: {body[:200].decode('utf-8', 'replace')}")
    return body


def _fish(text: str, voice: str, reference: str | None, reference_text: str | None) -> bytes:
    """fish.audio: a voice model id, or cloning from a consented reference clip -> WAV."""
    if not os.environ.get("FISH_API_KEY"):
        raise RuntimeError("FISH_API_KEY is not set")
    try:
        from fishaudio import FishAudio
        from fishaudio.types import ReferenceAudio
    except ImportError as e:
        raise RuntimeError("fish engine needs: pip install fish-audio-sdk") from e
    kw: dict = {"text": text, "format": "wav", "latency": "normal", "model": FISH_TTS_MODEL}
    if reference:
        if not reference_text:
            raise RuntimeError("fish cloning needs referenceText (the transcript of the reference clip)")
        kw["references"] = [ReferenceAudio(audio=Path(reference).read_bytes(), text=reference_text)]
    elif voice:
        kw["reference_id"] = voice
    else:
        raise RuntimeError("fish engine needs a voice (model id) or a reference clip")
    audio = FishAudio().tts.convert(**kw)
    return audio if isinstance(audio, bytes) else b"".join(audio)


_VIENEU: dict = {}
_VIENEU_LOCK = __import__("threading").Lock()


def _vieneu_model():
    """Load VieNeu-TTS once per process (~20 s the first time, then cached)."""
    if "tts" in _VIENEU:
        return _VIENEU["tts"]
    try:
        from vieneu import Vieneu
        from vieneu._v3_turbo_engine import onnx_runtime_lite as orl
    except ImportError as e:
        raise RuntimeError("vieneu engine needs: pip install vieneu") from e
    root = Path(os.environ.get("VIENEU_CACHE", Path.home() / ".cache" / "wb-video" / "vieneu"))

    def fetch(repo: str, files: list, subfolder: str | None) -> Path:
        # Real files instead of HF-cache symlinks: onnxruntime >= 1.2x rejects ONNX
        # external data that resolves outside the model's own directory.
        from huggingface_hub import hf_hub_download
        last = None
        for fn in files:
            try:
                last = hf_hub_download(repo, fn, subfolder=subfolder or None,
                                       local_dir=root / repo.replace("/", "--"))
            except Exception:
                if fn.endswith(".json"):
                    continue
                raise
        return Path(last).parent
    orl.OnnxV3LiteEngine._fetch = staticmethod(fetch)
    _VIENEU["tts"] = Vieneu(mode=VIENEU_MODE)
    return _VIENEU["tts"]


def release_models() -> None:
    """Free loaded local TTS models (VieNeu holds ~1.5 GB) once the voice stage is done."""
    import gc
    _VIENEU.clear()
    gc.collect()


def vieneu_voices() -> list[str]:
    return [vid for _, vid in _vieneu_model().list_preset_voices()]


def engine_available(engine: str) -> bool:
    """False when an optional engine's package is missing (callers fall back to edge)."""
    import importlib.util
    mod = {"vieneu": "vieneu", "fish": "fishaudio"}.get(engine)
    return mod is None or importlib.util.find_spec(mod) is not None


def plausible_speech(text: str, pcm, lo: float = 0.55, hi: float = 1.8) -> float:
    """How far the voiced length is from what the text needs (1.0 = as expected).

    Generative voices occasionally babble, stall or swallow words; those takes are
    far off the ~4.5 syllables/s of narration.  Returns the ratio voiced/expected.
    """
    import wb_video
    iv = _voiced_intervals(pcm, 250)
    voiced = sum(e - s for s, e in iv) / 1000.0
    syllables = sum(_speech_weight(t) for t in tokens(text)) / 5.5
    expected = max(0.4, syllables / 4.5)
    return voiced / expected if len(pcm) > wb_video.SAMPLE_RATE // 20 else 0.0


VIENEU_TAKES = int(os.environ.get("VIENEU_TAKES", "3"))    # max takes per sentence


def _vieneu(text: str, voice: str, reference: str | None, tmp: Path):
    """One VieNeu synthesis -> mono float32 at 48 kHz.  A take whose length is
    implausible for the text (babbling / swallowed words) is generated again and the
    most plausible take is kept."""
    import wb_video
    best, best_err = None, float("inf")
    for _ in range(max(1, VIENEU_TAKES)):
        with _VIENEU_LOCK:                      # CPU-bound and not re-entrant
            tts = _vieneu_model()
            if reference:
                wav = tts.infer(text, ref_audio=reference)
            else:
                if tts.resolve_voice_name(voice) is None:
                    raise RuntimeError(f"unknown VieNeu voice {voice!r}; available: {vieneu_voices()}")
                wav = tts.infer(text, voice=tts.get_preset_voice(voice))
            rate = tts.sample_rate
        pcm = _vieneu_to48k(wav, rate, tmp)
        ratio = plausible_speech(text, pcm)
        err = abs(math.log(max(ratio, 1e-3)))
        if err < best_err:
            best, best_err = pcm, err
        if 0.55 <= ratio <= 1.8:
            break
    return best


def _vieneu_to48k(wav, rate: int, tmp: Path):
    import wb_video
    f = tmp.with_suffix(".wav")
    wb_video.save_wav(f, wav, sample_rate=rate)
    try:
        return wb_video.load_audio(f, stereo=False)      # resamples if rate != 48 kHz
    finally:
        f.unlink(missing_ok=True)


def _decode(data: bytes, suffix: str, tmp: Path):
    """Audio bytes -> mono float32 at 48 kHz."""
    import wb_video
    f = tmp.with_suffix(suffix)
    f.write_bytes(data)
    try:
        return wb_video.load_audio(f, stereo=False)
    finally:
        f.unlink(missing_ok=True)


# ──────────────────────────────────────────────────────────────
# Timing for engines without timestamps: pause-anchored alignment
# ──────────────────────────────────────────────────────────────
FRAME_MS = 10
MIN_GAP_MS = 130
_BREAK_PUNCT = ",;:.!?…—–"


def _frame_rms(pcm, frame_ms: int = FRAME_MS):
    import numpy as np
    import wb_video
    n = max(1, int(wb_video.SAMPLE_RATE * frame_ms / 1000))
    k = len(pcm) // n
    if k == 0:
        return np.zeros(0, np.float32)
    return np.sqrt((pcm[:k * n].reshape(k, n) ** 2).mean(axis=1))


def _voiced_mask(pcm):
    env = _frame_rms(pcm)
    if not len(env):
        return env > 0
    return env > max(0.003, float(env.max()) * 0.05)


def _voiced_intervals(pcm, min_gap_ms: int = MIN_GAP_MS) -> list[tuple[int, int]]:
    """Speech regions (ms), split only at silences >= min_gap_ms (short dips stay voiced)."""
    import numpy as np
    on = np.nonzero(_voiced_mask(pcm))[0]
    if on.size == 0:
        return []
    out, start, prev = [], int(on[0]), int(on[0])
    gap_frames = max(1, min_gap_ms // FRAME_MS)
    for f in on[1:]:
        f = int(f)
        if f - prev - 1 >= gap_frames:
            out.append((start * FRAME_MS, (prev + 1) * FRAME_MS))
            start = f
        prev = f
    out.append((start * FRAME_MS, (prev + 1) * FRAME_MS))
    return out


def _voiced_timeline(iv: list[tuple[int, int]]) -> tuple[list[int], float]:
    cum_v, t = [], 0
    for s, e in iv:
        cum_v.append(t)
        t += e - s
    return cum_v, float(t)


def _match_breaks(toks: list[str], w: list[float], iv: list[tuple[int, int]], cum_v: list[int],
                  total_v: float, beats: dict | None = None) -> list[tuple[int, int]]:
    """Match the punctuation of the text to the silences of the audio.

    Both are placed in *voiced time* (the timeline with the pauses cut out, where the
    speaking rate is nearly uniform); a monotonic DP pairs them.  Returns
    ``(token index, gap index)`` pairs - gap ``j`` is the silence before ``iv[j + 1]``."""
    gaps = [(float(cum_v[k]), float(iv[k][0] - iv[k - 1][1])) for k in range(1, len(iv))]
    W = sum(w) or 1.0
    cw = [0.0]
    for x in w:
        cw.append(cw[-1] + x)
    beats = beats or {}
    bounds = [(i, total_v * cw[i + 1] / W, 450.0 if toks[i].rstrip("\"'”’)]»")[-1:] in ".!?…" else 250.0)
              for i in range(len(toks) - 1) if _break_char(toks[i]) or i in beats]
    nb, ng = len(bounds), len(gaps)
    tol = max(700.0, 0.3 * total_v)
    inf = float("inf")
    dp = [[inf] * (ng + 1) for _ in range(nb + 1)]
    bk: list[list] = [[None] * (ng + 1) for _ in range(nb + 1)]
    dp[0][0] = 0.0
    for i in range(nb + 1):
        for j in range(ng + 1):
            if i == 0 and j == 0:
                continue
            best, how = inf, None
            if i and dp[i - 1][j] + bounds[i - 1][2] < best:
                best, how = dp[i - 1][j] + bounds[i - 1][2], "b"
            if j:
                c = dp[i][j - 1] + 150.0 + 0.8 * gaps[j - 1][1]
                if c < best:
                    best, how = c, "g"
            if i and j:
                d = abs(bounds[i - 1][1] - gaps[j - 1][0])
                if d <= tol and dp[i - 1][j - 1] + d < best:
                    best, how = dp[i - 1][j - 1] + d, "m"
            dp[i][j], bk[i][j] = best, how
    pairs: list[tuple[int, int]] = []
    i, j = nb, ng
    while i or j:
        how = bk[i][j]
        if how == "m":
            pairs.append((bounds[i - 1][0], j - 1))
            i, j = i - 1, j - 1
        elif how == "b":
            i -= 1
        else:
            j -= 1
    pairs.reverse()
    return pairs


def anchor_words(text: str, pcm, beats: dict | None = None) -> list[Word]:
    """Word timings for audio without timestamps.

    Silences in the audio are matched (monotonic DP) to the punctuation of the text in
    *voiced time* - the timeline with the pauses cut out, where speaking rate is nearly
    uniform - and tokens are spread by length over the voiced time between anchors, so
    no word is ever placed inside a pause.
    """
    toks = tokens(text)
    if not toks:
        return []
    iv = _voiced_intervals(pcm)
    if not iv:
        import wb_video
        return estimate_words(text, 0, len(pcm) * 1000 / wb_video.SAMPLE_RATE)
    cum_v, total_v = _voiced_timeline(iv)
    w = [_speech_weight(x) for x in toks]
    anchors = [(ti, float(cum_v[j + 1])) for ti, j in _match_breaks(toks, w, iv, cum_v, total_v, beats)]

    def wall(v: float, is_end: bool) -> float:
        for k, (s, e) in enumerate(iv):
            lo, hi = cum_v[k], cum_v[k] + (e - s)
            if (lo < v <= hi) if is_end else (lo <= v < hi):
                return s + (v - lo)
        return float(iv[-1][1]) if v >= total_v else float(iv[0][0])

    out: list[Word] = []
    runs, a, va = [], 0, 0.0
    for ti, vg in anchors:
        runs.append((a, ti + 1, va, vg))
        a, va = ti + 1, vg
    runs.append((a, len(toks), va, total_v))
    for r0, r1, v0, v1 in runs:
        rw = sum(w[r0:r1]) or 1.0
        v = v0
        for k in range(r0, r1):
            nv = v + (v1 - v0) * w[k] / rw
            s, e = wall(v, False), wall(nv, True)
            out.append(Word(toks[k], int(round(s)), int(round(max(s, e)))))
            v = nv
    return out


# ──────────────────────────────────────────────────────────────
# Pause shaping: the narrator's breaks, not the model's
# ──────────────────────────────────────────────────────────────
# A generative voice decides on its own how long to rest at each comma: in one sentence it
# runs through a comma, in the next it stops for longer than between two sentences, and now
# and then it hesitates in the middle of a phrase.  A presenter's breaks follow the text:
# light inside a phrase, a breath at a comma, an expectant beat at a colon.  So every
# silence inside a clip is matched to the punctuation and set to the length that punctuation
# calls for; silences the text does not explain are shortened.
PAUSE_TARGET_MS = {",": 170, ";": 280, ":": 300, "—": 260, "–": 260, "…": 380, ".": 450, "!": 450, "?": 480}
SHORT_PHRASE_WORDS = 2     # "thật ra," - a light touch
LONG_PHRASE_WORDS = 8      # a long run of words before the comma - a real breath
SHORT_COMMA_MS = 120
LONG_COMMA_MS = 230
HESITATION_MAX_MS = 140    # a silence the punctuation does not explain is kept at most this long
INSERT_MIN_MS = 250        # a break this long that the voice ran through is opened at a word boundary
EDGE_KEEP_MS = 25          # audio kept on each side of a resized silence (release / attack)


def _break_char(tok: str) -> str:
    c = tok.rstrip("\"'”’)]»")[-1:]
    return c if c and c in _BREAK_PUNCT else ""


def _align_syllables(toks: list[str], w: list[float], pcm) -> list[tuple[float, float]] | None:
    """Where each token boundary falls in the audio: ``[(gap start ms, gap end ms)]`` for the
    boundary after token ``i`` (start == end when the two tokens run together).

    Vietnamese is written one syllable per token, and a syllable is one stretch of voice, so
    the stretches of voice between the smallest silences are aligned to the tokens with a
    DP: a group of tokens to one stretch or one token to a few stretches, scored by length
    against the token weights, by how well long silences line up with punctuation, and by
    any silence that would fall inside a word.  Far more exact than spreading the text over
    the clip by proportion, which misplaces a beat by a word or two around short syllables."""
    import numpy as np
    import wb_video
    ch = _voiced_intervals(pcm, 20)
    T, C = len(toks), len(ch)
    if T < 2 or C == 0:
        return None
    d = [e - s for s, e in ch]
    unit = sum(d) / (sum(w) or 1.0)
    gap_after = [ch[c + 1][0] - ch[c][1] for c in range(C - 1)] + [0]
    punct = [bool(_break_char(t)) for t in toks]
    INF = float("inf")
    f = [[INF] * (C + 1) for _ in range(T + 1)]
    bk: list[list] = [[None] * (C + 1) for _ in range(T + 1)]
    f[0][0] = 0.0
    MAX_TOKS, MAX_CHUNKS = 14, 4        # tokens run together in one stretch / one token in a few
    for b in range(1, T + 1):
        for e in range(1, C + 1):
            best, arg = INF, None
            for a in range(max(0, b - MAX_TOKS), b):
                for c in range(max(0, e - MAX_CHUNKS), e):
                    if (b - a > 1 and e - c > 1) or f[a][c] == INF:
                        continue
                    E = unit * sum(w[a:b])
                    D = sum(d[c:e])
                    cost = 4.0 * math.log(max(D, 1.0) / max(E, 1.0)) ** 2
                    if e - c > 1:                                   # silence inside one word
                        cost += sum(gap_after[c:e - 1]) / 80.0
                    if b - a > 1:                                   # punctuation run through
                        cost += 1.5 * sum(punct[a:b - 1])
                    if e < C:                                       # the silence after this group
                        g = gap_after[e - 1]
                        cost += -min(g, 600) / 300.0 if punct[b - 1] else max(0.0, g - 150) / 150.0
                    v = f[a][c] + cost
                    if v < best:
                        best, arg = v, (a, c)
            f[b][e], bk[b][e] = best, arg
    if f[T][C] == INF:
        return None
    groups = []
    b, e = T, C
    while b:
        a, c = bk[b][e]
        groups.append((a, b, c, e))
        b, e = a, c
    groups.reverse()
    env = _frame_rms(pcm)
    out: list[tuple[float, float]] = []
    for a, b, c, e in groups:
        if b - a > 1:                                  # tokens sharing one stretch: split at the quietest frame
            s0, e0 = ch[c][0], ch[e - 1][1]
            tot = sum(w[a:b]) or 1.0
            acc = 0.0
            for k in range(a, b - 1):
                acc += w[k]
                guess = s0 + (e0 - s0) * acc / tot
                lo, hi = int((guess - 50) / FRAME_MS), int((guess + 50) / FRAME_MS) + 1
                lo, hi = max(lo, int(s0 / FRAME_MS) + 1), min(hi, int(e0 / FRAME_MS) - 1)
                at = guess if hi <= lo else (lo + int(np.argmin(env[lo:hi]))) * FRAME_MS + FRAME_MS / 2
                out.append((at, at))
        if b < T:
            out.append((float(ch[e - 1][1]), float(ch[e][0]) if e < C else float(ch[e - 1][1])))
    return out if len(out) == T - 1 else None


def pause_target_ms(toks: list[str], i: int, scale: float = 1.0) -> int | None:
    """How long a narrator rests after token ``i`` (None: no punctuation there)."""
    p = _break_char(toks[i])
    if p not in PAUSE_TARGET_MS:
        return None
    base = PAUSE_TARGET_MS[p]
    if p == ",":
        left = 1
        while i - left >= 0 and not _break_char(toks[i - left]):
            left += 1
        right = 0
        while i + 1 + right < len(toks):
            right += 1
            if _break_char(toks[i + right]):
                break
        if left <= SHORT_PHRASE_WORDS or right <= SHORT_PHRASE_WORDS:
            base = SHORT_COMMA_MS
        elif left >= LONG_PHRASE_WORDS:
            base = LONG_COMMA_MS
    return int(round(base * scale))


def shape_pauses(text: str, pcm, scale: float = 1.0, beats: dict | None = None):
    """Resize the silences inside one clip to the breaks its punctuation calls for.

    Every token boundary is located in the audio (:func:`_align_syllables`).  A boundary
    after punctuation gets :func:`pause_target_ms`; ``beats`` ({token index: ms}, from the
    delivery plan) set the rest after those tokens, punctuated or not, and are opened even
    where the voice ran straight on; a silence the text does not explain is shortened to
    ``HESITATION_MAX_MS``.  Speech itself is never touched."""
    import numpy as np
    import wb_video
    toks = tokens(text)
    if len(toks) < 2 or not len(pcm):
        return pcm
    sr = wb_video.SAMPLE_RATE
    beats = {int(k): int(v) for k, v in (beats or {}).items()}
    w = [_speech_weight(x) for x in toks]
    bounds = _align_syllables(toks, w, pcm)
    if bounds is None:
        return pcm
    edits: list[tuple[float, float, float]] = []          # (start ms, end ms, new length ms)
    for i, (a, b) in enumerate(bounds):
        want = int(round(beats[i] * scale)) if i in beats else pause_target_ms(toks, i, scale)
        if want is not None:
            if b - a > 1 or want >= INSERT_MIN_MS * scale or i in beats:
                edits.append((a, b, want))
        elif b - a > HESITATION_MAX_MS * scale:
            edits.append((a, b, HESITATION_MAX_MS * scale))
    if not edits:
        return pcm
    edits.sort()
    fade = max(1, int(0.004 * sr))
    out, cur = [], 0
    for a, b, new in edits:
        sa, sb = int(a * sr / 1000), int(b * sr / 1000)
        if sa < cur:
            continue
        old = sb - sa
        keep = min(int(EDGE_KEEP_MS * sr / 1000), old // 3, int(new * sr / 1000) // 2)
        left = np.array(pcm[cur:sa + keep], np.float32)
        if len(left) > fade:
            left[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
        out.append(left)
        out.append(np.zeros(max(0, int(new * sr / 1000) - 2 * keep), np.float32))
        right = np.array(pcm[sb - keep:sb], np.float32)
        if len(right) > fade:
            right[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
        out.append(right)
        cur = sb
    out.append(np.asarray(pcm[cur:], np.float32))
    return np.concatenate(out)


def stress_words(text: str, pcm, spans: list[tuple[int, int]], beats: dict | None = None):
    """Speak the stressed token spans a little slower (``vs.EMPH_RATE``), the way a presenter
    lands the word that matters.  Tempo only (WSOLA): the timbre and pitch stay the voice's."""
    import numpy as np
    import wb_video
    words = anchor_words(text, pcm, beats)
    if not words:
        return pcm
    sr = wb_video.SAMPLE_RATE
    out = np.asarray(pcm, np.float32)
    for a, b in sorted(spans, reverse=True):
        if not (0 <= a <= b < len(words)):
            continue
        s0 = max(0, int((words[a].startMs - 20) * sr / 1000))
        s1 = min(len(out), int((words[b].endMs + 30) * sr / 1000))
        if s1 - s0 < sr // 10:
            continue
        slow = wb_video.apply_prosody(out[s0:s1], vs.EMPH_RATE)
        out = np.concatenate([out[:s0], slow.astype(np.float32), out[s1:]])
    return out


# ──────────────────────────────────────────────────────────────
# Stitching sentence / block clips with exact planned pauses
# ──────────────────────────────────────────────────────────────
LEAD_KEEP_MS = 30        # audio kept before the first word
TAIL_KEEP_MS = 140       # audio kept after the last word (release)
MIN_TAIL_MS = 48
FINAL_TAIL_MS = 450


@dataclass
class Clip:
    pcm: object                     # mono float32 @ 48 kHz
    words: list[Word]               # aligned to the display text, relative to the clip start
    pause_before_ms: int


def stitch(clips: list[Clip], trailing_ms: int = 0):
    """Trim each clip to its speech and join them so the silence between one clip's last
    word and the next clip's first word is exactly its ``pause_before_ms``."""
    import numpy as np
    import wb_video
    sr = wb_video.SAMPLE_RATE
    parts, words, cursor = [], [], 0          # cursor in samples
    prev_end: float | None = None
    fade = int(0.006 * sr)
    for i, c in enumerate(clips):
        clip_ms = len(c.pcm) * 1000 / sr
        if not c.words:
            continue
        s_ms, e_ms = c.words[0].startMs, c.words[-1].endMs
        nxt = clips[i + 1].pause_before_ms if i + 1 < len(clips) else None
        tail = FINAL_TAIL_MS if nxt is None else max(MIN_TAIL_MS, min(TAIL_KEEP_MS, nxt - LEAD_KEEP_MS))
        a = max(0.0, s_ms - LEAD_KEEP_MS)
        b = min(clip_ms, e_ms + tail)
        seg = np.array(c.pcm[int(a * sr / 1000):int(b * sr / 1000)], np.float32)
        if len(seg) > 2 * fade:
            seg[:fade] *= np.linspace(0, 1, fade, dtype=np.float32)
            seg[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
        target = c.pause_before_ms if prev_end is None else prev_end + c.pause_before_ms
        gap = target - (cursor * 1000 / sr + (s_ms - a))
        if gap > 0:
            n = int(round(gap * sr / 1000))
            parts.append(np.zeros(n, np.float32))
            cursor += n
        t0 = cursor * 1000 / sr - a              # wall time of the clip's t=0
        words += [Word(w.text, int(round(w.startMs + t0)), int(round(w.endMs + t0))) for w in c.words]
        parts.append(seg)
        cursor += len(seg)
        prev_end = t0 + e_ms
    if trailing_ms > FINAL_TAIL_MS:
        n = int(round((trailing_ms - FINAL_TAIL_MS) * sr / 1000))
        parts.append(np.zeros(n, np.float32))
    pcm = np.concatenate(parts) if parts else np.zeros(0, np.float32)
    return pcm, words


def _group_blocks(segments: list, max_chars: int) -> list[list]:
    """Sentences joined into paragraph blocks (LLM voices keep intonation across them)."""
    blocks: list[list] = []
    for seg in segments:
        cur = blocks[-1] if blocks else None
        if (cur and not seg.manual_pause and seg.boundary in ("sentence", "clause")
                and sum(len(x.spoken) + 1 for x in cur) + len(seg.spoken) < max_chars):
            cur.append(seg)
        else:
            blocks.append([seg])
    return blocks


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


# One request per sentence: exact sentence boundaries + planned pauses (the timing of
# engines without timestamps then only has to be estimated inside one sentence).
SENTENCE_ENGINES = {"edge", "tiktok", "gemini", "vieneu"}
# engines without prosody controls: moods are applied to the audio (tempo/pitch/gain)
PROSODY_DSP_ENGINES = {"vieneu", "tiktok", "makevoice", "fish"}
# How much of a mood's tempo change is applied by DSP.  Small WSOLA changes are transparent;
# large ones start to sound processed.  Pitch is NOT shifted by DSP: resampling moves the
# formants too, so the narrator's timbre would change from sentence to sentence.  For these
# engines a mood is carried by tempo, loudness, crescendo and the pauses around the sentence.
DSP_TEMPO_SCALE = 0.6
PROSODY_VERSION = 4          # bump when mood planning / DSP changes (invalidates voice caches)
# engines whose own pauses are left to a generative model: their silences are reshaped
PAUSE_SHAPE_ENGINES = {"vieneu", "tiktok", "makevoice", "fish"}
BLOCK_CHARS = {"gemini": 1500, "openai": 1500, "makevoice": 1500, "fish": 1500, "vieneu": 600}
PARALLEL = {"edge": 4, "tiktok": 3, "gemini": 3, "openai": 3, "makevoice": 2, "fish": 2, "vieneu": 1}


def synthesize(text: str, out: str | Path, engine: str = "edge", voice: str | None = None,
               rate: str = "+0%", pitch: str = "+0Hz", volume: str = "+0%",
               instructions: str | None = None, language: str | None = "vi",
               style: str | None = None, pause_scale: float = 1.0, lexicon: dict | list | None = None,
               phrasing: bool = True, reference: str | None = None, reference_text: str | None = None,
               consent: bool = False, chunk: str | None = None, mood: str | None = None,
               expressiveness: float = 1.0, auto_mood: bool = True, pause_shaping: bool = True) -> TTSResult:
    """Speak ``text`` into ``out``.  ``style`` (natural/news/story/podcast/ads) turns on the
    Voice Studio: per-sentence prosody + planned pauses (edge/tiktok/vieneu) or a style
    direction (gemini/openai).  ``style=None`` or "plain" keeps a single request (edge/openai).
    ``chunk`` = "sentence" | "paragraph" overrides how the text is split into requests.

    Moods (content-aware delivery): each sentence gets a mood - from a ``[cao trào]``-style
    tag, the scene ``mood``, or read from its words (``auto_mood``) - that sets its tempo,
    pitch, loudness and the pauses around it, scaled by ``expressiveness`` (0 = flat).
    Edge plays them through SSML prosody; engines without prosody controls (vieneu, tiktok,
    makevoice, fish) get gentle per-sentence tempo (WSOLA), loudness and pause changes (no DSP
    pitch shift, which would alter the timbre); gemini/openai get a spoken direction per sentence.

    Foreign names: write them in their own spelling.  VieNeu's G2P detects English words and
    reads them in English; a Vietnamese respelling in ``lexicon`` forces a Vietnamese reading.

    ``pause_shaping``: for engines whose pauses come from a generative model (vieneu, tiktok,
    makevoice, fish) the silences inside each sentence are set by its punctuation
    (:func:`shape_pauses`) instead of whatever length the model chose."""
    import wb_video
    if engine not in ENGINES:
        raise ValueError(f"unknown TTS engine: {engine} (choose from {', '.join(ENGINES)})")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    voice = voice or DEFAULT_VOICES.get(engine, "")
    text = unicodedata.normalize("NFC", text.strip())
    display = vs.strip_pause_tags(text)
    if style == "plain":
        style = None
    if style is not None and style not in vs.STYLE_PRESETS:
        raise ValueError(f"unknown voice style: {style} (choose from {', '.join(vs.STYLES)})")
    if engine in ("fish", "vieneu") and reference and not consent:
        raise RuntimeError("Voice cloning needs the speaker's consent: set \"confirmAuthorizedVoice\": true "
                           "only after they agreed (tts.py --confirm-authorized-voice).")

    if engine == "silent":
        ms = estimate_speech_ms(display)
        out = out.with_suffix(".wav")
        wb_video.save_wav(out, wb_video.silence(ms + 200))
        return TTSResult(str(out), ms + 200, estimate_words(display, 100, 100 + ms), engine, voice)
    if engine == "elevenlabs" or (engine in ("edge", "openai") and style is None):
        if engine == "edge":
            spoken = _edge(display, out, voice, rate, pitch, volume)
        elif engine == "elevenlabs":
            spoken = _elevenlabs(display, out, voice, language)
        else:
            _openai(display, out, voice, instructions)
            spoken = []
        words = align_to_text(display, spoken) if spoken else anchor_words(display, wb_video.load_audio(out, stereo=False))
        return TTSResult(str(out), _speech_span(out)[2], words, engine, voice)

    if chunk not in (None, "sentence", "paragraph"):
        raise ValueError(f"chunk must be 'sentence' or 'paragraph', not {chunk!r}")
    per_sentence = engine in SENTENCE_ENGINES if chunk is None else chunk == "sentence"
    plan = vs.plan_script(text, style or "natural",
                          rate if engine == "edge" else 0, pitch if engine == "edge" else 0,
                          pause_scale, phrasing=phrasing and per_sentence, lexicon=lexicon,
                          lang=language if language in ("vi", "en") else None, mood=mood,
                          expressiveness=expressiveness, auto_mood=auto_mood)
    if not plan.segments:
        raise ValueError("no speakable text")
    if per_sentence:
        units = [[s] for s in plan.segments]
    else:
        units = _group_blocks(plan.segments, BLOCK_CHARS.get(engine, 1500))
    tmp = out.parent / f".{out.stem}.parts"
    tmp.mkdir(exist_ok=True)
    direct = instructions or vs.direction(plan.style, plan.lang)

    def render(k: int) -> Clip:
        segs = units[k]
        spoken = " ".join(s.spoken for s in segs)
        disp = " ".join(s.display for s in segs)
        part = tmp / f"{k:03d}"
        same = all(s.mood == segs[0].mood for s in segs)      # one feeling for the whole request
        s0 = segs[0]
        if engine == "edge":
            f = part.with_suffix(".mp3")
            sw = _edge(spoken, f, voice, vs.format_rate(s0.rate), vs.format_pitch(s0.pitch), volume)
            pcm = wb_video.load_audio(f, stereo=False)
            f.unlink(missing_ok=True)
            pcm = wb_video.apply_prosody(pcm, gain_db=s0.gain_db, ramp_db=s0.ramp_db)   # tempo/pitch: SSML
            words = align_to_text(disp, sw) if sw else anchor_words(disp, pcm)
            return Clip(pcm, words, s0.pause_before_ms)
        say = direct
        if same and s0.mood != "neutral" and s0.intensity >= 0.5:
            say = f"{direct} {vs.MOODS[s0.mood]['direction']}"
        if engine == "tiktok":
            import numpy as np
            chunks = vs.split_long_sentence(spoken, 280)       # the proxy takes <= 300 chars
            pcm = np.concatenate([_decode(_tiktok(c, voice), ".mp3", part.with_name(f"{k:03d}-{i}"))
                                  for i, c in enumerate(chunks)])
        elif engine == "gemini":
            pcm = _decode(_gemini(spoken, voice, say), ".wav", part)
        elif engine == "makevoice":
            pcm = _decode(_makevoice(spoken, voice, language), ".mp3", part)
        elif engine == "fish":
            pcm = _decode(_fish(spoken, voice, reference, reference_text), ".wav", part)
        elif engine == "vieneu":
            pcm = _vieneu(spoken, voice, reference, part)
        else:  # openai with a style: the style direction becomes the instructions
            f = part.with_suffix(".mp3")
            _openai(spoken, f, voice, say)
            pcm = wb_video.load_audio(f, stereo=False)
            f.unlink(missing_ok=True)
        if engine in PROSODY_DSP_ENGINES and same:
            pcm = wb_video.apply_prosody(pcm, s0.mood_rate * DSP_TEMPO_SCALE, 0.0, s0.gain_db, s0.ramp_db)
        beats: dict[int, int] = {}
        if pause_shaping and engine in PAUSE_SHAPE_ENGINES:
            stressed, off = [], 0
            for sg in segs:                    # the delivery plan, in display tokens of this request
                beats.update({off + int(k): int(v) for k, v in sg.breaks.items()})
                stressed += [(off + int(a), off + int(b)) for a, b in sg.emph]
                off += len(tokens(sg.display))
            if stressed:
                pcm = stress_words(disp, pcm, stressed, beats)
            pace = 1.0 + (vs.MOODS[s0.mood]["pace"] - 1.0) * s0.intensity * expressiveness if same else 1.0
            pcm = shape_pauses(disp, pcm, max(0.3, min(3.0, float(pause_scale))) * pace, beats)
        return Clip(pcm, anchor_words(disp, pcm, beats), s0.pause_before_ms)

    try:
        with ThreadPoolExecutor(max_workers=PARALLEL.get(engine, 2)) as ex:
            clips = list(ex.map(render, range(len(units))))
    finally:
        for f in tmp.glob("*"):
            f.unlink(missing_ok=True)
        tmp.rmdir()
    pcm, words = stitch(clips, plan.trailing_pause_ms)
    out = out.with_suffix(".wav")
    wb_video.save_wav(out, pcm)
    return TTSResult(str(out), int(round(len(pcm) * 1000 / wb_video.SAMPLE_RATE)), words, engine, voice)


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
    p.add_argument("--engine", default="edge", choices=ENGINES)
    p.add_argument("--voice", default=None)
    p.add_argument("--style", default=None, choices=vs.STYLES + ["plain"],
                   help="Voice Studio style (expressive per-sentence prosody / LLM direction)")
    p.add_argument("--rate", default="+0%")
    p.add_argument("--pitch", default="+0Hz")
    p.add_argument("--pause-scale", type=float, default=1.0)
    p.add_argument("--instructions", default=None, help="openai/gemini: custom speaking direction")
    p.add_argument("--reference", default=None, help="fish: reference clip to clone (needs consent)")
    p.add_argument("--reference-text", default=None, help="fish: transcript of the reference clip")
    p.add_argument("--confirm-authorized-voice", action="store_true",
                   help="fish: the speaker of --reference consented to this voice clone")
    p.add_argument("--srt", default=None)
    p.add_argument("--words", default=None)
    p.add_argument("--chunk", default=None, choices=["sentence", "paragraph"])
    p.add_argument("--mood", default=None, help="default mood: " + ", ".join(vs.MOODS))
    p.add_argument("--expressiveness", type=float, default=1.0, help="0 = flat, 1 = default, 2 = strong")
    p.add_argument("--no-auto-mood", action="store_true", help="only [mood] tags / --mood, no automatic reading")
    p.add_argument("--list-voices", default=None, metavar="LOCALE_PREFIX",
                   help="edge voices for a locale; 'vieneu' lists the VieNeu presets")
    a = p.parse_args(argv)
    if a.list_voices is not None:
        voices = vieneu_voices() if a.list_voices == "vieneu" else list_voices(a.list_voices)
        print(json.dumps(voices, ensure_ascii=False, indent=2))
        return 0
    if not a.text or not a.out:
        p.error("text and out are required")
    text = Path(a.text[1:]).read_text(encoding="utf-8") if a.text.startswith("@") else a.text
    r = synthesize(text, a.out, a.engine, a.voice, a.rate, a.pitch, instructions=a.instructions,
                   style=a.style, pause_scale=a.pause_scale, reference=a.reference,
                   reference_text=a.reference_text, consent=a.confirm_authorized_voice, chunk=a.chunk,
                   mood=a.mood, expressiveness=a.expressiveness, auto_mood=not a.no_auto_mood)
    if a.srt:
        Path(a.srt).write_text(words_to_srt(r.words), encoding="utf-8")
    if a.words:
        Path(a.words).write_text(json.dumps(r.to_json(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(r.words)} words, {r.durationMs} ms")
    print(f"OUTPUT={Path(r.audio).resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
