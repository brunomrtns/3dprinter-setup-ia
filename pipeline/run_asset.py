#!/usr/bin/env python3
"""Universal Asset Auto-Painting Runner (pipe_std).

Single command per asset:
  python pipeline/run_asset.py --config assets/<id>.json --out <dir> [--resume] [--auto-publish]

Orchestrates the approved Fox PBR pipeline generically across any 3D asset:
  00_preflight    -> UV pre-flight check (and xatlas unwrap preserving geometry if mesh has no UV)
  01_conditioning -> Selects input_images by tier ("photos" | "single" | "none" neutral Blender renders)
  02_paint_hunyuan-> Hunyuan3D-Paint 2048 + per-view Real-ESRGAN x4 SR + per-island gutter bleed + uv_inpaint
  03_photo_blend  -> Silhouette-IoU photo blending (tier == "photos" only; IoU >= 0.90 gate)
  04_patch_repair -> Generic 2D+3D patch/speck repair (with photo-consistency guard when tier == "photos")
  05_trellis_pbr  -> TRELLIS.2-4B shape-conditioned MetallicRoughness 2048 PNG on same UV layout
  06_pack_glb     -> Real-ESRGAN x4 BaseColor 8K/4K JPEG q95 + MR 2048 PNG -> GLBs
  07_qa_eval      -> Automated QA gates (qa.json) + standardized renders & crops
  08_publish      -> Auto-publish ONLY if QA overall_pass == True (backup_prev -> manifest -> deploy -> HTTP 200)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

PIPELINE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PIPELINE_DIR.parent
sys.path.insert(0, str(PIPELINE_DIR))

from config_loader import load_asset_config, uv_preflight  # noqa: E402

HUNYUAN_PY = "/home/bruno/.venvs/hunyuan/bin/python"
TRELLIS_PY = "/home/bruno/.venvs/trellis2/bin/python"

NEUTRAL_RENDER_BLENDER = r'''
import bpy, os, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
mesh_path, out_dir = argv[0], argv[1]
os.makedirs(out_dir, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = 16
scene.render.resolution_x = 512
scene.render.resolution_y = 512
scene.render.film_transparent = False
scene.world = bpy.data.worlds.new("W")
scene.world.use_nodes = True
bg = scene.world.node_tree.nodes.get("Background")
if bg:
    bg.inputs[0].default_value = (1.0, 1.0, 1.0, 1.0)
    bg.inputs[1].default_value = 1.0
scene.view_settings.view_transform = "Standard"
scene.view_settings.look = "None"

if mesh_path.lower().endswith(".glb") or mesh_path.lower().endswith(".gltf"):
    bpy.ops.import_scene.gltf(filepath=mesh_path)
else:
    bpy.ops.wm.obj_import(filepath=mesh_path)

objs = [o for o in scene.objects if o.type == "MESH"]
pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
center = (mn + mx) * 0.5
max_dim = max(mx.x - mn.x, mx.y - mn.y, mx.z - mn.z)

light_data = bpy.data.lights.new("Sun", type="SUN")
light_data.energy = 2.5
light = bpy.data.objects.new("Sun", light_data)
light.location = center + Vector((max_dim * 2, -max_dim * 2, max_dim * 3))
scene.collection.objects.link(light)

cam_data = bpy.data.cameras.new("Cam")
cam_data.type = "ORTHO"
cam_data.ortho_scale = max_dim * 1.25
cam = bpy.data.objects.new("Cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam

dist = max_dim * 2.5
for name, offset in [
    ("front", Vector((0, -dist, 0))),
    ("left",  Vector((-dist, 0, 0))),
    ("back",  Vector((0,  dist, 0))),
    ("right", Vector(( dist, 0, 0))),
]:
    cam.location = center + offset
    cam.rotation_euler = (center - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(out_dir, f"neutral_{name}.png")
    bpy.ops.render.render(write_still=True)
'''


def stage_is_cached(stage_dir: Path, artifact: Path, config_hash: str) -> bool:
    rep = stage_dir / "report.json"
    if not rep.exists() or not artifact.exists():
        return False
    try:
        data = json.loads(rep.read_text(encoding="utf-8"))
        return data.get("_config_hash") == config_hash and data.get("status", "OK") == "OK"
    except Exception:
        return False


def write_stage_report(stage_dir: Path, config_hash: str, payload: dict) -> None:
    stage_dir.mkdir(parents=True, exist_ok=True)
    payload["_config_hash"] = config_hash
    payload.setdefault("status", "OK")
    (stage_dir / "report.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def ensure_uv_obj(mesh_path: Path, uv_out_path: Path, target_faces: int = 100000) -> dict:
    """Loads mesh; if UV is absent, decimates high-poly raw meshes (>120k faces) cleanly via
    pymeshlab QEM to ~100k faces and runs xatlas with 2048px/4px padding for crisp zero-overlap UVs."""
    mesh = trimesh.load(str(mesh_path), force="mesh", process=False)
    uv = getattr(mesh.visual, "uv", None)
    if uv is not None and len(uv) == len(mesh.vertices) and str(mesh_path).lower().endswith(".obj"):
        return {"uv_obj": str(mesh_path), "unwrapped_now": False, "faces": int(len(mesh.faces))}

    if uv is not None and len(uv) == len(mesh.vertices):
        uv_out_path.parent.mkdir(parents=True, exist_ok=True)
        mesh.export(str(uv_out_path))
        return {"uv_obj": str(uv_out_path), "unwrapped_now": False, "faces": int(len(mesh.faces))}

    import xatlas

    t0 = time.time()
    faces_orig = int(len(mesh.faces))
    decimated = False

    # High-poly raw meshes (e.g. 500k-950k faces from TripoSF/Hi3DGen) fragment xatlas into 15k+ micro-islands.
    # Clean quadric decimation to ~100k preserves facial/silhouette detail while yielding crisp, non-overlapping UVs.
    if faces_orig > 120000:
        try:
            import pymeshlab

            ms = pymeshlab.MeshSet()
            ms.add_mesh(pymeshlab.Mesh(np.asarray(mesh.vertices, dtype=np.float64), np.asarray(mesh.faces, dtype=np.int32)))
            ms.meshing_remove_duplicate_vertices()
            ms.meshing_remove_duplicate_faces()
            if hasattr(ms, "meshing_remove_null_faces"):
                ms.meshing_remove_null_faces()
            ms.meshing_decimation_quadric_edge_collapse(
                targetfacenum=target_faces,
                preserveboundary=True,
                preservenormal=True,
                preservetopology=True,
                qualitythr=0.5,
            )
            cm = ms.current_mesh()
            v = np.asarray(cm.vertex_matrix(), dtype=np.float32)
            f = np.asarray(cm.face_matrix(), dtype=np.uint32)
            decimated = True
            print(f"[ensure_uv_obj] QEM decimated {faces_orig} -> {len(f)} faces before xatlas", flush=True)
        except Exception as e:
            print(f"[ensure_uv_obj] pymeshlab decimation warn (falling back to raw mesh): {e}", flush=True)
            v = np.asarray(mesh.vertices, dtype=np.float32)
            f = np.asarray(mesh.faces, dtype=np.uint32)
    else:
        v = np.asarray(mesh.vertices, dtype=np.float32)
        f = np.asarray(mesh.faces, dtype=np.uint32)

    atlas = xatlas.Atlas()
    atlas.add_mesh(v, f)
    pack_opts = xatlas.PackOptions()
    pack_opts.resolution = 2048
    pack_opts.padding = 4
    pack_opts.bilinear = True
    atlas.generate(pack_options=pack_opts)
    vmapping, indices, uvs = atlas[0]
    v_new = v[vmapping]
    mesh_uv = trimesh.Trimesh(
        vertices=v_new,
        faces=indices,
        process=False,
        visual=trimesh.visual.TextureVisuals(uv=uvs),
    )
    uv_out_path.parent.mkdir(parents=True, exist_ok=True)
    mesh_uv.export(str(uv_out_path))
    return {
        "uv_obj": str(uv_out_path),
        "unwrapped_now": True,
        "decimated": decimated,
        "faces_before": faces_orig,
        "faces_after": int(len(indices)),
        "verts_after": int(len(v_new)),
        "unwrap_s": round(time.time() - t0, 2),
    }


def run_cmd(cmd: list[str], env: dict | None = None, label: str = "") -> None:
    print(f"[run_asset] >>> {label}: {' '.join(cmd)}", flush=True)
    p = subprocess.run(cmd, env=env)
    if p.returncode != 0:
        raise RuntimeError(f"Stage failed ({label}) with exit code {p.returncode}")


def build_compat_config(
    cfg: dict,
    uv_obj_path: str,
    prev_tex_path: str,
    ref_images: list[str],
    out_root: Path,
    compat_path: Path,
) -> Path:
    vid = cfg.get("variant_id", "pbr")
    gt_views = {}
    if cfg["tier"] == "photos" and "views" in cfg.get("photo_blend", {}):
        for v in cfg["photo_blend"]["views"]:
            gt_views[v["name"]] = v["image"]
    elif ref_images:
        gt_views["front"] = ref_images[0]

    compat = {
        "asset_id": cfg["id"],
        "seed": int(cfg["seed"]),
        "work_dir": str(out_root / "work"),
        "models_dir": str(out_root / "staged_models"),
        "evidence_dir": str(out_root),
        "variants": [
            {
                "id": vid,
                "uv_obj": uv_obj_path,
                "prev_texture": prev_tex_path,
                "gt_views": gt_views,
            }
        ],
        "reference_images": ref_images,
        "paint": cfg["paint"],
        "photo_blend": cfg["photo_blend"],
        "patch_repair": cfg["patch_repair"],
        "pack": cfg["pack"],
        "eval": {
            "render_res": cfg["qa"]["render_res"],
            "views": cfg["qa"]["views"],
            "crop_boxes": cfg["qa"].get("standard_crops", {}),
        },
    }
    (out_root / "work" / vid).mkdir(parents=True, exist_ok=True)
    compat_path.write_text(json.dumps(compat, indent=2, ensure_ascii=False), encoding="utf-8")
    return compat_path


def compute_qa_gates(cfg: dict, eval_rep: dict, pack_rep: dict, mr_exists: bool) -> dict:
    vid = cfg.get("variant_id", "pbr")
    qa_cfg = cfg["qa"]
    ev = eval_rep["variants"][vid]
    fin = ev["final"]
    bef = ev["before"]
    pk = pack_rep["variants"][vid]

    lap_val = fin["views_laplacian_mean"]
    patch_pct = fin["patch_texels_pct"]
    sat_pct = fin["texture_sat_pct"]
    glb_8k_mb = pk["glb_8k"]["size_mb"]
    glb_4k_mb = pk["glb_4k"]["size_mb"]

    gates = {
        "lap_var": {
            "value": lap_val,
            "threshold": f">= {qa_cfg['lap_min']}",
            "pass": lap_val >= float(qa_cfg["lap_min"]),
        },
        "bright_patches": {
            "value": patch_pct,
            "threshold": f"<= {qa_cfg['patch_max_pct']}%",
            "pass": patch_pct <= float(qa_cfg["patch_max_pct"]),
        },
        "saturation_band": {
            "value": sat_pct,
            "threshold": f"[{qa_cfg['sat_min_pct']}%, {qa_cfg['sat_max_pct']}%]",
            "pass": float(qa_cfg["sat_min_pct"]) <= sat_pct <= float(qa_cfg["sat_max_pct"]),
        },
        "mr_pbr_present": {
            "value": mr_exists,
            "threshold": f"required={qa_cfg['mr_required']}",
            "pass": (mr_exists if qa_cfg["mr_required"] else True),
        },
        "glb_sizes_sane": {
            "value": {"8k_mb": glb_8k_mb, "4k_mb": glb_4k_mb},
            "threshold": f"[{qa_cfg['glb_min_mb']}, {qa_cfg['glb_max_mb']}] MB",
            "pass": (
                float(qa_cfg["glb_min_mb"]) <= glb_8k_mb <= float(qa_cfg["glb_max_mb"])
                and float(qa_cfg["glb_min_mb"]) <= glb_4k_mb <= float(qa_cfg["glb_max_mb"])
            ),
        },
    }

    if cfg["tier"] == "photos" and qa_cfg.get("require_photo_consistency_gain", True):
        b_maes = [v["mae_255"] for v in bef.get("photo_consistency", {}).values()]
        f_maes = [v["mae_255"] for v in fin.get("photo_consistency", {}).values()]
        b_mean = round(float(np.mean(b_maes)), 2) if b_maes else 999.0
        f_mean = round(float(np.mean(f_maes)), 2) if f_maes else 999.0
        gates["photo_consistency"] = {
            "value": {"before_mae": b_mean, "final_mae": f_mean},
            "threshold": "final_mae < before_mae",
            "pass": f_mean < b_mean,
        }

    overall = all(g["pass"] for g in gates.values())
    return {
        "asset_id": cfg["id"],
        "tier": cfg["tier"],
        "overall_pass": overall,
        "gates": gates,
        "crops": ev.get("crops", {}),
    }


def auto_publish(cfg: dict, out_root: Path, pack_rep: dict, total_time_s: float, peak_vram_mib: int) -> dict:
    """Backs up previous GLBs, copies staged GLBs to models_dir, updates manifest.json, runs deploy & HTTP 200 check."""
    vid = cfg.get("variant_id", "pbr")
    asset_id = cfg["id"]
    models_dir = Path(cfg["models_dir"])
    backup_dir = out_root / "backup_prev"
    backup_dir.mkdir(parents=True, exist_ok=True)

    staged_dir = out_root / "staged_models"
    mode_8k = cfg["outputs"].get("mode_8k", f"{vid}_8k")
    mode_4k = cfg["outputs"].get("mode_4k", f"{vid}_4k")
    glb_names = cfg["outputs"]["glb_names"]
    src_8k = staged_dir / f"{asset_id}__{vid}_8k.glb"
    src_4k = staged_dir / f"{asset_id}__{vid}_4k.glb"
    dst_8k = models_dir / glb_names[0]
    dst_4k = models_dir / glb_names[1]

    for dst in (dst_8k, dst_4k):
        if dst.exists():
            shutil.copy2(dst, backup_dir / dst.name)

    shutil.copy2(src_8k, dst_8k)
    shutil.copy2(src_4k, dst_4k)

    # Update manifest.json preserving all existing cases and modes
    man_path = Path(cfg["manifest_path"])
    man = json.loads(man_path.read_text(encoding="utf-8"))
    pk = pack_rep["variants"][vid]
    uv_obj_faces = 0
    uv_obj_verts = 0
    pref = json.loads((out_root / "00_preflight" / "report.json").read_text(encoding="utf-8"))
    uv_obj_faces = pref.get("preflight", {}).get("faces", 0)
    uv_obj_verts = pref.get("preflight", {}).get("verts", 0)

    for c in man.get("cases", []):
        if c.get("id") == asset_id:
            c["modes"][mode_8k] = {
                "faces": uv_obj_faces,
                "verts": uv_obj_verts,
                "tempo_s": round(total_time_s, 1),
                "vram": peak_vram_mib,
                "size_mb": pk["glb_8k"]["size_mb"],
                "pbr": True,
            }
            c["modes"][mode_4k] = {
                "faces": uv_obj_faces,
                "verts": uv_obj_verts,
                "tempo_s": round(total_time_s, 1),
                "vram": peak_vram_mib,
                "size_mb": pk["glb_4k"]["size_mb"],
                "pbr": True,
            }
            break
    man_path.write_text(json.dumps(man, indent=2, ensure_ascii=False), encoding="utf-8")

    # Deploy via deploy.sh
    run_cmd(["bash", str(REPO_ROOT / "tools" / "modelos3d-site" / "deploy.sh")], label="08_deploy")

    # HTTP 200 verification
    base_url = cfg["pack"]["base_url"]
    http_res = {}
    for gname in glb_names:
        url = f"{base_url}/models/{gname}"
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=20) as resp:
            http_res[url] = {
                "status": resp.status,
                "content_length": int(resp.headers.get("Content-Length", "0")),
                "last_modified": resp.headers.get("Last-Modified"),
            }
    return {"published": True, "http": http_res, "modes": [mode_8k, mode_4k]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True, help="Output evidence directory for this asset")
    ap.add_argument("--resume", action="store_true", help="Skip completed stages with matching config hash")
    ap.add_argument("--auto-publish", action="store_true", help="Publish automatically ONLY if QA passes")
    args = ap.parse_args()

    cfg = load_asset_config(args.config)
    chash = cfg["_config_hash"]
    vid = cfg.get("variant_id", "pbr")
    out_root = Path(args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    peak_vram_overall = 0

    print(f"=== [pipe_std] Asset={cfg['id']} tier={cfg['tier']} hash={chash} ===", flush=True)

    # ── 00_preflight ──────────────────────────────────────────────────────────
    d00 = out_root / "00_preflight"
    uv_work_obj = out_root / "work" / vid / "uv.obj"
    if args.resume and stage_is_cached(d00, uv_work_obj, chash):
        pref_rep = json.loads((d00 / "report.json").read_text(encoding="utf-8"))
        uv_obj_path = pref_rep["uv_obj"]
        print("[00_preflight] RESUME (cached)", flush=True)
    else:
        raw_pref = uv_preflight(cfg["uv"])
        unwrap_info = ensure_uv_obj(Path(cfg["uv"]), uv_work_obj)
        uv_obj_path = unwrap_info["uv_obj"]
        final_pref = uv_preflight(uv_obj_path) if unwrap_info["unwrapped_now"] else raw_pref
        pref_rep = {"uv_obj": uv_obj_path, "unwrap": unwrap_info, "preflight": final_pref}
        write_stage_report(d00, chash, pref_rep)
        print(f"[00_preflight] OK: islands={final_pref['num_islands']} warning={final_pref['warning']}", flush=True)

    # ── 01_conditioning ───────────────────────────────────────────────────────
    d01 = out_root / "01_conditioning"
    d01.mkdir(parents=True, exist_ok=True)
    tier = cfg["tier"]
    if tier == "none":
        ref_imgs = [str(d01 / f"neutral_{n}.png") for n in ("front", "left", "back", "right")]
        if not (args.resume and stage_is_cached(d01, Path(ref_imgs[0]), chash)):
            with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as tf:
                tf.write(NEUTRAL_RENDER_BLENDER)
                sp = tf.name
            try:
                run_cmd(["blender", "-b", "-P", sp, "--", uv_obj_path, str(d01)], label="01_neutral_renders")
            finally:
                Path(sp).unlink(missing_ok=True)
            write_stage_report(d01, chash, {"tier": tier, "ref_images": ref_imgs})
    else:
        ref_imgs = list(cfg["input_images"])
        write_stage_report(d01, chash, {"tier": tier, "ref_images": ref_imgs})

    # Neutral gray baseline texture if asset had no previous texture
    prev_tex = cfg.get("prev_texture")
    if not prev_tex or not Path(prev_tex).exists():
        prev_tex_p = out_root / "01_conditioning" / "baseline_gray_512.png"
        if not prev_tex_p.exists():
            Image.new("RGB", (512, 512), (191, 196, 204)).save(prev_tex_p)
        prev_tex = str(prev_tex_p)

    compat_cfg = build_compat_config(cfg, uv_obj_path, prev_tex, ref_imgs, out_root, out_root / "_compat_cfg.json")

    # ── 02_paint_hunyuan (uses pipeline/paint_quality.py -> etapa_a) ──────────
    d02 = out_root / "etapa_a"
    tex_02_candidates = sorted(d02.glob(f"{vid}_native_*.png")) if d02.exists() else []
    if args.resume and tex_02_candidates and stage_is_cached(d02, tex_02_candidates[0], chash):
        rep02 = json.loads((d02 / "report.json").read_text(encoding="utf-8"))
        print("[02_paint_hunyuan] RESUME (cached)", flush=True)
    else:
        run_cmd([HUNYUAN_PY, str(PIPELINE_DIR / "paint_quality.py"), "--config", str(compat_cfg)], label="02_paint_hunyuan")
        rep02 = json.loads((d02 / "report.json").read_text(encoding="utf-8"))
        write_stage_report(d02, chash, rep02)
    peak_vram_overall = max(peak_vram_overall, int(rep02.get("vram_pico_mib", 0)))

    # ── 03_photo_blend (tier == "photos" only) ────────────────────────────────
    d03 = out_root / "etapa_b"
    d03.mkdir(parents=True, exist_ok=True)
    if tier == "photos":
        art03 = d03 / f"{vid}_blended_2048.png"
        if not (args.resume and stage_is_cached(d03, art03, chash)):
            run_cmd(
                [HUNYUAN_PY, str(PIPELINE_DIR / "photo_blend.py"), "--config", str(compat_cfg), "--input-dir", str(d02), "--output-dir", str(d03)],
                label="03_photo_blend",
            )
            rep03 = json.loads((d03 / "report.json").read_text(encoding="utf-8"))
            write_stage_report(d03, chash, rep03)
        else:
            rep03 = json.loads((d03 / "report.json").read_text(encoding="utf-8"))
        peak_vram_overall = max(peak_vram_overall, int(rep03.get("vram_pico_mib", 0)))
        in_for_04 = d03
        photo_ref_arg = ["--photo-ref-dir", str(d03)]
    else:
        write_stage_report(d03, chash, {"skipped": True, "reason": f"tier={tier} (photo_blend only runs on tier='photos')"})
        in_for_04 = d02
        photo_ref_arg = []

    # ── 04_patch_repair ───────────────────────────────────────────────────────
    d04 = out_root / "etapa_c"
    art04 = d04 / f"{vid}_repaired.png"
    if not (args.resume and stage_is_cached(d04, art04, chash)):
        run_cmd(
            [
                HUNYUAN_PY, str(PIPELINE_DIR / "patch_repair.py"),
                "--config", str(compat_cfg),
                "--input-dir", str(in_for_04),
                "--output-dir", str(d04),
                "--report-out", str(d04 / "report.json"),
                *photo_ref_arg,
            ],
            label="04_patch_repair",
        )
        rep04 = json.loads((d04 / "report.json").read_text(encoding="utf-8"))
        write_stage_report(d04, chash, rep04)
    else:
        print("[04_patch_repair] RESUME (cached)", flush=True)

    # ── 05_trellis_pbr (MetallicRoughness 2048 PNG) ───────────────────────────
    d05 = out_root / "etapa_trellis_pbr"
    d05.mkdir(parents=True, exist_ok=True)
    mr_final_dir = d05 / "mr_final"
    mr_final_dir.mkdir(parents=True, exist_ok=True)
    mr_dst = mr_final_dir / f"{vid}_metallic_roughness.png"
    if cfg["trellis_pbr"].get("enabled", True):
        if not (args.resume and stage_is_cached(d05, mr_dst, chash)):
            env_t2 = dict(os.environ)
            env_t2["ATTN_BACKEND"] = cfg["trellis_pbr"].get("attn_backend", "xformers")
            run_cmd(
                [
                    TRELLIS_PY, str(PIPELINE_DIR / "retexture_trellis.py"),
                    "--config", str(compat_cfg),
                    "--cond-image", ref_imgs[0],
                    "--cond-tag", "primary",
                    "--report-out", str(d05 / "report.json"),
                ],
                env=env_t2,
                label="05_trellis_pbr",
            )
            rep05 = json.loads((d05 / "report.json").read_text(encoding="utf-8"))
            mr_src_str = rep05.get("variants", {}).get(vid, {}).get("mr_path", "")
            if mr_src_str and Path(mr_src_str).is_file():
                shutil.copy2(Path(mr_src_str), mr_dst)
            write_stage_report(d05, chash, rep05)
        else:
            rep05 = json.loads((d05 / "report.json").read_text(encoding="utf-8"))
            print("[05_trellis_pbr] RESUME (cached)", flush=True)
        peak_vram_overall = max(peak_vram_overall, int(rep05.get("vram_pico_mib", 0)))

    # ── 06_pack_glb (8K/4K JPEG q95 + MR 2048 PNG) ────────────────────────────
    d06 = out_root / "etapa_e"
    d06.mkdir(parents=True, exist_ok=True)
    staged_8k = out_root / "staged_models" / f"{cfg['id']}__{vid}_8k.glb"
    if not (args.resume and stage_is_cached(d06, staged_8k, chash)):
        pbr_args = ["--pbr-dir", str(mr_final_dir)] if mr_dst.exists() else []
        run_cmd(
            [
                HUNYUAN_PY, str(PIPELINE_DIR / "pack_glb.py"),
                "--config", str(compat_cfg),
                "--input-dir", str(d04),
                "--variants", vid,
                "--report-out", str(d06 / "report.json"),
                *pbr_args,
            ],
            label="06_pack_glb",
        )
        rep06 = json.loads((d06 / "report.json").read_text(encoding="utf-8"))
        write_stage_report(d06, chash, rep06)
    else:
        rep06 = json.loads((d06 / "report.json").read_text(encoding="utf-8"))
        print("[06_pack_glb] RESUME (cached)", flush=True)
    peak_vram_overall = max(peak_vram_overall, int(rep06.get("vram_pico_mib", 0)))

    # ── 07_qa_eval -> qa.json ─────────────────────────────────────────────────
    d07 = out_root / "etapa_d"
    d07.mkdir(parents=True, exist_ok=True)
    qa_path = out_root / "qa.json"
    if not (args.resume and stage_is_cached(d07, qa_path, chash)):
        run_cmd(
            [
                HUNYUAN_PY, str(PIPELINE_DIR / "eval_texture.py"),
                "--config", str(compat_cfg),
                "--final-dir", str(d04),
                "--report-out", str(d07 / "report.json"),
            ],
            label="07_qa_eval",
        )
        rep07 = json.loads((d07 / "report.json").read_text(encoding="utf-8"))
        write_stage_report(d07, chash, rep07)
    else:
        rep07 = json.loads((d07 / "report.json").read_text(encoding="utf-8"))
        print("[07_qa_eval] RESUME (cached)", flush=True)

    qa = compute_qa_gates(cfg, rep07, rep06, mr_dst.exists())
    total_s = round(time.time() - t_start, 2)
    qa["tempo_total_s"] = total_s
    qa["vram_pico_mib"] = peak_vram_overall
    qa["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    qa_path.write_text(json.dumps(qa, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── 08_publish (ONLY if QA overall_pass == True and --auto-publish) ───────
    pub_info = {"published": False, "reason": "auto-publish disabled"}
    if args.auto_publish:
        if qa["overall_pass"]:
            pub_info = auto_publish(cfg, out_root, rep06, total_s, peak_vram_overall)
        else:
            pub_info = {"published": False, "reason": "QA FAIL — mantendo anterior intacto"}
    qa["publish"] = pub_info
    qa_path.write_text(json.dumps(qa, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        f"RUN_ASSET_DONE asset={cfg['id']} tier={tier} qa_pass={qa['overall_pass']} "
        f"published={pub_info['published']} peak_vram={peak_vram_overall}MiB tempo={total_s}s",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
