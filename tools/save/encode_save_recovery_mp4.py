import json
import os
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

CAPTURE_DIR = Path(r"C:\Users\Bruno\workspace\game-concerto\unity\Logs\save_recovery_capture")
OUT_MP4 = Path(r"C:\Users\Bruno\workspace\game-concerto\captures\save\save_recuperacao_backup.mp4")


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
    meta_path = CAPTURE_DIR / "save_recovery_meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing {meta_path}")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    frames = meta.get("frames", [])
    if not frames:
        raise RuntimeError("No frames recorded in save_recovery_meta.json")

    ann_dir = CAPTURE_DIR / "_annotated"
    ann_dir.mkdir(parents=True, exist_ok=True)
    OUT_MP4.parent.mkdir(parents=True, exist_ok=True)

    f_title = load_font(30)
    f_status = load_font(25)
    f_detail = load_font(22)
    f_badge = load_font(22)

    for i, item in enumerate(frames):
        src = CAPTURE_DIR / f"frame_{item['index']:04d}.jpg"
        img = Image.open(src).convert("RGBA")
        w, h = img.size
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)

        badge = item.get("badge", "")
        if badge == "CORROMPIDO":
            accent = (255, 76, 76, 255)
        elif badge == "RECUPERADO":
            accent = (56, 240, 158, 255)
        elif badge in ("SALVO", "3 SLOTS"):
            accent = (56, 220, 255, 255)
        else:
            accent = (255, 196, 62, 255)

        # Top-left phase banner
        d.rectangle([28, 24, 1240, 102], fill=(10, 15, 24, 222))
        d.rectangle([28, 24, 38, 102], fill=accent)
        d.text((54, 42), f"SAVE SYSTEM  |  {item.get('phase', '')}", font=f_title, fill=(246, 250, 255, 255))

        # Top-right badge
        d.rectangle([w - 260, 24, w - 28, 102], fill=(10, 15, 24, 222))
        d.text((w - 238, 48), badge, font=f_badge, fill=accent)

        # Bottom status & detail card
        d.rectangle([28, h - 126, w - 28, h - 24], fill=(10, 15, 24, 225))
        d.rectangle([28, h - 126, 38, h - 24], fill=accent)
        d.text((56, h - 110), item.get("status", ""), font=f_status, fill=accent)
        d.text((56, h - 68), item.get("detail", ""), font=f_detail, fill=(235, 242, 250, 255))

        comp = Image.alpha_composite(img, overlay).convert("RGB")
        comp.save(ann_dir / f"ann_{i:04d}.jpg", quality=92)

    cmd = [
        "ffmpeg", "-y",
        "-framerate", "12",
        "-i", str(ann_dir / "ann_%04d.jpg"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-movflags", "+faststart",
        str(OUT_MP4),
    ]
    subprocess.run(cmd, check=True)
    print(f"MP4_OK: {OUT_MP4} ({len(frames)} frames)")


if __name__ == "__main__":
    main()
