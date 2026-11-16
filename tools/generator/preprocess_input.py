#!/usr/bin/env python3
"""C2 da Fase C — padronização de entrada para geradores image→3D.

O elo mais fraco medido na Fase 1/C é a qualidade da imagem de entrada. Este
script padroniza QUALQUER imagem para o formato canônico do projeto:

  PNG 1024×1024, fundo removido (rembg), sujeito aparado pela máscara alfa,
  pad quadrado SEM cortar o sujeito, composto sobre fundo branco.

Por saída é gerado um sidecar de procedência (ADR-003) com origem, comando,
versões e hash do original.

Uso:
  # um arquivo
  tools/setup/py.sh tools/generator/preprocess_input.py --input img.png --output out.png
  # lote (todos os .png/.jpg do diretório)
  tools/setup/py.sh tools/generator/preprocess_input.py --batch <dir> --output-dir <dir> [--manifest <manifest.json>]

Upscale (Real-ESRGAN ou similar): OPCIONAL, OFF por default (--upscale). Se as
deps não existirem, registra pendência e segue sem — nada pesado é instalado
aqui (decisão C2).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import platform
import sys
import uuid
from pathlib import Path

from PIL import Image

TARGET_PX = 1024
BACKGROUND_RGB = (255, 255, 255)
REMBG_MODEL = "u2net"  # default do rembg; registrado no sidecar


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def try_upscale(img: Image.Image) -> tuple[Image.Image, str]:
    """Upscale opcional (OFF por default). Sem deps → pendência honesta, sem instalar nada."""
    try:
        import realesrgan  # noqa: F401
        return img, "upscale: realesrgan disponível (não usado nesta versão do C2)"
    except ImportError:
        return img, (
            "upscale: INDISPONÍVEL — realesrgan ausente no venv; seguiu sem upscale "
            "[!] pendência registrada (decisão C2: nada pesado instalado nesta sessão)"
        )


def process_one(input_path: Path, output_path: Path, manifest_entry: dict | None, do_upscale: bool) -> dict:
    from rembg import remove, new_session

    session = new_session(REMBG_MODEL)
    original = Image.open(input_path).convert("RGBA")

    # 1. fundo removido (rembg)
    cut = remove(original, session=session)

    # 2. aparar pelo bounding box da máscara alfa (sem cortar sujeito: bbox cobre tudo)
    alpha = cut.split()[3]
    bbox = alpha.getbbox()
    if bbox:
        cut = cut.crop(bbox)

    # 3. pad quadrado SEM cortar (lado = maior dimensão, sujeito centralizado)
    side = max(cut.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(cut, ((side - cut.size[0]) // 2, (side - cut.size[1]) // 2))

    # 4. redimensionar para TARGET_PX
    final = square.resize((TARGET_PX, TARGET_PX), Image.LANCZOS)

    # 5. upscale opcional (OFF por default) — ANTES do composite para ganhar definição
    upscale_note = "upscale: OFF (default)"
    if do_upscale:
        final, upscale_note = try_upscale(final)

    # 6. composto sobre fundo branco (compatível com todos os geradores/consumidores)
    canvas = Image.new("RGB", final.size, BACKGROUND_RGB)
    canvas.paste(final, mask=final.split()[3])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, "PNG")

    # 7. sidecar ADR-003
    src = (manifest_entry or {}).get("source", {})
    sidecar = {
        "id": str(uuid.uuid4()),
        "source": {
            "url": src.get("url", str(input_path)),
            "author": src.get("author", "desconhecido"),
            "license": src.get("license", "desconhecida"),
            "triage": src.get("triage", "amarelo"),
            "retrieved_at": src.get("retrieved_at", datetime.date.today().isoformat()),
        },
        "hash_original": sha256_file(input_path),
        "transform_log": [
            {
                "op": "preprocess.c2",
                "tool": f"preprocess_input.py (rembg {REMBG_MODEL}, PIL {Image.__version__ if hasattr(Image, '__version__') else 'n/a'}, python {platform.python_version()})",
                "params": {
                    "target_px": TARGET_PX,
                    "background": "branco",
                    "pad": "quadrado, bbox alfa, sem corte",
                    "upscale": upscale_note,
                },
                "ts": datetime.datetime.now().isoformat(timespec="seconds"),
            }
        ],
        "units": "px",
        "generator": None,
    }
    sidecar_path = output_path.with_suffix(".json")
    sidecar_path.write_text(json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "input": str(input_path),
        "output": str(output_path),
        "size_original": list(original.size),
        "size_final": list(canvas.size),
        "sidecar": str(sidecar_path),
        "upscale_note": upscale_note,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="C2 — padronização de entrada (1024px, fundo removido, pad quadrado)")
    ap.add_argument("--input", type=Path, help="imagem única de entrada")
    ap.add_argument("--output", type=Path, help="PNG de saída (para --input)")
    ap.add_argument("--batch", type=Path, help="diretório de entrada (.png/.jpg/.jpeg/.webp)")
    ap.add_argument("--output-dir", type=Path, help="diretório de saída do lote")
    ap.add_argument("--manifest", type=Path, help="manifest.json de procedência do testset (opcional)")
    ap.add_argument("--suffix", default="_preproc", help="sufixo do nome de saída (default: _preproc)")
    ap.add_argument("--upscale", action="store_true", help="ativa upscale se as deps existirem (OFF por default)")
    args = ap.parse_args()

    manifest: dict[str, dict] = {}
    if args.manifest and args.manifest.is_file():
        data = json.loads(args.manifest.read_text(encoding="utf-8"))
        entries = data.get("casos", data) if isinstance(data, dict) else data
        for entry in entries:
            key = Path(entry.get("arquivo", entry.get("file", ""))).stem
            manifest[key] = entry

    jobs: list[tuple[Path, Path, dict | None]] = []
    if args.input:
        if not args.output:
            ap.error("--input exige --output")
        jobs.append((args.input, args.output, manifest.get(args.input.stem)))
    elif args.batch:
        if not args.output_dir:
            ap.error("--batch exige --output-dir")
        exts = {".png", ".jpg", ".jpeg", ".webp"}
        for img in sorted(args.batch.iterdir()):
            if img.suffix.lower() in exts and not img.stem.endswith(args.suffix):
                out = args.output_dir / f"{img.stem}{args.suffix}.png"
                jobs.append((img, out, manifest.get(img.stem)))
    else:
        ap.error("use --input/--output ou --batch/--output-dir")

    print(f"[preprocess.c2] {len(jobs)} imagem(ns); modelo rembg={REMBG_MODEL}; upscale={'ON' if args.upscale else 'OFF'}")
    for input_path, output_path, entry in jobs:
        info = process_one(input_path, output_path, entry, args.upscale)
        print(
            f"[preprocess.c2] OK {input_path.name} → {output_path.name} "
            f"{info['size_original']}→{info['size_final']} | {info['upscale_note']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
