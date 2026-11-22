#!/usr/bin/env python3
"""
tools/generator/inventario_pesos.py — Inventário read-only de pesos locais (Lei 8 / ADR-010).

Varre ~/tools/, ~/.cache/huggingface/hub/, ~/.rembg/, ~/.cache/torch/ e caminhos conhecidos
de pesos de IA no WSL, calcula tamanho real e SHA-256 (somente leitura — ZERO downloads),
detecta possíveis duplicidades e grava docs/knowledge/inventario-pesos.md.

Uso (WSL):
  python3 tools/generator/inventario_pesos.py [--out docs/knowledge/inventario-pesos.md]
"""
from __future__ import annotations

import argparse
import hashlib
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

WEIGHT_EXTS = {".safetensors", ".ckpt", ".pth", ".pt", ".bin", ".onnx"}
MIN_BYTES = 5 * 1024 * 1024  # >= 5 MiB para ignorar configs/tokenizers pequenos

HOME = Path.home()

# Mapa heurístico: padrão no caminho -> (família, origem/HF repo, venv/runner)
FAMILY_RULES = [
    ("triposg", ("TripoSG", "VAST-AI/TripoSG", "~/.venvs/triposg · tools/generator/triposg_runner.py")),
    ("triposf", ("TripoSF", "VAST-AI/TripoSF", "~/venvs/triposf · tools/generator/triposf/triposf_runner.py")),
    ("triposr", ("TripoSR", "stabilityai/TripoSR", "~/.venvs/printer3d-ia · tools/generator/triposr_runner.py")),
    ("trellis.2", ("TRELLIS.2", "microsoft/TRELLIS.2-4B", "~/.venvs/trellis2 · pipeline/retexture_trellis.py (MR PBR)")),
    ("trellis-image", ("TRELLIS (v1)", "microsoft/TRELLIS-image-large", "~/.venvs/printer3d-ia · legado/descontinuado")),
    ("trellis", ("TRELLIS", "microsoft/TRELLIS*", "~/.venvs/trellis2 ou ~/.venvs/printer3d-ia")),
    ("hunyuan3d", ("Hunyuan3D (dit/paint/mv)", "tencent/Hunyuan3D-2*", "~/.venvs/hunyuan · pipeline/paint_quality.py & hunyuan_runner.py")),
    ("hi3dgen", ("Hi3DGen", "Stable-X/trellis-normal-v0-1 / Hi3DGen", "~/.venvs/hi3dgen · tools/generator/hi3dgen_runner.py")),
    ("yoso", ("Hi3DGen (NiRNE YOSO)", "Stable-X/yoso-normal-v1-8-1", "~/.venvs/hi3dgen · tools/generator/hi3dgen_runner.py")),
    ("realesrgan", ("RealESRGAN", "xinntao/Real-ESRGAN (x4plus)", "~/.venvs/hunyuan · pipeline/pack_glb.py & paint_quality.py")),
    ("esrgan", ("RealESRGAN", "xinntao/Real-ESRGAN", "~/.venvs/hunyuan · pipeline/pack_glb.py")),
    ("rmbg", ("rembg / BriaRMBG", "briaai/RMBG-1.4 / 2.0", "~/.venvs/triposg & ~/.venvs/printer3d-ia")),
    ("u2net", ("rembg (u2net/isnet)", "danielgatis/rembg", "~/.venvs/printer3d-ia · tools/generator/preprocess_input.py")),
    ("isnet", ("rembg (u2net/isnet)", "danielgatis/rembg", "~/.venvs/printer3d-ia · tools/generator/preprocess_input.py")),
    ("birefnet", ("rembg (BiRefNet)", "ZhengPeng7/BiRefNet", "~/.venvs/printer3d-ia · tools/generator/preprocess_input.py")),
    ("dinov3", ("DINOv3 (TRELLIS.2)", "camenduru/dinov3-vitl16-pretrain-lvd1689m", "~/.venvs/trellis2 · pipeline/retexture_trellis.py")),
    ("dinov2", ("DINOv2", "facebook/dinov2*", "~/.venvs/printer3d-ia / hunyuan / trellis2")),
    ("sdxl", ("SDXL-Turbo (2D)", "stabilityai/sdxl-turbo", "~/.venvs/hunyuan · concept_bridge (game-concerto)")),
    ("vggt", ("VGGT", "facebook/VGGT-1B", "~/.venvs/hunyuan · tools/generator/vggt_recon.py")),
]


def classify(path_str: str) -> tuple[str, str, str]:
    low = path_str.lower()
    for key, val in FAMILY_RULES:
        if key in low:
            return val
    # Extrai repo HF se estiver em ~/.cache/huggingface/hub/models--ORG--REPO
    if "models--" in path_str:
        seg = path_str.split("models--", 1)[1].split("/", 1)[0]
        repo = seg.replace("--", "/")
        return (repo.split("/")[-1], repo, "cache HF compartilhado")
    return ("Outros", "local", "desconhecido")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fmt_size(nbytes: int) -> str:
    if nbytes >= 1024**3:
        return f"{nbytes / (1024**3):.2f} GiB"
    return f"{nbytes / (1024**2):.1f} MiB"


def scan_roots() -> list[Path]:
    roots = [
        HOME / "tools",
        HOME / ".cache" / "huggingface" / "hub",
        HOME / ".cache" / "torch" / "hub" / "checkpoints",
        HOME / ".rembg",
        HOME / ".u2net",
        HOME / "printer3d-work" / "weights",
    ]
    return [r for r in roots if r.exists()]


def collect_weights() -> list[dict]:
    seen_real: set[str] = set()
    entries: list[dict] = []

    for root in scan_roots():
        for dirpath, dirnames, filenames in os.walk(root):
            # Ignora .git e caches internos de blobs HF se ja vamos pegar pelos snapshots (ou pega blobs reais)
            # No cache HF, snapshots/ contem symlinks para blobs/; dedup por realpath garante 1 entrada real!
            dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", "node_modules")]
            for fn in filenames:
                p = Path(dirpath) / fn
                ext = p.suffix.lower()
                # Em HF blobs nao ha extensao; pegamos via snapshots (symlink -> blob) onde o nome tem extensao!
                if ext not in WEIGHT_EXTS:
                    continue
                try:
                    real = str(p.resolve(strict=True))
                    st = p.stat()
                except OSError:
                    continue
                if st.st_size < MIN_BYTES:
                    continue
                if real in seen_real:
                    continue
                seen_real.add(real)
                rel_display = str(p).replace(str(HOME), "~")
                fam, repo, runner = classify(rel_display)
                digest = sha256_file(Path(real))
                entries.append({
                    "family": fam,
                    "path": rel_display,
                    "repo": repo,
                    "size_bytes": st.st_size,
                    "size_str": fmt_size(st.st_size),
                    "sha256": digest,
                    "runner": runner,
                })

    entries.sort(key=lambda e: (e["family"].lower(), -e["size_bytes"], e["path"]))
    return entries


def render_markdown(entries: list[dict]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total_bytes = sum(e["size_bytes"] for e in entries)

    by_sha: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        by_sha[e["sha256"]].append(e)
    dups = {k: v for k, v in by_sha.items() if len(v) > 1}

    by_fam: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        by_fam[e["family"]].append(e)

    lines = [
        "# Inventário de Pesos Locais (Lei 8 / ADR-010)",
        "",
        f"> Gerado automaticamente por `tools/generator/inventario_pesos.py` em **{now}** (somente leitura — zero downloads).",
        f"> **Total inventariado:** **{len(entries)} arquivos** (`>= 5 MiB`) · **{fmt_size(total_bytes)}** · **Duplicidades por SHA-256:** **{len(dups)}**.",
        "",
        "## Resumo por Família",
        "",
        "| Família | Arquivos | Tamanho Total | Venv / Runner Principal |",
        "|---|---:|---:|---|",
    ]
    for fam in sorted(by_fam.keys(), key=str.lower):
        f_items = by_fam[fam]
        f_bytes = sum(x["size_bytes"] for x in f_items)
        lines.append(f"| {fam} | {len(f_items)} | {fmt_size(f_bytes)} | `{f_items[0]['runner']}` |")

    lines += [
        "",
        "## Duplicidades Detectadas (mesmo SHA-256 em caminhos físicos distintos)",
        "",
    ]
    if not dups:
        lines.append("- **Zero duplicidades físicas encontradas** (symlinks do cache HF `snapshots/ -> blobs/` deduplicados por `realpath`).")
    else:
        for sha, group in dups.items():
            paths = ", ".join(f"`{g['path']}`" for g in group)
            lines.append(f"- `{sha[:16]}…` ({group[0]['size_str']}): {paths}")

    lines += [
        "",
        "## Tabela Completa de Pesos (Read-Only + SHA-256)",
        "",
        "| Família | Caminho | Origem / HF Repo | Tamanho | SHA-256 (16 hex) | Venv / Runner |",
        "|---|---|---|---:|---|---|",
    ]
    for e in entries:
        lines.append(
            f"| {e['family']} | `{e['path']}` | `{e['repo']}` | {e['size_str']} | `{e['sha256'][:16]}` | `{e['runner']}` |"
        )

    lines += [
        "",
        "## Regra Operacional (ADR-010 — Lei 8)",
        "",
        "1. Antes de baixar qualquer peso novo, execute `python3 tools/generator/inventario_pesos.py` e confira esta tabela.",
        "2. Se o peso já existir no disco, reutilize via cache HF compartilhado (`~/.cache/huggingface/hub/`) ou symlink — **nunca crie uma segunda cópia física**.",
        "3. Todo novo peso autorizado pelo dono deve ser registrado aqui imediatamente após o download.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Inventário read-only de pesos locais (ADR-010 / Lei 8)")
    ap.add_argument("--out", default="docs/knowledge/inventario-pesos.md")
    args = ap.parse_args()

    entries = collect_weights()
    md = render_markdown(entries)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"[inventario_pesos] Gravado: {out_path} ({len(entries)} arquivos, {fmt_size(sum(e['size_bytes'] for e in entries))})")


if __name__ == "__main__":
    main()
