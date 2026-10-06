# Nghiên cứu & lộ trình nâng cấp (09/2026)

## 1. Hiện trạng repo gốc (trước khi nâng cấp)

Repo gốc (`srt-whiteboard-animation`, MIT) có ý tưởng tốt – "mask choreography + stream strokes": mỗi vùng được vẽ theo thứ tự kể chuyện, vùng chưa tới lượt không bị lộ. Nhưng để làm kênh đều đặn thì nó còn thiếu và lỗi khá nhiều:

| Vấn đề | Hậu quả |
|---|---|
| `render_stream_whiteboard.py` gọi `_lay_ink` sai số tham số khi vùng không có nét | **Crash** ở chế độ mặc định |
| `render_annotation_preview.py` hardcode `C:/Windows/Fonts/msyh.ttc` | **Crash** trên macOS/Linux |
| Đầu ra 1080×600 @60fps (căn theo lưới) | Không đúng chuẩn YouTube 1920×1080 / TikTok 1080×1920 |
| Không có giọng đọc, nhạc, phụ đề | Phải dựng lại bằng CapCut/Premiere |
| Tổng thời lượng làm tròn theo từng đoạn | Lệch tiếng dần khi ghép nhiều cảnh |
| Mỗi đoạn nét tạo mặt nạ toàn khung | Chậm (36s cho 8.6s video ở 1080×600) |
| Toàn bộ quy trình bắt người dùng xác nhận 7 lần, agent tự chấm toạ độ pixel | Không thể "một prompt ra video" |
| Chữ thương hiệu tiếng Trung trên cây bút | Không dùng được cho kênh riêng |
| UI/tài liệu chỉ tiếng Trung | Khó dùng |

## 2. Những gì bản nâng cấp đã làm

- **Renderer mới**: đúng độ phân giải bất kỳ, đúng số khung tuyệt đối, nhanh hơn ~4 lần/pixel (thao tác cục bộ + ghi H.264 trực tiếp qua PyAV, không cần ffmpeg hệ thống), nét giữ màu gốc và khử răng cưa, tay trượt vào/ra giữa các phần tử, **camera zoom theo phần tử đang vẽ** rồi lùi ra toàn cảnh, mờ dần về tranh hoàn chỉnh, sắp xếp nét theo "đầu bút gần nhất" để tay không nhảy lung tung.
- **Chế độ SVG (agent tự vẽ)**: nét vector thật → bút đi đúng từng nét, chữ được viết tay trái→phải, vùng chính xác đến từng pixel (label map), không cần API ảnh.
- **Tự chia vùng ảnh raster** (`auto_annotate.py`): tách vật thể, bỏ qua đường nền nối các vật, thứ tự đọc.
- **Giọng đọc tiếng Việt miễn phí** (edge-tts: HoaiMy nữ / NamMinh nam) có timestamp từng từ; ElevenLabs (timestamp ký tự), OpenAI TTS (ước lượng); căn chỉnh từ ở mức ký tự (xử lý "năm 2024", "365,25"…).
- **Đồng bộ "nói tới đâu vẽ tới đó"**: `data-say` trên từng phần tử.
- **Dựng hoàn chỉnh**: 16:9 + 9:16 (vùng an toàn TikTok) + 1:1, phụ đề karaoke tiếng Việt (Be Vietnam Pro), tiêu đề cho bản dọc, chuyển cảnh, nhạc nền tự hạ khi có giọng (ducking), tiếng bút sột soạt tổng hợp (mặc định tắt), chuẩn hoá **-14 LUFS**, xuất SRT, contact sheet QA, báo cáo JSON.
- **Cache theo nội dung** + render song song: sửa một cảnh chỉ render lại cảnh đó.
- **Test tự động** (14 test, chạy offline) + CI.

## 3. Đối chiếu với công cụ thương mại

Top tính năng giữ chân người xem (tổng hợp từ VideoScribe, Doodly, OpenDoodler và best-practice Shorts/TikTok):

| # | Tính năng | Trạng thái |
|---|---|---|
| 1 | Hook trong 1–2 giây đầu (đang vẽ ngay, câu hỏi trên màn hình) | ✅ phần tử đầu vẽ ở 0.15s + header bản dọc |
| 2 | Vẽ khớp với lời nói theo timestamp thật | ✅ `data-say` + word timings |
| 3 | Thứ tự nét tự nhiên, tay không nhảy | ✅ vector strokes / greedy ordering |
| 4 | Bàn tay/bút thật, đầu bút đúng nét | ✅ (có bản không chữ, in tên kênh được) |
| 5 | Camera pan/zoom theo phần tử, lùi ra cuối cảnh | ✅ `camera: follow` |
| 6 | Tô màu sau khi vẽ nét | ✅ contour-wipe / brush / fade |
| 7 | Phụ đề karaoke trong vùng an toàn | ✅ |
| 8 | Chữ viết tay từng nét | ✅ (quét trái→phải; chưa theo nét glyph) |
| 9 | Âm thanh: tiếng bút (tuỳ chọn, mặc định tắt), nhạc ducking, -14 LUFS | ✅ (chưa có "whoosh" chuyển cảnh) |
| 10 | Chuyển cảnh, không đứng yên > 2–3s | ✅ fade/slide, camera luôn chuyển động |

## 4. Nguồn lực bên ngoài đáng dùng

**TTS tiếng Việt**
- edge-tts 7.2.x: phải truyền `boundary="WordBoundary"` (mặc định mới là SentenceBoundary) – đã xử lý. Chỉ có 2 giọng Việt.
- ElevenLabs: tiếng Việt có ở Flash/Turbo v2.5 và v3 (không có ở Multilingual v2); endpoint `/with-timestamps` trả timestamp ký tự – đã tích hợp (`ELEVENLABS_MODEL` cấu hình được).
- OpenAI `gpt-4o-mini-tts`: có tiếng Việt, không có timestamp → ước lượng; nên thêm forced alignment.
- Thay thế: FPT.AI, Viettel AI, Zalo AI (API chưa kiểm chứng), VieNeu-TTS (chạy local, clone giọng).
- **Khảo sát 09/2026** (chi tiết: báo cáo "Giọng đọc tiếng Việt tốt nhất 2026"):
  - Nhóm dẫn đầu tiếng Việt: Gemini 3.8 Flash TTS (23/09/2026, có free tier, không timestamp) và ElevenLabs v4 (28/09/2026, timestamp ký tự).
  - Azure vi-VN vẫn chỉ HoaiMy/NamMinh, không có HD. Vbee/FPT/Viettel không trả timestamp từng từ.
  - Mã nguồn mở: VieNeu-TTS v3 Turbo (Apache-2.0, CPU, WER 3,3% trên ViTTS-Bench) → engine `vieneu`. F5-TTS-Vietnamese và viXTTS chỉ phi thương mại.
  - Proxy TikTok / MakeVoice và edge-tts không có điều khoản thương mại rõ ràng → chỉ dùng làm nháp.
- Căn timestamp cho audio bất kỳ: WhisperX forced alignment (model tiếng Việt `nguyenvulebinh/wav2vec2-base-vi-vlsp2020`).

**Tạo ảnh** (tên model đổi liên tục → để trong biến môi trường)
- Lưu ý ngừng hoạt động: `gemini-2.5-flash-image` (02/10/2026), `gpt-image-1` (23/10/2026).
- Recraft vector models xuất **SVG thật** → cắm thẳng vào chế độ SVG (đáng thử nhất).

**Nền tảng**
- TikTok 1080×1920: tránh trên 130px, dưới 484px, phải 140px, trái 44px. Shorts: dưới ~300–400px.
- Độ dài tối ưu 30–60s; retention ~70% ở giây thứ 3 → hook là quan trọng nhất.
- Loudness -14 LUFS, true peak ≤ -1 dBTP; nhạc thấp hơn giọng 18–25 dB.

**Dự án mã nguồn mở tham khảo**: ToBeWin/HandDraw-Skill (Remotion, SVG dashoffset, MIT), brandonvant/claude-skill-whiteboard-explainer (Whisper timing + QA gates, MIT), edwardaiwang-svg/doodle-studio (viết chữ theo skeleton glyph, MIT), Rsverma/OpenDoodler (AGPL – chỉ tham khảo ý tưởng).

## 5. "Sản phẩm triệu đô"? – đánh giá thẳng

Với mục tiêu **tự dùng để làm kênh**, giá trị nằm ở: *chi phí mỗi video ≈ 0đ, thời gian ≈ vài phút máy chạy, chất lượng ổn định, agent tự làm từ một prompt*. Sau đợt nâng cấp này, phần "máy" đã đạt mức dùng thật được. Phần quyết định kênh có lên hay không vẫn là **kịch bản + hook + hình minh hoạ có ý tưởng** – đó là chỗ agent cần được hướng dẫn tốt (SKILL.md) và là nơi nên đầu tư tiếp.

## 6. Lộ trình tiếp theo (ưu tiên giảm dần)

1. **Chữ viết tay theo nét glyph** (skeleton của font Patrick Hand) thay vì quét trái→phải.
2. **Forced alignment WhisperX** cho giọng thu sẵn / OpenAI TTS → timestamp thật.
3. **Thư viện icon SVG** (người, mũi tên, não, tiền, đồng hồ…) do agent tái sử dụng → nhất quán + nhanh.
4. **Nhiều bàn tay** (trái/phải, màu da, bút dạ/phấn) + bảng đen/bảng kính.
5. **Hiệu ứng**: khoanh tròn/gạch chân nhấn mạnh, "pop" phần tử, xoá bảng khi chuyển cảnh, âm "whoosh".
6. **Cảnh dài liên tục**: camera pan sang vùng trống kế tiếp của một "bảng lớn" thay vì cắt cảnh.
7. **Recraft SVG** làm nguồn ảnh vector khi cần tranh phức tạp hơn khả năng tự vẽ của agent.
8. **Xuất bản tự động**: tạo tiêu đề/mô tả/hashtag, thumbnail từ khung đẹp nhất, upload YouTube API.
9. **Preview trong trình duyệt** phát được audio + vẽ nét thật (WebCodecs) để chỉnh nhanh không cần render.
