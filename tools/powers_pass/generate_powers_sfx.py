"""
Generate CC0 procedural SFX for CONCERTO #93 (Poderes do Dez: Eco Temporal + Estase).
License: CC0 1.0 Universal (100% original mathematical synthesis).
"""
import math
import os
import random
import struct
import wave

SR = 44100
OUT_DIR = r"C:\Users\Bruno\workspace\game-concerto\unity\Assets\Game\Audio\SFX\Powers"


def write_wav(filename: str, samples: list[float]):
    os.makedirs(OUT_DIR, exist_ok=True)
    full = os.path.join(OUT_DIR, filename)
    peak = max((abs(s) for s in samples), default=1.0)
    if peak > 0.92:
        sc = 0.90 / peak
        samples = [s * sc for s in samples]
    with wave.open(full, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        buf = bytearray()
        for s in samples:
            buf.extend(struct.pack("<h", int(max(-1.0, min(1.0, s)) * 32767)))
        wf.writeframes(buf)
    print(f"[OK] {filename} ({len(samples)/SR:.2f}s)")


def gen_eco_reverse_sfx():
    """Eco Temporal: whoosh ciano com 're' sutil (envelope invertido + chime cristalino reverso)."""
    rng = random.Random(9301)
    dur = 0.34
    n = int(SR * dur)
    # Constroi um chime+whoosh normal e inverte os primeiros 65% para dar assinatura 're' (reverse)
    fwd = []
    for i in range(n):
        t = i / SR
        env = math.exp(-t * 14.0)
        chime = (
            0.45 * math.sin(2 * math.pi * (880.0 - 320.0 * t) * t)
            + 0.25 * math.sin(2 * math.pi * (1320.0 - 400.0 * t) * t)
        ) * env
        air = rng.uniform(-1, 1) * math.exp(-t * 18.0) * 0.32
        fwd.append(chime + air)
    rev_part = list(reversed(fwd[: int(n * 0.68)]))
    tail = [fwd[i] * 0.65 for i in range(int(n * 0.32))]
    combined = rev_part + tail
    # Suaviza extremidades
    fade = int(0.015 * SR)
    for i in range(fade):
        a = i / fade
        combined[i] *= a
        combined[-1 - i] *= a
    return combined


def gen_estase_pulse_sfx():
    """Estase: pulsacao grave que 'freia' o ar (pitch drop + ressonancia temporal)."""
    rng = random.Random(9302)
    dur = 0.65
    n = int(SR * dur)
    out = []
    phase = 0.0
    for i in range(n):
        t = i / SR
        u = t / dur
        # Queda de frequencia 240 Hz -> 52 Hz (sensacao de mundo desacelerando)
        freq = 240.0 * ((1.0 - u) ** 1.6) + 52.0
        phase += 2.0 * math.pi * freq / SR
        env = (1.0 - math.exp(-t * 45.0)) * math.exp(-t * 4.2)
        sub = 0.65 * math.sin(phase) + 0.28 * math.sin(phase * 1.5)
        shimmer = 0.14 * math.sin(2 * math.pi * (520.0 * (1.0 - 0.55 * u)) * t) * math.exp(-t * 7.5)
        air = rng.uniform(-1, 1) * 0.12 * math.exp(-t * 9.0)
        out.append((sub + shimmer + air) * env)
    return out


if __name__ == "__main__":
    write_wav("sfx_eco_temporal_reverse_TEMP.wav", gen_eco_reverse_sfx())
    write_wav("sfx_estase_pulse_TEMP.wav", gen_estase_pulse_sfx())
