#!/usr/bin/env python3
"""
Storyboard: write a video as Python - one ``scene(narration, note, *elements)`` per scene -
and build the whole project from it (scenes/*.svg, video.json, a readable script), with the
checks that catch the usual mistakes before any audio is made.

    # projects/<slug>/build.py
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from motifs import *                       # noqa: F401,F403
    from storyboard import Storyboard

    sb = Storyboard(__file__, "Người học thông thái", preset="youtube", lexicon={"MBTI": "em bi ti ai"})
    sb.scene("[hồi hộp] Nếu có ai đó tuyên bố rằng họ đã giác ngộ, ...", "Hook",
             g("guru", "Người tự xưng giác ngộ", "đã giác ngộ", person(300, 800, 1.0, "smile", "up")),
             ...)
    sb.scene("Trước hết, điều quan trọng nhất ...", "Phần 1",
             g("chap", "Phần 1", "điều quan trọng nhất", chapter(1, "Hiểu chính mình")), ...)
    sys.exit(sb.build())

Checks (exit code 1 when one fails):
  * every ``data-say`` is in its scene's narration (as spoken: tags and delivery marks removed);
  * every character of every ``<text>`` exists in Patrick Hand (a missing glyph falls back to
    another font and looks wrong: draw arrows with ``arrow()``, never type "→").

Scenes that open with a ``chapter()`` board get a chapter name (used by export_script.py)
and a longer rest before them (``pauseBeforeMs``).  Presets: youtube | broadcast | tiktok.
Prints ``N scenes, W words`` and ``OUTPUT=<video.json>``.
"""
from __future__ import annotations

import copy
import json
import re
import sys
import unicodedata
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import voice_studio as vs  # noqa: E402
from motifs import svg  # noqa: E402

FONT = SCRIPTS.parent / "assets" / "fonts" / "PatrickHand-Regular.ttf"
CHAPTER_PAUSE_MS = 500

_BASE = {
    "voice": {"engine": "vieneu", "voice": "Hải Đăng", "style": "natural", "pauseScale": 1.1},
    "captions": {"enabled": True, "karaoke": True, "maxWords": 7},
    "music": {"generate": "calm", "volumeDb": -27, "duck": True, "duckDb": -8},
    "sfx": {"pen": False, "volumeDb": -25},      # pen scratch off by default; set "pen": True to bring it back
    "render": {"camera": "follow", "cameraMaxZoom": 1.2},
    "transition": {"type": "fade", "ms": 400},
}
PRESETS = {
    # YouTube / web: 1080p30, -14 LUFS
    "youtube": {"formats": ["landscape"], "fps": 30, "audio_master": {"lufs": -14.0}},
    # television (Vietnam, EBU R128): 1080p25, -23 LUFS; keep drawings inside the 90 % title-safe area
    "broadcast": {"formats": ["landscape"], "fps": 25, "audio_master": {"lufs": -23.0}},
    # TikTok / Shorts / Reels
    "tiktok": {"formats": ["portrait"], "fps": 30, "audio_master": {"lufs": -14.0},
               "captions": {"enabled": True, "karaoke": True, "maxWords": 6}},
}
_CHAPTER = re.compile(r">PHẦN (\d+)</text>\s*<text[^>]*>([^<]+)</text>")


def slugify(title: str) -> str:
    s = unicodedata.normalize("NFD", title.lower().replace("đ", "d"))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60] or "video"


def _merge(a: dict, b: dict) -> dict:
    out = copy.deepcopy(a)
    for k, v in b.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def font_chars() -> set[str]:
    try:
        from fontTools.ttLib import TTFont
        return {chr(c) for c in TTFont(str(FONT)).getBestCmap()}
    except Exception:                                   # fontTools missing: skip the glyph check
        return set()


def _unescape(t: str) -> str:
    return t.replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")


class Storyboard:
    def __init__(self, build_file: str | Path, title: str, name: str | None = None, preset: str = "youtube",
                 lexicon: dict | None = None, config: dict | None = None):
        self.dir = Path(build_file).resolve().parent
        self.title = title
        self.name = name or slugify(title)
        if preset not in PRESETS:
            raise ValueError(f"unknown preset {preset!r} (choose from {', '.join(PRESETS)})")
        self.config = _merge(_merge(_BASE, PRESETS[preset]), config or {})
        if lexicon:
            self.config["voice"]["lexicon"] = dict(lexicon)
        self.scenes: list[dict] = []

    def scene(self, narration: str, note: str, *elements: str, chapter: str | None = None,
              **extra) -> None:
        """One scene: its narration (mood tags, ``|`` beats and ``*stress*`` allowed), a note
        for the SVG comment, and its top-level groups.  ``chapter`` names the chapter it opens
        (detected from a ``chapter()`` board otherwise); ``extra`` goes into the scene entry
        of video.json (e.g. ``voice={"mood": "emotional"}``, ``pauseBeforeMs=800``)."""
        self.scenes.append({"narration": narration, "note": note, "els": [e for e in elements if e],
                            "chapter": chapter, "extra": extra})

    def check(self) -> list[str]:
        have = font_chars()
        problems = []
        for i, sc in enumerate(self.scenes, 1):
            sid = f"scene-{i:02d}"
            spoken = unicodedata.normalize("NFC", vs.strip_pause_tags(sc["narration"])).lower()
            body = "\n".join(sc["els"])
            if "data-say=" not in body:
                problems.append(f"{sid}: no element has data-say (nothing is tied to the voice)")
            for say in re.findall(r'data-say="([^"]+)"', body):
                if unicodedata.normalize("NFC", _unescape(say)).lower() not in spoken:
                    problems.append(f"{sid}: data-say {say!r} is not in the narration")
            if have:
                for t in re.findall(r"<text[^>]*>([^<]*)</text>", body):
                    miss = {c for c in unicodedata.normalize("NFC", _unescape(t)) if c not in have and not c.isspace()}
                    if miss:
                        problems.append(f"{sid}: Patrick Hand has no {''.join(sorted(miss))!r} (in {t!r})")
        return problems

    def _chapter(self, i: int, sc: dict) -> str | None:
        if sc["chapter"]:
            return sc["chapter"]
        m = _CHAPTER.search("\n".join(sc["els"]))
        if m:
            return f"Phần {m.group(1)}: {_unescape(m.group(2))}"
        return "Mở đầu" if i == 1 else None

    def build(self) -> int:
        problems = self.check()
        (self.dir / "scenes").mkdir(exist_ok=True)
        entries, lines = [], [f"# {self.title} (kịch bản rút gọn)", ""]
        for i, sc in enumerate(self.scenes, 1):
            sid = f"scene-{i:02d}"
            body = "\n".join(sc["els"])
            (self.dir / "scenes" / f"{sid}.svg").write_text(svg(body, sc["note"]), encoding="utf-8")
            entry = {"id": sid, "svg": f"scenes/{sid}.svg", "narration": unicodedata.normalize("NFC", sc["narration"])}
            chap = self._chapter(i, sc)
            if chap:
                entry["chapter"] = chap
                if i > 1:
                    entry["pauseBeforeMs"] = CHAPTER_PAUSE_MS
                lines += [f"## {chap}", ""]
            entry.update(sc["extra"])
            entries.append(entry)
            lines += [f"**{i}.** {vs.strip_pause_tags(sc['narration'])}", ""]
        proj = {"title": self.title, "name": self.name, **self.config, "scenes": entries}
        out = self.dir / "video.json"
        out.write_text(json.dumps(proj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (self.dir / "kich-ban-rut-gon.md").write_text("\n".join(lines), encoding="utf-8")
        words = sum(len(vs.strip_pause_tags(e["narration"]).split()) for e in entries)
        print(f"{len(entries)} scenes, {words} words")
        for p in problems:
            print("!!", p)
        print(f"OUTPUT={out}")
        return 1 if problems else 0
