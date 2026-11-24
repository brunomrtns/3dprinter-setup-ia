#!/usr/bin/env python3
"""
Encoda o MP4 1080p ANTES/DEPOIS do FIX 1 (VFX de morte/dissolve sem shader magenta -> URP/Particles/Unlit ciano).
Le os frames capturados em unity/Logs/review_fix_93_94_capture/ (before_0000.jpg.. e after_0000.jpg..),
adiciona tarjas limpas ANTES / DEPOIS com PIL e gera MP4 H.264 1920x1080 com audio sincronizado.
"""
import os
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(r"C:\Users\Bruno\workspace\game-concerto")
FRAMES_DIR = REPO_ROOT / "unity" / "Logs" / "review_fix_93_94_capture"
OUT_MP4 = REPO_ROOT / "captures" / "review_fix_93_94" / "fix1_dissolve_antes_depois_1080p.mp4"
SFX_ROOT = REPO_ROOT / "unity" / "Assets" / "Game" / "Resources" / "Audio"


def load_font(size: int):
    for cand in [
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\calibrib.ttf",
    ]:
        if os.path.exists(cand):
            return ImageFont.truetype(cand, size)
    return ImageFont.load_default()


def annotate_frame(src_path: Path, dst_path: Path, badge_text: str, sub_text: str, badge_rgb):
    img = Image.open(src_path).convert("RGB").resize((1920, 1080), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(img, "RGBA")
    # Tarja superior discreta
    draw.rectangle([(0, 0), (1920, 92)], fill=(12, 16, 24, 205))
    draw.rectangle([(28, 18), (44, 74)], fill=(*badge_rgb, 255))
    f_title = load_font(34)
    f_sub = load_font(22)
    draw.text((62, 16), badge_text, fill=(245, 248, 255, 255), font=f_title)
    draw.text((62, 56), sub_text, fill=(185, 202, 224, 255), font=f_sub)
    img.save(dst_path, quality=92)


def main():
    before_frames = sorted(FRAMES_DIR.glob("before_*.jpg"))
    after_frames = sorted(FRAMES_DIR.glob("after_*.jpg"))
    if not before_frames or not after_frames:
        print(f"ERRO: frames nao encontrados em {FRAMES_DIR}", file=sys.stderr)
        sys.exit(1)

    seq_dir = FRAMES_DIR / "_seq1080"
    seq_dir.mkdir(parents=True, exist_ok=True)
    for old in seq_dir.glob("*.jpg"):
        old.unlink()

    idx = 0
    # 2x hold para leitura confortavel em 15fps (~4.8s ANTES + 4.8s DEPOIS = ~9.6s)
    for p in before_frames:
        dst = seq_dir / f"seq_{idx:04d}.jpg"
        annotate_frame(
            p,
            dst,
            "ANTES — BUG ORIGINAL (PARTICULAS MAGENTA / SEM SHADER)",
            "ManifestationEnemyBase.SpawnGlitchDissolveParticles() sem ParticleSystemRenderer.sharedMaterial",
            (235, 58, 168),
        )
        idx += 1
        # duplica frame durante o pico do dissolve (frames 8..28) para slow-mo legivel
        if 8 <= int(p.stem.split("_")[1]) <= 28:
            dst2 = seq_dir / f"seq_{idx:04d}.jpg"
            dst2.write_bytes(dst.read_bytes())
            idx += 1

    before_count = idx

    for p in after_frames:
        dst = seq_dir / f"seq_{idx:04d}.jpg"
        annotate_frame(
            p,
            dst,
            "DEPOIS — FIX 1 (URP/Particles/Unlit CIANO CACHEADO)",
            "Material estatico URP/Particles/Unlit atribuido ao ParticleSystemRenderer + swing real MultiTool",
            (64, 232, 248),
        )
        idx += 1
        if 8 <= int(p.stem.split("_")[1]) <= 28:
            dst2 = seq_dir / f"seq_{idx:04d}.jpg"
            dst2.write_bytes(dst.read_bytes())
            idx += 1

    fps = 15
    total_dur = idx / fps
    t_before_hit = 8.0 / fps
    t_after_hit = (before_count + 8.0) / fps

    OUT_MP4.parent.mkdir(parents=True, exist_ok=True)

    hit_wav = SFX_ROOT / "SFX" / "Tool" / "tool_melee_hit_TEMP.wav"
    diss_wav = SFX_ROOT / "SFX" / "Combat" / "sfx_enemy_dissolve_reverse_TEMP.wav"

    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(seq_dir / "seq_%04d.jpg"),
    ]
    if hit_wav.exists() and diss_wav.exists():
        ms_b_hit = int(t_before_hit * 1000)
        ms_b_dis = int((t_before_hit + 0.12) * 1000)
        ms_a_hit = int(t_after_hit * 1000)
        ms_a_dis = int((t_after_hit + 0.12) * 1000)
        cmd += [
            "-i", str(hit_wav),
            "-i", str(diss_wav),
            "-filter_complex",
            (
                f"anullsrc=r=44100:cl=stereo:d={total_dur:.2f}[bg];"
                f"[1:a]asplit=2[h1][h2];"
                f"[2:a]asplit=2[d1][d2];"
                f"[h1]adelay={ms_b_hit}|{ms_b_hit},volume=0.85[h1d];"
                f"[d1]adelay={ms_b_dis}|{ms_b_dis},volume=0.90[d1d];"
                f"[h2]adelay={ms_a_hit}|{ms_a_hit},volume=0.85[h2d];"
                f"[d2]adelay={ms_a_dis}|{ms_a_dis},volume=0.90[d2d];"
                f"[bg][h1d][d1d][h2d][d2d]amix=inputs=5:duration=first:normalize=0[aout]"
            ),
            "-map", "0:v", "-map", "[aout]",
            "-c:a", "aac", "-b:a", "192k",
        ]
    else:
        cmd += ["-an"]

    cmd += [
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
        "-movflags", "+faststart",
        str(OUT_MP4),
    ]
    print("Executando ffmpeg:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"MP4 gerado com sucesso: {OUT_MP4} ({idx} frames, {total_dur:.2f}s)")


if __name__ == "__main__":
    main()
