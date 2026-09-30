#!/usr/bin/env python3
"""
Package a big video so it can be handed over from a cloud session (chat uploads
are capped at ~30 MB) as ONE full-quality file.

The video is cut into byte-exact chunks (<= --chunk-mb, default 14 MB so each fits
an Artifact file), next to a small ``index.html`` player page.  Opened as a
claude.ai Artifact (publish ``index.html`` with the ``parts/*`` files and the
``downloads`` capability), the page fetches the chunks, joins them back into the
original MP4, checks size + SHA-256, plays it, and offers "Lưu video" to save
the complete file.  Nothing is re-encoded.

  python share_video.py out/video.mp4 --title "Tên video" [--out-dir share/] [--chunk-mb 14]

Prints the publish batches (an Artifact publish takes <= 64 MB per call) and
``OUTPUT=<index.html>``.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from pathlib import Path

PAGE = r"""<title>__TITLE__</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600&family=Patrick+Hand&display=swap">
<style>
/* Layout: one narrow column like a sheet of whiteboard paper; the player is the page. */
:root {
  --paper: #f6f1e3; --sheet: #fffdf7; --ink: #2b2b2b; --muted: #6f6758;
  --accent: #d9652f; --line: #e2d9c4; --ok: #3f8a4f; --err: #c0392b;
  --display: "Patrick Hand", "Comic Sans MS", cursive;
  --body: "Be Vietnam Pro", system-ui, -apple-system, "Segoe UI", sans-serif;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --paper: #1d1b18; --sheet: #26231f; --ink: #efe8d8; --muted: #b3a994;
  --accent: #f08a57; --line: #3a352d; --ok: #7cc58b; --err: #ef7d6f; color-scheme: dark } }
:root[data-theme="dark"] {
  --paper: #1d1b18; --sheet: #26231f; --ink: #efe8d8; --muted: #b3a994;
  --accent: #f08a57; --line: #3a352d; --ok: #7cc58b; --err: #ef7d6f; color-scheme: dark }
body { background: var(--paper); color: var(--ink); font-family: var(--body); font-size: 16px; line-height: 1.55;
  padding-inline: 16px; padding-block: 32px 48px }
.wrap { max-width: 880px; margin: 0 auto; display: grid; gap: 20px }
h1 { font-family: var(--display); font-weight: 400; font-size: clamp(2rem, 5vw, 3rem); line-height: 1.1;
  margin: 0; text-wrap: balance }
h1 .underline { background: linear-gradient(transparent 72%, color-mix(in srgb, var(--accent) 45%, transparent) 72%) }
.meta { display: flex; flex-wrap: wrap; gap: 8px 18px; color: var(--muted); font-size: .92rem;
  font-variant-numeric: tabular-nums; margin: 0 }
.sheet { background: var(--sheet); border: 1px solid var(--line); border-radius: 14px; padding: 18px; display: grid; gap: 14px }
.screen { aspect-ratio: 16 / 9; max-width: 100%; border-radius: 10px; background: var(--paper);
  border: 2px dashed var(--line); display: grid; place-items: center; text-align: center; padding: 16px }
.screen p { margin: 0; color: var(--muted); max-width: 38ch }
video { width: 100%; max-width: 100%; border-radius: 10px; background: #000 }
.row { display: flex; flex-wrap: wrap; gap: 12px; align-items: center }
button { font: 600 1rem var(--body); border-radius: 999px; padding: 10px 20px; cursor: pointer;
  border: 2px solid var(--ink); background: var(--ink); color: var(--sheet) }
button.secondary { background: transparent; color: var(--ink) }
button:disabled { opacity: .5; cursor: default }
button:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px }
.bar { flex: 1 1 220px; min-width: 0; height: 10px; border-radius: 99px; background: var(--line); overflow: hidden }
.bar i { display: block; height: 100%; width: 0; background: var(--accent); transition: width .2s }
.status { font-size: .95rem; color: var(--muted); font-variant-numeric: tabular-nums; min-width: 0 }
.status.ok { color: var(--ok) } .status.err { color: var(--err) }
.note { font-size: .88rem; color: var(--muted); margin: 0; max-width: 65ch }
code { font-size: .9em }
@media (prefers-reduced-motion: reduce) { .bar i { transition: none } }
</style>
<div class="wrap">
  <header>
    <h1><span class="underline">__TITLE_HTML__</span></h1>
  </header>
  <p class="meta" id="meta"></p>
  <section class="sheet" aria-label="Video">
    <div class="screen" id="screen"><p>Bấm <b>Tải video</b> để ghép lại bản đầy đủ từ các phần đã tải lên, rồi xem hoặc lưu về máy.</p></div>
    <video id="player" controls playsinline hidden></video>
    <div class="row">
      <button id="load" type="button">Tải video</button>
      <button id="save" type="button" class="secondary" hidden>Lưu video (.mp4)</button>
      <div class="bar" aria-hidden="true"><i id="fill"></i></div>
    </div>
    <div class="status" id="status" role="status" aria-live="polite">Chưa tải.</div>
  </section>
  <p class="note">File được ghép lại byte-by-byte từ <span id="nparts"></span> phần và kiểm tra SHA-256, nên giống hệt file gốc do pipeline xuất ra, không nén lại lần nào.</p>
</div>
<script type="application/json" id="manifest">__MANIFEST__</script>
<script>
(() => {
  const M = JSON.parse(document.getElementById("manifest").textContent);
  const $ = (id) => document.getElementById(id);
  const mb = (n) => (n / 1048576).toFixed(1).replace(".", ",") + " MB";
  const mmss = (s) => Math.floor(s / 60) + ":" + String(Math.round(s % 60)).padStart(2, "0");
  $("meta").textContent = [M.resolution, M.duration ? mmss(M.duration) : "", mb(M.size), M.parts.length + " phần"]
    .filter(Boolean).join("  ·  ");
  $("nparts").textContent = M.parts.length;
  let blob = null;
  const dlPromise = window.claude && window.claude.use ? window.claude.use("downloads") : Promise.resolve(null);
  const setStatus = (t, cls) => { const s = $("status"); s.textContent = t; s.className = "status" + (cls ? " " + cls : ""); };

  async function fetchPart(p, onBytes) {
    const r = await fetch(p.path);
    if (!r.ok) throw new Error("Không tải được " + p.path + " (HTTP " + r.status + ")");
    if (!r.body || !r.body.getReader) { const b = await r.blob(); onBytes(b.size); return b; }
    const reader = r.body.getReader(), chunks = [];
    for (;;) { const { done, value } = await reader.read(); if (done) break; chunks.push(value); onBytes(value.length); }
    return new Blob(chunks);
  }
  const hex = (buf) => Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");

  $("load").addEventListener("click", async () => {
    $("load").disabled = true;
    let got = 0;
    try {
      const parts = [];
      for (const [i, p] of M.parts.entries()) {
        parts.push(await fetchPart(p, (n) => {
          got += n; $("fill").style.width = (100 * got / M.size).toFixed(1) + "%";
          setStatus("Đang tải phần " + (i + 1) + "/" + M.parts.length + " · " + mb(got) + " / " + mb(M.size));
        }));
      }
      blob = new Blob(parts, { type: "video/mp4" });
      if (blob.size !== M.size) throw new Error("Sai dung lượng: " + blob.size + " thay vì " + M.size + " byte");
      setStatus("Đang kiểm tra SHA-256…");
      if (window.crypto && crypto.subtle) {
        const h = hex(await crypto.subtle.digest("SHA-256", await blob.arrayBuffer()));
        if (h !== M.sha256) throw new Error("Mã kiểm tra SHA-256 không khớp, hãy tải lại trang");
      }
      $("screen").hidden = true;
      $("player").src = URL.createObjectURL(blob);
      $("player").hidden = false;
      setStatus("Sẵn sàng: bản đầy đủ " + mb(M.size) + ", đã kiểm tra.", "ok");
      const dl = await dlPromise;
      if (dl) $("save").hidden = false;
      else setStatus("Sẵn sàng để xem. Trang này không cho lưu file ở chế độ xem hiện tại.", "ok");
    } catch (e) {
      setStatus(e.message || String(e), "err");
      $("load").disabled = false;
    }
  });

  $("save").addEventListener("click", async () => {
    const dl = await dlPromise;
    if (!dl || !blob) return;
    try {
      await dl.save({ filename: M.filename, data: blob });
      setStatus("Đã chuyển file " + M.filename + " cho trình duyệt lưu.", "ok");
    } catch (e) {
      const why = { declined: "Bạn đã huỷ lưu.", rate_limited: "Đang có một hộp thoại lưu mở, thử lại sau giây lát." };
      setStatus(why[e && e.code] || ("Không lưu được: " + ((e && e.message) || e)), (e && e.code) === "declined" ? "" : "err");
    }
  });
})();
</script>
"""


def probe(path: Path) -> tuple[str, float]:
    try:
        import av
        with av.open(str(path)) as c:
            v = c.streams.video[0]
            dur = float(c.duration / 1_000_000) if c.duration else 0.0
            return f"{v.codec_context.width}×{v.codec_context.height}", dur
    except Exception:
        return "", 0.0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Split a video into Artifact-sized parts + a player/download page")
    p.add_argument("video")
    p.add_argument("--title", default=None)
    p.add_argument("--out-dir", default=None, help="default: <video dir>/share-<video stem>")
    p.add_argument("--chunk-mb", type=float, default=14.0)
    p.add_argument("--batch-mb", type=float, default=60.0, help="max MB per Artifact publish call")
    a = p.parse_args(argv)
    src = Path(a.video).resolve()
    out = Path(a.out_dir or src.parent / f"share-{src.stem}").resolve()
    (out / "parts").mkdir(parents=True, exist_ok=True)
    for old in (out / "parts").glob("part-*.mp4"):
        old.unlink()
    data = src.read_bytes()
    size = int(a.chunk_mb * 1024 * 1024)
    parts = []
    for i in range(0, len(data), size):
        name = f"parts/part-{i // size + 1:02d}.mp4"   # byte slice; .mp4 only so it is served as video/mp4
        (out / name).write_bytes(data[i:i + size])
        parts.append({"path": name, "size": len(data[i:i + size])})
    res, dur = probe(src)
    title = a.title or src.stem
    manifest = {"filename": src.name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                "resolution": res, "duration": round(dur, 1), "parts": parts}
    page = (PAGE.replace("__TITLE_HTML__", html.escape(title)).replace("__TITLE__", html.escape(title))
            .replace("__MANIFEST__", json.dumps(manifest, ensure_ascii=False).replace("</", "<\\/")))
    (out / "index.html").write_text(page, encoding="utf-8")
    # publish batches: index.html goes with the first one
    batches, cur, cur_mb = [], [], 0.0
    for part in parts:
        pmb = part["size"] / 1048576
        if cur and cur_mb + pmb > a.batch_mb:
            batches.append(cur)
            cur, cur_mb = [], 0.0
        cur.append(part["path"])
        cur_mb += pmb
    if cur:
        batches.append(cur)
    print(f"{len(parts)} parts of <= {a.chunk_mb:g} MB, {len(data) / 1048576:.1f} MB total, sha256 {manifest['sha256'][:12]}…")
    for k, b in enumerate(batches, 1):
        print(f"publish batch {k}: {' '.join(b)}")
    print(f"OUTPUT={out / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
