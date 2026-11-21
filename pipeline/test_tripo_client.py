#!/usr/bin/env python3
"""Offline unit tests (mocked HTTP, zero network / zero credits) for pipeline/tripo_client.py."""
from __future__ import annotations

import io
import json
import struct
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tripo_client as tc  # noqa: E402


def _make_minimal_glb(path: Path, with_mr: bool = True) -> Path:
    b_buf = io.BytesIO()
    Image.new("RGB", (64, 64), (210, 110, 40)).save(b_buf, format="PNG")
    b_bytes = b_buf.getvalue()

    chunks = [b_bytes]
    buffer_views = [{"buffer": 0, "byteOffset": 0, "byteLength": len(b_bytes)}]
    images = [{"bufferView": 0, "mimeType": "image/png"}]
    textures = [{"source": 0}]
    pbr: dict = {"baseColorTexture": {"index": 0}}

    if with_mr:
        m_buf = io.BytesIO()
        Image.new("RGB", (64, 64), (0, 160, 40)).save(m_buf, format="PNG")
        m_bytes = m_buf.getvalue()
        off = len(b_bytes)
        while off % 4 != 0:
            chunks.append(b"\x00")
            off += 1
        chunks.append(m_bytes)
        buffer_views.append({"buffer": 0, "byteOffset": off, "byteLength": len(m_bytes)})
        images.append({"bufferView": 1, "mimeType": "image/png"})
        textures.append({"source": 1})
        pbr["metallicRoughnessTexture"] = {"index": 1}

    bin_blob = b"".join(chunks)
    while len(bin_blob) % 4 != 0:
        bin_blob += b"\x00"

    gltf = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(bin_blob)}],
        "bufferViews": buffer_views,
        "images": images,
        "textures": textures,
        "materials": [{"pbrMetallicRoughness": pbr}],
    }
    j_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    while len(j_bytes) % 4 != 0:
        j_bytes += b" "

    total = 12 + 8 + len(j_bytes) + 8 + len(bin_blob)
    raw = (
        struct.pack("<4sII", b"glTF", 2, total)
        + struct.pack("<II", len(j_bytes), 0x4E4F534A)
        + j_bytes
        + struct.pack("<II", len(bin_blob), 0x004E4942)
        + bin_blob
    )
    path.write_bytes(raw)
    return path


class _FakeResp:
    def __init__(self, status_code: int, payload: dict | bytes):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload) if isinstance(payload, dict) else ""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        assert isinstance(self._payload, dict)
        return self._payload

    def iter_bytes(self):
        assert isinstance(self._payload, bytes)
        yield self._payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        mesh_p = _make_minimal_glb(tmp / "test_mesh.glb", with_mr=True)
        out_glb_bytes = mesh_p.read_bytes()

        # 1. Test STS upload + SigV4 PUT
        def fake_post(url, **kwargs):
            if url.endswith("/upload/sts/token"):
                return _FakeResp(200, {"data": {
                    "sts_ak": "AKIA_TEST",
                    "sts_sk": "SECRET_TEST",
                    "session_token": "SESS_TEST",
                    "resource_bucket": "tripo-data",
                    "resource_uri": "uploads/test_mesh.glb",
                    "region": "us-west-2",
                }})
            if url.endswith("/models/texture"):
                return _FakeResp(200, {"data": {"task_id": "task_mock_123"}})
            raise AssertionError(f"Unexpected POST {url}")

        def fake_put(url, **kwargs):
            assert "tripo-data.s3.us-west-2.amazonaws.com/uploads/test_mesh.glb" in url
            assert "AWS4-HMAC-SHA256" in kwargs["headers"]["Authorization"]
            return _FakeResp(200, {})

        poll_states = [
            _FakeResp(200, {"data": {"status": "queued", "progress": 0}}),
            _FakeResp(200, {"data": {"status": "running", "progress": 55}}),
            _FakeResp(200, {"data": {
                "status": "success",
                "progress": 100,
                "cost": 20,
                "output": {"pbr_model": "https://cdn.tripo3d.ai/mock/out.glb", "rendered_image": "https://cdn.tripo3d.ai/mock/out.png"},
            }}),
        ]

        def fake_get(url, **kwargs):
            return poll_states.pop(0)

        def fake_stream(method, url, **kwargs):
            return _FakeResp(200, out_glb_bytes)

        with patch("tripo_client.httpx.post", side_effect=fake_post), \
             patch("tripo_client.httpx.put", side_effect=fake_put), \
             patch("tripo_client.httpx.get", side_effect=fake_get), \
             patch("tripo_client.httpx.stream", side_effect=fake_stream):
            up = tc.tripo_sts_upload_mesh(mesh_p, api_key="mock_key")
            assert up["method"] == "sts" and up["object"]["bucket"] == "tripo-data"

            t_info = tc.tripo_texture_model(up, quality="detailed", pbr=True, api_key="mock_key")
            assert t_info["task_id"] == "task_mock_123"

            polled = tc.tripo_poll("task_mock_123", poll_interval_s=0.01, api_key="mock_key")
            assert polled["status"] == "success" and polled["cost_credits"] == 20

            dl = tc.tripo_download(polled["model_url"], tmp / "downloaded.glb")
            ext = tc.extract_glb_textures(dl, tmp / "extracted", variant_id="pbr")
            assert ext["mr_source"] == "tripo" and ext["texture_resolution"] == [64, 64]
            assert Path(ext["basecolor_path"]).is_file() and Path(ext["mr_path"]).is_file()

        # 2. Test failed task aborts with RuntimeError
        with patch("tripo_client.httpx.get", return_value=_FakeResp(200, {"data": {"status": "failed", "error": "bad mesh"}})):
            try:
                tc.tripo_poll("task_fail", poll_interval_s=0.01, api_key="mock_key")
                raise AssertionError("Expected RuntimeError on failed task")
            except RuntimeError as e:
                assert "bad mesh" in str(e)

        # 3. Test GLB without metallicRoughness returns mr_source='none'
        no_mr_glb = _make_minimal_glb(tmp / "no_mr.glb", with_mr=False)
        ext2 = tc.extract_glb_textures(no_mr_glb, tmp / "ext_no_mr", variant_id="pbr")
        assert ext2["mr_source"] == "none" and ext2["mr_path"] is None

    print("UNIT_TEST_TRIPO_CLIENT_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
