"""Plugin TRELLIS.2 (Fase C) — venv próprio ~.venvs/trellis2 (ADR-004).

Runner shape-only (512³ single-stage — 1024_cascade OOM em 12GB mesmo com
no_grad; ver evidence/fase-c/comparativo-3060/install-notes.md); ATTN_BACKEND=xformers.
"""
from __future__ import annotations

import os

from base_plugin import BaseGenerator, sync_runner


class Trellis2Generator(BaseGenerator):
    mode = "trellis2"
    model = "microsoft/TRELLIS.2-4B"
    runner_script = "trellis2_runner.py"
    vram_min_free_mib = 9_000  # fork com offload (low_vram=True); 12GB com folga
    venv_py = os.path.expanduser("~/.venvs/trellis2/bin/python")

    def _build_env(self) -> dict:
        return {"TRELLIS2_HOME": os.path.expanduser("~/tools/TRELLIS.2")}

    def prepare(self) -> None:
        sync_runner(self.runner_script)
