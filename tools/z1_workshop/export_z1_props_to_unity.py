#!/usr/bin/env python3
"""
Converte os GLBs 4K PBR (gerados via TripoSG + pipeline oficial) da Oficina Z1
para FBX 100% solidos/watertight (remove_doubles ANTES do Decimate!) + extrai
texturas PBR (BaseColor, MetallicSmoothness Unity, Cyan EmissionMask).
"""
import os
import json
import struct
import io
import bpy
import numpy as np
from PIL import Image
from mathutils import Vector

WORK = "/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia/work/z1_workshop"
OUT_ART = "/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Art/Generated/z1_workshop"
OUT_MAT = "/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Materials/Fab3D"
os.makedirs(OUT_ART, exist_ok=True)
os.makedirs(OUT_MAT, exist_ok=True)

ASSETS = [
    ("z1_prop_nave_manutencao", 8000, 0.35),
    ("z1_prop_cristal_energia", 4500, 0.28),
]


def extract_glb_textures(glb_path: str, slug: str, cyan_thresh: float):
    """Extrai BaseColor + MetallicRoughness do GLB, converte MR -> Unity MetallicSmoothness e gera EmissionMask ciano."""
    with open(glb_path, "rb") as f:
        data = f.read()
    # GLB header: magic(4), version(4), length(4); chunk0: len(4), type(4), json; chunk1: len(4), type(4), bin
    json_len, _ = struct.unpack_from("<II", data, 12)
    gltf = json.loads(data[20 : 20 + json_len].decode("utf-8"))
    bin_off = 20 + json_len
    bin_len, _ = struct.unpack_from("<II", data, bin_off)
    bin_blob = data[bin_off + 8 : bin_off + 8 + bin_len]

    def load_img(tex_idx):
        img_idx = gltf["textures"][tex_idx]["source"]
        img_def = gltf["images"][img_idx]
        bv = gltf["bufferViews"][img_def["bufferView"]]
        off = bv.get("byteOffset", 0)
        raw = bin_blob[off : off + bv["byteLength"]]
        return Image.open(io.BytesIO(raw))

    mat = gltf["materials"][0]
    pbr = mat.get("pbrMetallicRoughness", {})

    base_path = os.path.join(OUT_MAT, f"{slug}_albedo.png")
    ms_path   = os.path.join(OUT_MAT, f"{slug}_metallicsmooth.png")
    em_path   = os.path.join(OUT_MAT, f"{slug}_emission.png")

    if "baseColorTexture" in pbr:
        im_base = load_img(pbr["baseColorTexture"]["index"]).convert("RGB")
        # Reduz para 2048 se for maior para Unity importar rapido mantendo nitidez AAA
        if im_base.width > 2048:
            im_base = im_base.resize((2048, 2048), Image.LANCZOS)
        im_base.save(base_path)

        # Gera mascara de emissao apenas para pixels ciano/turquesa brilhantes (cristais e nucleo da nave!)
        arr = np.asarray(im_base, dtype=np.float32) / 255.0
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
        # Ciano: B e G bem maiores que R e com luminancia boa
        cyan_score = np.clip((np.minimum(g, b) - r * 1.15 - cyan_thresh) / 0.25, 0.0, 1.0)
        em = np.zeros_like(arr)
        em[..., 0] = r * cyan_score
        em[..., 1] = g * cyan_score
        em[..., 2] = b * cyan_score
        Image.fromarray(np.clip(em * 255.0, 0, 255).astype(np.uint8), mode="RGB").save(em_path)
        em_pct = float((cyan_score > 0.1).mean() * 100.0)
        print(f"  EXTRACTED {slug}: albedo={im_base.size}, cyan_emission_coverage={em_pct:.2f}%")

    if "metallicRoughnessTexture" in pbr:
        im_mr = load_img(pbr["metallicRoughnessTexture"]["index"]).convert("RGB")
        if im_mr.width > 2048:
            im_mr = im_mr.resize((2048, 2048), Image.LANCZOS)
        mr = np.asarray(im_mr, dtype=np.uint8)
        # glTF: G = Roughness, B = Metallic -> Unity URP MetallicGlossMap: R = Metallic, A = Smoothness (255 - Roughness)
        metallic = mr[..., 2]
        smoothness = 255 - mr[..., 1]
        rgba = np.stack([metallic, metallic, metallic, smoothness], axis=-1)
        Image.fromarray(rgba, mode="RGBA").save(ms_path)


def export_solid_fbx(glb_path: str, fbx_out: str, target_tris: int):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=glb_path)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # Remove empties sobrando
    for o in list(bpy.data.objects):
        if o != obj:
            bpy.data.objects.remove(o, do_unlink=True)

    # REGRA DA FABRICA: remove_doubles ANTES do Decimate para manter malha 100% solida e UVs intactas!
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=0.0002)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    if len(obj.data.polygons) > target_tris:
        dec = obj.modifiers.new(name="DecSolid", type="DECIMATE")
        dec.ratio = float(target_tris) / float(len(obj.data.polygons))
        bpy.ops.object.modifier_apply(modifier=dec.name)

    bpy.ops.object.shade_smooth()

    # Centraliza X/Y e ancora base exatamente em Z = 0 (Y = 0 no Unity!)
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    obj.location.x -= (mn.x + mx.x) * 0.5
    obj.location.y -= (mn.y + mx.y) * 0.5
    obj.location.z -= mn.z
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    bpy.ops.export_scene.fbx(
        filepath=fbx_out,
        use_selection=False,
        bake_anim=False,
        path_mode="AUTO",
    )
    print(f"  FBX_OK {os.path.basename(fbx_out)}: polys={len(obj.data.polygons)} verts={len(obj.data.vertices)} uv_layers={len(obj.data.uv_layers)}")


for slug, tris, thresh in ASSETS:
    glb = os.path.join(WORK, slug, "pbr_out", "staged_models", f"{slug}__pbr_4k.glb")
    if not os.path.exists(glb):
        raise FileNotFoundError(f"GLB nao encontrado: {glb}")
    print(f"=== Exporting {slug} ===")
    extract_glb_textures(glb, slug, thresh)
    fbx_out = os.path.join(OUT_ART, f"{slug}.fbx")
    export_solid_fbx(glb, fbx_out, tris)

print("ALL_Z1_PROPS_EXPORTED_OK")
