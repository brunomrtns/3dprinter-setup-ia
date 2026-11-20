#!/usr/bin/env python3
"""Universal Asset Config Loader, Schema Validator & UV Pre-Flight Checker."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import trimesh

DEFAULTS_PATH = Path(__file__).resolve().parent / "defaults.json"
VALID_TIERS = {"photos", "single", "none"}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_asset_config(config_path: str | Path) -> dict[str, Any]:
    """Loads pipeline/defaults.json merged with assets/<id>.json and validates schema."""
    defaults = json.loads(DEFAULTS_PATH.read_text(encoding="utf-8"))
    user_cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))

    required_keys = ["id", "mesh", "tier", "outputs"]
    for rk in required_keys:
        if rk not in user_cfg:
            raise ValueError(f"Asset config missing required key '{rk}': {config_path}")

    tier = user_cfg["tier"]
    if tier not in VALID_TIERS:
        raise ValueError(f"Invalid tier '{tier}', expected one of {sorted(VALID_TIERS)}")

    merged = deep_merge(defaults, user_cfg)
    merged.setdefault("uv", user_cfg.get("mesh"))
    merged.setdefault("input_images", [])
    merged.setdefault("notes", "")
    merged["_config_path"] = str(Path(config_path).resolve())

    # Deterministic config hash for --resume
    canonical = json.dumps(
        {k: v for k, v in merged.items() if not k.startswith("_")},
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")
    merged["_config_hash"] = hashlib.sha256(canonical).hexdigest()[:16]
    return merged


def uv_preflight(mesh_path: str | Path, tex_res: int = 1024) -> dict[str, Any]:
    """Generic UV pre-flight check before spending GPU: island count, min area, overlap %, warnings."""
    mesh = trimesh.load(str(mesh_path), force="mesh", process=False)
    verts = int(len(mesh.vertices))
    faces = int(len(mesh.faces))
    uv = getattr(mesh.visual, "uv", None)

    if uv is None or len(uv) != verts:
        return {
            "has_uv": False,
            "verts": verts,
            "faces": faces,
            "num_islands": 0,
            "min_island_area_px": 0,
            "uv_utilization_pct": 0.0,
            "overlap_pct": 0.0,
            "warning": "Malha de entrada sem UV — será necessário unwrap xatlas (preservando geometria).",
        }

    uv_arr = np.asarray(uv, dtype=np.float32)
    uv_px = np.empty_like(uv_arr)
    uv_px[:, 0] = np.clip(uv_arr[:, 0], 0.0, 1.0) * (tex_res - 1)
    uv_px[:, 1] = (1.0 - np.clip(uv_arr[:, 1], 0.0, 1.0)) * (tex_res - 1)
    tris = np.round(uv_px[np.asarray(mesh.faces, dtype=np.int32)]).astype(np.int32)

    cov = np.zeros((tex_res, tex_res), dtype=np.uint8)
    hit_count = np.zeros((tex_res, tex_res), dtype=np.int32)
    # Fast rasterization for island & overlap estimation
    for tri in tris:
        x0, y0 = int(tri[:, 0].min()), int(tri[:, 1].min())
        x1, y1 = int(tri[:, 0].max()), int(tri[:, 1].max())
        if x1 <= x0 and y1 <= y0:
            cov[y0, x0] = 255
            hit_count[y0, x0] += 1
            continue
        roi_w, roi_h = x1 - x0 + 1, y1 - y0 + 1
        local = tri - np.array([x0, y0], dtype=np.int32)
        tmp = np.zeros((roi_h, roi_w), dtype=np.uint8)
        cv2.fillConvexPoly(tmp, local, 1)
        cov[y0 : y1 + 1, x0 : x1 + 1][tmp > 0] = 255
        hit_count[y0 : y1 + 1, x0 : x1 + 1] += tmp

    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(cov, connectivity=4)
    num_islands = max(0, int(num_labels) - 1)
    areas = [int(stats[i, cv2.CC_STAT_AREA]) for i in range(1, num_labels)]
    min_area = min(areas) if areas else 0
    covered_px = int((cov > 0).sum())
    # Edge-sharing adjacent triangles hit boundary pixels twice; >= 3 hits indicates real UV overlap
    overlap_px = int((hit_count > 2).sum())
    util_pct = round(covered_px / float(tex_res * tex_res) * 100.0, 2)
    overlap_pct = round(overlap_px / max(1, covered_px) * 100.0, 2)

    warnings = []
    if num_islands > 2500 or min_area <= 1:
        warnings.append("UV muito fragmentado (ilhas mínimas <= 1px) — qualidade de pintura limitada por UV.")
    if overlap_pct > 5.0:
        warnings.append(f"UV com sobreposição alta ({overlap_pct}%) — qualidade de pintura limitada por UV.")
    if util_pct < 25.0:
        warnings.append(f"Baixa utilização do atlas UV ({util_pct}%) — qualidade de pintura limitada por UV.")

    return {
        "has_uv": True,
        "verts": verts,
        "faces": faces,
        "num_islands": num_islands,
        "min_island_area_px": min_area,
        "uv_utilization_pct": util_pct,
        "overlap_pct": overlap_pct,
        "warning": " | ".join(warnings) if warnings else None,
    }


if __name__ == "__main__":
    import sys

    cfg = load_asset_config(sys.argv[1])
    print("CONFIG_OK:", cfg["id"], "tier=", cfg["tier"], "hash=", cfg["_config_hash"])
    print("UV_PREFLIGHT:", json.dumps(uv_preflight(cfg["uv"]), ensure_ascii=False))
