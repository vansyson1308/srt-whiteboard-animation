#!/usr/bin/env python3
"""
Generate whiteboard-style line-art scenes with an image API (optional path -
agents can also draw scenes themselves as SVG, see svg_scene.py).

Providers (model ids are configurable because vendors retire them often):
  openai   OPENAI_API_KEY   model: $OPENAI_IMAGE_MODEL  (default gpt-image-2)
  gemini   GEMINI_API_KEY   model: $GEMINI_IMAGE_MODEL  (default gemini-3.1-flash-image)

Every prompt is wrapped with the shared STYLE so a series stays consistent.

Usage:
  python generate_images.py "a sun shining on a small planet" scenes/scene-01.png
        [--provider openai|gemini] [--aspect 16:9|9:16|1:1] [--annotate 4]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

STYLE = (
    "Minimal hand-drawn whiteboard illustration, clean sketch line art like a Notion doodle. "
    "Warm beige paper background (#F5EBD7), dark grey (#2b2b2b) marker lines of even width, "
    "only small accents of red, orange and blue. Flat, no shading texture, no 3D, no photo realism. "
    "Lots of empty space; separate objects clearly with gaps between them so each can be drawn on its own. "
    "Absolutely no text, letters, numbers or labels anywhere in the image."
)
SIZES = {"16:9": "1536x864", "9:16": "864x1536", "1:1": "1024x1024", "4:5": "1024x1280"}


def _post(url: str, payload: dict, headers: dict) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())


def openai_image(prompt: str, aspect: str) -> bytes:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    model = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-2")
    data = _post("https://api.openai.com/v1/images/generations",
                 {"model": model, "prompt": prompt, "size": SIZES.get(aspect, "1536x864"),
                  "quality": os.environ.get("OPENAI_IMAGE_QUALITY", "medium"), "n": 1},
                 {"Authorization": f"Bearer {key}"})
    return base64.b64decode(data["data"][0]["b64_json"])


def gemini_image(prompt: str, aspect: str) -> bytes:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")
    model = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    data = _post(url, {"contents": [{"parts": [{"text": f"{prompt}\nAspect ratio {aspect}."}]}],
                       "generationConfig": {"responseModalities": ["IMAGE"]}}, {})
    for part in data["candidates"][0]["content"]["parts"]:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline:
            return base64.b64decode(inline["data"])
    raise RuntimeError("Gemini returned no image")


def generate(subject: str, out: str | Path, provider: str = "openai", aspect: str = "16:9") -> Path:
    prompt = f"{STYLE}\nScene: {subject}"
    png = openai_image(prompt, aspect) if provider == "openai" else gemini_image(prompt, aspect)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(png)
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Generate a whiteboard line-art scene")
    p.add_argument("subject", help="what the scene shows (any language)")
    p.add_argument("out")
    p.add_argument("--provider", default="openai", choices=["openai", "gemini"])
    p.add_argument("--aspect", default="16:9", choices=list(SIZES))
    p.add_argument("--annotate", type=int, default=None, metavar="K", help="also auto-annotate into K elements")
    a = p.parse_args(argv)
    out = generate(a.subject, a.out, a.provider, a.aspect)
    if a.annotate:
        import auto_annotate
        auto_annotate.main([str(out), "--elements", str(a.annotate)])
    print(f"OUTPUT={out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
