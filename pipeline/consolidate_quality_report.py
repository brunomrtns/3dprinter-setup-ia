#!/usr/bin/env python3
"""Consolida evidence/rtx3060-12gb/fox_quality/report.json + verificação HTTP 200 + Last-Modified."""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

EVID = Path("/mnt/c/Users/Bruno/OneDrive/Documentos/Default Project/3dprinter-setup-ia/evidence/rtx3060-12gb/fox_quality")
BASE = "https://brunointegrations.com/modelos3d"

URLS = [
    f"{BASE}/manifest.json",
    f"{BASE}/models/carro_foxh__mv_a_8k.glb",
    f"{BASE}/models/carro_foxh__mv_b_8k.glb",
    f"{BASE}/models/carro_foxh__mv_a_4k.glb",
    f"{BASE}/models/carro_foxh__mv_b_4k.glb",
]


def check_http() -> dict:
    endpoints = {}
    for url in URLS:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=20) as resp:
            endpoints[url] = {
                "status": resp.status,
                "content_length": int(resp.headers.get("Content-Length", "0")),
                "last_modified": resp.headers.get("Last-Modified"),
                "etag": resp.headers.get("ETag"),
            }
    return endpoints


def main() -> int:
    stage_a = json.loads((EVID / "stage_a_hunyuan.json").read_text(encoding="utf-8"))
    stage_b_front = json.loads((EVID / "stage_b_trellis2_front.json").read_text(encoding="utf-8"))
    stage_b_34 = json.loads((EVID / "stage_b_trellis2_34.json").read_text(encoding="utf-8"))
    stage_c_hy = json.loads((EVID / "stage_c_patch_repair_hunyuan.json").read_text(encoding="utf-8"))
    stage_c_t2 = json.loads((EVID / "stage_c_patch_repair.json").read_text(encoding="utf-8"))
    stage_d_hy = json.loads((EVID / "stage_d_eval_hunyuan2048.json").read_text(encoding="utf-8"))
    stage_d_t2 = json.loads((EVID / "stage_d_eval_final.json").read_text(encoding="utf-8"))
    stage_e = json.loads((EVID / "stage_e_pack.json").read_text(encoding="utf-8"))
    http_ep = check_http()

    report = {
        "run": "fox_quality",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "seed": 42,
        "gpu": "NVIDIA GeForce RTX 3060 12GB",
        "winner_architecture": "Hybrid Universal PBR: BaseColor (Hunyuan3D-Paint v2-0 native 2048 + per-view Real-ESRGAN x4 SR + generic patch_repair) + MetallicRoughness PBR 2048 PNG (TRELLIS.2-4B TexturingPipeline 1024^3 cond=three_quarter, same UV layout)",
        "pbr_included": True,
        "generic_pipeline_scripts": [
            "pipeline/paint_quality.py",
            "pipeline/retexture_trellis.py",
            "pipeline/patch_repair.py",
            "pipeline/eval_texture.py",
            "pipeline/pack_glb.py",
        ],
        "asset_config": "cars/fox.json",
        "genericity_debt": False,
        "backup_prev_dir": str(EVID / "backup_prev"),
        "viewer_version": "v19 (PBR preserved when metallicRoughnessTexture present; MeshPhysicalMaterial clearcoat 0.4 + RoomEnvironment for albedo-only; NoToneMapping + SRGBColorSpace)",
        "stage_a_hunyuan_2048": stage_a,
        "stage_b_trellis2_pbr_front": stage_b_front,
        "stage_b_trellis2_pbr_three_quarter": stage_b_34,
        "stage_c_patch_repair_winner_basecolor": stage_c_hy,
        "stage_c_patch_repair_trellis2": stage_c_t2,
        "stage_d_eval_winner_basecolor": stage_d_hy,
        "stage_d_eval_trellis2": stage_d_t2,
        "stage_e_pack_glb": stage_e,
        "http_verification": http_ep,
        "viewer_urls": {
            "mv_b_8k": f"{BASE}/?case=carro_foxh&mode=mv_b_8k",
            "mv_a_8k": f"{BASE}/?case=carro_foxh&mode=mv_a_8k",
            "vs_8k": f"{BASE}/?case=carro_foxh&mode=mv_b_8k&vs=1&mode2=mv_a_8k",
            "mv_b_4k": f"{BASE}/?case=carro_foxh&mode=mv_b_4k",
            "mv_a_4k": f"{BASE}/?case=carro_foxh&mode=mv_a_4k",
        },
    }

    (EVID / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("CONSOLIDATE_QUALITY_OK")
    for u, info in http_ep.items():
        print(f"  {info['status']} | {info['content_length']:>10} B | {info['last_modified']} | {u}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
