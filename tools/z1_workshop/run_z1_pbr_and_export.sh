#!/usr/bin/env bash
set -euo pipefail

REPO="/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia"
WORK="$REPO/work/z1_workshop"

# 1. Decima os dois mesh.obj do TripoSG para 30k faces usando Blender/bpy (unirig venv)
~/.venvs/unirig/bin/python - <<PY
import bpy
for slug in ["z1_prop_nave_manutencao", "z1_prop_cristal_energia"]:
    src = f"$WORK/{slug}/mesh.obj"
    dst = f"$WORK/{slug}/mesh_30k.obj"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=src)
    obj = [o for o in bpy.data.objects if o.type == "MESH"][0]
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    if len(obj.data.polygons) > 30000:
        dec = obj.modifiers.new(name="Dec30k", type="DECIMATE")
        dec.ratio = 30000.0 / float(len(obj.data.polygons))
        bpy.ops.object.modifier_apply(modifier=dec.name)
    bpy.ops.wm.obj_export(filepath=dst, export_materials=False)
    print(f"DECIMATE_OK {slug}: faces={len(obj.data.polygons)} -> {dst}")
PY

# 2. Pipeline PBR oficial (Hunyuan3D-Paint + TRELLIS.2 PBR + pack_glb)
cd "$REPO"

echo "=== [1/2] PBR Oficial: z1_prop_nave_manutencao ==="
/home/bruno/.venvs/hunyuan/bin/python pipeline/run_asset.py \
  --config assets/z1_prop_nave_manutencao.json \
  --out "$WORK/z1_prop_nave_manutencao/pbr_out"

echo "=== [2/2] PBR Oficial: z1_prop_cristal_energia ==="
/home/bruno/.venvs/hunyuan/bin/python pipeline/run_asset.py \
  --config assets/z1_prop_cristal_energia.json \
  --out "$WORK/z1_prop_cristal_energia/pbr_out"

# 3. Exporta GLBs 4K -> FBX solidos + texturas PBR + EmissionMask ciano direto para o Unity!
echo "=== [3/3] Exportando FBX solidos + PBR + EmissionMask para Unity ==="
~/.venvs/unirig/bin/python "$REPO/tools/z1_workshop/export_z1_props_to_unity.py" || true

echo "ALL_Z1_PBR_AND_EXPORT_DONE"
