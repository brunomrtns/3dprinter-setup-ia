"""
Encode CONCERTO #93 (Poderes do Dez: Eco Temporal + Estase) 1080p MP4 with synced SFX audio.
"""
import json
import math
import os
import struct
import subprocess
import wave

SR = 44100
REPO = r"C:\Users\Bruno\workspace\game-concerto"
AUDIO_ROOT = os.path.join(REPO, "unity", "Assets", "Game", "Audio")
SRC_DIR = os.path.join(REPO, "unity", "Logs", "powers_capture")
OUT_MP4 = os.path.join(REPO, "captures", "powers", "dez_powers_eco_estase_1080p.mp4")


def read_wav_mono(path: str) -> list[float]:
    if not os.path.exists(path):
        return []
    with wave.open(path, "rb") as wf:
        ch, sw, rate, nf = wf.getnchannels(), wf.getsampwidth(), wf.getframerate(), wf.getnframes()
        raw = wf.readframes(nf)
    vals = struct.unpack(f"<{len(raw)//2}h", raw)
    mono = [sum(vals[i:i+ch]) / (ch * 32768.0) for i in range(0, len(vals), ch)] if ch > 1 else [v / 32768.0 for v in vals]
    return mono


def mix_oneshot(buf, clip, t_sec, gain):
    s0 = int(t_sec * SR)
    for i, v in enumerate(clip):
        idx = s0 + i
        if 0 <= idx < len(buf):
            buf[idx] += v * gain


def main():
    with open(os.path.join(SRC_DIR, "powers_events.json"), encoding="utf-8-sig") as f:
        meta = json.load(f)
    dur = float(meta["duration_sec"])
    fps = float(meta["fps"])
    buf = [0.0] * max(SR, int((dur + 0.5) * SR))

    amb = read_wav_mono(os.path.join(AUDIO_ROOT, "Ambience", "workshop_warm_ambience_TEMP.wav"))
    if amb:
        for i in range(len(buf)):
            buf[i] += amb[i % len(amb)] * 0.25

    for ev in meta["events"]:
        clip = read_wav_mono(os.path.join(AUDIO_ROOT, ev["clip"]))
        mix_oneshot(buf, clip, float(ev["t"]), 0.90)

    wav_out = os.path.join(SRC_DIR, "powers_mix.wav")
    data = bytearray()
    for s in buf:
        v = max(-1.0, min(1.0, math.tanh(s * 0.92) * 0.88))
        iv = int(v * 32767)
        data.extend(struct.pack("<hh", iv, iv))
    with wave.open(wav_out, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(data)

    os.makedirs(os.path.dirname(OUT_MP4), exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y",
        "-framerate", f"{fps:.3f}",
        "-i", os.path.join(SRC_DIR, "frame_%04d.jpg"),
        "-i", wav_out,
        "-vf", "scale=1920:1080:flags=lanczos,fps=30,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "21",
        "-c:a", "aac", "-b:a", "192k", "-ar", str(SR),
        "-shortest", OUT_MP4
    ], check=True)
    print(f"[MP4 OK] {OUT_MP4} ({os.path.getsize(OUT_MP4)/(1024*1024):.2f} MB)")


if __name__ == "__main__":
    main()
