#!/usr/bin/env python3
"""Jubarte B2 — Passo 1: 2 execuções TRELLIS (seeds 42 e 777)."""
import datetime
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.expanduser("~/printer3d-work/gen"))
from trellis_plugin import TrellisGenerator  # noqa: E402

REF = os.path.expanduser("~/printer3d-work/inputs/jubarte_b2.png")
OUT = os.path.expanduser("~/printer3d-work/jubarte_b2")
SEEDS = [42, 777]


def vram_free() -> int:
    r = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                       capture_output=True, text=True, timeout=30)
    return int(r.stdout.strip())


exp = {"ts": datetime.datetime.now().isoformat(timespec="seconds"),
       "input": "inputs/jubarte_b2.png", "rodadas": []}

gen = TrellisGenerator()
gen.prepare()
for seed in SEEDS:
    livre = vram_free()
    print(f"[b2] seed {seed}: VRAM livre {livre} MiB (guard confirma antes de rodar)")
    outdir = os.path.join(OUT, f"trellis_{seed}")
    rep = gen.generate(REF, outdir, {"seed": seed}).to_dict()
    ok = os.path.isfile(os.path.join(outdir, "mesh.obj"))
    exp["rodadas"].append({
        "candidato": f"cand_{seed}", "seed": seed, "vram_antes_mib": livre,
        "mesh_ok": ok, "tempo_s": rep.get("tempo_s"),
        "vram_pico_mib": rep.get("vram_pico_mib"),
        "vertices": rep.get("vertices"), "faces": rep.get("faces"),
        "erros": [str(e)[:150] for e in (rep.get("erros") or [])][:2],
    })
    print(f"[b2] seed {seed}: ok={ok} t={rep.get('tempo_s')}s "
          f"vram={rep.get('vram_pico_mib')} verts={rep.get('vertices')}")
    # confirmação de liberação entre execuções
    print(f"[b2] VRAM pós-run: {vram_free()} MiB")

with open(os.path.join(OUT, "experimento_jubarte.json"), "w") as f:
    json.dump(exp, f, indent=1, ensure_ascii=False)
oks = sum(1 for r in exp["rodadas"] if r["mesh_ok"])
print(f"B2_TRELLIS_FIM {oks}/2 com malha")
