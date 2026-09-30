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
    "chunk": null,                           // "sentence" | "paragraph": mỗi request một câu hay cả đoạn (mặc định theo engine)
    "fx": "broadcast",                       // xử lý giọng kiểu phát thanh (lọc ù, rõ tiếng, nén nhẹ); "none" để tắt
    "lexicon": {"GPT": "gi pi ti"},          // cách đọc từ viết tắt / tên riêng
    "instructions": null,                    // gemini/openai: tự mô tả giọng điệu (thay cho style)
    "reference": null, "referenceText": null, "confirmAuthorizedVoice": false   // fish: clone giọng có sự đồng ý
  },
  "audio": null,                             // HOẶC giọng thu sẵn: {"file": "voice.mp3", "srt": "voice.srt", "words": "words.json"}

  "captions": { "enabled": true, "karaoke": true, "maxWords": 6, "uppercase": false,
                "box": false, "highlight": "#FFD60A", "size": 0 },
  "header": { "text": "Tiêu đề hiện ở bản dọc" },   // false để tắt; mặc định = title
  "music":  { "file": "music/nhac-nen.mp3", "volumeDb": -20, "duck": true, "duckDb": -8 },
                                             // hoặc {"generate": "calm"|"bright"} = nhạc tự tạo, không bản quyền
  "sfx":    { "pen": true, "volumeDb": -17 },       // tiếng bút sột soạt khi đang vẽ
  "render": { "inkPath": "skeleton", "colorFill": "contour-wipe", "camera": "follow",
              "cameraMaxZoom": 1.2, "paper": "#F6F1E3", "hand": null, "handHeightRatio": 0.42,
              "humanMotion": true,                  // nhịp tay người: chậm ở góc/cuối nét, dừng khi đặt/nhấc bút
              "penLift": 14 },                      // px (ở 1080p) bàn tay nhấc lên khi di chuyển giữa các nét
  "sync":   { "leadMs": 250, "voiceDelayMs": 200, "minDrawMs": 900, "maxDrawMs": 4500, "tailMs": 800 },
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
| `narration` | Lời thoại của cảnh (chế độ TTS). Có thể chèn `[pause 800ms]`, `[ngắt 1s]` – không hiện trong phụ đề. |
| `voice` | Ghi đè giọng cho riêng cảnh này, ví dụ `{"style": "ads"}` hoặc `{"engine": "tiktok"}`. |
| `say` | Danh sách cụm từ kích hoạt, gán lần lượt cho các phần tử chưa có `say`. |
| `cues` | `[đầu, cuối]` (đánh số từ 1) – các câu SRT thuộc cảnh này (chế độ `audio`). |
| `keepTiming` | `true` = giữ nguyên thời gian trong annotation, không đồng bộ theo giọng. |
| `minMs` | Độ dài tối thiểu của cảnh. |

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
