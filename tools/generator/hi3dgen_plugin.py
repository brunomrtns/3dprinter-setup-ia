"""Plugin Hi3DGen (Fase C / C7-B) — venv próprio ~/.venvs/hi3dgen (ADR-004)."""
from __future__ import annotations

import os

from base_plugin import BaseGenerator, sync_runner


class Hi3DGenGenerator(BaseGenerator):
    mode = "hi3dgen"
    model = "bytedance/Hi3DGen"
    runner_script = "hi3dgen_runner.py"
    vram_min_free_mib = 8_000  # ~7-9 GB de VRAM com offload NiRNE
    venv_py = os.path.expanduser("~/.venvs/hi3dgen/bin/python")

    def _build_env(self) -> dict:
        return {
            "HI3DGEN_HOME": os.path.expanduser("~/tools/Hi3DGen"),
            "SPCONV_ALGO": "native",
        }

    def prepare(self) -> None:
        sync_runner(self.runner_script)
