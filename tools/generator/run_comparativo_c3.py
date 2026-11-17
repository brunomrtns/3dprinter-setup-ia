#!/usr/bin/env python3
"""Comparativo formal da Fase C (C3) na rtx3060-12gb.

4 geradores na MESMA entrada pré-processada (testset_preproc):
  trellis2 · triposg · trellis (baseline) · triposr (baseline)

Mesmos gates da Fase 1 (scoring importado de run_benchmark.py): manifold leve,
espessura pct5, vértices, faces, tempo, VRAM pico (guard + poller 1Hz).

Estágios (igual run_benchmark.py):
  gerar   — roda os modos pendentes
  render  — galeria 2 ângulos via Blender (mesma câmera/luz) + input
  publish — results.json + scores.md + gallery.md na evidência do repo

Evidência: evidence/fase-c/comparativo-3060/ (namespaced por fase — ADR-006).
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

_REPO_GENERATOR = os.environ.get(
    "C3_REPO_GENERATOR",
    "/mnt/c/Users/Bruno/OneDrive/Documentos/Default Project/3dprinter-setup-ia/tools/generator",
)
sys.path.insert(0, _REPO_GENERATOR)

import run_benchmark as rb  # noqa: E402  (reusa carregar_manifest, escorear, log, fmt)

WORKDIR = os.path.expanduser("~/printer3d-work")
PREPROC = os.path.join(WORKDIR, "testset_preproc")
OUT = os.path.join(WORKDIR, "c3-bench")
EVID = os.path.join(_REPO_GENERATOR, "..", "..", "evidence", "fase-c", "comparativo-3060")
REPO_EVID = Path(EVID).resolve()
MODES = ("trellis2", "triposg", "trellis", "triposr")
SEED = 42


def input_path(caso_id: str) -> str:
    return os.path.join(PREPROC, f"{caso_id}_preproc.png")


def stage_gerar(modes: list[str]) -> None:
    # Repo primeiro: gen/ tem cópias antigas da Fase 1 (base_plugin sem venv_py)
    # — se viesse primeiro, trellis2/triposg rodariam no venv errado.
    gen_dir = os.path.join(WORKDIR, "gen")
    sys.path.insert(0, _REPO_GENERATOR)
    if os.path.isdir(gen_dir):
        sys.path.append(gen_dir)
    from trellis2_plugin import Trellis2Generator
    from triposg_plugin import TripoSGGenerator
    from trellis_plugin import TrellisGenerator
    from triposr_plugin import TripoSRGenerator

    gens = {
        "trellis2": Trellis2Generator,
        "triposg": TripoSGGenerator,
        "trellis": TrellisGenerator,
        "triposr": TripoSRGenerator,
    }
    casos = rb.carregar_manifest()
    for mode in modes:
        gen = gens[mode]()
        gen.prepare()
        for caso in casos:
            ip = input_path(caso["id"])
            if not os.path.isfile(ip):
                rb.log(f"{caso['id']}/{mode}: INPUT ausente ({ip}) — pulando")
                continue
            out = os.path.join(OUT, caso["id"], mode)
            rep_path = os.path.join(out, "report.json")
            if os.path.isfile(rep_path):
                rb.log(f"{caso['id']}/{mode}: já existe, pulando")
                continue
            rb.log(f"{caso['id']}/{mode}: gerando...")
            # triposr é determinístico (sem ruído) — runner não aceita --seed
            params = {"seed": SEED} if mode != "triposr" else {}
            rep = gen.generate(ip, out, params)
            d = rep.to_dict()
            if d.get("mesh_reparada_path") and os.path.isfile(d["mesh_reparada_path"]):
                d = rb.escorear(d, d["mesh_reparada_path"])
            d["caso"] = caso["id"]
            d["categoria"] = caso.get("categoria", "")
            d["ts"] = rb.now_iso()
            with open(rep_path, "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False, indent=1)
            status = "OK" if not d.get("erros") else f"ERROS: {d['erros'][:1]}"
            rb.log(
                f"{caso['id']}/{mode}: {status} | t={d.get('tempo_s')}s "
                f"vram={d.get('vram_pico_mib')}MiB verts={d.get('vertices')} "
                f"manifold {d.get('manifold_antes')}->{d.get('manifold_depois_reparo')}"
            )


def stage_render() -> None:
    render_py = os.path.join(WORKDIR, "render_preview.py")
    repo_render = os.path.join(_REPO_GENERATOR, "render_preview.py")
    shutil.copyfile(repo_render, render_py)
    gal_dir = os.path.join(WORKDIR, "c3-bench", "gallery")
    os.makedirs(gal_dir, exist_ok=True)
    for caso in rb.carregar_manifest():
        for mode in MODES:
            out = os.path.join(OUT, caso["id"], mode)
            mesh = os.path.join(out, "mesh.obj")
            if not os.path.isfile(mesh):
                rb.log(f"{caso['id']}/{mode}: sem mesh, render pulado")
                continue
            a = os.path.join(gal_dir, f"{caso['id']}_{mode}_a.png")
            b = os.path.join(gal_dir, f"{caso['id']}_{mode}_b.png")
            if os.path.isfile(a) and os.path.isfile(b):
                continue
            r = subprocess.run(
                ["blender", "-b", "-P", render_py, "--", "--input", mesh,
                 "--out1", a, "--out2", b, "--res", "640"],
                capture_output=True, text=True, timeout=600,
            )
            ok = "RENDER_OK" in r.stdout
            rb.log(f"{caso['id']}/{mode}: render {'OK' if ok else 'FALHOU'}")


def coletar_resultados() -> dict:
    casos = []
    for caso in rb.carregar_manifest():
        for mode in MODES:
            p = os.path.join(OUT, caso["id"], mode, "report.json")
            if os.path.isfile(p):
                with open(p, encoding="utf-8") as f:
                    casos.append(json.load(f))
            else:
                casos.append({"caso": caso["id"], "mode": mode, "erros": ["sem report"]})
    meta = {
        "data": rb.now_iso(),
        "seed": SEED,
        "entrada": "testset_preproc (C2 — preprocess_input.py)",
        "gpu": subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip(),
        "venvs": {
            "trellis2": "printer3d-venvs trellis2 (torch 2.8.0+cu128, xformers fallback)",
            "triposg": "triposg (torch 2.8.0+cu128, diffusers 0.43)",
            "trellis": "printer3d-ia (torch 2.5.1+cu121)",
            "triposr": "printer3d-ia (torch 2.5.1+cu121)",
        },
        "python_runner": platform.python_version(),
        "repos": {
            "trellis2": "microsoft/TRELLIS.2-4B via fork IgorAherne/TRELLIS.2-stableprojectorz (shape-only 512³ — 1024_cascade OOM em 12GB; ATTN=xformers)",
            "triposg": "VAST-AI/TripoSG (diffusers TripoSGPipeline, fp16, 50 steps, cfg 7.0)",
            "trellis": "microsoft/TRELLIS @ main 2026-10-27 (baseline Fase 1)",
            "triposr": "VAST-AI-Research/TripoSR @ 107cefd (baseline Fase 1)",
        },
    }
    return {"meta": meta, "resultados": casos}


def gerar_scores_md(res: dict) -> str:
    linhas = [
        "# Comparativo Fase C (C3) — 4 geradores, entrada pré-processada",
        "",
        f"Gerado automaticamente em {res['meta']['data']} — sem edição manual.",
        "",
        f"GPU: `{res['meta']['gpu']}` · entrada: {res['meta']['entrada']} · seed {SEED}",
        "",
        "## Tabela por caso × modo",
        "",
        "| caso | modo | tempo_s | VRAM pico MiB | vértices | manifold antes→depois | espessura pct5 | erro |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in res["resultados"]:
        esp = (r.get("espessura") or {}).get("espessura_pct5")
        erro = "SIM" if r.get("erros") else ""
        linhas.append(
            f"| {r['caso']} | {r['mode']} | {rb.fmt(r.get('tempo_s'))} | "
            f"{rb.fmt(r.get('vram_pico_mib'), 0)} | {rb.fmt(r.get('vertices'), 0)} | "
            f"{r.get('manifold_antes')}→{r.get('manifold_depois_reparo')} | {rb.fmt(esp, 3)} | {erro} |"
        )
    linhas += ["", "## Resumo por modo", "",
               "| modo | tempo mediana s | VRAM pico máx MiB | vértices médios | manifold pós-reparo | erros |",
               "|---|---|---|---|---|---|"]
    for mode in MODES:
        rs = [r for r in res["resultados"] if r["mode"] == mode and not r.get("erros")]
        if not rs:
            linhas.append(f"| {mode} | — | — | — | — | {sum(1 for r in res['resultados'] if r['mode']==mode and r.get('erros'))}/10 |")
            continue
        tempos = [r["tempo_s"] for r in rs if r.get("tempo_s")]
        vrams = [r["vram_pico_mib"] for r in rs if r.get("vram_pico_mib")]
        verts = [r.get("vertices_reparada") or r.get("vertices") or 0 for r in rs]
        manifold_ok = sum(1 for r in rs if r.get("manifold_depois_reparo"))
        erros = sum(1 for r in res["resultados"] if r["mode"] == mode and r.get("erros"))
        linhas.append(
            f"| {mode} | {rb.fmt(statistics.median(tempos))} | {rb.fmt(max(vrams), 0)} | "
            f"{rb.fmt(statistics.mean(verts), 0)} | {manifold_ok}/10 | {erros}/10 |"
        )
    return "\n".join(linhas) + "\n"


def gerar_gallery_md() -> str:
    gal = "https://raw.githubusercontent.com"  # não usado; caminhos relativos no repo
    linhas = [
        "# Galeria Fase C (C3) — entrada pré-processada × 4 geradores",
        "",
        "Renders: Blender headless, mesma câmera/luz (ângulos A/B, 640px). Malha CRUDA do gerador (sem reparo pesado).",
        "",
    ]
    for caso in rb.carregar_manifest():
        cid = caso["id"]
        linhas.append(f"## {cid} — {caso.get('categoria', '')}")
        linhas.append("")
        inp = os.path.join(PREPROC, f"{cid}_preproc.png")
        linhas.append(f"![input {cid}](../../../data/testset_preproc/{cid}_preproc.png)" if False else
                      f"**Entrada pré-processada:** `~/printer3d-work/testset_preproc/{cid}_preproc.png`")
        linhas.append("")
        for mode in MODES:
            a = os.path.join(WORKDIR, "c3-bench", "gallery", f"{cid}_{mode}_a.png")
            b = os.path.join(WORKDIR, "c3-bench", "gallery", f"{cid}_{mode}_b.png")
            if os.path.isfile(a) and os.path.isfile(b):
                linhas.append(
                    f"![{cid} {mode} A](gallery_render/{cid}_{mode}_a.png) ![{cid} {mode} B](gallery_render/{cid}_{mode}_b.png) `{mode}`"
                )
            else:
                linhas.append(f"`{mode}: sem render`")
        linhas.append("")
    return "\n".join(linhas) + "\n"


def stage_publish() -> None:
    res = coletar_resultados()
    REPO_EVID.mkdir(parents=True, exist_ok=True)
    with open(REPO_EVID / "results.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    (REPO_EVID / "scores.md").write_text(gerar_scores_md(res), encoding="utf-8")
    (REPO_EVID / "gallery.md").write_text(gerar_gallery_md(), encoding="utf-8")
    # renders commitados (evidência de imagem, ~350KB × 80)
    gal_src = os.path.join(WORKDIR, "c3-bench", "gallery")
    gal_dst = REPO_EVID / "gallery_render"
    gal_dst.mkdir(exist_ok=True)
    for f in os.listdir(gal_src):
        if f.endswith(".png"):
            shutil.copyfile(os.path.join(gal_src, f), gal_dst / f)
    rb.log(f"publish OK → {REPO_EVID}")


def main() -> int:
    stage = sys.argv[1] if len(sys.argv) > 1 else "gerar"
    modes = sys.argv[2].split(",") if len(sys.argv) > 2 else list(MODES)
    if stage == "gerar":
        stage_gerar(modes)
    elif stage == "render":
        stage_render()
    elif stage == "publish":
        stage_publish()
    else:
        print(f"estágio desconhecido: {stage} (use gerar|render|publish)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
