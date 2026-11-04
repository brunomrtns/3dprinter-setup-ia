"""Contrato comum dos geradores (ADR-001): generate(image, output_dir, params) -> GenerationReport.

Toda a malha gerada é ESCOREADA igual: manifold antes/depois de reparo leve
(merge_vertices + fill_holes, trimesh), vértices/faces, bbox, tempo e VRAM pico.
Plugins rodam como subprocesso do runner correspondente (isolamento de memória
e captura de VRAM por poller externo).
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Optional

from gpu_guard import GpuJobContext, VramPoller, wait_for_vram

VENVPY = os.path.expanduser("~/.venvs/printer3d-ia/bin/python")
REPO_GENERATOR = os.environ.get(
    "GENERATOR_SRC",
    "/mnt/c/Users/Bruno/OneDrive/Documentos/Default Project/3dprinter-setup-ia/tools/generator",
)
WORKDIR = os.path.expanduser("~/printer3d-work")


@dataclass
class GenerationReport:
    mode: str
    model: str
    image: str
    mesh_path: Optional[str] = None
    mesh_reparada_path: Optional[str] = None
    texturas: list = field(default_factory=list)
    seed: Optional[int] = None
    tempo_s: Optional[float] = None
    tempo_load_s: Optional[float] = None
    tempo_run_s: Optional[float] = None
    vram_pico_mib: Optional[int] = None
    vram_baseline_mib: Optional[int] = None
    vertices: Optional[int] = None
    faces: Optional[int] = None
    bbox: Optional[list] = None
    manifold_antes: Optional[bool] = None
    manifold_depois_reparo: Optional[bool] = None
    reparo_ok: Optional[bool] = None
    erros: list = field(default_factory=list)
    saida_raw: Optional[dict] = None

    def to_dict(self) -> dict:
        return asdict(self)


def reparo_leve(mesh):
    """Reparo leve canônico do benchmark: merge_vertices + fill_holes (trimesh)."""
    import trimesh

    m = mesh.copy()
    m.merge_vertices()
    trimesh.repair.fill_holes(m)
    return m


class BaseGenerator(ABC):
    """Interface de plugin (ADR-001). Mesmos gates para todos os modos."""

    mode: str = "base"
    model: str = "?"
    vram_min_free_mib: int = 10_000
    runner_script: str = ""

    @abstractmethod
    def _build_env(self) -> dict:
        ...

    def generate(
        self, image_path: str, output_dir: str, params: Optional[dict] = None
    ) -> GenerationReport:
        params = dict(params or {})
        os.makedirs(output_dir, exist_ok=True)
        runner = os.path.join(WORKDIR, os.path.basename(self.runner_script))
        report = GenerationReport(
            mode=self.mode, model=self.model, image=image_path, seed=params.get("seed")
        )

        with GpuJobContext(min_free_mib=self.vram_min_free_mib, job_name=self.mode):
            poller = VramPoller(interval_s=1.0)
            poller.start()
            t0 = time.time()
            env = dict(os.environ)
            env.update(self._build_env())
            cmd = [
                VENVPY,
                runner,
                "--image",
                image_path,
                "--output-dir",
                output_dir,
            ]
            if params.get("seed") is not None:
                cmd += ["--seed", str(params["seed"])]
            proc = subprocess.run(
                cmd, capture_output=True, text=True, env=env, cwd=WORKDIR
            )
            report.tempo_s = round(time.time() - t0, 2)
            peak = poller.stop()
            report.vram_pico_mib = peak.used_mib
            report.vram_baseline_mib = peak.baseline_mib

        if proc.returncode != 0:
            report.erros.append(
                f"runner_exit_{proc.returncode}: {proc.stderr.strip()[-2000:]}"
            )
            return report

        raw = None
        for line in reversed(proc.stdout.splitlines()):
            if line.startswith("REPORT_JSON="):
                raw = json.loads(line[len("REPORT_JSON=") :])
                break
        if raw is None:
            report.erros.append("runner sem REPORT_JSON no stdout")
            return report
        report.saida_raw = raw
        report.erros.extend(raw.get("erros", []))
        report.tempo_load_s = raw.get("tempo_load_s")
        report.tempo_run_s = raw.get("tempo_run_s")
        report.vertices = raw.get("vertices")
        report.faces = raw.get("faces")
        report.bbox = raw.get("bbox")

        mesh_path = raw.get("obj")
        report.mesh_path = mesh_path
        if not mesh_path or not os.path.isfile(mesh_path):
            report.erros.append("mesh de saida ausente")
            return report

        import trimesh

        mesh = trimesh.load(mesh_path, force="mesh", process=False)
        report.manifold_antes = bool(mesh.is_watertight)
        try:
            reparada = reparo_leve(mesh)
            out_rep = os.path.join(output_dir, "mesh_reparada.obj")
            reparada.export(out_rep)
            report.mesh_reparada_path = out_rep
            report.manifold_depois_reparo = bool(reparada.is_watertight)
            report.reparo_ok = report.manifold_depois_reparo
            report.vertices = int(len(reparada.vertices))
            report.faces = int(len(reparada.faces))
        except Exception as e:  # noqa: BLE001
            report.erros.append(f"reparo_leve: {type(e).__name__}: {e}")
            report.reparo_ok = False
        return report


def sync_runner(script_name: str) -> None:
    """Copia o runner do repo (Windows) para o workdir WSL antes do job (I/O leve)."""
    import shutil

    src = os.path.join(REPO_GENERATOR, script_name)
    dst = os.path.join(WORKDIR, script_name)
    shutil.copyfile(src, dst)
