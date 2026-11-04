#!/usr/bin/env python3
"""Benchmark 10 casos × 2 modos (TRELLIS vs TripoSR) — Fase 1.

Estágios resumíveis (estado por caso em ~/printer3d-work/benchmark/<caso>/<modo>/):
  trellis  — gera + repara + escoreia os 10 casos no modo TRELLIS
  triposr  — idem TripoSR
  render   — previews padronizados (Blender, câmera/luz fixas, 2 ângulos)
  publish  — results.json + scores.md + gallery.md + PNGs → evidence/benchmark/ (repo)

Espessura mínima: ESTIMATIVA AMOSTRAL por raycast (open3d BVH) — 300 amostras de
superfície, raio ao longo de -normal, distância à 1ª oposição; reportado o
percentil 5 em unidades da malha (≈cubo unitário dos geradores). Não é medição
exata de engenharia — é gate comparável entre modos.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys

import numpy as np
import trimesh

WORKDIR = os.path.expanduser("~/printer3d-work")
BENCH = os.path.join(WORKDIR, "benchmark")
TESTSET_SRC = "/mnt/c/Users/Bruno/OneDrive/Documentos/Default Project/3dprinter-setup-ia/benchmarks/testset"
REPO_EVID = "/mnt/c/Users/Bruno/OneDrive/Documentos/Default Project/3dprinter-setup-ia/evidence/benchmark"
SEED = 42
N_AMOSTRAS_ESPESSURA = 300


def now_iso() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def log(msg: str) -> None:
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def carregar_manifest() -> list[dict]:
    with open(os.path.join(TESTSET_SRC, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)["casos"]


def preparar_testset_local() -> dict[str, str]:
    dst_dir = os.path.join(WORKDIR, "testset")
    os.makedirs(dst_dir, exist_ok=True)
    mapa = {}
    for caso in carregar_manifest():
        src = os.path.join(TESTSET_SRC, caso["arquivo"])
        dst = os.path.join(dst_dir, caso["arquivo"])
        if not os.path.isfile(dst):
            shutil.copyfile(src, dst)
        mapa[caso["id"]] = dst
    return mapa


def espessura_minima_estimada(mesh: trimesh.Trimesh) -> dict:
    import open3d as o3d

    pts, face_idx = trimesh.sample.sample_surface(mesh, N_AMOSTRAS_ESPESSURA, seed=SEED)
    normals = mesh.face_normals[face_idx]
    scene = o3d.t.geometry.RaycastingScene()
    scene.add_triangles(
        o3d.core.Tensor(np.asarray(mesh.vertices, dtype=np.float32)),
        o3d.core.Tensor(np.asarray(mesh.faces, dtype=np.uint32)),
    )
    rays = np.hstack([pts, -normals]).astype(np.float32)
    ans = scene.cast_rays(o3d.core.Tensor(rays))
    t = ans["t_hit"].numpy()
    sem_parede = int(np.sum(~np.isfinite(t)))
    validos = t[np.isfinite(t) & (t > 1e-3)]
    if len(validos) == 0:
        return {
            "espessura_pct5": None,
            "espessura_min": None,
            "amostras": int(len(pts)),
            "sem_parede_oposta": sem_parede,
            "metodo": f"raycast -normal, {N_AMOSTRAS_ESPESSURA} amostras, pct5, unidades da malha",
        }
    return {
        "espessura_pct5": round(float(np.percentile(validos, 5)), 5),
        "espessura_min": round(float(validos.min()), 5),
        "amostras": int(len(pts)),
        "sem_parede_oposta": sem_parede,
        "metodo": f"raycast -normal, {N_AMOSTRAS_ESPESSURA} amostras, pct5, unidades da malha",
    }


def escorear(report_dict: dict, mesh_reparada_path: str) -> dict:
    m = trimesh.load(mesh_reparada_path, force="mesh", process=False)
    esp = espessura_minima_estimada(m)
    report_dict["espessura"] = esp
    report_dict["vertices_reparada"] = int(len(m.vertices))
    report_dict["faces_reparada"] = int(len(m.faces))
    return report_dict


def stage_gerar(mode: str) -> None:
    gen_dir = os.path.join(WORKDIR, "gen")
    sys.path.insert(0, gen_dir if os.path.isdir(gen_dir) else ".")
    if mode == "trellis":
        from trellis_plugin import TrellisGenerator as Gen
    else:
        from triposr_plugin import TripoSRGenerator as Gen

    imagens = preparar_testset_local()
    gen = Gen()
    gen.prepare()
    for caso in carregar_manifest():
        out = os.path.join(BENCH, caso["id"], mode)
        rep_path = os.path.join(out, "report.json")
        if os.path.isfile(rep_path):
            log(f"{caso['id']}/{mode}: já existe, pulando")
            continue
        log(f"{caso['id']}/{mode}: gerando...")
        params = {"seed": SEED} if mode == "trellis" else {}
        rep = gen.generate(imagens[caso["id"]], out, params)
        d = rep.to_dict()
        if d.get("mesh_reparada_path") and os.path.isfile(d["mesh_reparada_path"]):
            d = escorear(d, d["mesh_reparada_path"])
        d["caso"] = caso["id"]
        d["categoria"] = caso.get("categoria", "")
        d["ts"] = now_iso()
        with open(rep_path, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        status = "OK" if not d.get("erros") else f"ERROS: {d['erros'][:1]}"
        log(
            f"{caso['id']}/{mode}: {status} | t={d.get('tempo_s')}s "
            f"vram={d.get('vram_pico_mib')}MiB verts={d.get('vertices')} "
            f"manifold {d.get('manifold_antes')}->{d.get('manifold_depois_reparo')}"
        )


def stage_render() -> None:
    render_py = os.path.join(WORKDIR, "render_preview.py")
    repo_render = "/mnt/c/Users/Bruno/OneDrive/Documentos/Default Project/3dprinter-setup-ia/tools/generator/render_preview.py"
    shutil.copyfile(repo_render, render_py)
    gal_dir = os.path.join(WORKDIR, "benchmark", "gallery")
    os.makedirs(gal_dir, exist_ok=True)
    for caso in carregar_manifest():
        for mode in ("trellis", "triposr"):
            out = os.path.join(BENCH, caso["id"], mode)
            mesh = os.path.join(out, "mesh.obj")
            if not os.path.isfile(mesh):
                log(f"{caso['id']}/{mode}: sem mesh, render pulado")
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
            log(f"{caso['id']}/{mode}: render {'OK' if ok else 'FALHOU'}")


def coletar_resultados() -> dict:
    casos = []
    for caso in carregar_manifest():
        for mode in ("trellis", "triposr"):
            p = os.path.join(BENCH, caso["id"], mode, "report.json")
            if os.path.isfile(p):
                with open(p, encoding="utf-8") as f:
                    casos.append(json.load(f))
            else:
                casos.append({"caso": caso["id"], "mode": mode, "erros": ["sem report"]})
    import torch

    meta = {
        "data": now_iso(),
        "seed_trellis": SEED,
        "seed_triposr": None,
        "torch": torch.__version__,
        "gpu": subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version",
             "--format=csv,noheader"],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip(),
        "venv": "printer3d-ia (py3.11.16)",
        "trellis_repo": "microsoft/TRELLIS @ main 2026-10-27",
        "triposr_repo": "VAST-AI-Research/TripoSR @ 107cefd",
    }
    return {"meta": meta, "resultados": casos}


def fmt(x, nd=1):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{nd}f}"
    return str(x)


def gerar_scores_md(res: dict) -> str:
    linhas = [
        "# Benchmark Fase 1 — TRELLIS vs TripoSR (10 casos fixos)",
        "",
        f"Gerado automaticamente por `run_benchmark.py` em {res['meta']['data']} — sem edição manual.",
        "",
        f"GPU: `{res['meta']['gpu']}` · torch {res['meta']['torch']} · seed TRELLIS {res['meta']['seed_trellis']}",
        "",
        "Espessura = estimativa amostral (raycast −normal, 300 amostras, percentil 5, **unidades da malha ≈ cubo unitário** — mm reais só após `scale_mm` na Forja). `parede%` = amostras com oposição encontrada (100% = casca fechada em todo o amostrado).",
        "",
        "## Tabela completa (por caso × modo)",
        "",
        "| caso | modo | tempo_s | VRAM pico MiB | vértices | faces | manifold antes→depois reparo | espessura pct5 | parede% | erro |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in res["resultados"]:
        esp = r.get("espessura") or {}
        n = esp.get("amostras")
        parede = (
            f"{100.0 * (n - esp.get('sem_parede_oposta', n)) / n:.0f}%" if n else "—"
        )
        erro = "SIM" if r.get("erros") else ""
        linhas.append(
            f"| {r.get('caso')} | {r.get('mode')} | {fmt(r.get('tempo_s'))} | "
            f"{fmt(r.get('vram_pico_mib'), 0)} | {fmt(r.get('vertices'), 0)} | "
            f"{fmt(r.get('faces'), 0)} | "
            f"{r.get('manifold_antes')}→{r.get('manifold_depois_reparo')} | "
            f"{fmt(esp.get('espessura_pct5'), 3)} | {parede} | {erro} |"
        )

    linhas += ["", "## Resumo por modo", ""]
    linhas.append("| modo | tempo médio s | mediana s | VRAM pico máx MiB | vértices médios | manifold após reparo (n/10) | erros (n/10) |")
    linhas.append("|---|---|---|---|---|---|---|")
    for mode in ("trellis", "triposr"):
        rs = [r for r in res["resultados"] if r.get("mode") == mode]
        tempos = sorted(r["tempo_s"] for r in rs if r.get("tempo_s"))
        vrams = [r["vram_pico_mib"] for r in rs if r.get("vram_pico_mib")]
        verts = [r["vertices"] for r in rs if r.get("vertices")]
        manifold_ok = sum(1 for r in rs if r.get("manifold_depois_reparo"))
        erros = sum(1 for r in rs if r.get("erros"))
        linhas.append(
            f"| {mode} | {fmt(np.mean(tempos)) if tempos else '—'} | "
            f"{fmt(np.median(tempos)) if tempos else '—'} | "
            f"{fmt(max(vrams), 0) if vrams else '—'} | "
            f"{fmt(np.mean(verts), 0) if verts else '—'} | "
            f"{manifold_ok}/10 | {erros}/10 |"
        )
    return "\n".join(linhas) + "\n"


def gerar_gallery_md(res: dict) -> str:
    casos = {c["id"]: c for c in carregar_manifest()}
    linhas = [
        "# Galeria — 10 casos × 2 modos",
        "",
        f"Gerado automaticamente em {res['meta']['data']}. Render: Blender 5.0.1 headless,",
        "Cycles CPU, **câmera/luz idênticas para todos** (ângulo A = 3/4 frontal 35°/25°,",
        "ângulo B = 3/4 traseiro 145°/15°). Malha CRUDA do gerador (sem reparo).",
        "",
    ]
    for cid, caso in casos.items():
        linhas += [
            f"## {cid} — {caso.get('categoria', '')}",
            "",
            "| input | TRELLIS A / B | TripoSR A / B |",
            "|---|---|---|",
        ]
        def score_cell(mode: str) -> str:
            r = next(
                (x for x in res["resultados"]
                 if x.get("caso") == cid and x.get("mode") == mode), None
            )
            if not r or r.get("erros") and not r.get("mesh_path"):
                return f"`{mode}: ERRO`"
            esp = r.get("espessura") or {}
            txt = (
                f"`t={fmt(r.get('tempo_s'))}s · {fmt(r.get('vram_pico_mib'), 0)}MiB · "
                f"{fmt(r.get('vertices'), 0)}v · manifold {r.get('manifold_antes')}→{r.get('manifold_depois_reparo')}`"
            )
            imgs = (
                f"![{cid} {mode} A](gallery/{cid}_{mode}_a.png)<br>"
                f"![{cid} {mode} B](gallery/{cid}_{mode}_b.png)<br>{txt}"
            )
            return imgs

        linhas.append(
            f"![input {cid}](../../benchmarks/testset/{caso['arquivo']})<br>"
            f"`{caso['origem'].get('licenca', '')}` | "
            f"{score_cell('trellis')} | {score_cell('triposr')} |"
        )
        linhas.append("")
    linhas += [
        "---",
        "Votação do dono: 👍/👎 por caso, por modo — registrada depois em ADR-005 (default mode).",
        "",
    ]
    return "\n".join(linhas) + "\n"


def stage_publish() -> None:
    res = coletar_resultados()
    os.makedirs(REPO_EVID, exist_ok=True)
    gal_repo = os.path.join(REPO_EVID, "gallery")
    os.makedirs(gal_repo, exist_ok=True)
    with open(os.path.join(REPO_EVID, "results.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    with open(os.path.join(REPO_EVID, "scores.md"), "w", encoding="utf-8") as f:
        f.write(gerar_scores_md(res))
    with open(os.path.join(REPO_EVID, "gallery.md"), "w", encoding="utf-8") as f:
        f.write(gerar_gallery_md(res))
    gal_src = os.path.join(BENCH, "gallery")
    n = 0
    for fn in os.listdir(gal_src):
        if fn.endswith(".png"):
            dst = os.path.join(gal_repo, fn)
            if not os.path.isfile(dst):
                shutil.copyfile(os.path.join(gal_src, fn), dst)
                n += 1
    log(f"publish: {n} PNGs novos copiados; results.json/scores.md/gallery.md escritos")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--stage", required=True,
                   choices=["trellis", "triposr", "render", "publish", "all"])
    a = p.parse_args()
    if a.stage in ("trellis", "all"):
        stage_gerar("trellis")
    if a.stage in ("triposr", "all"):
        stage_gerar("triposr")
    if a.stage in ("render", "all"):
        stage_render()
    if a.stage in ("publish", "all"):
        stage_publish()
    log(f"stage {a.stage} concluído")


if __name__ == "__main__":
    main()
