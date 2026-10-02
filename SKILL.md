---
name: srt-whiteboard-animation
description: Làm video whiteboard minh hoạ (bàn tay cầm bút vẽ từng nét, tô màu, giọng đọc tiếng Việt có nhịp như người dẫn, phụ đề karaoke) cho YouTube/truyền hình/TikTok từ một chủ đề, một kịch bản (kể cả rất dài), hoặc file SRT + giọng thu sẵn. Agent chắt lọc + kiểm chứng kịch bản, viết cảnh bằng Python (motifs + storyboard), chạy make_video.py ra MP4, soát QA và giao file. Dùng khi người dùng muốn "làm video giải thích/whiteboard/vẽ tay", "biến kịch bản/SRT thành video", "làm video TikTok/YouTube kiến thức".
---

# Video whiteboard từ một prompt

Bạn (agent) là **biên kịch + biên tập viên + hoạ sĩ + đạo diễn giọng đọc + dựng phim**. Máy lo phần còn lại: TTS, nhịp đọc, đồng bộ, vẽ nét, camera, phụ đề, âm thanh, xuất file.
Trả lời người dùng bằng ngôn ngữ của họ (mặc định tiếng Việt).

## Chế độ làm việc

- **Autopilot (mặc định):** đi hết quy trình dưới đây rồi giao video. Chỉ hỏi lại khi thiếu thông tin thật sự quan trọng.
- **Duyệt từng bước:** khi người dùng yêu cầu, dừng sau bước 1 (dàn ý), bước 4 (ảnh soát cảnh) và bước 6 (kiểm tra khớp) để chờ xác nhận.
- **Một kịch bản mới:** dọn dẹp video trước (bước 9), rồi mới bắt đầu.

## Chuẩn bị môi trường (một lần)

```bash
python scripts/prepare_env.py          # tạo .venv + cài thư viện; VieNeu (giọng offline) nếu cài được
```

Dùng interpreter in ở dòng cuối (`ENV_PY=...`) cho mọi lệnh bên dưới; tài liệu này gọi nó là `$PY`. Sau proxy hoặc SSL tự ký: đặt `SSL_CERT_FILE=<ca-bundle>`.

## Quy trình

### 1. Chắt lọc và kiểm chứng nội dung

Đọc hết nguồn: transcript, kịch bản, bài viết. Viết dàn ý trước khi vẽ.

- **Dàn ý:**
  - **Hook** ở câu đầu: một tình huống, một con số, một câu hỏi hiểu được trong 2 giây.
  - **Vòng mở:** 3–4 điều khán giả sẽ biết, nhá trước, chưa trả lời.
  - **Thẻ tiêu đề.**
  - **Các phần "PHẦN n"**, mỗi phần một luận điểm, 4–8 cảnh.
  - **Kết:** quay lại hook, rút ra một câu chốt, rồi lời kêu gọi hợp nền tảng. YouTube: chia sẻ, bình luận. Truyền hình: lời cảm ơn, không kêu gọi đăng ký.
- **Độ dài:**
  - TikTok/Shorts 30–60 s (khoảng 110–180 từ).
  - YouTube dài 10–15 phút (khoảng 2.300–3.000 từ, 45–60 cảnh).
  - Tốc độ đọc khoảng 230 từ/phút.
- **Chắt lọc:**
  - Giữ những ý tinh túy nhất. Bỏ lặp, lan man, quảng cáo.
  - Viết lại thành văn nói, câu ngắn, ai nghe cũng hiểu.
  - Có thể bổ sung kiến thức chuẩn để làm rõ: kinh điển, triết học, tâm lý học.
- **Kiểm chứng:**
  - Mọi số liệu, năm, tên người, trích dẫn và tin thời sự đều phải được tra lại (dùng web/agent nghiên cứu khi có).
  - Sửa lỗi của nguồn. Ghi rõ "được kể lại rằng" với giai thoại, nói rõ truyền thuyết hay chú giải.
  - Lưu nguồn vào một file ghi chú (`ghi-chu-nguon.md`) để giao kèm. Không đọc trích dẫn dày đặc trong video.
- **Biên tập:**
  - Cân bằng, tôn trọng.
  - Không mô tả chi tiết bạo lực hay tình dục, không quy chụp nhóm người.
  - Chủ đề trẻ em, sức khỏe tâm thần: nhắc kênh hỗ trợ (Tổng đài quốc gia bảo vệ trẻ em 111).
- **Tên dự án:** `projects/<slug>/` là thư mục riêng của người dùng, **không commit**: thêm `projects/<slug>/` vào `.git/info/exclude`. Không commit giọng mẫu, audio, video, API key hay `.env*`.

### 2. Viết kịch bản + cảnh trong `projects/<slug>/build.py`

Mẫu: [`examples/storyboard-mau/build.py`](examples/storyboard-mau/build.py). Video dài: tách cảnh ra `scenes_a.py`, `scenes_b.py`… (mỗi file một danh sách `sb.scene(...)` hoặc một hàm nhận `sb`), giữ `build.py` ngắn.

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from motifs import *
from storyboard import Storyboard

sb = Storyboard(__file__, "Tên video", preset="youtube", lexicon={})   # youtube | broadcast | tiktok
sb.scene("[hồi hộp] Lời thoại cảnh 1 …", "ghi chú",
         g("id", "Nhãn", "cụm từ nguyên văn", person(300, 800, 1.1), speech(...)), ...)
sys.exit(sb.build())
```

**Lời thoại** (từng cảnh 40–70 từ, mỗi cảnh một ý):

- **Văn nói:** câu ngắn. Viết số thành chữ khi cần đọc tự nhiên ("một một một", "năm một chín bảy chín").
- **Dấu câu theo ý:** phẩy là chỗ lấy hơi, hai chấm là nhịp chờ trước điều sắp nói, chấm là hết ý. Hệ thống tự đặt nhịp như người dẫn theo cấu trúc câu:
  - điểm nhấn sau câu dẫn ("…bốn chữ: …");
  - hai vế đối xứng;
  - "Thứ nhất / Thứ hai";
  - liệt kê, tương phản, câu chốt.
- **Đọc lại như một MC:** chỗ cần dừng mà cấu trúc câu không tự lộ ra thì chèn `|` (nhịp ngừng) hoặc `||` (ngừng dài); cụm cần nhấn thì viết `*cụm từ*`. Tiết chế: 0–2 dấu mỗi cảnh. Ngắt chính xác giữa hai câu: `[pause 600ms]`. Các dấu này không hiện trong phụ đề.
- **Cảm xúc:** đặt tag ở đầu câu then chốt, 1–3 tag mỗi cảnh:
  - `[hồi hộp]` cho hook, câu dẫn tò mò;
  - `[cao trào]` cho con số sốc, cú lật;
  - `[xúc động]` cho đoạn sâu lắng;
  - `[chậm]` cho ý cốt lõi, câu chốt;
  - `[nhanh]` cho đoạn dẫn dắt;
  - `[vui]` cho lời kêu gọi tích cực;
  - `[bình thường]` để ghim lại câu máy đọc nhầm.
- **Tên riêng nước ngoài:** viết chính tả gốc (Einstein, Carl Jung). Kiểm tra cách đọc:

  ```bash
  $PY -c "from vieneu_utils.phonemize_text import phonemize_text_with_emotions as p; print(p('Sartre'))"
  ```

  Chỉ thêm `lexicon` khi máy đọc sai, ví dụ `{"Sartre": "Xác tơ", "MBTI": "em bi ti ai"}`. Đừng phiên âm kiểu "Niu-tơn".

**Cảnh** (đọc [`docs/SVG_GUIDE.md`](docs/SVG_GUIDE.md)):

- **Số phần tử:** 3–5 phần tử nhẹ mỗi cảnh, mỗi phần tử là `g(id, nhãn, data-say, *hình)`.
- **`data-say`:** 1–3 từ, **nguyên văn** trong lời thoại của cảnh. Phần tử được vẽ theo thứ tự cụm từ được nói.
- **Phần tử đầu tiên:** gắn với những chữ đầu của lời thoại.
- **Hình mẫu:** dùng hình trong `motifs.py` cho phong cách thống nhất, như `person`, `woman`, `kid`, `teen`, `parent`, `monk`, `buddha`, `sage`, `book`, `scroll`, `phone`, `laptop`, `scale`, `ledger`, `heart`, `lens`, `mirror`, `hourglass`, `calendar`…
  - Chữ và bố cục: `chapter(n, "Tên phần")` cho cảnh mở chương; `tag`, `speech`, `thought`, `arrow`, `check`, `cross`, `number_card`, `big_number`.
  - Thiếu hình thì viết hàm mới trong `build.py` theo cùng phong cách (nét `#2b2b2b`, dày 4–7). Hình dùng nhiều lần nên thêm vào `motifs.py`.
- **Tránh:**
  - hình nặng (đám đông lớn, nhiều chữ), vì bút sẽ vẽ chậm;
  - ký tự không có trong Patrick Hand ("→"): dùng `arrow()`;
  - dấu gạch đè lên chữ: đặt `cross()` cạnh nhãn;
  - nội dung sát mép;
  - hình quan trọng ở 10% dưới cùng (chỗ của phụ đề).

### 3. Dựng dự án

```bash
$PY projects/<slug>/build.py
```

Lệnh này in `N scenes, W words`. Nếu có dòng `!!` (`data-say` không khớp lời thoại, thiếu glyph) thì sửa đến khi sạch.

### 4. Soát hình

```bash
$PY scripts/scene_sheet.py projects/<slug> [--safe]     # --safe: khung an toàn 90% (truyền hình)
```

Xem từng trang ảnh, mỗi trang 12 cảnh, bằng công cụ đọc ảnh. Kiểm tra:

- hình chồng nhau, chữ tràn khung;
- hình bị hiểu sai (ví dụ bát mì bị nhìn thành bát cơm);
- dấu gạch đè chữ, hình quá to bị cắt.

Sửa rồi chạy lại hai bước 3–4. Màu trong ảnh soát có thể khác màu render thật; chỉ dùng ảnh này để soát bố cục.

### 5. Soát giọng (không cần tạo audio)

```bash
$PY scripts/voice_studio.py "<lời thoại của một cảnh>"
```

Mỗi câu được in kèm khoảng nghỉ trước nó, cảm xúc, nhịp ngừng `⟨ms⟩` và cụm được nhấn `*…*`. Duyệt nhanh cả kịch bản: in các câu có cảm xúc khác `neutral` qua `voice_studio.plan_script(...)`.

- Câu giải thích bị đọc thành `climax` / `fast` / `suspense` thì ghim `[bình thường]` hoặc `[chậm]`.
- Thiếu điểm nhấn thì thêm `|` hoặc `*…*`.

### 6. Kiểm tra khớp hình–tiếng

```bash
$PY scripts/make_video.py projects/<slug>/video.json --sync-check
```

Lệnh này tạo giọng (được cache) và lập lịch vẽ, không render. Dòng `sync:` cho biết trung vị bút đặt xuống so với lúc nói cụm từ (nên khoảng −0,2 s) và các phần tử trễ nhất. Trễ hơn khoảng 1,2 s:

- tách câu;
- đưa cụm `data-say` lên sớm hơn;
- giản lược hình nặng.

Đừng chạy hai lệnh `make_video` cùng lúc trên một dự án.

### 7. Xuất bản chính thức

```bash
$PY scripts/make_video.py projects/<slug>/video.json --cleanup
```

Video dài 12 phút mất khoảng 20–25 phút trên CPU; chạy nền và chờ thông báo. Sau đó:

- Đọc `out/<name>-report.json`: thời lượng, `frames == round(durationSec × fps)`, loudness đúng preset.
- Xem `out/*-qa.jpg`.

### 8. Giao

```bash
$PY scripts/share_video.py projects/<slug>/out/<name>-landscape.mp4 --title "Tên video"
$PY scripts/export_script.py projects/<slug>/video.json --notes projects/<slug>/ghi-chu-nguon.md
```

- **Publish video:**
  - Publish `out/share-*/index.html` bằng Artifact tool với `files` của lượt 1, `capabilities: {"downloads": true}`, `icon: "video"` và một câu `description`.
  - Các lượt sau publish lại **cùng file_path**, chỉ kèm `files` còn lại.
  - Kiểm tra bằng `list` với scope `files`: đủ mọi phần.
  - Sửa video sau đó thì publish lại cùng file_path để giữ nguyên link.
- **Gửi file:** gửi `kich-ban-<name>.md` (mốc chương dán vào mô tả YouTube, lời thoại kèm thời điểm) và `out/<name>.srt`.
- **Báo người dùng:**
  - link, thời lượng, mốc chương;
  - những chỗ đã sửa hoặc kiểm chứng so với nguồn;
  - gợi ý tiêu đề và mô tả nếu là YouTube.

### 9. Dọn dẹp

- **Xoá:** `out/share-*/parts`, ảnh soát trong thư mục nháp, `__pycache__`.
- **Cache giọng (`build/voice`):** chỉ giữ khi có thể phải sửa video. Khi đổi `PROSODY_VERSION`, cache cũ trở thành rác.
- **Không xoá video đã giao** nếu người dùng chưa đồng ý.

## Video ngắn (TikTok) và JSON viết tay

- **Video ngắn:** vẫn dùng `Storyboard` với `preset="tiktok"`, 3–6 cảnh.
  - Hoặc `make_video.py --init projects/<slug>` rồi viết `video.json` và SVG bằng tay (mẫu: `examples/demo-bau-troi/`).
  - Khung TikTok toàn màn hình: SVG `viewBox="0 0 1080 1920"`, nội dung ở y 150–1120, chừa y 1150–1400 cho phụ đề (`examples/showcase-gap-giay/`).
- **Ảnh raster thay cho SVG:** `"image": ..., "auto": {"elements": K, "labels": [...]}, "say": [...]`. Ảnh tạo bằng `generate_images.py` (cần API key) hoặc ảnh có sẵn.
- **Giọng thu sẵn + SRT:** `"voice": null, "audio": {"file": "voice.mp3", "srt": "voice.srt"}`, mỗi cảnh có `"cues": [1, 5]`.

## Tuỳ chọn hay dùng

| Muốn | Đặt (trong `Storyboard(config={...})` hoặc `video.json`) |
|---|---|
| Giọng nam khác | `"voice": {"voice": "Thiện Minh"}` (kể chuyện), `"Minh Đức"` (tin tức), `"Thanh Bình"` |
| Nghỉ dài/ngắn hơn toàn bài | `"voice": {"pauseScale": 1.2}` (mặc định trong preset: 1.1) |
| Đọc nhanh hơn | `"voice": {"rate": "+8%"}` |
| Tắt nhịp tự động (giữ dấu `\|`, `*…*`) | `"voice": {"phrasing": false}` |
| Một cảnh đọc khác | `sb.scene(..., voice={"mood": "emotional"})` hoặc `{"style": "ads"}` |
| Nghỉ dài trước một cảnh | `sb.scene(..., pauseBeforeMs=800)` (cảnh mở chương tự có 500) |
| Giọng LLM | `"voice": {"engine": "gemini", "voice": "Sulafat"}` + `GEMINI_API_KEY` |
| Nhạc của bạn | `"music": {"file": "music/bg.mp3", "volumeDb": -20}` |
| Tên kênh trên bút | `$PY scripts/brand_hand.py "Tên Kênh" assets/my-hand.png` → `"render": {"hand": "../../assets/my-hand.png"}` |
| Không có tay / không zoom | `"render": {"hand": false}` / `"render": {"camera": "none"}` |

Schema đầy đủ: [`docs/PROJECT_FORMAT.md`](docs/PROJECT_FORMAT.md).

## Giọng đọc

| Engine | Giọng | Cần | Ghi chú |
|---|---|---|---|
| `vieneu` (mặc định) | Bắc: `Hải Đăng` (mặc định), `Thiện Minh`, `Minh Đức`, `Thanh Bình`, `Mai Anh` (nữ), `Ngọc Linh` (nữ); Nam: `Minh Triết`, `Thùy Dung`; Trung: `Quang Sơn` | `pip install vieneu` (~1 GB model lần đầu) | offline, CPU ~1× thời gian thực. Clone từ `"reference"` cần `"confirmAuthorizedVoice": true` |
| `edge` | `vi-VN-NamMinhNeural`, `vi-VN-HoaiMyNeural` | không | tự dùng khi chưa cài VieNeu |
| `gemini` | `Sulafat`, `Kore`, `Charon`… | `GEMINI_API_KEY` | làm theo `style` bằng lời |
| `elevenlabs` | MinhTrung hoặc Voice Library | `ELEVENLABS_API_KEY` | timestamp ký tự |
| `openai` | `alloy`, `nova`… | `OPENAI_API_KEY` | `OPENAI_BASE_URL` trỏ server tương thích |
| `fish` | model id / clone | `FISH_API_KEY` | **chỉ clone khi chính chủ đồng ý**; không commit giọng mẫu |
| `tiktok` / `makevoice` | – | không | dịch vụ trung gian không chính thức: **chỉ làm nháp** |

Ba tầng điều khiển cách đọc:

1. **Phong cách và cảm xúc:** nhịp nghỉ giữa câu và đoạn; tốc độ, độ to, khoảng nghỉ theo tag.
2. **Khoảng nghỉ theo dấu câu** (`pauseShaping`): mỗi câu được căn từng âm tiết rồi đặt lại khoảng lặng.
   - Dấu phẩy khoảng 170 ms, dấu hai chấm 300 ms.
   - Chỗ ngập ngừng không có dấu câu rút còn tối đa 140 ms.
3. **Đạo diễn nhịp** (`phrasing`): nhịp theo cấu trúc câu và dấu `|`, `*…*` của người viết.

Bảng chi tiết: PROJECT_FORMAT, mục "Nhịp đọc như người dẫn".

## Xử lý sự cố

| Triệu chứng | Cách xử lý |
|---|---|
| `!! data-say … is not in the narration` | sửa cho khớp nguyên văn lời thoại (sau khi bỏ tag, dấu nhịp) |
| `!! Patrick Hand has no '→'` | vẽ bằng `arrow()` hoặc viết chữ |
| phần tử vẽ trễ | `--sync-check`; tách câu, đổi `data-say`, giản lược hình |
| máy đọc sai cảm xúc hoặc thiếu điểm nhấn | `voice_studio.py "…"`; ghim tag, thêm `\|` / `*…*` |
| đọc sai tên riêng | phonemize để kiểm tra, thêm `lexicon` |
| `edge-tts failed … certificate` | `SSL_CERT_FILE` |
| không có mạng | `--engine silent` để dựng nháp đúng nhịp |
| `Killed` khi xuất video dài | thiếu RAM: chạy lại (đã cache); video 15 phút cần ~4 GB |
| `Wave_write` lỗi | hai lệnh `make_video` chạy cùng lúc trên một dự án |
| muốn làm lại từ đầu | `--no-cache` hoặc xoá `build/` |

## Các script

| Script | Việc |
|---|---|
| `make_video.py` | pipeline một lệnh (`--draft`, `--sync-check`, `--cleanup`, `--init`) |
| `storyboard.py` | dựng dự án từ cảnh viết bằng Python + kiểm tra `data-say` / glyph + preset |
| `motifs.py` | khoảng 200 hình mẫu cùng phong cách + `g()`, `chapter()`, `tag()` |
| `scene_sheet.py` | ảnh tổng hợp các cảnh để soát bố cục |
| `voice_studio.py` | xem trước cách đọc: cảm xúc, khoảng nghỉ, nhịp, nhấn |
| `tts.py` | TTS + timestamp từng từ, 9 engine (`--list-voices vieneu`) |
| `export_script.py` | kịch bản có mốc thời gian + chương |
| `share_video.py` | giao video lớn: cắt phần + trang Artifact xem/tải bản gốc |
| `svg_scene.py` | SVG → PNG + annotation nét vector |
| `qa_frames.py` | contact sheet + thông số một video |
| `auto_annotate.py`, `render_annotation_preview.py` | ảnh raster → annotation; ảnh kiểm tra vùng |
| `gen_music.py`, `brand_hand.py`, `generate_images.py` | nhạc nền; tên kênh trên bút; tạo ảnh line-art (tuỳ chọn) |
| `render_stream_whiteboard.py`, `parse_srt.py`, `merge_scenes.py` | quy trình cũ (SRT + ảnh + chỉnh tay) |
