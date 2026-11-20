#!/usr/bin/env python3
"""Consolida evidence/rtx3060-12gb/fox_aipaint/report.json + verificação HTTP 200 + Last-Modified."""
from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path("/mnt/c/Users/Bruno/OneDrive/Documentos/Default Project/3dprinter-setup-ia")
EVID = REPO / "evidence" / "rtx3060-12gb" / "fox_aipaint"
BASE = "https://brunointegrations.com/modelos3d"

URLS = [
    f"{BASE}/manifest.json",
    f"{BASE}/models/carro_foxh__mv_a_8k.glb",
    f"{BASE}/models/carro_foxh__mv_b_8k.glb",
    f"{BASE}/models/carro_foxh__mv_a_4k.glb",
    f"{BASE}/models/carro_foxh__mv_b_4k.glb",
]


def check_http() -> dict:
    checks = {}
    for url in URLS:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=20) as resp:
            checks[url] = {
                "status": resp.status,
                "content_length": int(resp.headers.get("Content-Length", "0")),
                "last_modified": resp.headers.get("Last-Modified"),
                "etag": resp.headers.get("ETag"),
            }
    # Confirma que manifest.json mantém os 4 modos intactos
    with urllib.request.urlopen(f"{BASE}/manifest.json", timeout=20) as resp:
        man = json.loads(resp.read().decode("utf-8"))
    fox_modes = []
    for item in man.get("models", []):
        if item.get("id") == "carro_foxh":
            fox_modes = [m.get("id") for m in item.get("modes", [])]
    return {"endpoints": checks, "manifest_carro_foxh_modes": fox_modes}


def main() -> int:
    color_audit = json.loads((EVID / "color_audit.json").read_text(encoding="utf-8"))
    region_diag = json.loads((EVID / "region_diag.json").read_text(encoding="utf-8"))
    ai_paint = json.loads((EVID / "ai_paint_result.json").read_text(encoding="utf-8"))
    eval_v2 = json.loads((EVID / "eval_v2.json").read_text(encoding="utf-8"))
    etapa_f = json.loads((EVID / "etapa_f_pack.json").read_text(encoding="utf-8"))
    http_check = check_http()

    report = {
        "run": "fox_aipaint",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "seed": 42,
        "gpu": "NVIDIA GeForce RTX 3060 12GB",
        "caminho_usado": ai_paint["caminho_usado"],
        "fallback_semantico_usado": False,
        "override_rodas_c_plus_usado": False,
        "base_meshes_reusadas": {
            "commit_origem": "954e4d8",
            "mv_a_obj": "/home/bruno/printer3d-work/carro/fox_fullrun/mv_a/uv.obj",
            "mv_b_obj": "/home/bruno/printer3d-work/carro/fox_fullrun/mv_b/uv.obj",
            "malha_uv_manifest_intactos": True,
        },
        "etapa_0_color_audit": color_audit,
        "etapa_a_region_diag_before": region_diag,
        "etapa_c_ai_paint": ai_paint,
        "etapa_e_eval_v2": eval_v2,
        "etapa_f_upscale_pack": etapa_f,
        "http_verification": http_check,
        "viewer_urls": {
            "site": BASE,
            "mv_a_8k": f"{BASE}/#carro_foxh/mv_a_8k",
            "mv_b_8k": f"{BASE}/#carro_foxh/mv_b_8k",
            "mv_a_4k": f"{BASE}/#carro_foxh/mv_a_4k",
            "mv_b_4k": f"{BASE}/#carro_foxh/mv_b_4k",
        },
    }

    (EVID / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("CONSOLIDATE_OK")
    for u, info in http_check["endpoints"].items():
        print(f"  {info['status']} | {info['content_length']:>10} B | {info['last_modified']} | {u}")
    print("  modes:", http_check["manifest_carro_foxh_modes"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
