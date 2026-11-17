#!/usr/bin/env python3
"""Sonda: mede pico de VRAM por estágio do forward do TripoSF (o256)."""
import os, sys, torch
os.environ["ATTN_BACKEND"] = "xformers"
os.environ["SPARSE_ATTN_BACKEND"] = "xformers"
sys.path.insert(0, os.path.expanduser("~/tools/TripoSF"))

from inference import TripoSFVAEInference, normalize_mesh, load_quantized_mesh_original
from triposf.modules import sparse as sp

CFG = os.path.expanduser("~/printer3d-work/triposf-bench/configs/TripoSFVAE_o256.yaml")
MESH = os.path.expanduser("~/tools/TripoSF/assets/examples/jacket.obj")

def peak(tag):
    torch.cuda.synchronize()
    alloc = torch.cuda.max_memory_allocated() / 2**20
    reserved = torch.cuda.max_memory_reserved() / 2**20
    print(f"[probe] {tag}: alloc_pico={alloc:.0f} MiB reserved_pico={reserved:.0f} MiB", flush=True)

model = TripoSFVAEInference.from_config(CFG).to("cuda")
peak("modelo_carregado")

mesh_gt = normalize_mesh(MESH)
import tempfile
tmp = tempfile.NamedTemporaryFile(suffix=".obj", delete=False)
import trimesh as tm
tm.Trimesh(vertices=mesh_gt.vertices.tolist(), faces=mesh_gt.faces.tolist()).export(tmp.name)
sparse_voxels, points_sample = load_quantized_mesh_original(
    tmp.name, volume_resolution=model.cfg.resolution,
    use_normals=model.cfg.use_normals, pc_sample_number=model.cfg.sample_points_num)
print(f"[probe] voxels={len(sparse_voxels)} points={len(points_sample)}", flush=True)

sv = sparse_voxels.to("cuda"); ps = points_sample.to("cuda")
sv_sp = torch.cat([torch.zeros_like(sv[..., :1]), sv], dim=-1).int()

torch.cuda.reset_peak_memory_stats()
with torch.no_grad(), torch.autocast("cuda", dtype=torch.float16):
    feats = model.local_pc_encoder(ps[None], sv_sp, res=model.cfg.resolution, bbox_size=(-0.5, 0.5))
peak("apos_local_pc_encoder")

st = sp.SparseTensor(feats, sv_sp)
with torch.no_grad(), torch.autocast("cuda", dtype=torch.float16):
    latent, posterior = model.encoder(st)
peak("apos_encoder")

with torch.no_grad(), torch.autocast("cuda", dtype=torch.float16):
    mesh = model.decoder(latent, pruning=model.cfg.pruning)
peak("apos_decoder")
print(f"[probe] faces_recon={len(mesh.faces)}", flush=True)
