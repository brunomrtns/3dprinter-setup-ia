#!/usr/bin/env python3
"""M6 — Agente de Edição com Whitelist Fechada + Guardrails + Provider Abstraído (Mock / Z.ai GLM).

Regras invioláveis:
  - Whitelist fechada: APENAS scripts de pipeline/ autorizados e blender.
  - seed 42 fixo (não configurável pelo agente).
  - Máximo 10 passos por pedido, timeout 300s por passo.
  - Publicação NUNCA é ação do agente — resultado sempre volta para `review` humano.
  - Toda execução (e toda tentativa bloqueada) é logada em evidence/.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HUNYUAN_PY = "/home/bruno/.venvs/hunyuan/bin/python"

ALLOWED_TOOLS = {
    "run_asset": str(REPO_ROOT / "pipeline" / "run_asset.py"),
    "patch_repair": str(REPO_ROOT / "pipeline" / "patch_repair.py"),
    "photo_blend": str(REPO_ROOT / "pipeline" / "photo_blend.py"),
    "eval_texture": str(REPO_ROOT / "pipeline" / "eval_texture.py"),
    "pack_glb": str(REPO_ROOT / "pipeline" / "pack_glb.py"),
    "edit_mesh_region": str(REPO_ROOT / "pipeline" / "edit_mesh_region.py"),
    "blender": "blender",
}

MAX_STEPS = 10
STEP_TIMEOUT_S = 300


def validate_command_whitelist(step: dict[str, Any], job_workspace: Path) -> tuple[bool, str]:
    """Strict closed whitelist check. Blocks arbitrary shell commands, publish, and path escapes."""
    tool = str(step.get("tool", "")).strip()
    if tool not in ALLOWED_TOOLS:
        return False, f"BLOCKED_WHITELIST: tool '{tool}' is not in {sorted(ALLOWED_TOOLS.keys())}"

    args = [str(a) for a in step.get("args", [])]
    forbidden_flags = {"--auto-publish", "--publish", "deploy.sh", "rm", "curl", "wget", "ssh"}
    for a in args:
        al = a.lower()
        if any(f in al for f in forbidden_flags):
            return False, f"BLOCKED_GUARDRAIL: forbidden argument '{a}'"
        if ".." in a:
            return False, f"BLOCKED_PATH_ESCAPE: '{a}'"

    return True, "OK"


def build_edit_plan(user_prompt: str, qa_summary: dict[str, Any], provider: str | None = None) -> dict[str, Any]:
    """Generates a structured edit plan via Mock (default) or Z.ai GLM when ZAI_API_KEY is configured."""
    prov = (provider or os.environ.get("AGENT_PROVIDER", "mock")).lower()
    api_key = os.environ.get("ZAI_API_KEY", "").strip()

    if prov == "zai" and api_key:
        import httpx

        api_url = os.environ.get("ZAI_API_URL", "https://api.z.ai/api/coding/paas/v4/chat/completions").strip()
        model = os.environ.get("ZAI_MODEL", "glm-4.5-air").strip()
        sys_prompt = (
            "Agente de edição da Fábrica 3D. Responda APENAS JSON compacto sem markdown: "
            '{"summary":"explicação curta em PT-BR","steps":[{"tool":"edit_mesh_region|patch_repair|eval_texture|pack_glb|run_asset","args":[...]}]}. '
            "Para ajustes de forma/geometria localizada (ex: afinar/alongar/reduzir protuberância frontal/superior), use tool 'edit_mesh_region' "
            "com args: ['--anchor','front_upper_protrusion','--radius','0.10','--scale','sx,sy,sz','--shift','dx,dy,dz','--taper','0.35'] "
            "(NÃO passe --input nem --output, o worker injeta os arquivos GLB automaticamente). "
            "Nunca use publish ou ferramentas fora da whitelist."
        )
        r = httpx.post(
            api_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": f"Pedido: {user_prompt}\nQA: {json.dumps(qa_summary)[:800]}"},
                ],
                "temperature": 0.1,
                "max_tokens": 350,
                "thinking": {"type": "disabled"},
            },
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        txt = (data["choices"][0]["message"].get("content") or "").strip()
        if txt.startswith("```"):
            txt = txt.strip("`")
            if txt.startswith("json"):
                txt = txt[4:].strip()
        usage = data.get("usage", {})
        return {"provider": f"zai:{model}", "tokens_used": usage.get("total_tokens", 0), **json.loads(txt)}

    # Deterministic MOCK provider (default for offline/no-key testing)
    low = user_prompt.lower()
    if any(k in low for k in ("rm ", "ssh ", "curl ", "bash", "shell", "apagar servidor", "executar comando")):
        # Deliberately proposes the requested unsafe tool so the whitelist guardrail can be tested end-to-end
        return {
            "provider": "mock",
            "summary": "Tentativa de comando fora da whitelist (deve ser bloqueada pelos guardrails).",
            "steps": [{"tool": "bash_shell", "args": ["-c", user_prompt]}],
        }

    return {
        "provider": "mock",
        "summary": f"Plano de edição determinístico para: '{user_prompt}' (reparo de manchas/patches + reavaliação QA; publicação aguarda aprovação humana).",
        "steps": [
            {"tool": "patch_repair", "args": ["--help"]},
            {"tool": "eval_texture", "args": ["--help"]},
        ],
    }


def execute_edit_request(
    user_prompt: str,
    qa_summary: dict[str, Any],
    job_workspace: Path,
    evidence_dir: Path,
    provider: str | None = None,
    source_glbs: dict[str, Path] | None = None,
) -> dict[str, Any]:
    """Plans, validates against whitelist, executes up to MAX_STEPS, and logs everything to evidence/."""
    evidence_dir.mkdir(parents=True, exist_ok=True)
    plan = build_edit_plan(user_prompt, qa_summary, provider=provider)
    steps = plan.get("steps", [])[:MAX_STEPS]

    exec_log = []
    blocked_count = 0
    produced_glbs: dict[str, str] = {}

    for idx, step in enumerate(steps):
        ok, reason = validate_command_whitelist(step, job_workspace)
        if not ok:
            blocked_count += 1
            entry = {"step": idx, "tool": step.get("tool"), "args": step.get("args"), "blocked": True, "reason": reason}
            exec_log.append(entry)
            continue

        tool = step["tool"]
        raw_args = [str(a) for a in step.get("args", [])]

        if tool == "edit_mesh_region" and source_glbs:
            # Strip any model-supplied --input/--output and apply cleanly to both 8k and 4k GLBs
            clean_args: list[str] = []
            skip_next = False
            for a in raw_args:
                if skip_next:
                    skip_next = False
                    continue
                if a in ("--input", "--output"):
                    skip_next = True
                    continue
                clean_args.append(a)

            for variant, src_path in source_glbs.items():
                if not src_path.is_file():
                    continue
                out_path = job_workspace / f"edited_{variant}.glb"
                cmd = [HUNYUAN_PY, ALLOWED_TOOLS[tool], "--input", str(src_path), "--output", str(out_path), *clean_args]
                t0 = time.time()
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=STEP_TIMEOUT_S)
                if p.returncode == 0 and out_path.is_file():
                    produced_glbs[variant] = str(out_path)
                exec_log.append({
                    "step": idx,
                    "variant": variant,
                    "tool": tool,
                    "cmd": cmd,
                    "blocked": False,
                    "exit_code": p.returncode,
                    "duration_s": round(time.time() - t0, 2),
                    "stdout_tail": p.stdout[-400:],
                    "stderr_tail": p.stderr[-400:],
                })
            continue

        cmd = [ALLOWED_TOOLS[tool], *raw_args] if tool == "blender" else [HUNYUAN_PY, ALLOWED_TOOLS[tool], *raw_args]
        t0 = time.time()
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=STEP_TIMEOUT_S)
        exec_log.append({
            "step": idx,
            "tool": tool,
            "cmd": cmd,
            "blocked": False,
            "exit_code": p.returncode,
            "duration_s": round(time.time() - t0, 2),
            "stdout_tail": p.stdout[-400:],
            "stderr_tail": p.stderr[-400:],
        })

    result = {
        "provider": plan.get("provider", "mock"),
        "tokens_used": plan.get("tokens_used", 0),
        "seed": 42,
        "summary": plan.get("summary", ""),
        "blocked_count": blocked_count,
        "steps_executed": len(exec_log) - blocked_count,
        "produced_glbs": produced_glbs,
        "publish_allowed": False,
        "log": exec_log,
    }
    (evidence_dir / "edit_agent_log.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result
