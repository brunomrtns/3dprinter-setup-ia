#!/usr/bin/env python3
"""ETAPA 2 — Renderiza malha texturizada em 4 vistas ortográficas (front/left/back/top)
com fundo transparente via Blender headless (Emission + Standard + Cycles 1 sample) e
calcula métricas obrigatórias sobre a silhueta:
  - dark_pct (luminância < 80): deve ficar entre 4% e 20%
  - mud_pct ("cinzalama", luminância 80–180): deve ser < 10%
"""
import argparse
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1 :]
    ap = argparse.ArgumentParser()
    ap.add_argument("--obj", required=True)
    ap.add_argument("--texture", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--res", type=int, default=512)
    return ap.parse_args(argv)


def main():
    args = parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene

    # Cycles CPU, 1 sample, 0 bounces, Emission shader + Standard color management = cor exata da textura
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 1
    scene.cycles.use_denoising = False
    scene.cycles.max_bounces = 0
    scene.cycles.diffuse_bounces = 0
    scene.cycles.glossy_bounces = 0
    scene.render.resolution_x = args.res
    scene.render.resolution_y = args.res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0

    # Importa uv.obj preservando eixo Y-up (forward_axis='Z', up_axis='Y' -> em Blender vira Z-up, Y-front ou mantemos raw)
    # Importar com forward_axis='NEGATIVE_Z', up_axis='Y' (default glTF/OBJ -> Blender Z-up):
    #   OBJ +Y (up)    -> Blender +Z (up)
    #   OBJ +Z (front) -> Blender -Y (front)
    #   OBJ +X (right) -> Blender +X (right)
    bpy.ops.wm.obj_import(filepath=args.obj)
    objs = [o for o in scene.objects if o.type == "MESH"]
    obj = objs[0]

    # Material Emission com textura 2048
    mat = bpy.data.materials.new("EvalMat")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out_node = nt.nodes.new("ShaderNodeOutputMaterial")
    emit_node = nt.nodes.new("ShaderNodeEmission")
    tex_node = nt.nodes.new("ShaderNodeTexImage")
    img = bpy.data.images.load(args.texture)
    img.colorspace_settings.name = "sRGB"
    tex_node.image = img
    nt.links.new(tex_node.outputs["Color"], emit_node.inputs["Color"])
    nt.links.new(emit_node.outputs["Emission"], out_node.inputs["Surface"])

    obj.data.materials.clear()
    obj.data.materials.append(mat)

    # Calcula bounding box no espaço world do Blender
    coords = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    bmin = Vector((min(c.x for c in coords), min(c.y for c in coords), min(c.z for c in coords)))
    bmax = Vector((max(c.x for c in coords), max(c.y for c in coords), max(c.z for c in coords)))
    center = (bmin + bmax) * 0.5
    ext = bmax - bmin

    # Cria câmera ortográfica
    cam_data = bpy.data.cameras.new("OrthoCam")
    cam_data.type = "ORTHO"
    cam_obj = bpy.data.objects.new("OrthoCam", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    # Em Blender após obj_import default (up=Y -> +Z, forward=-Z -> +Y, logo +Z OBJ = -Y Blender):
    # Vamos verificar pela altura do capô qual extremo de Y é a frente!
    verts_w = np.array([tuple(obj.matrix_world @ v.co) for v in obj.data.vertices], dtype=np.float32)
    z_pos_y = verts_w[verts_w[:, 1] > center.y + ext.y * 0.25, 2].max()
    z_neg_y = verts_w[verts_w[:, 1] < center.y - ext.y * 0.25, 2].max()
    # Capô é mais baixo que a traseira hatchback
    front_sign = 1.0 if z_pos_y < z_neg_y else -1.0

    dist = max(ext.x, ext.y, ext.z) * 2.5
    views_cfg = {
        "front": (
            center + Vector((0.0, front_sign * dist, 0.0)),
            max(ext.x, ext.z) * 1.15,
            Vector((0.0, 0.0, 1.0)),
        ),
        "back": (
            center + Vector((0.0, -front_sign * dist, 0.0)),
            max(ext.x, ext.z) * 1.15,
            Vector((0.0, 0.0, 1.0)),
        ),
        "left": (
            center + Vector((-dist, 0.0, 0.0)),
            max(ext.y, ext.z) * 1.15,
            Vector((0.0, 0.0, 1.0)),
        ),
        "top": (
            center + Vector((0.0, 0.0, dist)),
            max(ext.x, ext.y) * 1.15,
            Vector((0.0, front_sign, 0.0)),
        ),
    }

    results = {}
    all_pass = True

    for vname, (cam_pos, ortho_scale, up_vec) in views_cfg.items():
        cam_obj.location = cam_pos
        direction = (center - cam_pos).normalized()
        rot_quat = direction.to_track_quat("-Z", "Y")
        cam_obj.rotation_euler = rot_quat.to_euler()
        # Para vista top, ajusta rotação em Z para o carro ficar vertical na imagem
        if vname == "top":
            cam_obj.rotation_euler = (0.0, 0.0, 0.0 if front_sign > 0 else math.pi)
        cam_data.ortho_scale = ortho_scale

        out_png = os.path.join(args.outdir, f"{args.prefix}_{vname}.png")
        scene.render.filepath = out_png
        bpy.ops.render.render(write_still=True)

        # Lê PNG renderizado e calcula métricas sobre silhueta (alpha > 128)
        im_b = bpy.data.images.load(out_png)
        px = np.array(im_b.pixels[:], dtype=np.float32).reshape(args.res, args.res, 4)
        bpy.data.images.remove(im_b)

        rgb = px[..., :3] * 255.0
        alpha = px[..., 3] * 255.0
        sil = alpha > 128.0
        n_sil = int(sil.sum())
        if n_sil == 0:
            results[vname] = {"error": "empty_silhouette", "pass": False}
            all_pass = False
            continue

        lum = (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2])[sil]
        dark_pct = round(float((lum < 80.0).mean() * 100.0), 2)
        mud_pct = round(float(((lum >= 80.0) & (lum <= 180.0)).mean() * 100.0), 2)
        bright_pct = round(float((lum > 180.0).mean() * 100.0), 2)

        ok_dark = 4.0 <= dark_pct <= 20.0
        ok_mud = mud_pct < 10.0
        v_pass = ok_dark and ok_mud
        if not v_pass:
            all_pass = False

        results[vname] = {
            "png": out_png,
            "sil_px": n_sil,
            "dark_pct": dark_pct,
            "mud_pct": mud_pct,
            "bright_pct": bright_pct,
            "ok_dark_4_20": ok_dark,
            "ok_mud_lt_10": ok_mud,
            "pass": v_pass,
        }

    out = {"prefix": args.prefix, "all_pass": all_pass, "views": results}
    print("EVAL_JSON=" + json.dumps(out))


if __name__ == "__main__":
    main()
