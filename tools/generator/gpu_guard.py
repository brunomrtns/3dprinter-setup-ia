"""Guard de VRAM + fila serial de GPU + poller de pico (requisito de design).

Realidade medida (audit Fase 1): VRAM total 12.288 MiB, desktop Windows consome
~1,2-1,8 GiB em repouso; TRELLIS pico 11.947 MiB. Jobs de GPU são SERIALIZADOS
(lock de arquivo) e só despacham com VRAM livre >= threshold; abaixo disso,
registra aviso e AGUARDA com re-tentativa periódica.

O threshold é PARAMÉTRICO por perfil de máquina (ADR-006), resolvido nesta ordem:
1. Argumento explícito (`min_free_mib=`) — vence tudo (plugins da 3060 continuam
   idênticos: trellis 10.000, triposr 6.000);
2. Env `PRINTER3D_GUARD_MIN_FREE_MIB` (inteiro);
3. Env `PRINTER3D_MACHINE_PROFILE` → chave em `docs/operations/machine-profiles/profiles.json`;
4. Perfil default do profiles.json (hoje: rtx3060-12gb → 10.000 MiB, comportamento
   histórico desta máquina — backward compat garantido);
5. Fallback 10.000 MiB se profiles.json não existir/corromper (aviso no log).
"""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

LOCK_PATH = os.path.expanduser("~/printer3d-work/gpu.serial.lock")

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES_JSON = REPO_ROOT / "docs" / "operations" / "machine-profiles" / "profiles.json"
DEFAULT_MIN_FREE_MIB = 10_000  # comportamento histórico da rtx3060-12gb


def _load_profiles() -> dict:
    try:
        with open(PROFILES_JSON, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        print(
            f"[gpu_guard] AVISO: profiles.json indisponível ({exc}); "
            f"usando default {DEFAULT_MIN_FREE_MIB} MiB (perfil rtx3060-12gb)"
        )
        return {}


def resolve_min_free_mib(min_free_mib: int | None = None) -> int:
    """Resolve o threshold do guard (ordem na docstring do módulo)."""
    if min_free_mib is not None:
        return int(min_free_mib)

    env_abs = os.environ.get("PRINTER3D_GUARD_MIN_FREE_MIB")
    if env_abs:
        try:
            return int(env_abs)
        except ValueError:
            print(
                f"[gpu_guard] AVISO: PRINTER3D_GUARD_MIN_FREE_MIB='{env_abs}' "
                "não é inteiro; ignorando"
            )

    profiles = _load_profiles()
    perfis = profiles.get("perfis", {})
    profile_name = os.environ.get("PRINTER3D_MACHINE_PROFILE") or profiles.get("default")
    if profile_name and profile_name in perfis:
        limite = int(perfis[profile_name]["guard_min_free_mib"])
        status = perfis[profile_name].get("status", "")
        print(
            f"[gpu_guard] perfil de máquina: {profile_name} → guard {limite} MiB "
            f"({status})"
        )
        return limite

    if profile_name:
        print(
            f"[gpu_guard] AVISO: perfil '{profile_name}' não existe em "
            f"{PROFILES_JSON}; usando default {DEFAULT_MIN_FREE_MIB} MiB"
        )
    else:
        print(f"[gpu_guard] AVISO: nenhum perfil; usando default {DEFAULT_MIN_FREE_MIB} MiB")
    return DEFAULT_MIN_FREE_MIB


def query_vram_mib() -> tuple[int, int]:
    """(used_mib, free_mib) via nvidia-smi. Falha → levanta (não inventar número)."""
    out = subprocess.run(
        [
            "nvidia-smi",
            "--query-gpu=memory.used,memory.free",
            "--format=csv,noheader,nounits",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    used, free = (int(x.strip()) for x in out.stdout.strip().splitlines()[0].split(","))
    return used, free


def wait_for_vram(
    min_free_mib: int | None = None,
    poll_s: float = 10.0,
    max_wait_s: float | None = None,
    log=print,
) -> int:
    """Aguarda até haver VRAM livre suficiente. Retorna free_mib no despacho.

    min_free_mib=None → resolve pelo perfil de máquina (ADR-006)."""
    min_free_mib = resolve_min_free_mib(min_free_mib)
    t0 = time.time()
    waited = False
    while True:
        _used, free = query_vram_mib()
        if free >= min_free_mib:
            if waited:
                log(f"[gpu_guard] liberou: free={free} MiB (>= {min_free_mib})")
            return free
        waited = True
        elapsed = int(time.time() - t0)
        log(
            f"[gpu_guard] AVISO: VRAM livre {free} MiB < {min_free_mib} exigidos; "
            f"aguardando (poll {poll_s:.0f}s, já {elapsed}s)"
        )
        if max_wait_s is not None and time.time() - t0 > max_wait_s:
            raise TimeoutError(
                f"gpu_guard: VRAM livre insuficiente por mais de {max_wait_s}s"
            )
        time.sleep(poll_s)


@dataclass
class VramPeak:
    used_mib: int
    baseline_mib: int


class VramPoller:
    """Amostra memory.used a 1 Hz em thread; stop() devolve o pico (Pendência #2: medir)."""

    def __init__(self, interval_s: float = 1.0):
        self.interval_s = interval_s
        self._samples: list[int] = []
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def _loop(self):
        while not self._stop.is_set():
            try:
                used, _free = query_vram_mib()
                with self._lock:
                    self._samples.append(used)
            except Exception:  # noqa: BLE001
                pass
            self._stop.wait(self.interval_s)

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> VramPeak:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        with self._lock:
            samples = list(self._samples)
        if not samples:
            return VramPeak(used_mib=0, baseline_mib=0)
        return VramPeak(used_mib=max(samples), baseline_mib=samples[0])


@contextmanager
def serial_gpu_lock(timeout_s: float = 7200.0):
    """Fila serial ÚNICA de jobs GPU (cross-process, flock no WSL)."""
    os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
    with open(LOCK_PATH, "w") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("[gpu_guard] fila serial: aguardando job GPU anterior terminar...")
            deadline = time.time() + timeout_s
            while True:
                try:
                    fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.time() > deadline:
                        raise TimeoutError("gpu_guard: fila serial excedeu timeout")
                    time.sleep(5)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


@contextmanager
def GpuJobContext(min_free_mib: int | None = None, job_name: str = "gpu_job"):
    """Sequência canônica: lock serial → guard de VRAM → (job com poller externo).

    min_free_mib=None → resolve pelo perfil de máquina (ADR-006)."""
    with serial_gpu_lock():
        free = wait_for_vram(min_free_mib=min_free_mib)
        print(f"[gpu_guard] {job_name}: liberado com {free} MiB livres")
        try:
            yield
        finally:
            try:
                used, free_after = query_vram_mib()
                print(f"[gpu_guard] {job_name}: fim, VRAM used={used} free={free_after}")
            except Exception:  # noqa: BLE001
                pass


if __name__ == "__main__":
    # Comando canônico do guard (README §Comandos canônicos):
    #   tools/setup/py.sh tools/generator/gpu_guard.py
    # Mostra o perfil resolvido, o threshold e a VRAM atual. Sai com erro
    # (exit 2) se a VRAM livre está abaixo do threshold; exit 0 caso contrário.
    limite = resolve_min_free_mib()
    try:
        used, free = query_vram_mib()
    except Exception as exc:  # noqa: BLE001
        print(f"[gpu_guard] ERRO ao consultar VRAM via nvidia-smi: {exc}")
        sys.exit(1)
    print(f"[gpu_guard] VRAM used={used} MiB free={free} MiB threshold={limite} MiB")
    if free < limite:
        print("[gpu_guard] INSUFICIENTE — não iniciar job GPU (aguardar/liberar)")
        sys.exit(2)
    print("[gpu_guard] OK para despachar job GPU")
