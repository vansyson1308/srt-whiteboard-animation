"""Mẫu dự án dài viết bằng Python: chạy file này để sinh scenes/*.svg + video.json.

    $PY examples/storyboard-mau/build.py
    $PY scripts/scene_sheet.py examples/storyboard-mau          # soát bố cục mọi cảnh
    $PY scripts/make_video.py examples/storyboard-mau/video.json --sync-check
    $PY scripts/make_video.py examples/storyboard-mau/video.json --cleanup
    $PY scripts/export_script.py examples/storyboard-mau/video.json

Mỗi ``sb.scene(lời thoại, ghi chú, *phần tử)`` là một cảnh; mỗi ``g(id, nhãn, data-say, *hình)``
là một phần tử được vẽ khi giọng đọc nói tới ``data-say`` (nguyên văn trong lời thoại).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from motifs import *  # noqa: E402,F401,F403
from storyboard import Storyboard  # noqa: E402

sb = Storyboard(__file__, "Vì sao cần ngủ đủ giấc?", name="ngu-du-giac", preset="youtube")

# Mở đầu: hook + vòng mở (open loop)
sb.scene("[hồi hộp] Thức trắng một đêm, não bạn hoạt động gần giống một người đã uống rượu. "
         "Vậy trong lúc ta ngủ, cơ thể đang làm gì mà quan trọng đến thế?",
         "Hook",
         g("night", "Thức trắng", "Thức trắng một đêm", moon(300, 300, 90), person(300, 760, 1.1, "sad")),
         g("brain", "Não như say rượu", "uống rượu", brain(800, 420, 1.0), cup(980, 700, 0.8)),
         g("q", "Câu hỏi", "cơ thể đang làm gì", qmark(1300, 420, 1.6, RED)))

# Phần 1: bảng chương + ba phần tử
sb.scene("Câu trả lời nằm ở một việc rất ít người để ý: | trong giấc ngủ sâu, não *tự dọn rác*. "
         "Dịch não tủy chảy qua các khe giữa tế bào, cuốn đi những chất thải tích tụ suốt ngày.",
         "Phần 1: não dọn rác khi ngủ",
         g("chap", "Phần 1: Não tự dọn rác", "Câu trả lời", chapter(1, "Não tự dọn rác")),
         g("clean", "Não dọn rác", "tự dọn rác", brain(500, 520, 1.1), water(330, 670, 640)),
         g("waste", "Chất thải tích tụ", "chất thải", *[circle(1100 + dx, 520 + dy, 18, GRAY, INK, 4)
                                                        for dx, dy in ((0, 0), (60, -40), (110, 30))],
           arrow(1000, 520, 1300, 520, BLUE)))

# Kết: callback + câu chốt
sb.scene("Vì vậy, ngủ đủ không phải là lười. [chậm] Đó là lúc bộ não tự chữa lành cho ngày mai.",
         "Kết",
         g("sleep", "Giấc ngủ", "ngủ đủ", moon(450, 330, 90), text(620, 330, "Z z z", 70, BLUE),
           person(450, 780, 1.0, "smile")),
         g("not", "Không phải lười", "không phải là lười", tag(1100, 330, "lười?", "#f4f4f4", 50, 220),
           cross(1260, 330, 1.0)),                 # dấu gạch đặt cạnh nhãn, không đè lên chữ
         g("heal", "Tự chữa lành", "tự chữa lành", heart(1150, 600, 1.2)),
         chapter="Kết")

sys.exit(sb.build())
