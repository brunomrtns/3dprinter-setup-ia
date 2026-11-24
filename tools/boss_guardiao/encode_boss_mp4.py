"""
Encode CONCERTO #103 (Mini-boss Guardiao da Fenda — luta completa + vitoria + holograma + Fim do Ato 3) 1080p MP4.
"""
import json, math, os, struct, subprocess, tempfile, wave

SR = 44100
REPO = r"C:\Users\Bruno\workspace\game-concerto"
AUDIO_ROOT = os.path.join(REPO, "unity", "Assets", "Game", "Audio")
SRC_DIR = os.path.join(REPO, "unity", "Logs", "boss_capture")
OUT_MP4 = os.path.join(REPO, "captures", "boss_guardiao", "guardiao_luta_completa_vitoria_1080p.mp4")


def load_mono(rel_path: str) -> list[float]:
    full = os.path.join(AUDIO_ROOT, rel_path)
    if not os.path.exists(full):
        return []
    if full.lower().endswith(".wav"):
        with wave.open(full, "rb") as wf:
            ch, nf = wf.getnchannels(), wf.getnframes()
            raw = wf.readframes(nf)
        vals = struct.unpack(f"<{len(raw)//2}h", raw)
        return [sum(vals[i:i+ch])/(ch*32768.0) for i in range(0, len(vals), ch)] if ch > 1 else [v/32768.0 for v in vals]
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        tmp = tf.name
    try:
        subprocess.run(["ffmpeg", "-y", "-i", full, "-ac", "1", "-ar", str(SR), "-sample_fmt", "s16", tmp],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with wave.open(tmp, "rb") as wf:
            raw = wf.readframes(wf.getnframes())
        vals = struct.unpack(f"<{len(raw)//2}h", raw)
        return [v / 32768.0 for v in vals]
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def main():
    with open(os.path.join(SRC_DIR, "boss_events.json"), encoding="utf-8-sig") as f:
        meta = json.load(f)
    dur, fps = float(meta["duration_sec"]), float(meta["fps"])
    buf = [0.0] * max(SR, int((dur + 0.5) * SR))

    bgm = load_mono("Music/concerto_bgm/caldeiral_combat_contratempo.ogg")
    # Musica do boss para no dissolve (silencio dramatico antes do holograma!)
    dissolve_t = next((float(e["t"]) for e in meta["events"] if e["event"] == "boss_dissolve"), dur)
    if bgm:
        for i in range(len(buf)):
            t = i / SR
            if t < dissolve_t:
                buf[i] += bgm[i % len(bgm)] * 0.28

    cache = {}
    for ev in meta["events"]:
        rel = ev["clip"]
        if rel not in cache:
            cache[rel] = load_mono(rel)
        clip = cache[rel]
        s0 = int(float(ev["t"]) * SR)
        for i, v in enumerate(clip):
            idx = s0 + i
            if 0 <= idx < len(buf):
                buf[idx] += v * 0.90

    wav_out = os.path.join(SRC_DIR, "boss_mix.wav")
    data = bytearray()
    for s in buf:
        v = max(-1.0, min(1.0, math.tanh(s * 0.92) * 0.88))
        iv = int(v * 32767)
        data.extend(struct.pack("<hh", iv, iv))
    with wave.open(wav_out, "wb") as wf:
        wf.setnchannels(2); wf.setsampwidth(2); wf.setframerate(SR)
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
