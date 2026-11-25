import json
import os
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

CAPTURE_DIR = Path(r"C:\Users\Bruno\workspace\game-concerto\unity\Logs\onboarding_capture")
OUT_MP4 = Path(r"C:\Users\Bruno\workspace\game-concerto\captures\onboarding\onboarding_completo.mp4")


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
    meta_path = CAPTURE_DIR / "onboarding_meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Missing {meta_path}")

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    frames = meta.get("frames", [])
    if not frames:
        raise RuntimeError("No frames recorded in onboarding_meta.json")

    ann_dir = CAPTURE_DIR / "_annotated"
    ann_dir.mkdir(parents=True, exist_ok=True)
    OUT_MP4.parent.mkdir(parents=True, exist_ok=True)

    f_title = load_font(30)
    f_prompt = load_font(26)
    f_badge = load_font(22)

    for i, item in enumerate(frames):
        src = CAPTURE_DIR / f"frame_{item['index']:04d}.jpg"
        img = Image.open(src).convert("RGBA")
        w, h = img.size
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)

        # Top-left phase banner
        phase = item.get("phase", "")
        badge = item.get("badge", "")
        d.rectangle([28, 24, 1080, 96], fill=(10, 16, 26, 215))
        accent = (255, 194, 56, 255) if badge == "TELEGRAPH" else (56, 224, 255, 255)
        if badge in ("OK", "CONCLUIDO", "PODER #1", "PODER #2"):
            accent = (56, 240, 158, 255)
        d.rectangle([28, 24, 38, 96], fill=accent)
        d.text((54, 42), f"ONBOARDING  |  {phase}", font=f_title, fill=(245, 250, 255, 255))

        # Bottom single-line diegetic prompt pill (max 1 line)
        prompt = item.get("prompt", "")
        if prompt:
            d.rectangle([260, h - 104, w - 260, h - 32], fill=(10, 16, 26, 220))
            d.rectangle([260, h - 104, 270, h - 32], fill=accent)
            d.text((294, h - 84), prompt, font=f_prompt, fill=(255, 255, 255, 255))

        # Bottom-right badge
        d.rectangle([w - 230, 24, w - 28, 96], fill=(10, 16, 26, 215))
        d.text((w - 210, 46), badge, font=f_badge, fill=accent)

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
    print("METRICS:", json.dumps(meta.get("metrics", []), indent=2))


if __name__ == "__main__":
    main()
