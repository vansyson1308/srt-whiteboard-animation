# Hướng dẫn vẽ cảnh bằng SVG (dành cho agent)

Claude Code / Codex không cần API tạo ảnh: agent **tự viết SVG**, `svg_scene.py` biến nó thành PNG + annotation có **nét vector thật**, nên bàn tay vẽ đúng thứ tự từng nét như người thật. Đây là đường mặc định, nhanh, rẻ, nhất quán.

## Quy ước bắt buộc

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900">
  <g id="sun" data-label="Mặt Trời" data-say="mặt trời">
    <circle cx="300" cy="380" r="95" fill="#f6c453" stroke="#2b2b2b" stroke-width="6"/>
  </g>
  <g id="title" data-label="Tiêu đề" data-say="vì sao">
    <text x="800" y="120" text-anchor="middle" font-family="Patrick Hand" font-size="84" fill="#2b2b2b">Vì sao…?</text>
  </g>
</svg>
```

- Mỗi `<g id="…">` **cấp cao nhất** = một phần tử vẽ. Thứ tự trong file = thứ tự vẽ.
- `data-say` = cụm từ **nguyên văn trong lời thoại**. Phần tử bắt đầu được vẽ ngay trước khi cụm từ đó được đọc. Phần tử đầu tiên luôn bắt đầu ngay lập tức (hook).
- `data-label` = tên dễ đọc (hiện trong preview/QA). `data-role` tuỳ chọn.
- Bên trong nhóm, thứ tự các shape = thứ tự nét. Chữ `<text>` được "viết tay" từ trái sang phải.
- Không vẽ hình chữ nhật nền phủ toàn khung (nếu có, nó được dùng làm màu giấy và bị loại bỏ).

## Khung hình

| Mục tiêu | viewBox gợi ý | Ghi chú |
|---|---|---|
| YouTube 16:9 | `0 0 1600 900` | Chừa ~10% phía dưới cho phụ đề |
| TikTok/Shorts 9:16 | `0 0 1080 1350` (4:5) | Khi ghép vào 1080×1920 sẽ lấp gần hết vùng an toàn |
| Dùng chung cả hai | `0 0 1600 900` | Bản dọc sẽ đặt tranh ở giữa, tiêu đề phía trên, phụ đề phía dưới |

## Phong cách (nhất quán cả series)

- Nét chính `#2b2b2b`, `stroke-width` 5–8, `stroke-linecap="round"`, `stroke-linejoin="round"`.
- Màu nhấn tiết chế: cam `#e8743b`, đỏ `#e04b3a`, xanh `#3b7dd8`, vàng `#f6c453`; tô nền nhạt `#dfeefe`, `#eef5fb`, `#ffffff`.
- Font chữ: `Patrick Hand` (viết tay, có dấu tiếng Việt) – đã kèm trong `assets/fonts/`.
- Tối giản, nhiều khoảng trắng, mỗi cảnh chỉ **một ý chính**, 3–6 phần tử.
- Tách các phần tử bằng khoảng trống: vùng của phần tử được tính từ chính pixel của nhóm, chồng lấn nhẹ không sao.
- Ưu tiên `path`/`circle`/`line` đơn giản; tránh `filter`, `mask`, ảnh nhúng, gradient phức tạp.
- Chữ trong cảnh: ngắn (1–4 từ), dùng như nhãn/từ khoá; câu dài để cho phụ đề.

## Mẹo làm video "cuốn"

- Phần tử 1 nên là câu hỏi/tuyên bố gây tò mò (hook trong 2 giây đầu).
- 1 cảnh ≈ 10–20 giây lời thoại; video TikTok 30–60 giây ≈ 3–5 cảnh.
- Mũi tên, gạch chân, khoanh tròn là các phần tử riêng → được vẽ đúng lúc nhấn mạnh.
- Mỗi `data-say` nên là 1–3 từ đặc trưng, xuất hiện một lần trong lời thoại của cảnh.

## Kiểm tra nhanh

```bash
python scripts/svg_scene.py scenes/scene-01.svg --out-dir /tmp/s1
python scripts/render_annotation_preview.py /tmp/s1/scene-01.png /tmp/s1/scene-01.annotation.json /tmp/s1/check.jpg
```
