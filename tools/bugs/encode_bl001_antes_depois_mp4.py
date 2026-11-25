#!/usr/bin/env python3
"""
Encoda GATE 1 (captures/bugs/missao_reset_antes.mp4) e GATE 5 (captures/bugs/missao_reset_depois.mp4)
com o banner real de ObjectiveSystem.CurrentObjective desenhado a cada frame a partir de frames_meta.json.
"""
import json
import os
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(r"C:\Users\Bruno\workspace\game-concerto")
CAP_BASE = REPO_ROOT / "unity" / "Logs" / "bl001_capture"
OUT_DIR = REPO_ROOT / "captures" / "bugs"


def load_font(size: int):
    for cand in [r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf"]:
        if os.path.exists(cand):
            return ImageFont.truetype(cand, size)
    return ImageFont.load_default()


def encode_phase(phase: str, out_mp4: Path, is_bug: bool):
    src_dir = CAP_BASE / phase
    meta = json.loads((src_dir / "frames_meta.json").read_text(encoding="utf-8"))
    seq_dir = src_dir / "_annotated"
    seq_dir.mkdir(parents=True, exist_ok=True)
    for old in seq_dir.glob("*.jpg"):
        old.unlink()

    f_hdr = load_font(30)
    f_obj = load_font(34)
    f_sub = load_font(22)

    for item in meta:
        idx = item["f"]
        img = Image.open(src_dir / f"frame_{idx:04d}.jpg").convert("RGB").resize((1920, 1080), Image.Resampling.BILINEAR)
        draw = ImageDraw.Draw(img, "RGBA")

        # Banner de Objetivo real (top-left, refletindo exatamente ObjectiveSystem.CurrentObjective)
        obj_txt = item["objective"]
        broken = is_bug and obj_txt != "Peças (2/5)"
        border_col = (235, 68, 68, 255) if broken else (56, 224, 212, 255)
        draw.rectangle([(28, 28), (940, 134)], fill=(12, 16, 24, 225))
        draw.rectangle([(28, 28), (40, 134)], fill=border_col)
        draw.text((58, 36), "OBJETIVO ATUAL (ObjectiveSystem.CurrentObjective):", fill=(175, 198, 218, 255), font=f_sub)
        draw.text((58, 72), obj_txt, fill=(255, 110, 110, 255) if broken else (240, 252, 255, 255), font=f_obj)

        # Caixa de dialogo quando falando com Juno
        if item["talking"]:
            draw.rectangle([(260, 820), (1660, 960)], fill=(10, 14, 22, 225))
            draw.rectangle([(260, 820), (1660, 828)], fill=(64, 232, 248, 255))
            draw.text((300, 845), "JUNO (Diálogo ativo — re-conversando com NPC)", fill=(64, 232, 248, 255), font=f_sub)
            draw.text((300, 888), "\"Traz as peças pra bancada assim que encontrar...\"", fill=(240, 246, 255, 255), font=f_hdr)

        # Tarja inferior de status
        badge_col = (220, 62, 62, 255) if is_bug else (42, 200, 140, 255)
        tag = "GATE 1 — ANTES (REPRODUÇÃO DO BUG)" if is_bug else "GATE 5 — DEPOIS (FIX VALIDADO)"
        draw.rectangle([(0, 1010), (1920, 1080)], fill=(12, 15, 22, 225))
        draw.rectangle([(24, 1022), (38, 1068)], fill=badge_col)
        draw.text((54, 1028), f"{tag}   |   {item['step']}", fill=(240, 246, 255, 255), font=f_hdr)

        img.save(seq_dir / f"ann_{idx:04d}.jpg", quality=90)

    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-framerate", "12",
        "-i", str(seq_dir / "ann_%04d.jpg"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
        "-movflags", "+faststart", str(out_mp4),
    ], check=True)
    print(f"MP4_OK: {out_mp4} ({len(meta)} frames)")


if __name__ == "__main__":
    encode_phase("antes", OUT_DIR / "missao_reset_antes.mp4", is_bug=True)
    encode_phase("depois", OUT_DIR / "missao_reset_depois.mp4", is_bug=False)
