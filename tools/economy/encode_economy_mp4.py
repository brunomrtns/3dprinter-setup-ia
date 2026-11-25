import json
import os
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

CAPTURE_DIR = Path(r"C:\Users\Bruno\workspace\game-concerto\unity\Logs\economy_capture")
OUT_MP4 = Path(r"C:\Users\Bruno\workspace\game-concerto\captures\economia\economia_upgrades_fluxo.mp4")


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
    frames = json.loads((CAPTURE_DIR / "economy_meta.json").read_text(encoding="utf-8"))["frames"]
    ann_dir = CAPTURE_DIR / "_annotated"
    ann_dir.mkdir(parents=True, exist_ok=True)
    OUT_MP4.parent.mkdir(parents=True, exist_ok=True)

    f_title = load_font(28)
    f_detail = load_font(23)
    f_badge = load_font(22)

    for i, item in enumerate(frames):
        img = Image.open(CAPTURE_DIR / f"frame_{item['index']:04d}.jpg").convert("RGBA")
        w, h = img.size
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)

        badge = item["badge"]
        accent = (255, 206, 64, 255) if badge in ("COLETA", "POSTO") else (56, 240, 158, 255)
        if badge == "INICIO":
            accent = (56, 220, 255, 255)

        d.rectangle([24, 18, 1340, 86], fill=(10, 15, 24, 224))
        d.rectangle([24, 18, 34, 86], fill=accent)
        d.text((50, 34), f"ECONOMIA  |  {item['step']}", font=f_title, fill=(246, 250, 255, 255))

        d.rectangle([w - 280, 18, w - 24, 86], fill=(10, 15, 24, 224))
        d.text((w - 256, 38), badge, font=f_badge, fill=accent)

        d.rectangle([24, h - 86, w - 24, h - 18], fill=(10, 15, 24, 226))
        d.rectangle([24, h - 86, 34, h - 18], fill=accent)
        d.text((52, h - 66), item["detail"], font=f_detail, fill=(242, 248, 255, 255))

        Image.alpha_composite(img, overlay).convert("RGB").save(ann_dir / f"ann_{i:04d}.jpg", quality=90)

    subprocess.run([
        "ffmpeg", "-y", "-framerate", "1", "-i", str(ann_dir / "ann_%04d.jpg"),
        "-r", "12", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19", "-movflags", "+faststart",
        str(OUT_MP4)
    ], check=True)
    print(f"MP4_OK: {OUT_MP4} ({len(frames)}s)")


if __name__ == "__main__":
    main()
