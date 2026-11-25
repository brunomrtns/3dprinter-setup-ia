import json
import os
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

CAPTURE_DIR = Path(r"C:\Users\Bruno\workspace\game-concerto\unity\Logs\ui_a11y_capture")
OUT_MP4 = Path(r"C:\Users\Bruno\workspace\game-concerto\captures\ui\ui_navegacao_controle_3min.mp4")


def load_font(size: int):
    for candidate in (
        r"C:\Windows\Fonts\segoeuib.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ):
        if os.path.exists(candidate):
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def main():
    meta_path = CAPTURE_DIR / "ui_a11y_meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing {meta_path}")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    frames = meta.get("frames", [])
    if not frames:
        raise RuntimeError("No frames recorded in ui_a11y_meta.json")

    ann_dir = CAPTURE_DIR / "_annotated"
    ann_dir.mkdir(parents=True, exist_ok=True)
    OUT_MP4.parent.mkdir(parents=True, exist_ok=True)

    f_title = load_font(28)
    f_ctrl = load_font(24)
    f_state = load_font(22)
    f_badge = load_font(22)

    for i, item in enumerate(frames):
        src = CAPTURE_DIR / f"frame_{item['index']:04d}.jpg"
        img = Image.open(src).convert("RGBA")
        w, h = img.size
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)

        badge = item.get("badge", "")
        accent = (56, 224, 255, 255)
        if badge == "DALTONISMO":
            accent = (255, 176, 56, 255)
        elif badge == "REMAP":
            accent = (182, 130, 255, 255)
        elif badge in ("CONCLUIDO", "HUD", "LEGENDAS"):
            accent = (56, 240, 158, 255)

        mm = i // 60
        ss = i % 60
        ts = f"{mm:02d}:{ss:02d} / 03:00"

        # Top-left section banner
        d.rectangle([24, 20, 1320, 92], fill=(10, 15, 24, 224))
        d.rectangle([24, 20, 34, 92], fill=accent)
        d.text((50, 38), f"UI & ACESSIBILIDADE  |  {item.get('section', '')}", font=f_title, fill=(246, 250, 255, 255))

        # Top-right timer + badge
        d.rectangle([w - 360, 20, w - 24, 92], fill=(10, 15, 24, 224))
        d.text((w - 340, 30), f"{badge}  |  {ts}", font=f_badge, fill=accent)
        d.text((w - 340, 60), "MODO: SO CONTROLE", font=load_font(16), fill=(210, 226, 240, 255))

        # Bottom controller input + live option value
        d.rectangle([24, h - 118, w - 24, h - 20], fill=(10, 15, 24, 228))
        d.rectangle([24, h - 118, 34, h - 20], fill=accent)
        d.text((52, h - 104), f"CONTROLE: {item.get('controllerInput', '')}", font=f_ctrl, fill=accent)
        d.text((52, h - 62), f"ESTADO ATIVO: {item.get('liveState', '')}", font=f_state, fill=(240, 246, 252, 255))

        comp = Image.alpha_composite(img, overlay).convert("RGB")
        comp.save(ann_dir / f"ann_{i:04d}.jpg", quality=90)

    cmd = [
        "ffmpeg", "-y",
        "-framerate", "1",
        "-i", str(ann_dir / "ann_%04d.jpg"),
        "-r", "12",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "20",
        "-movflags", "+faststart",
        str(OUT_MP4),
    ]
    subprocess.run(cmd, check=True)
    print(f"MP4_OK: {OUT_MP4} ({len(frames)}s = 3:00)")


if __name__ == "__main__":
    main()
