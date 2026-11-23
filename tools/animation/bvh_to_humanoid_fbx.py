#!/usr/bin/env python3
"""
tools/animation/bvh_to_humanoid_fbx.py — Converte BVH do MoMask (20 fps, foot-IK) para FBX Unity Humanoid (60 fps).
Executar via ~/.venvs/unirig/bin/python (bpy headless).
"""
from __future__ import annotations

import argparse
import bpy


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Caminho .bvh de entrada")
    ap.add_argument("--output", required=True, help="Caminho .fbx de saida")
    ap.add_argument("--target-fps", type=int, default=60)
    ap.add_argument("--src-fps", type=int, default=20)
    ap.add_argument("--in-place", action="store_true", help="Remove deslocamento XZ da raiz mantendo bounce vertical Y")
    ap.add_argument("--clip-name", default="MoMaskClip")
    args = ap.parse_args()

    bpy.ops.wm.read_homefile(use_empty=True)
    bpy.context.scene.render.fps = args.target_fps

    # Importa BVH (eixo Y-up nativo do MoMask -> Blender Z-up automatico, escala 1:1 metros)
    bpy.ops.import_anim.bvh(
        filepath=args.input,
        axis_forward="-Z",
        axis_up="Y",
        global_scale=1.0,
        frame_start=1,
        use_fps_scale=False,
        update_scene_fps=False,
        update_scene_duration=True,
    )

    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if not arms:
        raise RuntimeError("Nenhuma Armature importada do BVH.")
    arm = arms[0]
    arm.name = "Armature"

    action = arm.animation_data.action if (arm.animation_data and arm.animation_data.action) else None
    if action is None:
        raise RuntimeError("Nenhuma Action encontrada no BVH importado.")
    action.name = args.clip_name

    # Re-amostra keyframes de src_fps (20) para target_fps (60) com interpolacao BEZIER suave
    scale_t = float(args.target_fps) / float(args.src_fps)
    f_min, f_max = action.frame_range

    for fc in action.fcurves:
        # Se --in-place: trava X e Y (horizontal no espaco local da Armature/Hips; Z ou Y dependendo do canal)
        # No BVH importado pelo Blender, Hips location: index 0 = X (lateral), index 1 = Y (vertical), index 2 = Z (frente)
        is_hips_loc = (fc.data_path == 'pose.bones["Hips"].location')
        base_val = fc.keyframe_points[0].co[1] if len(fc.keyframe_points) > 0 else 0.0
        for kp in fc.keyframe_points:
            kp.co[0] = (kp.co[0] - 1.0) * scale_t + 1.0
            if args.in_place and is_hips_loc and fc.array_index in (0, 2):
                kp.co[1] = base_val
            kp.interpolation = "BEZIER"
            kp.handle_left_type = "AUTO_CLAMPED"
            kp.handle_right_type = "AUTO_CLAMPED"
        fc.update()

    new_end = int(round((f_max - 1.0) * scale_t + 1.0))
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = max(2, new_end)

    bpy.ops.export_scene.fbx(
        filepath=args.output,
        use_selection=False,
        object_types={"ARMATURE"},
        use_armature_deform_only=False,
        add_leaf_bones=False,
        bake_anim=True,
        bake_anim_use_all_bones=True,
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False,
        bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0,
        axis_forward="-Z",
        axis_up="Y",
    )
    print(f"[bvh_to_humanoid_fbx] OK: frames=1..{new_end} @ {args.target_fps}fps | in_place={args.in_place} | out={args.output}")


if __name__ == "__main__":
    main()
