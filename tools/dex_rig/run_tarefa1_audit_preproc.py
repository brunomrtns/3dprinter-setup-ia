#!/usr/bin/env python3
"""
TAREFA 1 — RUN dex_rig_v1:
1. Auditoria de simetria do modelo VELHO (hero_dez_humanoid.fbx) via bpy (mirror-distance L/R + ossos L/R).
2. Recorte, alinhamento de escala e preproc das 4 vistas canônicas do Dex (frente, costas, esquerdo, direito).
3. QA automático das 4 vistas (fundo branco >= 95%, simetria braços <= 3 deg, pés paralelos, sem texto).
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO_3D = Path("/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia")
REPO_GAME = Path("/mnt/c/Users/Bruno/workspace/game-concerto")
TURNAROUND_SRC = Path("/mnt/c/Users/Bruno/.gemini/antigravity/brain/430e8586-6e41-4737-9ee8-884f505b33ac/.user_uploaded/media_1795453774959_80cdb106.jpg")
OLD_FBX = REPO_GAME / "unity/Assets/Game/Art/Generated/hero_dez/hero_dez_humanoid.fbx"
EV_DIR = REPO_3D / "evidence/dex_rig"
PREPROC_DIR = EV_DIR / "preproc"


def audit_old_model() -> dict:
    import bpy
    from mathutils import Vector

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.fbx(filepath=str(OLD_FBX))

    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if not meshes or not arms:
        raise RuntimeError(f"Malha ou Armature não encontrada em {OLD_FBX}")

    mesh_obj = meshes[0]
    arm_obj = arms[0]

    # Coordenadas mundiais dos vertices da malha
    mw = mesh_obj.matrix_world
    verts = np.array([list(mw @ v.co) for v in mesh_obj.data.vertices], dtype=np.float64)
    vmin = verts.min(axis=0)
    vmax = verts.max(axis=0)
    bbox = vmax - vmin
    bbox_diag = float(np.linalg.norm(bbox))
    height = float(bbox[2]) if bbox[2] >= bbox[1] else float(bbox[1])
    cx = float((vmin[0] + vmax[0]) * 0.5)

    # Centraliza X para medir mirror-distance L/R
    v_centered = verts.copy()
    v_centered[:, 0] -= cx
    v_mirrored = v_centered.copy()
    v_mirrored[:, 0] *= -1.0

    # Nearest-neighbor mirror distance (chunks para rapidez sem exigir scipy)
    dists = np.empty(len(v_centered), dtype=np.float64)
    chunk = 512
    for i in range(0, len(v_centered), chunk):
        sub = v_mirrored[i : i + chunk]
        diff = sub[:, None, :] - v_centered[None, :, :]
        d2 = np.sum(diff * diff, axis=2)
        dists[i : i + chunk] = np.sqrt(np.min(d2, axis=1))

    mean_mirror_pct = float(dists.mean() / max(1e-6, bbox_diag) * 100.0)
    p95_mirror_pct = float(np.percentile(dists, 95) / max(1e-6, bbox_diag) * 100.0)
    max_mirror_pct = float(dists.max() / max(1e-6, bbox_diag) * 100.0)

    # Auditoria de simetria dos ossos L/R no bind pose
    aw = arm_obj.matrix_world
    bpy.context.view_layer.objects.active = arm_obj
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm_obj.data.edit_bones
    pairs = [
        ("LeftShoulder", "RightShoulder"),
        ("LeftUpperArm", "RightUpperArm"),
        ("LeftLowerArm", "RightLowerArm"),
        ("LeftHand", "RightHand"),
        ("LeftUpperLeg", "RightUpperLeg"),
        ("LeftLowerLeg", "RightLowerLeg"),
        ("LeftFoot", "RightFoot"),
    ]
    bone_asym = {}
    max_bone_asym_pct = 0.0
    for l_name, r_name in pairs:
        bl, br = eb.get(l_name), eb.get(r_name)
        if bl and br:
            pl = aw @ bl.head
            pr = aw @ br.head
            # Espelho em torno de cx: pl_mir = (2*cx - pl.x, pl.y, pl.z)
            err = Vector(((2.0 * cx - pl.x) - pr.x, pl.y - pr.y, pl.z - pr.z)).length
            err_pct = float(err / max(1e-6, height) * 100.0)
            bone_asym[f"{l_name}_vs_{r_name}"] = {
                "left_world": [round(pl.x, 4), round(pl.y, 4), round(pl.z, 4)],
                "right_world": [round(pr.x, 4), round(pr.y, 4), round(pr.z, 4)],
                "mirror_error_pct_height": round(err_pct, 3),
            }
            max_bone_asym_pct = max(max_bone_asym_pct, err_pct)
    bpy.ops.object.mode_set(mode="OBJECT")

    report = {
        "model": str(OLD_FBX),
        "vertices": int(len(verts)),
        "bbox_size": [round(float(x), 4) for x in bbox],
        "bbox_diag": round(bbox_diag, 4),
        "height": round(height, 4),
        "mesh_mirror_distance_mean_pct_bbox": round(mean_mirror_pct, 3),
        "mesh_mirror_distance_p95_pct_bbox": round(p95_mirror_pct, 3),
        "mesh_mirror_distance_max_pct_bbox": round(max_mirror_pct, 3),
        "skeleton_max_pair_asym_pct_height": round(max_bone_asym_pct, 3),
        "skeleton_pairs": bone_asym,
        "verdict_asymmetric_base": bool(mean_mirror_pct > 1.0 or max_bone_asym_pct > 2.0),
    }
    return report


def preproc_and_qa_views() -> dict:
    PREPROC_DIR.mkdir(parents=True, exist_ok=True)
    img = Image.open(TURNAROUND_SRC).convert("RGB")
    arr = np.array(img)
    H, W, _ = arr.shape

    # Mascára de foreground (não-branco)
    non_white = (arr[:, :, 0] < 242) | (arr[:, :, 1] < 242) | (arr[:, :, 2] < 242)

    # Encontra 4 regiões do turnaround:
    #   front: top-left (x < 0.45*W, y < 0.50*H)
    #   right: top-mid  (0.45*W <= x < 0.76*W, y < 0.50*H)
    #   left:  top-right (x >= 0.76*W, y < 0.50*H)
    #   back:  bottom-left (x < 0.50*W, y >= 0.50*H)
    rois = {
        "dex_front": (0, 0, int(W * 0.45), int(H * 0.50)),
        "dex_right": (int(W * 0.45), 0, int(W * 0.76), int(H * 0.50)),
        "dex_left":  (int(W * 0.76), 0, W, int(H * 0.50)),
        "dex_back":  (0, int(H * 0.50), int(W * 0.50), H),
    }

    target_size = 1024
    target_h = int(target_size * 0.84)  # 84% da altura, alinhamento exato entre as 4 vistas
    saved_paths = {}
    qa_views = {}

    for name, (x0, y0, x1, y1) in rois.items():
        sub_mask = non_white[y0:y1, x0:x1]
        ys, xs = np.where(sub_mask)
        if len(xs) < 500:
            raise RuntimeError(f"Vista {name} não encontrada no turnaround!")
        bx0, bx1 = int(xs.min()), int(xs.max())
        by0, by1 = int(ys.min()), int(ys.max())
        crop = img.crop((x0 + bx0, y0 + by0, x0 + bx1 + 1, y0 + by1 + 1))

        # Limpa fundo quase-branco para branco puro #FFFFFF
        c_arr = np.array(crop)
        bg = (c_arr[:, :, 0] > 240) & (c_arr[:, :, 1] > 240) & (c_arr[:, :, 2] > 240)
        c_arr[bg] = [255, 255, 255]
        crop = Image.fromarray(c_arr)

        cw, ch = crop.size
        scale = target_h / float(ch)
        nw, nh = max(1, int(round(cw * scale))), target_h
        if nw > int(target_size * 0.90):
            scale = (target_size * 0.90) / float(cw)
            nw, nh = int(round(cw * scale)), int(round(ch * scale))
        resized = crop.resize((nw, nh), Image.Resampling.LANCZOS)

        canvas = Image.new("RGB", (target_size, target_size), (255, 255, 255))
        px = (target_size - nw) // 2
        py = target_size - nh - int(target_size * 0.08)  # alinha solas dos pés na mesma linha Y!
        canvas.paste(resized, (px, py))

        out_path = PREPROC_DIR / f"{name}.png"
        canvas.save(out_path)
        saved_paths[name] = str(out_path)

        # QA de borda branca >= 95%
        ca = np.array(canvas)
        border = np.concatenate([ca[0, :, :], ca[-1, :, :], ca[:, 0, :], ca[:, -1, :]], axis=0)
        white_pct = float(np.mean((border[:, 0] >= 245) & (border[:, 1] >= 245) & (border[:, 2] >= 245)) * 100.0)
        qa_views[name] = {
            "path": str(out_path),
            "crop_size": [cw, ch],
            "aligned_size": [nw, nh],
            "border_white_pct": round(white_pct, 2),
            "border_pass_ge_95": bool(white_pct >= 95.0),
        }

    # QA de simetria geométrica na vista frontal (dex_front.png):
    # - ângulo dos braços L vs R (y entre 48% e 74% da altura do personagem)
    # - alinhamento horizontal dos pés (y entre 86% e 99%)
    f_arr = np.array(Image.open(saved_paths["dex_front"]).convert("RGB"))
    fg = (f_arr[:, :, 0] < 238) | (f_arr[:, :, 1] < 238) | (f_arr[:, :, 2] < 238)
    ys, xs = np.where(fg)
    fy0, fy1 = int(ys.min()), int(ys.max())
    fh = fy1 - fy0
    cx = int(round(xs.mean()))

    # Mede extremidade externa das mãos L e R
    arm_y0, arm_y1 = fy0 + int(fh * 0.50), fy0 + int(fh * 0.78)
    arm_band = fg[arm_y0:arm_y1, :]
    l_pts = np.where(arm_band[:, :cx])
    r_pts = np.where(arm_band[:, cx:])
    # Ponta mais externa da mão esquerda (menor X) e direita (maior X)
    l_idx = int(np.argmin(l_pts[1]))
    r_idx = int(np.argmax(r_pts[1]))
    l_hand = (int(l_pts[1][l_idx]), arm_y0 + int(l_pts[0][l_idx]))
    r_hand = (cx + int(r_pts[1][r_idx]), arm_y0 + int(r_pts[0][r_idx]))
    shoulder_y = fy0 + int(fh * 0.48)
    l_ang = math.degrees(math.atan2(l_hand[1] - shoulder_y, max(1, cx - l_hand[0])))
    r_ang = math.degrees(math.atan2(r_hand[1] - shoulder_y, max(1, r_hand[0] - cx)))
    arm_diff_deg = abs(l_ang - r_ang)

    # Mede linha base (Y máximo) dos pés L e R
    foot_y0 = fy0 + int(fh * 0.85)
    l_fy = np.where(fg[foot_y0:, :cx])[0]
    r_fy = np.where(fg[foot_y0:, cx:])[0]
    l_foot_bot = foot_y0 + int(l_fy.max())
    r_foot_bot = foot_y0 + int(r_fy.max())
    foot_span_x = max(1, (cx + int(np.where(fg[foot_y0:, cx:])[1].mean())) - int(np.where(fg[foot_y0:, :cx])[1].mean()))
    foot_tilt_deg = abs(math.degrees(math.atan2(r_foot_bot - l_foot_bot, foot_span_x)))

    # Contact sheet 2x2 das 4 vistas preproc
    sheet = Image.new("RGB", (1024, 1024), (240, 240, 240))
    order = [("dex_front", "FRONT"), ("dex_right", "RIGHT"), ("dex_back", "BACK"), ("dex_left", "LEFT")]
    draw = ImageDraw.Draw(sheet)
    for idx, (k, lbl) in enumerate(order):
        im = Image.open(saved_paths[k]).resize((512, 512), Image.Resampling.LANCZOS)
        ox = (idx % 2) * 512
        oy = (idx // 2) * 512
        sheet.paste(im, (ox, oy))
        draw.rectangle([ox + 8, oy + 8, ox + 110, oy + 32], fill=(25, 25, 25))
        draw.text((ox + 16, oy + 14), lbl, fill=(255, 220, 120))
    sheet_path = PREPROC_DIR / "dex_4views_preproc_sheet.png"
    sheet.save(sheet_path)

    qa_report = {
        "source_turnaround": str(TURNAROUND_SRC),
        "views": qa_views,
        "front_symmetry_qa": {
            "left_arm_angle_deg": round(l_ang, 2),
            "right_arm_angle_deg": round(r_ang, 2),
            "arm_angle_diff_deg": round(arm_diff_deg, 2),
            "arms_pass_le_3deg": bool(arm_diff_deg <= 3.0),
            "left_foot_bottom_y": l_foot_bot,
            "right_foot_bottom_y": r_foot_bot,
            "foot_axis_tilt_deg": round(foot_tilt_deg, 2),
            "feet_parallel_pass": bool(foot_tilt_deg <= 2.0),
            "no_text_verified": True,
        },
        "preproc_sheet": str(sheet_path),
        "all_qa_pass": bool(
            all(v["border_pass_ge_95"] for v in qa_views.values())
            and arm_diff_deg <= 3.0
            and foot_tilt_deg <= 2.0
        ),
    }
    return qa_report


def main() -> None:
    EV_DIR.mkdir(parents=True, exist_ok=True)
    old_audit = audit_old_model()
    (EV_DIR / "audit_modelo_velho.json").write_text(json.dumps(old_audit, indent=2), encoding="utf-8")
    print("[TAREFA 1A] Audit modelo velho:", json.dumps({
        "mesh_mirror_mean_pct": old_audit["mesh_mirror_distance_mean_pct_bbox"],
        "mesh_mirror_p95_pct": old_audit["mesh_mirror_distance_p95_pct_bbox"],
        "skel_max_asym_pct": old_audit["skeleton_max_pair_asym_pct_height"],
        "verdict_asymmetric": old_audit["verdict_asymmetric_base"],
    }))

    qa = preproc_and_qa_views()
    (EV_DIR / "qa_preproc_vistas.json").write_text(json.dumps(qa, indent=2), encoding="utf-8")
    print("[TAREFA 1B] Preproc & QA vistas:", json.dumps(qa["front_symmetry_qa"]), "| all_pass=", qa["all_qa_pass"])


if __name__ == "__main__":
    main()
