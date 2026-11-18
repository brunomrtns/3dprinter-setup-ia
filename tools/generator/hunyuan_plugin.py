"""Plugin Hunyuan3D (Fase C / C6) — venv próprio ~/.venvs/hunyuan (ADR-004).

Suporta:
  - Hunyuan3D-2mv (multi-vista até 4 ângulos: front, left, back, right) quando params
    inclui left/back/right ou variant='mv';
  - Hunyuan3D-2.1 (single-view DiT MoE 4096 latents) quando variant='2.1'.
Com offload por estágio (conditioner -> DiT -> ShapeVAE), cabe com folga na RTX 3060 12GB.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Optional

from base_plugin import BaseGenerator, GenerationReport, WORKDIR, reparo_leve, sync_runner
from gpu_guard import GpuJobContext, VramPoller


class HunyuanGenerator(BaseGenerator):
    mode = "hunyuan"
    model = "tencent/Hunyuan3D-2mv+2.1"
    runner_script = "hunyuan_runner.py"
    vram_min_free_mib = 9_500
    venv_py = os.path.expanduser("~/.venvs/hunyuan/bin/python")

    def _build_env(self) -> dict:
        return {
            "HUNYUAN21_HOME": os.path.expanduser("~/tools/Hunyuan3D-2.1"),
            "HUNYUAN2_HOME": os.path.expanduser("~/tools/Hunyuan3D-2"),
        }

    def prepare(self) -> None:
        sync_runner(self.runner_script)

    def generate(
        self, image_path: str, output_dir: str, params: Optional[dict] = None
    ) -> GenerationReport:
        params = dict(params or {})
        self.prepare()
        os.makedirs(output_dir, exist_ok=True)
        runner = os.path.join(WORKDIR, os.path.basename(self.runner_script))
        report = GenerationReport(
            mode=params.get("mode_override", self.mode),
            model=self.model,
            image=image_path,
            seed=params.get("seed"),
        )

        with GpuJobContext(min_free_mib=self.vram_min_free_mib, job_name=report.mode):
            poller = VramPoller(interval_s=1.0)
            poller.start()
            t0 = time.time()
            env = dict(os.environ)
            env.update(self._build_env())
            cmd = [
                self.venv_py,
                runner,
                "--image",
                image_path,
                "--output-dir",
                output_dir,
            ]
            for extra_key in ("left", "back", "right", "variant", "steps", "octree_res"):
                if params.get(extra_key) is not None:
                    cmd += [f"--{extra_key.replace('_', '-')}", str(params[extra_key])]
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
