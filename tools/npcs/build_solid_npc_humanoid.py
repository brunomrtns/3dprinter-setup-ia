#!/usr/bin/env python3
"""
build_solid_npc_humanoid.py — Converte <slug>__pbr_4k.glb (TripoSG + PBR) + <slug>_skin.fbx (UniRig)
em <slug>_humanoid.fbx 100% solido/watertight, com UVs intactas, 22 ossos Unity Mecanim Humanoid,
limpeza de pesos vazados no queixo, botas ancoradas em Z=0 e texturas PBR + EmissionMask ciano!
"""
import io
import json
import os
import struct
import sys
import bpy
import numpy as np
from PIL import Image
from mathutils import Vector

sys.path.insert(0, "/mnt/c/Users/Bruno/workspace/game-concerto/tools/art/ai_generator")
from unirig_to_mecanim import UNIRIG_BIPED_MAP


def world_bounds(obj):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


def extract_glb_textures(glb_path: str, slug: str, out_mat_dir: str):
    with open(glb_path, "rb") as f:
        data = f.read()
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
        return Image.open(io.BytesIO(bin_blob[off : off + bv["byteLength"]]))

    pbr = gltf["materials"][0].get("pbrMetallicRoughness", {})
    if "baseColorTexture" in pbr:
        im_base = load_img(pbr["baseColorTexture"]["index"]).convert("RGB")
        if im_base.width > 2048:
            im_base = im_base.resize((2048, 2048), Image.LANCZOS)
        im_base.save(os.path.join(out_mat_dir, f"{slug}_albedo.png"))

        # Emissao ciano apenas em detalhes luminosos (frascos de cristal da Vo Segunda, visor/braceletes da Luma)
        arr = np.asarray(im_base, dtype=np.float32) / 255.0
        r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
        cyan_score = np.clip((np.minimum(g, b) - r * 1.35 - 0.34) / 0.22, 0.0, 1.0)
        em = np.zeros_like(arr)
        em[..., 0] = r * cyan_score
        em[..., 1] = g * cyan_score
        em[..., 2] = b * cyan_score
        Image.fromarray(np.clip(em * 255.0, 0, 255).astype(np.uint8), mode="RGB").save(
            os.path.join(out_mat_dir, f"{slug}_emission.png")
        )

    if "metallicRoughnessTexture" in pbr:
        im_mr = load_img(pbr["metallicRoughnessTexture"]["index"]).convert("RGB")
        if im_mr.width > 2048:
            im_mr = im_mr.resize((2048, 2048), Image.LANCZOS)
        mr = np.asarray(im_mr, dtype=np.uint8)
        metallic = mr[..., 2]
        smoothness = 255 - mr[..., 1]
        rgba = np.stack([metallic, metallic, metallic, smoothness], axis=-1)
        Image.fromarray(rgba, mode="RGBA").save(os.path.join(out_mat_dir, f"{slug}_metallicsmooth.png"))


def build_npc(slug: str, glb_src: str, fbx_skin: str, fbx_out: str, out_mat_dir: str, target_tris: int = 6500):
    os.makedirs(os.path.dirname(fbx_out), exist_ok=True)
    os.makedirs(out_mat_dir, exist_ok=True)

    extract_glb_textures(glb_src, slug, out_mat_dir)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=fbx_skin)
    arm = [o for o in bpy.data.objects if o.type == "ARMATURE"][0]
    skin_ref = [o for o in bpy.data.objects if o.type == "MESH"][0]
    r_mn, r_mx = world_bounds(skin_ref)
    r_sz = r_mx - r_mn
    r_c = (r_mn + r_mx) * 0.5

    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=glb_src)
    new_meshes = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for m in new_meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = new_meshes[0]
    if len(new_meshes) > 1:
        bpy.ops.object.join()
    clean_mesh = bpy.context.view_layer.objects.active
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # REGRA DA FABRICA: remove_doubles ANTES do Decimate!
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.remove_doubles(threshold=0.0002)
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    if len(clean_mesh.data.polygons) > target_tris:
        dec = clean_mesh.modifiers.new(name="DecSolid", type="DECIMATE")
        dec.ratio = float(target_tris) / float(len(clean_mesh.data.polygons))
        bpy.ops.object.modifier_apply(modifier=dec.name)

    c_mn, c_mx = world_bounds(clean_mesh)
    c_sz = c_mx - c_mn
    scale_r = r_sz.z / max(1e-5, c_sz.z)
    clean_mesh.scale = (scale_r, scale_r, scale_r)
    bpy.context.view_layer.update()
    c_mn, c_mx = world_bounds(clean_mesh)
    c_c = (c_mn + c_mx) * 0.5
    clean_mesh.location += (r_c - c_c)
    bpy.context.view_layer.update()
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    for vg in skin_ref.vertex_groups:
        clean_mesh.vertex_groups.new(name=vg.name)

    dt = clean_mesh.modifiers.new(name="TransferWeights", type="DATA_TRANSFER")
    dt.object = skin_ref
    dt.use_vert_data = True
    dt.data_types_verts = {"VGROUP_WEIGHTS"}
    dt.vert_mapping = "NEAREST"
    bpy.ops.object.modifier_apply(modifier=dt.name)

    for o in list(bpy.data.objects):
        if o not in (arm, clean_mesh):
            bpy.data.objects.remove(o, do_unlink=True)

    clean_mesh.parent = arm
    arm_mod = clean_mesh.modifiers.new(name="Armature", type="ARMATURE")
    arm_mod.object = arm

    bpy.context.view_layer.objects.active = clean_mesh
    bpy.ops.object.select_all(action="DESELECT")
    clean_mesh.select_set(True)
    bpy.ops.object.shade_smooth()

    # Renomeia 22 ossos para Mecanim Humanoid
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    renamed = 0
    for eb in arm.data.edit_bones:
        if eb.name in UNIRIG_BIPED_MAP:
            eb.name = UNIRIG_BIPED_MAP[eb.name]
            renamed += 1
    bpy.ops.object.mode_set(mode="OBJECT")

    # Limpeza cirurgica de pesos de ombros/bracos vazados no queixo/cabeca
    arm_limb_groups = {
        "LeftShoulder", "RightShoulder",
        "LeftUpperArm", "RightUpperArm",
        "LeftLowerArm", "RightLowerArm",
        "LeftHand", "RightHand",
    }
    neck_bone = arm.data.bones.get("Neck")
    head_bone = arm.data.bones.get("Head")
    if neck_bone is not None and head_bone is not None:
        neck_z = (arm.matrix_world @ neck_bone.head_local).z
        head_z = (arm.matrix_world @ head_bone.head_local).z
        vg_by_name = {g.name: g for g in clean_mesh.vertex_groups}
        vg_by_idx = {g.index: g.name for g in clean_mesh.vertex_groups}
        vg_head = vg_by_name.get("Head")
        vg_neck = vg_by_name.get("Neck")
        for v in clean_mesh.data.vertices:
            p = clean_mesh.matrix_world @ v.co
            if p.z >= neck_z:
                leaked = 0.0
                to_remove = []
                for g in v.groups:
                    bname = vg_by_idx.get(g.group, "")
                    if bname in arm_limb_groups and g.weight > 0.0:
                        leaked += g.weight
                        to_remove.append(vg_by_name[bname])
                    elif p.z >= (head_z - 0.03) and bname in ("Chest", "UpperChest", "Spine") and g.weight > 0.0:
                        leaked += g.weight
                        to_remove.append(vg_by_name[bname])
                if leaked > 0.0:
                    for vg in to_remove:
                        vg.remove([v.index])
                    target_vg = vg_head if (p.z >= head_z - 0.03 and vg_head is not None) else vg_neck
                    if target_vg is not None:
                        target_vg.add([v.index], leaked, "ADD")

    bpy.context.view_layer.objects.active = clean_mesh
    bpy.ops.object.vertex_group_normalize_all(group_select_mode="ALL", lock_active=False)

    # Ancora as solas das botas exatamente em Z = 0 (Y = 0 no Unity!)
    f_mn, _ = world_bounds(clean_mesh)
    if abs(f_mn.z) > 1e-4:
        arm.location.z -= f_mn.z
        bpy.context.view_layer.update()

    bpy.ops.export_scene.fbx(
        filepath=fbx_out,
        use_selection=False,
        add_leaf_bones=False,
        bake_anim=False,
        path_mode="AUTO",
    )
    print(f"NPC_HUMANOID_OK {slug}: polys={len(clean_mesh.data.polygons)} verts={len(clean_mesh.data.vertices)} renamed={renamed} -> {fbx_out}")


if __name__ == "__main__":
    build_npc(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
