# blender_mod.py — remesh voxel e/ou decimação via Blender headless (CPU puro)
import argparse
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1 :]
p = argparse.ArgumentParser()
p.add_argument("--input", required=True)
p.add_argument("--output", required=True)
p.add_argument("--voxel", type=float, default=None)
p.add_argument("--max-tris", type=int, default=None)
a = p.parse_args(argv)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=a.input)
obj = next(o for o in bpy.context.scene.objects if o.type == "MESH")

if a.voxel is not None:
    md = obj.modifiers.new("remesh", "REMESH")
    md.mode = "VOXEL"
    md.voxel_size = a.voxel
    md.adaptivity = 0.0
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=md.name)

if a.max_tris is not None:
    atual = len(obj.data.polygons)
    if atual > a.max_tris:
        md = obj.modifiers.new("dec", "DECIMATE")
        md.ratio = max(0.01, a.max_tris / atual)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=md.name)

bpy.ops.wm.obj_export(filepath=a.output)
print(f"BLENDER_MOD_OK tris={len(obj.data.polygons)}")
