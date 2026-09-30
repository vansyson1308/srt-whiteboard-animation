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
    plan = vs.plan_script(text, "story", rate="+4%", auto_mood=False)     # the style layer alone
    segs = plan.segments
    assert [s.type for s in segs] == ["question", "exclamation", "question", "statement"]
    assert [s.boundary for s in segs] == ["start", "sentence", "paragraph", "sentence"]
    story = vs.STYLE_PRESETS["story"]
    assert segs[1].pause_before_ms == story["pauses"]["afterQuestion"]      # after a question
    assert segs[2].pause_before_ms == story["pauses"]["paragraph"]
    assert segs[3].pause_before_ms == 1500 and segs[3].manual_pause          # [pause 1.5s] is exact
    # style rate -8 + user +4, question tweak -1, paragraph start 0
    assert segs[0].rate == -8 + 4 - 1 and segs[0].pitch == 0 + 3 + 1
    ads = vs.plan_script(text, "ads", auto_mood=False)
    assert ads.segments[1].pause_before_ms < segs[1].pause_before_ms       # punchier pacing
    assert vs.strip_pause_tags(text).endswith("Vậy tại sao? Hãy cùng xem.")


def test_moods_from_tags_scene_and_words():
    text = ("Năm 1923, nước Đức in tiền không ngừng. Giá bánh mì lên tới hàng nghìn tỷ mark! "
            "Người mẹ già ngồi khóc. Bà ngồi đó. [nhanh] Rồi đến Hungary, Zimbabwe, Venezuela.")
    segs = vs.plan_script(text, "natural").segments
    assert [s.mood for s in segs] == ["neutral", "climax", "emotional", "emotional", "fast"]
    assert segs[3].intensity < segs[2].intensity                     # the feeling lingers, weaker
    assert segs[1].rate > segs[0].rate and segs[1].pitch > segs[0].pitch and segs[1].gain_db > 0
    assert segs[2].rate < segs[0].rate and segs[2].mood_st < 0 and segs[2].gain_db < 0
    assert segs[2].pause_before_ms > segs[1].pause_before_ms > 400    # room around big moments
    assert vs.strip_pause_tags(text).count("[") == 0 and segs[4].display.startswith("Rồi đến Hungary")
    flat = vs.plan_script(text, "natural", expressiveness=0).segments
    assert all(s.mood_rate == 0 and s.gain_db == 0 for s in flat)
    assert all(s.mood == "emotional" for s in vs.plan_script(text, "natural", mood="xúc động").segments[:3])
    assert vs.plan_script("[Cao trào] Xong rồi.", "natural").segments[0].mood == "climax"
    assert vs.detect_mood("Lạm phát là khi giá cả tăng.") == ("neutral", 0.0)


def test_apply_prosody_changes_tempo_and_pitch():
    import wb_video as wv
    sr = wv.SAMPLE_RATE
    t = np.arange(sr) / sr
    x = sum(np.sin(2 * np.pi * 150 * k * t) / k for k in range(1, 10)).astype(np.float32) * 0.2

    def f0(y):
        seg = y[sr // 4:sr // 4 + 4096].astype(np.float64)
        ac = np.correlate(seg, seg, "full")[len(seg) - 1:]
        return sr / (sr // 400 + np.argmax(ac[sr // 400:sr // 60]))
    slow = wv.apply_prosody(x, rate_pct=-12)
    assert abs(len(slow) - len(x) / 0.88) < 2 and abs(f0(slow) - 150) < 4        # longer, same pitch
    up = wv.apply_prosody(x, semitones=2)
    assert abs(len(up) - len(x)) < 2 and abs(f0(up) - 150 * 2 ** (2 / 12)) < 4   # same length, higher
    loud = wv.apply_prosody(x, gain_db=6, ramp_db=4)
    assert np.abs(loud[-sr // 10:]).max() > np.abs(loud[:sr // 10]).max() * 1.4    # crescendo


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


def test_vieneu_engine_per_sentence_and_consent(monkeypatch, tmp_path):
    calls = []

    def fake_vieneu(text, voice, reference, tmp):
        calls.append((text, voice, reference))
        n = len(text.split())
        return speech([(60, 60 + 260 * n)], 200 + 260 * n)

    monkeypatch.setattr(tts, "_vieneu", fake_vieneu)
    r = tts.synthesize("Lạm phát là gì? Nó lấy đi sức mua của tiền.", tmp_path / "v.mp3", "vieneu",
                       style="news", auto_mood=False)
    assert [c[1] for c in calls] == ["Hải Đăng", "Hải Đăng"]               # default voice, per sentence
    assert r.audio.endswith(".wav") and len(r.words) == 11
    gap = r.words[4].startMs - r.words[3].endMs
    assert abs(gap - vs.STYLE_PRESETS["news"]["pauses"]["afterQuestion"]) <= 40
    ref = tmp_path / "ref.wav"
    ref.write_bytes(wav_bytes(speech([(0, 500)], 600)))
    with pytest.raises(RuntimeError, match="consent"):
        tts.synthesize("Xin chào.", tmp_path / "c.mp3", "vieneu", reference=str(ref))


def test_vieneu_moods_retime_the_audio(monkeypatch, tmp_path):
    monkeypatch.setattr(tts, "_vieneu", lambda text, voice, reference, tmp:
                        speech([(60, 60 + 260 * len(text.split()))], 200 + 260 * len(text.split())))
    text = "Nước Đức in tiền mỗi ngày. Người mẹ già ngồi khóc mãi."
    span = lambda ws: ws[-1].endMs - ws[0].startMs  # noqa: E731
    r = tts.synthesize(text, tmp_path / "m.mp3", "vieneu", style="natural")
    assert span(r.words[6:]) > 1.1 * span(r.words[:6])               # the sad line is read slower
    flat = tts.synthesize(text, tmp_path / "f.mp3", "vieneu", style="natural", expressiveness=0)
    assert abs(span(flat.words[6:]) - span(flat.words[:6])) < 60


def test_chunk_override_groups_sentences(monkeypatch, tmp_path):
    texts = []

    def fake_gemini(text, voice, direction):
        texts.append(text)
        return wav_bytes(speech([(100, 900), (1200, 2000)], 2200))

    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setattr(tts, "_gemini", fake_gemini)
    tts.synthesize("Câu một. Câu hai.", tmp_path / "a.mp3", "gemini")
    assert texts == ["Câu một.", "Câu hai."]                               # sentence by default
    texts.clear()
    tts.synthesize("Câu một. Câu hai.", tmp_path / "b.mp3", "gemini", chunk="paragraph")
    assert texts == ["Câu một. Câu hai."]
    with pytest.raises(ValueError, match="chunk"):
        tts.synthesize("x", tmp_path / "c.mp3", "gemini", chunk="word")


def test_elevenlabs_falls_back_to_older_models(monkeypatch, tmp_path):
    import base64
    import json
    tried = []

    def fake_post(url, payload, headers, what=""):
        tried.append(payload["model_id"])
        if payload["model_id"] != "eleven_flash_v2_5":
            raise RuntimeError(f"{what}: HTTP 400 model not found")
        return json.dumps({"audio_base64": base64.b64encode(wav_bytes(speech([(50, 700)], 900))).decode(),
                           "alignment": {"characters": list("Xin chào"),
                                         "character_start_times_seconds": [i * 0.08 for i in range(8)],
                                         "character_end_times_seconds": [i * 0.08 + 0.08 for i in range(8)]}
                           }).encode()

    monkeypatch.setenv("ELEVENLABS_API_KEY", "test")
    monkeypatch.setattr(tts, "_post_json", fake_post)
    monkeypatch.setattr(tts, "ELEVENLABS_MODELS", ["eleven_v4", "eleven_v3", "eleven_flash_v2_5"])
    r = tts.synthesize("Xin chào", tmp_path / "e.mp3", "elevenlabs")
    assert tried == ["eleven_v4", "eleven_v3", "eleven_flash_v2_5"]
    assert r.voice == "FTYCiQT21H9XQvhRu0ch" and [w.text for w in r.words] == ["Xin", "chào"]

    def denied(url, payload, headers, what=""):
        tried.append(payload["model_id"])
        raise RuntimeError(f"{what}: HTTP 401 invalid api key")
    tried.clear()
    monkeypatch.setattr(tts, "_post_json", denied)
    with pytest.raises(RuntimeError, match="401"):
        tts.synthesize("Xin chào", tmp_path / "f.mp3", "elevenlabs")
    assert tried == ["eleven_v4"]                                         # auth errors don't retry


def test_vieneu_retries_implausible_takes(monkeypatch, tmp_path):
    takes = iter([speech([(0, 9000)], 9500),            # babbling: 9 s for four syllables
                  speech([(50, 1000)], 1200)])          # plausible
    calls = []

    class FakeTTS:
        sample_rate = SR

        def resolve_voice_name(self, v):
            return v

        def get_preset_voice(self, v):
            return {"name": v}

        def infer(self, text, voice=None, ref_audio=None):
            calls.append(text)
            return next(takes)

    monkeypatch.setattr(tts, "_vieneu_model", lambda: FakeTTS())
    pcm = tts._vieneu("Xin chào các bạn.", "Hải Đăng", None, tmp_path / "t")
    assert len(calls) == 2 and len(pcm) < 2 * SR
    assert 0.55 <= tts.plausible_speech("Xin chào các bạn.", pcm) <= 1.8


def test_polish_voice_keeps_level_and_cuts_rumble():
    t = np.arange(SR * 2) / SR
    voice = 0.2 * np.sin(2 * np.pi * 220 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 3 * t) ** 2)
    rumble = 0.2 * np.sin(2 * np.pi * 30 * t)
    x = (voice + rumble).astype(np.float32)
    y = wb_video.polish_voice(np.stack([x, x], axis=1))
    assert y.shape == (len(x), 2) and np.max(np.abs(y)) <= 0.99
    assert abs(np.sqrt(np.mean(y ** 2)) - np.sqrt(np.mean(x ** 2))) < 1e-3   # same RMS

    def band(a, f0):
        spec = np.abs(np.fft.rfft(a))
        f = np.fft.rfftfreq(len(a), 1 / SR)
        return spec[(f > f0 - 5) & (f < f0 + 5)].sum()
    assert band(y[:, 0], 30) / band(y[:, 0], 220) < 0.3 * band(x, 30) / band(x, 220)
    assert wb_video.polish_voice(x, "none") is x


def test_unavailable_engine_falls_back_to_edge(monkeypatch, tmp_path):
    seen = {}

    def fake_synth(text, out, engine, voice, *a, **kw):
        seen["engine"], seen["voice"] = engine, voice
        f = Path(out).with_suffix(".wav")
        wb_video.save_wav(f, speech([(0, 500)], 600))
        return tts.TTSResult(str(f), 600, [tts.Word("Xin", 0, 200), tts.Word("chào.", 200, 500)], engine, voice)

    monkeypatch.setattr(tts, "engine_available", lambda e: e != "vieneu")
    monkeypatch.setattr(tts, "synthesize", fake_synth)
    v = make_video.tts_scene({"id": "s1", "narration": "Xin chào."}, dict(make_video.DEFAULTS["voice"]),
                             tmp_path, 200, None, tmp_path)
    assert seen == {"engine": "edge", "voice": "vi-VN-NamMinhNeural"}
    assert v.words[0].startMs == 200
