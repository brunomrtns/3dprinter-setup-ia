#!/usr/bin/env python3
"""ETAPA B/C — Hunyuan3D-Paint v2-0 (1.3B) com offload agressivo para RTX 3060 12GB.

Reaproveita EXATAMENTE mv_a/uv.obj e mv_b/uv.obj (sem re-gerar malha nem UV!).
Ordem de baixa VRAM:
  1. fp16 + offload sequencial (delight -> descarrega -> multiview com enable_model_cpu_offload + VAE slicing/tiling)
  2. Textura 1024 primeiro; se pico < 9.5GB (9728 MiB) -> refaz bake nativo em 2048
  3. Se OOM -> tenta sequential_cpu_offload
  4. Seed 42 em tudo + amostragem de VRAM a cada 10s.
"""
from __future__ import annotations

import gc
import json
import os
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

os.environ.setdefault(
    "PYTORCH_CUDA_ALLOC_CONF",
    "expandable_segments:True,garbage_collection_threshold:0.65,max_split_size_mb:128",
)

HY2_HOME = os.path.expanduser("~/tools/Hunyuan3D-2")
sys.path.insert(0, HY2_HOME)
REPO_ROOT = Path("/mnt/c/Users/Bruno/OneDrive/Documentos/Default Project/3dprinter-setup-ia")
sys.path.insert(0, str(REPO_ROOT / "tools" / "generator"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
import trimesh  # noqa: E402
from huggingface_hub import snapshot_download  # noqa: E402
from PIL import Image  # noqa: E402

from gpu_guard import GpuJobContext  # noqa: E402


def query_vram_used_mib() -> int:
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            text=True,
        ).strip()
        return int(out.splitlines()[0].strip())
    except Exception:
        return -1


class VramSampler10s:
    def __init__(self, interval_s: float = 10.0):
        self.interval_s = interval_s
        self.samples: list[list[float | int]] = []
        self.peak_mib = 0
        self._stop = threading.Event()
        self._t0 = 0.0
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._t0 = time.time()
        self._sample()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _sample(self) -> None:
        used = query_vram_used_mib()
        if used >= 0:
            self.samples.append([round(time.time() - self._t0, 1), used])
            if used > self.peak_mib:
                self.peak_mib = used

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_s):
            self._sample()

    def stop(self) -> dict:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._sample()
        return {
            "vram_samples_10s": self.samples,
            "vram_pico_mib": self.peak_mib,
            "vram_baseline_mib": self.samples[0][1] if self.samples else 0,
        }


def seed_all(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def hsv_sat_pct(rgb: np.ndarray) -> float:
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    return round(float(hsv[..., 1].astype(np.float32).mean() / 255.0 * 100.0), 2)


def ensure_weights() -> tuple[str, str]:
    """Baixa (ou reutiliza cache HF) de hunyuan3d-delight-v2-0 e hunyuan3d-paint-v2-0."""
    print("[etapa_b] Verificando/baixando pesos tencent/Hunyuan3D-2 (delight + paint-v2-0)...", flush=True)
    p_delight = snapshot_download(
        repo_id="tencent/Hunyuan3D-2",
        allow_patterns=["hunyuan3d-delight-v2-0/*"],
    )
    p_paint = snapshot_download(
        repo_id="tencent/Hunyuan3D-2",
        allow_patterns=["hunyuan3d-paint-v2-0/*"],
    )
    return (
        os.path.join(p_delight, "hunyuan3d-delight-v2-0"),
        os.path.join(p_paint, "hunyuan3d-paint-v2-0"),
    )


def run_delight(
    delight_ckpt: str,
    ref_paths: list[Path],
    cache_dir: Path,
    use_sequential: bool = False,
) -> list[Image.Image]:
    """Roda Light_Shadow_Remover nas 4 fotos reais (com cache em disco) e descarrega 100% da GPU depois."""
    cache_paths = [cache_dir / f"delight_{rp.stem}.png" for rp in ref_paths]
    if all(cp.exists() for cp in cache_paths):
        print("[etapa_c] Reutilizando 4 fotos delighted em cache.", flush=True)
        return [Image.open(cp).convert("RGB").resize((512, 512), Image.Resampling.LANCZOS) for cp in cache_paths]

    from diffusers import DiffusionPipeline, EulerAncestralDiscreteScheduler

    print(f"[etapa_c] Carregando delight_model ({delight_ckpt})...", flush=True)
    pipe = DiffusionPipeline.from_pretrained(delight_ckpt, torch_dtype=torch.float16)
    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(
        pipe.scheduler.config, timestep_spacing="trailing"
    )
    pipe.set_progress_bar_config(disable=True)
    if hasattr(pipe, "enable_vae_slicing"):
        pipe.enable_vae_slicing()
    if hasattr(pipe, "enable_vae_tiling"):
        pipe.enable_vae_tiling()
    if use_sequential:
        pipe.enable_sequential_cpu_offload()
    else:
        pipe.enable_model_cpu_offload()

    delighted = []
    with torch.inference_mode():
        for rp, cp in zip(ref_paths, cache_paths):
            im = Image.open(rp).convert("RGB").resize((512, 512), Image.Resampling.LANCZOS)
            gen = torch.Generator(device="cuda").manual_seed(42)
            out = pipe(
                prompt="",
                image=im,
                generator=gen,
                num_inference_steps=50,
                image_guidance_scale=1.5,
                guidance_scale=1.0,
            ).images[0].resize((512, 512), Image.Resampling.LANCZOS)
            out.save(cp)
            delighted.append(out)
            print(f"  delight OK: {rp.name}", flush=True)

    del pipe
    gc.collect()
    torch.cuda.empty_cache()
    return delighted


def run_paint_mesh(
    uv_obj_path: Path,
    delighted_imgs: list[Image.Image],
    paint_ckpt: str,
    tex_size: int,
    use_sequential: bool = False,
) -> tuple[Image.Image, list[Image.Image], dict]:
    """Sintetiza 6 vistas via Hunyuan3D-Paint v2-0 e faz bake preservando UV original de uv.obj."""
    from diffusers import DiffusionPipeline, EulerAncestralDiscreteScheduler
    from hy3dgen.texgen.differentiable_renderer.mesh_render import MeshRender

    t0 = time.time()
    seed_all(42)

    # 1. Carrega malha preservando UV existente (NÃO chama mesh_uv_wrap!)
    mesh = trimesh.load(str(uv_obj_path), force="mesh", process=False)
    render = MeshRender(default_resolution=tex_size, texture_size=tex_size)
    render.load_mesh(mesh)

    camera_azims = [0, 90, 180, 270, 0, 180]
    camera_elevs = [0, 0, 0, 0, 90, -90]
    view_weights = [1.0, 0.3, 0.8, 0.3, 0.5, 0.05]

    normal_maps = [render.render_normal(el, az, use_abs_coor=True, return_type="pl") for el, az in zip(camera_elevs, camera_azims)]
    position_maps = [render.render_position(el, az, return_type="pl") for el, az in zip(camera_elevs, camera_azims)]

    camera_info = [
        (((az // 30) + 9) % 12) // {-20: 1, 0: 1, 20: 1, -90: 3, 90: 3}[el]
        + {-20: 0, 0: 12, 20: 24, -90: 36, 90: 40}[el]
        for az, el in zip(camera_azims, camera_elevs)
    ]

    # 2. Carrega Hunyuan3D-Paint v2-0 com offload de CPU + VAE slicing/tiling
    custom_pipe_dir = os.path.join(HY2_HOME, "hy3dgen", "texgen", "hunyuanpaint")
    print(f"[etapa_c] Carregando multiview paint (tex={tex_size}, sequential={use_sequential})...", flush=True)
    pipe = DiffusionPipeline.from_pretrained(
        paint_ckpt,
        custom_pipeline=custom_pipe_dir,
        torch_dtype=torch.float16,
    )
    pipe.scheduler = EulerAncestralDiscreteScheduler.from_config(
        pipe.scheduler.config, timestep_spacing="trailing"
    )
    pipe.set_progress_bar_config(disable=True)
    if hasattr(pipe, "enable_vae_slicing"):
        pipe.enable_vae_slicing()
    if hasattr(pipe, "enable_vae_tiling"):
        pipe.enable_vae_tiling()
    if hasattr(pipe, "enable_attention_slicing"):
        pipe.enable_attention_slicing(1)

    # Offload manual por estágio (Etapa B.1):
    # - pipe.to("cuda") preserva pipe._execution_device == cuda:0
    # - antes do denoise: VAE + text_encoder vão pra CPU (só UNet em CUDA)
    # - depois do denoise (antes do vae.decode): UNet vai pra CPU (só VAE em CUDA)
    pipe.to("cuda")
    torch.cuda.empty_cache()

    orig_denoise = pipe.denoise

    def _staged_denoise(*args, **kwargs):
        pipe.vae.to("cpu")
        gc.collect()
        torch.cuda.empty_cache()
        out_lat = orig_denoise(*args, **kwargs)
        pipe.unet.to("cpu")
        gc.collect()
        torch.cuda.empty_cache()
        pipe.vae.to("cuda")
        return out_lat

    pipe.denoise = _staged_denoise

    control_images = [im.resize((512, 512)) for im in (normal_maps + position_maps)]
    num_view = len(camera_azims)
    normal_in = [[control_images[i] for i in range(num_view)]]
    pos_in = [[control_images[i + num_view] for i in range(num_view)]]

    # Referência: usa as 4 fotos reais (ou a vista herói + multi-ref suportada pelo pipeline)
    ref_in = [im.resize((512, 512)) for im in delighted_imgs]
    # O pipeline espera lista de input_images e camera_info_ref com mesmo tamanho
    # Vamos passar as 4 fotos reais com azims [0, 90, 180, 270] ou fallback [ref_in[0]] se o pipeline aceitar só 1 ref
    with torch.inference_mode():
        gen = torch.Generator(device="cuda").manual_seed(42)
        try:
            multiviews = pipe(
                ref_in,
                num_inference_steps=30,
                generator=gen,
                width=512,
                height=512,
                num_in_batch=num_view,
                camera_info_gen=[camera_info],
                camera_info_ref=[[0, 3, 6, 9][: len(ref_in)]],
                normal_imgs=normal_in,
                position_imgs=pos_in,
            ).images
            ref_mode = f"multi_ref_{len(ref_in)}"
        except Exception as e:
            print(f"  [aviso] multi-ref falhou ({type(e).__name__}: {str(e)[:120]}), usando single-ref [R1_front]", flush=True)
            gc.collect()
            torch.cuda.empty_cache()
            pipe.unet.to("cuda")
            pipe.vae.to("cuda")
            gen = torch.Generator(device="cuda").manual_seed(42)
            multiviews = pipe(
                [ref_in[0]],
                num_inference_steps=30,
                generator=gen,
                width=512,
                height=512,
                num_in_batch=num_view,
                camera_info_gen=[camera_info],
                camera_info_ref=[[0]],
                normal_imgs=normal_in,
                position_imgs=pos_in,
            ).images
            ref_mode = "single_ref_R1_front"

    del pipe
    gc.collect()
    torch.cuda.empty_cache()

    # 3. Bake + inpaint 100% da textura na resolução tex_size (1024 ou 2048)
    mv_resized = [mv.resize((tex_size, tex_size), Image.Resampling.LANCZOS) for mv in multiviews]
    project_textures, project_weighted_cos = [], []
    for mv, el, az, wt in zip(mv_resized, camera_elevs, camera_azims, view_weights):
        ptex, pcos, _ = render.back_project(mv, el, az)
        project_textures.append(ptex)
        project_weighted_cos.append(wt * (pcos ** 4))

    tex_t, trust_t = render.fast_bake_texture(project_textures, project_weighted_cos)
    mask_np = ((trust_t > 1e-8).squeeze(-1).cpu().numpy() * 255).astype(np.uint8)
    tex_np = render.uv_inpaint(tex_t, mask_np)
    tex_img = Image.fromarray(np.clip(tex_np, 0, 255).astype(np.uint8), mode="RGB")

    del render, tex_t, trust_t, project_textures, project_weighted_cos
    gc.collect()
    torch.cuda.empty_cache()

    return tex_img, multiviews, {
        "tex_size": tex_size,
        "ref_mode": ref_mode,
        "tempo_s": round(time.time() - t0, 2),
        "sat_pct": hsv_sat_pct(np.asarray(tex_img)),
    }


def main() -> int:
    work = Path("/home/bruno/printer3d-work/carro/fox_fullrun")
    evid = REPO_ROOT / "evidence" / "rtx3060-12gb" / "fox_aipaint"
    ai_dir = evid / "ai_textures"
    ai_dir.mkdir(parents=True, exist_ok=True)

    ref_dir = Path("/mnt/c/Users/Bruno/Downloads/fox/prep_real")
    ref_paths = [
        ref_dir / "R1_front.png",
        ref_dir / "R2_side.png",
        ref_dir / "R3_back.png",
        ref_dir / "R2r_right.png",
    ]

    delight_ckpt, paint_ckpt = ensure_weights()

    sampler = VramSampler10s(interval_s=10.0)
    results = {
        "seed": 42,
        "caminho_usado": None,
        "ref_images": [str(p) for p in ref_paths],
        "meshes": {},
        "erros": [],
    }

    with GpuJobContext(min_free_mib=7500, job_name="fox_aipaint_hy3d"):
        sampler.start()
        t_all = time.time()

        # Delight das 4 fotos reais (com cache em disco)
        try:
            delighted = run_delight(delight_ckpt, ref_paths, ai_dir, use_sequential=False)
        except torch.cuda.OutOfMemoryError:
            gc.collect()
            torch.cuda.empty_cache()
            results["erros"].append("delight OOM com model_cpu_offload; tentando sequential_cpu_offload")
            delighted = run_delight(delight_ckpt, ref_paths, ai_dir, use_sequential=True)

        # Para cada malha (mv_a e mv_b): tenta 1024 primeiro; se pico < 9.5GB (9728 MiB), refaz nativo em 2048!
        for tag in ("mv_a", "mv_b"):
            uv_obj = work / tag / "uv.obj"
            print(f"\n=== [ETAPA C] Pintura AI Hunyuan3D-Paint v2-0: {tag} ===", flush=True)
            tex_img = None
            info = None
            use_seq = False
            for attempt in range(2):
                try:
                    tex_img, mvs, info = run_paint_mesh(
                        uv_obj, delighted, paint_ckpt, tex_size=1024, use_sequential=use_seq
                    )
                    break
                except torch.cuda.OutOfMemoryError as e:
                    gc.collect()
                    torch.cuda.empty_cache()
                    results["erros"].append(f"{tag} 1024 OOM attempt {attempt+1}: {str(e)[:120]}")
                    use_seq = True

            if tex_img is None:
                results["caminho_usado"] = "OOM_FALHA_AI"
                break

            peak_so_far = sampler.peak_mib
            print(f"  {tag} 1024 OK! tempo={info['tempo_s']}s sat={info['sat_pct']}% peak_vram={peak_so_far} MiB", flush=True)

            # Regra Etapa B.2: se pico < 9.5GB (9728 MiB), refaz nativo em 2048!
            if peak_so_far < 9728:
                try:
                    print(f"  [ETAPA B.2] Pico {peak_so_far} MiB < 9728 MiB -> refazendo {tag} nativo em 2048!", flush=True)
                    tex_2k, mvs_2k, info_2k = run_paint_mesh(
                        uv_obj, delighted, paint_ckpt, tex_size=2048, use_sequential=use_seq
                    )
                    tex_img, mvs, info = tex_2k, mvs_2k, info_2k
                    results["caminho_usado"] = "AI_2048"
                except torch.cuda.OutOfMemoryError as e:
                    gc.collect()
                    torch.cuda.empty_cache()
                    results["erros"].append(f"{tag} 2048 OOM (mantendo 1024): {str(e)[:120]}")
                    results["caminho_usado"] = "AI_1024"
            else:
                results["caminho_usado"] = "AI_1024"

            # Salva textura crua AI em evidence e copia como bake2048.png (2048x2048) para Etapa F
            raw_ai_path = ai_dir / f"{tag}_ai_{info['tex_size']}.png"
            tex_img.save(raw_ai_path)
            bake2k = tex_img if tex_img.size == (2048, 2048) else tex_img.resize((2048, 2048), Image.Resampling.LANCZOS)
            bake2k.save(work / tag / "bake2048.png")

            results["meshes"][tag] = {
                "raw_ai_png": str(raw_ai_path),
                "bake2048_png": str(work / tag / "bake2048.png"),
                **info,
            }

        vram_info = sampler.stop()
        results["tempo_total_s"] = round(time.time() - t_all, 2)
        results.update(vram_info)

    (evid / "ai_paint_result.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("AI_PAINT_DONE=" + json.dumps({"caminho": results["caminho_usado"], "peak_mib": results.get("vram_pico_mib"), "tempo_s": results.get("tempo_total_s")}))
    return 0 if results["caminho_usado"] in ("AI_2048", "AI_1024") else 2


if __name__ == "__main__":
    raise SystemExit(main())
