#!/usr/bin/env python3
"""
The script of a finished video, for whoever publishes it: chapter timestamps (paste into a
YouTube description) and every scene's narration with the time it starts.

Usage:
  python export_script.py <project>/video.json [--report out/<name>-report.json] [--out FILE]
                          [--notes notes.md]

Times come from the render report (scene lengths); chapters from each scene's ``chapter``
(written by storyboard.py), the first scene being "Mở đầu".  Mood tags and delivery marks
are removed.  ``--notes`` appends a file (sources, fact-check notes).  Writes
``<project>/kich-ban-<name>.md``; prints ``OUTPUT=<file>``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import voice_studio as vs  # noqa: E402


def clock(sec: float) -> str:
    s = int(round(sec))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def export(video_json: Path, report: Path | None = None, out: Path | None = None, notes: Path | None = None) -> Path:
    proj = json.loads(video_json.read_text(encoding="utf-8"))
    name = proj.get("name") or video_json.parent.name
    report = report or video_json.parent / "out" / f"{name}-report.json"
    rep = json.loads(report.read_text(encoding="utf-8"))
    secs = {s["id"]: float(s["sec"]) for s in rep["scenes"]}
    starts, t = {}, 0.0
    for s in proj["scenes"]:
        starts[s["id"]] = t
        t += secs.get(s["id"], 0.0)
    out_info = (rep.get("outputs") or [{}])[0]
    meta = [f"Thời lượng: {clock(rep.get('durationSec', t))}"]
    if out_info:
        meta.append(f"{out_info.get('width')}×{out_info.get('height')}, {out_info.get('fps', proj.get('fps'))} khung hình/giây")
        if out_info.get("loudnessLUFS") is not None:
            meta.append(f"{out_info['loudnessLUFS']} LUFS")
    voice = proj.get("voice") or {}
    if voice:
        meta.append(f"giọng {voice.get('voice', '')} ({voice.get('engine', '')})".strip())
    chapters, body = [], []
    for i, s in enumerate(proj["scenes"]):
        chap = s.get("chapter") or ("Mở đầu" if i == 0 else None)
        if chap:
            chapters.append(f"{clock(starts[s['id']])} {chap}")
            body += [f"## {chap}", ""]
        body += [f"**{i + 1}.** `[{clock(starts[s['id']])}]` {vs.strip_pause_tags(s.get('narration', ''))}", ""]
    lines = [f"# {proj.get('title', name)}", "", " · ".join(meta), "",
             "## Mốc thời gian (chương)", "", "```", *chapters, "```", "", *body]
    if notes and notes.exists():
        lines += ["", notes.read_text(encoding="utf-8").strip(), ""]
    out = out or video_json.parent / f"kich-ban-{name}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="timestamped script of a rendered video")
    p.add_argument("video_json")
    p.add_argument("--report", default=None)
    p.add_argument("--out", default=None)
    p.add_argument("--notes", default=None, help="markdown appended at the end (sources, fact-check notes)")
    a = p.parse_args(argv)
    out = export(Path(a.video_json), Path(a.report) if a.report else None, Path(a.out) if a.out else None,
                 Path(a.notes) if a.notes else None)
    print(f"OUTPUT={out.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
