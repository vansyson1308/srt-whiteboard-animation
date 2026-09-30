---
name: srt-whiteboard-animation
description: Làm video whiteboard minh hoạ (bàn tay cầm bút vẽ từng nét, tô màu, giọng đọc tiếng Việt, phụ đề karaoke) cho TikTok/YouTube từ một chủ đề, một kịch bản, hoặc file SRT + giọng thu sẵn. Agent tự viết kịch bản, tự vẽ cảnh bằng SVG, rồi chạy một lệnh make_video.py ra MP4 16:9 và 9:16. Dùng khi người dùng muốn "làm video giải thích/whiteboard/vẽ tay", "biến SRT thành video vẽ tay", "làm video TikTok/YouTube kiến thức".
---

# Video whiteboard từ một prompt

Bạn (agent) là **biên kịch + hoạ sĩ + dựng phim**. Máy lo phần còn lại: TTS, đồng bộ, vẽ nét, camera, phụ đề, âm thanh, xuất file.
Trả lời người dùng bằng ngôn ngữ của họ (mặc định tiếng Việt).

## Chế độ làm việc

- **Autopilot (mặc định)**: đi hết quy trình dưới đây rồi giao video + QA. Chỉ hỏi lại khi thiếu thông tin thật sự quan trọng (ví dụ: chủ đề mơ hồ).
- **Duyệt từng bước**: nếu người dùng yêu cầu "cho tôi duyệt", dừng sau bước 2 (kịch bản), bước 3 (bản nháp `--draft`) để chờ xác nhận.

## Chuẩn bị môi trường (một lần)

```bash
python scripts/prepare_env.py          # tạo .venv + cài opencv, numpy, av, Pillow, edge-tts, resvg-py, svgelements
```
Dùng interpreter in ra ở dòng cuối `ENV_PY=...` cho mọi lệnh bên dưới (gọi là `$PY`).
Sau proxy công ty/SSL tự ký: đặt `SSL_CERT_FILE=<ca-bundle>` (TTS sẽ dùng).

## Quy trình autopilot

### 1. Tạo dự án
```bash
$PY scripts/make_video.py --init projects/<slug>
```
Tạo `projects/<slug>/video.json` + `scenes/`. (Mẫu hoàn chỉnh: `examples/demo-bau-troi/`.)

### 2. Viết kịch bản (phần quan trọng nhất)
- Độ dài: TikTok/Shorts 30–60s (~110–180 từ); YouTube 2–6 phút.
- **Câu đầu là hook** (câu hỏi gây tò mò / sự thật bất ngờ / lời hứa giá trị) – phải hiểu được ngay trong 2 giây.
- Chia 3–6 cảnh, **mỗi cảnh một ý**, 25–60 từ/cảnh (10–20 giây). Kết bằng một câu chốt/kêu gọi.
- Câu ngắn, văn nói tự nhiên, số viết dạng chữ số được (TTS đọc đúng). Tránh ký hiệu lạ, viết tắt.
- Viết `narration` cho từng cảnh vào `video.json`.

### 3. Vẽ từng cảnh bằng SVG
Đọc **docs/SVG_GUIDE.md** trước khi vẽ. Tóm tắt:
- `viewBox="0 0 1600 900"` (dùng chung 16:9 và 9:16) hoặc `0 0 1080 1350` nếu chỉ làm TikTok.
- Mỗi `<g id=… data-label=… data-say="cụm từ trong lời thoại">` cấp cao nhất là một phần tử; thứ tự trong file = thứ tự vẽ; 3–6 phần tử/cảnh.
- `data-say` phải **xuất hiện nguyên văn** trong `narration` của cảnh đó.
- Nét `#2b2b2b` dày 5–8, bo tròn; nhấn cam/đỏ/xanh; font `Patrick Hand`; nhiều khoảng trắng; chữ trong cảnh chỉ là nhãn ngắn.
- Phần tử đầu tiên nên là thứ "hút mắt" nhất (câu hỏi, con số, hình lạ).

Kiểm tra từng cảnh (nhìn ảnh bằng công cụ đọc ảnh của bạn):
```bash
$PY scripts/svg_scene.py projects/<slug>/scenes/scene-01.svg --out-dir /tmp/chk
$PY scripts/render_annotation_preview.py /tmp/chk/scene-01.png /tmp/chk/scene-01.annotation.json /tmp/chk/scene-01-check.jpg
```
Sửa SVG nếu: phần tử đè lên nhau khó đọc, chữ tràn khung, bố cục lệch, thiếu khoảng trống cho phụ đề ở đáy (~10%).

*Ảnh raster thay cho SVG* (khi cần tranh chi tiết): `scripts/generate_images.py` (cần API key) hoặc ảnh có sẵn → trong cảnh dùng `"image": ..., "auto": {"elements": K, "labels": [...]}, "say": [...]`.

### 4. Bản nháp nhanh
```bash
$PY scripts/make_video.py projects/<slug>/video.json --draft
```
Mở `out/*-draft-qa.jpg` và đọc log `-- sync` (mỗi phần tử bắt đầu lúc nào). Kiểm tra:
- khung 0s–2s đã có nét đang vẽ (hook);
- mỗi phần tử xuất hiện đúng lúc nói tới nó (log sync ≈ thời điểm của cụm từ);
- phụ đề không đè lên hình quan trọng, chữ tiếng Việt đúng dấu;
- không phần tử nào vẽ quá vội (< 0.9s) – nếu có: tách câu, đổi `data-say`, hoặc bớt phần tử.

### 5. Xuất bản chính thức
```bash
$PY scripts/make_video.py projects/<slug>/video.json
```
Kết quả trong `projects/<slug>/out/`: `*-portrait.mp4` (TikTok/Shorts/Reels), `*-landscape.mp4` (YouTube), `*.srt`, `*-qa.jpg`, `*-report.json`.
Xem `*-qa.jpg` một lần cuối, rồi báo cho người dùng: đường dẫn file, thời lượng, loudness, và gợi ý tiêu đề + mô tả + 5 hashtag.

## Tuỳ chọn hay dùng trong `video.json`

| Muốn | Đặt |
|---|---|
| Giọng nam | `"voice": {"voice": "vi-VN-NamMinhNeural"}` |
| Đọc nhanh hơn | `"voice": {"rate": "+10%"}` |
| Nhạc nền không lo bản quyền | `"music": {"generate": "calm", "volumeDb": -24}` (hoặc `"bright"`) |
| Nhạc nền của bạn | `"music": {"file": "music/bg.mp3", "volumeDb": -20}` |
| TikTok full màn hình | vẽ SVG `viewBox="0 0 1080 1920"`, `"formats": ["portrait"]`; giữ nội dung ở y 150–1120, chừa y 1150–1400 cho phụ đề – xem `examples/showcase-gap-giay/` |
| Tên kênh trên bút | `$PY scripts/brand_hand.py "Tên Kênh" assets/my-hand.png` → `"render": {"hand": "../../assets/my-hand.png"}` |
| Không có tay | `"render": {"hand": false}` |
| Không zoom camera | `"render": {"camera": "none"}` |
| Chỉ bản dọc | `"formats": ["portrait"]` |
| Giọng thu sẵn + SRT | `"voice": null, "audio": {"file": "voice.mp3", "srt": "voice.srt"}`, cảnh dùng `"cues": [1, 5]` |

Schema đầy đủ: **docs/PROJECT_FORMAT.md**.

## Xử lý sự cố

- `edge-tts failed … certificate` → đặt `SSL_CERT_FILE`; không có mạng → `--engine silent` để làm nháp đúng nhịp.
- Phần tử không được vẽ đúng lúc → `data-say` không khớp lời thoại (xem log `-- sync`), sửa cho khớp nguyên văn.
- Nét bị cắt / vùng sai (ảnh raster) → mở `assets/preview.html`, chỉnh vùng, lưu, chạy lại.
- Mọi thứ được cache trong `build/`; `--no-cache` để làm lại từ đầu.

## Các script

| Script | Việc |
|---|---|
| `make_video.py` | Pipeline một lệnh (dùng cái này) |
| `svg_scene.py` | SVG → PNG + annotation có nét vector + label map |
| `auto_annotate.py` | Ảnh raster → annotation tự động |
| `tts.py` | TTS + timestamp từng từ (+ `--list-voices vi`) |
| `render_stream_whiteboard.py` | Render một cảnh (tương thích CLI cũ) |
| `render_annotation_preview.py` | Ảnh kiểm tra vùng/thời gian |
| `qa_frames.py` | Contact sheet + thông số video/âm thanh |
| `generate_images.py` | Tạo ảnh line-art bằng OpenAI/Gemini (tuỳ chọn) |
| `brand_hand.py` | In tên kênh lên bút |
| `gen_music.py` | Nhạc nền procedural, không bản quyền |
| `parse_srt.py`, `merge_scenes.py` | Công cụ SRT/ghép cảnh của quy trình cũ |
