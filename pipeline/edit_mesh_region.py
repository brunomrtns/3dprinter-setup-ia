#!/usr/bin/env python3
"""Generic proportional region sculpture for GLB meshes (preserves 100% UVs, PBR textures & materials).

Modifies ONLY the POSITION accessor bytes in-place inside the GLB binary chunk (and updates
accessor min/max bounds), keeping all embedded 8K/4K JPEG BaseColor and PNG MetallicRoughness
textures untouched without recompression.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
import numpy as np


def _read_glb(path: Path) -> tuple[dict, bytes]:
    raw = path.read_bytes()
    magic, version, length = struct.unpack_from("<4sII", raw, 0)
    if magic != b"glTF":
        raise ValueError(f"Not a valid GLB file: {path}")
    off = 12
    json_len, json_type = struct.unpack_from("<II", raw, off)
    off += 8
    gltf = json.loads(raw[off : off + json_len].decode("utf-8"))
    off += json_len
    bin_len, bin_type = struct.unpack_from("<II", raw, off)
    off += 8
    bin_chunk = raw[off : off + bin_len]
    return gltf, bin_chunk


def _write_glb(path: Path, gltf: dict, bin_chunk: bytes) -> None:
    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    while len(json_bytes) % 4 != 0:
        json_bytes += b" "
    bin_pad = bytearray(bin_chunk)
    while len(bin_pad) % 4 != 0:
        bin_pad.append(0)
    total_len = 12 + 8 + len(json_bytes) + 8 + len(bin_pad)
    out = bytearray()
    out += struct.pack("<4sII", b"glTF", 2, total_len)
    out += struct.pack("<II", len(json_bytes), 0x4E4F534A)
    out += json_bytes
    out += struct.pack("<II", len(bin_pad), 0x004E4942)
    out += bin_pad
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(out))


def deform_glb_region(
    input_glb: Path,
    output_glb: Path,
    anchor: str = "front_upper_protrusion",
    center_norm: tuple[float, float, float] | None = None,
    radius: float = 0.11,
    scale: tuple[float, float, float] = (0.72, 0.76, 1.28),
    shift: tuple[float, float, float] = (0.0, 0.012, 0.045),
    taper: float = 0.35,
) -> dict:
    gltf, bin_chunk = _read_glb(input_glb)
    buf = bytearray(bin_chunk)

    # Collect all POSITION accessors across meshes
    pos_acc_indices = set()
    for mesh in gltf.get("meshes", []):
        for prim in mesh.get("primitives", []):
            attrs = prim.get("attributes", {})
            if "POSITION" in attrs:
                pos_acc_indices.add(attrs["POSITION"])

    if not pos_acc_indices:
        raise RuntimeError("GLB has no POSITION attributes")

    # Compute global bounding box across all position accessors
    views = []
    all_mins, all_maxs = [], []
    for acc_idx in sorted(pos_acc_indices):
        acc = gltf["accessors"][acc_idx]
        bv = gltf["bufferViews"][acc["bufferView"]]
        byte_off = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
        count = acc["count"]
        arr = np.frombuffer(buf, dtype="<f4", count=count * 3, offset=byte_off).reshape((count, 3)).copy()
        all_mins.append(arr.min(axis=0))
        all_maxs.append(arr.max(axis=0))
        views.append((acc_idx, byte_off, arr))

    bmin = np.min(all_mins, axis=0)
    bmax = np.max(all_maxs, axis=0)
    ext = np.maximum(bmax - bmin, 1e-6)
    diag_h = float(ext[1])  # height as reference scale

    # Resolve region center in mesh coordinates
    if center_norm is not None:
        center = bmin + np.array(center_norm, dtype=np.float32) * ext
    elif anchor == "front_upper_protrusion":
        # Find frontmost (+Z) vertex in upper-center zone (y in [0.58, 0.90], |x - 0.5| < 0.22)
        best_v = None
        best_z = -1e9
        for _, _, arr in views:
            xn = (arr[:, 0] - bmin[0]) / ext[0]
            yn = (arr[:, 1] - bmin[1]) / ext[1]
            mask = (yn >= 0.58) & (yn <= 0.90) & (np.abs(xn - 0.5) <= 0.22)
            if mask.any():
                sub = arr[mask]
                idx = int(np.argmax(sub[:, 2]))
                if sub[idx, 2] > best_z:
                    best_z = float(sub[idx, 2])
                    best_v = sub[idx].copy()
        if best_v is None:
            center = bmin + np.array([0.5, 0.75, 0.95], dtype=np.float32) * ext
        else:
            # Pull center slightly inward along -Z so deformation wraps the whole protrusion smoothly
            center = best_v - np.array([0.0, 0.0, 0.035 * diag_h], dtype=np.float32)
    else:
        center = bmin + np.array([0.5, 0.5, 0.5], dtype=np.float32) * ext

    r_world = max(radius * diag_h, 1e-4)
    scale_vec = np.array(scale, dtype=np.float32)
    shift_vec = np.array(shift, dtype=np.float32) * diag_h
    affected_total = 0

    for acc_idx, byte_off, arr in views:
        rel = arr - center
        dist = np.linalg.norm(rel, axis=1)
        # Smooth Gaussian weight
        w = np.exp(-0.5 * (dist / r_world) ** 2).astype(np.float32)
        active = w > 1e-4
        affected_total += int(active.sum())

        if active.any():
            wa = w[active][:, None]
            ra = rel[active]

            # Progressive taper along +Z forward direction to remove spherical bulb shape
            forward_t = np.clip(ra[:, 2] / r_world, 0.0, 1.5)
            taper_xy = 1.0 - taper * np.clip(forward_t, 0.0, 1.0)
            local_scale = np.ones_like(ra)
            local_scale[:, 0] = scale_vec[0] * taper_xy
            local_scale[:, 1] = scale_vec[1] * taper_xy
            local_scale[:, 2] = scale_vec[2]

            target = center + ra * local_scale + shift_vec
            arr[active] = arr[active] * (1.0 - wa) + target * wa

        # Write back in-place & update accessor bounds
        buf[byte_off : byte_off + arr.nbytes] = arr.astype("<f4").tobytes()
        acc = gltf["accessors"][acc_idx]
        acc["min"] = [float(x) for x in arr.min(axis=0)]
        acc["max"] = [float(x) for x in arr.max(axis=0)]

    _write_glb(output_glb, gltf, bytes(buf))
    return {
        "input": str(input_glb),
        "output": str(output_glb),
        "anchor": anchor,
        "center_world": [round(float(x), 4) for x in center],
        "radius_world": round(r_world, 4),
        "scale": list(scale),
        "shift": list(shift),
        "taper": taper,
        "affected_vertices": affected_total,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--anchor", default="front_upper_protrusion")
    ap.add_argument("--center", default="")
    ap.add_argument("--radius", type=float, default=0.11)
    ap.add_argument("--scale", default="0.72,0.76,1.28")
    ap.add_argument("--shift", default="0.0,0.012,0.045")
    ap.add_argument("--taper", type=float, default=0.35)
    args = ap.parse_args()

    center_norm = tuple(float(x) for x in args.center.split(",")) if args.center else None
    scale = tuple(float(x) for x in args.scale.split(","))
    shift = tuple(float(x) for x in args.shift.split(","))
    res = deform_glb_region(
        Path(args.input),
        Path(args.output),
        anchor=args.anchor,
        center_norm=center_norm,
        radius=args.radius,
        scale=scale,
        shift=shift,
        taper=args.taper,
    )
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
