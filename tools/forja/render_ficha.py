# render_ficha.py — 3 ângulos da peça para a ficha de review (CPU, preset review)
# Ângulos: A=35/25 frontal · B=145/15 traseira · C=15/75 topo
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1 :]
p = argparse.ArgumentParser()
p.add_argument("--input", required=True)
p.add_argument("--outprefix", required=True)
p.add_argument("--res", type=int, default=512)
a = p.parse_args(argv)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=a.input)
objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
bpy.ops.object.select_all(action="DESELECT")
for o in objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = objs[0]
bpy.ops.object.join()
obj = bpy.context.view_layer.objects.active
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
mat = bpy.data.materials.new("g")
mat.use_nodes = True
b = mat.node_tree.nodes.get("Principled BSDF")
b.inputs["Base Color"].default_value = (0.78, 0.79, 0.82, 1.0)
b.inputs["Roughness"].default_value = 0.5
obj.data.materials.clear()
obj.data.materials.append(mat)
for poly in obj.data.polygons:
    poly.use_smooth = True
dim = max(obj.dimensions)
s = 1.6 / dim if dim > 0 else 1.0
obj.scale = (s, s, s)
bpy.ops.object.transform_apply(scale=True)
c = (obj.matrix_world @ Vector(obj.bound_box[6]) + obj.matrix_world @ Vector(obj.bound_box[0])) / 2
zmin = min((obj.matrix_world @ Vector(v)).z for v in obj.bound_box)
obj.location = (obj.location.x - c.x, obj.location.y - c.y, obj.location.z - zmin)

cam_d = bpy.data.cameras.new("c")
cam_d.lens = 50
cam = bpy.data.objects.new("c", cam_d)
bpy.context.scene.collection.objects.link(cam)
bpy.context.scene.camera = cam
tgt = bpy.data.objects.new("t", None)
tgt.location = (0, 0, 0.8)
bpy.context.scene.collection.objects.link(tgt)
con = cam.constraints.new("TRACK_TO")
con.target = tgt
sun_d = bpy.data.lights.new("s", type="SUN")
sun_d.energy = 3.0
sun = bpy.data.objects.new("s", sun_d)
sun.location = (4, -3, 6)
sun.rotation_euler = (math.radians(45), math.radians(15), math.radians(30))
bpy.context.scene.collection.objects.link(sun)
w = bpy.data.worlds.new("w")
w.use_nodes = True
w.node_tree.nodes.get("Background").inputs[0].default_value = (0.05, 0.05, 0.06, 1.0)
bpy.context.scene.world = w

sc = bpy.context.scene
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = 32
sc.cycles.use_denoising = True
sc.render.resolution_x = a.res
sc.render.resolution_y = a.res

for az, el, suf in ((35, 25, "a"), (145, 15, "b"), (15, 75, "c")):
    azr, elr = math.radians(az), math.radians(el)
    cam.location = Vector((0, 0, 0.8)) + 3.4 * Vector(
        (math.cos(elr) * math.sin(azr), -math.cos(elr) * math.cos(azr), math.sin(elr))
    )
    sc.render.filepath = f"{a.outprefix}_{suf}.png"
    bpy.ops.render.render(write_still=True)
    print(f"FICHA_OK {sc.render.filepath}")
