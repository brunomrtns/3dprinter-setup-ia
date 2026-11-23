#!/usr/bin/env python3
"""
tools/hooks/enforce_triposg_only.py — Hook Inviolável TripoSG-Only.

Bloqueia (exit 2 em PreToolUse / exit 1 em CLI) qualquer tentativa de geração de
malha 3D usando modelos proibidos (Meshy, Luma, TripoSR, Hunyuan3D-2mv/2.1 shape,
InstantMesh, SF3D, Rodin, etc.). Permite exclusivamente TripoSG para forma 3D.

Uso:
  1. Como PreToolUse hook (JSON via stdin com tool_input.command / CommandLine).
  2. Como validador CLI: python tools/hooks/enforce_triposg_only.py --check-cmd "<comando>"
  3. Como git pre-commit: python tools/hooks/enforce_triposg_only.py --check-staged
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys

# Padrões proibidos para geração de FORMA 3D (exclui explicitamente pintura PBR Hunyuan3D-Paint / TRELLIS.2 PBR)
FORBIDDEN_3D_PATTERNS = [
    (r"\bhunyuan_runner\.py\b", "Hunyuan3D shape runner (proibido — use exclusivamente TripoSG)"),
    (r"tencent/Hunyuan3D-2(mv|\.1)", "Hunyuan3D-2mv/2.1 shape model (proibido — use exclusivamente TripoSG)"),
    (r"\bmeshy(\.ai|_api|-api)?\b", "Meshy (proibido — use exclusivamente TripoSG)"),
    (r"\bluma(labs|_3d|-3d)?\b", "Luma (proibido — use exclusivamente TripoSG)"),
    (r"\btriposr\b", "TripoSR (proibido — use exclusivamente TripoSG)"),
    (r"\btripo3d\.ai\b", "Tripo3D cloud API (proibido — use exclusivamente TripoSG local)"),
    (r"\binstantmesh\b", "InstantMesh (proibido — use exclusivamente TripoSG)"),
    (r"\b(sf3d|stable-fast-3d)\b", "Stable Fast 3D / SF3D (proibido — use exclusivamente TripoSG)"),
    (r"\b(rodin|hyper3d)\b", "Rodin/Hyper3D (proibido — use exclusivamente TripoSG)"),
]


def check_text(text: str) -> list[str]:
    hits = []
    for pattern, reason in FORBIDDEN_3D_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            hits.append(reason)
    return hits


def check_staged_files() -> int:
    res = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, check=False,
    )
    files = [f.strip() for f in res.stdout.splitlines() if f.strip()]
    blocked = []
    for f in files:
        if f.endswith("enforce_triposg_only.py") or f.endswith("CLAUDE.md") or f.endswith("AGENTS.md"):
            continue
        if f.startswith("evidence/") and f.endswith(".json"):
            continue
        if f.endswith((".py", ".sh", ".ps1", ".json")):
            diff = subprocess.run(
                ["git", "diff", "--cached", "--unified=0", "--", f],
                capture_output=True, text=True, check=False,
            ).stdout
            added_lines = "\n".join(
                line[1:] for line in diff.splitlines()
                if line.startswith("+") and not line.startswith("+++")
            )
            hits = check_text(added_lines)
            if hits:
                blocked.append((f, hits))
    if blocked:
        print("[BLOCKED BY enforce_triposg_only] Regra inviolável violada nos arquivos staged:", file=sys.stderr)
        for f, hits in blocked:
            print(f"  - {f}: {', '.join(hits)}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-cmd", default=None, help="Valida uma linha de comando diretamente")
    ap.add_argument("--check-staged", action="store_true", help="Valida arquivos staged no git")
    args = ap.parse_args()

    if args.check_staged:
        return check_staged_files()

    if args.check_cmd is not None:
        hits = check_text(args.check_cmd)
        if hits:
            print(f"[BLOCKED] Geração 3D fora do TripoSG rejeitada: {', '.join(hits)}", file=sys.stderr)
            return 1
        print("[ALLOW] Comando aprovado pela política TripoSG-only.")
        return 0

    # Modo PreToolUse hook (lê JSON via stdin)
    raw = sys.stdin.read().strip()
    if not raw:
        return 0
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        payload = {"raw": raw}

    serialized = json.dumps(payload, ensure_ascii=False)
    hits = check_text(serialized)
    if hits:
        msg = (
            "REGRA INVIOLÁVEL BLOQUEOU ESTA AÇÃO: "
            f"{', '.join(hits)}. "
            "TODA geração de asset 3D / personagem usa EXCLUSIVAMENTE TripoSG. "
            "Se TripoSG não estiver disponível, PARE e pergunte ao dono."
        )
        print(msg, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
