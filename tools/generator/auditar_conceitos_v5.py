#!/usr/bin/env python3
"""
tools/generator/auditar_conceitos_v5.py — Auditoria retroativa do gate anti-grade (RUN mega_v5, CPU-only).
Varre todas as imagens de conceito existentes no game-concerto, grava sidecar .gate.json e
gera evidence/fase-p/gate-anti-grade/auditoria_retroativa_v5.{json,md}.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gate_concept_image import evaluate_image  # noqa: E402

CONCERTO = Path("/mnt/c/Users/Bruno/workspace/game-concerto")
FAB3D = Path("/mnt/c/Users/Bruno/workspace/3dprinter-setup-ia")
OUT_DIR = FAB3D / "evidence" / "fase-p" / "gate-anti-grade"

DIRS = [
    "evidence/concepts/c5_props",
    "evidence/concepts/c5_props_batch2",
    "evidence/concepts/c5_personagens",
    "evidence/concepts/c5_personagens_flux",
    "director_review/2026-11-22_c5_conceitos_porca_dez",
    "director_review/2026-11-22_c5_conceitos_porca_dez_flux",
    "director_review/2026-11-22_ab_gerador_imagem",
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = []
    for rel in DIRS:
        d = CONCERTO / rel
        if d.is_dir():
            targets.extend(sorted(d.glob("*.png")))

    rows = []
    for p in targets:
        res = evaluate_image(p, write_sidecar=True)
        rel_p = str(p.relative_to(CONCERTO))
        is_sheet = ("sheet" in p.name.lower()) or ("painel" in p.name.lower())
        rows.append({
            "path": rel_p,
            "raw_url": f"https://raw.githubusercontent.com/brunomrtns/concerto/main/{rel_p}",
            "is_contact_sheet": is_sheet,
            "gate_pass": res["gate_pass"],
            "n_componentes": res["n_componentes"],
            "calhas": res["calhas"],
            "corte": res["corte"],
            "max_border_touch_pct": res["max_border_touch_pct"],
            "razao": res["razao"],
            "backend": res["backend"],
        })

    (OUT_DIR / "auditoria_retroativa_v5.json").write_text(
        json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# Auditoria Retroativa — Gate Anti-Grade (`RUN mega_v5`, CPU-only)",
        "",
        "| Imagem | Tipo | Veredito | Comps | Calhas | Corte | Razão |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :--- |",
    ]
    for r in rows:
        tipo = "Contact Sheet (ref. humana)" if r["is_contact_sheet"] else "Individual (candidata 3D)"
        verd = "PASS" if r["gate_pass"] else "FAIL"
        lines.append(
            f"| `{r['path']}` | {tipo} | **{verd}** | {r['n_componentes']} | {r['calhas']} | {r['corte']} | {r['razao']} |"
        )
    (OUT_DIR / "auditoria_retroativa_v5.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    passed = sum(1 for r in rows if r["gate_pass"])
    failed = sum(1 for r in rows if not r["gate_pass"])
    ind_fail = [r for r in rows if (not r["gate_pass"]) and (not r["is_contact_sheet"])]
    print(f"TOTAL={len(rows)} | PASS={passed} | FAIL={failed} | INDIVIDUAIS_FAIL={len(ind_fail)}")
    for r in rows:
        tag = "PASS" if r["gate_pass"] else ("SHEET-FAIL(esperado)" if r["is_contact_sheet"] else "INDIV-FAIL!")
        print(f"{tag:20s} | {r['path']} | comps={r['n_componentes']} calhas={r['calhas']} corte={r['corte']} | {r['razao']}")


if __name__ == "__main__":
    main()
