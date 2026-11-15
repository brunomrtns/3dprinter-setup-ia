"""Teste do guard paramétrico por perfil de máquina (ADR-006).

Roda no WSL com o python do venv (stdlib only):
  tools/setup/py.sh tools/generator/test_gpu_guard_profiles.py
ou, sem venv:
  python3.11 tools/generator/test_gpu_guard_profiles.py
"""
from __future__ import annotations

import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gpu_guard  # noqa: E402

ENVS = ("PRINTER3D_GUARD_MIN_FREE_MIB", "PRINTER3D_MACHINE_PROFILE")


def resolver(*, profile: str | None = None, absolute: str | None = None, arg=None):
    for key in ENVS:
        os.environ.pop(key, None)
    if profile is not None:
        os.environ["PRINTER3D_MACHINE_PROFILE"] = profile
    if absolute is not None:
        os.environ["PRINTER3D_GUARD_MIN_FREE_MIB"] = absolute
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        resultado = gpu_guard.resolve_min_free_mib(arg)
    return resultado, buffer.getvalue()


class TestResolveGuard(unittest.TestCase):
    def setUp(self):
        for key in ENVS:
            os.environ.pop(key, None)

    def tearDown(self):
        for key in ENVS:
            os.environ.pop(key, None)

    def test_default_sem_env_e_3060(self):
        valor, log = resolver()
        self.assertEqual(valor, 10_000)
        self.assertIn("rtx3060-12gb", log)
        self.assertIn("10000", log.replace(".", ""))

    def test_perfil_rtx5060ti(self):
        valor, log = resolver(profile="rtx5060ti-8gb")
        self.assertEqual(valor, 6_500)
        self.assertIn("rtx5060ti-8gb", log)
        self.assertIn("confirmado", log)  # audit Fase A 2026-11-15: livre 6803 MiB > guard 6500

    def test_env_absoluto_vence_perfil(self):
        valor, log = resolver(profile="rtx5060ti-8gb", absolute="7000")
        self.assertEqual(valor, 7_000)
        self.assertNotIn("perfil de máquina", log)

    def test_arg_explicito_vence_tudo(self):
        valor, log = resolver(profile="rtx5060ti-8gb", absolute="7000", arg=10_000)
        self.assertEqual(valor, 10_000)

    def test_perfil_desconhecido_cai_no_default(self):
        valor, log = resolver(profile="gpu-inexistente")
        self.assertEqual(valor, 10_000)
        self.assertIn("não existe", log)

    def test_env_invalido_cai_no_default(self):
        valor, log = resolver(absolute="bananas")
        self.assertEqual(valor, 10_000)
        self.assertIn("não é inteiro", log)

    def test_profiles_json_existe_no_repo(self):
        self.assertTrue(gpu_guard.PROFILES_JSON.is_file(), str(gpu_guard.PROFILES_JSON))
        perfis = gpu_guard._load_profiles()["perfis"]
        self.assertEqual(perfis["rtx3060-12gb"]["guard_min_free_mib"], 10_000)
        self.assertEqual(perfis["rtx5060ti-8gb"]["guard_min_free_mib"], 6_500)
        self.assertEqual(perfis["rtx5060ti-8gb"]["vram_total_mib"], 8151)
        self.assertIn("medido", perfis["rtx5060ti-8gb"]["status"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
