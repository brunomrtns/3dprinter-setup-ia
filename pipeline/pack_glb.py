#!/usr/bin/env python3
"""Universal Asset Texture Painting — Stage E (Real-ESRGAN x4 8K/4K + GLB JPEG q95 / PBR Pack).

Supports both albedo-only textures and PBR (BaseColor + optional Metallic/Roughness <= 2048 PNG).
Preserves input UV mesh verbatim and writes <asset_id>__<variant_id>_{8k,4k}.glb.
"""
from __future__ import annotations

import argparse
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

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools" / "generator"))
from upscale_and_pack_fox import RRDBNet, VramSampler10s, upscale_tiled  # noqa: E402


def mean_sat_pct(img: Image.Image) -> float:
    arr = np.asarray(img.convert("RGB"), dtype=np.uint8)
    hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
    return round(float(hsv[..., 1].astype(np.float32).mean() / 255.0 * 100.0), 3)


def boost_sat_hsv(img: Image.Image, factor: float) -> Image.Image:
    arr = np.asarray(img.convert("RGB"), dtype=np.uint8)
    hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[..., 1] = np.clip(hsv[..., 1] * factor, 0.0, 255.0)
    rgb = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)
    return Image.fromarray(rgb, mode="RGB")


def export_glb_with_maps(
    uv_obj_path: Path,
    base_color: Image.Image,
    out_glb_path: Path,
    jpeg_quality: int = 95,
    metallic_roughness_img: Image.Image | None = None,
) -> dict:
    """Exports GLB with JPEG q95 baseColorTexture and optional PNG metallicRoughnessTexture."""
    mesh = trimesh.load(str(uv_obj_path), force="mesh", process=False)
    uv = mesh.visual.uv
    if uv is None or len(uv) != len(mesh.vertices):
        raise RuntimeError(f"Invalid UV in {uv_obj_path}")

    tiny_base = Image.new("RGB", (16, 16), (255, 255, 255))
    mat_kwargs = {
        "name": "asset_pbr",
        "baseColorTexture": tiny_base,
        "doubleSided": True,
    }
    if metallic_roughness_img is not None:
        mr = metallic_roughness_img.convert("RGB")
        if max(mr.size) > 2048:
            mr = mr.resize((2048, 2048), Image.Resampling.LANCZOS)
        mat_kwargs["metallicRoughnessTexture"] = mr
        mat_kwargs["metallicFactor"] = 1.0
        mat_kwargs["roughnessFactor"] = 1.0
    else:
        mat_kwargs["metallicFactor"] = 0.0
        mat_kwargs["roughnessFactor"] = 0.55

    mat = trimesh.visual.material.PBRMaterial(**mat_kwargs)
    mesh.visual = trimesh.visual.TextureVisuals(uv=uv, material=mat)
    raw = trimesh.exchange.gltf.export_glb(mesh, include_normals=True)

    magic, version, _ = struct.unpack_from("<III", raw, 0)
    assert magic == 0x46546C67 and version == 2
    json_len, json_type = struct.unpack_from("<II", raw, 12)
    assert json_type == 0x4E4F534A
    gltf = json.loads(raw[20 : 20 + json_len].decode("utf-8"))
    bin_off = 20 + json_len
    bin_len, bin_type = struct.unpack_from("<II", raw, bin_off)
    assert bin_type == 0x004E4942
    bin_data = bytearray(raw[bin_off + 8 : bin_off + 8 + bin_len])

    # Identify baseColor image index from material
    pbr = gltf["materials"][0]["pbrMetallicRoughness"]
    bc_tex_idx = pbr["baseColorTexture"]["index"]
    bc_img_idx = gltf["textures"][bc_tex_idx]["source"]

    jbuf = io.BytesIO()
    base_color.convert("RGB").save(jbuf, format="JPEG", quality=jpeg_quality, subsampling=0, optimize=True)
    jpeg_bytes = jbuf.getvalue()

    img_meta = gltf["images"][bc_img_idx]
    bv_idx = img_meta["bufferView"]
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
        "has_pbr_mr": metallic_roughness_img is not None,
        "tex_px": list(base_color.size),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--input-dir", required=True, help="Directory with <vid>_*.png final basecolor textures")
    ap.add_argument("--pbr-dir", default="", help="Optional directory with <vid>_metallic_roughness.png")
    ap.add_argument("--variants", default="", help="Comma-separated variant IDs to publish (default: all)")
    ap.add_argument("--report-out", required=True)
    args = ap.parse_args()

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    seed = int(cfg["seed"])
    torch.manual_seed(seed)
    np.random.seed(seed)

    pack_cfg = cfg["pack"]
    in_dir = Path(args.input_dir)
    pbr_dir = Path(args.pbr_dir) if args.pbr_dir else None
    work_dir = Path(cfg["work_dir"])
    models_dir = Path(cfg["models_dir"])
    models_dir.mkdir(parents=True, exist_ok=True)
    allowed = {v.strip() for v in args.variants.split(",") if v.strip()} if args.variants else None

    weights_path = Path.home() / ".cache" / "realesrgan" / "RealESRGAN_x4plus.pth"
    if not weights_path.exists():
        raise FileNotFoundError(f"Real-ESRGAN weights missing: {weights_path}")

    sampler = VramSampler10s(interval_s=10.0)
    sampler.start()
    t0 = time.time()

    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    ck = torch.load(str(weights_path), map_location="cpu", weights_only=True)
    sd = ck.get("params_ema", ck.get("params", ck))
    model.load_state_dict(sd, strict=True)
    model.eval().half().cuda()

    report = {"stage": "E_pack_glb", "asset_id": cfg["asset_id"], "seed": seed, "variants": {}}

    for var in cfg["variants"]:
        vid = var["id"]
        if allowed is not None and vid not in allowed:
            continue
        t_v = time.time()
        cands = sorted(in_dir.glob(f"{vid}_*.png"))
        if not cands:
            raise FileNotFoundError(f"No input texture for {vid} in {in_dir}")
        src_tex = cands[0]

        im_in = Image.open(src_tex).convert("RGB")
        if im_in.size != (2048, 2048):
            im_in = im_in.resize((2048, 2048), Image.Resampling.LANCZOS)
        sat_before = mean_sat_pct(im_in)

        im_8k = upscale_tiled(
            model,
            im_in,
            scale=int(pack_cfg.get("upscale_scale", 4)),
            tile_size=int(pack_cfg.get("tile_size", 512)),
            tile_pad=16,
            device="cuda",
        )
        sat_after = mean_sat_pct(im_8k)
        rel_loss = round((sat_before - sat_after) / max(1e-6, sat_before) * 100.0, 2)
        resat = False
        sat_final = sat_after
        if rel_loss > float(pack_cfg.get("sat_loss_trigger_pct", 3.0)):
            im_8k = boost_sat_hsv(im_8k, float(pack_cfg.get("sat_boost_factor", 1.05)))
            sat_final = mean_sat_pct(im_8k)
            resat = True

        im_4k = im_8k.resize((4096, 4096), Image.Resampling.LANCZOS)

        mr_img = None
        if pbr_dir and (pbr_dir / f"{vid}_metallic_roughness.png").exists():
            mr_img = Image.open(pbr_dir / f"{vid}_metallic_roughness.png").convert("RGB")

        tag_dir = work_dir / vid
        im_in.save(tag_dir / "bake2048.png")
        im_8k.save(tag_dir / "tex8192.png", optimize=False)
        im_4k.save(tag_dir / "tex4096.png", optimize=False)

        asset_id = cfg["asset_id"]
        out_8k = tag_dir / f"{asset_id}__{vid}_8k.glb"
        out_4k = tag_dir / f"{asset_id}__{vid}_4k.glb"
        jq = int(pack_cfg.get("jpeg_quality", 95))
        info_8k = export_glb_with_maps(Path(var["uv_obj"]), im_8k, out_8k, jq, mr_img)
        info_4k = export_glb_with_maps(Path(var["uv_obj"]), im_4k, out_4k, jq, mr_img)

        dst_8k = models_dir / f"{asset_id}__{vid}_8k.glb"
        dst_4k = models_dir / f"{asset_id}__{vid}_4k.glb"
        dst_8k.write_bytes(out_8k.read_bytes())
        dst_4k.write_bytes(out_4k.read_bytes())

        report["variants"][vid] = {
            "tempo_s": round(time.time() - t_v, 2),
            "sat_before_pct": sat_before,
            "sat_after_pct": sat_after,
            "sat_rel_loss_pct": rel_loss,
            "resat_applied": resat,
            "sat_final_8k_pct": sat_final,
            "glb_8k": info_8k,
            "glb_4k": info_4k,
        }
        print(
            f"[stage_e] {vid} OK: sat {sat_before}%->{sat_final}% | "
            f"8K={info_8k['size_mb']}MB, 4K={info_4k['size_mb']}MB (PBR={info_8k['has_pbr_mr']})",
            flush=True,
        )

    del model
    torch.cuda.empty_cache()
    report["tempo_total_s"] = round(time.time() - t0, 2)
    report.update(sampler.stop())

    Path(args.report_out).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"STAGE_E_OK peak={report['vram_pico_mib']}MiB t={report['tempo_total_s']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
