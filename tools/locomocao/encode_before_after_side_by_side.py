#!/usr/bin/env python3
"""
Encoda GATE 6: captures/animacao/dez_locomocao_antes_depois_1080p.mp4
Comparativo LADO A LADO 1920x1080 (30s ANTES a esquerda vs 30s DEPOIS a direita),
mesma rota e angulo em Caldeiral: andar, correr, parar brusco, pular/cair/aterrissar, interagir.
"""
import os
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(r"C:\Users\Bruno\workspace\game-concerto")
BASE_DIR = REPO_ROOT / "unity" / "Logs" / "locomocao_capture"
BEFORE_DIR = BASE_DIR / "before"
AFTER_DIR = BASE_DIR / "after"
OUT_MP4 = REPO_ROOT / "captures" / "animacao" / "dez_locomocao_antes_depois_1080p.mp4"


def load_font(size: int):
    for cand in [
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\calibrib.ttf",
    ]:
        if os.path.exists(cand):
            return ImageFont.truetype(cand, size)
    return ImageFont.load_default()


def phase_label(sec: float) -> str:
    if sec < 5.0:
        return "01 / 06  —  ANDAR (WALK 2.2 m/s)"
    if sec < 11.0:
        return "02 / 06  —  CORRER (RUN 5.4 m/s)"
    if sec < 14.0:
        return "03 / 06  —  PARAR BRUSCO  →  IDLE"
    if sec < 20.0:
        return "04 / 06  —  PULAR  →  CAIR  →  ATERRISSAR (COYOTE 100ms / BUFFER 150ms)"
    if sec < 24.0:
        return "05 / 06  —  APROXIMAR DO OBJETO (FASE 1 — OFICINA)"
    return "06 / 06  —  INTERAGIR COM OBJETO (ANIMATION RIGGING HAND IK)"


def main():
    before_frames = sorted(BEFORE_DIR.glob("frame_*.jpg"))
    after_frames = sorted(AFTER_DIR.glob("frame_*.jpg"))
    n = min(len(before_frames), len(after_frames))
    if n < 100:
        print(f"ERRO: frames insuficientes (before={len(before_frames)}, after={len(after_frames)})", file=sys.stderr)
        sys.exit(1)

    seq_dir = BASE_DIR / "_side_by_side_1080"
    seq_dir.mkdir(parents=True, exist_ok=True)
    for old in seq_dir.glob("*.jpg"):
        old.unlink()

    f_hdr = load_font(28)
    f_sub = load_font(22)
    fps = 15

    for i in range(n):
        img_l = Image.open(before_frames[i]).convert("RGB").resize((960, 1080), Image.Resampling.BILINEAR)
        img_r = Image.open(after_frames[i]).convert("RGB").resize((960, 1080), Image.Resampling.BILINEAR)

        canvas = Image.new("RGB", (1920, 1080))
        canvas.paste(img_l, (0, 0))
        canvas.paste(img_r, (960, 0))

        draw = ImageDraw.Draw(canvas, "RGBA")
        # Divisoria central limpa
        draw.rectangle([(958, 0), (962, 1080)], fill=(255, 255, 255, 220))

        # Cabecalhos ANTES / DEPOIS
        draw.rectangle([(0, 0), (958, 66)], fill=(16, 18, 26, 210))
        draw.rectangle([(18, 14), (30, 52)], fill=(235, 92, 92, 255))
        draw.text((44, 18), "ANTES — ANIMACAO ANTERIOR (PROCEDURAL + MOMASK)", fill=(245, 245, 250, 255), font=f_hdr)

        draw.rectangle([(962, 0), (1920, 66)], fill=(16, 18, 26, 210))
        draw.rectangle([(980, 14), (992, 52)], fill=(64, 232, 248, 255))
        draw.text((1006, 18), "DEPOIS — STARTER ASSETS + BLEND TREE + ANIMATION RIGGING IK", fill=(245, 248, 255, 255), font=f_hdr)

        # Rodape com fase sincronizada
        sec = i / float(fps)
        draw.rectangle([(0, 1022), (1920, 1080)], fill=(12, 15, 22, 215))
        draw.text((32, 1036), f"{phase_label(sec)}    |    t = {sec:04.1f}s / 30.0s", fill=(225, 238, 255, 255), font=f_sub)

        canvas.save(seq_dir / f"sbs_{i:04d}.jpg", quality=90)

    OUT_MP4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(seq_dir / "sbs_%04d.jpg"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-preset", "medium",
        "-movflags", "+faststart",
        str(OUT_MP4),
    ]
    subprocess.run(cmd, check=True)
    print(f"MP4 lado-a-lado gerado: {OUT_MP4} ({n} frames, {n / fps:.1f}s)")


if __name__ == "__main__":
    main()
