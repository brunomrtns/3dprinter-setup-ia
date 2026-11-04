"""Plugin TRELLIS (ADR-001): mesma interface de todos os geradores."""
from __future__ import annotations

import os

from base_plugin import BaseGenerator, sync_runner


class TrellisGenerator(BaseGenerator):
    mode = "trellis"
    model = "microsoft/TRELLIS-image-large"
    runner_script = "trellis_runner.py"
    vram_min_free_mib = 10_000

    def _build_env(self) -> dict:
        return {
            "ATTN_BACKEND": "flash-attn",
            "SPCONV_ALGO": "native",
            "TRELLIS_HOME": os.path.expanduser("~/tools/TRELLIS"),
        }

    def prepare(self) -> None:
        sync_runner(self.runner_script)
