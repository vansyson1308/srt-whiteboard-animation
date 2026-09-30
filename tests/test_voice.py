"""Voice Studio (ttspromax port): planner, pause-anchored timing, stitching, engines (offline)."""
from __future__ import annotations

import io
import sys
import wave
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import make_video  # noqa: E402
import tts  # noqa: E402
import voice_studio as vs  # noqa: E402
import wb_video  # noqa: E402

SR = wb_video.SAMPLE_RATE


def speech(segments: list[tuple[float, float]], total_ms: float) -> np.ndarray:
    """Fake speech: a buzzy tone inside each (start_ms, end_ms), silence elsewhere."""
    a = np.zeros(int(total_ms * SR / 1000), np.float32)
    for s, e in segments:
        i, j = int(s * SR / 1000), int(e * SR / 1000)
        t = np.arange(j - i) / SR
        a[i:j] = 0.3 * np.sin(2 * np.pi * 180 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 5 * t) ** 2)
    return a


def wav_bytes(a: np.ndarray, rate: int = SR) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype("<i2").tobytes())
    return buf.getvalue()


def test_plan_styles_pauses_and_sentence_types():
    text = "Gập giấy 42 lần thì sao? Nó dày tới Mặt Trăng!\n\nVậy tại sao? [pause 1.5s] Hãy cùng xem."
    plan = vs.plan_script(text, "story", rate="+4%")
    segs = plan.segments
    assert [s.type for s in segs] == ["question", "exclamation", "question", "statement"]
    assert [s.boundary for s in segs] == ["start", "sentence", "paragraph", "sentence"]
    story = vs.STYLE_PRESETS["story"]
    assert segs[1].pause_before_ms == story["pauses"]["afterQuestion"]      # after a question
    assert segs[2].pause_before_ms == story["pauses"]["paragraph"]
    assert segs[3].pause_before_ms == 1500 and segs[3].manual_pause          # [pause 1.5s] is exact
    # style rate -8 + user +4, question tweak -1, paragraph start 0
    assert segs[0].rate == -8 + 4 - 1 and segs[0].pitch == 0 + 3 + 1
    ads = vs.plan_script(text, "ads")
    assert ads.segments[1].pause_before_ms < segs[1].pause_before_ms       # punchier pacing
    assert vs.strip_pause_tags(text).endswith("Vậy tại sao? Hãy cùng xem.")


def test_segmenter_keeps_abbreviations_and_splits_long():
    assert vs.split_sentences("Theo GS. Minh, đó là thật. Còn bạn?") == ["Theo GS. Minh, đó là thật.", "Còn bạn?"]
    assert vs.split_sentences("Uống vitamin C. Rồi ngủ.") == ["Uống vitamin C.", "Rồi ngủ."]
    long = ", ".join(["một câu rất dài có nhiều vế"] * 30) + "."
    parts = vs.split_long_sentence(long, 120)
    assert all(len(p) <= 120 for p in parts) and " ".join(parts) == long


def test_breath_commas_and_lexicon():
    s = "Nghe thì vô lý nhưng toán học không nói dối trong khi trực giác của chúng ta thường xuyên đánh lừa ta"
    out = vs.insert_phrase_breaks(s)
    assert ", trong khi" in out and ", nhưng" not in out                   # only after a long clause
    lex = vs.lexicon_entries({"GPT": "gi pi ti"})
    assert vs.apply_lexicon("GPT và AI ở TP.HCM", lex) == "gi pi ti và ây ai ở Thành phố Hồ Chí Minh"
    assert vs.apply_lexicon("HTTP không đổi", lex) == "HTTP không đổi"      # whole tokens only


def test_anchor_words_snaps_to_pauses():
    text = "Một hai ba bốn, năm sáu bảy tám chín mười. Mười một mười hai!"
    # three phrases separated by silences; the phrase lengths deliberately differ from
    # what the text proportions would predict
    a = speech([(100, 1500), (1900, 4300), (4900, 5500)], 6000)
    words = tts.anchor_words(text, a)
    assert [w.text for w in words] == tts.tokens(text)
    by = {w.text: w for w in words}
    assert abs(by["bốn,"].endMs - 1500) <= 30 and abs(by["năm"].startMs - 1900) <= 30
    assert abs(by["mười."].endMs - 4300) <= 30 and abs(words[-4].startMs - 4900) <= 30
    assert all(b.startMs >= a_.endMs for a_, b in zip(words, words[1:]))  # monotonic
    for w in words:                                                        # never inside a pause
        assert not (1500 < w.startMs < 1900 or 4300 < w.startMs < 4900)


def test_number_weight_reflects_spoken_length():
    assert tts._speech_weight("1969") > 3 * tts._speech_weight("con")


def test_stitch_makes_exact_gaps():
    c1 = tts.Clip(speech([(100, 900)], 1600), [tts.Word("A", 100, 500), tts.Word("B.", 500, 900)], 0)
    c2 = tts.Clip(speech([(120, 700)], 1500), [tts.Word("C", 120, 700)], 650)
    pcm, words = tts.stitch([c1, c2])
    assert [w.text for w in words] == ["A", "B.", "C"]
    assert abs(words[2].startMs - words[1].endMs - 650) <= 1
    iv = tts._voiced_intervals(pcm)
    assert len(iv) == 2 and abs((iv[1][0] - iv[0][1]) - 650) <= 20
    assert abs(iv[1][0] - words[2].startMs) <= 20


def test_expressive_edge_per_sentence(monkeypatch, tmp_path):
    calls = []

    def fake_edge(text, out, voice, rate, pitch, volume):
        calls.append((text, rate, pitch))
        n = len(text.split())
        Path(out).write_bytes(wav_bytes(speech([(100, 100 + 250 * n)], 400 + 250 * n)))
        return [tts.Word(t, 100 + 250 * i, 330 + 250 * i) for i, t in enumerate(text.split())]

    monkeypatch.setattr(tts, "_edge", fake_edge)
    r = tts.synthesize("Bạn có biết không? Giấy rất mỏng. [pause 2s] Nhưng mà!", tmp_path / "v.mp3",
                       "edge", style="podcast", rate="+10%")
    assert len(calls) == 3 and calls[0][1] == "+12%" and calls[0][2] == "+4Hz"   # 2+10, question tweaks
    assert r.audio.endswith(".wav") and Path(r.audio).exists()
    assert [w.text for w in r.words] == tts.tokens("Bạn có biết không? Giấy rất mỏng. Nhưng mà!")
    gaps = [b.startMs - a.endMs for a, b in zip(r.words, r.words[1:]) if b.startMs - a.endMs > 50]
    assert np.allclose(gaps, [vs.STYLE_PRESETS["podcast"]["pauses"]["afterQuestion"], 2000], atol=1)


def test_gemini_engine_mocked(monkeypatch, tmp_path):
    seen = {}

    def fake_post(url, payload, headers, what=""):
        seen["url"], seen["payload"] = url, payload
        import base64
        import json
        audio = speech([(200, 1400), (1800, 2600)], 3000)
        pcm = (audio[::2] * 32767).astype("<i2").tobytes()       # raw 24 kHz L16, like the API
        return json.dumps({"outputs": [{"type": "audio", "mime_type": "audio/L16;rate=24000",
                                        "data": base64.b64encode(pcm).decode()}]}).encode()

    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setattr(tts, "_post_json", fake_post)
    r = tts.synthesize("Tờ giấy mỏng lắm, chỉ một phần mười milimét.", tmp_path / "g.mp3",
                       "gemini", voice="Charon", style="news")
    style = seen["payload"]["input"][0]["content"][0]["annotations"][0]["style"]
    assert "news anchor" in style and "Vietnamese" in style
    assert seen["payload"]["generation_config"]["speech_config"][0]["voice"] == "Charon"
    assert "interactions" in seen["url"]
    by = {w.text: w for w in r.words}
    assert abs(by["lắm,"].endMs - by["chỉ"].startMs) >= 300                  # the pause was found


def test_tiktok_and_makevoice_mocked(monkeypatch, tmp_path):
    import base64
    import json
    reqs = []

    def fake_request(url, data, headers, what, attempts=4):
        body = json.loads(data)
        reqs.append((url, body))
        if "makevoice" in url:
            return wav_bytes(speech([(100, 1200)], 1500)), "audio/wav"
        return json.dumps({"success": True, "data": base64.b64encode(wav_bytes(speech([(80, 900)], 1100))).decode()}
                          ).encode(), "application/json"

    monkeypatch.setattr(tts, "_request", fake_request)
    decode = tts._decode
    monkeypatch.setattr(tts, "_decode", lambda data, suffix, tmp: decode(data, ".wav", tmp))
    r = tts.synthesize("Xin chào! Mình là Vi.", tmp_path / "t.mp3", "tiktok")
    assert [b["voice"] for _, b in reqs] == ["BV074_streaming"] * 2       # one request per sentence
    assert [w.text for w in r.words] == ["Xin", "chào!", "Mình", "là", "Vi."]
    reqs.clear()
    r = tts.synthesize("Xin chào! Mình là Adam.", tmp_path / "m.mp3", "makevoice")
    assert len(reqs) == 1 and reqs[0][1]["model"] == "eleven_turbo_v2_5"  # one block, context kept
    assert len(r.words) == 5


def test_fish_cloning_requires_consent(tmp_path):
    ref = tmp_path / "ref.wav"
    ref.write_bytes(wav_bytes(speech([(0, 500)], 600)))
    with pytest.raises(RuntimeError, match="consent"):
        tts.synthesize("Xin chào.", tmp_path / "f.mp3", "fish", reference=str(ref), reference_text="xin chào")


def test_scene_voice_overrides(tmp_path):
    base = {"engine": "edge", "voice": "vi-VN-HoaiMyNeural", "style": "natural"}
    cfg = make_video.scene_voice_cfg({"voice": {"style": "ads"}}, base, tmp_path)
    assert cfg["style"] == "ads" and cfg["voice"] == "vi-VN-HoaiMyNeural"
    cfg = make_video.scene_voice_cfg({"voice": {"engine": "tiktok"}}, base, tmp_path)
    assert cfg["engine"] == "tiktok" and cfg["voice"] is None
    with pytest.raises(ValueError, match="style"):
        tts.synthesize("x", tmp_path / "x.mp3", "edge", style="opera")
