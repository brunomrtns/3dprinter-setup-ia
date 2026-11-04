"""Plugin TripoSR (modo legado) — mesma interface, com shim torchmcubes via PYTHONPATH."""
from __future__ import annotations

import os

from base_plugin import BaseGenerator, sync_runner

SHIM_DIR = os.path.expanduser("~/printer3d-work/shim")


class TripoSRGenerator(BaseGenerator):
    mode = "triposr"
    model = "stabilityai/TripoSR"
    runner_script = "triposr_runner.py"
    vram_min_free_mib = 6_000  # pico medido: ~4.3 GiB (evidence/fase1)

    def _build_env(self) -> dict:
        return {
            "TRIPOSR_HOME": os.path.expanduser("~/tools/TripoSR"),
            "PYTHONPATH": SHIM_DIR,  # shim torchmcubes (skimage) — nunca instalado no venv
        }

    def prepare(self) -> None:
        sync_runner(self.runner_script)
