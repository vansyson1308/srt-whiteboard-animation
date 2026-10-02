# Whiteboard Video – vẽ tay + giọng đọc, từ một prompt

Biến **một chủ đề, một kịch bản (kể cả rất dài), hoặc file SRT + giọng thu sẵn** thành video giải thích kiểu whiteboard:

- một bàn tay cầm bút vẽ từng nét **đúng lúc lời thoại nhắc tới**, tô màu, camera bám theo chỗ đang vẽ;
- giọng đọc tiếng Việt **có nhịp như người dẫn chương trình** (ngừng trước điểm nhấn, tách hai vế đối xứng, trình bày luận điểm từng ý);
- phụ đề karaoke, nhạc nền tự tạo, tiếng bút sột soạt;
- xuất **16:9 cho YouTube / truyền hình**, **9:16 cho TikTok/Shorts** và **1:1** từ cùng một dự án.

Repo được thiết kế để **một agent (Claude Code, Codex…) làm trọn một video từ một câu lệnh**: chắt lọc kịch bản, vẽ cảnh bằng SVG, chạy một lệnh ra MP4, tự soát ảnh QA, rồi giao file.

![Demo: Vì sao bầu trời màu xanh?](examples/demo-bau-troi/demo-landscape.gif)

<details><summary>Ví dụ TikTok 9:16: "Lạm phát là gì?" (<code>examples/lam-phat</code>)</summary>

![Lạm phát 9:16](examples/lam-phat/lam-phat-qa.jpg)
</details>

---

## Mục lục

1. [Bắt đầu nhanh](#1-bắt-đầu-nhanh)
2. [Quy trình sản xuất chuẩn](#2-quy-trình-sản-xuất-chuẩn)
3. [Tiêu chuẩn chất lượng](#3-tiêu-chuẩn-chất-lượng)
4. [Một dự án gồm những gì](#4-một-dự-án-gồm-những-gì)
5. [Pipeline hoạt động thế nào](#5-pipeline-hoạt-động-thế-nào)
6. [Giọng đọc và nhịp đọc](#6-giọng-đọc-và-nhịp-đọc)
7. [Nét vẽ và đồng bộ](#7-nét-vẽ-và-đồng-bộ)
8. [Âm thanh, phụ đề, định dạng xuất](#8-âm-thanh-phụ-đề-định-dạng-xuất)
9. [Giao video và dọn dẹp](#9-giao-video-và-dọn-dẹp)
10. [Dành cho người phát triển](#10-dành-cho-người-phát-triển)
11. [Xử lý sự cố](#11-xử-lý-sự-cố)
12. [Cấu trúc repo](#12-cấu-trúc-repo)

---

## 1. Bắt đầu nhanh

### Nhờ agent (khuyên dùng)

Mở repo trong Claude Code / Codex và nói, ví dụ:

> Làm video TikTok 60 giây giải thích lạm phát là gì, dễ hiểu, giọng nam.

> Đây là kịch bản dài của tôi. Chắt lọc phần tinh túy nhất rồi làm video YouTube khoảng 12 phút.

> Tôi có file `giong.mp3` và `phu-de.srt`, biến nó thành video vẽ tay 16:9.

Agent đọc [`AGENTS.md`](AGENTS.md) / [`CLAUDE.md`](CLAUDE.md) rồi làm theo [`SKILL.md`](SKILL.md) – quy trình chi tiết từng bước.

### Tự chạy

```bash
python scripts/prepare_env.py          # lần đầu: tạo .venv, cài thư viện (không cần ffmpeg)
PY=.venv/bin/python                    # Windows: .venv\Scripts\python.exe

$PY examples/storyboard-mau/build.py                              # sinh cảnh + video.json từ file Python
$PY scripts/scene_sheet.py examples/storyboard-mau                # soát bố cục mọi cảnh
$PY scripts/make_video.py examples/storyboard-mau/video.json --draft   # nháp nhanh
$PY scripts/make_video.py examples/storyboard-mau/video.json           # bản chính thức
```

| Tuỳ chọn `make_video.py` | Tác dụng |
|---|---|
| `--draft` | nửa độ phân giải, 15 fps – xem nhanh |
| `--sync-check` | chỉ tạo giọng + lập lịch, báo hình có khớp tiếng không (không render) |
| `--cleanup` | sau khi xuất, xoá bản render từng cảnh và ảnh trung gian (giữ cache giọng, nhạc) |
| `--formats portrait,landscape,square` | chọn định dạng xuất |
| `--scenes scene-02,scene-05` | chỉ làm lại vài cảnh |
| `--engine silent` | không gọi TTS: dựng nháp đúng nhịp khi không có mạng |
| `--no-cache` | xoá `build/`, làm lại từ đầu |
| `--init projects/<tên>` | tạo khung dự án tối thiểu (JSON viết tay) |

Mọi script in `OUTPUT=<đường dẫn>` ở dòng cuối.

---

## 2. Quy trình sản xuất chuẩn

Đây là quy trình đã dùng cho các video dài 10–15 phút (YouTube, truyền hình). Video ngắn đi cùng đường, chỉ ít cảnh hơn.

| # | Bước | Công cụ | Kết quả |
|---|---|---|---|
| 1 | **Chắt lọc + kiểm chứng** nội dung nguồn | đọc, tra cứu | dàn ý: hook, vòng mở, các phần, kết |
| 2 | **Viết kịch bản + vẽ cảnh** trong một file Python | `motifs.py`, `storyboard.py` | `projects/<tên>/build.py` |
| 3 | **Dựng dự án** + kiểm tra tự động | `python build.py` | `scenes/*.svg`, `video.json`, `kich-ban-rut-gon.md` |
| 4 | **Soát hình** | `scene_sheet.py` | ảnh tổng hợp 12 cảnh/trang |
| 5 | **Soát giọng** (cảm xúc, nhịp) | `voice_studio.py "…"` | sửa tag cảm xúc / dấu nhịp |
| 6 | **Kiểm tra khớp hình–tiếng** | `make_video.py --sync-check` | trung vị, các phần tử trễ nhất |
| 7 | **Xuất bản chính thức** | `make_video.py --cleanup` | MP4, SRT, QA, report |
| 8 | **Giao** video + kịch bản có mốc thời gian | `share_video.py`, `export_script.py` | trang xem/tải, `kich-ban-<tên>.md` |
| 9 | **Dọn dẹp** | xoá `out/share-*/parts`, file nháp | máy gọn cho video sau |

Chi tiết từng bước, lệnh cụ thể và mẹo: [`SKILL.md`](SKILL.md).

---

## 3. Tiêu chuẩn chất lượng

### Kịch bản

- **Cấu trúc:**
  - Câu đầu là **hook**, hiểu được trong 2 giây.
  - Tiếp theo là **vòng mở**: nhá trước 3–4 điều sẽ có trong video.
  - Sau đó là **thẻ tiêu đề**.
  - Nội dung chia **chương "PHẦN n"**, mỗi chương 4–8 cảnh.
  - Phần **kết quay lại hook**, rồi lời kêu gọi hợp nền tảng. YouTube: chia sẻ, bình luận. Truyền hình: lời cảm ơn, không kêu gọi đăng ký.
- **Mỗi cảnh một ý**, 40–70 từ (video dài) hoặc 25–60 từ (TikTok).
  - Câu ngắn, văn nói.
  - Viết số thành chữ khi muốn đọc tự nhiên ("một một một", "năm một chín bảy chín").
- **Kiểm chứng:**
  - Mọi số liệu, trích dẫn, tên người, năm đều phải được tra lại.
  - Sửa lỗi của bản nguồn. Nói rõ đâu là truyền thuyết, đâu là chú giải.
  - Ghi nguồn vào ghi chú kèm kịch bản, không đọc trích dẫn dày đặc trong video.
- **Biên tập:**
  - Cân bằng, tôn trọng.
  - Không mô tả chi tiết bạo lực hay tình dục, không quy chụp nhóm người.
  - Chủ đề trẻ em, sức khỏe tâm thần: nhắc kênh hỗ trợ (ví dụ Tổng đài 111).
- **Tên riêng nước ngoài:** viết đúng chính tả gốc. Kiểm tra cách đọc, chỉ thêm `lexicon` khi máy đọc sai (xem §6).

### Hình

- **Số phần tử:** 3–5 phần tử nhẹ mỗi cảnh. Hình nặng (đám đông, nhiều chữ) làm bút vẽ chậm, cảnh bị kéo dài.
- **`data-say`:** 1–3 từ, **nguyên văn** trong lời thoại của cảnh. Phần tử đầu tiên gắn với những chữ đầu của lời thoại.
- **Chữ trên hình:** nhãn ngắn. Chỉ dùng ký tự có trong font Patrick Hand: mũi tên phải vẽ bằng `arrow()`, không gõ "→".
- **Dấu gạch chéo:** đặt cạnh nhãn, không đè lên chữ.
- **Vùng trống:** chừa khoảng 10% phía dưới cho phụ đề. Truyền hình: giữ nội dung trong vùng an toàn 90% (`scene_sheet.py --safe`).

### Giọng và đồng bộ

- **Tag cảm xúc:** 1–3 tag mỗi cảnh. Câu giải thích bị máy đọc nhầm thành cao trào hoặc đọc nhanh thì ghim lại bằng `[bình thường]` hoặc `[chậm]`.
- **Nhịp đọc:** đặt dấu câu theo ý. Chỉ thêm `|` hoặc `*nhấn*` ở chỗ cấu trúc câu không tự cho thấy điểm nhấn (§6).
- **`--sync-check`:** trung vị bút đặt xuống so với lời nói khoảng −0,2 s, không phần tử nào trễ quá khoảng 1,2 s.

### Kỹ thuật

- **Số khung hình:** mỗi cảnh có đúng `round(ms × fps / 1000)` khung hình.
- **Âm lượng:** −14 LUFS cho web, −23 LUFS / 25 khung hình/giây cho truyền hình (preset `broadcast`).
- **Bản giao:** gồm MP4, SRT và kịch bản có mốc thời gian.

---

## 4. Một dự án gồm những gì

```text
projects/<tên>/
  build.py            kịch bản + cảnh viết bằng Python (Storyboard) – nguồn của mọi thứ dưới đây
  video.json          cấu hình + lời thoại từng cảnh (sinh ra; có thể viết tay cho video ngắn)
  scenes/scene-NN.svg cảnh vẽ
  kich-ban-rut-gon.md kịch bản đọc được, theo chương
  build/              cache (giọng, nhạc, render) – xoá lúc nào cũng được
  out/                MP4, SRT, QA, report
```

`projects/` là thư mục làm việc riêng: **không commit** nội dung của người dùng, giọng mẫu hay video vào repo.

Viết một dự án bằng `Storyboard` (mẫu đầy đủ: [`examples/storyboard-mau/build.py`](examples/storyboard-mau/build.py)):

```python
from motifs import *
from storyboard import Storyboard

sb = Storyboard(__file__, "Vì sao cần ngủ đủ giấc?", preset="youtube")   # youtube | broadcast | tiktok
sb.scene("[hồi hộp] Thức trắng một đêm, não bạn hoạt động gần giống một người đã uống rượu.",
         "Hook",
         g("night", "Thức trắng", "Thức trắng", moon(300, 300, 90), person(300, 760, 1.1, "sad")),
         g("brain", "Như say rượu", "uống rượu", brain(800, 420, 1.0), cup(980, 700, 0.8)))
sb.scene("Câu trả lời: | trong giấc ngủ sâu, não *tự dọn rác*.", "Phần 1",
         g("chap", "Phần 1", "Câu trả lời", chapter(1, "Não tự dọn rác")), ...)
sys.exit(sb.build())
```

- `g(id, nhãn, data-say, *hình)` là một phần tử. Nó được vẽ khi giọng đọc nói tới `data-say`.
- **`motifs.py`** có khoảng 200 hình mẫu cùng một phong cách:
  - người: `person`, `woman`, `kid`, `teen`, `parent`, `monk`, `sage`;
  - đồ vật, biểu tượng: `book`, `scroll`, `phone`, `laptop`, `scale`, `ledger`;
  - chữ và bố cục: `chapter`, `tag`, `speech`, `thought`, `arrow`, `check`, `cross`.
- **`build()`** kiểm tra hai lỗi hay gặp: `data-say` không có trong lời thoại, và ký tự không có trong font. Gặp lỗi, nó trả mã lỗi 1.
- **Chương:** cảnh mở bằng `chapter()` được đặt tên chương và tự có nhịp nghỉ dài hơn trước nó.

Schema đầy đủ: [`docs/PROJECT_FORMAT.md`](docs/PROJECT_FORMAT.md). Quy ước vẽ: [`docs/SVG_GUIDE.md`](docs/SVG_GUIDE.md).

| File trong `out/` | Nội dung |
|---|---|
| `<tên>-landscape.mp4` / `-portrait.mp4` / `-square.mp4` | H.264 + AAC |
| `<tên>.srt` | phụ đề theo từng từ đã đọc |
| `<tên>-<định dạng>-qa.jpg` | 12 khung hình để kiểm tra nhanh |
| `<tên>-report.json` | thời lượng từng cảnh, loudness, đỉnh âm, số khung, chỉ số đồng bộ |
| `<tên>-sync.json` | (khi `--sync-check`) độ lệch bút–lời của từng phần tử |

---

## 5. Pipeline hoạt động thế nào

```text
video.json
  ├─ 1. scenes   SVG → PNG + nét vector (svg_scene.py) · ảnh raster → tự chia vùng (auto_annotate.py)
  ├─ 2. voice    TTS từng câu → chuẩn hoá khoảng nghỉ → nhịp đọc → timestamp từng từ (tts.py, voice_studio.py)
  ├─ 3. sync     phần tử bắt đầu vẽ khi cụm data-say được đọc, theo thứ tự được nói (timing.py)
  ├─ 4. render   vẽ từng cảnh song song: nét bút, tô màu, bàn tay, camera (render_stream_whiteboard.py)
  ├─ 5. audio    giọng + nhạc nền (tự hạ khi có giọng) + tiếng bút → chuẩn hoá loudness
  └─ 6. compose  ghép cảnh, chuyển cảnh, phụ đề karaoke, xuất từng định dạng + QA
```

Hai bất biến luôn được giữ:

1. Phần tử chưa tới lượt không bao giờ lộ pixel nào.
2. Mỗi cảnh có đúng `round(ms × fps / 1000)` khung hình và số mẫu âm thanh khớp tuyệt đối, nên tiếng và hình không bao giờ trôi lệch nhau.

Mọi bước đều cache theo nội dung trong `build/`. Sửa một cảnh thì chỉ cảnh đó được làm lại.

---

## 6. Giọng đọc và nhịp đọc

### Engine

| Engine | Cần | Ghi chú |
|---|---|---|
| `vieneu` (mặc định) | không (cài qua `prepare_env`) | offline, CPU, Apache-2.0. Giọng nam **Hải Đăng** (mặc định), Thiện Minh, Minh Đức, Thanh Bình; nữ Mai Anh, Ngọc Linh… |
| `edge` | không | HoaiMy / NamMinh, timestamp thật; tự dùng khi chưa cài VieNeu |
| `gemini` | `GEMINI_API_KEY` | giọng LLM, làm theo chỉ dẫn phong cách |
| `elevenlabs` | `ELEVENLABS_API_KEY` | timestamp ký tự |
| `openai` | `OPENAI_API_KEY` | `OPENAI_BASE_URL` trỏ tới server tương thích |
| `fish` | `FISH_API_KEY` | clone giọng **chỉ khi chính chủ đồng ý** (`"confirmAuthorizedVoice": true`) |
| `tiktok` / `makevoice` | không | dịch vụ trung gian không chính thức: chỉ dùng làm nháp |
| `silent` | không | im lặng, để thử nhịp |
| giọng thu sẵn | – | `"voice": null, "audio": {"file": "giong.mp3", "srt": "phu-de.srt"}` |

Danh sách giọng: `$PY scripts/tts.py --list-voices vieneu`.

### Ba tầng điều khiển cách đọc

**1. Phong cách và cảm xúc** (`voice_studio.py`)

- **Phong cách (`style`):** `natural`, `news`, `story`, `podcast`, `ads`. Phong cách quyết định nhịp nghỉ giữa các câu và giữa các đoạn.
- **Cảm xúc từng câu:** đặt tag ở đầu câu: `[hồi hộp]`, `[cao trào]`, `[xúc động]`, `[chậm]`, `[nhanh]`, `[vui]`, `[bình thường]`. Không có tag thì hệ thống tự đọc cảm xúc từ từ ngữ.
  - Tag cảm xúc quyết định tốc độ, độ to và khoảng nghỉ quanh câu.
  - Khoảng nghỉ dài chỉ đến khi cảm xúc **đổi**, không lặp lại sau mỗi câu.
  - Với VieNeu, cao độ không bị dịch, để giữ nguyên chất giọng.

**2. Khoảng nghỉ theo dấu câu** (`"pauseShaping": true`, mặc định)

Giọng sinh bằng mô hình (VieNeu…) tự quyết độ dài từng khoảng lặng. Sau khi đọc mỗi câu, hệ thống căn từng âm tiết vào audio, rồi đặt lại khoảng lặng theo dấu câu:

| Dấu câu / chỗ ngắt | Khoảng nghỉ |
|---|---|
| dấu phẩy | khoảng 170 ms (vế 1–2 chữ 120 ms, sau vế dài 230 ms) |
| `:` | 300 ms |
| `;` | 280 ms |
| ngập ngừng không có dấu câu | rút còn tối đa 140 ms |

Phần lời nói không bị động tới, chỉ khoảng lặng được chỉnh.

**3. Đạo diễn nhịp** (`"phrasing": true`, mặc định)

Hệ thống đọc cấu trúc câu và tự đặt nhịp như người dẫn:

| Cấu trúc | Ví dụ | Cách đọc |
|---|---|---|
| điểm nhấn sau câu dẫn | "chỉ có bốn chữ: **con ghét bố mẹ**" | dừng ~420 ms, cụm chốt đọc chậm hơn ~7% |
| mở đầu luận điểm / danh sách | "ba cái bẫy:", "như sau:" | dừng ~450 ms |
| đầu mục | "Thứ nhất:", "Kết quả:" | dừng ~380 ms, nghỉ thêm trước mỗi mục |
| hai vế đối xứng | "Người lớn đọc… / Người trẻ đọc…" | nghỉ thêm trước vế sau |
| tương phản | "…, còn …", "không phải A / mà là B" | một nhịp ngắt |
| liệt kê | "khóc, gào, đòi hỏi" | từng mục, ~240 ms |
| câu chốt ngắn sau câu dài | | nghỉ thêm trước nó |

Chỗ máy không tự thấy, người viết đánh dấu trong lời thoại. Các dấu này không hiện trong phụ đề:

- `|`: một nhịp ngừng (~320 ms);
- `||`: ngừng dài (~600 ms);
- `*cụm từ*`: nhấn – ngừng trước cụm đó và đọc nó chậm hơn.

Xem trước cách đọc mà không cần tạo giọng:

```bash
$PY scripts/voice_studio.py "Tên nhóm chỉ có bốn chữ: con ghét bố mẹ. Người lớn đọc… Người trẻ đọc…"
# [    0 ms] … Tên nhóm chỉ có bốn chữ: ⟨420⟩ *con* *ghét* *bố* *mẹ.*
# [  620 ms] … Người trẻ đọc bốn chữ ấy, …
```

### Phát âm

- **Tên riêng nước ngoài:** viết đúng chính tả gốc (Einstein, Carl Jung…). VieNeu tự đọc kiểu Anh.
- **`lexicon`:** chỉ thêm khi máy đọc sai, ví dụ `{"MBTI": "em bi ti ai", "Sartre": "Xác tơ"}`. Kiểm tra cách đọc:

  ```bash
  $PY -c "from vieneu_utils.phonemize_text import phonemize_text_with_emotions as p; print(p('Sartre'))"
  ```

- **Đọc lại câu lỗi:** câu nào đọc lan man hoặc nuốt chữ được đọc lại, giữ bản tốt nhất (`VIENEU_TAKES`, mặc định 3).
- **`"fx": "broadcast"`:** lọc ù, làm rõ tiếng, nén nhẹ.

---

## 7. Nét vẽ và đồng bộ

- **Bút đi theo nét vector thật** của SVG; chữ được "viết tay" từ trái sang phải.
- **Thứ tự vẽ là thứ tự được nói:**
  - Phần tử vẽ theo thứ tự cụm `data-say` xuất hiện trong lời thoại, không theo thứ tự trong file.
  - Phần tử đầu tiên bắt đầu không sớm hơn cụm từ của nó quá 1,5 s.
- **Nhịp tay người:** bút tăng tốc đầu nét, chậm ở góc và cuối nét, dừng một nhịp khi đặt và nhấc bút.
- **Chờ giữa hai phần tử:** vẽ xong mà chưa tới phần tử sau thì tay rút khỏi khung. Hình `data-filler="1"` được vẽ vào khoảng chờ đó.
- **Nhịp chuyển cảnh:**
  - Cảnh kết thúc tối đa `tailMs + maxHoldMs` (700 + 500 ms) sau từ cuối cùng. Nét cuối nếu chậm sẽ được vẽ nhanh hơn một chút thay vì để giọng chờ.
  - `pauseBeforeMs` cho cảnh mở chương mới nghỉ dài hơn.
- **Camera `follow`:** zoom mượt vào chỗ đang vẽ, lùi ra toàn cảnh ở cuối cảnh.
- **Bàn tay:** mặc định không có chữ. `brand_hand.py "Tên kênh"` in tên kênh lên bút.

---

## 8. Âm thanh, phụ đề, định dạng xuất

| Preset (`Storyboard`) | Định dạng | fps | Loudness | Ghi chú |
|---|---|---|---|---|
| `youtube` | 16:9 1080p | 30 | −14 LUFS | mặc định |
| `broadcast` | 16:9 1080p | 25 | −23 LUFS (EBU R128) | truyền hình; giữ nội dung trong vùng an toàn 90% |
| `tiktok` | 9:16 | 30 | −14 LUFS | phụ đề 6 từ/dòng |

- **Nhạc nền:** tự tạo, không lo bản quyền (`"music": {"generate": "calm" | "bright"}`), hoặc dùng file của bạn. Nhạc tự hạ khi có giọng.
- **Tiếng bút:** tổng hợp, chỉ phát khi đang vẽ.
- **Phụ đề karaoke:** font Be Vietnam Pro, nằm trong vùng an toàn. Mood tag và dấu nhịp không bao giờ hiện trong phụ đề.

---

## 9. Giao video và dọn dẹp

```bash
$PY scripts/share_video.py projects/<tên>/out/<tên>-landscape.mp4 --title "Tên video"
$PY scripts/export_script.py projects/<tên>/video.json [--notes ghi-chu-nguon.md]
```

- **`share_video.py`:**
  - Cắt video thành các phần ≤ 14 MB, không nén lại, rồi tạo `index.html`.
  - Agent publish trang này thành Artifact riêng tư với `capabilities: {"downloads": true}`. Mỗi lượt tối đa khoảng 60 MB; các lượt sau dùng **cùng file_path** để cộng dồn file.
  - Trang tự ghép các phần, kiểm tra SHA-256, phát video và cho tải bản gốc.
- **`export_script.py`:** tạo `kich-ban-<tên>.md`, gồm mốc chương dán thẳng vào mô tả YouTube và lời thoại từng cảnh kèm thời điểm. Giao kèm file `.srt`.
- **Dọn dẹp:** dùng `--cleanup` khi xuất. Sau khi publish, xoá `out/share-*/parts` và file nháp. Cache giọng chỉ nên giữ nếu có thể phải sửa video.

---

## 10. Dành cho người phát triển

- **Đọc trước:** [`SKILL.md`](SKILL.md), [`docs/PROJECT_FORMAT.md`](docs/PROJECT_FORMAT.md), [`docs/SVG_GUIDE.md`](docs/SVG_GUIDE.md), [`docs/RESEARCH.md`](docs/RESEARCH.md) (nghiên cứu và lộ trình).
- **Quy ước code:**
  - Python 3.10+. Dùng PyAV, không cần ffmpeg hệ thống.
  - Thời gian tính bằng ms, toạ độ annotation là pixel nguyên.
  - Mỗi script in `OUTPUT=` ở dòng cuối.
- **Bất biến của renderer:** giữ hai bất biến ở §5 khi sửa renderer.
- **Cache giọng:** khoá cache gồm `tts.PROSODY_VERSION`. Tăng số này khi đổi cách lập kế hoạch giọng, nhịp, DSP hoặc chuẩn hoá khoảng nghỉ.
- **Test:** chạy offline, khoảng 40 giây. Chạy trước mọi commit sửa `scripts/`:

  ```bash
  $PY -m pytest -q tests
  ```

- **Quy trình cũ** (SRT + ảnh + chỉnh tay) vẫn dùng được: `parse_srt.py` → `auto_annotate.py` / `assets/preview.html` → `render_stream_whiteboard.py`.

---

## 11. Xử lý sự cố

| Triệu chứng | Cách xử lý |
|---|---|
| `build.py` báo `data-say … is not in the narration` | sửa cho khớp **nguyên văn** lời thoại (sau khi bỏ tag / dấu nhịp) |
| `build.py` báo `Patrick Hand has no '→'` | vẽ bằng `arrow()` hoặc viết chữ |
| phần tử vẽ sai lúc / trễ | xem log `-- sync` hoặc `--sync-check`; tách câu, đổi `data-say`, giản lược hình nặng |
| máy đọc sai cảm xúc | `voice_studio.py "…"` để xem; ghim `[bình thường]` / `[chậm]` |
| đọc sai tên riêng | kiểm tra bằng phonemize (§6), thêm `lexicon` |
| `edge-tts failed … certificate` | đặt `SSL_CERT_FILE=<ca-bundle>` |
| không có mạng | `--engine silent` để dựng nháp đúng nhịp |
| video quá lớn để gửi qua chat | `share_video.py` (§9) |
| tiến trình bị `Killed` khi xuất video dài | thiếu RAM: chạy lại (đã có cache); video 15 phút cần khoảng 4 GB ở bước trộn |
| `Wave_write` lỗi khi chạy | đừng chạy hai lệnh `make_video` cùng lúc trên một dự án |
| muốn làm lại từ đầu | `--no-cache` hoặc xoá `build/` |

---

## 12. Cấu trúc repo

```text
scripts/
  make_video.py                 pipeline một lệnh
  storyboard.py  motifs.py      viết dự án bằng Python: cảnh, kiểm tra, ~200 hình mẫu chung
  scene_sheet.py                ảnh tổng hợp các cảnh để soát bố cục
  export_script.py              kịch bản có mốc thời gian + chương
  share_video.py                giao video lớn: cắt phần + trang xem/tải bản gốc
  tts.py  voice_studio.py       giọng đọc: engine, phong cách, cảm xúc, khoảng nghỉ, đạo diễn nhịp
  timing.py                     đồng bộ phần tử theo lời nói
  render_stream_whiteboard.py   renderer: mask choreography, nét liên tục, nhịp tay người, camera
  svg_scene.py  auto_annotate.py
  captions.py  wb_video.py  gen_music.py  qa_frames.py
  brand_hand.py  generate_images.py  render_annotation_preview.py
  stream_render.py  parse_srt.py  merge_scenes.py  prepare_env.py
assets/     bàn tay, font tiếng Việt (OFL), preview.html
examples/   storyboard-mau (mẫu dự án Python) · demo-bau-troi · showcase-gap-giay · lam-phat
docs/       PROJECT_FORMAT.md · SVG_GUIDE.md · RESEARCH.md
tests/      bộ test chạy offline
```

## Ghi công & giấy phép

Fork từ skill `srt-whiteboard-animation` gốc (MIT) của tác giả "江哥是老登啊". Ý tưởng mask choreography + stream strokes và ảnh ví dụ con khỉ thuộc về tác giả gốc.

- **Voice Studio:** port từ [ttspromax](https://github.com/vansyson1308/ttspromax).
- **VieNeu-TTS:** Apache-2.0.
- **Font Be Vietnam Pro và Patrick Hand:** SIL Open Font License (`assets/fonts/OFL-*.txt`).
- **Mã nguồn repo:** MIT, xem [LICENSE](LICENSE).
