"""Plugin TripoSG (Fase C) — venv próprio ~.venvs/triposg (ADR-004)."""
from __future__ import annotations

import os

from base_plugin import BaseGenerator, sync_runner


class TripoSGGenerator(BaseGenerator):
    mode = "triposg"
    model = "VAST-AI/TripoSG"
    runner_script = "triposg_runner.py"
    vram_min_free_mib = 8_000  # documentado ~8GB de VRAM
    venv_py = os.path.expanduser("~/.venvs/triposg/bin/python")

    def _build_env(self) -> dict:
        return {"TRIPOSG_HOME": os.path.expanduser("~/tools/TripoSG")}

    def prepare(self) -> None:
        sync_runner(self.runner_script)
