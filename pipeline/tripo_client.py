#!/usr/bin/env python3
"""Tripo3D OpenAPI Client — Stage 02 Paint Provider (STS mesh upload + texture_model + poll + GLB texture extraction).

Supports:
  - STS temporary credentials upload for external meshes (GLB/OBJ/FBX/STL, <= 150 MB)
    via POST https://api.tripo3d.ai/v2/openapi/upload/sts/token + SigV4 S3 PUT (or boto3 if available),
    with fallback to direct upload endpoint.
  - Reference image upload via POST https://api.tripo3d.ai/v2/openapi/upload (<= 20 MB).
  - Async texture_model via POST https://openapi.tripo3d.ai/v3/models/texture (with v2 fallback).
  - Polling every 10s with structured progress logging; abort on failed task.
  - GLB download + baseColor & metallicRoughness texture extraction for downstream QA/pack.

Auth: TRIPO_API_KEY from environment or factory/worker/.env (NEVER printed or committed).
"""
from __future__ import annotations

import datetime
import hashlib
import hmac
import io
import json
import os
import struct
import time
import urllib.parse
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

MAX_MESH_BYTES = 150 * 1024 * 1024  # 150 MB official Tripo limit
MAX_IMAGE_BYTES = 20 * 1024 * 1024  # 20 MB official Tripo image limit

DEFAULT_V3_BASE = "https://openapi.tripo3d.ai/v3"
DEFAULT_V2_BASE = "https://api.tripo3d.ai/v2/openapi"


def load_tripo_api_key() -> str:
    """Reads TRIPO_API_KEY from env or gitignored factory/worker/.env. Never prints the value."""
    key = os.environ.get("TRIPO_API_KEY", "").strip()
    if key:
        return key
    worker_env = Path(__file__).resolve().parent.parent / "factory" / "worker" / ".env"
    if worker_env.is_file():
        for line in worker_env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.strip() == "TRIPO_API_KEY":
                return v.strip().strip('"').strip("'")
    return ""


def _auth_headers(api_key: str) -> dict[str, str]:
    if not api_key:
        raise RuntimeError("TRIPO_API_KEY ausente. Configure TRIPO_API_KEY em factory/worker/.env.")
    return {"Authorization": f"Bearer {api_key}"}


def _sigv4_s3_put(
    *,
    bucket: str,
    key: str,
    region: str,
    access_key: str,
    secret_key: str,
    session_token: str,
    payload: bytes,
    content_type: str = "application/octet-stream",
    endpoint_host: str | None = None,
    timeout: float = 180.0,
) -> None:
    """Pure-Python AWS SigV4 S3 PUT (zero boto3 dependency required)."""
    host = endpoint_host or f"{bucket}.s3.{region}.amazonaws.com"
    canonical_uri = "/" + urllib.parse.quote(key.lstrip("/"), safe="/-_.~")
    url = f"https://{host}{canonical_uri}"

    now = datetime.datetime.now(datetime.timezone.utc)
    amz_date = now.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = now.strftime("%Y%m%d")
    payload_hash = hashlib.sha256(payload).hexdigest()

    headers_to_sign = {
        "content-type": content_type,
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": amz_date,
        "x-amz-security-token": session_token,
    }
    signed_header_names = ";".join(sorted(headers_to_sign.keys()))
    canonical_headers = "".join(f"{k}:{headers_to_sign[k]}\n" for k in sorted(headers_to_sign.keys()))
    canonical_request = f"PUT\n{canonical_uri}\n\n{canonical_headers}\n{signed_header_names}\n{payload_hash}"

    credential_scope = f"{date_stamp}/{region}/s3/aws4_request"
    string_to_sign = (
        f"AWS4-HMAC-SHA256\n{amz_date}\n{credential_scope}\n"
        f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
    )

    def _sign(k_bytes: bytes, msg: str) -> bytes:
        return hmac.new(k_bytes, msg.encode("utf-8"), hashlib.sha256).digest()

    k_date = _sign(("AWS4" + secret_key).encode("utf-8"), date_stamp)
    k_region = _sign(k_date, region)
    k_service = _sign(k_region, "s3")
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    auth_header = (
        f"AWS4-HMAC-SHA256 Credential={access_key}/{credential_scope}, "
        f"SignedHeaders={signed_header_names}, Signature={signature}"
    )

    resp = httpx.put(
        url,
        content=payload,
        headers={
            "Content-Type": content_type,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
            "x-amz-security-token": session_token,
            "Authorization": auth_header,
        },
        timeout=timeout,
    )
    resp.raise_for_status()


def tripo_sts_upload_mesh(
    path: Path | str,
    *,
    api_key: str | None = None,
    v2_base: str = DEFAULT_V2_BASE,
    max_retries: int = 3,
    timeout: float = 120.0,
) -> dict[str, Any]:
    """Uploads a 3D mesh (GLB/GLTF/OBJ/FBX/STL <= 150 MB) via Tripo STS flow.

    Returns dict:
      {
        "method": "sts" | "direct_upload",
        "object": {"bucket": ..., "key": ...} | None,
        "file_token": str | None,
        "format": "glb" | "obj" | ...,
        "size_bytes": int,
      }
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Mesh não encontrada: {p}")
    size = p.stat().st_size
    if size > MAX_MESH_BYTES:
        raise ValueError(f"Mesh excede limite Tripo de 150 MB ({size / (1024*1024):.1f} MB)")

    fmt = p.suffix.lstrip(".").lower() or "glb"
    key = api_key if api_key is not None else load_tripo_api_key()
    hdrs = _auth_headers(key)
    payload = p.read_bytes()

    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            r = httpx.post(
                f"{v2_base.rstrip('/')}/upload/sts/token",
                headers={**hdrs, "Content-Type": "application/json"},
                json={"format": fmt},
                timeout=timeout,
            )
            r.raise_for_status()
            body = r.json()
            data = body.get("data", body)
            sts_ak = data.get("sts_ak") or data.get("access_key_id")
            sts_sk = data.get("sts_sk") or data.get("secret_access_key")
            sess_tok = data.get("session_token") or ""
            bucket = data.get("resource_bucket") or data.get("bucket")
            uri = data.get("resource_uri") or data.get("key")
            region = data.get("region") or "us-west-2"
            if not (sts_ak and sts_sk and bucket and uri):
                raise RuntimeError(f"Resposta STS inesperada: {list(data.keys())}")

            _sigv4_s3_put(
                bucket=bucket,
                key=uri,
                region=region,
                access_key=sts_ak,
                secret_key=sts_sk,
                session_token=sess_tok,
                payload=payload,
                timeout=max(timeout, 180.0),
            )
            return {
                "method": "sts",
                "object": {"bucket": bucket, "key": uri},
                "file_token": data.get("file_token"),
                "format": fmt,
                "size_bytes": size,
            }
        except Exception as e:
            last_err = e
            print(f"[tripo_client] STS upload attempt {attempt}/{max_retries} failed: {e}", flush=True)
            if attempt < max_retries:
                time.sleep(2.0 * attempt)

    # Fallback: try direct /upload multipart endpoint if STS failed
    try:
        r = httpx.post(
            f"{v2_base.rstrip('/')}/upload",
            headers=hdrs,
            files={"file": (p.name, payload, "application/octet-stream")},
            timeout=max(timeout, 180.0),
        )
        r.raise_for_status()
        data = r.json().get("data", r.json())
        tok = data.get("file_token") or data.get("image_token")
        if tok:
            return {
                "method": "direct_upload",
                "object": None,
                "file_token": tok,
                "format": fmt,
                "size_bytes": size,
            }
    except Exception as e2:
        raise RuntimeError(f"STS upload falhou ({last_err}) e fallback direto falhou ({e2})") from e2

    raise RuntimeError(f"STS upload falhou: {last_err}")


def tripo_upload_image(
    path: Path | str,
    *,
    api_key: str | None = None,
    v2_base: str = DEFAULT_V2_BASE,
    timeout: float = 60.0,
) -> str:
    """Uploads a reference image (PNG/JPEG/WEBP <= 20 MB) and returns image_token."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Imagem não encontrada: {p}")
    size = p.stat().st_size
    if size > MAX_IMAGE_BYTES:
        raise ValueError(f"Imagem excede 20 MB ({size / (1024*1024):.1f} MB)")

    key = api_key if api_key is not None else load_tripo_api_key()
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    r = httpx.post(
        f"{v2_base.rstrip('/')}/upload",
        headers=_auth_headers(key),
        files={"file": (p.name, p.read_bytes(), mime)},
        timeout=timeout,
    )
    r.raise_for_status()
    data = r.json().get("data", r.json())
    tok = data.get("image_token") or data.get("file_token")
    if not tok:
        raise RuntimeError(f"Upload de imagem não retornou image_token: {data}")
    return str(tok)


def tripo_texture_model(
    mesh_upload: dict[str, Any] | str,
    quality: str = "detailed",
    pbr: bool = True,
    *,
    ref_image_token: str | None = None,
    text_prompt: str | None = None,
    seed: int = 42,
    api_key: str | None = None,
    v3_base: str = DEFAULT_V3_BASE,
    v2_base: str = DEFAULT_V2_BASE,
    timeout: float = 60.0,
) -> dict[str, Any]:
    """Starts an async texture_model task on Tripo API.

    Tries v3 POST /v3/models/texture first; if 404/405, falls back to v2 POST /v2/openapi/task.
    Returns {"task_id": str, "endpoint_used": str, "quality": str, "pbr": bool}.
    """
    key = api_key if api_key is not None else load_tripo_api_key()
    hdrs = {**_auth_headers(key), "Content-Type": "application/json"}

    # Build model reference payload
    if isinstance(mesh_upload, str):
        model_input: dict[str, Any] = {"file_token": mesh_upload}
    elif mesh_upload.get("object"):
        model_input = {"type": mesh_upload.get("format", "glb"), "object": mesh_upload["object"]}
    elif mesh_upload.get("file_token"):
        model_input = {"type": mesh_upload.get("format", "glb"), "file_token": mesh_upload["file_token"]}
    else:
        raise ValueError("mesh_upload precisa conter 'object' (STS) ou 'file_token'")

    texture_prompt: dict[str, Any] = {}
    if ref_image_token:
        texture_prompt["image"] = {"type": "png", "file_token": ref_image_token}
    if text_prompt:
        texture_prompt["text"] = text_prompt

    # 1. Try v3 endpoint
    v3_payload: dict[str, Any] = {
        "input": model_input,
        "pbr": bool(pbr),
        "texture_quality": quality,
        "texture_seed": int(seed),
    }
    if texture_prompt:
        v3_payload["texture_prompt"] = texture_prompt

    v3_url = f"{v3_base.rstrip('/')}/models/texture"
    r = httpx.post(v3_url, headers=hdrs, json=v3_payload, timeout=timeout)
    if r.status_code in (200, 201, 202):
        data = r.json().get("data", r.json())
        tid = data.get("task_id") or data.get("id")
        if tid:
            return {"task_id": str(tid), "endpoint_used": v3_url, "quality": quality, "pbr": bool(pbr)}

    # 2. Fallback to v2 task endpoint
    if r.status_code in (404, 405, 400, 422):
        v2_url = f"{v2_base.rstrip('/')}/task"
        v2_payload: dict[str, Any] = {
            "type": "texture_model",
            "pbr": bool(pbr),
            "texture_quality": quality,
            "texture_seed": int(seed),
            "model": model_input,
        }
        if texture_prompt:
            v2_payload["texture_prompt"] = texture_prompt
        r2 = httpx.post(v2_url, headers=hdrs, json=v2_payload, timeout=timeout)
        r2.raise_for_status()
        data2 = r2.json().get("data", r2.json())
        tid2 = data2.get("task_id") or data2.get("id")
        if not tid2:
            raise RuntimeError(f"Tripo v2 task não retornou task_id: {data2}")
        return {"task_id": str(tid2), "endpoint_used": v2_url, "quality": quality, "pbr": bool(pbr)}

    r.raise_for_status()
    raise RuntimeError(f"Erro inesperado Tripo texture_model: HTTP {r.status_code} {r.text[:300]}")


def tripo_poll(
    task_id: str,
    *,
    timeout_s: float = 1200.0,
    poll_interval_s: float = 10.0,
    api_key: str | None = None,
    v2_base: str = DEFAULT_V2_BASE,
    v3_base: str = DEFAULT_V3_BASE,
    use_v3: bool = False,
) -> dict[str, Any]:
    """Polls Tripo task every 10s until success or failed (aborts on failed)."""
    key = api_key if api_key is not None else load_tripo_api_key()
    hdrs = _auth_headers(key)
    poll_url = f"{v3_base.rstrip('/')}/tasks/{task_id}" if use_v3 else f"{v2_base.rstrip('/')}/task/{task_id}"
    alt_url = f"{v2_base.rstrip('/')}/task/{task_id}" if use_v3 else f"{v3_base.rstrip('/')}/tasks/{task_id}"

    t0 = time.time()
    while True:
        elapsed = round(time.time() - t0, 1)
        if elapsed > timeout_s:
            raise TimeoutError(f"Tripo task {task_id} excedeu timeout de {timeout_s}s")

        r = httpx.get(poll_url, headers=hdrs, timeout=30.0)
        if r.status_code == 404:
            r = httpx.get(alt_url, headers=hdrs, timeout=30.0)
            if r.status_code == 200:
                poll_url = alt_url
        r.raise_for_status()

        body = r.json()
        data = body.get("data", body)
        status = str(data.get("status", "unknown")).lower()
        progress = data.get("progress", 0)
        print(f"[tripo_poll] task={task_id} status={status} progress={progress}% elapsed={elapsed}s", flush=True)

        if status == "success":
            out = data.get("output", {}) or {}
            model_url = out.get("pbr_model") or out.get("model") or out.get("model_url") or out.get("base_model")
            render_url = out.get("rendered_image") or out.get("rendered_image_url")
            if not model_url:
                raise RuntimeError(f"Tripo task {task_id} concluiu sem model_url: {out}")
            return {
                "task_id": task_id,
                "status": "success",
                "elapsed_s": elapsed,
                "model_url": model_url,
                "rendered_image_url": render_url,
                "cost_credits": data.get("cost") or data.get("credits_used") or data.get("credit_cost"),
                "raw_output": out,
            }

        if status in ("failed", "cancelled", "banned", "expired"):
            err_msg = data.get("error") or data.get("message") or json.dumps(data)[:300]
            raise RuntimeError(f"Tripo task {task_id} falhou (status={status}): {err_msg}")

        time.sleep(poll_interval_s)


def tripo_download(model_url: str, dest: Path | str, timeout: float = 300.0) -> Path:
    """Downloads resulting GLB from Tripo model_url to dest."""
    dst = Path(dest)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", model_url, timeout=timeout, follow_redirects=True) as r:
        r.raise_for_status()
        with dst.open("wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    if dst.stat().st_size < 100 or dst.read_bytes()[:4] != b"glTF":
        raise RuntimeError(f"Arquivo baixado de {model_url} não é um GLB válido")
    return dst


def extract_glb_textures(glb_path: Path | str, out_dir: Path | str, variant_id: str = "pbr") -> dict[str, Any]:
    """Extracts embedded baseColor and metallicRoughness textures from a Tripo GLB.

    Returns {
      "basecolor_path": str,
      "mr_path": str | None,
      "mr_source": "tripo" | "none",
      "texture_resolution": [w, h],
    }
    """
    p = Path(glb_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    raw = p.read_bytes()
    magic, _, _ = struct.unpack_from("<4sII", raw, 0)
    if magic != b"glTF":
        raise ValueError(f"Arquivo inválido (não é GLB): {p}")

    jlen, _ = struct.unpack_from("<II", raw, 12)
    gltf = json.loads(raw[20 : 20 + jlen].decode("utf-8"))
    bin_off = 20 + jlen + 8

    images = gltf.get("images", [])
    textures = gltf.get("textures", [])
    buffer_views = gltf.get("bufferViews", [])
    materials = gltf.get("materials", [])

    def _read_img_by_tex_idx(tex_idx: int) -> Image.Image | None:
        if tex_idx is None or tex_idx >= len(textures):
            return None
        img_idx = textures[tex_idx].get("source")
        if img_idx is None or img_idx >= len(images):
            return None
        img_obj = images[img_idx]
        bv_idx = img_obj.get("bufferView")
        if bv_idx is None or bv_idx >= len(buffer_views):
            return None
        bv = buffer_views[bv_idx]
        start = bin_off + bv.get("byteOffset", 0)
        blob = raw[start : start + bv["byteLength"]]
        return Image.open(io.BytesIO(blob))

    base_im: Image.Image | None = None
    mr_im: Image.Image | None = None
    for mat in materials:
        pbr = mat.get("pbrMetallicRoughness", {})
        if base_im is None and "baseColorTexture" in pbr:
            base_im = _read_img_by_tex_idx(pbr["baseColorTexture"].get("index"))
        if mr_im is None and "metallicRoughnessTexture" in pbr:
            mr_im = _read_img_by_tex_idx(pbr["metallicRoughnessTexture"].get("index"))

    # Fallback: first image if material lookup missed
    if base_im is None and images:
        bv = buffer_views[images[0]["bufferView"]]
        start = bin_off + bv.get("byteOffset", 0)
        base_im = Image.open(io.BytesIO(raw[start : start + bv["byteLength"]]))

    if base_im is None:
        raise RuntimeError(f"GLB do Tripo não contém textura baseColor embutida: {p}")

    base_im = base_im.convert("RGB")
    base_out = out / f"{variant_id}_tripo_albedo.png"
    base_im.save(base_out)

    mr_out_str: str | None = None
    if mr_im is not None:
        mr_dir = out / "mr_tripo"
        mr_dir.mkdir(parents=True, exist_ok=True)
        mr_out = mr_dir / f"{variant_id}_mr.png"
        mr_im.convert("RGB").save(mr_out)
        mr_out_str = str(mr_out)

    return {
        "basecolor_path": str(base_out),
        "mr_path": mr_out_str,
        "mr_source": "tripo" if mr_out_str else "none",
        "texture_resolution": [base_im.width, base_im.height],
    }
