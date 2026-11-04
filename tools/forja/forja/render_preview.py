# render_preview.py — preview padronizado (Blender headless, WSL)
# Câmera e luz FIXAS para todos os casos (comparabilidade da galeria).
# Uso: blender -b -P render_preview.py -- --input mesh.obj --out1 a.png --out2 b.png [--res 640]
#
# Dois ângulos canônicos:
#   A: azimute 35°, elevação 25°   (3/4 frontal)
#   B: azimute 145°, elevação 15°  (3/4 traseira)
# Render: Cycles CPU (determinístico, sem dependência de GL no headless).
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1 :]
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--out1", required=True)
    p.add_argument("--out2", required=True)
    p.add_argument("--res", type=int, default=640)
    p.add_argument("--samples", type=int, default=32)
    return p.parse_args(argv)


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_mesh(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    elif ext in (".glb", ".gltf"):
        bpy.ops.wm.gltf_import(filepath=path)
    elif ext == ".stl":
        bpy.ops.wm.stl_import(filepath=path)
    elif ext == ".ply":
        bpy.ops.wm.ply_import(filepath=path)
    else:
        raise ValueError(f"formato nao suportado: {ext}")
    objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not objs:
        raise RuntimeError("nenhum mesh importado")
    return objs


def normalize(objs):
    # junta, centraliza na origem, apoia no plano XZ(Y-up do blender? não — Z-up):
    # Blender é Z-up: base em Z=0, centro em XY=0, maior dimensão = 1.6 m
    import bpy

    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # material cinza neutro (mesh gerada não tem material)
    mat = bpy.data.materials.new("preview_gray")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.75, 0.75, 0.78, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.55
    if obj.data.materials:
        obj.data.materials.clear()
    obj.data.materials.append(mat)
    for poly in obj.data.polygons:
        poly.use_smooth = True

    # normalização de escala/posição
    dim = max(obj.dimensions)
    scale = 1.6 / dim if dim > 0 else 1.0
    obj.scale = (scale, scale, scale)
    bpy.ops.object.transform_apply(scale=True)
    local_center = (obj.matrix_world @ Vector(obj.bound_box[6]) + obj.matrix_world @ Vector(obj.bound_box[0])) / 2
    zmin = min((obj.matrix_world @ Vector(c)).z for c in obj.bound_box)
    obj.location = (
        obj.location.x - local_center.x,
        obj.location.y - local_center.y,
        obj.location.z - zmin,
    )
    bpy.context.view_layer.update()
    return obj


def add_camera_light():
    # Alvo fixo: centro da peça normalizada ~ (0, 0, 0.8)
    target = Vector((0.0, 0.0, 0.8))

    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = 50
    cam = bpy.data.objects.new("cam", cam_data)
    bpy.context.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    empty = bpy.data.objects.new("target", None)
    empty.location = target
    bpy.context.collection.objects.link(empty)

    con = cam.constraints.new(type="TRACK_TO")
    con.target = empty

    sun_data = bpy.data.lights.new("sun", type="SUN")
    sun_data.energy = 3.0
    sun = bpy.data.objects.new("sun", sun_data)
    sun.location = (4.0, -3.0, 6.0)
    sun.rotation_euler = (math.radians(45), math.radians(15), math.radians(30))
    bpy.context.collection.objects.link(sun)

    bpy.context.scene.world = bpy.data.worlds.new("w")
    bpy.context.scene.world.use_nodes = True
    bg = bpy.context.scene.world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.04, 0.04, 0.05, 1.0)
    return cam


def place_camera(cam, azim_deg, elev_deg, radius=3.4):
    target = Vector((0.0, 0.0, 0.8))
    az = math.radians(azim_deg)
    el = math.radians(elev_deg)
    loc = target + radius * Vector(
        (math.cos(el) * math.sin(az), -math.cos(el) * math.cos(az), math.sin(el))
    )
    cam.location = loc


def setup_render(res, samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.film_transparent = False


def main():
    a = parse_args()
    clear_scene()
    objs = import_mesh(a.input)
    normalize(objs)
    cam = add_camera_light()
    setup_render(a.res, a.samples)

    for azim, elev, out in ((35, 25, a.out1), (145, 15, a.out2)):
        place_camera(cam, azim, elev)
        bpy.context.scene.render.filepath = out
        bpy.ops.render.render(write_still=True)
        print(f"RENDER_OK {out}")


main()
