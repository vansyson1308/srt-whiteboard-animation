# Định dạng dự án `video.json`

Một thư mục dự án = một video. Mọi đường dẫn là tương đối so với `video.json`. Kết quả nằm ở `out/`, cache ở `build/` (xoá được bất cứ lúc nào).

```json
{
  "title": "Vì sao bầu trời màu xanh?",
  "name": "vi-sao-bau-troi",                 // tên file đầu ra (mặc định: slug của title)
  "formats": ["portrait", "landscape"],      // portrait 1080x1920, landscape 1920x1080, square 1080x1080
  "fps": 30,

  "voice": {                                 // TTS theo từng cảnh (null = không đọc)
    "engine": "vieneu",                      // vieneu (mặc định) | edge | gemini | elevenlabs | openai | fish | tiktok | makevoice | silent
    "voice": "Hải Đăng",                     // giọng nam VieNeu; Thiện Minh, Minh Đức… / vi-VN-NamMinhNeural (edge) / Sulafat (gemini)
    "style": "natural",                      // natural | news | story | podcast | ads | plain (đọc một lượt)
    "rate": "+5%", "pitch": "+0Hz",          // cộng thêm vào phong cách (edge)
    "pauseScale": 1.0,                       // nhân độ dài khoảng lặng tự động (0.3–3)
    "pauseShaping": true,                    // vieneu/tiktok/makevoice/fish: khoảng nghỉ trong câu theo dấu câu (xem dưới)
    "chunk": null,                           // "sentence" | "paragraph": mỗi request một câu hay cả đoạn (mặc định theo engine)
    "fx": "broadcast",                       // xử lý giọng kiểu phát thanh (lọc ù, rõ tiếng, nén nhẹ); "none" để tắt
    "mood": null,                            // cảm xúc mặc định: fast | slow | climax | emotional | suspense | happy | neutral
    "expressiveness": 1.0,                   // độ đậm của điều tiết cảm xúc: 0 = đọc phẳng … 1 = mặc định … 2 = rất đậm
    "autoMood": true,                        // tự đọc cảm xúc từng câu từ nội dung (tag [cao trào]… luôn thắng)
    "lexicon": {"GPT": "gi pi ti"},          // cách đọc từ viết tắt; tên tiếng Anh để nguyên (VieNeu tự đọc kiểu Anh)
    "instructions": null,                    // gemini/openai: tự mô tả giọng điệu (thay cho style)
    "reference": null, "referenceText": null, "confirmAuthorizedVoice": false   // fish: clone giọng có sự đồng ý
  },
  "audio": null,                             // HOẶC giọng thu sẵn: {"file": "voice.mp3", "srt": "voice.srt", "words": "words.json"}

  "captions": { "enabled": true, "karaoke": true, "maxWords": 6, "uppercase": false,
                "box": false, "highlight": "#FFD60A", "size": 0 },
  "header": { "text": "Tiêu đề hiện ở bản dọc" },   // false để tắt; mặc định = title
  "music":  { "file": "music/nhac-nen.mp3", "volumeDb": -20, "duck": true, "duckDb": -8 },
                                             // hoặc {"generate": "calm"|"bright"} = nhạc tự tạo, không bản quyền
  "sfx":    { "pen": false, "volumeDb": -23 },      // tiếng bút sột soạt khi vẽ: mặc định TẮT, đặt "pen": true để bật lại
  "render": { "inkPath": "skeleton", "colorFill": "contour-wipe", "camera": "follow",
              "cameraMaxZoom": 1.2, "paper": "#F6F1E3", "hand": null, "handHeightRatio": 0.42,
              "humanMotion": true,                  // nhịp tay người: chậm ở góc/cuối nét, dừng khi đặt/nhấc bút
              "penLift": 14,                        // px (ở 1080p) bàn tay nhấc lên khi di chuyển giữa các nét
              "idleHand": "exit",                   // exit: vẽ đúng tốc độ tự nhiên rồi rút tay ra khỏi khung khi chờ
                                                    //   (data-filler lấp khoảng nghỉ) | stretch: kéo dài nét cho kín thời gian
              "drawSpeed": 1100 },                  // tốc độ bút tự nhiên, px/giây ở 1080p
  "sync":   { "leadMs": 250, "voiceDelayMs": 200, "minDrawMs": 900, "maxDrawMs": 4500, "tailMs": 700,
              "maxHoldMs": 500 },                   // cảnh kết thúc tối đa tailMs + maxHoldMs sau từ cuối cùng
  "transition": { "type": "fade", "ms": 350 },      // fade | slide | cut
  "audio_master": { "lufs": -14 },

  "scenes": [
    { "id": "scene-01", "svg": "scenes/scene-01.svg",
      "narration": "Lời thoại của cảnh 1…" },

    { "id": "scene-02", "image": "scenes/scene-02.png",           // ảnh raster + annotation có sẵn
      "annotation": "scenes/scene-02.annotation.json",
      "narration": "…" },

    { "id": "scene-03", "image": "scenes/scene-03.png",           // ảnh raster, tự chia vùng
      "auto": { "elements": 4, "order": "reading",
                "labels": ["Núi", "Khỉ lớn", "Khỉ nhỏ", "Trẻ em"] },
      "say": ["ngọn núi", "con khỉ lớn", "khỉ nhỏ", "các bạn nhỏ"],
      "narration": "…" }
  ]
}
```

(JSON thật không có comment – bản trên chỉ để giải thích.)

## Các trường của cảnh

| Trường | Ý nghĩa |
|---|---|
| `svg` | Cảnh do agent vẽ – xem [SVG_GUIDE.md](SVG_GUIDE.md). Tốt nhất. |
| `image` + `annotation` | Ảnh raster + annotation (tạo tay / preview.html). |
| `image` + `auto` | Tự chia vùng bằng `auto_annotate.py`. |
| `narration` | Lời thoại của cảnh (chế độ TTS). Có thể chèn `[pause 800ms]`, `[ngắt 1s]` và tag cảm xúc `[cao trào]`, `[xúc động]`… (xem dưới) – không hiện trong phụ đề. |
| `voice` | Ghi đè giọng cho riêng cảnh này, ví dụ `{"style": "ads"}`, `{"mood": "emotional"}` hoặc `{"engine": "tiktok"}`. |
| `say` | Danh sách cụm từ kích hoạt, gán lần lượt cho các phần tử chưa có `say`. |
| `cues` | `[đầu, cuối]` (đánh số từ 1) – các câu SRT thuộc cảnh này (chế độ `audio`). |
| `keepTiming` | `true` = giữ nguyên thời gian trong annotation, không đồng bộ theo giọng. |
| `minMs` | Độ dài tối thiểu của cảnh. |
| `pauseBeforeMs` | Nghỉ thêm trước lời đọc của cảnh này, ví dụ `500` khi sang chương mới. |
| `chapter` | Tên chương mà cảnh này mở đầu (vd. `"Phần 1: Hiểu chính mình"`); `storyboard.py` tự đặt từ bảng `chapter()`, `export_script.py` dùng để in mốc chương. Không ảnh hưởng tới render. |

## Nhịp đọc như người dẫn

Giọng VieNeu (và tiktok, makevoice, fish) tự quyết độ dài từng khoảng lặng, nên cùng một dấu phẩy có lúc lướt qua, có lúc dừng lâu hơn cả giữa hai câu. Với `"pauseShaping": true` (mặc định), mỗi câu sau khi đọc được đo lại: khoảng lặng được ghép với dấu câu (DP trên trục thời gian có tiếng), rồi đặt lại độ dài theo dấu câu, nhân `pauseScale` và nhịp của cảm xúc:

| Chỗ ngắt | Độ dài |
|---|---|
| dấu phẩy | 170 ms; 120 ms khi một vế chỉ 1–2 từ ("thật ra,"); 230 ms sau một vế dài ≥ 8 từ |
| `;` / `—` | 280 / 260 ms |
| `:` | 300 ms – nhịp chờ trước điều sắp nói; mở ra cả khi giọng đọc lướt qua |
| `…` giữa câu | 380 ms |
| khoảng lặng không có dấu câu (ngập ngừng) | rút còn tối đa 140 ms |

### Đạo diễn nhịp: ngắt theo ý, không chỉ theo dấu câu

Dấu câu cho biết câu *có thể* ngắt ở đâu; người dẫn còn chọn chỗ *nên* dừng. `voice_studio.py` đọc cấu trúc của từng câu và từng cặp câu, đặt thêm những nhịp ấy. Ở chỗ không có dấu câu, nó thêm dấu phẩy vào lời đọc (không vào phụ đề), để giọng tự khép cụm từ; độ dài nhịp vẫn đặt lại sau khi đọc như trên:

| Cấu trúc | Ví dụ | Cách đọc |
|---|---|---|
| Điểm nhấn sau câu dẫn | "Tên nhóm chỉ có bốn chữ: **con ghét bố mẹ**." · "…đó là **…**" | dừng 420 ms rồi đọc cụm chốt chậm hơn ~7 %. Không dừng sau "nghĩa là / tức là" (lời giải nghĩa đọc liền), sau phủ định ("không chỉ là"), hay khi vừa ngừng ở dấu câu ngay trước |
| Mở đầu một danh sách / luận điểm | "…ba cái bẫy: …", "…như sau: …" | dừng 450 ms |
| Đầu mục ngắn | "Thứ nhất: …", "Kết quả: …" | dừng 380 ms; câu mở bằng "Thứ hai", "Dấu hiệu thứ ba"… nghỉ thêm 250 ms trước nó |
| Hai vế đối xứng | "Người lớn đọc… **/** Người trẻ đọc…" · "Có người…, có người…" | nghỉ thêm 220 ms giữa hai câu, 260 ms giữa hai vế trong một câu |
| Tương phản | "…, còn …", "…, nhưng …", "không phải A **/** mà là B" | 280 / 220 ms |
| Liệt kê | "khóc, gào, đòi hỏi" (≥ 3 mục ngắn) | mỗi dấu phẩy 240 ms |
| Câu chốt | câu ≤ 7 từ ngay sau một câu dài | nghỉ thêm 150 ms trước nó |

Chỗ máy không tự thấy, người viết kịch bản đánh dấu thẳng trong `narration` (không hiện trong phụ đề):

- `|`: một nhịp ngừng (~320 ms); `||`: nhịp ngừng dài (~600 ms).
- `*cụm từ*`: nhấn: đọc cụm đó chậm hơn một chút. Chỉ ngừng trước nó khi từ ngay trước là "là" / "rằng" (từ báo trước điểm nhấn); chỗ khác muốn dừng thì viết thêm `|`, vì ngừng giữa một cụm ("giống | lớp đường") nghe như người đọc bị vấp.

Ví dụ: `Họ không tìm thấy một kẻ thù. | Họ tìm thấy *chính mình*.` Xem trước kế hoạch: `python scripts/voice_studio.py "…"` (trường `breaks`, `emph` của từng câu). `"phrasing": false` tắt phần tự nhận diện; dấu `|`, `*…*` vẫn có hiệu lực.

Giữa các câu là khoảng nghỉ theo phong cách; khoảng nghỉ dài của cảm xúc (hồi hộp, xúc động…) chỉ đến khi cảm xúc đổi, không lặp lại sau mỗi câu, và tối đa 1 giây. Giữa hai cảnh là một nhịp ngắt đoạn: cảnh kết thúc tối đa `tailMs + maxHoldMs` sau từ cuối cùng; nét vẽ cuối nếu chậm hơn sẽ được vẽ nhanh lên một chút thay vì để giọng chờ. Muốn ngắt theo ý thì viết dấu câu theo ý: phẩy cho hơi thở, hai chấm cho nhịp chờ, chấm cho hết ý; `[ngắt 800ms]` khi cần một khoảng lặng chính xác.

## Ba chế độ âm thanh

1. **TTS (mặc định)** – mỗi cảnh có `narration`; giọng được tổng hợp, lưu cache theo nội dung, có timestamp từng từ → đồng bộ + phụ đề karaoke.
2. **Giọng thu sẵn** – `"voice": null, "audio": {"file", "srt"}`. Cảnh được cắt theo `cues` (hoặc chia đều theo thời gian). Có `words` (JSON `[{text,startMs,endMs}]`, ví dụ từ WhisperX) thì phụ đề và đồng bộ chính xác hơn; không có thì ước lượng theo độ dài chữ trong từng câu SRT.
3. **Không tiếng** – `"voice": null` và không có `audio`: dùng thời gian trong annotation.

## Đảm bảo đồng bộ

Mỗi cảnh có đúng `round(ms × fps / 1000)` khung hình và đúng `khung × 48000 / fps` mẫu âm thanh; lịch vẽ vượt quá độ dài cảnh sẽ tự được nén lại. Vì vậy video dài bao nhiêu cũng không bị lệch tiếng.

## Đầu ra (`out/`)

- `<name>-<format>.mp4` – H.264 + AAC, -14 LUFS, faststart
- `<name>-<format>-qa.jpg` – contact sheet 12 khung để kiểm tra
- `<name>.srt` – phụ đề (upload kèm lên YouTube)
- `<name>-report.json` – thời lượng từng cảnh, loudness, đường dẫn

## Điều tiết giọng theo nội dung (mood)

Mỗi câu được đọc với một "mood" quyết định tốc độ, cao độ, độ to, hướng to/nhỏ dần trong câu và khoảng nghỉ trước/sau câu:

| Tag trong lời thoại | Mood | Cách đọc |
|---|---|---|
| `[nhanh]` | fast | nhanh hơn ~11%, nghỉ ngắn – liệt kê, dẫn dắt |
| `[chậm]`, `[nhấn]` | slow | chậm ~10%, to hơn chút, nghỉ sau dài – ý cốt lõi, kết luận |
| `[cao trào]` | climax | nhanh nhẹ, cao hơn ~1.8 cung, to hơn 3 dB và to dần, nghỉ trước để "lấy đà" |
| `[xúc động]`, `[trầm]`, `[buồn]` | emotional | chậm ~14%, trầm ~1.3 cung, nhỏ hơn và nhỏ dần, nghỉ dài |
| `[hồi hộp]` | suspense | chậm, nhỏ, trầm, nghỉ dài sau câu – trước khi "lật bài" |
| `[vui]`, `[hào hứng]` | happy | nhanh nhẹ, sáng, to hơn |
| `[bình thường]` | neutral | tắt điều tiết cho câu đó |

- Tag đặt ở đầu câu (hoặc trong câu) và chỉ áp cho **câu đó**. Muốn cả cảnh: `"voice": {"mood": "emotional"}`.
- Không có tag thì câu được **tự đọc cảm xúc** từ từ ngữ và dấu câu (`!` → cao trào, `…` → hồi hộp, "đau khổ", "nước mắt" → xúc động, "bản chất", "tóm lại" → nhấn; câu kết ngắn của cảnh → chậm lại). Cảm xúc buồn/hồi hộp còn "vương" nhẹ sang câu kế tiếp.
- Agent viết kịch bản nên tự đặt tag cho các câu then chốt (hook, cú lật, cao trào, đoạn xúc động, câu chốt): hiểu nội dung tốt hơn luật từ khoá.
- Xem trước cách đọc (không cần mạng): `$PY scripts/voice_studio.py "Lời thoại…" --style podcast`.
- Edge đọc bằng SSML prosody (đổi được cả cao độ). VieNeu, TikTok, MakeVoice, Fish được chỉnh nhẹ tốc độ (WSOLA, 60% mức của bảng), độ to và khoảng nghỉ. Không dịch cao độ bằng xử lý âm thanh, vì dịch như vậy làm đổi âm sắc giọng đọc; Gemini/OpenAI nhận thêm lời chỉ dẫn giọng cho từng câu. ElevenLabs (đọc một lượt) chưa áp dụng.
