import json
import os
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(r"C:\Users\Bruno\workspace\game-concerto\unity\Logs\gamefeel_capture")
OUT_MP4 = Path(r"C:\Users\Bruno\workspace\game-concerto\captures\gamefeel\gamefeel_antes_depois_60s.mp4")


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
    antes_meta = json.loads((ROOT_DIR / "antes" / "meta.json").read_text(encoding="utf-8"))["frames"]
    depois_meta = json.loads((ROOT_DIR / "depois" / "meta.json").read_text(encoding="utf-8"))["frames"]
    n = min(len(antes_meta), len(depois_meta))
    if n == 0:
        raise RuntimeError("No frames captured for gamefeel side-by-side")

    comp_dir = ROOT_DIR / "_sidebyside"
    comp_dir.mkdir(parents=True, exist_ok=True)
    OUT_MP4.parent.mkdir(parents=True, exist_ok=True)

    f_hdr = load_font(28)
    f_beat = load_font(22)
    f_met = load_font(19)

    for i in range(n):
        left = Image.open(ROOT_DIR / "antes" / f"frame_{i:04d}.jpg").convert("RGBA")
        right = Image.open(ROOT_DIR / "depois" / f"frame_{i:04d}.jpg").convert("RGBA")
        canvas = Image.new("RGBA", (1920, 1080), (8, 12, 18, 255))
        canvas.paste(left, (0, 0))
        canvas.paste(right, (960, 0))

        overlay = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)

        # Center split divider
        d.rectangle([957, 0, 963, 1080], fill=(240, 248, 255, 220))

        # Left header (ANTES)
        d.rectangle([18, 18, 940, 82], fill=(16, 12, 16, 224))
        d.rectangle([18, 18, 28, 82], fill=(255, 86, 86, 255))
        d.text((44, 34), f"ANTES (SEM JUICE)  |  00:{i:02d} / 01:00", font=f_hdr, fill=(255, 136, 136, 255))

        # Right header (DEPOIS)
        d.rectangle([980, 18, 1902, 82], fill=(10, 18, 24, 224))
        d.rectangle([980, 18, 990, 82], fill=(56, 240, 158, 255))
        d.text((1006, 34), f"DEPOIS (COM JUICE — DESIGN BIBLE)  |  00:{i:02d}", font=f_hdr, fill=(80, 255, 180, 255))

        # Bottom left bar
        d.rectangle([18, 962, 940, 1062], fill=(14, 14, 20, 228))
        d.text((34, 974), antes_meta[i]["beat"], font=f_beat, fill=(255, 200, 200, 255))
        d.text((34, 1012), antes_meta[i]["metric"], font=f_met, fill=(220, 220, 230, 255))

        # Bottom right bar
        d.rectangle([980, 962, 1902, 1062], fill=(10, 18, 24, 228))
        d.text((996, 974), depois_meta[i]["beat"], font=f_beat, fill=(80, 255, 180, 255))
        d.text((996, 1012), depois_meta[i]["metric"], font=f_met, fill=(235, 248, 255, 255))

        out = Image.alpha_composite(canvas, overlay).convert("RGB")
        out.save(comp_dir / f"sbs_{i:04d}.jpg", quality=90)

    cmd = [
        "ffmpeg", "-y",
        "-framerate", "1",
        "-i", str(comp_dir / "sbs_%04d.jpg"),
        "-r", "12",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "20",
        "-movflags", "+faststart",
        str(OUT_MP4),
    ]
    subprocess.run(cmd, check=True)
    print(f"MP4_OK: {OUT_MP4} ({n}s lado a lado)")


if __name__ == "__main__":
    main()
