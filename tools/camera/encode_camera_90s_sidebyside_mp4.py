import json
import os
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT_DIR = Path(r"C:\Users\Bruno\workspace\game-concerto\unity\Logs\camera_pass_capture")
OUT_MP4 = Path(r"C:\Users\Bruno\workspace\game-concerto\captures\camera\camera_antes_depois_90s.mp4")


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

    comp_dir = ROOT_DIR / "_sidebyside"
    comp_dir.mkdir(parents=True, exist_ok=True)
    OUT_MP4.parent.mkdir(parents=True, exist_ok=True)

    f_hdr = load_font(26)
    f_seg = load_font(21)
    f_inf = load_font(18)

    for i in range(n):
        left = Image.open(ROOT_DIR / "antes" / f"frame_{i:04d}.jpg").convert("RGBA")
        right = Image.open(ROOT_DIR / "depois" / f"frame_{i:04d}.jpg").convert("RGBA")
        canvas = Image.new("RGBA", (1920, 1080), (8, 12, 18, 255))
        canvas.paste(left, (0, 0))
        canvas.paste(right, (960, 0))

        overlay = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        d.rectangle([957, 0, 963, 1080], fill=(240, 248, 255, 220))

        ts = f"{i // 60:02d}:{i % 60:02d} / 01:30"
        d.rectangle([18, 18, 940, 80], fill=(16, 12, 16, 224))
        d.rectangle([18, 18, 28, 80], fill=(255, 86, 86, 255))
        d.text((44, 34), f"ANTES (CAMERA BASE)  |  {ts}", font=f_hdr, fill=(255, 136, 136, 255))

        d.rectangle([980, 18, 1902, 80], fill=(10, 18, 24, 224))
        d.rectangle([980, 18, 990, 80], fill=(56, 240, 158, 255))
        d.text((1006, 34), f"DEPOIS (CINEMACHINE PASS)  |  {ts}", font=f_hdr, fill=(80, 255, 180, 255))

        d.rectangle([18, 966, 940, 1062], fill=(14, 14, 20, 228))
        d.text((34, 978), antes_meta[i]["segment"], font=f_seg, fill=(255, 200, 200, 255))
        d.text((34, 1014), antes_meta[i]["info"], font=f_inf, fill=(220, 220, 230, 255))

        d.rectangle([980, 966, 1902, 1062], fill=(10, 18, 24, 228))
        d.text((996, 978), depois_meta[i]["segment"], font=f_seg, fill=(80, 255, 180, 255))
        d.text((996, 1014), depois_meta[i]["info"], font=f_inf, fill=(235, 248, 255, 255))

        Image.alpha_composite(canvas, overlay).convert("RGB").save(comp_dir / f"sbs_{i:04d}.jpg", quality=90)

    subprocess.run([
        "ffmpeg", "-y", "-framerate", "1", "-i", str(comp_dir / "sbs_%04d.jpg"),
        "-r", "12", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart",
        str(OUT_MP4)
    ], check=True)
    print(f"MP4_OK: {OUT_MP4} ({n}s lado a lado)")


if __name__ == "__main__":
    main()
