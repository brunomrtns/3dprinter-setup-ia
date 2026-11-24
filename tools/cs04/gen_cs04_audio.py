#!/usr/bin/env python3
"""
Gera os 2 SFX TEMP da Cutscene 4 ("O Céu Rachou"):
  1. cs04_alarm_backup_TEMP.wav (10s) — alarme discreto industrial + queda de relé de energia para backup.
  2. cs04_heavy_door_unlock_TEMP.wav (8s) — trancas metálicas pesadas, despressurização, ranger de ferro e lufada de vento frio.
"""
import math
import os
import random
import struct
import wave

SR = 44100
OUT_DIR = "/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Audio/SFX/Cutscenes"
os.makedirs(OUT_DIR, exist_ok=True)


def write_wav(path: str, samples):
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


def gen_alarm_backup():
    dur = 10.0
    n = int(SR * dur)
    samples = [0.0] * n
    rng = random.Random(4041)

    for i in range(n):
        t = i / SR
        # Queda de energia / relé elétrico em t=0.45s
        s = 0.0
        if 0.45 <= t <= 0.72:
            dt = t - 0.45
            s += math.sin(2 * math.pi * (140 - dt * 320) * dt) * math.exp(-dt * 14.0) * 0.55
            s += (rng.random() * 2 - 1) * math.exp(-dt * 24.0) * 0.25

        # Zumbido grave de energia de backup (60Hz + 120Hz suave)
        hum = (math.sin(2 * math.pi * 60 * t) * 0.07 + math.sin(2 * math.pi * 120 * t) * 0.03)
        hum *= min(1.0, t / 0.8)

        # Alarme discreto industrial: pulso duplo a cada 1.8s (não estridente, tenso)
        cycle = (t - 0.8) % 1.8 if t >= 0.8 else -1.0
        alarm = 0.0
        if 0.0 <= cycle < 0.26:
            env = math.sin(math.pi * (cycle / 0.26))
            alarm = (math.sin(2 * math.pi * 440 * t) * 0.22 + math.sin(2 * math.pi * 660 * t) * 0.08) * env
        elif 0.34 <= cycle < 0.54:
            env = math.sin(math.pi * ((cycle - 0.34) / 0.20))
            alarm = (math.sin(2 * math.pi * 392 * t) * 0.19 + math.sin(2 * math.pi * 588 * t) * 0.06) * env

        fade_out = 1.0 if t < 9.0 else max(0.0, (10.0 - t) / 1.0)
        samples[i] = (s + hum + alarm) * fade_out

    write_wav(os.path.join(OUT_DIR, "cs04_alarm_backup_TEMP.wav"), samples)


def gen_heavy_door_unlock():
    dur = 8.0
    n = int(SR * dur)
    samples = [0.0] * n
    rng = random.Random(4042)
    lp_noise = 0.0

    # Três pancadas de trava metálica pesada em t=0.6s, 1.5s, 2.5s
    clunks = [0.6, 1.5, 2.5]

    for i in range(n):
        t = i / SR
        noise = rng.random() * 2.0 - 1.0
        lp_noise = lp_noise * 0.96 + noise * 0.04
        s = 0.0

        # 1. Trancas metálicas
        for ct in clunks:
            if ct <= t <= ct + 0.45:
                dt = t - ct
                ring = (
                    math.sin(2 * math.pi * 115 * dt) * 0.45
                    + math.sin(2 * math.pi * 278 * dt) * 0.28
                    + math.sin(2 * math.pi * 612 * dt) * 0.14
                ) * math.exp(-dt * 9.5)
                impact = noise * math.exp(-dt * 42.0) * 0.5
                s += ring + impact

        # 2. Descarga pneumática / pressão (t=2.8..4.6s)
        if 2.8 <= t <= 4.7:
            dt = t - 2.8
            env = math.sin(math.pi * min(1.0, dt / 1.9))
            hiss = (noise - lp_noise) * 0.30 * env
            s += hiss

        # 3. Ranger pesado da porta deslizando/abrindo (t=3.4..6.8s)
        if 3.4 <= t <= 6.8:
            dt = t - 3.4
            env = math.sin(math.pi * (dt / 3.4))
            freq = 72.0 + 18.0 * math.sin(dt * 3.1)
            groan = (
                math.sin(2 * math.pi * freq * dt) * 0.24
                + math.sin(2 * math.pi * (freq * 2.03) * dt) * 0.12
                + lp_noise * 0.22
            ) * env
            s += groan

        # 4. Lufada de vento frio entrando pelo vão da porta (t=4.5..8.0s)
        if t >= 4.5:
            dt = t - 4.5
            env = min(1.0, dt / 1.8)
            wind_mod = 0.65 + 0.35 * math.sin(2 * math.pi * 0.35 * dt)
            s += lp_noise * 0.45 * env * wind_mod

        samples[i] = max(-0.95, min(0.95, s))

    write_wav(os.path.join(OUT_DIR, "cs04_heavy_door_unlock_TEMP.wav"), samples)


if __name__ == "__main__":
    gen_alarm_backup()
    gen_heavy_door_unlock()
