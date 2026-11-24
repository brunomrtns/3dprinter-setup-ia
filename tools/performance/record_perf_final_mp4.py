#!/usr/bin/env python3
"""
Grava GATE 8 (Pass de Performance): captures/profiler/performance_final.mp4
via Playcaller MCP + Unity Recorder (16s @ 30fps, 1280x720) no pior ato (Ato 1 — Caldeiral).
"""
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, r"C:\Users\Bruno\workspace\3dprinter-setup-ia\tools\qa_playcaller")
from run_playcaller_qa import McpStdioClient, UNITY_DIR, UNITY_EXE  # noqa: E402


def main():
    temp_dir = UNITY_DIR / "Temp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    unity_log = UNITY_DIR / "Logs" / "perf_final_recorder_unity.log"

    print(f"[Perf MP4] Abrindo Unity Editor em {UNITY_DIR}...", flush=True)
    unity_proc = subprocess.Popen(
        [UNITY_EXE, "-projectPath", str(UNITY_DIR), "-logFile", str(unity_log)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    client = McpStdioClient(["uvx", "--with", "mcp<2", "playcaller"], cwd=UNITY_DIR)
    try:
        client.request(
            "initialize",
            {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "concerto-perf-mp4", "version": "1.0.0"}},
            timeout=60.0,
        )
        client.notify("notifications/initialized")

        for attempt in range(24):
            if unity_proc.poll() is not None:
                raise RuntimeError(f"Unity saiu prematuramente ({unity_proc.returncode})")
            txt, is_err = client.call_tool("playcaller_get_editor_state", {}, timeout=25.0)
            if not is_err and "not connected" not in txt.lower() and "failed" not in txt.lower():
                if '"isCompiling": true' not in txt and '"isCompiling":true' not in txt:
                    print(f"[Perf MP4] Unity conectado (tentativa {attempt + 1})", flush=True)
                    break
            time.sleep(2.5)

        client.call_tool("playcaller_set_game_view_size", {"width": 1280, "height": 720}, timeout=15.0)
        client.call_tool("playcaller_execute_menu_item", {"menuPath": "CONCERTO/QA/Open Act 1 Caldeiral"}, timeout=20.0)
        time.sleep(1.5)
        client.call_tool("playcaller_playmode", {"action": "play"}, timeout=30.0)
        time.sleep(4.0)

        rec_txt, _ = client.call_tool("playcaller_execute_menu_item", {"menuPath": "CONCERTO/QA/Start Performance Final Recorder MP4"}, timeout=20.0)
        print("[Perf MP4] Recorder iniciado:", rec_txt, flush=True)

        # Movimenta o Dez suavemente durante 16s no pior ato (sem pausar)
        t0 = time.time()
        keys = ["W", "D", "Space", "S", "A", "Space"]
        idx = 0
        while (time.time() - t0) < 16.5:
            k = keys[idx % len(keys)]
            idx += 1
            try:
                client.call_tool("playcaller_key_press", {"key": k}, timeout=15.0)
            except Exception:
                pass
            time.sleep(1.0)

        time.sleep(2.5)
        try:
            client.call_tool("playcaller_execute_menu_item", {"menuPath": "CONCERTO/QA/Stop Recorder MP4"}, timeout=20.0)
        except Exception:
            pass
        time.sleep(2.0)
        try:
            client.call_tool("playcaller_playmode", {"action": "stop"}, timeout=20.0)
        except Exception:
            pass
        time.sleep(1.5)
        print("[Perf MP4] Gravacao finalizada com sucesso!", flush=True)
    finally:
        client.close()
        try:
            unity_proc.terminate()
            unity_proc.wait(timeout=10)
        except Exception:
            try:
                unity_proc.kill()
            except Exception:
                pass


if __name__ == "__main__":
    main()
