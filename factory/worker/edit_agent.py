#!/usr/bin/env python3
"""M6 — Agente de Edição Blindado (Zero args livres do LLM, Whitelist Estrita + Guardrails).

Segurança (Defense-in-Depth):
  1. ZERO strings livres do usuário ou do LLM são passadas para subprocess/CLI.
  2. O LLM só pode escolher uma ação de um enum fechado (`edit_mesh_region`, `revert_previous`, `unsupported`)
     e preencher parâmetros numéricos estritamente limitados (clamped).
  3. Caminhos de arquivo (--input / --output) são 100% controlados pelo worker dentro do workspace do job.
  4. `shell=False` sempre, `seed=42` fixo, máximo 3 passos, timeout 300s, publicação NUNCA permitida.
  5. Prompt injection / comandos de sistema são detectados, bloqueados e logados em `evidence/`.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HUNYUAN_PY = "/home/bruno/.venvs/hunyuan/bin/python"

ALLOWED_TOOLS = {
    "edit_mesh_region": str(REPO_ROOT / "pipeline" / "edit_mesh_region.py"),
    "revert_previous": "builtin:revert_previous",
    "unsupported": "builtin:unsupported",
}

ALLOWED_ANCHORS = {"front_upper_protrusion", "center"}
MAX_STEPS = 3
STEP_TIMEOUT_S = 300

INJECTION_PATTERNS = [
    r"\b(rm|sudo|chmod|chown|curl|wget|ssh|scp|nc|bash|sh|powershell|cmd\.exe|python|eval|exec)\b",
    r"(;|&&|\|\||`|\$\(|/etc/|/root/|~/.ssh|\.env|ignore previous|system prompt)",
]


def _clamp(val: Any, lo: float, hi: float, default: float) -> float:
    try:
        f = float(val)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, f))


def _clamp_vec3(val: Any, lo: float, hi: float, default: tuple[float, float, float]) -> tuple[float, float, float]:
    if isinstance(val, str):
        parts = [p.strip() for p in val.split(",")]
    elif isinstance(val, (list, tuple)):
        parts = list(val)
    else:
        return default
    if len(parts) != 3:
        return default
    return (
        _clamp(parts[0], lo, hi, default[0]),
        _clamp(parts[1], lo, hi, default[1]),
        _clamp(parts[2], lo, hi, default[2]),
    )


def detect_prompt_injection(text: str) -> str | None:
    low = text.lower()
    for pat in INJECTION_PATTERNS:
        m = re.search(pat, low)
        if m:
            return f"BLOCKED_INJECTION: pattern '{m.group(0)}' not allowed"
    return None


def validate_command_whitelist(step: dict[str, Any], job_workspace: Path) -> tuple[bool, str]:
    """Strict closed whitelist check. Only typed actions are permitted."""
    tool = str(step.get("tool", "")).strip()
    if tool not in ALLOWED_TOOLS:
        return False, f"BLOCKED_WHITELIST: tool '{tool}' is not in {sorted(ALLOWED_TOOLS.keys())}"
    return True, "OK"


def build_edit_plan(user_prompt: str, qa_summary: dict[str, Any], provider: str | None = None) -> dict[str, Any]:
    """Generates a strictly typed edit plan via Z.ai GLM Coding Plan or Mock."""
    inj = detect_prompt_injection(user_prompt)
    if inj:
        return {
            "provider": "guardrail:blocked",
            "tokens_used": 0,
            "summary": "Pedido bloqueado pelos guardrails de segurança da Fábrica 3D.",
            "steps": [{"tool": "bash_shell", "reason": inj}],
        }

    # Instant deterministic revert/undo (0 tokens)
    low = user_prompt.lower()
    if any(k in low for k in ("voltar", "reverter", "desfazer", "anterior", "restaurar", "original", "undo", "revert")):
        return {
            "provider": "builtin:revert",
            "tokens_used": 0,
            "summary": "Restaurando o modelo original anterior da peça (8K e 4K intactos).",
            "steps": [{"tool": "revert_previous", "params": {}}],
        }

    prov = (provider or os.environ.get("AGENT_PROVIDER", "mock")).lower()
    api_key = os.environ.get("ZAI_API_KEY", "").strip()

    if prov == "zai" and api_key:
        import httpx

        api_url = os.environ.get("ZAI_API_URL", "https://api.z.ai/api/coding/paas/v4/chat/completions").strip()
        model = os.environ.get("ZAI_MODEL", "glm-4.5-air").strip()
        sys_prompt = (
            "Você é o planejador seguro da Fábrica 3D. Responda APENAS JSON compacto sem markdown:\n"
            '{"summary":"explicação honesta em PT-BR","steps":[{"tool":"edit_mesh_region|revert_previous|unsupported","params":{...}}]}.\n'
            "Regras:\n"
            "- Use 'edit_mesh_region' APENAS para ajuste suave de proporção na protuberância frontal (params: "
            '{"anchor":"front_upper_protrusion","radius":0.05,"scale":[sx,sy,sz],"shift":[dx,dy,dz],"taper":0.25}).\n'
            "- Se o pedido exigir pintura localizada específica (ex: pintar olhos/emblemas/detalhes novos) ou algo que não existe nas ferramentas acima, "
            "use tool='unsupported' e explique honestamente em 'summary' que o recurso ainda não é suportado automaticamente.\n"
            "- NUNCA invente ferramentas, caminhos ou flags."
        )
        r = httpx.post(
            api_url,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": f"Pedido do usuário: {user_prompt[:400]}"},
                ],
                "temperature": 0.1,
                "max_tokens": 300,
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
        parsed = json.loads(txt)
        return {"provider": f"zai:{model}", "tokens_used": usage.get("total_tokens", 0), **parsed}

    # Deterministic MOCK provider
    return {
        "provider": "mock",
        "tokens_used": 0,
        "summary": f"Modo mock ativo para: '{user_prompt[:120]}'. Nenhuma alteração aplicada ao GLB.",
        "steps": [{"tool": "unsupported", "params": {}}],
    }


def execute_edit_request(
    user_prompt: str,
    qa_summary: dict[str, Any],
    job_workspace: Path,
    evidence_dir: Path,
    provider: str | None = None,
    source_glbs: dict[str, Path] | None = None,
) -> dict[str, Any]:
    """Plans, validates strictly typed params, executes safely with shell=False, and logs everything."""
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
            exec_log.append({
                "step": idx,
                "tool": step.get("tool"),
                "blocked": True,
                "reason": step.get("reason") or reason,
            })
            continue

        tool = step["tool"]
        params = step.get("params") if isinstance(step.get("params"), dict) else {}

        if tool == "unsupported":
            exec_log.append({"step": idx, "tool": tool, "blocked": False, "exit_code": 0, "note": "No GLB modified"})
            continue

        if tool == "revert_previous" and source_glbs:
            for variant, src_path in source_glbs.items():
                if src_path.is_file():
                    produced_glbs[variant] = str(src_path)
            exec_log.append({"step": idx, "tool": tool, "blocked": False, "exit_code": 0, "restored": produced_glbs})
            continue

        if tool == "edit_mesh_region" and source_glbs:
            # Strictly clamp every single numeric parameter — ZERO raw LLM strings reach CLI!
            anchor = str(params.get("anchor", "front_upper_protrusion"))
            if anchor not in ALLOWED_ANCHORS:
                anchor = "front_upper_protrusion"
            radius = _clamp(params.get("radius"), 0.03, 0.12, 0.06)
            sx, sy, sz = _clamp_vec3(params.get("scale"), 0.65, 1.50, (0.85, 0.88, 1.18))
            dx, dy, dz = _clamp_vec3(params.get("shift"), -0.06, 0.06, (0.0, 0.0, 0.02))
            taper = _clamp(params.get("taper"), 0.0, 0.60, 0.25)

            safe_args = [
                "--anchor", anchor,
                "--radius", f"{radius:.4f}",
                "--scale", f"{sx:.4f},{sy:.4f},{sz:.4f}",
                "--shift", f"{dx:.4f},{dy:.4f},{dz:.4f}",
                "--taper", f"{taper:.4f}",
            ]

            for variant, src_path in source_glbs.items():
                if not src_path.is_file():
                    continue
                out_path = job_workspace / f"edited_{variant}.glb"
                cmd = [HUNYUAN_PY, ALLOWED_TOOLS[tool], "--input", str(src_path), "--output", str(out_path), *safe_args]
                t0 = time.time()
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=STEP_TIMEOUT_S, shell=False)
                if p.returncode == 0 and out_path.is_file():
                    produced_glbs[variant] = str(out_path)
                exec_log.append({
                    "step": idx,
                    "variant": variant,
                    "tool": tool,
                    "safe_args": safe_args,
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
