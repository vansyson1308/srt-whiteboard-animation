"""Test suite: run with  <ENV_PY> -m pytest -q  (offline; uses the silent TTS engine)."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import auto_annotate  # noqa: E402
import parse_srt  # noqa: E402
import svg_scene  # noqa: E402
import timing  # noqa: E402
import tts  # noqa: E402
import wb_video  # noqa: E402
from render_stream_whiteboard import RenderOptions, SceneRenderer, build_pen_plan, render_scene  # noqa: E402

EXAMPLES = ROOT / "examples"
MONKEY_PNG = EXAMPLES / "scene-01-monkey-mountain-banana.png"
MONKEY_ANN = EXAMPLES / "scene-01-monkey-mountain-banana.annotation.json"
DEMO = EXAMPLES / "demo-bau-troi"
W = tts.Word


# ── SRT / text ───────────────────────────────────────────────
def test_parse_srt_and_grouping():
    srt = "﻿1\n00:00:00,000 --> 00:00:04,000\nMột\n\n2\n00:00:04.500 --> 00:00:31,000\nHai\nba\n\n" \
          "3\n00:00:31,000 --> 00:00:40,000\nBốn\n"
    cues = parse_srt.parse_srt(srt)
    assert [c["text"] for c in cues] == ["Một", "Hai ba", "Bốn"]
    assert cues[1]["startMs"] == 4500
    scenes = parse_srt.group_scenes(cues, 30, 25, 35)
    assert scenes[0]["cueRange"] == [1, 2] and scenes[1]["cueRange"] == [3, 3]


def test_align_handles_merged_and_split_words():
    spoken = [W("Bạn", 100, 400), W("biết", 400, 700), W("năm 2024", 900, 2600), W("có", 2600, 2750),
              W("365", 2750, 3000), W("25", 3000, 3300), W("ngày", 3300, 3600)]
    out = tts.align_to_text("Bạn biết, năm 2024 có 365,25 ngày.", spoken)
    assert [w.text for w in out] == ["Bạn", "biết,", "năm", "2024", "có", "365,25", "ngày."]
    assert out[2].startMs == 900 and out[3].endMs == 2600       # merged word split
    assert out[5].startMs == 2750 and out[5].endMs == 3300      # split word merged
    assert all(a.startMs <= b.startMs for a, b in zip(out, out[1:]))


def test_estimate_and_srt():
    ws = tts.estimate_words("Xin chào. Đây là một câu thử.", 0, 3000)
    assert ws[0].startMs == 0 and ws[-1].endMs <= 3000
    srt = tts.words_to_srt(ws)
    assert "00:00:00,000 -->" in srt and "Xin chào." in srt


# ── timing ───────────────────────────────────────────────────
def _words(text: str, step: int = 300) -> list:
    return [W(t, i * step, i * step + step - 50) for i, t in enumerate(text.split())]


def test_schedule_follows_say_phrases():
    words = _words("Đầu tiên là mặt trời. Sau đó có đám mây trôi. Cuối cùng một người đứng nhìn lên trời.")
    els = [{"sequence": 1, "say": "mặt trời"}, {"sequence": 2, "say": "đám mây"}, {"sequence": 3, "say": "người"}]
    total = timing.schedule(els, words, words[-1].endMs, timing.SyncOptions(first_start_ms=None))
    starts = [e["reveal"]["startMs"] for e in els]
    assert starts == sorted(starts)
    assert abs(starts[1] - (words[8].startMs - 250)) <= 1          # "đám" is word 8
    assert total >= words[-1].endMs
    assert all(900 <= e["reveal"]["durationMs"] <= 4500 for e in els)


def test_schedule_hook_starts_immediately():
    words = _words("Một hai ba bốn năm sáu bảy tám chín mười")
    els = [{"sequence": 1, "say": "năm"}, {"sequence": 2}]
    timing.schedule(els, words, words[-1].endMs)
    assert els[0]["reveal"]["startMs"] <= 150


def test_find_phrase_fuzzy():
    words = _words("hiện tượng tán xạ Rayleigh rất thú vị")
    assert timing.find_phrase(words, "tán xạ Rayleigh") == 2
    assert timing.find_phrase(words, "tan xa rayleig") == 2


# ── renderer ─────────────────────────────────────────────────
def test_pen_plan_travel_is_not_drawn():
    a = np.array([[0, 0], [10, 0]], np.float32)
    b = np.array([[100, 0], [110, 0]], np.float32)
    pts, draw, rad = build_pen_plan([a, b], spacing=2.0, travel_speed=3.0, radii=[3, 5])
    assert len(pts) == len(draw) == len(rad)
    assert draw[1] and not draw[2]                  # travel samples after the first stroke
    assert rad[-1] == 5 and rad[0] == 3


class _ListSink:
    def __init__(self):
        self.frames = []

    def write(self, f):
        self.frames.append(f.copy())


def test_render_exact_frames_and_mask_invariant():
    import cv2
    img = cv2.imread(str(MONKEY_PNG))
    ann = json.loads(MONKEY_ANN.read_text(encoding="utf-8"))
    opts = RenderOptions(width=480, height=270, fps=10, camera="none", verbose=False)
    r = SceneRenderer(img, ann, opts, bare_tip=True)
    sink = _ListSink()
    n = r.render(sink, total_ms=8600)
    assert n == len(sink.frames) == 86
    paper = r.paper.astype(int)
    # first frame: clean paper, nothing leaked
    assert np.abs(sink.frames[0].astype(int) - paper).max() <= 2
    # while element 1 draws, the last element's region is still blank paper
    last = ann["elements"][-1]
    x0, y0, x1, y1 = r._rect(last["region"])
    mid = sink.frames[int(1.5 * opts.fps)]
    assert np.abs(mid[y0:y1, x0:x1].astype(int) - paper).max() <= 2
    # last frame: full picture
    assert np.abs(sink.frames[-1].astype(int) - r.color[:270, :480].astype(int)).mean() < 1.0


def test_render_scene_writes_video(tmp_path):
    out = tmp_path / "s.mp4"
    act = tmp_path / "s.activity.json"
    opts = RenderOptions(width=320, height=180, fps=10, verbose=False, preset="ultrafast")
    render_scene(MONKEY_PNG, MONKEY_ANN, out, opts, total_ms=3000, activity_path=act)
    info = wb_video.probe_video(out)
    assert (info["width"], info["height"], info["frames"]) == (320, 180, 30)
    assert len(json.loads(act.read_text())["activity"]) == 30


# ── scene builders ───────────────────────────────────────────
def test_auto_annotate_finds_objects():
    ann = auto_annotate.annotate(MONKEY_PNG, k=4)
    assert len(ann["elements"]) == 4
    xs = [e["region"]["x"] for e in ann["elements"]]
    assert xs == sorted(xs)                          # reading order, left to right here
    assert ann["canvas"] == {"width": 1672, "height": 941}


def test_svg_scene_builds_strokes_and_masks(tmp_path):
    png, annp = svg_scene.build(DEMO / "scenes" / "scene-01.svg", tmp_path, width=960)
    ann = json.loads(annp.read_text(encoding="utf-8"))
    assert ann["canvas"] == {"width": 960, "height": 540}
    assert [e["id"] for e in ann["elements"]] == ["title", "sun", "sky", "person"]
    assert ann["elements"][1]["say"] == "mặt trời"
    title = ann["elements"][0]
    assert title["strokes"][0]["width"] > 20        # text is hand-written first...
    assert title["strokes"][1]["width"] < 10        # ...then the underline
    for e in ann["elements"]:
        for s in e["strokes"]:
            p = np.asarray(s["points"])
            assert p[:, 0].min() >= -5 and p[:, 0].max() <= 965 and p[:, 1].max() <= 545
    import cv2
    labels = cv2.imread(str(tmp_path / ann["maskFile"]), cv2.IMREAD_GRAYSCALE)
    assert set(np.unique(labels)) >= {0, 1, 2, 3, 4}


# ── audio ────────────────────────────────────────────────────
def test_loudness_and_normalize():
    t = np.arange(wb_video.SAMPLE_RATE * 2) / wb_video.SAMPLE_RATE
    a = (0.1 * np.sin(2 * np.pi * 1000 * t)).astype(np.float32)
    st = np.stack([a, a], 1)
    assert abs(wb_video.loudness_lufs(st) - (-20.0)) < 0.3
    assert abs(wb_video.loudness_lufs(wb_video.normalize_loudness(st, -14)) - (-14.0)) < 0.3


# ── end to end ───────────────────────────────────────────────
@pytest.fixture()
def demo_copy(tmp_path):
    d = tmp_path / "demo"
    shutil.copytree(DEMO, d, ignore=shutil.ignore_patterns("build", "out"))
    return d


def test_make_video_end_to_end_silent(demo_copy):
    import make_video
    proj = json.loads((demo_copy / "video.json").read_text(encoding="utf-8"))
    proj["scenes"] = proj["scenes"][:2]
    (demo_copy / "video.json").write_text(json.dumps(proj, ensure_ascii=False), encoding="utf-8")
    rep = make_video.run(demo_copy / "video.json", formats=["portrait", "landscape"], draft=True,
                         engine_override="silent", jobs=2)
    total = sum(s["sec"] for s in rep["scenes"])
    for o in rep["outputs"]:
        assert Path(o["video"]).exists() and Path(o["sheet"]).exists()
        assert abs(o["durationSec"] - total) < 0.1
        assert o["hasAudio"] and abs(o["audioSec"] - o["durationSec"]) < 0.15
    assert Path(rep["srt"]).read_text(encoding="utf-8").startswith("1\n")
    # second run is fully cached (no re-render)
    rep2 = make_video.run(demo_copy / "video.json", formats=["landscape"], draft=True, engine_override="silent")
    assert rep2["durationSec"] == rep["durationSec"]


def test_make_video_external_audio_and_srt(tmp_path):
    """Original workflow: recorded voice + SRT + hand-made annotation."""
    import make_video
    d = tmp_path / "p"
    d.mkdir()
    shutil.copy(MONKEY_PNG, d / "a.png")
    shutil.copy(MONKEY_ANN, d / "a.annotation.json")
    wb_video.save_wav(d / "voice.wav", (0.05 * np.random.default_rng(0).standard_normal((48000 * 6, 2))).astype(np.float32))
    (d / "voice.srt").write_text("1\n00:00:00,200 --> 00:00:02,500\nCon khỉ ngồi trên núi.\n\n"
                                 "2\n00:00:02,600 --> 00:00:05,500\nKhỉ lớn chạy tới cướp chuối.\n", encoding="utf-8")
    (d / "video.json").write_text(json.dumps({
        "title": "Khỉ", "voice": None, "audio": {"file": "voice.wav", "srt": "voice.srt"},
        "formats": ["landscape"], "scenes": [{"id": "s1", "image": "a.png"}]}), encoding="utf-8")
    rep = make_video.run(d / "video.json", draft=True)
    o = rep["outputs"][0]
    assert abs(o["durationSec"] - 6.0) < 0.1            # scene length == audio length (no drift)
    assert abs(o["audioSec"] - 6.0) < 0.15


def test_svg_scene_portrait_uses_long_edge(tmp_path):
    svg = tmp_path / "tall.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1920">'
                   '<g id="a"><circle cx="540" cy="500" r="100" fill="none" stroke="#222" stroke-width="6"/></g></svg>')
    _, annp = svg_scene.build(svg, tmp_path, width=960)
    assert json.loads(annp.read_text(encoding="utf-8"))["canvas"] == {"width": 540, "height": 960}


def test_hand_exits_sideways_on_tall_frames():
    import cv2
    img = cv2.imread(str(MONKEY_PNG))
    ann = json.loads(MONKEY_ANN.read_text(encoding="utf-8"))
    r = SceneRenderer(img, ann, RenderOptions(width=270, height=480, fps=10, verbose=False))
    x, y = r._hand_rest()
    assert x >= r.W and y < r.H                       # off to the right, not through the caption band
    assert r.hand.h <= int(0.42 * 270) + 1            # hand scaled to the short side


@pytest.mark.parametrize("seed", [3, 4, 5])      # 4 and 5 start the first note before t=0
def test_generated_music(seed):
    import gen_music
    a = gen_music.generate(4.0, "calm", seed=seed)
    assert a.shape == (4 * wb_video.SAMPLE_RATE, 2)
    assert 0.5 < float(np.max(np.abs(a))) <= 0.81
