#!/usr/bin/env python3
"""Generate tiny Situation-Room sound cues with the stdlib (no deps, no binary assets to ship
by hand). Run once: python scripts/generate_sfx.py  ->  assets/sfx/*.wav

Cues: blip (a turn resolves), backfire (decision blew up), windfall (paid off), gameover, victory.
Short, soft, retro-terminal — played via a hidden autoplay gr.Audio in the app.
"""

from __future__ import annotations

import math
import os
import struct
import wave

SR = 16000
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "sfx")


def tone(freqs, dur, vol=0.35, shape="flat"):
    """A short waveform that glides through `freqs` (Hz). shape tweaks the amplitude envelope."""
    n = int(SR * dur)
    samples = []
    for i in range(n):
        t = i / SR
        frac = i / max(1, n - 1)
        f = freqs[0] if len(freqs) == 1 else _interp(freqs, frac)
        env = _envelope(frac, shape)
        samples.append(int(max(-1, min(1, math.sin(2 * math.pi * f * t) * env * vol)) * 32767))
    return samples


def _interp(freqs, frac):
    seg = frac * (len(freqs) - 1)
    i = min(len(freqs) - 2, int(seg))
    return freqs[i] + (freqs[i + 1] - freqs[i]) * (seg - i)


def _envelope(frac, shape):
    attack = min(1.0, frac / 0.05)            # 5% fade-in (kills clicks)
    release = min(1.0, (1 - frac) / 0.2)      # 20% fade-out
    base = attack * release
    if shape == "decay":
        base *= (1 - frac) ** 0.6
    elif shape == "swell":
        base *= 0.4 + 0.6 * frac
    return base


def write(name, samples):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", s) for s in samples))
    print("wrote", path)


def main():
    write("blip.wav", tone([880], 0.07, vol=0.22))
    write("backfire.wav", tone([420, 230, 150], 0.38, vol=0.4, shape="decay"))
    write("windfall.wav", tone([660, 990, 1320], 0.34, vol=0.32, shape="swell"))
    write("gameover.wav", tone([240, 160, 110], 0.7, vol=0.4, shape="decay"))
    write("victory.wav", tone([523, 659, 784, 1046], 0.55, vol=0.34, shape="swell"))


if __name__ == "__main__":
    main()
