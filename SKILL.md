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
- **Chọn giọng + phong cách đọc** (mục "Giọng đọc" bên dưới): TikTok/kiến thức → `"style": "podcast"`; kể chuyện/cảm xúc → `"story"`; tin tức → `"news"`; kêu gọi hành động → `"ads"`. Có thể đặt riêng cho từng cảnh bằng `"voice": {"style": "story"}` trong cảnh. Muốn ngắt nghỉ có chủ ý (trước câu chốt) → chèn `[pause 600ms]` vào `narration`; thẻ này không hiện trong phụ đề.
- **Đạo diễn cảm xúc từng câu** (quan trọng để giọng truyền cảm): đặt tag ở đầu các câu then chốt – `[hồi hộp]` cho hook/câu dẫn tò mò, `[cao trào]` cho con số sốc/cú lật, `[xúc động]` cho đoạn buồn/sâu lắng, `[chậm]` cho định nghĩa/ý cốt lõi/câu chốt, `[nhanh]` cho đoạn liệt kê/dẫn dắt, `[vui]` cho kêu gọi tích cực. Mỗi cảnh chỉ 1–3 tag, để phần còn lại tự nhiên (không tag thì hệ thống tự đọc cảm xúc từ từ ngữ). Cả cảnh một màu cảm xúc → `"voice": {"mood": "emotional"}`. Kiểm tra: `$PY scripts/voice_studio.py "narration…" --style podcast` in ra mood, tốc độ, khoảng nghỉ từng câu.

### 3. Vẽ từng cảnh bằng SVG
Đọc **docs/SVG_GUIDE.md** trước khi vẽ. Tóm tắt:
- `viewBox="0 0 1600 900"` (dùng chung 16:9 và 9:16) hoặc `0 0 1080 1350` nếu chỉ làm TikTok.
- Mỗi `<g id=… data-label=… data-say="cụm từ trong lời thoại">` cấp cao nhất là một phần tử; thứ tự trong file = thứ tự vẽ; 3–6 phần tử/cảnh.
- `data-say` phải **xuất hiện nguyên văn** trong `narration` của cảnh đó.
- Nét `#2b2b2b` dày 5–8, bo tròn; nhấn cam/đỏ/xanh; font `Patrick Hand`; nhiều khoảng trắng; chữ trong cảnh chỉ là nhãn ngắn.
- Phần tử đầu tiên nên là thứ "hút mắt" nhất (câu hỏi, con số, hình lạ).
- Bàn tay vẽ với tốc độ tự nhiên rồi rút khỏi khung trong lúc chờ phần tử sau. Nếu một cảnh có quãng nói dài (> 3 giây) mà không có gì mới để vẽ, thêm phần tử có `data-say` cho quãng đó, hoặc 1–2 hình trang trí `data-filler="1"` (bóng đèn, ngôi sao, gạch chân phụ…) – renderer tự vẽ chúng vào khoảng nghỉ.

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

### 6. Giao file cho người dùng (video lớn)
Chat chỉ nhận file ≤ 30 MB, nên video dài (vài phút 1080p thường 50–150 MB) phải giao qua một trang Artifact:
```bash
$PY scripts/share_video.py projects/<slug>/out/<slug>-landscape.mp4 --title "Tên video"
```
Script cắt file thành các phần ≤ 14 MB (`share-<tên>/parts/`), tạo `index.html` và in các lượt publish. Publish `index.html` bằng Artifact tool, kèm `files` của lượt 1, `capabilities: {"downloads": true}` và `icon: "video"`. Các lượt sau publish lại **cùng file_path** chỉ với `files` còn lại (file được cộng dồn). Trang tự ghép các phần, kiểm tra SHA-256, phát video và có nút **Lưu video (.mp4)** để tải bản gốc, không nén lại. Trang là riêng tư; không đưa video lên repo.

### 7. Dọn dẹp sau khi giao (video dài)
Sau khi người dùng đã nhận video, giải phóng dung lượng: `$PY scripts/make_video.py <dự án>/video.json --cleanup` (hoặc thêm `--cleanup` ngay lần xuất cuối). Lệnh này xoá các bản render từng cảnh và PNG trung gian, giữ cache giọng đọc và nhạc (tốn thời gian tạo lại). Xoá luôn thư mục `out/share-*/parts` sau khi đã publish. Video 15 phút cần ~4 GB RAM ở bước trộn âm thanh; model VieNeu được giải phóng ngay sau bước giọng đọc.

## Tuỳ chọn hay dùng trong `video.json`

| Muốn | Đặt |
|---|---|
| Giọng nam (mặc định) | VieNeu `Hải Đăng`; nam khác: `"voice": {"voice": "Thiện Minh"}` (kể chuyện), `"Minh Đức"` (tin tức), `"Thanh Bình"` |
| Đọc nhanh hơn | `"voice": {"rate": "+10%"}` |
| Đọc có hồn hơn | `"voice": {"style": "podcast"}` (hoặc `story` / `news` / `ads` / `natural`) |
| Giọng Việt tự nhiên, miễn phí, chạy offline | `"voice": {"engine": "vieneu", "voice": "Hải Đăng", "style": "podcast"}` (cần `pip install vieneu`) |
| Giọng LLM hay nhất (key miễn phí) | `"voice": {"engine": "gemini", "voice": "Sulafat", "style": "story"}` + `GEMINI_API_KEY` |
| Giọng cao cấp (trả phí) | `"voice": {"engine": "elevenlabs"}` + `ELEVENLABS_API_KEY` (mặc định giọng Việt MinhTrung) |
| Đọc đúng từ viết tắt | `"voice": {"lexicon": {"GPT": "gi pi ti", "NASA": "na xa"}}` |
| Nhạc nền không lo bản quyền | `"music": {"generate": "calm", "volumeDb": -24}` (hoặc `"bright"`) |
| Nhạc nền của bạn | `"music": {"file": "music/bg.mp3", "volumeDb": -20}` |
| TikTok full màn hình | vẽ SVG `viewBox="0 0 1080 1920"`, `"formats": ["portrait"]`; giữ nội dung ở y 150–1120, chừa y 1150–1400 cho phụ đề – xem `examples/showcase-gap-giay/` |
| Tên kênh trên bút | `$PY scripts/brand_hand.py "Tên Kênh" assets/my-hand.png` → `"render": {"hand": "../../assets/my-hand.png"}` |
| Không có tay | `"render": {"hand": false}` |
| Không zoom camera | `"render": {"camera": "none"}` |
| Chỉ bản dọc | `"formats": ["portrait"]` |
| Giọng thu sẵn + SRT | `"voice": null, "audio": {"file": "voice.mp3", "srt": "voice.srt"}`, cảnh dùng `"cues": [1, 5]` |

Schema đầy đủ: **docs/PROJECT_FORMAT.md**.

## Giọng đọc (Voice Studio – từ ttspromax)

`"style"` bật "đạo diễn giọng đọc": mỗi câu được đọc riêng với tốc độ/cao độ theo loại câu (hỏi, cảm thán, đầu/cuối đoạn), thêm dấu phẩy lấy hơi trước từ nối trong câu dài, và ghép lại với khoảng lặng chính xác theo phong cách. Mặc định `"natural"`; `"plain"` = đọc một lượt như cũ.

**Mặc định**: engine `vieneu`, giọng nam `Hải Đăng`, `"fx": "broadcast"` (lọc ù, tăng độ rõ, nén nhẹ như giọng phát thanh). Chưa cài `vieneu` thì tự chuyển sang edge `vi-VN-NamMinhNeural`. Mỗi câu VieNeu có độ dài bất thường (đọc lan man/nuốt chữ) được đọc lại, giữ bản tốt nhất (`VIENEU_TAKES`, mặc định 3).

| Engine | Giọng (`voice`) | Cần | Ghi chú |
|---|---|---|---|
| `edge` (mặc định) | `vi-VN-HoaiMyNeural`, `vi-VN-NamMinhNeural`, `en-US-AndrewMultilingualNeural`, … | không | miễn phí, timestamp thật; chỉ 2 giọng Việt |
| `vieneu` | Bắc: `Hải Đăng`, `Thiện Minh` (kể chuyện), `Minh Đức` (tin tức), `Thanh Bình`, `Mai Anh` (nữ, tin tức), `Ngọc Linh` (nữ, kể chuyện); Nam: `Minh Triết`, `Thùy Dung`; Trung: `Quang Sơn` (`tts.py --list-voices vieneu`) | `pip install vieneu` (~1 GB model tải lần đầu) | VieNeu-TTS v3 Turbo, Apache-2.0, chạy CPU (~1× thời gian thực); clone từ `"reference"` cần `"confirmAuthorizedVoice": true` |
| `gemini` | `Sulafat` (ấm), `Kore`, `Aoede`, `Charon` (nam, truyền đạt), `Algieba`, `Gacrux`, … | `GEMINI_API_KEY` (có gói miễn phí) | LLM hiểu ngữ cảnh, làm theo `style` bằng lời; đọc từng câu (`"chunk": "paragraph"` để đọc cả đoạn) |
| `elevenlabs` | mặc định `FTYCiQT21H9XQvhRu0ch` (MinhTrung), hoặc giọng Việt khác trong Voice Library / giọng bạn tự clone | `ELEVENLABS_API_KEY` | timestamp ký tự thật; tự thử `eleven_v4` → `eleven_v3` → `eleven_flash_v2_5` (`ELEVENLABS_MODEL` để cố định) |
| `openai` | `alloy`, `nova`, … | `OPENAI_API_KEY` | `style` thành `instructions`; `OPENAI_BASE_URL` trỏ tới server tương thích (vd. `vieneu serve`) |
| `fish` | model id trên fish.audio, hoặc clone từ `"reference"` + `"referenceText"` | `FISH_API_KEY`, `pip install fish-audio-sdk` | **chỉ clone giọng khi chính chủ đồng ý**: `"confirmAuthorizedVoice": true`; không commit file giọng mẫu |
| `tiktok` / `makevoice` | `BV074_streaming`, `BV075_streaming` / ID ElevenLabs | không | qua dịch vụ trung gian không chính thức, điều khoản thương mại không rõ → **chỉ dùng làm nháp**, không dùng cho kênh kiếm tiền |

**Điều tiết theo nội dung (mood)**: mỗi câu có mood riêng (tag `[cao trào]`, `[xúc động]`, `[hồi hộp]`, `[chậm]`, `[nhanh]`, `[vui]`, hoặc tự đọc từ nội dung) quyết định tốc độ, cao độ, độ to, to/nhỏ dần và khoảng nghỉ quanh câu. `"expressiveness"` (0–2, mặc định 1) chỉnh độ đậm; `"autoMood": false` chỉ nghe theo tag. Bảng đầy đủ: docs/PROJECT_FORMAT.md.

Xem cách một đoạn sẽ được đọc (không cần mạng): `$PY scripts/voice_studio.py "Lời thoại…" --style story`. Danh sách giọng: `$PY scripts/voice_studio.py x --catalogue`.
Engine không có timestamp (vieneu/gemini/tiktok/makevoice/openai/fish) được căn thời gian bằng khoảng lặng trong audio khớp với dấu câu, nên `data-say` vẫn đồng bộ tốt (sai số ~0.1s); câu ngắn, dấu câu rõ ràng giúp đồng bộ chính xác hơn.

## Xử lý sự cố

- `edge-tts failed … certificate` → đặt `SSL_CERT_FILE`; không có mạng → `--engine silent` để làm nháp đúng nhịp.
- Engine trả thiếu giọng / lỗi mạng (gemini, tiktok, makevoice) → chạy lại (có retry + cache theo cảnh), hoặc tạm `--engine edge`.
- Phần tử không được vẽ đúng lúc → `data-say` không khớp lời thoại (xem log `-- sync`), sửa cho khớp nguyên văn.
- Nét bị cắt / vùng sai (ảnh raster) → mở `assets/preview.html`, chỉnh vùng, lưu, chạy lại.
- Mọi thứ được cache trong `build/`; `--no-cache` để làm lại từ đầu.

## Các script

| Script | Việc |
|---|---|
| `make_video.py` | Pipeline một lệnh (dùng cái này) |
| `svg_scene.py` | SVG → PNG + annotation có nét vector + label map |
| `auto_annotate.py` | Ảnh raster → annotation tự động |
| `tts.py` | TTS + timestamp từng từ, 8 engine (+ `--list-voices vi`) |
| `voice_studio.py` | Đạo diễn giọng đọc: phong cách, ngắt nghỉ, từ điển phát âm |
| `render_stream_whiteboard.py` | Render một cảnh (tương thích CLI cũ) |
| `render_annotation_preview.py` | Ảnh kiểm tra vùng/thời gian |
| `qa_frames.py` | Contact sheet + thông số video/âm thanh |
| `share_video.py` | Giao video lớn: cắt phần + trang Artifact xem/tải bản gốc |
| `generate_images.py` | Tạo ảnh line-art bằng OpenAI/Gemini (tuỳ chọn) |
| `brand_hand.py` | In tên kênh lên bút |
| `gen_music.py` | Nhạc nền procedural, không bản quyền |
| `parse_srt.py`, `merge_scenes.py` | Công cụ SRT/ghép cảnh của quy trình cũ |
