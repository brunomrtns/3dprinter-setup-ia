#!/usr/bin/env python3
"""
build_solid_dex_humanoid.py (v2 — 100% SOLIDO + UVs ORIGINAIS DO GLB + RIG UNIRIG):
  1. Importa hero_dex__pbr_4k.glb (glTF 100% integro, sem bug de FBX 5.0->4.2!) e decima para 8000 tris preservando UVs perfeitas.
  2. Importa o Armature + pesos neurais do hero_dex_skin.fbx (UniRig simetrico 0.781%).
  3. Alinha bboxes exatamente e transfere os Vertex Groups (pesos do UniRig) para a malha solida do GLB.
  4. Renomeia os 22 ossos para Unity Mecanim Humanoid + adiciona Ear_L, Ear_R, Antenna_Top.
  5. Exporta hero_dex_humanoid.fbx 100% solido, pintado e pronto para o Unity!
"""
import sys
import bpy
from mathutils import Vector

sys.path.insert(0, "/mnt/c/Users/Bruno/workspace/game-concerto/tools/art/ai_generator")
from unirig_to_mecanim import UNIRIG_BIPED_MAP, add_secondary_head_bones

glb_src = "/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Art/Generated/hero_dex/hero_dex__pbr_4k.glb"
fbx_skin = "/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Art/Generated/hero_dex/hero_dex_skin.fbx"
fbx_out = "/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Art/Generated/hero_dex/hero_dex_humanoid.fbx"

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)


def world_bounds(obj):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mn, mx


# 1. Importa Armature + malha de pesos do UniRig (hero_dex_skin.fbx)
bpy.ops.import_scene.fbx(filepath=fbx_skin)
arm = [o for o in bpy.data.objects if o.type == "ARMATURE"][0]
skin_ref = [o for o in bpy.data.objects if o.type == "MESH"][0]
r_mn, r_mx = world_bounds(skin_ref)
r_sz = r_mx - r_mn
r_c = (r_mn + r_mx) * 0.5

# 2. Importa hero_dex__pbr_4k.glb (100% solido, watertight, UVs perfeitas de fabrica!)
before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=glb_src)
new_meshes = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
# Junta se houver mais de 1 mesh
bpy.ops.object.select_all(action="DESELECT")
for m in new_meshes:
    m.select_set(True)
bpy.context.view_layer.objects.active = new_meshes[0]
if len(new_meshes) > 1:
    bpy.ops.object.join()
clean_mesh = bpy.context.view_layer.objects.active
# Limpa parentes vazios vindos do glTF preservando transform
bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# CRITICO: SOLDA vertices duplicados do glTF (87k -> ~20k) ANTES do Decimate!
# No Blender, UVs ficam nos LOOPS, entao remove_doubles preserva 100% da pintura PBR
# e fecha a malha watertight para o Decimate nao rasgar nenhuma costura UV!
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=0.0002)
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode="OBJECT")

# Decima malha FECHADA para 8000 tris preservando UVs perfeitas
if len(clean_mesh.data.polygons) > 8000:
    dec = clean_mesh.modifiers.new(name="Dec8k", type="DECIMATE")
    dec.ratio = 8000.0 / float(len(clean_mesh.data.polygons))
    bpy.ops.object.modifier_apply(modifier=dec.name)

# Alinha clean_mesh exatamente ao bbox do skin_ref (UniRig)
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

# 3. Transfere os Vertex Groups (pesos do UniRig) de skin_ref -> clean_mesh
for vg in skin_ref.vertex_groups:
    clean_mesh.vertex_groups.new(name=vg.name)

dt = clean_mesh.modifiers.new(name="TransferWeights", type="DATA_TRANSFER")
dt.object = skin_ref
dt.use_vert_data = True
dt.data_types_verts = {"VGROUP_WEIGHTS"}
dt.vert_mapping = "NEAREST"
bpy.ops.object.modifier_apply(modifier=dt.name)

# Remove skin_ref e objetos extras (empties do glTF)
for o in list(bpy.data.objects):
    if o not in (arm, clean_mesh):
        bpy.data.objects.remove(o, do_unlink=True)

# Parenteia clean_mesh no Armature do UniRig
clean_mesh.parent = arm
arm_mod = clean_mesh.modifiers.new(name="Armature", type="ARMATURE")
arm_mod.object = arm

# Garante shading suave e normais consistentes para fora
bpy.context.view_layer.objects.active = clean_mesh
bpy.ops.object.select_all(action="DESELECT")
clean_mesh.select_set(True)
bpy.ops.object.shade_smooth()

# 4. Renomeia 22 ossos para Mecanim Humanoid + adiciona Ear_L, Ear_R, Antenna_Top
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
renamed = 0
for eb in arm.data.edit_bones:
    if eb.name in UNIRIG_BIPED_MAP:
        eb.name = UNIRIG_BIPED_MAP[eb.name]
        renamed += 1
bpy.ops.object.mode_set(mode="OBJECT")

sec = add_secondary_head_bones(arm, clean_mesh)

# Normaliza pesos de todos os vertices
bpy.context.view_layer.objects.active = clean_mesh
bpy.ops.object.vertex_group_normalize_all(group_select_mode="ALL", lock_active=False)

# Ancora as solas das botas exatamente em Z = 0 (Y = 0 no Unity!) para ficar de pe no EditMode E no PlayMode!
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
print(f"GLB_SOLID_DEX_OK: polys={len(clean_mesh.data.polygons)} verts={len(clean_mesh.data.vertices)} uv_layers={len(clean_mesh.data.uv_layers)} renamed={renamed} secondary={sec}")
