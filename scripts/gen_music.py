#!/usr/bin/env python3
"""
Copyright-free background music, generated procedurally (no samples, no licences).

A soft lo-fi loop: warm pad chords + gentle plucked arpeggio + round bass over a
I-V-vi-IV progression.  Quiet, steady and unobtrusive - made to sit under a voice.

  python gen_music.py out.wav --seconds 60 [--style calm|bright] [--bpm 84] [--seed 3]

In video.json:  "music": {"generate": "calm", "volumeDb": -22}
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wb_video as wv  # noqa: E402

SR = wv.SAMPLE_RATE
STYLES = {
    # (key root midi, progression as scale-degree roots with chord quality, bpm)
    "calm": (57, [(0, "maj"), (7, "maj"), (9, "min"), (5, "maj")], 80),     # A: A E F#m D
    "bright": (60, [(0, "maj"), (9, "min"), (5, "maj"), (7, "maj")], 92),   # C: C Am F G
}


def _hz(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)


def _tone(freq: float, dur: float, harmonics=(1.0, 0.35, 0.12), attack=0.01, decay=3.0,
          release=0.05, vibrato=0.0) -> np.ndarray:
    n = int(dur * SR)
    t = np.arange(n) / SR
    ph = 2 * np.pi * freq * t
    if vibrato:
        ph += vibrato * np.sin(2 * np.pi * 4.5 * t)
    wave = sum(a * np.sin(ph * (k + 1)) for k, a in enumerate(harmonics))
    env = np.exp(-t * decay)
    a = max(1, int(attack * SR))
    env[:a] *= np.linspace(0, 1, a)
    r = max(1, int(release * SR))
    env[-r:] *= np.linspace(1, 0, r)
    return (wave * env).astype(np.float32)


def _add(buf: np.ndarray, x: np.ndarray, start: float, pan: float = 0.0, gain: float = 1.0) -> None:
    i = int(start * SR)
    if i >= len(buf):
        return
    x = x[:len(buf) - i] * gain
    l, r = np.sqrt(0.5 * (1 - pan)), np.sqrt(0.5 * (1 + pan))
    buf[i:i + len(x), 0] += x * l
    buf[i:i + len(x), 1] += x * r


def _lowpass(a: np.ndarray, cutoff: float) -> np.ndarray:
    f = np.fft.rfftfreq(len(a), 1 / SR)
    h = 1 / np.sqrt(1 + (f / cutoff) ** 4)
    return np.fft.irfft(np.fft.rfft(a, axis=0) * h[:, None], n=len(a), axis=0).astype(np.float32)


def generate(seconds: float, style: str = "calm", bpm: float | None = None, seed: int = 3) -> np.ndarray:
    root, prog, default_bpm = STYLES.get(style, STYLES["calm"])
    bpm = bpm or default_bpm
    beat = 60.0 / bpm
    bar = 4 * beat
    rng = np.random.default_rng(seed)
    n = int(seconds * SR) + SR
    buf = np.zeros((n, 2), np.float32)
    t, i = 0.0, 0
    pattern = [0, 1, 2, 1, 3, 2, 1, 2]           # arpeggio over chord tones (8ths)
    while t < seconds:
        deg, qual = prog[i % len(prog)]
        base = root + deg
        chord = [base, base + (4 if qual == "maj" else 3), base + 7, base + 12]
        # pad: whole bar, slow attack, very soft
        for k, m in enumerate(chord[:3]):
            _add(buf, _tone(_hz(m), bar + 0.6, (1.0, 0.18), attack=0.5, decay=0.35, release=0.6,
                            vibrato=0.002), t, pan=(k - 1) * 0.4, gain=0.05)
        # bass on beats 1 and 3
        for b in (0, 2):
            _add(buf, _tone(_hz(base - 12), 1.6 * beat, (1.0, 0.25), attack=0.01, decay=2.2), t + b * beat,
                 gain=0.16)
        # plucked arpeggio, one octave up, humanised timing/velocity
        for s, idx in enumerate(pattern):
            m = chord[idx] + 12
            jitter = rng.normal(0, 0.008)
            vel = 0.07 * rng.uniform(0.75, 1.0) * (1.15 if s % 4 == 0 else 1.0)
            _add(buf, _tone(_hz(m), 1.4, (1.0, 0.3, 0.1, 0.04), attack=0.004, decay=4.5), t + s * beat / 2 + jitter,
                 pan=0.35 if s % 2 else -0.35, gain=vel)
        t += bar
        i += 1
    buf = _lowpass(buf, 5200)
    # simple room: two short feedback-less echoes
    for d, g in ((0.11, 0.22), (0.23, 0.12)):
        k = int(d * SR)
        buf[k:] += buf[:-k] * g
    buf = buf[:int(seconds * SR)]
    buf = wv.fade(buf, 1500, 2500)
    peak = float(np.max(np.abs(buf))) or 1.0
    return (buf / peak * 0.8).astype(np.float32)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Procedural, copyright-free background music")
    p.add_argument("out")
    p.add_argument("--seconds", type=float, default=60)
    p.add_argument("--style", default="calm", choices=list(STYLES))
    p.add_argument("--bpm", type=float, default=None)
    p.add_argument("--seed", type=int, default=3)
    a = p.parse_args(argv)
    out = wv.save_wav(a.out, generate(a.seconds, a.style, a.bpm, a.seed))
    print(f"OUTPUT={Path(out).resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
