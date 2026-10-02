"""Storyboard / scene sheets / script export: the authoring tools around make_video."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import export_script  # noqa: E402
import scene_sheet  # noqa: E402
from motifs import arrow, chapter, g, person, speech, text  # noqa: E402
from storyboard import Storyboard  # noqa: E402


def _board(tmp_path: Path, say_ok: bool = True, glyph_ok: bool = True) -> Storyboard:
    sb = Storyboard(tmp_path / "build.py", "Vì sao cần ngủ đủ giấc?", preset="broadcast",
                    lexicon={"REM": "rem"})
    sb.scene("[hồi hộp] Thức trắng một đêm, | não bạn như *say rượu*.", "Hook",
             g("p", "Người thức trắng", "Thức trắng", person(300, 760, 1.0, "sad")),
             g("q", "Say rượu", "say rượu" if say_ok else "say bia", speech(500, 200, 300, 100, "?!", 48)))
    sb.scene("Câu trả lời nằm ở giấc ngủ sâu.", "Phần 1",
             g("chap", "Phần 1", "Câu trả lời", chapter(1, "Não tự dọn rác")),
             g("t", "Nhãn", "giấc ngủ sâu", text(800, 500, "ngủ sâu" if glyph_ok else "ngủ → sâu", 50),
               arrow(600, 600, 900, 600)))
    return sb


def test_storyboard_builds_a_project(tmp_path):
    assert _board(tmp_path).build() == 0
    proj = json.loads((tmp_path / "video.json").read_text(encoding="utf-8"))
    assert proj["name"] == "vi-sao-can-ngu-du-giac" and proj["fps"] == 25
    assert proj["audio_master"]["lufs"] == -23.0 and proj["voice"]["lexicon"] == {"REM": "rem"}
    s1, s2 = proj["scenes"]
    assert s1["chapter"] == "Mở đầu" and "pauseBeforeMs" not in s1
    assert s2["chapter"] == "Phần 1: Não tự dọn rác" and s2["pauseBeforeMs"] == 500
    assert (tmp_path / "scenes" / "scene-02.svg").exists()
    script = (tmp_path / "kich-ban-rut-gon.md").read_text(encoding="utf-8")
    assert "não bạn như say rượu." in script and "|" not in script and "[hồi hộp]" not in script


def test_storyboard_catches_mistakes(tmp_path):
    problems = _board(tmp_path, say_ok=False, glyph_ok=False).check()
    assert any("say bia" in p for p in problems)
    assert any("→" in p for p in problems)


def test_scene_sheet_and_script_export(tmp_path):
    _board(tmp_path).build()
    pages = scene_sheet.sheets(tmp_path, tmp_path / "sheets", safe=True)
    assert len(pages) == 1 and pages[0].stat().st_size > 1000
    report = {"durationSec": 75.4, "scenes": [{"id": "scene-01", "sec": 14.2}, {"id": "scene-02", "sec": 61.2}],
              "outputs": [{"width": 1920, "height": 1080, "fps": 25.0, "loudnessLUFS": -23.0}]}
    (tmp_path / "out").mkdir()
    rep = tmp_path / "out" / "vi-sao-can-ngu-du-giac-report.json"
    rep.write_text(json.dumps(report), encoding="utf-8")
    out = export_script.export(tmp_path / "video.json")
    md = out.read_text(encoding="utf-8")
    assert out.name == "kich-ban-vi-sao-can-ngu-du-giac.md"
    assert "0:00 Mở đầu" in md and "0:14 Phần 1: Não tự dọn rác" in md and "1:15" in md
    assert "**2.** `[0:14]` Câu trả lời nằm ở giấc ngủ sâu." in md
