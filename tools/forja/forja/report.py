#!/usr/bin/env python3
"""Gravação dos relatórios JSON."""
import json
import os


def salvar(rel: dict, caminho: str) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(caminho)), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(rel, f, ensure_ascii=False, indent=1)
    return caminho
