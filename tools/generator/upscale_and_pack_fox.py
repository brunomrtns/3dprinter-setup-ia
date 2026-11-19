#!/usr/bin/env python3
"""Bloco G — Real-ESRGAN 4x (2048 -> 8192 + variante 4096) + export GLB 8K/4K para mv_a e mv_b.

Usa RRDBNet 23 blocos (RealESRGAN_x4plus.pth) em FP16 com inferência em tiles (512px, pad 16)
para manter VRAM baixa na RTX 3060 12GB, com seed 42 e amostragem de VRAM a cada 10s.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import threading
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
import trimesh
from PIL import Image


# ── RRDBNet (arquitetura exata do RealESRGAN_x4plus.pth) ─────────────────────
class ResidualDenseBlock(nn.Module):
    def __init__(self, num_feat: int = 64, num_grow_ch: int = 32):
        super().__init__()
        self.conv1 = nn.Conv2d(num_feat, num_grow_ch, 3, 1, 1)
        self.conv2 = nn.Conv2d(num_feat + num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv3 = nn.Conv2d(num_feat + 2 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv4 = nn.Conv2d(num_feat + 3 * num_grow_ch, num_grow_ch, 3, 1, 1)
        self.conv5 = nn.Conv2d(num_feat + 4 * num_grow_ch, num_feat, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
        return x5 * 0.2 + x


class RRDB(nn.Module):
    def __init__(self, num_feat: int, num_grow_ch: int = 32):
        super().__init__()
        self.rdb1 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb2 = ResidualDenseBlock(num_feat, num_grow_ch)
        self.rdb3 = ResidualDenseBlock(num_feat, num_grow_ch)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.rdb1(x)
        out = self.rdb2(out)
        out = self.rdb3(out)
        return out * 0.2 + x


class RRDBNet(nn.Module):
    def __init__(
        self,
        num_in_ch: int = 3,
        num_out_ch: int = 3,
        scale: int = 4,
        num_feat: int = 64,
        num_block: int = 23,
        num_grow_ch: int = 32,
    ):
        super().__init__()
        self.scale = scale
        self.conv_first = nn.Conv2d(num_in_ch, num_feat, 3, 1, 1)
        self.body = nn.Sequential(*[RRDB(num_feat=num_feat, num_grow_ch=num_grow_ch) for _ in range(num_block)])
        self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up1 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_up2 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
        self.conv_last = nn.Conv2d(num_feat, num_out_ch, 3, 1, 1)
        self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feat = self.conv_first(x)
        body_feat = self.conv_body(self.body(feat))
        feat = feat + body_feat
        feat = self.lrelu(self.conv_up1(F.interpolate(feat, scale_factor=2, mode="nearest")))
        feat = self.lrelu(self.conv_up2(F.interpolate(feat, scale_factor=2, mode="nearest")))
        out = self.conv_last(self.lrelu(self.conv_hr(feat)))
        return out


# ── Amostrador de VRAM a cada 10s ────────────────────────────────────────────
def query_vram_used_mib() -> int:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True,
        ).strip()
        return int(out.splitlines()[0].strip())
    except Exception:
        return -1


class VramSampler10s:
    def __init__(self, interval_s: float = 10.0):
        self.interval_s = interval_s
        self.samples: list[list[float | int]] = []
        self.peak_mib = 0
        self._stop = threading.Event()
        self._t0 = 0.0
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._t0 = time.time()
        self._sample()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _sample(self) -> None:
        used = query_vram_used_mib()
        if used >= 0:
            self.samples.append([round(time.time() - self._t0, 1), used])
            if used > self.peak_mib:
                self.peak_mib = used

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_s):
            self._sample()

    def stop(self) -> dict:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._sample()
        return {
            "vram_samples_10s": self.samples,
            "vram_pico_mib": self.peak_mib,
            "vram_baseline_mib": self.samples[0][1] if self.samples else 0,
        }


@torch.no_grad()
def upscale_tiled(
    model: nn.Module,
    img: Image.Image,
    scale: int = 4,
    tile_size: int = 512,
    tile_pad: int = 16,
    device: str = "cuda",
) -> Image.Image:
    arr = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    # HWC -> NCHW
    img_t = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)
    _, _, h, w = img_t.shape
    out_h, out_w = h * scale, w * scale
    output = torch.zeros((1, 3, out_h, out_w), dtype=torch.float32)

    tiles_x = math.ceil(w / tile_size)
    tiles_y = math.ceil(h / tile_size)
    total = tiles_x * tiles_y
    done = 0

    for y in range(tiles_y):
        for x in range(tiles_x):
            ofs_x = x * tile_size
            ofs_y = y * tile_size
            in_x0 = max(ofs_x - tile_pad, 0)
            in_x1 = min(ofs_x + tile_size + tile_pad, w)
            in_y0 = max(ofs_y - tile_pad, 0)
            in_y1 = min(ofs_y + tile_size + tile_pad, h)

            tile = img_t[:, :, in_y0:in_y1, in_x0:in_x1].to(device=device, dtype=torch.float16)
            out_tile = model(tile).float().cpu()

            out_x0 = ofs_x * scale
            out_x1 = min(ofs_x + tile_size, w) * scale
            out_y0 = ofs_y * scale
            out_y1 = min(ofs_y + tile_size, h) * scale

            tile_x0 = (ofs_x - in_x0) * scale
            tile_x1 = tile_x0 + (out_x1 - out_x0)
            tile_y0 = (ofs_y - in_y0) * scale
            tile_y1 = tile_y0 + (out_y1 - out_y0)

            output[:, :, out_y0:out_y1, out_x0:out_x1] = out_tile[:, :, tile_y0:tile_y1, tile_x0:tile_x1]
            done += 1
            if done % 4 == 0 or done == total:
                print(f"  tile {done}/{total}", flush=True)

    out_np = (output.squeeze(0).permute(1, 2, 0).clamp(0.0, 1.0).numpy() * 255.0).round().astype(np.uint8)
    return Image.fromarray(out_np, mode="RGB")


def export_textured_glb(uv_obj_path: Path, tex_img: Image.Image, out_glb_path: Path) -> dict:
    mesh = trimesh.load(str(uv_obj_path), force="mesh", process=False)
    uv = mesh.visual.uv
    if uv is None or len(uv) != len(mesh.vertices):
        raise RuntimeError(f"UV inválido em {uv_obj_path}")

    # Material PBR com textura embutida (baseColorTexture)
    mat = trimesh.visual.material.PBRMaterial(
        name="fox_pbr",
        baseColorTexture=tex_img,
        metallicFactor=0.08,
        roughnessFactor=0.48,
        doubleSided=True,
    )
    mesh.visual = trimesh.visual.TextureVisuals(uv=uv, material=mat)

    out_glb_path.parent.mkdir(parents=True, exist_ok=True)
    # Exporta GLB com extensão JPEG (mantém resolução exata 8192/4096 com tamanho ideal p/ WebGL)
    glb_bytes = trimesh.exchange.gltf.export_glb(mesh, include_normals=True)
    out_glb_path.write_bytes(glb_bytes)
    size_mb = round(len(glb_bytes) / (1024 * 1024), 2)
    return {
        "glb": str(out_glb_path),
        "size_mb": size_mb,
        "verts": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "tex_px": list(tex_img.size),
    }


def main() -> int:
    torch.manual_seed(42)
    np.random.seed(42)

    work_dir = Path.home() / "printer3d-work" / "carro" / "fox_fullrun"
    models_dir = Path.home() / "printer3d-work" / "modelos3d-site" / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    weights_path = Path.home() / ".cache" / "realesrgan" / "RealESRGAN_x4plus.pth"
    report_path = Path("/mnt/c/Users/Bruno/OneDrive/Documentos/Default Project/3dprinter-setup-ia/evidence/rtx3060-12gb/fox_fullrun/report.json")

    if not weights_path.exists():
        raise FileNotFoundError(f"Pesos Real-ESRGAN ausentes: {weights_path}")

    sampler = VramSampler10s(interval_s=10.0)
    sampler.start()
    t0 = time.time()

    print("[bloco_g] Carregando RealESRGAN_x4plus (FP16 CUDA)...", flush=True)
    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    ck = torch.load(str(weights_path), map_location="cpu", weights_only=True)
    sd = ck.get("params_ema", ck.get("params", ck))
    model.load_state_dict(sd, strict=True)
    model.eval().half().cuda()

    bloco_g = {"seed": 42, "modelo_upscale": "RealESRGAN_x4plus (RRDBNet 23b FP16 tile=512)", "variants": {}}

    for tag in ("mv_a", "mv_b"):
        t_tag = time.time()
        tag_dir = work_dir / tag
        bake_path = tag_dir / "bake2048.png"
        uv_path = tag_dir / "uv.obj"
        print(f"[bloco_g] Processando {tag}: {bake_path}", flush=True)

        im_2k = Image.open(bake_path).convert("RGB")
        t_up = time.time()
        im_8k = upscale_tiled(model, im_2k, scale=4, tile_size=512, tile_pad=16, device="cuda")
        t_up_s = round(time.time() - t_up, 2)

        tex8k_path = tag_dir / "tex8192.png"
        im_8k.save(tex8k_path, optimize=False)
        print(f"[bloco_g] {tag} 8K salvo ({im_8k.size}) em {t_up_s}s", flush=True)

        im_4k = im_8k.resize((4096, 4096), Image.Resampling.LANCZOS)
        tex4k_path = tag_dir / "tex4096.png"
        im_4k.save(tex4k_path, optimize=False)
        print(f"[bloco_g] {tag} 4K salvo ({im_4k.size})", flush=True)

        # Exporta GLB 8K e GLB 4K
        out_8k_work = tag_dir / f"carro_foxh__{tag}_8k.glb"
        out_4k_work = tag_dir / f"carro_foxh__{tag}_4k.glb"
        info_8k = export_textured_glb(uv_path, im_8k, out_8k_work)
        info_4k = export_textured_glb(uv_path, im_4k, out_4k_work)

        # Copia para pasta de modelos do viewer
        dst_8k = models_dir / f"carro_foxh__{tag}_8k.glb"
        dst_4k = models_dir / f"carro_foxh__{tag}_4k.glb"
        dst_8k.write_bytes(out_8k_work.read_bytes())
        dst_4k.write_bytes(out_4k_work.read_bytes())

        bloco_g["variants"][tag] = {
            "tempo_upscale_s": t_up_s,
            "tempo_total_tag_s": round(time.time() - t_tag, 2),
            "tex8192_png": str(tex8k_path),
            "tex4096_png": str(tex4k_path),
            "glb_8k": info_8k,
            "glb_4k": info_4k,
            "site_glb_8k": str(dst_8k),
            "site_glb_4k": str(dst_4k),
        }
        print(
            f"[bloco_g] {tag} GLBs prontos: 8K={info_8k['size_mb']}MB, 4K={info_4k['size_mb']}MB",
            flush=True,
        )

    del model
    torch.cuda.empty_cache()
    vram_info = sampler.stop()
    bloco_g["tempo_total_s"] = round(time.time() - t0, 2)
    bloco_g.update(vram_info)

    # Atualiza report.json
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["bloco_g_8k"] = bloco_g
    report_path.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print("[bloco_g] CONCLUÍDO! VRAM pico:", bloco_g["vram_pico_mib"], "MiB | Tempo:", bloco_g["tempo_total_s"], "s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
