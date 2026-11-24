#!/usr/bin/env python3
"""
Gera SFX TEMP da Missao 'Sinal':
  signal_antenna_capture_TEMP.wav (3.4s) — varredura de telemetria da antena apontada para a rachadura + glitch de registro corrompido + chime de captura.
"""
import math
import os
import random
import struct
import wave

SR = 44100
OUT_DIR = "/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX/Sector"
os.makedirs(OUT_DIR, exist_ok=True)

dur = 3.4
n = int(SR * dur)
rng = random.Random(7071)
samples = [0.0] * n

for i in range(n):
    t = i / SR
    s = 0.0

    # 1. Varredura crescente de telemetria (0.0..2.2s)
    if t < 2.3:
        p = t / 2.3
        freq = 280.0 + 720.0 * (p ** 1.6)
        pulse = 0.55 + 0.45 * math.sin(2 * math.pi * (6.0 + 10.0 * p) * t)
        s += (math.sin(2 * math.pi * freq * t) * 0.28 + math.sin(2 * math.pi * freq * 1.5 * t) * 0.12) * pulse

    # 2. Glitch digital / registro corrompido (2.1..2.65s)
    if 2.1 <= t <= 2.65:
        dt = t - 2.1
        stutter = 1.0 if int(dt * 28) % 2 == 0 else 0.15
        s += ((rng.random() * 2 - 1) * 0.24 + math.sin(2 * math.pi * 1420 * t) * 0.20) * stutter

    # 3. Chime cristalino de leitura capturada (2.65..3.4s)
    if t >= 2.65:
        dt = t - 2.65
        env = math.exp(-dt * 4.5)
        s += (math.sin(2 * math.pi * 587.33 * dt) * 0.30 + math.sin(2 * math.pi * 880.0 * dt) * 0.24 + math.sin(2 * math.pi * 1174.66 * dt) * 0.15) * env

    samples[i] = max(-0.95, min(0.95, s))

out_path = os.path.join(OUT_DIR, "signal_antenna_capture_TEMP.wav")
with wave.open(out_path, "w") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    buf = bytearray()
    for v in samples:
        buf.extend(struct.pack("<h", int(v * 32767)))
    wf.writeframes(buf)

print(f"WROTE {out_path} ({dur:.2f}s)")
