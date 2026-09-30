# Hướng dẫn cho agent (Codex, Claude Code, …)

Repo này biến một chủ đề / kịch bản / SRT thành video whiteboard vẽ tay có giọng đọc tiếng Việt.

- Quy trình làm video từ một prompt: **[SKILL.md](SKILL.md)** – đọc và làm theo.
- Vẽ cảnh bằng SVG: [docs/SVG_GUIDE.md](docs/SVG_GUIDE.md). Schema dự án: [docs/PROJECT_FORMAT.md](docs/PROJECT_FORMAT.md).
- Môi trường: `python scripts/prepare_env.py` → dùng interpreter `ENV_PY` in ra ở dòng cuối.
- Lệnh chính: `$ENV_PY scripts/make_video.py <dự án>/video.json [--draft]`.
- Test (offline, ~40s): `$ENV_PY -m pytest -q tests`. Chạy test trước khi commit thay đổi trong `scripts/`.

Quy ước code: Python 3.10+, không phụ thuộc ffmpeg hệ thống (dùng PyAV), mọi thời gian tính bằng ms, mọi toạ độ annotation là pixel nguyên của ảnh gốc. Mỗi script in `OUTPUT=<path>` ở dòng cuối.
Khi thay đổi renderer, luôn giữ hai bất biến: (1) phần tử chưa tới lượt không lộ pixel nào, (2) số khung hình của cảnh đúng bằng `round(ms*fps/1000)`.
