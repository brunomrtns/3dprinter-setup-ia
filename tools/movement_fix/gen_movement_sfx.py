#!/usr/bin/env python3
"""
Gera 4 SFX TEMP de superficie & pouso para DezLocomotionController:
  - footstep_floor_TEMP.wav  (piso industrial / pedra da oficina)
  - footstep_metal_TEMP.wav  (grade / plataforma metalica)
  - footstep_puddle_TEMP.wav (poca de oleo/agua da oficina)
  - landing_thud_TEMP.wav    (pouso com peso leve)
"""
import math
import os
import random
import struct
import wave

SR = 44100
OUT_DIR = "/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX/Movement"
os.makedirs(OUT_DIR, exist_ok=True)


def write_wav(name, samples):
    path = os.path.join(OUT_DIR, name)
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        buf = bytearray()
        for s in samples:
            v = max(-1.0, min(1.0, s))
            buf.extend(struct.pack("<h", int(v * 32767)))
        wf.writeframes(buf)
    print(f"WROTE {path} ({len(samples)/SR:.2f}s)")


def gen_floor():
    n = int(SR * 0.14)
    rng = random.Random(101)
    lp = 0.0
    out = []
    for i in range(n):
        t = i / SR
        nz = rng.random() * 2 - 1
        lp = lp * 0.86 + nz * 0.14
        s = (math.sin(2 * math.pi * 135 * t) * 0.35 + lp * 0.45) * math.exp(-t * 32.0)
        out.append(s)
    write_wav("footstep_floor_TEMP.wav", out)


def gen_metal():
    n = int(SR * 0.18)
    rng = random.Random(102)
    out = []
    for i in range(n):
        t = i / SR
        nz = rng.random() * 2 - 1
        ring = (math.sin(2 * math.pi * 520 * t) * 0.28 + math.sin(2 * math.pi * 1140 * t) * 0.20 + math.sin(2 * math.pi * 1890 * t) * 0.12) * math.exp(-t * 22.0)
        tap = nz * math.exp(-t * 55.0) * 0.35
        out.append(ring + tap)
    write_wav("footstep_metal_TEMP.wav", out)


def gen_puddle():
    n = int(SR * 0.20)
    rng = random.Random(103)
    lp = 0.0
    out = []
    for i in range(n):
        t = i / SR
        nz = rng.random() * 2 - 1
        lp = lp * 0.72 + nz * 0.28
        splash = (nz - lp) * 0.50 * math.exp(-t * 16.0)
        bloop = math.sin(2 * math.pi * (320 + t * 900) * t) * 0.18 * math.exp(-t * 24.0)
        out.append(splash + bloop)
    write_wav("footstep_puddle_TEMP.wav", out)


def gen_landing():
    n = int(SR * 0.24)
    rng = random.Random(104)
    lp = 0.0
    out = []
    for i in range(n):
        t = i / SR
        nz = rng.random() * 2 - 1
        lp = lp * 0.92 + nz * 0.08
        thud = (math.sin(2 * math.pi * (95 - t * 180) * t) * 0.58 + lp * 0.42) * math.exp(-t * 17.0)
        out.append(thud)
    write_wav("landing_thud_TEMP.wav", out)


if __name__ == "__main__":
    gen_floor()
    gen_metal()
    gen_puddle()
    gen_landing()
