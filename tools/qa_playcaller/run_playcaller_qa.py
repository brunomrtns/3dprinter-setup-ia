#!/usr/bin/env python3
"""
Driver MCP real para Playcaller (uvx --with mcp<2 playcaller):
  - GATE 2: playcaller_get_editor_state + playcaller_screenshot -> captures/qa/playcaller_conexao.png
  - GATE 4: sessao jogada pela IA no Ato 1 (Caldeiral) por >= 125s (spawn -> mover -> pular -> pause -> voltar)
            gravada via Unity Recorder -> captures/qa/sessao_playcaller.mp4
"""
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(r"C:\Users\Bruno\workspace\game-concerto")
UNITY_DIR = REPO_ROOT / "unity"
QA_DIR = REPO_ROOT / "captures" / "qa"
CONN_PNG = QA_DIR / "playcaller_conexao.png"
REPORT_JSON = QA_DIR / "playcaller_session_report.json"
UNITY_EXE = r"C:\Program Files\Unity\Hub\Editor\6000.3.26f1\Editor\Unity.exe"


class McpStdioClient:
    def __init__(self, cmd, cwd):
        self.proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        self._id = 0
        self._q = queue.Queue()
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()

    def _read_loop(self):
        try:
            for line in self.proc.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    self._q.put(msg)
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass

    def _send(self, obj):
        self.proc.stdin.write(json.dumps(obj, ensure_ascii=False) + "\n")
        self.proc.stdin.flush()

    def _read_response(self, expected_id, timeout=30.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            remaining = max(0.05, deadline - time.time())
            try:
                msg = self._q.get(timeout=min(0.5, remaining))
            except queue.Empty:
                if self.proc.poll() is not None:
                    err = self.proc.stderr.read()
                    raise RuntimeError(f"MCP server exited ({self.proc.returncode}): {err}")
                continue
            if msg.get("id") == expected_id:
                if "error" in msg:
                    raise RuntimeError(f"MCP error: {msg['error']}")
                return msg.get("result")
        raise TimeoutError(f"MCP timeout esperando resposta id={expected_id}")

    def request(self, method, params=None, timeout=30.0):
        self._id += 1
        req_id = self._id
        self._send({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}})
        return self._read_response(req_id, timeout=timeout)

    def notify(self, method, params=None):
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def call_tool(self, name, arguments=None, timeout=30.0):
        res = self.request("tools/call", {"name": name, "arguments": arguments or {}}, timeout=timeout)
        texts = []
        if isinstance(res, dict):
            for c in res.get("content", []):
                if isinstance(c, dict) and c.get("type") == "text":
                    texts.append(c.get("text", ""))
        return "\n".join(texts), bool(res.get("isError", False)) if isinstance(res, dict) else False

    def close(self):
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass


def extract_png_path(text: str):
    m = re.search(r'([A-Za-z]:[\\/][^\s"\'<>|]+\.png|/[^\s"\'<>|]+\.png)', text)
    return Path(m.group(1)) if m else None


def main():
    QA_DIR.mkdir(parents=True, exist_ok=True)
    duration_target = int(os.environ.get("QA_SESSION_SEC", "124"))

    temp_dir = UNITY_DIR / "Temp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    unity_log = UNITY_DIR / "Logs" / "qa_playcaller_unity.log"

    print(f"[Playcaller QA] Abrindo Unity Editor em {UNITY_DIR}...", flush=True)
    unity_proc = subprocess.Popen(
        [UNITY_EXE, "-projectPath", str(UNITY_DIR), "-logFile", str(unity_log)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    print("[Playcaller QA] Iniciando servidor MCP `uvx --with mcp<2 playcaller`...", flush=True)
    client = McpStdioClient(["uvx", "--with", "mcp<2", "playcaller"], cwd=UNITY_DIR)
    report = {
        "gate2_editor_state": None,
        "gate2_screenshot_tool": None,
        "gate2_screenshot_saved": False,
        "gate4_duration_sec": 0.0,
        "gate4_cycles": 0,
        "gate4_actions_count": 0,
        "gate4_console_errors": "",
        "gate4_console_warnings": "",
        "gate4_dez_positions": [],
        "gate4_key_responses": [],
    }

    try:
        init_res = client.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "concerto-qa-driver", "version": "1.0.0"},
            },
            timeout=60.0,
        )
        print("[Playcaller QA] MCP initialized:", init_res.get("serverInfo"), flush=True)
        client.notify("notifications/initialized")

        editor_state_txt = ""
        for attempt in range(24):
            if unity_proc.poll() is not None:
                raise RuntimeError(f"Unity Editor encerrou prematuramente (exit={unity_proc.returncode}). Ver {unity_log}")
            txt, is_err = client.call_tool("playcaller_get_editor_state", {}, timeout=25.0)
            if not is_err and "not connected" not in txt.lower() and "failed" not in txt.lower():
                editor_state_txt = txt
                print(f"[Playcaller QA] Unity conectado (tentativa {attempt + 1}): {txt}", flush=True)
                if '"isCompiling": true' not in txt and '"isCompiling":true' not in txt:
                    break
            else:
                print(f"[Playcaller QA] Aguardando Unity ({attempt + 1}/36): {txt[:140]}", flush=True)
            time.sleep(2.5)

        if not editor_state_txt:
            raise RuntimeError("Unity Editor nao conectou ao Playcaller dentro do tempo limite.")

        report["gate2_editor_state"] = editor_state_txt

        # Ajusta Game View para 1280x720 (16:9) antes de entrar em Play Mode
        try:
            gv_txt, _ = client.call_tool("playcaller_set_game_view_size", {"width": 1280, "height": 720}, timeout=15.0)
            print("[Playcaller QA] GameView 1280x720:", gv_txt, flush=True)
        except Exception as exc:
            print(f"[Playcaller QA] Aviso set_game_view_size: {exc}", flush=True)

        if '"isPlaying": true' in editor_state_txt or '"isPlaying":true' in editor_state_txt:
            client.call_tool("playcaller_playmode", {"action": "stop"}, timeout=20.0)
            time.sleep(2.0)

        txt, _ = client.call_tool("playcaller_execute_menu_item", {"menuPath": "CONCERTO/QA/Open Act 1 Caldeiral"}, timeout=20.0)
        print("[Playcaller QA] Open Act 1:", txt, flush=True)
        time.sleep(1.5)

        txt, is_err = client.call_tool("playcaller_playmode", {"action": "play"}, timeout=30.0)
        print("[Playcaller QA] Play Mode start:", txt, flush=True)
        if is_err:
            raise RuntimeError(f"Falha ao iniciar Play Mode: {txt}")

        time.sleep(4.0)
        for _ in range(15):
            st, st_err = client.call_tool("playcaller_get_editor_state", {}, timeout=20.0)
            if not st_err and ('"isPlaying": true' in st or '"isPlaying":true' in st):
                report["gate2_editor_state"] = st
                break
            time.sleep(1.5)

        # GATE 2: Screenshot 1280x720 limpa via playcaller_screenshot
        shot_txt, shot_err = client.call_tool("playcaller_screenshot", {}, timeout=20.0)
        shot_tool = "playcaller_screenshot"
        png_path = extract_png_path(shot_txt) if not shot_err else None
        if not png_path or not png_path.exists():
            shot_txt, shot_err = client.call_tool("playcaller_read_gameview_pixels", {}, timeout=20.0)
            shot_tool = "playcaller_read_gameview_pixels"
            png_path = extract_png_path(shot_txt) if not shot_err else None

        if png_path and png_path.exists():
            shutil.copy2(png_path, CONN_PNG)
            report["gate2_screenshot_tool"] = shot_tool
            report["gate2_screenshot_saved"] = True
            print(f"[Playcaller QA] GATE 2 screenshot salva em {CONN_PNG} (via {shot_tool})", flush=True)
        else:
            raise RuntimeError(f"GATE 2 falhou ao capturar screenshot: {shot_txt}")

        # Inspeciona Dez antes da gravacao
        try:
            go_txt, go_err = client.call_tool("playcaller_get_gameobject", {"path": "Player_Dez_Placeholder"}, timeout=20.0)
            if not go_err:
                report["gate4_dez_positions"].append({"t": 0.0, "info": go_txt[:260]})
        except Exception as exc:
            print(f"[Playcaller QA] get_gameobject inicial aviso: {exc}", flush=True)

        # Limpa console antes da sessao de 2+ minutos (GATE 4)
        client.call_tool("playcaller_console_log", {"count": 10, "level": "all", "clear": True}, timeout=20.0)

        # Inicia Unity Recorder MP4 (intervalo automatico 0..125s para flush garantido do moov atom)
        rec_txt, _ = client.call_tool("playcaller_execute_menu_item", {"menuPath": "CONCERTO/QA/Start Recorder MP4"}, timeout=20.0)
        print("[Playcaller QA] Start Recorder:", rec_txt, flush=True)
        time.sleep(1.0)

        # GATE 4: Sessao jogada pela IA >= 124 segundos reais
        t0 = time.time()
        cycle = 0
        actions = 0
        move_keys = ["W", "D", "S", "A"]

        while (time.time() - t0) < duration_target:
            cycle += 1
            for k in move_keys:
                if (time.time() - t0) >= duration_target:
                    break
                try:
                    ktxt, _ = client.call_tool("playcaller_key_press", {"key": k}, timeout=20.0)
                    actions += 1
                    if len(report["gate4_key_responses"]) < 6:
                        report["gate4_key_responses"].append(ktxt)
                except Exception as exc:
                    print(f"[Playcaller QA] key {k} aviso: {exc}", flush=True)
                time.sleep(1.1)

            if (time.time() - t0) >= duration_target:
                break

            # Pular
            try:
                client.call_tool("playcaller_key_press", {"key": "Space"}, timeout=20.0)
                actions += 1
            except Exception as exc:
                print(f"[Playcaller QA] key Space aviso: {exc}", flush=True)
            time.sleep(1.2)

            # Abrir Pause -> aguardar -> Voltar
            try:
                client.call_tool("playcaller_key_press", {"key": "Escape"}, timeout=20.0)
                actions += 1
                time.sleep(1.6)
                client.call_tool("playcaller_key_press", {"key": "Escape"}, timeout=20.0)
                actions += 1
                time.sleep(1.0)
            except Exception as exc:
                print(f"[Playcaller QA] pause toggle aviso: {exc}", flush=True)

            elapsed = time.time() - t0
            print(f"[Playcaller QA] Ciclo {cycle} concluido ({elapsed:.1f}s / {duration_target}s, actions={actions})", flush=True)

        report["gate4_duration_sec"] = round(time.time() - t0, 2)
        report["gate4_cycles"] = cycle
        report["gate4_actions_count"] = actions

        # Aguarda flush automatico do Unity Recorder (125s) e garante Stop
        time.sleep(3.0)
        try:
            stop_rec_txt, _ = client.call_tool("playcaller_execute_menu_item", {"menuPath": "CONCERTO/QA/Stop Recorder MP4"}, timeout=25.0)
            print("[Playcaller QA] Stop Recorder:", stop_rec_txt, flush=True)
        except Exception as exc:
            print(f"[Playcaller QA] Stop Recorder aviso: {exc}", flush=True)
        time.sleep(2.0)

        # Coleta console logs de todo o periodo da sessao
        try:
            err_txt, _ = client.call_tool("playcaller_console_log", {"count": 100, "level": "error", "clear": False}, timeout=25.0)
            warn_txt, _ = client.call_tool("playcaller_console_log", {"count": 100, "level": "warning", "clear": False}, timeout=25.0)
            report["gate4_console_errors"] = err_txt
            report["gate4_console_warnings"] = warn_txt
            print("[Playcaller QA] Console errors:", err_txt[:400], flush=True)
        except Exception as exc:
            print(f"[Playcaller QA] console_log aviso: {exc}", flush=True)

        try:
            client.call_tool("playcaller_playmode", {"action": "stop"}, timeout=25.0)
        except Exception:
            pass
        time.sleep(2.0)

        REPORT_JSON.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[Playcaller QA] CONCLUIDO! Relatorio salvo em {REPORT_JSON}", flush=True)
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
