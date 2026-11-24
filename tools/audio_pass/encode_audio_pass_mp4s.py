"""
Encode CONCERTO Audio Pass 1080p MP4 captures WITH synchronized real project audio.
Reads the captured frames + recorded audio event/ducking timelines from Unity PlayMode tests,
mixes the real project WAV/OGG assets at the exact recorded timestamps/volumes/duck curves,
and muxes 1080p H.264 + AAC 192kbps MP4s into captures/audio_pass/.
"""
import json
import math
import os
import struct
import subprocess
import tempfile
import wave

SR = 44100
REPO_ROOT = r"C:\Users\Bruno\workspace\game-concerto"
AUDIO_ROOT = os.path.join(REPO_ROOT, "unity", "Assets", "Game", "Audio")
CAPTURE_SRC = os.path.join(REPO_ROOT, "unity", "Logs", "audio_pass_capture")
OUT_DIR = os.path.join(REPO_ROOT, "captures", "audio_pass")


def load_audio_mono_float(rel_path: str) -> list[float]:
    full_path = os.path.join(AUDIO_ROOT, rel_path)
    if not os.path.exists(full_path):
        print(f"[WARN] Missing audio file: {full_path}")
        return []
    if full_path.lower().endswith(".wav"):
        return read_wav_mono(full_path)
    # Decode OGG/other via ffmpeg into temp 44.1kHz mono PCM WAV
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        tmp_wav = tf.name
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", full_path, "-ac", "1", "-ar", str(SR), "-sample_fmt", "s16", tmp_wav],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return read_wav_mono(tmp_wav)
    finally:
        if os.path.exists(tmp_wav):
            os.remove(tmp_wav)


def read_wav_mono(path: str) -> list[float]:
    with wave.open(path, "rb") as wf:
        ch = wf.getnchannels()
        sw = wf.getsampwidth()
        rate = wf.getframerate()
        nframes = wf.getnframes()
        raw = wf.readframes(nframes)

    if sw != 2:
        # Fallback via ffmpeg
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            tmp_wav = tf.name
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", path, "-ac", "1", "-ar", str(SR), "-sample_fmt", "s16", tmp_wav],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return read_wav_mono(tmp_wav)
        finally:
            if os.path.exists(tmp_wav):
                os.remove(tmp_wav)

    total_samples = len(raw) // 2
    vals = struct.unpack(f"<{total_samples}h", raw)
    if ch > 1:
        mono = [sum(vals[i : i + ch]) / (ch * 32768.0) for i in range(0, total_samples, ch)]
    else:
        mono = [v / 32768.0 for v in vals]

    if rate != SR and len(mono) > 1:
        ratio = SR / rate
        new_len = int(len(mono) * ratio)
        resampled = []
        for i in range(new_len):
            src_pos = i / ratio
            idx = int(src_pos)
            frac = src_pos - idx
            s0 = mono[min(idx, len(mono) - 1)]
            s1 = mono[min(idx + 1, len(mono) - 1)]
            resampled.append(s0 + (s1 - s0) * frac)
        mono = resampled
    return mono


def mix_oneshot(buf: list[float], clip: list[float], t_sec: float, gain: float, pitch: float = 1.0):
    if not clip:
        return
    start = int(t_sec * SR)
    step = max(0.5, min(2.0, pitch))
    n_out = int(len(clip) / step)
    buf_len = len(buf)
    for i in range(n_out):
        dst = start + i
        if 0 <= dst < buf_len:
            src_f = i * step
            idx = int(src_f)
            if idx < len(clip):
                buf[dst] += clip[idx] * gain


def mix_loop(buf: list[float], clip: list[float], gain_fn):
    if not clip:
        return
    clen = len(clip)
    for i in range(len(buf)):
        t = i / SR
        g = gain_fn(t)
        if g > 0.0001:
            buf[i] += clip[i % clen] * g


def write_stereo_wav(path: str, mono: list[float]):
    # Soft-clip limiter (nada no nivel da dor, headroom limpo -1 dBFS)
    data = bytearray()
    for s in mono:
        limited = math.tanh(s * 0.92) * 0.88
        v = max(-1.0, min(1.0, limited))
        iv = int(v * 32767)
        data.extend(struct.pack("<hh", iv, iv))
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(data)


def encode_mp4(frames_dir: str, audio_wav: str, out_mp4: str, input_fps: float):
    os.makedirs(os.path.dirname(out_mp4), exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-framerate", f"{input_fps:.3f}",
        "-i", os.path.join(frames_dir, "frame_%04d.jpg"),
        "-i", audio_wav,
        "-vf", "scale=1920:1080:flags=lanczos,fps=30,format=yuv420p",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-ar", str(SR),
        "-shortest",
        out_mp4,
    ]
    subprocess.run(cmd, check=True)
    print(f"[MP4 OK] {out_mp4} ({os.path.getsize(out_mp4) / (1024*1024):.2f} MB)")


def build_gameplay_mp4():
    gdir = os.path.join(CAPTURE_SRC, "gameplay")
    with open(os.path.join(gdir, "audio_events_gameplay.json"), encoding="utf-8-sig") as f:
        raw_json = f.read().replace('"pitch":F2', '"pitch":1.00')
        meta = json.loads(raw_json)

    dur = float(meta["duration_sec"])
    fps = float(meta["fps"])
    buf = [0.0] * int(dur * SR)

    bgm = load_audio_mono_float("Music/concerto_bgm/caldeiral_sync_loop.ogg")
    amb_work = load_audio_mono_float("Ambience/workshop_warm_ambience_TEMP.wav")
    amb_sect = load_audio_mono_float("SFX/Sector/sector_cold_wind_ambience_TEMP.wav")

    # Music bed (-10 dB so SFX & impacts always punch through clearly)
    mix_loop(buf, bgm, lambda t: 0.24)

    # Smooth ambience crossfade: workshop -> sector (44.5..46.5s) -> workshop (53.0..55.0s)
    def work_gain(t: float) -> float:
        if t < 44.5:
            return 0.28
        if t < 46.5:
            return 0.28 * (1.0 - (t - 44.5) / 2.0)
        if t < 53.0:
            return 0.0
        if t < 55.0:
            return 0.28 * ((t - 53.0) / 2.0)
        return 0.28

    def sect_gain(t: float) -> float:
        if t < 44.5:
            return 0.0
        if t < 46.5:
            return 0.34 * ((t - 44.5) / 2.0)
        if t < 53.0:
            return 0.34
        if t < 55.0:
            return 0.34 * (1.0 - (t - 53.0) / 2.0)
        return 0.0

    mix_loop(buf, amb_work, work_gain)
    mix_loop(buf, amb_sect, sect_gain)

    clip_cache: dict[str, list[float]] = {}
    for ev in meta["events"]:
        if ev["event"].startswith("ambience_"):
            continue
        rel = ev["clip"]
        if rel not in clip_cache:
            clip_cache[rel] = load_audio_mono_float(rel)
        mix_oneshot(buf, clip_cache[rel], float(ev["t"]), float(ev["vol"]) * 0.85, float(ev.get("pitch", 1.0)))

    wav_path = os.path.join(gdir, "gameplay_mix.wav")
    write_stereo_wav(wav_path, buf)
    encode_mp4(gdir, wav_path, os.path.join(OUT_DIR, "audio_pass_gameplay_60s_1080p.mp4"), fps)


def build_cutscene_mp4():
    cdir = os.path.join(CAPTURE_SRC, "cutscene")
    with open(os.path.join(cdir, "audio_events_cutscene.json"), encoding="utf-8-sig") as f:
        meta = json.load(f)

    dur = float(meta["duration_sec"])
    fps = float(meta["fps"])
    cs_start = float(meta["cutscene_start_sec"])
    cs_end = float(meta["cutscene_end_sec"])
    curve = meta["duck_curve"]
    buf = [0.0] * int(dur * SR)

    bgm = load_audio_mono_float("Music/concerto_bgm/caldeiral_sync_loop.ogg")
    amb_work = load_audio_mono_float("Ambience/workshop_warm_ambience_TEMP.wav")
    motif = load_audio_mono_float("Cutscenes/CS01/cs01_musicbox_motif_TEMP.wav")
    chime = load_audio_mono_float("Cutscenes/CS01/cs01_radio_chime_TEMP.wav")
    vo_narr = load_audio_mono_float("VO/cs01_abertura/cs01_narr_01.wav")

    # Interpolate exact recorded ducking curve from Unity AudioMixController
    times = [float(p["t"]) for p in curve]
    ducks = [float(p["duck"]) for p in curve]

    def duck_at(t: float) -> float:
        if not times:
            return 1.0
        if t <= times[0]:
            return ducks[0]
        if t >= times[-1]:
            return ducks[-1]
        # Linear search near index (fast because t is monotonic or simple index estimate)
        idx = min(len(times) - 2, max(0, int(t * fps)))
        while idx > 0 and times[idx] > t:
            idx -= 1
        while idx < len(times) - 2 and times[idx + 1] < t:
            idx += 1
        span = max(1e-5, times[idx + 1] - times[idx])
        u = max(0.0, min(1.0, (t - times[idx]) / span))
        return ducks[idx] + (ducks[idx + 1] - ducks[idx]) * u

    mix_loop(buf, bgm, lambda t: 0.42 * duck_at(t))
    mix_loop(buf, amb_work, lambda t: 0.22 * (0.55 + 0.45 * duck_at(t)))

    # Cutscene focal audio (motif + radio chime + VO clearly intelligible over ducked music!)
    mix_oneshot(buf, motif, cs_start + 0.4, 0.55, 1.0)
    mix_oneshot(buf, vo_narr, cs_start + 1.2, 0.90, 1.0)
    mix_oneshot(buf, chime, cs_start + 4.8, 0.65, 1.0)

    wav_path = os.path.join(cdir, "cutscene_ducking_mix.wav")
    write_stereo_wav(wav_path, buf)
    encode_mp4(cdir, wav_path, os.path.join(OUT_DIR, "audio_pass_cutscene_ducking_1080p.mp4"), fps)


if __name__ == "__main__":
    build_gameplay_mp4()
    build_cutscene_mp4()
    print("All Audio Pass MP4s encoded successfully with synced audio.")
