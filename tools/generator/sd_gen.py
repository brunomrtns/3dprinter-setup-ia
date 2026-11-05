#!/usr/bin/env python3
"""Gera 4 candidatos 'Jubarte nas Ondas' via SD 2.1 (venv printer3d-sd, GPU exclusiva).

Ao final o processo termina — VRAM liberada por definição. O caller confirma via nvidia-smi.
"""
import datetime
import json
import os
import time

import numpy as np
import torch

OUT = os.path.expanduser("~/printer3d-work/jubarte/sd")
os.makedirs(OUT, exist_ok=True)

PROMPT = (
    "stylized sculpture of a humpback whale diving through a circular wave ring, "
    "matte clay material, chunky stylization, thick curves, no thin fragile parts, "
    "single object, centered, neutral gray background, studio lighting, 3/4 view, "
    "high detail, no text"
)
NEG = "text, watermark, multiple objects, floating parts, thin fragile parts, photo, humans"
SEEDS = [11, 23, 42, 77]

print("[sd] carregando pipeline fp16...", flush=True)
t0 = time.time()
from diffusers import StableDiffusionPipeline  # noqa: E402

pipe = StableDiffusionPipeline.from_pretrained(
    "CompVis/stable-diffusion-v1-4", torch_dtype=torch.float16, safety_checker=None
)
pipe = pipe.to("cuda")
pipe.set_progress_bar_config(disable=True)
t_load = round(time.time() - t0, 1)
print(f"[sd] load {t_load}s — gerando {len(SEEDS)} candidatos", flush=True)

rep = {"modelo": "CompVis/stable-diffusion-v1-4",
       "nota": "SD2.1 gated no HF (401 anônimo) — fallback v1-4 público, licença CreativeML OpenRAIL",
       "fp16": True, "prompt": PROMPT,
       "negativo": NEG, "steps": 30, "guidance": 7.5, "resolucao": 512,
       "tempo_load_s": t_load, "candidatos": []}

for seed in SEEDS:
    g = torch.Generator("cuda").manual_seed(seed)
    t0 = time.time()
    img = pipe(PROMPT, negative_prompt=NEG, num_inference_steps=30,
               guidance_scale=7.5, generator=g).images[0]
    dt = round(time.time() - t0, 1)
    p = os.path.join(OUT, f"cand_{seed}.png")
    img.save(p)
    vram = int(torch.cuda.max_memory_allocated() / 1024 / 1024)
    rep["candidatos"].append({"seed": seed, "arquivo": p, "tempo_s": dt,
                              "vram_pico_alloc_mib": vram})
    print(f"[sd] seed {seed}: {dt}s alloc_pico {vram}MiB -> {p}", flush=True)

rep["ts"] = datetime.datetime.now().isoformat(timespec="seconds")
with open(os.path.join(OUT, "sd_report.json"), "w") as f:
    json.dump(rep, f, indent=1)
print("SD_GEN_OK")
