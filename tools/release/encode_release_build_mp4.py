import json
import os
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

TELE_DIR = Path(r"C:\Users\Bruno\workspace\game-concerto\unity\Logs\release_build_telemetry")
OUT_MP4 = Path(r"C:\Users\Bruno\workspace\game-concerto\captures\release\build_15min.mp4")


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
    tele = json.loads((TELE_DIR / "build_telemetry.json").read_text(encoding="utf-8"))
    shots = sorted(TELE_DIR.glob("shot_*.png"))
    if not shots:
        raise RuntimeError("No standalone build screenshots found")

    ann_dir = TELE_DIR / "_annotated"
    ann_dir.mkdir(parents=True, exist_ok=True)
    OUT_MP4.parent.mkdir(parents=True, exist_ok=True)

    f_hdr = load_font(26)
    f_sub = load_font(21)

    avg_fps = tele.get("avgFps", 0.0)
    p99_ms = tele.get("p99FrameMs", 0.0)
    ver = tele.get("version", "")
    errs = tele.get("consoleErrorCount", 0)
    frames_tot = tele.get("totalFrames", 0)

    # 15 shots x 2s each = 30s clean, crisp 1080p standalone build proof video
    idx = 0
    for s_i, shot_path in enumerate(shots):
        img = Image.open(shot_path).convert("RGBA").resize((1920, 1080))
        overlay = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)

        label = "TELA INICIAL — VERSAO AUTOMATICA" if s_i == 0 else f"ATO 1 (CALDEIRAL) — BUILD STANDALONE WIN64  [{s_i:02d}/{len(shots)-1:02d}]"
        d.rectangle([24, 18, 1260, 84], fill=(8, 14, 22, 224))
        d.rectangle([24, 18, 34, 84], fill=(56, 240, 158, 255))
        d.text((50, 34), f"RELEASE DEMO v{ver}  |  {label}", font=f_hdr, fill=(244, 250, 255, 255))

        d.rectangle([1280, 18, 1896, 84], fill=(8, 14, 22, 224))
        d.text((1300, 26), f"FPS MEDIO: {avg_fps:.1f} FPS  (P99: {p99_ms:.2f} ms)", font=f_sub, fill=(80, 255, 180, 255))
        d.text((1300, 54), f"ERROS CONSOLE: {errs}  |  FRAMES: {frames_tot}", font=load_font(17), fill=(210, 232, 248, 255))

        comp = Image.alpha_composite(img, overlay).convert("RGB")
        for _ in range(2):
            comp.save(ann_dir / f"rel_{idx:04d}.jpg", quality=92)
            idx += 1

    cmd = [
        "ffmpeg", "-y",
        "-framerate", "1",
        "-i", str(ann_dir / "rel_%04d.jpg"),
        "-r", "12",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "19",
        "-movflags", "+faststart",
        str(OUT_MP4),
    ]
    subprocess.run(cmd, check=True)
    print(f"MP4_OK: {OUT_MP4} ({idx}s, {len(shots)} standalone build captures)")


if __name__ == "__main__":
    main()
