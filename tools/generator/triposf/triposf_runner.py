#!/usr/bin/env python3
"""Runner TripoSF (refino) — venv ~/venvs/triposf (TRIPOSF_PY/TRIPOSF_HOME sobrescrevem). Versionado em tools/generator/triposf/.

Contrato (espelha triposg_runner.py do C3): roda o inference.py OFICIAL do repo
TripoSF como subprocesso, mede pico de VRAM com poller nvidia-smi 1Hz, aplica o
GUARD de 10.000 MiB (pico acima = mata o job, marca BLOQUEADO), e emite
REPORT_JSON=... na última linha.

Uso:
  triposf_bench.py --mesh-path <obj> --output-dir <dir> --config <yaml> --label <nome>
"""
import argparse
import fcntl
import json
import os
import re
import subprocess
import threading
import time

TRIPOSF_HOME = os.environ.get("TRIPOSF_HOME") or os.path.expanduser("~/tools/TripoSF")
VENV_PY = os.environ.get("TRIPOSF_PY") or os.path.expanduser("~/venvs/triposf/bin/python")
LOCK_PATH = os.path.expanduser("~/printer3d-work/gpu.serial.lock")
GUARD_PEAK_MIB = int(os.environ.get("TRIPOSF_GUARD_PEAK_MIB", "11000"))  # c/ reclaim_windows_vram baseline ~500MiB (11GB seguro na 3060 12GB)
GUARD_MIN_FREE_MIB = 8_000   # pré-despacho: GPU ociosa
POLL_S = 1.0


def query_vram():
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    used, total = (int(x) for x in out.split(","))
    return used, total


class VramPoller(threading.Thread):
    def __init__(self, csv_path):
        super().__init__(daemon=True)
        self.csv_path = csv_path
        self.peak = 0
        self.baseline = None
        self.samples = []
        self._halt = threading.Event()
        self.kill_event = threading.Event()

    def run(self):
        with open(self.csv_path, "w", buffering=1) as fh:
            fh.write("ts,used_mib\n")
            while not self._halt.is_set():
                try:
                    used, _total = query_vram()
                except Exception:
                    used = 0
                if self.baseline is None:
                    self.baseline = used
                self.peak = max(self.peak, used)
                self.samples.append(used)
                fh.write(f"{time.time():.1f},{used}\n")
                if used > GUARD_PEAK_MIB:
                    self.kill_event.set()
                self._halt.wait(POLL_S)

    def stop(self):
        self._halt.set()
        self.join(timeout=5)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mesh-path", required=True)
    ap.add_argument("--output-dir", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--label", required=True)
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    log_path = os.path.join(os.path.abspath(args.output_dir), "log.txt")
    csv_path = os.path.join(os.path.abspath(args.output_dir), "vram.csv")
    report_path = os.path.join(os.path.abspath(args.output_dir), "report.json")

    report = {"label": args.label, "mesh_path": args.mesh_path, "config": args.config, "erros": []}

    # lock serial da GPU (mesmo arquivo do guard do repo — jobs nunca em paralelo)
    lock_fh = open(LOCK_PATH, "w")
    fcntl.flock(lock_fh, fcntl.LOCK_EX)

    # pré-despacho: esperar VRAM livre >= guard (desktop Windows consome ~1.7GB)
    t_wait = time.time()
    while True:
        used, total = query_vram()
        free = total - used
        if free >= GUARD_MIN_FREE_MIB:
            break
        print(f"[guard] VRAM livre {free} MiB < {GUARD_MIN_FREE_MIB}; aguardando 5s...")
        time.sleep(5)
    report["vram_wait_s"] = round(time.time() - t_wait, 1)
    report["vram_baseline_mib"] = used

    env = dict(os.environ)
    env["ATTN_BACKEND"] = "xformers"
    env["PYTHONUNBUFFERED"] = "1"
    env["SPARSE_ATTN_BACKEND"] = "xformers"

    cmd = [
        VENV_PY, "inference.py",
        "--mesh-path", args.mesh_path,
        "--output-dir", args.output_dir,
        "--config", args.config,
    ]

    poller = VramPoller(csv_path)
    poller.start()

    t0 = time.time()
    with open(log_path, "w") as log_fh:
        proc = subprocess.Popen(cmd, cwd=TRIPOSF_HOME, env=env, stdout=log_fh, stderr=subprocess.STDOUT)
        killed_by_guard = False
        while proc.poll() is None:
            if poller.kill_event.is_set() and not killed_by_guard:
                killed_by_guard = True
                report["erros"].append(
                    f"GUARD_VRAM_EXCEDIDO: pico {poller.peak} MiB > {GUARD_PEAK_MIB} MiB — job morto"
                )
                proc.kill()
            time.sleep(0.5)
        code = proc.returncode
    poller.stop()
    report["tempo_total_s"] = round(time.time() - t0, 2)
    report["exit_code"] = code
    report["vram_pico_mib"] = poller.peak
    report["guard_tripped"] = poller.kill_event.is_set()

    # tempos internos impressos pelo inference.py oficial
    try:
        log_txt = open(log_path).read()
        m = re.search(r"Mesh Normalizing Time: ([\d.]+)", log_txt)
        if m:
            report["tempo_normalize_s"] = float(m.group(1))
        m = re.search(r"Mesh Loading Time: ([\d.]+)", log_txt)
        if m:
            report["tempo_load_s"] = float(m.group(1))
        m = re.search(r"Mesh Reconstructing Time: ([\d.]+)", log_txt)
        if m:
            report["tempo_recon_s"] = float(m.group(1))
    except OSError:
        pass

    # estatísticas da mesh de saída (contrato dos runners do benchmark)
    if code == 0 and not report["guard_tripped"]:
        try:
            import trimesh  # venv triposf tem trimesh 4.5.3
            name = os.path.split(args.mesh_path)[-1].split(".")[0]
            recon = os.path.join(args.output_dir, f"{name}_reconstruction.obj")
            mesh = trimesh.load(recon, process=False, force="mesh")
            report["mesh_recon"] = recon
            report["vertices"] = int(len(mesh.vertices))
            report["faces"] = int(len(mesh.faces))
            report["bbox"] = [round(float(v), 4) for v in mesh.bounding_box.extents]
            report["watertight"] = bool(mesh.is_watertight)
        except Exception as e:  # noqa: BLE001
            report["erros"].append(f"stats_falhou: {type(e).__name__}: {str(e)[:200]}")

    fcntl.flock(lock_fh, fcntl.LOCK_UN)
    lock_fh.close()

    with open(report_path, "w") as fh:
        json.dump(report, fh, indent=1)
    print("REPORT_JSON=" + json.dumps(report))
    return 0 if (code == 0 and not report["guard_tripped"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
