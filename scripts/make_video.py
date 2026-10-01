#!/usr/bin/env python3
"""
One command: project JSON -> finished whiteboard explainer video(s).

  python make_video.py video.json                      # everything in the project
  python make_video.py video.json --draft              # fast low-res preview (same timing)
  python make_video.py video.json --formats portrait   # only 9:16
  python make_video.py --init my-video                 # scaffold a new project

Pipeline
  1. scenes    SVG -> PNG + annotation (vector strokes); PNG without annotation -> auto-annotate
  2. voice     per-scene TTS (edge expressive / gemini / tiktok / elevenlabs / ...) with word timings,
               or one recorded audio file + SRT (+ optional word timings)
  3. sync      each element starts drawing when its `say` phrase is spoken
  4. render    scenes rendered in parallel, cached by content hash
  5. compose   per format (landscape 1920x1080, portrait 1080x1920, square 1080x1080):
               layout + header + karaoke captions + scene transitions
  6. audio     voice + ducked background music + pen scratch SFX, normalised to -14 LUFS
  7. QA        contact sheet + JSON report for every output

Everything is frame-accurate: every scene has exactly round(ms*fps/1000) frames
and exactly frames*48000/fps audio samples, so voice never drifts.
See docs/PROJECT_FORMAT.md for the full project schema.
"""
from __future__ import annotations

import argparse
import copy
import gc
import hashlib
import json
import math
import os
import re
import shutil
import sys
import time
import unicodedata
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path

import cv2
import numpy as np

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

import auto_annotate  # noqa: E402
import captions as cap  # noqa: E402
import parse_srt  # noqa: E402
import stream_render as sr  # noqa: E402
import svg_scene  # noqa: E402
import timing  # noqa: E402
import tts  # noqa: E402
import wb_video as wv  # noqa: E402
from render_stream_whiteboard import RenderOptions, render_scene  # noqa: E402

FORMATS = {"landscape": (1920, 1080), "portrait": (1080, 1920), "square": (1080, 1080)}
# renders are cached by content; include the renderer's own code so code changes invalidate the cache
RENDERER_HASH = hashlib.sha256(b"".join(
    (SCRIPTS / f).read_bytes() for f in ("render_stream_whiteboard.py", "stream_render.py"))).hexdigest()[:16]
SVG_BUILDER_HASH = hashlib.sha256((SCRIPTS / "svg_scene.py").read_bytes()).hexdigest()[:16]
SR = wv.SAMPLE_RATE


# ──────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────
def log(msg: str) -> None:
    print(msg, flush=True)


def sha(*parts) -> str:
    h = hashlib.sha256()
    for p in parts:
        if isinstance(p, (bytes, bytearray)):
            h.update(p)
        else:
            h.update(json.dumps(p, sort_keys=True, ensure_ascii=False, default=str).encode())
        h.update(b"|")
    return h.hexdigest()


def file_hash(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p and p.exists() else ""


def slugify(text: str) -> str:
    t = unicodedata.normalize("NFD", text).replace("đ", "d").replace("Đ", "D")
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-").lower()
    return t or "video"


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    b = sr._hex_to_bgr(h)
    return int(b[2]), int(b[1]), int(b[0])


# ──────────────────────────────────────────────────────────────
# project
# ──────────────────────────────────────────────────────────────
DEFAULTS = {
    "fps": 30,
    "formats": ["landscape"],
    # best free voice: offline VieNeu-TTS male narrator; falls back to edge NamMinh if vieneu isn't installed
    "voice": {"engine": "vieneu", "voice": "Hải Đăng", "style": "natural", "rate": "+0%", "pitch": "+0Hz",
              "fx": "broadcast"},
    "captions": {"enabled": True, "karaoke": True, "maxWords": 6, "uppercase": False, "box": False},
    "render": {"inkPath": "skeleton", "colorFill": "contour-wipe", "camera": "follow", "cameraMaxZoom": 1.2,
               "paper": "#F6F1E3", "hand": None, "handHeightRatio": 0.42, "humanMotion": True, "penLift": 14,
               "idleHand": "exit", "drawSpeed": 1100},
    "sync": {"leadMs": 250, "voiceDelayMs": 200, "minDrawMs": 900, "maxDrawMs": 4500, "tailMs": 800},
    "transition": {"type": "fade", "ms": 350},
    "audio_master": {"lufs": -14.0},
}


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_project(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    proj = deep_merge(DEFAULTS, raw)
    if raw.get("voice") is None and "voice" in raw:   # "voice": null -> no TTS
        proj["voice"] = None
    if not proj.get("scenes"):
        raise ValueError("project has no scenes")
    for i, s in enumerate(proj["scenes"], 1):
        s.setdefault("id", f"scene-{i:02d}")
    return proj


# ──────────────────────────────────────────────────────────────
# 1. scene assets
# ──────────────────────────────────────────────────────────────
def prepare_scene(scene: dict, pdir: Path, bdir: Path, paper: str) -> tuple[Path, dict, Path]:
    """-> (image path, annotation dict, base dir for maskFile)."""
    sid = scene["id"]
    if scene.get("svg"):
        svg = pdir / scene["svg"]
        out = bdir / "scenes"
        out.mkdir(parents=True, exist_ok=True)
        key = sha(file_hash(svg), paper, SVG_BUILDER_HASH)
        png, annp = out / f"{svg.stem}.png", out / f"{svg.stem}.annotation.json"
        stamp = out / f"{svg.stem}.key"
        if not (png.exists() and annp.exists() and stamp.exists() and stamp.read_text() == key):
            log(f"  [{sid}] SVG -> PNG + vector strokes")
            svg_scene.build(svg, out, paper=paper)
            stamp.write_text(key)
        ann = json.loads(annp.read_text(encoding="utf-8"))
        image, base = png, out
    else:
        image = pdir / scene["image"]
        if not image.exists():
            raise FileNotFoundError(f"[{sid}] image not found: {image}")
        annp = pdir / scene["annotation"] if scene.get("annotation") else \
            image.parent / f"{image.stem}.annotation.json"
        if annp.exists() and not scene.get("auto"):
            ann = json.loads(annp.read_text(encoding="utf-8"))
        else:
            a = scene.get("auto") or {}
            log(f"  [{sid}] auto-annotating {image.name}")
            ann = auto_annotate.annotate(image, a.get("elements"), a.get("order", "reading"),
                                         a.get("labels"), a.get("say"))
        base = annp.parent
    # scene-level `say` list: assign phrases to elements (in drawing order) that have none
    says = scene.get("say") or []
    els = sorted(ann["elements"], key=lambda e: e.get("sequence", 0))
    for e, phrase in zip(els, says):
        if phrase and not e.get("say"):
            e["say"] = phrase
    return image, ann, base


# ──────────────────────────────────────────────────────────────
# 2. voice
# ──────────────────────────────────────────────────────────────
class SceneVoice:
    def __init__(self, audio: np.ndarray | None, words: list[tts.Word], speech_end: int, fixed_ms: int | None = None):
        self.audio = audio            # stereo float32 at SR, starts at scene start
        self.words = words            # relative to scene start
        self.speech_end = speech_end  # ms
        self.fixed_ms = fixed_ms      # scene length imposed by an external audio track


VOICE_KEYS = ("voice", "style", "rate", "pitch", "pauseScale", "phrasing", "lexicon", "instructions",
              "language", "reference", "referenceText", "confirmAuthorizedVoice", "chunk",
              "mood", "expressiveness", "autoMood")


_WARNED: dict = {}


def scene_voice_cfg(scene: dict, voice: dict, pdir: Path) -> dict:
    """Project voice + the scene's own "voice" overrides (e.g. {"style": "ads"} for the CTA)."""
    cfg = dict(voice)
    if isinstance(scene.get("voice"), dict):
        cfg.update(scene["voice"])
        if "engine" in scene["voice"] and "voice" not in scene["voice"]:
            cfg["voice"] = None                       # another engine: use its default voice
    if cfg.get("reference"):
        cfg["reference"] = str((pdir / cfg["reference"]).resolve())
    return cfg


def tts_scene(scene: dict, voice: dict, bdir: Path, delay_ms: int, engine_override: str | None,
              pdir: Path | None = None) -> SceneVoice:
    text = scene.get("narration", "").strip()
    if not text:
        return SceneVoice(None, [], 0)
    voice = scene_voice_cfg(scene, voice, pdir or bdir.parent)
    engine = engine_override or voice.get("engine", "edge")
    if not tts.engine_available(engine):
        if not _WARNED.get(engine):
            log(f"  !! engine '{engine}' is not installed (pip install {engine}); using edge vi-VN-NamMinhNeural")
            _WARNED[engine] = True
        voice = {**voice, "engine": "edge", "voice": "vi-VN-NamMinhNeural"}
        engine = "edge"
    cfg = {k: voice.get(k) for k in VOICE_KEYS}
    if engine != voice.get("engine"):
        cfg["voice"] = None                           # --engine override: that engine's default voice
    ref = Path(cfg["reference"]) if cfg.get("reference") else None
    key = sha(engine, cfg, text, ref.read_bytes() if ref and ref.exists() else b"", tts.PROSODY_VERSION)[:16]
    vdir = bdir / "voice"
    vdir.mkdir(parents=True, exist_ok=True)
    meta = vdir / f"{scene['id']}-{key}.json"
    if meta.exists():
        res = tts.TTSResult.from_json(json.loads(meta.read_text(encoding="utf-8")))
        if not Path(res.audio).exists():
            res = None
    else:
        res = None
    if res is None:
        style = cfg.get("style")
        log(f"  [{scene['id']}] TTS ({engine}{', ' + style if style else ''}) {len(text)} chars")
        res = tts.synthesize(text, vdir / f"{scene['id']}-{key}.mp3", engine, cfg["voice"],
                             cfg.get("rate") or "+0%", cfg.get("pitch") or "+0Hz",
                             instructions=cfg.get("instructions"), language=cfg.get("language") or "vi",
                             style=style, pause_scale=float(cfg.get("pauseScale") or 1.0),
                             lexicon=cfg.get("lexicon"), phrasing=cfg.get("phrasing", True) is not False,
                             reference=cfg.get("reference"), reference_text=cfg.get("referenceText"),
                             consent=cfg.get("confirmAuthorizedVoice") is True, chunk=cfg.get("chunk"),
                             mood=cfg.get("mood"),
                             expressiveness=float(cfg["expressiveness"]) if cfg.get("expressiveness")
                             is not None else 1.0,
                             auto_mood=cfg.get("autoMood", True) is not False)
        meta.write_text(json.dumps(res.to_json(), ensure_ascii=False), encoding="utf-8")
    audio = wv.polish_voice(wv.load_audio(res.audio), voice.get("fx", "broadcast"))
    audio = np.concatenate([wv.silence(delay_ms), audio])
    words = [tts.Word(w.text, w.startMs + delay_ms, w.endMs + delay_ms) for w in res.words]
    end = words[-1].endMs if words else delay_ms
    return SceneVoice(audio, words, end)


def external_audio_voices(proj: dict, pdir: Path) -> list[SceneVoice]:
    """One recorded voice track (+ SRT / word timings) cut into scenes."""
    acfg = proj["audio"]
    audio = wv.load_audio(pdir / acfg["file"]) if acfg.get("file") else None
    cues = []
    if acfg.get("srt"):
        cues = parse_srt.parse_srt((pdir / acfg["srt"]).read_text(encoding="utf-8-sig"))
    words_abs: list[tts.Word] = []
    if acfg.get("words"):
        wj = json.loads((pdir / acfg["words"]).read_text(encoding="utf-8"))
        wl = wj["words"] if isinstance(wj, dict) else wj
        words_abs = [tts.Word(w["text"], int(w["startMs"]), int(w["endMs"])) for w in wl]
    elif cues:
        for c in cues:
            words_abs += tts.estimate_words(c["text"], c["startMs"], c["endMs"])
    total_ms = int(len(audio) * 1000 / SR) if audio is not None else (cues[-1]["endMs"] + 800 if cues else 0)
    scenes = proj["scenes"]
    n = len(scenes)
    # scene boundaries: explicit cue ranges, or cues split evenly by time
    starts: list[int] = []
    if cues and all(s.get("cues") for s in scenes):
        starts = [cues[s["cues"][0] - 1]["startMs"] for s in scenes]
    elif cues:
        tot = cues[-1]["endMs"]
        for i in range(n):
            target = tot * i / n
            starts.append(min(cues, key=lambda c: abs(c["startMs"] - target))["startMs"])
    else:
        starts = [int(total_ms * i / n) for i in range(n)]
    starts[0] = 0
    out = []
    for i in range(n):
        s0 = starts[i]
        s1 = starts[i + 1] if i + 1 < n else total_ms
        seg = audio[int(s0 * SR / 1000):int(s1 * SR / 1000)] if audio is not None else None
        ws = [tts.Word(w.text, w.startMs - s0, w.endMs - s0) for w in words_abs if s0 <= w.startMs < s1]
        end = ws[-1].endMs if ws else 0
        out.append(SceneVoice(seg, ws, end, fixed_ms=max(1, s1 - s0)))
    return out


def fit_elements(elements: list[dict], limit_ms: int) -> None:
    """Compress a schedule so everything finishes before ``limit_ms``."""
    elements = [e for e in elements if not e.get("filler")]    # fillers are placed by the renderer
    if not elements:
        return
    last = max(e["reveal"]["startMs"] + e["reveal"]["durationMs"] for e in elements)
    if last <= limit_ms:
        return
    k = max(0.05, limit_ms / last)
    for e in elements:
        e["reveal"]["startMs"] = int(e["reveal"]["startMs"] * k)
        e["reveal"]["durationMs"] = max(300, int(e["reveal"]["durationMs"] * k))


# ──────────────────────────────────────────────────────────────
# 4. render (parallel, cached)
# ──────────────────────────────────────────────────────────────
def master_size(image: Path, long_edge: int) -> tuple[int, int]:
    img = sr._imread_any(str(image))
    h, w = img.shape[:2]
    s = long_edge / max(w, h)
    return max(2, int(round(w * s / 2)) * 2), max(2, int(round(h * s / 2)) * 2)


def _render_job(job: dict) -> dict:
    opts = RenderOptions(**job["opts"])
    t0 = time.time()
    render_scene(job["image"], job["annotation"], job["out"], opts, total_ms=job["total_ms"],
                 base_dir=job["base"], activity_path=job["activity"])
    return {"id": job["id"], "sec": time.time() - t0}


def render_scenes(jobs: list[dict], max_workers: int) -> None:
    todo = [j for j in jobs if not (Path(j["out"]).exists() and Path(j["activity"]).exists())]
    for j in jobs:
        if j not in todo:
            log(f"  [{j['id']}] cached render")
    if not todo:
        return
    workers = max(1, min(max_workers, len(todo)))
    log(f"  rendering {len(todo)} scene(s) with {workers} worker(s)...")
    if workers == 1:
        for j in todo:
            r = _render_job(j)
            log(f"  [{r['id']}] rendered in {r['sec']:.1f}s")
        return
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_render_job, j): j for j in todo}
        for f in as_completed(futs):
            r = f.result()
            log(f"  [{r['id']}] rendered in {r['sec']:.1f}s")


# ──────────────────────────────────────────────────────────────
# 5. compose
# ──────────────────────────────────────────────────────────────
def layout(fmt: str, W: int, H: int, aspect: float, header: bool, captions_on: bool):
    """Content box, caption style centre/size/width, header centre."""
    if fmt == "portrait":
        safe_bottom = int(H * (1 - 0.252))      # TikTok UI covers the bottom ~484 px of 1920
        size = int(W * 0.058)
        if aspect < 0.8:                          # tall artwork: full bleed, captions over it
            box = (0, 0, W, H)
            return box, (int(W * 0.47), int(H * 0.66)), size, int(W * 0.78), None
        top = int(H * (0.235 if header else 0.14))
        cap_h = int(H * 0.15) if captions_on else 0
        max_h = safe_bottom - top - cap_h - int(H * 0.02)
        cw, ch = W, int(W / aspect)
        if ch > max_h:
            ch = max_h
            cw = int(ch * aspect)
        box = ((W - cw) // 2, top, cw, ch)
        cap_center = (int(W * 0.47), top + ch + int(H * 0.02) + cap_h // 2)
        head = (W // 2, int(H * 0.145)) if header else None
        return box, cap_center, size, int(W * 0.8), head
    if fmt == "square":
        size = int(W * 0.052)
        if captions_on:
            ch = int(H * 0.84)
            cw = int(ch * aspect)
            if cw > W:
                cw, ch = W, int(W / aspect)
            box = ((W - cw) // 2, int(H * 0.02), cw, ch)
            return box, (W // 2, int(H * 0.92)), size, int(W * 0.86), None
        return (0, 0, W, H), (W // 2, int(H * 0.9)), size, int(W * 0.86), None
    # landscape: shrink the board a little to keep a clean caption band at the bottom
    size = int(H * 0.058)
    if captions_on:
        ch = int(H * 0.87)
        cw = int(ch * aspect)
        if cw > W:
            cw, ch = W, int(W / aspect)
        box = ((W - cw) // 2, 0, cw, ch)
        return box, (W // 2, int(H * 0.925)), size, int(W * 0.8), None
    return (0, 0, W, H), (W // 2, int(H * 0.9)), size, int(W * 0.8), None


def pen_sfx(activity: np.ndarray, fps: int, n_samples: int, seed: int = 7) -> np.ndarray:
    """Procedural marker-on-paper scratch, gated by per-frame pen activity."""
    if not len(activity) or not np.any(activity > 0):
        return np.zeros((n_samples, 2), np.float32)
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(n_samples).astype(np.float32)
    noise = wv.fft_filter(noise, lambda f: np.exp(-((np.log(np.maximum(f, 1)) - np.log(3800)) ** 2)
                                                  / (2 * 0.55 ** 2)))
    noise /= max(1e-6, float(np.std(noise)))
    spf = SR / fps
    env = np.repeat(np.clip(activity, 0, 1), int(round(spf)))[:n_samples]
    env = np.pad(env, (0, max(0, n_samples - len(env))))
    k = int(SR * 0.03)
    env = np.convolve(env, np.ones(k) / k, mode="same")
    # stroke texture: slow random amplitude wobble
    wob = np.repeat(rng.uniform(0.55, 1.0, n_samples // 2400 + 1), 2400)[:n_samples]
    wob = np.convolve(wob, np.ones(1200) / 1200, mode="same")
    s = noise * env * wob * 0.12
    return np.stack([s, s * 0.92], axis=1).astype(np.float32)


def build_audio(voices: list[SceneVoice], scene_frames: list[int], fps: int, proj: dict, pdir: Path,
                activities: list[np.ndarray]) -> np.ndarray | None:
    spf = SR // fps if SR % fps == 0 else SR / fps
    parts = []
    has_voice = any(v.audio is not None and len(v.audio) and float(np.max(np.abs(v.audio))) > 1e-4 for v in voices)
    for v, nf in zip(voices, scene_frames):
        n = int(round(nf * spf))
        a = v.audio if v.audio is not None else np.zeros((0, 2), np.float32)
        parts.append(wv.fit_length(a, n))
    voice = np.concatenate(parts) if parts else np.zeros((0, 2), np.float32)
    total = len(voice)
    mix = voice.copy()
    music_cfg = dict(proj.get("music") or {})
    if music_cfg.get("generate") and not music_cfg.get("file"):
        import gen_music
        style = music_cfg["generate"]
        style = style if isinstance(style, str) and style in gen_music.STYLES else "calm"
        secs = int(math.ceil(total / SR))          # the cached file always covers the whole video
        gp = pdir / "build" / f"music-{style}-{secs}s.wav"
        if not gp.exists():
            log(f"  generating {style} background music ({secs}s)")
            gp.parent.mkdir(parents=True, exist_ok=True)
            wv.save_wav(gp, gen_music.generate(secs + 0.5, style))
        music_cfg["file"] = str(gp)
    if music_cfg.get("file"):
        mp = pdir / music_cfg["file"]
        if mp.exists():
            m = wv.load_audio(mp)
            if len(m):
                reps = int(math.ceil(total / len(m)))
                m = np.concatenate([m] * max(1, reps))[:total]
                m = wv.fade(m, 800, 1500)
                base = float(music_cfg.get("volumeDb", -20))
                if has_voice and music_cfg.get("duck", True):
                    m = wv.duck_music(m, voice, base_gain_db=base, duck_db=float(music_cfg.get("duckDb", -8)))
                else:
                    m = m * (10 ** (base / 20))
                mix = mix + m
        else:
            log(f"  [warn] music file not found: {mp}")
    sfx = proj.get("sfx") or {}
    if sfx.get("pen", True) and activities:
        act = np.concatenate([a[:nf] if len(a) >= nf else np.pad(a, (0, nf - len(a)))
                              for a, nf in zip(activities, scene_frames)])
        s = pen_sfx(act, fps, total) * (10 ** (float(sfx.get("volumeDb", -17)) / 20))
        mix = mix + s
    if not has_voice and not music_cfg.get("file") and not sfx.get("pen", True):
        return None
    lufs = float(proj.get("audio_master", {}).get("lufs", -14.0))
    return wv.normalize_loudness(mix, lufs) if has_voice or music_cfg.get("file") else mix


def compose(fmt: str, proj: dict, scenes: list[dict], words_abs: list[tts.Word], audio: np.ndarray | None,
            out: Path, draft: bool, content_aspect: float) -> Path:
    W, H = FORMATS[fmt]
    if draft:
        W, H = W // 2 // 2 * 2, H // 2 // 2 * 2
    fps = proj["fps"]
    paper = proj["render"]["paper"]
    ccfg = proj.get("captions") or {}
    captions_on = bool(ccfg.get("enabled", True)) and bool(words_abs)
    head_cfg = proj.get("header")
    header_text = None
    if fmt == "portrait":
        header_text = (head_cfg or {}).get("text", proj.get("title")) if head_cfg is not False else None
    box, cap_center, cap_size, cap_width, head_center = layout(fmt, W, H, content_aspect, bool(header_text),
                                                               captions_on)
    def build_bg(color_bgr) -> np.ndarray:
        b = np.empty((H, W, 3), np.uint8)
        b[...] = color_bgr
        if header_text and head_center:
            cap.draw_text_block(b, header_text, head_center, int(W * 0.84), int(W * 0.066))
        return b
    bg = build_bg(sr._hex_to_bgr(paper))
    bg_fixed = False
    track = None
    if captions_on:
        st = cap.CaptionStyle(size=int(ccfg.get("size", 0) * (W / FORMATS[fmt][0])) or cap_size,
                              max_width=cap_width, center=cap_center,
                              max_words=int(ccfg.get("maxWords", 6)), karaoke=bool(ccfg.get("karaoke", True)),
                              uppercase=bool(ccfg.get("uppercase", False)), box=bool(ccfg.get("box", False)))
        if ccfg.get("highlight"):
            st.highlight = hex_to_rgb(ccfg["highlight"])
        track = cap.CaptionTrack(words_abs, st)
    x, y, cw, ch = box
    tr = proj.get("transition") or {}
    tr_type, tr_frames = tr.get("type", "fade"), int(round(tr.get("ms", 350) * fps / 1000))
    frame_idx = 0
    prev_last = None
    with wv.VideoSink(out, W, H, fps, crf=26 if draft else 20, preset="ultrafast" if draft else "medium",
                      audio=audio) as sink:
        for si, sc in enumerate(scenes):
            k = 0
            last = None
            for f in wv.iter_frames(sc["video"]):
                if k >= sc["frames"]:
                    break
                if not bg_fixed:
                    # use the paper colour as it came out of the codec, so the board and the
                    # surrounding band match exactly (yuv round trips shift colours slightly)
                    m = max(2, min(f.shape[:2]) // 60)
                    corners = np.concatenate([f[:m, :m].reshape(-1, 3), f[:m, -m:].reshape(-1, 3),
                                              f[-m:, :m].reshape(-1, 3), f[-m:, -m:].reshape(-1, 3)])
                    bg = build_bg(np.median(corners, axis=0).astype(np.uint8))
                    bg_fixed = True
                content = f if (f.shape[1], f.shape[0]) == (cw, ch) else \
                    cv2.resize(f, (cw, ch), interpolation=cv2.INTER_AREA)
                if prev_last is not None and k < tr_frames and tr_type != "cut":
                    a = 0.5 - 0.5 * math.cos(math.pi * (k + 1) / (tr_frames + 1))
                    if tr_type == "slide":
                        off = int(cw * a)
                        mixed = np.empty_like(content)
                        mixed[:, :cw - off] = prev_last[:, off:]
                        mixed[:, cw - off:] = content[:, :off] if off else mixed[:, cw - off:]
                        content = mixed
                    else:
                        content = cv2.addWeighted(prev_last, 1 - a, content, a, 0)
                frame = bg.copy()
                frame[y:y + ch, x:x + cw] = content
                if track is not None:
                    track.draw(frame, frame_idx * 1000.0 / fps)
                sink.write(frame)
                last = content
                frame_idx += 1
                k += 1
            while k < sc["frames"]:     # decoder came up short (should not happen): hold last frame
                frame = bg.copy()
                if last is not None:
                    frame[y:y + ch, x:x + cw] = last
                if track is not None:
                    track.draw(frame, frame_idx * 1000.0 / fps)
                sink.write(frame)
                frame_idx += 1
                k += 1
            prev_last = last
    return out


# ──────────────────────────────────────────────────────────────
# main pipeline
# ──────────────────────────────────────────────────────────────
def clean_build(bdir: Path) -> float:
    """Delete the large, cheap-to-rebuild intermediates (per-scene renders, scene PNGs);
    keep the voice and music caches, which are slow to regenerate.  Returns MB freed."""
    freed = 0
    for sub in ("render", "scenes"):
        d = bdir / sub
        if d.exists():
            freed += sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
            shutil.rmtree(d)
    return round(freed / 2**20, 1)


def run(project_path: Path, formats: list[str] | None = None, draft: bool = False, only: list[str] | None = None,
        jobs: int | None = None, engine_override: str | None = None, no_cache: bool = False,
        cleanup: bool = False) -> dict:
    t_start = time.time()
    pdir = project_path.parent.resolve()
    proj = load_project(project_path)
    name = proj.get("name") or slugify(proj.get("title") or project_path.stem)
    bdir = pdir / "build"
    if no_cache and bdir.exists():
        shutil.rmtree(bdir)
    bdir.mkdir(parents=True, exist_ok=True)
    odir = pdir / proj.get("outputDir", "out")
    odir.mkdir(parents=True, exist_ok=True)
    formats = formats or proj["formats"]
    fps = 15 if draft else int(proj["fps"])
    proj["fps"] = fps
    rcfg, scfg = proj["render"], proj["sync"]
    scenes_cfg = [s for s in proj["scenes"] if not only or s["id"] in only]

    log(f"== {proj.get('title', name)}: {len(scenes_cfg)} scene(s), formats={formats}{' [draft]' if draft else ''}")
    # 1. scene assets
    log("-- scenes")
    assets = [prepare_scene(s, pdir, bdir, rcfg["paper"]) for s in scenes_cfg]

    # 2. voice
    log("-- voice")
    if proj.get("audio"):
        voices = external_audio_voices(proj, pdir)
        if only:
            ids = [s["id"] for s in proj["scenes"]]
            voices = [voices[ids.index(s["id"])] for s in scenes_cfg]
    elif proj.get("voice"):
        voices = [tts_scene(s, proj["voice"], bdir, int(scfg["voiceDelayMs"]), engine_override, pdir)
                  for s in scenes_cfg]
    else:
        voices = [SceneVoice(None, [], 0) for _ in scenes_cfg]
    tts.release_models()                       # the voice model is not needed any more

    # 3. sync
    log("-- sync")
    sopts = timing.SyncOptions(lead_ms=int(scfg["leadMs"]), min_draw_ms=int(scfg["minDrawMs"]),
                               max_draw_ms=int(scfg["maxDrawMs"]), tail_ms=int(scfg["tailMs"]))
    durations = []
    for sc, (img, ann, base), v in zip(scenes_cfg, assets, voices):
        els = ann["elements"]
        if sc.get("keepTiming"):
            ms = int(ann.get("sceneDurationMs") or timing.schedule_without_voice(els, opts=sopts))
        elif v.words:
            ms = timing.schedule(els, v.words, v.speech_end, sopts)
        else:
            ms = int(ann.get("sceneDurationMs") or timing.schedule_without_voice(els, opts=sopts))
        if v.fixed_ms:
            fit_elements(els, v.fixed_ms - 400)
            ms = v.fixed_ms
        if sc.get("minMs"):
            ms = max(ms, int(sc["minMs"]))
        ann["sceneDurationMs"] = ms
        durations.append(ms)
        els_sorted = sorted(els, key=lambda e: e["reveal"]["startMs"])
        log(f"  [{sc['id']}] {ms / 1000:.2f}s: " + ", ".join(
            f"{e.get('label', e.get('id'))}@{e['reveal']['startMs'] / 1000:.1f}s" for e in els_sorted))
        (bdir / "scenes").mkdir(exist_ok=True)
        (bdir / "scenes" / f"{sc['id']}.scheduled.json").write_text(
            json.dumps({k: v2 for k, v2 in ann.items()}, ensure_ascii=False, indent=1), encoding="utf-8")

    # 4. render
    log("-- render")
    long_edge = 960 if draft else 1920
    rdir = bdir / "render"
    rdir.mkdir(exist_ok=True)
    jobs_list = []
    aspects = []
    for sc, (img, ann, base), ms in zip(scenes_cfg, assets, durations):
        w, h = master_size(img, long_edge)
        aspects.append(w / h)
        opts = dict(width=w, height=h, fps=fps, ink_path=rcfg["inkPath"], color_fill=rcfg["colorFill"],
                    camera=rcfg["camera"], camera_max_zoom=float(rcfg["cameraMaxZoom"]),
                    paper_hex=rcfg["paper"], hand_height_ratio=float(rcfg["handHeightRatio"]),
                    human_motion=bool(rcfg["humanMotion"]), pen_lift=float(rcfg["penLift"]),
                    idle_hand=str(rcfg["idleHand"]), draw_speed=float(rcfg["drawSpeed"]),
                    crf=24 if draft else 14, preset="ultrafast" if draft else "veryfast", verbose=False)
        if rcfg.get("hand"):
            opts["hand"] = str((pdir / rcfg["hand"]).resolve())
        elif rcfg.get("hand") is False:
            opts["hand"] = None
        mask_hash = file_hash(base / ann["maskFile"]) if ann.get("maskFile") else ""
        hand_file = opts["hand"] if "hand" in opts else RenderOptions().hand   # None = no hand
        hand_hash = file_hash(Path(hand_file)) if hand_file else ""
        key = sha(file_hash(img), ann, opts, mask_hash, hand_hash, RENDERER_HASH)[:14]
        jobs_list.append({"id": sc["id"], "image": str(img), "annotation": ann, "base": str(base),
                          "out": str(rdir / f"{sc['id']}-{key}.mp4"),
                          "activity": str(rdir / f"{sc['id']}-{key}.activity.json"),
                          "total_ms": ms, "opts": opts})
    render_scenes(jobs_list, jobs or (os.cpu_count() or 2))

    scene_frames = [int(round(ms * fps / 1000)) for ms in durations]
    activities = [np.asarray(json.loads(Path(j["activity"]).read_text())["activity"], np.float32)
                  for j in jobs_list]

    # absolute word timeline for captions
    words_abs: list[tts.Word] = []
    t0 = 0
    for v, nf in zip(voices, scene_frames):
        words_abs += [tts.Word(w.text, w.startMs + t0, w.endMs + t0) for w in v.words]
        t0 += nf * 1000 / fps
    srt_path = odir / f"{name}.srt"
    if words_abs:
        srt_path.write_text(tts.words_to_srt(words_abs), encoding="utf-8")

    # 6. audio
    log("-- audio")
    audio = build_audio(voices, scene_frames, fps, proj, pdir, activities)
    for v in voices:                           # mixed: free the per-scene tracks before encoding
        v.audio = None
    del activities
    gc.collect()
    if audio is not None:
        log(f"  mixed {len(audio) / SR:.2f}s, loudness {wv.loudness_lufs(audio):.1f} LUFS")

    # 5. compose
    import qa_frames
    report = {"project": str(project_path), "title": proj.get("title"), "durationSec": round(sum(scene_frames) / fps, 3),
              "scenes": [{"id": s["id"], "sec": round(nf / fps, 3)} for s, nf in zip(scenes_cfg, scene_frames)],
              "outputs": []}
    scenes_media = [{"video": j["out"], "frames": nf} for j, nf in zip(jobs_list, scene_frames)]
    aspect = float(np.median(aspects)) if aspects else 16 / 9
    for fmt in formats:
        if fmt not in FORMATS:
            raise ValueError(f"unknown format '{fmt}' (use {list(FORMATS)})")
        out = odir / f"{name}-{fmt}{'-draft' if draft else ''}.mp4"
        log(f"-- compose {fmt} -> {out.name}")
        compose(fmt, proj, scenes_media, words_abs, audio, out, draft, aspect)
        sheet = odir / f"{out.stem}-qa.jpg"
        rep = qa_frames.contact_sheet(str(out), str(sheet), count=12, cols=4,
                                      tile_w=360 if fmt != "portrait" else 220)
        report["outputs"].append(rep)
        log(f"  {rep['width']}x{rep['height']} {rep['durationSec']}s"
            + (f", {rep.get('loudnessLUFS')} LUFS" if rep.get("hasAudio") else ""))
    if words_abs:
        report["srt"] = str(srt_path)
    if cleanup:
        report["cleanedMB"] = clean_build(bdir)
        log(f"-- cleanup: freed {report['cleanedMB']} MB of intermediate renders")
    report["elapsedSec"] = round(time.time() - t_start, 1)
    (odir / f"{name}-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


# ──────────────────────────────────────────────────────────────
# scaffold
# ──────────────────────────────────────────────────────────────
def init_project(d: Path) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "scenes").mkdir(exist_ok=True)
    src = ROOT / "examples" / "demo-bau-troi"
    for f in (src / "scenes").glob("scene-01.svg"):
        shutil.copy(f, d / "scenes" / f.name)
    proj = {
        "title": "Tiêu đề video",
        "formats": ["portrait", "landscape"],
        "voice": {"engine": "vieneu", "voice": "Hải Đăng", "style": "podcast"},
        "music": {"file": None, "volumeDb": -20},
        "scenes": [{"id": "scene-01", "svg": "scenes/scene-01.svg",
                    "narration": "Viết lời thoại của cảnh một ở đây. Mỗi phần tử có data-say sẽ được vẽ khi câu đó được đọc."}],
    }
    p = d / "video.json"
    p.write_text(json.dumps(proj, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Project JSON -> whiteboard explainer video(s)")
    ap.add_argument("project", nargs="?", help="video.json")
    ap.add_argument("--formats", default=None, help="comma list: landscape,portrait,square")
    ap.add_argument("--draft", action="store_true", help="half resolution, 15 fps, fast encode")
    ap.add_argument("--scenes", default=None, help="only these scene ids (comma list)")
    ap.add_argument("--jobs", type=int, default=None, help="parallel render workers")
    ap.add_argument("--engine", default=None, choices=tts.ENGINES,
                    help="override the TTS engine (e.g. silent for offline tests)")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--cleanup", action="store_true",
                    help="after a successful build, delete per-scene renders (keeps voice/music caches)")
    ap.add_argument("--init", default=None, metavar="DIR", help="create a new project skeleton")
    a = ap.parse_args(argv)
    if a.init:
        p = init_project(Path(a.init))
        print(f"OUTPUT={p.resolve()}")
        return 0
    if not a.project:
        ap.error("project is required")
    split = lambda s: [x.strip() for x in s.split(",") if x.strip()] if s else None  # noqa: E731
    try:
        rep = run(Path(a.project), split(a.formats), a.draft, split(a.scenes), a.jobs, a.engine, a.no_cache,
                  a.cleanup)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"[err] {e}", file=sys.stderr)
        return 1
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    for o in rep["outputs"]:
        print(f"OUTPUT={Path(o['video']).resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
