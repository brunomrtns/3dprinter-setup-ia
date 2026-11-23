#!/usr/bin/env bash
set -euo pipefail

REPO="/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia"
EV="$REPO/evidence/z1_workshop"
WORK="$REPO/work/z1_workshop"
BRAIN="/mnt/c/Users/Bruno/.gemini/antigravity/brain/430e8586-6e41-4737-9ee8-884f505b33ac"

mkdir -p "$EV" "$WORK/z1_prop_nave_manutencao" "$WORK/z1_prop_cristal_energia"

# 1. Converte concepts JPG -> PNG limpos
~/.venvs/triposg/bin/python - <<PY
from PIL import Image
Image.open("$BRAIN/concept_nave_manutencao_clean_1795468732334.jpg").convert("RGB").save("$EV/concept_nave_manutencao.png")
Image.open("$BRAIN/concept_cristal_energia_1795468714582.jpg").convert("RGB").save("$EV/concept_cristal_energia.png")
print("CONCEPTS_PNG_OK")
PY

# 2. Gera malhas 3D EXCLUSIVAMENTE via TripoSG!
export TRIPOSG_HOME="$HOME/tools/TripoSG"

echo "=== [1/2] TripoSG: z1_prop_nave_manutencao ==="
~/.venvs/triposg/bin/python "$REPO/tools/generator/triposg_runner.py" \
  --image "$EV/concept_nave_manutencao.png" \
  --output-dir "$WORK/z1_prop_nave_manutencao" \
  --seed 42

echo "=== [2/2] TripoSG: z1_prop_cristal_energia ==="
~/.venvs/triposg/bin/python "$REPO/tools/generator/triposg_runner.py" \
  --image "$EV/concept_cristal_energia.png" \
  --output-dir "$WORK/z1_prop_cristal_energia" \
  --seed 42

# 3. Decima para 30k faces antes do PBR oficial
~/.venvs/triposg/bin/python - <<PY
import trimesh
for slug in ["z1_prop_nave_manutencao", "z1_prop_cristal_energia"]:
    src = f"$WORK/{slug}/mesh.obj"
    dst = f"$WORK/{slug}/mesh_30k.obj"
    m = trimesh.load(src, force="mesh")
    if len(m.faces) > 30000:
        m = m.simplify_quadric_decimation(face_count=30000)
    m.export(dst)
    print(f"DECIMATE_OK {slug}: faces={len(m.faces)} -> {dst}")
PY

# 4. Pipeline PBR oficial (Hunyuan3D-Paint + TRELLIS.2 PBR + pack_glb)
cd "$REPO"

echo "=== [1/2] PBR Oficial: z1_prop_nave_manutencao ==="
/home/bruno/.venvs/hunyuan/bin/python pipeline/run_asset.py \
  --config assets/z1_prop_nave_manutencao.json \
  --out "$WORK/z1_prop_nave_manutencao/pbr_out"

echo "=== [2/2] PBR Oficial: z1_prop_cristal_energia ==="
/home/bruno/.venvs/hunyuan/bin/python pipeline/run_asset.py \
  --config assets/z1_prop_cristal_energia.json \
  --out "$WORK/z1_prop_cristal_energia/pbr_out"

echo "ALL_Z1_WORKSHOP_TRIPOSG_PBR_DONE"
