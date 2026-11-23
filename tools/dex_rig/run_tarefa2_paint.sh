#!/usr/bin/env bash
set -euo pipefail

REPO="/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia"
VRAM_LOG="$REPO/evidence/dex_rig/vram_tarefa2_paint.csv"
echo "ts,used_mib" > "$VRAM_LOG"
( while true; do echo "$(date -Iseconds),$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits)" >> "$VRAM_LOG"; sleep 3; done ) &
VPID=$!
trap 'kill $VPID 2>/dev/null || true' EXIT

echo "=== [2B] Decimate 40k via bpy ==="
/home/bruno/.venvs/unirig/bin/python - <<'PY'
import bpy
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
bpy.ops.wm.obj_import(filepath="/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia/work/dex_rig/cand_a_triposg/mesh.obj")
obj = [o for o in bpy.data.objects if o.type == "MESH"][0]
bpy.context.view_layer.objects.active = obj
mod = obj.modifiers.new(name="Dec", type="DECIMATE")
mod.ratio = 40000.0 / max(1, len(obj.data.polygons))
bpy.ops.object.modifier_apply(modifier=mod.name)
bpy.ops.wm.obj_export(filepath="/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia/work/dex_rig/cand_a_triposg/mesh_40k.obj", export_materials=False)
print("DECIMATE_40K_BPY_OK:", len(obj.data.polygons))
PY

echo "=== [2C] Running official pipeline/run_asset.py (Hunyuan3D-Paint + TRELLIS.2 PBR + pack_glb) ==="
/home/bruno/.venvs/hunyuan/bin/python "$REPO/pipeline/run_asset.py" \
  --config "$REPO/assets/hero_dex.json" \
  --out "$REPO/work/dex_rig/hero_dex_pbr"

PEAK=$(awk -F, 'NR>1 && $2>m {m=$2} END {print m+0}' "$VRAM_LOG")
echo "TAREFA2_PAINT_DONE | PEAK_VRAM_MIB=$PEAK"
