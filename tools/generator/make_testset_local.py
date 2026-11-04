# make_testset_local.py — 3 imagens de teste procedurais (CC0) via Blender headless
# Objetos: caneca (mug), engrenagem (gear), gancho de parede (hook)
# Mesma linguagem visual das imagens de repo: objeto isolado, fundo claro limpo.
# Uso: blender -b -P make_testset_local.py -- --outdir <dir>
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1 :]
    p = argparse.ArgumentParser()
    p.add_argument("--outdir", required=True)
    p.add_argument("--res", type=int, default=800)
    return p.parse_args(argv)


def clear():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mat(name, color, rough=0.5, metallic=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    return m


def boolean(target, tool, op):
    m = target.modifiers.new("b", "BOOLEAN")
    m.operation = op
    m.object = tool
    m.solver = "EXACT"
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(tool, do_unlink=True)


def cylinder(name, r, depth, loc=(0, 0, 0), rot=(0, 0, 0), seg=64):
    bpy.ops.mesh.primitive_cylinder_add(vertices=seg, radius=r, depth=depth, location=loc, rotation=rot)
    o = bpy.context.active_object
    o.name = name
    return o


def build_mug():
    body = cylinder("body", 0.5, 1.0)
    body.location = (0, 0, 0.5)
    inner = cylinder("inner", 0.42, 1.2, loc=(0, 0, 0.9))
    boolean(body, inner, "DIFFERENCE")
    bpy.ops.mesh.primitive_torus_add(major_radius=0.34, minor_radius=0.08, location=(0.52, 0, 0.5), rotation=(math.pi / 2, 0, 0))
    handle = bpy.context.active_object
    boolean(body, handle, "UNION")
    s = body.modifiers.new("s", "SUBSURF")
    s.levels = 2
    bpy.ops.object.modifier_apply(modifier=s.name)
    body.data.materials.append(mat("mug", (0.85, 0.35, 0.15), rough=0.4))
    return body


def build_gear():
    gear = cylinder("gear", 0.85, 0.3, seg=96)
    gear.location = (0, 0, 0.15)
    tooth_template = None
    for i in range(16):
        ang = i * 2 * math.pi / 16
        bpy.ops.mesh.primitive_cube_add(size=0.28, location=(math.cos(ang) * 0.88, math.sin(ang) * 0.88, 0.15), rotation=(0, 0, ang))
        t = bpy.context.active_object
        t.scale = (0.6, 1.0, 0.52)
        bpy.ops.object.transform_apply(scale=True)
        if tooth_template is None:
            tooth_template = t
            continue
        boolean(gear, t, "UNION")
    boolean(gear, tooth_template, "UNION")
    hole = cylinder("hole", 0.22, 0.6, loc=(0, 0, 0.15))
    boolean(gear, hole, "DIFFERENCE")
    gear.data.materials.append(mat("gear", (0.72, 0.73, 0.76), rough=0.35, metallic=0.6))
    return gear


def build_hook():
    base = bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0.25, 1.0))
    base_o = bpy.context.active_object
    base_o.scale = (0.5, 0.08, 0.75)
    bpy.ops.object.transform_apply(scale=True)
    arm = cylinder("arm", 0.07, 0.8, loc=(0, -0.05, 0.65))
    boolean(base_o, arm, "UNION")
    bpy.ops.mesh.primitive_torus_add(major_radius=0.22, minor_radius=0.07, location=(0, -0.05, 0.28), rotation=(0, 0, 0))
    tor = bpy.context.active_object
    boolean(base_o, tor, "UNION")
    wall = bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0.5, 0))
    base_o.data.materials.append(mat("hook", (0.2, 0.55, 0.8), rough=0.45))
    return base_o


BUILDERS = {"caneca": build_mug, "engrenagem": build_gear, "gancho": build_hook}


def setup_render(res):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24
    sc.cycles.use_denoising = True
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    w = bpy.data.worlds.new("w")
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.93, 0.93, 0.94, 1.0)
    bg.inputs[1].default_value = 1.0
    sc.world = w


def shoot(obj):
    dim = max(obj.dimensions)
    obj.location = (-obj.location.x, -obj.location.y, -obj.location.z)
    bpy.context.view_layer.update()
    sc = bpy.context.scene
    cam_data = bpy.data.cameras.new("c")
    cam_data.lens = 60
    cam = bpy.data.objects.new("c", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    d = dim * 2.1 + 0.5
    cam.location = (d * 0.55, -d * 0.9, dim * 0.45)
    con = cam.constraints.new("TRACK_TO")
    con.target = obj
    sun = bpy.data.lights.new("s", type="SUN")
    sun.energy = 3.0
    so = bpy.data.objects.new("s", sun)
    so.location = (4, -2, 6)
    so.rotation_euler = (math.radians(50), math.radians(10), math.radians(20))
    sc.collection.objects.link(so)


def main():
    a = parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    for name, build in BUILDERS.items():
        clear()
        obj = build()
        setup_render(a.res)
        shoot(obj)
        out = os.path.join(a.outdir, f"local_{name}.png")
        bpy.context.scene.render.filepath = out
        bpy.ops.render.render(write_still=True)
        print(f"LOCAL_TESTSET_OK {out}")


main()
