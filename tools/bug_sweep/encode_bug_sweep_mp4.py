"""
Encode CONCERTO #106 (Varredura de Bugs — rota limpa Boot->Ato 3 + prova dos 3 fixes P0) 1080p MP4 with audio.
"""
import os, subprocess

REPO = r"C:\Users\Bruno\workspace\game-concerto"
SRC_DIR = os.path.join(REPO, "unity", "Logs", "bug_sweep_capture")
BGM = os.path.join(REPO, "unity", "Assets", "Game", "Audio", "Music", "concerto_bgm", "caldeiral_sync_loop.ogg")
OUT_MP4 = os.path.join(REPO, "captures", "bug_sweep", "bug_sweep_rota_limpa_e_fixes_1080p.mp4")

os.makedirs(os.path.dirname(OUT_MP4), exist_ok=True)
subprocess.run([
    "ffmpeg", "-y",
    "-framerate", "15",
    "-i", os.path.join(SRC_DIR, "frame_%04d.jpg"),
    "-stream_loop", "-1", "-i", BGM,
    "-vf", "scale=1920:1080:flags=lanczos,fps=30,format=yuv420p",
    "-af", "volume=0.35",
    "-c:v", "libx264", "-preset", "medium", "-crf", "21",
    "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
    "-shortest", OUT_MP4
], check=True)
print(f"[MP4 OK] {OUT_MP4} ({os.path.getsize(OUT_MP4)/(1024*1024):.2f} MB)")
