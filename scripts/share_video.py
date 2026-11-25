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

An Artifact version holds at most 256 MB, so a bigger video (a 90-minute one is
~550 MB) is spread over several pages (``--page-mb``, default 240): ``page-1/``,
``page-2/``, ... each with its own ``index.html`` and parts, published as separate
Artifacts.  Every page but the last saves its segment of the file (checked by
SHA-256); the last page takes those saved segments from the viewer, checks each,
appends its own, checks the whole file's SHA-256, plays it and saves the full MP4.
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
[hidden] { display: none !important }
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
.pick { display: grid; gap: 8px; min-width: 0 }
.pick label { font-weight: 600 }
.pick input { max-width: 100%; font: inherit; color: var(--ink) }
.pick ul { margin: 0; padding-left: 1.2em; color: var(--muted); font-size: .92rem; font-variant-numeric: tabular-nums }
.pick li.ok { color: var(--ok) } .pick li.err { color: var(--err) }
@media (prefers-reduced-motion: reduce) { .bar i { transition: none } }
</style>
<div class="wrap">
  <header>
    <h1><span class="underline">__TITLE_HTML__</span></h1>
  </header>
  <p class="meta" id="meta"></p>
  <section class="sheet" aria-label="Video">
    <div class="screen" id="screen"><p id="intro">Bấm <b>Tải video</b> để ghép lại bản đầy đủ từ các phần đã tải lên, rồi xem hoặc lưu về máy.</p></div>
    <video id="player" controls playsinline hidden></video>
    <div class="pick" id="pick" hidden>
      <label for="prev" id="prevlabel">Chọn các file phần trước đã lưu</label>
      <input id="prev" type="file" accept="video/mp4,.mp4" multiple>
      <ul id="prevlist"></ul>
    </div>
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
  const P = M.pages || 1, K = M.page || 1, multi = P > 1, last = K === P;
  const own = multi ? M.segments[K - 1] : { filename: M.filename, size: M.size, sha256: M.sha256 };
  const prevSegs = multi ? M.segments.slice(0, P - 1) : [];
  $("meta").textContent = [multi ? "Trang " + K + "/" + P : "", M.resolution, M.duration ? mmss(M.duration) : "",
    mb(M.size), M.parts.length + " phần trên trang này"].filter(Boolean).join("  ·  ");
  $("nparts").textContent = multi ? "các" : M.parts.length;
  if (multi && !last) {
    $("intro").textContent = "Video dài " + mb(M.size) + " nên được chia ra " + P + " trang. Đây là trang " + K +
      ": bấm Tải phần " + K + ", rồi Lưu phần " + K + ". Lưu xong các phần, mở trang " + P + " (trang cuối) để ghép thành video đầy đủ.";
    $("load").textContent = "Tải phần " + K;
    $("save").textContent = "Lưu phần " + K + " (.mp4)";
  } else if (multi) {
    $("intro").textContent = "Đây là trang cuối (" + K + "/" + P + "). Lưu phần 1" + (P > 2 ? " đến " + (P - 1) : "") +
      " từ các trang trước, chọn các file đó ở dưới, rồi bấm Ghép video. Trang sẽ kiểm tra từng phần và cả file.";
    $("prevlabel").textContent = "Chọn " + prevSegs.map((g) => g.filename).join(", ");
    $("pick").hidden = false;
    $("load").textContent = "Ghép video";
    $("load").disabled = true;
  }
  let blob = null, picked = [];
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
  const sha = async (b) => (window.crypto && crypto.subtle) ? hex(await crypto.subtle.digest("SHA-256", await b.arrayBuffer())) : null;

  $("prev").addEventListener("change", () => {
    picked = Array.from($("prev").files || []);
    const ul = $("prevlist"); ul.textContent = "";
    for (const f of picked) { const li = document.createElement("li"); li.textContent = f.name + " · " + mb(f.size); ul.appendChild(li); }
    $("load").disabled = picked.length !== prevSegs.length;
    setStatus(picked.length === prevSegs.length ? "Đã chọn đủ " + picked.length + " file. Bấm Ghép video."
      : "Cần chọn đúng " + prevSegs.length + " file (đang chọn " + picked.length + ").");
  });

  async function checkPicked() {
    // match each needed segment to a picked file by size, then confirm by SHA-256 (any order, any file name)
    const found = [], items = $("prevlist").children;
    for (const [i, g] of prevSegs.entries()) {
      setStatus("Đang kiểm tra phần " + (i + 1) + "…");
      let hit = null;
      for (const [j, f] of picked.entries()) {
        if (f.size !== g.size) continue;
        const h = await sha(f);
        if (h === null || h === g.sha256) { hit = f; if (items[j]) items[j].className = "ok"; break; }
      }
      if (!hit) throw new Error("Thiếu hoặc sai file phần " + (i + 1) + " (" + g.filename + ", " + mb(g.size) + "). Hãy lưu lại phần đó từ trang " + (i + 1) + ".");
      found.push(hit);
    }
    return found;
  }

  $("load").addEventListener("click", async () => {
    $("load").disabled = true;
    $("prev").disabled = true;
    let got = 0;
    try {
      const prev = multi && last ? await checkPicked() : [];
      const parts = [];
      for (const [i, p] of M.parts.entries()) {
        parts.push(await fetchPart(p, (n) => {
          got += n; $("fill").style.width = (100 * got / own.size).toFixed(1) + "%";
          setStatus("Đang tải phần " + (i + 1) + "/" + M.parts.length + " · " + mb(got) + " / " + mb(own.size));
        }));
      }
      let mine = new Blob(parts, { type: "video/mp4" });
      if (mine.size !== own.size) throw new Error("Sai dung lượng: " + mine.size + " thay vì " + own.size + " byte");
      if (multi) {
        setStatus("Đang kiểm tra SHA-256 phần " + K + "…");
        const h = await sha(mine);
        if (h !== null && h !== own.sha256) throw new Error("Mã kiểm tra SHA-256 của phần " + K + " không khớp, hãy tải lại trang");
      }
      if (multi && !last) {
        blob = mine;
        setStatus("Phần " + K + " đã sẵn sàng (" + mb(own.size) + ", đã kiểm tra). Bấm Lưu phần " + K + ".", "ok");
        const dl = await dlPromise;
        if (dl) $("save").hidden = false;
        else setStatus("Trang này không cho lưu file ở chế độ xem hiện tại.", "err");
        return;
      }
      blob = multi ? new Blob([...prev, mine], { type: "video/mp4" }) : mine;
      mine = null;
      if (blob.size !== M.size) throw new Error("Sai dung lượng: " + blob.size + " thay vì " + M.size + " byte");
      setStatus("Đang kiểm tra SHA-256 cả video…");
      const h = await sha(blob);
      if (h !== null && h !== M.sha256) throw new Error("Mã kiểm tra SHA-256 không khớp, hãy tải lại trang");
      $("screen").hidden = true;
      $("pick").hidden = true;
      $("player").src = URL.createObjectURL(blob);
      $("player").hidden = false;
      setStatus("Sẵn sàng: bản đầy đủ " + mb(M.size) + ", đã kiểm tra.", "ok");
      const dl = await dlPromise;
      if (dl) $("save").hidden = false;
      else setStatus("Sẵn sàng để xem. Trang này không cho lưu file ở chế độ xem hiện tại.", "ok");
    } catch (e) {
      setStatus(e.message || String(e), "err");
      $("load").disabled = false;
      $("prev").disabled = false;
    }
  });

  $("save").addEventListener("click", async () => {
    const dl = await dlPromise;
    if (!dl || !blob) return;
    try {
      const name = multi && !last ? own.filename : M.filename;
      await dl.save({ filename: name, data: blob });
      setStatus("Đã chuyển file " + name + " cho trình duyệt lưu." + (multi && !last ? " Tiếp theo: mở trang " + (K + 1 < P ? K + 1 : P) + "." : ""), "ok");
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
    p.add_argument("--page-mb", type=float, default=240.0,
                   help="max MB of parts per page/Artifact (an Artifact version holds <= 256 MB)")
    a = p.parse_args(argv)
    src = Path(a.video).resolve()
    out = Path(a.out_dir or src.parent / f"share-{src.stem}").resolve()
    out.mkdir(parents=True, exist_ok=True)
    for old in list(out.glob("parts/part-*.mp4")) + list(out.glob("page-*/parts/part-*.mp4")) \
            + list(out.glob("page-*/index.html")):
        old.unlink()
    data = src.read_bytes()
    size = int(a.chunk_mb * 1024 * 1024)
    chunks = [(i // size + 1, i, min(len(data), i + size)) for i in range(0, len(data), size)]
    # group the chunks into pages that each fit one Artifact version
    pages, cur = [], []
    for c in chunks:
        if cur and sum(e - b for _, b, e in cur) + (c[2] - c[1]) > a.page_mb * 1048576:
            pages.append(cur)
            cur = []
        cur.append(c)
    pages.append(cur)
    res, dur = probe(src)
    title = a.title or src.stem
    n = len(pages)
    segments = [{"filename": f"{src.stem}-phan-{k}-of-{n}{src.suffix}", "size": pg[-1][2] - pg[0][1],
                 "sha256": hashlib.sha256(data[pg[0][1]:pg[-1][2]]).hexdigest()} for k, pg in enumerate(pages, 1)]
    full = {"filename": src.name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "resolution": res, "duration": round(dur, 1)}
    print(f"{len(chunks)} parts of <= {a.chunk_mb:g} MB, {len(data) / 1048576:.1f} MB total, "
          f"sha256 {full['sha256'][:12]}…" + (f", {n} pages" if n > 1 else ""))
    index = None
    for k, pg in enumerate(pages, 1):
        pdir = out if n == 1 else out / f"page-{k}"
        (pdir / "parts").mkdir(parents=True, exist_ok=True)
        parts = []
        for num, b, e in pg:
            name = f"parts/part-{num:02d}.mp4"   # byte slice; .mp4 only so it is served as video/mp4
            (pdir / name).write_bytes(data[b:e])
            parts.append({"path": name, "size": e - b})
        manifest = dict(full, parts=parts)
        page_title = title
        if n > 1:
            manifest.update(page=k, pages=n, segments=segments)
            page_title = f"{title} · trang {k}/{n}"
        page = (PAGE.replace("__TITLE_HTML__", html.escape(page_title)).replace("__TITLE__", html.escape(page_title))
                .replace("__MANIFEST__", json.dumps(manifest, ensure_ascii=False).replace("</", "<\\/")))
        (pdir / "index.html").write_text(page, encoding="utf-8")
        index = index or pdir / "index.html"
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
        prefix = "" if n == 1 else f"page {k}/{n} ({pdir.name}/, {segments[k - 1]['size'] / 1048576:.1f} MB) "
        for j, b in enumerate(batches, 1):
            print(f"{prefix}publish batch {j}: {' '.join(b)}")
    print(f"OUTPUT={index}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
