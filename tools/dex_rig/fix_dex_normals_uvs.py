#!/usr/bin/env python3
"""Recalcula normais 100% para fora e transfere UVs limpas do hero_dex.fbx original para hero_dex_humanoid.fbx."""
import bpy

fbx_in = "/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Art/Generated/hero_dex/hero_dex_humanoid.fbx"
fbx_uv_src = "/mnt/c/Users/Bruno/workspace/game-concerto/unity/Assets/Game/Art/Generated/hero_dex/hero_dex.fbx"

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

bpy.ops.import_scene.fbx(filepath=fbx_in)
rig_meshes = [o for o in bpy.data.objects if o.type == "MESH"]
target_mesh = rig_meshes[0]

before_objs = set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=fbx_uv_src)
src_objs = [o for o in bpy.data.objects if o not in before_objs and o.type == "MESH"]
src_mesh = src_objs[0]

# Alinha escala/posicao do src_mesh ao target_mesh caso haja diferenca de escala de importacao
print("TARGET_DIMS:", list(target_mesh.dimensions), "SRC_DIMS:", list(src_mesh.dimensions))

bpy.context.view_layer.objects.active = target_mesh
bpy.ops.object.select_all(action="DESELECT")
target_mesh.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode="OBJECT")
bpy.ops.object.shade_smooth()

if len(target_mesh.data.uv_layers) == 0:
    target_mesh.data.uv_layers.new(name="UVMap")
mod = target_mesh.modifiers.new(name="TransferUV", type="DATA_TRANSFER")
mod.object = src_mesh
mod.use_loop_data = True
mod.data_types_loops = {"UV"}
mod.loop_mapping = "POLYINTERP_NEAREST"
bpy.ops.object.modifier_apply(modifier=mod.name)

bpy.data.objects.remove(src_mesh, do_unlink=True)

bpy.ops.export_scene.fbx(
    filepath=fbx_in,
    use_selection=False,
    add_leaf_bones=False,
    bake_anim=False,
    path_mode="AUTO",
)
print("FIXED_NORMALS_AND_UVS_OK:", len(target_mesh.data.polygons), "uv_layers=", len(target_mesh.data.uv_layers))
