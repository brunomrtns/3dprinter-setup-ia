"""
Generate procedural CC0 WAV audio assets for CONCERTO Audio Pass.
License: CC0 1.0 Universal (100% original procedural synthesis, zero external samples).
Outputs directly into unity/Assets/Game/Audio/...
"""
import math
import os
import random
import struct
import wave

SR = 44100
GAME_AUDIO_ROOT = r"C:\Users\Bruno\workspace\game-concerto\unity\Assets\Game\Audio"


def write_wav(rel_path: str, samples: list[float], sample_rate: int = SR):
    full_path = os.path.join(GAME_AUDIO_ROOT, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    peak = max((abs(s) for s in samples), default=1.0)
    if peak > 0.95:
        scale = 0.92 / peak
        samples = [s * scale for s in samples]
    with wave.open(full_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        data = bytearray()
        for s in samples:
            v = max(-1.0, min(1.0, s))
            data.extend(struct.pack("<h", int(v * 32767)))
        wf.writeframes(data)
    print(f"[OK] {rel_path} ({len(samples)/sample_rate:.2f}s, {os.path.getsize(full_path)} bytes)")


def lowpass(samples: list[float], alpha: float) -> list[float]:
    out = []
    y = 0.0
    for x in samples:
        y = y + alpha * (x - y)
        out.append(y)
    return out


def gen_footstep_floor(seed: int, f_body: float, dur: float = 0.14):
    rng = random.Random(seed)
    n = int(SR * dur)
    raw = []
    for i in range(n):
        t = i / SR
        env = math.exp(-t * 36.0)
        thump = math.sin(2 * math.pi * (f_body * (1.0 - 0.45 * t / dur)) * t) * env * 0.65
        scuff = (rng.uniform(-1, 1)) * math.exp(-t * 52.0) * 0.42
        raw.append(thump + scuff)
    return lowpass(raw, 0.28)


def gen_footstep_metal(seed: int, f1: float, f2: float, dur: float = 0.22):
    rng = random.Random(seed)
    n = int(SR * dur)
    out = []
    for i in range(n):
        t = i / SR
        env_hit = math.exp(-t * 48.0)
        env_ring = math.exp(-t * 16.0)
        ring = (
            0.42 * math.sin(2 * math.pi * f1 * t)
            + 0.28 * math.sin(2 * math.pi * f2 * t)
            + 0.18 * math.sin(2 * math.pi * (f2 * 1.47) * t)
        ) * env_ring
        clang = rng.uniform(-1, 1) * env_hit * 0.45
        out.append((ring + clang) * 0.78)
    return out


def gen_footstep_puddle(seed: int, f_drop: float, dur: float = 0.26):
    rng = random.Random(seed)
    n = int(SR * dur)
    raw = []
    for i in range(n):
        t = i / SR
        env_splash = math.exp(-t * 15.0) * (1.0 - math.exp(-t * 140.0))
        noise = rng.uniform(-1, 1) * env_splash * 0.62
        # bubble/droplet pitch sweep
        drop_env = math.exp(-((t - 0.045) ** 2) / 0.0005)
        drop = math.sin(2 * math.pi * (f_drop + 420.0 * t) * t) * drop_env * 0.35
        raw.append(noise + drop)
    return lowpass(raw, 0.45)


def gen_jump_takeoff():
    rng = random.Random(404)
    dur = 0.20
    n = int(SR * dur)
    raw = []
    for i in range(n):
        t = i / SR
        env = math.exp(-t * 18.0) * (1.0 - math.exp(-t * 180.0))
        # Upward pitch whoosh + soft boot spring
        freq = 115.0 + 340.0 * (t / dur)
        tone = math.sin(2 * math.pi * freq * t) * env * 0.48
        cloth = rng.uniform(-1, 1) * math.exp(-t * 24.0) * 0.32
        raw.append(tone + cloth)
    return lowpass(raw, 0.35)


def gen_ui_open():
    dur = 0.18
    n = int(SR * dur)
    out = []
    for i in range(n):
        t = i / SR
        # Two-step warm brass/clockwork rise (C5 -> G5)
        if t < 0.065:
            e = math.exp(-t * 28.0)
            s = math.sin(2 * math.pi * 523.25 * t) * 0.55 + math.sin(2 * math.pi * 1046.5 * t) * 0.20
            out.append(s * e * 0.75)
        else:
            t2 = t - 0.065
            e = math.exp(-t2 * 22.0)
            s = math.sin(2 * math.pi * 783.99 * t2) * 0.55 + math.sin(2 * math.pi * 1567.98 * t2) * 0.18
            out.append(s * e * 0.78)
    return out


def gen_ui_close():
    dur = 0.16
    n = int(SR * dur)
    out = []
    for i in range(n):
        t = i / SR
        if t < 0.055:
            e = math.exp(-t * 32.0)
            s = math.sin(2 * math.pi * 659.25 * t) * 0.50
            out.append(s * e * 0.68)
        else:
            t2 = t - 0.055
            e = math.exp(-t2 * 26.0)
            s = math.sin(2 * math.pi * 440.0 * t2) * 0.52 + math.sin(2 * math.pi * 220.0 * t2) * 0.20
            out.append(s * e * 0.65)
    return out


def gen_ui_confirm():
    dur = 0.22
    n = int(SR * dur)
    out = []
    for i in range(n):
        t = i / SR
        e = math.exp(-t * 15.0) * (1.0 - math.exp(-t * 300.0))
        # Crisp warm harmonic triad (E5 + B5 + E6)
        s = (
            0.50 * math.sin(2 * math.pi * 659.25 * t)
            + 0.30 * math.sin(2 * math.pi * 987.77 * t)
            + 0.20 * math.sin(2 * math.pi * 1318.51 * t)
        )
        out.append(s * e * 0.78)
    return out


def gen_ui_deny():
    dur = 0.22
    n = int(SR * dur)
    out = []
    for i in range(n):
        t = i / SR
        # Muted double low pulse
        p1 = math.exp(-((t - 0.035) ** 2) / 0.0006)
        p2 = math.exp(-((t - 0.125) ** 2) / 0.0009)
        env = p1 + 0.85 * p2
        s = 0.55 * math.sin(2 * math.pi * 175.0 * t) + 0.30 * math.sin(2 * math.pi * 131.0 * t)
        out.append(s * env * 0.72)
    return out


def gen_workshop_warm_ambience():
    """Seamless 6.0s loop: subtle warm boiler room tone + gentle distant clockwork tick."""
    rng = random.Random(777)
    dur = 6.0
    n = int(SR * dur)
    raw = [0.0] * n
    # Seamless low-frequency harmonics (integer cycles in 6.0s)
    for i in range(n):
        t = i / SR
        hum = (
            0.22 * math.sin(2 * math.pi * 55.0 * t)
            + 0.12 * math.sin(2 * math.pi * 110.0 * t)
            + 0.06 * math.sin(2 * math.pi * 165.0 * t + 0.4)
        )
        # Gentle slow breathing modulation (1 cycle per 6s -> seamless!)
        mod = 0.82 + 0.18 * math.sin(2 * math.pi * (1.0 / dur) * t)
        # Soft warm air hiss
        air = rng.uniform(-1, 1) * 0.09
        raw[i] = (hum * mod) + air

    # Add gentle distant clockwork ticks every 0.75s (8 ticks in 6.0s -> seamless)
    for tick_idx in range(8):
        t0 = tick_idx * 0.75 + 0.12
        start = int(t0 * SR)
        tick_freq = 1480.0 if (tick_idx % 2 == 0) else 1240.0
        for j in range(int(0.035 * SR)):
            idx = (start + j) % n
            tj = j / SR
            env = math.exp(-tj * 130.0)
            raw[idx] += math.sin(2 * math.pi * tick_freq * tj) * env * 0.14

    filtered = lowpass(raw, 0.12)
    # Crossfade edges (last 0.15s blended into first 0.15s) for 100% clickless loop
    xf = int(0.15 * SR)
    for i in range(xf):
        a = i / xf
        filtered[i] = filtered[i] * a + filtered[n - xf + i] * (1.0 - a)
    return [s * 0.55 for s in filtered]


if __name__ == "__main__":
    # 2 extra variations per surface (bringing floor/metal/puddle to 3 each)
    write_wav("SFX/Movement/footstep_floor_02_TEMP.wav", gen_footstep_floor(102, 118.0, 0.13))
    write_wav("SFX/Movement/footstep_floor_03_TEMP.wav", gen_footstep_floor(103, 96.0, 0.15))
    write_wav("SFX/Movement/footstep_metal_02_TEMP.wav", gen_footstep_metal(202, 430.0, 790.0, 0.21))
    write_wav("SFX/Movement/footstep_metal_03_TEMP.wav", gen_footstep_metal(203, 515.0, 910.0, 0.19))
    write_wav("SFX/Movement/footstep_puddle_02_TEMP.wav", gen_footstep_puddle(302, 540.0, 0.24))
    write_wav("SFX/Movement/footstep_puddle_03_TEMP.wav", gen_footstep_puddle(303, 620.0, 0.27))

    # Jump takeoff
    write_wav("SFX/Movement/jump_takeoff_TEMP.wav", gen_jump_takeoff())

    # UI SFX (open / close / confirm / deny)
    write_wav("SFX/UI/ui_open_TEMP.wav", gen_ui_open())
    write_wav("SFX/UI/ui_close_TEMP.wav", gen_ui_close())
    write_wav("SFX/UI/ui_confirm_TEMP.wav", gen_ui_confirm())
    write_wav("SFX/UI/ui_deny_TEMP.wav", gen_ui_deny())

    # Warm workshop continuous ambience loop (for crossfade with sector_cold_wind_ambience_TEMP)
    write_wav("Ambience/workshop_warm_ambience_TEMP.wav", gen_workshop_warm_ambience())
    print("All procedural CC0 audio assets generated successfully.")
