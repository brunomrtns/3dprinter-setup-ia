#!/usr/bin/env python3
"""ETAPA F — Real-ESRGAN x4 (FP16, tiles 512) -> 8192 + 4096, checagem de saturação,
GLB com textura embutida JPEG q95 (mesmos nomes em modelos3d-site/models), seed 42, VRAM 10s.
"""
from __future__ import annotations

import io
import json
import struct
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import trimesh
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from upscale_and_pack_fox import RRDBNet, VramSampler10s, upscale_tiled

REPO = Path("/mnt/c/Users/Bruno/OneDrive/Documentos/Default Project/3dprinter-setup-ia")
WORK = Path.home() / "printer3d-work" / "carro" / "fox_fullrun"
MODELS_DIR = Path.home() / "printer3d-work" / "modelos3d-site" / "models"
EVID = REPO / "evidence" / "rtx3060-12gb" / "fox_aipaint"


def mean_sat_pct(img: Image.Image) -> float:
    arr = np.asarray(img.convert("RGB"), dtype=np.uint8)
    hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
    return round(float(hsv[..., 1].astype(np.float32).mean() / 255.0 * 100.0), 3)


def boost_saturation_hsv(img: Image.Image, factor: float = 1.05) -> Image.Image:
    arr = np.asarray(img.convert("RGB"), dtype=np.uint8)
    hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * factor, 0.0, 255.0)
    rgb = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
    return Image.fromarray(rgb, mode="RGB")


def export_glb_jpeg95(uv_obj_path: Path, tex_img: Image.Image, out_glb_path: Path) -> dict:
    """Exporta GLB com PBR neutro (metallic=0, roughness=0.65) e textura embutida JPEG q95."""
    mesh = trimesh.load(str(uv_obj_path), force="mesh", process=False)
    uv = mesh.visual.uv
    if uv is None or len(uv) != len(mesh.vertices):
        raise RuntimeError(f"UV inválido em {uv_obj_path}")

    # Exporta com placeholder 16x16 PNG e substitui bufferView da imagem por JPEG q95
    tiny = Image.new("RGB", (16, 16), (255, 255, 255))
    mat = trimesh.visual.material.PBRMaterial(
        name="fox_pbr",
        baseColorTexture=tiny,
        metallicFactor=0.0,
        roughnessFactor=0.65,
        doubleSided=True,
    )
    mesh.visual = trimesh.visual.TextureVisuals(uv=uv, material=mat)
    raw = trimesh.exchange.gltf.export_glb(mesh, include_normals=True)

    # Parse GLB chunks
    magic, version, total_len = struct.unpack_from("<III", raw, 0)
    assert magic == 0x46546C67 and version == 2
    json_len, json_type = struct.unpack_from("<II", raw, 12)
    assert json_type == 0x4E4F534A
    gltf = json.loads(raw[20 : 20 + json_len].decode("utf-8"))
    bin_off = 20 + json_len
    bin_len, bin_type = struct.unpack_from("<II", raw, bin_off)
    assert bin_type == 0x004E4942
    bin_data = bytearray(raw[bin_off + 8 : bin_off + 8 + bin_len])

    # Encode JPEG q95 subsampling=0
    jbuf = io.BytesIO()
    tex_img.convert("RGB").save(jbuf, format="JPEG", quality=95, subsampling=0, optimize=True)
    jpeg_bytes = jbuf.getvalue()

    img_meta = gltf["images"][0]
    bv_idx = img_meta["bufferView"]
    # Append JPEG alinhado a 4 bytes ao final do BIN e atualiza bufferView
    while len(bin_data) % 4 != 0:
        bin_data.append(0)
    new_offset = len(bin_data)
    bin_data.extend(jpeg_bytes)
    while len(bin_data) % 4 != 0:
        bin_data.append(0)

    gltf["bufferViews"][bv_idx]["byteOffset"] = new_offset
    gltf["bufferViews"][bv_idx]["byteLength"] = len(jpeg_bytes)
    img_meta["mimeType"] = "image/jpeg"
    gltf["buffers"][0]["byteLength"] = len(bin_data)

    new_json = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    while len(new_json) % 4 != 0:
        new_json += b" "

    new_total = 12 + 8 + len(new_json) + 8 + len(bin_data)
    out = bytearray()
    out += struct.pack("<III", 0x46546C67, 2, new_total)
    out += struct.pack("<II", len(new_json), 0x4E4F534A)
    out += new_json
    out += struct.pack("<II", len(bin_data), 0x004E4942)
    out += bin_data

    out_glb_path.parent.mkdir(parents=True, exist_ok=True)
    out_glb_path.write_bytes(bytes(out))
    return {
        "glb": str(out_glb_path),
        "size_mb": round(len(out) / (1024 * 1024), 2),
        "size_bytes": len(out),
        "jpeg_mb": round(len(jpeg_bytes) / (1024 * 1024), 2),
        "verts": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "tex_px": list(tex_img.size),
        "mime": "image/jpeg",
        "jpeg_quality": 95,
    }


def main() -> int:
    torch.manual_seed(42)
    np.random.seed(42)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    weights_path = Path.home() / ".cache" / "realesrgan" / "RealESRGAN_x4plus.pth"
    if not weights_path.exists():
        raise FileNotFoundError(f"Pesos Real-ESRGAN ausentes: {weights_path}")

    sampler = VramSampler10s(interval_s=10.0)
    sampler.start()
    t0 = time.time()

    print("[etapa_f] Carregando RealESRGAN_x4plus (FP16 CUDA, tile=512)...", flush=True)
    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    ck = torch.load(str(weights_path), map_location="cpu", weights_only=True)
    sd = ck.get("params_ema", ck.get("params", ck))
    model.load_state_dict(sd, strict=True)
    model.eval().half().cuda()

    res = {
        "seed": 42,
        "modelo_upscale": "RealESRGAN_x4plus (RRDBNet 23b FP16 tile=512)",
        "variants": {},
    }

    for tag in ("mv_a", "mv_b"):
        t_tag = time.time()
        tag_dir = WORK / tag
        bake_path = tag_dir / "bake2048.png"
        uv_path = tag_dir / "uv.obj"

        im_2k = Image.open(bake_path).convert("RGB")
        if im_2k.size != (2048, 2048):
            im_2k = im_2k.resize((2048, 2048), Image.Resampling.LANCZOS)
        sat_before = mean_sat_pct(im_2k)

        print(f"[etapa_f] Upscale 4x {tag} ({im_2k.size} -> 8192)...", flush=True)
        t_up = time.time()
        im_8k = upscale_tiled(model, im_2k, scale=4, tile_size=512, tile_pad=16, device="cuda")
        t_up_s = round(time.time() - t_up, 2)

        sat_after = mean_sat_pct(im_8k)
        rel_loss = round((sat_before - sat_after) / max(1e-6, sat_before) * 100.0, 2)
        resat_applied = False
        sat_final = sat_after
        if rel_loss > 3.0:
            print(f"[etapa_f] {tag}: perda saturação {rel_loss}% > 3% -> re-saturação 1.05x", flush=True)
            im_8k = boost_saturation_hsv(im_8k, 1.05)
            sat_final = mean_sat_pct(im_8k)
            resat_applied = True

        im_4k = im_8k.resize((4096, 4096), Image.Resampling.LANCZOS)
        im_8k.save(tag_dir / "tex8192.png", optimize=False)
        im_4k.save(tag_dir / "tex4096.png", optimize=False)

        out_8k = tag_dir / f"carro_foxh__{tag}_8k.glb"
        out_4k = tag_dir / f"carro_foxh__{tag}_4k.glb"
        info_8k = export_glb_jpeg95(uv_path, im_8k, out_8k)
        info_4k = export_glb_jpeg95(uv_path, im_4k, out_4k)

        dst_8k = MODELS_DIR / f"carro_foxh__{tag}_8k.glb"
        dst_4k = MODELS_DIR / f"carro_foxh__{tag}_4k.glb"
        dst_8k.write_bytes(out_8k.read_bytes())
        dst_4k.write_bytes(out_4k.read_bytes())

        res["variants"][tag] = {
            "tempo_upscale_s": t_up_s,
            "tempo_total_tag_s": round(time.time() - t_tag, 2),
            "sat_before_upscale_pct": sat_before,
            "sat_after_upscale_pct": sat_after,
            "sat_rel_loss_pct": rel_loss,
            "resat_105_applied": resat_applied,
            "sat_final_8k_pct": sat_final,
            "glb_8k": info_8k,
            "glb_4k": info_4k,
            "site_glb_8k": str(dst_8k),
            "site_glb_4k": str(dst_4k),
        }
        print(
            f"[etapa_f] {tag} OK: sat {sat_before}%->{sat_after}% (final {sat_final}%) | "
            f"8K={info_8k['size_mb']}MB, 4K={info_4k['size_mb']}MB",
            flush=True,
        )

    del model
    torch.cuda.empty_cache()
    res["tempo_total_s"] = round(time.time() - t0, 2)
    res.update(sampler.stop())

    (EVID / "etapa_f_pack.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"ETAPA_F_OK vram_pico={res['vram_pico_mib']}MiB tempo={res['tempo_total_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
