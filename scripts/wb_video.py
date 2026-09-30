#!/usr/bin/env python3
"""
Shared video / audio I/O built on PyAV (bundles FFmpeg - no system ffmpeg needed).

* VideoSink       - write BGR numpy frames straight to H.264 (+ optional AAC audio)
* iter_frames     - decode a video into BGR numpy frames
* load_audio      - decode any audio file to float32 mono/stereo numpy at a sample rate
* save_wav / audio helpers (silence, concat, mix with ducking, loudness normalisation)
"""
from __future__ import annotations

import math
import wave
from fractions import Fraction
from pathlib import Path
from typing import Iterator

import numpy as np

SAMPLE_RATE = 48000


# ──────────────────────────────────────────────────────────────
# Video
# ──────────────────────────────────────────────────────────────
class VideoSink:
    """H.264 writer. ``audio`` (float32, shape (n, 2) or (n,)) is muxed as AAC when given."""

    def __init__(self, path: str | Path, width: int, height: int, fps: int,
                 crf: int = 18, preset: str = "veryfast",
                 audio: np.ndarray | None = None, sample_rate: int = SAMPLE_RATE) -> None:
        self.path = Path(path)
        self.width, self.height, self.fps = width, height, fps
        self.audio, self.sample_rate = audio, sample_rate
        self._cv = None
        try:
            import av  # noqa: F401
        except ImportError:  # pragma: no cover - fallback path
            import cv2
            self._cv = cv2.VideoWriter(str(self.path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
            return
        import av
        self.av = av
        self.container = av.open(str(self.path), mode="w", options={"movflags": "+faststart"})
        self.stream = self.container.add_stream("libx264", rate=fps)
        self.stream.width, self.stream.height = width, height
        self.stream.pix_fmt = "yuv420p"
        self.stream.options = {"crf": str(crf), "preset": preset}
        self.stream.codec_context.time_base = Fraction(1, fps)
        self.astream = None
        if audio is not None:
            self.astream = self.container.add_stream("aac", rate=sample_rate)
            self.astream.bit_rate = 192000
            try:
                self.astream.layout = "stereo"
            except Exception:  # pragma: no cover
                pass

    def write(self, bgr: np.ndarray) -> None:
        if bgr.shape[1] != self.width or bgr.shape[0] != self.height:
            raise ValueError(f"frame {bgr.shape[1]}x{bgr.shape[0]} != sink {self.width}x{self.height}")
        if self._cv is not None:
            self._cv.write(np.ascontiguousarray(bgr))
            return
        frame = self.av.VideoFrame.from_ndarray(np.ascontiguousarray(bgr), format="bgr24")
        for pkt in self.stream.encode(frame):
            self.container.mux(pkt)

    def _write_audio(self) -> None:
        a = self.audio
        if a.ndim == 1:
            a = np.stack([a, a], axis=1)
        a = np.clip(a, -1.0, 1.0).astype(np.float32)
        chunk = 1024
        pts = 0
        for i in range(0, len(a), chunk):
            block = np.ascontiguousarray(a[i:i + chunk].T)  # planar (2, n)
            frame = self.av.AudioFrame.from_ndarray(block, format="fltp", layout="stereo")
            frame.sample_rate = self.sample_rate
            frame.pts = pts
            pts += block.shape[1]
            for pkt in self.astream.encode(frame):
                self.container.mux(pkt)
        for pkt in self.astream.encode(None):
            self.container.mux(pkt)

    def close(self) -> None:
        if self._cv is not None:
            self._cv.release()
            return
        for pkt in self.stream.encode(None):
            self.container.mux(pkt)
        if self.astream is not None:
            self._write_audio()
        self.container.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def iter_frames(path: str | Path) -> Iterator[np.ndarray]:
    import av
    with av.open(str(path)) as c:
        for f in c.decode(video=0):
            yield f.to_ndarray(format="bgr24")


def probe_video(path: str | Path) -> dict:
    import av
    with av.open(str(path)) as c:
        v = c.streams.video[0]
        n = v.frames or sum(1 for _ in c.decode(video=0))
        return {"width": v.codec_context.width, "height": v.codec_context.height,
                "fps": float(v.average_rate or 0), "frames": n,
                "has_audio": bool(c.streams.audio)}


# ──────────────────────────────────────────────────────────────
# Audio
# ──────────────────────────────────────────────────────────────
def load_audio(path: str | Path, sample_rate: int = SAMPLE_RATE, stereo: bool = True) -> np.ndarray:
    """Decode an audio file (mp3/wav/m4a/...) to float32 (n, 2) or (n,)."""
    import av
    layout = "stereo" if stereo else "mono"
    chunks = []
    with av.open(str(path)) as c:
        res = av.AudioResampler(format="fltp", layout=layout, rate=sample_rate)
        for frame in c.decode(audio=0):
            for rf in res.resample(frame):
                chunks.append(rf.to_ndarray())
        for rf in res.resample(None):
            chunks.append(rf.to_ndarray())
    if not chunks:
        return np.zeros((0, 2) if stereo else 0, np.float32)
    a = np.concatenate(chunks, axis=1).astype(np.float32)
    return a.T if stereo else a[0]


def audio_duration_ms(path: str | Path) -> int:
    a = load_audio(path, stereo=False)
    return int(round(len(a) * 1000 / SAMPLE_RATE))


def silence(ms: float, stereo: bool = True) -> np.ndarray:
    n = int(round(ms * SAMPLE_RATE / 1000))
    return np.zeros((n, 2) if stereo else n, np.float32)


def fit_length(a: np.ndarray, n: int) -> np.ndarray:
    if len(a) >= n:
        return a[:n]
    pad = np.zeros((n - len(a),) + a.shape[1:], np.float32)
    return np.concatenate([a, pad])


def save_wav(path: str | Path, a: np.ndarray, sample_rate: int = SAMPLE_RATE) -> Path:
    path = Path(path)
    if a.ndim == 1:
        a = a[:, None]
    pcm = (np.clip(a, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(pcm.shape[1])
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())
    return path


def rms_envelope(a: np.ndarray, win_ms: float = 50.0) -> np.ndarray:
    mono = a.mean(axis=1) if a.ndim == 2 else a
    win = max(1, int(SAMPLE_RATE * win_ms / 1000))
    power = np.convolve(mono ** 2, np.ones(win) / win, mode="same")
    return np.sqrt(power)


def duck_music(music: np.ndarray, voice: np.ndarray, base_gain_db: float = -18.0,
               duck_db: float = -10.0, attack_ms: float = 60, release_ms: float = 400) -> np.ndarray:
    """Scale music to ``base_gain_db`` and dip a further ``duck_db`` while the voice speaks."""
    n = len(voice)
    music = fit_length(music, n)
    env = rms_envelope(voice)
    speaking = (env > 0.01).astype(np.float32)
    # asymmetric smoothing (fast attack, slow release), decimated for speed
    step = 240
    s = speaking[::step]
    out = np.empty_like(s)
    a_att = 1 - math.exp(-step / (SAMPLE_RATE * attack_ms / 1000))
    a_rel = 1 - math.exp(-step / (SAMPLE_RATE * release_ms / 1000))
    v = 0.0
    for i, x in enumerate(s):
        v += (x - v) * (a_att if x > v else a_rel)
        out[i] = v
    duck = np.repeat(out, step)[:n]
    gain_db = base_gain_db + duck_db * duck
    gain = (10 ** (gain_db / 20)).astype(np.float32)
    return music * (gain[:, None] if music.ndim == 2 else gain)


def fade(a: np.ndarray, in_ms: float = 0, out_ms: float = 0) -> np.ndarray:
    a = a.copy()
    for ms, rev in ((in_ms, False), (out_ms, True)):
        n = min(len(a), int(SAMPLE_RATE * ms / 1000))
        if n <= 0:
            continue
        ramp = np.linspace(0, 1, n, dtype=np.float32)
        if rev:
            ramp = ramp[::-1]
            sl = slice(len(a) - n, len(a))
        else:
            sl = slice(0, n)
        a[sl] *= ramp[:, None] if a.ndim == 2 else ramp
    return a


def _k_weight(x: np.ndarray) -> np.ndarray:
    """ITU-R BS.1770 K-weighting applied in the frequency domain (magnitude only;
    phase does not matter for a power measurement)."""
    n = len(x)
    f = np.fft.rfftfreq(n, 1.0 / SAMPLE_RATE)
    z = np.exp(-2j * np.pi * f / SAMPLE_RATE)

    def resp(b, a):
        return (b[0] + b[1] * z + b[2] * z * z) / (a[0] + a[1] * z + a[2] * z * z)
    h = np.abs(resp([1.53512485958697, -2.69169618940638, 1.19839281085285],
                    [1.0, -1.69065929318241, 0.73248077421585])
               * resp([1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621]))
    return np.fft.irfft(np.fft.rfft(x, axis=0) * h[:, None], n=n, axis=0)


def loudness_lufs(a: np.ndarray) -> float:
    """Integrated loudness (BS.1770 K-weighting + absolute/relative gating)."""
    x = (a if a.ndim == 2 else a[:, None]).astype(np.float64)
    if len(x) == 0:
        return -70.0
    y = _k_weight(x)
    block, hop = int(0.4 * SAMPLE_RATE), int(0.1 * SAMPLE_RATE)
    sq = np.sum(y ** 2, axis=1)
    if len(sq) < block:
        ms = float(np.mean(sq))
        return -0.691 + 10 * math.log10(ms) if ms > 0 else -70.0
    c = np.concatenate([[0.0], np.cumsum(sq)])
    starts = np.arange(0, len(sq) - block + 1, hop)
    powers = (c[starts + block] - c[starts]) / block
    powers = powers[powers > 0]
    if powers.size == 0:
        return -70.0
    lk = -0.691 + 10 * np.log10(powers)
    g = powers[lk > -70]
    if g.size == 0:
        return -70.0
    rel = -0.691 + 10 * math.log10(float(np.mean(g))) - 10
    g2 = powers[-0.691 + 10 * np.log10(powers) > rel]
    return -0.691 + 10 * math.log10(float(np.mean(g2 if g2.size else g)))


def normalize_loudness(a: np.ndarray, target_lufs: float = -14.0, true_peak_db: float = -1.5) -> np.ndarray:
    if not len(a) or not np.any(a):
        return a
    cur = loudness_lufs(a)
    gain = 10 ** ((target_lufs - cur) / 20)
    out = a * gain
    peak = float(np.max(np.abs(out)))
    lim = 10 ** (true_peak_db / 20)
    if peak > lim:  # simple soft limiter on the peaks
        k = lim
        over = np.abs(out) > k * 0.8
        out = np.where(over, np.sign(out) * (k * 0.8 + (k * 0.2) * np.tanh((np.abs(out) - k * 0.8) / (k * 0.2))), out)
    return out.astype(np.float32)
